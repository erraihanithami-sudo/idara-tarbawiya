"""وثيقة «التنظيم التربوي» (نموذج المدير 2026-11-03). أسماء وأرقام وهمية."""

import os
from pathlib import Path

import docx
import pytest
from docx.oxml.ns import qn

from idara.services import etablissement as et
from idara.services import import_eleves as imp
from idara.services import personnel as rh
from idara.services import tanzim as tz
from tests.fabrique_massar import classeur
from tests.test_import_massar import AR, FR


@pytest.fixture
def base(tmp_path, dossier, conn):
    et.appliquer_configuration_initiale(conn, dossier, et.ConfigurationInitiale(
        etablissement=et.Etablissement(nom_ar="مدرسة تجريبية", direction_ar="م", academie_ar="أ",
                                       ville_redaction_ar="المدينة"),
        directeur=et.Directeur(nom_ar="المدير", prenom_ar="أحمد", sexe="M", ppr="1000000"),
        annee="2026/2027", unites=["الوحدة المركزية", "وحدة فرعية"]))
    r = imp.analyser(conn, [classeur(tmp_path / "a.xlsx", AR), classeur(tmp_path / "f.xlsx", FR, "fr")])
    imp.appliquer(conn, dossier, r)
    return conn


def _classe(conn, code):
    return conn.execute("SELECT id FROM classe WHERE code=?", (code,)).fetchone()[0]


def _prof(conn, prenom, ppr, **k):
    d = dict(nom_ar="التجريبي", prenom_ar=prenom, sexe="M", categorie="enseignant", ppr=ppr, grade="الدرجة الأولى",
             matiere="عربية", date_recrutement="2005-09-16", date_affectation="2015-09-01", date_grade="2020-01-01",
             echelon="7", date_echelon="2023-06-01", note_inspection=16.5, date_inspection="2025-03-10",
             inspecteur="المفتش التجريبي", unite="الوحدة المركزية")
    d.update(k)
    return rh.enregistrer(conn, rh.Personnel(**d))


def _completer(conn):
    e = et.lire_etablissement(conn)
    e.code_etab, e.telephone, e.commune_ar = "12345X", "0536000000", "الجماعة التجريبية"
    et.enregistrer_etablissement(conn, e)
    d = next(p for p in rh.lister(conn) if p.categorie == "directeur")
    d.date_recrutement, d.date_fonction, d.date_affectation = "2000-09-16", "2018-09-01", "2018-09-01"
    d.repos_matin, d.repos_soir = "الأربعاء", "السبت"
    rh.enregistrer(conn, d)


def test_manquants_puis_generation(base, dossier):
    assert any("رمز المؤسسة" in m for m in tz.manquants(base))
    assert any("أحمد المدير" in m and "تاريخ المهمة الحالية" in m for m in tz.manquants(base))
    with pytest.raises(tz.ErreurTanzim, match="معطيات ناقصة"):
        tz.generer(base, dossier)
    _completer(base)
    _prof(base, "سعيد", "2000001", classes=[_classe(base, "4APG-5APG-6APG")], matiere_tarl="فرنسية",
          classes_tarl="مجموعة القراءة 2")
    _prof(base, "كريم", "2000002", classes=[_classe(base, "PS1-PS2")], sans_inspection=True, note_inspection=None,
          date_inspection="", inspecteur="", unite="وحدة فرعية")
    _prof(base, "نادية", "2000003", sexe="F", situation="charge_in", etab_charge="مدرسة الأصل", date_charge="2026-09-05",
          classes=[_classe(base, "4APG-5APG-6APG")])
    _prof(base, "هشام", "2000004", situation="charge_out", etab_charge="مدرسة التكليف", date_charge="2026-09-10")
    rh.enregistrer(base, rh.Personnel(nom_ar="المساعدة", prenom_ar="سلمى", sexe="F", categorie="assistant",
                                      cin="AB12345", date_affectation="2025-10-01"))
    tz.definir_inspecteurs(base, {"tanzim_insp_ar": "المفتش أ", "tanzim_insp_fr": "المفتشة ب", "tanzim_insp_mixte": ""})
    assert tz.manquants(base) == []
    s = {x["niveau"]: x for x in tz.structure(base)}
    assert s["6AP"]["total"] == 2 and s["6AP"]["groupes"] == [("4APG-5APG-6APG", 2)] and s["6AP"]["moyenne"] == 2
    assert s["5AP"]["total"] == 1 and s["1AP"]["groupes"] == [] and s["1AP"]["moyenne"] is None
    f = tz.generer(base, dossier)
    assert f.exists() and "التنظيم التربوي" in str(f)
    d = docx.Document(str(f))
    texte = "".join(x.text or "" for x in d.element.body.iter(qn("w:t")))
    for attendu in ("للموسم الدراسي 2026/2027", "12345X", "الجماعة التجريبية", "عربية: المفتش أ",
                    "مزدوج: —", "سعيد التجريبي", "2000001", "16.5", "مجموعة القراءة 2", "لم يُفتَّش بعد",
                    "مدرسة الأصل", "05/09/2026", "مدرسة التكليف", "المساعدون التربويون", "سلمى المساعدة",
                    "AB12345", "حرر في: المدينة"):
        assert attendu in texte, attendu
    assert "أنصاف أيام العطلة الأسبوعية" not in texte   # قرار المدير 2026-11-07
    tbls = list(d.element.body.iter(qn("w:tbl")))
    ens = tbls[4]   # بعد إضافة جدول المساعدين
    assert len(ens.findall(qn("w:tr"))) == 2 + 2   # عنوانان + أستاذان يعملان بالمؤسسة
    if os.environ.get("TANZIM_SORTIE"):
        Path(os.environ["TANZIM_SORTIE"]).write_bytes(f.read_bytes())


def test_inspecteurs(base):
    tz.definir_inspecteurs(base, {"tanzim_insp_fr": "  المفتشة   ب "})
    assert tz.inspecteurs(base)["tanzim_insp_fr"] == "المفتشة ب"
    tz.definir_inspecteurs(base, {"tanzim_insp_fr": ""})
    assert tz.inspecteurs(base)["tanzim_insp_fr"] == ""
    with pytest.raises(tz.ErreurTanzim):
        tz.definir_inspecteurs(base, {"autre": "x"})
