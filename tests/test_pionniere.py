"""المدرسة الرائدة: تتبع النتائج حسب الفترات، اللقاءات التواصلية، المؤشرات العامة. بيانات وهمية."""

import pytest

from idara.services import pionniere as pn
from idara.services import riyada as ry
from tests.test_docs_association import texte
from tests.test_eleves import base  # noqa: F401  (fixture)


def test_resultats_par_periode_et_rapport(base, dossier):  # noqa: F811
    a = "2026/2027"
    with pytest.raises(pn.ErreurPionniere, match="لا نتائج"):
        pn.generer_rapport_resultats(base, dossier, a)
    ry.enregistrer_isa(base, a, "1-1", 1, {"ar": "40", "fr": "30", "ma": "50"})
    ry.enregistrer_isa(base, a, "1-2", 1, {"ar": "60", "fr": "", "ma": "40"})
    ry.enregistrer_isa(base, a, "1-1", 2, {"ar": "55", "fr": "45", "ma": "65"})
    l = pn.resultats_periode(base, a, 1)
    assert [x["classe"] for x in l] == ["1-1", "1-2"] and l[1]["fr"] is None and l[1]["moyenne"] == 50.0
    m = pn.moyennes_par_phase(base, a)
    assert list(m) == [1, 2] and m[1]["ar"] == 50.0 and m[2]["all"] == 55.0
    t = texte(pn.generer_rapport_resultats(base, dossier, a))
    assert "تقرير تركيبي حول النتائج حسب الفترات" in t and "المرحلة 2: النسب حسب الأقسام" in t
    assert "قراءة موجزة" in t and "أعلى نسبة في الرياضيات" in t
    ind = {x["cle"]: x for x in pn.indicateurs(base)}
    assert ind["isa2"]["valeur"] == 55.0 and ind["isa2"]["etat"] == "في تحسن"
    assert ind["activites"]["etat"] in ("لا مرجع للمقارنة", "لا معطيات") and ind["hadar"]["sens"] == -1


def test_rencontres_et_rapports(base, dossier):  # noqa: F811
    with pytest.raises(pn.ErreurPionniere, match="أكبر"):
        pn.enregistrer_rencontre(base, pn.Rencontre("rencontre", "2026-11-10", invites=10, presents=12))
    rid = pn.enregistrer_rencontre(base, pn.Rencontre("rencontre", "2026-11-10", "نتائج المرحلة الأولى", "15:00",
                                                      40, 30, "عرض النتائج", "تتبع الواجبات المنزلية"))
    pn.enregistrer_rencontre(base, pn.Rencontre("portes", "2026-12-05", "الأبواب المفتوحة", invites=50, presents=20))
    assert len(pn.rencontres(base)) == 2 and len(pn.rencontres(base, "portes")) == 1
    assert pn.taux_presence(pn.rencontre(base, rid)) == 75.0
    t = texte(pn.generer_rapport_rencontre(base, dossier, rid))
    assert "تقرير حول اليوم التواصلي" in t and "75.0%" in t and "تتبع الواجبات المنزلية" in t
    t = texte(pn.generer_rapport_rencontres(base, dossier))
    assert "الأيام التواصلية والأبواب المفتوحة" in t and "55.6%" in t and "أبرز التوصيات" in t
    pn.supprimer_rencontre(base, rid)
    assert len(pn.rencontres(base)) == 1
