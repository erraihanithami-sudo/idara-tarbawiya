"""التدبير التربوي: أداء المؤسسة بالأسدوس، التعلمات الأساس (TaRL)، الأندية والأنشطة. بيانات وهمية."""

import pytest

from idara.services import evaluation as ev
from idara.services import tarl
from idara.services import vie_scolaire as vs
from tests.fabrique_resultats import classeur_resultats
from tests.fabrique_tarl import classeur_niveaux
from tests.test_docs_association import texte
from tests.test_eleves import _id, base  # noqa: F401  (fixture)


# ---------- أداء المؤسسة ----------

def test_comparaison_semestres(conn, tmp_path):
    n = [6] * 8
    f1 = classeur_resultats(tmp_path / "a.xlsx", {"4APG-1": [("X000000001", "أ", n), ("X000000002", "ب", n)],
                                                   "4APG-2": [("X000000003", "ج", n)]}, annee="2025/2026",
                            semestres={"X000000001": (4.5, 6), "X000000002": (7, 8), "X000000003": (5, 4)})
    ev.importer(conn, [f1])
    f2 = classeur_resultats(tmp_path / "b.xlsx", {"4APG-1": [("X000000004", "د", n), ("X000000005", "ه", n)]},
                            annee="2026/2027", semestres={"X000000004": (8, None), "X000000005": (3, None)})
    r = ev.importer(conn, [f2])
    assert r.sans_moyenne == ["د (4APG-1)", "ه (4APG-1)"]  # ملف منتصف السنة: لا معدل سنوي محسوب
    assert ev.periodes(conn) == [("2025/2026", 1), ("2025/2026", 2), ("2026/2027", 1)]
    l = {x["cle"]: x for x in ev.comparaison(conn, ("2025/2026", 2))}
    assert (l["4AP"]["moyenne"], l["4AP"]["taux"], l["4AP"]["moyenne_avant"], l["4AP"]["taux_avant"]) == \
        (6.0, 66.67, 5.5, 66.67)
    assert l["4AP"]["ecart_moyenne"] == 0.5 and l["4AP"]["avant"] == "الأسدوس الأول 2025/2026"
    der = {x["cle"]: x for x in ev.comparaison(conn)}  # آخر أسدوس مقارنة بالأسدوس الثاني من السنة الفارطة
    assert der["المؤسسة"]["periode"] == "الأسدوس الأول 2026/2027"
    assert (der["المؤسسة"]["moyenne"], der["المؤسسة"]["taux"], der["المؤسسة"]["ecart_taux"]) == (5.5, 50.0, -16.67)
    c = {x["cle"]: x for x in ev.comparaison(conn, ("2025/2026", 2), par="classe")}
    assert c["4APG-2"]["moyenne"] == 4.0 and c["4APG-2"]["ecart_moyenne"] == -1.0


# ---------- التعلمات الأساس ----------

def _tarl(tmp_path):
    return classeur_niveaux(tmp_path / "t.xlsx", {
        "2APG-1": [("X000000001", "أ", "حرف", "كلمة", "débutant", "Mot simple", "رقمان", "جمع"),
                   ("X000000002", "ب", "مبتدئ ", "حرف", "lettre", "lettre", "مبتدئ ", "رقم واحد"),
                   ("X000000003", "ج", "كلمة", "فقرة", "Mot  simple", "Mot avancé", "جمع", "جمع")],
        "2APG-2": [("X000000004", "د", "كلمة", "حرف", "lettre", "inconnu", "رقمان", None)]})


def test_import_niveaux_apprentissage(conn, tmp_path):
    r = tarl.importer(conn, [_tarl(tmp_path)])
    assert (r.annee, r.eleves, r.classes) == ("2026/2027", 4, ["2APG-1", "2APG-2"])
    assert r.alertes == ["2APG-2: مستوى غير معروف «inconnu» (اللغة الفرنسية) لـ X000000004."]
    assert tarl.attendu(conn, "2026/2027", "2AP", "ar") == "كلمة"
    tb = tarl.tableau_bord(conn, "2026/2027", "*", "ar")
    assert tb["distribution"]["post"] == {"مبتدئ": 0, "حرف": 2, "كلمة": 1, "فقرة": 1, "أقصوصة": 0}
    assert tb["taux_attendu"] == {"pre": 50.0, "post": 50.0}
    assert tb["evolution"] == {"progres": 3, "stable": 0, "recul": 1}
    fr = tarl.tableau_bord(conn, "2026/2027", "c:2APG-1", "fr")
    assert fr["effectifs"] == {"pre": 3, "post": 3} and fr["taux_attendu"]["post"] == pytest.approx(66.67)
    assert [x["code_massar"] for x in tarl.eleves_en_difficulte(conn, "2026/2027", "n:2AP", "ma")] == ["X000000002"]
    assert [g[1] for g in tarl.groupes(conn, "2026/2027")] == ["المؤسسة", "المستوى الثاني", "القسم 2APG1", "القسم 2APG2"]
    tarl.importer(conn, [_tarl(tmp_path)])  # إعادة الاستيراد تحدّث ولا تكرر
    assert conn.execute("SELECT COUNT(*) FROM niveau_apprentissage").fetchone()[0] == 22


def test_fichier_sans_niveaux(conn, tmp_path):
    f = classeur_resultats(tmp_path / "r.xlsx", {"4APG-1": [("X000000001", "أ", [5] * 8)]})
    with pytest.raises(tarl.ErreurTarl, match="مستويات التعلم"):
        tarl.importer(conn, [f])


# ---------- الأندية والأنشطة ----------

def test_clubs_et_activites(base, dossier):  # noqa: F811
    from idara.services import personnel as rh
    pid = rh.lister(base)[0].id
    c = vs.enregistrer_club(base, "النادي البيئي", pid, "التربية على البيئة", "الأربعاء 15:00-16:00")
    with pytest.raises(vs.ErreurVie, match="بنفس الاسم"):
        vs.enregistrer_club(base, "النادي البيئي")
    vs.ajouter_membre(base, c, _id(base, "X000000001"), "رئيس النادي")
    vs.ajouter_membre(base, c, _id(base, "X000000002"))
    assert vs.clubs(base)[0]["membres"] == 2
    a1 = vs.enregistrer_activite(base, vs.Activite("نشاط نادٍ تربوي", "حملة نظافة", c, "منشط النادي", "أعضاء النادي",
                                                   "شهر أكتوبر"))
    with pytest.raises(vs.ErreurVie, match="عدد المشاركين"):
        vs.enregistrer_activite(base, vs.Activite("يوم وطني أو دولي", "ذكرى المسيرة الخضراء",
                                                  date_debut="2026-11-06", statut="realisee"))
    vs.enregistrer_activite(base, vs.Activite("يوم وطني أو دولي", "ذكرى المسيرة الخضراء", None, "جميع الأطر",
                                              "جميع التلاميذ", date_debut="2026-11-06", statut="realisee",
                                              nb_garcons=40, nb_filles="45", bilan="أناشيد وعروض"))
    vs.enregistrer_activite(base, vs.Activite("مسابقة", "مسابقة ملغاة", periode="دجنبر", statut="annulee"))
    with pytest.raises(vs.ErreurVie, match="فترة الإنجاز"):
        vs.enregistrer_activite(base, vs.Activite("مسابقة", "بدون فترة"))
    b = vs.bilan(base)
    assert (b["programmees"], b["realisees"], b["taux"], b["garcons"], b["filles"]) == (2, 1, 50.0, 40, 45)
    assert vs.activite(base, a1).club_id == c
    t = texte(vs.generer_programme(base, dossier))
    assert "البرنامج السنوي للعمل التربوي" in t and "نشاط نادٍ تربوي: النادي البيئي" in t and "مسابقة ملغاة" not in t
    t = texte(vs.generer_bilan(base, dossier))
    assert "حصيلة الأنشطة" in t and "نسبة الإنجاز 50.00%" in t and "أناشيد وعروض" in t
    t = texte(vs.generer_liste_club(base, dossier, c))
    assert "رئيس النادي" in t and "الأربعاء 15:00-16:00" in t


# ---------- الريادة ----------

def test_parcours_de_soutien(conn, tmp_path):
    from tests.fabrique_tarl import classeur_groupes
    r = tarl.importer(conn, [classeur_groupes(tmp_path / "g.xlsx", {"4APG-1": ("المسار 2", "parcours 2", "parcours 1")})])
    assert r.parcours == 3 and r.classes == ["4APG-1"]
    assert tarl.parcours(conn, "2026/2027") == {"4APG-1": {"ar": "المسار 2", "fr": "parcours 2", "ma": "parcours 1"}}
    assert tarl.annees(conn) == ["2026/2027"]


def _enseignant(conn, classe_code, matiere="فرنسية", sexe="M"):
    pid = conn.execute("INSERT INTO personnel(nom_ar, prenom_ar, sexe, categorie, statut, matiere) "
                       "VALUES ('الوهمي', 'الأستاذ', ?, 'enseignant', 'actif', ?)", (sexe, matiere)).lastrowid
    cid = conn.execute("SELECT c.id FROM classe c JOIN annee_scolaire a ON a.id=c.annee_id WHERE c.code=?",
                       (classe_code,)).fetchone()[0]
    conn.execute("INSERT INTO affectation_classe(personnel_id, classe_id) VALUES (?,?)", (pid, cid))
    conn.commit()
    return pid


def test_isa_phases_et_lettres(base, dossier):  # noqa: F811
    from idara.services import riyada as ry
    cl = base.execute("SELECT code FROM classe ORDER BY code").fetchone()[0]
    with pytest.raises(ry.ErreurRiyada, match="خارج المجال"):
        ry.enregistrer_isa(base, "2026/2027", cl, 1, {"fr": "120"})
    ry.enregistrer_isa(base, "2026/2027", cl, 0, {"fr": "60,5", "ma": "70%"})
    ry.enregistrer_isa(base, "2026/2027", cl, 1, {"fr": "75.94", "ma": "65"})
    ry.enregistrer_isa(base, "2026/2027", cl, 3, {"fr": "65.51", "ar": "50"})
    assert ry.isa(base, "2026/2027")[cl]["fr"] == {0: 60.5, 1: 75.94, 3: 65.51}
    assert ry.evolution({0: 60.5, 1: 75.94, 3: 65.51}) == [(0, 60.5, None), (1, 75.94, 15.44), (3, 65.51, -10.43)]
    with pytest.raises(ry.ErreurRiyada, match="لا نسب ISA2"):
        ry.generer_lettres(base, dossier, "2026/2027", 3)
    _enseignant(base, cl)
    t = texte(ry.generer_lettres(base, dossier, "2026/2027", 3, maths="fr"))
    assert "بخصوص نتائج المرحلة الثالثة" in t and "أتشرف بتهنئتكم" in t and "مؤشر ISA2" in t
    assert "الفرنسية" in t and "65.51%" in t and "-10.43" in t and "الرياضيات" not in t  # لا نسبة رياضيات في المرحلة 3
    t = texte(ry.generer_lettres(base, dossier, "2026/2027", 1, felicitations=False))
    assert "أتشرف بتهنئتكم" not in t and "الرياضيات" in t and "+15.44" in t


def test_dossier_riyada_et_synthese(base, dossier, tmp_path):  # noqa: F811
    from idara.services import riyada as ry
    assert len(ry.pieces(base, "2026/2027")) == 20
    ry.enregistrer_piece(base, "2026/2027", 2, True, "مصادق عليه في 10/10")
    ry.enregistrer_infos(base, {"riyada_date_construction": "1985", "riyada_formes_tarl": "6"})
    inf = dict((l, v) for l, v, _ in ry.infos(base))
    assert inf["تاريخ بناء المؤسسة"] == "1985" and int(inf["عدد تلاميذ المؤسسة ذكور"]) + int(
        inf["عدد تلاميذ المؤسسة إناث"]) == 5
    t = texte(ry.generer_dossier(base, dossier, "2026/2027"))
    assert "ملف شارة الريادة" in t and "حقيبة المعلومات" in t and "المتوفر منها: 1" in t and "مصادق عليه في 10/10" in t
    with pytest.raises(ry.ErreurRiyada, match="لا معطيات"):
        ry.generer_synthese(base, dossier, "2026/2027")
    tarl.importer(base, [_tarl(tmp_path)])
    p = ry.pieces(base, "2026/2027")
    assert p[12]["indice"] and p[13]["indice"] and p[9]["indice"]
    t = texte(ry.generer_liste_difficultes(base, dossier, "2026/2027"))
    assert "يعانون من صعوبات" in t and "X000000002" in t
    t = texte(ry.generer_synthese(base, dossier, "2026/2027", "تعزيز الدعم"))
    assert "التعلمات الأساس" in t and "50.00%" in t and "تعزيز الدعم" in t
