"""تتبع مشروع المؤسسة (بيانات وهمية)."""

import pytest
from docx import Document

from idara.services import projet_etab as pe
from tests.fabrique_projet import export_operations, rapport_plan_action
from tests.test_eleves import base  # noqa: F401


def _textes(f):
    d = Document(f)
    return "\n".join([p.text for p in d.paragraphs] + [c.text for t in d.tables for r in t.rows for c in r.cells])


def test_projet_indicateurs(base):  # noqa: F811
    with pytest.raises(pe.ErreurProjet, match="قبل"):
        pe.enregistrer_projet(base, "م", "2027/2028", "2026/2027")
    with pytest.raises(pe.ErreurProjet, match="صيغة"):
        pe.enregistrer_projet(base, "م", "2026/2028", "2027/2028")
    pid = pe.enregistrer_projet(base, "", "2025/2026", "2027/2028")
    assert pe.projet_actif(base)["intitule"] == "مشروع المؤسسة المندمج"
    assert pe.annees_projet("2025/2026", "2027/2028") == ["2025/2026", "2026/2027", "2027/2028"]
    pe.enregistrer_cibles(base, pid, [("hadar", "ref", "3", None), ("hadar", "2026/2027", "2,5", None),
                                      ("activites", "2025/2026", "20", "18"), ("activites", "2026/2027", 30, None)])
    with pytest.raises(pe.ErreurProjet, match="بين 0 و100"):
        pe.enregistrer_cibles(base, pid, [("tarl", "ref", 120, None)])
    # منقطع واحد ونادٍ بتلميذين هذه السنة
    aid = base.execute("SELECT id FROM annee_scolaire WHERE libelle='2026/2027'").fetchone()[0]
    ids = [r[0] for r in base.execute("SELECT id FROM inscription WHERE annee_id=? ORDER BY id", (aid,))]
    eleves = [r[0] for r in base.execute("SELECT eleve_id FROM inscription WHERE annee_id=? ORDER BY id", (aid,))]
    with base:
        base.execute("UPDATE inscription SET statut='interrompu', date_sortie='2026-11-01' WHERE id=?", (ids[0],))
        cid = base.execute("INSERT INTO club(annee_id, nom) VALUES (?, 'نادي البيئة')", (aid,)).lastrowid
        base.executemany("INSERT INTO club_membre(club_id, eleve_id) VALUES (?,?)", [(cid, e) for e in eleves[1:3]])
    t = pe.tableau_indicateurs(base, pid)
    h = {l["annee"]: l for l in t["hadar"]["annees"]}
    assert h["2026/2027"]["realise"] == round(100 / len(ids), 1) and h["2026/2027"]["source"] == "البرنامج"
    assert h["2026/2027"]["atteint"] is (100 / len(ids) <= 2.5)
    ac = {l["annee"]: l for l in t["activites"]["annees"]}
    assert ac["2025/2026"]["realise"] == 18 and ac["2025/2026"]["source"] == "يدوي" and ac["2025/2026"]["atteint"] is False
    assert ac["2026/2027"]["realise"] == round(200 / (len(ids) - 1), 1)
    assert t["hadar"]["reference"] == 3 and t["hadar"]["derniere"]["annee"] == "2026/2027"
    assert t["tarl"]["derniere"] is None   # لا روائز في البيانات الوهمية


def test_import_et_suivi(base, dossier, tmp_path):  # noqa: F811
    pid = pe.enregistrer_projet(base, "مشروع تجريبي", "2026/2027", "2028/2029")
    ops = pe.lire_operations(rapport_plan_action(tmp_path / "plan.xlsx"))
    assert [o["axe"] for o in ops] == ["التلميذ", "التلميذ", "المؤسسة التعليمية"]
    assert ops[0]["critere"] == "11 : الأنشطة الموازية" and ops[0]["date_debut"] == "2026-09-01"
    assert ops[0]["montant"] == 2500 and ops[0]["priorite"] == 1 and ops[1]["sous_critere"] == ops[0]["sous_critere"]
    r = pe.importer_operations(base, pid, tmp_path / "plan.xlsx")
    assert (r.ajoutees, r.mises_a_jour) == (3, 0)
    o = next(x for x in pe.operations(base, pid) if x["intitule"].startswith("تعبئة"))
    pe.suivre(base, o["id"], "realisee", None, "1400", "أنجزت")
    o2 = next(x for x in pe.operations(base, pid) if x["intitule"].startswith("تنظيم"))
    pe.suivre(base, o2["id"], "en_cours", "40", None, "")
    with pytest.raises(pe.ErreurProjet, match="غير معروفة"):
        pe.suivre(base, o2["id"], "x")
    # إعادة الاستيراد بمبلغ جديد: تُحدَّث المعطيات المبرمجة ويبقى التتبع
    r = pe.importer_operations(base, pid, rapport_plan_action(tmp_path / "plan2.xlsx", variante=2))
    assert (r.ajoutees, r.mises_a_jour) == (0, 3)
    o = next(x for x in pe.operations(base, pid) if x["id"] == o["id"])
    assert o["montant"] == 3000 and o["statut"] == "realisee" and o["taux"] == 100 and o["montant_depense"] == 1400
    # ملف التصدير: عمليتان، إحداهما موجودة بنفس المعيار والاسم؟ لا: «11 : الأنشطة الموازية» بدون فراغات زائدة
    r = pe.importer_operations(base, pid, export_operations(tmp_path / "export.xlsx"))
    assert r.ajoutees + r.mises_a_jour == 2
    assert any(x["ref_massar"] == "A-1" and x["axe"] == "الأستاذ" for x in pe.operations(base, pid))
    s = pe.synthese_operations(base, pid)
    assert s["par_statut"]["realisee"] == 1 and s["par_statut"]["en_cours"] == 1
    assert s["montant_depense"] == 1400 and s["axes"][0]["axe"] == "التلميذ"
    with pytest.raises(pe.ErreurProjet, match="لم يُعثر"):
        from openpyxl import Workbook
        Workbook().save(tmp_path / "vide.xlsx")
        pe.lire_operations(tmp_path / "vide.xlsx")
    # التقارير
    t = _textes(pe.generer_rapport(base, dossier, pid))
    assert "التقرير التركيبي لتنزيل مشروع المؤسسة المندمج" in t and "تعبئة طفايات الحريق الوهمية" in t
    assert "الهدف 2: تقليص الهدر المدرسي" in t and "منجزة" in t
    t = _textes(pe.generer_rapport(base, dossier, pid, final=True))
    assert "خلاصات لاستثمارها في صياغة المشروع الجديد" in t and "العمليات غير المنجزة" in t
