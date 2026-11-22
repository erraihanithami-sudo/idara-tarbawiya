"""شاشة العرض (طلب المدير 2026-11-21): شرائح تُعرض على تلفاز أو شاشة المؤسسة أمام الزوار والآباء والمرتفقين
واللجان، تُولَّد مباشرة من معطيات البرنامج دون أي استيراد. أرقام مجمَّعة فقط: لا أسماء تلاميذ ولا نقط فردية
(قانون 09-08 لحماية المعطيات الشخصية).

لكل شريحة «نقاط» (بطاقة رقم، مستوى، مادة، عملية، منجز، شراكة…) يختار المدير منها ما يُعرض ويزيل العلامة عما لا
يريد عرضه (2026-11-21، الدفعة الثانية)."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path

from idara.services import annee as annee_srv
from idara.services import etablissement as etab_srv
from idara.services import fiches

CLE = "ecran_affichage"
CLE_REALISATIONS = "ecran_realisations"

# (المفتاح، العنوان، الوصف)
CATALOGUE = (
    ("couverture", "المؤسسة بالأرقام", "شعار الوزارة وشعار المؤسسة واسمها والموسم، وعدد التلاميذ والأقسام والأطر."),
    ("indicateurs", "مؤشرات المؤسسة", "مؤشرات يضيفها المدير بنفسه (العنوان والقيمة)."),
    ("cartes_niveaux", "بطاقات المستويات", "لكل مستوى: عدد التلاميذ والأقسام ونسبتا الذكور والإناث."),
    ("niveaux", "التلاميذ حسب المستوى", "الذكور والإناث في كل مستوى."),
    ("pyramide", "هرم الأعمار", "التلاميذ حسب السن: الذكور والإناث."),
    ("ages", "التلاميذ حسب السن والمستوى", "جدول توزيع التلاميذ حسب السن في كل مستوى."),
    ("mouvements", "حركية التلاميذ والهدر", "الوافدون والمغادرون والمنقطعون والمفصولون، بحلقات وعدادات متحركة."),
    ("maitrise", "مستوى التحكم في التعلمات الأساس", "نسبة المتحكمين في كل مادة (آخر رائز متوفر)."),
    ("tarl", "نتائج الدعم المكثف", "نسبة من بلغوا المستوى المتوقع في الرائز القبلي ثم البعدي لكل مستوى."),
    ("acquis", "تقييم مكتسبات المستوى الأول", "توزيع تلاميذ المستوى الأول على مستويات التحكم (أ، ب، ج)."),
    ("isa", "مراحل التدريس الصريح ومؤشر ISA2", "مقارنة مؤشر ISA2 بين المراحل في كل مادة."),
    ("resultats", "النتائج التربوية", "نسبة النجاح، والمستفيدون من الأنشطة."),
    ("examens", "نتائج المراقبة المستمرة والامتحانات", "نسبة النجاح ومعدل كل مستوى."),
    ("honneur", "لوحة الشرف", "الثلاثة الأوائل في كل مستوى (أسماء: بموافقة الأولياء، معطلة افتراضياً)."),
    ("projet", "منجزات مشروع المؤسسة", "نسبة الإنجاز، والعمليات المنجزة من مشروع المؤسسة المندمج."),
    ("realisations", "أهم منجزات المؤسسة", "المنجزات في محاور التلميذ والمدرسة والأستاذ (يكتبها المدير)."),
    ("partenariats", "منجزات الشراكة", "الشراكات وموضوعاتها من سجل «الانفتاح والشراكة»."),
    ("salles", "القاعات والأساتذة الآن", "أين يوجد كل أستاذ(ة) الآن: القاعة والقسم والمادة، من استعمالات الزمن."),
    ("equipements", "مرافق المؤسسة", "المرافق وأعدادها من «البنية المادية» مع صورها."),
    ("galerie", "صور من أنشطتنا", "معرض صور الأنشطة والأيام التواصلية (بموافقة الأولياء، معطل افتراضياً)."),
    ("etoile", "نجم الأسبوع", "شهادة بإطار ذهبي وصورة التلميذ(ة) (بموافقة الولي، معطلة افتراضياً)."),
    ("annonces", "أخبار وإعلانات", "أخبار وإعلانات يكتبها المدير."),
)
# شرائح فيها أسماء أو صور تلاميذ، أو نصوص يكتبها المدير: لا تُفعَّل إلا باختياره
INACTIVES_DEFAUT = {"honneur", "galerie", "etoile", "annonces"}
# شرائح تتغير مع الساعة: يُعاد حسابها عند كل ظهور
DYNAMIQUES = {"salles"}
CLE_INDICATEURS = "ecran_indicateurs"
CLE_ANNONCES = "ecran_annonces"
CLE_ETOILE = "ecran_etoile"
MINISTERE = Path(__file__).resolve().parent.parent / "resources" / "ministere.png"
TITRES = {c: t for c, t, _ in CATALOGUE}
DUREE_DEFAUT = 12      # ثوانٍ لكل شريحة
DUREES = (6, 8, 10, 12, 15, 20, 30, 45, 60)
AXES = (("eleve", "محور التلميذ"), ("ecole", "محور المدرسة"), ("professeur", "محور الأستاذ"))
LIB_AXES = dict(AXES)


class ErreurEcran(ValueError):
    pass


def reglages(conn: sqlite3.Connection) -> dict:
    """الإعدادات: الترتيب، الشرائح المفعّلة، المدة، الشريط المتحرك، الشعار، والنقاط المخفية لكل شريحة."""
    d = fiches.lire(conn, CLE) or {}
    connues = set(d.get("ordre", []))
    ordre = [c for c in d.get("ordre", []) if c in TITRES]
    ordre += [c for c, *_ in CATALOGUE if c not in ordre]
    actives = d.get("actives")
    actives = set(actives) if isinstance(actives, list) else set()
    # الشرائح الجديدة (غير المحفوظة في الترتيب) تأخذ حالتها الافتراضية
    actives = [c for c in ordre if c in actives or (c not in connues and c not in INACTIVES_DEFAUT)]
    durees = {c: int(d.get("durees", {}).get(c, DUREE_DEFAUT)) for c in ordre}
    masques = {c: list(v) for c, v in (d.get("masques") or {}).items() if c in TITRES}
    return {"ordre": ordre, "actives": actives, "durees": durees, "bandeau": d.get("bandeau", ""),
            "logo": d.get("logo", ""), "masques": masques, "ministere": d.get("ministere", "")}


def _ecrire(conn, r: dict) -> dict:
    fiches.ecrire(conn, CLE, {k: r[k] for k in ("ordre", "actives", "durees", "bandeau", "logo", "masques",
                                                "ministere")})
    return reglages(conn)


def enregistrer_reglages(conn: sqlite3.Connection, ordre: list[str], actives: list[str], durees: dict[str, int],
                         bandeau: str = "") -> dict:
    ordre = [c for c in ordre if c in TITRES]
    if not ordre:
        raise ErreurEcran("الشرائح غير معروفة.")
    ordre += [c for c, *_ in CATALOGUE if c not in ordre]
    actives = [c for c in ordre if c in actives]
    if not actives:
        raise ErreurEcran("اختر شريحة واحدة على الأقل للعرض.")
    r = reglages(conn)
    r.update(ordre=ordre, actives=actives, bandeau=" ".join((bandeau or "").split()),
             durees={c: max(3, min(300, int(durees.get(c, r["durees"].get(c, DUREE_DEFAUT))))) for c in ordre})
    return _ecrire(conn, r)


def definir_masques(conn: sqlite3.Connection, cle: str, caches: list[str]) -> dict:
    """النقاط التي أزال المدير علامتها في شريحة (لا تُعرض)."""
    if cle not in TITRES:
        raise ErreurEcran("شريحة غير معروفة.")
    r = reglages(conn)
    r["masques"][cle] = [str(x) for x in caches]
    return _ecrire(conn, r)


def definir_logo(conn: sqlite3.Connection, dossier, source) -> str:
    """ينسخ شعار المؤسسة (PNG/JPG) إلى مجلد البيانات ويحفظه للعرض. source=None يزيله."""
    r = reglages(conn)
    if source is None:
        r["logo"] = ""
    else:
        try:
            r["logo"] = etab_srv.importer_image(dossier, source, "logo_ecran")
        except Exception as e:  # noqa: BLE001 — ErreurValidation
            raise ErreurEcran(str(e)) from e
    _ecrire(conn, r)
    return r["logo"]


def definir_logo_ministere(conn: sqlite3.Connection, dossier, source=None, masquer: bool = False) -> str:
    """شعار الوزارة في الغلاف: المدمج في البرنامج افتراضياً، أو صورة يختارها المدير، أو لا شيء (masquer)."""
    r = reglages(conn)
    if masquer:
        r["ministere"] = "aucun"
    elif source is None:
        r["ministere"] = ""
    else:
        try:
            r["ministere"] = etab_srv.importer_image(dossier, source, "logo_ministere")
        except Exception as e:  # noqa: BLE001
            raise ErreurEcran(str(e)) from e
    _ecrire(conn, r)
    return r["ministere"]


def chemin_ministere(conn: sqlite3.Connection, dossier) -> str:
    rel = reglages(conn)["ministere"]
    if rel == "aucun":
        return ""
    if rel and dossier is not None and (dossier.racine / rel).exists():
        return str(dossier.racine / rel)
    return str(MINISTERE) if MINISTERE.exists() else ""


def chemin_logo(conn: sqlite3.Connection, dossier) -> str:
    rel = reglages(conn)["logo"]
    if not rel or dossier is None:
        return ""
    p = dossier.racine / rel
    return str(p) if p.exists() else ""


# ---------- المنجزات حسب المحاور (يكتبها المدير) ----------

def realisations(conn: sqlite3.Connection) -> list[dict]:
    return list((fiches.lire(conn, CLE_REALISATIONS) or {}).get("lignes", []))


def ajouter_realisation(conn: sqlite3.Connection, axe: str, texte: str) -> dict:
    if axe not in LIB_AXES:
        raise ErreurEcran("اختر المحور: التلميذ أو المدرسة أو الأستاذ.")
    texte = " ".join((texte or "").split())
    if not texte:
        raise ErreurEcran("اكتب المنجز.")
    if len(texte) > 140:
        raise ErreurEcran("المنجز طويل: جملة قصيرة تُقرأ من بعيد (140 حرفاً على الأكثر).")
    ls = realisations(conn)
    nid = max([int(l["id"]) for l in ls] + [0]) + 1
    l = {"id": nid, "axe": axe, "texte": texte}
    fiches.ecrire(conn, CLE_REALISATIONS, {"lignes": ls + [l]})
    return l


def supprimer_realisation(conn: sqlite3.Connection, rid: int) -> None:
    fiches.ecrire(conn, CLE_REALISATIONS, {"lignes": [l for l in realisations(conn) if int(l["id"]) != int(rid)]})


# ---------- مؤشرات المدير، والإعلانات، ونجم الأسبوع (2026-11-22) ----------

def _liste(conn, cle: str) -> list[dict]:
    return list((fiches.lire(conn, cle) or {}).get("lignes", []))


def _ajouter(conn, cle: str, ligne: dict, maxi: int) -> dict:
    ls = _liste(conn, cle)
    if len(ls) >= maxi:
        raise ErreurEcran(f"بلغت {maxi} عناصر، وهو الحد الذي يُقرأ على الشاشة. احذف عنصراً أولاً.")
    ligne = {"id": max([int(l["id"]) for l in ls] + [0]) + 1, **ligne}
    fiches.ecrire(conn, cle, {"lignes": ls + [ligne]})
    return ligne


def _supprimer(conn, cle: str, lid: int) -> None:
    fiches.ecrire(conn, cle, {"lignes": [l for l in _liste(conn, cle) if int(l["id"]) != int(lid)]})


def _court(t: str, lib: str, maxi: int, obligatoire: bool = True) -> str:
    t = " ".join((t or "").split())
    if obligatoire and not t:
        raise ErreurEcran(f"اكتب {lib}.")
    if len(t) > maxi:
        raise ErreurEcran(f"{lib} طويل: {maxi} حرفاً على الأكثر ليُقرأ من بعيد.")
    return t


def indicateurs_perso(conn: sqlite3.Connection) -> list[dict]:
    return _liste(conn, CLE_INDICATEURS)


def ajouter_indicateur(conn: sqlite3.Connection, libelle: str, valeur: str, sous: str = "") -> dict:
    """مؤشر يضيفه المدير: «نسبة التمدرس» = «98%»…"""
    return _ajouter(conn, CLE_INDICATEURS, {"libelle": _court(libelle, "عنوان المؤشر", 40),
                                            "valeur": _court(str(valeur), "قيمة المؤشر", 12),
                                            "sous": _court(sous, "التوضيح", 50, False)}, 8)


def supprimer_indicateur(conn: sqlite3.Connection, lid: int) -> None:
    _supprimer(conn, CLE_INDICATEURS, lid)


def annonces(conn: sqlite3.Connection) -> list[dict]:
    return _liste(conn, CLE_ANNONCES)


def ajouter_annonce(conn: sqlite3.Connection, titre: str, texte: str = "", le: str = "") -> dict:
    return _ajouter(conn, CLE_ANNONCES, {"titre": _court(titre, "عنوان الإعلان", 70),
                                         "texte": _court(texte, "نص الإعلان", 160, False),
                                         "date": le or date.today().isoformat()}, 6)


def supprimer_annonce(conn: sqlite3.Connection, lid: int) -> None:
    _supprimer(conn, CLE_ANNONCES, lid)


def etoile(conn: sqlite3.Connection) -> dict:
    return fiches.lire(conn, CLE_ETOILE) or {}


def definir_etoile(conn: sqlite3.Connection, dossier, nom: str, classe: str = "", motif: str = "",
                   photo=None, consentement: bool = False, eleve_id: int | None = None) -> dict:
    """نجم الأسبوع: الاسم والقسم وسبب التتويج، وصورته (بموافقة الولي فقط)."""
    nom = _court(nom, "اسم التلميذ(ة)", 60)
    if photo is not None and not consentement:
        raise ErreurEcran("لا تُعرض صورة التلميذ(ة) إلا بموافقة وليه: علّم خانة الموافقة.")
    ancien = etoile(conn)
    d = {"nom": nom, "classe": _court(classe, "القسم", 30, False), "motif": _court(motif, "سبب التتويج", 120, False),
         "eleve_id": eleve_id, "semaine": date.today().isoformat(), "photo": ancien.get("photo", "") if
         ancien.get("nom") == nom else "", "consentement": bool(consentement)}
    if photo is not None:
        try:
            d["photo"] = etab_srv.importer_image(dossier, photo, "etoile_semaine")
        except Exception as e:  # noqa: BLE001
            raise ErreurEcran(str(e)) from e
    if not consentement:
        d["photo"] = ""
    fiches.ecrire(conn, CLE_ETOILE, d)
    return d


def retirer_etoile(conn: sqlite3.Connection) -> None:
    fiches.ecrire(conn, CLE_ETOILE, {})


# ---------- القاعات: أين الأستاذ(ة) الآن ----------

JOURS = ("الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد")


def _mn(h: str) -> int:
    try:
        a, b = h.split(":")
        return int(a) * 60 + int(b)
    except (ValueError, AttributeError):
        return -1


def ou_sont(conn: sqlite3.Connection, le: datetime | None = None) -> list[dict]:
    """لكل أستاذ(ة) له حصص اليوم: الحصة الجارية (القاعة والقسم والمادة)، أو حصته القادمة."""
    from idara.services import personnel as rh
    from idara.services import vie_admin as va
    le = le or datetime.now()
    jour = JOURS[le.weekday()]
    m = le.hour * 60 + le.minute
    res = []
    for p in rh.lister(conn):
        if p.statut != "actif" or p.categorie != "enseignant":
            continue
        ss = sorted((s for s in va.lire_emploi(conn, p.id) if s[0] == jour), key=lambda s: s[1])
        if not ss:
            continue
        cour = next((s for s in ss if _mn(s[1]) <= m < _mn(s[2])), None)
        proch = next((s for s in ss if _mn(s[1]) > m), None)
        s, etat = (cour, "en_cours") if cour else (proch, "prochaine") if proch else (ss[-1], "termine")
        res.append({"id": str(p.id), "libelle": f"{p.prenom_ar} {p.nom_ar}", "etat": etat, "debut": s[1], "fin": s[2],
                    "matiere": s[3], "classe": s[4], "salle": s[5]})
    ordre = {"en_cours": 0, "prochaine": 1, "termine": 2}
    return sorted(res, key=lambda x: (ordre[x["etat"]], x["salle"] or "~", x["libelle"]))


def ou_est(conn: sqlite3.Connection, texte: str, le: datetime | None = None) -> str:
    """جواب البحث السريع: «أين الأستاذ(ة) فلان الآن؟»."""
    from idara.services import personnel as rh
    texte = " ".join((texte or "").split())
    if len(texte) < 2:
        return "اكتب جزءاً من اسم الأستاذ(ة)."
    ids = {str(p.id) for p in rh.lister(conn, texte)}
    if not ids:
        return f"لا أستاذ(ة) باسم «{texte}»."
    ls = [x for x in ou_sont(conn, le) if x["id"] in ids]
    if not ls:
        return "لا حصص مسجلة اليوم لهذا الاسم في استعمالات الزمن."
    res = []
    for x in ls[:4]:
        ou = f"القاعة {x['salle']}" if x["salle"] else "قاعة غير محددة"
        quoi = " · ".join(v for v in (x["classe"], x["matiere"]) if v)
        if x["etat"] == "en_cours":
            res.append(f"{x['libelle']}: الآن في {ou} ({quoi}) حتى {x['fin']}.")
        elif x["etat"] == "prochaine":
            res.append(f"{x['libelle']}: لا حصة الآن؛ حصته القادمة {x['debut']} في {ou} ({quoi}).")
        else:
            res.append(f"{x['libelle']}: أنهى حصصه اليوم (آخرها في {ou}).")
    return "\n".join(res)


# ---------- الأعمار ----------

def _annee_debut(conn) -> int | None:
    import re
    a = annee_srv.annee_courante(conn)
    m = re.search(r"(\d{4})", a["libelle"]) if a else None
    return int(m.group(1)) if m else None


def repartition_ages(conn: sqlite3.Connection) -> list[dict]:
    """[{niveau، libelle، par_age: {سن: {M، F}}}] — السن في 31 دجنبر من بداية الموسم."""
    from idara.services import textes as tx
    from idara.services.statistiques import ORDRE_NIVEAUX
    a = annee_srv.annee_courante(conn)
    y = _annee_debut(conn)
    if a is None or y is None:
        return []
    par: dict[str, dict[int, dict[str, int]]] = {}
    for r in conn.execute("SELECT n.code AS niveau, e.sexe, e.date_naissance FROM inscription i JOIN eleve e "
                          "ON e.id=i.eleve_id LEFT JOIN niveau n ON n.id=i.niveau_id WHERE i.annee_id=? AND "
                          "i.statut IN ('inscrit','arrive') AND e.date_naissance IS NOT NULL", (a["id"],)):
        try:
            age = y - int(str(r["date_naissance"])[:4])
        except ValueError:
            continue
        if not 2 <= age <= 20 or not r["niveau"]:
            continue
        c = par.setdefault(r["niveau"], {}).setdefault(age, {"M": 0, "F": 0})
        c["F" if r["sexe"] == "F" else "M"] += 1
    rang = lambda n: ORDRE_NIVEAUX.index(n) if n in ORDRE_NIVEAUX else 99  # noqa: E731
    return [{"niveau": n, "libelle": tx.niveau_ar(n) if n in tx.NIVEAUX else n, "par_age": par[n]}
            for n in sorted(par, key=rang)]


# ---------- النتائج ----------

def _moyennes(conn, aid: int) -> list[sqlite3.Row]:
    return conn.execute("SELECT r.nom, r.classe, r.niveau, COALESCE(r.moyenne, r.moyenne_s2, r.moyenne_s1) AS m "
                        "FROM resultat r WHERE r.annee_id=?", (aid,)).fetchall()


def _par_niveau_resultats(conn) -> dict[str, list]:
    from idara.services.statistiques import ORDRE_NIVEAUX
    a = annee_srv.annee_courante(conn)
    if a is None:
        return {}
    par: dict[str, list] = {}
    for r in _moyennes(conn, a["id"]):
        if r["niveau"] and r["m"] is not None:
            par.setdefault(r["niveau"], []).append(r)
    return dict(sorted(par.items(), key=lambda kv: ORDRE_NIVEAUX.index(kv[0]) if kv[0] in ORDRE_NIVEAUX else 99))


# ---------- محتوى الشرائح ----------

def _pct(n: int, d: int) -> float | None:
    return round(100 * n / d, 1) if d else None


def identite(conn: sqlite3.Connection, dossier=None) -> dict:
    e = etab_srv.lire_etablissement(conn)
    a = annee_srv.annee_courante(conn)
    return {"nom": (e.nom_ar if e else "") or "المؤسسة", "annee": a["libelle"] if a else "",
            "pionniere": bool(e and getattr(e, "est_pionniere", False)), "logo": chemin_logo(conn, dossier),
            "ministere": chemin_ministere(conn, dossier)}


def bandeau_defaut(conn: sqlite3.Connection) -> str:
    i = identite(conn)
    return f"مرحباً بكم في {i['nom']}   ·   مدرسة الجودة والإنصاف   ·   الموسم الدراسي {i['annee']}"


def _items(conn: sqlite3.Connection, cle: str, dossier=None, le: datetime | None = None) -> tuple[list[dict], dict]:
    """(النقاط، معطيات إضافية للشريحة). لكل نقطة id ثابت و libelle (يظهر في نافذة الاختيار)."""
    from idara.services import statistiques as st
    from idara.services import tableau_bord as tb
    if cle in _NOUVELLES:
        return _NOUVELLES[cle](conn, dossier, le)
    if cle == "couverture":
        ind = tb.indicateurs(conn)
        return [{"id": "eleves", "libelle": "تلميذة وتلميذاً", "valeur": ind["eleves"], "sous": "مجموع المتمدرسين",
                 "couleur": "or"},
                {"id": "garcons", "libelle": "ذكور", "valeur": ind["garcons"], "couleur": "bleu"},
                {"id": "filles", "libelle": "إناث", "valeur": ind["filles"], "couleur": "rose"},
                {"id": "classes", "libelle": "قسماً", "valeur": len(ind["classes"]), "couleur": "violet"},
                {"id": "personnel", "libelle": "إطاراً", "valeur": ind["personnel"], "sous": "تربوياً وإدارياً",
                 "couleur": "vert"}], {"vide": not ind["eleves"] and not ind["personnel"]}
    if cle == "niveaux":
        return [{"id": n["niveau"], "libelle": n["libelle"], "valeurs": [n["garcons"], n["filles"]]}
                for n in st.par_niveau(conn)], {}
    if cle == "maitrise":
        a = annee_srv.annee_courante(conn)
        m = tb._maitrise(conn, a["libelle"], None) if a else {}
        return [{"id": k, "libelle": v["matiere"], "taux": v["taux"], "sous": v["epreuve"]}
                for k, v in m.items() if v["total"]], {}
    if cle == "tarl":
        return [{"id": n["niveau"], "libelle": n["libelle"], "valeurs": [n["pre"], n["post"]]}
                for n in st.evolution_tarl(conn) if n["pre"] is not None or n["post"] is not None], {}
    if cle == "resultats":
        ind = tb.indicateurs(conn)
        r = tb._reussite(conn, annee_srv.annee_courante(conn)["id"], None) if annee_srv.annee_courante(conn) else {}
        items = []
        if r.get("total"):
            items.append({"id": "reussite", "libelle": "نسبة النجاح", "taux": r["taux"], "sous": r["source"]})
        if ind["eleves"]:
            items.append({"id": "activites", "libelle": "المستفيدون من الأنشطة", "taux": ind["activites"]["taux"],
                          "sous": "الأندية والأنشطة"})
        h = ind["hadar"]
        if h["concernes"] and h["taux"] is not None:
            items.append({"id": "hadar", "libelle": "نسبة الهدر المدرسي", "taux": h["taux"],
                          "sous": "المنقطعون والمفصولون"})
        return items, {}
    if cle == "projet":
        from idara.services import projet_etab as pe
        p = pe.projet_actif(conn)
        if p is None:
            return [], {}
        s = pe.synthese_operations(conn, p["id"])
        ops = [o for o in pe.operations(conn, p["id"]) if o["statut"] == "realisee"]
        return ([{"id": str(o["id"]), "libelle": o["intitule"], "axe": o["axe"] or ""} for o in ops],
                {"intitule": p["intitule"], "pct_realisees": s["pct_realisees"], "taux_global": s["taux_global"],
                 "actives": s["actives"], "realisees": s["par_statut"]["realisee"]})
    if cle == "realisations":
        return [{"id": str(l["id"]), "libelle": l["texte"], "axe": l["axe"]} for l in realisations(conn)], {}
    if cle == "partenariats":
        from idara.services import registres as rg
        ls = [l for l in rg.lister(conn, "partenariats") if l.get("etat") != "قيد الإعداد"]
        return [{"id": str(l["id"]), "libelle": l["partenaire"], "objet": l["objet"], "etat": l.get("etat", "")}
                for l in ls], {}
    if cle == "mouvements":
        from idara.services import mouvements as mv
        try:
            t = mv.statistiques(conn)["totaux"]
        except Exception:  # noqa: BLE001 — لا سنة جارية
            t = {}
        items = [{"id": "arrive", "libelle": "وافدون", "valeur": t.get("arrive", 0), "sous": "التحقوا بمؤسستنا",
                  "couleur": "vert"},
                 {"id": "parti", "libelle": "مغادرون", "valeur": t.get("parti", 0),
                  "sous": "انتقلوا إلى مؤسسات أخرى", "couleur": "orange"},
                 {"id": "interrompu", "libelle": "منقطعون", "valeur": t.get("interrompu", 0),
                  "sous": "نتابعهم لإرجاعهم", "couleur": "rouge"},
                 {"id": "exclu", "libelle": "مفصولون", "valeur": t.get("exclu", 0), "couleur": "violet"}]
        n = tb.indicateurs(conn)["eleves"]
        for i in items:
            i["taux"] = _pct(i["valeur"], n)   # نسبة من مجموع المتمدرسين
        return items, {"vide": not any(i["valeur"] for i in items), "effectif": n}
    raise ErreurEcran("شريحة غير معروفة.")


def _it_indicateurs(conn, dossier, le):
    return [{"id": str(l["id"]), "libelle": l["libelle"], "valeur": l["valeur"], "sous": l.get("sous", "")}
            for l in indicateurs_perso(conn)], {}


def _it_cartes_niveaux(conn, dossier, le):
    from idara.services import statistiques as st
    return [{"id": n["niveau"], "libelle": n["libelle"], "eleves": n["eleves"], "classes": n["classes"],
             "garcons": n["garcons"], "filles": n["filles"], "pct_garcons": n["pct_garcons"],
             "pct_filles": n["pct_filles"]} for n in st.par_niveau(conn)], {}


def _it_pyramide(conn, dossier, le):
    ages: dict[int, list[int]] = {}
    for n in repartition_ages(conn):
        for a, c in n["par_age"].items():
            v = ages.setdefault(a, [0, 0])
            v[0] += c["M"]
            v[1] += c["F"]
    return [{"id": str(a), "libelle": f"{a} سنوات" if 3 <= a <= 10 else f"{a} سنة", "valeurs": ages[a]}
            for a in sorted(ages, reverse=True)], {}


def _it_ages(conn, dossier, le):
    ns = repartition_ages(conn)
    tous = sorted({a for n in ns for a in n["par_age"]})
    return [{"id": n["niveau"], "libelle": n["libelle"],
             "par_age": {str(a): c["M"] + c["F"] for a, c in n["par_age"].items()}} for n in ns], {"ages": tous}


def _it_acquis(conn, dossier, le):
    from idara.services import isa
    from idara.services.massar import niveaux_du_code_classe
    a = annee_srv.annee_courante(conn)
    if a is None:
        return [], {}
    don = {c: v for c, v in isa.resultats(conn, a["libelle"]).items() if niveaux_du_code_classe(c)[:1] == ["1AP"]}
    phases = sorted({p for v in don.values() for m in v.values() for p in m})
    if not phases:
        return [], {}
    ph = phases[-1] if any(p >= 1 for p in phases) else phases[0]
    items = []
    for m, lib in isa.MATIERES.items():
        k = isa.ensemble(don, m, ph)
        if k and k.total:
            items.append({"id": m, "libelle": lib, "valeurs": [k.pct(k.a), k.pct(k.b), k.pct(k.c)],
                          "total": k.total})
    return items, {"phase": isa.libelle_phase(ph)}


def _it_isa(conn, dossier, le):
    from idara.services import isa
    a = annee_srv.annee_courante(conn)
    if a is None:
        return [], {}
    don = isa.resultats(conn, a["libelle"])
    etapes = sorted({p for v in don.values() for m in v.values() for p in m if isa.est_etape(p)})
    items = []
    for m, lib in isa.MATIERES.items():
        vals = [(isa.ensemble(don, m, p) or isa.Calcul(0, 0, 0)).isa for p in etapes]
        if any(v is not None for v in vals):
            items.append({"id": m, "libelle": lib, "valeurs": vals})
    return items, {"phases": [isa.libelle_phase(p) for p in etapes]}


def _it_examens(conn, dossier, le):
    from idara.services import textes as tx
    from idara.services.evaluation import SEUIL
    items = []
    for n, rs in _par_niveau_resultats(conn).items():
        ok = sum(1 for r in rs if r["m"] >= SEUIL)
        items.append({"id": n, "libelle": tx.niveau_ar(n) if n in tx.NIVEAUX else n,
                      "valeurs": [_pct(ok, len(rs))], "moyenne": round(sum(r["m"] for r in rs) / len(rs), 2),
                      "total": len(rs)})
    return items, {}


def _it_honneur(conn, dossier, le):
    from idara.services import textes as tx
    items = []
    for n, rs in _par_niveau_resultats(conn).items():
        top = sorted(rs, key=lambda r: -r["m"])[:3]
        items.append({"id": n, "libelle": tx.niveau_ar(n) if n in tx.NIVEAUX else n,
                      "podium": [{"nom": r["nom"], "classe": (r["classe"] or "").replace("-", "")} for r in top]})
    return items, {}


def _it_salles(conn, dossier, le):
    return ou_sont(conn, le), {"heure": f"{(le or datetime.now()):%H:%M}"}


def _it_equipements(conn, dossier, le):
    from idara.services import photos as ph
    from idara.services import structure as su
    items = []
    for l in su.tableau(conn)["lignes"]:
        if not l["total"]:
            continue
        ps = [ph.chemin(dossier, p) for p in ph.lister(conn, "structure", l["element"])] if dossier else []
        items.append({"id": l["element"], "libelle": l["libelle"].replace("عدد ", ""), "valeur": l["total"],
                      "photo": next((str(x) for x in ps if x.exists()), "")})
    return items, {}


def _it_galerie(conn, dossier, le):
    from idara.services import photos as ph
    from idara.services import pionniere as pn
    from idara.services import vie_scolaire as vs
    if dossier is None:
        return [], {}
    items = []
    try:
        acts = vs.activites(conn)
    except Exception:  # noqa: BLE001 — لا سنة جارية
        acts = []
    for a in reversed(acts):
        ps = [str(ph.chemin(dossier, p)) for p in ph.lister(conn, "activite", a["id"])]
        ps = [x for x in ps if Path(x).exists()]
        if ps:
            items.append({"id": f"activite:{a['id']}", "libelle": a["titre"], "photos": ps})
    try:
        rs = pn.rencontres(conn)
    except Exception:  # noqa: BLE001
        rs = []
    for r in rs:
        ps = [str(ph.chemin(dossier, p)) for p in ph.lister(conn, "rencontre", r.id)]
        ps = [x for x in ps if Path(x).exists()]
        if ps:
            items.append({"id": f"rencontre:{r.id}", "libelle": f"{pn.TYPES_RENCONTRE[r.type]}: {r.theme}".strip(": "),
                          "photos": ps})
    return items, {}


def _it_etoile(conn, dossier, le):
    e = etoile(conn)
    if not e.get("nom"):
        return [], {}
    photo = ""
    if e.get("photo") and e.get("consentement") and dossier is not None and (dossier.racine / e["photo"]).exists():
        photo = str(dossier.racine / e["photo"])
    return [{"id": "etoile", "libelle": e["nom"], "classe": e.get("classe", ""), "motif": e.get("motif", ""),
             "photo": photo, "semaine": e.get("semaine", "")}], {}


def _it_annonces(conn, dossier, le):
    from idara.services import textes as tx
    return [{"id": str(l["id"]), "libelle": l["titre"], "texte": l.get("texte", ""),
             "date": tx.date_chiffres(l["date"]) if l.get("date") else ""} for l in annonces(conn)], {}


_NOUVELLES = {"indicateurs": _it_indicateurs, "cartes_niveaux": _it_cartes_niveaux, "pyramide": _it_pyramide,
              "ages": _it_ages, "acquis": _it_acquis, "isa": _it_isa, "examens": _it_examens,
              "honneur": _it_honneur, "salles": _it_salles, "equipements": _it_equipements,
              "galerie": _it_galerie, "etoile": _it_etoile, "annonces": _it_annonces}


def points(conn: sqlite3.Connection, cle: str, dossier=None) -> list[dict]:
    """كل نقاط الشريحة مع حالة العرض (للنافذة التي يختار منها المدير)."""
    caches = set(reglages(conn)["masques"].get(cle, []))
    return [{"id": i["id"], "libelle": i["libelle"] + (f" ({LIB_AXES.get(i.get('axe'), i.get('axe'))})"
                                                       if i.get("axe") else ""),
             "affiche": i["id"] not in caches} for i in _items(conn, cle, dossier)[0]]


def diapositive(conn: sqlite3.Connection, cle: str, le: datetime | None = None, masques: dict | None = None,
                dossier=None) -> dict:
    """محتوى شريحة واحدة بعد إخفاء النقاط التي أزال المدير علامتها: {cle، titre، vide، items، ...}."""
    if masques is None:
        masques = reglages(conn)["masques"]
    items, extra = _items(conn, cle, dossier, le if isinstance(le, datetime) else None)
    caches = set(masques.get(cle, []))
    items = [i for i in items if i["id"] not in caches]
    d = {"cle": cle, "titre": TITRES[cle], "items": items}
    d.update(extra)
    d["vide"] = extra.get("vide", False) or not items
    return d


def diaporama(conn: sqlite3.Connection, le: datetime | None = None, avec_vides: bool = False, dossier=None) -> list[dict]:
    """الشرائح المفعّلة بترتيبها مع مدة كل واحدة. الشريحة التي لا نقاط لها تُسقط (إلا الغلاف)."""
    r = reglages(conn)
    res = []
    for c in r["actives"]:
        d = diapositive(conn, c, le, r["masques"], dossier)
        if d["vide"] and c != "couverture" and not avec_vides:
            continue
        d["duree"] = r["durees"][c]
        res.append(d)
    return res
