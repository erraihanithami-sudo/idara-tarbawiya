"""وحدة النصوص: التواريخ والمدد والتذكير والتأنيث."""

from datetime import date

import pytest

from idara.services import textes as tx


@pytest.mark.parametrize("d, attendu", [
    (date(2025, 12, 23), "23 دجنبر 2025"),
    (date(2026, 7, 13), "13 يوليوز 2026"),
    (date(2026, 8, 1), "1 غشت 2026"),
    (date(2026, 9, 15), "15 شتنبر 2026"),
    (date(2026, 11, 14), "14 نونبر 2026"),
    ("1998-06-30", "30 يونيو 1998"),
])
def test_date_ar(d, attendu):
    assert tx.date_ar(d) == attendu


def test_autres_formats():
    assert tx.date_longue_ar(date(2026, 10, 31)) == "السبت 31 أكتوبر 2026"
    assert tx.date_chiffres("2026-07-06") == "06/07/2026"
    assert tx.date_fr(date(2026, 11, 1)) == "1er novembre 2026"
    assert tx.date_fr(date(2024, 12, 19)) == "19 décembre 2024"
    assert tx.date_fr(date(2026, 8, 31)) == "31 août 2026"


@pytest.mark.parametrize("n, attendu", [
    (1, "يوم واحد"), (2, "يومان"), (3, "ثلاثة أيام"), (10, "عشرة أيام"),
    (11, "أحد عشر يوماً"), (12, "اثنا عشر يوماً"), (15, "خمسة عشر يوماً"),
    (20, "عشرون يوماً"), (21, "واحد وعشرون يوماً"), (22, "اثنان وعشرون يوماً"),
    (45, "خمسة وأربعون يوماً"), (90, "تسعون يوماً"), (120, "120 يوماً"),
])
def test_duree_jours(n, attendu):
    assert tx.duree_jours_ar(n) == attendu


def test_duree_invalide():
    with pytest.raises(ValueError):
        tx.duree_jours_ar(0)


def test_accord():
    assert tx.accord("M", "المزداد", "المزدادة") == "المزداد"
    assert tx.accord("F", "Né", "Née") == "Née"
    with pytest.raises(ValueError):
        tx.accord(None, "a", "b")


def test_niveaux_complets():
    assert set(tx.NIVEAUX) == {"PS1", "PS2", "1AP", "2AP", "3AP", "4AP", "5AP", "6AP"}
    assert tx.niveau_ar("5AP") == "الخامس"
    assert tx.niveau_fr("6AP") == "6ème année de l’enseignement primaire"
