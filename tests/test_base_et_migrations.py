"""إنشاء القاعدة وترحيلها."""

import sqlite3

import pytest

from idara.data import db as dbmod
from idara.data.db import ErreurMigration, connecter, migrer, ouvrir_base, version_actuelle
from idara.data.dossier import SOUS_DOSSIERS
from idara.data.journal import dernieres_operations, journaliser


def test_dossier_cree_avec_ses_sous_dossiers(dossier):
    for nom in SOUS_DOSSIERS:
        assert (dossier.racine / nom).is_dir()


def test_base_neuve_au_dernier_niveau(conn):
    assert version_actuelle(conn) == len(dbmod.lister_migrations())
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for t in ("etablissement", "eleve", "inscription", "personnel", "conge",
              "reprise_travail", "courrier", "document_genere", "journal"):
        assert t in tables


def test_donnees_de_reference(conn):
    assert conn.execute("SELECT COUNT(*) FROM niveau").fetchone()[0] == 8
    assert conn.execute("SELECT COUNT(*) FROM cas_reprise").fetchone()[0] == 10
    assert conn.execute("SELECT COUNT(*) FROM type_conge").fetchone()[0] == 5


def test_cles_etrangeres_actives(conn):
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_reouverture_sans_reappliquer(dossier, conn):
    conn.close()
    c2 = ouvrir_base(dossier.base)
    assert migrer(c2) == []
    assert c2.execute("SELECT COUNT(*) FROM niveau").fetchone()[0] == 8
    c2.close()


def test_migration_suivante_sans_perte(tmp_path, dossier, conn):
    conn.execute("INSERT INTO etablissement(id, nom_ar) VALUES (1, 'مؤسسة تجريبية')")
    conn.commit()
    conn.close()
    dossier_m = tmp_path / "migrations"
    dossier_m.mkdir()
    for _, nom, f in dbmod.lister_migrations():
        (dossier_m / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
    (dossier_m / "0003_test_ajout.sql").write_text(
        "ALTER TABLE etablissement ADD COLUMN email TEXT;", encoding="utf-8")
    c = connecter(dossier.base)
    assert migrer(c, dossier_m) == ["0003_test_ajout"]
    assert c.execute("SELECT nom_ar FROM etablissement").fetchone()[0] == "مؤسسة تجريبية"
    assert version_actuelle(c) == 3
    c.close()


def test_migration_defaillante_annulee_entierement(tmp_path, dossier, conn):
    conn.close()
    dossier_m = tmp_path / "migrations"
    dossier_m.mkdir()
    for _, nom, f in dbmod.lister_migrations():
        (dossier_m / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
    (dossier_m / "0003_casse.sql").write_text(
        "CREATE TABLE nouvelle(x INTEGER);\nINSERT INTO table_inexistante VALUES (1);",
        encoding="utf-8")
    c = connecter(dossier.base)
    with pytest.raises(ErreurMigration):
        migrer(c, dossier_m)
    tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "nouvelle" not in tables
    assert version_actuelle(c) == 2
    c.close()


def test_numerotation_non_continue_refusee(tmp_path):
    d = tmp_path / "m"
    d.mkdir()
    (d / "0001_a.sql").write_text("SELECT 1;", encoding="utf-8")
    (d / "0003_c.sql").write_text("SELECT 1;", encoding="utf-8")
    with pytest.raises(ErreurMigration):
        dbmod.lister_migrations(d)


def test_journal(conn):
    journaliser(conn, "ajout", "eleve", 7, {"nom": "تجريبي"})
    op = dernieres_operations(conn, 1)[0]
    assert op["action"] == "ajout" and op["cible_id"] == 7
    assert "تجريبي" in op["details"]
