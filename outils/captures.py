"""يلتقط صوراً للواجهة ببيانات وهمية لمراجعتها دون حاسوب Windows.

الاستعمال: python outils/captures.py <مجلد_الصور>
"""

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication  # noqa: E402

from idara.app import creer_application  # noqa: E402


def main(sortie: Path) -> None:
    sortie.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp())
    os.environ["IDARA_CONFIG_DIR"] = str(tmp / "config")
    app = creer_application(["captures"])
    from idara.ui.assistant import AssistantPremierLancement
    from idara.ui.fenetre import FenetrePrincipale

    a = AssistantPremierLancement()
    a.resize(1280, 800)
    a.show()

    def photo(w, nom):
        QApplication.processEvents()
        w.grab().save(str(sortie / f"{nom}.png"))

    photo(a, "01_assistant_etape1_vide")
    a.suivant()
    photo(a, "02_assistant_erreur")
    a.f_etab.nom_ar.setText("مجموعة مدارس تجريبية")
    a.f_etab.nom_fr.setText("GS TEST")
    a.f_etab.commune_ar.setText("الجماعة التجريبية")
    a.f_etab.direction_ar.setText("المديرية التجريبية")
    a.f_etab.academie_ar.setText("الأكاديمية التجريبية")
    a.f_etab.unites.setText("الوحدة المركزية، وحدة فرعية")
    photo(a, "03_assistant_etape1_rempli")
    a.suivant()
    a.f_dir.nom_ar.setText("التجريبي")
    a.f_dir.prenom_ar.setText("أحمد")
    a.f_dir.nom_fr.setText("TAJRIBI")
    a.f_dir.prenom_fr.setText("Ahmed")
    photo(a, "04_assistant_etape2")
    a.suivant()
    a.f_id.ville_ar.setText("المدينة")
    a.f_id.ville_fr.setText("Ville")
    photo(a, "05_assistant_etape3")
    a.suivant()
    a.f_donnees.dossier.setText(str(tmp / "الإدارة التربوية"))
    photo(a, "06_assistant_etape4")
    dossier = a.terminer()
    a.close()

    f = FenetrePrincipale(dossier)
    f.resize(1280, 800)
    f.show()
    for page, nom in [("لوحة القيادة", "07_tableau_de_bord"), ("إعداد المؤسسة", "08_etablissement"),
                      ("الوثائق", "10_documents")]:
        f.aller_a(page)
        photo(f, nom)
    # الاستيراد بلوائح وهمية بنفس بنية مسار
    from tests.fabrique_massar import classeur
    from tests.test_import_massar import AR, FR
    f.aller_a("الاستيراد من مسار")
    p = f.page_import
    p.definir_fichiers([classeur(tmp / "ar.xlsx", AR, etab="مجموعة مدارس تجريبية",
                                 annee=__import__("idara.services.annee", fromlist=["x"]).libelle_pour_date()),
                        classeur(tmp / "fr.xlsx", FR, "fr",
                                 annee=__import__("idara.services.annee", fromlist=["x"]).libelle_pour_date())])
    p.analyser()
    photo(f, "11_import_rapport")
    p.appliquer()
    photo(f, "12_import_niveaux")
    f.aller_a("لوحة القيادة")
    photo(f, "13_tableau_apres_import")
    # التلاميذ: البحث ثم البطاقة
    from datetime import date, timedelta
    from idara.services import bureautique
    bureautique.ouvrir = lambda p: None
    f.aller_a("التلاميذ")
    photo(f, "14_eleves_liste")
    e = f.page_eleves
    e.recherche.setText("يوسف")
    __import__("idara.ui.saisie", fromlist=["x"]).selectionner(e.resultats, 0)
    photo(f, "15_eleve_fiche")
    from idara.ui.page_eleves import DialogueVacances
    d = DialogueVacances(e.titre.text(), f)
    d.show()
    photo(d, "16_dialogue_vacances")
    d.close()
    e.vacances(date.today(), date.today() + timedelta(days=10))
    photo(f, "17_eleve_niveau_non_confirme")
    # معرض وثائق التلاميذ ونوافذه (طلب المدير 2026-11-18)
    try:
        photo(e, "17b_eleves_galerie")
        _d = e.ouvrir_document("vacances", ouvrir=False)
        _d.show()
        photo(_d, "17c_eleves_doc_vacances")
        _d.close()
        _d = e.ouvrir_document("portes", ouvrir=False)
        _d.show()
        photo(_d, "17d_eleves_convoc_portes")
        _d.close()
        e.ouvrir_fiche()
        photo(e.fiche, "17e_eleve_fiche_popup")
        e.fiche.hide()
    except Exception as _e:  # noqa: BLE001
        print("galerie eleves:", repr(_e))
    f.aller_a("التلاميذ القدامى")
    a2 = f.page_anciens
    photo(f, "18_anciens_vide")
    a2.ouvrir_nouveau()
    a2.c_num.setText("8173")
    a2.c_nom.setText("القديم")
    a2.c_prenom.setText("فيصل")
    a2.r_m.setChecked(True)
    a2.c_naissance.setText("01/01/1985")
    a2.c_lieu.setText("الخميسات")
    a2.c_entree.setText("15/10/1992")
    a2.c_sortie.setText("30/06/1998")
    a2.c_niveau.setCurrentIndex(4)
    a2.c_dest.setText("فيصل القديم")
    a2.c_cin.setText("A000000")
    a2.generer()
    photo(a2.fiche, "19_anciens_fiche_popup")
    a2.fiche.hide()
    photo(f, "19_anciens_certificat")
    # الموارد البشرية
    f.aller_a("الموارد البشرية")
    r = f.page_rh
    photo(f, "20_personnel_liste")
    r.ouvrir_nouveau()
    r.c["nom_ar"].setText("التجريبية")
    r.c["prenom_ar"].setText("فاطمة")
    r.r_f.setChecked(True)
    r.categorie.setCurrentIndex(r.categorie.findData("enseignant"))
    r.c["ppr"].setText("1234567")
    r.c["cin"].setText("AB123456")
    r.cadre.setCurrentIndex(1)
    r.grade.setCurrentIndex(1)
    r.matiere.setCurrentIndex(r.matiere.findData("عربية"))
    r.c["heures_hebdo"].setText("30")
    r.classes.item(0).setCheckState(Qt.Checked)
    for k, v in (("date_naissance", "15/03/1980"), ("date_recrutement", "16/09/2003"),
                 ("date_affectation_academie", "16/09/2003"), ("date_affectation_direction", "01/09/2008"),
                 ("date_affectation", "01/09/2015")):
        r.dates[k].setText(v)
    r.d_tanzim["date_grade"].setText("01/01/2020")
    r.echelon.setCurrentIndex(r.echelon.findData("7"))
    r.d_tanzim["date_echelon"].setText("01/06/2023")
    r.note_insp.setText("16.5")
    r.d_tanzim["date_inspection"].setText("10/03/2025")
    r.inspecteur.setText("المفتش التجريبي")
    r.enregistrer()
    photo(r.fiche, "21_personnel_fiche")
    r.dates["date_naissance"].ouvrir_calendrier()
    QApplication.processEvents()
    __import__("PySide6.QtGui", fromlist=["x"]).QGuiApplication.primaryScreen()
    r.dates["date_naissance"].popup.grab().save(str(sortie / "21b_calendrier.png"))
    r.dates["date_naissance"].popup.close()
    photo(r.fiche.findChild(__import__("PySide6.QtWidgets", fromlist=["x"]).QScrollArea).widget(),
          "22_personnel_fiche_complete")
    r.fiche.hide()
    r.rafraichir()
    photo(f, "22b_personnel_page")
    photo(r, "22c_personnel_page_complete")
    # تدبير الفائض
    from idara.services import personnel as rh
    for prenom, sexe, recrut, direc, etab, naiss in (
            ("سعيد", "M", "2005-09-16", "2005-09-16", "2016-09-01", "1980-02-01"),
            ("نادية", "F", "2012-09-16", "2012-09-16", "2019-09-01", "1987-06-10"),
            ("كريم", "M", "2021-09-16", "2021-09-16", "2024-09-01", "1996-03-03")):
        rh.enregistrer(f.conn, rh.Personnel(nom_ar="التجريبي", prenom_ar=prenom, sexe=sexe, categorie="enseignant",
                                            matiere="عربية", date_naissance=naiss, date_recrutement=recrut,
                                            date_affectation_direction=direc, date_affectation=etab))
    f.aller_a("تدبير الفائض")
    f.page_fa.cartes[next(iter(f.page_fa.cartes))].postes.setValue(3)
    photo(f, "23_fa")
    # الرخص
    from idara.services import conges as cg
    fatima = next(x for x in rh.lister(f.conn) if x.prenom_ar == "فاطمة")
    fatima.grade, fatima.fonction, fatima.cycle, fatima.adresse, fatima.telephone = (
        "الدرجة الأولى", "التدريس", "ابتدائي", "حي تجريبي", "0600000000")
    rh.enregistrer(f.conn, fatima)
    f.aller_a("الرخص")
    pc = f.page_conges
    photo(f, "24_conges_vide")
    pc.ouvrir_nouveau()
    pc.personnel.setCurrentIndex(pc.personnel.findData(fatima.id))
    pc.debut.setText("10/11/2026")
    pc.duree.setValue(10)
    pc.adresse.setText("حي تجريبي")
    pc.avis.setText("أستاذة منضبطة في عملها")
    pc.mesures.setText("توزيع التلاميذ على الأقسام")
    pc.medecin.setText("الدكتور الطبيب")
    pc.specialite.setText("الطب العام")
    pc.recu_le.setText("10/11/2026")
    pc.deposant.setText("المدلي")
    pc.deposant_cin.setText("CD1")
    pc.enregistrer()
    pc.b_demande.click()
    photo(pc.fiche, "25_conge_fiche")
    photo(pc.fiche.findChild(__import__("PySide6.QtWidgets", fromlist=["x"]).QScrollArea).widget(),
          "26_conge_fiche_complete")
    pc.fiche.hide()
    photo(f, "26b_conges_page")
    photo(pc, "26c_conges_page_complete")
    from idara.ui.page_conges import DialogueBordereau
    d = DialogueBordereau(f, cg.pieces_proposees(f.conn, cg.lire(f.conn, pc.cid)), "ملف رخصة")
    d.show()
    photo(d, "27_dialogue_bordereau")
    d.close()
    f.aller_a("سجل الصادر")
    photo(f, "28_sortants")
    # حركية التلاميذ
    from idara.services import mouvements as mvs
    mvs.enregistrer(f.conn, mvs.Mouvement("arrive", "Y000000009", "الوافد", "هبة", "F", "2026-09-08",
                                          "المؤسسة الأصلية", niveau="الخامس"))
    mvs.enregistrer(f.conn, mvs.Mouvement("parti", "X000000003", date_mouvement="2026-10-15",
                                          etablissement="المؤسسة المستقبلة", direction="عمالة: فاس",
                                          academie="فاس مكناس", hors_province=True))
    try:
        mvs.changer_statut_sortie(f.conn, "X000000002", "non_rejoint", "2026-09-20", "لم يلتحق منذ الدخول")
    except mvs.ErreurMouvement as e:
        print("non_rejoint:", e)
    f.aller_a("حركية التلاميذ")
    f.page_mouvements.rafraichir()
    photo(f, "31_mouvements")
    _pm = f.page_mouvements
    _pm.filtrer("parti")
    __import__("idara.ui.saisie", fromlist=["x"]).selectionner(_pm.t_dossiers, 0)
    photo(f, "32_mouvements_depart")
    _pm.filtrer(None)
    _dm = _pm.ajouter(ouvrir=False)
    _dm.show()
    photo(_dm, "33_mouvements_ajout")
    _dm.close()
    photo(_pm, "34_mouvements_complet")   # الصفحة كاملة (الجدول والمبيانات) دون تمرير
    from idara.services import comportement as cpt
    yid = f.conn.execute("SELECT id FROM eleve WHERE code_massar='X000000001'").fetchone()[0]
    cpt.enregistrer(f.conn, cpt.Observation(yid, "2026-10-05", "شغب في القسم", "", "أستاذ القسم", "تنبيه شفوي"))
    cpt.enregistrer(f.conn, cpt.Observation(yid, "2026-10-12", "عنف لفظي", "", "أستاذ القسم", ""))
    f.aller_a("تتبع السلوك")
    __import__("idara.ui.saisie", fromlist=["x"]).selectionner(f.page_comportement.liste, 0)
    photo(f, "33_comportement")
    try:
        _fc = f.page_comportement.ouvrir_nouvelle()
        photo(_fc, "33_comportement_nouvelle")
        _fc.hide()
    except Exception as e:  # noqa: BLE001
        print("capture comportement:", e)
    from tests.fabrique_resultats import classeur_resultats
    fic = classeur_resultats(tmp / "res.xlsx", {
        "PS1-PS2": [], "4APG-5APG-6APG": [("X000000001", "التجريبي سعيد", [8] * 8),
                                           ("X000000002", "الوهمي سلمى", [4.5] * 8)]},
        annee=__import__("idara.services.annee", fromlist=["x"]).libelle_pour_date())
    f.aller_a("مجالس الأقسام")
    f.page_conseils.importer([fic])
    photo(f, "34_conseils")
    from idara.services import associations as aso
    ex = aso.ouvrir_exercice(f.conn, "najah", "2025/2026", "2025-09-01", "2026-08-31", 42000, 350, "محضر تسليم المهام")
    def _r(l): return f.conn.execute("SELECT id FROM rubrique WHERE ligne LIKE ?", (f"%{l}%",)).fetchone()[0]
    aso.modifier_association(f.conn, "najah", "", "الرئيس التجريبي", "أمين المال التجريبي")
    aso.enregistrer(f.conn, aso.Operation(ex, "2025-10-01", "recette", "banque", 10000, _r("منحة المديرية"),
                                          tiers="المديرية الإقليمية"))
    aso.enregistrer(f.conn, aso.Operation(ex, "2025-10-24", "transfert", "banque", 3000, reference="شيك 01"))
    aso.enregistrer(f.conn, aso.Operation(ex, "2025-11-05", "depense", "caisse", 850, _r("صيانة وإصلاح تجهيزات"),
                                          "فاتورة 12", "إصلاح النوافذ"))
    aso.definir_prevision(f.conn, ex, _r("صيانة وإصلاح تجهيزات"), 600)
    f.aller_a("جمعية دعم مدرسة النجاح")
    f.page_asso._charger_association()
    photo(f, "35_association")
    __import__("idara.ui.saisie", fromlist=["x"]).selectionner(f.page_asso.ops, 4)
    photo(f, "36_association_pieces")
    from idara.services import achats as acx
    e_ = __import__("idara.services.etablissement", fromlist=["x"])
    et_ = e_.lire_etablissement(f.conn); et_.adresse = "حي تجريبي"; e_.enregistrer_etablissement(f.conn, et_)
    aid = acx.creer(f.conn, ex, "bon_commande", "اقتناء طابعات", _r("معدات معلوماتية"), "", "2025-10-01")
    acx.definir_besoin(f.conn, aid, "اقتناء طابعات", _r("معدات معلوماتية"), [("طابعة ليزر", 2, "وحدة", 2000)], 20)
    acx.definir_demande(f.conn, aid, "2025-10-02", 10, 3)
    acx.definir_commission(f.conn, aid, "2025-10-15", "10:00", [("الرئيس التجريبي", "رئيسا"),
                           ("أمين المال التجريبي", "أمين المال"), ("العضو التجريبي", "عضو بمكتب الجمعية")])
    for nom, m in (("الممون أ", 5000), ("الممون ب", 4800), ("الممون ج", 5200)):
        acx.ajouter_offre(f.conn, aid, nom, m)
    acx.choisir(f.conn, aid, acx.fournisseur_par_nom(f.conn, "الممون ب"))
    f.aller_a("الصرف")
    f.page_achats.afficher_liste(aid)
    photo(f, "37_achats")
    from tests.fabrique_tarl import classeur_niveaux
    from idara.services import vie_scolaire as vsx
    fic2 = classeur_resultats(tmp / "res2.xlsx", {"4APG-5APG-6APG": [("X000000001", "التجريبي سعيد", [8] * 8),
                                                                      ("X000000002", "الوهمي سلمى", [4.5] * 8)]},
                              annee=__import__("idara.services.annee", fromlist=["x"]).libelle_pour_date(),
                              semestres={"X000000001": (7.5, 8.2), "X000000002": (4.2, 4.8)})
    f.page_perf.importer([fic2])
    f.aller_a("أداء المؤسسة")
    photo(f, "38_performance")
    f.page_tarl.importer([classeur_niveaux(tmp / "tarl.xlsx", {
        "2APG-1": [("X000000001", "التجريبي سعيد", "حرف", "كلمة", "débutant", "Mot simple", "رقمان", "جمع"),
                   ("X000000002", "الوهمي سلمى", "مبتدئ", "حرف", "lettre", "lettre", "رقم واحد", "رقمان")]},
        annee=__import__("idara.services.annee", fromlist=["x"]).libelle_pour_date())])
    f.aller_a("التعلمات الأساس")
    photo(f, "39_tarl")
    # بطاقة التلميذ (توجيهات 2026-11-15)
    try:
        from idara.services import fiche_eleve as _fe
        from idara.ui.graphe_parcours import graphiques as _gr
        fp = f.page_fiche_eleve
        f.aller_a("بطاقة التلميذ")
        fp.rafraichir()
        fp.recherche.setText("X000000001")
        if fp.lignes:
            fp.charger(fp.lignes[0]["id"])
            for ph, n in ((-1, "C"), (0, "B"), (1, "B"), (2, "A"), (3, "A")):
                _fe.enregistrer_etape(f.conn, fp.eid, fp.p["annee"], ph, "ar", n)
            for ph, n in ((-1, "C"), (0, "C"), (1, "B"), (2, "B")):
                _fe.enregistrer_etape(f.conn, fp.eid, fp.p["annee"], ph, "ma", n)
            from idara.services import registres as _rg
            _n = fp.p["eleve"]["nom"]
            _rg.enregistrer(f.conn, "examens_medicaux", {"date": "2026-10-20", "eleve": _n, "type": "فحص البصر",
                                                          "resultat": "ضعف خفيف", "suite": "إخبار ولي الأمر"})
            _rg.enregistrer(f.conn, "tahfiz", {"date": "2026-11-02", "eleve": _n, "type": "تشجيع",
                                                "motif": "المواظبة والانضباط"})
            fp.afficher()
            photo(f, "70_fiche_eleve")
            fp.choisir_section("comportement")
            photo(fp.c_dossier, "70_fiche_dossier_comportement")
            fp.choisir_section("parcours")
            fp.g_etapes.grab().save(str(sortie / "70_fiche_eleve_etapes.png"))
            import shutil as _sh2
            _sh2.copy(_fe.generer(f.conn, f.dossier, [fp.eid], fp.p["annee"], _gr), sortie / "70_fiche_eleve.docx")
    except Exception as e:  # noqa: BLE001
        print("fiche_eleve:", repr(e))
    cid = vsx.enregistrer_club(f.conn, "النادي البيئي", None, "التربية على البيئة", "الأربعاء 15:00-16:00")
    vsx.enregistrer_activite(f.conn, vsx.Activite("يوم وطني أو دولي", "ذكرى المسيرة الخضراء", None, "جميع الأطر",
                                                  "جميع التلاميذ", "نونبر", statut="prevue"))
    vsx.enregistrer_activite(f.conn, vsx.Activite("نشاط نادٍ تربوي", "حملة نظافة", cid, "منشط النادي", "أعضاء النادي",
                                                  "شهر أكتوبر"))
    f.aller_a("الأندية والأنشطة")
    photo(f, "40_vie_scolaire")
    from idara.services import riyada as ryx
    an_ = __import__("idara.services.annee", fromlist=["x"]).libelle_pour_date()
    cl_ = ryx.classes(f.conn, an_)[0]
    for ph, vals in ((0, {"ar": 55, "fr": 60.5, "ma": 58}), (1, {"ar": 62, "fr": 75.94, "ma": 64}),
                     (3, {"ar": 66, "fr": 65.51, "ma": 70})):
        ryx.enregistrer_isa(f.conn, an_, cl_, ph, vals)
    from idara.services import isa as isax
    for ph, n in ((-1, (3, 8, 12)), (0, (6, 9, 8)), (1, (9, 8, 6))):
        for m in isax.MATIERES:
            isax.enregistrer(f.conn, an_, cl_, m, ph, *n)
    f.aller_a("الريادة")
    photo(f, "41_riyada")
    from idara.services import conseils_etab as cex
    cex.enregistrer_membres(f.conn, "gestion", [(n or f"العضو {i}", q) for i, (n, q, _) in
                                                 enumerate(cex.proposition(f.conn, "gestion"))])
    cex.enregistrer_seance(f.conn, cex.Seance("gestion", "2026-10-03", [cex.SUGGESTIONS["gestion"][0],
                                                                        cex.SUGGESTIONS["gestion"][1]]))
    cex.enregistrer_seance(f.conn, cex.Seance("gestion", (__import__("datetime").date.today() +
                                                          __import__("datetime").timedelta(days=12)).isoformat(),
                                              [cex.SUGGESTIONS["gestion"][2]], "15:00"))
    f.aller_a("مجالس المؤسسة")
    f.page_conseils_etab.rafraichir()
    photo(f, "42_conseils_etab")
    try:
        _pc = f.page_conseils_etab
        photo(_pc, "42b_conseils_page_complete")
        _pc.ouvrir_programmation("gestion")
        photo(_pc.fiche_seance, "42c_conseils_convocation")
        _pc.fiche_seance.hide()
        _pc.ouvrir_pv()
        photo(_pc.fiche_seance, "42d_conseils_pv")
        _pc.fiche_seance.hide()
        _pc.ouvrir_composition("gestion")
        photo(_pc.fiche_compo, "42e_conseils_composition")
        _pc.fiche_compo.hide()
    except Exception as _e:  # noqa: BLE001
        print("conseils:", repr(_e))
    f.aller_a("تسليم المهام")
    photo(f, "29_section_a_venir")
    f.aller_a("الموارد البشرية")
    photo(f, "30_sections_onglets")
    f.aller_a("تتبع السلوك")
    photo(f, "43_navigation_fils")
    f.aller_a("الجرد")
    photo(f, "44_fil_a_venir")
    f.aller_a("التنظيم التربوي")
    photo(f, "45_tanzim_tarbawi")
    f.aller_a("الامتحان")
    photo(f, "46_examen")
    # المظاهر والصفحات الجديدة (اقتراح المدير 2026-11-06)
    for nom in ("marine", "violet", "classique", "maghribi"):
        f.appliquer_theme(nom)
        f.aller_a("لوحة القيادة")
        photo(f, f"50_theme_{nom}_tableau")
        f.aller_a("الإحصائيات")
        photo(f, f"51_theme_{nom}_statistiques")
        f.aller_a("دليل الاستخدام")
        photo(f, f"52_theme_{nom}_guide")
    # السنوات الدراسية (طلب المدير 2026-11-12)
    d_an = f.gerer_annees()
    d_an.nouvelle("2025/2026", confirmer=False)
    photo(d_an, "60_annees_dialogue")
    d_an.close()
    f.aller_a("لوحة القيادة")
    photo(f, "61_annee_archive_bandeau")
    f.bandeau_archive.revenir()
    f.aller_a("التسجيلات")
    photo(f, "54_inscriptions")
    f.aller_a("تتبع الغياب")
    pa = f.page_absences
    pa.mois.setCurrentIndex(pa.mois.findData("2026-10"))
    if hasattr(pa, 'jours'):
        pa.jours.setValue(20)
    for i in range(pa.table.rowCount()):
        pa.table.item(i, 3).setText(str(96 - i % 4))
    pa.enregistrer()
    pa.mois.setCurrentIndex(pa.mois.findData("2026-11"))
    if hasattr(pa, 'jours'):
        pa.jours.setValue(18)
    for i in range(pa.table.rowCount()):
        pa.table.item(i, 3).setText(str(97 - i % 3))
    pa.enregistrer()
    photo(f, "55_absences")
    with f.conn:   # أستاذة وهمية للدعم
        f.conn.execute("INSERT OR IGNORE INTO personnel(nom_ar, prenom_ar, sexe, categorie, ppr) VALUES "
                       "('التجريبية', 'سعاد', 'F', 'enseignant', '7654329')")
    f.aller_a("الدعم التربوي")
    ps = f.page_soutien
    ps.nom_etape.setText("الدعم المرحلي الأول")
    ps.ajouter_etape()
    if ps.creer_groupe():
        ps.cocher(list(range(min(4, ps.t_classe.rowCount()))))
        ps.affecter()
        for i in range(ps.t_membres.rowCount()):
            ps.t_membres.item(i, 2).setText(str(3 + i % 3))
            ps.t_membres.item(i, 3).setText(str(5 + i % 4))
        ps.enregistrer_notes()
        ps.h_debut.setText("14:30")
        ps.h_fin.setText("15:30")
        ps.ajouter_seance()
    photo(f, "56_soutien")
    from tests.fabrique_projet import rapport_plan_action   # خطة عمل وهمية
    f.aller_a("مشروع المؤسسة")
    pp = f.page_projet
    pp.intitule.setText("مشروع المؤسسة المندمج")
    pp.debut.setCurrentIndex(pp.debut.findData("2025/2026"))
    pp.fin.setCurrentIndex(pp.fin.findData("2027/2028"))
    if pp.enregistrer_projet():
        from idara.services import projet_etab as pe
        pe.enregistrer_cibles(f.conn, pp.pid(), [
            ("tarl", "ref", 35, None), ("tarl", "2025/2026", 40, 38), ("tarl", "2026/2027", 50, None),
            ("tarl", "2027/2028", 60, None), ("hadar", "ref", 3, None), ("hadar", "2025/2026", 2.5, 2.8),
            ("hadar", "2026/2027", 2, None), ("hadar", "2027/2028", 1.5, None), ("activites", "ref", 15, None),
            ("activites", "2025/2026", 25, 22), ("activites", "2026/2027", 35, None),
            ("activites", "2027/2028", 45, None)])
        pp.importer(rapport_plan_action(Path(tempfile.mkdtemp()) / "plan.xlsx"))
        if pp.t_ops.rowCount():
            pp.t_ops.cellWidget(0, 5).setCurrentIndex(pp.t_ops.cellWidget(0, 5).findData("realisee"))
            pp.enregistrer_suivi()
    photo(f, "57_projet_etablissement")
    # الرحاب والسجلات (2026-11-14)
    from idara.ui.fenetre import SECTIONS
    titres = [t for t, _ in SECTIONS]
    for num, t in (("60", "الحياة المدرسية"), ("61", "التلاميذ"), ("62", "الموارد البشرية")):
        f.ouvrir_rahba(titres.index(t))
        photo(f, f"{num}_rahba")
    f.aller_a("الصحة والسلامة")
    v = f.page_sante.vue()
    if v.w["eleve"].count() > 1:
        v.w["eleve"].setEditText(v.w["eleve"].itemText(1))
        v.remplir({"date": "2026-11-10", "lieu": "الساحة", "description": "سقوط أثناء الاستراحة", "declare": "نعم"})
        v.enregistrer()
    photo(f, "63_registre_accidents")
    try:
        if v.lignes:
            _fd = v.ouvrir_dossier(v.lignes[0]["id"])
            photo(_fd, "63_accident_dossier")
            _fd.hide()
        _fn = v.ouvrir_nouveau()
        photo(_fn, "63_accident_nouveau")
        _fn.hide()
    except Exception as e:  # noqa: BLE001
        print("capture accidents:", e)
    f.aller_a("خليتا اليقظة والإنصات")
    photo(f, "64_cellules")
    f.aller_a("التحفيز والتهاني")
    photo(f, "65_tahfiz")
    # الإعلانات المزخرفة والاستدعاءات (2026-11-15)
    try:
        from PySide6.QtCore import QRectF as _R
        from PySide6.QtGui import QPainter as _P, QPixmap as _PM
        from idara.services import affiches as _af
        from idara.services import convocations as _cv
        from idara.ui import affiche_qt as _aq
        f.aller_a("الإعلام والتواصل")
        va = f.page_annonces.vue("affiche")
        va.choisir_theme("arche")
        va.date.definir("2026-09-07")
        va.heure.setText("8:30 صباحاً")
        va.lieu.setText("ساحة المؤسسة")
        va.actualiser()
        app.processEvents()
        photo(f, "67_affiches_page")
        _c = va.contenu()
        _c.note = "المرجو إحضار اللوازم المدرسية"
        planche = _PM(5 * 520, 2 * 735)
        planche.fill(Qt.gray)
        _q = _P(planche)
        for _k, _cle in enumerate(_af.THEMES):
            _aq.peindre(_q, _af.composer(_cle, _c), _R(10 + (_k % 5) * 520, 10 + (_k // 5) * 735, 500, 707))
        _q.end()
        planche.save(str(sortie / "68_affiches_planche.png"))
        _aq.exporter_pdf(_af.composer("zellige", _c), "A3", sortie / "68_affiche_A3.pdf")
        f.page_annonces.choisir("convocations")
        app.processEvents()
        photo(f, "69_convocations")
        import shutil as _sh
        _doc = _cv.generer(f.conn, f.dossier, "rencontre", "02", "2026-11-21", "10:00", "قاعة الاجتماعات",
                           "تتبع النتائج", 6, None, [e["id"] for e in _cv.eleves(f.conn)[:6]])
        _ed = f.ouvrir_document(_doc)
        if _ed is not None:
            _ed.exporter_pdf(sortie / "69_convocations.pdf")
            f.fermer_document()
        _sh.copy(_doc, sortie / "69_convocations.docx")
    except Exception as e:  # noqa: BLE001
        import traceback
        print("affiches:", traceback.format_exc())
    from idara.services import registres as _rg   # محرر الوثائق (2026-11-15)
    try:
        _rg.enregistrer(f.conn, "agents", {"nom": "عون تجريبي", "fonction": "الحراسة", "societe": "شركة وهمية",
                                           "telephone": "0600000000", "horaire": "8:00 - 16:00"})
        ed = f.ouvrir_document(_rg.generer(f.conn, f.dossier, "agents", "liste"))
        if ed is not None:
            app.processEvents()
            photo(f, "66_editeur_apercu")
            ed.b_modifier.click()
            app.processEvents()
            photo(f, "66_editeur_modification")
            ed.exporter_pdf(sortie / "66_editeur.pdf")
            ed.exporter_image(sortie / "66_editeur_image.png")
            ed.b_retour.click()
    except Exception as e:  # noqa: BLE001
        print("editeur:", repr(e))
    # الحراسة بالمناطق (توجيه 2026-11-15): أساتذة وهميون
    try:
        from datetime import date as _date, timedelta as _td
        from idara.services import garde as _gd
        _g = _gd.lire(f.conn)
        _g.update(nb_zones=5, zones=["الباب الرئيسي", "الساحة الشمالية", "الساحة الجنوبية", "المرافق الصحية",
                                     "الملعب"], semaines=4,
                  debut=(_date.today() - _td(days=_date.today().weekday())).isoformat())
        _g["grille"] = _gd.repartir([f"أستاذ(ة) وهمي(ة) {i}" for i in range(1, 16)], 5, 4, _g["jours"])
        _gd.enregistrer(f.conn, _g)
        f.page_garde.rafraichir()
        f.aller_a("جدول الحراسة")
        photo(f, "71_garde_zones")
        import shutil as _sh3
        _sh3.copy(_gd.generer(f.conn, f.dossier, "tableau"), sortie / "71_garde_tableau.docx")
        _sh3.copy(_gd.generer(f.conn, f.dossier, "note"), sortie / "71_garde_note.docx")
        f.tableau.rafraichir()
        f.aller_a("لوحة القيادة")
        photo(f, "72_tableau_garde_jour")
    except Exception as e:  # noqa: BLE001
        print("garde:", repr(e))
    # ---- طلب المدير 2026-11-19 ----
    try:
        from datetime import date as _d, timedelta as _td

        from idara.services import memo as _mm
        from idara.services import pionniere as _pn
        f.aller_a("نتائج الريادة")
        photo(f, "80_pionniere_resultats")
        _pn.enregistrer_rencontre(f.conn, _pn.Rencontre("rencontre", _d.today().isoformat(), "نتائج المرحلة الأولى",
                                                        "15:00", 60, 44, "عرض النتائج", "تتبع الواجبات"))
        _pn.enregistrer_rencontre(f.conn, _pn.Rencontre("portes", (_d.today() + _td(days=9)).isoformat(),
                                                        "الأبواب المفتوحة", invites=80))
        f.aller_a("تواصل الريادة")
        photo(f, "81_pionniere_communication")
        f.page_comm_pionniere.ouvrir_rencontre(type_="rencontre")
        photo(f.page_comm_pionniere.fiche, "81b_pionniere_rencontre_popup")
        f.page_comm_pionniere.fiche.hide()
        f.aller_a("مؤشرات الريادة")
        photo(f, "82_pionniere_indicateurs")
        for i, (suj, j, h, c) in enumerate((("زيارة المفتش التربوي", 0, "09:30", "jaune"),
                                            ("تسليم الإحصاء السنوي للمديرية", 1, "11:00", "rose"),
                                            ("اجتماع مجلس التدبير", 3, "15:00", "vert"),
                                            ("تتبع ملفات الأساتذة الوافدين", 5, "", "bleu"),
                                            ("الاتصال بجمعية الآباء", 8, "10:00", "orange"))):
            _mm.enregistrer(f.conn, _mm.Memo(suj, (_d.today() + _td(days=j)).isoformat(), h, couleur=c))
        f.aller_a("مفكرة المدير")
        photo(f, "83_mofakkira")
        f.page_memo.nouveau("rose")
        photo(f.page_memo.fiche, "83b_mofakkira_popup")
        f.page_memo.fiche.hide()
        f.aller_a("التواصل")
        photo(f, "84_contact")
        f.aller_a("استعمالات الزمن")
        photo(f, "85_emplois")
        f.page_emplois.mode.setCurrentIndex(1)
        photo(f, "85b_emplois_collectif")
        f.aller_a("ملفات الأساتذة")
        photo(f, "86_dossiers_profs_suivi")
        f.aller_a("سجل الصادر")
        f.page_sortants.ouvrir_structure()
        photo(f.page_sortants.fiche_structure, "87_structure_direction")
        f.page_sortants.fiche_structure.hide()
        f.aller_a("التلاميذ")
        photo(f, "88_eleves_filtres")
        f.aller_a("مجالس المؤسسة")
        photo(f.page_conseils_etab, "89_conseils_liste")
        f.aller_a("الموارد البشرية")
        photo(f, "90_personnel_triangles")
        from idara.services import logements as _lg
        _l = _lg.enregistrer_logement(f.conn, _lg.Logement("سكن الوحدة المركزية", "77/1", nature="صلب"))
        _c = _lg.enregistrer_concours(f.conn, _lg.Concours(_l, _d.today().isoformat(), "", "", rural=True))
        f.aller_a("السكنيات")
        photo(f, "91_logements")
        f.page_logements.ouvrir_points(_c)
        photo(f.page_logements.fiche_points, "91b_logements_points")
        f.page_logements.fiche_points.hide()
        _e = f.ouvrir_document(_lg.generer(f.conn, f.dossier, "demande", _c))
        if _e is not None:
            _e.basculer_edition(True)
            photo(f, "92_editeur_ruban")
            _e.choisir_onglet(2)
            photo(f, "92b_editeur_mise_en_page")
            f.fermer_document()
    except Exception as _e:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        print("2026-11-19:", repr(_e))
    f.filtrer_nav("محضر")
    photo(f, "53_recherche_nav")
    f.filtrer_nav("")
    f.close()
    app.quit()
    print("captures:", sorted(p.name for p in sortie.glob("*.png")))


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "captures"))
