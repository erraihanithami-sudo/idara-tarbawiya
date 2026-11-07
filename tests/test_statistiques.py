"""إحصائيات المؤسسة (بيانات وهمية)."""

from idara.services import eleves as el
from idara.services import statistiques as st
from tests.test_eleves import base  # noqa: F401


def test_analyse_et_niveaux(base):  # noqa: F811
    a = st.analyse_eleves(base)
    assert a["total"] > 0 and a["total"] == a["garcons"] + a["filles"] and a["apres_mouvement"] == a["total"]
    eid = base.execute("SELECT eleve_id FROM inscription LIMIT 1").fetchone()[0]
    el.changer_statut(base, eid, "interrompu", "2026-11-01", motif="انقطاع")
    a2 = st.analyse_eleves(base)
    d = {lib: (n, p) for lib, n, p in a2["details"]}
    assert d["المنقطعون"][0] == 1 and a2["apres_mouvement"] == a["total"] - 1 and a2["total"] == a["total"]
    niv = st.par_niveau(base)
    assert niv and sum(n["eleves"] for n in niv) == a2["apres_mouvement"]
    for n in niv:
        assert n["garcons"] + n["filles"] == n["eleves"] and n["classes"] >= 1
        assert "age" not in n   # لا تقدير للتكرار من السن (قرار المدير 2026-11-07)
    assert st.par_niveau(base, unite="وحدة غير موجودة") == []


def test_evolution_tarl(base):  # noqa: F811
    aid = base.execute("SELECT id FROM annee_scolaire WHERE est_courante=1").fetchone()[0]
    base.execute("INSERT INTO niveau_attendu(annee_id, niveau, matiere, valeur) VALUES (?, '4AP', 'ar', 'فقرة')", (aid,))
    for i, (pre, post) in enumerate((("حرف", "فقرة"), ("كلمة", "أقصوصة"), ("فقرة", "فقرة"), ("مبتدئ", "كلمة"))):
        for ep, v in (("pre", pre), ("post", post)):
            base.execute("INSERT INTO niveau_apprentissage(annee_id, code_massar, nom, classe, niveau, matiere, epreuve,"
                         " valeur) VALUES (?,?,?,?,?,?,?,?)", (aid, f"Z{i}", "س", "4APG-5APG-6APG", "4AP", "ar", ep, v))
    r = st.evolution_tarl(base)
    assert r == [{"niveau": "4AP", "libelle": "الرابع", "pre": 25.0, "post": 75.0, "evolution": 50.0,
                  "effectif_pre": 4, "effectif_post": 4}]
    assert st.evolution_tarl(base, "fr") == []


def test_unites_masquees_si_independante(base):  # noqa: F811
    """مؤسسة مستقلة: لا وحدات في الواجهة (قرار المدير 2026-11-07)."""
    from idara.services import etablissement as et
    et.definir_unites(base, ["الوحدة المركزية", "وحدة 2"])
    e = et.lire_etablissement(base)
    e.type_etab = "groupe"
    et.enregistrer_etablissement(base, e)
    assert et.est_groupe(base) and et.unites(base) == ["الوحدة المركزية", "وحدة 2"]
    e.type_etab = "independant"
    et.enregistrer_etablissement(base, e)
    assert not et.est_groupe(base) and et.unites(base) == [] and len(et.unites(base, toutes=True)) == 2
