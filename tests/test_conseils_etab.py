"""مجالس المؤسسة حسب المرسوم 2.02.376: التركيبة، الاجتماعات والنصاب، المحاضر والاستدعاءات. بيانات وهمية."""

import pytest

from idara.services import conseils_etab as ce
from tests.test_docs_association import texte
from tests.test_eleves import base  # noqa: F401  (fixture)


def _gestion(base):  # noqa: F811
    lignes = [("المدير أحمد", "رئيس المجلس")] + [(f"الأستاذ {o}", f"ممثل القسم {o}") for o in ce.NIVEAUX]
    lignes += [("الحارس", "ممثل الأطر الإدارية والتقنية"), ("رئيس الجمعية", "رئيس جمعية آباء وأولياء التلاميذ"),
               ("المستشار", "ممثل المجلس الجماعي")]
    ce.enregistrer_membres(base, "gestion", lignes)
    return ce.membres_actifs(base, "gestion")


def test_composition_et_ecarts(base):  # noqa: F811
    p = ce.proposition(base, "gestion")
    assert p[0] == ("أحمد المدير", "رئيس المجلس", "") and p[-1][1] == "ممثل المجلس الجماعي"
    assert [x[1] for x in ce.proposition(base, "enseignement")][:2] == ["مدير المؤسسة", "مدير المؤسسة"]
    ce.enregistrer_membres(base, "gestion", [("المدير", "رئيس المجلس"), ("أ", "ممثل القسم الأول")])
    assert "ممثل المجلس الجماعي" in ce.ecarts_decret(base, "gestion")
    with pytest.raises(ce.ErreurConseil, match="الاسم والصفة"):
        ce.enregistrer_membres(base, "pedagogique", [("", "رئيس المجلس"), ("س", "")])
    with pytest.raises(ce.ErreurConseil, match="حدد المادة"):
        ce.enregistrer_membres(base, "enseignement", [("المدير", "مدير المؤسسة")])
    assert len(_gestion(base)) == 10 and ce.ecarts_decret(base, "gestion") == []


def test_quorum_et_seances(base, dossier):  # noqa: F811
    ms = _gestion(base)
    ids = [m["id"] for m in ms]
    s = ce.Seance("gestion", "2026-10-03", ["دراسة برنامج العمل السنوي الخاص بأنشطة المؤسسة والموافقة عليه"],
                  "10:00", presents=ids[:4])
    with pytest.raises(ce.ErreurConseil, match="النصاب غير مكتمل"):
        ce.enregistrer_seance(base, s)
    s.convocation = "seconde"
    sid = ce.enregistrer_seance(base, s)
    with pytest.raises(ce.ErreurConseil, match="جدول الأعمال"):
        ce.enregistrer_seance(base, ce.Seance("gestion", "2026-10-03", [" "]))
    with pytest.raises(ce.ErreurConseil, match="المستقبل"):
        ce.enregistrer_seance(base, ce.Seance("gestion", "2099-01-01", ["x"]))
    sid2 = ce.enregistrer_seance(base, ce.Seance("gestion", "2026-10-20", ["حصيلة"], presents=ids[:5],
                                                 deliberations="ناقش المجلس.\nصادق المجلس.",
                                                 decisions=["المصادقة على البرنامج"]))
    assert [x["numero"] for x in ce.seances(base, "gestion")] == [1, 2]
    t = texte(ce.generer_pv(base, dossier, sid2))
    assert "الحمد لله وحده" in t and "محضر اجتماع مجلس التدبير رقم 2" in t and "النصاب مكتمل: 5 من 10" in t
    assert "ناقش المجلس." in t and "1- المصادقة على البرنامج" in t and "توقيعات أعضاء مجلس التدبير" in t
    assert "وتغيب:" in t and "المستشار (ممثل المجلس الجماعي)" in t
    t = texte(ce.generer_pv(base, dossier, sid))
    assert "استدعاء ثانٍ" in t
    suivi = {x["conseil"]: x for x in ce.suivi(base)}
    assert suivi["gestion"]["nombre"] == 2 and any("نهاية السنة" in a for a in suivi["gestion"]["alertes"])
    assert "1 من 2" not in " ".join(suivi["gestion"]["alertes"])
    t = texte(ce.generer_convocation(base, dossier, "gestion", "2026-11-20", "15:00", ["النقطة الأولى"]))
    assert "استدعاء لحضور اجتماع مجلس التدبير" in t and "على الساعة 15:00" in t and "تاريخ التوصل" in t


def test_enseignement_tableaux_par_matiere(base, dossier):  # noqa: F811
    ce.enregistrer_membres(base, "enseignement", [("المدير", "مدير المؤسسة", "عربية"), ("أ", "ممثل القسم الأول", "عربية"),
                                                  ("المدير", "مدير المؤسسة", "فرنسية"), ("ب", "ممثل القسم الأول", "فرنسية")])
    sid = ce.enregistrer_seance(base, ce.Seance("enseignement", "2026-10-10", ["تتبع نتائج تحصيل التلاميذ"]))
    t = texte(ce.generer_pv(base, dossier, sid))
    assert "المجالس التعليمية عربية" in t and "المجالس التعليمية فرنسية" in t and "عقدت المجالس التعليمية" in t
    assert "." * 100 in t  # بدون مداولات: أسطر للكتابة باليد
    ce.enregistrer_membres(base, "enseignement", [("المدير", "مدير المؤسسة", "عربية"), ("ج", "ممثل القسم الأول", "عربية")])
    assert len(ce.membres_actifs(base, "enseignement")) == 2 and len(ce.membres(base, "enseignement")) == 5
    assert "ب" in texte(ce.generer_pv(base, dossier, sid))  # المحضر السابق يحتفظ بأعضائه
