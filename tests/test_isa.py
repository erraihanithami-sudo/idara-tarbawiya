"""مؤشر ISA2 محسوب من نتائج الروائز (صيغة المدير 2026-11-12). كل البيانات وهمية."""

import openpyxl
import pytest

from idara.services import isa
from tests.test_docs_association import texte
from tests.test_eleves import base  # noqa: F401  (fixture)


def test_formule_et_objectif():
    k = isa.Calcul(10, 6, 4)          # A 50%، B 30%، C 20%
    assert k.ind == round((3 * .5 + 2 * .3 + .2) / 3 * 100, 2) == 76.67
    assert k.isa == round(0.8 * (3 * .5 + 2 * .3 + .2) / 3 * 100, 2) == 61.33
    assert isa.Calcul(0, 0, 0).isa is None
    assert isa.Calcul(5, 0, 0).isa == 80.0 and isa.Calcul(0, 0, 5).isa == 26.67
    o = isa.objectif(25.0)
    assert (o["min"], o["max"], o["objectif"]) == (15, 20, "ISA2+20% ≤ OB ≤ 50%") and o["cible_min"] == 45.0
    assert isa.objectif(30.0)["min"] == 15 and isa.objectif(30.01)["min"] == 10
    assert isa.objectif(45.0)["objectif"] == "40% ≤ OB ≤ 65%"
    assert isa.objectif(61.33)["min"] == 5 and isa.objectif(61.33)["max"] == 10
    assert isa.objectif(70.0)["objectif"] == "OB ≥ 75%"


def test_niveaux_lus():
    assert [isa.niveau(v) for v in ("A", " b ", "ج", "تحكم تام", "تحكم مقنع", "تحكم ضعيف", 80, 60, 30, "45,5", 0.9)] \
        == ["A", "B", "C", "A", "B", "C", "A", "B", "C", "C", "A"]
    assert isa.niveau("؟؟") is None and isa.niveau(None) is None


def _fichier(chemin, classe, lignes):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = classe
    ws.append(["نتائج الرائز البعدي"])
    ws.append(["القسم", classe])
    ws.append([])
    ws.append(["رقم التلميذ", "الاسم الكامل", "اللغة العربية", "اللغة الفرنسية", "الرياضيات"])
    for i, l in enumerate(lignes, start=1):
        ws.append([f"X{i:09d}", f"تلميذ {i}", *l])
    wb.save(chemin)
    return chemin


def test_import_calcul_rapport(base, dossier, tmp_path):  # noqa: F811
    cl = base.execute("SELECT code FROM classe ORDER BY code").fetchone()[0]
    f = _fichier(tmp_path / "post.xlsx", cl, [("A", "تحكم تام", 90), ("B", "تحكم ضعيف", 55), ("C", "B", 20),
                                              ("A", "", "غير مفهوم")])
    r = isa.importer(base, "2026/2027", 0, [f])
    assert r.eleves == 4 and r.lignes == 3 and any("غير مفهومة" in a for a in r.alertes)
    d = isa.resultats(base, "2026/2027")[cl]
    assert (d["ar"][0].a, d["ar"][0].b, d["ar"][0].c) == (2, 1, 1)
    assert (d["ma"][0].a, d["ma"][0].b, d["ma"][0].c) == (1, 1, 1)
    # يُكتب أيضاً في جدول المراحل الذي تستعمله المراسلات
    from idara.services import riyada as ry
    assert ry.isa(base, "2026/2027")[cl]["ar"][0] == d["ar"][0].isa
    # القبلي (ISA0) والمرحلة الأولى يدوياً
    isa.enregistrer(base, "2026/2027", cl, "ar", -1, 0, 2, 2)
    isa.enregistrer(base, "2026/2027", cl, "ar", 1, 3, 1, 0)
    assert -1 not in ry.isa(base, "2026/2027")[cl]["ar"]
    with pytest.raises(isa.ErreurIsa):
        isa.enregistrer(base, "2026/2027", cl, "ar", 1, "x", 1, 0)
    isa.enregistrer(base, "2026/2027", cl, "fr", 2, 0, 0, 0)   # أعداد فارغة: لا سطر
    assert 2 not in isa.resultats(base, "2026/2027")[cl]["fr"]
    t = texte(isa.generer_rapport(base, dossier, "2026/2027"))
    assert "مؤشر التحكم في التعلمات ISA2" in t and "الرائز القبلي" in t and "ISA0" in t and "تحديد الهدف" in t
    assert "OB ≥ 75%" in t and "+" in t


def test_rapport_sans_donnees(base, dossier):  # noqa: F811
    with pytest.raises(isa.ErreurIsa, match="لا نتائج"):
        isa.generer_rapport(base, dossier, "2026/2027")
