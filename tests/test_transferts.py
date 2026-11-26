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


def test_projet_et_rapport_cooperative(base, dossier):  # noqa: F811
    """بطاقة مشروع صرف مداخيل التعاونية والتقرير المالي (نماذج المديرية، 2026-11-26)."""
    with pytest.raises(tr.ErreurTransfert, match="المنقول"):
        tr.generer_projet_cooperative(base, dossier)
    tr.definir_collecte(base, "cooperative", 2260)          # حصة المؤسسة 40% = 904
    d = tr.donnees_cooperative(base)
    assert d["prevu"] == 904 and d["source_prevu"] == "programme" and d["surplus"] is None
    tr.definir_donnees_cooperative(base, "92", None, "111-85", "منسق وهمي")
    b = tr.bilan_cooperative(base)
    assert b["base"] == 996 and [l["alloue"] for l in b["lignes"]] == [298.8, 199.2, 199.2, 199.2, 99.6]
    assert b["total_alloue"] == 996 and b["solde"] is None
    with pytest.raises(tr.ErreurTransfert, match="سالباً"):
        tr.definir_donnees_cooperative(base, "-1")
    p = tr.generer_projet_cooperative(base, dossier)
    doc = Document(p)
    txt = " ".join(x.text for x in doc.paragraphs)
    cells = " ".join(c.text for t in doc.tables for r in t.rows for c in r.cells)
    assert "بطاقة مشروع صرف مداخيل التعاونية المدرسية" in txt and "111-85" in txt and "20/11" in txt
    assert "298.80" in cells and "996.00" in cells and "منسق وهمي" in cells
    # السنة المالية: المنقول منها والمصاريف حسب المجال
    tr.definir_donnees_cooperative(base, None, None, "111-85")
    eid = asso.ouvrir_exercice(base, "cooperative", "2026-2027", "2026-09-01", "2027-08-31", 92, 0)
    rid = {r["chapitre"]: r["id"] for r in asso.rubriques(base, "cooperative", "depense")}
    asso.enregistrer(base, asso.Operation(eid, "2026-11-10", "depense", "banque", 90, rid["النشاط الاجتماعي"], "فاتورة 1"))
    asso.enregistrer(base, asso.Operation(eid, "2026-11-12", "depense", "banque", 2, rid["مختلفات"], "كشف 1"))
    b = tr.bilan_cooperative(base)
    assert b["surplus"] == 92 and b["source_surplus"] == "programme"
    assert b["lignes"][0]["depense"] == 90 and b["lignes"][0]["reste"] == 208.8 and b["autres_depenses"] == 2
    assert b["solde"] == 0 and b["exercice"] == "2026-2027"
    r = Document(tr.generer_rapport_cooperative(base, dossier))
    txt = " ".join(x.text for x in r.paragraphs)
    cells = " ".join(c.text for t in r.tables for row in t.rows for c in row.cells)
    assert "التقرير المالي للتعاونية المدرسية" in txt and "30/05" in txt and "الباقي في الحساب" in txt
    assert "208.80" in cells and "90.00" in cells
