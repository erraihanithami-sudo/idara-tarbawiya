"""مسطرة الصرف لجمعية دعم مدرسة النجاح، حسب الدليل المسطري (يوليوز 2023):

- آلية الصرف بواسطة سند الطلب (الفقرة 1.2.3): التعبير عن الحاجة، طلب عروض الأثمان (3 على الأقل، أجل
  لا يتعدى 15 يوماً)، لجنة دراسة العروض والعرض الأقل ثمناً (أو تبرير العرض الأكثر نفعاً)، سند الطلب،
  سند التسليم، الفاتورة («خدمة منجزة» و«قابل للأداء»)، ثم الأداء بالشيك.
- آلية الصرف بواسطة الاتفاقية أو الشراكة (الفقرة 3.2.3): لخدمات لائحة الملحق 27 فقط، نفس المنافسة،
  ثم الاتفاقية (الملحق 26) والطلب (الملحق 6) ومحضر إنجاز الخدمة والمطابقة (الملحق 28)، والأداء بالشيك
  أو التحويل.
- وصل تسلم تجهيز للمداخيل العينية (الملحق 14)، والتصريح بتلقي مساعدة أجنبية (الملحق 15).

الفاتورة (الملحق 8) وعرض الأثمان المملوء وثيقتان يحررهما الممون: يسجل التطبيق رقم الفاتورة وتاريخها،
ويولد عرض الأثمان فارغ الأثمان ليملأه الممون.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, fields
from datetime import date, timedelta
from pathlib import Path

from docx.shared import Cm

from idara.data.dossier import DossierDonnees
from idara.services import associations as asso
from idara.services import docs_association as da
from idara.services import etablissement as etab_srv
from idara.services import textes as tx
from idara.services.docs_association import (ajouter, dh, ltr, para, saut_page, tableau, _cellule, _nouveau,
                                             _ombre)

# الملحق 27: لائحة الخدمات موضوع الاتفاقية أو الشراكة
SERVICES_CONVENTION = (
    "خدمات تنشيط الحياة المدرسية من طرف جمعيات معتمدة",
    "خدمات النقل لفائدة المتعلمين والمتعلمات (خرجات تربوية، خرجات في إطار الأنشطة الرياضية، زيارات في إطار "
    "استكشاف المهن، خرجات ترفيهية...) — لا تشمل النقل المدرسي",
    "خدمات الطبع والتوثيق والنسخ",
    "الاستشارات الطبية",
    "خدمات الاستقبال والمأكل",
    "الاشتراك في شبكات الاتصالات أو خدمات الإنترنيت",
    "أعمال التكوين المستمر لفائدة الأطر التربوية والإدارية للمؤسسة التعليمية",
    "أعمال الصيانة المتعلقة ببنايات وتجهيزات المؤسسة التعليمية",
)
MODES = {"bon_commande": "سند الطلب", "convention": "الاتفاقية أو الشراكة"}
DELAI_MAX = 15
DEMANDES_MIN = 3

DOCUMENTS = {  # الرمز ← (العنوان، الملحق، الآليات)
    "demande_devis": ("طلب عرض أثمان", 2, ("bon_commande", "convention")),
    "modele_devis": ("نموذج عرض أثمان (يملؤه الممون)", 3, ("bon_commande", "convention")),
    "invitations": ("دعوات المشاركة في لجنة دراسة عروض الأثمان", 4, ("bon_commande", "convention")),
    "pv_commission": ("محضر اجتماع لجنة دراسة عروض الأثمان", 5, ("bon_commande", "convention")),
    "convention": ("الاتفاقية", 26, ("convention",)),
    "bon_commande": ("سند الطلب", 6, ("bon_commande", "convention")),
    "bon_livraison": ("سند التسليم", 7, ("bon_commande",)),
    "pv_service": ("محضر إنجاز الخدمة والمطابقة", 28, ("convention",)),
}


class ErreurAchat(ValueError):
    """رسالة موجهة للمدير بالعربية."""


def _d(v: str | None, lib: str) -> date:
    try:
        return date.fromisoformat(v or "")
    except ValueError:
        raise ErreurAchat(f"{lib} غير صحيح.") from None


def _nombre(v, lib: str) -> float:
    try:
        return round(float(str(v).replace(",", ".").replace(" ", "").replace(" ", "")), 2)
    except ValueError:
        raise ErreurAchat(f"{lib} غير صحيح.") from None


def _txt(v) -> str:
    return " ".join(str(v or "").split())


# ---------- الممونون ----------

@dataclass
class Fournisseur:
    nom: str
    represente_par: str = ""
    cin: str = ""
    adresse: str = ""
    telephone: str = ""
    rc: str = ""
    patente: str = ""
    cnss: str = ""
    ice: str = ""
    compte_bancaire: str = ""
    id: int | None = None


def enregistrer_fournisseur(conn, f: Fournisseur) -> int:
    vals = {k.name: _txt(getattr(f, k.name)) for k in fields(f) if k.name != "id"}
    if not vals["nom"]:
        raise ErreurAchat("اسم الممون إجباري.")
    with conn:
        if f.id is None:
            r = conn.execute("SELECT id FROM fournisseur WHERE nom=?", (vals["nom"],)).fetchone()
            if r:
                f.id = r[0]
            else:
                cols = ", ".join(vals)
                f.id = conn.execute(f"INSERT INTO fournisseur({cols}) VALUES ({', '.join('?' * len(vals))})",
                                    [v or None for v in vals.values()]).lastrowid
                return f.id
        conn.execute("UPDATE fournisseur SET " + ", ".join(f"{k}=?" for k in vals) + " WHERE id=?",
                     [v or None for v in vals.values()] + [f.id])
    return f.id


def fournisseur(conn, fid: int) -> Fournisseur:
    r = conn.execute("SELECT * FROM fournisseur WHERE id=?", (fid,)).fetchone()
    if r is None:
        raise ErreurAchat("الممون غير موجود.")
    return Fournisseur(**{k.name: (r[k.name] or "") if k.name != "id" else r["id"] for k in fields(Fournisseur)})


def fournisseurs(conn) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM fournisseur ORDER BY nom").fetchall()


def fournisseur_par_nom(conn, nom: str) -> int:
    """الممون باسمه؛ يُنشأ إن لم يوجد، ولا تُمس بياناته إن وُجد."""
    r = conn.execute("SELECT id FROM fournisseur WHERE nom=?", (_txt(nom),)).fetchone()
    return r[0] if r else enregistrer_fournisseur(conn, Fournisseur(_txt(nom)))


# ---------- الملف ----------

def achat(conn, aid: int) -> sqlite3.Row:
    r = conn.execute("SELECT a.*, r.ligne, r.chapitre, f.nom AS fournisseur FROM achat a "
                     "LEFT JOIN rubrique r ON r.id=a.rubrique_id LEFT JOIN fournisseur f ON f.id=a.fournisseur_id "
                     "WHERE a.id=?", (aid,)).fetchone()
    if r is None:
        raise ErreurAchat("الملف غير موجود.")
    return r


def dossiers(conn, eid: int) -> list[sqlite3.Row]:
    return conn.execute("SELECT a.*, f.nom AS fournisseur FROM achat a LEFT JOIN fournisseur f "
                        "ON f.id=a.fournisseur_id WHERE a.exercice_id=? ORDER BY a.id DESC", (eid,)).fetchall()


def _verifier_objet(conn, mode: str, objet: str, rubrique_id, service_type: str) -> None:
    if mode not in MODES:
        raise ErreurAchat("آلية الصرف: سند الطلب أو الاتفاقية.")
    if not _txt(objet):
        raise ErreurAchat("موضوع الحاجة إجباري.")
    r = conn.execute("SELECT sens, actif FROM rubrique WHERE id=?", (rubrique_id,)).fetchone()
    if r is None or r["sens"] != "depense" or not r["actif"]:
        raise ErreurAchat("اختر بند الميزانية (من بنود المصاريف).")
    if mode == "convention" and service_type not in SERVICES_CONVENTION:
        raise ErreurAchat("الصرف بالاتفاقية يخص فقط الخدمات الواردة في الملحق 27 من الدليل.")


def creer(conn, eid: int, mode: str, objet: str, rubrique_id: int, service_type: str = "",
          date_besoin: str | None = None) -> int:
    asso.exercice(conn, eid)
    _verifier_objet(conn, mode, objet, rubrique_id, service_type)
    with conn:
        return conn.execute("INSERT INTO achat(exercice_id, mode, objet, rubrique_id, service_type, date_besoin) "
                            "VALUES (?,?,?,?,?,?)", (eid, mode, _txt(objet), rubrique_id,
                                                     service_type if mode == "convention" else None,
                                                     date_besoin or date.today().isoformat())).lastrowid


def _non_engage(a) -> None:
    if a["date_bc"]:
        raise ErreurAchat("صدر سند الطلب (أو الطلب): لا يمكن تغيير الحاجة بعده.")


def definir_besoin(conn, aid: int, objet: str, rubrique_id: int, articles: list[tuple], taux_tva=20,
                   service_type: str = "") -> None:
    """articles: (التعيين، الكمية، الوحدة[، الثمن الفردي]) — الثمن يُحدد بعد اختيار العرض."""
    a = achat(conn, aid)
    _non_engage(a)
    _verifier_objet(conn, a["mode"], objet, rubrique_id, service_type)
    tva = _nombre(taux_tva, "نسبة الضريبة على القيمة المضافة")
    if not 0 <= tva <= 30:
        raise ErreurAchat("نسبة الضريبة على القيمة المضافة بين 0 و30.")
    lignes = []
    for i, art in enumerate(articles, start=1):
        des = _txt(art[0])
        if not des:
            continue
        q = _nombre(art[1] if len(art) > 1 else "", f"كمية السطر {i}")
        if q <= 0:
            raise ErreurAchat(f"كمية السطر {i} تكون أكبر من صفر.")
        pu = art[3] if len(art) > 3 else None
        pu = None if pu in (None, "") else _nombre(pu, f"ثمن السطر {i}")
        lignes.append((des, q, _txt(art[2]) if len(art) > 2 else "", pu))
    if not lignes:
        raise ErreurAchat("أضف سطراً واحداً على الأقل (التعيين والكمية).")
    with conn:
        conn.execute("UPDATE achat SET objet=?, rubrique_id=?, taux_tva=?, service_type=? WHERE id=?",
                     (_txt(objet), rubrique_id, tva, service_type if a["mode"] == "convention" else None, aid))
        conn.execute("DELETE FROM achat_article WHERE achat_id=?", (aid,))
        conn.executemany("INSERT INTO achat_article(achat_id, ordre, designation, quantite, unite, prix_unitaire) "
                         "VALUES (?,?,?,?,?,?)", [(aid, i, *l) for i, l in enumerate(lignes, start=1)])


def articles(conn, aid: int) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM achat_article WHERE achat_id=? ORDER BY ordre", (aid,)).fetchall()


def totaux(conn, aid: int) -> dict[str, float]:
    a = achat(conn, aid)
    ht = round(sum(r["quantite"] * (r["prix_unitaire"] or 0) for r in articles(conn, aid)), 2)
    tva = round(ht * a["taux_tva"] / 100, 2)
    return {"ht": ht, "tva": tva, "ttc": round(ht + tva, 2)}


def definir_demande(conn, aid: int, date_demande: str, delai: int | str, nb: int | str) -> None:
    """طلب عروض الأثمان: 3 ممونين على الأقل في نفس التاريخ، وأجل الرد لا يتعدى 15 يوماً."""
    a = achat(conn, aid)
    _non_engage(a)
    e = asso.exercice(conn, a["exercice_id"])
    d = _d(date_demande, "تاريخ طلب عروض الأثمان")
    if not e["date_debut"] <= date_demande <= e["date_fin"]:
        raise ErreurAchat("تاريخ الطلب خارج السنة المالية.")
    delai, nb = int(_nombre(delai, "أجل الرد")), int(_nombre(nb, "عدد الطلبات"))
    if not 1 <= delai <= DELAI_MAX:
        raise ErreurAchat(f"أجل إرجاع الرد لا يتعدى {DELAI_MAX} يوماً (الدليل المسطري).")
    if nb < DEMANDES_MIN:
        raise ErreurAchat(f"توجه على الأقل {DEMANDES_MIN} طلبات عروض الأثمان إلى ثلاثة ممونين (الدليل المسطري).")
    if a["date_besoin"] and d < _d(a["date_besoin"], "تاريخ الحاجة"):
        raise ErreurAchat("تاريخ الطلب قبل تاريخ التعبير عن الحاجة.")
    with conn:
        conn.execute("UPDATE achat SET date_demande=?, delai_jours=?, nb_demandes=? WHERE id=?",
                     (date_demande, delai, nb, aid))


def definir_commission(conn, aid: int, date_c: str, heure: str, membres: list[tuple[str, str]],
                       absents: str = "") -> None:
    """اللجنة: رئيس الجمعية وأمين مالها وعضو أو أعضاء آخرون من المكتب أو مجلس التدبير."""
    a = achat(conn, aid)
    _non_engage(a)
    if not a["date_demande"]:
        raise ErreurAchat("سجل طلب عروض الأثمان أولاً.")
    d = _d(date_c, "تاريخ اجتماع اللجنة")
    if d < _d(a["date_demande"], ""):
        raise ErreurAchat("اجتماع اللجنة قبل تاريخ طلب عروض الأثمان.")
    heure = _txt(heure)
    if not heure:
        raise ErreurAchat("ساعة الاجتماع إجبارية.")
    m = [(_txt(n), _txt(q)) for n, q in membres if _txt(n)]
    if len(m) < 3:
        raise ErreurAchat("اللجنة: الرئيس وأمين المال وعضو آخر على الأقل.")
    with conn:
        conn.execute("UPDATE achat SET date_commission=?, heure_commission=?, membres=?, absents=? WHERE id=?",
                     (date_c, heure, json.dumps(m, ensure_ascii=False), _txt(absents) or None, aid))


def membres(a) -> list[tuple[str, str]]:
    return [tuple(x) for x in json.loads(a["membres"] or "[]")]


def ajouter_offre(conn, aid: int, nom_fournisseur: str, montant) -> int:
    a = achat(conn, aid)
    _non_engage(a)
    m = _nombre(montant, "مبلغ العرض")
    if m <= 0:
        raise ErreurAchat("مبلغ العرض يكون أكبر من صفر.")
    fid = fournisseur_par_nom(conn, nom_fournisseur)
    with conn:
        conn.execute("INSERT INTO achat_offre(achat_id, fournisseur_id, montant) VALUES (?,?,?) "
                     "ON CONFLICT(achat_id, fournisseur_id) DO UPDATE SET montant=excluded.montant", (aid, fid, m))
    return fid


def supprimer_offre(conn, aid: int, fid: int) -> None:
    a = achat(conn, aid)
    _non_engage(a)
    with conn:
        conn.execute("DELETE FROM achat_offre WHERE achat_id=? AND fournisseur_id=?", (aid, fid))
        if a["fournisseur_id"] == fid:
            conn.execute("UPDATE achat SET fournisseur_id=NULL, justification=NULL WHERE id=?", (aid,))


def offres(conn, aid: int) -> list[sqlite3.Row]:
    return conn.execute("SELECT o.*, f.nom FROM achat_offre o JOIN fournisseur f ON f.id=o.fournisseur_id "
                        "WHERE o.achat_id=? ORDER BY o.montant, f.nom", (aid,)).fetchall()


def choisir(conn, aid: int, fid: int, justification: str = "") -> None:
    """اللجنة تعتمد العرض الأقل ثمناً؛ غيره يستلزم تبريراً (الجودة/الثمن) يُضمَّن في المحضر."""
    a = achat(conn, aid)
    _non_engage(a)
    if not a["date_commission"]:
        raise ErreurAchat("سجل اجتماع اللجنة أولاً.")
    os_ = offres(conn, aid)
    if fid not in [o["fournisseur_id"] for o in os_]:
        raise ErreurAchat("اختر عرضاً من العروض المسجلة.")
    plus_bas = os_[0]["montant"]
    choisi = next(o for o in os_ if o["fournisseur_id"] == fid)
    if choisi["montant"] > plus_bas and not _txt(justification):
        raise ErreurAchat("العرض المختار ليس الأقل ثمناً: يجب تبرير الاختيار بمقياس الجودة/الثمن.")
    with conn:
        conn.execute("UPDATE achat SET fournisseur_id=?, justification=? WHERE id=?",
                     (fid, _txt(justification) if choisi["montant"] > plus_bas else None, aid))


def engager(conn, aid: int, date_bc: str, date_convention: str | None = None) -> list[str]:
    """سند الطلب (أو الطلب المقدم للمكلف بالأعمال): بعد المحضر، وكل الأثمان محددة. يرجع تنبيهات الميزانية."""
    a = achat(conn, aid)
    if not a["fournisseur_id"]:
        raise ErreurAchat("لم يقع الاختيار على عرض بعد.")
    if any(r["prix_unitaire"] is None for r in articles(conn, aid)):
        raise ErreurAchat("حدد الثمن الفردي لكل سطر حسب العرض المختار.")
    d = _d(date_bc, "تاريخ سند الطلب")
    if d < _d(a["date_commission"], ""):
        raise ErreurAchat("سند الطلب قبل اجتماع اللجنة.")
    e = asso.exercice(conn, a["exercice_id"])
    if not e["date_debut"] <= date_bc <= e["date_fin"]:
        raise ErreurAchat("تاريخ سند الطلب خارج السنة المالية.")
    if a["mode"] == "convention":
        dc = _d(date_convention, "تاريخ الاتفاقية")
        if dc > d:
            raise ErreurAchat("الطلب يأتي بعد إبرام الاتفاقية.")
    t = totaux(conn, aid)
    alertes = []
    ligne = next((r for r in asso.execution(conn, a["exercice_id"]) if r["id"] == a["rubrique_id"]), None)
    if ligne and t["ttc"] > ligne["reste"] + 1e-9:
        alertes.append(f"المبلغ ({t['ttc']:,.2f}) يتجاوز الباقي من المتوقع في بند «{ligne['ligne']}» "
                       f"({ligne['reste']:,.2f}).")
    banque = asso.soldes(conn, a["exercice_id"])["banque"]
    if t["ttc"] > banque:
        alertes.append(f"رصيد البنك ({banque:,.2f}) لا يغطي المبلغ: الدليل يشترط التأكد من توفر الموارد.")
    with conn:
        conn.execute("UPDATE achat SET date_bc=?, date_convention=? WHERE id=?",
                     (date_bc, date_convention if a["mode"] == "convention" else None, aid))
    return alertes


def reception(conn, aid: int, date_l: str, commission: list[tuple[str, str]] | None = None) -> None:
    """التسليم: سند التسليم (سند الطلب) أو محضر إنجاز الخدمة والمطابقة بلجنة من شخصين على الأقل (الاتفاقية)."""
    a = achat(conn, aid)
    if not a["date_bc"]:
        raise ErreurAchat("لم يصدر سند الطلب بعد.")
    if _d(date_l, "تاريخ التسليم") < _d(a["date_bc"], ""):
        raise ErreurAchat("التسليم قبل سند الطلب.")
    c = [(_txt(n), _txt(q)) for n, q in (commission or []) if _txt(n)]
    if a["mode"] == "convention" and len(c) < 2:
        raise ErreurAchat("لجنة التسليم الجزئي أو الكلي للخدمة: شخصان على الأقل.")
    with conn:
        conn.execute("UPDATE achat SET date_livraison=?, commission_reception=? WHERE id=?",
                     (date_l, json.dumps(c, ensure_ascii=False) if c else None, aid))


def facture(conn, aid: int, numero: str, date_f: str) -> None:
    a = achat(conn, aid)
    if not a["date_livraison"]:
        raise ErreurAchat("الفاتورة بعد التسليم أو إنجاز الخدمة.")
    if not _txt(numero):
        raise ErreurAchat("رقم الفاتورة إجباري.")
    if _d(date_f, "تاريخ الفاتورة") < _d(a["date_bc"], ""):
        raise ErreurAchat("الفاتورة قبل سند الطلب.")
    with conn:
        conn.execute("UPDATE achat SET facture_numero=?, facture_date=? WHERE id=?", (_txt(numero), date_f, aid))


def payer(conn, aid: int, date_p: str, mode: str, reference_paiement: str) -> int:
    """الأداء بالشيك أو التحويل البنكي فقط (حصراً للاتفاقية، والقاعدة لسند الطلب)، ويُسجل مصروفاً بسجل البنك."""
    a = achat(conn, aid)
    if a["operation_id"]:
        raise ErreurAchat("سُجل أداء هذا الملف من قبل.")
    if not a["facture_numero"]:
        raise ErreurAchat("سجل الفاتورة («خدمة منجزة» و«قابل للأداء») قبل الأداء.")
    if mode not in ("cheque", "virement"):
        raise ErreurAchat("الأداء بالشيك أو بالتحويل البنكي.")
    if not _txt(reference_paiement):
        raise ErreurAchat("رقم الشيك أو مرجع التحويل إجباري.")
    if _d(date_p, "تاريخ الأداء") < _d(a["facture_date"], ""):
        raise ErreurAchat("الأداء قبل تاريخ الفاتورة.")
    t = totaux(conn, aid)
    lib = "شيك رقم" if mode == "cheque" else "تحويل"
    op = asso.Operation(a["exercice_id"], date_p, "depense", "banque", t["ttc"], a["rubrique_id"],
                        f"{lib} {_txt(reference_paiement)} — فاتورة {a['facture_numero']}", a["objet"],
                        tiers=a["fournisseur"], tiers_qualite="ممون" if a["mode"] == "bon_commande"
                        else "مكلف بالأعمال")
    try:
        oid = asso.enregistrer(conn, op)
    except asso.ErreurAssociation as e:
        raise ErreurAchat(str(e)) from None
    with conn:
        conn.execute("UPDATE achat SET operation_id=? WHERE id=?", (oid, aid))
    return oid


def supprimer(conn, aid: int) -> None:
    a = achat(conn, aid)
    if a["date_bc"]:
        raise ErreurAchat("صدر سند الطلب: الملف جزء من الأرشيف المالي ولا يُحذف.")
    with conn:
        conn.execute("DELETE FROM achat WHERE id=?", (aid,))


def etapes(conn, aid: int) -> list[tuple[str, bool]]:
    """ملف الأداء كما يحدده الدليل، مع حالة كل وثيقة."""
    a = achat(conn, aid)
    conv = a["mode"] == "convention"
    res = [("التعبير عن الحاجة", bool(articles(conn, aid))),
           ("طلب عروض الأثمان (3 على الأقل)", bool(a["date_demande"])),
           ("محضر البت في عروض الأثمان مرفقاً بالعروض", bool(a["fournisseur_id"]))]
    if conv:
        res.append(("النسخة الأصلية للاتفاقية", bool(a["date_convention"])))
    res += [("الطلب المقدم للمكلف بالأعمال" if conv else "النسخة الأصلية لسند الطلب", bool(a["date_bc"])),
            ("محضر إنجاز الخدمة" if conv else "سند التسليم", bool(a["date_livraison"])),
            ("النسخة الأصلية للفاتورة", bool(a["facture_numero"])),
            ("الشيك أو الأمر بالتحويل (مسجل بسجل البنك)", bool(a["operation_id"]))]
    return res


# ---------- الوثائق ----------

def _numero(conn, a, type_: str) -> str:
    r = conn.execute("SELECT numero FROM numero_achat WHERE type=? AND achat_id=?", (type_, a["id"])).fetchone()
    if r:
        n = r[0]
    else:
        with conn:
            n = conn.execute("SELECT COALESCE(MAX(numero),0)+1 FROM numero_achat WHERE exercice_id=? AND type=?",
                             (a["exercice_id"], type_)).fetchone()[0]
            conn.execute("INSERT INTO numero_achat(exercice_id, type, numero, achat_id) VALUES (?,?,?,?)",
                         (a["exercice_id"], type_, n, a["id"]))
    return ltr(f"{n:02d}/{da.code_exercice(asso.exercice(conn, a['exercice_id'])['libelle'])}")


def _ctx(conn, a) -> dict:
    try:
        ctx = da._contexte(conn, a["exercice_id"])
    except da.ErreurDocAssociation as e:
        raise ErreurAchat(str(e)) from None
    etab = etab_srv.lire_etablissement(conn)
    if not etab.adresse:
        raise ErreurAchat("عنوان المؤسسة غير مسجل (الإعدادات ← المؤسسة): يُكتب في رأس وثائق الجمعية.")
    ctx["adresse"], ctx["tel"] = etab.adresse, etab.telephone or "—"
    return ctx


def _entete_asso(d, ctx) -> None:
    for lib, v in (("الجمعية: ", ctx["a"]["nom"]), ("العنوان: ", ctx["adresse"]),
                   ("الهاتف/الفاكس: ", ltr(ctx["tel"]) if ctx["tel"] != "—" else "—")):
        p = para(d, apres=0)
        ajouter(p, lib, gras=True)
        ajouter(p, v)
    para(d, apres=8)


def _bloc_fournisseur(d, f: Fournisseur | None) -> None:
    v = (lambda x: x or "—") if f else (lambda x: "....................")
    f = f or Fournisseur("")
    t = tableau(d, 3, 2, bordures=False, largeurs=[9.2, 8.2])
    for i, ((l1, v1), (l2, v2)) in enumerate(((("اسم الممون أو الشركة أو المقاولة: ", f.nom), ("رقم الضريبة المهنية: ", f.patente)),
                                              (("رقم ص.و.ض.ج: ", f.cnss), ("رقم القيد في السجل التجاري: ", f.rc)),
                                              (("العنوان الاجتماعي: ", f.adresse), ("الهاتف والفاكس: ", f.telephone)))):
        for j, (lib, val) in enumerate(((l1, v1), (l2, v2))):
            c = t.cell(i, j)
            c.paragraphs[0]._element.getparent().remove(c.paragraphs[0]._element)
            p = para(c, apres=2)
            ajouter(p, lib, gras=True, taille=13)
            ajouter(p, v(val), taille=13)
    para(d, apres=6)


def _titre(d, ar: str, fr: str, numero: str, exercice: str, extra: str = "") -> None:
    p = para(d, centre=True, apres=0)
    ajouter(p, f"{ar} رقم: ", gras=True, taille=19)
    ajouter(p, numero, gras=True, taille=17)
    para(d, ltr(fr), centre=True, taille=12, apres=0)
    para(d, f"السنة المالية {exercice}" + (f" — {extra}" if extra else ""), gras=True, centre=True, apres=8)


def _table_articles(d, arts, avec_prix: bool, prix_vides: bool = False, tot: dict | None = None) -> None:
    cols = [("رقم الترتيب", ""), ("التعيين", "Désignation"), ("الكمية", "Quantité")]
    larg = [1.6, 10.8, 2.6] if not avec_prix else [1.4, 7.6, 2.0, 3.0, 3.4]
    if avec_prix:
        cols += [("الثمن الفردي", "Prix unitaire"), ("الثمن الإجمالي", "Prix total")]
    n_tot = 3 if avec_prix else 0
    t = tableau(d, 1 + max(len(arts), 1) + n_tot, len(cols), largeurs=larg)
    for j, (ar, fr) in enumerate(cols):
        c = t.cell(0, j)
        _cellule(c, ar, gras=True, taille=12)
        if fr:
            para(c, ltr(fr), taille=10, centre=True, apres=0)
    for i, r in enumerate(arts, start=1):
        q = f"{r['quantite']:g}" + (f" {r['unite']}" if r["unite"] else "")
        vals = [f"{i:02d}", r["designation"], q]
        if avec_prix:
            if prix_vides:
                vals += ["", ""]
            else:
                vals += [dh(r["prix_unitaire"]), dh(round(r["quantite"] * r["prix_unitaire"], 2))]
        for j, v in enumerate(vals):
            _cellule(t.cell(i, j), v, taille=12, centre=j != 1)
    if avec_prix:
        base = 1 + max(len(arts), 1)
        for k, (ar, fr, cle) in enumerate((("المجموع دون احتساب الضريبة على القيمة المضافة", "TOTAL (HORS TVA EN DH)", "ht"),
                                           ("مجموع الضريبة على القيمة المضافة", "TOTAL TVA", "tva"),
                                           ("المجموع باحتساب الضريبة على القيمة المضافة", "TOTAL (TTC EN DH)", "ttc"))):
            row = base + k
            t.cell(row, 0).merge(t.cell(row, 3))
            _cellule(t.cell(row, 0), f"{ar}  {ltr(fr)}", gras=True, taille=11, centre=False)
            _cellule(t.cell(row, 4), "" if tot is None else dh(tot[cle]), gras=True, taille=12)
            _ombre(t.cell(row, 0), "F2F2F2")
    para(d, apres=8)


def _fait(d, ctx, d_iso: str | None) -> None:
    para(d, f"حرر ب{ctx['ville']} بتاريخ {tx.date_chiffres(d_iso) if d_iso else '....................'}", apres=4)


def _signatures(d, libs: list[str]) -> None:
    w = 17.4 / len(libs)
    t = tableau(d, 1, len(libs), bordures=False, largeurs=[w] * len(libs))
    for j, lib in enumerate(libs):
        _cellule(t.cell(0, j), lib, gras=True)
    para(d, apres=40)


def _doc_demande_devis(conn, d, a, ctx):
    if not a["date_demande"]:
        raise ErreurAchat("سجل تاريخ طلب عروض الأثمان وأجل الرد أولاً.")
    arts = articles(conn, a["id"])
    if not arts:
        raise ErreurAchat("حدد الحاجة (التعيين والكمية) أولاً.")
    _entete_asso(d, ctx)
    _titre(d, "طلب عرض أثمان", "Demande de devis N°", _numero(conn, a, "demande_devis"), ctx["e"]["libelle"])
    para(d, f"الموضوع: {a['objet']}", gras=True, apres=6)
    _table_articles(d, arts, False)
    fin = _d(a["date_demande"], "") + timedelta(days=a["delai_jours"])
    para(d, f"أجل إرجاع الرد: {a['delai_jours']} يوماً، أي قبل {tx.date_chiffres(fin.isoformat())}.", apres=4)
    _fait(d, ctx, a["date_demande"])
    _signatures(d, ["رئيس الجمعية أو الشخص المفوض له"])


def _doc_modele_devis(conn, d, a, ctx):
    arts = articles(conn, a["id"])
    if not arts:
        raise ErreurAchat("حدد الحاجة (التعيين والكمية) أولاً.")
    _bloc_fournisseur(d, None)
    _titre(d, "رقم عرض أثمان", "Devis N°", "....................", ctx["e"]["libelle"])
    para(d, f"الموضوع: {a['objet']} — طلب عرض الأثمان رقم {_numero(conn, a, 'demande_devis')}", apres=6)
    _table_articles(d, arts, True, prix_vides=True)
    para(d, ltr("Arrêté le présent Devis à la somme de : ......................................................"),
         taille=12, apres=4)
    para(d, ltr("Fait à .................... le ...................."), taille=12, apres=10)
    _signatures(d, ["توقيع الممون", "توقيع أعضاء لجنة فتح الأظرفة في خلف الوثيقة"])


def _doc_invitations(conn, d, a, ctx):
    if not a["date_commission"]:
        raise ErreurAchat("سجل تاريخ اجتماع اللجنة وأعضاءها أولاً.")
    president = _txt(ctx["a"]["president"])
    invites = [m for m in membres(a) if m[0] != president]
    numero = _numero(conn, a, "invitations")
    for k, (nom, qualite) in enumerate(invites):
        if k:
            saut_page(d)
        _entete_asso(d, ctx)
        para(d, "دعوة للمشاركة في لجنة دراسة عروض الأثمان", gras=True, taille=19, centre=True, apres=0)
        p = para(d, centre=True, apres=14)
        ajouter(p, "رقم ", gras=True)
        ajouter(p, numero)
        para(d, "تتشرف الجمعية بدعوة", apres=4)
        para(d, f"السيد(ة): {nom}، {qualite or 'عضو(ة) بمكتب الجمعية'}؛", apres=4)
        para(d, f"وذلك من أجل المشاركة ضمن لجنة دراسة طلبات عروض الأثمان المتعلقة ب: {a['objet']}", apres=4)
        para(d, f"بتاريخ {tx.date_chiffres(a['date_commission'])} على الساعة {a['heure_commission']}.", apres=20)
        _signatures(d, ["إمضاء رئيس الجمعية"])


def _doc_pv_commission(conn, d, a, ctx):
    if not a["fournisseur_id"]:
        raise ErreurAchat("سجل العروض واختيار اللجنة أولاً.")
    os_ = offres(conn, a["id"])
    choisi = next(o for o in os_ if o["fournisseur_id"] == a["fournisseur_id"])
    _entete_asso(d, ctx)
    para(d, "محضر اجتماع لجنة دراسة عروض الأثمان", gras=True, taille=19, centre=True, apres=0)
    p = para(d, centre=True, apres=10)
    ajouter(p, "رقم ", gras=True)
    ajouter(p, _numero(conn, a, "pv_commission"))
    para(d, f"اجتمعت لجنة البت في عروض الأثمان لجمعية دعم مدرسة النجاح ب{ctx['etab']}", apres=2)
    para(d, f"بتاريخ {tx.date_chiffres(a['date_commission'])} على الساعة {a['heure_commission']}، وقد حضر الاجتماع:",
         apres=2)
    for nom, q in membres(a):
        para(d, f"السيد(ة) {nom}: {q}؛", apres=0)
    if a["absents"]:
        para(d, f"في حين تغيب السادة: {a['absents']}؛", apres=2)
    para(d, f"وذلك من أجل البت في طلبات عرض الأثمان عدد {a['nb_demandes']} بتاريخ {tx.date_chiffres(a['date_demande'])} "
            f"والمتعلقة ب: {a['objet']}.", apres=4)
    para(d, "عند افتتاح الجلسة تلا رئيسها لائحة المتنافسين المتوصل بعروضهم في الأجل سواء بواسطة البريد المضمون أو "
            "التي تم إيداعها مقابل إيصالات لدى إدارة الجمعية.", apres=2)
    para(d, "وتم حصر لائحة المتنافسين في:", apres=0)
    for o in sorted(os_, key=lambda o: o["nom"]):
        para(d, f"- {o['nom']}", apres=0)
    para(d, "بعد ذلك شرع في دراسة الأثمان المدلى بها في طلبات المتنافسين حيث أسفرت الدراسة عن النتائج المتضمنة "
            "في الجدول الآتي:", apres=4)
    t = tableau(d, 2 + len(os_), 3, largeurs=[5.2, 3.4, 8.8])
    t.cell(0, 0).merge(t.cell(1, 0))
    _cellule(t.cell(0, 0), "المتنافسون", gras=True)
    t.cell(0, 1).merge(t.cell(0, 2))
    _cellule(t.cell(0, 1), "العروض المالية", gras=True)
    _cellule(t.cell(1, 1), "بالأرقام", gras=True, taille=12)
    _cellule(t.cell(1, 2), "بالحروف", gras=True, taille=12)
    for i, o in enumerate(os_, start=2):
        _cellule(t.cell(i, 0), o["nom"], taille=12)
        _cellule(t.cell(i, 1), dh(o["montant"]), taille=12)
        _cellule(t.cell(i, 2), tx.montant_lettres_ar(o["montant"]), taille=12)
    para(d, apres=4)
    para(d, f"وبعد المداولة ومقارنة عروض الأثمان من جهة مع المواصفات المحددة في طلب عروض الأثمان، وقع اختيار "
            f"اللجنة على عرض المتنافس: {choisi['nom']}، والذي قدم العرض المالي البالغ قدره: "
            f"{dh(choisi['montant'])} درهما ({tx.montant_lettres_ar(choisi['montant'])}).", apres=4)
    if a["justification"]:
        para(d, "اعتمدت اللجنة العرض الأكثر نفعاً (Le mieux disant) بغض النظر عن الأقل ثمناً، وتبرير ذلك بمقياس "
                f"الجودة/الثمن: {a['justification']}", apres=4)
    para(d, f"حرر ب{ctx['ville']} في {tx.date_chiffres(a['date_commission'])}", apres=8)
    para(d, "توقيعات أعضاء اللجنة", gras=True, apres=2)
    m = membres(a)
    t = tableau(d, 1 + len(m), 2, largeurs=[8.7, 8.7])
    _cellule(t.cell(0, 0), "أسماء أعضاء اللجنة", gras=True)
    _cellule(t.cell(0, 1), "التوقيعات", gras=True)
    for i, (nom, q) in enumerate(m, start=1):
        _cellule(t.cell(i, 0), f"{nom} ({q})", taille=13)
        t.rows[i].height = Cm(1.2)


def _doc_bon_commande(conn, d, a, ctx):
    if not a["date_bc"]:
        raise ErreurAchat("سجل تاريخ سند الطلب أولاً (بعد اختيار العرض وتحديد الأثمان).")
    f = fournisseur(conn, a["fournisseur_id"])
    if not f.adresse:
        raise ErreurAchat("عنوان الممون غير مسجل (بيانات الممون).")
    _entete_asso(d, ctx)
    _titre(d, "رقم سند الطلب", "Bon de Commande N°", _numero(conn, a, "bon_commande"), ctx["e"]["libelle"])
    for ar, fr, v in (("إسم الممون", "Nom et Prénom du fournisseur", f.nom), ("عنوان الممون", "Adresse", f.adresse)):
        p = para(d, apres=2)
        ajouter(p, f"{ar} ({ltr(fr)}): ", gras=True)
        ajouter(p, v)
    if a["mode"] == "convention":
        para(d, f"في إطار الاتفاقية رقم {_numero(conn, a, 'convention')} بتاريخ {tx.date_chiffres(a['date_convention'])}",
             apres=2)
    para(d, f"الموضوع: {a['objet']}", apres=6)
    _table_articles(d, articles(conn, a["id"]), True, tot=totaux(conn, a["id"]))
    _fait(d, ctx, a["date_bc"])
    _signatures(d, ["أمين المال أو الشخص المفوض له"])


def _doc_bon_livraison(conn, d, a, ctx):
    if not a["date_livraison"]:
        raise ErreurAchat("سجل تاريخ التسليم أولاً.")
    _bloc_fournisseur(d, fournisseur(conn, a["fournisseur_id"]))
    _titre(d, "رقم سند التسليم", "Bon de Livraison N°", _numero(conn, a, "bon_livraison"), ctx["e"]["libelle"],
           f"سند الطلب رقم {_numero(conn, a, 'bon_commande')} بتاريخ {tx.date_chiffres(a['date_bc'])}")
    _table_articles(d, articles(conn, a["id"]), False)
    _fait(d, ctx, a["date_livraison"])
    _signatures(d, ["توقيع الممون", "توقيع المسؤول عن مخزن الجمعية (أمين المال)"])


def _doc_convention(conn, d, a, ctx):
    if not a["date_convention"]:
        raise ErreurAchat("سجل تاريخ الاتفاقية مع تاريخ الطلب أولاً.")
    f = fournisseur(conn, a["fournisseur_id"])
    manque = [lib for lib, v in (("المتصرف باسمه أو نيابة عن", f.represente_par), ("رقم البطاقة الوطنية", f.cin),
                                 ("محل الإقامة", f.adresse), ("الحساب البنكي", f.compte_bancaire)) if not v]
    if manque:
        raise ErreurAchat("بيانات المكلف بالأعمال ناقصة: " + "، ".join(manque) + ".")
    president = ctx["a"]["president"]
    if not president:
        raise ErreurAchat("اسم رئيس الجمعية غير مسجل (معطيات الجمعية).")
    num = _numero(conn, a, "convention")
    t = tableau(d, 1, 1, largeurs=[16])
    c = t.cell(0, 0)
    c.paragraphs[0]._element.getparent().remove(c.paragraphs[0]._element)
    p = para(c, centre=True)
    ajouter(p, "الاتفاقية رقم ", gras=True, taille=20)
    ajouter(p, num, gras=True, taille=18)
    para(c, "المبرمة بين:", gras=True, centre=True)
    para(c, f"- جمعية دعم مدرسة النجاح للمؤسسة التعليمية: {ctx['etab']}")
    para(c, f"- والمكلف(ة) بالأعمال السيد(ة): {f.nom}", apres=6)
    para(d, apres=6)
    para(d, "الموضوع:", gras=True, souligne=True, centre=True)
    para(d, a["objet"], centre=True, apres=14)
    para(d, "تم إبرام هذه الاتفاقية وفقاً لقواعد القانون العام", gras=True)
    para(d, "بين الموقعين أسفله:", gras=True, souligne=True)
    para(d, f"رئيس جمعية دعم مدرسة النجاح للمؤسسة التعليمية: {ctx['etab']}، السيد(ة) {president}")
    para(d, "(المشار إليه فيما يلي باسم «رئيس الجمعية») من جهة،", taille=12, apres=8)
    para(d, "والسيد(ة):", gras=True, souligne=True)
    for lib, v in (("الاسم والنسب", f.nom), ("المتصرف باسمه أو نيابة عن", f.represente_par),
                   ("الحامل للبطاقة الوطنية رقم", ltr(f.cin)), ("محل إقامته في", f.adresse),
                   ("المسجل في السجل التجاري تحت رقم", ltr(f.rc) if f.rc else "—"),
                   ("المنخرط ب CNSS تحت رقم", ltr(f.cnss) if f.cnss else "—"),
                   ("صاحب الحساب البنكي المفتوح في البنك أو بمدينة رقم", ltr(f.compte_bancaire)),
                   ("الحامل للضريبة المهنية رقم", ltr(f.patente) if f.patente else "—"),
                   ("تعريفه الضريبي رقم", ltr(f.ice) if f.ice else "—")):
        p = para(d, apres=1)
        ajouter(p, f"- {lib}: ", gras=True)
        ajouter(p, v)
    para(d, "(المشار إليه فيما يلي باسم «المكلف بأعمال») من جهة أخرى،", taille=12, apres=4)
    para(d, "تقرر الاتفاق على ما يلي:", gras=True, apres=6)
    articles_txt = [
        ("المادة 1: موضوع الاتفاقية", [f"الغرض من هذه الاتفاقية هو: {a['objet']} ({a['service_type']})."]),
        ("المادة 2: مكان التنفيذ", ["يتم إنجاز الأعمال موضوع الاتفاقية داخل المؤسسة التعليمية المشار إليها أعلاه أو "
                                    "في الأماكن التي يحددها رئيس الجمعية."]),
        ("المادة 3: مدة سريان الاتفاقية وتاريخ الشروع في تنفيذها", [
            "يتم عقد هذه الاتفاقية لمدة سنة كاملة قابلة للتجديد الضمني لمدة سنتين شريطة ألا تتجاوز مدتها 03 ثلاث سنوات.",
            "ويجب أن تبدأ الخدمات التي تغطيها هذه الاتفاقية من اليوم التالي للإخطار بأمر الخدمة الذي ينص على بدء "
            "إنجاز الخدمات ومدة الإنجاز.",
            "ستكون هذه الاتفاقية نهائية وقابلة للتنفيذ فقط بعد أن يتم التوقيع عليها من قبل الطرفين."]),
        ("المادة 4: مراجعة الأثمان", ["أثمان هذه الاتفاقية ثابتة ولا تخضع للمراجعة."]),
        ("المادة 5: إجراءات وشكليات الأداء", [
            "يتم أداء المبالغ المستحقة في إطار هذه الاتفاقية سواء عن طريق التحويل البنكي أو بواسطة الشيك، وفي مقابل "
            "الخدمات المنجزة فعلياً مع تطبيق الأثمان الواردة بالجدول التفصيلي للأثمان، أو عرض الأثمان المقدم من طرف "
            "المكلف بالأعمال."]),
        ("المادة 7: النزاعات وفسخ الاتفاقية", [
            "يجب أن تخضع النزاعات التي قد تنشأ أثناء تنفيذ هذه الاتفاقية، والتي لم يتم حلها بالوسائل الرضائية، "
            "للمحاكم المختصة بمكان تواجد المؤسسة أو المدينة الأقرب عند التعذر.",
            "ولكل طرف الحرية في طلب فسخ وإنهاء هذه الاتفاقية في أي وقت، طواعية، ودون أي تعويض، بشرط أن يتم توجيه "
            "إخبار بذلك في محرر مكتوب قبل 30 يوماً إلى الطرف الآخر في الاتفاقية. كما يتم فسخ هذه الاتفاقية عندما "
            "يتعذر تنفيذها بسبب الظروف غير المتوقعة أو القوة القاهرة."]),
        ("المادة 8: طبيعة كميات الخدمات المطلوبة", [
            "يقوم رئيس الجمعية بإخطار المكلف بالأعمال بأي وسيلة مثبتة (محرر مكتوب، فاكس، بريد إلكتروني ...)، مبينة "
            "تحديد كميات الخدمات المطلوبة والتواريخ والأوقات وكافة التفاصيل اللازمة لحسن التسليم أو الإنجاز."]),
        ("المادة 9: مراقبة الجودة والكميات المنجزة", [
            "يجوز لرئيس الجمعية، إذا لزم الأمر، تعيين لجنة تكون مهمتها مراقبة جودة الخدمات المنجزة أو الكميات "
            "المسلمة والحكم على جودتها ومدى مطابقتها للمواصفات المطلوبة.",
            "يمكن إجراء هذه المراقبة في أماكن العمل الخاصة بالمكلف بالأعمال أو عند التسليم.",
            "يتم الإبلاغ عن أي نقص أو عيب تمت ملاحظتها من أجل التصحيح أو الاستبدال أو التقويم للمكلف بالأعمال الذي "
            "يجب أن يتفاعل معها ويتدخل بشكل عاجل قدر الإمكان وبأكثر الطرق كفاءة في أجل لا يتعدى 48 ساعة. إذا عجز "
            "المكلف بالأعمال عن الوفاء بالالتزامات المشار إليه أعلاه، الموكلة إليه، فسيتم إرسال جميع الإعذارات "
            "المتعلقة بهذه الاتفاقية إليه بشكل صحيح في محل إقامته.",
            "لا يتم أداء أي خدمة من قبل رئيس الجمعية لا يتم إنجازها من طرف المكلف بالأعمال وفقاً لقواعد الفن، ودون "
            "أي شكوى أو تعرض من طرفه."]),
        ("المادة 10: المستندات التي ينبغي الإدلاء بها قصد الأداء", [
            "تتم الأداءات مقابل الخدمات الناتجة عن هذه الاتفاقية عند تقديم سند تسليم وفاتورة أو مذكرة أتعاب توضح "
            "بالتفصيل الخدمات المنجزة أو الكميات المقدمة."]),
    ]
    for titre, alineas in articles_txt:
        para(d, titre, gras=True, apres=2)
        for al in alineas:
            para(d, al, taille=14, apres=3)
    para(d, "المادة 11: جدول الأثمان", gras=True, apres=2)
    arts = articles(conn, a["id"])
    t = tableau(d, 1 + len(arts), 4, largeurs=[1.6, 9.0, 3.0, 3.8])
    for j, lib in enumerate(("الرقم", "الخدمة", "الوحدة", "الثمن")):
        _cellule(t.cell(0, j), lib, gras=True)
    for i, r in enumerate(arts, start=1):
        for j, v in enumerate((f"{i:02d}", r["designation"], r["unite"] or "—", dh(r["prix_unitaire"]))):
            _cellule(t.cell(i, j), v, taille=13, centre=j != 1)
    saut_page(d)
    para(d, "الصفحة الأخيرة من الاتفاقية", gras=True, souligne=True, centre=True, apres=6)
    p = para(d, centre=True, apres=8)
    ajouter(p, "رقم: ", gras=True, taille=18)
    ajouter(p, num, gras=True, taille=18)
    para(d, "الموضوع:", gras=True, souligne=True)
    para(d, a["objet"], apres=8)
    tt = totaux(conn, a["id"])
    para(d, "حصر مبلغها في:", gras=True, souligne=True)
    para(d, f"بالأرقام: {dh(tt['ttc'])} {ltr('DHS TTC')}")
    para(d, f"بالحروف: {tx.montant_lettres_ar(tt['ttc'])} {ltr('DHS TTC')}", apres=8)
    para(d, f"حرر في {ctx['ville']} بتاريخ: {tx.date_chiffres(a['date_convention'])}", apres=10)
    t = tableau(d, 1, 2, bordures=False, largeurs=[8.7, 8.7])
    _cellule(t.cell(0, 0), "توقيع وطابع رئيس الجمعية", gras=True)
    c = t.cell(0, 1)
    _cellule(c, "توقيع وطابع المكلف بالأعمال", gras=True)
    para(c, "(قرئ وصودق عليه بخط اليد)", taille=12, centre=True)
    para(c, "بتاريخ: ....................", taille=12, centre=True)


def _doc_pv_service(conn, d, a, ctx):
    if not a["date_livraison"]:
        raise ErreurAchat("سجل تاريخ إنجاز الخدمة ولجنة التسليم أولاً.")
    f = fournisseur(conn, a["fournisseur_id"])
    para(d, "محضر إنجاز الخدمة والمطابقة", gras=True, taille=20, centre=True, apres=8)
    com = [tuple(x) for x in json.loads(a["commission_reception"] or "[]")]
    lignes = [("محضر رقم: ", _numero(conn, a, "pv_service")),
              ("حرر المحضر في: ", f"{ctx['ville']} — تاريخ المحضر: {tx.date_chiffres(a['date_livraison'])}"),
              ("اسم المؤسسة: ", ctx["etab"]), ("رقم الاتفاقية: ", _numero(conn, a, "convention")),
              ("موضوع الاتفاقية: ", a["objet"]), ("المكلف(ة) بالأعمال: ", f.nom),
              ("رقم الطلب: ", _numero(conn, a, "bon_commande")), ("موضوع الطلب: ", a["objet"])]
    t = tableau(d, 1, 1, largeurs=[17.4])
    c = t.cell(0, 0)
    c.paragraphs[0]._element.getparent().remove(c.paragraphs[0]._element)
    for lib, v in lignes:
        p = para(c, apres=1)
        ajouter(p, lib, gras=True, taille=14)
        ajouter(p, v, taille=14)
    para(c, "اللجنة المكلفة بعملية التسليم الجزئي أو الكلي للخدمة (الممثلين عن المؤسسة):", gras=True, taille=14)
    for nom, q in com:
        para(c, f"الاسم الكامل والصفة: {nom}، {q}", taille=14, apres=0)
    para(c, "المكلف(ة) بالأعمال:", gras=True, taille=14)
    para(c, f"الاسم الكامل والصفة: {f.represente_par or f.nom}", taille=14)
    para(d, "التسليم الجزئي أو الكلي للخدمة", gras=True, centre=True, apres=2)
    para(d, "الجدول أدناه يصف الخدمات التي تم جردها وقبولها:", apres=2)
    arts = articles(conn, a["id"])
    t = tableau(d, 1 + len(arts), 5, largeurs=[1.4, 8.0, 2.4, 2.0, 3.6])
    for j, lib in enumerate(("الرقم", "الخدمة", "الوحدة", "الكمية", "الإنجاز والمطابقة")):
        _cellule(t.cell(0, j), lib, gras=True, taille=13)
    for i, r in enumerate(arts, start=1):
        for j, v in enumerate((f"{i:02d}", r["designation"], r["unite"] or "—", f"{r['quantite']:g}", "مطابق")):
            _cellule(t.cell(i, j), v, taille=13, centre=j != 1)
    para(d, apres=4)
    para(d, "إنجاز الخدمة والمطابقة", gras=True, centre=True, apres=2)
    para(d, "نحن الموقعون أسفله، نشهد بأن الخدمات المشار إليها أعلاه قد تم إنجازها وتسليمها طبقاً للمواصفات المتضمنة "
            "في بنود الاتفاقية والطلب المقدم للمكلف(ة) بالأعمال.", apres=6)
    para(d, f"التاريخ: {tx.date_chiffres(a['date_livraison'])}", gras=True)
    para(d, "التواقيع:", gras=True, apres=4)
    t = tableau(d, len(com) + 1, 2, largeurs=[10.4, 7.0])
    for i, (nom, q) in enumerate(com + [(f.represente_par or f.nom, "المكلف(ة) بالأعمال")]):
        _cellule(t.cell(i, 0), f"{nom} — {q}", taille=13, centre=False)
        t.rows[i].height = Cm(1.3)


_FABRIQUES = {"demande_devis": _doc_demande_devis, "modele_devis": _doc_modele_devis,
              "invitations": _doc_invitations, "pv_commission": _doc_pv_commission,
              "bon_commande": _doc_bon_commande, "bon_livraison": _doc_bon_livraison,
              "convention": _doc_convention, "pv_service": _doc_pv_service}


def documents_possibles(a) -> list[str]:
    return [k for k, (_, _, modes) in DOCUMENTS.items() if a["mode"] in modes]


def generer(conn, dossier: DossierDonnees, aid: int, code: str) -> Path:
    a = achat(conn, aid)
    if code not in documents_possibles(a):
        raise ErreurAchat("هذه الوثيقة لا تخص آلية الصرف المختارة.")
    ctx = _ctx(conn, a)
    d = _nouveau()
    _FABRIQUES[code](conn, d, a, ctx)
    titre = DOCUMENTS[code][0].split(" (")[0]
    return da._enregistrer(d, dossier, ctx["e"]["libelle"], "الصرف", f"{titre} - ملف {aid}")


# ---------- المداخيل العينية والمساعدات الأجنبية ----------

def recu_equipement(conn, dossier: DossierDonnees, eid: int, date_don: str, donateur: str,
                    description: str) -> Path:
    """وصل تسلم تجهيز (الملحق 14)، مرقم داخل السنة المالية. التجهيز يُسجل بعد ذلك بدفتر الجرد."""
    e = asso.exercice(conn, eid)
    _d(date_don, "تاريخ التسلم")
    if not e["date_debut"] <= date_don <= e["date_fin"]:
        raise ErreurAchat("التاريخ خارج السنة المالية.")
    if not _txt(donateur) or not _txt(description):
        raise ErreurAchat("الجهة المانحة ومواصفات التجهيز إجباريتان.")
    try:
        ctx = da._contexte(conn, eid)
    except da.ErreurDocAssociation as err:
        raise ErreurAchat(str(err)) from None
    if not ctx["a"]["tresorier"]:
        raise ErreurAchat("اسم أمين المال غير مسجل (معطيات الجمعية).")
    with conn:
        n = conn.execute("SELECT COALESCE(MAX(numero),0)+1 FROM don_nature WHERE exercice_id=?", (eid,)).fetchone()[0]
        conn.execute("INSERT INTO don_nature(exercice_id, numero, date_don, donateur, description) VALUES (?,?,?,?,?)",
                     (eid, n, date_don, _txt(donateur), description.strip()))
    d = _nouveau()
    cadre = tableau(d, 1, 1, largeurs=[14.5])
    c = cadre.cell(0, 0)
    c.paragraphs[0]._element.getparent().remove(c.paragraphs[0]._element)
    da._entete_piece(c, ctx, date_don)
    para(c, "وصل تسلم تجهيز", gras=True, taille=20, centre=True, souligne=True)
    para(c, f"رقم {ltr(f'{n:02d}/' + ctx['code'])}", gras=True, centre=True, apres=10)
    for lib, v in (("أنا الموقع أسفله: ", ctx["a"]["tresorier"]), ("بصفتي: ", "أمين مال الجمعية"),
                   ("أشهد أني تسلمت من: ", _txt(donateur)), ("التجهيز التالي (المواصفات): ", "")):
        p = para(c, apres=3)
        ajouter(p, lib, gras=True)
        ajouter(p, v)
    for ligne in description.strip().splitlines():
        para(c, ligne, apres=1)
    para(c, apres=10)
    para(c, "الإمضاء:", gras=True, apres=40)
    return da._enregistrer(d, dossier, e["libelle"], "المداخيل العينية", f"وصل تسلم تجهيز {n:02d}")


def dons(conn, eid: int) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM don_nature WHERE exercice_id=? ORDER BY numero", (eid,)).fetchall()


def declaration_aide_etrangere(conn, dossier: DossierDonnees, eid: int, date_reception: str, aides: list[str],
                               affectation: str, date_redaction: str | None = None) -> tuple[Path, str | None]:
    """التصريح لدى الأمانة العامة للحكومة (الملحق 15)، داخل أجل 30 يوماً من تاريخ التوصل بالمساعدة."""
    e = asso.exercice(conn, eid)
    dr = _d(date_reception, "تاريخ التوصل بالمساعدة")
    date_redaction = date_redaction or date.today().isoformat()
    dd = _d(date_redaction, "تاريخ التحرير")
    aides = [_txt(x) for x in aides if _txt(x)]
    if not aides or not _txt(affectation):
        raise ErreurAchat("المساعدات المتوصل بها وتخصيصها إجباريان.")
    ctx = _ctx(conn, {"exercice_id": eid})
    president = ctx["a"]["president"]
    if not president:
        raise ErreurAchat("اسم رئيس الجمعية غير مسجل (معطيات الجمعية).")
    alerte = None
    if (dd - dr).days > 30:
        alerte = (f"تنبيه: مر {(dd - dr).days} يوماً على التوصل بالمساعدة، والدليل يحدد أجل التصريح في ثلاثين يوماً.")
    nom = ctx["a"]["nom"]
    d = _nouveau()
    for lib, v in (("اسم الجمعية: ", f"{nom} ب{ctx['etab']}"), ("العنوان: ", ctx["adresse"])):
        p = para(d, apres=0)
        ajouter(p, lib, gras=True)
        ajouter(p, v)
    para(d, apres=10)
    para(d, "رئيس الجمعية المسماة", gras=True, centre=True, apres=0)
    para(d, f"«{nom}»", gras=True, centre=True, apres=10)
    for l in ("إلى", "السيد الأمين العام للحكومة", "مديرية الجمعيات والمهن المنظمة، حي الوزارات", "الرباط"):
        para(d, l, gras=True, centre=True, apres=0)
    para(d, apres=10)
    p = para(d, apres=8)
    ajouter(p, "الموضوع: ", gras=True)
    ajouter(p, "التصريح بتلقي الجمعية لمساعدة أجنبية.")
    para(d, f"وبعد، عملاً بمقتضيات الفصل 32 مكرر من الظهير الشريف رقم {ltr('1.58.376')} الصادر بتاريخ 3 جمادى "
            f"الأولى 1378 الموافق ل 15 نونبر 1958 بتنظيم حق تأسيس الجمعيات كما وقع تتميمه وتغييره؛", apres=6)
    para(d, f"يشرفني أن أصرح لديكم بتلقي الجمعية المسماة «{nom}» بتاريخ {tx.date_chiffres(date_reception)}", apres=2)
    para(d, "بالمساعدات التالية:", gras=True, apres=2)
    for x in aides:
        para(d, f"- {x}", apres=0)
    para(d, f"وقد تم تخصيص هذه المساعدات ل{_txt(affectation)}.", apres=8)
    para(d, "وتفضلوا، السيد الأمين العام للحكومة، بقبول عبارات التقدير والاحترام.", apres=8)
    para(d, f"حرر ب{ctx['ville']} في {tx.date_chiffres(date_redaction)}", apres=6)
    _signatures(d, [f"رئيس الجمعية: {president}"])
    p = para(d)
    ajouter(p, "المرفقات: ", gras=True)
    ajouter(p, "نسخة من بيان كشف الحساب المتعلق بالمساعدة المذكورة.")
    return da._enregistrer(d, dossier, e["libelle"], "مراسلات", "التصريح بتلقي مساعدة أجنبية"), alerte
