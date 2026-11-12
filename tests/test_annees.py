"""السنوات الدراسية: فتح سنة جديدة مع الأرشفة، والاطلاع على السنوات الماضية (طلب المدير 2026-11-12)."""

import pytest

from idara.services import annee as an
from idara.services import sauvegarde
from tests.test_eleves import base  # noqa: F401  (fixture)


def test_ouvrir_consulter_revenir(base, dossier):  # noqa: F811
    assert an.suivante("2026/2027") == "2027/2028"
    avant = an.lister(base)
    assert avant[0]["libelle"] == "2026/2027" and avant[0]["courante"] and avant[0]["eleves"] >= 1
    assert not an.en_consultation(base)
    # سنة سابقة للأعمال التجريبية
    arch = an.ouvrir_annee(base, dossier, "2025/2026")
    assert arch.exists() and arch in sauvegarde.lister_sauvegardes(dossier)
    assert an.annee_courante(base)["libelle"] == "2025/2026" and an.en_consultation(base)
    with pytest.raises(an.ErreurAnnee, match="موجودة"):
        an.ouvrir_annee(base, dossier, "2025/2026")
    with pytest.raises(an.ErreurAnnee):
        an.ouvrir_annee(base, dossier, "2025-2026")
    an.consulter(base, "2026/2027")
    assert not an.en_consultation(base)
    # سنة جديدة: تصبح هي الأحدث والمفتوحة، ومعطيات السنة الماضية تبقى
    an.ouvrir_annee(base, dossier, an.suivante("2026/2027"))
    l = {x["libelle"]: x for x in an.lister(base)}
    assert l["2027/2028"]["courante"] and l["2027/2028"]["eleves"] == 0 and l["2026/2027"]["eleves"] >= 1
    assert an.la_plus_recente(base) == "2027/2028" and not an.en_consultation(base)
    with pytest.raises(an.ErreurAnnee, match="غير موجودة"):
        an.consulter(base, "2030/2031")
