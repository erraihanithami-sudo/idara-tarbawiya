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
