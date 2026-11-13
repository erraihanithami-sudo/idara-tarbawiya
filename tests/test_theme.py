"""مظاهر البرنامج: كل نص مكتوب على خلفيته بتباين 4.5:1 على الأقل (WCAG AA)."""

import pytest

from idara.ui.palettes import NOMS_THEMES, PAIRES_TEXTE, PALETTES, contraste


@pytest.mark.parametrize("nom", list(PALETTES))
def test_contraste_palettes(nom):
    p = PALETTES[nom]
    for texte, fond in PAIRES_TEXTE:
        assert contraste(p[texte], p[fond]) >= 4.5, (nom, texte, fond, round(contraste(p[texte], p[fond]), 2))


def test_palettes_completes():
    cles = set(PALETTES["classique"])
    assert all(set(p) == cles for p in PALETTES.values()) and set(NOMS_THEMES) == set(PALETTES)


def test_rihab_par_defaut():
    """هوية «الشامل في الإدارة التربوية بالمغرب» (اختيار المدير 2026-11-13)، والمغربي يبقى متاحاً."""
    from idara.ui.palettes import THEME_DEFAUT
    assert THEME_DEFAUT == "rihab" and PALETTES["rihab"]["POLICE_TITRE"] == "El Messiri"
    assert PALETTES["rihab"]["NAV_FOND"] == "#2E3192" and PALETTES["maghribi"]["POLICE_TITRE"] == "Amiri"


def test_marque_geometrie():
    from idara import marque
    for pts in (marque.ARC_EXTERIEUR, marque.ARC_INTERIEUR):
        assert all(0 <= x <= 256 and 0 <= y <= 256 for x, y in pts)
        assert min(y for _, y in pts) < 120          # القوس يعلو الباب
        xs = [x for x, _ in pts]
        assert max(xs) - min(xs) > (pts[-1][0] - pts[0][0])   # حدوة: أعرض من قاعدتها
    assert marque.couleurs(True)["tuile"] == "#FFFFFF" and marque.couleurs()["tuile"] == marque.MAJORELLE
