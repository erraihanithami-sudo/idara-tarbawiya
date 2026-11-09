"""محاضر الموارد البشرية: الالتحاق بالعمل، الدخول والخروج (بيانات وهمية)."""

import pytest
from docx import Document

from idara.services import personnel as rh
from idara.services import pv_rh as pv
from tests.test_conges import _prof, base  # noqa: F401


def _textes(f):
    d = Document(f)
    return "\n".join([p.text for p in d.paragraphs] + [c.text for t in d.tables for r in t.rows for c in r.cells])


def test_prise_de_service(base, dossier):  # noqa: F811
    pid = _prof(base, sexe="F", prenom_ar="سلمى")
    with pytest.raises(pv.ErreurPV, match="حالة الالتحاق"):
        pv.enregistrer_prise(base, pv.PriseService(pid, "2026-09-01", 0))
    with pytest.raises(pv.ErreurPV, match="تاريخ"):
        pv.enregistrer_prise(base, pv.PriseService(pid, "2026-13-01", 6))
    vid = pv.enregistrer_prise(base, pv.PriseService(pid, "2026-09-01", 6, reference="رقم 123 بتاريخ 15/07/2026",
                                                     ancien_lieu="مدرسة سابقة", lieu_naissance="المدينة"))
    v = pv.valeurs_prise(base, vid)
    assert v["sayyid"] == "السيدة" and v["hadara"] == "حضرت" and v["cas_6"] == "☑" and v["cas_1"] == "☐"
    assert v["ana_mouwaqqi"] == "أنا الموقعة أسفله" and v["al_mouani"] == "المعنية"
    t = _textes(pv.generer_prise(base, dossier, vid).chemin)
    assert "محضر الالتحاق بالعمل" in t and "سلمى" in t and "رقم 123" in t and "مدرسة سابقة" in t
    assert "☑" in t and "{{" not in t
    assert [r["id"] for r in pv.lister_prises(base)] == [vid]
    # موظف له محضر لا يُحذف
    with pytest.raises(rh.ErreurPersonnel, match="محاضر التحاق"):
        rh.supprimer(base, pid)


def test_entree_sortie(base, dossier):  # noqa: F811
    ids = [_prof(base, prenom_ar=f"أستاذ{i}", ppr=f"70000{i:02d}", cin=f"AB{i:03d}") for i in range(15)]
    with base:
        base.execute("INSERT INTO personnel(nom_ar, prenom_ar, sexe, categorie) VALUES ('الحارس','علي','M','gardien')")
    assert len(pv.personnels(base, "enseignants")) == 15 and len(pv.personnels(base, "administratifs")) == 1
    with pytest.raises(pv.ErreurPV, match="السبب|سبب"):
        pv.enregistrer_collectif(base, "entree", "enseignants", "2026-09-01", [(ids[0], " ")])
    vid = pv.enregistrer_collectif(base, "entree", "enseignants", "2026-09-01", [])
    doc, non = pv.generer_collectif(base, dossier, vid)
    t = _textes(doc.chemin)
    assert "محضر الدخول يهم: هيأة التدريس" in t and "أستاذ14" in t and "02/02" in t and "{{" not in t
    tn = _textes(non.chemin)
    assert "لا أحد" in tn and "لم يوقعوا محضر الدخول" in tn
    vid = pv.enregistrer_collectif(base, "sortie", "enseignants", "2026-06-30", [(ids[2], "في رخصة مرضية")])
    _, non = pv.generer_collectif(base, dossier, vid)
    tn = _textes(non.chemin)
    assert "في رخصة مرضية" in tn and "أستاذ2" in tn and "لا أحد" not in tn
    assert len(pv.lister_collectifs(base)) == 2
