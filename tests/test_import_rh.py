"""استيراد الموظفين من ملف XML للموارد البشرية (معطيات وهمية)."""

import pytest

from idara.services import import_rh as irh
from idara.services import personnel as rh
from tests.fabrique_rh_xml import AGENTS, xml_rh
from tests.test_personnel import base  # noqa: F401


def test_lecture_et_correspondance():
    a = irh.lire_xml(xml_rh())
    assert len(a) == 3
    v = a[0].valeurs
    assert (v["nom_ar"], v["prenom_ar"], v["nom_fr"], v["prenom_fr"]) == ("الوهمي", "سعيد", "ELWAHMI", "SAID")
    assert v["cin"] == "ZZ100001" and v["sexe"] == "M" and v["date_naissance"] == "1985-03-05"
    assert v["cadre"] == "أستاذ(ة) التعليم الابتدائي" and v["grade"] == "الدرجة الأولى"
    assert v["date_grade"] == "2019-12-31" and v["echelon"] == "7" and v["date_echelon"] == "2023-11-29"
    assert v["categorie"] == "enseignant" and v["fonction"] == "التدريس" and v["cycle"] == "الابتدائي"
    assert v["matiere"] == "فرنسية" and v["heures_hebdo"] == 28
    assert v["niveau_enseigne"] == "الثالث، الرابع، الخامس، السادس"
    assert v["date_affectation"] == "2018-09-04" and v["date_recrutement"] == "2010-09-02"
    assert a[1].valeurs["nom_fr"] == "EL MITHAL" and a[1].valeurs["grade"] == "الدرجة الثانية"
    assert a[1].valeurs["matiere"] == "عربية"
    assert a[2].valeurs["categorie"] == "directeur" and a[2].valeurs["cadre"] == "متصرف(ة) تربوي(ة)"
    assert "cycle" not in a[2].valeurs


def test_grade_inconnu_signale():
    ag = list(AGENTS[0])
    ag[9] = "11090103"
    a = irh.lire_xml(xml_rh([tuple(ag)]))
    assert "grade" not in a[0].valeurs and "الدرجة" in a[0].notes[0]


def test_fichier_invalide():
    with pytest.raises(irh.ErreurImportRH):
        irh.lire_xml(b"<racine/>")
    with pytest.raises(irh.ErreurImportRH):
        irh.lire_xml(b"pas du xml")
    with pytest.raises(irh.ErreurImportRH):
        irh.lire_xml(b'<!DOCTYPE x [<!ENTITY a "b">]><DsAgentExport/>')


def test_import_puis_reimport(base):  # noqa: F811
    conn = base
    props = irh.comparer(conn, irh.lire_xml(xml_rh()))
    assert [p.etat for p in props] == ["nouveau", "nouveau", "ignore"]
    assert "إعداد المؤسسة" in props[2].raison
    assert irh.appliquer(conn, props) == {"ajoutes": 2, "maj": 0}
    p = rh.lire(conn, rh.lister(conn, "9000001")[0].id)
    assert p.matiere == "فرنسية" and p.cin == "ZZ100001"
    # تصحيح يدوي يُحترم، ومعطى خارج الملف لا يُمحى
    p.prenom_ar, p.note_inspection, p.date_inspection, p.inspecteur = "سعيد أمين", 15, "2024-01-10", "مفتش"
    p.nom_ar = "الوهمي"
    rh.enregistrer(conn, p)
    props = irh.comparer(conn, irh.lire_xml(xml_rh()))
    assert [x.etat for x in props] == ["identique", "identique", "ignore"]
    ag = list(AGENTS[0])
    ag[11] = 8
    props = irh.comparer(conn, irh.lire_xml(xml_rh([tuple(ag)])))
    assert props[0].etat == "maj" and props[0].changements == [("الرتبة", "7", "8")]
    irh.appliquer(conn, props)
    p = rh.lire(conn, p.id)
    assert p.echelon == "8" and p.prenom_ar == "سعيد أمين" and p.note_inspection == 15
    assert conn.execute("SELECT COUNT(*) FROM personnel WHERE ppr='9000001'").fetchone()[0] == 1


def test_directeur_complete_par_ppr(base):  # noqa: F811
    conn = base
    ag = list(AGENTS[2])
    ag[0] = "1000000"
    props = irh.comparer(conn, irh.lire_xml(xml_rh([tuple(ag)])))
    assert props[0].etat == "maj"
    libs = [c[0] for c in props[0].changements]
    assert "الفئة" not in libs and "النسب" not in libs and "الإطار" in libs
    irh.appliquer(conn, props)
    d = rh.lire(conn, props[0].pid)
    assert d.categorie == "directeur" and d.nom_ar == "المدير" and d.cadre == "متصرف(ة) تربوي(ة)"


def test_nom_ar_compose_et_correction_inversion(base):  # noqa: F811
    conn = base
    ag = list(AGENTS[1])
    ag[3] = "فاطمة الزهراء بن علي"
    v = irh.lire_xml(xml_rh([tuple(ag)]))[0].valeurs
    assert (v["prenom_ar"], v["nom_ar"]) == ("فاطمة", "الزهراء بن علي")   # الاسم المركب يُصحَّح يدوياً
    # موظف استورد سابقاً بالنسب والاسم مقلوبين: يُقترح التصحيح
    irh.appliquer(conn, irh.comparer(conn, irh.lire_xml(xml_rh([AGENTS[0]]))))
    p = rh.lire(conn, rh.lister(conn, "9000001")[0].id)
    p.nom_ar, p.prenom_ar = p.prenom_ar, p.nom_ar
    rh.enregistrer(conn, p)
    pr = irh.comparer(conn, irh.lire_xml(xml_rh([AGENTS[0]])))[0]
    assert pr.etat == "maj" and [c[0] for c in pr.changements] == ["النسب", "الاسم"]
    irh.appliquer(conn, [pr])
    p = rh.lire(conn, p.id)
    assert (p.nom_ar, p.prenom_ar) == ("الوهمي", "سعيد")



def test_reimport_garde_saisie_manuelle(base):  # noqa: F811
    """ساعات العمل والوحدة والمادة المدخلة يدوياً تبقى بعد إعادة الاستيراد."""
    conn = base
    irh.appliquer(conn, irh.comparer(conn, irh.lire_xml(xml_rh([AGENTS[0]]))))
    p = rh.lire(conn, rh.lister(conn, "9000001")[0].id)
    assert p.heures_hebdo == 28
    p.heures_hebdo, p.unite, p.matiere, p.telephone = 30, "وحدة فرعية", "مزدوجة", "0611111111"
    rh.enregistrer(conn, p)
    ag = list(AGENTS[0])
    ag[11] = 8   # ترقية في الرتبة: تُقترح
    pr = irh.comparer(conn, irh.lire_xml(xml_rh([tuple(ag)])))[0]
    assert pr.etat == "maj" and [c[0] for c in pr.changements] == ["الرتبة"]
    irh.appliquer(conn, [pr])
    p = rh.lire(conn, p.id)
    assert (p.heures_hebdo, p.unite, p.matiere, p.telephone, p.echelon) == (30, "وحدة فرعية", "مزدوجة",
                                                                            "0611111111", "8")
