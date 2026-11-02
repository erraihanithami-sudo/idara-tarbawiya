"""اختبارات الواجهة (تُشغَّل حيث يتوفر PySide6، أي على Windows في البناء الآلي).

تملأ المعالج كما يفعل المدير، وتتحقق مما كُتب في القاعدة. بيانات وهمية.
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402

from idara.app import creer_application, dossier_pret  # noqa: E402
from idara.data.db import ouvrir_base  # noqa: E402
from idara.services import etablissement as et  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return creer_application(["test"])


@pytest.fixture
def config_tmp(tmp_path, monkeypatch):
    monkeypatch.setenv("IDARA_CONFIG_DIR", str(tmp_path / "config"))
    return tmp_path


def remplir_assistant(a, dossier):
    a.f_etab.nom_ar.setText("مدرسة تجريبية")
    a.f_etab.nom_fr.setText("ECOLE TEST")
    a.f_etab.direction_ar.setText("المديرية التجريبية")
    a.f_etab.academie_ar.setText("الأكاديمية التجريبية")
    a.f_etab.unites.setText("الوحدة المركزية، وحدة فرعية")
    a.suivant()
    a.f_dir.nom_ar.setText("التجريبي")
    a.f_dir.prenom_ar.setText("أحمد")
    a.f_dir.ppr.setText("1234567")
    a.f_dir.nom_fr.setText("TAJRIBI")
    a.f_dir.prenom_fr.setText("Ahmed")
    a.suivant()
    a.f_id.ville_ar.setText("المدينة")
    a.f_id.ville_fr.setText("Ville")
    a.suivant()
    a.f_donnees.dossier.setText(str(dossier))


def test_application_en_arabe_de_droite_a_gauche(app):
    assert app.layoutDirection() == Qt.RightToLeft


def test_assistant_refuse_etape_incomplete(app, config_tmp):
    from idara.ui.assistant import AssistantPremierLancement
    a = AssistantPremierLancement()
    a.suivant()
    assert a.etape() == 0
    assert not a.erreur.isHidden()
    assert "إجباري" in a.erreur.text()
    a.f_etab.nom_ar.textEdited.emit("م")
    assert a.erreur.isHidden()


def test_assistant_complet_ecrit_la_base(app, config_tmp):
    from idara.ui.assistant import AssistantPremierLancement
    dossier = config_tmp / "الإدارة التربوية"
    a = AssistantPremierLancement()
    recu = []
    a.termine.connect(recu.append)
    remplir_assistant(a, dossier)
    assert a.etape() == 3
    a.suivant()
    assert recu, a.erreur.text()
    conn = ouvrir_base(dossier / "data.db")
    assert et.configuration_complete(conn)
    assert et.lire_etablissement(conn).nom_ar == "مدرسة تجريبية"
    assert et.unites(conn) == ["الوحدة المركزية", "وحدة فرعية"]
    conn.close()
    assert dossier_pret() is not None


def test_retour_ne_perd_pas_la_saisie(app, config_tmp):
    from idara.ui.assistant import AssistantPremierLancement
    a = AssistantPremierLancement()
    remplir_assistant(a, config_tmp / "d")
    a.precedent()
    a.precedent()
    assert a.etape() == 1
    assert a.f_dir.prenom_ar.text() == "أحمد"


def test_fenetre_principale_et_edition(app, config_tmp):
    from idara.ui.assistant import AssistantPremierLancement
    from idara.ui.fenetre import FenetrePrincipale
    a = AssistantPremierLancement()
    remplir_assistant(a, config_tmp / "الإدارة التربوية")
    dossier = a.terminer()
    f = FenetrePrincipale(dossier)
    f.tableau.rafraichir()
    from PySide6.QtWidgets import QWidget
    assert len([w for w in f.tableau.findChildren(QWidget, "", Qt.FindDirectChildrenOnly)
                if w.isVisibleTo(f.tableau)]) == 1
    assert f.nom_etab.text() == "مدرسة تجريبية"
    from idara.ui.fenetre import SECTIONS
    for nom in f.noms_pages():
        f.aller_a(nom)
        assert f.page_courante() == nom
    for i, (titre, noms) in enumerate(SECTIONS):
        f.aller_a(titre)
        assert f.pile.currentIndex() == i and f.boutons[i].isChecked()
        assert ("قريباً" in f.boutons[i].text()) == (not noms)
    assert f.page_courante() is not None
    f.aller_a("الرخص")
    f.aller([t for t, _ in SECTIONS].index("التلاميذ"))
    assert f.page_courante() == "التلاميذ"
    f.page_etab.f_etab.nom_ar.setText("اسم معدل")
    f.page_etab.enregistrer()
    assert f.page_etab.message.objectName() == "info", f.page_etab.message.text()
    assert et.lire_etablissement(f.conn).nom_ar == "اسم معدل"
    assert f.nom_etab.text() == "اسم معدل"
    f.close()
    assert len(list((dossier.sauvegardes).glob("*.db"))) == 1


def test_page_documents(app, config_tmp, monkeypatch):
    from idara.services import bureautique
    from idara.ui.assistant import AssistantPremierLancement
    from idara.ui.fenetre import FenetrePrincipale
    ouverts = []
    monkeypatch.setattr(bureautique, "ouvrir", lambda p: ouverts.append(p))
    monkeypatch.setattr(bureautique, "convertir_pdf", lambda p: p.with_suffix(".pdf"))
    a = AssistantPremierLancement()
    remplir_assistant(a, config_tmp / "الإدارة التربوية")
    f = FenetrePrincipale(a.terminer())
    f.aller_a("الوثائق")
    page = f.page_docs
    n = len(__import__("idara.services.documents", fromlist=["x"]).MODELES)
    assert len(page.lignes) == n
    page.rafraichir()
    page.rafraichir()
    assert sum(1 for i in range(page.grille.count()) if page.grille.itemAt(i).widget()) == 1
    for code, ligne in page.lignes.items():
        assert ligne.etat.objectName() == "ok", ligne.etat.text()
        chemin = page.apercu(code)
        assert chemin is not None and chemin.exists(), page.message.text()
    assert len(ouverts) == n
    assert page.apercu("visite_medicale", pdf=True).suffix == ".pdf"
    f.close()


def test_page_import_et_confirmation(app, config_tmp):
    from tests.fabrique_massar import classeur
    from tests.test_import_massar import AR, FR
    from idara.ui.assistant import AssistantPremierLancement
    from idara.ui.fenetre import FenetrePrincipale
    a = AssistantPremierLancement()
    remplir_assistant(a, config_tmp / "الإدارة التربوية")
    a.f_donnees.annee.setCurrentText("2026/2027")
    f = FenetrePrincipale(a.terminer())
    f.aller_a("الاستيراد من مسار")
    page = f.page_import
    assert page.c_niveaux.isHidden()
    page.definir_fichiers([classeur(config_tmp / "ar.xlsx", AR, etab="مدرسة تجريبية"),
                           classeur(config_tmp / "fr.xlsx", FR, "fr")])
    r = page.analyser()
    assert r is not None, page.message.text()
    assert not page.c_rapport.isHidden() and "X000000004" in page.details.text()
    res = page.appliquer()
    assert res is not None and res.ajoutes == 5, page.message.text()
    assert not page.c_niveaux.isHidden() and page.choix_classe.count() == 2
    page.choix_classe.setCurrentIndex(page.choix_classe.findData("PS1-PS2"))
    assert page.table.rowCount() == 2
    assert page.table.minimumHeight() >= 2 * 48 + 36
    assert page.confirmer() == 2
    assert page.choix_classe.count() == 1
    f.aller(0)
    f.close()


def _fenetre_avec_eleves(config_tmp):
    from tests.fabrique_massar import classeur
    from tests.test_import_massar import AR, FR
    from idara.services import import_eleves as imp
    from idara.ui.assistant import AssistantPremierLancement
    from idara.ui.fenetre import FenetrePrincipale
    a = AssistantPremierLancement()
    remplir_assistant(a, config_tmp / "الإدارة التربوية")
    a.f_donnees.annee.setCurrentText("2026/2027")
    f = FenetrePrincipale(a.terminer())
    r = imp.analyser(f.conn, [classeur(config_tmp / "ar.xlsx", AR), classeur(config_tmp / "fr.xlsx", FR, "fr")])
    imp.appliquer(f.conn, f.dossier, r)
    return f


def test_page_eleves_recherche_et_documents(app, config_tmp, monkeypatch):
    from datetime import date
    from idara.services import bureautique
    from idara.services import import_eleves as imp
    ouverts = []
    monkeypatch.setattr(bureautique, "ouvrir", lambda p: ouverts.append(p))
    f = _fenetre_avec_eleves(config_tmp)
    f.aller_a("التلاميذ")
    p = f.page_eleves
    assert p.resultats.rowCount() == 5 and p.c_fiche.isHidden()
    p.recherche.setText("يوسف")
    assert p.resultats.rowCount() == 1
    __import__("idara.ui.saisie", fromlist=["x"]).selectionner(p.resultats, 0)
    assert not p.c_fiche.isHidden() and "يوسف" in p.titre.text()
    # المستوى غير مؤكد: رسالة واضحة بدل وثيقة خاطئة
    assert p.vacances(date(2026, 12, 20), date(2027, 1, 4)) is None
    assert p.message.objectName() == "erreur"
    ins = f.conn.execute("SELECT id FROM inscription WHERE eleve_id=?", (p.eleve_id,)).fetchone()[0]
    imp.confirmer_niveaux(f.conn, {ins: "4AP"})
    doc = p.vacances(date(2026, 12, 20), date(2027, 1, 4))
    assert doc is not None and ouverts == [doc.chemin], p.message.text()
    assert p.docs.rowCount() == 1
    # تعديل الهوية
    p.c_prenom_fr.setText("Youssef-Amine")
    assert p.enregistrer() == ["prenom_fr"]
    assert "prenom_fr" in p.verrous.text()
    p.c_date.setText("31/02/2015")
    assert p.enregistrer() is None and p.message.objectName() == "erreur"
    # الوضعية
    assert not p.statut("parti", "2026-12-01")
    assert p.statut("parti", "2026-12-01", "مدرسة أخرى")
    assert "مغادر" in p.sous_titre.text()
    # استدعاءات متعددة
    p.recherche.clear()
    p.resultats.selectAll()
    docs = p.convocations()
    assert docs is not None and len(docs) == 5
    f.close()


def test_page_anciens_tous_champs(app, config_tmp, monkeypatch):
    from idara.services import bureautique
    ouverts = []
    monkeypatch.setattr(bureautique, "ouvrir", lambda p: ouverts.append(p))
    f = _fenetre_avec_eleves(config_tmp)
    f.aller_a("التلاميذ القدامى")
    p = f.page_anciens
    assert p.resultats.rowCount() == 0
    p.c_num.setText("8173")
    p.c_nom.setText("القديم")
    p.c_prenom.setText("فيصل")
    assert p.generer() is None and "متسلم" in p.message.text()
    p.c_dest.setText("فيصل القديم")
    p.c_cin.setText("a000000")
    assert p.generer() is None and "إجبارية" in p.message.text()
    p.r_m.setChecked(True)
    p.c_naissance.setText("01/01/1985")
    p.c_approx.setChecked(True)
    p.c_lieu.setText("الخميسات")
    p.c_entree.setText("15/10/1992")
    p.c_sortie.setText("30/06/1998")
    p.c_niveau.setCurrentIndex(4)
    doc = p.generer()
    assert doc is not None, p.message.text()
    assert ouverts == [doc.chemin] and p.remises.rowCount() == 1
    p.nouveau()
    assert p.c_num.text() == "" and p.eleve_id is None
    p.recherche.setText("8173")
    assert p.resultats.rowCount() == 1
    __import__("idara.ui.saisie", fromlist=["x"]).selectionner(p.resultats, 0)
    assert p.c_lieu.text() == "الخميسات" and p.c_niveau.currentText() == "الخامس"
    assert p._reimprimer(0, 0) is not None and len(ouverts) == 2
    # لا يختلط بتلاميذ مسار
    f.aller_a("التلاميذ")
    f.page_eleves.recherche.setText("فيصل")
    assert f.page_eleves.resultats.rowCount() == 0
    f.close()



def test_vacances_sans_nom_francais_du_directeur(app, config_tmp, monkeypatch):
    from datetime import date
    from idara.services import bureautique
    from idara.services import import_eleves as imp
    from idara.ui.saisie import selectionner
    monkeypatch.setattr(bureautique, "ouvrir", lambda p: None)
    f = _fenetre_avec_eleves(config_tmp)
    f.conn.execute("UPDATE personnel SET nom_fr=NULL, prenom_fr=NULL")
    f.conn.commit()
    f.aller_a("التلاميذ")
    p = f.page_eleves
    selectionner(p.resultats, 0)
    imp.confirmer_niveaux(f.conn, {f.conn.execute("SELECT id FROM inscription WHERE eleve_id=?",
                                                  (p.eleve_id,)).fetchone()[0]: "4AP"})
    assert p.vacances(date(2026, 12, 20), date(2027, 1, 4)) is None
    assert "اسم المدير ونسبه بالفرنسية" in p.message.text() and "إعداد المؤسسة" in p.message.text()
    f.close()


def test_page_personnel(app, config_tmp):
    from idara.services import personnel as rh
    from idara.ui.saisie import selectionner
    f = _fenetre_avec_eleves(config_tmp)
    f.aller_a("الموارد البشرية")
    p = f.page_rh
    assert p.liste.rowCount() == 1  # المدير من الإعداد
    assert "الإدارة: 1" in p.effectifs.text()
    # حفظ ناقص
    p.nouveau()
    p.c["nom_ar"].setText("الأستاذة")
    assert p.enregistrer() is None and "إجبارية" in p.message.text()
    p.c["prenom_ar"].setText("فاطمة")
    p.r_f.setChecked(True)
    p.categorie.setCurrentIndex(p.categorie.findData("enseignant"))
    assert not p.bloc_ens.isHidden()
    p.c["ppr"].setText("7654321")
    p.c["cin"].setText("ab123456")
    assert [p.cadre.itemData(i) for i in range(p.cadre.count())] == ["", "أستاذ(ة) التعليم الابتدائي", "متصرف(ة) تربوي(ة)"]
    assert p.grade.count() == 4
    p.cadre.setCurrentIndex(1)
    p.c["telephone"].setText("0612345678")
    p.c["heures_hebdo"].setText("30")
    assert [p.matiere.itemData(i) for i in range(p.matiere.count())] == ["", "عربية", "فرنسية", "مزدوجة", "أمازيغية"]
    p.matiere.setCurrentIndex(p.matiere.findData("مزدوجة"))
    # إسناد قسم: المستوى والعدد محسوبان
    for i in range(p.classes.count()):
        if p.classes.item(i).text().startswith("PS1-PS2"):
            p.classes.item(i).setCheckState(Qt.Checked)
    assert not p.c["nb_eleves"].isEnabled() and "2 تلميذاً" in p.calcul.text()
    pid = p.enregistrer()
    assert pid is not None, p.message.text()
    assert p.liste.rowCount() == 2 and "الأساتذة: 1" in p.effectifs.text()
    assert "ينقص" in p.manquants.text() and "الدرجة" in p.manquants.text()
    assert "ينقص لتحديد الفائض" in p.manquants.text()
    assert rh.lire(f.conn, pid).cin == "AB123456" and rh.lire(f.conn, pid).matiere == "مزدوجة"
    # المسار المهني
    p.dates["date_naissance"].setText("15/03/1980")
    p.dates["date_recrutement"].setText("16/09/1995")
    assert p.enregistrer() is None and "عند التوظيف" in p.message.text()
    p.dates["date_recrutement"].setText("16/09/2003")
    p.dates["date_affectation_academie"].setText("16/09/2003")
    p.dates["date_affectation_direction"].setText("01/09/2008")
    p.dates["date_affectation"].setText("01/09/2015")
    assert p.enregistrer() == pid, p.message.text()
    assert "الفائض" not in p.manquants.text() and "الأقدمية في الوظيفة" in p.anciennete.text()
    assert rh.lire(f.conn, pid).date_affectation_direction == "2008-09-01"
    # اقتراح الإطار في الملف الجديد
    p.nouveau()
    assert p.cadre.currentIndex() == 0 and p.cadre.count() == 3
    # المغادرة
    p.afficher(pid)
    assert p.depart("mute", "2026-12-01", "انتقال")
    assert p.liste.rowCount() == 1 and not p.b_retour.isHidden()
    p.voir_partis.setChecked(True)
    assert p.liste.rowCount() == 2
    # المدير: الفئة مقفلة، لا زر مغادرة
    ligne = next(i for i in range(p.liste.rowCount())
                 if p.liste.item(i, 0).data(Qt.UserRole) != pid)
    selectionner(p.liste, ligne)
    assert not p.categorie.isEnabled() and p.b_depart.isHidden()
    assert p.bloc_carriere.isHidden() and p.c["cycle"].isHidden()  # قرار المدير
    f.close()


def test_page_fa(app, config_tmp):
    from idara.services import personnel as rh
    f = _fenetre_avec_eleves(config_tmp)
    for prenom, recrut, etab, naiss in (("الأقدم", "2003-09-16", "2010-09-01", "1978-01-01"),
                                        ("الأحدث", "2020-09-16", "2023-09-01", "1995-01-01")):
        rh.enregistrer(f.conn, rh.Personnel(nom_ar="التجريبي", prenom_ar=prenom, sexe="M", categorie="enseignant",
                                            matiere="عربية", date_naissance=naiss, date_recrutement=recrut,
                                            date_affectation_direction=recrut, date_affectation=etab))
    rh.enregistrer(f.conn, rh.Personnel(nom_ar="ن", prenom_ar="بلا_مادة", sexe="F", categorie="enseignant"))
    f.aller_a("تدبير الفائض")
    p = f.page_fa
    c = p.cartes["عربية"]
    assert c.table.rowCount() == 2 and c.postes.value() == -1
    assert "حدد عدد الأساتذة" in c.etat.text()
    assert "بلا_مادة" in p.message.text()
    c.postes.setValue(1)
    assert "الفائض: الأحدث التجريبي" in c.etat.text()
    assert c.table.item(1, 7).text() == "فائض" and c.table.item(0, 0).text() == "1"
    assert p.cartes["فرنسية"].table.rowCount() == 0
    f.close()


def test_page_conges_chaine_complete(app, config_tmp, monkeypatch):
    from idara.services import bureautique
    from idara.services import conges as cg
    from idara.services import personnel as rh
    ouverts = []
    monkeypatch.setattr(bureautique, "ouvrir", lambda p: ouverts.append(p))
    f = _fenetre_avec_eleves(config_tmp)
    pid = rh.enregistrer(f.conn, rh.Personnel(
        nom_ar="التجريبية", prenom_ar="سلمى", sexe="F", categorie="enseignant", ppr="7654321", cin="AB1",
        cadre="أستاذ(ة) التعليم الابتدائي", grade="الدرجة الأولى", fonction="التدريس", cycle="ابتدائي", matiere="عربية",
        niveau_enseigne="الرابع", nb_eleves=28, heures_hebdo=30, adresse="حي", telephone="0600000000"))
    f.aller_a("الرخص")
    p = f.page_conges
    assert p.liste.rowCount() == 0 and not p.zone_docs.isEnabled()
    p.personnel.setCurrentIndex(p.personnel.findData(pid))
    assert p.motif.text() == "مرض"
    assert p.enregistrer() is None and "تاريخ بداية الرخصة" in p.message.text()
    p.debut.setText("10/11/2026")
    p.duree.setValue(10)
    assert "19 نونبر 2026" in p.fin.text()
    p.adresse.setText("حي تجريبي")
    p.avis.setText("أستاذة منضبطة")
    p.mesures.setText("توزيع التلاميذ")
    p.medecin.setText("الدكتور الطبيب")
    p.specialite.setText("الطب العام")
    p.recu_le.setText("10/11/2026")
    p.deposant.setText("المدلي")
    p.deposant_cin.setText("CD1")
    cid = p.enregistrer()
    assert cid is not None, p.message.text()
    assert p.zone_docs.isEnabled() and p.liste.rowCount() == 1
    for b in (p.b_demande, p.b_recu, p.b_remp):
        b.click()
        assert p.message.objectName() == "info", p.message.text()
    assert len(ouverts) == 3 and p.docs.rowCount() == 3
    assert p.bordereau(cg.pieces_proposees(f.conn, cg.lire(f.conn, cid)), "ملف رخصة") is not None
    assert [r["numero"] for r in cg.sortants(f.conn)] == [2, 1]
    r = cg.proposition_reprise(f.conn, cid)
    assert p.reprise(r) is not None and not p.b_reprise.isEnabled()
    assert p.liste.item(0, 1).text() == "مستأنفة"
    # سجل الصادر
    f.aller_a("سجل الصادر")
    s = f.page_sortants
    assert s.table.rowCount() == 2 and "3" in s.prochain.text()
    s.objet.setText("مراسلة يدوية")
    assert s.ajouter() == "3/26-27" and s.table.rowCount() == 3
    f.close()



def test_page_mouvements(app, config_tmp, monkeypatch):
    from idara.services import bureautique
    from idara.services import mouvements as mv
    from idara.ui.saisie import selectionner
    ouverts = []
    monkeypatch.setattr(bureautique, "ouvrir", lambda p: ouverts.append(p))
    f = _fenetre_avec_eleves(config_tmp)
    f.aller_a("حركية التلاميذ")
    p = f.page_mouvements
    assert f.page_courante() == "حركية التلاميذ" and p.liste.rowCount() == 0
    # وافد جديد
    p.code.setText("Y000000009")
    p._chercher_code()
    assert "غير موجود" in p.info_eleve.text()
    p.nom.setText("الوافد")
    p.prenom.setText("هبة")
    p.s_f.setChecked(True)
    p.date_mv.setText("08/09/2026")
    p.etab.setEditText("المؤسسة الأصلية")
    p.niveau.setEditText("الخامس")
    assert p.enregistrer() is not None, p.message.text()
    assert p.liste.rowCount() == 1 and "لم يُطلب الملف" in p.liste.item(0, 1).text()
    assert "وافدون لم يُطلب ملفهم (1): هبة الوافد" in p.alertes.text()
    selectionner(p.liste, 0)
    p.date_action.setText("10/09/2026")
    assert p.demande(False) is not None, p.message.text()
    assert len(ouverts) == 1 and "أُرسل الطلب" in p.liste.item(0, 1).text()
    assert "وافدون" not in p.alertes.text()
    selectionner(p.liste, 0)
    p.date_action.setText("20/09/2026")
    assert p.marquer("dossier_recu_le") and "توصلنا" in p.liste.item(0, 1).text()
    # مغادر من اللوائح
    p.f_parti.setChecked(True)
    p.code.setText("X000000003")
    p._chercher_code()
    assert p.prenom.text() == "يوسف"
    p.date_mv.setText("15/10/2026")
    p.etab.setEditText("قاسم أمين")
    assert p.enregistrer() is not None, p.message.text()
    assert p.r_parti.isChecked() and p.liste.rowCount() == 1 and p.b_envoi.isVisibleTo(p)
    assert "مغادرون لم يُرسل ملفهم (1)" in p.alertes.text()
    selectionner(p.liste, 0)
    p.date_action.setText("20/10/2026")
    assert p.envoi() is not None and "أُرسل الملف" in p.liste.item(0, 1).text()
    assert mv.alertes(f.conn)["envoi"] == []
    f.close()



def test_champ_date_calendrier(app):
    from PySide6.QtCore import QDate
    from idara.ui.saisie import ChampDate
    c = ChampDate()
    c.definir("2026-11-10")
    cal = c.ouvrir_calendrier()
    assert cal.selectedDate() == QDate(2026, 11, 10)
    cal.clicked.emit(QDate(2015, 9, 1))
    assert c.iso() == "2015-09-01" and c.popup is None
    c.clear()
    cal = c.ouvrir_calendrier()  # فارغ: اليومية على تاريخ اليوم
    assert cal.selectedDate() == QDate.currentDate()
    c.popup.close()



def test_page_comportement_et_exclus(app, config_tmp, monkeypatch):
    from idara.services import bureautique
    from idara.services import eleves as el
    from idara.ui.saisie import selectionner
    ouverts = []
    monkeypatch.setattr(bureautique, "ouvrir", lambda p: ouverts.append(p))
    f = _fenetre_avec_eleves(config_tmp)
    f.aller_a("تتبع السلوك")
    p = f.page_comportement
    assert p.liste.rowCount() == 0 and not p.b_save.isEnabled()
    p.recherche.setText("يوسف")
    selectionner(p.liste, 0)
    assert p.b_save.isEnabled() and "يوسف" in p.titre.text()
    assert p.enregistrer(False) is None and "إجبارية" in p.message.text()
    p.nature.setEditText("شغب في القسم")
    assert p.enregistrer(False) is not None and p.obs.rowCount() == 1
    p.nature.setEditText("عنف لفظي")
    assert p.enregistrer(True) is not None and len(ouverts) == 1
    assert "استدعاء" in p.obs.item(0, 2).text()
    p.recherche.clear()
    assert p.liste.rowCount() == 1 and p.liste.item(0, 1).text() == "2"
    # المفصولون في صفحة الحركية
    eid = f.conn.execute("SELECT id FROM eleve WHERE code_massar='X000000002'").fetchone()[0]
    el.changer_statut(f.conn, eid, "exclu", "2026-10-20", "", "قرار المجلس")
    f.aller_a("حركية التلاميذ")
    m = f.page_mouvements
    m.r_autres.setChecked(True)
    assert m.liste.rowCount() == 1 and "مفصول" in m.liste.item(0, 1).text() and m.b_demande.isHidden()
    f.close()



def test_page_conseils(app, config_tmp, monkeypatch):
    from idara.services import bureautique
    from tests.fabrique_resultats import classeur_resultats
    ouverts = []
    monkeypatch.setattr(bureautique, "ouvrir", lambda p: ouverts.append(p))
    f = _fenetre_avec_eleves(config_tmp)
    f.aller_a("التقييم")
    p = f.page_conseils
    assert f.page_courante() == "مجالس الأقسام" and not p.b_pv.isEnabled()
    fic = classeur_resultats(config_tmp / "r.xlsx", {
        "4APG-1": [("X000000001", "التجريبي سعيد", [8] * 8), ("X000000002", "الوهمي سلمى", [4] * 8)],
        "4APG-5APG-6APG": [("X000000004", "النموذج مريم", [6] * 8)]})
    r = p.importer([fic])
    assert r is not None and p.annee.currentText() == "2026/2027", p.message.text()
    assert not p.niveaux_manquants.isHidden() and p.niveaux_manquants.rowCount() == 1
    cb = p.niveaux_manquants.cellWidget(0, 1)
    cb.setCurrentIndex(cb.findData("5AP"))
    assert p.enregistrer_niveaux() == 1 and p.niveaux_manquants.isHidden()
    p.niveau.setCurrentIndex(p.niveau.findData("4AP"))
    assert p.stats.rowCount() == 1 and p.stats.item(0, 6).text() == "50.00%"
    p.isa["4APG-1"]["ar"].setText("66.03")
    p.difficultes.setPlainText("ضعف القراءة")
    p.date.setText("04/07/2026")
    assert p.generer_pv() is not None, p.message.text()
    assert p.generer_synthese() is not None and len(ouverts) == 2
    f.close()


def test_page_association_najah(app, config_tmp, monkeypatch, tmp_path):
    from idara.services import associations as asso
    from idara.services import bureautique
    from idara.ui.saisie import selectionner
    monkeypatch.setattr(bureautique, "ouvrir", lambda p: None)
    f = _fenetre_avec_eleves(config_tmp)
    f.aller_a("التدبير المالي والمادي")
    p = f.page_asso
    assert f.page_courante() == "جمعية دعم مدرسة النجاح" and not p.b_save.isEnabled()
    eid = p.ouvrir(dict(libelle="2025/2026", debut="2025-09-01", fin="2026-08-31",
                        report_banque=50000, report_caisse=300, reference="محضر تسليم المهام"))
    assert eid and p.b_save.isEnabled() and p.ops.rowCount() == 2
    assert p.chiffres["banque"].text() == "50\u00a0000.00"
    # تحويل: يختفي البند
    p.nature.setCurrentIndex(p.nature.findData("transfert"))
    assert p.ligne.isHidden() and p.l_registre.text() == "من *"
    p.date.setText("24/10/2025")
    p.montant.setText("3000")
    p.reference.setText("شيك 04")
    assert p.enregistrer(), p.message.text()
    # مصروف من الصندوق ببند من نموذج المدير
    p.nature.setCurrentIndex(p.nature.findData("depense"))
    p.registre.setCurrentIndex(p.registre.findData("caisse"))
    p.chapitre.setCurrentIndex(p.chapitre.findText("التجهيزات"))
    assert p.ligne.count() == 8 and "20000" in p.indice.text()
    p.date.setText("05/11/2025")
    p.montant.setText("99999")
    p.reference.setText("فاتورة 1")
    assert p.enregistrer() is None and "لا يكفي" in p.message.text()
    p.montant.setText("1200")
    p.reference.setText("فاتورة 1")
    assert p.enregistrer(), p.message.text()
    assert p.chiffres["caisse"].text() == "2\u00a0100.00"
    p.vue.setCurrentIndex(p.vue.findData("caisse"))
    assert p.ops.rowCount() == 3 and p.ops.item(2, 5).text() == "2\u00a0100.00"
    # الميزانية والتنبيه
    rid = asso.execution(f.conn, eid)
    i = next(k for k in range(p.budget.rowCount()) if p.budget.item(k, 0).data(Qt.UserRole) == p.ligne.itemData(0))
    selectionner(p.budget, i)
    p.prevu.setText("1000")
    assert p.enregistrer_prevision() and not p.alertes.isHidden() and rid
    selectionner(p.ops, 2)
    assert p.supprimer() and p.alertes.isHidden()
    assert p.exporter(tmp_path / "n.xlsx").exists()
    p.rib.setText("12A")
    assert not p.enregistrer_association()
    f.close()


def test_association_documents_du_guide(app, config_tmp, monkeypatch):
    from idara.services import associations as asso
    from idara.services import bureautique
    from idara.ui.saisie import selectionner
    ouverts = []
    monkeypatch.setattr(bureautique, "ouvrir", lambda p: ouverts.append(p))
    f = _fenetre_avec_eleves(config_tmp)
    f.aller_a("جمعية دعم مدرسة النجاح")
    p = f.page_asso
    p.ouvrir(dict(libelle="2025/2026", debut="2025-09-01", fin="2026-08-31", report_banque=5000, report_caisse=300))
    p.president.setText("الرئيس الوهمي")
    p.tresorier.setText("أمين المال الوهمي")
    assert p.enregistrer_association()
    p.nature.setCurrentIndex(p.nature.findData("recette"))
    p.registre.setCurrentIndex(p.registre.findData("caisse"))
    p.chapitre.setCurrentIndex(p.chapitre.findText("الهبات"))
    p.date.setText("02/10/2025")
    p.montant.setText("250")
    p.tiers.setText("محسن وهمي")
    assert p.enregistrer(), p.message.text()
    selectionner(p.ops, 2)
    assert p.b_pieces.isEnabled() and len(p.menu_pieces.actions()) == 1
    assert p.generer_piece("recu") and "وصل مداخيل 01" in p.l_pieces.text()
    asso_op = f.conn.execute("SELECT id FROM operation_financiere WHERE numero=1").fetchone()[0]
    assert asso_op and p.generer_registre("caisse") and p.generer_budget()
    assert p.passation(dict(date_pv="2026-01-10", ancien="أمين المال الوهمي", nouveau="الأمينة الجديدة",
                            remarques=[], maj=True))
    assert p.tresorier.text() == "الأمينة الجديدة" and len(ouverts) == 4
    assert p.rapport(dict(numero_ag="2", analyses={})) and len(ouverts) == 5
    from idara.ui.page_associations import DialogueExercice
    d = DialogueExercice(p, False, "2025-12-31")  # السنة المالية للجمعية سنة ميلادية
    assert (d.libelle.text(), d.debut.iso(), d.fin.iso()) == ("2026", "2026-01-01", "2026-12-31")
    assert asso.association(f.conn)["tresorier"] == "الأمينة الجديدة"
    f.close()


def test_page_achats_bon_de_commande(app, config_tmp, monkeypatch):
    from idara.services import achats as ac
    from idara.services import bureautique
    from idara.services import etablissement as et
    from idara.ui.saisie import selectionner
    ouverts = []
    monkeypatch.setattr(bureautique, "ouvrir", lambda p: ouverts.append(p))
    f = _fenetre_avec_eleves(config_tmp)
    e = et.lire_etablissement(f.conn)
    e.adresse = "حي تجريبي"
    et.enregistrer_etablissement(f.conn, e)
    pa = f.page_asso
    f.aller_a("جمعية دعم مدرسة النجاح")
    pa.ouvrir(dict(libelle="2025/2026", debut="2025-09-01", fin="2026-08-31", report_banque=20000, report_caisse=0))
    pa.president.setText("الرئيس الوهمي")
    pa.tresorier.setText("أمين المال الوهمي")
    assert pa.enregistrer_association()
    assert pa.recu_equipement(dict(date_don="2025-11-03", donateur="شركة وهمية", description="حاسوب"))
    f.aller_a("الصرف")
    p = f.page_achats
    assert f.page_courante() == "الصرف" and p.zone.isHidden()
    rub = p.rubrique.itemData(p.rubrique.findText("معدات معلوماتية", Qt.MatchContains))
    aid = p.nouveau(dict(mode="bon_commande", objet="اقتناء طابعات", rubrique_id=rub, service_type=""))
    assert aid and not p.zone.isHidden() and p.boutons_docs["pv_service"].isHidden()
    p.articles.setItem(0, 0, __import__("idara.ui.saisie", fromlist=["x"]).cellule("طابعة"))
    p.articles.setItem(0, 1, __import__("idara.ui.saisie", fromlist=["x"]).cellule("2"))
    assert p.enregistrer_besoin(), p.message.text()
    p.date_demande.setText("02/10/2025")
    p.nb.setText("2")
    assert not p.enregistrer_demande() and "3 طلبات" in p.message.text()
    p.nb.setText("3")
    assert p.enregistrer_demande() and p.document("demande_devis")
    p.date_comm.setText("15/10/2025")
    p.membres.setItem(2, 0, __import__("idara.ui.saisie", fromlist=["x"]).cellule("العضو الوهمي"))
    assert p.enregistrer_commission(), p.message.text()
    assert p.membres.item(0, 0).text() == "الرئيس الوهمي"
    for nom, m in (("الممون أ", "2500"), ("الممون ب", "2400"), ("الممون ج", "2600")):
        p.nom_offre.setEditText(nom)
        p.montant_offre.setText(m)
        assert p.ajouter_offre(), p.message.text()
    assert p.offres.rowCount() == 3 and p.offres.item(0, 0).text() == "الممون ب"
    selectionner(p.offres, 0)
    assert p.choisir() and p.document("pv_commission")
    p.articles.setItem(0, 3, __import__("idara.ui.saisie", fromlist=["x"]).cellule("1000"))
    assert p.enregistrer_besoin()
    p.date_bc.setText("20/10/2025")
    assert p.engager()
    assert p.editer_fournisseur(ac.Fournisseur("الممون ب", adresse="شارع وهمي",
                                               id=ac.fournisseur_par_nom(f.conn, "الممون ب")))
    assert p.document("bon_commande")
    p.date_liv.setText("24/10/2025")
    assert p.enregistrer_reception() and p.document("bon_livraison")
    p.num_facture.setText("F-1")
    p.date_facture.setText("25/10/2025")
    assert p.enregistrer_facture()
    p.date_paie.setText("28/10/2025")
    p.ref_paie.setText("0001")
    assert p.payer(), p.message.text()
    assert "○" not in p.etapes.text() and len(ouverts) == 5
    assert ac.achat(f.conn, aid)["operation_id"]
    f.close()


def test_section_pedagogie(app, config_tmp, monkeypatch):
    from idara.services import bureautique
    from idara.ui.saisie import selectionner
    from tests.fabrique_resultats import classeur_resultats
    from tests.fabrique_tarl import classeur_niveaux
    ouverts = []
    monkeypatch.setattr(bureautique, "ouvrir", lambda p: ouverts.append(p))
    f = _fenetre_avec_eleves(config_tmp)
    f.aller_a("التدبير التربوي")
    assert f.page_courante() == "أداء المؤسسة"
    p = f.page_perf
    fic = classeur_resultats(config_tmp / "r.xlsx", {"4APG-1": [("X000000001", "أ", [6] * 8), ("X000000002", "ب", [6] * 8)]},
                             semestres={"X000000001": (4, 6), "X000000002": (6, 7)})
    assert p.importer([fic]) and p.periode.count() == 2
    assert "الأسدوس الثاني 2026/2027" in p.titre.text()
    inst = p.table.item(p.table.rowCount() - 1, 0)
    assert inst.text() == "المؤسسة" and p.table.item(p.table.rowCount() - 1, 6).text() == "+1.50"
    f.aller_a("التعلمات الأساس")
    t = f.page_tarl
    ft = classeur_niveaux(config_tmp / "t.xlsx", {"2APG-1": [("X000000001", "أ", "حرف", "كلمة", "débutant", "lettre",
                                                              "رقمان", "جمع")]})
    assert t.importer([ft]) and t.groupe.count() == 3
    assert t.table.rowCount() == 5 and t.table.item(2, 3).text() == "1"
    t.matiere.setCurrentIndex(t.matiere.findData("fr"))
    assert t.difficulte.rowCount() == 1 and "100.00%" not in t.resume.text()
    f.aller_a("الأندية والأنشطة")
    v = f.page_vie
    v.nom_club.setText("النادي البيئي")
    v.horaire.setText("الأربعاء 15:00")
    assert v.enregistrer_club(True) and v.clubs.rowCount() == 1
    selectionner(v.clubs, 0)
    v.recherche.setText("X000000001")
    assert v.candidats.count() == 1
    assert v.ajouter_membre() and v.clubs.item(0, 3).text() == "1"
    selectionner(v.clubs, 0)
    assert v.membres.rowCount() == 1 and v.liste_club()
    v.titre_act.setText("ذكرى المسيرة الخضراء")
    v.type_act.setCurrentText("يوم وطني أو دولي")
    v.statut.setCurrentIndex(v.statut.findData("realisee"))
    v.debut.setText("06/11/2026")
    v.nb_g.setText("20")
    v.nb_f.setText("25")
    assert v.enregistrer_activite(True), v.message.text()
    assert v.acts.rowCount() == 1 and "45" in v.indic.text()
    assert v.document("programme") and v.document("bilan") and len(ouverts) == 3
    f.close()
