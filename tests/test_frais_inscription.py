"""تدبير تسجيلات التلاميذ: الواجبات والعدّاد التراكمي (بيانات وهمية)."""

import pytest

from idara.services import etablissement as et
from idara.services import frais_inscription as fr
from tests.test_eleves import base  # noqa: F401


def _milieu(conn, m):
    e = et.lire_etablissement(conn)
    e.milieu = m
    et.enregistrer_etablissement(conn, e)


def test_montants_selon_milieu(base):  # noqa: F811
    assert fr.montants(base)["assurance"] is None   # الوسط غير محدد بعد
    _milieu(base, "rural")
    assert fr.montants(base) == {"assurance": 8, "sport": 10, "cooperative": 10}
    _milieu(base, "urbain")
    assert fr.montants(base)["assurance"] == 12
    e = et.lire_etablissement(base)
    e.milieu = "ailleurs"
    with pytest.raises(et.ErreurValidation):
        e.valider()


def test_marquer_et_totaux(base):  # noqa: F811
    _milieu(base, "rural")
    liste = fr.lister(base)
    assert liste and all(not x["assurance"] for x in liste)
    ids = [x["id"] for x in liste]
    fr.marquer_tous(base, ids, "assurance")
    fr.marquer(base, ids[0], "sport", True)
    fr.marquer(base, ids[0], "cooperative", True)
    t = fr.totaux(base)
    n = len(ids)
    assert t["elements"]["assurance"] == {"libelle": "التأمين المدرسي", "payes": n, "montant_unitaire": 8,
                                          "montant": 8 * n}
    assert t["elements"]["sport"]["montant"] == 10 and t["total"] == 8 * n + 20
    fr.marquer(base, ids[0], "sport", False)
    assert fr.totaux(base)["elements"]["sport"]["payes"] == 0
    niv = liste[0]["niveau"]
    assert fr.totaux(base, niveau=niv)["eleves"] == sum(1 for x in liste if x["niveau"] == niv)
    with pytest.raises(fr.ErreurFrais):
        fr.marquer(base, ids[0], "autre", True)
