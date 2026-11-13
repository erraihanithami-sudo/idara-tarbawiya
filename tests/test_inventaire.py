"""سجل الجرد (طلب المدير 2026-11-13). بيانات وهمية."""

import pytest
from docx import Document

from idara.services import inventaire as inv


def _art(**k):
    d = dict(designation="مكتب خشبي", date_inscription="2025-10-01", quantite=2, type="أثاث مكتبي",
             facture_numero="F-12", facture_date="2025-09-28", fournisseur="مؤسسة تجريبية", prix_unitaire="1 250,5",
             affectation="الإدارة", entretien="صالح")
    d.update(k)
    return inv.Article(**d)


def test_enregistrement_et_numerotation(conn):
    a = inv.enregistrer(conn, _art())
    b = inv.enregistrer(conn, _art(designation="حاسوب محمول", type="معلوميات ووسائل رقمية", quantite=1,
                                   prix_unitaire="4000", entretien="يحتاج صيانة"))
    x = inv.lire(conn, a)
    assert x.numero == 1 and inv.lire(conn, b).numero == 2 and x.prix_unitaire == 1250.5 and x.total == 2501.0
    with pytest.raises(inv.ErreurInventaire, match="مستعمل"):
        inv.enregistrer(conn, _art(numero=2))
    for k, msg in ((dict(designation=" "), "وصف"), (dict(quantite=0), "واحد على الأقل"),
                   (dict(prix_unitaire="abc"), "رقم"), (dict(date_inscription="2099-01-01"), "المستقبل"),
                   (dict(date_inscription=""), "إجباري")):
        with pytest.raises(inv.ErreurInventaire, match=msg):
            inv.enregistrer(conn, _art(**k))
    # الفرز حسب النوع والبحث
    assert [a.type for a in inv.lister(conn)] == ["أثاث مكتبي", "معلوميات ووسائل رقمية"]
    assert [a.designation for a in inv.lister(conn, "معلوميات ووسائل رقمية")] == ["حاسوب محمول"]
    assert len(inv.lister(conn, texte="تجريبية")) == 2 and len(inv.lister(conn, texte="حاسوب")) == 1
    # المحو: يبقى السطر في السجل
    with pytest.raises(inv.ErreurInventaire, match="سبب"):
        inv.radier(conn, b, "2026-01-10", "")
    inv.radier(conn, b, "2026-01-10", "تلف لا يقبل الإصلاح", "ق-3")
    assert inv.lire(conn, b).radie and len(inv.lister(conn, radies=False)) == 1
    s = {x["type"]: x for x in inv.synthese(conn)}
    assert s["أثاث مكتبي"]["quantite"] == 2 and s["معلوميات ووسائل رقمية"]["radies"] == 1
    assert s["أثاث مكتبي"]["etats"]["صالح"] == 2 and s["أثاث مكتبي"]["valeur"] == 2501.0
    assert inv.pour_passation(conn) == [["مكتب خشبي", "02", "1", "02", "", "", "الإدارة"]]
    assert "أخرى" in inv.types_utilises(conn)
    inv.supprimer(conn, b)
    assert len(inv.lister(conn)) == 1


def test_registre_word(conn, dossier):
    with pytest.raises(inv.ErreurInventaire, match="لا تجهيزات"):
        inv.generer_registre(conn, dossier)
    inv.enregistrer(conn, _art())
    b = inv.enregistrer(conn, _art(designation="سبورة متحركة", type="تجهيزات الحجرات الدراسية", prix_unitaire=None))
    inv.radier(conn, b, "2026-01-10", "تلف")
    d = Document(inv.generer_registre(conn, dossier))
    cellules = [c.text for t in d.tables for r in t.rows for c in r.cells]
    for x in ("الرقم الترتيبي", "وصف التجهيزات", "رقم الفاتورة وتاريخها", "اسم التاجر", "الوحدة", "المجموع",
              "محو التجهيزات من السجل", "رقم القرار", "مكتب خشبي", "F-12 28/09/2025", "2 501.00", "تلف"):
        assert x in cellules, x
    assert d.sections[0].page_width > d.sections[0].page_height
    d = Document(inv.generer_registre(conn, dossier, "أثاث مكتبي"))
    cellules = [c.text for t in d.tables for r in t.rows for c in r.cells]
    assert "مكتب خشبي" in cellules and "سبورة متحركة" not in cellules
