"""حركية التلاميذ: الوافدون (طلب الملف، التذكير، التوصل) والمغادرون (إرسال الملف).

اقتراح المدير (2026-11-01): يُسجل التلميذ برمز مسار واسمه والمؤسسة الأخرى ومديريتها وأكاديميتها،
وتُولد المراسلة من نماذجه، ويُؤشر على الإرسال، مع تنبيهات بما لم يُرسل.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta

from idara.data.dossier import DossierDonnees
from idara.services import annee as annee_srv
from idara.services import conges as cg
from idara.services import documents as dc
from idara.services import eleves as el
from idara.services import textes as tx
from idara.services.massar import MOTIF_CODE, normaliser
from idara.services.moteur_docx import SUPPRIMER, SUPPRIMER_LIGNE

LIGNES_MAX = 6          # عدد أسطر التلاميذ في المراسلة الواحدة (حسب النموذج)
DELAI_RELANCE = 30      # أيام: طلب دون توصل ← اقتراح التذكير
SENS = {"arrive": "وافد", "parti": "مغادر"}


class ErreurMouvement(ValueError):
    """رسالة موجهة للمدير بالعربية."""


# ---------- صيغ المؤسسات الأخرى ----------

def formule_direction(texte: str) -> str:
    """«إقليم: بركان» (صيغة مسار) ← «المديرية الإقليمية ببركان»."""
    t = " ".join((texte or "").split())
    if not t or t.startswith("المديرية"):
        return t
    for prefixe, liaison in (("إقليم:", "ب"), ("إقليم", "ب"), ("عمالة:", "لعمالة "), ("عمالة", "لعمالة ")):
        if t.startswith(prefixe):
            return f"المديرية الإقليمية {liaison}{t[len(prefixe):].strip()}"
    return f"المديرية الإقليمية ب{t}"


def formule_academie(texte: str) -> str:
    """«الشرق» ← «الأكاديمية الجهوية للتربية والتكوين لجهة الشرق»."""
    t = " ".join((texte or "").split())
    if not t or t.startswith("الأكاديمية") or t.startswith("الاكاديمية"):
        return t
    return f"الأكاديمية الجهوية للتربية والتكوين لجهة {t.removeprefix('جهة ').strip()}"


def formule_etablissement(texte: str) -> str:
    t = " ".join((texte or "").split())
    if t and not t.startswith(("مدرسة", "مجموعة", "م.م", "المدرسة", "ثانوية", "إعدادية")):
        return f"مدرسة {t}"
    return t


def al_tilmidh(sexes: list[str]) -> str:
    n, f = len(sexes), all(s == "F" for s in sexes)
    if n == 1:
        return "التلميذة" if f else "التلميذ"
    if n == 2:
        return "التلميذتين" if f else "التلميذين"
    return "التلميذات" if f else "التلاميذ"


# ---------- التسجيل ----------

@dataclass
class Mouvement:
    sens: str
    code_massar: str
    nom_ar: str = ""
    prenom_ar: str = ""
    sexe: str = ""
    date_mouvement: str = ""
    etablissement: str = ""
    direction: str = ""
    academie: str = ""
    hors_province: bool = False
    niveau: str = ""
    ref_numero: str = ""
    ref_date: str = ""
    remarques: str = ""
    classe: str = ""          # مغادر سابق يُدرج يدوياً: قسمه (اختياري)
    id: int | None = None

    def valider(self) -> None:
        for k in ("nom_ar", "prenom_ar", "etablissement", "direction", "academie", "niveau", "ref_numero",
                  "remarques"):
            setattr(self, k, " ".join((getattr(self, k) or "").split()))
        self.code_massar = (self.code_massar or "").strip().upper()
        if self.sens not in SENS:
            raise ErreurMouvement("اختر: وافد أو مغادر.")
        if not MOTIF_CODE.match(self.code_massar):
            raise ErreurMouvement("رمز مسار غير صحيح (حرف ثم 9 أرقام).")
        if not self.etablissement:
            raise ErreurMouvement("المؤسسة " + ("الأصلية" if self.sens == "arrive" else "المستقبلة") + " إجبارية.")
        if self.hors_province and not (self.direction and self.academie):
            raise ErreurMouvement("خارج الإقليم: المديرية والأكاديمية التابعة لها المؤسسة إجباريتان.")
        for k, lib in (("date_mouvement", "تاريخ التحويل"), ("ref_date", "تاريخ المرجع")):
            v = getattr(self, k)
            if not v and k == "date_mouvement":
                raise ErreurMouvement("تاريخ التحويل إجباري.")
            if v:
                try:
                    if date.fromisoformat(v) > date.today():
                        raise ErreurMouvement(f"{lib} في المستقبل.")
                except ValueError as e:
                    if isinstance(e, ErreurMouvement):
                        raise
                    raise ErreurMouvement(f"{lib} غير صحيح.") from None


def _annee(conn):
    a = annee_srv.annee_courante(conn)
    if a is None:
        raise ErreurMouvement("لا توجد سنة دراسية جارية.")
    return a


def _eleve(conn, mv: Mouvement) -> int:
    """التلميذ برمز مسار؛ يُنشأ إن كان وافداً جديداً لم يرد بعد في لوائح مسار المستوردة."""
    r = conn.execute("SELECT id, nom_ar, prenom_ar FROM eleve WHERE code_massar=?", (mv.code_massar,)).fetchone()
    if mv.sens == "parti":
        return _eleve_parti(conn, mv, r["id"] if r else None)
    if r:
        return r["id"]
    if not (mv.nom_ar and mv.prenom_ar and mv.sexe in ("M", "F")):
        raise ErreurMouvement("تلميذ جديد: النسب والاسم والنوع إجبارية.")
    with conn:
        eid = conn.execute("INSERT INTO eleve(code_massar, nom_ar, prenom_ar, sexe, source) VALUES (?,?,?,?,'massar')",
                           (mv.code_massar, mv.nom_ar, mv.prenom_ar, mv.sexe)).lastrowid
        conn.execute("INSERT INTO inscription(eleve_id, annee_id, classe_id, statut, date_entree, etab_origine) "
                     "VALUES (?,?,?,'arrive',?,?)", (eid, _annee(conn)["id"], _classe_id(conn, mv),
                                                     mv.date_mouvement, mv.etablissement))
    return eid


def _classe_id(conn, mv: Mouvement) -> int | None:
    if not mv.classe.strip():
        return None
    c = conn.execute("SELECT id FROM classe WHERE annee_id=? AND code=?",
                     (_annee(conn)["id"], mv.classe.strip())).fetchone()
    if c is None:
        raise ErreurMouvement("القسم غير موجود في السنة الجارية.")
    return c["id"]


def _eleve_parti(conn, mv: Mouvement, eid: int | None) -> int:
    """مغادر لا يرد في اللائحة المستوردة (غادر قبل استيرادها): يُدرج يدوياً ويُسجَّل في السنة الجارية ثم يُعلَّم
    مغادراً (طلب المدير 2026-11-09)."""
    a = _annee(conn)
    if eid and conn.execute("SELECT 1 FROM inscription WHERE eleve_id=? AND annee_id=?", (eid, a["id"])).fetchone():
        return eid
    code_niv = next((k for k, v in tx.NIVEAUX.items() if v[0] == mv.niveau), None)
    if eid is None and not (mv.nom_ar and mv.prenom_ar and mv.sexe in ("M", "F")):
        raise ErreurMouvement(f"لا يوجد تلميذ برمز {mv.code_massar} في اللوائح. لإدراجه مغادراً: النسب والاسم والنوع "
                              "والمستوى إجبارية.")
    if code_niv is None:
        raise ErreurMouvement("مغادر غير وارد في اللائحة الحالية: اختر مستواه الدراسي.")
    niveau_id = conn.execute("SELECT id FROM niveau WHERE code=?", (code_niv,)).fetchone()
    classe_id = _classe_id(conn, mv)
    with conn:
        if eid is None:
            eid = conn.execute("INSERT INTO eleve(code_massar, nom_ar, prenom_ar, sexe, source) VALUES "
                               "(?,?,?,?,'massar')", (mv.code_massar, mv.nom_ar, mv.prenom_ar, mv.sexe)).lastrowid
        conn.execute("INSERT INTO inscription(eleve_id, annee_id, classe_id, niveau_id, niveau_confirme, statut) "
                     "VALUES (?,?,?,?,1,'inscrit')", (eid, a["id"], classe_id, niveau_id[0] if niveau_id else None))
    return eid


def enregistrer(conn: sqlite3.Connection, mv: Mouvement) -> int:
    mv.valider()
    eid = _eleve(conn, mv)
    fiche = el.fiche(conn, eid)
    if fiche["inscription_id"] is None:
        raise ErreurMouvement("التلميذ غير مسجل في السنة الجارية (استورد لوائح مسار أولاً).")
    if not mv.niveau and fiche["niveau"] in tx.NIVEAUX:
        mv.niveau = tx.niveau_ar(fiche["niveau"])
    a = _annee(conn)
    cols = ("date_mouvement", "etablissement", "direction", "academie", "hors_province", "niveau", "ref_numero",
            "ref_date", "remarques")
    vals = [getattr(mv, k) if getattr(mv, k) != "" else None for k in cols]
    vals[cols.index("hors_province")] = int(mv.hors_province)
    try:
        el.changer_statut(conn, eid, mv.sens, mv.date_mouvement, mv.etablissement)
    except el.ErreurEleve as e:
        raise ErreurMouvement(str(e)) from None
    with conn:
        existant = conn.execute("SELECT id FROM mouvement WHERE eleve_id=? AND annee_id=? AND sens=?",
                                (eid, a["id"], mv.sens)).fetchone()
        if existant and mv.id not in (None, existant["id"]):
            raise ErreurMouvement("هذه الحركة مسجلة من قبل لنفس التلميذ.")
        if existant:
            mv.id = existant["id"]
            conn.execute(f"UPDATE mouvement SET {', '.join(k + '=?' for k in cols)} WHERE id=?", (*vals, mv.id))
        else:
            mv.id = conn.execute(f"INSERT INTO mouvement(eleve_id, annee_id, sens, {', '.join(cols)}) "
                                 f"VALUES (?,?,?,{', '.join('?' * len(cols))})", (eid, a["id"], mv.sens, *vals)).lastrowid
    return mv.id


_SELECT = ("SELECT m.*, e.code_massar, e.nom_ar, e.prenom_ar, e.sexe FROM mouvement m "
           "JOIN eleve e ON e.id=m.eleve_id")


def eleves_unite(conn: sqlite3.Connection, unite: str | None) -> set[int] | None:
    """تلاميذ وحدة مدرسية (قسمهم في السنة الجارية). None: المؤسسة كاملة (طلب المدير 2026-11-09)."""
    if not unite:
        return None
    a = _annee(conn)
    return {r[0] for r in conn.execute(
        "SELECT i.eleve_id FROM inscription i JOIN classe c ON c.id=i.classe_id JOIN unite_scolaire u ON "
        "u.id=c.unite_id WHERE i.annee_id=? AND u.nom_ar=?", (a["id"], unite))}


def lister(conn: sqlite3.Connection, sens: str | None = None, texte: str = "",
           unite: str | None = None) -> list[sqlite3.Row]:
    a = _annee(conn)
    sql, args = _SELECT + " WHERE m.annee_id=?", [a["id"]]
    if sens:
        sql += " AND m.sens=?"
        args.append(sens)
    lignes = conn.execute(sql + " ORDER BY m.date_mouvement DESC, e.nom_ar", args).fetchall()
    ids = eleves_unite(conn, unite)
    if ids is not None:
        lignes = [r for r in lignes if r["eleve_id"] in ids]
    cible = normaliser(texte)
    if cible:
        lignes = [r for r in lignes if any(cible in normaliser(x) for x in (
            r["code_massar"], f"{r['nom_ar']}{r['prenom_ar']}", f"{r['prenom_ar']}{r['nom_ar']}", r["etablissement"]))]
    return lignes


def lire(conn, mid: int) -> sqlite3.Row:
    r = conn.execute(_SELECT + " WHERE m.id=?", (mid,)).fetchone()
    if r is None:
        raise ErreurMouvement("الحركة غير موجودة.")
    return r


def etat(r: sqlite3.Row, le: date | None = None) -> str:
    """حالة الملف كما تظهر في اللائحة."""
    if r["sens"] == "parti":
        return f"أُرسل الملف {tx.date_chiffres(r['dossier_envoye_le'])}" if r["dossier_envoye_le"] else "لم يُرسل الملف"
    if r["dossier_recu_le"]:
        return f"توصلنا بالملف {tx.date_chiffres(r['dossier_recu_le'])}"
    if r["demande2_le"]:
        return "أُرسل التذكير"
    if r["demande1_le"]:
        return "أُرسل الطلب"
    return "لم يُطلب الملف"


def alertes(conn: sqlite3.Connection, le: date | None = None,
            unite: str | None = None) -> dict[str, list[sqlite3.Row]]:
    le = le or date.today()
    limite = (le - timedelta(days=DELAI_RELANCE)).isoformat()
    return {
        "envoi": [r for r in lister(conn, "parti", unite=unite) if not r["dossier_envoye_le"]],
        "demande": [r for r in lister(conn, "arrive", unite=unite) if not r["demande1_le"] and not r["dossier_recu_le"]],
        "relance": [r for r in lister(conn, "arrive", unite=unite) if r["demande1_le"] and not r["dossier_recu_le"]
                    and (r["demande2_le"] or r["demande1_le"]) <= limite],
    }


def marquer(conn: sqlite3.Connection, mid: int, champ: str, le: str | None) -> None:
    """تأشير يدوي: إرسال الملف، التوصل بالملف، إرسال الطلب (le=None للإلغاء)."""
    if champ not in ("dossier_envoye_le", "dossier_recu_le", "demande1_le"):
        raise ErreurMouvement("تأشير غير معروف.")
    if le:
        try:
            if date.fromisoformat(le) > date.today():
                raise ErreurMouvement("التاريخ في المستقبل.")
        except ValueError as e:
            if isinstance(e, ErreurMouvement):
                raise
            raise ErreurMouvement("التاريخ غير صحيح.") from None
    with conn:
        conn.execute(f"UPDATE mouvement SET {champ}=? WHERE id=?", (le, mid))


# ---------- المراسلات ----------

def _groupe(conn, ids: list[int], sens: str) -> list[sqlite3.Row]:
    if not ids:
        raise ErreurMouvement("حدد تلميذاً واحداً على الأقل.")
    if len(ids) > LIGNES_MAX:
        raise ErreurMouvement(f"المراسلة الواحدة تتسع لـ {LIGNES_MAX} تلاميذ على الأكثر.")
    lignes = [lire(conn, i) for i in ids]
    if any(r["sens"] != sens for r in lignes):
        raise ErreurMouvement("التلاميذ المحددون ليسوا كلهم " + SENS[sens] + "ين.")
    if len({normaliser(r["etablissement"]) for r in lignes}) > 1:
        raise ErreurMouvement("المراسلة الواحدة لمؤسسة واحدة: حدد تلاميذ نفس المؤسسة.")
    return lignes


def _valeurs(conn, lignes: list[sqlite3.Row], le: str, obs: str = "") -> dict[str, str]:
    r0 = lignes[0]
    etab = dc.etab_srv.lire_etablissement(conn)
    v = dc.champs_communs(conn)
    dest = cg.parametres(conn)["destinataire"]
    i = dest.find(" لوزارة")
    ville = dest.split()[-1] if dest.split()[-1].startswith("ب") else ""
    sous_couvert = f"{dest[:i]} {ville}".strip() if i > 0 else dest
    v.update({"date_redaction": tx.date_ar(le), "date_enregistrement": tx.date_chiffres(le),
              "sous_couvert": sous_couvert,
              "notre_direction": formule_direction(etab.direction_ar),
              "notre_academie": formule_academie(etab.academie_ar),
              "etab_cible": formule_etablissement(r0["etablissement"]),
              "direction_cible": formule_direction(r0["direction"] or ""),
              "academie_cible": formule_academie(r0["academie"] or ""),
              "al_tilmidh": al_tilmidh([r["sexe"] for r in lignes])})
    manque = [f"{r['prenom_ar']} {r['nom_ar']}" for r in lignes if not r["niveau"]]
    if manque:
        raise ErreurMouvement("المستوى غير محدد لـ: " + "، ".join(manque) + ". أدخله في الحركة أو أكّده.")
    if r0["hors_province"] and not (r0["direction"] and r0["academie"]):
        raise ErreurMouvement("خارج الإقليم: المديرية والأكاديمية إجباريتان.")
    for i in range(1, LIGNES_MAX + 1):
        if i <= len(lignes):
            r = lignes[i - 1]
            v.update({f"rt_{i}": f"{i:02d}", f"nom_{i}": f"{r['prenom_ar']} {r['nom_ar']}",
                      f"niveau_{i}": r["niveau"], f"code_{i}": r["code_massar"], f"obs_{i}": obs})
        else:
            for k in ("rt", "nom", "niveau", "code", "obs"):
                v[f"{k}_{i}"] = SUPPRIMER_LIGNE
    return v


def generer_demande(conn: sqlite3.Connection, dossier: DossierDonnees, ids: list[int],
                    le: str | None = None, rappel: bool = False) -> dc.DocumentGenere:
    """طلب ملف (أو تذكير) لتلاميذ وافدين من نفس المؤسسة؛ يُسجل في الصادر."""
    le = le or date.today().isoformat()
    lignes = _groupe(conn, ids, "arrive")
    if rappel:
        sans = [r for r in lignes if not r["demande1_le"]]
        if sans:
            raise ErreurMouvement("التذكير يكون بعد الطلب الأول، ولم يُرسل بعد لـ: "
                                  + "، ".join(f"{r['prenom_ar']} {r['nom_ar']}" for r in sans))
    v = _valeurs(conn, lignes, le, "الطلب الثاني" if rappel else "")
    r0 = lignes[0]
    if rappel:
        num = conn.execute("SELECT k.numero, a.code_court FROM courrier k JOIN annee_scolaire a ON a.id=k.annee_id "
                           "WHERE k.id=?", (r0["demande1_courrier_id"],)).fetchone()
        precedent = f" تحت عدد: ⁦{cg.numero_affiche(*num)}⁩" if num else ""
        v["tadhkir"] = " (تذكير)"
        v["rappel"] = (f"وعلاقة بالموضوع المشار إليه أعلاه، وتذكيرا بالطلب السابق المرسل إليكم بتاريخ "
                       f"{tx.date_ar(r0['demande1_le'])}{precedent}، ")
    else:
        v["tadhkir"] = v["rappel"] = ""
    v["reference"] = (f"المرجع: شهادة المغادرة رقم: {r0['ref_numero']} بتاريخ: {tx.date_chiffres(r0['ref_date'])}"
                      if r0["ref_numero"] and r0["ref_date"] else SUPPRIMER)
    noms = "، ".join(f"{r['prenom_ar']} {r['nom_ar']}" for r in lignes)
    cid, numero = cg.enregistrer_sortant(conn, ("تذكير بطلب" if rappel else "طلب") + f" ملف: {noms}", le)
    v["numero"] = f"⁦{numero}⁩"
    code = "demande_dossier_hors" if r0["hors_province"] else "demande_dossier"
    with conn:
        for r in lignes:
            if rappel:
                conn.execute("UPDATE mouvement SET demande2_courrier_id=?, demande2_le=? WHERE id=?", (cid, le, r["id"]))
            else:
                conn.execute("UPDATE mouvement SET demande1_courrier_id=?, demande1_le=? WHERE id=?", (cid, le, r["id"]))
    return dc.generer(conn, dossier, code, v, libelle=("تذكير " if rappel else "") + f"طلب ملف {noms}",
                      eleve_id=r0["eleve_id"], courrier_id=cid)


def generer_envoi(conn: sqlite3.Connection, dossier: DossierDonnees, ids: list[int],
                  le: str | None = None) -> dc.DocumentGenere:
    """إرسال ملفات تلاميذ مغادرين إلى نفس المؤسسة؛ يُسجل في الصادر ويُؤشر على الإرسال."""
    le = le or date.today().isoformat()
    lignes = _groupe(conn, ids, "parti")
    v = _valeurs(conn, lignes, le)
    r0 = lignes[0]
    ref = bool(r0["ref_numero"] and r0["ref_date"])
    if r0["hors_province"]:
        v["reference"] = (f"المرجع: مراسلتكم رقم: {r0['ref_numero']} بتاريخ: {tx.date_chiffres(r0['ref_date'])}"
                          if ref else SUPPRIMER)
        v["bina"] = "بناء على مراسلتكم المشار إليها في المرجع أعلاه، " if ref else ""
    else:
        v["bina"] = (f"بناء على مراسلتكم رقم: {r0['ref_numero']} بتاريخ: {tx.date_chiffres(r0['ref_date'])}، "
                     if ref else "")
    noms = "، ".join(f"{r['prenom_ar']} {r['nom_ar']}" for r in lignes)
    cid, numero = cg.enregistrer_sortant(conn, f"إرسال ملف: {noms}", le)
    v["numero"] = f"⁦{numero}⁩"
    with conn:
        for r in lignes:
            conn.execute("UPDATE mouvement SET envoi_courrier_id=?, dossier_envoye_le=? WHERE id=?", (cid, le, r["id"]))
    code = "envoi_dossier_hors" if r0["hors_province"] else "envoi_dossier"
    return dc.generer(conn, dossier, code, v, libelle=f"إرسال ملف {noms}", eleve_id=r0["eleve_id"], courrier_id=cid)


def suggestions(conn, champ: str) -> list[str]:
    if champ not in ("etablissement", "direction", "academie"):
        raise ValueError(champ)
    return [r[0] for r in conn.execute(f"SELECT {champ}, COUNT(*) n FROM mouvement WHERE {champ} IS NOT NULL "
                                       f"GROUP BY {champ} ORDER BY n DESC")]


# ---------- معاينة القوالب ----------

def exemple(conn, code: str) -> dict[str, str]:
    an = date.today().isoformat()
    lignes = [{"id": 0, "sexe": "F", "prenom_ar": "سلمى", "nom_ar": "التجريبي", "niveau": "الخامس",
               "code_massar": "X000000000", "etablissement": "المؤسسة الأخرى", "direction": "إقليم: الإقليم",
               "academie": "الجهة", "hors_province": 1}]
    v = _valeurs(conn, lignes, an, "")
    v.update({"numero": "1/26-27", "tadhkir": "", "rappel": "", "bina": "",
              "reference": "المرجع: شهادة المغادرة رقم: [الرقم] بتاريخ: [التاريخ]"})
    return v


def sorties_sans_transfert(conn: sqlite3.Connection, texte: str = "",
                           unite: str | None = None) -> list[sqlite3.Row]:
    """المنقطعون والمفصولون في السنة الجارية (لا ملف يُرسل)."""
    a = _annee(conn)
    lignes = conn.execute(
        "SELECT e.id AS eleve_id, e.code_massar, e.nom_ar, e.prenom_ar, i.statut, i.date_sortie, i.motif_sortie "
        "FROM inscription i JOIN eleve e ON e.id=i.eleve_id WHERE i.annee_id=? AND i.statut IN ('interrompu','exclu') "
        "ORDER BY i.date_sortie DESC", (a["id"],)).fetchall()
    ids = eleves_unite(conn, unite)
    if ids is not None:
        lignes = [r for r in lignes if r["eleve_id"] in ids]
    cible = normaliser(texte)
    if cible:
        lignes = [r for r in lignes if any(cible in normaliser(x) for x in (
            r["code_massar"], f"{r['nom_ar']}{r['prenom_ar']}", f"{r['prenom_ar']}{r['nom_ar']}"))]
    return lignes
