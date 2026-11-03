"""التدبير المالي للجمعيات، على نموذج المدير (قاعدة Access لجمعية دعم مدرسة النجاح).

- الأبواب والبنود (المداخيل والمصاريف) وملاحظاتها من نموذج المدير.
- العمليات: التاريخ، النوع (مدخول، مصروف، تحويل بين الصندوقين)، السجل (البنك أو الصندوق)، البند، المبلغ، المرجع.
- المنقول من السنة المالية السابقة يُسجل عملية مدخول (كما في نموذج المدير)، ويُولد آلياً عند فتح سنة مالية جديدة.
- السجلات (البنك، الصندوق، اليومية، تنفيذ الميزانية) تُصدَّر إلى Excel للطباعة؛ نماذجها الرسمية تُضاف حين يوفرها المدير.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path

REGISTRES = {"banque": "البنك", "caisse": "الصندوق"}
NATURES = {"recette": "مدخول", "depense": "مصروف", "transfert": "تحويل بين الصندوقين"}
REPORT = "المنقول من السنة المالية السابقة"


class ErreurAssociation(ValueError):
    """رسالة موجهة للمدير بالعربية."""


def _d(v: str, lib: str) -> date:
    try:
        return date.fromisoformat(v)
    except (TypeError, ValueError):
        raise ErreurAssociation(f"{lib} غير صحيح.") from None


def association(conn, type_: str = "najah") -> sqlite3.Row:
    return conn.execute("SELECT * FROM association WHERE type=?", (type_,)).fetchone()


def modifier_association(conn, type_: str, rib: str = "", president: str = "", tresorier: str = "",
                         date_renouvellement: str = "") -> None:
    if date_renouvellement:
        _d(date_renouvellement, "تاريخ التجديد")
    rib = rib.replace(" ", "")
    if rib and not rib.isdigit():
        raise ErreurAssociation("رقم الحساب (RIB) أرقام فقط.")
    with conn:
        conn.execute("UPDATE association SET rib=?, president=?, tresorier=?, date_renouvellement=? WHERE type=?",
                     (rib or None, president.strip() or None, tresorier.strip() or None,
                      date_renouvellement or None, type_))


def rubriques(conn, type_: str = "najah", sens: str | None = None, actifs: bool = False) -> list[sqlite3.Row]:
    """أبواب وبنود الملحق 1 من الدليل المسطري؛ actifs: دون البنود التي لم تعد واردة فيه."""
    sql, args = "SELECT * FROM rubrique WHERE type_association=?" + (" AND actif=1" if actifs else ""), [type_]
    if sens:
        sql += " AND sens=?"
        args.append(sens)
    return conn.execute(sql + " ORDER BY ordre", args).fetchall()


def _rubrique_report(conn, type_: str) -> int:
    r = conn.execute("SELECT id FROM rubrique WHERE type_association=? AND sens='recette' AND ligne=?",
                     (type_, REPORT)).fetchone()
    if r is None:
        raise ErreurAssociation("بند «المنقول من السنة المالية السابقة» غير موجود.")
    return r[0]


# ---------- السنوات المالية ----------

def exercices(conn, type_: str = "najah") -> list[sqlite3.Row]:
    return conn.execute("SELECT e.* FROM exercice e JOIN association a ON a.id=e.association_id WHERE a.type=? "
                        "ORDER BY e.date_debut DESC", (type_,)).fetchall()


def ouvrir_exercice(conn, type_: str, libelle: str, debut: str, fin: str,
                    report_banque: float | None = None, report_caisse: float | None = None,
                    reference: str = "") -> int:
    """يفتح سنة مالية. المنقول: من رصيد السنة السابقة آلياً، أو المبالغ المدخلة (أول سنة في التطبيق)."""
    libelle = " ".join(libelle.split())
    if not libelle:
        raise ErreurAssociation("اسم السنة المالية إجباري.")
    d, f = _d(debut, "تاريخ البداية"), _d(fin, "تاريخ النهاية")
    if f <= d:
        raise ErreurAssociation("تاريخ النهاية قبل تاريخ البداية.")
    a = association(conn, type_)
    chevauche = conn.execute("SELECT libelle FROM exercice WHERE association_id=? AND date_debut<=? AND date_fin>=?",
                             (a["id"], fin, debut)).fetchone()
    if chevauche:
        raise ErreurAssociation(f"تتداخل مع السنة المالية {chevauche[0]}.")
    precedent = conn.execute("SELECT id FROM exercice WHERE association_id=? AND date_fin<? ORDER BY date_fin DESC "
                             "LIMIT 1", (a["id"], debut)).fetchone()
    if precedent:
        # المنقول = رصيد السنة السابقة دائماً (ويُحيَّن آلياً إذا عُدلت عملياتها)
        s = soldes(conn, precedent[0])
        report_banque, report_caisse, reference = s["banque"], s["caisse"], "رصيد السنة المالية السابقة"
    montants = {"banque": _montant_report(report_banque), "caisse": _montant_report(report_caisse)}
    _rubrique_report(conn, type_)
    try:
        with conn:  # السنة والمنقول معاً: لا تُفتح سنة دون منقولها
            eid = conn.execute("INSERT INTO exercice(association_id, libelle, date_debut, date_fin) VALUES (?,?,?,?)",
                               (a["id"], libelle, debut, fin)).lastrowid
            _ecrire_report(conn, eid, montants, reference)
            _propager(conn, eid)
    except sqlite3.IntegrityError:
        raise ErreurAssociation("سنة مالية بنفس الاسم موجودة.") from None
    return eid


def _montant_report(v) -> float:
    try:
        m = round(float(str(v or 0).replace(",", ".").replace(" ", "").replace(" ", "")), 2)
    except ValueError:
        raise ErreurAssociation("مبلغ المنقول غير صحيح.") from None
    if m < 0:
        raise ErreurAssociation("مبلغ المنقول لا يكون سالباً.")
    return m


def _voisin(conn, eid: int, sens: str) -> int | None:
    e = exercice(conn, eid)
    if sens == "precedent":
        sql = "SELECT id FROM exercice WHERE association_id=? AND date_fin<? ORDER BY date_fin DESC LIMIT 1"
        arg = e["date_debut"]
    else:
        sql = "SELECT id FROM exercice WHERE association_id=? AND date_debut>? ORDER BY date_debut LIMIT 1"
        arg = e["date_fin"]
    r = conn.execute(sql, (e["association_id"], arg)).fetchone()
    return r[0] if r else None


def report(conn, eid: int) -> dict[str, float]:
    """المنقول المسجل في بداية السنة المالية، لكل سجل."""
    rid = _rubrique_report(conn, exercice(conn, eid)["type"])
    s = {"banque": 0.0, "caisse": 0.0}
    for r in conn.execute("SELECT registre, SUM(montant) FROM operation_financiere WHERE exercice_id=? AND "
                          "rubrique_id=? GROUP BY registre", (eid, rid)):
        s[r[0]] = round(r[1], 2)
    return s


def _ecrire_report(conn, eid: int, montants: dict[str, float], reference: str = "") -> bool:
    """يكتب عمليات المنقول (داخل معاملة مفتوحة، دون حفظ). يرجع True إذا تغير شيء."""
    e = exercice(conn, eid)
    rid = _rubrique_report(conn, e["type"])
    change = False
    for reg in REGISTRES:
        m = round(montants.get(reg) or 0, 2)
        ops = conn.execute("SELECT id, montant FROM operation_financiere WHERE exercice_id=? AND rubrique_id=? AND "
                           "registre=? ORDER BY numero", (eid, rid, reg)).fetchall()
        if len(ops) == 1 and abs(ops[0]["montant"] - m) < 0.005:
            continue
        if not ops and m <= 0:
            continue
        change = True
        garder = ops[0]["id"] if ops and m > 0 else None
        for o in ops:
            if o["id"] == garder:
                continue
            if conn.execute("SELECT 1 FROM piece_association WHERE operation_id=?", (o["id"],)).fetchone():
                raise ErreurAssociation("صدر وصل لعملية المنقول: لا يمكن تعديلها.")
            conn.execute("DELETE FROM operation_financiere WHERE id=?", (o["id"],))
        ref = (reference or "").strip() or "محضر تسليم المهام / كشف الحساب"
        if garder:
            conn.execute("UPDATE operation_financiere SET montant=?, date_op=?, reference=? WHERE id=?",
                         (m, e["date_debut"], ref, garder))
        elif m > 0:
            num = conn.execute("SELECT COALESCE(MAX(numero),0)+1 FROM operation_financiere WHERE exercice_id=?",
                               (eid,)).fetchone()[0]
            conn.execute("INSERT INTO operation_financiere(exercice_id, numero, date_op, nature, registre, rubrique_id,"
                         " montant, reference, detail) VALUES (?,?,?,?,?,?,?,?,?)",
                         (eid, num, e["date_debut"], "recette", reg, rid, m, ref, f"المنقول — {REGISTRES[reg]}"))
    if change:
        neg = _premier_negatif(conn, eid)
        if neg:
            raise ErreurAssociation(f"بهذا المنقول يصير رصيد {REGISTRES[neg[0]]} سالباً بتاريخ {neg[1]} "
                                    f"(السنة المالية {e['libelle']}).")
        conn.execute("INSERT INTO journal(action, cible, cible_id, details) VALUES ('report','exercice',?,?)",
                     (eid, f"البنك {montants.get('banque') or 0} — الصندوق {montants.get('caisse') or 0}"))
    return change


def _propager(conn, eid: int) -> None:
    """ينقل رصيد كل سنة إلى منقول السنة الموالية (داخل المعاملة المفتوحة)."""
    suivant = _voisin(conn, eid, "suivant")
    while suivant is not None:
        _ecrire_report(conn, suivant, soldes(conn, eid), "رصيد السنة المالية السابقة")
        eid, suivant = suivant, _voisin(conn, suivant, "suivant")


def modifier_report(conn, eid: int, banque, caisse, reference: str = "") -> None:
    """تعديل المنقول يدوياً: لأول سنة مالية في التطبيق فقط (الموالية تأخذ رصيد السابقة)."""
    if _voisin(conn, eid, "precedent") is not None:
        raise ErreurAssociation("المنقول في هذه السنة هو رصيد السنة المالية السابقة، ويُحيَّن آلياً.")
    m = {"banque": _montant_report(banque), "caisse": _montant_report(caisse)}
    with conn:
        _ecrire_report(conn, eid, m, reference)
        _propager(conn, eid)


def peut_modifier_report(conn, eid: int) -> bool:
    return _voisin(conn, eid, "precedent") is None


def explication_report(conn, eid: int) -> str:
    """لماذا لا يُعدل منقول سنة موالية يدوياً، وأين يُصحح."""
    p = _voisin(conn, eid, "precedent")
    if p is None:
        return ""
    return (f"المنقول في هذه السنة هو رصيد السنة المالية {exercice(conn, p)['libelle']} ويُحيَّن آلياً. إذا كان فيه "
            "خطأ، فصحح عمليات تلك السنة (تعديل العملية أو حذفها) أو منقولها إن كانت أول سنة.")


def synchroniser(conn, type_: str = "najah") -> list[str]:
    """يصحح منقول كل سنة من رصيد السابقة (بيانات سُجلت قبل التحيين الآلي). يرجع التنبيهات."""
    ex = sorted(exercices(conn, type_), key=lambda e: e["date_debut"])
    if not ex:
        return []
    try:
        with conn:
            _propager(conn, ex[0]["id"])
    except ErreurAssociation as err:
        return [str(err)]
    return []


def exercice(conn, eid: int) -> sqlite3.Row:
    r = conn.execute("SELECT e.*, a.type FROM exercice e JOIN association a ON a.id=e.association_id WHERE e.id=?",
                     (eid,)).fetchone()
    if r is None:
        raise ErreurAssociation("السنة المالية غير موجودة.")
    return r


# ---------- العمليات ----------

@dataclass
class Operation:
    exercice_id: int
    date_op: str
    nature: str
    registre: str
    montant: float | str
    rubrique_id: int | None = None
    reference: str = ""
    detail: str = ""
    observation: str = ""
    id: int | None = None
    tiers: str = ""           # المؤدي أو المستفيد (للوصولات والسندات)
    tiers_qualite: str = ""


def _effet(nature: str, registre: str, montant: float) -> dict[str, float]:
    """أثر العملية على كل سجل."""
    if nature == "recette":
        return {registre: montant}
    if nature == "depense":
        return {registre: -montant}
    autre = "caisse" if registre == "banque" else "banque"
    return {registre: -montant, autre: montant}


def soldes(conn, eid: int, jusqu_a: str | None = None, sauf: int | None = None) -> dict[str, float]:
    s = {"banque": 0.0, "caisse": 0.0}
    sql, args = "SELECT nature, registre, montant FROM operation_financiere WHERE exercice_id=? AND id IS NOT ?", [eid, sauf]
    if jusqu_a:
        sql += " AND date_op<=?"
        args.append(jusqu_a)
    for r in conn.execute(sql, args):
        for k, v in _effet(r["nature"], r["registre"], r["montant"]).items():
            s[k] += v
    return {k: round(v, 2) for k, v in s.items()}


def _premier_negatif(conn, eid: int, sauf: int | None = None,
                     ajout: tuple[str, dict[str, float]] | None = None) -> tuple[str, str] | None:
    """يحاكي الأرصدة بعد التعديل (دون الكتابة): أول (سجل، تاريخ) يصير فيه الرصيد سالباً."""
    mouvements = [(r["date_op"], _effet(r["nature"], r["registre"], r["montant"])) for r in conn.execute(
        "SELECT date_op, nature, registre, montant FROM operation_financiere WHERE exercice_id=? AND id IS NOT ?",
        (eid, sauf))]
    if ajout:
        mouvements.append(ajout)
    mouvements.sort(key=lambda m: m[0])
    solde = {"banque": 0.0, "caisse": 0.0}
    i = 0
    while i < len(mouvements):
        jour = mouvements[i][0]
        while i < len(mouvements) and mouvements[i][0] == jour:  # عمليات نفس اليوم معاً
            for k, v in mouvements[i][1].items():
                solde[k] += v
            i += 1
        for k, v in solde.items():
            if v < -1e-9:
                return k, jour
    return None


def _achat_lie(conn, op_id: int) -> str | None:
    r = conn.execute("SELECT objet FROM achat WHERE operation_id=?", (op_id,)).fetchone()
    return (r["objet"] or "ملف صرف") if r else None


def enregistrer(conn, op: Operation) -> int:
    e = exercice(conn, op.exercice_id)
    ancien = None
    if op.id is not None:
        ancien = conn.execute("SELECT * FROM operation_financiere WHERE id=?", (op.id,)).fetchone()
        if ancien is None or ancien["exercice_id"] != op.exercice_id:
            raise ErreurAssociation("العملية غير موجودة في هذه السنة المالية.")
        if ancien["rubrique_id"] == _rubrique_report(conn, e["type"]):
            raise ErreurAssociation("المنقول يُعدل بزر «تعديل المنقول».")
    if op.nature not in NATURES:
        raise ErreurAssociation("نوع العملية غير صحيح.")
    if op.registre not in REGISTRES:
        raise ErreurAssociation("السجل: البنك أو الصندوق.")
    try:
        montant = round(float(str(op.montant).replace(",", ".").replace(" ", "")), 2)
    except ValueError:
        raise ErreurAssociation("المبلغ غير صحيح.") from None
    if montant <= 0:
        raise ErreurAssociation("المبلغ يكون أكبر من صفر.")
    d = _d(op.date_op, "تاريخ العملية")
    if not e["date_debut"] <= op.date_op <= e["date_fin"]:
        raise ErreurAssociation(f"التاريخ خارج السنة المالية {e['libelle']} "
                                f"({e['date_debut']} — {e['date_fin']}).")
    if d > date.today():
        raise ErreurAssociation("تاريخ العملية في المستقبل.")
    if op.nature == "transfert":
        op.rubrique_id = None
    else:
        r = conn.execute("SELECT sens, actif, ligne FROM rubrique WHERE id=?", (op.rubrique_id,)).fetchone()
        if r is None:
            raise ErreurAssociation("اختر البند.")
        if not r["actif"] and op.id is None:
            raise ErreurAssociation("هذا البند لم يعد وارداً في الدليل المسطري (الملحق 1).")
        if r["sens"] != op.nature:
            raise ErreurAssociation("البند لا يناسب نوع العملية.")
        if r["ligne"] == REPORT:
            raise ErreurAssociation("المنقول يُسجل عند فتح السنة المالية أو بزر «تعديل المنقول».")
    if op.nature != "recette" and not (op.reference or "").strip():
        raise ErreurAssociation("مرجع المصروف أو التحويل إجباري (فاتورة، سند الطلب، كشف الحساب...).")
    if ancien is not None:
        change = (ancien["date_op"] != op.date_op or ancien["nature"] != op.nature or ancien["registre"] != op.registre
                  or ancien["rubrique_id"] != op.rubrique_id or abs(ancien["montant"] - montant) > 0.005)
        if change and conn.execute("SELECT 1 FROM piece_association WHERE operation_id=?", (op.id,)).fetchone():
            raise ErreurAssociation("صدرت لهذه العملية وثائق مرقمة (وصل أو سند): يمكن تصحيح المرجع والبيان والطرف "
                                    "المعني فقط. لتصحيح المبلغ أو التاريخ أو البند، سجل عملية معاكسة مع ذكر السبب.")
        lie = _achat_lie(conn, op.id)
        if change and lie:
            raise ErreurAssociation(f"هذه العملية أداء ملف الصرف «{lie}»: يمكن تصحيح المرجع والبيان فقط.")
    neg = _premier_negatif(conn, e["id"], op.id, (op.date_op, _effet(op.nature, op.registre, montant)))
    if neg:
        raise ErreurAssociation(f"رصيد {REGISTRES[neg[0]]} لا يكفي: يصير سالباً بتاريخ {neg[1]}.")
    vals = (op.date_op, op.nature, op.registre, op.rubrique_id, montant, (op.reference or "").strip() or None,
            (op.detail or "").strip() or None, (op.observation or "").strip() or None,
            " ".join((op.tiers or "").split()) or None, " ".join((op.tiers_qualite or "").split()) or None)
    with conn:
        if op.id is None:
            num = conn.execute("SELECT COALESCE(MAX(numero),0)+1 FROM operation_financiere WHERE exercice_id=?",
                               (e["id"],)).fetchone()[0]
            op.id = conn.execute(
                "INSERT INTO operation_financiere(exercice_id, numero, date_op, nature, registre, rubrique_id, montant,"
                " reference, detail, observation, tiers, tiers_qualite) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (e["id"], num, *vals)).lastrowid
        else:
            conn.execute("UPDATE operation_financiere SET date_op=?, nature=?, registre=?, rubrique_id=?, montant=?, "
                         "reference=?, detail=?, observation=?, tiers=?, tiers_qualite=? WHERE id=?", (*vals, op.id))
        conn.execute("INSERT INTO journal(action, cible, cible_id, details) VALUES ('operation','association',?,?)",
                     (op.id, f"{NATURES[op.nature]} {montant} {REGISTRES[op.registre]}"))
        _propager(conn, e["id"])
    return op.id


def supprimer(conn, op_id: int) -> None:
    r = conn.execute("SELECT * FROM operation_financiere WHERE id=?", (op_id,)).fetchone()
    if r is None:
        raise ErreurAssociation("العملية غير موجودة.")
    if conn.execute("SELECT 1 FROM piece_association WHERE operation_id=?", (op_id,)).fetchone():
        raise ErreurAssociation("صدرت لهذه العملية وثائق مرقمة (وصل أو سند): لا تُحذف. "
                                "صحح الخطأ بعملية معاكسة مع ذكر السبب في البيان.")
    lie = _achat_lie(conn, op_id)
    if lie:
        raise ErreurAssociation(f"هذه العملية أداء ملف الصرف «{lie}»: لا تُحذف من هنا.")
    if r["rubrique_id"] == _rubrique_report(conn, exercice(conn, r["exercice_id"])["type"]):
        raise ErreurAssociation("المنقول لا يُحذف: عدّله بزر «تعديل المنقول» (أول سنة مالية) أو يُحيَّن آلياً.")
    if _premier_negatif(conn, r["exercice_id"], sauf=op_id):
        raise ErreurAssociation("حذف هذا المدخول يجعل الرصيد سالباً بعده: احذف المصاريف المرتبطة أولاً.")
    with conn:
        conn.execute("DELETE FROM operation_financiere WHERE id=?", (op_id,))
        _propager(conn, r["exercice_id"])


def operations(conn, eid: int, registre: str | None = None) -> list[sqlite3.Row]:
    sql = ("SELECT o.*, r.chapitre, r.ligne FROM operation_financiere o LEFT JOIN rubrique r ON r.id=o.rubrique_id "
           "WHERE o.exercice_id=?")
    lignes = conn.execute(sql + " ORDER BY o.date_op, o.numero", (eid,)).fetchall()
    if registre:
        lignes = [l for l in lignes if registre in _effet(l["nature"], l["registre"], l["montant"])]
    return lignes


def registre(conn, eid: int, reg: str) -> list[dict]:
    """سجل البنك أو الصندوق: مدخول، مصروف، الرصيد بعد كل عملية."""
    solde, res = 0.0, []
    for l in operations(conn, eid, reg):
        v = _effet(l["nature"], l["registre"], l["montant"])[reg]
        solde = round(solde + v, 2)
        libelle = l["ligne"] or ("تمويل الصندوق" if l["registre"] == "banque" else "تحويل إلى الحساب البنكي")
        res.append({"numero": l["numero"], "date": l["date_op"], "libelle": libelle, "detail": l["detail"] or "",
                    "reference": l["reference"] or "", "entree": v if v > 0 else 0.0, "sortie": -v if v < 0 else 0.0,
                    "solde": solde})
    return res


# ---------- الميزانية ----------

def definir_prevision(conn, eid: int, rubrique_id: int, montant: float | str) -> None:
    try:
        m = round(float(str(montant or 0).replace(",", ".").replace(" ", "")), 2)
    except ValueError:
        raise ErreurAssociation("المبلغ غير صحيح.") from None
    if m < 0:
        raise ErreurAssociation("المبلغ لا يكون سالباً.")
    with conn:
        conn.execute("INSERT INTO prevision(exercice_id, rubrique_id, montant) VALUES (?,?,?) "
                     "ON CONFLICT(exercice_id, rubrique_id) DO UPDATE SET montant=excluded.montant", (eid, rubrique_id, m))


def execution(conn, eid: int) -> list[dict]:
    """لكل بند: المتوقع، المنجز، الباقي، نسبة الإنجاز."""
    e = exercice(conn, eid)
    prev = {r[0]: r[1] for r in conn.execute("SELECT rubrique_id, montant FROM prevision WHERE exercice_id=?", (eid,))}
    real = {r[0]: r[1] for r in conn.execute("SELECT rubrique_id, SUM(montant) FROM operation_financiere "
                                             "WHERE exercice_id=? AND rubrique_id IS NOT NULL GROUP BY rubrique_id", (eid,))}
    res = []
    for r in rubriques(conn, e["type"]):
        p, x = prev.get(r["id"], 0.0), round(real.get(r["id"], 0.0), 2)
        if not r["actif"] and not p and not x:
            continue
        res.append({"id": r["id"], "sens": r["sens"], "chapitre": r["chapitre"], "ligne": r["ligne"],
                    "observation": r["observation"], "prevu": p, "realise": x, "reste": round(p - x, 2),
                    "taux": (f"{x / p * 100:.0f}%" if p else "—")})
    return res


def totaux(conn, eid: int) -> dict[str, float]:
    ex = execution(conn, eid)
    t = {k: round(sum(r[c] for r in ex if r["sens"] == s), 2) for k, s, c in (
        ("recettes_prevues", "recette", "prevu"), ("recettes", "recette", "realise"),
        ("depenses_prevues", "depense", "prevu"), ("depenses", "depense", "realise"))}
    s = soldes(conn, eid)
    t.update({"banque": s["banque"], "caisse": s["caisse"], "solde": round(s["banque"] + s["caisse"], 2)})
    return t


# السقوف السنوية التي ينص عليها الدليل المسطري (يوليوز 2023)
PLAFONDS = {"التجهيزات": 20000.0}


def depassements(conn, eid: int) -> list[str]:
    """تنبيهات: بنود تجاوز منجزها المتوقع، ومجالات تجاوزت سقف الدليل."""
    res = []
    ex = execution(conn, eid)
    for ch, plafond in PLAFONDS.items():
        for cle, lib in (("realise", "المنجز"), ("prevu", "المتوقع")):
            m = round(sum(r[cle] for r in ex if r["chapitre"] == ch), 2)
            if m > plafond:
                res.append(f"مجال {ch}: {lib} {m:,.2f} يتجاوز السقف السنوي الذي يحدده الدليل ({plafond:,.0f} درهم)")
    for r in ex:
        if r["sens"] == "depense" and r["realise"] > r["prevu"] + 1e-9:
            res.append(f"{r['ligne']} ({r['chapitre']}): المنجز {r['realise']:,.2f} يتجاوز المتوقع {r['prevu']:,.2f}")
    return res


# ---------- التصدير ----------

def exporter_excel(conn, eid: int, chemin: Path) -> Path:
    """سجلات داخلية للطباعة: اليومية، البنك، الصندوق، تنفيذ الميزانية."""
    import openpyxl
    from openpyxl.styles import Alignment, Font

    e = exercice(conn, eid)
    a = association(conn, e["type"])
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    def feuille(titre, entetes, lignes):
        ws = wb.create_sheet(titre[:31])
        ws.sheet_view.rightToLeft = True
        ws.append([f"{a['nom']} — {titre} — السنة المالية {e['libelle']}"])
        ws["A1"].font = Font(bold=True, size=13)
        ws.append([])
        ws.append(entetes)
        for c in ws[3]:
            c.font = Font(bold=True)
            c.alignment = Alignment(horizontal="center")
        for l in lignes:
            ws.append(l)
        for col in ws.columns:
            ws.column_dimensions[col[2].column_letter].width = max(12, min(55, max(len(str(c.value or "")) for c in col[2:]) + 2))
        return ws

    feuille("اليومية", ["رقم", "التاريخ", "النوع", "السجل", "الباب", "البند", "التفاصيل", "المرجع", "المبلغ"],
            [[l["numero"], l["date_op"], NATURES[l["nature"]], REGISTRES[l["registre"]], l["chapitre"] or "—",
              l["ligne"] or "—", l["detail"] or "", l["reference"] or "", l["montant"]] for l in operations(conn, eid)])
    for reg in REGISTRES:
        feuille(f"سجل {REGISTRES[reg]}", ["رقم", "التاريخ", "البند", "التفاصيل", "المرجع", "مدخول", "مصروف", "الرصيد"],
                [[r["numero"], r["date"], r["libelle"], r["detail"], r["reference"], r["entree"] or "", r["sortie"] or "",
                  r["solde"]] for r in registre(conn, eid, reg)])
    feuille("تنفيذ الميزانية", ["النوع", "الباب", "البند", "المتوقع", "المنجز", "الباقي", "نسبة الإنجاز"],
            [["المداخيل" if r["sens"] == "recette" else "المصاريف", r["chapitre"], r["ligne"], r["prevu"], r["realise"],
              r["reste"], r["taux"]] for r in execution(conn, eid)])
    t = totaux(conn, eid)
    feuille("الحصيلة", ["البيان", "المبلغ"], [
        ["مجموع المداخيل", t["recettes"]], ["مجموع المصاريف", t["depenses"]], ["رصيد البنك", t["banque"]],
        ["رصيد الصندوق", t["caisse"]], ["الرصيد الإجمالي", t["solde"]]])
    wb.save(chemin)
    return chemin
