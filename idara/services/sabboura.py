"""السبورة المرجعية (القيادة والتدبير؛ نماذج المدير 2026-11-13).

إحدى عشرة لوحة تُعلَّق في مكتب الإدارة، كل لوحة صفحة A4 على شكل نموذج المدير: ترويسة المؤسسة، شريط العنوان
البرتقالي، ثم جدول برأس أزرق. اللوحات:
بطاقة معلومات المؤسسة، البنية التربوية، التنظيم التربوي، البنية المادية للمؤسسة، الأندية التربوية، المجلس التربوي،
مجلس التدبير، جمعية دعم مدرسة النجاح، الجمعية الرياضية المدرسية، خلايا المؤسسة، استعمال الزمن الجماعي (أفقية).
كل لوحة تُملأ من معطيات البرنامج، وتُعدَّل يدوياً، وتُولَّد وحدها أو مع باقي اللوحات في وثيقة واحدة.
"""

from __future__ import annotations

import io
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from idara.data.dossier import DossierDonnees
from idara.data.journal import journaliser
from idara.services import annee as annee_srv
from idara.services import etablissement as etab_srv
from idara.services import personnel as rh
from idara.services import textes as tx

BLEU = "0070C0"
ORANGE = "F7A21B"


class ErreurSabboura(ValueError):
    """رسالة موجهة للمدير بالعربية."""


@dataclass(frozen=True)
class Champ:
    cle: str
    libelle: str
    plein: bool = False          # سطر كامل (العنوان، المجاميع)


@dataclass(frozen=True)
class Lavha:
    cle: str
    titre: str
    nature: str                  # fiche | tableau | cellules
    champs: tuple = ()
    colonnes: tuple = ()
    groupes: tuple = ()          # رأس من مستويين: ((العنوان، عدد الأعمدة)...)
    numero: bool = False
    paysage: bool = False
    defaut: tuple = ()           # أسطر مقترحة
    lignes_vides: int = 0        # أسطر فارغة إضافية تُملأ باليد (استعمال الزمن)
    note: str = ""               # سطر حر تحت الجدول (منسقة التعاونية المدرسية...)
    source: str = ""


C = Champ
_ROLES_CONSEIL = ("رئيس المجلس", "ممثل القسم الأول", "ممثل القسم الثاني", "ممثل القسم الثالث", "ممثل القسم الرابع",
                  "ممثل القسم الخامس", "ممثل القسم السادس")
_ROLES_ASSO = ("رئيس الجمعية", "نائب الرئيس", "الكاتب(ة)", "نائب(ة) الكاتب(ة)", "أمين المال", "نائب الأمين", "مستشار")
_JOURS = ("الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت")

LAVHAT: list[Lavha] = [
    Lavha("fiche", "بطاقة معلومات المؤسسة", "fiche", champs=(
        C("nom", "اسم المؤسسة"), C("cycle", "السلك"), C("milieu", "الوسط"), C("commune", "الجماعة"),
        C("gresa", "رمز Gresa"), C("gipe", "رمز GIPE"), C("adresse", "عنوان المؤسسة", True),
        C("creation", "تاريخ إحداث المؤسسة"), C("fonctionnement", "تاريخ تشغيل المؤسسة"),
        C("nb_admin", "عدد الأطر الإدارية"), C("directeur", "اسم المدير"),
        C("affectation", "تاريخ التعيين بالمؤسسة"), C("telephone", "رقم الهاتف"),
        C("prof_m", "عدد الأساتذة ذكور"), C("prof_f", "عدد الأساتذة إناث"),
        C("classes", "عدد الأقسام الدراسية", True), C("eleves_primaire", "مجموع تلاميذ التعليم الابتدائي", True),
        C("eleves_prescolaire", "مجموع تلاميذ التعليم الأولي", True),
        C("gardiens", "عدد مستخدمي الحراسة"), C("proprete", "عدد مستخدمي النظافة"),
        C("eleves_m", "عدد تلاميذ المؤسسة ذكور"), C("eleves_f", "عدد تلاميذ المؤسسة إناث"),
        C("educatrices", "عدد مربيات التعليم الأولي"), C("classes_prescolaire", "عدد أقسام التعليم الأولي"),
        C("prescolaire_m", "عدد تلاميذ التعليم الأولي ذكور"), C("prescolaire_f", "عدد تلاميذ التعليم الأولي إناث"),
        C("salles", "عدد حجرات التعليم العام"), C("salles_prescolaire", "عدد حجرات التعليم الأولي")),
        source="من إعداد المؤسسة والمدير والموارد البشرية واللوائح والبنية المادية. رمز GIPE وتاريخ التشغيل يدويان."),
    Lavha("structure_ped", "البنية التربوية", "tableau", colonnes=("المستوى", "عدد الأقسام"),
          source="عدد الأقسام (الأفواج) في كل مستوى من اللوائح المستوردة؛ القسم المشترك يُعد في كل مستوى من مستوياته."),
    Lavha("tanzim", "التنظيم التربوي", "tableau",
          colonnes=("الاسم والنسب", "المستوى المسند", "عدد التلاميذ: إ", "عدد التلاميذ: ذ", "عدد التلاميذ: مج"),
          groupes=(("الاسم والنسب", 1), ("المستوى المسند", 1), ("عدد التلاميذ", 3)), numero=True,
          source="الأساتذة والأقسام المسندة إليهم وعدد تلاميذها (إناث، ذكور، المجموع)."),
    Lavha("structure_mat", "البنية المادية للمؤسسة", "tableau", colonnes=("المكوّن", "العدد"),
          source="من صفحة البنية المادية (التدبير المالي والمادي)."),
    Lavha("clubs", "الأندية التربوية", "tableau", colonnes=("النادي", "المنسق(ة)"), note="منسق(ة) التعاونية المدرسية",
          source="من الأندية والأنشطة (النادي ومنشطه)."),
    Lavha("conseil_ped", "المجلس التربوي", "tableau", colonnes=("الاسم", "الصفة"),
          defaut=tuple(("", r) for r in _ROLES_CONSEIL), source="من مجالس المؤسسة: أعضاء المجلس التربوي."),
    Lavha("conseil_gestion", "مجلس التدبير", "tableau", colonnes=("الاسم", "الصفة"),
          defaut=tuple(("", r) for r in _ROLES_CONSEIL), source="من مجالس المؤسسة: أعضاء مجلس التدبير."),
    Lavha("najah", "جمعية دعم مدرسة النجاح", "tableau", colonnes=("الاسم", "المهمة"),
          defaut=tuple(("", r) for r in _ROLES_ASSO), source="الرئيس وأمين المال من صفحة الجمعية، والباقي يدوي."),
    Lavha("sportive", "الجمعية الرياضية المدرسية", "tableau", colonnes=("الاسم", "المهمة"),
          defaut=tuple(("", r) for r in _ROLES_ASSO), source="يدوي."),
    Lavha("cellules", "خلايا المؤسسة", "cellules", colonnes=("الخلية", "الأعضاء"),
          defaut=(("خلية اليقظة", ""), ("خلية الإنصات", "")),
          source="يدوي: لكل خلية أعضاؤها مفصولون بفاصلة."),
    Lavha("emploi", "استعمال الزمن الجماعي", "tableau", paysage=True, numero=True,
          colonnes=("اسم الأستاذ(ة)", "رقم التأجير") + tuple(f"{j}: {m}" for j in _JOURS for m in ("صباحاً", "مساءً"))
          + ("حصص التربية البدنية",),
          groupes=(("اسم الأستاذ(ة)", 1), ("رقم التأجير", 1)) + tuple((j, 2) for j in _JOURS)
          + (("حصص التربية البدنية", 1),), lignes_vides=2,
          source="الأساتذة وأرقام تأجيرهم من الموارد البشرية؛ الحصص تُملأ يدوياً أو باليد على الورق."),
]
PAR_CLE = {l.cle: l for l in LAVHAT}


# ---------- المعطيات الآلية ----------

def _nb(n) -> str:
    return f"{n:02d}" if isinstance(n, int) else ("" if n is None else str(n))


def _annee_id(conn) -> int:
    a = annee_srv.annee_courante(conn)
    return a["id"] if a else -1


def _eleves(conn, cycle: str | None = None) -> dict[str, int]:
    sql = ("SELECT e.sexe, COUNT(*) FROM inscription i JOIN eleve e ON e.id=i.eleve_id "
           "LEFT JOIN niveau n ON n.id=i.niveau_id WHERE i.annee_id=? AND i.statut IN ('inscrit','arrive')")
    args: list = [_annee_id(conn)]
    if cycle == "prescolaire":
        sql += " AND n.cycle='prescolaire'"
    elif cycle == "primaire":
        sql += " AND (n.cycle IS NULL OR n.cycle='primaire')"
    d = {"M": 0, "F": 0}
    for s, n in conn.execute(sql + " GROUP BY e.sexe", args):
        d["F" if s == "F" else "M"] += n
    return d


def _classes_cycle(conn, cycle: str) -> int:
    return conn.execute(
        "SELECT COUNT(DISTINCT i.classe_id) FROM inscription i JOIN niveau n ON n.id=i.niveau_id "
        "WHERE i.annee_id=? AND i.statut IN ('inscrit','arrive') AND n.cycle=?", (_annee_id(conn), cycle)).fetchone()[0]


def _date_creation(conn) -> str:
    try:
        v = conn.execute("SELECT date_creation FROM etablissement LIMIT 1").fetchone()
    except sqlite3.Error:
        return ""
    v = v[0] if v else None
    if not v:
        return ""
    try:
        return tx.date_chiffres(v)
    except (ValueError, TypeError):
        return str(v)


def _auto_fiche(conn) -> dict:
    from idara.services import structure as st
    e = etab_srv.lire_etablissement(conn)
    d = etab_srv.directeur_actuel(conn)
    actifs = [p for p in rh.lister(conn) if p.statut == "actif"]
    ens = [p for p in actifs if p.categorie == "enseignant"]
    tous = _eleves(conn)
    pre = _eleves(conn, "prescolaire")
    prim = _eleves(conn, "primaire")
    nb_classes = conn.execute("SELECT COUNT(*) FROM classe c WHERE c.annee_id=? AND EXISTS (SELECT 1 FROM inscription "
                              "i WHERE i.classe_id=c.id)", (_annee_id(conn),)).fetchone()[0]
    sal = {l["element"]: l["total"] for l in st.tableau(conn)["lignes"]}
    v = {"cycle": "ابتدائي", "nb_admin": _nb(sum(1 for p in actifs if p.categorie in ("directeur", "assistant"))),
         "prof_m": _nb(sum(1 for p in ens if p.sexe == "M")), "prof_f": _nb(sum(1 for p in ens if p.sexe == "F")),
         "classes": _nb(nb_classes - _classes_cycle(conn, "prescolaire")),
         "eleves_primaire": _nb(prim["M"] + prim["F"]), "eleves_prescolaire": _nb(pre["M"] + pre["F"]),
         "gardiens": _nb(sum(1 for p in actifs if p.categorie == "gardien")),
         "proprete": _nb(sum(1 for p in actifs if p.categorie == "proprete")),
         "eleves_m": _nb(tous["M"]), "eleves_f": _nb(tous["F"]),
         "educatrices": _nb(sum(1 for p in actifs if p.categorie == "educatrice")),
         "classes_prescolaire": _nb(_classes_cycle(conn, "prescolaire")),
         "prescolaire_m": _nb(pre["M"]), "prescolaire_f": _nb(pre["F"]),
         "salles": _nb(sal.get("salles")), "salles_prescolaire": _nb(sal.get("salles_prescolaire"))}
    if e:
        v.update({"nom": e.nom_ar, "milieu": etab_srv.MILIEUX.get(e.milieu, ""), "commune": e.commune_ar,
                  "gresa": e.code_etab, "adresse": e.adresse or "", "telephone": e.telephone or "",
                  "creation": _date_creation(conn)})
    if d:
        v.update({"directeur": f"{d['prenom_ar']} {d['nom_ar']}",
                  "affectation": tx.date_chiffres(d["mandat_debut"]) if d["mandat_debut"] else ""})
    return {"champs": v}


def _auto_structure_ped(conn) -> dict:
    from idara.services import tanzim
    lignes = []
    for niv, lib in (("PS1", "الأول أولي"), ("PS2", "الثاني أولي")):
        n = conn.execute("SELECT COUNT(DISTINCT i.classe_id) FROM inscription i JOIN niveau v ON v.id=i.niveau_id "
                         "WHERE i.annee_id=? AND v.code=? AND i.statut IN ('inscrit','arrive')",
                         (_annee_id(conn), niv)).fetchone()[0]
        if n:
            lignes.append([lib, _nb(n)])
    for s in tanzim.structure(conn):
        lignes.append([s["libelle"].replace(" عام", ""), _nb(len(s["groupes"]))])
    return {"lignes": lignes}


def _auto_tanzim(conn) -> dict:
    aid = _annee_id(conn)
    lignes = []
    for r in conn.execute(
            "SELECT p.prenom_ar, p.nom_ar, c.code, c.id FROM affectation_classe a JOIN personnel p ON p.id=a.personnel_id "
            "JOIN classe c ON c.id=a.classe_id WHERE c.annee_id=? AND p.statut='actif' ORDER BY c.code, p.nom_ar",
            (aid,)):
        n = {"M": 0, "F": 0}
        for s, k in conn.execute("SELECT e.sexe, COUNT(*) FROM inscription i JOIN eleve e ON e.id=i.eleve_id "
                                 "WHERE i.classe_id=? AND i.statut IN ('inscrit','arrive') GROUP BY e.sexe", (r[3],)):
            n["F" if s == "F" else "M"] += k
        lignes.append([f"{r[0]} {r[1]}", r[2], _nb(n["F"]), _nb(n["M"]), _nb(n["F"] + n["M"])])
    return {"lignes": lignes}


def _auto_structure_mat(conn) -> dict:
    from idara.services import structure as st
    return {"lignes": [[l["libelle"], _nb(l["total"])] for l in st.tableau(conn)["lignes"] if l["total"] is not None]}


def _auto_clubs(conn) -> dict:
    return {"lignes": [[r[0], (f"{r[1]} {r[2]}" if r[1] else "")] for r in conn.execute(
        "SELECT c.nom, p.prenom_ar, p.nom_ar FROM club c LEFT JOIN personnel p ON p.id=c.animateur_id "
        "WHERE c.annee_id=? ORDER BY c.id", (_annee_id(conn),))]}


def _auto_conseil(conseil: str):
    def f(conn) -> dict:
        try:
            from idara.services import conseils_etab as ce
            ms = ce.membres_actifs(conn, conseil)
        except Exception:   # noqa: BLE001 (لا سنة جارية)
            ms = []
        return {"lignes": [[m["nom"], m["qualite"]] for m in ms]}
    return f


def _auto_bureau(cle: str):
    def f(conn) -> dict:
        from idara.services import fiches
        d = fiches.lire(conn, f"asso:{cle}")      # مكتب الجمعية من صفحة الوثائق القانونية للجمعيات
        ms = [[m[0], m[1]] for m in (d or {}).get("membres", []) if m and m[0]]
        if ms:
            return {"lignes": ms}
        return _auto_najah(conn) if cle == "najah" else {"lignes": []}
    return f


def _auto_najah(conn) -> dict:
    a = conn.execute("SELECT president, tresorier FROM association WHERE type='najah'").fetchone()
    lignes = [["", r] for r in _ROLES_ASSO]
    if a:
        lignes[0][0] = a["president"] or ""
        lignes[4][0] = a["tresorier"] or ""
    return {"lignes": lignes if any(l[0] for l in lignes) else []}


def _auto_emploi(conn) -> dict:
    ens = sorted((p for p in rh.lister(conn) if p.statut == "actif" and p.categorie == "enseignant"),
                 key=lambda p: (p.nom_ar, p.prenom_ar))
    from idara.services import vie_admin as va
    lignes = []
    for p in ens:
        dj = va.demi_journees(conn, p.id)       # من صفحة استعمالات الزمن إن أُدخلت حصصه
        lignes.append([f"{p.prenom_ar} {p.nom_ar}", p.ppr or ""] + [x for j in va.JOURS for x in dj[j]] + [""])
    return {"lignes": lignes}


AUTO: dict[str, Callable] = {"fiche": _auto_fiche, "structure_ped": _auto_structure_ped, "tanzim": _auto_tanzim,
                             "structure_mat": _auto_structure_mat, "clubs": _auto_clubs,
                             "conseil_ped": _auto_conseil("pedagogique"), "conseil_gestion": _auto_conseil("gestion"),
                             "najah": _auto_bureau("najah"), "sportive": _auto_bureau("sportive"),
                             "emploi": _auto_emploi}


def _auto(conn, cle: str) -> dict:
    d = AUTO[cle](conn) if cle in AUTO else {}
    d.setdefault("champs", {})
    d.setdefault("lignes", [])
    if not d["lignes"] and PAR_CLE[cle].defaut:
        d["lignes"] = [list(x) for x in PAR_CLE[cle].defaut]
    return d


# ---------- الحفظ ----------

def _normaliser(l: Lavha, d: dict) -> dict:
    n = len(l.colonnes)
    lignes = []
    for x in d.get("lignes", []):
        x = [" ".join(str(v if v is not None else "").split()) for v in x][:n]
        x += [""] * (n - len(x))
        if any(x):
            lignes.append(x)
    champs = {k: " ".join(str(v if v is not None else "").split()) for k, v in d.get("champs", {}).items()}
    return {"champs": champs, "lignes": lignes, "note": " ".join(str(d.get("note") or "").split())}


def _lavha(cle: str) -> Lavha:
    if cle not in PAR_CLE:
        raise ErreurSabboura("لوحة غير معروفة.")
    return PAR_CLE[cle]


def lire(conn: sqlite3.Connection, cle: str) -> dict:
    l = _lavha(cle)
    r = conn.execute("SELECT donnees FROM sabboura WHERE cle=?", (cle,)).fetchone()
    return _normaliser(l, json.loads(r[0]) if r and r[0] else _auto(conn, cle))


def enregistrer(conn: sqlite3.Connection, cle: str, donnees: dict) -> None:
    d = _normaliser(_lavha(cle), donnees)
    with conn:
        conn.execute("INSERT INTO sabboura(cle, donnees, maj_le) VALUES (?,?,datetime('now','localtime')) "
                     "ON CONFLICT(cle) DO UPDATE SET donnees=excluded.donnees, maj_le=excluded.maj_le",
                     (cle, json.dumps(d, ensure_ascii=False)))


def actualiser(conn: sqlite3.Connection, cle: str) -> dict:
    """يعيد ما يأتي من البرنامج ويحتفظ بما أُدخل يدوياً (الخانات التي لا يقترحها البرنامج، والأسطر الموافقة)."""
    l = _lavha(cle)
    actuel = lire(conn, cle)
    auto = _normaliser(l, _auto(conn, cle))
    champs = dict(actuel["champs"])
    champs.update({k: v for k, v in auto["champs"].items() if v})
    lignes = actuel["lignes"]
    if cle in AUTO and auto["lignes"]:
        anciens = {x[0]: x for x in actuel["lignes"]}
        lignes = [[a or (anciens.get(x[0]) or [""] * len(x))[j] for j, a in enumerate(x)] for x in auto["lignes"]]
    enregistrer(conn, cle, {"champs": champs, "lignes": lignes, "note": actuel["note"]})
    return lire(conn, cle)


def reinitialiser(conn: sqlite3.Connection, cle: str) -> dict:
    with conn:
        conn.execute("DELETE FROM sabboura WHERE cle=?", (cle,))
    return lire(conn, cle)


# ---------- التوليد ----------

def _ecrire(c, texte: str, gras=True, taille=13, couleur: str | None = None, fond: str | None = None,
            centre=True) -> None:
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Pt, RGBColor
    for p in list(c.paragraphs)[1:]:
        p._element.getparent().remove(p._element)
    p = c.paragraphs[0]
    for r in list(p.runs):
        r._element.getparent().remove(r._element)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER if centre else WD_ALIGN_PARAGRAPH.RIGHT
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.space_before = Pt(0)
    ppr = p._p.get_or_add_pPr()
    if ppr.find(qn("w:bidi")) is None:
        ppr.append(OxmlElement("w:bidi"))
    r = p.add_run(texte)
    r.bold = gras
    r.font.size = Pt(taille)
    r.font.name = "Arial"
    rpr = r._r.get_or_add_rPr()
    rpr.append(OxmlElement("w:rtl"))
    f = rpr.find(qn("w:rFonts"))
    f.set(qn("w:cs"), "Arial")
    sz = OxmlElement("w:szCs")
    sz.set(qn("w:val"), str(int(taille * 2)))
    rpr.append(sz)
    if gras:
        rpr.append(OxmlElement("w:bCs"))
    if couleur:
        r.font.color.rgb = RGBColor.from_string(couleur)
    if fond:
        from idara.services.docs_association import _ombre
        _ombre(c, fond)


def _table(d, n_lignes: int, n_cols: int, largeurs: list[float]):
    from idara.services.docs_association import tableau
    t = tableau(d, n_lignes, n_cols, largeurs=largeurs)
    return t


def _page(d, conn, dossier: DossierDonnees, l: Lavha, ruban: bytes | None, premiere: bool) -> None:
    """ترويسة المؤسسة في رأس الصفحة، وشريط العنوان، ومسافة."""
    from docx.enum.section import WD_ORIENT, WD_SECTION
    from docx.shared import Cm

    from idara.services.docs_association import para
    if premiere:
        s = d.sections[0]
    else:
        s = d.add_section(WD_SECTION.NEW_PAGE)
    larg, haut = (Cm(29.7), Cm(21.0)) if l.paysage else (Cm(21.0), Cm(29.7))
    s.orientation = WD_ORIENT.LANDSCAPE if l.paysage else WD_ORIENT.PORTRAIT
    s.page_width, s.page_height = larg, haut
    s.left_margin = s.right_margin = Cm(1.5)
    s.top_margin, s.bottom_margin = Cm(1.0), Cm(1.2)
    s.header_distance = s.footer_distance = Cm(0.5)
    if premiere:
        _entete_pied(d, conn, dossier, s)
    para(d, "", apres=4)
    if ruban:
        d.add_picture(io.BytesIO(ruban), width=Cm(13))
        d.paragraphs[-1].alignment = 1
    else:
        t = _table(d, 1, 1, [12.0])
        _ecrire(t.cell(0, 0), l.titre, taille=20, couleur="1B1B3A", fond=ORANGE)
    para(d, "", apres=10)


def _entete_pied(d, conn, dossier: DossierDonnees, s) -> None:
    """رأس الصفحة: صورة ترويسة المؤسسة إن وُجدت (وإلا الأسطر الرسمية)، والتذييل: صورته أو اسم المؤسسة وهاتفها."""
    from docx.shared import Cm

    from idara.services.docs_association import para
    e = etab_srv.lire_etablissement(conn)
    h = s.header
    for p in list(h.paragraphs):
        p.text = ""
    if e and e.logo_path and (dossier.racine / e.logo_path).exists():
        h.paragraphs[0].add_run().add_picture(str(dossier.racine / e.logo_path), width=Cm(17.5))
        h.paragraphs[0].alignment = 1
    elif e:
        for k, ligne in enumerate(("المملكة المغربية", "وزارة التربية الوطنية والتعليم الأولي والرياضة",
                                   e.academie_ar, e.direction_ar, e.nom_ar)):
            if ligne:
                p = h.paragraphs[0] if k == 0 else h.add_paragraph()
                p.text = ligne
                p.alignment = 1
    f = s.footer
    if e and e.pied_image_path and (dossier.racine / e.pied_image_path).exists():
        f.paragraphs[0].add_run().add_picture(str(dossier.racine / e.pied_image_path), width=Cm(17.5))
        f.paragraphs[0].alignment = 1
    elif e:
        vide = f.paragraphs[0]
        para(f, " – ".join(x for x in (e.nom_ar, e.direction_ar, e.telephone) if x), taille=9, centre=True, apres=0)
        vide._element.getparent().remove(vide._element)


def _rendre(d, l: Lavha, donnees: dict) -> None:
    from idara.services.docs_association import para
    if l.nature == "fiche":
        champs = donnees["champs"]
        rangs, courant = [], []
        for c in l.champs:
            if c.plein:
                if courant:
                    rangs.append(courant)
                    courant = []
                rangs.append([c])
            else:
                courant.append(c)
                if len(courant) == 2:
                    rangs.append(courant)
                    courant = []
        if courant:
            rangs.append(courant)
        t = _table(d, len(rangs), 4, [4.4, 4.3, 4.4, 4.3])
        for i, rang in enumerate(rangs):
            if len(rang) == 1 and rang[0].plein:
                c = rang[0]
                _ecrire(t.cell(i, 0), c.libelle, taille=12, couleur="FFFFFF", fond=BLEU)
                v = t.cell(i, 1).merge(t.cell(i, 3))
                _ecrire(v, champs.get(c.cle, ""), taille=12)
                continue
            for k, c in enumerate(rang):
                _ecrire(t.cell(i, 2 * k), c.libelle, taille=12, couleur="FFFFFF", fond=BLEU)
                _ecrire(t.cell(i, 2 * k + 1), champs.get(c.cle, ""), taille=12)
        return
    lignes = donnees["lignes"] + [[""] * len(l.colonnes) for _ in range(l.lignes_vides)]
    if l.nature == "cellules":
        t = _table(d, 2 * max(1, len(lignes)), 1, [14.0])
        for i, (nom, membres) in enumerate(lignes):
            _ecrire(t.cell(2 * i, 0), nom, taille=14, couleur="FFFFFF", fond=BLEU)
            noms = [m.strip() for m in membres.replace("،", ",").split(",") if m.strip()]
            c = t.cell(2 * i + 1, 0)
            _ecrire(c, noms[0] if noms else "", taille=13)
            from idara.services.docs_association import para as p_
            for m in noms[1:]:
                p_(c, m, gras=True, taille=13, centre=True, apres=0)
        return
    entetes = (["ر.ت"] if l.numero else []) + list(l.colonnes)
    dec = 1 if l.numero else 0
    n = len(entetes)
    if l.paysage:
        largeurs = ([0.9] if l.numero else []) + [4.6, 2.4] + [1.45] * 12 + [2.6]
    else:
        reste = 17.0 - (1.0 if l.numero else 0)
        larg_col = {2: [9.0, 8.0], 5: [5.6, 4.4, 2.0, 2.0, 2.0]}.get(len(l.colonnes),
                                                                      [round(reste / len(l.colonnes), 2)] * len(l.colonnes))
        largeurs = ([1.0] if l.numero else []) + larg_col
    deux = bool(l.groupes)
    t = _table(d, (2 if deux else 1) + len(lignes), n, largeurs)
    taille = 9 if l.paysage else 13
    if deux:
        if l.numero:
            c = t.cell(0, 0).merge(t.cell(1, 0))
            _ecrire(c, "ر.ت", taille=taille, couleur="FFFFFF", fond=BLEU)
        j = dec
        for lib, span in l.groupes:
            if span == 1:
                c = t.cell(0, j).merge(t.cell(1, j))
                _ecrire(c, lib, taille=taille, couleur="FFFFFF", fond=BLEU)
            else:
                c = t.cell(0, j).merge(t.cell(0, j + span - 1))
                _ecrire(c, lib, taille=taille, couleur="FFFFFF", fond=BLEU)
                for k in range(span):
                    sous = l.colonnes[j - dec + k].split(": ", 1)[-1]
                    _ecrire(t.cell(1, j + k), sous, taille=taille - 1, couleur="FFFFFF", fond=BLEU)
            j += span
    else:
        for j, h in enumerate(entetes):
            _ecrire(t.cell(0, j), h, taille=taille, couleur="FFFFFF", fond=BLEU)
    debut = 2 if deux else 1
    for i, x in enumerate(lignes):
        vals = ([f"{i + 1:02d}"] if l.numero else []) + x
        for j, v in enumerate(vals):
            _ecrire(t.cell(debut + i, j), v, taille=taille)
    if l.note:
        para(d, "", apres=14)
        t2 = _table(d, 2, 1, [14.0])
        _ecrire(t2.cell(0, 0), l.note, taille=13, couleur="FFFFFF", fond=BLEU)
        _ecrire(t2.cell(1, 0), donnees.get("note", ""), taille=13)


def generer(conn: sqlite3.Connection, dossier: DossierDonnees, cles: list[str] | None = None,
            rubans: dict[str, bytes] | None = None) -> Path:
    """لوحة واحدة أو أكثر في وثيقة Word (صفحة لكل لوحة). rubans: صور شريط العنوان، ترسمها الواجهة."""
    from idara.services.docs_association import _nouveau
    cles = cles or [l.cle for l in LAVHAT]
    for c in cles:
        _lavha(c)
    d = _nouveau()
    for k, c in enumerate(cles):
        l = PAR_CLE[c]
        _page(d, conn, dossier, l, (rubans or {}).get(c), k == 0)
        _rendre(d, l, lire(conn, c))
    rep = dossier.archives / "السبورة المرجعية"
    rep.mkdir(parents=True, exist_ok=True)
    nom = PAR_CLE[cles[0]].titre.replace(" ", "_") if len(cles) == 1 else "السبورة_المرجعية"
    chemin = rep / f"{datetime.now():%Y%m%d_%H%M%S}_{nom}.docx"
    n = 1
    while chemin.exists():
        n += 1
        chemin = chemin.with_name(f"{chemin.stem}_{n}.docx")
    d.save(chemin)
    journaliser(conn, "generation", "sabboura", None, chemin.name)
    return chemin
