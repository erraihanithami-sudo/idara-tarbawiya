"""إنهاء الوثائق: حذف علامات الاتجاه، والتحويل إلى HTML للمحرر (2026-11-15). بيانات وهمية."""

import zipfile

from docx import Document

from idara.services import finition as fi
from idara.services import personnel as rh
from idara.services import registres as rg
from tests.test_eleves import AR, base, classeur  # noqa: F401

MARQUES = "⁦⁩⁧⁨"


def test_segments():
    assert fi._segments("ولد في ⁦22/12/1976⁩ بوجدة") == [("ولد في ", False), ("22/12/1976", True),
                                                                  (" بوجدة", False)]
    assert fi._segments("⁦AB1⁩") == [("AB1", True)] and fi._segments("نص") == [("نص", False)]
    assert fi.sans_marques("⁦x⁩") == "x"


def test_nettoyage_des_marques(base, dossier):  # noqa: F811
    rh.enregistrer(base, rh.Personnel(nom_ar="التجريبي", prenom_ar="سعيد", sexe="M", categorie="enseignant",
                                      ppr="1234567", date_naissance="1985-01-02", nom_fr="TAJRIBI", prenom_fr="Said"))
    p = rg.generer(base, dossier, "demandes", "fiche_personnelle", cible="سعيد التجريبي")
    brut = zipfile.ZipFile(p).read("word/document.xml").decode()
    assert "⁦" in brut   # المولّدات ما زالت تعزل الأرقام…
    assert fi.nettoyer_marques(p) is True
    brut = zipfile.ZipFile(p).read("word/document.xml").decode()
    assert not any(m in brut for m in MARQUES)   # …والملف المعروض بلا أي علامة
    d = Document(p)   # الوثيقة سليمة، والنص المعزول صار مقطعاً من اليسار إلى اليمين
    runs = [r for t in d.tables for row in t.rows for c in row.cells for q in c.paragraphs for r in q.runs]
    ppr = next(r for r in runs if r.text == "1234567")
    assert ppr._element.rPr.find(fi._q("rtl")) is None
    nom = next(r for r in runs if r.text == "التجريبي سعيد")
    assert nom._element.rPr.find(fi._q("rtl")) is not None
    assert any(r.text == "02/01/1985" for r in runs) and any(r.text == "TAJRIBI SAID" for r in runs)
    assert fi.nettoyer_marques(p) is False   # لا شيء يُعاد
    assert fi.nettoyer_marques(dossier.racine / "غير_موجود.docx") is False


def test_conversion_html(base, dossier):  # noqa: F811
    rg.enregistrer(base, "agents", {"nom": "عون تجريبي", "fonction": "الحراسة", "horaire": "8:00 - 16:00"})
    pg = fi.en_html(rg.generer(base, dossier, "agents", "service"))
    assert not pg.paysage and pg.largeur_mm == 210.0 and pg.marges_mm[0] == 18.0
    h = pg.html
    assert 'dir="rtl"' in h and "جدول الخدمة" in h and "<table" in h and "عون تجريبي" in h
    assert 'bgcolor="#E7E6F0"' in h and "text-decoration:underline" in h and 'align="center"' in h
    assert not any(m in h for m in MARQUES)
    # أعمدة الجدول معكوسة (الجدول مرئياً من اليمين): «ر.ت» آخر خلية في سطر العناوين
    entete = h[h.index("<tr>"):h.index("</tr>")]
    assert entete.index("توقيت العمل") < entete.index("الاسم الكامل") < entete.index("ر.ت")
    # الشهادة: أفقية
    nom, classe = rg.eleves(base)[0]
    lid = rg.enregistrer(base, "tahfiz", {"date": "2026-11-14", "eleve": nom, "classe": classe,
                                          "type": "شهادة تقديرية", "motif": "التفوق"})
    pg = fi.en_html(rg.generer(base, dossier, "tahfiz", "certificat", lid))
    assert pg.paysage and nom in pg.html and "color:#2E3192" in pg.html and "font-size:40pt" in pg.html


def test_cellules_fusionnees(tmp_path):
    d = Document()
    t = d.add_table(rows=3, cols=3)
    t.cell(0, 0).merge(t.cell(0, 1)).text = "أفقي"
    t.cell(1, 2).merge(t.cell(2, 2)).text = "عمودي"
    d.add_paragraph("بعد⁦ 12 ⁩الجدول")
    p = tmp_path / "t.docx"
    d.save(p)
    h = fi.en_html(p).html
    assert 'colspan="2"' in h and 'rowspan="2"' in h and h.count("<td") == 7 and "بعد 12 الجدول" in h
