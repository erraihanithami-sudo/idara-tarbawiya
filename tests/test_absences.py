"""تتبع الغياب الشهري (بيانات وهمية)."""

import pytest
from docx import Document

from idara.services import absences as ab
from idara.services import etablissement as et
from tests.test_eleves import base  # noqa: F401


def test_mois_et_saisie(base, dossier):  # noqa: F811
    """قرار 2026-11-13: نسبة الحضور الشهرية لكل قسم يدوياً، والبرنامج يحسب نسبة المؤسسة."""
    mois = ab.mois_de_l_annee(base)
    assert mois[0] == ("2026-09", "شتنبر 2026") and mois[-1] == ("2027-06", "يونيو 2027") and len(mois) == 10
    ls = ab.lignes(base, "2026-10")
    assert ls and all(not x["saisi"] and x["taux"] is None for x in ls)
    c1 = ls[0]
    ab.enregistrer(base, "2026-10", [(c1["classe_id"], 20, "95,5")])
    s = ab.synthese_mois(base, "2026-10")
    assert s["classes"][0]["taux"] == 95.5 and s["etablissement"]["taux"] == 95.5 and s["jours_etude"] is None
    # تعديل نفس الشهر يعوّض ولا يكرر، وأيام الدراسة اختيارية
    ab.enregistrer(base, "2026-10", [(c1["classe_id"], 20, 90)], jours=22)
    assert ab.synthese_mois(base, "2026-10")["etablissement"]["taux"] == 90
    assert ab.jours_etude(base, "2026-10") == 22
    ab.enregistrer(base, "2026-11", [(c1["classe_id"], 20, "100%")])
    ev = ab.evolution(base)
    assert [e["mois"] for e in ev] == ["2026-10", "2026-11"] and ev[1]["etablissement"]["taux"] == 100
    assert ab.dernier_taux(base) == ("نونبر 2026", 100)
    # إفراغ نسبة قسم يحذفها
    ab.enregistrer(base, "2026-11", [(c1["classe_id"], 20, "100")] +
                   [(x["classe_id"], x["effectif"], "") for x in ls[1:]])
    f = ab.generer_rapport(base, dossier, "2026-10", None)
    texte = "\n".join(c.text for t in Document(f).tables for r in t.rows for c in r.cells)
    assert c1["classe"] in texte and "المؤسسة كاملة" in texte and "نسبة الحضور" in texte and "90%" in texte
    assert "تقرير الحضور الشهري: أكتوبر 2026" in "\n".join(p.text for p in Document(f).paragraphs)


def test_moyenne_ponderee(base):  # noqa: F811
    ls = ab.lignes(base, "2026-10")
    if len(ls) < 2:
        pytest.skip("قسم واحد في البيانات الوهمية")
    ab.enregistrer(base, "2026-10", [(ls[0]["classe_id"], 30, 90), (ls[1]["classe_id"], 10, 100)])
    assert ab.synthese_mois(base, "2026-10")["etablissement"]["taux"] == 92.5     # (90×30 + 100×10) ÷ 40


@pytest.mark.parametrize("taux, msg", [("101", "بين 0 و100"), ("abc", "بين 0 و100"), ("-1", "بين 0 و100")])
def test_validation(base, taux, msg):  # noqa: F811
    c = ab.lignes(base, "2026-10")[0]
    with pytest.raises(ab.ErreurAbsence, match=msg):
        ab.enregistrer(base, "2026-10", [(c["classe_id"], 20, taux)])
    with pytest.raises(ab.ErreurAbsence, match="عدد التلاميذ"):
        ab.enregistrer(base, "2026-10", [(c["classe_id"], 0, 90)])
    with pytest.raises(ab.ErreurAbsence, match="قسم واحد على الأقل"):
        ab.enregistrer(base, "2026-10", [(c["classe_id"], 20, "")])
    with pytest.raises(ab.ErreurAbsence, match="خارج"):
        ab.enregistrer(base, "2027-08", [])


def test_par_unite(base):  # noqa: F811
    et.definir_unites(base, ["الوحدة أ"])
    e = et.lire_etablissement(base)
    e.type_etab = "groupe"
    et.enregistrer_etablissement(base, e)
    uid = base.execute("SELECT id FROM unite_scolaire WHERE nom_ar='الوحدة أ'").fetchone()[0]
    ls = ab.lignes(base, "2026-10")
    base.execute("UPDATE classe SET unite_id=? WHERE id=?", (uid, ls[0]["classe_id"]))
    ab.enregistrer(base, "2026-10", [(x["classe_id"], x["effectif"], 95) for x in ls if x["effectif"]])
    s = ab.synthese_mois(base, "2026-10")
    assert s["unites"][0]["unite"] == "الوحدة أ"
