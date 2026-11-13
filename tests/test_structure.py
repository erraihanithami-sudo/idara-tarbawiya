"""البنية المادية (طلب المدير 2026-11-13). بيانات وهمية."""

import pytest
from docx import Document

from idara.services import passation as ps
from idara.services import structure as st
from tests.test_eleves import AR, base, classeur  # noqa: F401
from tests.test_vidage import _deux_unites


def test_saisie_par_unite_et_document(base, dossier):  # noqa: F811
    _deux_unites(base)
    t = st.tableau(base)
    (u1, n1), (u2, n2) = t["unites"]
    assert [l["libelle"] for l in t["lignes"]][:2] == ["الحجرات الدراسية", "المباني الإدارية"]
    with pytest.raises(st.ErreurStructure, match="لم يُدخل"):
        st.generer(base, dossier)
    lignes = [{"element": "salles", "libelle": "الحجرات الدراسية", "nombres": {u1: "6", u2: 3}, "remarques": ""},
              {"element": "sanitaires_handicap", "libelle": "مراحيض الأشخاص في وضعية إعاقة",
               "nombres": {u1: "1", u2: ""}, "remarques": "قيد الإنجاز بالفرعية"},
              {"element": "autre:", "libelle": "مستودع", "nombres": {u1: "1"}, "remarques": ""}]
    st.enregistrer(base, lignes)
    t = {l["element"]: l for l in st.tableau(base)["lignes"]}
    assert t["salles"]["total"] == 9 and t["sanitaires_handicap"]["total"] == 1
    assert t["autre:مستودع"]["libelle"] == "مستودع" and t["terrains"]["total"] is None
    with pytest.raises(st.ErreurStructure, match="عدد صحيح"):
        st.enregistrer(base, [{"element": "salles", "libelle": "الحجرات الدراسية", "nombres": {u1: "ستة"}}])
    with pytest.raises(st.ErreurStructure, match="سالباً"):
        st.enregistrer(base, [{"element": "salles", "libelle": "الحجرات الدراسية", "nombres": {u1: "-1"}}])
    # إعادة الحفظ تعوّض، والخانة الفارغة تُحذف
    st.enregistrer(base, [{"element": "salles", "libelle": "الحجرات الدراسية", "nombres": {u1: "7", u2: ""}}])
    assert {l["element"]: l for l in st.tableau(base)["lignes"]}["salles"]["total"] == 7
    d = Document(st.generer(base, dossier))
    cellules = [c.text for tb in d.tables for r in tb.rows for c in r.cells]
    for x in ("المكوّن", n1, n2, "المجموع", "الحجرات الدراسية", "07", "مستودع", "قيد الإنجاز بالفرعية"):
        assert x in cellules, x
    assert "الملاعب" not in cellules          # المكونات دون عدد لا تُطبع
    # محضر تسليم المهام: محور البنايات من البنية المادية
    b = ps.lire(base, "batiments")["lignes"]
    assert [n1, "الحجرات الدراسية", "07", "", "", ""] in b
    with pytest.raises(st.ErreurStructure, match="أضفتموه"):
        st.supprimer_element(base, "salles")
    st.supprimer_element(base, "autre:مستودع")
    assert "autre:مستودع" not in [k for k, _ in st.elements(base)]
