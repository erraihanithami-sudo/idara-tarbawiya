"""السبورة المرجعية (نماذج المدير 2026-11-13). بيانات وهمية."""

import pytest
from docx import Document

from idara.services import personnel as rh
from idara.services import sabboura as sb
from idara.services import structure as st
from tests.test_eleves import AR, base, classeur  # noqa: F401


def _textes(chemin):
    d = Document(chemin)
    return d, [c.text for t in d.tables for r in t.rows for c in r.cells]


def test_lavhat_et_donnees_auto(base):  # noqa: F811
    assert len(sb.LAVHAT) == 11 and [l.titre for l in sb.LAVHAT][0] == "بطاقة معلومات المؤسسة"
    rh.enregistrer(base, rh.Personnel(nom_ar="التجريبية", prenom_ar="أستاذة", sexe="F", categorie="enseignant",
                                      ppr="900001"))
    f = sb.lire(base, "fiche")["champs"]
    assert f["nom"] and f["cycle"] == "ابتدائي" and f["prof_f"] == "01" and f["prof_m"] == "00"
    assert int(f["eleves_m"]) + int(f["eleves_f"]) == int(f["eleves_primaire"]) + int(f["eleves_prescolaire"])
    assert sb.lire(base, "emploi")["lignes"][0][:2] == ["أستاذة التجريبية", "900001"]
    assert [l[1] for l in sb.lire(base, "conseil_ped")["lignes"]][:2] == ["رئيس المجلس", "ممثل القسم الأول"]
    assert sb.lire(base, "cellules")["lignes"][0][0] == "خلية اليقظة"
    assert sb.lire(base, "structure_ped")["lignes"]
    assert sb.lire(base, "structure_mat")["lignes"] == []
    st.enregistrer(base, [{"element": "salles", "libelle": "", "nombres": {u: "6" for u, _ in st.unites(base)}}])
    assert sb.lire(base, "structure_mat")["lignes"] == [["عدد حجرات التعليم العام", "06"]]
    with pytest.raises(sb.ErreurSabboura, match="غير معروفة"):
        sb.lire(base, "x")


def test_saisie_actualisation_generation(base, dossier):  # noqa: F811
    d = sb.lire(base, "fiche")
    d["champs"]["gipe"] = "GIPE-TEST"
    d["champs"]["nom"] = "اسم معدل"
    sb.enregistrer(base, "fiche", d)
    a = sb.actualiser(base, "fiche")["champs"]
    assert a["gipe"] == "GIPE-TEST" and a["nom"] != "اسم معدل"       # اليدوي يبقى، والآلي يتجدد
    sb.enregistrer(base, "cellules", {"lignes": [["خلية اليقظة", "ذ. الأول، ذة. الثانية"], ["خلية الإنصات", ""]]})
    sb.enregistrer(base, "clubs", {"lignes": [["النادي البيئي", "ذة. التجريبية"]], "note": "ذة. المنسقة"})
    doc, cellules = _textes(sb.generer(base, dossier))
    for x in ("اسم المؤسسة", "رمز GIPE", "GIPE-TEST", "البنية التربوية", "التنظيم التربوي", "عدد التلاميذ",
              "النادي البيئي", "منسق(ة) التعاونية المدرسية", "ذة. المنسقة", "خلية اليقظة", "رئيس المجلس",
              "استعمال الزمن الجماعي", "حصص التربية البدنية", "صباحاً"):
        assert x in cellules or any(x in c for c in cellules), x
    assert len(doc.sections) == 11 and doc.sections[-1].page_width > doc.sections[-1].page_height
    assert doc.sections[0].page_height > doc.sections[0].page_width
    doc, cellules = _textes(sb.generer(base, dossier, ["cellules"], {"cellules": None}))
    assert len(doc.sections) == 1 and "ذة. الثانية" in "\n".join(cellules)
    assert sb.reinitialiser(base, "fiche")["champs"].get("gipe", "") == ""
