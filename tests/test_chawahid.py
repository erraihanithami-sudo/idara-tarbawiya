"""الشواهد التقديرية المزخرفة (طلب المدير 2026-11-22): معطيات وهمية فقط."""

import pytest

from idara.services import chawahid as ch
from idara.services import registres as rg
from tests.test_eleves import base  # noqa: F401


def test_modeles_et_fonds():
    assert len(ch.MODELES) >= 7 and len({m.cle for m in ch.MODELES}) == len(ch.MODELES)
    for m in ch.MODELES:
        assert m.fond.exists() and m.fond.stat().st_size < 600_000
        assert {"entete", "corps", "date", "signature"} <= set(m.zones)
        assert bool(m.titre_fixe) != ("titre" in m.zones)   # عنوان مخطوط في الزخرفة أو عنوان يُكتب
        for x, y, w, h in m.zones.values():
            assert 0 <= x and 0 <= y and x + w <= 100.01 and y + h <= 100.01
    assert ch.MINISTERE.exists()


def test_accord_et_contenu(base):  # noqa: F811
    assert ch.accorder("لتفوق{ه} ومتمنين {له} التلميذ(ة)", True) == "لتفوقها ومتمنين لها التلميذة"
    assert ch.accorder("لتفوق{ه} ومتمنين {له} التلميذ(ة)", False) == "لتفوقه ومتمنين له التلميذ"
    el = {"nom": "تلميذة وهمية", "classe": "4APG-1", "sexe": "F"}
    c = ch.contenu(base, el, "شهادة تفوق", ch.MOTIFS[1], "الأسدوس الأول", "2026-12-05")
    assert c["titre"] == "شهادة تفوق" and c["nom"] == "تلميذة وهمية" and c["classe"] == "القسم: 4APG-1"
    assert c["motif"].startswith("تقديراً لحصولها على الرتبة الأولى في قسمها خلال الأسدوس الأول من الموسم الدراسي")
    assert c["intro"].endswith("إلى التلميذة:") and "شهادة التفوق" in c["intro"]
    assert c["voeu"] == "متمنين لها مزيداً من التألق والنجاح."
    assert c["jour"] == "5" and c["mois"] == "دجنبر" and c["annee"] == "2026" and "05/12/2026" in c["date"]
    assert c["entete"] and c["entete"][0].startswith("الأكاديمية الجهوية")
    with pytest.raises(ch.ErreurChahada, match="أكمل"):
        ch.contenu(base, el, "تهنئة", "تهنئةً على تتويجه في {المسابقة}")
    with pytest.raises(ch.ErreurChahada, match="اختر التلميذ"):
        ch.contenu(base, {"nom": " "}, "تهنئة", "سبب")
    with pytest.raises(ch.ErreurChahada, match="سبب"):
        ch.contenu(base, el, "تهنئة", "")
    assert ch.contenu(base, el, "تشجيع", "سبب", afficher_classe=False)["classe"] == ""


def test_eleves_enregistrement_et_pptx(base, dossier, tmp_path):  # noqa: F811
    tous = ch.eleves(base)
    assert tous and all({"id", "nom", "classe", "sexe"} <= set(e) for e in tous)
    cl = tous[0]["classe"]
    assert ch.classes(base) and all(e["classe"] == cl for e in ch.eleves(base, cl))
    cs = [ch.contenu(base, e, "شهادة تقديرية", ch.MOTIFS[0], "الأسدوس الثاني",
                     signataires=("مدير المؤسسة", "رئيس جمعية الآباء")) for e in tous[:2]]
    ids = ch.enregistrer(base, cs, "almasi")
    ls = rg.lister(base, "tahfiz")
    assert len(ids) == 2 and {l["eleve"] for l in ls} == {e["nom"] for e in tous[:2]}
    assert all(l["modele"] == "الماسي بالوسام" and l["periode"] == "الأسدوس الثاني" for l in ls)
    from pptx import Presentation
    for m in ch.MODELES:
        p = ch.generer_pptx(cs, m.cle, tmp_path / f"{m.cle}.pptx")
        prs = Presentation(str(p))
        assert len(prs.slides) == 2
        textes = " ".join(sh.text_frame.text for sh in prs.slides[1].shapes if sh.has_text_frame)
        assert tous[1]["nom"] in textes and "رئيس جمعية الآباء" in textes
    ex = ch.exemple(base)
    assert ex["nom"] == "اسم التلميذة أو التلميذ"
    c1 = ch.chemin_sortie(dossier, "شهادة تقديرية - أ/ب", "pdf")
    assert c1.parent.name == "الشواهد التقديرية" and "/" not in c1.name
