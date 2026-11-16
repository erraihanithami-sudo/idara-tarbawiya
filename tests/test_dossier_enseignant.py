"""طلب ملف أستاذ وإرساله (توجيه المدير 2026-11-15). أسماء وهمية."""

import pytest
from docx import Document

from idara.services import conges as cg
from idara.services import dossier_enseignant as de
from tests.test_eleves import AR, base, classeur  # noqa: F401


def _texte(chemin):
    d = Document(chemin)
    return "\n".join(p.text for p in d.paragraphs), [c.text for t in d.tables for r in t.rows for c in r.cells]


def test_demande_et_envoi(base, dossier):  # noqa: F811
    with pytest.raises(de.ErreurDossierProf, match="المؤسسة المرسل إليها"):
        de.generer(base, dossier, "demande", " ", [("أ", "", "")])
    with pytest.raises(de.ErreurDossierProf, match="أستاذاً واحداً"):
        de.generer(base, dossier, "demande", "مدرسة وهمية", [(" ", "1", "")])
    n0 = cg.prochain_numero(base)
    p, num = de.generer(base, dossier, "demande", "مدرسة وهمية", [("أستاذة تجريبية", "1234567", "التحاق بالحركة")],
                        le="2026-11-16", sous_couvert="بإقليم وهمي")
    t, c = _texte(p)
    assert "الموضوع: طلب ملف إداري وتربوي." in t and "إلى السيد(ة) مدير(ة) مدرسة وهمية" in t
    assert "تحت إشراف السيد المدير الإقليمي بإقليم وهمي" in t and "للأستاذ(ة) المذكور(ة)" in t
    assert "الاسم والنسب" in c and "أستاذة تجريبية" in c and "⁦1234567⁩" in c and "التحاق بالحركة" in c
    assert num in t and "وتقبلوا أزكى التحيات." in t
    assert cg.prochain_numero(base) == n0 + 1
    p, _ = de.generer(base, dossier, "envoi", "مدرسة أخرى", [("أستاذ أ", "1", ""), ("أستاذ ب", "2", "")],
                      reference="مراسلتكم رقم 12 بتاريخ 01/11/2026")
    t, c = _texte(p)
    assert "الموضوع: إرسال ملف إداري وتربوي." in t and "بناء على مراسلتكم المشار إليها" in t
    assert "للأطر المذكورين" in t and "تحت إشراف" not in t and c.count("02") == 1
    p, _ = de.generer(base, dossier, "demande", "مدرسة وهمية", [("أستاذة تجريبية", "", "")], rappel=True)
    assert "تذكير بطلب ملف إداري وتربوي" in _texte(p)[0]
