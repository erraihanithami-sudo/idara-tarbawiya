"""ملف الرخصة وسلسلة وثائقه، وسجل الصادر.

ملف رخصة واحد يُدخل مرة، ومنه تُولد: طلب الرخصة (أو التمديد)، إيصال الشهادة الطبية،
طلب التعويض، ورقة الإرسال، ثم محضر استئناف العمل عند العودة.
كل حقول الوثيقة إجبارية: لا تُكتب نقط مكان معلومة ناقصة (قاعدة المدير).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date, timedelta

from idara.data.dossier import DossierDonnees
from idara.services import annee as annee_srv
from idara.services import documents as dc
from idara.services import personnel as rh
from idara.services import textes as tx
from idara.services.moteur_docx import SUPPRIMER


class ErreurConge(ValueError):
    """رسالة موجهة للمدير بالعربية."""


# ---------- صيغ المراسلات (من نماذج المدير، قابلة للتعديل) ----------

PARAMETRES = {
    "destinataire": ("الجهة المرسل إليها", None),  # تُبنى من مدينة التحرير إن لم تُحدد
    "service_rh": ("المصلحة", "مصلحة تدبير الموارد البشرية"),
    "bureau_conges": ("مكتب الرخص", "مكتب الرخص والتغيبات"),
    "bureau_etablissements": ("مكتب تسيير المؤسسات", "مكتب تسيير مؤسسات التعليم الابتدائي"),
}
_MINISTERE = "السيد المدير الإقليمي لوزارة التربية الوطنية والتعليم الأولي والرياضة"


def parametres(conn: sqlite3.Connection) -> dict[str, str]:
    lus = {r["cle"]: r["valeur"] for r in conn.execute("SELECT cle, valeur FROM parametre")}
    res = {}
    for k, (_, defaut) in PARAMETRES.items():
        if lus.get(k):
            res[k] = lus[k]
        elif k == "destinataire":
            etab = dc.etab_srv.lire_etablissement(conn)
            ville = etab.ville_redaction_ar if etab else ""
            res[k] = f"{_MINISTERE} ب{ville}" if ville else _MINISTERE
        else:
            res[k] = defaut
    return res


def definir_parametres(conn: sqlite3.Connection, valeurs: dict[str, str]) -> None:
    with conn:
        for k, v in valeurs.items():
            if k not in PARAMETRES:
                raise ErreurConge(f"إعداد غير معروف: {k}")
            v = " ".join((v or "").split())
            if not v:
                raise ErreurConge(f"{PARAMETRES[k][0]}: لا يكون فارغاً.")
            conn.execute("INSERT INTO parametre(cle, valeur) VALUES (?,?) "
                         "ON CONFLICT(cle) DO UPDATE SET valeur=excluded.valeur", (k, v))


def _destination(conn) -> dict[str, str]:
    p = parametres(conn)
    d = p["destinataire"]
    i = d.find(" لوزارة")
    return {"destinataire": d, "dest_titre": d[:i] if i > 0 else d, "dest_ministere": d[i + 1:] if i > 0 else "",
            "dest_service": p["service_rh"], "bureau_conges": p["bureau_conges"],
            "bureau_etablissements": p["bureau_etablissements"]}


# ---------- سجل الصادر ----------

def _annee(conn):
    a = annee_srv.annee_courante(conn)
    if a is None:
        raise ErreurConge("لا توجد سنة دراسية جارية.")
    return a


def _isoler(texte: str) -> str:
    """رقم مثل 98/25-26 داخل سطر عربي: يُعزل اتجاهه حتى لا ينقلب ترتيبه."""
    return f"\u2066{texte}\u2069"


def numero_affiche(n: int, code_court: str) -> str:
    return f"{n}/{code_court}"


def prochain_numero(conn: sqlite3.Connection) -> int:
    a = _annee(conn)
    r = conn.execute("SELECT MAX(numero) FROM courrier WHERE sens='sortant' AND annee_id=?", (a["id"],)).fetchone()
    return (r[0] or 0) + 1


def enregistrer_sortant(conn: sqlite3.Connection, objet: str, le: str, conge_id: int | None = None,
                        numero: int | None = None) -> tuple[int, str]:
    """يسجل مراسلة صادرة. الرقم يتوالى ويبدأ من 1 كل سنة دراسية. يرجع (المعرف، الرقم المعروض)."""
    objet = " ".join((objet or "").split())
    if not objet:
        raise ErreurConge("موضوع المراسلة إجباري.")
    try:
        date.fromisoformat(le)
    except (TypeError, ValueError):
        raise ErreurConge("تاريخ المراسلة غير صحيح.") from None
    a = _annee(conn)
    n = numero or prochain_numero(conn)
    if n < 1:
        raise ErreurConge("رقم الصادر يبدأ من 1.")
    try:
        with conn:
            cid = conn.execute(
                "INSERT INTO courrier(sens, annee_id, numero, date_courrier, objet, conge_id) "
                "VALUES ('sortant',?,?,?,?,?)", (a["id"], n, le, objet, conge_id)).lastrowid
    except sqlite3.IntegrityError:
        raise ErreurConge(f"الرقم {n} مستعمل في سجل الصادر لهذه السنة.") from None
    return cid, numero_affiche(n, a["code_court"])


def sortants(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    a = _annee(conn)
    return conn.execute(
        "SELECT c.id, c.numero, c.date_courrier, c.objet, c.conge_id, ? AS code_court FROM courrier c "
        "WHERE c.sens='sortant' AND c.annee_id=? ORDER BY c.numero DESC", (a["code_court"], a["id"])).fetchall()


# ---------- ملف الرخصة ----------

def types_conge(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT id, libelle_ar FROM type_conge ORDER BY id").fetchall()


def cas_reprise(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT id, libelle_ar FROM cas_reprise ORDER BY id").fetchall()


RADAA = "رخصة الرضاعة"
MOIS_RADAA = 24   # الفصل 46 (القانون 30.22): إلى أن يبلغ الطفل 24 شهراً


def est_allaitement(conn, type_conge_id) -> bool:
    r = conn.execute("SELECT libelle_ar FROM type_conge WHERE id=?", (type_conge_id,)).fetchone()
    return bool(r) and r[0] == RADAA


def _plus_mois(d: date, mois: int) -> date:
    a, m = divmod(d.month - 1 + mois, 12)
    an, mo = d.year + a, m + 1
    import calendar
    return date(an, mo, min(d.day, calendar.monthrange(an, mo)[1]))


def periode_allaitement(conn, personnel_id: int | None, naissance: str) -> tuple[str, str]:
    """بداية رخصة الرضاعة (اليوم الموالي لنهاية آخر رخصة ولادة بعد الازدياد، وإلا يوم الازدياد)
    ونهايتها (اليوم السابق لبلوغ الطفل 24 شهراً)."""
    n = date.fromisoformat(naissance)
    debut = n
    if personnel_id:
        r = conn.execute("SELECT MAX(c.date_fin) FROM conge c JOIN type_conge t ON t.id=c.type_conge_id "
                         "WHERE c.personnel_id=? AND t.libelle_ar LIKE '%الولادة%' AND c.date_fin>=?",
                         (personnel_id, (n - timedelta(days=300)).isoformat())).fetchone()
        if r and r[0]:
            debut = max(n, date.fromisoformat(r[0]) + timedelta(days=1))
    return debut.isoformat(), (_plus_mois(n, MOIS_RADAA) - timedelta(days=1)).isoformat()


def allaitements_en_cours(conn, le: date | None = None) -> list[sqlite3.Row]:
    le = (le or date.today()).isoformat()
    return conn.execute(
        "SELECT c.*, p.prenom_ar, p.nom_ar FROM conge c JOIN type_conge t ON t.id=c.type_conge_id "
        "JOIN personnel p ON p.id=c.personnel_id WHERE t.libelle_ar=? AND c.date_debut<=? AND c.date_fin>=? "
        "ORDER BY c.date_fin", (RADAA, le, le)).fetchall()


def _est_maladie(libelle: str) -> bool:
    return "مرض" in libelle


def motif_defaut(libelle_type: str) -> str:
    if _est_maladie(libelle_type):
        return "مرض"
    if "الولادة" in libelle_type:
        return "الولادة"
    if libelle_type == RADAA:
        return "الرضاعة"
    return ""


@dataclass
class Conge:
    personnel_id: int | None = None
    type_conge_id: int | None = None
    date_debut: str = ""
    duree_jours: int | str = ""
    motif: str = ""
    adresse_conge: str = ""
    date_demande: str = ""
    prolongation_de: int | None = None
    avis_directeur: str = ""
    mesures_prises: str = ""
    pieces: str = ""
    # الشهادة الطبية
    medecin: str = ""
    specialite: str = ""
    certificat_recu_le: str = ""
    certificat_remis_par: str = ""
    certificat_remis_par_cin: str = ""
    certificat_duree_jours: int | str | None = None
    remarques_certificat: str = ""
    demande_remplacement: bool = False
    # رخصة الرضاعة
    date_naissance_enfant: str = ""
    horaire_allaitement: str = ""
    id: int | None = None
    erreurs: list[str] = field(default_factory=list)

    @property
    def date_fin(self) -> str:
        return (date.fromisoformat(self.date_debut) + timedelta(days=int(self.duree_jours) - 1)).isoformat()

    def valider(self) -> None:
        for k in ("motif", "adresse_conge", "avis_directeur", "mesures_prises", "pieces", "medecin",
                  "specialite", "certificat_remis_par", "remarques_certificat", "horaire_allaitement"):
            setattr(self, k, " ".join((getattr(self, k) or "").split()))
        self.certificat_remis_par_cin = (self.certificat_remis_par_cin or "").replace(" ", "").upper()
        if not self.personnel_id:
            raise ErreurConge("اختر الموظف.")
        if not self.type_conge_id:
            raise ErreurConge("اختر نوع الرخصة.")
        for k, lib in (("date_debut", "تاريخ بداية الرخصة"), ("date_demande", "تاريخ الطلب"),
                       ("certificat_recu_le", "تاريخ تسلم الشهادة الطبية"),
                       ("date_naissance_enfant", "تاريخ ازدياد الطفل")):
            v = getattr(self, k)
            if not v and k == "date_debut":
                raise ErreurConge(f"{lib} إجباري.")
            if v:
                try:
                    date.fromisoformat(v)
                except ValueError:
                    raise ErreurConge(f"{lib} غير صحيح.") from None
        for k, lib in (("duree_jours", "مدة الرخصة"), ("certificat_duree_jours", "مدة الشهادة الطبية")):
            v = getattr(self, k)
            if v in ("", None):
                if k == "duree_jours":
                    raise ErreurConge("مدة الرخصة إجبارية (بالأيام).")
                setattr(self, k, None)
                continue
            try:
                v = int(v)
            except (TypeError, ValueError):
                raise ErreurConge(f"{lib}: عدد أيام صحيح.") from None
            if not 1 <= v <= 1100:
                raise ErreurConge(f"{lib}: قيمة غير معقولة.")
            setattr(self, k, v)
        if not self.date_demande:
            self.date_demande = date.today().isoformat()


def _ligne_vers(r: sqlite3.Row) -> Conge:
    c = Conge()
    for k in Conge.__dataclass_fields__:
        if k in r.keys():
            v = r[k]
            setattr(c, k, v if v is not None else ("" if isinstance(getattr(c, k), str) else v))
    c.demande_remplacement = bool(r["demande_remplacement"])
    return c


def lire(conn: sqlite3.Connection, conge_id: int) -> Conge:
    r = conn.execute("SELECT * FROM conge WHERE id=?", (conge_id,)).fetchone()
    if r is None:
        raise ErreurConge("الرخصة غير موجودة.")
    return _ligne_vers(r)


def lister(conn: sqlite3.Connection, personnel_id: int | None = None) -> list[sqlite3.Row]:
    sql = ("SELECT c.*, t.libelle_ar AS type, p.nom_ar, p.prenom_ar, p.sexe, "
           "(SELECT id FROM reprise_travail r WHERE r.conge_id=c.id) AS reprise_id, "
           "(SELECT numero FROM courrier k WHERE k.conge_id=c.id AND k.objet LIKE 'طلب%' "
           " ORDER BY k.id LIMIT 1) AS numero, "
           "(SELECT a.code_court FROM courrier k JOIN annee_scolaire a ON a.id=k.annee_id WHERE k.conge_id=c.id "
           " AND k.objet LIKE 'طلب%' ORDER BY k.id LIMIT 1) AS code_court "
           "FROM conge c JOIN type_conge t ON t.id=c.type_conge_id JOIN personnel p ON p.id=c.personnel_id")
    if personnel_id:
        return conn.execute(sql + " WHERE c.personnel_id=? ORDER BY c.date_debut DESC", (personnel_id,)).fetchall()
    return conn.execute(sql + " ORDER BY c.date_debut DESC, c.id DESC").fetchall()


def enregistrer(conn: sqlite3.Connection, c: Conge) -> int:
    c.valider()
    p = rh.lire(conn, c.personnel_id)
    if p.statut != "actif":
        raise ErreurConge("الموظف غير عامل حالياً.")
    if not conn.execute("SELECT 1 FROM type_conge WHERE id=?", (c.type_conge_id,)).fetchone():
        raise ErreurConge("نوع الرخصة غير معروف.")
    radaa = est_allaitement(conn, c.type_conge_id)
    if radaa:
        if p.sexe != "F":
            raise ErreurConge("رخصة الرضاعة خاصة بالموظفات.")
        if not c.date_naissance_enfant:
            raise ErreurConge("تاريخ ازدياد الطفل (أو تاريخ الكفالة) إجباري لرخصة الرضاعة.")
        if c.date_naissance_enfant > date.today().isoformat():
            raise ErreurConge("تاريخ ازدياد الطفل في المستقبل.")
        if c.date_debut < c.date_naissance_enfant:
            raise ErreurConge("رخصة الرضاعة تبدأ بعد ازدياد الطفل (عند انتهاء رخصة الولادة).")
        _, limite = periode_allaitement(conn, None, c.date_naissance_enfant)
        if c.date_fin > limite:
            raise ErreurConge(f"رخصة الرضاعة تنتهي عند بلوغ الطفل {MOIS_RADAA} شهراً "
                              f"({tx.date_chiffres(limite)}) حسب الفصل 46 من النظام الأساسي العام.")
        c.prolongation_de = None
    else:
        c.date_naissance_enfant = ""
        c.horaire_allaitement = ""
    if c.prolongation_de:
        parent = conn.execute("SELECT * FROM conge WHERE id=?", (c.prolongation_de,)).fetchone()
        if parent is None or parent["personnel_id"] != c.personnel_id or parent["id"] == c.id:
            raise ErreurConge("الرخصة الممدَّدة يجب أن تكون لنفس الموظف.")
        if c.date_debut <= parent["date_debut"]:
            raise ErreurConge("التمديد يبدأ بعد بداية الرخصة الأصلية.")
    fin = c.date_fin
    # الرضاعة ساعة يومية لا تغيب: لا تتداخل إلا مع رضاعة أخرى
    chevauche = conn.execute(
        "SELECT t.libelle_ar, c.date_debut, c.date_fin FROM conge c JOIN type_conge t ON t.id=c.type_conge_id "
        "WHERE c.personnel_id=? AND c.id IS NOT ? AND c.date_debut<=? AND c.date_fin>=? AND "
        + ("t.libelle_ar=?" if radaa else "t.libelle_ar<>?"),
        (c.personnel_id, c.id, fin, c.date_debut, RADAA)).fetchone()
    if chevauche:
        raise ErreurConge(f"تتداخل مع {chevauche[0]} من {tx.date_chiffres(chevauche[1])} "
                          f"إلى {tx.date_chiffres(chevauche[2])}.")
    cols = ("personnel_id", "type_conge_id", "prolongation_de", "date_debut", "duree_jours", "adresse_conge",
            "avis_directeur", "mesures_prises", "medecin", "specialite", "certificat_recu_le",
            "certificat_remis_par", "certificat_remis_par_cin", "certificat_duree_jours", "motif", "pieces",
            "remarques_certificat", "date_demande", "date_naissance_enfant", "horaire_allaitement")
    vals = [getattr(c, k) if getattr(c, k) != "" else None for k in cols]
    with conn:
        if c.id is None:
            c.id = conn.execute(
                f"INSERT INTO conge({', '.join(cols)}, date_fin, demande_remplacement) "
                f"VALUES ({', '.join('?' * len(cols))}, ?, ?)", (*vals, fin, int(c.demande_remplacement))).lastrowid
        else:
            conn.execute(f"UPDATE conge SET {', '.join(k + '=?' for k in cols)}, date_fin=?, "
                         f"demande_remplacement=? WHERE id=?", (*vals, fin, int(c.demande_remplacement), c.id))
        conn.execute("INSERT INTO journal(action, cible, cible_id, details) VALUES ('enregistrement','conge',?,?)",
                     (c.id, f"{p.prenom_ar} {p.nom_ar} {c.date_debut} ({c.duree_jours} يوماً)"))
    return c.id


def rentrees_attendues(conn: sqlite3.Connection, le: date | None = None) -> list[sqlite3.Row]:
    """رخص انتهت دون محضر استئناف (تنبيه)."""
    le = le or date.today()
    lignes = lister(conn)
    parents = {r["id"]: r["prolongation_de"] for r in lignes}
    avec_reprise = {r["id"] for r in lignes if r["reprise_id"]}

    def chaine_close(cid):  # محضر الاستئناف يُسجل على الرخصة الأصلية ويغطي تمديداتها
        while cid:
            if cid in avec_reprise:
                return True
            cid = parents.get(cid)
        return False
    return [r for r in lignes if r["date_fin"] < le.isoformat() and not chaine_close(r["id"]) and r["type"] != RADAA
            and not any(p == r["id"] for p in parents.values())]


# ---------- بيان الرخص خلال 12 شهراً ----------

def historique_12_mois(conn: sqlite3.Connection, c: Conge) -> list[sqlite3.Row]:
    debut = date.fromisoformat(c.date_debut)
    depuis = date(debut.year - 1, debut.month, min(debut.day, 28)).isoformat()
    return conn.execute(
        "SELECT t.libelle_ar AS type, c.duree_jours, c.date_debut, c.date_fin, c.prolongation_de "
        "FROM conge c JOIN type_conge t ON t.id=c.type_conge_id WHERE c.personnel_id=? AND c.id IS NOT ? "
        "AND c.date_fin>=? AND c.date_debut<? ORDER BY c.date_debut",
        (c.personnel_id, c.id, depuis, c.date_debut)).fetchall()


# ---------- قيم الوثائق ----------

def _accords(sexe: str) -> dict[str, str]:
    a = tx.accord
    return {"sayyid": a(sexe, "السيد", "السيدة"), "sayyid_label": a(sexe, "السيـــــــــــد", "السيـــــــــــدة"),
            "bi_sayyid": a(sexe, "بالسيد", "بالسيدة"), "ostadh": a(sexe, "أستاذ", "أستاذة"),
            "al_ostadh": a(sexe, "الأستاذ", "الأستاذة"), "alladhi": a(sexe, "الذي", "التي"),
            "yaamal": a(sexe, "يعمل", "تعمل"), "litaawid": a(sexe, "لتعويضه", "لتعويضها"),
            "istaanafa": a(sexe, "استأنف عمله", "استأنفت عملها")}


def _accords_directeur(s: str) -> dict[str, str]:
    a = tx.accord
    return {"sayyid_mudir": a(s, "السيد مدير", "السيدة مديرة"),
            "rai_mudir": a(s, "رأي السيد المدير", "رأي السيدة المديرة"),
            "ana_mouwaqqi": a(s, "أنا الموقع أسفله السيد", "أنا الموقعة أسفله السيدة"),
            "bisifati": a(s, "بصفتي مديرا", "بصفتي مديرة")}


def _exiger(valeurs: dict[str, object], libelles: dict[str, str], ou: str) -> None:
    manque = [lib for k, lib in libelles.items() if valeurs.get(k) in ("", None)]
    if manque:
        raise ErreurConge("بيانات ناقصة لهذه الوثيقة: " + "، ".join(manque) + f". أكملها في {ou}.")


def _personnel_valeurs(conn, p: rh.Personnel, champs: dict[str, str]) -> dict[str, str]:
    enseignant = p.categorie in ("enseignant", "educatrice")
    e = rh.enseignement(conn, p) if enseignant else {"niveau": "—", "nb_eleves": "—"}
    v = {"nom_complet": f"{p.prenom_ar} {p.nom_ar}", "prenom": p.prenom_ar, "nom": p.nom_ar, "ppr": p.ppr,
         "cin": p.cin, "cadre": rh.cadre_accorde(p.cadre, p.sexe), "grade": rh.grade_court(p.grade),
         "fonction": p.fonction, "adresse": p.adresse,
         "telephone": p.telephone,
         "cycle": p.cycle if enseignant else "—", "matiere": p.matiere if enseignant else "—",
         "niveau": e["niveau"], "nb_eleves": "" if e["nb_eleves"] in (None, "") else str(e["nb_eleves"]),
         "heures": ("" if p.heures_hebdo is None else str(p.heures_hebdo)) if enseignant else "—"}
    libs = {"ppr": "رقم التأجير", "cin": "رقم البطاقة الوطنية", "cadre": "الإطار", "grade": "الدرجة",
            "fonction": "المهمة", "adresse": "العنوان الشخصي", "telephone": "الهاتف", "cycle": "السلك",
            "matiere": "مادة التدريس", "niveau": "مستوى التدريس (أو إسناد قسم)",
            "nb_eleves": "عدد التلاميذ (أو إسناد قسم)", "heures": "ساعات العمل"}
    _exiger(v, {k: libs[k] for k in champs if k in libs}, "ملف الموظف (الموارد البشرية)")
    v.update(_accords(p.sexe))
    return v


def _communs(conn) -> dict[str, str]:
    v = dc.champs_communs(conn)
    d = dc.etab_srv.directeur_actuel(conn)
    v.update(_accords_directeur(d["sexe"]))
    v.update(_destination(conn))
    return v


def _type(conn, c: Conge) -> str:
    return conn.execute("SELECT libelle_ar FROM type_conge WHERE id=?", (c.type_conge_id,)).fetchone()[0]


def valeurs_demande(conn, c: Conge, numero: str, historique: list | None = None,
                    p: rh.Personnel | None = None) -> dict[str, str]:
    p = p or rh.lire(conn, c.personnel_id)
    if not (c.adresse_conge or "").strip():   # افتراضياً: عنوان الموظف في ملفه (قرار المدير 2026-11-09)
        c.adresse_conge = p.adresse
    t = _type(conn, c)
    v = _communs(conn)
    v.update(_personnel_valeurs(conn, p, ("ppr", "cin", "cadre", "fonction", "cycle", "matiere", "niveau",
                                          "nb_eleves", "heures")))
    _exiger({"adresse_conge": c.adresse_conge, "motif": c.motif, "mesures": c.mesures_prises,
             "avis": c.avis_directeur},
            {"adresse_conge": "عنوان الإقامة خلال الرخصة", "motif": "سبب الرخصة",
             "mesures": "الإجراءات المتخذة في سير الدراسة", "avis": "رأي المدير"}, "ملف الرخصة")
    hist = historique if historique is not None else historique_12_mois(conn, c)
    if hist:
        col = lambda f: "\n".join(f(h) for h in hist)  # noqa: E731
        h = {"h_type": col(lambda h: h["type"]), "h_duree": col(lambda h: tx.duree_jours_ar(h["duree_jours"])),
             "h_du": col(lambda h: tx.date_chiffres(h["date_debut"])),
             "h_au": col(lambda h: tx.date_chiffres(h["date_fin"])),
             "h_obs": col(lambda h: "تمديد" if h["prolongation_de"] else "—")}
    else:
        h = {"h_type": "لا شيء", "h_duree": "—", "h_du": "—", "h_au": "—", "h_obs": "—"}
    v.update(h)
    v.update({"date_redaction": tx.date_ar(c.date_demande), "dest_bureau": v["bureau_conges"],
              "objet": "طلب تمديد رخصة مرضية" if c.prolongation_de else "طلب رخصة",
              "motif": c.motif + (" (تمديد)" if c.prolongation_de and "تمديد" not in c.motif else ""),
              "duree": tx.duree_jours_ar(c.duree_jours), "du": tx.date_ar(c.date_debut), "au": tx.date_ar(c.date_fin),
              "adresse_conge": c.adresse_conge, "pieces": c.pieces or "—", "avis": c.avis_directeur,
              "mesures": c.mesures_prises, "numero": _isoler(numero), "date_enregistrement": tx.date_ar(c.date_demande),
              "type_conge": t})
    return v


def valeurs_recu(conn, c: Conge, p: rh.Personnel | None = None) -> dict[str, str]:
    p = p or rh.lire(conn, c.personnel_id)
    v = _communs(conn)
    v.update(_personnel_valeurs(conn, p, ("ppr", "cadre", "adresse", "matiere")))
    _exiger({"medecin": c.medecin, "specialite": c.specialite, "recu": c.certificat_recu_le,
             "deposant": c.certificat_remis_par, "cin": c.certificat_remis_par_cin},
            {"medecin": "اسم الطبيب", "specialite": "تخصص الطبيب", "recu": "تاريخ تسلم الشهادة",
             "deposant": "اسم المدلي بالشهادة", "cin": "رقم بطاقة المدلي بالشهادة"}, "ملف الرخصة (الشهادة الطبية)")
    v.update({"date_reception": tx.date_ar(c.certificat_recu_le), "deposant": c.certificat_remis_par,
              "deposant_cin": c.certificat_remis_par_cin, "medecin": c.medecin, "specialite": c.specialite,
              "duree": tx.duree_jours_ar(c.certificat_duree_jours or c.duree_jours), "du": tx.date_ar(c.date_debut),
              "remarques": c.remarques_certificat or "—",
              # الموظف نفسه أدلى بالشهادة (طلب المدير 2026-11-13): اسمه أسفل الوصل تحت رقم بطاقته
              "deposant_bas": f"الاسم الكامل: {c.certificat_remis_par}" if depose_par_lui_meme(c, p) else ""})
    return v


def depose_par_lui_meme(c: Conge, p: rh.Personnel) -> bool:
    """المدلي بالشهادة هو الموظف نفسه (الاسم نفسه، بالترتيبين)."""
    def n(s: str) -> str:
        return " ".join((s or "").split())
    return n(c.certificat_remis_par) in (n(f"{p.prenom_ar} {p.nom_ar}"), n(f"{p.nom_ar} {p.prenom_ar}")) and \
        bool(n(c.certificat_remis_par))


def valeurs_remplacement(conn, c: Conge, le: str | None = None, p: rh.Personnel | None = None) -> dict[str, str]:
    p = p or rh.lire(conn, c.personnel_id)
    if p.categorie not in ("enseignant", "educatrice"):
        raise ErreurConge("طلب التعويض خاص بالأساتذة والمربين.")
    t = _type(conn, c)
    v = _communs(conn)
    v.update(_personnel_valeurs(conn, p, ("ppr", "matiere")))
    v.update({"date_redaction": tx.date_ar(le or c.date_demande), "dest_bureau": v["bureau_etablissements"],
              "type_conge": t, "duree": tx.duree_jours_ar(c.duree_jours), "du": tx.date_ar(c.date_debut)})
    return v


def valeurs_bordereau(conn, pieces: list[tuple[str, int]], numero: str, le: str,
                      bureau: str = "bureau_conges") -> dict[str, str]:
    pieces = [(" ".join(d.split()), n) for d, n in pieces if d and d.strip()]
    if not pieces:
        raise ErreurConge("أضف وثيقة واحدة على الأقل لورقة الإرسال.")
    if len(pieces) > 8:
        raise ErreurConge("ورقة الإرسال تتسع لثماني وثائق على الأكثر.")
    if any(int(n) < 1 for _, n in pieces):
        raise ErreurConge("عدد النسخ يبدأ من 1.")
    v = _communs(conn)
    # رقم الإرسال يُترك فارغاً ويكتبه المدير بيده (قرار المدير 2026-11-09)
    v.update({"date_redaction": tx.date_ar(le), "numero": "", "date_enregistrement": tx.date_ar(le),
              "dest_bureau": v[bureau]})
    for i in range(1, 9):
        if i <= len(pieces):
            v[f"piece_{i}"], v[f"nb_{i}"] = pieces[i - 1][0], f"*{int(pieces[i - 1][1]):02d}"
        else:
            v[f"piece_{i}"] = v[f"nb_{i}"] = SUPPRIMER
    return v


def pieces_proposees(conn, c: Conge) -> list[tuple[str, int]]:
    p = rh.lire(conn, c.personnel_id)
    qui = f"{tx.accord(p.sexe, 'الأستاذ', 'الأستاذة') if p.categorie == 'enseignant' else tx.accord(p.sexe, 'السيد', 'السيدة')} {p.prenom_ar} {p.nom_ar}"
    objet = "طلب تمديد رخصة" if c.prolongation_de else "طلب رخصة"
    res = [(f"{objet} يخص {qui}", 1)]
    if c.medecin:
        res += [("شهادة طبية", 1), ("نسخة من الشهادة الطبية", 1), ("وصل تسلم الشهادة الطبية", 1)]
    return res


# ---------- التوليد ----------

def _numero_demande(conn, c: Conge) -> str:
    """رقم الصادر للطلب: يُسجل مرة واحدة عند أول توليد، ويبقى نفسه عند إعادة التوليد."""
    r = conn.execute("SELECT k.numero, a.code_court FROM courrier k JOIN annee_scolaire a ON a.id=k.annee_id "
                     "WHERE k.conge_id=? AND k.objet LIKE 'طلب%' ORDER BY k.id LIMIT 1", (c.id,)).fetchone()
    if r:
        return numero_affiche(r[0], r[1])
    p = rh.lire(conn, c.personnel_id)
    objet = ("طلب تمديد رخصة" if c.prolongation_de else "طلب رخصة") + f": {p.prenom_ar} {p.nom_ar}"
    return enregistrer_sortant(conn, objet, c.date_demande, conge_id=c.id)[1]


def generer_demande(conn, dossier: DossierDonnees, conge_id: int) -> dc.DocumentGenere:
    c = lire(conn, conge_id)
    v = valeurs_demande(conn, c, "؟")  # التحقق قبل حجز رقم في سجل الصادر
    v["numero"] = _isoler(_numero_demande(conn, c))
    return dc.generer(conn, dossier, "demande_conge", v, libelle=f"{v['objet']} {v['nom_complet']}",
                      personnel_id=c.personnel_id, conge_id=c.id)


def generer_recu(conn, dossier: DossierDonnees, conge_id: int) -> dc.DocumentGenere:
    c = lire(conn, conge_id)
    v = valeurs_recu(conn, c)
    return dc.generer(conn, dossier, "recu_certificat", v, libelle=f"إيصال شهادة طبية {v['nom_complet']}",
                      personnel_id=c.personnel_id, conge_id=c.id)


def generer_remplacement(conn, dossier: DossierDonnees, conge_id: int, le: str | None = None) -> dc.DocumentGenere:
    c = lire(conn, conge_id)
    v = valeurs_remplacement(conn, c, le)
    with conn:
        conn.execute("UPDATE conge SET demande_remplacement=1 WHERE id=?", (c.id,))
    return dc.generer(conn, dossier, "demande_remplacement", v, libelle=f"طلب تعويض {v['nom_complet']}",
                      personnel_id=c.personnel_id, conge_id=c.id)


def generer_bordereau(conn, dossier: DossierDonnees, pieces: list[tuple[str, int]], objet: str,
                      le: str | None = None, conge_id: int | None = None,
                      bureau: str = "bureau_conges") -> dc.DocumentGenere:
    """ورقة إرسال: تُسجل في الصادر برقم جديد."""
    le = le or date.today().isoformat()
    valeurs_bordereau(conn, pieces, "؟", le, bureau)  # تحقق قبل حجز الرقم
    cid, num = enregistrer_sortant(conn, f"ورقة إرسال: {objet}", le, conge_id=conge_id)
    with conn:
        conn.executemany("INSERT INTO piece_bordereau(courrier_id, designation, nb_exemplaires) VALUES (?,?,?)",
                         [(cid, d, int(n)) for d, n in pieces if d.strip()])
    v = valeurs_bordereau(conn, pieces, num, le, bureau)
    return dc.generer(conn, dossier, "bordereau_envoi", v, libelle=f"ورقة إرسال {num.replace('/', '_')}",
                      conge_id=conge_id, courrier_id=cid)


# ---------- استئناف العمل ----------

@dataclass
class Reprise:
    personnel_id: int
    cas_reprise_id: int
    date_debut_absence: str
    date_fin_absence: str
    date_reprise: str
    conge_id: int | None = None
    autres_contacts: str = ""
    date_redaction: str = ""


def proposition_reprise(conn, conge_id: int) -> Reprise:
    """من ملف الرخصة (مع تمديداتها): الغياب من بداية الرخصة إلى نهاية آخر تمديد، والاستئناف في اليوم الموالي."""
    c = lire(conn, conge_id)
    fin, dernier = c.date_fin, c
    while True:
        r = conn.execute("SELECT id FROM conge WHERE prolongation_de=?", (dernier.id,)).fetchone()
        if not r:
            break
        dernier = lire(conn, r[0])
        fin = max(fin, dernier.date_fin)
    t = conn.execute("SELECT libelle_ar FROM type_conge WHERE id=?", (c.type_conge_id,)).fetchone()[0]
    cas = conn.execute("SELECT id FROM cas_reprise WHERE libelle_ar LIKE ?", (f"%{t}%",)).fetchone()
    reprise = (date.fromisoformat(fin) + timedelta(days=1)).isoformat()
    return Reprise(c.personnel_id, cas[0] if cas else 0, c.date_debut, fin, reprise, conge_id=c.id,
                   date_redaction=reprise)


def enregistrer_reprise(conn, r: Reprise) -> int:
    for k, lib in (("date_debut_absence", "بداية الغياب"), ("date_fin_absence", "نهاية الغياب"),
                   ("date_reprise", "تاريخ الاستئناف")):
        try:
            date.fromisoformat(getattr(r, k))
        except (TypeError, ValueError):
            raise ErreurConge(f"{lib}: تاريخ غير صحيح.") from None
    if not conn.execute("SELECT 1 FROM cas_reprise WHERE id=?", (r.cas_reprise_id,)).fetchone():
        raise ErreurConge("اختر حالة الاستئناف.")
    if r.date_fin_absence < r.date_debut_absence:
        raise ErreurConge("نهاية الغياب قبل بدايته.")
    if r.date_reprise <= r.date_fin_absence:
        raise ErreurConge("تاريخ الاستئناف يكون بعد نهاية الغياب.")
    r.date_redaction = r.date_redaction or r.date_reprise
    try:
        with conn:
            rid = conn.execute(
                "INSERT INTO reprise_travail(personnel_id, conge_id, cas_reprise_id, date_debut_absence, "
                "date_fin_absence, date_reprise, autres_contacts, date_redaction) VALUES (?,?,?,?,?,?,?,?)",
                (r.personnel_id, r.conge_id, r.cas_reprise_id, r.date_debut_absence, r.date_fin_absence,
                 r.date_reprise, r.autres_contacts or None, r.date_redaction)).lastrowid
    except sqlite3.IntegrityError:
        raise ErreurConge("محضر الاستئناف مسجل من قبل لهذه الرخصة.") from None
    return rid


def valeurs_reprise(conn, reprise_id: int | None, r: dict | None = None,
                    p: rh.Personnel | None = None) -> dict[str, str]:
    r = r or conn.execute("SELECT * FROM reprise_travail WHERE id=?", (reprise_id,)).fetchone()
    if r is None:
        raise ErreurConge("محضر الاستئناف غير موجود.")
    p = p or rh.lire(conn, r["personnel_id"])
    v = _communs(conn)
    v.update(_personnel_valeurs(conn, p, ("ppr", "cin", "cadre", "grade", "fonction", "adresse", "telephone")))
    jours = (date.fromisoformat(r["date_fin_absence"]) - date.fromisoformat(r["date_debut_absence"])).days + 1
    v.update({"date_reprise": tx.date_ar(r["date_reprise"]), "duree": tx.duree_jours_ar(jours),
              "du": tx.date_chiffres(r["date_debut_absence"]), "au": tx.date_chiffres(r["date_fin_absence"]),
              "autres_contacts": r["autres_contacts"] or "—",
              "date_redaction": tx.date_chiffres(r["date_redaction"] or r["date_reprise"])})
    for c in cas_reprise(conn):
        v[f"cas_{c['id']}"] = "☑" if c["id"] == r["cas_reprise_id"] else "☐"
    return v


def generer_reprise(conn, dossier: DossierDonnees, reprise_id: int) -> dc.DocumentGenere:
    v = valeurs_reprise(conn, reprise_id)
    r = conn.execute("SELECT personnel_id, conge_id FROM reprise_travail WHERE id=?", (reprise_id,)).fetchone()
    return dc.generer(conn, dossier, "pv_reprise", v, libelle=f"محضر استئناف {v['nom_complet']}",
                      personnel_id=r["personnel_id"], conge_id=r["conge_id"])


def documents(conn, conge_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT d.id, m.titre, d.date_generation, d.fichier_archive FROM document_genere d "
        "JOIN modele_document m ON m.id=d.modele_id WHERE d.conge_id=? ORDER BY d.id DESC", (conge_id,)).fetchall()


# ---------- معاينة القوالب ببيانات وهمية ----------

def exemple(conn, code: str, sexe: str = "M") -> dict[str, str]:
    p = rh.Personnel(nom_ar="التجريبي", prenom_ar="سعيد" if sexe == "M" else "سلمى", sexe=sexe,
                     categorie="enseignant", ppr="1234567", cin="AB123456", cadre=rh.CADRES[0], grade=rh.GRADES[0],
                     fonction="التدريس", cycle="ابتدائي", matiere="عربية", niveau_enseigne="الرابع",
                     nb_eleves=30, heures_hebdo=30, adresse="[العنوان الشخصي]", telephone="0600000000")
    an = date.today().year
    c = Conge(personnel_id=0, type_conge_id=conn.execute("SELECT MIN(id) FROM type_conge").fetchone()[0],
              date_debut=f"{an}-02-10", duree_jours=10, motif="مرض", adresse_conge="[عنوان الإقامة]",
              date_demande=f"{an}-02-10", avis_directeur="[رأي المدير]", mesures_prises="[الإجراءات المتخذة]",
              medecin="الدكتور [اسم الطبيب]", specialite="[التخصص]", certificat_recu_le=f"{an}-02-10",
              certificat_remis_par="[اسم المدلي]", certificat_remis_par_cin="X000000")
    if code == "demande_conge":
        return valeurs_demande(conn, c, f"1/{_annee(conn)['code_court']}", historique=[], p=p)
    if code == "recu_certificat":
        return valeurs_recu(conn, c, p=p)
    if code == "demande_remplacement":
        return valeurs_remplacement(conn, c, p=p)
    if code == "bordereau_envoi":
        return valeurs_bordereau(conn, [("طلب رخصة يخص الأستاذ سعيد التجريبي", 1), ("شهادة طبية", 1)],
                                 f"1/{_annee(conn)['code_court']}", c.date_demande)
    if code == "pv_reprise":
        r = {"personnel_id": 0, "cas_reprise_id": 6, "date_debut_absence": c.date_debut,
             "date_fin_absence": c.date_fin, "date_reprise": f"{an}-02-20", "autres_contacts": None,
             "date_redaction": f"{an}-02-20"}
        return valeurs_reprise(conn, None, r=r, p=p)
    raise ErreurConge(f"قالب غير معروف: {code}")
