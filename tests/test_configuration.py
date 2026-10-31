"""خدمات الإعداد: المؤسسة، المدير، السنة الدراسية، مكان البيانات. بيانات وهمية."""

from datetime import date

import pytest

from idara.services import annee as an
from idara.services import config as cf
from idara.services import etablissement as et


def _etab(**k):
    base = dict(nom_ar="مدرسة تجريبية", direction_ar="المديرية التجريبية",
                academie_ar="الأكاديمية التجريبية")
    base.update(k)
    return et.Etablissement(**base)


def _dir(**k):
    base = dict(nom_ar="التجريبي", prenom_ar="أحمد", sexe="M", ppr="1234567")
    base.update(k)
    return et.Directeur(**base)


# ---------- السنة الدراسية ----------

@pytest.mark.parametrize("jour, attendu", [
    (date(2026, 10, 31), "2026/2027"),
    (date(2026, 9, 1), "2026/2027"),
    (date(2026, 8, 31), "2025/2026"),
    (date(2027, 3, 15), "2026/2027"),
])
def test_libelle_annee(jour, attendu):
    assert an.libelle_pour_date(jour) == attendu


def test_code_court():
    assert an.code_court("2025/2026") == "25-26"
    with pytest.raises(an.ErreurAnnee):
        an.code_court("2025/2027")
    with pytest.raises(an.ErreurAnnee):
        an.code_court("2025-2026")


def test_une_seule_annee_courante(conn):
    a1 = an.activer_annee(conn, "2025/2026")
    a2 = an.activer_annee(conn, "2026/2027")
    assert an.annee_courante(conn)["id"] == a2
    assert an.activer_annee(conn, "2025/2026") == a1
    assert an.annee_courante(conn)["libelle"] == "2025/2026"
    assert conn.execute("SELECT COUNT(*) FROM annee_scolaire").fetchone()[0] == 2


# ---------- المؤسسة ----------

def test_enregistrer_et_relire_etablissement(conn):
    et.enregistrer_etablissement(conn, _etab(nom_fr="ECOLE TEST", commune_ar="  جماعة   تجريبية "))
    lu = et.lire_etablissement(conn)
    assert lu.nom_ar == "مدرسة تجريبية" and lu.nom_fr == "ECOLE TEST"
    assert lu.commune_ar == "جماعة تجريبية"
    et.enregistrer_etablissement(conn, _etab(nom_ar="اسم معدل"))
    assert et.lire_etablissement(conn).nom_ar == "اسم معدل"
    assert conn.execute("SELECT COUNT(*) FROM etablissement").fetchone()[0] == 1


@pytest.mark.parametrize("champ", ["nom_ar", "direction_ar", "academie_ar"])
def test_champs_obligatoires(conn, champ):
    with pytest.raises(et.ErreurValidation):
        et.enregistrer_etablissement(conn, _etab(**{champ: "   "}))


def test_type_inconnu_refuse(conn):
    with pytest.raises(et.ErreurValidation):
        et.enregistrer_etablissement(conn, _etab(type_etab="autre"))


def test_unites_sans_doublons(conn):
    assert et.definir_unites(conn, ["وحدة أ", "وحدة  أ", "", "وحدة ب"]) == ["وحدة أ", "وحدة ب"]
    assert et.definir_unites(conn, ["وحدة ب", "وحدة ج"]) == ["وحدة أ", "وحدة ب", "وحدة ج"]


def test_import_image(tmp_path, dossier):
    src = tmp_path / "شعار المدرسة.PNG"
    src.write_bytes(b"\x89PNG fake")
    rel = et.importer_image(dossier, src, "logo")
    assert rel == "modeles/identite/logo.png"
    assert (dossier.racine / rel).read_bytes() == b"\x89PNG fake"
    with pytest.raises(et.ErreurValidation):
        et.importer_image(dossier, tmp_path / "x.pdf", "logo")


# ---------- المدير ----------

def test_directeur_creation_et_modification(conn):
    pid = et.enregistrer_directeur(conn, _dir(date_affectation="2026-09-01"))
    d = et.directeur_actuel(conn)
    assert d["id"] == pid and d["categorie"] == "directeur" and d["mandat_debut"] == "2026-09-01"
    et.enregistrer_directeur(conn, _dir(prenom_ar="محمد"))
    assert et.directeur_actuel(conn)["prenom_ar"] == "محمد"
    assert conn.execute("SELECT COUNT(*) FROM mandat_directeur").fetchone()[0] == 1


def test_nouveau_directeur_garde_l_ancien(conn):
    ancien = et.enregistrer_directeur(conn, _dir())
    nouveau = et.enregistrer_directeur(conn, _dir(nom_ar="الجديد", ppr="7654321"), nouveau=True)
    assert et.directeur_actuel(conn)["id"] == nouveau
    fin = conn.execute("SELECT date_fin FROM mandat_directeur WHERE personnel_id=?",
                       (ancien,)).fetchone()[0]
    assert fin is not None


@pytest.mark.parametrize("champs", [
    dict(nom_ar=""), dict(prenom_ar=" "), dict(sexe="X"), dict(ppr="12A4"),
    dict(date_affectation="31/09/2026")])
def test_directeur_invalide(conn, champs):
    with pytest.raises(et.ErreurValidation):
        et.enregistrer_directeur(conn, _dir(**champs))


# ---------- الإعداد الأول كاملاً ----------

def test_configuration_initiale_complete(tmp_path, dossier, conn):
    assert not et.configuration_complete(conn)
    logo = tmp_path / "logo.jpg"
    logo.write_bytes(b"jpg")
    cfg = et.ConfigurationInitiale(
        etablissement=_etab(type_etab="groupe"), directeur=_dir(),
        annee="2026/2027", unites=["الوحدة المركزية", "وحدة فرعية"], logo_source=str(logo))
    et.appliquer_configuration_initiale(conn, dossier, cfg)
    assert et.configuration_complete(conn)
    assert et.lire_etablissement(conn).logo_path == "modeles/identite/logo.jpg"
    assert et.unites(conn) == ["الوحدة المركزية", "وحدة فرعية"]
    assert an.annee_courante(conn)["code_court"] == "26-27"
    actions = {r[0] for r in conn.execute("SELECT action FROM journal")}
    assert {"enregistrement", "nouveau_directeur", "annee_courante"} <= actions


def test_configuration_invalide_n_ecrit_rien(dossier, conn):
    cfg = et.ConfigurationInitiale(etablissement=_etab(), directeur=_dir(nom_ar=""))
    with pytest.raises(et.ErreurValidation):
        et.appliquer_configuration_initiale(conn, dossier, cfg)
    assert et.lire_etablissement(conn) is None


# ---------- مكان البيانات ----------

def test_config_du_poste(tmp_path, monkeypatch):
    monkeypatch.setenv("IDARA_CONFIG_DIR", str(tmp_path / "cfg"))
    assert cf.dossier_donnees_enregistre() is None
    cf.ecrire_config(dossier_donnees=str(tmp_path / "الإدارة التربوية"))
    assert cf.dossier_donnees_enregistre() == tmp_path / "الإدارة التربوية"
    cf.fichier_config().write_text("{cassé", encoding="utf-8")
    assert cf.lire_config() == {}


# ---------- التواريخ بالعربية ----------

def test_dates_en_arabe():
    from idara.services.textes import date_ar, date_longue_ar
    assert date_ar(date(2025, 12, 23)) == "23 دجنبر 2025"
    assert date_ar(date(2026, 7, 13)) == "13 يوليوز 2026"
    assert date_longue_ar(date(2026, 10, 31)) == "السبت 31 أكتوبر 2026"
