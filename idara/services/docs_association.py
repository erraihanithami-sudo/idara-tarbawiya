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

def generer_budget(conn, dossier: DossierDonnees, eid: int) -> Path:
    ctx = _contexte(conn, eid)
    ex = asso.execution(conn, eid)
    d = _nouveau()
    para(d, f"{ctx['a']['nom']} — المؤسسة: {ctx['etab']}", gras=True, taille=13)
    para(d, "وثيقة الميزانية", gras=True, taille=22, centre=True, apres=0)
    para(d, f"السنة المالية {ctx['e']['libelle']}", centre=True, apres=8)
    total_general = {}
    for sens, titre in (("recette", "المداخيل"), ("depense", "المصاريف")):
        lignes = [r for r in ex if r["sens"] == sens]
        chapitres: list[tuple[str, list[dict]]] = []
        for r in lignes:
            if not chapitres or chapitres[-1][0] != r["chapitre"]:
                chapitres.append((r["chapitre"], []))
            chapitres[-1][1].append(r)
        para(d, titre, gras=True, taille=18, centre=True, apres=2)
        n = len(lignes) + len(chapitres) + 2
        t = tableau(d, n, 3, largeurs=[4.4, 9.4, 3.6])
        for j, lib in enumerate(("المجالات", "بنود الميزانية", "المبلغ")):
            _cellule(t.cell(0, j), lib, gras=True)
        i = 1
        total = 0.0
        for ch, rs in chapitres:
            debut = i
            for r in rs:
                _cellule(t.cell(i, 1), r["ligne"], taille=13, centre=False)
                _cellule(t.cell(i, 2), dh(r["prevu"]) if r["prevu"] else "", taille=13)
                i += 1
            if len(rs) > 1:
                t.cell(debut, 0).merge(t.cell(i - 1, 0))
            _cellule(t.cell(debut, 0), ch, gras=True, taille=13)
            st = round(sum(r["prevu"] for r in rs), 2)
            total += st
            t.cell(i, 0).merge(t.cell(i, 1))
            _cellule(t.cell(i, 0), f"مجموع {ch}", gras=True, taille=13, centre=False)
            _cellule(t.cell(i, 2), dh(st), gras=True, taille=13)
            i += 1
        t.cell(i, 0).merge(t.cell(i, 1))
        _cellule(t.cell(i, 0), "المجموع العام", gras=True)
        _cellule(t.cell(i, 2), dh(total), gras=True)
        total_general[sens] = round(total, 2)
        para(d, apres=10)
    if total_general["recette"] != total_general["depense"]:
        para(d, f"ملاحظة: مجموع المداخيل ({dh(total_general['recette'])}) لا يساوي مجموع المصاريف "
                f"({dh(total_general['depense'])}). الدليل يوصي بالحرص على التوازن بينهما.", taille=12)
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

