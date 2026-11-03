"""البحث والبطاقة والتعديل والوضعيات وتوليد وثائق التلاميذ، والتلاميذ القدامى. بيانات وهمية."""

from datetime import date

import pytest

from idara.services import anciens as an
from idara.services import eleves as el
from idara.services import etablissement as et
from idara.services import import_eleves as imp
from idara.services import moteur_docx as m
from tests.fabrique_massar import classeur
from tests.test_import_massar import AR, FR


@pytest.fixture
def base(tmp_path, dossier, conn):
    et.appliquer_configuration_initiale(conn, dossier, et.ConfigurationInitiale(
        etablissement=et.Etablissement(nom_ar="مدرسة تجريبية", direction_ar="م", academie_ar="أ",
                                       nom_fr="ECOLE TEST", ville_redaction_ar="المدينة", ville_redaction_fr="Ville"),
        directeur=et.Directeur(nom_ar="المدير", prenom_ar="أحمد", sexe="M", nom_fr="MOUDIR",
                               prenom_fr="AHMED"), annee="2026/2027"))
    r = imp.analyser(conn, [classeur(tmp_path / "a.xlsx", AR), classeur(tmp_path / "f.xlsx", FR, "fr")])
    imp.appliquer(conn, dossier, r)
    return conn


def _id(conn, code):
    return conn.execute("SELECT id FROM eleve WHERE code_massar=?", (code,)).fetchone()[0]


def _confirmer(conn, code, niveau):
    ins = conn.execute("SELECT i.id FROM inscription i JOIN eleve e ON e.id=i.eleve_id "
                       "WHERE e.code_massar=?", (code,)).fetchone()[0]
    imp.confirmer_niveaux(conn, {ins: niveau})


# ---------- البحث ----------

@pytest.mark.parametrize("texte, codes", [
    ("X000000003", ["X000000003"]), ("x0000000", None), ("يوسف", ["X000000003"]),
    ("المثال يوسف", ["X000000003"]), ("يوسف المثال", ["X000000003"]), ("youssef", ["X000000003"]),
    ("ادم", ["X000000005"]),  # «آدم» بدون همزة
    ("لا أحد", []),
])
def test_recherche(base, texte, codes):
    res = [r["code_massar"] for r in el.rechercher(base, texte)]
    if codes is None:
        assert len(res) == 5
    else:
        assert res == codes


def test_recherche_vide_liste_les_inscrits(base):
    res = el.rechercher(base, "")
    assert len(res) == 5 and all(r["classe"] for r in res)


# ---------- التعديل ----------

def test_modification_verrouille_et_import_respecte(tmp_path, base, dossier):
    eid = _id(base, "X000000004")
    changes = el.modifier(base, eid, {"prenom_fr": "Meriem", "lieu_ar": "القرية", "lieu_fr": "village"})
    assert set(changes) == {"prenom_fr", "lieu"}
    r = el.fiche(base, eid)
    assert r["prenom_fr"] == "MERIEM" and r["lieu_fr"] == "VILLAGE"
    assert el.champs_verrouilles(base, eid) == {"prenom_fr", "lieu"}
    rap = imp.analyser(base, [classeur(tmp_path / "f2.xlsx", FR, "fr")])
    imp.appliquer(base, dossier, rap)
    assert el.fiche(base, eid)["prenom_fr"] == "MERIEM"
    # تصحيح الاسم الفرنسي لمكان يصحح كل المزدادين فيه
    el.modifier(base, _id(base, "X000000002"), {"lieu_fr": "VILLAGE"})
    assert base.execute("SELECT nom_fr FROM lieu WHERE nom_ar='القرية'").fetchone()[0] == "VILLAGE"


@pytest.mark.parametrize("valeurs", [{"nom_ar": " "}, {"sexe": "X"}, {"date_naissance": "2099-01-01"},
                                     {"date_naissance": "31/12/2015"}])
def test_modification_refusee(base, valeurs):
    with pytest.raises(el.ErreurEleve):
        el.modifier(base, _id(base, "X000000001"), valeurs)


def test_sans_changement(base):
    assert el.modifier(base, _id(base, "X000000001"), {"nom_ar": "التجريبي"}) == []
    assert el.champs_verrouilles(base, _id(base, "X000000001")) == set()


# ---------- الوضعيات ----------

def test_statuts(base):
    eid = _id(base, "X000000001")
    with pytest.raises(el.ErreurEleve, match="تاريخ"):
        el.changer_statut(base, eid, "parti")
    with pytest.raises(el.ErreurEleve, match="المؤسسة المستقبلة"):
        el.changer_statut(base, eid, "parti", "2026-12-01")
    el.changer_statut(base, eid, "parti", "2026-12-01", "مدرسة أخرى", "انتقال الأسرة")
    r = el.fiche(base, eid)
    assert r["statut"] == "parti"
    assert len(el.rechercher(base, "")) == 5  # يبقى في التاريخ
    el.changer_statut(base, eid, "inscrit")
    assert el.fiche(base, eid)["statut"] == "inscrit"
    el.changer_statut(base, eid, "arrive", "2026-10-01", "مدرسة الأصل")
    p = el.parcours(base, eid)[0]
    assert p["statut"] == "arrive" and p["etab_origine"] == "مدرسة الأصل"


# ---------- توليد الوثائق ----------

def test_vacances_exige_niveau_confirme(base, dossier):
    eid = _id(base, "X000000003")
    with pytest.raises(el.ErreurEleve, match="أكّده"):
        el.generer_attestation_vacances(base, dossier, eid, date(2026, 12, 20), date(2027, 1, 4))
    _confirmer(base, "X000000003", "4AP")
    doc = el.generer_attestation_vacances(base, dossier, eid, date(2026, 12, 20), date(2027, 1, 4))
    texte = m.texte_complet(doc.chemin.read_bytes())
    assert "20/12/2026 Au 04/01/2027" in texte and "MITHAL YOUSSEF" in texte and "4ème année" in texte
    assert [d["titre"] for d in el.documents(base, eid)] == ["شهادة العطلة"]


def test_vacances_sans_lieu_francais(base, dossier):
    _confirmer(base, "X000000004", "5AP")
    with pytest.raises(Exception, match="مكان الازدياد"):
        el.generer_attestation_vacances(base, dossier, _id(base, "X000000004"),
                                        date(2026, 12, 20), date(2027, 1, 4))


def test_visite_et_convocations(base, dossier):
    _confirmer(base, "X000000001", "PS1")
    doc = el.generer_visite_medicale(base, dossier, _id(base, "X000000001"))
    assert "القسم الأولى أولي" in m.texte_complet(doc.chemin.read_bytes())
    ids = [_id(base, c) for c in ("X000000001", "X000000002", "X000000003")]
    docs = el.generer_convocations(base, dossier, ids)
    assert len(docs) == 3 and len({d.chemin for d in docs}) == 1
    texte = m.texte_complet(docs[0].chemin.read_bytes())
    assert "سعيد التجريبي" in texte and "سلمى الوهمي" in texte and "يوسف المثال" in texte
    for i in ids:
        assert any(d["titre"] == "استدعاء ولي الأمر" for d in el.documents(base, i))
    with pytest.raises(el.ErreurEleve):
        el.generer_convocations(base, dossier, [])


# ---------- التلاميذ القدامى ----------

def _ancien(**k):
    base = dict(num_registre="8173", nom_ar="القديم", prenom_ar="فيصل", sexe="M",
                date_naissance="1985-01-01", date_naissance_approx=True, lieu_ar="الخميسات",
                date_entree="1992-10-15", date_sortie="1998-06-30", dernier_niveau="الخامس")
    base.update(k)
    return an.Ancien(**base)


@pytest.mark.parametrize("champ", ["num_registre", "nom_ar", "prenom_ar", "sexe", "date_naissance",
                                   "lieu_ar", "date_entree", "date_sortie", "dernier_niveau"])
def test_ancien_tous_champs_obligatoires(base, champ):
    with pytest.raises(an.ErreurAncien, match="إجبارية"):
        an.enregistrer(base, _ancien(**{champ: ""}))


@pytest.mark.parametrize("modif, message", [
    (dict(num_registre="12a"), "أرقام"), (dict(date_entree="1999-01-01"), "منطقية"),
    (dict(date_sortie="2099-01-01"), "منطقية"), (dict(date_naissance="1999-02-30"), "غير صحيح")])
def test_ancien_valeurs_invalides(base, modif, message):
    with pytest.raises(an.ErreurAncien, match=message):
        an.enregistrer(base, _ancien(**modif))


def test_ancien_enregistrement_et_certificat(base, dossier):
    eid = an.enregistrer(base, _ancien())
    assert an.par_numero(base, "8173").id == eid
    assert [r["num_registre"] for r in el.rechercher(base, "فيصل", source="avant_massar")] == [8173]
    assert el.rechercher(base, "8173", source="avant_massar")[0]["id"] == eid
    assert el.rechercher(base, "فيصل") == []  # لا يختلط بتلاميذ مسار
    with pytest.raises(an.ErreurAncien, match="مسجل لتلميذ آخر"):
        an.enregistrer(base, _ancien(nom_ar="آخر"))
    a = an.lire(base, eid)
    a.dernier_niveau = "السادس"
    an.enregistrer(base, a)
    doc = an.generer_certificat(base, dossier, eid, "فيصل القديم", "fa000000", date(2026, 11, 1))
    texte = m.texte_complet(doc.chemin.read_bytes())
    for attendu in ["أن السيد: فيصل القديم", "المزداد بتاريخ: 01/01/1985 بالخميسات",
                    "تحت رقم التسجيل: 8173", "من تاريخ: 15/10/1992 إلى 30/06/1998",
                    "آخر قسم درس به: السادس", "وقد انقطع بتاريخ: 30 يونيو 1998",
                    "اسم متسلم الشهادة المدرسية: فيصل القديم", "FA000000", "1 نونبر 2026"]:
        assert attendu in texte, attendu
    assert "............" not in texte
    remises = an.remises(base, eid)
    assert len(remises) == 1 and remises[0]["destinataire_cin"] == "FA000000"


def test_ancien_certificat_sans_destinataire(base, dossier):
    eid = an.enregistrer(base, _ancien())
    with pytest.raises(Exception, match="متسلم"):
        an.generer_certificat(base, dossier, eid, "", "")


def test_statut_exclu(base):
    """طلب المدير: وضعية «مفصول» بتاريخ وسبب/مرجع القرار؛ يخرج من الحاضرين ولا يُحذف."""
    eid = _id(base, "X000000002")
    with pytest.raises(el.ErreurEleve, match="إجباري"):
        el.changer_statut(base, eid, "exclu", "2026-12-01")
    el.changer_statut(base, eid, "exclu", "2026-12-01", "", "قرار مجلس القسم رقم 3")
    r = el.fiche(base, eid)
    assert r["statut"] == "exclu" and el.STATUTS["exclu"] == "مفصول"
    assert el.STATUTS["inscrit"] == "يتابع دراسته"  # قرار المدير 2026-11-03
    assert base.execute("SELECT COUNT(*) FROM inscription WHERE statut IN ('inscrit','arrive')").fetchone()[0] == 4
    p = el.parcours(base, eid)[0]
    assert p["date_sortie"] == "2026-12-01"
    el.changer_statut(base, eid, "inscrit")
    assert el.fiche(base, eid)["statut"] == "inscrit"
