"""وثائق جمعية دعم مدرسة النجاح، منقولة عن ملاحق «الدليل المسطري في شأن التدبير المالي لجمعيات
دعم مدرسة النجاح» (وزارة التربية الوطنية ووزارة الاقتصاد والمالية، يوليوز 2023):

- الملحق 1: وثيقة الميزانية.
- الملاحق 9 إلى 13: وصل مداخيل، أمر بالأداء، إذن بالسحب من الحساب البنكي، سند الصندوق، سند تسلم.
- الملاحق 17 إلى 19: السجل اليومي للعمليات، سجل البنك، سجل الصندوق (25 عملية في الصفحة، والرصيد
  يُنقل في رأس الصفحة الموالية كما ينص الدليل).
- الملحق 25: محضر تسليم المهام المالية.

الوثائق تُبنى مباشرة (لا قوالب Word للمؤسسة هنا)، والقاعدة نفسها: لا نقط مكان معطى ناقص، بل رسالة.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

from idara.data.dossier import DossierDonnees
from idara.services import associations as asso
from idara.services import documents as dc
from idara.services import textes as tx

POLICE = "Sakkal Majalla"
TAILLE = 15
LIGNES_PAR_PAGE = 25

PIECES = {  # النوع ← (العنوان، رقم الملحق)
    "recu": ("وصل مداخيل", 9),
    "ordre_paiement": ("أمر بالأداء", 10),
    "autorisation_retrait": ("إذن بالسحب من الحساب البنكي", 11),
    "bon_caisse": ("سند الصندوق", 12),
    "bon_reception": ("سند تسلم", 13),
}
REGISTRES_DOC = {"journal": ("السجل اليومي للعمليات", 17), "banque": ("سجل البنك", 18),
                 "caisse": ("سجل الصندوق", 19)}


class ErreurDocAssociation(ValueError):
    """رسالة موجهة للمدير بالعربية."""


def dh(x: float) -> str:
    """الرقم معزول الاتجاه (LRI…PDI) حتى لا تنقلب أجزاؤه داخل السطر العربي."""
    return "\u2066" + f"{x:,.2f}".replace(",", "\u00a0") + "\u2069"


def ltr(texte: str) -> str:
    return f"\u2066{texte}\u2069"


# ---------- بناء DOCX من اليمين إلى اليسار ----------

def _rtl_run(run, gras=False, taille=None, souligne=False) -> None:
    run.bold = gras
    run.underline = souligne
    run.font.size = Pt(taille or TAILLE)
    rpr = run._element.get_or_add_rPr()
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        rpr.insert(0, fonts)
    for a in ("w:ascii", "w:hAnsi", "w:cs"):
        fonts.set(qn(a), POLICE)
    if gras:
        rpr.append(OxmlElement("w:bCs"))
    sz = OxmlElement("w:szCs")
    sz.set(qn("w:val"), str(int((taille or TAILLE) * 2)))
    rpr.append(sz)
    rpr.append(OxmlElement("w:rtl"))


def _bidi(p) -> None:
    ppr = p._element.get_or_add_pPr()
    if ppr.find(qn("w:bidi")) is None:
        ppr.insert(0, OxmlElement("w:bidi"))


def para(conteneur, texte: str = "", gras=False, taille=None, centre=False, souligne=False, apres=2):
    p = conteneur.add_paragraph()
    _bidi(p)
    if centre:
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(apres)
    p.paragraph_format.space_before = Pt(0)
    if texte:
        _rtl_run(p.add_run(texte), gras, taille, souligne)
    return p


def ajouter(p, texte: str, gras=False, taille=None) -> None:
    _rtl_run(p.add_run(texte), gras, taille)


def _cellule(c, texte: str, gras=False, taille=None, centre=True) -> None:
    c.paragraphs[0]._element.getparent().remove(c.paragraphs[0]._element)
    para(c, texte, gras, taille, centre, apres=0)


def _bordures(table, epaisseur=6) -> None:
    tblpr = table._tbl.tblPr
    b = OxmlElement("w:tblBorders")
    for cote in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement(f"w:{cote}")
        e.set(qn("w:val"), "single")
        e.set(qn("w:sz"), str(epaisseur))
        e.set(qn("w:color"), "000000")
        b.append(e)
    tblpr.append(b)


def tableau(conteneur, lignes: int, colonnes: int, bordures=True, largeurs: list[float] | None = None):
    t = conteneur.add_table(rows=lignes, cols=colonnes)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t._tbl.tblPr.append(OxmlElement("w:bidiVisual"))
    if bordures:
        _bordures(t)
    if largeurs:
        _largeurs(t, largeurs)
    return t


def _largeurs(t, largeurs: list[float]) -> None:
    """عرض ثابت للأعمدة (tblLayout fixed + gridCol + عرض كل خلية)."""
    t.autofit = False
    tblpr = t._tbl.tblPr
    lay = OxmlElement("w:tblLayout")
    lay.set(qn("w:type"), "fixed")
    tblpr.append(lay)
    w = tblpr.find(qn("w:tblW"))
    if w is None:
        w = OxmlElement("w:tblW")
        tblpr.append(w)
    w.set(qn("w:type"), "dxa")
    w.set(qn("w:w"), str(int(sum(largeurs) * 567)))
    for gc, l in zip(t._tbl.tblGrid.findall(qn("w:gridCol")), largeurs):
        gc.set(qn("w:w"), str(int(l * 567)))
    for ligne in t.rows:
        for c, l in zip(ligne.cells, largeurs):
            c.width = Cm(l)


def _nouveau(paysage=False) -> Document:
    d = Document()
    s = d.sections[0]
    s.page_height, s.page_width = Cm(29.7), Cm(21)
    if paysage:
        s.orientation = WD_ORIENT.LANDSCAPE
        s.page_height, s.page_width = s.page_width, s.page_height
    for m in ("top_margin", "bottom_margin"):
        setattr(s, m, Cm(1.5))
    for m in ("left_margin", "right_margin"):
        setattr(s, m, Cm(1.8))
    st = d.styles["Normal"]
    st.font.name = POLICE
    st.font.size = Pt(TAILLE)
    rpr = st.element.get_or_add_rPr()
    fonts = rpr.find(qn("w:rFonts"))
    for a in ("w:ascii", "w:hAnsi", "w:cs"):
        fonts.set(qn(a), POLICE)
    return d


def saut_page(d) -> None:
    p = d.add_paragraph()
    p.add_run().add_break(WD_BREAK.PAGE)


def _enregistrer(d: Document, dossier: DossierDonnees, exercice: str, sous: str, nom: str) -> Path:
    rep = dossier.archives / f"جمعية النجاح {exercice.replace('/', '-')}" / sous
    rep.mkdir(parents=True, exist_ok=True)
    chemin = rep / f"{datetime.now():%Y%m%d_%H%M%S}_{nom}.docx"
    n = 1
    while chemin.exists():
        n += 1
        chemin = chemin.with_name(f"{chemin.stem}_{n}.docx")
    d.save(chemin)
    return chemin


# ---------- المعطيات المشتركة ----------

def _contexte(conn, eid: int) -> dict:
    e = asso.exercice(conn, eid)
    a = asso.association(conn, e["type"])
    try:
        c = dc.champs_communs(conn)
    except dc.ErreurDocument as err:
        raise ErreurDocAssociation(str(err)) from None
    return {"e": e, "a": a, "etab": c["etablissement"], "ville": c["ville"], "code": code_exercice(e["libelle"])}


def code_exercice(libelle: str) -> str:
    """2025/2026 ← 25-26 (كترقيم الصادر)؛ غير ذلك كما هو."""
    import re
    m = re.fullmatch(r"(\d{4})\s*[/-]\s*(\d{4})", libelle.strip())
    return f"{m[1][2:]}-{m[2][2:]}" if m else libelle.replace("/", "-")


def _exiger(valeurs: dict[str, str]) -> None:
    manque = [lib for lib, v in valeurs.items() if not (v or "").strip()]
    if manque:
        raise ErreurDocAssociation("معطيات ناقصة: " + "، ".join(manque) + ".")


def _entete_piece(conteneur, ctx, date_doc: str) -> None:
    t = tableau(conteneur, 1, 2, bordures=False, largeurs=[6.8, 7.2])
    _cellule(t.cell(0, 0), ctx["a"]["nom"], gras=True, centre=False)
    _cellule(t.cell(0, 1), f"{ctx['ville']} في: {tx.date_chiffres(date_doc)}", centre=True)
    para(conteneur, f"المؤسسة: {ctx['etab']}", apres=6)


# ---------- الوصولات والسندات (الملاحق 9 إلى 13) ----------

def pieces_pour(op) -> list[str]:
    """الوثائق التي ينص عليها الدليل لكل نوع من العمليات."""
    if op["nature"] == "recette":
        return [] if op["ligne"] == asso.REPORT else ["recu"]
    if op["nature"] == "transfert":
        return ["autorisation_retrait"] if op["registre"] == "banque" else []
    if op["registre"] == "caisse":
        return ["ordre_paiement", "bon_caisse", "bon_reception"]
    return []


def numero_piece(conn, op, type_: str) -> int:
    """رقم الوصل أو السند: يُمنح عند أول إصدار ويبقى ثابتاً بعده."""
    r = conn.execute("SELECT numero FROM piece_association WHERE type=? AND operation_id=?", (type_, op["id"])).fetchone()
    if r:
        return r[0]
    with conn:
        n = conn.execute("SELECT COALESCE(MAX(numero),0)+1 FROM piece_association WHERE exercice_id=? AND type=?",
                         (op["exercice_id"], type_)).fetchone()[0]
        conn.execute("INSERT INTO piece_association(exercice_id, type, numero, operation_id) VALUES (?,?,?,?)",
                     (op["exercice_id"], type_, n, op["id"]))
    return n


def pieces_emises(conn, op_id: int) -> dict[str, int]:
    return {r[0]: r[1] for r in conn.execute("SELECT type, numero FROM piece_association WHERE operation_id=?", (op_id,))}


def _operation(conn, op_id: int):
    op = conn.execute("SELECT o.*, r.ligne, r.chapitre FROM operation_financiere o LEFT JOIN rubrique r "
                      "ON r.id=o.rubrique_id WHERE o.id=?", (op_id,)).fetchone()
    if op is None:
        raise ErreurDocAssociation("العملية غير موجودة.")
    return op


def generer_piece(conn, dossier: DossierDonnees, op_id: int, type_: str) -> Path:
    op = _operation(conn, op_id)
    if type_ not in pieces_pour(op):
        raise ErreurDocAssociation("هذه الوثيقة لا تخص هذا النوع من العمليات.")
    ctx = _contexte(conn, op["exercice_id"])
    a = ctx["a"]
    objet = " — ".join(x for x in (op["ligne"], op["detail"]) if x) or "تمويل الصندوق"
    montant = f"{dh(op['montant'])} درهم"
    lettres = tx.montant_lettres_ar(op["montant"])
    lignes: list[tuple[str, str]]
    if type_ == "recu":
        _exiger({"أمين المال (معطيات الجمعية)": a["tresorier"], "الطرف المؤدي": op["tiers"]})
        mode = "شيك" if op["registre"] == "banque" else "نقدا"
        tiers = op["tiers"] + (f" ({op['tiers_qualite']})" if op["tiers_qualite"] else "")
        lignes = [("أنا الموقع أسفله: ", a["tresorier"]), ("بصفتي: ", "أمين مال الجمعية"),
                  ("تسلمت من السيد: ", tiers), (f"مبلغ ({mode}): ", montant), ("", lettres)]
        if op["detail"]:
            lignes.append(("وذلك برسم: ", op["detail"]))
        signataire = "أمين المال"
    elif type_ in ("ordre_paiement", "autorisation_retrait"):
        _exiger({"رئيس الجمعية (معطيات الجمعية)": a["president"]})
        verbe = "أرخص بأداء مبلغ مالي قدره: " if type_ == "ordre_paiement" else "أرخص بسحب مبلغ مالي قدره: "
        lignes = [("أنا الموقع أسفله: ", a["president"]), ("بصفتي: ", "رئيس الجمعية"), (verbe, montant),
                  ("", lettres + (" من حساب الجمعية." if type_ == "autorisation_retrait" else "")),
                  ("لتغطية النفقات الخاصة ب: ", objet)]
        signataire = "الرئيس أو من ينوب عنه"
    elif type_ == "bon_caisse":
        lignes = [("المبلغ: ", montant), ("", lettres), ("لأجل: ", objet)]
        signataire = ""
    else:  # bon_reception
        _exiger({"أمين المال (معطيات الجمعية)": a["tresorier"], "المستفيد": op["tiers"],
                 "صفة المستفيد": op["tiers_qualite"]})
        lignes = [("أنا الموقع أسفله: ", op["tiers"]), ("بصفتي: ", op["tiers_qualite"]),
                  ("أشهد أني تسلمت من السيد: ", a["tresorier"]), ("مبلغا ماليا قدره: ", montant), ("", lettres),
                  ("وذلك في مقابل: ", objet)]
        signataire = ""
    n = numero_piece(conn, op, type_)
    titre, _ = PIECES[type_]

    d = _nouveau()
    cadre = tableau(d, 1, 1, largeurs=[14.5])
    c = cadre.cell(0, 0)
    c.paragraphs[0]._element.getparent().remove(c.paragraphs[0]._element)
    _entete_piece(c, ctx, op["date_op"])
    para(c, titre, gras=True, taille=20, centre=True, souligne=True)
    para(c, f"رقم {ltr(f'{n:02d}/' + ctx['code'])}", gras=True, centre=True, apres=10)
    for lib, val in lignes:
        p = para(c, apres=4)
        if lib:
            ajouter(p, lib, gras=True)
        ajouter(p, val)
    para(c, apres=10)
    p = para(c, "الإمضاء:", gras=True, apres=30)
    if signataire:
        para(c, signataire, gras=True, centre=True, apres=40)
    else:
        para(c, apres=30)
    return _enregistrer(d, dossier, ctx["e"]["libelle"], titre, f"{titre} {n:02d}")


# ---------- السجلات (الملاحق 17 إلى 19) ----------

def lignes_registre(conn, eid: int, kind: str) -> tuple[float, list[dict]]:
    """(المنقول، العمليات المرقمة). السجل اليومي يضم المداخيل والمصاريف (لا التحويلات بين البنك والصندوق)."""
    report, res, solde = 0.0, [], 0.0
    pieces = {}
    for r in conn.execute("SELECT p.operation_id, p.type, p.numero FROM piece_association p WHERE exercice_id=?", (eid,)):
        pieces.setdefault(r[0], []).append((r[1], r[2]))
    code = code_exercice(asso.exercice(conn, eid)["libelle"])
    for o in asso.operations(conn, eid, None if kind == "journal" else kind):
        if kind == "journal":
            if o["nature"] == "transfert":
                continue
            v = o["montant"] if o["nature"] == "recette" else -o["montant"]
        else:
            v = asso._effet(o["nature"], o["registre"], o["montant"])[kind]
        if o["ligne"] == asso.REPORT:
            report = round(report + v, 2)
            solde = report
            continue
        solde = round(solde + v, 2)
        ref = o["reference"] or ""
        if not ref and o["id"] in pieces:
            t, n = pieces[o["id"]][0]
            ref = f"{PIECES[t][0]} {ltr(f'{n:02d}/{code}')}"
        if o["nature"] == "transfert":
            lib = "تمويل الصندوق" if o["registre"] == "banque" else "إيداع نقود الصندوق في الحساب"
        else:
            lib = o["ligne"]
        if o["detail"]:
            lib += f" — {o['detail']}"
        res.append({"date": o["date_op"], "reference": ref, "libelle": lib,
                    "entree": v if v > 0 else 0.0, "sortie": -v if v < 0 else 0.0, "solde": solde})
    return report, res


def generer_registre(conn, dossier: DossierDonnees, eid: int, kind: str) -> Path:
    ctx = _contexte(conn, eid)
    titre, _ = REGISTRES_DOC[kind]
    report, lignes = lignes_registre(conn, eid, kind)
    d = _nouveau()
    largeurs = [1.6, 2.4, 2.5, 4.5, 2.0, 2.0, 2.4]
    pages = [lignes[i:i + LIGNES_PAR_PAGE] for i in range(0, len(lignes), LIGNES_PAR_PAGE)] or [[]]
    solde, k = report, 0
    for ip, page in enumerate(pages):
        if ip:
            saut_page(d)
        para(d, f"{ctx['a']['nom']} — المؤسسة: {ctx['etab']}", gras=True, taille=13, apres=0)
        para(d, titre, gras=True, taille=20, centre=True, apres=0)
        para(d, f"السنة المالية {ctx['e']['libelle']} — الصفحة {ip + 1}/{len(pages)}", centre=True, taille=13)
        t = tableau(d, 3 + LIGNES_PAR_PAGE, 7, largeurs=largeurs)
        for j, lib in enumerate(("الرقم الترتيبي للعملية", "المرجع", "تاريخ العملية", "بيان العملية")):
            t.cell(0, j).merge(t.cell(1, j))
            _cellule(t.cell(0, j), lib, gras=True, taille=11)
        t.cell(0, 4).merge(t.cell(0, 5))
        _cellule(t.cell(0, 4), "المبلغ", gras=True, taille=12)
        _cellule(t.cell(1, 4), "مداخيل", gras=True, taille=12)
        _cellule(t.cell(1, 5), "مصاريف", gras=True, taille=12)
        t.cell(0, 6).merge(t.cell(1, 6))
        _cellule(t.cell(0, 6), "الرصيد", gras=True, taille=12)
        _cellule(t.cell(2, 3), "المنقول", gras=True, taille=12)
        _cellule(t.cell(2, 4), dh(solde), taille=12)
        _cellule(t.cell(2, 6), dh(solde), taille=12)
        for i in range(LIGNES_PAR_PAGE):
            row = 3 + i
            if i < len(page):
                l = page[i]
                k += 1
                vals = (f"{k:02d}", l["reference"], tx.date_chiffres(l["date"]), l["libelle"],
                        dh(l["entree"]) if l["entree"] else "", dh(l["sortie"]) if l["sortie"] else "", dh(l["solde"]))
                solde = l["solde"]
            else:
                vals = ("", "", "", "", "", "", "")
            for j, v in enumerate(vals):
                _cellule(t.cell(row, j), v, taille=10.5, centre=j != 3)
    return _enregistrer(d, dossier, ctx["e"]["libelle"], "السجلات", titre)


# ---------- وثيقة الميزانية (الملحق 1) ----------

def _ombre(cellule, couleur="E7E6F0") -> None:
    tcpr = cellule._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), couleur)
    tcpr.append(shd)


def _chapitres(lignes: list[dict]) -> list[tuple[str, list[dict]]]:
    res: list[tuple[str, list[dict]]] = []
    for r in lignes:
        if not res or res[-1][0] != r["chapitre"]:
            res.append((r["chapitre"], []))
        res[-1][1].append(r)
    return res


def generer_budget(conn, dossier: DossierDonnees, eid: int) -> Path:
    """الملحق 1: المداخيل (يميناً) والمصاريف (يساراً) متقابلتان، بالمجالات ومجموع كل مجال والمجموع العام."""
    ctx = _contexte(conn, eid)
    ex = asso.execution(conn, eid)
    d = _nouveau()
    para(d, f"{ctx['a']['nom']} — المؤسسة: {ctx['etab']}", gras=True, taille=13)
    para(d, "وثيقة الميزانية", gras=True, taille=22, centre=True, apres=0)
    para(d, f"السنة المالية {ctx['e']['libelle']}", centre=True, apres=8)
    T = 10.5
    cadre = tableau(d, 1, 2, bordures=False, largeurs=[7.0, 10.4])
    totaux = {}

    # المداخيل: البند (والمجال المرقم في سطر مظلل) والمبلغ
    rec = _chapitres([r for r in ex if r["sens"] == "recette"])
    c = cadre.cell(0, 0)
    n = 2 + sum(1 + len(rs) for _, rs in rec) + 1
    t = tableau(c, n, 2, largeurs=[4.5, 2.3])
    t.cell(0, 0).merge(t.cell(0, 1))
    _cellule(t.cell(0, 0), "المداخيل", gras=True, taille=13)
    _cellule(t.cell(1, 0), "بنود الميزانية", gras=True, taille=T)
    _cellule(t.cell(1, 1), "المبلغ", gras=True, taille=T)
    i, total = 2, 0.0
    for k, (ch, rs) in enumerate(rec, start=1):
        st = round(sum(r["prevu"] for r in rs), 2)
        _cellule(t.cell(i, 0), f"{k} - {ch}", gras=True, taille=T, centre=False)
        _cellule(t.cell(i, 1), dh(st) if st else "", gras=True, taille=T)
        _ombre(t.cell(i, 0))
        _ombre(t.cell(i, 1))
        i += 1
        for r in rs:
            _cellule(t.cell(i, 0), r["ligne"], taille=T, centre=False)
            _cellule(t.cell(i, 1), dh(r["prevu"]) if r["prevu"] else "", taille=T)
            i += 1
        total += st
    _cellule(t.cell(i, 0), "المجموع العام", gras=True, taille=T)
    _cellule(t.cell(i, 1), dh(total), gras=True, taille=T)
    _ombre(t.cell(i, 0), "D9D9D9")
    _ombre(t.cell(i, 1), "D9D9D9")
    totaux["recette"] = round(total, 2)
    c.add_paragraph()

    # المصاريف: المجالات، بنود الميزانية، المبلغ، ومجموع نفقات كل مجال
    dep = _chapitres([r for r in ex if r["sens"] == "depense"])
    c = cadre.cell(0, 1)
    n = 2 + sum(len(rs) + 1 for _, rs in dep) + 1
    t = tableau(c, n, 3, largeurs=[2.4, 5.5, 2.3])
    t.cell(0, 0).merge(t.cell(0, 2))
    _cellule(t.cell(0, 0), "المصاريف", gras=True, taille=13)
    for j, lib in enumerate(("المجالات", "بنود الميزانية", "المبلغ")):
        _cellule(t.cell(1, j), lib, gras=True, taille=T)
    i, total = 2, 0.0
    for ch, rs in dep:
        debut = i
        for r in rs:
            _cellule(t.cell(i, 1), r["ligne"], taille=T, centre=False)
            _cellule(t.cell(i, 2), dh(r["prevu"]) if r["prevu"] else "", taille=T)
            i += 1
        if len(rs) > 1:
            t.cell(debut, 0).merge(t.cell(i - 1, 0))
        _cellule(t.cell(debut, 0), ch, gras=True, taille=T)
        st = round(sum(r["prevu"] for r in rs), 2)
        total += st
        t.cell(i, 0).merge(t.cell(i, 1))
        nom = ch if ch.startswith("نفقات") else f"نفقات {ch}"
        _cellule(t.cell(i, 0), f"مجموع {nom}", gras=True, taille=T, centre=False)
        _cellule(t.cell(i, 2), dh(st), gras=True, taille=T)
        _ombre(t.cell(i, 0))
        _ombre(t.cell(i, 2))
        i += 1
    t.cell(i, 0).merge(t.cell(i, 1))
    _cellule(t.cell(i, 0), "المجموع العام", gras=True, taille=T)
    _cellule(t.cell(i, 2), dh(total), gras=True, taille=T)
    _ombre(t.cell(i, 0), "D9D9D9")
    _ombre(t.cell(i, 2), "D9D9D9")
    totaux["depense"] = round(total, 2)
    c.add_paragraph()

    para(d, apres=6)
    if totaux["recette"] != totaux["depense"]:
        para(d, f"ملاحظة: مجموع المداخيل ({dh(totaux['recette'])}) لا يساوي مجموع المصاريف "
                f"({dh(totaux['depense'])}). الدليل يوصي بالحرص على التوازن بينهما.", taille=12)
    t = tableau(d, 1, 2, bordures=False, largeurs=[8.7, 8.7])
    _cellule(t.cell(0, 0), "توقيع رئيس الجمعية", gras=True)
    _cellule(t.cell(0, 1), "توقيع أمين المال", gras=True)
    return _enregistrer(d, dossier, ctx["e"]["libelle"], "الميزانية", "وثيقة الميزانية")


# ---------- محضر تسليم المهام المالية (الملحق 25) ----------

DOCUMENTS_REMIS = ("السجل اليومي للعمليات", "سجل البنك", "سجل الصندوق", "دفتر الجرد", "سجل تسليم الشيكات",
                   "دفتر/دفاتر الشيكات وجدور الشيكات المستعملة", "التقرير المالي عن السنة الماضية",
                   "وثيقة الميزانية للسنة الجارية",
                   "دفاتر الوصولات المعتمدة لدى الجمعية (وصل مداخيل، أمر بالأداء، إذن بالسحب من الحساب البنكي، "
                   "سند الصندوق، سند تسلم، وصل تسلم تجهيز...)")


def generer_pv_passation(conn, dossier: DossierDonnees, eid: int, date_pv: str, ancien: str, nouveau: str,
                         remarques: list[str] | None = None) -> Path:
    ctx = _contexte(conn, eid)
    a = ctx["a"]
    _exiger({"رئيس الجمعية (معطيات الجمعية)": a["president"], "أمين المال السابق": ancien,
             "أمين المال الجديد": nouveau})
    e = ctx["e"]
    if not e["date_debut"] <= date_pv <= e["date_fin"]:
        raise ErreurDocAssociation("تاريخ المحضر خارج السنة المالية المختارة.")
    s = asso.soldes(conn, eid, jusqu_a=date_pv)
    d = _nouveau()
    _entete_piece(d, ctx, date_pv)
    para(d, "محضر تسليم المهام المالية", gras=True, taille=22, centre=True, souligne=True, apres=10)
    para(d, f"تم في التاريخ المشار إليه أعلاه بمؤسسة {ctx['etab']}")
    para(d, f"وبحضور السيد(ة): {a['president']}، رئيس(ة) الجمعية،")
    para(d, "تسليم المهام")
    para(d, f"بين السيد(ة): {' '.join(ancien.split())}، أمين(ة) المال السابق(ة)")
    para(d, f"و السيد(ة): {' '.join(nouveau.split())}، أمين(ة) المال الجديد(ة)", apres=8)
    para(d, "وبعد الاطلاع على الوضعية المالية للجمعية ومراجعة السجلات المحاسبية تم حصر الوضعية المالية فيما يلي:",
         gras=True, apres=4)
    t = tableau(d, 3, 2, largeurs=[7, 5])
    for i, (lib, v) in enumerate((("الرصيد بالبنك", s["banque"]), ("الرصيد بالصندوق", s["caisse"]),
                                  ("المجموع", s["banque"] + s["caisse"]))):
        _cellule(t.cell(i, 0), lib, gras=True)
        _cellule(t.cell(i, 1), f"{dh(v)} درهم")
    para(d, apres=6)
    para(d, f"ولقد تسلم أمين المال الجديد المبلغ المتبقي بالصندوق وهو (بالأرقام): {dh(s['caisse'])}\u00a0درهم")
    para(d, f"(بالحروف): {tx.montant_lettres_ar(s['caisse'])}")
    para(d, "وبناء عليه تم حصر كل من السجل اليومي للعمليات وسجل الصندوق وسجل البنك في تاريخه.", apres=8)
    para(d, "وبعد ذلك تم الاطلاع على جميع الوثائق والتقارير والسجلات المعتمدة في التسيير المالي للجمعية، "
            "تم تسليم هذه الوثائق لأمين المال الجديد وهي على الشكل التالي:")
    for doc in DOCUMENTS_REMIS:
        para(d, f"- {doc}", apres=0)
    para(d, "هذا بالإضافة لكل وثائق الأرشيف المالي للجمعية.", apres=6)
    para(d, "وقد تم تسجيل الملاحظات التالية:")
    rem = [r.strip() for r in (remarques or []) if r.strip()]
    for i, r in enumerate(rem or ["لا شيء."], start=1):
        para(d, f"{i}- {r}")
    para(d, apres=10)
    t = tableau(d, 1, 3, bordures=False, largeurs=[5.8, 5.8, 5.8])
    for j, lib in enumerate(("توقيع أمين المال السابق", "توقيع أمين المال الجديد", "توقيع رئيس الجمعية")):
        _cellule(t.cell(0, j), lib, gras=True)
    return _enregistrer(d, dossier, e["libelle"], "محاضر", "محضر تسليم المهام المالية")



# ---------- التقرير المالي (الملحق 16) ----------

# توزيع أبواب الملحق 1 على فقرات التقرير المالي (المصادقة: المدير، 2026-11-02).
# المداخيل القارة: منحة المديرية الإقليمية. المنقول ليس مدخولاً للسنة: يظهر في وضعية الخزينة.
RAPPORT_RECETTES = (("مداخيل قارة", lambda r: r["ligne"] == "منحة المديرية الإقليمية"),
                    ("مداخيل الأنشطة", lambda r: r["chapitre"] == "مداخيل الأنشطة"),
                    ("المنح والهبات", lambda r: r["chapitre"] in ("المنح", "الهبات")
                     and r["ligne"] != "منحة المديرية الإقليمية"),
                    ("مداخيل استثنائية", lambda r: r["chapitre"] == "مداخيل استثنائية" and r["ligne"] != asso.REPORT))
RAPPORT_DEPENSES = (("أ- مصاريف التجهيزات", ("التجهيزات",)),
                    ("ب- مصاريف الأنشطة", ("الأندية التربوية", "التظاهرات المدرسية", "الدعم التربوي",
                                           "دعم الصحة المدرسية", "الدعم النفسي", "التوجيه المدرسي والمهني",
                                           "نفقات تشجيع التميز والإبداع والابتكار")),
                    ("د- مصاريف التسيير", ("التدبير والشراكة", "صيانة وإصلاح تجهيزات وبنيات المؤسسة وتأهيلها")),
                    ("ج- مصاريف استثنائية", ("نفقات استثنائية",)))
QUESTIONS_RAPPORT = (("relation", "حلل العلاقة بين المصاريف والمنجزات"),
                     ("resultat", "قم بتبرير النتيجة المحصل عليها في الرصيد إن كانت إيجابية فلماذا وإن كانت سلبية فلماذا"),
                     ("difficultes", "ماهي إكراهات التدبير المالي للجمعية، والتدابير الإجرائية المتخذة لتجاوزها"),
                     ("durabilite", "الاستدامة المالية: وضح ماهي السياسة التي تم إتباعها من أجل ضمان الاستدامة المالية"))


def chiffres_rapport(conn, eid: int) -> dict:
    ex = asso.execution(conn, eid)
    rec = [(lib, round(sum(r["realise"] for r in ex if r["sens"] == "recette" and f(r)), 2))
           for lib, f in RAPPORT_RECETTES]
    dep = [(lib, round(sum(r["realise"] for r in ex if r["sens"] == "depense" and r["chapitre"] in chs), 2))
           for lib, chs in RAPPORT_DEPENSES]
    report = round(sum(r["realise"] for r in ex if r["ligne"] == asso.REPORT), 2)
    tr, td = round(sum(m for _, m in rec), 2), round(sum(m for _, m in dep), 2)
    return {"recettes": rec, "depenses": dep, "total_recettes": tr, "total_depenses": td, "report": report,
            "resultat": round(tr - td, 2), "soldes": asso.soldes(conn, eid)}


def generer_rapport_financier(conn, dossier: DossierDonnees, eid: int, numero_ag: str,
                              analyses: dict[str, str] | None = None) -> Path:
    ctx = _contexte(conn, eid)
    a = ctx["a"]
    _exiger({"رقم الجمع العام العادي": numero_ag, "رئيس الجمعية (معطيات الجمعية)": a["president"],
             "أمين المال (معطيات الجمعية)": a["tresorier"]})
    c = chiffres_rapport(conn, eid)
    analyses = {k: (v or "").strip() for k, v in (analyses or {}).items()}
    d = _nouveau()
    para(d, f"{a['nom']} — المؤسسة: {ctx['etab']}", gras=True, taille=13)
    para(d, "التقرير المالي", gras=True, taille=22, centre=True, apres=8)
    p = para(d, apres=0)
    ajouter(p, "الجمع العام العادي رقم: ", gras=True)
    ajouter(p, ltr(" ".join(numero_ag.split())))
    p = para(d, apres=8)
    ajouter(p, "السنة: ", gras=True)
    ajouter(p, f"{ctx['e']['libelle']} ({tx.date_chiffres(ctx['e']['date_debut'])} — {tx.date_chiffres(ctx['e']['date_fin'])})")
    n = max(len(c["recettes"]), len(c["depenses"]))
    t = tableau(d, 3 + n, 4, largeurs=[5.0, 3.7, 5.0, 3.7])
    t.cell(0, 0).merge(t.cell(0, 1))
    _cellule(t.cell(0, 0), "المداخيل", gras=True)
    t.cell(0, 2).merge(t.cell(0, 3))
    _cellule(t.cell(0, 2), "المصاريف", gras=True)
    for j, lib in enumerate(("الفقرات", "المبلغ", "الفقرات", "المبلغ")):
        _cellule(t.cell(1, j), lib, gras=True, taille=13)
    for i in range(n):
        for col, lst in ((0, c["recettes"]), (2, c["depenses"])):
            if i < len(lst):
                _cellule(t.cell(2 + i, col), lst[i][0], taille=13, centre=False)
                _cellule(t.cell(2 + i, col + 1), dh(lst[i][1]), taille=13)
    for col, tot in ((0, c["total_recettes"]), (2, c["total_depenses"])):
        _cellule(t.cell(2 + n, col), "المجموع العام", gras=True, taille=13)
        _cellule(t.cell(2 + n, col + 1), dh(tot), gras=True, taille=13)
        _ombre(t.cell(2 + n, col), "D9D9D9")
        _ombre(t.cell(2 + n, col + 1), "D9D9D9")
    para(d, apres=6)
    para(d, "الوضعية الإجمالية للخزينة", gras=True, apres=2)
    s = c["soldes"]
    t = tableau(d, 6, 2, largeurs=[9.4, 4.4])
    for i, (lib, v) in enumerate((("المنقول من السنة المالية السابقة", c["report"]),
                                  ("مداخيل السنة", c["total_recettes"]), ("مصاريف السنة", c["total_depenses"]),
                                  ("الرصيد بالبنك في نهاية الفترة", s["banque"]),
                                  ("الرصيد بالصندوق في نهاية الفترة", s["caisse"]),
                                  ("المجموع", s["banque"] + s["caisse"]))):
        _cellule(t.cell(i, 0), lib, gras=i == 5, taille=13, centre=False)
        _cellule(t.cell(i, 1), dh(v), gras=i == 5, taille=13)
    para(d, apres=6)
    para(d, "التحليل:", gras=True, souligne=True, apres=4)
    tdep = c["total_depenses"]
    for cle, q in QUESTIONS_RAPPORT:
        para(d, f"▪ {q}", gras=True, apres=2)
        if cle == "relation" and tdep:
            nsb = "، ".join(f"{lib[3:]}: {m / tdep * 100:.1f}%" for lib, m in c["depenses"])
            para(d, f"نسب مصاريف كل مجال من المجموع العام ({dh(tdep)} درهم): {nsb}.", taille=14, apres=2)
        if cle == "resultat":
            r = c["resultat"]
            etat = "إيجابية" if r > 0 else ("سلبية" if r < 0 else "متوازنة")
            para(d, f"النتيجة (المداخيل ناقص المصاريف): {dh(r)} درهم — {etat}.", taille=14, apres=2)
        if analyses.get(cle):
            for ligne in analyses[cle].splitlines():
                para(d, ligne, taille=14, apres=2)
        else:
            para(d, "." * 150, taille=11, apres=2)
            para(d, "." * 150, taille=11, apres=4)
    para(d, apres=6)
    para(d, "الإمضاء", gras=True, apres=2)
    t = tableau(d, 1, 2, bordures=False, largeurs=[8.7, 8.7])
    _cellule(t.cell(0, 0), f"الرئيس: {a['president']}", gras=True)
    _cellule(t.cell(0, 1), f"أمين المال: {a['tresorier']}", gras=True)
    para(d, apres=30)
    para(d, "يُرسل هذا التقرير إلى مجلس تدبير المؤسسة وإلى المديرية الإقليمية قبل 15 يناير من السنة التي تلي تلقي "
            "المنحة أو الإعانة (الدليل المسطري).", taille=11)
    return _enregistrer(d, dossier, ctx["e"]["libelle"], "التقارير", "التقرير المالي")
