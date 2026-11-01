"""تتبع سلوك التلاميذ والاستدعاء. بيانات وهمية."""

import pytest

from idara.services import comportement as cp
from tests.test_eleves import _id, base  # noqa: F401  (fixture)


def test_observation_et_recapitulatif(base):  # noqa: F811
    a, b = _id(base, "X000000001"), _id(base, "X000000002")
    cp.enregistrer(base, cp.Observation(a, "2026-10-01", "شغب في القسم", signale_par="أستاذ القسم"))
    o2 = cp.enregistrer(base, cp.Observation(a, "2026-10-10", "شغب في القسم", mesure="تنبيه شفوي"))
    cp.enregistrer(base, cp.Observation(b, "2026-10-05", "تأخر متكرر"))
    assert [r["date_obs"] for r in cp.observations(base, a)] == ["2026-10-10", "2026-10-01"]
    rec = cp.recapitulatif(base)
    assert [(r["id"], r["n"]) for r in rec] == [(a, 2), (b, 1)]
    assert cp.suggestions(base, "nature")[0] == "شغب في القسم"
    cp.enregistrer(base, cp.Observation(a, "2026-10-11", "تأخر", id=o2))
    assert cp.observations(base, a)[0]["nature"] == "تأخر"


@pytest.mark.parametrize("modif, message", [(dict(nature=" "), "إجبارية"), (dict(date_obs="2099-01-01"), "المستقبل"),
                                            (dict(date_obs="x"), "غير صحيح")])
def test_refus(base, modif, message):  # noqa: F811
    d = dict(eleve_id=_id(base, "X000000001"), date_obs="2026-10-01", nature="شغب")
    d.update(modif)
    with pytest.raises(cp.ErreurComportement, match=message):
        cp.enregistrer(base, cp.Observation(**d))


def test_convocation_depuis_observation(base, dossier):  # noqa: F811
    from idara.services import eleves as el
    from idara.services import moteur_docx as m
    a = _id(base, "X000000003")
    o = cp.enregistrer(base, cp.Observation(a, "2026-10-01", "عنف لفظي"))
    doc = cp.convoquer(base, dossier, o, "2026-10-02")
    assert "يوسف المثال" in m.texte_complet(doc.chemin.read_bytes())
    r = cp.observations(base, a)[0]
    assert r["date_convocation"] == "2026-10-02" and r["mesure"] == "استدعاء ولي الأمر"
    assert cp.recapitulatif(base)[0]["convocations"] == 1
    assert any(d["titre"] == "استدعاء ولي الأمر" for d in el.documents(base, a))
    with pytest.raises(cp.ErreurComportement, match="لا تُحذف"):
        cp.supprimer(base, o)
    o2 = cp.enregistrer(base, cp.Observation(a, "2026-10-03", "خطأ"))
    cp.supprimer(base, o2)
    assert len(cp.observations(base, a)) == 1
