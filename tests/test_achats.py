"""مسطرة الصرف حسب الدليل المسطري (يوليوز 2023): سند الطلب والاتفاقية. بيانات ومبالغ وهمية."""

import pytest

from idara.services import achats as ac
from idara.services import associations as asso
from idara.services import etablissement as et
from tests.test_docs_association import texte


@pytest.fixture
def ex(conn):
    et.enregistrer_etablissement(conn, et.Etablissement(nom_ar="مدرسة تجريبية", direction_ar="المديرية التجريبية",
                                                        academie_ar="الأكاديمية التجريبية", commune_ar="جماعة تجريبية",
                                                        adresse="حي تجريبي", telephone="0500000000"))
    et.enregistrer_directeur(conn, et.Directeur(nom_ar="التجريبي", prenom_ar="أحمد", sexe="M", ppr="1234567"))
    asso.modifier_association(conn, "najah", "", "الرئيس الوهمي", "أمين المال الوهمي")
    return asso.ouvrir_exercice(conn, "najah", "2025/2026", "2025-09-01", "2026-08-31", 30000, 300, "محضر")


def _r(conn, l):
    return conn.execute("SELECT id FROM rubrique WHERE ligne LIKE ? AND actif=1", (f"%{l}%",)).fetchone()[0]


COMMISSION = [("الرئيس الوهمي", "رئيسا"), ("أمين المال الوهمي", "أمين المال"), ("العضو الوهمي", "عضو بمكتب الجمعية")]


def _jusqu_au_choix(conn, ex, mode="bon_commande", service=""):
    rub = _r(conn, "معدات معلوماتية") if mode == "bon_commande" else _r(conn, "مصاريف التنقل للتلاميذ")
    aid = ac.creer(conn, ex, mode, "اقتناء طابعات" if mode == "bon_commande" else "نقل التلاميذ في خرجة", rub,
                   service, "2025-10-01")
    ac.definir_besoin(conn, aid, ac.achat(conn, aid)["objet"], rub,
                      [("طابعة ليزر", "2", "وحدة"), ("خرطوشة حبر", 4, "وحدة"), ("", "", "")], 20, service)
    ac.definir_demande(conn, aid, "2025-10-02", 10, 3)
    ac.definir_commission(conn, aid, "2025-10-15", "10:00", COMMISSION, "العضو الغائب")
    for nom, m in (("الممون أ", 6000), ("الممون ب", 5400), ("الممون ج", 7000)):
        ac.ajouter_offre(conn, aid, nom, m)
    return aid


def test_regles_de_la_concurrence(conn, ex):
    rub = _r(conn, "معدات معلوماتية")
    aid = ac.creer(conn, ex, "bon_commande", "اقتناء طابعات", rub, date_besoin="2025-10-01")
    with pytest.raises(ac.ErreurAchat, match="سطراً واحداً"):
        ac.definir_besoin(conn, aid, "اقتناء طابعات", rub, [("", "", "")])
    ac.definir_besoin(conn, aid, "اقتناء طابعات", rub, [("طابعة", 1, "")])
    with pytest.raises(ac.ErreurAchat, match="15 يوماً"):
        ac.definir_demande(conn, aid, "2025-10-02", 20, 3)
    with pytest.raises(ac.ErreurAchat, match="3 طلبات"):
        ac.definir_demande(conn, aid, "2025-10-02", 10, 2)
    with pytest.raises(ac.ErreurAchat, match="طلب عروض الأثمان أولاً"):
        ac.definir_commission(conn, aid, "2025-10-15", "10:00", COMMISSION)
    ac.definir_demande(conn, aid, "2025-10-02", 10, 3)
    with pytest.raises(ac.ErreurAchat, match="عضو آخر"):
        ac.definir_commission(conn, aid, "2025-10-15", "10:00", COMMISSION[:2])
    with pytest.raises(ac.ErreurAchat, match="الملحق 27"):
        ac.creer(conn, ex, "convention", "صيانة", _r(conn, "صيانة وإصلاح تجهيزات"), "خدمة غير واردة")


def test_choix_du_moins_disant_ou_justification(conn, ex):
    aid = _jusqu_au_choix(conn, ex)
    assert [o["nom"] for o in ac.offres(conn, aid)] == ["الممون ب", "الممون أ", "الممون ج"]
    fa = ac.fournisseur_par_nom(conn, "الممون أ")
    with pytest.raises(ac.ErreurAchat, match="الجودة/الثمن"):
        ac.choisir(conn, aid, fa)
    ac.choisir(conn, aid, fa, "ضمان سنتين على الطابعات")
    assert ac.achat(conn, aid)["justification"] == "ضمان سنتين على الطابعات"
    fb = ac.fournisseur_par_nom(conn, "الممون ب")
    ac.choisir(conn, aid, fb, "تبرير لا يلزم")
    assert ac.achat(conn, aid)["justification"] is None


def test_chaine_bon_de_commande_jusqu_au_paiement(conn, dossier, ex):
    aid = _jusqu_au_choix(conn, ex)
    fb = ac.fournisseur_par_nom(conn, "الممون ب")
    ac.choisir(conn, aid, fb)
    with pytest.raises(ac.ErreurAchat, match="الثمن الفردي"):
        ac.engager(conn, aid, "2025-10-20")
    ac.definir_besoin(conn, aid, "اقتناء طابعات", _r(conn, "معدات معلوماتية"),
                      [("طابعة ليزر", 2, "وحدة", "2000"), ("خرطوشة حبر", 4, "وحدة", 125)], 20)
    assert ac.totaux(conn, aid) == {"ht": 4500, "tva": 900, "ttc": 5400}
    alertes = ac.engager(conn, aid, "2025-10-20")
    assert any("الباقي من المتوقع" in a for a in alertes)  # لا ميزانية متوقعة لهذا البند
    with pytest.raises(ac.ErreurAchat, match="لا يمكن تغيير"):
        ac.ajouter_offre(conn, aid, "ممون متأخر", 100)
    with pytest.raises(ac.ErreurAchat, match="الفاتورة بعد التسليم"):
        ac.facture(conn, aid, "F-12", "2025-10-25")
    ac.reception(conn, aid, "2025-10-24")
    ac.facture(conn, aid, "F-12", "2025-10-25")
    with pytest.raises(ac.ErreurAchat, match="رقم الشيك"):
        ac.payer(conn, aid, "2025-10-28", "cheque", "")
    oid = ac.payer(conn, aid, "2025-10-28", "cheque", "0012345")
    op = conn.execute("SELECT * FROM operation_financiere WHERE id=?", (oid,)).fetchone()
    assert (op["registre"], op["montant"], op["tiers"]) == ("banque", 5400, "الممون ب")
    assert op["reference"] == "شيك رقم 0012345 — فاتورة F-12"
    assert all(ok for _, ok in ac.etapes(conn, aid))
    with pytest.raises(ac.ErreurAchat, match="لا يُحذف"):
        ac.supprimer(conn, aid)
    with pytest.raises(ac.ErreurAchat, match="عنوان الممون"):
        ac.generer(conn, dossier, aid, "bon_commande")
    ac.enregistrer_fournisseur(conn, ac.Fournisseur("الممون ب", adresse="شارع وهمي", patente="123", id=fb))
    t = texte(ac.generer(conn, dossier, aid, "bon_commande"))
    assert "رقم سند الطلب" in t and "01/25-26" in t and "5 400.00" in t and "شارع وهمي" in t
    t = texte(ac.generer(conn, dossier, aid, "pv_commission"))
    assert "خمسة آلاف وأربعمائة درهم" in t and "العضو الغائب" in t and "الممون ج" in t
    t = texte(ac.generer(conn, dossier, aid, "bon_livraison"))
    assert "سند الطلب رقم 01/25-26 بتاريخ 20/10/2025" in t and "123" in t
    t = texte(ac.generer(conn, dossier, aid, "invitations"))
    assert t.count("دعوة للمشاركة") == 2 and "الرئيس الوهمي" not in t.split("رئيس الجمعية")[0]
    t = texte(ac.generer(conn, dossier, aid, "demande_devis"))
    assert "أجل إرجاع الرد: 10" in t and "12/10/2025" in t
    assert "Devis N°" in texte(ac.generer(conn, dossier, aid, "modele_devis"))
    with pytest.raises(ac.ErreurAchat, match="لا تخص"):
        ac.generer(conn, dossier, aid, "convention")


def test_convention_et_pv_service(conn, dossier, ex):
    s = ac.SERVICES_CONVENTION[1]
    aid = _jusqu_au_choix(conn, ex, "convention", s)
    fb = ac.fournisseur_par_nom(conn, "الممون ب")
    ac.choisir(conn, aid, fb)
    ac.definir_besoin(conn, aid, "نقل التلاميذ في خرجة", _r(conn, "مصاريف التنقل للتلاميذ"),
                      [("نقل ذهاباً وإياباً", 1, "رحلة", 4500)], 20, s)
    with pytest.raises(ac.ErreurAchat, match="بعد إبرام"):
        ac.engager(conn, aid, "2025-10-20", "2025-10-22")
    ac.engager(conn, aid, "2025-10-20", "2025-10-18")
    with pytest.raises(ac.ErreurAchat, match="شخصان"):
        ac.reception(conn, aid, "2025-10-30", [("واحد", "أستاذ")])
    ac.reception(conn, aid, "2025-10-30", [("الأستاذ الوهمي", "أستاذ"), ("الحارس الوهمي", "حارس")])
    with pytest.raises(ac.ErreurAchat, match="بيانات المكلف"):
        ac.generer(conn, dossier, aid, "convention")
    ac.enregistrer_fournisseur(conn, ac.Fournisseur("الممون ب", "مقاولة النقل الوهمية", "AB123", "شارع وهمي",
                                                    compte_bancaire="0000111122223333", id=fb))
    t = texte(ac.generer(conn, dossier, aid, "convention"))
    assert "الاتفاقية رقم" in t and "المادة 11: جدول الأثمان" in t and "خمسة آلاف وأربعمائة درهم" in t
    assert "مقاولة النقل الوهمية" in t and "03 ثلاث سنوات" in t
    t = texte(ac.generer(conn, dossier, aid, "pv_service"))
    assert "محضر إنجاز الخدمة والمطابقة" in t and "الحارس الوهمي" in t and "مطابق" in t
    assert ac.etapes(conn, aid)[3] == ("النسخة الأصلية للاتفاقية", True)
    ac.ajouter_offre(conn, ac.creer(conn, ex, "convention", "خرجة ثانية", _r(conn, "مصاريف التنقل للتلاميذ"), s),
                     "الممون ب", 100)
    assert ac.fournisseur(conn, fb).cin == "AB123"  # تسجيل عرض جديد لا يمحو بيانات الممون


def test_recu_equipement_et_aide_etrangere(conn, dossier, ex):
    t = texte(ac.recu_equipement(conn, dossier, ex, "2025-11-03", "شركة وهمية", "حاسوب محمول\nطابعة"))
    assert "وصل تسلم تجهيز" in t and "رقم 01/25-26" in t and "حاسوب محمول" in t
    assert len(ac.dons(conn, ex)) == 1
    f, alerte = ac.declaration_aide_etrangere(conn, dossier, ex, "2025-11-01", ["كتب مدرسية"], "مكتبة المؤسسة",
                                              "2025-12-15")
    t = texte(f)
    assert "الأمين العام للحكومة" in t and "1.58.376" in t and "كتب مدرسية" in t
    assert alerte and "44 يوماً" in alerte
