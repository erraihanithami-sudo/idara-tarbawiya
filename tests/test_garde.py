"""الحراسة التربوية بالمناطق (توجيه المدير 2026-11-15). أسماء وهمية."""

from datetime import date

import pytest
from docx import Document

from idara.services import garde as gd
from tests.test_eleves import AR, base, classeur  # noqa: F401

PROFS = [f"أستاذ وهمي {i}" for i in range(1, 8)]


def _texte(chemin):
    d = Document(chemin)
    return d, "\n".join(p.text for p in d.paragraphs), [c.text for t in d.tables for r in t.rows for c in r.cells]


def test_repartition_equitable():
    g = gd.repartir(PROFS, 3, 4, list(gd.JOURS))
    assert list(g) == ["1", "2", "3", "4"] and all(len(g[s][j]) == 3 for s in g for j in gd.JOURS)
    for s in g:
        for j in gd.JOURS:
            assert len(set(g[s][j])) == 3   # لا أستاذ في منطقتين في اليوم نفسه
    n = {}
    for s in g:
        for j in gd.JOURS:
            for p in g[s][j]:
                n[p] = n.get(p, 0) + 1
    assert set(n) == set(PROFS) and max(n.values()) - min(n.values()) <= 1 and sum(n.values()) == 72
    zones_de_1 = {g[s][j].index(PROFS[0]) for s in g for j in gd.JOURS if PROFS[0] in g[s][j]}
    assert len(zones_de_1) > 1   # تناوب المناطق
    with pytest.raises(gd.ErreurGarde, match="أقل من عدد المناطق"):
        gd.repartir(PROFS[:2], 3, 1, ["الاثنين"])


def test_enregistrement_jour_et_documents(base, dossier):  # noqa: F811
    g = gd.lire(base)
    assert g["nb_zones"] == 4 and g["semaines"] == 4 and g["jours"] == list(gd.JOURS) and "عشر دقائق" in g["consignes"]
    with pytest.raises(gd.ErreurGarde, match="فارغ"):
        gd.generer(base, dossier, "tableau")
    with pytest.raises(gd.ErreurGarde, match="من 1 إلى 10"):
        gd.enregistrer(base, {**g, "nb_zones": 11})
    with pytest.raises(gd.ErreurGarde, match="يوم حراسة"):
        gd.enregistrer(base, {**g, "jours": []})
    g.update(nb_zones=3, zones=["الباب الرئيسي", "الساحة", ""], semaines=2, jours=list(gd.JOURS[:5]),
             debut="2026-11-02")
    g["grille"] = gd.repartir(PROFS, 3, 2, g["jours"])
    double = {s: {j: list(v) for j, v in js.items()} for s, js in g["grille"].items()}
    double["1"]["الاثنين"][1] = double["1"]["الاثنين"][0]
    with pytest.raises(gd.ErreurGarde, match="بمنطقتين يوم الاثنين من الأسبوع 1"):
        gd.enregistrer(base, {**g, "grille": double})
    gd.enregistrer(base, g)
    l = gd.lire(base)
    assert l["zones"] == ["الباب الرئيسي", "الساحة", ""] and l["grille"]["2"]["الجمعة"] == g["grille"]["2"]["الجمعة"]
    assert sum(n for _, n in gd.bilan(base)) == 30
    # حراسة اليوم: الأسبوع من الدورة، والأحد والسبت غير المبرمج
    assert gd.semaine_de(l, date(2026, 11, 4)) == 1 and gd.semaine_de(l, date(2026, 11, 10)) == 2
    assert gd.semaine_de(l, date(2026, 11, 16)) == 1
    j = gd.du_jour(base, date(2026, 11, 10))
    assert j["semaine"] == 2 and j["jour"] == "الثلاثاء" and j["lignes"][0] == (
        "منطقة 01", g["grille"]["2"]["الثلاثاء"][0]) and j["lignes"][2][0] == "منطقة 03"
    assert "الأحد" in gd.du_jour(base, date(2026, 11, 15))["motif"]
    assert "السبت" in gd.du_jour(base, date(2026, 11, 14))["motif"]
    # الوثائق
    d, t, c = _texte(gd.generer(base, dossier, "tableau"))
    assert t.count("جدول الحراسة التربوية") == 2 and "الأسبوع 2" in t and "منطقة 01" in c
    # طلب المدير 2026-11-20: مفتاح المناطق أسفل كل جدول
    assert t.count("مفتاح المناطق: منطقة 01: الباب الرئيسي · منطقة 02: الساحة") == 2
    assert "السبت" not in c and g["grille"]["1"]["الاثنين"][0] in c
    d, t, c = _texte(gd.generer(base, dossier, "note"))
    assert "في شأن تدبير الحراسة التربوية" in t and "المادة 85 مكرر" in t and "التوقيع" in c and "الباب الرئيسي" in c
    d, t, c = _texte(gd.generer(base, dossier, "jour", jour=date(2026, 11, 10)))
    assert "الأسبوع 2 من الدورة" in t and g["grille"]["2"]["الثلاثاء"][1] in c
    with pytest.raises(gd.ErreurGarde, match="الأحد"):
        gd.generer(base, dossier, "jour", jour=date(2026, 11, 15))
