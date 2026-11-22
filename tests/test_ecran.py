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
    assert r["ordre"] == [c for c, *_ in ec.CATALOGUE]
    assert r["actives"] == [c for c in r["ordre"] if c not in ec.INACTIVES_DEFAUT]
    assert {"honneur", "etoile", "galerie"} <= ec.INACTIVES_DEFAUT   # الأسماء والصور باختيار المدير
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
    texte = json.dumps([ec.diapositive(base, k) for k, *_ in ec.CATALOGUE if k not in ec.INACTIVES_DEFAUT],
                       ensure_ascii=False)
    noms = [r[0] for r in base.execute("SELECT nom_ar FROM eleve WHERE nom_ar<>'' LIMIT 20")]
    codes = [r[0] for r in base.execute("SELECT code_massar FROM eleve WHERE code_massar<>'' LIMIT 20")]
    assert noms and not any(x in texte for x in noms + codes)
    cles = [d["cle"] for d in ec.diaporama(base)]
    assert cles[0] == "couverture" and "mouvements" not in cles
    assert len(ec.diaporama(base, avec_vides=True)) == len(ec.CATALOGUE) - len(ec.INACTIVES_DEFAUT)
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


# ---------- الدفعة الثالثة (2026-11-22) ----------

def test_nouvelles_diapos_actives_pour_anciens_reglages(base):  # noqa: F811
    from idara.services import fiches
    fiches.ecrire(base, ec.CLE, {"ordre": ["couverture", "niveaux"], "actives": ["niveaux"]})
    r = ec.reglages(base)
    assert "couverture" not in r["actives"] and "niveaux" in r["actives"]
    assert "pyramide" in r["actives"] and "honneur" not in r["actives"] and "etoile" not in r["actives"]


def test_indicateurs_et_annonces(base):  # noqa: F811
    with pytest.raises(ec.ErreurEcran, match="اكتب"):
        ec.ajouter_indicateur(base, "", "5")
    with pytest.raises(ec.ErreurEcran, match="طويل"):
        ec.ajouter_indicateur(base, "نسبة", "1" * 13)
    a = ec.ajouter_indicateur(base, " نسبة   التمدرس ", "98%", "الفئة 6-11 سنة")
    d = ec.diapositive(base, "indicateurs")
    assert d["items"][0]["libelle"] == "نسبة التمدرس" and d["items"][0]["valeur"] == "98%"
    for k in range(7):
        ec.ajouter_indicateur(base, f"م{k}", str(k))
    with pytest.raises(ec.ErreurEcran, match="الحد"):
        ec.ajouter_indicateur(base, "زائد", "1")
    ec.supprimer_indicateur(base, a["id"])
    assert len(ec.indicateurs_perso(base)) == 7
    ec.ajouter_annonce(base, "انطلاق الأنشطة الرياضية", "كل أربعاء", "2026-12-01")
    d = ec.diapositive(base, "annonces")
    assert d["items"][0]["texte"] == "كل أربعاء" and d["items"][0]["date"]


def test_etoile_consentement(base, tmp_path):  # noqa: F811
    from PIL import Image
    from idara.data.dossier import DossierDonnees
    dossier = DossierDonnees(tmp_path / "د").preparer()
    src = tmp_path / "e.jpg"
    Image.new("RGB", (60, 80), "gold").save(src)
    assert ec.diapositive(base, "etoile", dossier=dossier)["vide"]
    with pytest.raises(ec.ErreurEcran, match="موافقة"):
        ec.definir_etoile(base, dossier, "تلميذة وهمية", "4-1", "التفوق", src, consentement=False)
    ec.definir_etoile(base, dossier, "تلميذة وهمية", "4-1", "التفوق في القراءة", src, consentement=True)
    it = ec.diapositive(base, "etoile", dossier=dossier)["items"][0]
    assert it["libelle"] == "تلميذة وهمية" and it["photo"].endswith(".jpg") and it["motif"] == "التفوق في القراءة"
    ec.definir_etoile(base, dossier, "تلميذة وهمية", "4-1", "", None, consentement=False)
    assert ec.diapositive(base, "etoile", dossier=dossier)["items"][0]["photo"] == ""   # سُحبت الموافقة
    ec.retirer_etoile(base)
    assert ec.diapositive(base, "etoile")["vide"]


def test_niveaux_ages_et_pyramide(base):  # noqa: F811
    base.execute("UPDATE eleve SET date_naissance='2018-03-04'")
    base.commit()
    cn = ec.diapositive(base, "cartes_niveaux")
    assert cn["items"] and all({"classes", "pct_garcons", "pct_filles"} <= set(i) for i in cn["items"])
    py = ec.diapositive(base, "pyramide")
    assert [i["id"] for i in py["items"]] == ["8"] and sum(py["items"][0]["valeurs"]) == sum(
        i["eleves"] for i in cn["items"])
    ag = ec.diapositive(base, "ages")
    assert ag["ages"] == [8] and all(set(i["par_age"]) == {"8"} for i in ag["items"])


def test_mouvements_en_pourcentage(base):  # noqa: F811
    d = ec.diapositive(base, "mouvements")
    assert d["effectif"] > 0 and all("taux" in i for i in d["items"])


def test_isa_acquis_examens_honneur(base):  # noqa: F811
    from idara.services import isa
    isa.enregistrer(base, "2026/2027", "1APG-1", "ar", -1, 2, 3, 5)
    isa.enregistrer(base, "2026/2027", "1APG-1", "ar", 1, 4, 4, 2)
    isa.enregistrer(base, "2026/2027", "1APG-1", "ar", 2, 6, 3, 1)
    a = ec.diapositive(base, "acquis")
    assert a["phase"] == "المرحلة 2" and a["items"][0]["valeurs"] == [60.0, 30.0, 10.0]
    i = ec.diapositive(base, "isa")
    assert i["phases"] == ["المرحلة 1", "المرحلة 2"] and len(i["items"][0]["valeurs"]) == 2
    assert i["items"][0]["valeurs"][1] > i["items"][0]["valeurs"][0]
    aid = base.execute("SELECT id FROM annee_scolaire WHERE libelle='2026/2027'").fetchone()[0]
    for k, (m, nom) in enumerate(((8.5, "أ"), (4.0, "ب"), (9.1, "ج"), (7.0, "د"))):
        base.execute("INSERT INTO resultat(annee_id, code_massar, nom, classe, niveau, moyennes, moyenne) "
                     "VALUES (?,?,?,?,?,?,?)", (aid, f"Z{k}", f"تلميذ {nom}", "3APG-1", "3AP", "{}", m))
    base.commit()
    e = ec.diapositive(base, "examens")["items"][0]
    assert e["valeurs"] == [75.0] and e["moyenne"] == 7.15
    h = ec.diapositive(base, "honneur")["items"][0]
    assert [x["nom"] for x in h["podium"]] == ["تلميذ ج", "تلميذ أ", "تلميذ د"]
    assert "9.1" not in json.dumps(h, ensure_ascii=False)   # الترتيب دون النقط


def test_ou_sont_les_professeurs(base):  # noqa: F811
    from datetime import datetime
    from idara.services import personnel as rh
    from idara.services import vie_admin as va
    pid = rh.enregistrer(base, rh.Personnel(nom_ar="الوهمي", prenom_ar="أستاذ", sexe="M", categorie="enseignant",
                                            ppr="900077"))
    va.enregistrer_emploi(base, pid, [["الاثنين", "08:30", "10:30", "الرياضيات", "4APG-1", "ق3"],
                                      ["الاثنين", "14:30", "16:30", "العربية", "4APG-1", "ق5"]])
    lundi = datetime(2026, 11, 23, 9, 0)
    s = ec.diapositive(base, "salles", lundi)
    assert s["items"][0]["salle"] == "ق3" and s["items"][0]["etat"] == "en_cours" and s["heure"] == "09:00"
    assert "الآن في القاعة ق3" in ec.ou_est(base, "الوهمي", lundi)
    assert "حصته القادمة 14:30 في القاعة ق5" in ec.ou_est(base, "الوهمي", datetime(2026, 11, 23, 12, 0))
    assert "أنهى" in ec.ou_est(base, "الوهمي", datetime(2026, 11, 23, 18, 0))
    assert "لا حصص" in ec.ou_est(base, "الوهمي", datetime(2026, 11, 24, 9, 0))
    assert "لا أستاذ" in ec.ou_est(base, "غيرموجود", lundi)


def test_equipements_galerie_et_ministere(base, tmp_path):  # noqa: F811
    from PIL import Image
    from idara.data.dossier import DossierDonnees
    from idara.services import photos as ph
    from idara.services import structure as su
    from idara.services import vie_scolaire as vs
    dossier = DossierDonnees(tmp_path / "د").preparer()
    src = tmp_path / "p.jpg"
    Image.new("RGB", (80, 60), "green").save(src)
    su.enregistrer(base, [{"element": "salles", "nombres": {None: 6}}, {"element": "terrains", "nombres": {None: 1}}])
    ph.ajouter(base, dossier, "structure", "terrains", src)
    eq = ec.diapositive(base, "equipements", dossier=dossier)["items"]
    assert {i["id"]: i["valeur"] for i in eq} == {"salles": 6, "terrains": 1}
    assert [i for i in eq if i["id"] == "terrains"][0]["photo"].endswith(".jpg")
    aid = vs.enregistrer_activite(base, vs.Activite("مسابقة", "مسابقة الرسم", periode="نونبر"))
    ph.ajouter(base, dossier, "activite", aid, src)
    g = ec.diapositive(base, "galerie", dossier=dossier)
    assert g["items"][0]["libelle"] == "مسابقة الرسم" and len(g["items"][0]["photos"]) == 1
    assert ec.identite(base, dossier)["ministere"].endswith("ministere.png")
    ec.definir_logo_ministere(base, dossier, masquer=True)
    assert ec.identite(base, dossier)["ministere"] == ""
    ec.definir_logo_ministere(base, dossier, src)
    assert ec.identite(base, dossier)["ministere"].endswith("logo_ministere.jpg")
    ec.definir_logo_ministere(base, dossier)
    assert ec.identite(base, dossier)["ministere"].endswith("ministere.png")
