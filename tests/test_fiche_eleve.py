"""بطاقة التلميذ: تتبع المسار من الرائز القبلي إلى البعدي ثم المراحل (توجيهات المدير 2026-11-15). بيانات وهمية."""

import pytest
from docx import Document

from idara.services import fiche_eleve as fe
from idara.services import riyada as ry
from idara.services import tarl
from tests.fabrique_tarl import classeur_niveaux
from tests.test_eleves import AR, base, classeur  # noqa: F401


def _eleve(conn):
    return conn.execute("SELECT e.id, e.code_massar, c.code FROM eleve e JOIN inscription i ON i.eleve_id=e.id "
                        "JOIN classe c ON c.id=i.classe_id WHERE c.code NOT LIKE 'PS%' ORDER BY e.id").fetchone()


def _texte(chemin):
    d = Document(chemin)
    return d, "\n".join(p.text for p in d.paragraphs), [c.text for t in d.tables for r in t.rows for c in r.cells]


def test_parcours_et_carte(base, dossier, tmp_path):  # noqa: F811
    eid, code, cl = _eleve(base)
    with pytest.raises(fe.ErreurFiche, match="لا معطيات"):
        fe.generer(base, dossier, [eid])
    tarl.importer(base, [classeur_niveaux(tmp_path / "n.xlsx", {cl: [
        (code, "تلميذ وهمي", "حرف", "كلمة", "lettre", "lettre", "رقمان", "رقم واحد")]})])
    p = fe.parcours(base, eid)
    t = p["tarl"]
    assert (t["ar"]["pre"], t["ar"]["post"], t["ar"]["attendu"]) == ("حرف", "كلمة", "كلمة")
    assert t["ar"]["rang_post"] - t["ar"]["rang_pre"] == 1 and t["fr"]["rang_post"] == t["fr"]["rang_pre"]
    obs = fe.observations(p)
    assert "اللغة العربية: من «حرف» إلى «كلمة» (تقدم بـ1 درجة)." in obs
    assert "اللغة العربية: بلغ(ت) المستوى المتوقع «كلمة»." in obs
    assert any("الرياضيات: من «رقمان» إلى «رقم واحد» (تراجع" in o for o in obs)
    assert any(o.startswith("اللغة الفرنسية: دون المستوى المتوقع «Mot simple» بـ1") for o in obs)
    assert fe.a_besoin_soutien(p)
    # مستويات المراحل: إدخال يدوي
    with pytest.raises(fe.ErreurFiche, match="A أو B أو C"):
        fe.enregistrer_etape(base, eid, p["annee"], 1, "ar", "D")
    for ph, n in ((-1, "C"), (0, "B"), (1, "B"), (2, "A")):
        fe.enregistrer_etape(base, eid, p["annee"], ph, "ar", n)
    fe.enregistrer_etape(base, eid, p["annee"], 1, "ma", "c")
    fe.enregistrer_etape(base, eid, p["annee"], 1, "ma", "")   # فارغ: يُحذف
    p = fe.parcours(base, eid)
    assert p["etapes"] == {"ar": {-1: "C", 0: "B", 1: "B", 2: "A"}}
    assert "اللغة العربية: تحكم تام في المرحلة 2." in fe.observations(p)
    # الوثيقة: الجدولان والملاحظات، والمبيانان إن مُرِّرا
    png = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
           b"\x00\x00\x0cIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa7\x35\x81\x84\x00\x00\x00\x00IEND\xaeB`\x82")
    vus = []
    d, txt, cells = _texte(fe.generer(base, dossier, [eid], graphiques=lambda q: vus.append(q) or (png, png)))
    assert "بطاقة التلميذ(ة)" in txt and "يُقترح إدراجه(ا) في مجموعات الدعم." in txt and len(vus) == 1
    assert "الرائز القبلي" in cells and "المرحلة 2" in cells and "حرف" in cells and "+1" in cells
    assert len(d.inline_shapes) == 2 and not any("⁦" in c for c in cells) is False   # الأرقام معزولة الاتجاه
    # بطاقات قسم كامل: صفحة لكل تلميذ، والتلميذ دون معطيات لا يوقف الكل
    ids = [e["id"] for e in fe.eleves(base)]
    d, txt, _ = _texte(fe.generer(base, dossier, ids))
    assert txt.count("بطاقة التلميذ(ة)") == len(ids) and txt.count("لم تُستورد مستويات التعلم") == len(ids) - 1


def test_recherche_et_riyada_tarl(base, tmp_path):  # noqa: F811
    eid, code, cl = _eleve(base)
    assert fe.eleves(base, texte=code)[0]["id"] == eid and not fe.eleves(base, texte="لا_أحد")
    tarl.importer(base, [classeur_niveaux(tmp_path / "n.xlsx", {cl: [
        (code, "تلميذ وهمي", "حرف", "كلمة", "lettre", "Mot simple", "رقمان", "جمع")]})])
    # الرائزان في نسب «مؤسسات الريادة» من مستويات التعلم (الخانات الفارغة فقط)
    ry.enregistrer_isa(base, "2026/2027", cl, -1, {"ma": "12"})
    n = ry.remplir_depuis_tarl(base, "2026/2027")
    d = ry.isa(base, "2026/2027")[cl]
    assert n == 5 and d["ma"][-1] == 12.0 and d["ar"][-1] == 0.0 and d["ar"][0] == 100.0 and d["fr"][0] == 100.0
    assert ry.remplir_depuis_tarl(base, "2026/2027") == 0
