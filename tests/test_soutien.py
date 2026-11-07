"""الدعم التربوي (بيانات وهمية)."""

import pytest
from docx import Document

from idara.services import soutien as sv
from tests.test_eleves import base  # noqa: F401


def _prof(conn, prenom="سعاد", ppr="7654321"):
    with conn:
        return conn.execute("INSERT INTO personnel(nom_ar, prenom_ar, sexe, categorie, ppr) VALUES "
                            "('التجريبية', ?, 'F', 'enseignant', ?)", (prenom, ppr)).lastrowid


def _textes(f):
    d = Document(f)
    return "\n".join([p.text for p in d.paragraphs] + [c.text for t in d.tables for r in t.rows for c in r.cells])


def test_parcours_complet(base, dossier):  # noqa: F811
    cats = sv.categories(base)
    assert [c["nom"] for c in cats] == sv.CATEGORIES_DEFAUT
    cid = sv.ajouter_categorie(base, "  صعوبات   في التركيز ")
    with pytest.raises(sv.ErreurSoutien, match="موجودة"):
        sv.ajouter_categorie(base, "صعوبات في التركيز")
    eid = sv.enregistrer_etape(base, "الدعم المرحلي الأول", "2026-11-09", "2026-11-28")
    with pytest.raises(sv.ErreurSoutien, match="قبل"):
        sv.enregistrer_etape(base, "خطأ", "2026-12-10", "2026-12-01")
    p = _prof(base)
    assert any(i["id"] == p for i in sv.intervenants(base))
    gid = sv.creer_groupe(base, eid, cats[0]["id"], p, "العربية")
    g = sv.groupe(base, gid)
    assert g["nom"] == "تعثر في القراءة - المجموعة 1" and g["effectif"] == 0
    classe = base.execute("SELECT classe_id FROM inscription GROUP BY classe_id ORDER BY COUNT(*) DESC").fetchone()[0]
    els = sv.eleves_classe(base, classe)
    assert len(els) >= 3
    ids = [e["inscription_id"] for e in els[:3]]
    assert sv.affecter(base, gid, ids) == len(ids)
    assert sv.affecter(base, gid, ids[:1]) == 0          # لا تكرار
    ms = sv.membres(base, gid)
    assert len(ms) == len(ids) and all(m["evolution"] == "—" for m in ms)
    notes = [(ids[0], 3, 6.5, "تحسن واضح"), (ids[1], "4", "4", ""), (ids[2], 7, 5, "")]
    sv.noter(base, gid, notes)
    ms = {m["inscription_id"]: m for m in sv.membres(base, gid)}
    assert ms[ids[0]]["evolution"] == "تحسن" and ms[ids[0]]["observation"] == "تحسن واضح"
    with pytest.raises(sv.ErreurSoutien, match="بين 0 و10"):
        sv.noter(base, gid, [(ids[0], 12, 3, "")])
    # استعمال الزمن مع منع التداخل لنفس الأستاذ
    sv.ajouter_seance(base, gid, 2, "14:30", "15:30", "القاعة 3")
    g2 = sv.creer_groupe(base, eid, cid, p)
    with pytest.raises(sv.ErreurSoutien, match="تتداخل"):
        sv.ajouter_seance(base, g2, 2, "15:00", "16:00")
    sv.ajouter_seance(base, g2, 2, "15:30", "16:30")
    with pytest.raises(sv.ErreurSoutien, match="14:30"):
        sv.ajouter_seance(base, g2, 3, "9h", "10h")
    assert [s["debut"] for s in sv.emploi_du_temps(base, eid)] == ["14:30", "15:30"]
    with pytest.raises(sv.ErreurSoutien, match="مرتبطة"):
        sv.supprimer_categorie(base, cid)
    # الحصيلة
    b = sv.bilan_etape(base, eid)
    assert b["beneficiaires"] == len(ids) and b["intervenants"] == 1 and len(b["groupes"]) == 2
    assert b["global"]["moy_avant"] == round((3 + 4 + 7) / 3, 2)
    assert b["global"]["maitrise_avant"] == round(100 / 3, 1) and b["global"]["maitrise_apres"] == round(200 / 3, 1)
    assert b["global"]["ameliores"] == 1
    # الوثائق
    t = _textes(sv.generer_registre(base, dossier, eid, p))
    assert "سجل الدعم التربوي: الدعم المرحلي الأول" in t and ms[ids[0]]["nom"] in t and "الأربعاء 14:30-15:30" in t
    t = _textes(sv.generer_programme(base, dossier, eid))
    assert "استعمال زمن الدعم" in t and "القاعة 3" in t and "سعاد التجريبية" in t
    t = _textes(sv.generer_rapport(base, dossier, eid, None))
    assert "تتبع التلاميذ: النتائج قبل الدعم وبعده" in t and "تحسن" in t and "تعثر في القراءة" in t
    # حذف المجموعة يحذف تلاميذها وحصصها
    sv.supprimer_groupe(base, gid)
    assert not base.execute("SELECT 1 FROM soutien_eleve WHERE groupe_id=?", (gid,)).fetchone()
    with pytest.raises(sv.ErreurSoutien, match="لا مجموعات"):
        sv.generer_registre(base, dossier, sv.enregistrer_etape(base, "مرحلة فارغة"), p)
