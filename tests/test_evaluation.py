"""التقييم: نتائج مسار وإحصاء الحاصلين على المعدل ومحاضر مجالس الأقسام. بيانات وهمية."""

import pytest

from idara.services import evaluation as ev
from idara.services import moteur_docx as m
from idara.services import personnel as rh
from tests.fabrique_resultats import classeur_resultats
from tests.test_eleves import base  # noqa: F401

N = lambda x: [x] * 8  # noqa: E731


def _fichier(tmp_path, nom="r.xlsx", **k):
    classes = {
        "4APG-1": [("X000000001", "التجريبي سعيد", N(8.0)), ("X000000002", "الوهمي سلمى", N(4.5)),
                   ("Y100000001", "مجهول أحمد", [5, 5, 5, 5, 5, 5, 4, 4])],
        "4APG-2": [("X000000003", "المثال يوسف", [7.82, 9.70, 7.80, 8.57, 7.82, 8.00, 7.75, 7.75])],
        "4APG-5APG-6APG": [("X000000004", "النموذج مريم", N(6.0))],
    }
    return classeur_resultats(tmp_path / nom, classes, **k)


def test_lecture(tmp_path):
    f = ev.lire_fichier(_fichier(tmp_path))
    assert f.annee == "2026/2027" and f.classes == ["4APG-1", "4APG-2", "4APG-5APG-6APG"] and len(f.lignes) == 5
    l = f.lignes[3]
    assert l.code == "X000000003" and l.moyennes["اللغة الفرنسية"] == 9.70 and l.moyenne_massar is None
    # نفس مثال بيان النتائج الحقيقي: 8,15
    assert ev.moyenne_annuelle(l, "4AP") == (8.15, "calcul")
    assert ev.moyenne_annuelle(l, "6AP") == (None, None)


def test_fichier_invalide(tmp_path):
    p = tmp_path / "x.xlsx"
    p.write_text("ليس Excel")
    with pytest.raises(ev.ErreurEvaluation, match="Excel"):
        ev.lire_fichier(p)
    import openpyxl
    wb = openpyxl.Workbook()
    wb.save(tmp_path / "vide.xlsx")
    with pytest.raises(ev.ErreurEvaluation, match="مجمل المعدلات"):
        ev.lire_fichier(tmp_path / "vide.xlsx")


def test_import_stats_et_reimport(tmp_path, base):  # noqa: F811
    r = ev.importer(base, [_fichier(tmp_path)])
    assert r.annee == "2026/2027" and r.eleves == 5
    assert r.inconnus == ["مجهول أحمد (Y100000001)"]
    assert r.sans_niveau == ["النموذج مريم (4APG-5APG-6APG)"]
    s = {x.libelle: x for x in ev.stats_par_classe(base, "2026/2027", "4AP")}
    s1 = s["4APG1"]
    assert (s1.g, s1.f, s1.t, s1.rg, s1.rf, s1.rt, s1.sans_sexe) == (1, 1, 3, 1, 0, 1, 1)
    assert s1.pourcentage == "33.33%" and s["4APG2"].pourcentage == "100%"
    # تحديد مستوى تلميذ القسم المشترك
    ev.definir_niveau(base, "2026/2027", "X000000004", "5AP")
    assert ev.niveaux(base, "2026/2027") == ["4AP", "5AP"]
    assert ev.a_verifier(base, "2026/2027")["niveau"] == []
    # إعادة الاستيراد لا تكرر
    ev.importer(base, [_fichier(tmp_path, "r2.xlsx")])
    assert base.execute("SELECT COUNT(*) FROM resultat").fetchone()[0] == 5


def test_pourcentage_tronque_comme_le_directeur():
    s = ev.Stats("x", t=19, rt=18)
    assert s.pourcentage == "94.73%"
    assert ev.Stats("x", t=342, rt=333).pourcentage == "97.36%"
    assert ev.Stats("x").pourcentage == "—"


def test_sixieme_sans_annuel_puis_avec(tmp_path, base):  # noqa: F811
    classes = {"6APG-1": [("X000000005", "الاختبار آدم", N(7.0))]}
    ev.importer(base, [classeur_resultats(tmp_path / "s.xlsx", classes, niveau="السادس ابتدائي عام")])
    assert ev.a_verifier(base, "2026/2027")["moyenne"] == ["الاختبار آدم (6APG-1)"]
    ev.importer(base, [classeur_resultats(tmp_path / "s2.xlsx", classes, niveau="السادس ابتدائي عام",
                                          annuels={"X000000005": 4.9})])
    st = ev.stats_par_classe(base, "2026/2027", "6AP")[0]
    assert (st.t, st.rt, st.et) == (1, 0, 1)


def test_annees_differentes_refusees(tmp_path, base):  # noqa: F811
    a = _fichier(tmp_path, "a.xlsx")
    b = _fichier(tmp_path, "b.xlsx", annee="2025/2026")
    with pytest.raises(ev.ErreurEvaluation, match="سنوات"):
        ev.importer(base, [a, b])


def test_proces_verbal_niveau_et_synthese(tmp_path, base, dossier):  # noqa: F811
    ev.importer(base, [_fichier(tmp_path)])
    ev.definir_niveau(base, "2026/2027", "X000000004", "5AP")
    c = base.execute("SELECT id FROM classe WHERE code='4APG-5APG-6APG'").fetchone()[0]
    rh.enregistrer(base, rh.Personnel(nom_ar="الأستاذة", prenom_ar="فاطمة", sexe="F", categorie="enseignant",
                                      classes=[c]))
    ev.enregistrer_isa(base, "2026/2027", "4APG-1", {"ar": "66.03", "fr": "57,14%", "ma": "", "gl": "62.22"})
    with pytest.raises(ev.ErreurEvaluation, match="0 و100"):
        ev.enregistrer_isa(base, "2026/2027", "4APG-1", {"ar": "150"})
    ev.enregistrer_conseil(base, "2026/2027", "4AP", "2027-07-04", "الخامسة", "ضعف القراءة", "دعم مكثف")
    t = m.texte_complet(ev.generer_conseil(base, dossier, "2026/2027", "4AP").chemin.read_bytes())
    for x in ["محضر مجلس القسم الرابع", "الأحد 4 يوليوز 2027", "4APG1", "4APG2", "33.33%", "66.03%", "57.14%",
              "ضعف القراءة", "دعم مكثف", "المرحلة الخامسة من الموسم الدراسي 2026/2027"]:
        assert x in t, x
    assert "supprimer" not in t and "{{" not in t
    t5 = m.texte_complet(ev.generer_conseil(base, dossier, "2026/2027", "5AP").chemin.read_bytes())
    assert "فاطمة الأستاذة" in t5 and "......" in t5  # الصعوبات فارغة: أسطر للكتابة باليد
    ts = m.texte_complet(ev.generer_synthese(base, dossier, "2026/2027", le="2027-07-04").chemin.read_bytes())
    for x in ["القسم الرابع", "القسم الخامس", "المجموع", "بمدرسة تجريبية", "للأسدوس الثاني", "2026/2027"]:
        assert x in ts, x
    assert "القسم الأول" not in ts
