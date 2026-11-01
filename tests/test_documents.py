"""محرك القوالب والوثائق. القوالب الحقيقية مفرغة من البيانات الشخصية، والقيم وهمية."""

import io
import re
import zipfile
from datetime import date

import pytest
from lxml import etree

from idara.services import documents as dc
from idara.services import etablissement as et
from idara.services import moteur_docx as m

W = m.W


def _run(t: str) -> str:
    gras = t.startswith("**")
    t = t[2:] if gras else t
    return f'<w:r>{"<w:rPr><w:b/></w:rPr>" if gras else ""}<w:t xml:space="preserve">{t}</w:t></w:r>'


def _docx(*paragraphes: list[str]) -> bytes:
    """وثيقة Word صغيرة: كل فقرة قائمة مقاطع (runs)، لاختبار تقطيع Word للنص.
    المقطع الذي يبدأ بـ ** يكون بخط عريض."""
    corps = "".join("<w:p>" + "".join(_run(t) for t in runs) + "</w:p>" for runs in paragraphes)
    doc = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           f'<w:document xmlns:w="{W}"><w:body>{corps}<w:sectPr/></w:body></w:document>')
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", doc)
    return b.getvalue()


# ---------- المحرك ----------

def test_champ_coupe_sur_plusieurs_runs():
    modele = _docx(["الاسم: {", "{ no", "m }", "} انتهى"], ["{{ville}} في {{date}}"])
    assert m.champs_du_modele(modele) == {"nom", "ville", "date"}
    sortie = m.remplir(modele, {"nom": "سعيد", "ville": "المدينة", "date": "1 نونبر 2026"})
    assert m.texte_complet(sortie) == "الاسم: سعيد انتهى\nالمدينة في 1 نونبر 2026"
    assert m.champs_du_modele(sortie) == set()


def test_champ_sans_valeur_refuse():
    with pytest.raises(m.ErreurModele, match="date"):
        m.remplir(_docx(["{{ville}} {{date}}"]), {"ville": "x"})


def test_valeur_ne_peut_pas_injecter_un_champ():
    sortie = m.remplir(_docx(["{{a}}"]), {"a": "{{b}}"})
    assert m.champs_du_modele(sortie) == set()


def test_formatage_du_run_de_depart_conserve():
    sortie = m.remplir(_docx(["رقم: ", "**{{num}}"]), {"num": "8173"})
    racine = etree.fromstring(zipfile.ZipFile(io.BytesIO(sortie)).read("word/document.xml"))
    t = [t for t in racine.iter(f"{{{W}}}t") if t.text == "8173"][0]
    assert t.getparent().find(f"{{{W}}}rPr/{{{W}}}b") is not None


# ---------- القوالب الحقيقية ----------

@pytest.fixture
def pret(dossier, conn):
    et.appliquer_configuration_initiale(conn, dossier, et.ConfigurationInitiale(
        etablissement=et.Etablissement(nom_ar="مدرسة تجريبية", nom_fr="ECOLE TEST",
                                       direction_ar="م", academie_ar="أ",
                                       ville_redaction_ar="المدينة", ville_redaction_fr="Ville"),
        directeur=et.Directeur(nom_ar="المدير", prenom_ar="أحمد", nom_fr="Moudir",
                               prenom_fr="Ahmed", sexe="F"),
        annee="2026/2027"))
    return conn


def _valide(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        assert z.testzip() is None
        for n in z.namelist():
            if n.endswith(".xml"):
                etree.fromstring(z.read(n))
    return m.texte_complet(data)


@pytest.mark.parametrize("code", list(dc.MODELES))
def test_modeles_fournis_sans_donnees_personnelles(code):
    data = dc.chemin_defaut(code).read_bytes()
    texte = m.texte_complet(data)
    assert not re.search(r"\b[A-Z]\d{9}\b", texte), "رمز مسار حقيقي في القالب"
    assert not re.search(r"\b[A-Z]{1,2}\d{4,7}\b", texte), "رقم بطاقة وطنية في القالب"
    inconnus = [c for c in m.champs_du_modele(data) if not dc.champ_reconnu(code, c)]
    assert inconnus == []


@pytest.mark.parametrize("code", list(dc.MODELES))
@pytest.mark.parametrize("sexe", ["M", "F"])
def test_generation_complete(pret, dossier, code, sexe):
    valeurs, pages = dc.exemple(pret, code, sexe)
    doc = dc.generer(pret, dossier, code, valeurs, pages, essai=True)
    texte = _valide(doc.chemin.read_bytes())
    assert "{{" not in texte
    assert "essais" in doc.chemin.parts


def test_certificat_accords(pret, dossier):
    for sexe, attendus in {"M": ["أن السيد", "المزداد بتاريخ", "كان يتابع دراسته", "درس به",
                                  "وقد انقطع", "سلمت له"],
                           "F": ["أن السيدة", "المزدادة بتاريخ", "كانت تتابع دراستها", "درست به",
                                 "وقد انقطعت", "سلمت لها"]}.items():
        v, _ = dc.exemple(pret, "certificat_scolarite_ancien", sexe)
        texte = m.texte_complet(dc.generer(pret, dossier, "certificat_scolarite_ancien", v,
                                           essai=True).chemin.read_bytes())
        for a in attendus:
            assert a in texte, (sexe, a)
        # المديرة (الإعداد أعلاه: أنثى)
        assert "يشهد السيدة: أحمد المدير" in texte
        assert "بصفتها مديرة لمدرسة تجريبية" in texte
        assert "من تاريخ: 15/10/1992 إلى 30/06/1998" in texte
        assert "بتاريخ: 30 يونيو 1998" in texte


def test_vacances_accords(pret, dossier):
    v, _ = dc.exemple(pret, "attestation_vacances", "F")
    texte = m.texte_complet(dc.generer(pret, dossier, "attestation_vacances", v,
                                       essai=True).chemin.read_bytes())
    for a in ["Je soussignée, MOUDIR AHMED", "En tant que directrice", "TAJRIBI SALMA",
              "Née le", "Inscrite", "5ème année de l’enseignement primaire",
              "l’intéressée", "de la directrice"]:
        assert a in texte, a


def test_convocation_par_pages(pret, dossier):
    v, pages = dc.exemple(pret, "convocation_parent")
    assert len(pages) == 2 and set(pages[1]) == {"eleve_1", "tilmidh_1", "ibn_1"}
    data = dc.generer(pret, dossier, "convocation_parent", v, pages, essai=True).chemin.read_bytes()
    texte = _valide(data)
    for nom in ("سعيد التجريبي", "سلمى التجريبي", "يوسف التجريبي"):
        assert nom in texte
    assert "التلميذة سلمى" in texte and "ابنتكم" in texte
    racine = etree.fromstring(zipfile.ZipFile(io.BytesIO(data)).read("word/document.xml"))
    sauts = [b for b in racine.iter(f"{{{W}}}br") if b.get(f"{{{W}}}type") == "page"]
    assert len(sauts) == 1
    ids = [d.get("id") for d in racine.iter(f"{{{m.WP}}}docPr")]
    assert len(ids) == len(set(ids)) == 3  # مربعان في الصفحة الأولى ومربع واحد في الثانية


@pytest.mark.parametrize("modif, message", [
    (dict(sexe=None), "نوع التلميذ"),
    (dict(nom_fr="", prenom_fr=""), "بالفرنسية"),
    (dict(lieu_fr=None), "مكان الازدياد بالفرنسية"),
])
def test_donnees_manquantes_vacances(pret, modif, message):
    e = {**dc._eleve_exemple("M"), **modif}
    with pytest.raises(dc.ErreurDocument, match=message):
        dc.champs_attestation_vacances(pret, e, "5AP", "2026-07-07", "2026-08-31")


def test_periode_inversee(pret):
    with pytest.raises(dc.ErreurDocument, match="قبل"):
        dc.champs_attestation_vacances(pret, dc._eleve_exemple(), "5AP", "2026-08-31", "2026-07-07")


@pytest.mark.parametrize("champ", ["date_entree", "date_sortie", "date_naissance", "lieu_ar",
                                   "dernier_niveau", "num_registre"])
def test_certificat_tous_les_champs_obligatoires(pret, champ):
    e = dc._eleve_exemple("M", num_registre=5, date_naissance="1985-01-01", date_entree="1992-10-15",
                          date_sortie="1998-06-30", dernier_niveau="الخامس")
    e[champ] = None
    with pytest.raises(dc.ErreurDocument):
        dc.champs_certificat_ancien(pret, e, "x", "y")


def test_certificat_dates_incoherentes(pret):
    e = dc._eleve_exemple("M", num_registre=5, date_naissance="1985-01-01", date_entree="1998-10-15",
                          date_sortie="1992-06-30", dernier_niveau="الخامس")
    with pytest.raises(dc.ErreurDocument, match="منطقية"):
        dc.champs_certificat_ancien(pret, e, "x", "y")


def test_sans_configuration(conn):
    with pytest.raises(dc.ErreurDocument, match="إعداد"):
        dc.champs_communs(conn)


# ---------- الأرشفة وإعادة الطباعة ----------

def test_archive_et_reimpression(pret, dossier):
    v, _ = dc.exemple(pret, "visite_medicale", "M")
    doc = dc.generer(pret, dossier, "visite_medicale", v, libelle="سعيد التجريبي")
    assert doc.id is not None and "2026-2027" in doc.chemin.parts
    ligne = pret.execute("SELECT * FROM document_genere WHERE id=?", (doc.id,)).fetchone()
    assert (dossier.racine / ligne["fichier_archive"]).exists()
    # تغيير اسم المؤسسة بعد التوليد لا يغير الوثيقة المعاد طباعتها
    pret.execute("UPDATE etablissement SET nom_ar='اسم جديد'")
    pret.commit()
    re2 = dc.regenerer(pret, dossier, doc.id)
    assert m.texte_complet(re2.chemin.read_bytes()) == m.texte_complet(doc.chemin.read_bytes())
    assert len(dc.documents_recents(pret)) == 2
    assert dc.documents_recents(pret)[0]["libelle"] == "سعيد التجريبي"


# ---------- قوالب المؤسسة ----------

def test_modele_copie_dans_le_dossier(dossier):
    etat = dc.etat_modele(dossier, "visite_medicale")
    assert etat.chemin.parent == dossier.modeles and etat.utilisable and not etat.personnalise


def test_import_modele(tmp_path, dossier):
    bon = tmp_path / "قالبي.docx"
    bon.write_bytes(_docx(["{{mudir}} {{etablissement}}: {{eleve}}"]))
    etat = dc.importer_modele(dossier, "visite_medicale", bon)
    assert etat.personnalise and etat.utilisable
    assert set(etat.absents) == {"tilmidh", "niveau", "ville"}
    mauvais = tmp_path / "خطأ.docx"
    mauvais.write_bytes(_docx(["{{champ_invente}}"]))
    with pytest.raises(dc.ErreurDocument, match="champ_invente"):
        dc.importer_modele(dossier, "visite_medicale", mauvais)
    dc.restaurer_modele(dossier, "visite_medicale")
    assert not dc.etat_modele(dossier, "visite_medicale").personnalise


def test_modele_corrompu_signale(dossier):
    dc.chemin_modele(dossier, "visite_medicale").write_bytes(b"pas un docx")
    etat = dc.etat_modele(dossier, "visite_medicale")
    assert not etat.utilisable


def test_champs_de_cases_reconnus():
    assert dc.champ_reconnu("convocation_parent", "eleve_7")
    assert not dc.champ_reconnu("convocation_parent", "eleve")
    assert not dc.champ_reconnu("visite_medicale", "eleve_1")
