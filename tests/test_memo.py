"""مفكرة المدير: بطاقات التذكير وأحداث اليومية. بيانات وهمية."""

from datetime import date, timedelta

import pytest

from idara.services import calendrier as cal
from idara.services import memo
from tests.test_eleves import base  # noqa: F401  (fixture)


def test_memos_et_evenements(base):  # noqa: F811
    with pytest.raises(memo.ErreurMemo, match="موضوع"):
        memo.enregistrer(base, memo.Memo("  ", "2026-11-20"))
    with pytest.raises(memo.ErreurMemo, match="الساعة"):
        memo.enregistrer(base, memo.Memo("اجتماع", "2026-11-20", "25:00"))
    j = date.today()
    mid = memo.enregistrer(base, memo.Memo("زيارة المفتش التربوي", j.isoformat(), "9.30", couleur="rose"))
    memo.enregistrer(base, memo.Memo("تسليم الإحصاء", (j + timedelta(days=1)).isoformat()))
    assert memo.lire(base, mid).heure == "09:30" and [m.sujet for m in memo.lister(base)][0] == "زيارة المفتش التربوي"
    assert memo.echeance(memo.lire(base, mid)) == "اليوم"
    cal.enregistrer_locale(base, "يوم تواصلي", (j + timedelta(days=2)).isoformat())
    ev = memo.evenements(base, j, j + timedelta(days=3))
    assert ev[j.isoformat()][0] == ("memo", "تذكير 09:30: زيارة المفتش التربوي")
    assert any(t == "local" and "يوم تواصلي" in x for t, x in ev[(j + timedelta(days=2)).isoformat()])
    memo.marquer_fait(base, mid)
    assert len(memo.lister(base)) == 1 and len(memo.lister(base, inclure_faits=True)) == 2
    memo.supprimer(base, mid)
    with pytest.raises(memo.ErreurMemo):
        memo.lire(base, mid)
