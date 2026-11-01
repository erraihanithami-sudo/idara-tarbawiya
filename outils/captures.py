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
    r.c["cadre"].setEditText("أستاذة التعليم الابتدائي")
    r.matiere.setCurrentIndex(r.matiere.findData("عربية"))
    r.c["heures_hebdo"].setText("30")
    r.classes.item(0).setCheckState(Qt.Checked)
    for k, v in (("date_naissance", "15/03/1980"), ("date_recrutement", "16/09/2003"),
                 ("date_affectation_academie", "16/09/2003"), ("date_affectation_direction", "01/09/2008"),
                 ("date_affectation", "01/09/2015")):
        r.dates[k].setText(v)
    r.enregistrer()
    photo(f, "21_personnel_fiche")
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
        "الأولى", "التدريس", "ابتدائي", "حي تجريبي", "0600000000")
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
    f.aller_a("التقييم")
    photo(f, "29_section_a_venir")
    f.aller_a("الموارد البشرية")
    photo(f, "30_sections_onglets")
    f.close()
    app.quit()
    print("captures:", sorted(p.name for p in sortie.glob("*.png")))


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "captures"))
