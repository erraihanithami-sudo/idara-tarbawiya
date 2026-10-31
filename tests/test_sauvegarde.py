"""النسخ الاحتياطي والاسترجاع والتصدير. بيانات وهمية فقط."""

import zipfile
from datetime import date

import pytest

from idara.data.db import connecter
from idara.services import sauvegarde as sv


def _ajouter_eleve(conn, code, nom):
    conn.execute(
        "INSERT INTO eleve(code_massar, nom_ar, prenom_ar, sexe, source) VALUES (?,?,?,?,?)",
        (code, nom, "تجريبي", "M", "massar"))
    conn.commit()


def _noms(dossier):
    c = connecter(dossier.base)
    noms = sorted(r[0] for r in c.execute("SELECT nom_ar FROM eleve"))
    c.close()
    return noms


def test_sauvegarde_valide_et_lisible(dossier, conn):
    _ajouter_eleve(conn, "X000000001", "أ")
    f = sv.creer_sauvegarde(dossier)
    assert f.exists() and f.parent == dossier.sauvegardes
    sv.verifier_base(f)


def test_restauration_retrouve_l_etat_et_garde_l_etat_courant(dossier, conn):
    _ajouter_eleve(conn, "X000000001", "أ")
    copie = sv.creer_sauvegarde(dossier)
    _ajouter_eleve(conn, "X000000002", "ب")
    conn.close()
    securite = sv.restaurer_sauvegarde(dossier, copie)
    assert _noms(dossier) == ["أ"]
    # الحالة السابقة للاسترجاع محفوظة وفيها التلميذان
    c = connecter(securite)
    assert c.execute("SELECT COUNT(*) FROM eleve").fetchone()[0] == 2
    c.close()


def test_restauration_pendant_que_la_base_est_ouverte(dossier, conn):
    _ajouter_eleve(conn, "X000000001", "أ")
    copie = sv.creer_sauvegarde(dossier)
    _ajouter_eleve(conn, "X000000002", "ب")
    sv.restaurer_sauvegarde(dossier, copie)
    assert conn.execute("SELECT COUNT(*) FROM eleve").fetchone()[0] == 1


def test_fichier_corrompu_refuse_et_donnees_intactes(dossier, conn):
    _ajouter_eleve(conn, "X000000001", "أ")
    faux = dossier.sauvegardes / "sauvegarde_20260101_000000_faux.db"
    faux.write_bytes(b"ceci n'est pas une base" * 100)
    with pytest.raises(sv.ErreurSauvegarde):
        sv.restaurer_sauvegarde(dossier, faux)
    assert conn.execute("SELECT COUNT(*) FROM eleve").fetchone()[0] == 1


def test_base_etrangere_refusee(tmp_path, dossier, conn):
    import sqlite3
    autre = tmp_path / "autre.db"
    a = sqlite3.connect(autre)
    a.execute("CREATE TABLE t(x)")
    a.commit()
    a.close()
    with pytest.raises(sv.ErreurSauvegarde):
        sv.restaurer_sauvegarde(dossier, autre)


def test_on_garde_les_30_dernieres(dossier, conn):
    for _ in range(35):
        sv.creer_sauvegarde(dossier)
    assert len(sv.lister_sauvegardes(dossier)) == sv.MAX_SAUVEGARDES


def test_sauvegarde_quotidienne_une_seule_fois(dossier, conn):
    premiere = sv.sauvegarde_quotidienne(dossier, date.today())
    assert premiere is not None
    assert sv.sauvegarde_quotidienne(dossier, date.today()) is None


def test_export_et_import_complet(tmp_path, dossier, conn):
    _ajouter_eleve(conn, "X000000001", "أ")
    (dossier.modeles / "شهادة مدرسية.docx").write_bytes(b"modele")
    (dossier.archives / "2026-2027").mkdir()
    (dossier.archives / "2026-2027" / "وثيقة.pdf").write_bytes(b"pdf")
    usb = tmp_path / "usb"
    usb.mkdir()
    archive = sv.exporter(dossier, usb)
    with zipfile.ZipFile(archive) as z:
        noms = set(z.namelist())
    assert {"data.db", "modeles/شهادة مدرسية.docx", "archives/2026-2027/وثيقة.pdf"} <= noms
    assert not any(n.startswith("sauvegardes/") for n in noms)

    # حاسوب جديد: مجلد فارغ
    from idara.data.dossier import DossierDonnees
    neuf = DossierDonnees(tmp_path / "حاسوب جديد").preparer()
    assert sv.importer_export(neuf, archive) is None
    assert _noms(neuf) == ["أ"]
    assert (neuf.modeles / "شهادة مدرسية.docx").read_bytes() == b"modele"
    assert (neuf.archives / "2026-2027" / "وثيقة.pdf").exists()


def test_import_sur_donnees_existantes_garde_une_copie(tmp_path, dossier, conn):
    _ajouter_eleve(conn, "X000000001", "أ")
    archive = sv.exporter(dossier, tmp_path)
    _ajouter_eleve(conn, "X000000002", "ب")
    conn.close()
    securite = sv.importer_export(dossier, archive)
    assert securite is not None and securite.exists()
    assert _noms(dossier) == ["أ"]


def test_archive_malveillante_refusee(tmp_path, dossier, conn):
    piege = tmp_path / "piege.zip"
    with zipfile.ZipFile(piege, "w") as z:
        z.writestr("../../hors_dossier.txt", "x")
        z.writestr("data.db", "x")
    with pytest.raises(sv.ErreurSauvegarde):
        sv.importer_export(dossier, piege)
    assert not (tmp_path / "hors_dossier.txt").exists()
