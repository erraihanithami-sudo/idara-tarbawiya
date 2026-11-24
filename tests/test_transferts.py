"""استخلاص واجبات الجمعية الرياضية والتعاونية المدرسية وتحويل حصصها (وثائق المدير 2026-11-24): معطيات وهمية."""

from datetime import date

import pytest
from docx import Document

from idara.services import associations as asso
from idara.services import frais_inscription as fr
from idara.services import transferts as tr
from tests.test_eleves import base  # noqa: F401
from tests.test_frais_inscription import _milieu


def test_regimes_et_rubriques(base):  # noqa: F811
    for t in ("sportive", "cooperative"):
        rg = tr.regime(t)
        assert sum(p.pct for p in rg.parts) == 100
        assert asso.association(base, t)["nom"] == rg.nom
        assert asso.rubriques(base, t, "recette", actifs=True) and asso.rubriques(base, t, "depense", actifs=True)
    assert sum(pc for _, pc in tr.regime("cooperative").parts[1].sous) == 60
    assert sum(pc for _, pc in tr.regime("cooperative").programme) == 100
    with pytest.raises(tr.ErreurTransfert):
        tr.regime("autre")


def test_collecte_repartition_virements(base, dossier):  # noqa: F811
    _milieu(base, "urbain")
    ids = [x["id"] for x in fr.lister(base)]
    fr.marquer_tous(base, ids, "sport")
    c = tr.collecte(base, "sportive")
    assert c["source"] == "programme" and c["montant"] == 10 * len(ids) and c["eleves"] == len(ids)
    tr.definir_collecte(base, "sportive", "2 000", 200)   # المسك اليدوي من محاضر الأساتذة
    r = tr.repartition(base, "sportive")
    assert {l["cle"]: l["du"] for l in r["lignes"]} == {"association": 1300, "frmss": 300, "fonds": 100,
                                                        "direction": 200, "academie": 100}
    assert r["lignes"][1]["compte"].startswith("CCP 5094-70X")
    tr.definir_compte(base, "sportive", "direction", " 0011  22 ")
    assert tr.repartition(base, "sportive")["lignes"][3]["compte"] == "0011 22"
    with pytest.raises(tr.ErreurTransfert, match="يتجاوز"):
        tr.enregistrer_virement(base, "sportive", "frmss", "2026-10-10", 301)
    tr.enregistrer_virement(base, "sportive", "frmss", "2026-10-10", 200, "شيك 12")
    v = tr.enregistrer_virement(base, "sportive", "frmss", "2026-12-20")   # الباقي
    l = tr.repartition(base, "sportive")["lignes"][1]
    assert l["vire"] == 300 and l["reste"] == 0 and l["dates"] == ["2026-10-10", "2026-12-20"]
    with pytest.raises(tr.ErreurTransfert, match="لا باقي"):
        tr.enregistrer_virement(base, "sportive", "frmss", "2026-12-21")
    tr.supprimer_virement(base, "sportive", v)
    assert tr.repartition(base, "sportive")["lignes"][1]["reste"] == 100
    al = tr.echeances(base, "sportive", date(2026, 10, 1))
    assert al and "15 أكتوبر" in al[0]
    assert "تجاوز" in tr.echeances(base, "sportive", date(2027, 1, 5))[0]
    tr.definir_collecte(base, "sportive", None)
    assert tr.collecte(base, "sportive")["source"] == "programme"
    # التعاونية: 40% للمؤسسة وبرمجة صرفها، و60% للفرع بتفصيلها
    tr.definir_collecte(base, "cooperative", 1000)
    r = tr.repartition(base, "cooperative")
    assert [l["du"] for l in r["lignes"]] == [400, 600]
    assert r["lignes"][1]["sous"][0] == ("المطاعم المدرسية", 20, 200)
    assert [m for *_, m in r["programme"]] == [120, 80, 80, 80, 40]
    p = tr.generer_pv_collecte(base, dossier, "cooperative")
    texte = " ".join(c.text for t in Document(p).tables for row in t.rows for c in row.cells)
    assert "النشاط الاجتماعي" in texte and "المطاعم المدرسية" in texte and "400.00" in texte
    with pytest.raises(tr.ErreurTransfert, match="لا تحويلات"):
        tr.generer_certificat(base, dossier, "cooperative")
    tr.enregistrer_virement(base, "cooperative", "branche", "2026-11-02", reference="حوالة")
    d = Document(tr.generer_certificat(base, dossier, "cooperative", "رئيس الجمعية"))
    assert any("600.00" in p.text for p in d.paragraphs)
    assert "02/11/2026" in " ".join(c.text for row in d.tables[0].rows for c in row.cells)


def test_part_association_en_recette(base):  # noqa: F811
    tr.definir_collecte(base, "sportive", 1000)
    with pytest.raises(tr.ErreurTransfert, match="السنة المالية"):
        tr.inscrire_part_association(base, "sportive", "2026-10-20")
    asso.ouvrir_exercice(base, "sportive", "2026", "2026-01-01", "2026-12-31")
    oid = tr.inscrire_part_association(base, "sportive", "2026-10-20")
    eid = asso.exercices(base, "sportive")[0]["id"]
    assert oid and asso.totaux(base, eid)["recettes"] == 650 and asso.totaux(base, eid)["banque"] == 650
    with pytest.raises(tr.ErreurTransfert, match="من قبل"):
        tr.inscrire_part_association(base, "sportive", "2026-10-21")
