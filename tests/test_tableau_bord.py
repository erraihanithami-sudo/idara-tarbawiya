"""مؤشرات لوحة القيادة. بيانات وهمية."""

from idara.services import eleves as el
from idara.services import etablissement as et
from idara.services import evaluation as ev
from idara.services import tableau_bord as tb
from tests.fabrique_resultats import classeur_resultats
from tests.test_eleves import base  # noqa: F401


def test_indicateurs_de_base_hadar_et_reussite(tmp_path, base):  # noqa: F811
    i = tb.indicateurs(base)
    assert i["eleves"] == i["garcons"] + i["filles"] and i["eleves"] > 0
    assert i["hadar"]["taux"] == 0 and i["activites"]["taux"] == 0 and i["absences"] is None
    assert not i["pionniere"] and i["maitrise"] is None and i["reussite"]["total"] == 0
    eid = base.execute("SELECT e.id FROM eleve e JOIN inscription i ON i.eleve_id=e.id LIMIT 1").fetchone()[0]
    el.changer_statut(base, eid, "interrompu", "2026-11-01", motif="انقطاع")
    i2 = tb.indicateurs(base)
    assert i2["hadar"]["interrompus"] == 1 and i2["eleves"] == i["eleves"] - 1
    assert i2["hadar"]["taux"] == round(100 / i["eleves"], 2)
    codes = [r[0] for r in base.execute("SELECT code_massar FROM eleve LIMIT 2")]
    ev.importer(base, [classeur_resultats(tmp_path / "r.xlsx", {"4APG-5APG-6APG": [
        (codes[0], "أ", [8.0] * 8), (codes[1], "ب", [4.0] * 8)]})])
    r = tb.indicateurs(base)["reussite"]
    assert (r["admis"], r["total"], r["taux"], r["source"]) == (1, 2, 50.0, "المعدل السنوي")


def test_pionniere_et_unite(base):  # noqa: F811
    e = et.lire_etablissement(base)
    e.est_pionniere = "1"
    et.enregistrer_etablissement(base, e)
    i = tb.indicateurs(base)
    assert i["pionniere"] and set(i["maitrise"]) == {"ar", "fr", "ma"} and i["reussite"] is None
    assert i["maitrise"]["ar"]["taux"] is None
    assert tb.indicateurs(base, unite="وحدة غير موجودة")["eleves"] == 0
