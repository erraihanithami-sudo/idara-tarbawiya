"""ملف الموظفين. أسماء وأرقام وهمية."""

import pytest

from idara.services import etablissement as et
from idara.services import import_eleves as imp
from idara.services import personnel as rh
from tests.fabrique_massar import classeur
from tests.test_import_massar import AR, FR


@pytest.fixture
def base(tmp_path, dossier, conn):
    et.appliquer_configuration_initiale(conn, dossier, et.ConfigurationInitiale(
        etablissement=et.Etablissement(nom_ar="مدرسة تجريبية", direction_ar="م", academie_ar="أ"),
        directeur=et.Directeur(nom_ar="المدير", prenom_ar="أحمد", sexe="M", ppr="1000000"),
        annee="2026/2027", unites=["الوحدة المركزية", "وحدة فرعية"]))
    r = imp.analyser(conn, [classeur(tmp_path / "a.xlsx", AR), classeur(tmp_path / "f.xlsx", FR, "fr")])
    imp.appliquer(conn, dossier, r)
    return conn


def _prof(**k):
    d = dict(nom_ar="الأستاذة", prenom_ar="فاطمة", sexe="F", categorie="enseignant", ppr="1234567",
             cin="ab 123456", telephone="06 12 34 56 78", cadre="أستاذ(ة) التعليم الابتدائي",
             grade="الدرجة الأولى", fonction="التدريس", cycle="الابتدائي", matiere="عربية",
             heures_hebdo="30", adresse="حي تجريبي", date_affectation="2015-09-01")
    d.update(k)
    return rh.Personnel(**d)


def _classe(conn, code):
    return conn.execute("SELECT id FROM classe WHERE code=?", (code,)).fetchone()[0]


def test_directeur_present_depuis_le_parametrage(base):
    tous = rh.lister(base)
    assert [(p.categorie, p.prenom_ar) for p in tous] == [("directeur", "أحمد")]
    assert rh.effectifs(base)["directeur"] == 1


def test_ajout_normalisation_et_lecture(base):
    pid = rh.enregistrer(base, _prof())
    p = rh.lire(base, pid)
    assert p.cin == "AB123456" and p.telephone == "0612345678" and p.heures_hebdo == 30
    assert rh.effectifs(base)["enseignant"] == 1
    assert [x.prenom_ar for x in rh.lister(base, "فاطمه")] == []  # لا تطابق مع خطأ إملائي
    for t in ("فاطمة", "الأستاذة فاطمة", "1234567", "ab123456"):
        assert [x.id for x in rh.lister(base, t)] == [pid], t
    assert [x.id for x in rh.lister(base, categorie="gardien")] == []
    assert set(rh.suggestions(base, "fonction")) == {"التدريس", "الإدارة التربوية"}


@pytest.mark.parametrize("modif, message", [
    (dict(nom_ar=""), "إجبارية"), (dict(sexe=""), "إجبارية"), (dict(ppr="12a"), "أرقام"),
    (dict(cin="123"), "البطاقة"), (dict(telephone="12345"), "الهاتف"), (dict(heures_hebdo="x"), "عدد صحيح"),
    (dict(heures_hebdo="99"), "معقولة"), (dict(date_affectation="2099-01-01"), "المستقبل"),
    (dict(statut="retraite"), "تاريخ المغادرة"), (dict(categorie="directeur"), "إعداد المؤسسة"),
    (dict(unite="غير موجودة"), "الوحدة"), (dict(cadre="أستاذة"), "الإطار: اختر"),
    (dict(grade="الأولى"), "الدرجة: اختر"), (dict(matiere="الرياضيات"), "اختر من القائمة"),
])
def test_refus(base, modif, message):
    with pytest.raises(rh.ErreurPersonnel, match=message):
        rh.enregistrer(base, _prof(**modif))


def test_unicite(base):
    rh.enregistrer(base, _prof())
    with pytest.raises(rh.ErreurPersonnel, match="رقم التأجير"):
        rh.enregistrer(base, _prof(cin="CD1"))
    with pytest.raises(rh.ErreurPersonnel, match="البطاقة"):
        rh.enregistrer(base, _prof(ppr="7654321"))
    with pytest.raises(rh.ErreurPersonnel, match="رقم التأجير"):
        rh.enregistrer(base, _prof(ppr="1000000", cin=""))  # رقم المدير


def test_directeur_modifiable_mais_pas_depart(base):
    d = rh.lister(base, categorie="directeur")[0]
    d.cin, d.cadre, d.cycle = "Z99", "متصرف(ة) تربوي(ة)", "ابتدائي"
    rh.enregistrer(base, d)
    assert et.directeur_actuel(base)["cin"] == "Z99"
    assert rh.lire(base, d.id).cycle == ""  # السلك لا يخص المدير
    d.categorie = "enseignant"
    with pytest.raises(rh.ErreurPersonnel, match="إعداد المؤسسة"):
        rh.enregistrer(base, d)
    with pytest.raises(rh.ErreurPersonnel, match="مدير جديد"):
        rh.depart(base, d.id, "mute", "2026-12-01")


def test_classes_et_enseignement(base):
    c1, c2 = _classe(base, "PS1-PS2"), _classe(base, "4APG-5APG-6APG")
    p = _prof(classes=[c2, c1])
    pid = rh.enregistrer(base, p)
    p = rh.lire(base, pid)
    assert sorted(p.classes) == sorted([c1, c2])
    e = rh.enseignement(base, p)
    assert e["niveau"] == "، ".join(__import__("idara.services.textes", fromlist=["x"]).niveau_ar(n)
                                    for n in ["PS1", "PS2", "4AP", "5AP", "6AP"])
    assert e["nb_eleves"] == 5 and e["source"] == "أقسام"
    assert "فاطمة" in {r["code"]: r["enseignants"] for r in rh.classes_annee(base)}["PS1-PS2"]
    # تلميذ مغادر لا يُحسب
    from idara.services import eleves as el
    eid = base.execute("SELECT id FROM eleve WHERE code_massar='X000000001'").fetchone()[0]
    el.changer_statut(base, eid, "parti", "2026-12-01", "مدرسة أخرى")
    assert rh.enseignement(base, rh.lire(base, pid))["nb_eleves"] == 4
    with pytest.raises(rh.ErreurPersonnel, match="قسم"):
        rh.enregistrer(base, _prof(ppr="", cin="", classes=[9999]))


def test_enseignement_manuel_et_manquants(base):
    p = _prof(heures_hebdo="", adresse="")
    pid = rh.enregistrer(base, p)
    p = rh.lire(base, pid)
    m = rh.manquants_documents(base, p)
    assert m == ["العنوان الشخصي", "ساعات العمل", "مستوى التدريس (أو إسناد قسم)", "عدد التلاميذ (أو إسناد قسم)"]
    p.niveau_enseigne, p.nb_eleves, p.heures_hebdo, p.adresse = "الرابع", "28", 30, "حي"
    rh.enregistrer(base, p)
    assert rh.manquants_documents(base, rh.lire(base, pid)) == []
    gardien = rh.lire(base, rh.enregistrer(base, rh.Personnel(nom_ar="الحارس", prenom_ar="علي", sexe="M",
                                                               categorie="gardien")))
    assert "مادة التدريس" not in rh.manquants_documents(base, gardien)


def test_depart_et_reintegration(base):
    c = _classe(base, "PS1-PS2")
    pid = rh.enregistrer(base, _prof(classes=[c]))
    rh.depart(base, pid, "retraite", "2027-07-01", "تقاعد حد السن")
    p = rh.lire(base, pid)
    assert p.statut == "retraite" and p.classes == [] and "حد السن" in p.remarques
    assert rh.lister(base, "فاطمة") == []
    assert [x.id for x in rh.lister(base, "فاطمة", actifs_seulement=False)] == [pid]
    assert rh.effectifs(base)["enseignant"] == 0
    rh.reintegrer(base, pid)
    assert rh.lire(base, pid).statut == "actif" and rh.lire(base, pid).date_depart == ""


def test_unite(base):
    pid = rh.enregistrer(base, _prof(unite="وحدة فرعية"))
    assert rh.lire(base, pid).unite == "وحدة فرعية"


# ---------- المسار المهني (طلب المدير: لازم لتحديد الفائض) ----------

def _carriere(**k):
    d = dict(date_naissance="1980-03-15", date_recrutement="2003-09-16", date_affectation_academie="2003-09-16",
             date_affectation_direction="2008-09-01", date_affectation="2015-09-01")
    d.update(k)
    return _prof(**d)


def test_carriere_enregistree_et_anciennetes(base):
    from datetime import date
    pid = rh.enregistrer(base, _carriere())
    p = rh.lire(base, pid)
    assert p.date_recrutement == "2003-09-16" and p.date_affectation_direction == "2008-09-01"
    assert rh.manquants_carriere(p) == []
    a = rh.anciennetes(p, date(2026, 11, 1))
    assert a == {"age": 46, "fonction": 23, "academie": 23, "direction": 18, "etablissement": 11}
    assert rh.anciennetes(p, date(2026, 3, 14))["age"] == 45  # قبل يوم الميلاد


def test_carriere_manquante_signalee_pour_enseignants(base):
    p = rh.lire(base, rh.enregistrer(base, _prof(date_affectation="")))
    assert rh.manquants_carriere(p) == ["تاريخ الازدياد", "تاريخ التوظيف", "تاريخ التعيين بالأكاديمية",
                                        "تاريخ التعيين بالمديرية الإقليمية", "تاريخ التعيين بالمؤسسة"]
    g = rh.lire(base, rh.enregistrer(base, rh.Personnel(nom_ar="الحارس", prenom_ar="علي", sexe="M",
                                                        categorie="gardien")))
    assert rh.manquants_carriere(g) == []


@pytest.mark.parametrize("modif, message", [
    (dict(date_naissance="2015-01-01"), "أقل من 18"),
    (dict(date_recrutement="1995-01-01"), "عند التوظيف"),
    (dict(date_recrutement="2005-09-16", date_affectation_academie="2005-01-01"), "الأكاديمية قبل تاريخ التوظيف"),
    (dict(date_recrutement="2005-09-16", date_affectation_academie="", date_affectation_direction="2005-01-01"),
     "المديرية الإقليمية قبل تاريخ التوظيف"),
    (dict(date_affectation="2005-01-01"), "المؤسسة قبل تاريخ التعيين بالمديرية"),
    (dict(date_recrutement="2099-01-01"), "المستقبل"),
    (dict(date_naissance="1980-02-30"), "غير صحيح"),
])
def test_carriere_incoherente(base, modif, message):
    with pytest.raises(rh.ErreurPersonnel, match=message):
        rh.enregistrer(base, _carriere(**modif))


def test_reference_academies_pour_affectation_ancienne(base):
    """قرار المدير: المعيّن بالمديرية قبل إحداث الأكاديميات ← 01/09/2002 تاريخاً للتعيين بالأكاديمية."""
    from datetime import date
    pid = rh.enregistrer(base, _carriere(date_naissance="1965-05-10", date_recrutement="1987-09-16",
                                         date_affectation_academie="", date_affectation_direction="1990-09-01",
                                         date_affectation="1998-09-01"))
    p = rh.lire(base, pid)
    assert p.date_affectation_academie == "2002-09-01"
    assert rh.anciennetes(p, date(2026, 11, 1))["academie"] == 24
    rh.enregistrer(base, p)  # إعادة الحفظ بنفس التاريخ مقبولة
    with pytest.raises(rh.ErreurPersonnel, match="01/09/2002"):
        rh.enregistrer(base, _carriere(ppr="", cin="", date_recrutement="1987-09-16",
                                       date_affectation_academie="1995-01-01",
                                       date_affectation_direction="1990-09-01", date_affectation="1998-09-01"))


@pytest.mark.parametrize("modif, message", [
    (dict(date_recrutement="1990-09-16", date_affectation_academie="2001-09-01",
          date_affectation_direction="2008-09-01"), "قبل إحداث الأكاديميات"),
    (dict(date_affectation_academie="2009-09-01"), "بعد تاريخ التعيين بالمديرية"),
])
def test_academie_coherente(base, modif, message):
    with pytest.raises(rh.ErreurPersonnel, match=message):
        rh.enregistrer(base, _carriere(**modif))



@pytest.mark.parametrize("cadre, sexe, attendu", [
    ("أستاذ(ة) التعليم الابتدائي", "F", "أستاذة التعليم الابتدائي"),
    ("أستاذ(ة) التعليم الابتدائي", "M", "أستاذ التعليم الابتدائي"),
    ("متصرف(ة) تربوي(ة)", "F", "متصرفة تربوية"), ("متصرف(ة) تربوي(ة)", "M", "متصرف تربوي")])
def test_cadre_accorde(cadre, sexe, attendu):
    assert rh.cadre_accorde(cadre, sexe) == attendu
    assert rh.grade_court("الدرجة الممتازة") == "الممتازة"
