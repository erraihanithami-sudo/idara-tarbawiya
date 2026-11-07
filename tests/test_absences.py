"""تتبع الغياب الشهري (بيانات وهمية)."""

import pytest
from docx import Document

from idara.services import absences as ab
from idara.services import etablissement as et
from tests.test_eleves import base  # noqa: F401


def test_mois_et_saisie(base, dossier):  # noqa: F811
    mois = ab.mois_de_l_annee(base)
    assert mois[0] == ("2026-09", "شتنبر 2026") and mois[-1] == ("2027-06", "يونيو 2027") and len(mois) == 10
    ls = ab.lignes(base, "2026-10")
    assert ls and all(not x["saisi"] and x["taux"] is None for x in ls)
    c1 = ls[0]
    eff = c1["effectif"]
    ab.enregistrer(base, "2026-10", 20, [(c1["classe_id"], eff, 10.5, 3)])
    s = ab.synthese_mois(base, "2026-10")
    assert s["classes"][0]["taux"] == round(10.5 * 100 / (eff * 20), 2)
    assert s["etablissement"]["jours_absence"] == 10.5 and s["etablissement"]["absents"] == 3
    # تعديل نفس الشهر يعوّض ولا يكرر
    ab.enregistrer(base, "2026-10", 22, [(c1["classe_id"], eff, 4, 2)])
    assert ab.synthese_mois(base, "2026-10")["etablissement"]["jours_absence"] == 4
    assert ab.jours_etude(base, "2026-10") == 22
    ab.enregistrer(base, "2026-11", 18, [(c1["classe_id"], eff, 0, 0)])
    ev = ab.evolution(base)
    assert [e["mois"] for e in ev] == ["2026-10", "2026-11"] and ev[1]["etablissement"]["taux"] == 0
    assert ab.dernier_taux(base) == ("نونبر 2026", 0)
    f = ab.generer_rapport(base, dossier, "2026-10", None)
    texte = "\n".join(c.text for t in Document(f).tables for r in t.rows for c in r.cells)
    assert c1["classe"] in texte and "المؤسسة كاملة" in texte
    assert "تقرير الغياب الشهري: أكتوبر 2026" in "\n".join(p.text for p in Document(f).paragraphs)


@pytest.mark.parametrize("args, msg", [
    ((0, 5, 1), "بين 1 و31"), ((20, 2.3, 1), "بنصف يوم"), ((20, 5, 0), "دون عدد المتغيبين"),
    ((20, 99999, 1), "تتجاوز"), ((20, 1, 9999), "يتجاوز عدد التلاميذ")])
def test_validation(base, args, msg):  # noqa: F811
    c = ab.lignes(base, "2026-10")[0]
    j, ja, a = args
    with pytest.raises(ab.ErreurAbsence, match=msg):
        ab.enregistrer(base, "2026-10", j, [(c["classe_id"], c["effectif"], ja, a)])
    with pytest.raises(ab.ErreurAbsence, match="خارج"):
        ab.enregistrer(base, "2027-08", 10, [])


def test_par_unite(base):  # noqa: F811
    et.definir_unites(base, ["الوحدة أ"])
    e = et.lire_etablissement(base)
    e.type_etab = "groupe"
    et.enregistrer_etablissement(base, e)
    uid = base.execute("SELECT id FROM unite_scolaire WHERE nom_ar='الوحدة أ'").fetchone()[0]
    ls = ab.lignes(base, "2026-10")
    base.execute("UPDATE classe SET unite_id=? WHERE id=?", (uid, ls[0]["classe_id"]))
    ab.enregistrer(base, "2026-10", 20, [(x["classe_id"], x["effectif"], 1, 1) for x in ls if x["effectif"]])
    s = ab.synthese_mois(base, "2026-10")
    assert s["unites"][0]["unite"] == "الوحدة أ"
