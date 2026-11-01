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
    a.suivant()
    a.f_id.ville_ar.setText("المدينة")
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
    for i in range(len(f.PAGES)):
        f.aller(i)
        assert f.pile.currentIndex() == i
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
    assert len(page.lignes) == 4
    page.rafraichir()
    page.rafraichir()
    assert sum(1 for i in range(page.grille.count()) if page.grille.itemAt(i).widget()) == 1
    for code, ligne in page.lignes.items():
        assert ligne.etat.objectName() == "ok", ligne.etat.text()
        chemin = page.apercu(code)
        assert chemin is not None and chemin.exists(), page.message.text()
    assert len(ouverts) == 4
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
    p.resultats.selectRow(0)
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
    p.resultats.selectRow(0)
    assert p.c_lieu.text() == "الخميسات" and p.c_niveau.currentText() == "الخامس"
    assert p._reimprimer(0, 0) is not None and len(ouverts) == 2
    # لا يختلط بتلاميذ مسار
    f.aller_a("التلاميذ")
    f.page_eleves.recherche.setText("فيصل")
    assert f.page_eleves.resultats.rowCount() == 0
    f.close()
