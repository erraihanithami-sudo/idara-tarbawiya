"""وثائق جمعية دعم مدرسة النجاح حسب ملاحق الدليل المسطري (يوليوز 2023). بيانات ومبالغ وهمية."""

import zipfile

import pytest

from idara.services import associations as asso
from idara.services import docs_association as da
from idara.services import etablissement as et
from idara.services.textes import montant_lettres_ar


def texte(chemin) -> str:
    import re
    xml = zipfile.ZipFile(chemin).read("word/document.xml").decode("utf-8")
    return re.sub(r"<[^>]+>", " ", xml.replace("</w:p>", "\n")).replace("⁦", "").replace("⁩", "")


@pytest.fixture
def ex(conn):
    et.enregistrer_etablissement(conn, et.Etablissement(nom_ar="مدرسة تجريبية", direction_ar="المديرية التجريبية",
                                                        academie_ar="الأكاديمية التجريبية", commune_ar="جماعة تجريبية"))
    et.enregistrer_directeur(conn, et.Directeur(nom_ar="التجريبي", prenom_ar="أحمد", sexe="M", ppr="1234567"))
    return asso.ouvrir_exercice(conn, "najah", "2025/2026", "2025-09-01", "2026-08-31", 42000, 350, "محضر")


def _r(conn, l):
    return conn.execute("SELECT id FROM rubrique WHERE ligne LIKE ?", (f"%{l}%",)).fetchone()[0]


@pytest.mark.parametrize("m, attendu", [
    (1, "درهم واحد"), (3, "ثلاثة دراهم"), (25, "خمسة وعشرون درهما"), (200, "مائتا درهم"),
    (1200, "ألف ومائتا درهم"), (11000, "أحد عشر ألف درهم"), (45400, "خمسة وأربعون ألفا وأربعمائة درهم"),
    (160000, "مائة وستون ألف درهم"), (3119.5, "ثلاثة آلاف ومائة وتسعة عشر درهما وخمسون سنتيما"),
])
def test_montant_lettres(m, attendu):
    assert montant_lettres_ar(m) == attendu


def test_pieces_selon_operation(conn, ex):
    don = asso.enregistrer(conn, asso.Operation(ex, "2025-10-01", "recette", "caisse", 500, _r(conn, "هبات"),
                                                tiers="محسن وهمي"))
    tr = asso.enregistrer(conn, asso.Operation(ex, "2025-10-02", "transfert", "banque", 1000, reference="شيك 1"))
    dep = asso.enregistrer(conn, asso.Operation(ex, "2025-10-03", "depense", "caisse", 850,
                                                _r(conn, "صيانة وإصلاح تجهيزات"), "فاتورة 12", "إصلاح النوافذ"))
    banq = asso.enregistrer(conn, asso.Operation(ex, "2025-10-04", "depense", "banque", 100,
                                                 _r(conn, "مصاريف البريد والبنك"), "كشف الحساب"))
    report = conn.execute("SELECT id FROM operation_financiere WHERE numero=1").fetchone()[0]
    p = {i: da.pieces_pour(da._operation(conn, i)) for i in (don, tr, dep, banq, report)}
    assert p == {don: ["recu"], tr: ["autorisation_retrait"], dep: ["ordre_paiement", "bon_caisse", "bon_reception"],
                 banq: [], report: []}


def test_recu_numerote_et_donnees_requises(conn, dossier, ex):
    o = asso.enregistrer(conn, asso.Operation(ex, "2025-10-01", "recette", "banque", 10000,
                                              _r(conn, "منحة المديرية"), tiers="المديرية الإقليمية"))
    with pytest.raises(da.ErreurDocAssociation, match="أمين المال"):
        da.generer_piece(conn, dossier, o, "recu")
    asso.modifier_association(conn, "najah", "", "الرئيس الوهمي", "أمين المال الوهمي")
    f = da.generer_piece(conn, dossier, o, "recu")
    t = texte(f)
    assert "وصل مداخيل" in t and "رقم 01/25-26" in t and "عشرة آلاف درهم" in t and "مبلغ (شيك)" in t
    assert "أمين المال الوهمي" in t and "المديرية الإقليمية" in t and "جماعة تجريبية في: 01/10/2025" in t
    assert "رقم 01/25-26" in texte(da.generer_piece(conn, dossier, o, "recu"))  # الرقم ثابت عند إعادة التوليد
    o2 = asso.enregistrer(conn, asso.Operation(ex, "2025-10-02", "recette", "caisse", 50, _r(conn, "هبات"),
                                               tiers="محسن"))
    assert "رقم 02/25-26" in texte(da.generer_piece(conn, dossier, o2, "recu"))
    with pytest.raises(asso.ErreurAssociation, match="وثائق مرقمة"):
        asso.supprimer(conn, o)
    with pytest.raises(da.ErreurDocAssociation, match="لا تخص"):
        da.generer_piece(conn, dossier, o, "bon_caisse")


def test_depense_caisse_trois_pieces(conn, dossier, ex):
    asso.modifier_association(conn, "najah", "", "الرئيس الوهمي", "أمين المال الوهمي")
    o = asso.enregistrer(conn, asso.Operation(ex, "2025-12-05", "depense", "caisse", 200,
                                              _r(conn, "صيانة وإصلاح تجهيزات"), "فاتورة 12", "إصلاح النوافذ",
                                              tiers="النجار الوهمي"))
    t = texte(da.generer_piece(conn, dossier, o, "ordre_paiement"))
    assert "أرخص بأداء مبلغ مالي قدره" in t and "مائتا درهم" in t and "الرئيس أو من ينوب عنه" in t
    assert "صيانة وإصلاح تجهيزات المؤسسة — إصلاح النوافذ" in t
    assert "سند الصندوق" in texte(da.generer_piece(conn, dossier, o, "bon_caisse"))
    with pytest.raises(da.ErreurDocAssociation, match="صفة المستفيد"):
        da.generer_piece(conn, dossier, o, "bon_reception")
    conn.execute("UPDATE operation_financiere SET tiers_qualite='حرفي' WHERE id=?", (o,))
    t = texte(da.generer_piece(conn, dossier, o, "bon_reception"))
    assert "أشهد أني تسلمت من السيد" in t and "النجار الوهمي" in t and "حرفي" in t
    assert da.pieces_emises(conn, o) == {"ordre_paiement": 1, "bon_caisse": 1, "bon_reception": 1}


def test_registres_pages_et_report(conn, dossier, ex):
    asso.enregistrer(conn, asso.Operation(ex, "2025-10-24", "transfert", "banque", 3000, reference="شيك 01"))
    for i in range(27):
        asso.enregistrer(conn, asso.Operation(ex, f"2025-11-{i + 1:02d}", "depense", "caisse", 10,
                                              _r(conn, "مصاريف البريد والبنك"), f"فاتورة {i}"))
    report, lignes = da.lignes_registre(conn, ex, "journal")
    assert report == 42350 and len(lignes) == 27 and lignes[-1]["solde"] == 42080  # التحويل لا يدخل اليومية
    report, lignes = da.lignes_registre(conn, ex, "caisse")
    assert report == 350 and len(lignes) == 28 and lignes[0]["entree"] == 3000 and lignes[-1]["solde"] == 3080
    t = texte(da.generer_registre(conn, dossier, ex, "caisse"))
    assert "سجل الصندوق" in t and "الصفحة 2/2" in t and t.count("المنقول") == 2
    assert "3 090.00" in t  # رصيد آخر الصفحة الأولى منقول إلى الثانية


def test_budget_et_pv_passation(conn, dossier, ex):
    asso.definir_prevision(conn, ex, _r(conn, "منحة المديرية"), 30000)
    asso.definir_prevision(conn, ex, _r(conn, "معدات معلوماتية"), 20000)
    t = texte(da.generer_budget(conn, dossier, ex))
    assert "وثيقة الميزانية" in t and "المجموع العام" in t and "20 000.00" in t and "لا يساوي" in t
    with pytest.raises(da.ErreurDocAssociation, match="رئيس الجمعية"):
        da.generer_pv_passation(conn, dossier, ex, "2026-01-10", "القديم", "الجديد")
    asso.modifier_association(conn, "najah", "", "الرئيس الوهمي", "القديم")
    with pytest.raises(da.ErreurDocAssociation, match="خارج"):
        da.generer_pv_passation(conn, dossier, ex, "2027-01-10", "القديم", "الجديد")
    asso.enregistrer(conn, asso.Operation(ex, "2026-02-01", "recette", "caisse", 100, _r(conn, "هبات"), tiers="س"))
    t = texte(da.generer_pv_passation(conn, dossier, ex, "2026-01-10", "القديم", "الجديد", ["ملاحظة أولى"]))
    assert "محضر تسليم المهام المالية" in t and "42 000.00" in t and "ثلاثمائة وخمسون درهما" in t
    assert "1- ملاحظة أولى" in t and "سجل تسليم الشيكات" in t
