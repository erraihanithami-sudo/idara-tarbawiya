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
    yield tmp_path
    # اختبار فاشل لا يصل إلى f.close(): تُغلق نوافذه هنا حتى لا تتراكم (تراكمها أوقف Python على Windows)
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is not None:
        import sqlite3
        for w in app.topLevelWidgets():
            conn = getattr(w, "conn", None)
            if conn is not None:
                try:
                    conn.execute("SELECT 1")
                except sqlite3.ProgrammingError:   # أُغلقت من قبل
                    continue
                w.close()
            elif w.isVisible():
                w.close()
        app.processEvents()


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
    for i, (titre, fils) in enumerate(SECTIONS):
        f.aller_a(titre)
        assert f.page_courante() in [n for n, _ in fils] and f.boutons[i].actif
        assert sum(b.actif for b in f.boutons) == 1
        programmes = [n for n, _ in fils if n in f.pages]
        assert ("قريباً" in f.boutons[i].text()) == (not programmes)
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


def test_navigation_deroulante(app, config_tmp):
    """اقتراح المدير (2026-11-03): الفروع تحت القسم الرئيسي، تظهر بالضغط عليه وتختفي بالضغطة الثانية."""
    from idara.ui.fenetre import SECTIONS
    f = _fenetre_avec_eleves(config_tmp)
    titres = [t for t, _ in SECTIONS]
    assert titres[:8] == ["القيادة والتدبير", "التلاميذ", "الموارد البشرية", "التدبير التربوي",
                          "التدبير المالي والمادي", "التقييم", "مشروع المؤسسة", "تسليم المهام"]
    assert [l for _, l in SECTIONS[2][1]] == ["معلومات الأطر", "تدبير الفائض", "الرخص", "المحاضر"]
    assert [l for _, l in SECTIONS[0][1]] == ["لوحة القيادة", "إحصائيات المؤسسة", "برنامج العمل السنوي والتذكيرات",
                                         "الأداء العام للمؤسسة", "تتبع الغياب", "مجالس المؤسسة"]
    assert f.page_courante() == "لوحة القيادة" and f.est_ouvert(0)
    i = titres.index("التدبير المالي والمادي")
    f.boutons[i].click()
    assert f.est_ouvert(i) and not f.est_ouvert(0) and f.page_courante() == "لوحة القيادة"
    assert [b.text().split("  ")[0] for b in f.sous[i]][:3] == ["تدبير التسجيلات", "الجرد", "جمعية دعم مدرسة النجاح"]
    assert "قريباً" in f.sous[i][1].text() and "قريباً" not in f.sous[i][2].text()
    f.sous[i][2].click()
    assert f.page_courante() == "جمعية دعم مدرسة النجاح" and f.sous[i][2].isChecked() and f.boutons[i].actif
    f.boutons[i].click()   # الضغطة الثانية تطوي الفروع، والصفحة تبقى
    assert not f.est_ouvert(i) and f.page_courante() == "جمعية دعم مدرسة النجاح"
    f.aller_a("الجرد")
    assert f.page_courante() == "الجرد" and f.est_ouvert(i)
    j = titres.index("تسليم المهام")   # قسم دون فروع: يفتح صفحته مباشرة
    f.boutons[j].click()
    assert f.page_courante() == "تسليم المهام" and f.boutons[j].isChecked() and not f.est_ouvert(i)
    f.close()


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
    assert "لم يُحفظ" in p.message_bas.text() and not p.message_bas.isHidden()   # بجانب زر الحفظ أيضاً
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
    # قرار المدير (2026-11-03): معطيات التنظيم التربوي مطلوبة لملف الأستاذ(ة)
    assert not p.bloc_tanzim.isHidden() and not p.bloc_insp.isHidden()   # أستاذ: التفتيش ظاهر
    # تصحيح 2026-11-04: النقص لا يمنع الحفظ (أستاذ مستورد من XML دون تفتيش)، بل يُنبَّه إليه بجانب الزر
    pid0 = p.enregistrer()
    assert pid0 is not None and "حُفظ" in p.message_bas.text() and "تاريخ الدرجة" in p.message_bas.text()
    assert "آخر نقطة تفتيش" in p.message.text()
    p.grade.setCurrentIndex(p.grade.findData("الدرجة الأولى"))
    p.d_tanzim["date_grade"].setText("01/01/2020")
    p.echelon.setCurrentIndex(p.echelon.findData("7"))
    p.d_tanzim["date_echelon"].setText("01/06/2023")
    p.sans_insp.setChecked(True)
    assert not p.note_insp.isEnabled()
    pid = p.enregistrer()
    assert pid is not None, p.message.text()
    assert rh.lire(f.conn, pid).echelon == "7" and rh.lire(f.conn, pid).sans_inspection
    assert p.liste.rowCount() == 2 and "الأساتذة: 1" in p.effectifs.text()
    # قرار المدير (2026-11-03): المهمة بدل الفئة (التدريس أو الإدارة)، دون عمود الملف
    assert p.liste.columnCount() == 3 and p.liste.horizontalHeaderItem(2).text() == "المهمة"
    assert p.liste.horizontalHeaderItem(1).text() == "الوحدة المدرسية" and not p.liste.isColumnHidden(1)
    assert sorted(p.liste.item(i, 2).text() for i in range(2)) == ["الإدارة", "التدريس"]
    # حذف موظف أُدخل خطأً (طلب المدير 2026-11-03)، والمدير لا يُحذف
    assert p.b_suppr.objectName() == "danger" and not p.b_suppr.isHidden()
    p.c["ppr"].setText("")
    p.nouveau()
    p.c["nom_ar"].setText("خطأ")
    p.c["prenom_ar"].setText("إدخال")
    p.r_m.setChecked(True)
    p.categorie.setCurrentIndex(p.categorie.findData("gardien"))
    p.fonction.setCurrentIndex(0)
    pid_err = p.enregistrer()
    assert pid_err is not None, p.message.text()
    assert p.liste.rowCount() == 3
    assert p.supprimer(confirmer=False) and p.liste.rowCount() == 2 and "حُذف" in p.message.text()
    p.afficher(pid)
    assert [p.fonction.itemText(i) for i in range(p.fonction.count())][1:] == ["التدريس", "الإدارة"]
    assert "ينقص" in p.manquants.text() and "العنوان الشخصي" in p.manquants.text()
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


def test_page_conges_radaa(app, config_tmp):
    """رخصة الرضاعة في الاستمارة: تاريخ الازدياد يقترح الفترة، ولا تعويض ولا استئناف."""
    from datetime import date as _d
    from idara.services import conges as cg
    from idara.services import personnel as rh
    f = _fenetre_avec_eleves(config_tmp)
    pid = rh.enregistrer(f.conn, rh.Personnel(nom_ar="التجريبية", prenom_ar="سلمى", sexe="F", categorie="enseignant"))
    f.aller_a("الرخص")
    p = f.page_conges
    p.personnel.setCurrentIndex(p.personnel.findData(pid))
    assert p.zone_radaa.isHidden()
    p.type.setCurrentIndex(p.type.findText(cg.RADAA))
    assert not p.zone_radaa.isHidden() and p.motif.text() == "الرضاعة"
    p.naissance.setText("01/03/2025")
    assert p.debut.iso() == "2025-03-01"
    assert p.duree.value() == (_d(2027, 2, 28) - _d(2025, 3, 1)).days + 1
    p.horaire.setText("11:00 - 12:00")
    cid = p.enregistrer()
    assert cid, p.message.text()
    assert not p.b_reprise.isEnabled() and not p.b_remp.isEnabled()
    assert "رخص رضاعة جارية" in p.l_radaa.text() and "11:00 - 12:00" in p.l_radaa.text()
    assert "سلمى" not in p.alertes.text()
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
    # مغادر سابق غير وارد في اللائحة (طلب المدير 2026-11-09)
    p.nouveau()
    p.f_parti.setChecked(True)
    assert p.classe.isVisibleTo(p) and p.classe.count() > 1
    p.code.setText("Z000000001")
    p._chercher_code()
    assert "غير وارد في اللائحة" in p.info_eleve.text()
    p.nom.setText("المغادر")
    p.prenom.setText("سعيد")
    p.s_m.setChecked(True)
    p.niveau.setEditText("الرابع")
    p.classe.setCurrentIndex(1)
    p.date_mv.setText("01/10/2026")
    p.etab.setEditText("مدرسة أخرى")
    assert p.enregistrer() is not None, p.message.text()
    assert p.liste.rowCount() == 2
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
    f.aller_a("مجالس الأقسام")
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
    f.aller_a("جمعية دعم مدرسة النجاح")
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


def test_association_formulaire_et_report(app, config_tmp):
    """ملاحظتا المدير (2026-11-03): «الطرف المعني» كان فوق «البيان»؛ والمنقول غائب عن رصيد البنك."""
    f = _fenetre_avec_eleves(config_tmp)
    f.aller_a("جمعية دعم مدرسة النجاح")
    p = f.page_asso
    p.resize(1300, 900)
    p.show()
    app.processEvents()
    g = p.grille_op
    pos = {}
    for w in (p.detail, p.tiers, p.tiers_qualite, p.reference):
        i = g.indexOf(w)
        if i >= 0:
            pos[w] = g.getItemPosition(i)[0]
    assert len(set(pos.values())) >= 3 and pos[p.tiers] > pos[p.detail]
    eid = p.ouvrir(dict(libelle="2026", debut="2026-01-01", fin="2026-12-31"))
    assert eid and p.chiffres["banque"].text() == "0.00" and p.b_report.isEnabled()
    assert p.modifier_report(dict(banque="12 500,00", caisse="250", reference="كشف الحساب"))
    assert p.chiffres["banque"].text() == "12 500.00" and p.chiffres["caisse"].text() == "250.00"
    e2 = p.ouvrir(dict(libelle="2027", debut="2027-01-01", fin="2027-12-31"))
    assert e2 and p.chiffres["banque"].text() == "12 500.00"
    assert not p.modifier_report(dict(banque="1", caisse="0")) and "2026" in p.message.text()
    f.close()


def test_association_modifier_operation(app, config_tmp):
    """طلب المدير (2026-11-03): تعديل العمليات وحذفها، وتعديل المنقول."""
    from idara.services import associations as asso
    from idara.ui.saisie import selectionner
    f = _fenetre_avec_eleves(config_tmp)
    f.aller_a("جمعية دعم مدرسة النجاح")
    p = f.page_asso
    eid = p.ouvrir(dict(libelle="2026", debut="2026-01-01", fin="2026-12-31", report_banque=5000, report_caisse=0))
    p.nature.setCurrentIndex(p.nature.findData("depense"))
    p.chapitre.setCurrentIndex(p.chapitre.findText("التجهيزات"))
    p.date.setText("05/03/2026")
    p.montant.setText("1200")
    p.reference.setText("فاتورة 1")
    p.detail.setText("حاسوب")
    oid = p.enregistrer()
    assert oid, p.message.text()
    ligne = p.ligne.currentData()

    def rangee(cond):
        return next(k for k in range(p.ops.rowCount()) if cond(p.ops.item(k, 0).data(Qt.UserRole)))

    selectionner(p.ops, rangee(lambda x: x == oid))
    assert p.b_modif.isEnabled() and p.modifier()
    assert p.b_save.text() == "حفظ التعديل" and p.montant.text() == "1200.00" and p.detail.text() == "حاسوب"
    assert p.ligne.currentData() == ligne and p.nature.currentData() == "depense"
    p.montant.setText("1500")
    assert p.enregistrer() == oid and p.b_save.text() == "تسجيل العملية"
    assert len(asso.operations(f.conn, eid)) == 2 and asso.totaux(f.conn, eid)["banque"] == 3500
    selectionner(p.ops, rangee(lambda x: x == oid))
    p.modifier()
    p._fin_edition()
    assert p.edit_id is None and p.montant.text() == ""
    assert p.modifier_report(dict(banque="6000", caisse="0"))
    assert asso.totaux(f.conn, eid)["banque"] == 4500
    selectionner(p.ops, rangee(lambda x: x == oid))
    assert p.supprimer() and asso.totaux(f.conn, eid)["banque"] == 6000
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
    f.aller_a("أداء المؤسسة")
    assert f.page_courante() == "أداء المؤسسة"
    p = f.page_perf
    fic = classeur_resultats(config_tmp / "r.xlsx", {"4APG-1": [("X000000001", "أ", [6] * 8), ("X000000002", "ب", [6] * 8)]},
                             semestres={"X000000001": (4, 6), "X000000002": (6, 7)})
    assert p.importer([fic]) and p.periode.count() == 2
    assert "الأسدوس الثاني 2026/2027" in p.titre.text()
    inst = p.table.item(p.table.rowCount() - 1, 0)
    assert inst.text() == "المؤسسة" and p.table.item(p.table.rowCount() - 1, 6).text() == "\u200e+1.50"
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


def test_page_riyada(app, config_tmp, monkeypatch):
    from idara.services import bureautique
    from idara.services import riyada as ry
    ouverts = []
    monkeypatch.setattr(bureautique, "ouvrir", lambda p: ouverts.append(p))
    f = _fenetre_avec_eleves(config_tmp)
    f.aller_a("الريادة")
    p = f.page_riyada
    assert p.annee.currentText() == "2026/2027" and p.saisie.rowCount() >= 1 and p.pieces.rowCount() == 20
    cl = p.saisie.item(0, 0).data(Qt.UserRole)
    p.phase.setCurrentIndex(p.phase.findData(0))
    p.saisie.item(0, 2).setText("60")
    assert p.enregistrer_isa()
    p.phase.setCurrentIndex(p.phase.findData(1))
    p.saisie.item(0, 2).setText("150")
    assert not p.enregistrer_isa() and "خارج المجال" in p.message.text()
    p.saisie.item(0, 2).setText("72,5")
    assert p.enregistrer_isa() and p.evol.rowCount() == 1 and "+12.50" in p.evol.item(0, 3).text()
    assert ry.isa(f.conn, "2026/2027")[cl]["fr"] == {0: 60.0, 1: 72.5}
    assert not p.lettres() and "لا نسب" in p.message.text()  # لا أستاذ مسند للقسم
    p.pieces.item(1, 1).setCheckState(Qt.Checked)
    p.infos_w["riyada_date_construction"].setText("1985")
    assert p.enregistrer_dossier()
    assert ry.pieces(f.conn, "2026/2027")[1]["disponible"]
    assert p.document("dossier") and p.document("synthese") and len(ouverts) == 2
    f.close()


def test_bouton_ouvrir_exercice(app, config_tmp, monkeypatch):
    """النقر على «فتح سنة مالية جديدة» (لا الاستدعاء المباشر): زر Qt يمرر checked=False."""
    from PySide6.QtWidgets import QDialog
    from idara.services import associations as asso
    from idara.ui import page_associations as pa
    monkeypatch.setattr(pa.DialogueExercice, "exec", lambda self: QDialog.Accepted)
    f = _fenetre_avec_eleves(config_tmp)
    f.aller_a("جمعية دعم مدرسة النجاح")
    p = f.page_asso
    p.b_ouvrir.click()
    ex = asso.exercices(f.conn)
    assert len(ex) == 1 and ex[0]["date_debut"].endswith("-01-01"), p.message.text()
    p.b_ouvrir.click()  # السنة الموالية تُقترح آلياً
    assert [e["libelle"] for e in asso.exercices(f.conn)][0] == str(int(ex[0]["libelle"]) + 1)
    f.close()


def test_page_conseils_etablissement(app, config_tmp, monkeypatch):
    from idara.services import bureautique
    from idara.services import conseils_etab as ce
    from idara.ui.saisie import selectionner
    ouverts = []
    monkeypatch.setattr(bureautique, "ouvrir", lambda p: ouverts.append(p))
    f = _fenetre_avec_eleves(config_tmp)
    f.aller_a("مجالس المؤسسة")
    p = f.page_conseils_etab
    assert f.page_courante() == "مجالس المؤسسة" and p.suivi.rowCount() == 3
    p.proposer()
    assert p.membres.item(0, 1).text() == "رئيس المجلس" and p.c_optionnels.isVisibleTo(p)
    assert not any(p.membres.item(i, 1) and p.membres.item(i, 1).text() == "ممثل المجلس الجماعي"
                   for i in range(p.membres.rowCount()))
    p.c_optionnels.setChecked(True)  # الأعضاء الاختياريون بخانة
    for i in range(1, p.membres.rowCount()):
        it = p.membres.item(i, 0)
        if it is not None and not it.text():
            it.setText(f"العضو {i}")
    assert p.enregistrer_membres(), p.message.text()
    assert p.presence.count() == 10 and p.l_ecarts.isHidden()
    p.date.setText("03/10/2026")
    p.suggestion.setCurrentIndex(0)
    p._ajouter_point()
    for i in range(6):
        p.presence.item(i).setCheckState(Qt.Unchecked)
    assert not p.enregistrer(True) and "النصاب غير مكتمل" in p.message.text()
    p.convoc.setCurrentIndex(p.convoc.findData("seconde"))
    assert p.enregistrer(True) and p.seances.rowCount() == 1
    selectionner(p.seances, 0)
    assert p.sid and p.odj.toPlainText().startswith("دراسة برنامج العمل السنوي")
    assert p.pv() and p.convocation() and len(ouverts) == 2
    assert ce.suivi(f.conn)[0]["nombre"] == 1
    f.close()


def test_icones_des_sections(app, config_tmp):
    """لكل قسم رئيسي أيقونة خاصة به (طلب المدير 2026-11-03)، والألوان بتباين كاف."""
    from idara.ui import fenetre as fe, icones, theme
    noms = [n for n, _ in fe.SECTIONS]
    assert set(noms) <= set(icones.DESSINS) and set(noms) <= set(icones.COULEURS)
    images = {n: icones.pixmap(n).toImage() for n in noms}
    assert all(not img.isNull() and img.pixelColor(24, 24).alpha() >= 0 for img in images.values())
    assert len({bytes(img.constBits()) for img in images.values()}) == len(noms)  # أيقونات مختلفة

    def lum(h):
        c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]

    def contraste(a, b):
        x, y = sorted((lum(a), lum(b)), reverse=True)
        return (x + 0.05) / (y + 0.05)

    for texte, fond in ((theme.BLANC, theme.VERT), (theme.ENCRE, theme.PLATRE), (theme.GRIS, theme.PLATRE),
                        (theme.ENCRE, theme.VERT_CLAIR), (theme.ROUGE_TEXTE, theme.ROUGE_CLAIR)):
        assert contraste(texte, fond) >= 4.5, (texte, fond)
    f = _fenetre_avec_eleves(config_tmp)
    assert all(not b.icon().isNull() for b in f.boutons)
    f.close()


def test_page_tanzim_tarbawi(app, config_tmp, monkeypatch):
    """التنظيم التربوي (طلب المدير 2026-11-03): فرع تحت التدبير التربوي، معطيات الأطر في صفحة واحدة، وزر التوليد."""
    from idara.services import bureautique
    from idara.services import etablissement as et
    from idara.services import personnel as rh
    from idara.ui.fenetre import SECTIONS
    ouverts = []
    monkeypatch.setattr(bureautique, "ouvrir", lambda p: ouverts.append(p))
    f = _fenetre_avec_eleves(config_tmp)
    td = dict(SECTIONS)["التدبير التربوي"]
    assert td[0] == ("التنظيم التربوي", "التنظيم التربوي")
    f.aller_a("التنظيم التربوي")
    p = f.page_tanzim
    assert f.page_courante() == "التنظيم التربوي" and not p.b_generer.isEnabled()
    assert "رمز المؤسسة" in p.l_manquants.text() and p.tables["structure"].rowCount() == 6
    e = et.lire_etablissement(f.conn)
    e.code_etab, e.telephone, e.commune_ar = "12345X", "0536000000", "الجماعة"
    et.enregistrer_etablissement(f.conn, e)
    d = next(x for x in rh.lister(f.conn) if x.categorie == "directeur")
    d.date_recrutement, d.date_fonction, d.date_affectation, d.ppr = "2000-09-16", "2018-09-01", "2018-09-01", "1000000"
    rh.enregistrer(f.conn, d)
    rh.enregistrer(f.conn, rh.Personnel(
        nom_ar="التجريبي", prenom_ar="سعيد", sexe="M", categorie="enseignant", ppr="2000001", grade="الدرجة الأولى",
        matiere="عربية", date_recrutement="2005-09-16", date_affectation="2015-09-01", date_grade="2020-01-01",
        echelon="7", date_echelon="2023-06-01", note_inspection=16.5, date_inspection="2025-03-10",
        inspecteur="المفتش", niveau_enseigne="الرابع", nb_eleves=20))
    p.insp["tanzim_insp_ar"].setText("المفتش أ")
    assert p.enregistrer_inspecteurs()
    p.rafraichir()
    assert p.l_manquants.isHidden() and p.b_generer.isEnabled(), p.l_manquants.text()
    assert p.tables["enseignants"].rowCount() == 1 and "16.5" in p.tables["enseignants"].item(0, 7).text()
    chemin = p.generer()
    assert chemin and chemin.exists() and ouverts == [chemin]
    f.close()


def test_page_examen_et_deliberations(app, config_tmp, monkeypatch, tmp_path):
    """ملفا المدير (2026-11-03): الامتحان (المحلي والإقليمي) ومحاضر نهاية الأسدوس، تحت «التقييم»."""
    from PySide6.QtWidgets import QTableWidgetItem
    from idara.services import bureautique
    from idara.services import evaluation as ev
    from idara.services import examens as exs
    from idara.services import personnel as rh
    from idara.ui.fenetre import SECTIONS
    from tests.fabrique_resultats import classeur_resultats
    from tests.test_examens import _liste_direction
    ouverts = []
    monkeypatch.setattr(bureautique, "ouvrir", lambda p: ouverts.append(p))
    f = _fenetre_avec_eleves(config_tmp)
    noms = [n for n, _ in dict(SECTIONS)["التقييم"]]
    assert noms == ["المراقبة المستمرة", "الامتحان", "استثمار النتائج", "مجالس الأقسام", "محاضر نهاية الأسدوس"]
    for i in range(1, 4):
        rh.enregistrer(f.conn, rh.Personnel(nom_ar="التجريبي", prenom_ar=f"أستاذ{i}", sexe="M", categorie="enseignant",
                                            ppr=f"400000{i}"))
    f.aller_a("الامتحان")
    p = f.page_examen
    assert f.page_courante() == "الامتحان" and not p.b_local.isHidden() and "جدولة المواد" in p.l_manquants.text()
    p.premier.setValue(11)
    assert p.preparer_local() and p.cands.rowCount() >= 1 and p.cands.item(0, 0).text() == "11"
    p.mats.cellWidget(0, 0).setEditText("اللغة العربية")
    p.mats.setItem(0, 1, QTableWidgetItem("10/06/2027"))
    p.mats.setItem(0, 2, QTableWidgetItem("08:30"))
    p.mats.setItem(0, 3, QTableWidgetItem("10:00"))
    assert p.enregistrer_matieres(), p.message.text()
    assert len(exs.matieres(f.conn, p.eid)) == 1
    p.c_roles[exs.ROLES[0]][0].setCurrentIndex(1)
    assert p.enregistrer_roles(), p.message.text()
    p.par_salle.setValue(1)
    assert p.distribuer(), p.message.text()
    assert p.surv.columnCount() == 2 and any(p.surv.item(i, 1).text() for i in range(p.surv.rowCount()))
    assert p.l_manquants.isHidden(), p.l_manquants.text()
    assert p.generer("listes") and p.generer("convocations_profs") and len(ouverts) == 2
    # الإقليمي: أرقام المديرية
    p.type.setCurrentIndex(p.type.findData("provincial"))
    assert p.b_local.isHidden() and not p.b_prov.isHidden()
    assert p.importer_provincial(_liste_direction(tmp_path / "d.xlsx")), p.message.text()
    assert p.cands.item(0, 0).text() == "7903" and "7903–7905" in p.l_cands.text()
    # محاضر نهاية الأسدوس
    fic = classeur_resultats(tmp_path / "r.xlsx", {"6APG-1": [("X000000005", "الاختبار آدم", [7.0] * 8)]},
                             niveau="السادس ابتدائي عام", semestres={"X000000005": (8.41, 7.95)},
                             examens={"X000000005": (8.72, 6.05)})
    ev.importer(f.conn, [fic])
    f.aller_a("محاضر نهاية الأسدوس")
    d = f.page_deliberations
    d.periode.setCurrentIndex(d.periode.findData("S2"))
    d.classe.setCurrentIndex(d.classe.findText("6APG-1"))
    assert d.table.rowCount() == 1 and d.table.item(0, 2).text() == "7.78" and d.table.item(0, 5).text() == "ينتقل"
    d.table.setItem(0, 7, QTableWidgetItem("التعليم الإعدادي"))
    assert d.generer_classe(), d.message.text()
    d.niveau.setCurrentIndex(d.niveau.findData("6AP"))
    assert d.generer_niveau(), d.message.text()
    f.close()


def test_lauha_qiyada_et_boutons_suppression(app, config_tmp):
    """اقتراح المدير (2026-11-03): لوحة القيادة بمؤشرات مبيانية، وزر لكل وحدة مدرسية، وأزرار حذف حمراء."""
    from PySide6.QtWidgets import QPushButton
    from idara.services import etablissement as et
    f = _fenetre_avec_eleves(config_tmp)
    t = f.tableau
    f.aller_a("لوحة القيادة")
    t.rafraichir()
    assert t.jauges[1].note.startswith("منقطعون 0")
    titres = [j.titre for j in t.jauges]
    assert titres[:3] == ["الغياب", "الهدر المدرسي", "الأنشطة الموازية"] and titres[3] == "الحاصلون على المعدل"
    assert t.jauges[0].taux is None and t.jauges[1].taux == 0, t.jauges[1].note
    e = et.lire_etablissement(f.conn)
    e.est_pionniere, e.type_etab = "1", "groupe"
    et.enregistrer_etablissement(f.conn, e)
    et.definir_unites(f.conn, ["الوحدة المركزية", "الوحدة الفرعية"])
    t.rafraichir()
    assert [j.titre for j in t.jauges][3:] == ["التعلمات الأساس: اللغة العربية", "التعلمات الأساس: اللغة الفرنسية",
                                             "التعلمات الأساس: الرياضيات"]
    unites = et.unites(f.conn)
    assert list(t.boutons_unites) == [None, *unites] and len(unites) >= 2
    t.boutons_unites[unites[-1]].click()
    assert t.unite == unites[-1] and t.boutons_unites[unites[-1]].isChecked()
    t.boutons_unites[None].click()
    assert t.unite is None
    rouges = [b for b in f.findChildren(QPushButton) if b.text().startswith("حذف")]
    assert rouges and all(b.objectName() == "danger" and not b.icon().isNull() for b in rouges)
    f.close()


def test_personnel_import_xml(app, config_tmp):
    from tests.fabrique_rh_xml import xml_rh
    f = _fenetre_avec_eleves(config_tmp)
    f.aller_a("الموارد البشرية")
    p = f.page_rh
    assert p.importer_xml(b"<x/>", valider=True) is None and "DATAIDENTIFPERSONNEL" in p.message.text()
    assert p.importer_xml(xml_rh(), valider=False) is None and p.liste.rowCount() == 1
    assert p.importer_xml(xml_rh(), valider=True) == {"ajoutes": 2, "maj": 0}
    assert p.liste.rowCount() == 3 and "أُضيف 2" in p.message.text()
    assert p.importer_xml(xml_rh(), valider=True) == {"ajoutes": 0, "maj": 0}
    assert p.liste.rowCount() == 3
    from idara.services import import_rh as irh
    d = __import__("idara.ui.page_personnel", fromlist=["x"]).DialogueImportRH(
        irh.comparer(f.conn, irh.lire_xml(xml_rh())), p)
    assert [d.table.item(i, 2).text() for i in range(3)] == ["دون تغيير", "دون تغيير", "لا يُستورد"]
    assert d.choisies() == []
    # ملاحظة المدير 2026-11-04: أستاذ مستورد (دون معطيات التفتيش) تُحفظ وحدته وساعاته
    from idara.services import etablissement as et
    from idara.services import personnel as rh
    pid = rh.lister(f.conn, "9000001")[0].id
    p.afficher(pid)
    unite = et.unites(f.conn)[-1]
    p.unite.setCurrentIndex(p.unite.findData(unite))
    p.c["heures_hebdo"].setText("30")
    assert p.enregistrer() == pid, p.message_bas.text()
    assert "آخر نقطة تفتيش" in p.message_bas.text()
    q = rh.lire(f.conn, pid)
    assert (q.unite, q.heures_hebdo) == (unite, 30)
    assert p.importer_xml(xml_rh(), valider=True) == {"ajoutes": 0, "maj": 0}
    q = rh.lire(f.conn, pid)
    assert (q.unite, q.heures_hebdo) == (unite, 30)
    f.close()



def test_programme_annuel_et_rappels(app, config_tmp, monkeypatch):
    from datetime import date
    from idara.services import bureautique
    from idara.services import calendrier as cal
    monkeypatch.setattr(bureautique, "ouvrir", lambda p: None)
    f = _fenetre_avec_eleves(config_tmp)
    f.aller_a("لوحة القيادة")
    f.tableau.rafraichir()
    assert isinstance(f.tableau.lignes_rappels, list)
    f.aller_a("برنامج العمل")
    p = f.page_calendrier
    assert "047.26" in p.l_mouqarrar.text()
    assert p.t_stations.rowCount() == len(cal.stations_ministerielles("2026/2027"))
    p.f_source.setCurrentIndex(p.f_source.findData("l"))
    assert p.t_stations.rowCount() == 0
    p.titre.setText("اجتماع مجلس التدبير")
    p.debut.setText("07/10/2026")
    assert p.enregistrer(True) is not None, p.message.text()
    assert p.t_stations.rowCount() == 1
    from idara.ui.saisie import selectionner
    selectionner(p.t_stations, 0)
    assert p.sid is not None and p.titre.text() == "اجتماع مجلس التدبير" and p.b_suppr.objectName() == "danger"
    p.titre.setText("")
    assert p.enregistrer(False) is None and "إجباري" in p.message.text()
    p.f_source.setCurrentIndex(0)
    p.afficher_rappels(date(2027, 1, 20))
    etats = [p.t_rappels.item(i, 0).text() for i in range(p.t_rappels.rowCount())]
    assert "جارية" in etats and "قادمة" in etats
    selectionner(p.t_rappels, 0)
    assert p.marquer_selection(p.t_rappels, True) == 1
    assert sum(1 for s in cal.stations(f.conn) if s.fait_le) == 1
    assert p.generer() is not None and "برنامج العمل السنوي" in p.message.text()
    f.close()


def test_reinitialisation_depuis_les_parametres(app, config_tmp):
    f = _fenetre_avec_eleves(config_tmp)
    f.aller_a("إعداد المؤسسة")
    b = f.page_etab.b_reinit
    assert b.objectName() == "danger" and not b.icon().isNull()
    assert f.reinitialiser("نعم") is None and "لم يُحذف" in f.page_etab.message.text()
    assert f.dossier.base.exists()
    recu = []
    f.reinitialisation.connect(recu.append)
    copie = f.reinitialiser("تصفير")
    assert copie is not None and copie.exists() and recu == [copie]
    assert not f.dossier.base.exists() and f.reinitialise



def test_themes_recherche_guide_statistiques(app, config_tmp):
    """اقتراح المدير 2026-11-06: اختيار المظهر، البحث في الصفحات، دليل الاستخدام، الإحصائيات."""
    from idara.services import config as config_srv
    from idara.ui import theme
    from idara.ui.fenetre import SECTIONS
    f = _fenetre_avec_eleves(config_tmp)
    # عدّاد الصفحات الفرعية بجانب كل قسم
    i = [t for t, _ in SECTIONS].index("الموارد البشرية")
    assert f.boutons[i].l_badge.text() == "4" and not f.boutons[i].l_badge.isHidden()
    # البحث
    assert f.filtrer_nav("رخص") == ["الرخص"] and not f.boutons[i].isHidden()
    assert all(b.isHidden() for k, b in enumerate(f.boutons) if k != i)
    assert {"محاضر نهاية الأسدوس", "مجالس الأقسام"} <= set(f.filtrer_nav("محضر"))
    assert f.filtrer_nav("كلمة غير موجودة") == [] and not f.aucun_resultat.isHidden()
    f.recherche.setText("الامتحان")
    f.ouvrir_premier_resultat()
    assert f.page_courante() == "الامتحان" and f.recherche.text() == ""
    assert all(not b.isHidden() for b in f.boutons)
    # المظهر: يُطبَّق ويُحفظ، والشريط الجانبي يُعاد بناؤه
    f.aller_a("إعداد المؤسسة")
    c = f.page_etab.choix_theme
    assert c.count() == 3
    c.setCurrentIndex(c.findData("marine"))
    assert theme.THEME_ACTUEL == "marine" and config_srv.lire_config()["theme"] == "marine"
    assert theme.NAV_FOND in f.styleSheet() and f.page_courante() == "إعداد المؤسسة"
    assert f.filtrer_nav("رخص") == ["الرخص"]
    f.filtrer_nav("")
    c.setCurrentIndex(c.findData("violet"))
    assert theme.THEME_ACTUEL == "violet"
    c.setCurrentIndex(c.findData("classique"))
    assert theme.THEME_ACTUEL == "classique"
    # الدليل
    f.aller_a("دليل الاستخدام")
    g = f.page_guide
    assert len(g.boutons) == 9
    av = g.avancement()
    assert av[0][0] and av[1][0] and "تلميذاً" in av[1][1]
    g.boutons[1].click()
    assert f.page_courante() == "الاستيراد من مسار"
    # الإحصائيات
    f.aller_a("الإحصائيات")
    p = f.page_stats
    assert p.analyse["total"] > 0 and p.niveaux and p.evolution == []
    p.c_matiere.setCurrentIndex(p.c_matiere.findData("ar"))
    assert p.matiere == "ar"
    # بطاقات الأرقام في لوحة القيادة
    f.aller_a("لوحة القيادة")
    assert len(f.tableau.tuiles) == 4
    f.close()



def test_inscriptions_frais(app, config_tmp):
    """تدبير التسجيلات (طلب المدير 2026-11-07)."""
    from idara.services import etablissement as et
    f = _fenetre_avec_eleves(config_tmp)
    f.aller_a("التسجيلات")
    p = f.page_inscriptions
    assert "حدّد وسط المؤسسة" in p.l_milieu.text() and p.table.rowCount() > 0
    e = et.lire_etablissement(f.conn)
    e.milieu = "urbain"
    et.enregistrer_etablissement(f.conn, e)
    p.rafraichir()
    assert "حضري" in p.l_milieu.text()
    n = p.table.rowCount()
    p.table.item(0, 3).setCheckState(Qt.Checked)
    assert p.totaux["elements"]["assurance"] == {"libelle": "التأمين المدرسي", "payes": 1, "montant_unitaire": 12,
                                                 "montant": 12}
    assert p.tout_cocher("sport") == n and p.totaux["elements"]["sport"]["montant"] == 10 * n
    assert p.totaux["total"] == 12 + 10 * n
    p.table.item(0, 4).setCheckState(Qt.Unchecked)
    assert p.totaux["elements"]["sport"]["payes"] == n - 1
    f.aller_a("إعداد المؤسسة")
    assert f.page_etab.f_etab.milieu.currentData() == "urbain"
    f.close()


def test_absences_mensuelles(app, config_tmp, monkeypatch):
    """تتبع الغياب الشهري (طلب المدير 2026-11-07)."""
    from idara.services import bureautique
    from idara.ui.page_absences import png_evolution
    monkeypatch.setattr(bureautique, "ouvrir", lambda p: None)
    f = _fenetre_avec_eleves(config_tmp)
    f.aller_a("تتبع الغياب")
    p = f.page_absences
    assert p.mois.count() == 10 and p.table.rowCount() >= 1
    p.mois.setCurrentIndex(p.mois.findData("2026-10"))
    assert p.s is None and p.generer() is None
    p.jours.setValue(20)
    i = next(k for k, x in enumerate(p.lignes) if x["effectif"] >= 1)   # قسم فيه تلميذ على الأقل
    p.table.item(i, 3).setText("1")
    p.table.item(i, 4).setText("1.5")
    assert p.enregistrer(), p.message.text()
    assert p.s["etablissement"]["jours_absence"] == 1.5 and "✓" in p.mois.currentText()
    p.table.item(i, 4).setText("abc")
    assert not p.enregistrer() and "أرقام" in p.message.text()
    png = png_evolution(p.evolution)
    assert png and png[:4] == b"\x89PNG"
    chemin = p.generer()
    assert chemin is not None and chemin.exists()
    f.aller_a("لوحة القيادة")
    assert "أكتوبر 2026" in f.tableau.jauges[0].note and f.tableau.jauges[0].taux is not None
    f.close()


def test_soutien_pedagogique(app, config_tmp, monkeypatch):
    """الدعم التربوي (طلب المدير 2026-11-07): مرحلة، مجموعة، تلاميذ، نتائج، حصة، ووثائق."""
    from idara.services import bureautique
    monkeypatch.setattr(bureautique, "ouvrir", lambda p: None)
    f = _fenetre_avec_eleves(config_tmp)
    with f.conn:
        f.conn.execute("INSERT INTO personnel(nom_ar, prenom_ar, sexe, categorie, ppr) VALUES "
                       "('التجريبية', 'سعاد', 'F', 'enseignant', '7654321')")
    f.aller_a("الدعم التربوي")
    p = f.page_soutien
    assert p.creer_groupe() is None and "مرحلة" in p.message.text()
    p.nom_etape.setText("الدعم المرحلي الأول")
    assert p.ajouter_etape()
    assert p.intervenant.count() >= 1 and p.categorie.count() >= 5
    gid = p.creer_groupe()
    assert gid and p.gid() == gid
    assert p.t_classe.rowCount() > 0
    p.cocher(list(range(min(2, p.t_classe.rowCount()))))
    n = p.affecter()
    assert n >= 1 and p.t_membres.rowCount() == n
    p.t_membres.item(0, 2).setText("3")
    p.t_membres.item(0, 3).setText("7")
    assert p.enregistrer_notes()
    assert p.t_membres.item(0, 4).text() == "تحسن"
    p.h_debut.setText("14:30")
    p.h_fin.setText("15:30")
    assert p.ajouter_seance() and p.t_edt.rowCount() == 1
    assert p.b["global"]["ameliores"] == 1
    for fn in (p.generer_registre, p.generer_programme, p.generer_rapport):
        assert fn() is not None, p.message.text()
    f.close()


def test_guide_jolie_tournee(app, config_tmp):
    """الجولة المصورة في الدليل: كل صفحة موجودة وكل لقطة متوفرة."""
    from idara.ui.fenetre import SECTIONS
    from idara.ui.page_guide import TOUR, image_guide
    pages = {p for _, fils in SECTIONS for p, _ in fils}
    for titre, img, _, _, page in TOUR:
        assert page is None or page in pages, titre
        assert image_guide(img) is not None, img
    f = _fenetre_avec_eleves(config_tmp)
    f.aller_a("دليل الاستخدام")
    assert len(f.page_guide.images) == len(TOUR)
    f.close()


def test_projet_etablissement(app, config_tmp, monkeypatch, tmp_path):
    """تتبع مشروع المؤسسة (قرار المدير 2026-11-07): المشروع، المستهدفات، الاستيراد من مسار، التتبع، التقارير."""
    from idara.services import bureautique
    from tests.fabrique_projet import rapport_plan_action
    monkeypatch.setattr(bureautique, "ouvrir", lambda p: None)
    f = _fenetre_avec_eleves(config_tmp)
    f.aller_a("مشروع المؤسسة")
    p = f.page_projet
    assert p.importer(tmp_path / "x.xlsx") is None and "سجّل المشروع" in p.message.text()
    p.debut.setCurrentIndex(p.debut.findData("2025/2026"))
    p.fin.setCurrentIndex(p.fin.findData("2027/2028"))
    pid = p.enregistrer_projet()
    assert pid and p.pid() == pid and set(p.graphs) == {"tarl", "hadar", "activites"}
    assert p.t_cibles.rowCount() == 3 * 4
    p.t_cibles.item(4, 2).setText("2.5")     # الهدر: المرجعية ثم السنوات
    p.t_cibles.item(5, 4).setText("abc")
    assert not p.enregistrer_cibles()
    p.t_cibles.item(5, 4).setText("2.8")
    assert p.enregistrer_cibles(), p.message.text()
    assert p.ind["hadar"]["annees"][0]["realise"] == 2.8
    r = p.importer(rapport_plan_action(tmp_path / "plan.xlsx"))
    assert r and r.ajoutees == 3 and p.t_ops.rowCount() == 3
    p.t_ops.cellWidget(0, 5).setCurrentIndex(p.t_ops.cellWidget(0, 5).findData("realisee"))
    p.t_ops.item(1, 6).setText("50")
    assert p.enregistrer_suivi(), p.message.text()
    assert p.synthese["par_statut"]["realisee"] == 1 and p.synthese["taux_global"] == 50
    assert p.generer() is not None and p.generer(final=True) is not None
    f.close()


def test_unites_et_vidage(app, config_tmp):
    """طلب المدير 2026-11-07: لوائح كل وحدة على حدة، وتفريغ مكوّن واحد من صفحته أو من الإعدادات."""
    from tests.fabrique_massar import classeur
    from tests.test_import_massar import AR
    from idara.services import import_eleves as imp
    from idara.services import vidage as vd
    from idara.ui.vidage_ui import LigneVidage
    f = _fenetre_avec_eleves(config_tmp)
    f.aller_a("الاستيراد من مسار")
    p = f.page_import
    assert list(p.barre_unites.boutons) == [None, "الوحدة المركزية", "وحدة فرعية"]
    assert p.c_unites.isVisibleTo(p) and p.t_unites.rowCount() >= 2
    p.barre_unites.boutons["الوحدة المركزية"].click()
    assert p.barre_unites.unite == "الوحدة المركزية" and p.t_unites.rowCount() == 0
    p.definir_fichiers([classeur(config_tmp / "ar2.xlsx", AR)])
    p.analyser()
    assert p.appliquer() is not None and "الوحدة المركزية" in p.message.text()
    assert p.t_unites.rowCount() >= 1
    # تصحيح وحدة قسم
    p.barre_unites.boutons[None].click()
    i = next(k for k, r in enumerate(p.lignes_unites) if r["unite"] == "الوحدة المركزية")
    cb = p.t_unites.cellWidget(i, 1)
    cb.setCurrentIndex(cb.findData("وحدة فرعية"))
    assert p.enregistrer_unites() == 1
    # التلاميذ حسب الوحدة
    f.aller_a("التلاميذ")
    e = f.page_eleves
    tous = e.resultats.rowCount()
    e.barre_unites.boutons["وحدة فرعية"].click()
    n_sub = e.resultats.rowCount()
    assert 0 < n_sub <= tous and "وحدة فرعية" in e.nb.text()
    e.barre_unites.boutons[None].click()
    assert e.resultats.rowCount() == tous
    # التفريغ من صفحة الاستيراد: وحدة واحدة
    f.aller_a("الاستيراد من مسار")
    ligne = next(w for w in p.findChildren(LigneVidage) if w.cle == "eleves")
    assert ligne.portee.isVisibleTo(ligne)
    ligne.portee.setCurrentIndex(ligne.portee.findData("وحدة فرعية"))
    assert ligne.vider(confirmer=False) is None and vd.compter(f.conn, "eleves") == tous
    assert ligne.vider(confirmer=True) == n_sub
    assert vd.compter(f.conn, "eleves") == tous - n_sub
    # الإعدادات: سطر لكل مكوّن
    f.aller_a("إعداد المؤسسة")
    lignes = {w.cle: w for w in f.page_etab.findChildren(LigneVidage)}
    assert set(lignes) == {c.cle for c in vd.COMPOSANTS}
    assert lignes["eleves"].vider(confirmer=True) is not None and vd.compter(f.conn, "eleves") == 0
    assert not lignes["eleves"].bouton.isEnabled()
    f.close()


def test_mouvements_par_unite_et_quitter(app, config_tmp):
    """طلب المدير 2026-11-09: حركية التلاميذ حسب الوحدة، «(ما قبل مسار)»، وزر إقفال البرنامج."""
    import sqlite3
    from idara.services import import_eleves as imp
    from idara.services import mouvements as mv
    f = _fenetre_avec_eleves(config_tmp)
    rep = imp.repartition_classes(f.conn)
    imp.affecter_unite(f.conn, rep[0]["id"], "الوحدة المركزية")
    code = f.conn.execute("SELECT e.code_massar FROM inscription i JOIN eleve e ON e.id=i.eleve_id WHERE i.classe_id=?",
                          (rep[0]["id"],)).fetchone()[0]
    mv.enregistrer(f.conn, mv.Mouvement("parti", code, date_mouvement="2026-10-01", etablissement="مدرسة أخرى"))
    f.aller_a("حركية التلاميذ")
    p = f.page_mouvements
    assert list(p.barre_unites.boutons) == [None, "الوحدة المركزية", "وحدة فرعية"]
    p.r_parti.setChecked(True)
    p.rafraichir()
    assert p.liste.rowCount() == 1
    p.barre_unites.boutons["وحدة فرعية"].click()
    assert p.liste.rowCount() == 0 and "مغادرون لم يُرسل" not in p.alertes.text()
    assert p.classe.count() == 1    # لا أقسام مسندة لهذه الوحدة
    p.barre_unites.boutons["الوحدة المركزية"].click()
    assert p.liste.rowCount() == 1 and p.classe.count() == 2
    # وافد جديد في وحدة دون قسم: يُطلب القسم
    p.nouveau()
    p.f_arrive.setChecked(True)
    p.code.setText("Y000000077")
    p.nom.setText("الوافد")
    p.prenom.setText("هبة")
    p.s_f.setChecked(True)
    p.date_mv.setText("02/10/2026")
    p.etab.setEditText("مدرسة أصلية")
    assert p.enregistrer() is None and "اختر قسمه" in p.message.text()
    p.classe.setCurrentIndex(1)
    assert p.enregistrer() is not None, p.message.text()
    p.r_arrive.setChecked(True)
    p.rafraichir()
    assert p.liste.rowCount() == 1
    assert f.boutons_pages["التلاميذ القدامى"].l_texte.text() == "التلاميذ القدامى (ما قبل مسار)"
    f.b_quitter.click()
    with pytest.raises(sqlite3.ProgrammingError):
        f.conn.execute("SELECT 1")


def test_pv_ressources_humaines(app, config_tmp, monkeypatch):
    """طلب المدير 2026-11-09: محضر الالتحاق، ومحضرا الدخول والخروج مع لائحة من لم يوقعوا."""
    from idara.services import bureautique
    from idara.services import personnel as rh
    monkeypatch.setattr(bureautique, "ouvrir", lambda p: None)
    f = _fenetre_avec_eleves(config_tmp)
    for i in range(3):
        rh.enregistrer(f.conn, rh.Personnel(
            nom_ar="التجريبي", prenom_ar=f"أستاذ{i}", sexe="M", categorie="enseignant", ppr=f"765432{i}",
            cin=f"AB{i}", cadre=rh.CADRES[0], fonction="التدريس", matiere="عربية", adresse="حي", telephone="0612345678"))
    f.aller_a("محاضر الموارد البشرية")
    p = f.page_pv_rh
    assert p.personnel.count() == 4 and p.cas.count() == 12
    assert p.enregistrer_prise() is None and "اختر الموظف" in p.message.text()
    p.personnel.setCurrentIndex(1)
    p.cas.setCurrentIndex(5)
    p.reference.setText("رقم 1 بتاريخ 01/07/2026")
    p.date_prise.setText("01/09/2026")
    assert p.enregistrer_prise() is not None, p.message.text()
    assert p.t_prises.rowCount() == 1
    assert p.t_sign.rowCount() == 3
    p.date_pv.setText("01/09/2026")
    p.cocher(1, "رخصة مرضية")
    r = p.generer_collectif()
    assert r is not None, p.message.text()
    assert "آخر المحاضر" in p.l_collectifs.text()
    f.close()
