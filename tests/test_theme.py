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
