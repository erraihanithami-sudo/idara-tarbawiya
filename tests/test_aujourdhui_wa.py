"""«ماذا أفعل اليوم؟» ورسائل واتساب (2026-11-13). بيانات وهمية."""

from datetime import date

import pytest

from idara.services import aujourdhui as auj
from idara.services import messages_wa as wa
from tests.test_eleves import AR, base, classeur  # noqa: F401


def test_taches_du_jour(base, dossier):  # noqa: F811
    t = auj.taches(base, dossier, date(2026, 11, 13))
    textes = [x["texte"] for x in t]
    assert any("نسب حضور أكتوبر 2026" in x for x in textes)
    assert any("أولياء الأمور" in x for x in textes)
    assert any("نسخة احتياطية" in x["texte"] for x in auj.taches(base, dossier, date(2027, 3, 1)))
    assert [x["urgence"] for x in t] == sorted((x["urgence"] for x in t), reverse=True)
    assert all("page" in x for x in t)
    from idara.services import absences as ab
    c = ab.lignes(base, "2026-10")[0]
    ab.enregistrer(base, "2026-10", [(c["classe_id"], 20, 95)])
    assert not any("نسب حضور" in x["texte"] for x in auj.taches(base, dossier, date(2026, 11, 13)))


def test_numero_et_lien():
    for brut in ("0612345678", "06 12 34 56 78", "+212612345678", "00212612345678", "612345678"):
        assert wa.numero_international(brut) == "212612345678"
    with pytest.raises(wa.ErreurMessage, match="غير صالح"):
        wa.numero_international("12345")
    m = wa.texte("absence", "سلمى التجريبية", "F", "3APG-1", "مدرسة تجريبية", "13/11/2026")
    assert "ابنتكم سلمى التجريبية (3APG-1) تغيبت" in m and "13/11/2026" in m
    m2 = wa.texte("document", "عمر التجريبي", "M", etablissement="مدرسة تجريبية")
    assert "ابنكم عمر التجريبي" in m2 and "()" not in m2
    u = wa.lien("0612345678", m)
    assert u.startswith("https://wa.me/212612345678?text=") and " " not in u
    with pytest.raises(wa.ErreurMessage, match="فارغ"):
        wa.lien("0612345678", " ")
    with pytest.raises(wa.ErreurMessage, match="غير معروف"):
        wa.texte("x", "أ")
