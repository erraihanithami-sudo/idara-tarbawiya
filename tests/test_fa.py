"""تدبير الفائض حسب المذكرة الإطار وقرارات المدير. أسماء وتواريخ وهمية."""

from datetime import date

import pytest

from idara.services import etablissement as et
from idara.services import fa
from idara.services import personnel as rh


@pytest.fixture
def base(dossier, conn):
    et.appliquer_configuration_initiale(conn, dossier, et.ConfigurationInitiale(
        etablissement=et.Etablissement(nom_ar="مدرسة تجريبية", direction_ar="م", academie_ar="أ"),
        directeur=et.Directeur(nom_ar="المدير", prenom_ar="أحمد", sexe="M"), annee="2026/2027"))
    return conn


_n = iter(range(1000))


def prof(conn, prenom, recrut, direction, etab, naissance="1980-01-01", matiere="عربية", **k):
    return rh.enregistrer(conn, rh.Personnel(
        nom_ar="التجريبي", prenom_ar=prenom, sexe="M", categorie="enseignant", matiere=matiere,
        ppr=str(1000000 + next(_n)), date_naissance=naissance, date_recrutement=recrut,
        date_affectation_direction=direction, date_affectation=etab, **k))


@pytest.mark.parametrize("d, debut", [("2015-09-01", 2015), ("2016-06-30", 2015), ("2016-08-31", 2015),
                                      ("2016-09-16", 2016)])
def test_debut_saison(d, debut):
    assert fa.debut_saison(date.fromisoformat(d)) == debut


def test_saisons_incluent_la_saison_courante():
    """قرار المدير: كل موسم بسنة، بما فيه الموسم الجاري."""
    assert fa.saisons("2026-09-01", 2026) == 1
    assert fa.saisons("2015-09-01", 2026) == 12
    assert fa.saisons("2016-01-10", 2026) == 12  # التحق في يناير: موسم 2015/2016 يُحتسب


def test_calcul_classement_et_fa(base):
    a = prof(base, "أقدم", "2003-09-16", "2003-09-16", "2010-09-01")
    b = prof(base, "متوسط", "2010-09-16", "2010-09-16", "2018-09-01")
    c = prof(base, "حديث", "2020-09-16", "2020-09-16", "2023-09-01")
    groupes, sans = fa.calculer(base)
    g = next(x for x in groupes if x.matiere == "عربية")
    assert g.requis is None and not g.definitif and g.fa == []  # بدون عدد المناصب لا يُحدد الفائض
    l = {x.p.id: x for x in g.lignes}
    # 2003/04 → 2026/27 = 24 موسماً؛ المؤسسة 2010/11 → 17 موسماً ×2
    assert (l[a].generale, l[a].direction, l[a].etablissement, l[a].total) == (24, 24, 17, 82)
    assert (l[c].generale, l[c].direction, l[c].etablissement, l[c].total) == (7, 7, 4, 22)
    assert [x.rang for x in (l[a], l[b], l[c])] == [1, 2, 3]
    fa.definir_postes(base, "عربية", 2)
    g = next(x for x in fa.calculer(base)[0] if x.matiere == "عربية")
    assert g.definitif and [x.p.id for x in g.fa] == [c]
    assert {x.p.id: x.resultat for x in g.lignes} == {a: "maintenu", b: "maintenu", c: "fa"}


def test_departage(base):
    # نفس المجموع (المؤسسة تعوض الأقدمية العامة)، الأقدمية العامة تحسم
    x = prof(base, "عامة_أكبر", "2005-09-16", "2015-09-01", "2020-09-01")   # 22+12+7*2=48
    y = prof(base, "مؤسسة_أكبر", "2007-09-16", "2015-09-01", "2019-09-01")  # 20+12+8*2=48
    fa.definir_postes(base, "عربية", 1)
    g = next(g for g in fa.calculer(base)[0] if g.matiere == "عربية")
    l = {i.p.id: i for i in g.lignes}
    assert l[x].total == l[y].total == 48
    assert l[x].resultat == "maintenu" and l[y].resultat == "fa"


def test_departage_par_age_le_plus_jeune_est_fa(base):
    """قرار المدير: عند التساوي التام، الأصغر سناً هو الفائض."""
    vieux = prof(base, "الأكبر", "2010-09-16", "2010-09-16", "2015-09-01", naissance="1975-05-01")
    jeune = prof(base, "الأصغر", "2010-09-16", "2010-09-16", "2015-09-01", naissance="1985-05-01")
    fa.definir_postes(base, "عربية", 1)
    g = next(g for g in fa.calculer(base)[0] if g.matiere == "عربية")
    assert [l.p.id for l in g.fa] == [jeune]
    assert next(l for l in g.lignes if l.p.id == vieux).resultat == "maintenu"


def test_exemptions(base):
    ag = prof(base, "مبرز", "2022-09-16", "2022-09-16", "2023-09-01", exemption_fa="agrege")
    doc_ok = prof(base, "دكتوراه_قديمة", "2015-09-16", "2015-09-16", "2024-09-01",
                  exemption_fa="doctorat", date_exemption_fa="2019-07-01")
    doc_recent = prof(base, "دكتوراه_حديثة", "2015-09-16", "2015-09-16", "2024-09-01",
                      exemption_fa="doctorat", date_exemption_fa="2024-07-01")
    autre = prof(base, "عادي", "2000-09-16", "2000-09-16", "2001-09-01")
    fa.definir_postes(base, "عربية", 3)
    g = next(g for g in fa.calculer(base, date(2026, 11, 1))[0] if g.matiere == "عربية")
    r = {l.p.id: l.resultat for l in g.lignes}
    # المستثنيان يشغلان منصبين، فيبقى منصب واحد للمرتبين
    assert r == {ag: "exempte", doc_ok: "exempte", autre: "maintenu", doc_recent: "fa"}
    with pytest.raises(rh.ErreurPersonnel, match="الدكتوراه"):
        prof(base, "ب", "2015-09-16", "2015-09-16", "2024-09-01", exemption_fa="doctorat")


def test_incomplets_et_sans_matiere(base):
    ok = prof(base, "كامل", "2010-09-16", "2010-09-16", "2015-09-01")
    inc = rh.enregistrer(base, rh.Personnel(nom_ar="ن", prenom_ar="ناقص", sexe="F", categorie="enseignant",
                                            matiere="عربية", date_recrutement="2012-09-16"))
    sans = rh.enregistrer(base, rh.Personnel(nom_ar="ن", prenom_ar="بلا_مادة", sexe="F", categorie="enseignant"))
    rh.enregistrer(base, rh.Personnel(nom_ar="ح", prenom_ar="حارس", sexe="M", categorie="gardien"))
    fa.definir_postes(base, "عربية", 1)
    groupes, sans_matiere = fa.calculer(base)
    g = next(g for g in groupes if g.matiere == "عربية")
    assert not g.definitif and [l.p.id for l in g.incomplets] == [inc]
    assert "تاريخ التعيين بالمؤسسة" in g.incomplets[0].motif
    assert {l.p.id: l.resultat for l in g.lignes}[ok] == "maintenu"
    assert [p.id for p in sans_matiere] == [sans]


def test_matieres_separees_et_postes(base):
    prof(base, "ع", "2010-09-16", "2010-09-16", "2015-09-01", matiere="عربية")
    f = prof(base, "ف", "2020-09-16", "2020-09-16", "2021-09-01", matiere="فرنسية")
    fa.definir_postes(base, "عربية", 1)
    fa.definir_postes(base, "فرنسية", 0)
    groupes = {g.matiere: g for g in fa.calculer(base)[0]}
    assert groupes["عربية"].fa == [] and [l.p.id for l in groupes["فرنسية"].fa] == [f]
    assert "مزدوجة" not in groupes
    fa.definir_postes(base, "فرنسية", None)
    assert fa.postes_requis(base) == {"عربية": 1}
    with pytest.raises(fa.ErreurFa):
        fa.definir_postes(base, "الرياضيات", 1)
