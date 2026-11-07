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
    f.aller_a("التلاميذ القدامى")
    a2 = f.page_anciens
    photo(f, "18_anciens_vide")
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
    photo(f, "19_anciens_certificat")
    # الموارد البشرية
    f.aller_a("الموارد البشرية")
    r = f.page_rh
    photo(f, "20_personnel_liste")
    r.nouveau()
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
    photo(f, "21_personnel_fiche")
    r.dates["date_naissance"].ouvrir_calendrier()
    QApplication.processEvents()
    __import__("PySide6.QtGui", fromlist=["x"]).QGuiApplication.primaryScreen()
    r.dates["date_naissance"].popup.grab().save(str(sortie / "21b_calendrier.png"))
    r.dates["date_naissance"].popup.close()
    f.resize(1280, 1750)
    photo(f, "22_personnel_fiche_complete")
    f.resize(1280, 800)
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
    f.page_fa.cartes["عربية"].postes.setValue(3)
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
    photo(f, "25_conge_fiche")
    f.resize(1280, 1700)
    photo(f, "26_conge_fiche_complete")
    f.resize(1280, 800)
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
    f.aller_a("حركية التلاميذ")
    photo(f, "31_mouvements")
    f.page_mouvements.r_parti.setChecked(True)
    __import__("idara.ui.saisie", fromlist=["x"]).selectionner(f.page_mouvements.liste, 0)
    photo(f, "32_mouvements_depart")
    from idara.services import comportement as cpt
    yid = f.conn.execute("SELECT id FROM eleve WHERE code_massar='X000000001'").fetchone()[0]
    cpt.enregistrer(f.conn, cpt.Observation(yid, "2026-10-05", "شغب في القسم", "", "أستاذ القسم", "تنبيه شفوي"))
    cpt.enregistrer(f.conn, cpt.Observation(yid, "2026-10-12", "عنف لفظي", "", "أستاذ القسم", ""))
    f.aller_a("تتبع السلوك")
    __import__("idara.ui.saisie", fromlist=["x"]).selectionner(f.page_comportement.liste, 0)
    photo(f, "33_comportement")
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
    f.aller_a("الريادة")
    photo(f, "41_riyada")
    from idara.services import conseils_etab as cex
    cex.enregistrer_membres(f.conn, "gestion", [(n or f"العضو {i}", q) for i, (n, q, _) in
                                                 enumerate(cex.proposition(f.conn, "gestion"))])
    cex.enregistrer_seance(f.conn, cex.Seance("gestion", "2026-10-03", [cex.SUGGESTIONS["gestion"][0],
                                                                        cex.SUGGESTIONS["gestion"][1]]))
    f.aller_a("مجالس المؤسسة")
    photo(f, "42_conseils_etab")
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
    f.aller_a("محاضر نهاية الأسدوس")
    photo(f, "47_deliberations")
    # المظاهر والصفحات الجديدة (اقتراح المدير 2026-11-06)
    for nom in ("marine", "violet", "classique"):
        f.appliquer_theme(nom)
        f.aller_a("لوحة القيادة")
        photo(f, f"50_theme_{nom}_tableau")
        f.aller_a("الإحصائيات")
        photo(f, f"51_theme_{nom}_statistiques")
        f.aller_a("دليل الاستخدام")
        photo(f, f"52_theme_{nom}_guide")
    f.aller_a("التسجيلات")
    photo(f, "54_inscriptions")
    f.aller_a("تتبع الغياب")
    pa = f.page_absences
    pa.mois.setCurrentIndex(pa.mois.findData("2026-10"))
    pa.jours.setValue(20)
    for i in range(pa.table.rowCount()):
        pa.table.item(i, 3).setText("2")
        pa.table.item(i, 4).setText(str(3 + i))
    pa.enregistrer()
    pa.mois.setCurrentIndex(pa.mois.findData("2026-11"))
    pa.jours.setValue(18)
    for i in range(pa.table.rowCount()):
        pa.table.item(i, 3).setText("1")
        pa.table.item(i, 4).setText("2")
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
    f.filtrer_nav("محضر")
    photo(f, "53_recherche_nav")
    f.filtrer_nav("")
    f.close()
    app.quit()
    print("captures:", sorted(p.name for p in sortie.glob("*.png")))


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "captures"))
