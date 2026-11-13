"""أولياء الأمور (طلب المدير 2026-11-13): ملف وهمي بنفس بنية تصدير «Tuteur» من مسار."""

import openpyxl
import pytest
from docx import Document

from idara.services import parents as pa
from tests.test_eleves import AR, base, classeur  # noqa: F401

SOUS = ["ر.ب.و", "الإسم بالعربية", "النسب بالعربية", "الإسم بالفرنسية", "النسب بالفرنسية", "المهنة", "الهاتف",
        "العنوان"]


def fichier_tuteurs(chemin, eleves):
    """eleves: [(رمز مسار، نوع الوصاية، {الدور: [8 قيم]})]"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Tuteur"
    ws.append([None, None, "أكاديمية : ", "الجهة التجريبية", None, "المذيرية الإقليمية : ", "إقليم: تجريبي"])
    ws.append([None, None, "مؤسسة  :", "مدرسة تجريبية", None, "السنة الدراسية", "2026/2027"])
    ws.append([])
    ws.append([None, None, "رقم التلميذ", "النسب بالعربية", "الإسم بالعربية", "نوع الوصاية", "معلومات عن ولي الامر"]
              + [None] * 7 + ["معلومات عن الأب "] + [None] * 7 + ["معلومات عن الأم "])
    ws.append(["=data!A3"] + [None] * 5 + SOUS * 3)
    for k, (code, tut, roles) in enumerate(eleves):
        ligne = [k + 1, None, code, "النسب", "الاسم", tut]
        for r in ("tuteur", "pere", "mere"):
            ligne += roles.get(r, [None] * 8)
        ws.append(ligne)
    wb.create_sheet("data").append(["أب"])
    wb.save(chemin)
    return chemin


def _w(prenom, tel):
    return ["AB1234", prenom, "التجريبي", "Prenom", "Tajribi", "فلاح", tel, "دوار تجريبي"]


def test_import_et_mise_a_jour(base, tmp_path):  # noqa: F811
    code = base.execute("SELECT code_massar FROM eleve ORDER BY id LIMIT 1").fetchone()[0]
    f = fichier_tuteurs(tmp_path / "t.xlsx", [
        (code, "أب", {"tuteur": _w("أحمد", 612345678), "pere": _w("أحمد", "0612345678"),
                     "mere": ["", "فاطمة", "التجريبية", "", "", "ربة بيت", None, ""]}),
        ("Z999999999", "وصي", {"tuteur": _w("غريب", "0600000000")})])
    ls, nf = pa.lire_fichier(f)
    assert nf == 1 and len(ls) == 2 and ls[0]["roles"]["tuteur"]["telephone"] == "0612345678"   # صفر البداية
    r = pa.importer(base, [f])
    assert (r.eleves, r.ajoutes, r.mis_a_jour, r.inconnus) == (1, 3, 0, ["Z999999999"])
    eid = base.execute("SELECT id FROM eleve WHERE code_massar=?", (code,)).fetchone()[0]
    fi = pa.fiche(base, eid)
    assert fi["tuteur"]["tutelle"] == "أب" and fi["mere"]["prenom_ar"] == "فاطمة" and fi["mere"]["telephone"] is None
    # تعديل يدوي ثم إعادة استيراد: الخانة الفارغة في الملف لا تمحو المدخل يدوياً
    pa.enregistrer(base, eid, "mere", {**fi["mere"], "telephone": "0711111111"})
    r = pa.importer(base, [f])
    assert r.ajoutes == 0 and pa.fiche(base, eid)["mere"]["telephone"] == "0711111111"
    with pytest.raises(pa.ErreurParents, match="الهاتف"):
        pa.enregistrer(base, eid, "pere", {"telephone": "abc"})
    pa.enregistrer(base, eid, "pere", {})          # إفراغ كل الخانات يحذف السطر
    assert "pere" not in pa.fiche(base, eid)
    l = next(x for x in pa.lister(base) if x["eleve_id"] == eid)
    assert l["tuteur"] == "أحمد التجريبي" and l["lien"] == "أب" and l["telephone"] == "0612345678"
    assert pa.lister(base, texte="0612345678")[0]["eleve_id"] == eid


def test_fichier_refuse(tmp_path):
    wb = openpyxl.Workbook()
    wb.active.append(["لا شيء"])
    wb.save(tmp_path / "v.xlsx")
    with pytest.raises(pa.ErreurParents, match="لم يُعثر"):
        pa.lire_fichier(tmp_path / "v.xlsx")
    with pytest.raises(pa.ErreurParents, match="Excel"):
        pa.lire_fichier(tmp_path / "v.csv")


def test_liste_par_classe(base, dossier, tmp_path):  # noqa: F811
    code = base.execute("SELECT code_massar FROM eleve ORDER BY id LIMIT 1").fetchone()[0]
    pa.importer(base, [fichier_tuteurs(tmp_path / "t.xlsx", [(code, "أم", {"tuteur": _w("سعاد", "0655555555")})])])
    d = Document(pa.generer_liste(base, dossier))
    cellules = [c.text for t in d.tables for r in t.rows for c in r.cells]
    assert "ولي الأمر" in cellules and "سعاد التجريبي" in cellules and "0655555555" in cellules and code in cellules
