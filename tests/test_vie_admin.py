"""الوثائق القانونية للجمعيات، جدول الحراسة، النقل المدرسي، استعمالات الزمن (2026-11-13). بيانات وهمية."""

import pytest
from docx import Document

from idara.services import personnel as rh
from idara.services import sabboura as sb
from idara.services import vie_admin as va
from tests.test_eleves import AR, base, classeur  # noqa: F401


def _cellules(chemin):
    d = Document(chemin)
    return d, [c.text for t in d.tables for r in t.rows for c in r.cells], "\n".join(p.text for p in d.paragraphs)


def test_associations(base, dossier):  # noqa: F811
    d = va.lire_asso(base, "parents")
    assert [m[1] for m in d["membres"]][:2] == ["الرئيس", "نائب الرئيس"] and d["champs"]["siege"]
    with pytest.raises(va.ErreurVieAdmin, match="أعضاء المكتب"):
        va.generer_asso(base, dossier, "parents", "liste")
    d["membres"][0][0] = "رئيس تجريبي"
    d["membres"][4][0] = "أمين تجريبي"
    d["champs"].update({"date_ag": "2026-10-10", "presents": "40", "autorite": "قائد قيادة تجريبية"})
    va.enregistrer_asso(base, "parents", d)
    _, c, t = _cellules(va.generer_asso(base, dossier, "parents", "declaration"))
    assert "رئيس تجريبي" in c and "قائد قيادة تجريبية" in t and "تصريح بتجديد مكتب" in t and "التوقيع" not in c
    assert t.strip().endswith("رئيس تجريبي")            # الموقّع هو الرئيس لا المدير
    _, c, t = _cellules(va.generer_asso(base, dossier, "parents", "pv"))
    assert "بحضور 40 عضواً" in t and "تجديد مكتب الجمعية" in t and "التوقيع" in c
    va.generer_asso(base, dossier, "parents", "liste")
    with pytest.raises(va.ErreurVieAdmin, match="غير معروفة"):
        va.lire_asso(base, "x")
    # السبورة المرجعية تأخذ مكتب الجمعية الرياضية من هنا
    va.enregistrer_asso(base, "sportive", {"membres": [["رئيسة الرياضية", "الرئيس", "", "", ""]]})
    assert sb.lire(base, "sportive")["lignes"] == [["رئيسة الرياضية", "الرئيس"]]


def test_garde(base, dossier):  # noqa: F811
    g = va.lire_garde(base)
    assert len(g["periodes"]) == 6 and g["grille"]["الاثنين"] == [""] * 6
    with pytest.raises(va.ErreurVieAdmin, match="فارغ"):
        va.generer_garde(base, dossier)
    g["grille"]["الاثنين"][0] = "ذ. الأول، ذة. الثانية"
    g["grille"]["الثلاثاء"][1] = "ذ. الأول"
    g["consignes"] = "الحضور عشر دقائق قبل الدخول"
    va.enregistrer_garde(base, g)
    assert va.bilan_garde(base) == [("ذ. الأول", 2), ("ذة. الثانية", 1)]
    d, c, t = _cellules(va.generer_garde(base, dossier))
    assert "الدخول الصباحي" in c and "ذ. الأول، ذة. الثانية" in c and "السبت" not in c and "الحضور عشر دقائق" in t
    assert d.sections[0].page_width > d.sections[0].page_height


def test_transport(base, dossier):  # noqa: F811
    ls = va.eleves_transport(base)
    e1, e2 = ls[0]["eleve_id"], ls[1]["eleve_id"]
    with pytest.raises(va.ErreurVieAdmin, match="لا مستفيدين"):
        va.generer_transport(base, dossier)
    with pytest.raises(va.ErreurVieAdmin, match="مكرر"):
        va.enregistrer_transport(base, {"vehicules": [["1", "", "", "", ""], ["1", "", "", "", ""]]})
    with pytest.raises(va.ErreurVieAdmin, match="غير موجودة"):
        va.enregistrer_transport(base, {"vehicules": [["حافلة 1", "", "", "", ""]],
                                       "beneficiaires": {e1: {"vehicule": "حافلة 9"}}})
    va.enregistrer_transport(base, {"vehicules": [["حافلة 1", "سائق تجريبي", "0600000000", "المركز", "دوار أ"]],
                                   "beneficiaires": {e1: {"vehicule": "حافلة 1", "douar": "دوار أ"},
                                                     e2: {"vehicule": "حافلة 1", "douar": ""}}})
    st = va.stats_transport(base)
    assert st["total"] == 2 and st["vehicules"] == {"حافلة 1": 2} and st["douars"] == {"دوار أ": 1, "غير محدد": 1}
    _, c, t = _cellules(va.generer_transport(base, dossier))
    assert "عدد المستفيدين: 02" in t and "سائق تجريبي" in t and "دوار أ" in c and "توقيع المدير" not in t


def test_emploi_du_temps(base, dossier):  # noqa: F811
    pid = rh.enregistrer(base, rh.Personnel(nom_ar="التجريبي", prenom_ar="أستاذ", sexe="M", categorie="enseignant",
                                            ppr="900002"))
    for seances, msg in (([["الأحد", "08:00", "09:00", "الرياضيات", "", ""]], "يوم غير معروف"),
                         ([["الاثنين", "صباحاً", "09:00", "الرياضيات", "", ""]], "توقيت"),
                         ([["الاثنين", "10:00", "09:00", "الرياضيات", "", ""]], "قبل بدايتها"),
                         ([["الاثنين", "08:00", "09:00", "", "", ""]], "المادة"),
                         ([["الاثنين", "08:00", "09:00", "الرياضيات", "", ""],
                           ["الاثنين", "08:30", "09:30", "اللغة العربية", "", ""]], "متداخلتان")):
        with pytest.raises(va.ErreurVieAdmin, match=msg):
            va.enregistrer_emploi(base, pid, seances)
    va.enregistrer_emploi(base, pid, [["الثلاثاء", "14:00", "15:30", "الرياضيات", "3AP", "2"],
                                      ["الاثنين", "08:30", "09:30", "الرياضيات", "3AP", "2"],
                                      ["الاثنين", "9:30", "10:15", "اللغة العربية", "3AP", "2"]])
    assert [s[1] for s in va.lire_emploi(base, pid)] == ["08:30", "09:30", "14:00"]      # مرتبة، والتوقيت موحد
    c = va.controle_emploi(base, pid)
    assert c["total"] == 195 and c["heures"] == "3 س 15 د" and all(m["etat"] == "" for m in c["matieres"])
    with pytest.raises(va.ErreurVieAdmin, match="رقم"):
        va.enregistrer_quotas(base, {"الرياضيات": "خمس"})
    va.enregistrer_quotas(base, {"الرياضيات": "300", "اللغة العربية": 45, "النشاط العلمي": ""})
    etats = {m["matiere"]: m["etat"] for m in va.controle_emploi(base, pid)["matieres"]}
    assert etats == {"الرياضيات": "الحصيص غير مستكمل: ينقص 150 دقيقة", "اللغة العربية": "الحصيص مكتمل"}
    assert va.demi_journees(base, pid)["الاثنين"] == ["08:30–10:15", ""]
    assert va.demi_journees(base, pid)["الثلاثاء"] == ["", "14:00–15:30"]
    _, cel, t = _cellules(va.generer_emploi(base, dossier, pid))
    assert "08:30 – 09:30" in cel and "الحصيص مكتمل" in cel and "المجموع الأسبوعي: 3 س 15 د" in t
    ligne = next(l for l in sb.lire(base, "emploi")["lignes"] if l[1] == "900002")
    assert ligne[2:6] == ["08:30–10:15", "", "", "14:00–15:30"]
