"""شاشة العرض (طلب المدير 2026-11-21): شرائح من معطيات البرنامج، أرقام مجمَّعة فقط، ونقاط يختارها المدير
(بيانات وهمية)."""

import json

import pytest

from idara.services import ecran as ec
from tests.test_eleves import base  # noqa: F401


def test_catalogue_sans_actualites():
    cles = [c for c, *_ in ec.CATALOGUE]
    assert "actualites" not in cles
    assert {"maitrise", "projet", "realisations", "partenariats"} <= set(cles) and cles[0] == "couverture"


def test_reglages_par_defaut_et_enregistrement(base):  # noqa: F811
    r = ec.reglages(base)
    assert r["ordre"] == [c for c, *_ in ec.CATALOGUE] and r["actives"] == r["ordre"]
    assert all(v == ec.DUREE_DEFAUT for v in r["durees"].values()) and r["bandeau"] == "" and r["masques"] == {}
    with pytest.raises(ec.ErreurEcran, match="واحدة على الأقل"):
        ec.enregistrer_reglages(base, r["ordre"], [], {})
    r = ec.enregistrer_reglages(base, ["niveaux", "couverture", "inconnue"], ["couverture", "inconnue"],
                                {"couverture": 1, "niveaux": 999}, "  مرحباً   بكم  ")
    assert r["ordre"][:2] == ["niveaux", "couverture"] and len(r["ordre"]) == len(ec.CATALOGUE)
    assert r["actives"] == ["couverture"] and r["durees"]["couverture"] == 3 and r["durees"]["niveaux"] == 300
    assert r["bandeau"] == "مرحباً بكم"


def test_points_choisis_par_le_directeur(base):  # noqa: F811
    pts = ec.points(base, "couverture")
    assert [p["id"] for p in pts] == ["eleves", "garcons", "filles", "classes", "personnel"]
    assert all(p["affiche"] for p in pts)
    ec.definir_masques(base, "couverture", ["garcons", "filles"])
    d = ec.diapositive(base, "couverture")
    assert [i["id"] for i in d["items"]] == ["eleves", "classes", "personnel"]
    assert [p["affiche"] for p in ec.points(base, "couverture")] == [True, False, False, True, True]
    niv = ec.points(base, "niveaux")
    ec.definir_masques(base, "niveaux", [p["id"] for p in niv])
    assert ec.diapositive(base, "niveaux")["vide"] and "niveaux" not in [d["cle"] for d in ec.diaporama(base)]
    with pytest.raises(ec.ErreurEcran):
        ec.definir_masques(base, "inconnue", [])


def test_realisations_par_axe(base):  # noqa: F811
    assert ec.diapositive(base, "realisations")["vide"]
    with pytest.raises(ec.ErreurEcran, match="المحور"):
        ec.ajouter_realisation(base, "autre", "منجز")
    with pytest.raises(ec.ErreurEcran, match="اكتب"):
        ec.ajouter_realisation(base, "eleve", "  ")
    with pytest.raises(ec.ErreurEcran, match="طويل"):
        ec.ajouter_realisation(base, "eleve", "ك" * 141)
    a = ec.ajouter_realisation(base, "eleve", "  تتويج   فريق القراءة إقليمياً ")
    b = ec.ajouter_realisation(base, "ecole", "تجهيز قاعة متعددة الوسائط")
    ec.ajouter_realisation(base, "professeur", "تكوين الأساتذة في التدريس الصريح")
    d = ec.diapositive(base, "realisations")
    assert [i["axe"] for i in d["items"]] == ["eleve", "ecole", "professeur"]
    assert d["items"][0]["libelle"] == "تتويج فريق القراءة إقليمياً" and "(محور التلميذ)" in ec.points(
        base, "realisations")[0]["libelle"]
    ec.definir_masques(base, "realisations", [str(b["id"])])
    assert len(ec.diapositive(base, "realisations")["items"]) == 2
    ec.supprimer_realisation(base, a["id"])
    assert [l["texte"] for l in ec.realisations(base)][0] == "تجهيز قاعة متعددة الوسائط"


def test_projet_partenariats_et_maitrise(base):  # noqa: F811
    from idara.services import projet_etab as pe
    from idara.services import registres as rg
    assert ec.diapositive(base, "projet")["vide"] and ec.diapositive(base, "partenariats")["vide"]
    pid = pe.enregistrer_projet(base, "مدرستي فضاء للتعلم", "2025/2026", "2027/2028")
    pe.activer(base, pid)
    o1 = pe.ajouter_operation(base, pid, "تأهيل المكتبة المدرسية", "محور المدرسة")
    pe.ajouter_operation(base, pid, "دعم القراءة", "محور التلميذ")
    pe.suivre(base, o1, "realisee")
    d = ec.diapositive(base, "projet")
    assert [i["libelle"] for i in d["items"]] == ["تأهيل المكتبة المدرسية"] and d["realisees"] == 1
    assert d["actives"] == 2 and d["pct_realisees"] == 50.0 and d["intitule"] == "مدرستي فضاء للتعلم"
    rg.enregistrer(base, "partenariats", {"partenaire": "جمعية الآباء", "objet": "صيانة الحجرات", "etat": "سارية"})
    rg.enregistrer(base, "partenariats", {"partenaire": "الجماعة", "objet": "النقل", "etat": "قيد الإعداد"})
    p = ec.diapositive(base, "partenariats")
    assert [i["libelle"] for i in p["items"]] == ["جمعية الآباء"]
    assert ec.diapositive(base, "maitrise")["vide"]


def test_sans_donnees_personnelles(base):  # noqa: F811
    texte = json.dumps([ec.diapositive(base, k) for k, *_ in ec.CATALOGUE], ensure_ascii=False)
    noms = [r[0] for r in base.execute("SELECT nom_ar FROM eleve WHERE nom_ar<>'' LIMIT 20")]
    codes = [r[0] for r in base.execute("SELECT code_massar FROM eleve WHERE code_massar<>'' LIMIT 20")]
    assert noms and not any(x in texte for x in noms + codes)
    cles = [d["cle"] for d in ec.diaporama(base)]
    assert cles[0] == "couverture" and "mouvements" not in cles
    assert len(ec.diaporama(base, avec_vides=True)) == len(ec.CATALOGUE)
    assert "الموسم الدراسي" in ec.bandeau_defaut(base)


def test_logo(base, tmp_path):  # noqa: F811
    from PIL import Image
    from idara.data.dossier import DossierDonnees
    dossier = DossierDonnees(tmp_path / "د").preparer()
    src = tmp_path / "logo.png"
    Image.new("RGB", (40, 30), "navy").save(src)
    rel = ec.definir_logo(base, dossier, src)
    assert rel.endswith("logo_ecran.png") and ec.chemin_logo(base, dossier).endswith("logo_ecran.png")
    assert ec.identite(base, dossier)["logo"]
    with pytest.raises(ec.ErreurEcran):
        ec.definir_logo(base, dossier, tmp_path / "x.gif")
    assert ec.definir_logo(base, dossier, None) == "" and ec.identite(base, dossier)["logo"] == ""
