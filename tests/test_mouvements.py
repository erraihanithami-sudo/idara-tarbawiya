"""حركية التلاميذ: الوافدون والمغادرون وطلب الملفات وإرسالها. بيانات وهمية."""

from datetime import date

import pytest

from idara.services import conges as cg
from idara.services import eleves as el
from idara.services import etablissement as et
from idara.services import import_eleves as imp
from idara.services import moteur_docx as m
from idara.services import mouvements as mv
from tests.fabrique_massar import classeur
from tests.test_import_massar import AR, FR


@pytest.fixture
def base(tmp_path, dossier, conn):
    et.appliquer_configuration_initiale(conn, dossier, et.ConfigurationInitiale(
        etablissement=et.Etablissement(nom_ar="مدرسة تجريبية", direction_ar="إقليم: المدينة", academie_ar="الجهة",
                                       ville_redaction_ar="المدينة"),
        directeur=et.Directeur(nom_ar="المدير", prenom_ar="أحمد", sexe="M"), annee="2026/2027"))
    r = imp.analyser(conn, [classeur(tmp_path / "a.xlsx", AR), classeur(tmp_path / "f.xlsx", FR, "fr")])
    imp.appliquer(conn, dossier, r)
    return conn


def _parti(conn, code="X000000003", **k):
    d = dict(sens="parti", code_massar=code, date_mouvement="2026-10-15", etablissement="المؤسسة المستقبلة",
             niveau="الرابع")
    d.update(k)
    return mv.enregistrer(conn, mv.Mouvement(**d))


def _arrive(conn, code="Y000000009", **k):
    d = dict(sens="arrive", code_massar=code, nom_ar="الوافد", prenom_ar="هبة", sexe="F",
             date_mouvement="2026-09-08", etablissement="المؤسسة الأصلية", niveau="الخامس")
    d.update(k)
    return mv.enregistrer(conn, mv.Mouvement(**d))


@pytest.mark.parametrize("brut, attendu", [
    ("إقليم: بركان", "المديرية الإقليمية ببركان"), ("عمالة: فاس", "المديرية الإقليمية لعمالة فاس"),
    ("المديرية الإقليمية لمكناس", "المديرية الإقليمية لمكناس"), ("وجدة", "المديرية الإقليمية بوجدة"), ("", "")])
def test_formule_direction(brut, attendu):
    assert mv.formule_direction(brut) == attendu


def test_formules_academie_etablissement_et_accord():
    assert mv.formule_academie("الشرق") == "الأكاديمية الجهوية للتربية والتكوين لجهة الشرق"
    assert mv.formule_academie("جهة فاس مكناس") == "الأكاديمية الجهوية للتربية والتكوين لجهة فاس مكناس"
    assert mv.formule_etablissement("قاسم أمين") == "مدرسة قاسم أمين"
    assert mv.formule_etablissement("مجموعة مدارس النور") == "مجموعة مدارس النور"
    assert [mv.al_tilmidh(s) for s in (["M"], ["F"], ["F", "F"], ["F", "M"], ["F"] * 3, ["M"] * 3)] == [
        "التلميذ", "التلميذة", "التلميذتين", "التلميذين", "التلميذات", "التلاميذ"]


def test_depart_met_a_jour_le_statut_et_alerte(base):
    mid = _parti(base)
    eid = base.execute("SELECT id FROM eleve WHERE code_massar='X000000003'").fetchone()[0]
    f = el.fiche(base, eid)
    assert f["statut"] == "parti"
    assert [r["id"] for r in mv.alertes(base)["envoi"]] == [mid]
    assert mv.etat(mv.lire(base, mid)) == "لم يُرسل الملف"
    mv.marquer(base, mid, "dossier_envoye_le", "2026-10-20")
    assert mv.alertes(base)["envoi"] == [] and "أُرسل الملف" in mv.etat(mv.lire(base, mid))
    # إعادة التسجيل تحدّث ولا تكرر
    _parti(base, etablissement="مؤسسة أخرى")
    assert len(mv.lister(base, "parti")) == 1 and mv.lister(base, "parti")[0]["etablissement"] == "مؤسسة أخرى"


@pytest.mark.parametrize("modif, message", [
    (dict(code_massar="123"), "رمز مسار"), (dict(etablissement=""), "المستقبلة"),
    (dict(date_mouvement=""), "إجباري"), (dict(date_mouvement="2099-01-01"), "المستقبل"),
    (dict(hors_province=True), "المديرية والأكاديمية"), (dict(code_massar="Z999999999"), "لا يوجد تلميذ"),
])
def test_depart_refus(base, modif, message):
    with pytest.raises(mv.ErreurMouvement, match=message):
        _parti(base, **modif)


def test_arrivee_nouvel_eleve_cree(base):
    mid = _arrive(base)
    r = mv.lire(base, mid)
    assert r["prenom_ar"] == "هبة" and r["sexe"] == "F"
    eid = r["eleve_id"]
    assert el.fiche(base, eid)["statut"] == "arrive"
    assert [x["id"] for x in mv.alertes(base)["demande"]] == [mid]
    with pytest.raises(mv.ErreurMouvement, match="النسب والاسم"):
        _arrive(base, code="Y000000008", nom_ar="")


def test_demande_dossier_et_rappel(base, dossier):
    a = _arrive(base, ref_numero="19/2026", ref_date="2026-09-01")
    b = _arrive(base, code="Y000000008", prenom_ar="سارة")
    doc = mv.generer_demande(base, dossier, [a, b], "2026-09-10")
    t = m.texte_complet(doc.chemin.read_bytes())
    for x in ["طلب وثائق مدرسية.", "وثائق التلميذتين", "هبة الوافد", "سارة الوافد", "Y000000009", "1/26-27",
              "إلى السيد مدير مدرسة المؤسسة الأصلية", "المرجع: شهادة المغادرة رقم: 19/2026 بتاريخ: 01/09/2026"]:
        assert x in t, x
    assert t.count("الخامس") == 2 and "supprimer" not in t and "{{" not in t
    assert mv.alertes(base)["demande"] == []
    assert mv.etat(mv.lire(base, a)) == "أُرسل الطلب"
    # التذكير بعد 30 يوماً
    assert [r["id"] for r in mv.alertes(base, date(2026, 10, 15))["relance"]] == [a, b] or \
        sorted(r["id"] for r in mv.alertes(base, date(2026, 10, 15))["relance"]) == sorted([a, b])
    t2 = m.texte_complet(mv.generer_demande(base, dossier, [a], "2026-10-15", rappel=True).chemin.read_bytes())
    assert "طلب وثائق مدرسية (تذكير)." in t2 and "وتذكيرا بالطلب السابق المرسل إليكم بتاريخ 10 شتنبر 2026" in t2
    assert "1/26-27" in t2 and "2/26-27" in t2 and "الطلب الثاني" in t2
    mv.marquer(base, a, "dossier_recu_le", "2026-10-20")
    assert "توصلنا بالملف" in mv.etat(mv.lire(base, a))
    assert [r["numero"] for r in cg.sortants(base)] == [2, 1]


def test_demande_refus(base, dossier):
    a = _arrive(base)
    b = _arrive(base, code="Y000000008", etablissement="مؤسسة ثالثة")
    with pytest.raises(mv.ErreurMouvement, match="مؤسسة واحدة"):
        mv.generer_demande(base, dossier, [a, b])
    with pytest.raises(mv.ErreurMouvement, match="بعد الطلب الأول"):
        mv.generer_demande(base, dossier, [a], rappel=True)
    p = _parti(base)
    with pytest.raises(mv.ErreurMouvement, match="وافد"):
        mv.generer_demande(base, dossier, [a, p])
    with pytest.raises(mv.ErreurMouvement, match="على الأقل"):
        mv.generer_demande(base, dossier, [])
    assert cg.sortants(base) == []


def test_envoi_hors_province(base, dossier):
    p = _parti(base, hors_province=True, direction="عمالة: فاس", academie="فاس مكناس",
               ref_numero="2238/26", ref_date="2026-10-01")
    doc = mv.generer_envoi(base, dossier, [p], "2026-10-20")
    t = m.texte_complet(doc.chemin.read_bytes())
    for x in ["المديرية الإقليمية لعمالة فاس", "الأكاديمية الجهوية للتربية والتكوين لجهة فاس مكناس",
              "الأكاديمية الجهوية للتربية والتكوين لجهة الجهة", "مدرسة تجريبية -المدينة-",
              "المرجع: مراسلتكم رقم: 2238/26 بتاريخ: 01/10/2026", "بناء على مراسلتكم المشار إليها في المرجع أعلاه",
              "وثائق التلميذ:", "يوسف المثال"]:
        assert x in t, x
    assert mv.lire(base, p)["dossier_envoye_le"] == "2026-10-20" and mv.alertes(base)["envoi"] == []


def test_envoi_sans_reference_dans_la_province(base, dossier):
    p = _parti(base)
    t = m.texte_complet(mv.generer_envoi(base, dossier, [p], "2026-10-20").chemin.read_bytes())
    assert "وبعد، يشرفني أن أوافيكم بوثائق التلميذ:" in t and "المرجع" not in t


def test_niveau_requis_et_repris_de_la_fiche(base, dossier):
    p = _parti(base, niveau="")
    assert mv.lire(base, p)["niveau"]  # المستوى المقترح من بطاقة التلميذ
    a = _arrive(base, niveau="")  # وافد جديد بلا قسم
    with pytest.raises(mv.ErreurMouvement, match="المستوى"):
        mv.generer_demande(base, dossier, [a])
