"""تحديد حاجيات المؤسسة في إطار مشروع المؤسسة المندمج (طلب المدير 2026-11-23): معطيات وهمية."""

import pytest
from docx import Document

from idara.services import besoins as bz
from idara.services import conseils_etab as ce
from tests.test_eleves import base  # noqa: F401


def test_saisie_validation_et_synthese(base):  # noqa: F811
    with pytest.raises(bz.ErreurBesoin, match="مجال"):
        bz.enregistrer(base, {"domaine": "", "besoin": "حواسيب"})
    with pytest.raises(bz.ErreurBesoin, match="اكتب الحاجة"):
        bz.enregistrer(base, {"domaine": bz.DOMAINES[1], "besoin": " "})
    with pytest.raises(bz.ErreurBesoin, match="رقم"):
        bz.enregistrer(base, {"domaine": bz.DOMAINES[1], "besoin": "حواسيب", "cout": "كثير"})
    a = bz.enregistrer(base, {"domaine": bz.DOMAINES[1], "besoin": " حواسيب  محمولة ", "quantite": "4",
                              "cout": "12 000,5", "priorite": "عالية", "source": bz.SOURCES[0]})
    b = bz.enregistrer(base, {"domaine": bz.DOMAINES[0], "besoin": "كتب القراءة", "cout": "1500"})
    assert bz.besoin(base, a)["besoin"] == "حواسيب محمولة" and bz.besoin(base, a)["cout"] == 12000.5
    assert [x["id"] for x in bz.besoins(base)] == [b, a]   # حسب ترتيب المجالات
    assert bz.besoin(base, b)["priorite"] == "متوسطة"
    s = bz.synthese(base)
    assert s["nombre"] == 2 and s["cout"] == 13500.5 and s["prioritaires"] == 1
    bz.enregistrer(base, {"domaine": bz.DOMAINES[0], "besoin": "كتب القراءة والقصص", "cout": "1500"}, b)
    assert bz.besoin(base, b)["besoin"] == "كتب القراءة والقصص"
    bz.supprimer(base, a)
    assert len(bz.besoins(base)) == 1


def test_document_avec_signatures(base, dossier):  # noqa: F811
    with pytest.raises(bz.ErreurBesoin, match="أضف الحاجيات"):
        bz.generer(base, dossier)
    bz.enregistrer(base, {"domaine": bz.DOMAINES[2], "besoin": "إصلاح المرافق الصحية", "cout": "8000",
                          "priorite": "عالية", "justification": "تقادم التجهيزات"})
    with pytest.raises(bz.ErreurBesoin, match="مجلس التدبير"):
        bz.generer(base, dossier)
    ce.enregistrer_membres(base, "gestion", [("مدير وهمي", "رئيس المجلس"), ("أستاذة وهمية", "ممثل القسم الأول")])
    d = Document(bz.generer(base, dossier, date_seance="2026-11-20"))
    texte = "\n".join(p.text for p in d.paragraphs)
    cel = " ".join(c.text for t in d.tables for r in t.rows for c in r.cells)
    assert "وثيقة تحديد حاجيات المؤسسة" in texte and "في إطار مشروع المؤسسة المندمج" in texte
    assert "20/11/2026" in texte and "توقيعات أعضاء مجلس التدبير" in texte
    assert "إصلاح المرافق الصحية" in cel and "8 000" in cel and "أستاذة وهمية" in cel and "التوقيع" in cel
