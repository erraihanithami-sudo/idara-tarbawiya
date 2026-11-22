"""صور التقارير (طلب المدير 2026-11-22): الأنشطة والأيام التواصلية والأبواب المفتوحة (صور وهمية مولّدة)."""

import pytest
from docx import Document
from PIL import Image

from idara.services import photos as ph
from idara.services import pionniere as pn
from idara.services import vie_scolaire as vs
from tests.test_eleves import base  # noqa: F401


def _img(tmp_path, nom="a.jpg", taille=(2400, 1200), coul="teal"):
    p = tmp_path / nom
    Image.new("RGB", taille, coul).save(p)
    return p


def test_ajout_reduction_et_suppression(base, dossier, tmp_path):  # noqa: F811
    with pytest.raises(ph.ErreurPhoto, match="احفظ"):
        ph.ajouter(base, dossier, "activite", None, _img(tmp_path))
    with pytest.raises(ph.ErreurPhoto, match="ليس صورة"):
        ph.ajouter(base, dossier, "activite", 1, tmp_path / "x.txt")
    pid = ph.ajouter(base, dossier, "activite", 7, _img(tmp_path), "  افتتاح   النشاط ")
    p = ph.lister(base, "activite", 7)[0]
    assert p["legende"] == "افتتاح النشاط" and p["chemin"].startswith("pieces/photos/activite/7_")
    with Image.open(ph.chemin(dossier, p)) as im:
        assert max(im.size) == ph.MAX_PX   # مصغّرة
    png = tmp_path / "t.png"
    Image.new("RGBA", (50, 50), (255, 0, 0, 0)).save(png)
    n, err = ph.ajouter_plusieurs(base, dossier, "activite", 7, [png, tmp_path / "absente.jpg"])
    assert n == 1 and len(err) == 1 and ph.nombre(base, "activite", 7) == 2
    ph.definir_legende(base, pid, "توزيع الجوائز")
    assert ph.lister(base, "activite", 7)[0]["legende"] == "توزيع الجوائز"
    f = ph.chemin(dossier, p)
    ph.supprimer(base, dossier, pid)
    assert not f.exists() and ph.nombre(base, "activite", 7) == 1
    ph.supprimer_tout(base, dossier, "activite", 7)
    assert ph.nombre(base, "activite", 7) == 0


def test_rapport_activite_avec_photos(base, dossier, tmp_path):  # noqa: F811
    aid = vs.enregistrer_activite(base, vs.Activite("نشاط موازٍ", "مسابقة القراءة", periode="دجنبر", date_debut="2026-12-02", statut="realisee",
                                                    nb_garcons=10, nb_filles=12, bilan="تتويج الفائزين\nتوزيع الشواهد"))
    ph.ajouter(base, dossier, "activite", aid, _img(tmp_path), "لحظة التتويج")
    ph.ajouter(base, dossier, "activite", aid, _img(tmp_path, "b.jpg", coul="orange"))
    d = Document(vs.generer_rapport_activite(base, dossier, aid))
    t = "\n".join(p.text for p in d.paragraphs) + "\n".join(c.text for t in d.tables for r in t.rows for c in r.cells)
    assert "تقرير حول نشاط: مسابقة القراءة" in t and "صور من النشاط" in t and "لحظة التتويج" in t
    assert "22 (ذكور 10، إناث 12)" in t and "• تتويج الفائزين" in t
    assert len(d.inline_shapes) == 2
    vs.supprimer_activite(base, aid, dossier)
    assert ph.nombre(base, "activite", aid) == 0


def test_rapport_rencontre_avec_photos(base, dossier, tmp_path):  # noqa: F811
    rid = pn.enregistrer_rencontre(base, pn.Rencontre("portes", "2026-12-05", "الأبواب المفتوحة"))
    ph.ajouter(base, dossier, "rencontre", rid, _img(tmp_path))
    d = Document(pn.generer_rapport_rencontre(base, dossier, rid))
    assert len(d.inline_shapes) == 1
    assert any("صور من الأبواب المفتوحة" in p.text for p in d.paragraphs)
