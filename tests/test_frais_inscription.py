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


def test_montants_manuels_et_sans_prescolaire(base):  # noqa: F811
    """طلب المدير 2026-11-19: المبالغ يكتبها المدير، والتعليم الأولي خارج اللائحة، والعرض حسب القسم."""
    with pytest.raises(fr.ErreurFrais, match="رقم"):
        fr.definir_montants(base, {"assurance": "اثنا عشر"})
    with pytest.raises(fr.ErreurFrais, match="سالباً"):
        fr.definir_montants(base, {"sport": "-1"})
    m = fr.definir_montants(base, {"assurance": "12,5", "sport": "15", "cooperative": "5"})
    assert m == {"assurance": 12.5, "sport": 15, "cooperative": 5}
    liste = fr.lister(base)
    assert liste and not any((x["niveau"] or "").startswith("PS") or x["classe"].startswith("PS") for x in liste)
    cls = fr.classes(base)
    assert cls and all(not c.startswith("PS") for c in cls)
    assert {x["classe"] for x in fr.lister(base, classe=cls[0])} == {cls[0]}
    fr.marquer(base, liste[0]["id"], "assurance", True)
    assert fr.totaux(base)["elements"]["assurance"]["montant"] == 12.5


def test_mokhrajat_wajibat(base, dossier):  # noqa: F811
    """طلب المدير 2026-11-23: وثيقة مخرجات الواجبات المدرسية حسب الأقسام أو المؤسسة كاملة أو قسم."""
    from docx import Document
    _milieu(base, "urbain")
    liste = fr.lister(base)
    ids = [x["id"] for x in liste]
    fr.marquer_tous(base, ids, "assurance")
    fr.marquer(base, ids[0], "sport", True)
    r = fr.releve(base, "classes")
    assert sum(l["eleves"] for l in r["lignes"]) == len(ids) and r["totaux"]["total"] == 12 * len(ids) + 10
    assert {l["libelle"] for l in r["lignes"]} == set(fr.classes(base))
    re_ = fr.releve(base, "etablissement")
    assert sum(l["total"] for l in re_["lignes"]) == r["totaux"]["total"]
    cl = liste[0]["classe"]
    rc = fr.releve(base, "classe", cl)
    assert rc["lignes"][0]["elements"]["assurance"] and all(l["code"] is not None for l in rc["lignes"])
    with pytest.raises(fr.ErreurFrais, match="اختر القسم"):
        fr.releve(base, "classe")
    for portee, cle in (("classes", None), ("etablissement", None), ("classe", cl)):
        p = fr.generer_releve(base, dossier, portee, cle)
        d = Document(p)
        texte = "\n".join(x.text for x in d.paragraphs)
        cellules = " ".join(c.text for t in d.tables for row in t.rows for c in row.cells)
        assert "مخرجات الواجبات المدرسية" in texte and "المبلغ الإجمالي المتحصل عليه" in texte
        assert "المجموع" in cellules and "التأمين المدرسي" in cellules


def test_fiche_collecte_vierge(base, dossier):  # noqa: F811
    """طلب المدير 2026-11-24: مطبوع يملؤه الأساتذة يدوياً: الأسماء فقط، وخانات الواجبات فارغة."""
    from docx import Document
    _milieu(base, "urbain")
    liste = fr.lister(base)
    fr.marquer_tous(base, [x["id"] for x in liste], "assurance")   # ما سُجل في البرنامج لا يُطبع في المطبوع
    cl = liste[0]["classe"]
    d = Document(fr.generer_fiche_collecte(base, dossier, cl, lignes_vides=2))
    t = d.tables[0]
    n = len(fr.lister(base, classe=cl))
    assert len(t.rows) == 1 + n + 2 + 1
    assert [c.text for c in t.rows[0].cells][:4] == ["ر.ت", "النسب", "الاسم", "التأمين (12 د)"]
    assert t.rows[0].cells[-1].text == "رقم السجل" and t.rows[-1].cells[1].text == "المجموع"
    assert all(not c.text for r in t.rows[1:-1] for c in r.cells[3:])   # خانات الواجبات فارغة
    assert t.rows[1].cells[1].text == liste[0]["nom_ar"] and t.rows[n + 2].cells[0].text == f"{n + 2:02d}"
    assert any(f"القسم: {cl}" in p.text for p in d.paragraphs)
    d2 = Document(fr.generer_fiche_collecte(base, dossier, avec_montants=False))
    assert len(d2.tables) == len(fr.classes(base)) and d2.tables[0].rows[0].cells[3].text == "التأمين"
