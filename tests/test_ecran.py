"""شاشة العرض (طلب المدير 2026-11-21): شرائح من معطيات البرنامج، أرقام مجمَّعة فقط (بيانات وهمية)."""

import json
from datetime import date

import pytest

from idara.services import ecran as ec
from tests.test_eleves import base  # noqa: F401


def test_reglages_par_defaut_et_enregistrement(base):  # noqa: F811
    r = ec.reglages(base)
    assert r["ordre"] == [c for c, *_ in ec.CATALOGUE] and r["actives"] == r["ordre"]
    assert all(v == ec.DUREE_DEFAUT for v in r["durees"].values()) and r["bandeau"] == ""
    with pytest.raises(ValueError, match="واحدة على الأقل"):
        ec.enregistrer_reglages(base, r["ordre"], [], {})
    r = ec.enregistrer_reglages(base, ["niveaux", "couverture", "inconnue"], ["couverture", "inconnue"],
                                {"couverture": 1, "niveaux": 999}, "  مرحباً   بكم  ")
    assert r["ordre"][:2] == ["niveaux", "couverture"] and r["actives"] == ["couverture"]
    assert r["durees"]["couverture"] == 3 and r["durees"]["niveaux"] == 300 and r["bandeau"] == "مرحباً بكم"


def test_diapositives_sans_donnees_personnelles(base):  # noqa: F811
    c = ec.diapositive(base, "couverture")
    assert c["eleves"] > 0 and c["eleves"] == c["garcons"] + c["filles"] and c["classes"] >= 1 and not c["vide"]
    n = ec.diapositive(base, "niveaux")
    assert sum(x["eleves"] for x in n["niveaux"]) == c["eleves"]
    m = ec.diapositive(base, "mouvements")
    assert m["vide"] and m["arrive"] == 0
    t = ec.diapositive(base, "tarl")
    assert t["vide"] and t["niveaux"] == []
    a = ec.diapositive(base, "actualites", date(2026, 11, 20))
    assert isinstance(a["items"], list) and len(a["items"]) <= 6
    # لا أسماء ولا رموز مسار في أي شريحة
    texte = json.dumps([ec.diapositive(base, k) for k, *_ in ec.CATALOGUE], ensure_ascii=False)
    noms = [r[0] for r in base.execute("SELECT nom_ar FROM eleve WHERE nom_ar<>'' LIMIT 20")]
    codes = [r[0] for r in base.execute("SELECT code_massar FROM eleve WHERE code_massar<>'' LIMIT 20")]
    assert noms and not any(x in texte for x in noms + codes)


def test_diaporama_sans_diapos_vides(base):  # noqa: F811
    cles = [d["cle"] for d in ec.diaporama(base)]
    assert cles[0] == "couverture" and "mouvements" not in cles and "tarl" not in cles
    assert all(d["duree"] == ec.DUREE_DEFAUT for d in ec.diaporama(base))
    assert len(ec.diaporama(base, avec_vides=True)) == len(ec.CATALOGUE)
    assert "الموسم الدراسي" in ec.bandeau_defaut(base)
