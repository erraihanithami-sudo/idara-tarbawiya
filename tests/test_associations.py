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


def test_nomenclature_du_guide(conn):
    """الملحق 1 من الدليل المسطري (يوليوز 2023)، والبنود الزائدة من نموذج Access غير نشطة."""
    rs = asso.rubriques(conn, actifs=True)
    assert len(rs) == 52 and sum(r["sens"] == "recette" for r in rs) == 10
    chapitres = list(dict.fromkeys(r["chapitre"] for r in rs if r["sens"] == "depense"))
    assert chapitres == ["الأندية التربوية", "التظاهرات المدرسية", "الدعم التربوي", "دعم الصحة المدرسية",
                         "الدعم النفسي", "التوجيه المدرسي والمهني", "التدبير والشراكة",
                         "نفقات تشجيع التميز والإبداع والابتكار", "التجهيزات",
                         "صيانة وإصلاح تجهيزات وبنيات المؤسسة وتأهيلها", "نفقات استثنائية"]
    eq = [r for r in rs if r["chapitre"] == "التجهيزات"]
    assert len(eq) == 8 and "20000" in eq[0]["observation"] and eq[-1]["ligne"] == "كراء المعدات والتجهيزات"
    assert "مداخيل أخرى" in [r["ligne"] for r in rs]
    assert len(asso.rubriques(conn)) == 56
    assert asso.association(conn)["nom"] == "جمعية دعم مدرسة النجاح"


def test_bande_inactive_refusee(conn, ex):
    r = conn.execute("SELECT id FROM rubrique WHERE ligne='معدات تكييف الهواء'").fetchone()[0]
    with pytest.raises(asso.ErreurAssociation, match="لم يعد وارداً"):
        asso.enregistrer(conn, asso.Operation(ex, "2025-11-01", "depense", "banque", 10, r, "فاتورة"))
    assert r not in [x["id"] for x in asso.execution(conn, ex)]


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
    al = asso.depassements(conn, ex)
    assert any("يتجاوز المتوقع" in a for a in al)
    assert sum("السقف السنوي" in a for a in al) == 2  # المنجز والمتوقع فوق 20000 درهم للتجهيزات
    with pytest.raises(asso.ErreurAssociation):
        asso.definir_prevision(conn, ex, r, "-5")


def test_nouvel_exercice_reprend_les_soldes(conn, ex):
    asso.enregistrer(conn, asso.Operation(ex, "2025-10-24", "transfert", "banque", 3000, reference="شيك"))
    e2 = asso.ouvrir_exercice(conn, "najah", "2026/2027", "2026-09-01", "2027-08-31")
    assert asso.soldes(conn, e2) == {"banque": 47000.0, "caisse": 3300.0}
    assert all(o["ligne"] == asso.REPORT for o in asso.operations(conn, e2))


def test_report_dans_le_solde_et_mis_a_jour(conn, ex):
    """ملاحظة المدير (2026-11-03): المنقول يدخل في رصيد البنك، ويُحيَّن إذا عُدلت السنة السابقة."""
    t = asso.totaux(conn, ex)
    assert (t["banque"], t["caisse"]) == (50000, 300)
    e2 = asso.ouvrir_exercice(conn, "najah", "2026/2027", "2026-09-01", "2027-08-31")
    assert asso.report(conn, e2) == {"banque": 50000, "caisse": 300}
    # عملية متأخرة في السنة السابقة: يُحيَّن منقول الموالية
    r = _rub(conn, "معدات وعتاد مكتبي")
    oid = asso.enregistrer(conn, asso.Operation(ex, "2026-03-02", "depense", "banque", 1200, r, "فاتورة 7"))
    assert asso.report(conn, e2)["banque"] == 48800 and asso.totaux(conn, e2)["banque"] == 48800
    asso.supprimer(conn, oid)
    assert asso.report(conn, e2)["banque"] == 50000
    # المنقول لا يُدخل ولا يُحذف كعملية عادية، ولا يُعدل يدوياً إلا في أول سنة
    rid = _rub(conn, asso.REPORT)
    with pytest.raises(asso.ErreurAssociation, match="تعديل المنقول"):
        asso.enregistrer(conn, asso.Operation(e2, "2026-09-02", "recette", "banque", 10, rid))
    op = next(o for o in asso.operations(conn, e2) if o["registre"] == "banque")
    with pytest.raises(asso.ErreurAssociation, match="لا يُحذف"):
        asso.supprimer(conn, op["id"])
    assert not asso.peut_modifier_report(conn, e2)
    with pytest.raises(asso.ErreurAssociation, match="آلياً"):
        asso.modifier_report(conn, e2, 1, 1)
    # تعديل منقول أول سنة ينتقل إلى الموالية
    asso.modifier_report(conn, ex, "52 000,50", 0, "كشف الحساب")
    assert asso.report(conn, ex) == {"banque": 52000.5, "caisse": 0}
    assert asso.report(conn, e2) == {"banque": 52000.5, "caisse": 0}
    # مصروف في السنة الموالية لا يسمح بتخفيض المنقول تحته
    asso.enregistrer(conn, asso.Operation(e2, "2026-09-10", "depense", "banque", 52000, r, "فاتورة 8"))
    with pytest.raises(asso.ErreurAssociation, match="سالباً"):
        asso.modifier_report(conn, ex, 100, 0)
    assert asso.report(conn, e2)["banque"] == 52000.5


def test_sans_report_a_l_ouverture_repare(conn):
    """سنة فُتحت دون منقولها (خلل سابق): يصححها التحيين من رصيد السنة السابقة."""
    e1 = asso.ouvrir_exercice(conn, "najah", "2025", "2025-01-01", "2025-12-31", report_banque=9000)
    e2 = asso.ouvrir_exercice(conn, "najah", "2026", "2026-01-01", "2026-12-31")
    conn.execute("DELETE FROM operation_financiere WHERE exercice_id=?", (e2,))
    conn.commit()
    assert asso.totaux(conn, e2)["banque"] == 0
    assert asso.synchroniser(conn) == []
    assert asso.totaux(conn, e2)["banque"] == 9000 and asso.report(conn, e1)["banque"] == 9000
    # سنة موالية تبدأ في المستقبل: تُفتح بمنقولها (كان يُرفض تاريخه فيفتح دونه)
    e3 = asso.ouvrir_exercice(conn, "najah", "2027", "2027-01-01", "2027-12-31")
    assert asso.report(conn, e3)["banque"] == 9000


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
