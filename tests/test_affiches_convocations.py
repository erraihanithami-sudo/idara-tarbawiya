"""الإعلانات المزخرفة واستدعاءات أولياء الأمور (2026-11-15). بيانات وهمية."""

import re

import pytest
from docx import Document

from idara.services import affiches as af
from idara.services import convocations as cv
from tests.test_eleves import AR, base, classeur  # noqa: F401

CONTENU = af.Contenu(titre="الدخول المدرسي", texte="نص تجريبي", date="الاثنين 7 شتنبر 2026", heure="8:30",
                     lieu="ساحة المؤسسة", etablissement="مدرسة تجريبية")


def test_dix_themes_et_occasions():
    assert len(af.THEMES) == 10 and len({t.nom for t, _ in af.THEMES.values()}) == 10
    assert {"rentree", "activite", "examen"} <= set(af.OCCASIONS) and len(af.OCCASIONS) == 10
    for cle, (th, _) in af.THEMES.items():
        d = af.composer(cle, CONTENU)
        assert len(d.formes) > 15, cle
        x0, y0, x1, y1 = th.zone
        assert 0 <= x0 < x1 <= af.L and 0 <= y0 < y1 <= af.H
        for f in d.formes:   # الأشكال داخل الورقة (الزخرفة قد تتجاوز الحافة قليلاً وتُقص)
            pts = f.get("p") or ([f["c"]] if f["t"] == "cercle" else [f["b"][:2]])
            assert all(-12 <= x <= af.L + 12 and -12 <= y <= af.H + 12 for x, y in pts), (cle, f)
            assert 0 < f["o"] <= 1 and (f["f"] is not None or f["s"] is not None)
        for t in d.textes:   # كل نص داخل الورقة، بلون صالح
            x, y, w, h = t.boite
            assert x >= 0 and y >= 0 and x + w <= af.L and y + h <= af.H and w > 0 and h > 0, (cle, t)
            assert re.fullmatch(r"#[0-9A-Fa-f]{6}", t.couleur) and t.texte.strip()
        textes = [t.texte for t in d.textes]
        assert "الدخول المدرسي" in textes and "8:30" in textes and "ساحة المؤسسة" in textes and "الإدارة" in textes
        assert "الفئة المعنية" not in textes   # الحقل الفارغ لا يُرسم
        svg = af.en_svg(d, "A3")
        assert svg.startswith("<svg") and 'width="297.0mm"' in svg and 'viewBox="0 0 210.0 297.0"' in svg
    assert sum(th.economique for th, _ in af.THEMES.values()) == 1


def test_affiche_validation_et_infos():
    with pytest.raises(af.ErreurAffiche, match="عنوان"):
        af.composer("zellige", af.Contenu(titre="  "))
    with pytest.raises(af.ErreurAffiche, match="قالب"):
        af.composer("inconnu", CONTENU)
    c = af.Contenu(titre="ع", date="ت", heure="س", lieu="م", public="ف")
    assert [l for l, _ in c.infos()] == ["التاريخ", "الساعة", "المكان", "الفئة المعنية"]
    d = af.composer("officiel", c)
    assert sum(1 for t in d.textes if t.texte in ("ت", "س", "م", "ف")) == 4
    assert af.composer("rihab", af.Contenu(titre="عنوان فقط")).textes   # بلا نص ولا معطيات: لا خطأ
    assert not af.apercu_vide("fete").textes


def _textes(chemin):
    d = Document(chemin)
    return d, [c.text for t in d.tables for r in t.rows for c in r.cells]


def test_convocations(base, dossier):  # noqa: F811
    assert cv.libelle("portes", "3") == "الأبواب المفتوحة رقم 3" and cv.libelle("rencontre", "05").endswith("05")
    assert cv.libelle("ag_parents") == "الجمع العام لجمعية أمهات وآباء وأولياء التلاميذ"
    with pytest.raises(cv.ErreurConvocation, match="رقم"):
        cv.libelle("portes", "7")
    tous = cv.eleves(base)
    assert tous and all(e["code_massar"] for e in tous)
    with pytest.raises(cv.ErreurConvocation, match="تاريخ"):
        cv.generer(base, dossier, "ag_parents", "", "", "10:00", "")
    with pytest.raises(cv.ErreurConvocation, match="ساعة"):
        cv.generer(base, dossier, "ag_parents", "", "2026-11-21", " ", "")
    with pytest.raises(cv.ErreurConvocation, match="الصفحة"):
        cv.generer(base, dossier, "ag_parents", "", "2026-11-21", "10:00", "", par_page=5)
    p = cv.generer(base, dossier, "rencontre", "02", "2026-11-21", "10:00", "قاعة الاجتماعات",
                   "تتبع النتائج\nالدعم التربوي", par_page=4)
    d, cellules = _textes(p)
    pleines = [c for c in cellules if c.strip()]
    assert len(pleines) == len(tous) and len(d.tables) == -(-len(tous) // 4)
    assert all(len(t.columns) == 2 and len(t.rows) <= 2 for t in d.tables)
    e = tous[0]
    c = next(x for x in pleines if e["code_massar"] in x)
    assert f"{e['prenom_ar']} {e['nom_ar']}" in c and "اللقاء التواصلي رقم 02" in c and "السبت 21 نونبر 2026" in c
    assert "10:00" in c and "بـقاعة الاجتماعات" in c and "تتبع النتائج؛ الدعم التربوي" in c and "استدعاء" in c
    assert ("التلميذة:" in c) == (e["sexe"] == "F") and "..." not in c
    jour, mois, an = e["date_naissance"][8:], e["date_naissance"][5:7], e["date_naissance"][:4]
    assert f"{jour}/{mois}/{an}" in c
    # تلميذ واحد، استدعاء واحد في الصفحة؛ ثم ثمانية في الصفحة
    p = cv.generer(base, dossier, "ag_parents", "", "2026-11-21", "15:00", "", par_page=1, ids=[e["id"]])
    d, cellules = _textes(p)
    assert len(d.tables) == 1 and len(cellules) == 1 and "جدول الأعمال" not in cellules[0] and " بـ" not in cellules[0]
    d, _ = _textes(cv.generer(base, dossier, "portes", "1", "2026-11-21", "9:00", "", par_page=8))
    assert all(len(t.columns) == 2 and len(t.rows) <= 4 for t in d.tables)
    with pytest.raises(cv.ErreurConvocation, match="لا تلاميذ"):
        cv.generer(base, dossier, "portes", "1", "2026-11-21", "9:00", "", ids=[])
