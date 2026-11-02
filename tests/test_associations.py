"""التدبير المالي لجمعية دعم مدرسة النجاح (نموذج المدير). مبالغ وهمية."""

import openpyxl
import pytest

from idara.services import associations as asso


@pytest.fixture
def ex(conn):
    return asso.ouvrir_exercice(conn, "najah", "2025/2026", "2025-09-01", "2026-08-31",
                                report_banque=50000, report_caisse=300, reference="محضر تسليم المهام")


def _rub(conn, ligne, sens=None):
    sql = "SELECT id FROM rubrique WHERE ligne LIKE ?" + (" AND sens=?" if sens else "")
    return conn.execute(sql, (f"%{ligne}%", sens) if sens else (f"%{ligne}%",)).fetchone()[0]


def test_nomenclature_du_modele(conn):
    rs = asso.rubriques(conn)
    assert len(rs) == 55 and sum(r["sens"] == "recette" for r in rs) == 9
    eq = [r for r in rs if r["chapitre"] == "ر- التجهيزات"]
    assert len(eq) == 10 and "20000" in eq[0]["observation"]
    assert asso.association(conn)["nom"] == "جمعية دعم مدرسة النجاح"


def test_ouverture_report_et_soldes(conn, ex):
    assert asso.soldes(conn, ex) == {"banque": 50000.0, "caisse": 300.0}
    ops = asso.operations(conn, ex)
    assert [o["ligne"] for o in ops] == [asso.REPORT, asso.REPORT]
    with pytest.raises(asso.ErreurAssociation, match="تتداخل"):
        asso.ouvrir_exercice(conn, "najah", "x", "2026-01-01", "2026-12-31")


def test_operations_transfert_et_registres(conn, ex):
    asso.enregistrer(conn, asso.Operation(ex, "2025-10-01", "recette", "banque", "10 000", _rub(conn, "منحة المديرية")))
    asso.enregistrer(conn, asso.Operation(ex, "2025-10-24", "transfert", "banque", 3000, reference="شيك رقم 04/24"))
    asso.enregistrer(conn, asso.Operation(ex, "2025-11-05", "depense", "caisse", "180,5",
                                          _rub(conn, "صيانة وإصلاح تجهيزات المؤسسة"), "سند الصندوق 01/2025",
                                          "إصلاح باب"))
    assert asso.soldes(conn, ex) == {"banque": 57000.0, "caisse": 3119.5}
    rb = asso.registre(conn, ex, "banque")
    assert [r["solde"] for r in rb] == [50000.0, 60000.0, 57000.0]
    assert rb[2]["libelle"] == "تمويل الصندوق" and rb[2]["sortie"] == 3000
    rc = asso.registre(conn, ex, "caisse")
    assert [(r["entree"], r["sortie"], r["solde"]) for r in rc] == [(300, 0, 300), (3000, 0, 3300), (0, 180.5, 3119.5)]
    t = asso.totaux(conn, ex)
    assert t["recettes"] == 60300 and t["depenses"] == 180.5 and t["solde"] == 60119.5


@pytest.mark.parametrize("modif, message", [
    (dict(montant="0"), "أكبر من صفر"), (dict(montant="abc"), "غير صحيح"), (dict(date_op="2027-01-01"), "خارج"),
    (dict(reference=""), "مرجع"), (dict(montant=999999), "لا يكفي"), (dict(rubrique_id=None), "اختر البند"),
    (dict(nature="recette"), "لا يناسب"),
])
def test_refus(conn, ex, modif, message):
    d = dict(exercice_id=ex, date_op="2025-11-01", nature="depense", registre="caisse", montant=100,
             rubrique_id=_rub(conn, "مصاريف البريد والبنك"), reference="فاتورة 1")
    d.update(modif)
    with pytest.raises(asso.ErreurAssociation, match=message):
        asso.enregistrer(conn, asso.Operation(**d))


def test_solde_negatif_dans_le_passe_refuse(conn, ex):
    """مصروف مؤرخ قبل مدخول يغطيه: مرفوض حتى لو كان الرصيد النهائي كافياً."""
    asso.enregistrer(conn, asso.Operation(ex, "2025-12-01", "recette", "caisse", 1000, _rub(conn, "هبات", "recette")))
    with pytest.raises(asso.ErreurAssociation, match="سالباً بتاريخ 2025-11-01"):
        asso.enregistrer(conn, asso.Operation(ex, "2025-11-01", "depense", "caisse", 500,
                                              _rub(conn, "مصاريف البريد والبنك"), "فاتورة"))
    dep = asso.enregistrer(conn, asso.Operation(ex, "2025-12-02", "depense", "caisse", 1200,
                                                _rub(conn, "مصاريف البريد والبنك"), "فاتورة"))
    don = conn.execute("SELECT id FROM operation_financiere WHERE date_op='2025-12-01'").fetchone()[0]
    with pytest.raises(asso.ErreurAssociation, match="احذف المصاريف"):
        asso.supprimer(conn, don)
    asso.supprimer(conn, dep)
    asso.supprimer(conn, don)
    assert asso.soldes(conn, ex)["caisse"] == 300


def test_budget_execution_et_depassement(conn, ex):
    r = _rub(conn, "معدات وعتاد مكتبي")
    asso.definir_prevision(conn, ex, r, "40000")
    asso.enregistrer(conn, asso.Operation(ex, "2025-12-09", "depense", "banque", 45400, r, "سند الطلب 01/2025"))
    l = next(x for x in asso.execution(conn, ex) if x["id"] == r)
    assert (l["prevu"], l["realise"], l["reste"], l["taux"]) == (40000, 45400, -5400, "114%")
    assert "يتجاوز المتوقع" in asso.depassements(conn, ex)[0]
    with pytest.raises(asso.ErreurAssociation):
        asso.definir_prevision(conn, ex, r, "-5")


def test_nouvel_exercice_reprend_les_soldes(conn, ex):
    asso.enregistrer(conn, asso.Operation(ex, "2025-10-24", "transfert", "banque", 3000, reference="شيك"))
    e2 = asso.ouvrir_exercice(conn, "najah", "2026/2027", "2026-09-01", "2027-08-31")
    assert asso.soldes(conn, e2) == {"banque": 47000.0, "caisse": 3300.0}
    assert all(o["ligne"] == asso.REPORT for o in asso.operations(conn, e2))


def test_association_et_export(conn, ex, tmp_path):
    asso.modifier_association(conn, "najah", "0123 4567", "الرئيس", "أمين المال", "2024-10-01")
    assert asso.association(conn)["rib"] == "01234567"
    with pytest.raises(asso.ErreurAssociation, match="أرقام"):
        asso.modifier_association(conn, "najah", "12A")
    asso.enregistrer(conn, asso.Operation(ex, "2025-10-24", "transfert", "banque", 3000, reference="شيك"))
    f = asso.exporter_excel(conn, ex, tmp_path / "j.xlsx")
    wb = openpyxl.load_workbook(f)
    assert wb.sheetnames == ["اليومية", "سجل البنك", "سجل الصندوق", "تنفيذ الميزانية", "الحصيلة"]
    assert wb["سجل الصندوق"].cell(5, 8).value == 3300 and wb["اليومية"].sheet_view.rightToLeft
