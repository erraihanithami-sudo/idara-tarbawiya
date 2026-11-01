"""قراءة لوائح مسار واستيرادها. كل اللوائح هنا وهمية بنفس بنية تصدير مسار."""

import json

import pytest

from idara.services import etablissement as et
from idara.services import import_eleves as imp
from idara.services import massar as ms
from tests.fabrique_massar import classeur

AR = {
    "PS1-PS2": [("X000000001", "التجريبي", "سعيد", "M", "2022-02-12", "المدينة"),
                ("X000000002", "الوهمي", "سلمى", "F", "2021-03-31", "القرية")],
    "4APG-5APG-6APG": [("X000000003", "المثال", "يوسف", "M", "2015-04-30", "المدينة"),
                       ("X000000004", "النموذج", "مريم", "F", "2016-06-25", None),
                       ("X000000005", "الاختبار", "آدم", "M", "2010-07-15", "المدينة")],
}
FR = {
    "PS1-PS2": [("X000000001", "TAJRIBI", "Said", "M", "2022-02-12", "VILLE"),
                ("X000000002", "WAHMI", "SALMA", "F", "2021-03-31", "القرية")],
    "4APG-5APG-6APG": [("X000000003", "MITHAL", "YOUSSEF", "M", "2015-04-30", "VILLE"),
                       ("X000000004", "NAMOUDAJ", "MERYEM", "F", "2016-06-25", None),
                       ("X000000005", "IKHTIBAR", "ADAM", "M", "2010-07-15", "VILLE")],
}


@pytest.fixture
def fichiers(tmp_path):
    return (classeur(tmp_path / "ListEleve.xlsx", AR, "ar"),
            classeur(tmp_path / "ListEleveFR.xlsx", FR, "fr"))


@pytest.fixture
def pret(dossier, conn):
    et.appliquer_configuration_initiale(conn, dossier, et.ConfigurationInitiale(
        etablissement=et.Etablissement(nom_ar="مدرسة تجريبية", direction_ar="م", academie_ar="أ"),
        directeur=et.Directeur(nom_ar="المدير", prenom_ar="أحمد", sexe="M"), annee="2026/2027"))
    return conn


# ---------- القراءة ----------

def test_lecture_arabe(fichiers):
    f = ms.lire_fichier(fichiers[0])
    assert f.langue == "ar" and [x.classe for x in f.feuilles] == ["PS1-PS2", "4APG-5APG-6APG"]
    assert f.feuilles[0].entete["annee"] == "2026/2027"
    assert f.feuilles[0].entete["etablissement"] == "مدرسة تجريبية"
    l = f.feuilles[0].lignes[1]
    assert (l.code, l.nom, l.prenom, l.sexe, l.date_naissance) == (
        "X000000002", "الوهمي", "سلمى", "F", "2021-03-31")


def test_lecture_francaise_et_entete_decale(tmp_path):
    f = ms.lire_fichier(classeur(tmp_path / "fr.xlsx", FR, "fr", decalage=3))
    assert f.langue == "fr"
    assert f.feuilles[1].lignes[0].date_naissance == "2015-04-30"


def test_lignes_invalides_signalees(tmp_path):
    data = {"1APG": [("X000000001", "أ", "ب", "M", "2019-01-01", "م"),
                     ("12345", "خطأ", "رمز", "M", "2019-01-01", "م"),
                     ("X000000002", "ت", "ث", "؟", "31/02/2019", "م")]}
    f = ms.lire_fichier(classeur(tmp_path / "x.xlsx", data))
    assert len(f.feuilles[0].lignes) == 2
    assert any("12345" in a for a in f.alertes)
    assert any("النوع غير محدد" in a for a in f.alertes)
    assert any("تاريخ ازدياد غير مفهوم" in a for a in f.alertes)


def test_fichier_qui_n_est_pas_massar(tmp_path):
    from openpyxl import Workbook
    wb = Workbook()
    wb.active["A1"] = "شيء آخر"
    wb.save(tmp_path / "autre.xlsx")
    with pytest.raises(ms.ErreurMassar):
        ms.lire_fichier(tmp_path / "autre.xlsx")
    (tmp_path / "faux.xlsx").write_bytes(b"pas excel")
    with pytest.raises(ms.ErreurMassar):
        ms.lire_fichier(tmp_path / "faux.xlsx")


def test_fusion(fichiers):
    l = ms.fusionner([ms.lire_fichier(fichiers[1]), ms.lire_fichier(fichiers[0])])
    e = l.eleves["X000000001"]
    assert (e.nom_ar, e.prenom_ar, e.nom_fr, e.prenom_fr, e.lieu_fr) == ("التجريبي", "سعيد", "TAJRIBI", "SAID", "VILLE")
    assert l.eleves["X000000002"].lieu_fr == ""  # مكان بالعربية في اللائحة الفرنسية: لا يُعتمد
    assert l.annee == "2026/2027" and l.alertes == []


def test_fusion_incoherences(tmp_path):
    fr = {k: list(v) for k, v in FR.items()}
    fr["PS1-PS2"][0] = ("X000000001", "TAJRIBI", "SAID", "F", "2022-02-13", "VILLE")
    fr["PS1-PS2"].append(("X000000099", "SEUL", "FR", "M", "2022-01-01", "VILLE"))
    l = ms.fusionner([ms.lire_fichier(classeur(tmp_path / "a.xlsx", AR)),
                      ms.lire_fichier(classeur(tmp_path / "f.xlsx", fr, "fr"))])
    texte = "\n".join(l.alertes)
    assert "النوع مختلف" in texte and "تاريخ الازدياد مختلف" in texte
    assert "X000000099: موجود في اللائحة الفرنسية دون العربية" in texte
    assert l.eleves["X000000001"].sexe == "M"


def test_fusion_refus(tmp_path, fichiers):
    with pytest.raises(ms.ErreurMassar, match="بنفس اللغة"):
        ms.fusionner([ms.lire_fichier(fichiers[0]), ms.lire_fichier(fichiers[0])])
    autre = classeur(tmp_path / "f2.xlsx", FR, "fr", annee="2025/2026")
    with pytest.raises(ms.ErreurMassar, match="سنوات دراسية مختلفة"):
        ms.fusionner([ms.lire_fichier(fichiers[0]), ms.lire_fichier(autre)])


@pytest.mark.parametrize("code, attendu", [
    ("1APG-2APG-3APG", ["1AP", "2AP", "3AP"]), ("PS1-PS2", ["PS1", "PS2"]),
    ("5APG", ["5AP"]), ("6APG-2", ["6AP"]), ("INCONNU", [])])
def test_niveaux_du_code_classe(code, attendu):
    assert ms.niveaux_du_code_classe(code) == attendu


def test_proposition_par_age():
    # السن المعتاد: 6 سنوات في الأول ابتدائي (المولود سنة 2020 في 2026/2027)
    assert ms.proposer_niveau("1APG-2APG-3APG", "2020-03-01", 2026) == ("1AP", True)
    assert ms.proposer_niveau("4APG-5APG-6APG", "2017-02-01", 2026) == ("4AP", True)
    assert ms.proposer_niveau("4APG-5APG-6APG", "2016-06-25", 2026) == ("5AP", True)
    assert ms.proposer_niveau("4APG-5APG-6APG", "2015-01-01", 2026) == ("6AP", True)
    assert ms.proposer_niveau("4APG-5APG-6APG", "2010-07-15", 2026) == ("6AP", False)
    assert ms.proposer_niveau("5APG", None, 2026) == ("5AP", True)
    assert ms.proposer_niveau("1APG-2APG", None, 2026) == (None, False)


# ---------- الاستيراد ----------

def test_premier_import(pret, dossier, fichiers):
    r = imp.analyser(pret, fichiers)
    assert len(r.nouveaux) == 5 and not r.mis_a_jour and not r.absents and not r.nouvelle_annee
    assert any("X000000004" in a and "مكان الازدياد فارغ" in a for a in r.alertes)
    res = imp.appliquer(pret, dossier, r)
    assert res.ajoutes == 5 and res.sauvegarde.exists()
    assert pret.execute("SELECT COUNT(*) FROM eleve").fetchone()[0] == 5
    assert pret.execute("SELECT COUNT(*) FROM classe").fetchone()[0] == 2
    assert pret.execute("SELECT COUNT(*) FROM inscription").fetchone()[0] == 5
    # أماكن الازدياد موحدة: «المدينة» مرة واحدة بترجمتها الفرنسية
    assert pret.execute("SELECT nom_fr FROM lieu WHERE nom_ar='المدينة'").fetchone()[0] == "VILLE"
    assert pret.execute("SELECT COUNT(*) FROM lieu").fetchone()[0] == 2
    lot = pret.execute("SELECT * FROM import_lot").fetchone()
    assert lot["nb_ajoutes"] == 5 and json.loads(lot["rapport"])["annee"] == "2026/2027"


def test_reimport_sans_doublon(pret, dossier, fichiers):
    imp.appliquer(pret, dossier, imp.analyser(pret, fichiers))
    r = imp.analyser(pret, fichiers)
    assert not r.nouveaux and not r.mis_a_jour and r.inchanges == 5
    imp.appliquer(pret, dossier, r)
    assert pret.execute("SELECT COUNT(*) FROM eleve").fetchone()[0] == 5
    assert pret.execute("SELECT COUNT(*) FROM inscription").fetchone()[0] == 5


def test_mise_a_jour_et_champ_verrouille(tmp_path, pret, dossier, fichiers):
    imp.appliquer(pret, dossier, imp.analyser(pret, fichiers))
    pret.execute("UPDATE eleve SET prenom_fr='SAÏD', champs_verrouilles='[\"prenom_fr\"]' "
                 "WHERE code_massar='X000000001'")
    pret.commit()
    ar = {k: list(v) for k, v in AR.items()}
    ar["PS1-PS2"][1] = ("X000000002", "الوهمية", "سلمى", "F", "2021-03-31", "القرية")
    r = imp.analyser(pret, [classeur(tmp_path / "a2.xlsx", ar), fichiers[1]])
    assert [a.massar.code for a in r.mis_a_jour] == ["X000000002"]
    assert any("أُبقي على التعديل اليدوي" in a for a in r.alertes)
    imp.appliquer(pret, dossier, r)
    assert pret.execute("SELECT nom_ar FROM eleve WHERE code_massar='X000000002'").fetchone()[0] == "الوهمية"
    assert pret.execute("SELECT prenom_fr FROM eleve WHERE code_massar='X000000001'").fetchone()[0] == "SAÏD"


def test_valeur_vide_n_efface_pas(tmp_path, pret, dossier, fichiers):
    imp.appliquer(pret, dossier, imp.analyser(pret, fichiers))
    ar = {k: list(v) for k, v in AR.items()}
    ar["PS1-PS2"][0] = ("X000000001", "التجريبي", "سعيد", "M", "2022-02-12", None)
    r = imp.analyser(pret, [classeur(tmp_path / "a2.xlsx", ar)])
    assert not r.mis_a_jour
    imp.appliquer(pret, dossier, r)
    assert pret.execute("SELECT lieu_naissance_id FROM eleve WHERE code_massar='X000000001'").fetchone()[0]


def test_absents_et_changement_de_classe(tmp_path, pret, dossier, fichiers):
    imp.appliquer(pret, dossier, imp.analyser(pret, fichiers))
    ar = {"PS1-PS2": AR["PS1-PS2"] + [AR["4APG-5APG-6APG"][0]],
          "4APG-5APG-6APG": AR["4APG-5APG-6APG"][1:2]}
    r = imp.analyser(pret, [classeur(tmp_path / "a2.xlsx", ar)])
    assert [x["code_massar"] for x in r.absents] == ["X000000005"]
    assert [a.massar.code for a in r.changements_classe] == ["X000000003"]
    imp.appliquer(pret, dossier, r)
    # الغائب لا يُحذف
    assert pret.execute("SELECT COUNT(*) FROM inscription WHERE statut='inscrit'").fetchone()[0] == 5
    classe = pret.execute("SELECT c.code FROM inscription i JOIN classe c ON c.id=i.classe_id "
                          "JOIN eleve e ON e.id=i.eleve_id WHERE e.code_massar='X000000003'").fetchone()[0]
    assert classe == "PS1-PS2"


def test_absents_limites_aux_classes_importees(tmp_path, pret, dossier, fichiers):
    imp.appliquer(pret, dossier, imp.analyser(pret, fichiers))
    r = imp.analyser(pret, [classeur(tmp_path / "ps.xlsx", {"PS1-PS2": AR["PS1-PS2"]})])
    assert r.absents == []


def test_annee_suivante_et_report_du_niveau(tmp_path, pret, dossier, fichiers):
    imp.appliquer(pret, dossier, imp.analyser(pret, fichiers))
    a_confirmer = imp.niveaux_a_confirmer(pret)
    assert len(a_confirmer) == 5
    choix = {r["inscription_id"]: r["niveau"] for r in a_confirmer if r["niveau"]}
    # المدير يصحح المقترح: يوسف في الرابع (متأخر بسنتين عن سنه)
    youssef = next(r["inscription_id"] for r in a_confirmer if r["code_massar"] == "X000000003")
    choix[youssef] = "4AP"
    assert imp.confirmer_niveaux(pret, choix) == 5
    assert imp.niveaux_a_confirmer(pret) == []
    # السنة الموالية: يوسف (4AP) يُقترح له 5AP
    suivante = {"4APG-5APG-6APG": [AR["4APG-5APG-6APG"][0]]}
    r = imp.analyser(pret, [classeur(tmp_path / "n.xlsx", suivante, annee="2027/2028")])
    assert r.nouvelle_annee and r.absents == []
    imp.appliquer(pret, dossier, r)
    from idara.services import annee
    assert annee.annee_courante(pret)["libelle"] == "2027/2028"
    prop = imp.niveaux_a_confirmer(pret)
    assert [(x["code_massar"], x["niveau"]) for x in prop] == [("X000000003", "5AP")]


def test_annee_ancienne_refusee(tmp_path, pret):
    f = classeur(tmp_path / "old.xlsx", AR, annee="2025/2026")
    with pytest.raises(imp.ErreurImport, match="أقدم"):
        imp.analyser(pret, [f])


def test_etablissement_different_signale(tmp_path, pret):
    f = classeur(tmp_path / "x.xlsx", AR, etab="مؤسسة أخرى")
    assert any("لا يطابق" in a for a in imp.analyser(pret, [f]).alertes)


def test_classe_a_un_seul_niveau_confirmee(tmp_path, pret, dossier):
    f = classeur(tmp_path / "x.xlsx", {"5APG": [AR["4APG-5APG-6APG"][0]]})
    imp.appliquer(pret, dossier, imp.analyser(pret, [f]))
    assert imp.niveaux_a_confirmer(pret) == []


def test_age_hors_norme():
    assert imp.age_hors_norme("6AP", "2010-07-15", "2026/2027")
    assert not imp.age_hors_norme("4AP", "2016-01-01", "2026/2027")


def test_niveau_inconnu_refuse(pret):
    with pytest.raises(imp.ErreurImport):
        imp.confirmer_niveaux(pret, {1: "9AP"})


def test_lieu_ecriture_majoritaire(tmp_path, pret, dossier):
    ar = {"1APG": [(f"X00000001{i}", "أ", "ب", "M", "2020-01-01", "تافوغالت") for i in range(3)]}
    fr = {"1APG": [("X000000010", "A", "B", "M", "2020-01-01", "TAFOUGHALTE"),
                   ("X000000011", "A", "B", "M", "2020-01-01", "TAFOUGHALT"),
                   ("X000000012", "A", "B", "M", "2020-01-01", "TAFOUGHALT")]}
    r = imp.analyser(pret, [classeur(tmp_path / "a.xlsx", ar), classeur(tmp_path / "f.xlsx", fr, "fr")])
    imp.appliquer(pret, dossier, r)
    assert pret.execute("SELECT nom_fr FROM lieu WHERE nom_ar='تافوغالت'").fetchone()[0] == "TAFOUGHALT"
