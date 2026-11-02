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


def rubriques(conn, type_: str = "najah", sens: str | None = None) -> list[sqlite3.Row]:
    sql, args = "SELECT * FROM rubrique WHERE type_association=?", [type_]
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
    if precedent and report_banque is None and report_caisse is None:
        s = soldes(conn, precedent[0])
        report_banque, report_caisse, reference = s["banque"], s["caisse"], reference or "رصيد السنة المالية السابقة"
    try:
        with conn:
            eid = conn.execute("INSERT INTO exercice(association_id, libelle, date_debut, date_fin) VALUES (?,?,?,?)",
                               (a["id"], libelle, debut, fin)).lastrowid
    except sqlite3.IntegrityError:
        raise ErreurAssociation("سنة مالية بنفس الاسم موجودة.") from None
    rid = _rubrique_report(conn, type_)
    for reg, m in (("banque", report_banque), ("caisse", report_caisse)):
        if m and m > 0:
            enregistrer(conn, Operation(eid, debut, "recette", reg, round(m, 2), rid,
                                        reference or "محضر تسليم المهام / كشف الحساب",
                                        f"المنقول — {REGISTRES[reg]}"))
    return eid


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


def enregistrer(conn, op: Operation) -> int:
    e = exercice(conn, op.exercice_id)
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
        r = conn.execute("SELECT sens FROM rubrique WHERE id=?", (op.rubrique_id,)).fetchone()
        if r is None:
            raise ErreurAssociation("اختر البند.")
        if r["sens"] != op.nature:
            raise ErreurAssociation("البند لا يناسب نوع العملية.")
    if op.nature != "recette" and not (op.reference or "").strip():
        raise ErreurAssociation("مرجع المصروف أو التحويل إجباري (فاتورة، سند الطلب، كشف الحساب...).")
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
    return op.id


def supprimer(conn, op_id: int) -> None:
    r = conn.execute("SELECT * FROM operation_financiere WHERE id=?", (op_id,)).fetchone()
    if r is None:
        raise ErreurAssociation("العملية غير موجودة.")
    if conn.execute("SELECT 1 FROM piece_association WHERE operation_id=?", (op_id,)).fetchone():
        raise ErreurAssociation("صدرت لهذه العملية وثائق مرقمة (وصل أو سند): لا تُحذف. "
                                "صحح الخطأ بعملية معاكسة مع ذكر السبب في البيان.")
    if _premier_negatif(conn, r["exercice_id"], sauf=op_id):
        raise ErreurAssociation("حذف هذا المدخول يجعل الرصيد سالباً بعده: احذف المصاريف المرتبطة أولاً.")
    with conn:
        conn.execute("DELETE FROM operation_financiere WHERE id=?", (op_id,))


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


def depassements(conn, eid: int) -> list[str]:
    """تنبيهات: بنود تجاوز منجزها المتوقع، ومصاريف بدون ميزانية."""
    res = []
    for r in execution(conn, eid):
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
