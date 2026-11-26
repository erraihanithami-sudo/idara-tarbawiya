"""مقترح برنامج العمل السنوي (نموذج المدير 2026-11-26): التواريخ من المقرر والأيام العالمية، والتعديل والوثيقة.
بيانات وهمية."""

from datetime import date

import pytest
from docx import Document

from idara.services import programme_annuel as pa
from tests.test_personnel import base  # noqa: F401


def _cellules(f) -> str:
    return "\n".join(c.text for t in Document(f).tables for r in t.rows for c in r.cells)


def test_dates_des_journees():
    assert pa.date_journee("nettoyage", 2026) == (date(2026, 9, 19),) * 2       # السبت الثالث من شتنبر
    assert pa.date_journee("internet", 2026) == (date(2027, 2, 9),) * 2         # الثلاثاء الثاني من فبراير
    assert pa.date_journee("enseignant", 2026)[0] == date(2026, 10, 5)
    assert pa.date_journee("livre", 2026) == (date(2027, 4, 23), date(2027, 4, 26))
    assert pa.date_journee("sans_tabac", 2026)[0] == date(2027, 5, 31)


def test_proposition_par_defaut(base):  # noqa: F811
    p = pa.programme(base)
    assert not p["personnalise"] and [k for k, _, _ in pa.SECTIONS] == list(p["sections"])
    r = p["sections"]["rentree"]
    assert r[0]["debut"] == "2026-09-01" and r[1]["debut"] == "2026-09-02"   # المقرر الوزاري
    assert (r[3]["debut"], r[3]["fin"]) == ("2026-09-03", "2026-09-05")
    assert next(l for l in r if l["station"] == "الانطلاق الفعلي للدراسة")["debut"] == "2026-09-07"
    assert r[4]["debut"] == "" and r[4]["periode"] == ""                    # غير محدد في المقرر: فارغ
    assert all(not l["debut"] for l in p["sections"]["conseils"][:5])
    ev = p["sections"]["evaluation"]
    assert pa.periode(ev[0]) == "من 04 إلى 09 يناير 2027" and pa.periode(ev[2]).startswith("ابتداء من")
    assert pa.periode(next(l for l in ev if "المحلي لنيل" in l["operations"])) == "18 و19 يناير 2027"
    cl = p["sections"]["clubs"]
    ens = next(l for l in cl if "للمدرس" in l["operations"])
    assert pa.periode(ens) == "الإثنين 05 أكتوبر 2026" and pa.alerte(base, ens) == ""
    arbre = next(l for l in cl if "للشجرة" in l["operations"])
    assert "الفترة البينية الثالثة" in pa.alerte(base, arbre)              # 21 مارس 2027 في العطلة
    fetes = next(l for l in cl if "المسيرة" in l["operations"])
    assert pa.periode(fetes) == "الجمعة 06 نونبر 2026 والأربعاء 18 نونبر 2026"
    assert "نونبر 2026" in next(l for l in cl if "للتعاون المدرسي" in l["operations"])["periode"]
    pro = p["sections"]["prochaine"]
    assert [l["debut"] for l in pro if l["station"] == "توقيع محاضر الخروج"] == ["2027-07-10", "2027-07-31"]
    cg = pa.conges(base)
    assert cg[0]["titre"] == "الفترة البينية الأولى" and cg[0]["jours"] == "08"
    assert any(c["jours"] == "3 أو 4" and "تقريبي" in c["dates"] for c in cg)


def test_modification_et_document(base, dossier):  # noqa: F811
    i = pa.enregistrer_ligne(base, "conseils", "الاجتماع الأول لمجالس المؤسسة", "سطر وهمي", "2026-10-15")
    assert pa.programme(base)["personnalise"]
    assert pa.programme(base)["sections"]["conseils"][i]["operations"] == "سطر وهمي" and i == 2
    pa.enregistrer_ligne(base, "conseils", "الاجتماع الأول لمجالس المؤسسة", "سطر معدل", "", "", "خلال أكتوبر",
                         index=i)
    l = pa.programme(base)["sections"]["conseils"][i]
    assert l["operations"] == "سطر معدل" and pa.periode(l) == "خلال أكتوبر"
    with pytest.raises(pa.ErreurProgramme, match="إجباريتان"):
        pa.enregistrer_ligne(base, "clubs", "", "x")
    with pytest.raises(pa.ErreurProgramme, match="قبل"):
        pa.enregistrer_ligne(base, "clubs", "س", "x", "2026-10-10", "2026-10-01")
    with pytest.raises(pa.ErreurProgramme, match="العطل"):
        pa.enregistrer_ligne(base, "conges", "س", "x")
    n = len(pa.programme(base)["sections"]["clubs"])
    pa.supprimer_ligne(base, "clubs", 0)
    assert len(pa.programme(base)["sections"]["clubs"]) == n - 1
    assert pa.deplacer_ligne(base, "clubs", 0, 1) == 1
    pa.definir_validation(base, "2026-10-19")
    pa.reinitialiser(base, "clubs")
    assert len(pa.programme(base)["sections"]["clubs"]) == n and pa.programme(base)["validation"] == "2026-10-19"
    f = pa.generer(base, dossier)
    cel = _cellules(f)
    assert "برنامج العمل السنوي" in cel and "047.26" in cel and "عمليات الدخول المدرسي" in cel
    assert "لائحة العطل المدرسية" in cel and "الفترة البينية الأولى" in cel and "سطر معدل" in cel
    assert "19/10/2026" in "\n".join(p.text for p in Document(f).paragraphs)
    pa.reinitialiser(base)
    assert not pa.programme(base)["personnalise"]
    assert pa.lignes_sabboura(base)[0][2].startswith("الثلاثاء 01 شتنبر 2026")
