"""محاضر نهاية الأسدوس (ملف المدير «محاضر نهاية الأسدوس (إبتدائي)»). بيانات وهمية."""

import os
from pathlib import Path

import docx
import pytest
from docx.oxml.ns import qn

from idara.services import deliberations as dl
from idara.services import evaluation as ev
from tests.fabrique_resultats import classeur_resultats
from tests.test_eleves import base  # noqa: F401

N = lambda x: [x] * 8  # noqa: E731


def _texte(p: Path) -> str:
    return "".join(x.text or "" for x in docx.Document(str(p)).element.body.iter(qn("w:t")))


def test_mentions():
    assert [dl.mention(x) for x in (9.99, 10, 8, 7.99, 7, 6.99, 6, 5.99, None)] == \
        ["تنويه", "تنويه", "تنويه", "تشجيع", "تشجيع", "لوحة الشرف", "لوحة الشرف", "", ""]


def test_sixieme_moyenne_annuelle_du_fichier_du_directeur(tmp_path, base, dossier):  # noqa: F811
    """50% متوسط المراقبة المستمرة + 25% المحلي + 25% الإقليمي (سطر من ملف المدير: 7.78)."""
    classes = {"6APG-1": [("X000000005", "الاختبار آدم", N(7.0)), ("X000000006", "التجريبية سلمى", N(4.0)),
                          ("X000000007", "النموذج يوسف", N(6.0))]}
    f = classeur_resultats(tmp_path / "s.xlsx", classes, niveau="السادس ابتدائي عام",
                           semestres={"X000000005": (8.41, 7.95), "X000000006": (4.1, 4.3), "X000000007": (6.5, 6.7)},
                           examens={"X000000005": (8.72, 6.05), "X000000006": (3.9, 4.2), "X000000007": (6.0, 6.2)})
    ev.importer(base, [f])
    ls = {l["code"]: l for l in dl.lignes(base, "2026/2027", "S2", classe="6APG-1")}
    assert ls["X000000005"]["note"] == 7.78 and ls["X000000005"]["local"] == 8.72
    assert ls["X000000005"]["mention"] == "تشجيع" and ls["X000000005"]["rang"] == 1
    assert ls["X000000006"]["decision"] == "يكرر" and ls["X000000005"]["decision"] == "ينتقل"
    dl.enregistrer_deliberation(base, "2026/2027", "S2", "X000000006", "إنذار", "التعليم الإعدادي")
    with pytest.raises(ev.ErreurEvaluation, match="إنذار أو توبيخ"):
        dl.enregistrer_deliberation(base, "2026/2027", "S2", "X000000006", "طرد")
    st = dl.statistiques(dl.lignes(base, "2026/2027", "S2", classe="6APG-1"))
    assert st["max"] == 7.78 and st["tous"]["nombre"] == 3 and st["tous"]["admis"] == 2
    assert st["mentions"]["إنذار"] == 1 and st["taux_reussite"] == "66.66%"
    p = dl.generer_classe(base, dossier, "2026/2027", "6APG-1", "S2")
    t = _texte(p)
    for attendu in ("قرار مجلس القسم للأسدوس الثاني", "محضر مجلس القسم للأسدوس الثاني", "الامتحان الإقليمي",
                    "7.78", "ينتقل", "يكرر", "إنذار", "التعليم الإعدادي", "نسبة النجاح: \u206666.66%\u2069",
                    "توقيعات السادة الأساتذة", "الاستحقاق", "غير مسجلين في لوائح التلاميذ"):
        assert attendu in t, attendu
    p2 = dl.generer_niveau(base, dossier, "2026/2027", "6AP", "S2")
    assert "محضر نتائج المستوى للأسدوس الثاني" in _texte(p2) and "6APG-1" in _texte(p2)
    if os.environ.get("DELIB_SORTIE"):
        Path(os.environ["DELIB_SORTIE"]).write_bytes(p.read_bytes())


def test_premier_semestre_et_rang_partage(tmp_path, base, dossier):  # noqa: F811
    classes = {"4APG-1": [("X000000001", "التجريبي سعيد", N(8.0)), ("X000000002", "الوهمي سلمى", N(4.5)),
                          ("X000000003", "المثال يوسف", N(6.0))]}
    ev.importer(base, [classeur_resultats(tmp_path / "r.xlsx", classes,
                                          semestres={"X000000001": (8.5, ""), "X000000002": (4.5, ""),
                                                     "X000000003": (8.5, "")})])
    ls = dl.lignes(base, "2026/2027", "S1", classe="4APG-1")
    assert sorted(l["rang"] for l in ls) == [1, 1, 3] and all(l["decision"] == "" for l in ls)
    st = dl.statistiques(ls)
    assert st["moyenne"] == 7.17 and st["au_dessus"] == 2 and st["mentions"]["تنويه"] == 2
    t = _texte(dl.generer_classe(base, dossier, "2026/2027", "4APG-1", "S1"))
    assert "قرار مجلس القسم للأسدوس الأول" in t and "القرار" not in t.split("محضر")[0]
    with pytest.raises(ev.ErreurEvaluation, match="لا نتائج"):
        dl.generer_classe(base, dossier, "2026/2027", "5APG-9", "S1")
