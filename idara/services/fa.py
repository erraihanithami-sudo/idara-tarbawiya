"""تدبير الفائض على مستوى المؤسسة، حسب المذكرة الإطار (الفقرة 3.1) وقرارات المدير.

المعايير (لكل أستاذ عامل، حسب المادة):
- الأقدمية العامة: نقطة عن كل سنة ابتداء من تاريخ التوظيف.
- الأقدمية بالمديرية (النيابة): نقطة عن كل سنة ابتداء من تاريخ التعيين بإحدى مؤسساتها.
- الأقدمية بالمؤسسة: نقطتان عن كل سنة ابتداء من تاريخ التعيين بالمؤسسة الحالية.
تُحسب السنوات مواسمَ دراسية، كل موسم بسنة، بما فيه الموسم الجاري (قرار المدير 2026-11-01).
الترتيب تنازلي بمجموع النقط؛ عند التساوي: الأقدمية العامة، ثم بالمديرية، ثم بالمؤسسة، ثم السن،
والأصغر سناً هو الفائض (قرار المدير). المستثنون: المبرزون، وحاملو الدكتوراه بخمس سنوات على الأقل بهذه الصفة.
الفائض: من يبقى بعد إسناد حصة كاملة لعدد الأساتذة الذي تفرضه البنية التربوية.
يُرتَّب جميع الأساتذة معاً بغض النظر عن مادة التدريس (قرار المدير 2026-11-10)، بعدد مناصب واحد للمؤسسة.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date

from idara.services import annee as annee_srv
from idara.services import personnel as rh

DUREE_DOCTORAT = 5
TOUS = "جميع المواد"   # ترتيب واحد لكل الأساتذة (قرار المدير 2026-11-10)


class ErreurFa(ValueError):
    """رسالة موجهة للمدير بالعربية."""


def debut_saison(d: date) -> int:
    """سنة بداية الموسم الدراسي الذي يقع فيه التاريخ (الموسم يبدأ في شتنبر)."""
    return d.year if d.month >= 9 else d.year - 1


def saisons(depuis: str, saison_courante: int) -> int:
    """عدد المواسم من موسم التاريخ إلى الموسم الجاري، شاملاً الطرفين."""
    return max(0, saison_courante - debut_saison(date.fromisoformat(depuis)) + 1)


def saison_courante(conn: sqlite3.Connection) -> int:
    a = annee_srv.annee_courante(conn)
    if a is None:
        raise ErreurFa("لا توجد سنة دراسية جارية.")
    return int(a["libelle"][:4])


@dataclass
class Ligne:
    p: rh.Personnel
    generale: int = 0
    direction: int = 0
    etablissement: int = 0      # عدد المواسم (النقط = ضعفها)
    rang: int | None = None
    resultat: str = ""          # maintenu | fa | exempte | incomplet
    motif: str = ""

    @property
    def total(self) -> int:
        return self.generale + self.direction + 2 * self.etablissement


@dataclass
class Groupe:
    matiere: str
    requis: int | None
    lignes: list[Ligne] = field(default_factory=list)

    @property
    def fa(self) -> list[Ligne]:
        return [l for l in self.lignes if l.resultat == "fa"]

    @property
    def incomplets(self) -> list[Ligne]:
        return [l for l in self.lignes if l.resultat == "incomplet"]

    @property
    def definitif(self) -> bool:
        return self.requis is not None and not self.incomplets


def exemption(p: rh.Personnel, le: date) -> str:
    if p.exemption_fa == "agrege":
        return "أستاذ(ة) مبرز(ة)"
    if p.exemption_fa == "doctorat" and p.date_exemption_fa \
            and rh.annees_entre(date.fromisoformat(p.date_exemption_fa), le) >= DUREE_DOCTORAT:
        return f"حامل(ة) الدكتوراه منذ {DUREE_DOCTORAT} سنوات على الأقل"
    return ""


_REQUIS = (("date_naissance", "تاريخ الازدياد"), ("date_recrutement", "تاريخ التوظيف"),
           ("date_affectation_direction", "تاريخ التعيين بالمديرية الإقليمية"),
           ("date_affectation", "تاريخ التعيين بالمؤسسة"))


def postes_requis(conn: sqlite3.Connection) -> dict[str, int]:
    a = annee_srv.annee_courante(conn)
    if a is None:
        return {}
    return {r["matiere"]: r["nombre"] for r in conn.execute(
        "SELECT matiere, nombre FROM poste_requis WHERE annee_id=?", (a["id"],))}


def definir_postes(conn: sqlite3.Connection, matiere: str, nombre: int | None) -> None:
    if matiere not in rh.MATIERES and matiere != TOUS:
        raise ErreurFa("مادة غير معروفة.")
    a = annee_srv.annee_courante(conn)
    if a is None:
        raise ErreurFa("لا توجد سنة دراسية جارية.")
    with conn:
        if nombre is None:
            conn.execute("DELETE FROM poste_requis WHERE annee_id=? AND matiere=?", (a["id"], matiere))
        else:
            if nombre < 0:
                raise ErreurFa("عدد المناصب لا يكون سالباً.")
            conn.execute("INSERT INTO poste_requis(annee_id, matiere, nombre) VALUES (?,?,?) "
                         "ON CONFLICT(annee_id, matiere) DO UPDATE SET nombre=excluded.nombre",
                         (a["id"], matiere, nombre))


def calculer(conn: sqlite3.Connection, le: date | None = None) -> tuple[list[Groupe], list[rh.Personnel]]:
    """يرجع مجموعة واحدة (جميع الأساتذة بغض النظر عن المادة)، ولائحة فارغة للأساتذة بلا مادة (للتوافق)."""
    le = le or date.today()
    cour = saison_courante(conn)
    requis = postes_requis(conn)
    profs = rh.lister(conn, categorie="enseignant")
    sans_matiere: list[rh.Personnel] = []   # لم يعد شرطاً: الترتيب واحد لكل المواد
    groupes = []
    for m in [TOUS]:
        g = Groupe(m, requis.get(m))
        for p in profs:
            l = Ligne(p)
            manque = [lib for k, lib in _REQUIS if not getattr(p, k)]
            ex = exemption(p, le)
            if ex:
                l.resultat, l.motif = "exempte", ex
            elif manque:
                l.resultat, l.motif = "incomplet", "ينقص: " + "، ".join(manque)
            if not manque:
                l.generale = saisons(p.date_recrutement, cour)
                l.direction = saisons(p.date_affectation_direction, cour)
                l.etablissement = saisons(p.date_affectation, cour)
            g.lignes.append(l)
        a_classer = [l for l in g.lignes if l.resultat == ""]
        a_classer.sort(key=lambda l: (-l.total, -l.generale, -l.direction, -l.etablissement,
                                      l.p.date_naissance))  # الأكبر سناً (تاريخ أقدم) أولاً
        for i, l in enumerate(a_classer, 1):
            l.rang = i
        if g.requis is not None:
            places = max(0, g.requis - sum(1 for l in g.lignes if l.resultat == "exempte"))
            for l in a_classer:
                l.resultat = "maintenu" if l.rang <= places else "fa"
        g.lignes.sort(key=lambda l: ({"exempte": 0, "maintenu": 1, "": 1, "fa": 2, "incomplet": 3}[l.resultat],
                                     l.rang or 0))
        if g.lignes or g.requis:
            groupes.append(g)
    return groupes, sans_matiere


def nombre_classes(conn: sqlite3.Connection) -> int:
    """للمساعدة على تقدير عدد المناصب: عدد أقسام السنة الجارية."""
    return len(rh.classes_annee(conn))


# ---------- محضر الفائض وتوقيعات الأساتذة (طلب المدير 2026-11-12) ----------

RESULTATS = {"maintenu": "غير فائض", "fa": "فائض", "exempte": "مستثنى", "incomplet": "معطيات ناقصة", "": "—"}


def generer_pv(conn: sqlite3.Connection, dossier, le: date | None = None, observations: str = ""):
    """الصفحة الأولى: محضر تحديد الفائض (الترتيب والنتيجة). الصفحة الثانية: توقيعات الأساتذة العاملين بعد الاطلاع
    (نموذج المدير: ر.ت، الاسم الكامل، رقم التأجير، التوقيع)."""
    from datetime import datetime

    from idara.services import documents as dc
    from idara.services import etablissement as etab_srv
    from idara.services import textes as tx
    from idara.services.docs_association import _cellule, _nouveau, _ombre, para, saut_page, tableau
    from docx.shared import Cm

    le = le or date.today()
    try:
        c = dc.champs_communs(conn)
    except dc.ErreurDocument as e:
        raise ErreurFa(str(e)) from None
    groupes, _ = calculer(conn, le)
    g = next((x for x in groupes if x.matiere == TOUS), None)
    if g is None or not g.lignes:
        raise ErreurFa("لا أساتذة عاملين في ملفات الموارد البشرية.")
    if g.requis is None:
        raise ErreurFa("حدد أولاً عدد الأساتذة الذي تفرضه البنية التربوية (عدد المناصب) في صفحة تدبير الفائض.")
    a = annee_srv.annee_courante(conn)
    e = etab_srv.lire_etablissement(conn)
    d = _nouveau()
    for l in ("المملكة المغربية", "وزارة التربية الوطنية والتعليم الأولي والرياضة",
              f"الأكاديمية الجهوية للتربية والتكوين: {e.academie_ar}" if e and e.academie_ar else "",
              f"المديرية الإقليمية: {e.direction_ar}" if e and e.direction_ar else "",
              f"المؤسسة: {c['etablissement']}"):
        if l:
            para(d, l, gras=True, taille=12, apres=0)
    para(d, apres=6)
    para(d, "محضر تحديد الفائض بالمؤسسة", gras=True, taille=20, centre=True, apres=0)
    para(d, f"برسم الموسم الدراسي {a['libelle']}", centre=True, taille=14, apres=8)
    para(d, f"في يوم {tx.date_longue_ar(le.isoformat())}، وتطبيقاً لمقتضيات المذكرة الإطار المنظمة لتدبير الفائض "
            f"والخصاص، تم بمؤسسة {c['etablissement']} ترتيب الأساتذة العاملين بها حسب المعايير التالية: نقطة عن كل "
            "سنة من تاريخ التوظيف، ونقطة عن كل سنة بالمديرية الإقليمية، ونقطتان عن كل سنة بالمؤسسة الحالية (كل موسم "
            "دراسي بسنة، بما فيه الموسم الجاري). وعند التساوي: الأقدمية العامة، ثم بالمديرية، ثم بالمؤسسة، ثم السن "
            "(الأصغر سناً هو الفائض). ويُستثنى المبرزون وحاملو الدكتوراه منذ خمس سنوات على الأقل.", taille=12, apres=4)
    para(d, f"عدد الأساتذة الذي تفرضه البنية التربوية: {g.requis}، وعدد الأساتذة العاملين: {len(g.lignes)}.",
         gras=True, taille=12, apres=6)
    entetes = ("الرتبة", "الاسم الكامل", "رقم التأجير", "الأقدمية العامة", "بالمديرية", "بالمؤسسة (×2)",
               "المجموع", "النتيجة")
    t = tableau(d, 1 + len(g.lignes), len(entetes), largeurs=[1.4, 4.4, 2.2, 1.9, 1.8, 2.0, 1.7, 2.6])
    for j, lib in enumerate(entetes):
        _cellule(t.cell(0, j), lib, gras=True, taille=11)
        _ombre(t.cell(0, j))
    for i, l in enumerate(g.lignes, start=1):
        complet = l.resultat != "incomplet"
        vals = (str(l.rang or "—"), f"{l.p.nom_ar} {l.p.prenom_ar}".strip(), l.p.ppr or "",
                str(l.generale) if complet else "—", str(l.direction) if complet else "—",
                str(2 * l.etablissement) if complet else "—", str(l.total) if complet else "—",
                RESULTATS.get(l.resultat, l.resultat) + (f" ({l.motif})" if l.resultat == "exempte" else ""))
        for j, v in enumerate(vals):
            _cellule(t.cell(i, j), v, taille=11, gras=l.resultat == "fa", centre=j != 1)
    para(d, apres=6)
    fa_ = g.fa
    if g.incomplets:
        para(d, "تنبيه: معطيات ناقصة لـ: " + "، ".join(f"{l.p.nom_ar} {l.p.prenom_ar}" for l in g.incomplets)
             + " (الترتيب غير نهائي).", taille=11, apres=4)
    para(d, "النتيجة: " + ("الأستاذ(ة) الفائض(ة): " + "، ".join(f"{l.p.nom_ar} {l.p.prenom_ar}" for l in fa_)
                           if fa_ else "لا يوجد فائض بالمؤسسة برسم هذا الموسم."), gras=True, taille=13, apres=6)
    if observations.strip():
        para(d, "ملاحظات: " + " ".join(observations.split()), taille=12, apres=6)
    para(d, f"{c['ville']} في: {tx.date_ar(le)}", apres=10)
    para(d, c["mudir_moassasa"], gras=True, centre=True, apres=0)

    # الصفحة الثانية: توقيعات الأساتذة العاملين (نموذج المدير)
    saut_page(d)
    profs = rh.lister(conn, categorie="enseignant")
    para(d, f"المؤسسة: {c['etablissement']}", gras=True, taille=12, apres=4)
    para(d, "توقيعات السيدات الأستاذات والأساتذة بعد الاطلاع", gras=True, taille=18, centre=True, apres=0)
    para(d, f"على محضر تحديد الفائض برسم الموسم الدراسي {a['libelle']}", centre=True, taille=13, apres=8)
    t = tableau(d, 1 + len(profs), 4, largeurs=[1.4, 7.0, 3.4, 5.6])
    for j, lib in enumerate(("ر.ت", "الاسم الكامل", "رقم التأجير", "التوقيع")):
        _cellule(t.cell(0, j), lib, gras=True, taille=13)
        _ombre(t.cell(0, j))
    for i, p in enumerate(profs, start=1):
        for j, v in enumerate((f"{i:02d}", f"{p.nom_ar} {p.prenom_ar}".strip(), p.ppr or "", "")):
            _cellule(t.cell(i, j), v, taille=13, centre=j != 1)
        t.rows[i].height = Cm(1.2)
    rep = dossier.archives / a["libelle"].replace("/", "-") / "الموارد البشرية"
    rep.mkdir(parents=True, exist_ok=True)
    chemin = rep / f"{datetime.now():%Y%m%d_%H%M%S}_محضر الفائض.docx"
    d.save(chemin)
    return chemin
