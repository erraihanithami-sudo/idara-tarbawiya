"""تدبير السكنيات حسب المذكرة 40 (10 ماي 2004): التنقيط، التباري، المطبوعات. بيانات وهمية."""

import pytest
from docx import Document

from idara.services import logements as lg
from idara.services import personnel as rh
from tests.test_eleves import base  # noqa: F401  (fixture)


def _texte(p):
    d = Document(p)
    return "\n".join(x.text for x in d.paragraphs) + "\n" + "\n".join(c.text for t in d.tables for r in t.rows
                                                                       for c in r.cells)


def test_bareme_de_la_note():
    r = lg.points({"echelle": "11", "anciennete_generale": 17, "anciennete_locale": 7, "situation": "marie",
                   "enfants": 4, "conjoint_sans_travail": True, "responsabilite": "chef_service",
                   "rendement": "tres_bien"})
    assert [x[2] for x in r["details"]] == [3, 4, 2, 3, 2, 2, 4] and r["total"] == 20
    assert lg.points({"echelle": "6", "anciennete_generale": 1, "anciennete_locale": 1})["total"] == 1 + 1
    assert lg.points({"echelle": "hors", "anciennete_generale": 21, "rendement": "assez_bien"})["total"] == 3 + 5 + 1
    rur = lg.points({"echelle": "9", "femme_non_mariee": True, "satellite": True}, rural=True)
    assert rur["total"] == 2 + 3 + 2 and len(rur["details"]) == 9
    assert lg.points({"situation": "celibataire", "conjoint_sans_travail": True})["total"] == 0


def test_concours_et_imprimes(base, dossier):  # noqa: F811
    with pytest.raises(lg.ErreurLogement, match="عنوان السكن"):
        lg.enregistrer_logement(base, lg.Logement(" "))
    lid = lg.enregistrer_logement(base, lg.Logement("سكن الوحدة المركزية، دوار وهمي", "123/45", nature="صلب"))
    with pytest.raises(lg.ErreurLogement, match="قبل تاريخ الإعلان"):
        lg.enregistrer_concours(base, lg.Concours(lid, "2026-11-20", "2026-11-01"))
    cid = lg.enregistrer_concours(base, lg.Concours(lid, "2026-11-20", "2026-12-20", "2026-12-28", rural=True))
    a = rh.enregistrer(base, rh.Personnel(nom_ar="الأول", prenom_ar="أستاذ", sexe="M", ppr="1111111", grade="الدرجة الثانية",
                                          date_recrutement="2005-09-16", cin="AB1"))
    b = rh.enregistrer(base, rh.Personnel(nom_ar="الثانية", prenom_ar="أستاذة", sexe="F", ppr="2222222",
                                          grade="الدرجة الأولى", date_recrutement="2015-09-16"))
    prop = lg.proposition(base, b, rural=True)
    assert prop["echelle"] == "11" and prop["femme_non_mariee"] and prop["anciennete_generale"] >= 11
    lg.enregistrer_candidat(base, cid, a, {**lg.proposition(base, a, True), "rendement": "bien"})
    lg.enregistrer_candidat(base, cid, b, prop)
    cs = lg.candidats(base, cid)
    assert [c.personnel_id for c in cs] == [b, a] or cs[0].points >= cs[1].points
    lg.attribuer(base, cid, cs[0].personnel_id)
    assert lg.concours(base, cid).statut == "attribue" and lg.occupant_actuel(base, lid)["personnel_id"] == cs[0].personnel_id
    assert lg.synthese(base)["occupes"] == 1
    for code, attendu in (("demande", "طلب المشاركة في التباري"), ("pv", "محضر أشغال لجنة إسناد"),
                          ("engagement_droit", "وجوباً"), ("engagement_fait", "المسكنين بالفعل"),
                          ("constat", "بطاقة معاينة السكن"), ("controle", "بطاقة مراقبة السكن")):
        t = _texte(lg.generer(base, dossier, code, cid))
        assert attendu in t, code
        assert "المطبوع رقم" in t
    t = _texte(lg.generer(base, dossier, "pv", cid))
    assert "أستاذ الأول" in t and "مفتش(ة) المقاطعة" in t
    t = _texte(lg.generer(base, dossier, "demande", cid, a))
    assert "أستاذ الأول" in t and "مجموع النقط" in t
    assert "123/45" in _texte(lg.generer(base, dossier, "controle", logement_id=lid))
    blanc = _texte(lg.generer(base, dossier, "demande"))
    assert "........" in blanc
    with pytest.raises(lg.ErreurLogement, match="غير مرفق"):
        lg.generer(base, dossier, "carte1")
    d = Document(lg.generer(base, dossier, "engagement_droit", cid))
    assert not any("w:br" in p._p.xml and 'w:type="page"' in p._p.xml for p in d.paragraphs)   # مطبوع واحد
