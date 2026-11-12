"""حساب مؤشر التحكم في التعلمات ISA2 من نتائج الروائز (المدرسة الرائدة)، حسب الصيغة التي زوّد بها المدير
(2026-11-12):

    ISA0 = نسبة التحكم في الرائز القبلي، ISA1 = نسبة التحكم في الرائز البعدي.
    مستويات التحكم في الكفايات: A تحكم تام، B تحكم مقنع، C تحكم ضعيف (نسب التلاميذ في كل مستوى).
    Ind  = [(3×A + 2×B + 1×C) / 3] × 100
    ISA2 = α × Ind  ؛  α = 0,8

وتحديد الهدف حسب قيمة ISA2:
    ISA2 ≤ 30%        : التطور بين 15 و20 نقطة، والهدف ISA2+20% ≤ OB ≤ 50%
    30% < ISA2 ≤ 50%  : بين 10 و15 نقطة، والهدف 40% ≤ OB ≤ 65%
    50% < ISA2 < 70%  : بين 5 و10 نقط، والهدف 55% ≤ OB ≤ 80%
    ISA2 ≥ 70%        : 5 نقط، والهدف OB ≥ 75%

تُستورد نتائج كل مرحلة من ملف Excel (تصدير مسار أو ملف المؤسسة): سطر لكل تلميذ، وعمود لكل مادة فيه مستوى
التحكم (A/B/C، أو «تحكم تام/مقنع/ضعيف»، أو نقطة مئوية تُحوَّل حسب SEUILS). ويمكن أيضاً إدخال الأعداد يدوياً.
النسب المحسوبة للرائز البعدي والمراحل تُكتب كذلك في جدول ISA2 حسب المراحل (isa_phase) لتستعملها المراسلات
والتقارير الموجودة.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from idara.data.dossier import DossierDonnees
from idara.data.journal import journaliser
from idara.services import documents as dc
from idara.services import evaluation as ev
from idara.services import textes as tx
from idara.services.docs_association import _cellule, _nouveau, _ombre, para, saut_page, tableau
from idara.services.massar import MOTIF_CODE, normaliser

ALPHA = 0.8
MATIERES = {"ar": "العربية", "fr": "الفرنسية", "ma": "الرياضيات"}
NIVEAUX = {"A": "تحكم تام", "B": "تحكم مقنع", "C": "تحكم ضعيف"}
PHASES = [-1, 0, 1, 2, 3, 4, 5, 6]
# النقطة المئوية ← المستوى، إن كتب الملف نقطاً بدل المستويات (قابل للتعديل بعد الاطلاع على ملف مسار)
SEUILS = ((75.0, "A"), (50.0, "B"), (0.0, "C"))
# جدول تحديد الهدف: (الحد الأعلى للفئة، التطور الأدنى، التطور الأقصى، الهدف الأدنى، الهدف الأعلى، النص)
CATEGORIES = (
    (30.0, 15, 20, None, 50.0, "ISA2 ≤ 30%", "ISA2+20% ≤ OB ≤ 50%"),
    (50.0, 10, 15, 40.0, 65.0, "30% < ISA2 ≤ 50%", "40% ≤ OB ≤ 65%"),
    (70.0, 5, 10, 55.0, 80.0, "50% < ISA2 < 70%", "55% ≤ OB ≤ 80%"),
    (101.0, 5, 5, 75.0, 100.0, "ISA2 ≥ 70%", "OB ≥ 75%"),
)


class ErreurIsa(ValueError):
    """رسالة موجهة للمدير بالعربية."""


def libelle_phase(p: int) -> str:
    return {-1: "الرائز القبلي", 0: "الرائز البعدي"}.get(p, f"المرحلة {p}")


def code_isa(p: int) -> str:
    """ISA0 للقبلي، ISA1 للبعدي، ISA2 للمراحل."""
    return {-1: "ISA0", 0: "ISA1"}.get(p, "ISA2")


# ---------- الحساب ----------

@dataclass
class Calcul:
    a: int
    b: int
    c: int

    @property
    def total(self) -> int:
        return self.a + self.b + self.c

    def pct(self, n: int) -> float:
        return round(100.0 * n / self.total, 2) if self.total else 0.0

    def _ind(self) -> float | None:
        if not self.total:
            return None
        return (3 * self.a + 2 * self.b + self.c) / (3 * self.total) * 100

    @property
    def ind(self) -> float | None:
        """Ind = [(3A + 2B + C) / 3] × 100، حيث A وB وC نسب التلاميذ (من 0 إلى 1)."""
        x = self._ind()
        return None if x is None else round(x, 2)

    @property
    def isa(self) -> float | None:
        """ISA2 = α × Ind (محسوب قبل التقريب)."""
        x = self._ind()
        return None if x is None else round(ALPHA * x, 2)


def objectif(valeur: float) -> dict:
    """الفئة والتطور المرتقب (أدنى وأقصى) والهدف المقترح لقيمة ISA2."""
    for haut, dmin, dmax, ob_bas, ob_haut, fourchette, texte in CATEGORIES:
        if valeur <= haut if haut <= 50 else valeur < haut:
            bas = valeur + 20 if ob_bas is None else ob_bas
            cible_min = min(max(valeur + dmin, bas), ob_haut)
            cible_max = min(max(valeur + dmax, cible_min), ob_haut)
            return {"categorie": fourchette, "objectif": texte, "min": dmin, "max": dmax,
                    "ob_bas": round(min(bas, ob_haut), 2), "ob_haut": ob_haut,
                    "cible_min": round(cible_min, 2), "cible_max": round(cible_max, 2)}
    raise ErreurIsa(f"قيمة غير صحيحة: {valeur}")


# ---------- التخزين ----------

def _aid(conn, annee: str) -> int:
    return ev._annee_id(conn, annee)


def enregistrer(conn: sqlite3.Connection, annee: str, classe: str, matiere: str, phase: int,
                a: int, b: int, c: int, source: str = "إدخال يدوي") -> Calcul:
    """يحفظ أعداد مستويات التحكم، ويكتب ISA2 المحسوب في جدول المراحل (للرائز البعدي والمراحل)."""
    if matiere not in MATIERES:
        raise ErreurIsa(f"مادة غير معروفة: {matiere}")
    if phase not in range(-1, 9):
        raise ErreurIsa("مرحلة غير صحيحة.")
    try:
        a, b, c = (int(x or 0) for x in (a, b, c))
    except (TypeError, ValueError):
        raise ErreurIsa(f"{classe}: الأعداد يجب أن تكون أرقاماً صحيحة.") from None
    if min(a, b, c) < 0:
        raise ErreurIsa(f"{classe}: عدد سالب.")
    aid, calc = _aid(conn, annee), Calcul(a, b, c)
    with conn:
        if not calc.total:
            conn.execute("DELETE FROM isa_resultat WHERE annee_id=? AND classe=? AND phase=? AND matiere=?",
                         (aid, classe, phase, matiere))
        else:
            conn.execute("INSERT INTO isa_resultat(annee_id, classe, phase, matiere, nb_a, nb_b, nb_c, source) "
                         "VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(annee_id, classe, phase, matiere) DO UPDATE SET "
                         "nb_a=excluded.nb_a, nb_b=excluded.nb_b, nb_c=excluded.nb_c, source=excluded.source",
                         (aid, classe, phase, matiere, a, b, c, source))
        if phase >= 0 and calc.isa is not None:
            conn.execute("INSERT INTO isa_phase(annee_id, classe, phase, matiere, valeur) VALUES (?,?,?,?,?) "
                         "ON CONFLICT(annee_id, classe, phase, matiere) DO UPDATE SET valeur=excluded.valeur",
                         (aid, classe, phase, matiere, calc.isa))
    return calc


def resultats(conn: sqlite3.Connection, annee: str) -> dict[str, dict[str, dict[int, Calcul]]]:
    """القسم ← المادة ← المرحلة ← الحساب."""
    res: dict = {}
    for r in conn.execute("SELECT i.* FROM isa_resultat i JOIN annee_scolaire a ON a.id=i.annee_id "
                          "WHERE a.libelle=?", (annee,)):
        res.setdefault(r["classe"], {}).setdefault(r["matiere"], {})[r["phase"]] = Calcul(r["nb_a"], r["nb_b"],
                                                                                          r["nb_c"])
    return res


def ensemble(donnees: dict, matiere: str, phase: int) -> Calcul | None:
    """مجموع المؤسسة لمادة ومرحلة."""
    cs = [d[matiere][phase] for d in donnees.values() if phase in d.get(matiere, {})]
    if not cs:
        return None
    return Calcul(sum(x.a for x in cs), sum(x.b for x in cs), sum(x.c for x in cs))


def reference(par_phase: dict[int, Calcul]) -> tuple[int, Calcul] | None:
    """القيمة المرجعية لتحديد الهدف: آخر مرحلة متوفرة."""
    ps = [p for p in sorted(par_phase) if par_phase[p].total]
    return (ps[-1], par_phase[ps[-1]]) if ps else None


# ---------- قراءة ملفات النتائج ----------

def niveau(valeur) -> str | None:
    """A/B/C من قيمة الخانة: حرف، أو تسمية، أو نقطة مئوية."""
    if valeur is None:
        return None
    if isinstance(valeur, (int, float)):
        x = float(valeur)
        if 0 < x <= 1:
            x *= 100
        return next(n for s, n in SEUILS if x >= s) if 0 <= x <= 100 else None
    t = normaliser(valeur).replace("%", "")
    if not t:
        return None
    if t in ("a", "أ", "ا"):
        return "A"
    if t in ("b", "ب"):
        return "B"
    if t in ("c", "ج", "d", "د"):
        return "C"
    if "تام" in t or "متحكمتماما" in t:
        return "A"
    if "مقنع" in t or "متوسط" in t:
        return "B"
    if "ضعيف" in t or "غيرمتحكم" in t or "منعدم" in t:
        return "C"
    try:
        return niveau(float(t.replace(",", ".")))
    except ValueError:
        return None


def _matiere(texte) -> str | None:
    t = normaliser(texte)
    for k, mots in (("ar", ("العربية", "عربية", "arabe")), ("fr", ("الفرنسية", "فرنسية", "francais", "français")),
                    ("ma", ("الرياضيات", "رياضيات", "math"))):
        if any(normaliser(m) in t for m in mots):
            return k
    return None


@dataclass
class FichierIsa:
    comptes: dict[tuple[str, str], list[int]] = field(default_factory=dict)   # (القسم، المادة) ← [A, B, C]
    eleves: int = 0
    alertes: list[str] = field(default_factory=list)


def lire_fichier(chemin: Path) -> FichierIsa:
    """ورقة لكل قسم (أو عمود «القسم»)؛ رأس الجدول يحتوي «رقم التلميذ» أو «رمز مسار»، وعمود لكل مادة."""
    import openpyxl
    try:
        wb = openpyxl.load_workbook(chemin, read_only=True, data_only=True)
    except Exception as e:  # noqa: BLE001
        raise ErreurIsa(f"تعذرت قراءة الملف {Path(chemin).name}: ليس ملف Excel صالحاً.") from e
    res = FichierIsa()
    for ws in wb.worksheets:
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
        cle_code = ("رقمالتلميذ", "رمزمسار", "رمزالتلميذ", "codemassar", "الرمز")
        entete = next((i for i, r in enumerate(rows) if any(normaliser(c) in cle_code for c in r)), None)
        if entete is None:
            continue
        tete, dessus = rows[entete], rows[entete - 1] if entete else []
        i_code = next(j for j, c in enumerate(tete) if normaliser(c) in cle_code)
        i_classe = next((j for j, c in enumerate(tete) if normaliser(c) in ("القسم", "الفوج", "classe")), None)
        colonnes = []
        for j, c in enumerate(tete):
            m = _matiere(c) or (_matiere(dessus[j]) if j < len(dessus) and not _matiere(c) else None)
            if m and j != i_code and all(m != x[1] for x in colonnes):
                colonnes.append((j, m))
        if not colonnes:
            continue
        # القسم: من رأس الورقة («القسم: 4APG-1») أو من اسم الورقة
        classe_ws = ws.title.strip()
        for r in rows[:entete]:
            for j, c in enumerate(r):
                if normaliser(c) in ("القسم", "الفوج") and j + 1 < len(r) and r[j + 1]:
                    classe_ws = str(r[j + 1]).strip()
        for r in rows[entete + 1:]:
            code = str(r[i_code] or "").strip().upper() if i_code < len(r) else ""
            if not code or not MOTIF_CODE.match(code):
                continue
            classe = str(r[i_classe]).strip() if i_classe is not None and i_classe < len(r) and r[i_classe] \
                else classe_ws
            res.eleves += 1
            for j, m in colonnes:
                v = r[j] if j < len(r) else None
                if v in (None, ""):
                    continue
                n = niveau(v)
                if n is None:
                    res.alertes.append(f"{classe}: قيمة غير مفهومة «{v}» ({MATIERES[m]}) لـ {code}.")
                    continue
                res.comptes.setdefault((classe, m), [0, 0, 0])["ABC".index(n)] += 1
    if not res.comptes:
        raise ErreurIsa("لم يُعثر على نتائج في الملف: يلزم عمود «رقم التلميذ» (أو «رمز مسار») وعمود لكل مادة "
                        "(العربية، الفرنسية، الرياضيات) فيه مستوى التحكم A/B/C أو النقطة.")
    return res


@dataclass
class RapportIsa:
    phase: int
    eleves: int
    lignes: int
    alertes: list[str]


def importer(conn: sqlite3.Connection, annee: str, phase: int, chemins: list[Path]) -> RapportIsa:
    total: dict[tuple[str, str], list[int]] = {}
    eleves, alertes, noms = 0, [], []
    for ch in chemins:
        f = lire_fichier(Path(ch))
        eleves += f.eleves
        alertes += f.alertes
        noms.append(Path(ch).name)
        for k, v in f.comptes.items():
            t = total.setdefault(k, [0, 0, 0])
            for i in range(3):
                t[i] += v[i]
    for (classe, m), (a, b, c) in total.items():
        enregistrer(conn, annee, classe, m, phase, a, b, c, source="، ".join(noms))
    journaliser(conn, "isa_import", "isa_resultat", None, f"{annee} {libelle_phase(phase)}: {len(total)} سطر")
    return RapportIsa(phase, eleves, len(total), alertes[:20])


# ---------- التقرير ----------

def _f(x) -> str:
    return "—" if x is None else f"{x:.2f}%"


def generer_rapport(conn: sqlite3.Connection, dossier: DossierDonnees, annee: str) -> Path:
    """تقرير مؤشر التحكم في التعلمات: لكل قسم ومادة توزيع المستويات وInd وISA حسب المراحل، والهدف المقترح."""
    donnees = resultats(conn, annee)
    if not donnees:
        raise ErreurIsa(f"لا نتائج روائز للسنة {annee}: حمّل ملفات النتائج أو أدخل الأعداد أولاً.")
    try:
        c = dc.champs_communs(conn)
    except dc.ErreurDocument as e:
        raise ErreurIsa(str(e)) from None
    d = _nouveau(paysage=True)
    para(d, f"{c['ville']} في: {tx.date_longue_ar(date.today().isoformat())}", apres=0)
    para(d, f"المؤسسة: {c['etablissement']}", gras=True, apres=6)
    para(d, "تقرير حول مؤشر التحكم في التعلمات ISA2", gras=True, taille=20, centre=True, apres=0)
    para(d, f"المدرسة الرائدة — السنة الدراسية {annee}", centre=True, apres=4)
    para(d, f"طريقة الحساب: Ind = [(3×A + 2×B + 1×C) / 3] × 100 ؛ ISA2 = α × Ind ؛ α = {ALPHA:g}. "
            "A: تحكم تام، B: تحكم مقنع، C: تحكم ضعيف (نسب التلاميذ). ISA0: الرائز القبلي، ISA1: الرائز البعدي.",
         taille=11, apres=8)

    # 1. حصيلة المؤسسة
    phases = sorted({p for cl in donnees.values() for m in cl.values() for p in m})
    para(d, "1. حصيلة المؤسسة حسب المادة والمرحلة", gras=True, taille=16, apres=2)
    n = len(phases)
    t = tableau(d, 1 + len(MATIERES), 1 + n, largeurs=[3.2] + [22.0 / n] * n)
    _cellule(t.cell(0, 0), "المادة", gras=True, taille=11)
    _ombre(t.cell(0, 0))
    for j, p in enumerate(phases, start=1):
        _cellule(t.cell(0, j), f"{libelle_phase(p)} ({code_isa(p)})", gras=True, taille=11)
        _ombre(t.cell(0, j))
    for i, (m, lib) in enumerate(MATIERES.items(), start=1):
        _cellule(t.cell(i, 0), lib, gras=True, taille=11)
        for j, p in enumerate(phases, start=1):
            e = ensemble(donnees, m, p)
            _cellule(t.cell(i, j), "—" if e is None else f"{_f(e.isa)}\n(A {e.pct(e.a):.0f}% · B {e.pct(e.b):.0f}% · "
                                                         f"C {e.pct(e.c):.0f}%)", taille=10)
    para(d, apres=8)

    # 2. تفصيل حسب القسم
    para(d, "2. التفصيل حسب القسم والمادة", gras=True, taille=16, apres=2)
    entetes = ("القسم", "المادة", "المرحلة", "العدد", "A تام", "B مقنع", "C ضعيف", "Ind", "المؤشر", "التطور")
    lignes = []
    for cl in sorted(donnees):
        for m in MATIERES:
            avant = None
            for p in sorted(donnees[cl].get(m, {})):
                k = donnees[cl][m][p]
                ecart = None if avant is None or k.isa is None else round(k.isa - avant, 2)
                lignes.append((cl.replace("-", ""), MATIERES[m], f"{libelle_phase(p)} ({code_isa(p)})", str(k.total),
                               f"{k.a} ({k.pct(k.a):.0f}%)", f"{k.b} ({k.pct(k.b):.0f}%)", f"{k.c} ({k.pct(k.c):.0f}%)",
                               _f(k.ind), _f(k.isa), "—" if ecart is None else f"{ecart:+.2f}"))
                avant = k.isa
    t = tableau(d, 1 + len(lignes), len(entetes), largeurs=[1.8, 2.2, 3.6, 1.4, 2.4, 2.4, 2.4, 2.4, 2.4, 2.2])
    for j, lib in enumerate(entetes):
        _cellule(t.cell(0, j), lib, gras=True, taille=10)
        _ombre(t.cell(0, j))
    for i, l in enumerate(lignes, start=1):
        for j, v in enumerate(l):
            _cellule(t.cell(i, j), v, taille=10)

    # 3. تحديد الهدف
    saut_page(d)
    para(d, "3. تحديد الهدف حسب قيمة المؤشر (آخر مرحلة متوفرة)", gras=True, taille=16, apres=2)
    entetes = ("القسم", "المادة", "المرجع", "المؤشر", "الفئة", "التطور المرتقب", "الهدف حسب الجدول",
               "الهدف المقترح")
    lignes = []
    for cl in sorted(donnees):
        for m in MATIERES:
            ref = reference(donnees[cl].get(m, {}))
            if not ref or ref[1].isa is None:
                continue
            p, k = ref
            o = objectif(k.isa)
            lignes.append((cl.replace("-", ""), MATIERES[m], libelle_phase(p), _f(k.isa), o["categorie"],
                           f"من {o['min']} إلى {o['max']} نقطة", o["objectif"],
                           f"{o['cible_min']:.2f}% – {o['cible_max']:.2f}%"))
    t = tableau(d, 1 + len(lignes), len(entetes), largeurs=[1.8, 2.2, 2.8, 2.2, 3.6, 3.4, 4.2, 3.4])
    for j, lib in enumerate(entetes):
        _cellule(t.cell(0, j), lib, gras=True, taille=10)
        _ombre(t.cell(0, j))
    for i, l in enumerate(lignes, start=1):
        for j, v in enumerate(l):
            _cellule(t.cell(i, j), v, taille=10)
    para(d, apres=6)
    t = tableau(d, 1 + len(CATEGORIES), 4, largeurs=[5.0, 3.0, 3.0, 5.6])
    for j, lib in enumerate(("ISA2", "MIN", "MAX", "OBJECTIF")):
        _cellule(t.cell(0, j), lib, gras=True, taille=10)
        _ombre(t.cell(0, j))
    for i, (_, dmin, dmax, _, _, fourchette, texte) in enumerate(CATEGORIES, start=1):
        for j, v in enumerate((fourchette, str(dmin), str(dmax), texte)):
            _cellule(t.cell(i, j), v, taille=10)
    para(d, apres=12)
    para(d, c["mudir_moassasa"], gras=True, centre=True)
    rep = dossier.archives / annee.replace("/", "-") / "الريادة"
    rep.mkdir(parents=True, exist_ok=True)
    chemin = rep / f"{datetime.now():%Y%m%d_%H%M%S}_تقرير مؤشر ISA2.docx"
    d.save(chemin)
    return chemin
