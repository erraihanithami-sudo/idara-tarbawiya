"""تطبيق الترويسة والعلامة المائية والتذييل على الوثائق المولدة. صور وبيانات وهمية."""

import io
import zipfile

import pytest
from lxml import etree
from PIL import Image as PILImage

from idara.services import documents as dc
from idara.services import etablissement as et
from idara.services import identite_docx as idt
from idara.services import moteur_docx as m

W, WP, A, V = m.W, m.WP, idt.A, idt.V


def _image(chemin, l, h, couleur=(0, 98, 51)):
    PILImage.new("RGB", (l, h), couleur).save(chemin)
    return chemin


@pytest.fixture
def pret(tmp_path, dossier, conn):
    et.appliquer_configuration_initiale(conn, dossier, et.ConfigurationInitiale(
        etablissement=et.Etablissement(nom_ar="مدرسة تجريبية", direction_ar="م", academie_ar="أ",
                                       pied_page="مدرسة تجريبية - الهاتف 0500000000"),
        directeur=et.Directeur(nom_ar="المدير", prenom_ar="أحمد", sexe="M"),
        logo_source=str(_image(tmp_path / "ترويسة.png", 1700, 300)),
        filigrane_source=str(_image(tmp_path / "علامة.jpg", 600, 600, (200, 40, 40)))))
    return conn


def _parties(data: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        assert z.testzip() is None
        return {n: z.read(n) for n in z.namelist()}


def _generer(conn, dossier, code):
    v, p = dc.exemple(conn, code, "M")
    return _parties(dc.generer(conn, dossier, code, v, p, essai=True).chemin.read_bytes())


def test_ajuster_garde_les_proportions():
    assert idt.ajuster(1700, 300, 6000000, 1152000) == (6000000, 1058823)
    assert idt.ajuster(600, 600, 6000000, 1152000) == (1152000, 1152000)


@pytest.mark.parametrize("code", ["certificat_scolarite_ancien", "visite_medicale"])
def test_entete_filigrane_pied_remplaces(pret, dossier, code):
    parties = _generer(pret, dossier, code)
    medias_idara = [n for n in parties if n.startswith("word/media/idara_")]
    assert len(medias_idara) == 2  # الترويسة والعلامة المائية
    assert b'Extension="png"' in parties["[Content_Types].xml"]
    tout = {n: etree.fromstring(d) for n, d in parties.items() if n.endswith(".xml") and n.startswith("word/")}
    noms = [dp.get("name") for r in tout.values() for dp in r.iter(f"{{{WP}}}docPr")]
    assert noms.count("IDARA_ENTETE") == 1
    assert "IDARA_ENTETE_DECOR" not in noms and "IDARA_PIED" not in noms
    assert noms.count("IDARA_FILIGRANE") == 3  # في الترويسات الثلاث التي كانت فيها العلامة القديمة
    for r in tout.values():
        assert not [s for s in r.iter(f"{{{V}}}shape") if (s.get("id") or "").startswith("WordPictureWatermark")]
    # الترويسة الجديدة: لا قص بحدود الصورة القديمة
    for r in tout.values():
        for dp in r.iter(f"{{{WP}}}docPr"):
            if dp.get("name") == "IDARA_ENTETE":
                ancre = dp.getparent()
                assert ancre.find(f"{{{WP}}}wrapPolygon") is None
                assert ancre.find(f"{{{WP}}}wrapTopAndBottom") is not None
    assert "مدرسة تجريبية - الهاتف 0500000000" in m.texte_complet(_zip(parties))


def _zip(parties):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        for n, d in parties.items():
            z.writestr(n, d)
    return b.getvalue()


def test_vacances_entete_dans_le_corps_et_filigrane_ajoute(pret, dossier):
    parties = _generer(pret, dossier, "attestation_vacances")
    doc = etree.fromstring(parties["word/document.xml"])
    entete = [dp for dp in doc.iter(f"{{{WP}}}docPr") if dp.get("name") == "IDARA_ENTETE"]
    assert len(entete) == 1
    blip = next(entete[0].getparent().iter(f"{{{A}}}blip"))
    rels = parties["word/_rels/document.xml.rels"].decode()
    assert blip.get(f"{{{idt.R}}}embed") in rels and "media/idara_" in rels
    entetes = [etree.fromstring(d) for n, d in parties.items() if n.startswith("word/header")]
    filigranes = [dp for r in entetes for dp in r.iter(f"{{{WP}}}docPr") if dp.get("name") == "IDARA_FILIGRANE"]
    assert len(filigranes) == 1  # أضيفت إلى الترويسة الافتراضية فقط


def test_convocation_sans_entete_reste_valide(pret, dossier):
    parties = _generer(pret, dossier, "convocation_parent")
    assert not [n for n in parties if n.startswith("word/media/idara_")]


def test_sans_identite_rien_ne_change(dossier, conn):
    et.appliquer_configuration_initiale(conn, dossier, et.ConfigurationInitiale(
        etablissement=et.Etablissement(nom_ar="م", direction_ar="م", academie_ar="أ"),
        directeur=et.Directeur(nom_ar="ب", prenom_ar="أ", sexe="F")))
    parties = _generer(conn, dossier, "certificat_scolarite_ancien")
    assert not [n for n in parties if n.startswith("word/media/idara_")]
    noms = [dp.get("name") for n, d in parties.items() if n.endswith(".xml") and n.startswith("word/")
            for dp in etree.fromstring(d).iter(f"{{{WP}}}docPr")]
    assert "IDARA_ENTETE" in noms and "IDARA_PIED" in noms


def test_image_illisible(pret, dossier):
    etab = et.lire_etablissement(pret)
    (dossier.racine / etab.logo_path).write_bytes(b"pas une image")
    v, _ = dc.exemple(pret, "visite_medicale")
    with pytest.raises(dc.ErreurDocument, match="الترويسة"):
        dc.generer(pret, dossier, "visite_medicale", v, essai=True)


# ---------- تحديث قوالب الإصدارات السابقة ----------

def test_ancien_modele_non_modifie_mis_a_jour(dossier, monkeypatch):
    cible = dc.chemin_modele(dossier, "visite_medicale")
    cible.write_bytes(b"ancienne version")
    empreinte = dc._empreinte(cible)
    monkeypatch.setattr(dc, "_anciennes_versions", lambda: {"visite_medicale": [empreinte]})
    dc.chemin_modele(dossier, "visite_medicale")
    assert cible.read_bytes() == dc.chemin_defaut("visite_medicale").read_bytes()


def test_modele_modifie_par_le_directeur_jamais_ecrase(dossier, monkeypatch):
    cible = dc.chemin_modele(dossier, "visite_medicale")
    cible.write_bytes(b"modifie par le directeur")
    monkeypatch.setattr(dc, "_anciennes_versions", lambda: {"visite_medicale": ["autre"]})
    dc.chemin_modele(dossier, "visite_medicale")
    assert cible.read_bytes() == b"modifie par le directeur"


def test_liste_des_anciennes_versions_valide():
    versions = dc._anciennes_versions()
    for code in dc.MODELES:
        assert dc._empreinte(dc.chemin_defaut(code)) not in versions.get(code, [])


@pytest.mark.parametrize("code", ["certificat_scolarite_ancien", "visite_medicale"])
def test_pied_en_image(pret, dossier, tmp_path, code):
    """طلب المدير 2026-11-07: التذييل بصورة من الحاسوب بدل النص."""
    etab = et.lire_etablissement(pret)
    etab.pied_image_path = et.importer_image(dossier, _image(tmp_path / "تذييل.png", 1800, 200, (10, 30, 90)), "pied")
    et.enregistrer_etablissement(pret, etab)
    parties = _generer(pret, dossier, code)
    assert len([n for n in parties if n.startswith("word/media/idara_")]) == 3   # الترويسة والعلامة والتذييل
    tout = {n: etree.fromstring(d) for n, d in parties.items() if n.endswith(".xml") and n.startswith("word/")}
    images_pied = [(n, dp) for n, r in tout.items() for dp in r.iter(f"{{{WP}}}docPr")
                   if dp.get("name") == "IDARA_PIED_IMAGE"]
    assert images_pied and "IDARA_PIED" not in [dp.get("name") for r in tout.values() for dp in r.iter(f"{{{WP}}}docPr")]
    for n, dp in images_pied:
        ext = dp.getparent().find(f"{{{WP}}}extent")
        assert int(ext.get("cx")) <= idt.LARGEUR_MAX_PIED and int(ext.get("cy")) <= idt.HAUTEUR_MAX_PIED
        rid = next(dp.getparent().iter(f"{{{A}}}blip")).get(f"{{{idt.R}}}embed")
        rels = parties[f"word/_rels/{n.split('/')[1]}.rels"].decode()
        assert rid in rels
    assert "مدرسة تجريبية - الهاتف 0500000000" not in m.texte_complet(_zip(parties))
