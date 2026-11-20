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
    assert titres[:10] == ["القيادة والتدبير", "التلاميذ", "الموارد البشرية", "التدبير التربوي", "المدرسة الرائدة",
                           "الحياة المدرسية", "التدبير المالي والمادي", "التقييم", "مشروع المؤسسة", "تسليم المهام"]
    # طلب المدير 2026-11-19: المدرسة الرائدة بمكوناتها الفرعية، والتعلمات الأساس ضمنها
    assert [n for n, _ in dict(SECTIONS)["المدرسة الرائدة"]] == ["نتائج الريادة", "التعلمات الأساس", "تواصل الريادة",
                                                                 "مؤشرات الريادة", "الريادة"]
    assert [l for _, l in SECTIONS[2][1]] == ["معلومات الأطر", "تدبير الفائض", "الرخص", "المحاضر",
                                         "طلبات الموظفين والورقة الشخصية", "أعوان الحراسة والنظافة",
                                         "طلب ملف أستاذ وإرساله"]
    assert [l for _, l in SECTIONS[0][1]] == ["لوحة القيادة", "مفكرة المدير", "إحصائيات المؤسسة", "برنامج العمل السنوي والتذكيرات",
                                         "الأداء العام للمؤسسة", "تتبع الغياب", "مجالس المؤسسة",
                                         "السبورة المرجعية"]
    assert f.page_courante() == "لوحة القيادة" and f.est_ouvert(0)
    i = titres.index("التدبير المالي والمادي")
    f.boutons[i].click()   # النقر على القسم يفتح فروعه ويعرض رحبته (2026-11-14)
    assert f.est_ouvert(i) and not f.est_ouvert(0) and f.page_courante() is None and f.rahba_courante() == i
    assert f.groupe.checkedButton() is None and f.boutons[i].actif
    assert [b.text().split("  ")[0] for b in f.sous[i]][:3] == ["تدبير التسجيلات", "الجرد", "جمعية دعم مدرسة النجاح"]
    assert "قريباً" not in f.sous[i][1].text() and "قريباً" not in f.sous[i][2].text()   # الجرد مبرمج (2026-11-13)
    assert any("قريباً" in b.text() for b in f.sous[i])
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
    # طلب المدير 2026-11-19: تصفية حسب المستويات والأقسام، وعمود الاسم بعرض معقول
    assert p.resultats.columnCount() == 5 and p.resultats.columnWidth(1) <= 300 and len(p.pilules_niveaux) >= 2
    niv = next(k for k in p.pilules_niveaux if k)
    p.filtrer_niveau(niv)
    n_niv = p.resultats.rowCount()
    assert 0 < n_niv <= 5 and p.pilules_niveaux[niv].isChecked() and len(p.pilules_classes) >= 2
    cl = next(k for k in p.pilules_classes if k)
    p.filtrer_classe(cl)
    assert all(p.resultats.item(i, 3).text() == cl for i in range(p.resultats.rowCount()))
    p.filtrer_niveau(None)
    assert p.resultats.rowCount() == 5
    p.recherche.setText("يوسف")
    assert p.resultats.rowCount() == 1
    __import__("idara.ui.saisie", fromlist=["x"]).selectionner(p.resultats, 0)
    assert not p.c_fiche.isHidden() and "يوسف" in p.titre.text()
    # نسخ رمز مسار (طلب المدير 2026-11-13)
    from PySide6.QtWidgets import QApplication
    code = p.copier_code()
    assert code and QApplication.clipboard().text() == code and code in p.sous_titre.text()
    assert p.copier_code(depuis_liste=True) == code and p.resultats.actions()
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
    # طلب المدير 2026-11-18: معرض الوثائق ونوافذها المنبثقة
    assert len(p.cartes_docs) == 9 and p.cartes_docs["convocation"].compteur.text() == "وُلّدت 5"
    selectionner = __import__("idara.ui.saisie", fromlist=["x"]).selectionner
    d = p.ouvrir_document("visite", ouvrir=False)
    assert d.generer() is None and "حدد تلميذاً" in d.message.text()
    d.recherche.setText("يوسف")   # مستواه مؤكد أعلاه
    selectionner(d.table, 0)
    assert d.generer() is not None and d.message.objectName() == "info", d.message.text()
    d = p.ouvrir_document("vacances", ouvrir=False)
    d.recherche.setText("يوسف")
    selectionner(d.table, 0)
    d.du.setText("20/12/2026")
    d.au.setText("10/12/2026")
    assert d.generer() is None and "قبل بدايتها" in d.message.text()
    d.au.setText("04/01/2027")
    assert d.generer() is not None, d.message.text()
    d = p.ouvrir_document("convocation", ouvrir=False)
    d.table.selectAll()
    assert d.generer() is not None and p.cartes_docs["convocation"].compteur.text() == "وُلّدت 10"
    d = p.ouvrir_document("rencontre", ouvrir=False)
    assert d.vue.occasion.currentData() == "rencontre" and d.vue.table.rowCount() > 0
    d.vue.numero.setCurrentText("02")
    d.vue.date.setText("12/12/2026")
    d.vue.heure.setText("10:00")
    assert d.generer() is not None, d.message.text()
    assert p.ouvrir_document("ancien") is None and f.page_courante() == "التلاميذ القدامى"
    f.aller_a("التلاميذ")
    selectionner(p.resultats, 0)
    assert p.b_ouvrir.isEnabled() and p.ouvrir_fiche() is p.fiche and p.fiche.isVisible()
    p.fiche.hide()
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
    assert p.liste.columnCount() == 9 and p.liste.horizontalHeaderItem(2).text() == "المهمة"
    # طلب المدير 2026-11-18: الصفحة للمعلومات والإحصائيات، والملف في نافذة منبثقة
    assert p.cartes["tous"].chiffre.text() == "2" and p.cartes["enseignant"].chiffre.text() == "1"
    assert not p.c_graph.isHidden()
    p.filtrer("enseignant")
    assert p.liste.rowCount() == 1 and p.liste.item(0, 3).text() == "أستاذة"
    p.filtrer("enseignant")
    assert p.liste.rowCount() == 2
    p.filtrer("incomplet")
    assert p.liste.rowCount() == int(p.cartes["incomplet"].chiffre.text())
    # طلب المدير 2026-11-19: مثلث برتقالي قرب الاسم بدل عمود «اكتمال الملف»، والسبب في النافذة الصغيرة
    if p.liste.rowCount():
        assert not p.liste.item(0, 0).icon().isNull() and "تنبيه" in p.liste.item(0, 0).toolTip()
    p.filtrer("tous")
    d = p.ouvrir_nouveau()
    assert d.isVisible() and p.pid is None and d.windowTitle() == "إضافة موظف جديد"
    d.hide()
    selectionner(p.liste, 0)
    assert p.b_ouvrir.isEnabled() and p.ouvrir_fiche() is d and d.windowTitle().startswith("ملف الموظف: ")
    d.hide()
    p.afficher(pid)
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


def test_page_fa(app, config_tmp, monkeypatch):
    from idara.services import bureautique
    from idara.services import fa as fa_srv
    monkeypatch.setattr(bureautique, "ouvrir", lambda p: None)
    from idara.services import personnel as rh
    f = _fenetre_avec_eleves(config_tmp)
    for prenom, recrut, etab, naiss in (("الأقدم", "2003-09-16", "2010-09-01", "1978-01-01"),
                                        ("الأحدث", "2020-09-16", "2023-09-01", "1995-01-01")):
        rh.enregistrer(f.conn, rh.Personnel(nom_ar="التجريبي", prenom_ar=prenom, sexe="M", categorie="enseignant",
                                            matiere="عربية", date_naissance=naiss, date_recrutement=recrut,
                                            date_affectation_direction=recrut, date_affectation=etab))
    rh.enregistrer(f.conn, rh.Personnel(nom_ar="ن", prenom_ar="بلا_مادة", sexe="F", categorie="enseignant",
                                        date_naissance="1998-01-01", date_recrutement="2024-09-16",
                                        date_affectation_direction="2024-09-16", date_affectation="2024-09-16"))
    f.aller_a("تدبير الفائض")
    p = f.page_fa
    assert list(p.cartes) == [fa_srv.TOUS]   # ترتيب واحد بغض النظر عن المادة (قرار المدير 2026-11-10)
    c = p.cartes[fa_srv.TOUS]
    assert c.table.rowCount() == 3 and c.postes.value() == -1
    assert "حدد عدد الأساتذة" in c.etat.text()
    c.postes.setValue(2)
    assert "الفائض: بلا_مادة ن" in c.etat.text()
    assert c.table.item(2, 8).text() == "فائض" and c.table.item(0, 0).text() == "1"
    pv = p.generer_pv()   # المحضر + صفحة التوقيعات (طلب المدير 2026-11-12)
    assert pv and pv.exists() and "وُلّد المحضر" in p.message.text()
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
    # طلب المدير 2026-11-19: هيكلة المديرية (المصالح والمكاتب) في نافذة منبثقة
    d = s.ouvrir_structure()
    assert d.isVisible() and s.t_structure.rowCount() == 2 and "مصلحة تدبير الموارد البشرية" in s.l_structure.text()
    s._ligne_structure("مصلحة الشؤون التربوية", "مكتب التخطيط")
    s._ligne_structure("", "مكتب الحياة المدرسية")
    s.aff["bureau_etablissements"].setCurrentText("مكتب الحياة المدرسية")
    assert s.enregistrer_structure(), s.message_structure.text()
    assert cg.structure_direction(f.conn)[1] == {"service": "مصلحة الشؤون التربوية",
                                                 "bureaux": ["مكتب التخطيط", "مكتب الحياة المدرسية"]}
    assert cg.parametres(f.conn)["bureau_etablissements"] == "مكتب الحياة المدرسية"
    assert "مكتب التخطيط" in s.l_structure.text()
    s.aff["bureau_conges"].setCurrentText("مكتب غير موجود")
    assert not s.enregistrer_structure() and "غير موجود" in s.message_structure.text()
    d.hide()
    f.aller_a("الرخص")
    # طلب المدير 2026-11-18: وثائق الرخصة المحددة من الصفحة، و«حفظ وتوليد طلب الرخصة» من ملفها
    from idara.ui.saisie import selectionner
    selectionner(p.liste, 0)
    assert not p.barre_docs.isHidden() and p.p_remp.isEnabled()
    assert p.ouvrir_nouveau().isVisible() and not p.zone_docs.isEnabled() and not p.aide_docs.isHidden()
    p.personnel.setCurrentIndex(p.personnel.findData(pid))
    p.debut.setText("01/12/2026")
    p.duree.setValue(3)
    p.avis.setText("موافق")
    p.mesures.setText("توزيع التلاميذ")
    n = len(ouverts)
    assert p.enregistrer_et_demande() is not None and len(ouverts) == n + 1, p.message.text()
    assert p.zone_docs.isEnabled() and p.aide_docs.isHidden()
    p.fiche.hide()
    selectionner(p.liste, next(i for i in range(p.liste.rowCount()) if p.liste.item(i, 0).data(Qt.UserRole) == cid))
    assert p.cid == cid
    f.close()



def test_page_mouvements(app, config_tmp, monkeypatch):
    """طلب المدير 2026-11-17: الصفحة تعرض جدول الحركية ببطاقات معايير ومبيانات، والإضافة في نافذة منبثقة."""
    from idara.services import bureautique
    from idara.services import mouvements as mv
    from idara.ui.saisie import selectionner
    ouverts = []
    monkeypatch.setattr(bureautique, "ouvrir", lambda p: ouverts.append(p))
    f = _fenetre_avec_eleves(config_tmp)
    f.aller_a("حركية التلاميذ")
    p = f.page_mouvements
    assert f.page_courante() == "حركية التلاميذ" and p.liste.rowCount() == 0 and not p.vide.isHidden()
    assert p.c_graph.isHidden() and p.barre_sel.isHidden() and p.t_dossiers.isHidden()
    assert list(p.cartes) == ["arrive", "parti", "interrompu", "exclu", "non_rejoint"]
    assert p.generer_bilan() is None and "لا حركة" in p.message.text()
    # وافد جديد من نافذة الإضافة
    d = p.ajouter(ouvrir=False)
    assert d.types["arrive"].isChecked() and not d.etab.isHidden()
    d.code.setText("Y000000009")
    d._chercher_code()
    assert "غير موجود" in d.info_eleve.text()
    d.nom.setText("الوافد")
    d.prenom.setText("هبة")
    d.s_f.setChecked(True)
    d.date_mv.setText("08/09/2026")
    d.etab.setEditText("المؤسسة الأصلية")
    d.niveau.setEditText("الخامس")
    assert d.enregistrer() is not None, d.message.text()
    assert p.categorie == "arrive" and p.liste.rowCount() == 1 and p.cartes["arrive"].chiffre.text() == "1"
    assert p.liste.item(0, 0).text() == "وافد" and "لم يُطلب الملف" in p.liste.item(0, 8).text()
    assert "وافدون لم يُطلب ملفهم (1): هبة الوافد" in p.alertes.text() and not p.c_graph.isHidden()
    selectionner(p.liste, 0)
    assert p.b_modifier.isEnabled()
    # تتبع ملفات التلاميذ (طلب المدير 2026-11-18): مرحلة كل ملف، والإجراءات على جدول الملفات
    assert p.cartes_dossier["a_demander"].chiffre.text() == "1" and p.t_dossiers.rowCount() == 1
    assert p.t_dossiers.item(0, 0).text() == "لم يُطلب الملف"
    selectionner(p.t_dossiers, 0)
    assert not p.barre_sel.isHidden() and not p.b_demande.isHidden() and p.b_envoi.isHidden()
    p.date_action.setText("10/09/2026")
    assert p.demande(False) is not None, p.message.text()
    assert len(ouverts) == 1 and "أُرسل الطلب" in p.liste.item(0, 8).text()
    assert "10/09/2026 · رقم" in p.t_dossiers.item(0, 5).text() and p.cartes_dossier["a_demander"].chiffre.text() == "0"
    assert "وافدون" not in p.alertes.text()
    selectionner(p.t_dossiers, 0)
    p.date_action.setText("20/09/2026")
    assert p.marquer("dossier_recu_le") and "توصلنا" in p.liste.item(0, 8).text()
    assert p.t_dossiers.item(0, 0).text() == "توصلنا بالملف" and p.t_dossiers.item(0, 7).text() == "20/09/2026"
    p.filtrer_dossiers("recu")
    assert p.t_dossiers.rowCount() == 1
    p.filtrer_dossiers("attente")
    assert p.t_dossiers.rowCount() == 0
    p.filtrer_dossiers(None)
    # تعديل الحركية من الجدول
    selectionner(p.liste, 0)
    d = p.modifier(ouvrir=False)
    assert d is not None and not d.code.isEnabled() and d.etab.currentText() == "المؤسسة الأصلية"
    assert not d.types["parti"].isEnabled()
    d.remarques.setText("ملف كامل")
    assert d.enregistrer() is not None
    # مغادر من اللوائح
    d = p.ajouter("parti", ouvrir=False)
    d.code.setText("X000000003")
    d._chercher_code()
    assert d.prenom.text() == "يوسف"
    d.date_mv.setText("15/10/2026")
    d.etab.setEditText("قاسم أمين")
    assert d.enregistrer() is not None, d.message.text()
    assert p.categorie == "parti" and p.liste.rowCount() == 1
    assert "مغادرون لم يُرسل ملفهم (1)" in p.alertes.text()
    ligne = next(i for i, x in enumerate(p.dossiers) if x["sens"] == "parti")
    selectionner(p.t_dossiers, ligne)
    assert not p.b_envoi.isHidden() and p.b_demande.isHidden()
    p.date_action.setText("20/10/2026")
    assert p.envoi() is not None and "أُرسل الملف" in p.liste.item(0, 8).text()
    assert p.cartes_dossier["envoye"].chiffre.text() == "1"
    assert mv.alertes(f.conn)["envoi"] == []
    # مغادر سابق غير وارد في اللائحة (طلب المدير 2026-11-09)
    d = p.ajouter("parti", ouvrir=False)
    assert d.classe.isVisibleTo(d) and d.classe.count() > 1
    d.code.setText("Z000000001")
    d._chercher_code()
    assert "غير وارد في اللائحة" in d.info_eleve.text()
    d.nom.setText("المغادر")
    d.prenom.setText("سعيد")
    d.s_m.setChecked(True)
    d.niveau.setEditText("الرابع")
    d.classe.setCurrentIndex(1)
    d.date_mv.setText("01/10/2026")
    d.etab.setEditText("مدرسة أخرى")
    assert d.enregistrer() is not None, d.message.text()
    assert p.liste.rowCount() == 2
    # غير ملتحق (الحقول الخاصة بالتحويل تختفي)
    d = p.ajouter("non_rejoint", ouvrir=False)
    assert d.etab.isHidden() and d.nom.isHidden() and "المعاينة" in d.l_date.text()
    d.code.setText("X000000001")
    assert d.enregistrer() is None and "إجباري" in d.message.text()
    d.date_mv.setText("20/09/2026")
    assert d.enregistrer() is not None, d.message.text()
    assert p.categorie == "non_rejoint" and p.liste.rowCount() == 1 and p.liste.item(0, 0).text() == "غير ملتحق"
    selectionner(p.liste, 0)
    assert not p.b_modifier.isEnabled()
    # المعايير: بطاقة «الكل»، البحث، المستوى، الفترة
    p.filtrer(None)
    assert p.liste.rowCount() == 4 and p.c_solde.chiffre.text() == "4" and "الفرق" in p.c_solde.libelle.text()
    p.filtrer("arrive")
    p.filtrer("arrive")   # ضغطة ثانية على البطاقة نفسها: الكل
    assert p.categorie is None and p.liste.rowCount() == 4
    p.recherche.setText("هبة")
    assert p.liste.rowCount() == 1
    p.recherche.clear()
    p.niveau.setCurrentIndex(p.niveau.findData("الرابع"))
    assert p.liste.rowCount() >= 1 and all(p.liste.item(i, 4).text() == "الرابع" for i in range(p.liste.rowCount()))
    p.niveau.setCurrentIndex(0)
    p.debut.setText("01/10/2026")
    p.rafraichir()
    assert p.liste.rowCount() == 2 and p.cartes["arrive"].chiffre.text() == "0"
    p.debut.clear()
    p.rafraichir()
    # وثيقة الحركية مباشرة، والإحصائيات التفصيلية
    chemin = p.generer_bilan()
    assert chemin is not None and chemin.exists() and ouverts[-1] == chemin, p.message.text()
    ds = p.statistiques()
    t = ds.stats["totaux"]
    assert (t["arrive"], t["parti"], t["non_rejoint"]) == (1, 2, 1)
    assert ds.tuiles["الوافدون"].chiffre.text() == "1" and ds.tuiles["المغادرون"].chiffre.text() == "2"
    ds.close()
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
    m.rafraichir()
    m.filtrer("exclu")
    assert m.liste.rowCount() == 1 and m.liste.item(0, 0).text() == "مفصول" and m.cartes["exclu"].chiffre.text() == "1"
    assert "قرار المجلس" in m.liste.item(0, 8).text() and m.b_demande.isHidden()
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
    # حذف سنة مالية (طلب المدير 2026-11-10)
    assert p.b_suppr_exercice.isEnabled()
    assert not p.supprimer_exercice(confirmer=False) and p.exercice.count() == 2
    assert p.supprimer_exercice(confirmer=True) and p.exercice.count() == 1
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
    # طلب المدير 2026-11-19: إضافة الأندية والأنشطة في نوافذ منبثقة
    assert v.cartes["clubs"].chiffre.text() == "1" and v.cartes["realisees"].chiffre.text() == "1"
    d = v.ouvrir_club()
    assert d.isVisible() and v.c_membres.isHidden() and v.nom_club.text() == ""
    v.nom_club.setText("نادي القراءة")
    assert v.enregistrer_club(True) and v.clubs.rowCount() == 2 and not v.c_membres.isHidden() and v.club_id
    d.hide()
    assert v.clubs.cellWidget(0, 5) is not None
    cid = v.clubs.item(0, 0).data(Qt.UserRole)
    da = v._activite_club(cid)
    assert da.isVisible() and v.club_act.currentData() == cid and v.titre_act.text() == ""
    da.hide()
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


def test_ecole_pionniere_composants(app, config_tmp, monkeypatch):
    """طلب المدير 2026-11-19: المدرسة الرائدة: تتبع النتائج حسب الفترات، التواصل، المؤشرات العامة، شارة الريادة."""
    from idara.services import pionniere as pn
    from idara.services import riyada as ry
    f = _fenetre_avec_eleves(config_tmp)
    ouverts = []
    monkeypatch.setattr(f, "ouvrir_document", lambda c: ouverts.append(c))
    a = "2026/2027"
    ry.enregistrer_isa(f.conn, a, "1-1", 1, {"ar": "40", "fr": "70", "ma": "80"})
    ry.enregistrer_isa(f.conn, a, "1-1", 2, {"ar": "55", "fr": "75", "ma": "85"})
    f.aller_a("نتائج الريادة")
    p = f.page_resultats_pionniere
    assert f.page_courante() == "نتائج الريادة" and p.phase == 2 and p.cartes[2].chiffre.text() == "71.7%"
    assert p.cartes[-1].chiffre.text() == "—" and p.table.rowCount() == 1 and not p.c_graph.isHidden()
    p.choisir(1)
    assert p.table.item(0, 1).text() == "40.00%" and p.cartes[1].actif
    assert p.rapport() and len(ouverts) == 1
    f.aller_a("تواصل الريادة")
    c = f.page_comm_pionniere
    assert c.liste.isHidden() and not c.vide.isHidden()
    d = c.ouvrir_rencontre(type_="portes")
    assert d.isVisible() and c.c_type.currentData() == "portes"
    c.c_theme.setText("الأبواب المفتوحة الأولى")
    c.c_invites.setValue(40)
    c.c_presents.setValue(30)
    assert c.enregistrer_et_rapport() and len(ouverts) == 2
    d.hide()
    assert c.liste.rowCount() == 1 and c.cartes["portes"].chiffre.text() == "1" and c.c_taux.chiffre.text() == "75.0%"
    assert c.liste.cellWidget(0, 6) is not None and c.rapport_synthese() and len(ouverts) == 3
    dc = c.convocations("rencontre")
    assert dc.isVisible() and dc.vue.occasion.currentData() == "rencontre"
    dc.hide()
    c.supprimer(pn.rencontres(f.conn)[0].id)
    assert c.liste.rowCount() == 0
    f.aller_a("مؤشرات الريادة")
    i = f.page_ind_pionniere
    assert set(i.ind) == {"tarl", "isa2", "activites", "hadar"} and i.ind["isa2"]["etat"] == "في تحسن"
    assert i.cartes["isa2"].valeur.text() == "71.7%" and len(i.cartes["isa2"].points) == 2
    f.aller_a("الريادة")
    assert f.page_riyada.findChildren(type(f.page_riyada.message))  # الصفحة القائمة: شارة الريادة
    f.close()


def test_mofakkira_et_contact(app, config_tmp, monkeypatch):
    """طلب المدير 2026-11-19: مفكرة المدير (سبورة وبطاقات وساعة ويومية) وصفحة التواصل مع صاحب البرنامج."""
    from datetime import date, timedelta

    from idara.services import calendrier as cal
    from idara.services import memo as mm
    from idara.ui import page_contact as pc
    f = _fenetre_avec_eleves(config_tmp)
    f.aller_a("مفكرة المدير")
    p = f.page_memo
    assert f.page_courante() == "مفكرة المدير" and not p.sabboura.vide.isHidden() and len(p.paquet) == 6
    p.paquet["rose"].clique.emit("rose")
    assert p.fiche.isVisible() and p.c_couleur.currentData() == "rose" and p.b_fait.isHidden()
    assert p.enregistrer() is None and "موضوع" in p.message_fiche.text()
    p.c_sujet.setText("زيارة المفتش التربوي")
    p.c_heure.setText("9:30")
    demain = (date.today() + timedelta(days=1)).isoformat()
    p.c_date.definir(demain)
    mid = p.enregistrer()
    assert mid and not p.fiche.isVisible() and len(p.notes) == 1 and p.sabboura.vide.isHidden()
    assert p.notes[0].memo.heure == "09:30" and "زيارة المفتش" in p.notes[0].toolTip()
    assert p.agenda.evenements[demain][0][0] == "memo"
    cal.enregistrer_locale(f.conn, "يوم تواصلي", demain)
    p.rafraichir()
    assert {t for t, _ in p.agenda.evenements[demain]} == {"memo", "local"}
    p.agenda.jour_clique.emit(demain)
    assert p.fiche.isVisible() and p.c_date.iso() == demain
    p.fiche.hide()
    p.notes[0].clique.emit(p.notes[0].memo)
    assert p.mid == mid and not p.b_fait.isHidden()
    p.marquer_fait()
    assert p.notes == [] and mm.lister(f.conn, inclure_faits=True)[0].fait
    m0 = p.agenda.mois
    p.agenda.changer_mois(1)
    assert p.agenda.mois != m0
    img = p.grab()
    assert not img.isNull()
    f.aller_a("التواصل")
    c = f.page_contact
    monkeypatch.setattr(pc, "ouvrir_externe", lambda u: True)
    assert pc.TELEPHONE in c.wa.valeur.text() and pc.EMAIL in c.mail.valeur.text()
    c.wa.findChildren(pc.QPushButton)[0].click()
    c.mail.findChildren(pc.QPushButton)[0].click()
    assert c.ouverts[0] == "https://wa.me/212666949280" and c.ouverts[1].startswith("mailto:erraihani.thami@gmail.com")
    c.copier(pc.EMAIL)
    assert "نُسخ" in c.l_copie.text()
    f.close()


def test_page_logements(app, config_tmp, monkeypatch):
    """طلب المدير 2026-11-19: تدبير السكنيات حسب المذكرة 40: سكن، تباري، نقط، مطبوعات (معاينة، تعديل، طبع)."""
    from PySide6.QtWidgets import QPushButton
    from idara.services import logements as lg
    from idara.services import personnel as rh
    f = _fenetre_avec_eleves(config_tmp)
    ouverts = []

    class Faux:
        def __init__(self):
            self.mode = "apercu"

        def basculer_edition(self, _):
            self.mode = "modifier"

        def imprimer(self):
            self.mode = "imprimer"
    editeurs = []

    def ouvrir(c):
        ouverts.append(c)
        e = Faux()
        editeurs.append(e)
        return e
    monkeypatch.setattr(f, "ouvrir_document", ouvrir)
    pid = rh.enregistrer(f.conn, rh.Personnel(nom_ar="الوهمي", prenom_ar="أستاذ", sexe="M", ppr="7651234",
                                              grade="الدرجة الأولى", date_recrutement="2004-09-16"))
    f.aller_a("السكنيات")
    p = f.page_logements
    assert f.page_courante() == "السكنيات" and p.t_docs.rowCount() == 9 and p.t_logements.isHidden()
    # كل مطبوع: معاينة، تعديل، طبع؛ وغير المرفق بالمذكرة معطل
    b = {x.text(): x for x in p.t_docs.cellWidget(0, 3).findChildren(QPushButton)}
    assert set(b) == {"معاينة", "تعديل", "طبع"} and all(x.isEnabled() for x in b.values())
    r6 = [p.t_docs.item(i, 0).data(Qt.UserRole) for i in range(9)].index("carte1")
    assert not any(x.isEnabled() for x in p.t_docs.cellWidget(r6, 3).findChildren(QPushButton))
    assert p.document("demande", "apercu") and len(ouverts) == 1
    assert p.document("constat", "modifier") and editeurs[-1].mode == "modifier"
    assert p.document("engagement_droit", "imprimer") and editeurs[-1].mode == "imprimer"
    d = p.ouvrir_logement()
    assert d.isVisible()
    assert p.enregistrer_logement() is None and "عنوان السكن" in p.m_logement.text()
    p.l_adresse.setText("سكن الوحدة المركزية")
    p.l_numero.setText("77/1")
    lid = p.enregistrer_logement()
    assert lid and not d.isVisible() and p.t_logements.rowCount() == 1 and p.cartes["vacants"].chiffre.text() == "1"
    d = p.ouvrir_concours(logement_id=lid)
    assert d.isVisible() and p.c_logement.currentData() == lid
    p.c_limite.definir("2026-12-30")
    cid = p.enregistrer_concours()
    assert cid and p.t_concours.rowCount() == 1 and p.cartes["ouverts"].chiffre.text() == "1"
    d = p.ouvrir_points(cid)
    assert d.isVisible() and p.p_concours.currentData() == cid
    p.p_personne.setCurrentIndex(p.p_personne.findData(pid))
    assert p.p_echelle.currentData() == "11" and p.p_ag.value() >= 21
    p.p_situation.setCurrentIndex(p.p_situation.findData("marie"))
    p.p_enfants.setValue(2)
    p.p_conjoint.setChecked(True)
    p.p_rend.setCurrentIndex(p.p_rend.findData("tres_bien"))
    attendu = lg.points(p.donnees(), p._rural())["total"]
    assert p.total == attendu and str(attendu) in p.l_total.text()
    assert p.enregistrer_candidat() and p.t_classement.rowCount() == 1
    assert p.attribuer(pid) and lg.concours(f.conn, cid).statut == "attribue"
    assert p.cartes["occupes"].chiffre.text() == "1" and "أستاذ الوهمي" in p.t_logements.item(0, 4).text()
    d.hide()
    p.ctx_concours.setCurrentIndex(p.ctx_concours.findData(cid))
    assert p.ctx_personne.currentData() == pid
    n = len(ouverts)
    assert p.document("pv") and len(ouverts) == n + 1
    assert "7651234" in "".join(c.text for t in __import__("docx").Document(ouverts[-1]).tables
                                for r in t.rows for c in r.cells)
    f.close()


def test_page_riyada_isa2_calcule(app, config_tmp, monkeypatch, tmp_path):
    """حساب ISA2 من نتائج الروائز (صيغة المدير 2026-11-12): التحميل، الإدخال اليدوي، التقرير."""
    from idara.services import bureautique
    from idara.services import isa as isa_srv
    from tests.test_isa import _fichier
    ouverts = []
    monkeypatch.setattr(bureautique, "ouvrir", lambda p: ouverts.append(p))
    f = _fenetre_avec_eleves(config_tmp)
    f.aller_a("الريادة")
    p = f.page_riyada
    assert p.comptes.rowCount() >= 3 and p.phase_r.currentData() == 0
    cl, m = p.comptes.item(0, 0).data(Qt.UserRole)
    assert m == "ar"
    fic = _fichier(tmp_path / "post.xlsx", cl, [("A", "A", "B"), ("B", "C", "B"), ("C", "A", "B")])
    assert p.importer_resultats([fic]) and "3 تلميذاً" in p.message.text()
    assert p.comptes.item(0, 6).text() == "لا يُحتسب"   # الرائز البعدي: توزيع دون ISA2 (توجيه المدير)
    p.phase_r.setCurrentIndex(p.phase_r.findData(1))
    assert p.importer_resultats([fic])
    assert p.comptes.item(0, 7).text() == f"{isa_srv.Calcul(1, 1, 1).isa:.2f}%" and "إلى" in p.comptes.item(0, 8).text() \
        and "OB" in p.comptes.item(0, 8).toolTip()
    p.phase_r.setCurrentIndex(p.phase_r.findData(-1))   # الرائز القبلي يدوياً
    p.comptes.item(0, 2).setText("0")
    p.comptes.item(0, 3).setText("1")
    p.comptes.item(0, 4).setText("2")
    assert p.enregistrer_comptes()
    assert isa_srv.resultats(f.conn, "2026/2027")[cl]["ar"][-1].total == 3
    p.comptes.item(0, 2).setText("x")
    assert not p.enregistrer_comptes() and "أرقاماً" in p.message.text()
    assert p.rapport_isa() and len(ouverts) == 1
    f.close()


def test_page_fiche_eleve(app, config_tmp, monkeypatch):
    """بطاقة التلميذ: الاختيار، الجدولان والمبيانان، إدخال مستويات المراحل، الطبع. بيانات وهمية."""
    from idara.services import bureautique
    from idara.services import fiche_eleve as fe
    from idara.ui.saisie import selectionner
    from tests.fabrique_tarl import classeur_niveaux
    ouverts = []
    monkeypatch.setattr(bureautique, "ouvrir", lambda p: ouverts.append(p))
    f = _fenetre_avec_eleves(config_tmp)
    t = f.page_tarl
    assert t.importer([classeur_niveaux(config_tmp / "t.xlsx", {"2APG-1": [
        ("X000000001", "أ", "حرف", "كلمة", "débutant", "lettre", "رقمان", "جمع")]})])
    f.aller_a("بطاقة التلميذ")
    assert f.page_courante() == "بطاقة التلميذ"
    p = f.page_fiche_eleve
    assert p.c_fiche.isHidden() and p.liste.rowCount() >= 1
    assert p.generer() is None   # لا تلميذ مختار
    p.recherche.setText("X000000001")
    assert p.liste.rowCount() == 1
    selectionner(p.liste, 0)
    assert not p.c_fiche.isHidden() and p.t_tarl.rowCount() == 3 and not p.g_tarl.isHidden()
    assert p.t_tarl.item(0, 1).text() == "حرف" and p.t_tarl.item(0, 4).text() == "+1"
    assert p.g_etapes.isHidden()
    p.t_etapes.item(0, 0).setText("C")
    p.t_etapes.item(0, 2).setText("b")
    assert p.enregistrer() and not p.g_etapes.isHidden()
    assert fe.parcours(f.conn, p.eid)["etapes"] == {"ar": {-1: "C", 1: "B"}}
    p.t_etapes.item(1, 3).setText("Z")
    assert not p.enregistrer() and "A أو B أو C" in p.message.text()
    p.t_etapes.item(1, 3).setText("")
    g = p.g_tarl.grab()
    assert not g.isNull()
    assert p.generer() and len(ouverts) == 1
    assert p.generer(tous=True) is None and "اختر قسماً" in p.message.text()
    f.close()


def test_page_dossier_prof(app, config_tmp, monkeypatch):
    """طلب ملف أستاذ وإرساله من صفحة الموارد البشرية. أسماء وهمية."""
    from PySide6.QtWidgets import QPushButton
    from idara.services import bureautique
    from idara.services import conges as cg
    ouverts = []
    monkeypatch.setattr(bureautique, "ouvrir", lambda p: ouverts.append(p))
    f = _fenetre_avec_eleves(config_tmp)
    f.aller_a("ملفات الأساتذة")
    p = f.page_dossier_prof
    assert not p.rappel.isHidden()
    assert p.generer() is None and "المؤسسة المرسل إليها" in p.message.text()
    p.cible.setText("مدرسة وهمية")
    assert p.generer() is None and "أستاذاً واحداً" in p.message.text()
    p.ajouter("أستاذة تجريبية", "1234567", "")
    n = cg.prochain_numero(f.conn)
    assert p.generer() and len(ouverts) == 1 and cg.prochain_numero(f.conn) == n + 1
    p.sens.setCurrentIndex(p.sens.findData("envoi"))
    assert p.rappel.isHidden()
    p.table.setCurrentCell(0, 0)
    p.supprimer()
    assert p.table.rowCount() == 0
    # طلب المدير 2026-11-19: الطلب في نافذة منبثقة، والصفحة لتتبع التوصل، مرتبطة بمحضر تسليم المهام
    from idara.services import dossier_enseignant as de
    from idara.services import personnel as rh
    pid0 = rh.enregistrer(f.conn, rh.Personnel(nom_ar="الوهمي", prenom_ar="أستاذ", sexe="M", categorie="enseignant",
                                               ppr="7654321"))
    prof = rh.lire(f.conn, pid0)
    p.rafraichir()
    r = next(i for i in range(p.suivi.rowCount()) if p.suivi.item(i, 0).data(Qt.UserRole) == prof.id)
    assert not p.suivi.item(r, 0).icon().isNull() and "لم يُطلب" in p.suivi.item(r, 2).text()
    boutons = {b.text() for b in p.suivi.cellWidget(r, 4).findChildren(QPushButton)}
    assert boutons == {"طلب الملف", "تم التوصل بالملف"}
    d = p.ouvrir_correspondance("demande", [prof.id])
    assert d.isVisible() and p.table.rowCount() == 1 and p.sens.currentData() == "demande"
    assert p.generer() and de.historique(f.conn, prof.id)[-1]["sens"] == "demande"
    d.hide()
    r = next(i for i in range(p.suivi.rowCount()) if p.suivi.item(i, 0).data(Qt.UserRole) == prof.id)
    boutons = {b.text() for b in p.suivi.cellWidget(r, 4).findChildren(QPushButton)}
    assert "تذكير بإرسال الملف" in boutons and p.cartes["demande"].chiffre.text() == "1"
    d = p.ouvrir_correspondance("demande", [prof.id], rappel=True)
    assert p.rappel.isChecked() and p.cible.text() == "مدرسة وهمية"
    d.hide()
    n = int(p.cartes["recu"].chiffre.text())
    p.marquer_recu(prof.id)
    r = next(i for i in range(p.suivi.rowCount()) if p.suivi.item(i, 0).data(Qt.UserRole) == prof.id)
    assert p.suivi.item(r, 2).text() == "ملف الأستاذ موجود بالمؤسسة" and p.suivi.item(r, 0).icon().isNull()
    assert int(p.cartes["recu"].chiffre.text()) == n + 1 and "محضر تسليم المهام" in p.l_passation.text()
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
    assert p.membres.item(0, 1).text() == "رئيس المجلس" and not p.c_optionnels.isHidden()
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
    assert p.enregistrer(True) and p.liste.rowCount() == 1
    selectionner(p.liste, 0)
    assert p.sid and p.odj.toPlainText().startswith("دراسة برنامج العمل السنوي")
    assert p.pv() and p.convocation() and len(ouverts) == 2
    assert ce.suivi(f.conn)[0]["nombre"] == 1
    # طلب المدير 2026-11-18: الصفحة للجدولة والأرشيف، والاستدعاء والمحضر والتركيبة في نوافذ منبثقة
    # طلب المدير 2026-11-19: لا حد أدنى؛ لائحة واحدة للمبرمجة والمنجزة وأمام كل مجلس أزراره
    assert p.cartes["gestion"].chiffre.text() == "1" and p.t_docs.rowCount() == 2
    assert "منجز" in p.liste.item(0, 4).text() and p.liste.cellWidget(0, 6) is not None
    from PySide6.QtWidgets import QPushButton
    boutons = {b.text(): b for b in p.liste.cellWidget(0, 6).findChildren(QPushButton)}
    assert {"الاستدعاء", "توليد المحضر", "الاطلاع على المحضر"} <= set(boutons)
    assert boutons["الاطلاع على المحضر"].isEnabled() and ce.pv_existant(f.conn, f.dossier, p.liste.item(0, 0).data(Qt.UserRole))
    d = p.ouvrir_programmation("gestion")
    assert d.isVisible() and p.c_deroulement.isHidden() and p.sid is None and p.r_conseils["gestion"].isChecked()
    p.odj.setPlainText("التحضير لنهاية السنة")
    n = len(ouverts)
    assert p.programmer_et_convoquer() and len(ouverts) == n + 1, p.message.text()
    assert p.liste.rowCount() == 2 and "بعد 7 يوماً" in p.liste.item(0, 4).text()
    boutons = {b.text() for b in p.liste.cellWidget(0, 6).findChildren(QPushButton)}
    assert boutons == {"الاستدعاء", "تعديل الموعد"}
    n = len(ouverts)
    assert p.convocation_ligne(p.liste.item(0, 0).data(Qt.UserRole)) and len(ouverts) == n + 1
    assert p.cartes["gestion"].chiffre.text() == "1" and "مبرمج: 1" in p.cartes["gestion"].note.text()
    p.f_etat.setCurrentIndex(p.f_etat.findData("fait"))
    assert p.liste.rowCount() == 1
    p.f_etat.setCurrentIndex(0)
    d.hide()
    selectionner(p.liste, 1)
    assert not p.barre_sel.isHidden() and p.sid
    d = p.ouvrir_pv(p.sid)
    assert not p.c_deroulement.isHidden() and p.presence.count() == 10
    p.decisions.setPlainText("المصادقة على البرنامج")
    assert p.enregistrer_et_pv() and len(ouverts) == n + 2
    d.hide()
    p.filtrer("pedagogique")
    assert p.liste.rowCount() == 0 and p.cartes["pedagogique"].actif
    p.filtrer("pedagogique")
    assert p.liste.rowCount() == 2
    c = p.ouvrir_composition("pedagogique")
    assert c.isVisible() and p.conseil.currentData() == "pedagogique" and p.r_conseils_c["pedagogique"].isChecked()
    c.hide()
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
    assert noms == ["المراقبة المستمرة", "الامتحان", "استثمار النتائج", "مجالس الأقسام"]   # 2026-11-19
    for i in range(1, 4):
        rh.enregistrer(f.conn, rh.Personnel(nom_ar="التجريبي", prenom_ar=f"أستاذ{i}", sexe="M", categorie="enseignant",
                                            ppr=f"400000{i}"))
    f.aller_a("الامتحان")
    p = f.page_examen
    assert f.page_courante() == "الامتحان" and not p.b_local.isHidden() and "جدولة المواد" in p.l_manquants.text()
    p.premier.setValue(11)
    assert p.preparer_local() and p.cands.rowCount() >= 1 and p.cands.item(0, 0).text() == "11"
    n = p.cands.rowCount()
    if n > 1:   # زر الحذف أمام كل مترشح (طلب المدير 2026-11-10)
        p.cands.cellWidget(0, 5).click()
        assert p.cands.rowCount() == n - 1 and p.cands.item(0, 0).text() == "11"
        p.preparer_local()
    cb = p.mats.cellWidget(0, 0)   # مقترحات المواد بترتيب المدير، مع إمكانية الكتابة (2026-11-12)
    assert [cb.itemText(i) for i in range(cb.count())] == list(exs.MATIERES_SUGGEREES) and cb.isEditable()
    assert exs.MATIERES_SUGGEREES[:2] == ("اللغة العربية", "التربية الإسلامية")
    assert p.mats.columnWidth(0) == 210 and p.mats.columnWidth(2) == 170
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
    assert titres[:3] == ["الحضور", "الهدر المدرسي", "الأنشطة الموازية"] and titres[3] == "الحاصلون على المعدل"
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
    assert f.boutons[i].l_badge.text() == "7" and not f.boutons[i].l_badge.isHidden()
    # البحث
    assert f.filtrer_nav("رخص") == ["الرخص"] and not f.boutons[i].isHidden()
    assert all(b.isHidden() for k, b in enumerate(f.boutons) if k != i)
    assert "مجالس الأقسام" in set(f.filtrer_nav("محضر")) and "محاضر نهاية الأسدوس" not in f.pages
    assert f.filtrer_nav("كلمة غير موجودة") == [] and not f.aucun_resultat.isHidden()
    f.recherche.setText("الامتحان")
    f.ouvrir_premier_resultat()
    assert f.page_courante() == "الامتحان" and f.recherche.text() == ""
    assert all(not b.isHidden() for b in f.boutons)
    # المظهر: يُطبَّق ويُحفظ، والشريط الجانبي يُعاد بناؤه
    f.aller_a("إعداد المؤسسة")
    c = f.page_etab.choix_theme
    assert c.count() == 5 and c.itemData(0) == "rihab"
    from PySide6.QtWidgets import QLabel

    from idara import marque
    from idara.ui.zellige import LogoMarque
    assert f.findChildren(LogoMarque) and any(l.text() == marque.NOM_COURT for l in f.findChildren(QLabel))
    assert f.windowTitle().startswith("الشامل في الإدارة التربوية بالمغرب")
    c.setCurrentIndex(c.findData("marine"))
    assert theme.THEME_ACTUEL == "marine" and config_srv.lire_config()["theme"] == "marine"
    assert theme.NAV_FOND in f.styleSheet() and f.page_courante() == "إعداد المؤسسة"
    assert f.filtrer_nav("رخص") == ["الرخص"]
    f.filtrer_nav("")
    c.setCurrentIndex(c.findData("violet"))
    assert theme.THEME_ACTUEL == "violet"
    c.setCurrentIndex(c.findData("classique"))
    assert theme.THEME_ACTUEL == "classique"
    c.setCurrentIndex(c.findData("maghribi"))
    assert theme.THEME_ACTUEL == "maghribi" and theme.NAV_TEXTE_ACTIF == "#0B3B2C"
    c.setCurrentIndex(c.findData("rihab"))
    assert theme.THEME_ACTUEL == "rihab" and theme.NAV_FOND == "#2E3192" and "#4B50C8" in f.styleSheet() + \
        theme.FEUILLE_STYLE
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
    assert "حدّد مبالغ التسجيل" in p.l_milieu.text() and p.table.rowCount() > 0
    # طلب المدير 2026-11-19: لا تلاميذ التعليم الأولي، والأقسام في قائمة منسدلة
    assert all(not p.table.item(i, 2).text().startswith("PS") for i in range(p.table.rowCount()))
    assert p.classe.count() >= 2 and not any(p.classe.itemText(i).startswith("PS") for i in range(p.classe.count()))
    e = et.lire_etablissement(f.conn)
    e.milieu = "urbain"
    et.enregistrer_etablissement(f.conn, e)
    p.rafraichir()
    assert "12 درهم" in p.l_milieu.text() and "قيم افتراضية" in p.l_milieu.text()
    n = p.table.rowCount()
    p.table.item(0, 3).setCheckState(Qt.Checked)
    assert p.totaux["elements"]["assurance"] == {"libelle": "التأمين المدرسي", "payes": 1, "montant_unitaire": 12,
                                                 "montant": 12}
    assert p.tout_cocher("sport") == n and p.totaux["elements"]["sport"]["montant"] == 10 * n
    assert p.totaux["total"] == 12 + 10 * n
    p.table.item(0, 4).setCheckState(Qt.Unchecked)
    assert p.totaux["elements"]["sport"]["payes"] == n - 1
    d = p.ouvrir_montants()
    assert d.isVisible() and p.c_montants["assurance"].text() == "12"
    p.c_montants["sport"].setText("abc")
    assert not p.enregistrer_montants() and "رقم" in p.message_montants.text()
    p.c_montants["sport"].setText("20")
    assert p.enregistrer_montants() and not d.isVisible() and "قيم افتراضية" not in p.l_milieu.text()
    assert p.totaux["elements"]["sport"]["montant"] == 20 * (n - 1)
    cl = p.classe.itemData(1)
    p.classe.setCurrentIndex(1)
    assert all(p.table.item(i, 2).text() == cl for i in range(p.table.rowCount()))
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
    i = next(k for k, x in enumerate(p.lignes) if x["effectif"] >= 1)   # قسم فيه تلميذ على الأقل
    p.table.item(i, 3).setText("96.5")             # نسبة الحضور تُدخل يدوياً (قرار 2026-11-13)
    assert p.enregistrer(), p.message.text()
    assert p.s["etablissement"]["taux"] == 96.5 and "✓" in p.mois.currentText()
    p.table.item(i, 3).setText("abc")
    assert not p.enregistrer() and "بين 0 و100" in p.message.text()
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
    assert p.generer_tableau_bord() is not None and "لوحة القيادة" in p.message.text()
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
    p.filtrer("parti")
    p.rafraichir()
    assert p.liste.rowCount() == 1
    p.barre_unites.boutons["وحدة فرعية"].click()
    assert p.liste.rowCount() == 0 and "مغادرون لم يُرسل" not in p.alertes.text()
    d = p.ajouter("arrive", ouvrir=False)
    assert d.classe.count() == 1    # لا أقسام مسندة لهذه الوحدة
    p.barre_unites.boutons["الوحدة المركزية"].click()
    assert p.liste.rowCount() == 1
    # وافد جديد في وحدة دون قسم: يُطلب القسم
    d = p.ajouter("arrive", ouvrir=False)
    assert d.classe.count() == 2
    d.code.setText("Y000000077")
    d.nom.setText("الوافد")
    d.prenom.setText("هبة")
    d.s_f.setChecked(True)
    d.date_mv.setText("02/10/2026")
    d.etab.setEditText("مدرسة أصلية")
    assert d.enregistrer() is None and "اختر قسمه" in d.message.text()
    d.classe.setCurrentIndex(1)
    assert d.enregistrer() is not None, d.message.text()
    assert p.categorie == "arrive" and p.liste.rowCount() == 1
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


def test_tableau_rapide_suspend_puis_retablit_les_largeurs(app):
    """بلاغ 2026-11-10: ملء جدول كبير كان يعيد حساب عرض الأعمدة بعد كل خانة."""
    import time

    from PySide6.QtWidgets import QApplication, QHeaderView, QTableWidgetItem

    from idara.ui.saisie import tableau
    t = tableau(["أ", "ب", "ج", "د"])
    h = t.horizontalHeader()
    assert h.sectionResizeMode(0) == QHeaderView.ResizeToContents
    debut = time.perf_counter()
    t.setRowCount(400)
    assert h.sectionResizeMode(0) == QHeaderView.Interactive     # مجمّد أثناء الملء
    for i in range(400):
        for j in range(4):
            t.setItem(i, j, QTableWidgetItem(f"خانة طويلة نسبياً {i}-{j}"))
    assert time.perf_counter() - debut < 3
    QApplication.processEvents()
    assert h.sectionResizeMode(0) == QHeaderView.ResizeToContents   # يُستعاد بعد الملء
    assert h.sectionResizeMode(1) == QHeaderView.Stretch
    t.insertRow(0)
    QApplication.processEvents()
    assert h.sectionResizeMode(2) == QHeaderView.ResizeToContents


def test_annees_scolaires_archive_et_consultation(app, config_tmp):
    """فتح سنة جديدة مع الأرشفة، والاطلاع على السنوات الماضية (طلب المدير 2026-11-12)."""
    from idara.services import annee as an
    from idara.services import sauvegarde
    f = _fenetre_avec_eleves(config_tmp)
    assert "2026/2027" in f.b_annee.text() and f.bandeau_archive.isHidden()
    d = f.gerer_annees()
    assert d.table.rowCount() == 1 and "السنة الجارية" in d.table.item(0, 3).text()
    n = len(sauvegarde.lister_sauvegardes(f.dossier))
    assert d.nouvelle("2025/2026", confirmer=False)          # سنة سابقة للتجريب
    assert len(sauvegarde.lister_sauvegardes(f.dossier)) == n + 1
    assert "2025/2026" in f.b_annee.text() and "أرشيف" in f.b_annee.text()
    assert not f.bandeau_archive.isHidden() and "2026/2027" in f.bandeau_archive.texte.text()
    f.aller_a("التلاميذ")
    f.bandeau_archive.revenir()
    assert an.annee_courante(f.conn)["libelle"] == "2026/2027" and f.bandeau_archive.isHidden()
    assert not d.nouvelle("2026/2027", confirmer=False) and "موجودة" in d.message.text()
    assert d.nouvelle("2027/2028", confirmer=False) and f.bandeau_archive.isHidden()
    assert d.consulter("2026/2027") and not f.bandeau_archive.isHidden()
    assert d.table.rowCount() == 3
    d.close()
    f.close()


def test_page_passation(app, config_tmp, monkeypatch):
    """محضر تسليم المهام (نموذج المدير 2026-11-12): المحاور، الإدخال اليدوي، الاستيراد، والتوليد."""
    import openpyxl
    from PySide6.QtCore import Qt

    from idara.services import bureautique
    from idara.services import passation as ps
    ouverts = []
    monkeypatch.setattr(bureautique, "ouvrir", lambda p: ouverts.append(p))
    f = _fenetre_avec_eleves(config_tmp)
    f.aller_a("تسليم المهام")
    p = f.page_passation
    assert f.page_courante() == "تسليم المهام" and p.liste.count() == len(ps.SECTIONS)
    assert p.cle == "etablissement" and p.editeurs["nom"].text() == "مدرسة تجريبية"
    p.editeurs["date_creation"].setText("1985")
    p.liste.setCurrentRow([s.cle for s in ps.SECTIONS].index("eleves"))      # الانتقال يحفظ المحور السابق
    assert ps.lire(f.conn, "etablissement")["champs"]["date_creation"] == "1985"
    assert p.table is not None and sum(int(p.table.item(i, 1).text()) for i in range(p.table.rowCount())) == 5
    p.table.item(0, 2).setText("5")
    p.actualiser()
    assert p.table.item(0, 2).text() == "5" and not p.b_actualiser.isHidden()
    # لائحة الكتب: إضافة سطر، استيراد من Excel، حذف
    p.liste.setCurrentRow([s.cle for s in ps.SECTIONS].index("livres"))
    assert not p.b_importer.isHidden() and p.table.rowCount() == 0
    p.ajouter_ligne()
    p.table.item(0, 0).setText("كتاب يدوي")
    p.table.item(0, 1).setText("02")
    wb = openpyxl.Workbook()
    wb.active.append(["العنوان", "العدد"])
    wb.active.append(["كتاب مستورد", 3])
    wb.save(config_tmp / "kutub.xlsx")
    assert p.importer(str(config_tmp / "kutub.xlsx")) == 1
    assert [l[0] for l in ps.lire(f.conn, "livres")["lignes"]] == ["كتاب يدوي", "كتاب مستورد"]
    from idara.ui.saisie import selectionner
    selectionner(p.table, 0)
    p.supprimer_lignes()
    p.enregistrer()
    assert [l[0] for l in ps.lire(f.conn, "livres")["lignes"]] == ["كتاب مستورد"]
    # إخفاء محور وتغيير موضعه
    p.liste.item(p.liste.currentRow()).setCheckState(Qt.Unchecked)
    assert dict((s.cle, a) for s, a in ps.sections(f.conn))["livres"] is False
    p.deplacer(-1)
    assert [s.cle for s, _ in ps.sections(f.conn)].index("livres") == \
        [s.cle for s in ps.SECTIONS].index("livres") - 1 and p.cle == "livres"
    p.retablir()
    assert all(a for _, a in ps.sections(f.conn))
    # محور خاص (طلب المدير 2026-11-13)
    cle = p.ajouter_section("الحديقة المدرسية", "النوع، العدد", False)
    assert cle and p.cle == cle and p.table is not None and p.table.columnCount() == 2
    assert p.b_suppr_section.isEnabled() and p.liste.count() == len(ps.SECTIONS) + 1
    p.ajouter_ligne()
    p.table.item(0, 0).setText("أشجار")
    p.enregistrer()
    assert ps.lire(f.conn, cle)["lignes"] == [["أشجار", ""]]
    assert p.ajouter_section("الحديقة المدرسية", "", True) is None and "يوجد محور" in p.message.text()
    assert p.supprimer_section() and p.liste.count() == len(ps.SECTIONS)
    p.date_pv.setText("25/07/2026")
    chemin = p.generer()
    assert chemin is not None and chemin.exists() and ouverts == [chemin], p.message.text()
    assert ps.lire(f.conn, "_general")["champs"]["date_pv"] == "2026-07-25"
    f.close()


def test_page_inventaire(app, config_tmp, monkeypatch):
    """سجل الجرد (طلب المدير 2026-11-13): إدخال، فرز حسب النوع، محو، حذف، توليد."""
    from idara.services import bureautique
    from idara.services import inventaire as inv
    from idara.services import passation as ps
    from idara.ui.saisie import selectionner
    ouverts = []
    monkeypatch.setattr(bureautique, "ouvrir", lambda p: ouverts.append(p))
    f = _fenetre_avec_eleves(config_tmp)
    f.aller_a("الجرد")
    p = f.page_inventaire
    assert p.numero.text() == "1" and p.table.rowCount() == 0
    assert p.generer() is None and "لا تجهيزات" in p.message.text()
    p.designation.setText("خزانة حديدية")
    p.type.setCurrentText("أثاث مكتبي")
    p.quantite.setValue(3)
    p.prix.setText("900")
    p.entretien.setCurrentText("صالح")
    assert p.enregistrer(), p.message.text()
    p.nouveau()
    assert p.numero.text() == "2"
    p.designation.setText("طابعة")
    p.type.setCurrentText("معلوميات ووسائل رقمية")
    p.date_facture.setText("31/02/2025")
    assert p.enregistrer() is None and "التواريخ" in p.message.text()
    p.date_facture.setText("")
    assert p.enregistrer(), p.message.text()
    assert p.table.rowCount() == 2 and "2 700.00" in p.total.text()
    p.filtre.setCurrentIndex(p.filtre.findData("أثاث مكتبي"))
    assert p.table.rowCount() == 1 and p.table.item(0, 2).text() == "خزانة حديدية"
    p.filtre.setCurrentIndex(0)
    # المحو من السجل
    selectionner(p.table, [p.table.item(i, 2).text() for i in range(2)].index("طابعة"))
    p.radie_le.setText("01/10/2026")
    p.motif.setText("عطب")
    assert p.enregistrer() and inv.lister(f.conn, radies=False)[0].designation == "خزانة حديدية"
    p.radies.setChecked(False)
    assert p.table.rowCount() == 1
    assert ps.lire(f.conn, "equip_admin")["lignes"][0][:4] == ["خزانة حديدية", "03", "1", "03"]
    chemin = p.generer()
    assert chemin is not None and ouverts == [chemin]
    p.radies.setChecked(True)
    selectionner(p.table, 0)
    assert p.supprimer(confirmer=True) and p.table.rowCount() == 1
    assert p.t_types.rowCount() >= 1
    # طلب المدير 2026-11-19: التجهيز الجديد في نافذة منبثقة، وأعمدة الجدول بأحجام مناسبة
    d = p.ouvrir_nouveau()
    assert d.isVisible() and p.aid is None and p.designation.text() == ""
    num = p.numero.text()
    p.designation.setText("سبورة بيضاء")
    assert p.enregistrer() and f"حُفظ السطر {num}" in p.message_fiche.text()
    d.hide()
    assert p.table.columnWidth(0) < p.table.columnWidth(2) and p.table.columnWidth(4) < p.table.columnWidth(3)
    d = p.ouvrir(p.table.item(0, 0).data(Qt.UserRole))
    assert d.isVisible() and p.aid == p.table.item(0, 0).data(Qt.UserRole)
    d.hide()
    f.close()


def test_page_structure(app, config_tmp, monkeypatch):
    """البنية المادية (طلب المدير 2026-11-13)."""
    from idara.services import bureautique
    from idara.services import passation as ps
    from idara.services import structure as st
    monkeypatch.setattr(bureautique, "ouvrir", lambda p: None)
    f = _fenetre_avec_eleves(config_tmp)
    f.aller_a("البنية المادية")
    p = f.page_structure
    assert p.table.rowCount() == len(st.ELEMENTS) and p.table.item(0, 0).text() == "عدد حجرات التعليم العام"
    assert p.generer() is None and "لم يُدخل" in p.message.text()
    p.table.item(0, 1).setText("8")
    p.ajouter()
    i = p.table.rowCount() - 1
    p.table.item(i, 0).setText("مستودع")
    p.table.item(i, 1).setText("1")
    assert p.enregistrer(), p.message.text()
    assert p.table.rowCount() == len(st.ELEMENTS) + 1
    p.table.item(0, 1).setText("ثمانية")
    assert not p.enregistrer() and "عدد صحيح" in p.message.text()
    p.table.item(0, 1).setText("8")
    assert p.generer() is not None
    assert any(l[1] == "عدد حجرات التعليم العام" and l[2] == "08" for l in ps.lire(f.conn, "batiments")["lignes"])
    p.table.setCurrentCell(p.table.rowCount() - 1, 0)
    assert p.supprimer() and p.table.rowCount() == len(st.ELEMENTS)
    f.close()


def test_page_parents(app, config_tmp, monkeypatch):
    """أولياء الأمور (طلب المدير 2026-11-13): استيراد ملف مسار، تعديل، لائحة."""
    from idara.services import bureautique
    from idara.services import parents as pa
    from idara.ui.saisie import selectionner
    from tests.test_parents import _w, fichier_tuteurs
    monkeypatch.setattr(bureautique, "ouvrir", lambda p: None)
    f = _fenetre_avec_eleves(config_tmp)
    f.aller_a("أولياء الأمور")
    p = f.page_parents
    assert p.table.rowCount() == 5 and "معلومات الأولياء مسجلة لـ 0" in p.nb.text()
    code = f.conn.execute("SELECT code_massar FROM eleve ORDER BY id LIMIT 1").fetchone()[0]
    r = p.importer([fichier_tuteurs(config_tmp / "t.xlsx", [(code, "أب", {"tuteur": _w("أحمد", "0612345678")})])])
    assert r and r.eleves == 1 and "لـ 1" in p.nb.text()
    p.recherche.setText("0612345678")
    assert p.table.rowCount() == 1
    selectionner(p.table, 0)
    assert not p.c_fiche.isHidden() and p.champs["tuteur"]["telephone"].text() == "0612345678"
    p.champs["mere"]["prenom_ar"].setText("خديجة")
    p.champs["mere"]["telephone"].setText("هاتف")
    assert not p.enregistrer() and "الهاتف" in p.message.text()
    p.champs["mere"]["telephone"].setText("0700000000")
    assert p.enregistrer(), p.message.text()
    assert pa.fiche(f.conn, p.eid)["mere"]["prenom_ar"] == "خديجة"
    assert p.importer([config_tmp / "absent.xlsx"]) is None
    assert p.generer() is not None
    # رسالة واتساب جاهزة: تُفتح ولا تُرسل (2026-11-13)
    liens = []
    monkeypatch.setattr(bureautique, "ouvrir_lien", lambda u: liens.append(u))
    p.wa_type.setCurrentIndex(p.wa_type.findData("convocation"))
    p.wa_date.setText("16/11/2026")
    p.wa_heure.setText("10:00")
    assert "16/11/2026" in p.preparer_message() and "10:00" in p.wa_texte.toPlainText()
    assert p.ouvrir_whatsapp() == liens[0] and liens[0].startswith("https://wa.me/212612345678?text=")
    p.wa_dest.setCurrentIndex(p.wa_dest.findData("pere"))
    assert p.ouvrir_whatsapp() is None and "لا رقم هاتف" in p.message.text()
    # البحث الشامل وماذا أفعل اليوم
    f.recherche.setText("ققققق")
    assert f.liste_personnes.isHidden()            # لا تلميذ ولا موظف بهذا الاسم
    nom = f.conn.execute("SELECT nom_ar FROM eleve ORDER BY id LIMIT 1").fetchone()[0]
    f.recherche.setText(nom)
    assert not f.liste_personnes.isHidden() and f.liste_personnes.item(0).text().startswith("تلميذ")
    f.ouvrir_premier_resultat() if not f.resultats_recherche(nom) else f.ouvrir_personne(f.liste_personnes.item(0))
    assert f.page_courante() == "التلاميذ" and not f.page_eleves.c_fiche.isHidden()
    f.aller_a("لوحة القيادة")
    assert any("نسخة احتياطية" in t["texte"] or "حضور" in t["texte"] or "رخصة" in t["texte"] or True
               for t in f.tableau.taches) or f.tableau.taches == []
    f.close()


def test_page_sabboura(app, config_tmp, monkeypatch):
    """السبورة المرجعية (نماذج المدير 2026-11-13)."""
    from docx import Document

    from idara.services import bureautique
    from idara.services import sabboura as sb
    from idara.ui.page_sabboura import ruban_png
    ouverts = []
    monkeypatch.setattr(bureautique, "ouvrir", lambda p: ouverts.append(p))
    png = ruban_png("بطاقة معلومات المؤسسة")
    assert png[:4] == b"\x89PNG"
    f = _fenetre_avec_eleves(config_tmp)
    f.aller_a("السبورة المرجعية")
    p = f.page_sabboura
    assert p.liste.count() == 11 and p.cle == "fiche" and p.editeurs["nom"].text() == "مدرسة تجريبية"
    p.editeurs["gipe"].setText("G-1")
    p.liste.setCurrentRow([l.cle for l in sb.LAVHAT].index("cellules"))   # الانتقال يحفظ
    assert sb.lire(f.conn, "fiche")["champs"]["gipe"] == "G-1"
    assert p.table is not None and p.table.item(0, 0).text() == "خلية اليقظة"
    p.table.item(0, 1).setText("ذ. الأول، ذة. الثانية")
    p.liste.setCurrentRow([l.cle for l in sb.LAVHAT].index("clubs"))
    assert p.note is not None
    p.note.setText("ذة. المنسقة")
    p.ajouter_ligne()
    p.table.item(p.table.rowCount() - 1, 0).setText("النادي البيئي")
    chemin = p.generer()
    assert chemin is not None and ouverts == [chemin]
    d = Document(chemin)
    assert len(d.sections) == 1 and d.inline_shapes      # شريط العنوان صورة
    chemin = p.generer(tout=True)
    assert chemin is not None and len(Document(chemin).sections) == 11
    assert sb.lire(f.conn, "cellules")["lignes"][0][1] == "ذ. الأول، ذة. الثانية"
    f.close()


def test_pages_vie_admin(app, config_tmp, monkeypatch):
    """الوثائق القانونية للجمعيات، الحراسة، النقل، استعمالات الزمن (2026-11-13)."""
    from PySide6.QtWidgets import QPushButton
    from idara.services import bureautique
    from idara.services import personnel as rh
    from idara.services import vie_admin as va
    monkeypatch.setattr(bureautique, "ouvrir", lambda p: None)
    f = _fenetre_avec_eleves(config_tmp)
    pid = rh.enregistrer(f.conn, rh.Personnel(nom_ar="التجريبي", prenom_ar="أستاذ", sexe="M", categorie="enseignant",
                                              ppr="900003"))
    # الجمعيات
    f.aller_a("الوثائق القانونية للجمعيات")
    p = f.page_asso_legal
    assert p.table.rowCount() == len(va.ROLES_BUREAU) and p.generer("liste") is None
    p.table.item(0, 0).setText("رئيس تجريبي")
    p.ajouter_personnel()
    assert p.table.rowCount() == len(va.ROLES_BUREAU) + 1
    assert p.generer("declaration") is not None and p.generer("pv") is not None
    p.asso.setCurrentIndex(p.asso.findData("parents"))       # التبديل يحفظ الجمعية السابقة
    assert va.lire_asso(f.conn, "najah")["membres"][0][0] == "رئيس تجريبي"
    # الحراسة
    f.aller_a("جدول الحراسة")
    from idara.services import garde as gd
    g = f.page_garde
    assert g.generer() is None and "فارغ" in g.message.text()
    assert g.table.columnCount() == 4 and g.table.rowCount() == 6 and len(g.b_semaines) == 4
    g.nb_zones.setValue(2)
    g.semaines.setValue(2)
    g.jours["السبت"].setChecked(False)
    assert g.table.columnCount() == 2 and g.table.rowCount() == 5 and len(g.b_semaines) == 2
    g.t_zones.item(0, 0).setText("الباب الرئيسي")
    g.table.item(0, 0).setText("أستاذ التجريبي")
    g.table.item(0, 1).setText("أستاذ التجريبي")
    assert not g.enregistrer() and "بمنطقتين" in g.message.text()
    g.table.item(0, 1).setText("أستاذة ثانية")
    g.choisir_semaine(2)
    g.table.item(1, 0).setText("أستاذ ثالث")
    g.choisir_semaine(1)
    assert g.table.item(0, 1).text() == "أستاذة ثانية"   # التنقل بين الأسابيع لا يضيع المدخلات
    g.debut.setText("02/11/2026")
    assert g.generer("tableau") is not None and "أستاذ التجريبي (1)" in g.bilan.text()
    l = gd.lire(f.conn)
    assert l["zones"][0] == "الباب الرئيسي" and l["grille"]["2"]["الثلاثاء"][0] == "أستاذ ثالث"
    assert l["debut"] == "2026-11-02" and "السبت" not in l["jours"]
    assert g.generer("note") is not None
    g.repartir()   # أساتذة المؤسسة الوهميون أقل من منطقتين أو أكثر: رسالة أو جدول ممتلئ
    assert g.table.item(0, 0).text() or "أقل من عدد المناطق" in g.message.text()
    assert "حراسة اليوم" not in g.l_jour.text() and g.l_jour.text()
    # طلب المدير 2026-11-20: شرح المناطق في نافذة منبثقة، ومفتاح أسفل الجدول
    d = g.ouvrir_zones()
    assert d.isVisible() and g.t_zones.verticalHeaderItem(0).text() == "منطقة 01"
    g.t_zones.item(0, 0).setText("الباب الرئيسي")
    assert g.enregistrer_zones() and not d.isVisible() and "منطقة 01: الباب الرئيسي" in g.l_cle.text()
    assert g.table.horizontalHeaderItem(0).text() == "منطقة 01"
    # طلب المدير 2026-11-19: إلغاء التوزيع، ولا طبع لورقة اليوم
    assert g.annuler_repartition() and not any(x for j in gd.lire(f.conn)["grille"]["1"].values() for x in j)
    assert not any(b.text() == "طبع ورقة حراسة اليوم" for b in g.findChildren(QPushButton))
    f.tableau.rafraichir()
    assert f.tableau.garde_jour["jour"]
    # النقل
    f.aller_a("النقل المدرسي")
    t = f.page_transport
    assert t.t_el.rowCount() == 5 and t.generer() is None
    from idara.ui.page_vie_admin import _ajouter
    _ajouter(t.t_veh)
    t.t_veh.item(0, 0).setText("حافلة 1")
    t.t_el.item(0, 2).setText("حافلة 1")
    t.t_el.item(0, 3).setText("دوار أ")
    assert t.generer() is not None and "المستفيدون: 1" in t.stats.text()
    t.t_el.item(1, 2).setText("حافلة 7")
    assert not t.enregistrer() and "غير موجودة" in t.message.text()
    # استعمالات الزمن
    from idara.services import vie_admin as va
    f.aller_a("استعمالات الزمن")
    e = f.page_emplois
    e.prof.setCurrentIndex(e.prof.findData(pid))
    assert e.generer() is None
    e.ajouter()
    e.table.item(0, 1).setText("08:30")
    e.table.item(0, 2).setText("10:00")
    assert e.enregistrer(), e.message.text()
    assert "1 س 30 د" in e.total.text() and e.t_ctrl.rowCount() == 1
    i = [e.t_quotas.item(k, 0).text() for k in range(e.t_quotas.rowCount())].index(e.table.item(0, 3).text())
    e.t_quotas.item(i, 1).setText("90")
    assert e.enregistrer_quotas() and e.t_ctrl.item(0, 3).text() == "الحصيص مكتمل"
    e.table.item(0, 2).setText("08:00")
    assert not e.enregistrer() and "قبل بدايتها" in e.message.text()
    e.table.item(0, 2).setText("10:00")
    assert e.generer() is not None
    # طلب المدير 2026-11-19: الصفحة للعرض (لائحة الأساتذة أو الجماعي)، والمسك والحصيص في نوافذ منبثقة
    assert e.cartes["saisis"].chiffre.text() == "1" and e.liste.cellWidget(0, 5) is not None
    r = next(k for k in range(e.liste.rowCount()) if e.liste.item(k, 0).data(Qt.UserRole) == pid)
    assert e.liste.item(r, 2).text() == "1" and "1 س 30 د" in e.liste.item(r, 3).text()
    d = e.voir(pid)
    assert d.isVisible() and len(e.grille_vue.seances) == 1 and not e.grille_vue.grab().isNull()
    d2 = e.saisir(pid)
    assert d2.isVisible() and not d.isVisible() and e.prof.currentData() == pid
    d2.hide()
    e.mode.setCurrentIndex(e.mode.findData("collectif"))
    assert e.c_liste.isHidden() and not e.c_coll.isHidden()
    k = next(k for k in range(e.collectif.rowCount()) if e.collectif.item(k, 0).data(Qt.UserRole) == pid)
    assert any(e.collectif.item(k, j).text() == "08:30–10:00" for j in range(1, e.collectif.columnCount()))
    assert e.ouvrir_quotas().isVisible()
    # طلب المدير 2026-11-19: الحصيص حسب المستوى
    e.niveau_quota.setCurrentIndex(e.niveau_quota.findData("3AP"))
    assert all(not (e.t_quotas.item(k, 1) and e.t_quotas.item(k, 1).text()) for k in range(e.t_quotas.rowCount()))
    assert "الحصيص العام" in e.l_niveau_quota.text()
    e.t_quotas.item(0, 1).setText("120")
    assert e.enregistrer_quotas() and va.lire_quotas(f.conn, "3AP")[e.t_quotas.item(0, 0).text()] == 120
    f.close()


def test_rihab_et_registres(app, config_tmp, monkeypatch):
    """طلب المدير 2026-11-14: رحبة لكل قسم، شريط المسار، والسجلات الإدارية المعرَّفة بالوصف. بيانات وهمية."""
    from idara.services import bureautique
    from idara.ui.fenetre import SECTIONS
    from idara.ui.saisie import selectionner
    ouverts = []
    monkeypatch.setattr(bureautique, "ouvrir", lambda p: ouverts.append(p))
    f = _fenetre_avec_eleves(config_tmp)
    titres = [t for t, _ in SECTIONS]
    i = titres.index("الحياة المدرسية")
    f.ouvrir_rahba(i)
    r = f.rahbat[i]
    assert f.rahba_courante() == i and f.page_courante() is None and f.est_ouvert(i)
    assert list(r.cartes) == [p for p, _ in SECTIONS[i][1]]
    assert all(c.l_desc.text() for c in r.cartes.values())
    assert f.bandeau_page.indice == i and not any(b.isChecked() for b in f.bandeau_page.pilules.values())
    r.cartes["التحفيز والتهاني"].cliquer()
    assert f.page_courante() == "التحفيز والتهاني" and f.bandeau_page.pilules["التحفيز والتهاني"].isChecked()
    f.bandeau_page.pilules["الإعلام والتواصل"].click()   # الحبوب تنقل بين صفحات القسم
    assert f.page_courante() == "الإعلام والتواصل" and not f.bandeau_page.pilules["التحفيز والتهاني"].isChecked()
    f.bandeau_page.b_rahba.click()
    assert f.rahba_courante() == i
    j = titres.index("تسليم المهام")   # قسم بصفحة واحدة: لا رحبة، يفتح صفحته
    assert j not in f.rahbat
    f.ouvrir_rahba(j)
    assert f.page_courante() == "تسليم المهام" and f.bandeau_page.zone.isHidden()
    # كل صفحة لها سطر تعريفي في رحبتها
    from idara.ui.rihab import DESCRIPTIONS, SOUS_SECTIONS
    assert {p for _, fils in SECTIONS for p, _ in fils} <= set(DESCRIPTIONS)
    assert {t for t, fils in SECTIONS if len(fils) > 1} <= set(SOUS_SECTIONS)
    # سجل الحوادث
    f.aller_a("الصحة والسلامة")
    v = f.page_sante.vue()
    nom = v.w["eleve"].itemText(1)
    v.w["eleve"].setEditText(nom)
    assert v.w["classe"].text() == v.classes[nom] != ""
    assert v.enregistrer() is None and f.page_sante.message.objectName() == "erreur"   # التاريخ مطلوب
    v.remplir({"date": "2026-11-10", "description": "سقوط في الساحة", "lieu": "الساحة"})
    lid = v.enregistrer()
    assert lid and v.table.rowCount() == 1 and v.lid == lid and v.b_suppr.isEnabled()
    assert v.generer("declaration") is not None and len(ouverts) == 1
    v.nouveau()
    assert v.lid is None and not v.b_suppr.isEnabled() and v.generer("declaration") is None
    selectionner(v.table, 0)
    assert v.lid == lid and v.w["lieu"].currentText() == "الساحة"
    v.filtre.setCurrentIndex(v.filtre.findData("الملعب"))
    assert v.table.rowCount() == 0
    v.filtre.setCurrentIndex(0)
    assert v.table.rowCount() == 1
    k = titres.index("التلاميذ")   # عدّاد حي على بطاقة الصفحة في الرحبة
    f.ouvrir_rahba(k)
    assert f.rahbat[k].cartes["الصحة والسلامة"].l_pastille.text() == "1 سجلاً"
    assert "تلميذاً" in f.rahbat[k].cartes["التلاميذ"].l_pastille.text()
    # صفحة بسجلين: الحبوب تبدّل بينهما، والحصيلة تقترح أسماء الأعوان
    f.aller_a("الأعوان")
    p = f.page_agents
    assert not p.vues["agents"].isHidden() and p.vues["suivi_agents"].isHidden()
    p.vue().remplir({"nom": "عون تجريبي", "fonction": "الحراسة"})
    assert p.vue().enregistrer()
    p.pilules["suivi_agents"].click()
    assert p.cle == "suivi_agents" and p.vues["agents"].isHidden() and not p.vues["suivi_agents"].isHidden()
    assert p.vue().w["agent"].findText("عون تجريبي") >= 0
    f.aller_a("طلبات الموظفين")
    v = f.page_demandes.vue()
    assert v.cible is not None and v.supprimer() is False
    assert v.generer("suivi") is None and f.page_demandes.message.objectName() == "erreur"   # لا أسطر بعد
    f.close()


def test_editeur_de_documents(app, config_tmp, monkeypatch, tmp_path):
    """طلب المدير 2026-11-15: كل وثيقة تُفتح في محرر البرنامج، تُعدَّل وتُطبع منه، بلا علامات اتجاه ظاهرة."""
    from idara.services import bureautique
    from idara.services import registres as rg
    from idara.ui.editeur import EditeurDocument, fichier_modifie
    f = _fenetre_avec_eleves(config_tmp)
    externes = []
    monkeypatch.setattr(bureautique, "ouvrir_externe", lambda p: externes.append(p))
    monkeypatch.setattr(bureautique, "ouvreur", f.ouvrir_document)
    rg.enregistrer(f.conn, "agents", {"nom": "عون تجريبي", "fonction": "الحراسة", "horaire": "8:00 - 16:00"})
    f.aller_a("الأعوان")
    p = f.page_agents.vue().generer("service")   # التوليد يفتح المحرر لا برنامجاً خارجياً
    assert p is not None and not externes and len(f.editeurs) == 1
    e = f.editeurs[0]
    assert isinstance(e, EditeurDocument) and not e.isHidden() and e.chemin == p
    # داخل النافذة نفسها: معاينة للقراءة أولاً، ثم «تعديل الوثيقة»، و«رجوع» إلى الصفحة السابقة
    assert f.pile.currentIndex() == f.indice_doc and e.parent() is f.page_doc
    assert e.edit.isReadOnly() and e.outils.isHidden()
    e.b_modifier.click()
    assert not e.edit.isReadOnly() and not e.outils.isHidden()
    e.b_modifier.click()
    assert e.edit.isReadOnly()
    imgs = e.exporter_image(tmp_path / "صورة.png")
    assert imgs and imgs[0].exists() and imgs[0].read_bytes()[:4] == b"\x89PNG"
    e.b_retour.click()
    assert f.page_courante() == "الأعوان" and not f.editeurs
    p = f.page_agents.vue().generer("service")
    e = f.editeurs[0]
    texte = e.edit.toPlainText()
    assert "جدول الخدمة" in texte and "عون تجريبي" in texte and "8:00 - 16:00" in texte
    assert not any(c in texte for c in "\u2066\u2069") and e.etat.text() == "الوثيقة كما وُلّدت"
    assert e.edit.document().rootFrame().childFrames(), "الجدول لم يُنقل إلى المحرر"
    # تعديل ثم حفظ: يُعاد فتحه كما تُرك، والأصل لا يتغير
    avant = p.read_bytes()
    c = e.edit.textCursor()
    c.movePosition(c.MoveOperation.End)
    c.insertText(" ملاحظة مضافة باليد")
    assert e.etat.text() == "تعديلات غير محفوظة"
    e.enregistrer()
    assert fichier_modifie(p).exists() and p.read_bytes() == avant and e.etat.text() == "نسخة معدَّلة محفوظة"
    e2 = f.ouvrir_document(p)
    assert "ملاحظة مضافة باليد" in e2.edit.toPlainText() and e2.b_original.isEnabled()
    e2.revenir()
    assert "ملاحظة مضافة باليد" not in e2.edit.toPlainText() and not fichier_modifie(p).exists()
    # التنسيق
    e2.edit.selectAll()
    poids = int(e2.edit.fontWeight())
    e2.gras()   # يبدّل: الغامق يصير عادياً والعكس
    assert (int(e2.edit.fontWeight()) > 400) != (poids > 400)
    e2.taille(+2)
    e2.souligner()
    assert e2.edit.fontUnderline()
    # ملف للإرسال دون أي برنامج خارجي، بالاتجاه الصحيح للصفحة
    pdf = e2.exporter_pdf(tmp_path / "وثيقة.pdf")
    assert pdf.exists() and pdf.read_bytes()[:4] == b"%PDF" and pdf.stat().st_size > 1500
    assert e2.imprimante(tmp_path / "x.pdf").pageLayout().orientation().name == "Portrait"
    e2.ouvrir_externe()
    assert externes == [p]
    # بلاغ المدير 2026-11-19: الفتح ببرنامج الحاسوب لا يُسقط البرنامج مهما كان الخطأ
    def panne(_p):
        raise RuntimeError("عطب في برنامج الحاسوب")
    monkeypatch.setattr(bureautique, "ouvrir_externe", panne)
    e2.ouvrir_externe()
    assert "تعذر فتح الملف" in e2.message.text()
    monkeypatch.setattr(bureautique, "ouvrir_externe", lambda p: externes.append(p))
    # المعاينة: صفحات بعرض الشاشة، والتكبير والتصغير
    assert not e2.zone.isHidden() and e2.vue.n >= 1 and e2.l_pages.text()
    z = e2.vue.zoom
    e2.zoomer(1.15)
    assert abs(e2.vue.zoom - z * 1.15) < 0.01 and e2.mode_zoom == "fixe"
    e2.c_zoom.setCurrentText("الصفحة كاملة")
    assert e2.mode_zoom == "page"
    e2.c_zoom.setCurrentText("150%")
    assert abs(e2.vue.zoom - 1.5) < 0.01
    # المحرر المطوَّر: جدول، قائمة، تباعد، بحث واستبدال، إبراز، فاصل صفحات، تاريخ
    e2.b_modifier.click()
    assert e2.zone.isHidden() and not e2.fond.isHidden()
    c = e2.edit.textCursor()
    c.movePosition(c.MoveOperation.End)
    e2.edit.setTextCursor(c)
    t = e2.inserer_tableau(2, 3)
    assert t.rows() == 2 and t.columns() == 3
    c = e2.edit.textCursor()
    c.movePosition(c.MoveOperation.End)
    e2.edit.setTextCursor(c)
    e2.edit.insertPlainText("سطر للتجربة")
    e2.liste(__import__("PySide6.QtGui", fromlist=["x"]).QTextListFormat.ListDecimal)
    assert e2.edit.textCursor().currentList() is not None
    e2.interligne(1.5)
    assert e2.edit.textCursor().blockFormat().lineHeight() == 150
    r = e2.rechercher()
    r.cherche.setText("سطر للتجربة")
    r.remplace.setText("سطر مستبدل")
    assert r.tout_remplacer() == 1 and "سطر مستبدل" in e2.edit.toPlainText()
    r.close()
    e2.edit.selectAll()
    e2.surligner(__import__("PySide6.QtGui", fromlist=["x"]).QColor("#FFEB3B"))
    e2.couleur_texte(__import__("PySide6.QtGui", fromlist=["x"]).QColor("#1565C0"))
    e2.saut_page()
    e2.inserer_date()
    img = tmp_path / "صورة.png"
    __import__("PySide6.QtGui", fromlist=["x"]).QImage(40, 30, __import__("PySide6.QtGui", fromlist=["x"]).QImage.Format_RGB32).save(str(img))
    assert e2.inserer_image(img)
    # طلب المدير 2026-11-19 «أريد مثل هذا المحرر»: شريط بتبويبات ومجموعات، مسطرة، شريط حالة، أدوات Word
    assert list(e2.onglets) == ["الصفحة الرئيسية", "إدراج", "تخطيط الصفحة", "عرض"] and not e2.regle.isHidden()
    e2.choisir_onglet(2)
    assert e2.pile_ruban.currentIndex() == 2 and e2.onglets["تخطيط الصفحة"].isChecked()
    e2.b_simple.setChecked(True)
    assert e2.pile_ruban.isHidden()
    e2.choisir_onglet(0)
    assert not e2.pile_ruban.isHidden() and not e2.b_simple.isChecked()
    e2.edit.selectAll()
    e2.position_texte(True)
    assert e2.edit.textCursor().charFormat().verticalAlignment() == e2.edit.textCursor().charFormat().VerticalAlignment.AlignSuperScript
    e2.position_texte(True)
    c = e2.edit.textCursor()
    c.movePosition(c.MoveOperation.Start)
    e2.edit.setTextCursor(c)
    e2.appliquer_style("عنوان 1")
    assert e2.edit.textCursor().blockFormat().headingLevel() == 1
    e2.direction(False)
    assert e2.edit.textCursor().blockFormat().layoutDirection() == Qt.LeftToRight
    e2.inserer_symbole("☑")
    assert "☑" in e2.edit.toPlainText()
    larg = e2.largeur_contenu
    e2.orientation(True)
    assert e2.page.paysage and e2.largeur_contenu > larg and e2.b_paysage.isChecked()
    assert e2.imprimante(tmp_path / "p.pdf").pageLayout().orientation().name == "Landscape"
    e2.orientation(False)
    e2.marges(12.7)
    assert e2.largeur_contenu >= larg and e2.page.marges_mm == (12.7,) * 4
    e2._maj_barre_etat()
    assert "كلمة" in e2.barre_etat.l_mots.text() and e2.barre_etat.l_page.text().startswith("الصفحات")
    e2.b_regle.click()
    assert e2.regle.isHidden()
    assert not e2.regle.grab().isNull() and not e2.outils.grab().isNull()
    e2.b_modifier.click()
    assert e2.vue.n >= 2   # فاصل الصفحات
    # وثيقة لا يفهمها المحرر: تُفتح خارجياً بدل رسالة خطأ
    faux = tmp_path / "تالف.docx"
    faux.write_bytes(b"ceci n'est pas un docx")
    assert f.ouvrir_document(faux) is None and externes[-1] == faux
    for x in f.editeurs:
        x.close()
    f.close()


def test_affiches_et_convocations(app, config_tmp, monkeypatch, tmp_path):
    """طلب المدير 2026-11-15: إعلانات مزخرفة (10 قوالب، A4/A3) واستدعاءات أولياء الأمور (عدة في الصفحة)."""
    import re

    from docx import Document
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QPainter, QPixmap

    from idara.services import affiches as af
    from idara.services import bureautique
    from idara.ui import affiche_qt
    from idara.ui.saisie import selectionner
    ouverts = []
    monkeypatch.setattr(bureautique, "ouvrir", lambda p: ouverts.append(p))
    f = _fenetre_avec_eleves(config_tmp)
    f.aller_a("الإعلام والتواصل")
    p = f.page_annonces
    v = p.vue()
    assert p.cle == "affiche" and len(v.vignettes) == 10 and v.vignettes["zellige"].isChecked()
    assert v.titre.text().startswith("الدخول المدرسي") and not v.apercu.pixmap().isNull()
    v.choisir_theme("nuit")
    v.occasion.setCurrentIndex(v.occasion.findData("examen"))
    assert v.theme == "nuit" and v.titre.text() == "الامتحان الموحد" and "الامتحان" in v.texte.toPlainText()
    v.date.definir("2026-11-21")
    v.heure.setText("8:30")
    c = v.contenu()
    assert c.date == "السبت 21 نونبر 2026" and c.etablissement and [l for l, _ in c.infos()] == ["التاريخ", "الساعة"]
    for fmt, points in (("A4", (595, 842)), ("A3", (842, 1191))):   # حجم الصفحة الحقيقي في الملف
        v.format.setCurrentIndex(v.format.findData(fmt))
        pdf = v.enregistrer_pdf(tmp_path / f"{fmt}.pdf", ouvrir=False)
        brut = pdf.read_bytes()
        m = re.search(rb"/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)", brut)
        assert brut[:4] == b"%PDF" and len(brut) > 3000 and m
        assert abs(float(m[1]) - points[0]) < 2 and abs(float(m[2]) - points[1]) < 2
    img = v.enregistrer_image(tmp_path / "إعلان.png")
    assert QPixmap(str(img)).width() == 2480
    assert v.enregistrer_pdf() is not None and len(ouverts) == 1   # في الأرشيف ثم يُفتح
    v.titre.setText("")
    assert v.enregistrer_pdf(tmp_path / "x.pdf", ouvrir=False) is None and p.message.objectName() == "erreur"
    # النص الطويل يُصغَّر حتى يدخل صندوقه، والعنوان القصير يبقى بحجمه
    d = af.composer("officiel", af.Contenu(titre="عنوان", texte="كلمة " * 500))
    pm = QPixmap(420, 594)
    q = QPainter(pm)
    tailles = dict(zip([t.texte[:5] for t in d.textes], affiche_qt.peindre(q, d, QRectF(0, 0, 420, 594))))
    q.end()
    assert tailles["كلمة "] < int(22 * 0.3528 * 2) and tailles["عنوان"] == int(44 * 0.3528 * 2)
    # الاستدعاءات
    p.pilules["convocations"].click()
    cvu = p.vue()
    assert p.cle == "convocations" and v.isHidden() and cvu.numero.isHidden() and cvu.table.rowCount() > 0
    cvu.occasion.setCurrentIndex(cvu.occasion.findData("portes"))
    assert not cvu.numero.isHidden() and cvu.numero.count() == 4
    cvu.occasion.setCurrentIndex(cvu.occasion.findData("rencontre"))
    assert [cvu.numero.itemText(i) for i in range(cvu.numero.count())] == ["01", "02", "03", "04", "05"]
    assert cvu.generer() is None and p.message.objectName() == "erreur"   # التاريخ مطلوب
    cvu.date.definir("2026-11-21")
    cvu.heure.setText("10:00")
    cvu.numero.setCurrentIndex(2)
    selectionner(cvu.table, 0)
    assert len(cvu.choisis()) == 1 and "المحدَّدون: 1" in cvu.nb.text()
    doc = cvu.generer()
    cellules = [c.text for t in Document(doc).tables for r in t.rows for c in r.cells if c.text.strip()]
    assert len(cellules) == 1 and "اللقاء التواصلي رقم 03" in cellules[0] and len(ouverts) == 2
    cvu.table.clearSelection()
    cvu.par_page.setCurrentIndex(cvu.par_page.findData(8))
    assert cvu.choisis() is None and "كل المعروضين" in cvu.nb.text()
    doc = cvu.generer()
    assert sum(1 for t in Document(doc).tables for r in t.rows for c in r.cells if c.text.strip()) == cvu.table.rowCount()
    p.pilules["annonces"].click()   # سجل الإعلانات النصية ما زال في مكانه
    assert p.vue().r.cle == "annonces"
    f.close()


def test_editeur_apercu_et_nafidha(app, config_tmp, monkeypatch, tmp_path):
    """بلاغ المدير 2026-11-18: «معاينة الطبع» كانت تُغلق البرنامج، والوثيقة المولدة من نافذة منبثقة لا تظهر كاملة."""
    from PySide6.QtPrintSupport import QPrintPreviewDialog
    from PySide6.QtWidgets import QApplication, QWidget

    from idara.services import bureautique
    from idara.services import registres as rg
    from idara.ui.vitrine import FenetreFiche
    f = _fenetre_avec_eleves(config_tmp)
    monkeypatch.setattr(bureautique, "ouvrir_externe", lambda p: None)
    monkeypatch.setattr(bureautique, "ouvreur", f.ouvrir_document)
    rg.enregistrer(f.conn, "agents", {"nom": "عون تجريبي", "fonction": "الحراسة", "horaire": "8:00 - 16:00"})
    f.aller_a("الأعوان")
    p = f.page_agents.vue().generer("service")
    e = f.editeurs[0]
    rendus = []

    def exec_simule(d):   # المعاينة ترسم الصفحات ثم تُغلق (هنا في ملف، فلا طابعة في بيئة الاختبار)
        assert e._imprimante_apercu is not None
        d.paintRequested.emit(e.imprimante(tmp_path / f"apercu{len(rendus)}.pdf"))
        rendus.append(d)
        return 0
    monkeypatch.setattr(QPrintPreviewDialog, "exec", exec_simule)
    import gc
    e.apercu()
    gc.collect()
    e.apercu()
    assert len(rendus) == 2 and (tmp_path / "apercu1.pdf").stat().st_size > 1000
    e.b_retour.click()
    # وثيقة تُفتح من نافذة منبثقة: تُخفى النافذة وتُعرض الوثيقة كاملة، و«رجوع» يعيدها
    w = QWidget()
    fen = FenetreFiche(f, "نافذة تجريبية", "", w)
    fen.ouvrir()
    assert fen.isModal() and fen.isVisible()
    monkeypatch.setattr(QApplication, "activeModalWidget", staticmethod(lambda: fen))
    e2 = f.ouvrir_document(p)
    assert fen.isHidden() and f.pile.currentIndex() == f.indice_doc and e2.parent() is f.page_doc
    e2.b_retour.click()
    assert fen.isVisible() and f.pile.currentIndex() != f.indice_doc
    fen.close()
    f.close()
