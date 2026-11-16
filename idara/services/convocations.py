"""استدعاءات أولياء الأمور (طلب المدير 2026-11-15): استدعاء لكل تلميذ باسمه وتاريخ ازدياده ورقم مسار، للجمع
العام لجمعية الآباء أو الأبواب المفتوحة (1 إلى 4) أو اللقاءات التواصلية (01 إلى 05)، مع طبع عدة استدعاءات في
الصفحة الواحدة اقتصاداً للورق (خطوط متقطعة للقص).
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path

from docx.enum.table import WD_ROW_HEIGHT_RULE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

from idara.data.dossier import DossierDonnees
from idara.services import annee as annee_srv
from idara.services import etablissement as etab_srv
from idara.services import textes as tx
from idara.services.docs_association import _bidi, _nouveau, _rtl_run, ltr, para, tableau


class ErreurConvocation(ValueError):
    """رسالة موجهة للمدير بالعربية."""


# المناسبة ← (العنوان، أرقامها)
OCCASIONS = {
    "ag_parents": ("الجمع العام لجمعية أمهات وآباء وأولياء التلاميذ", ()),
    "portes": ("الأبواب المفتوحة", ("1", "2", "3", "4")),
    "rencontre": ("اللقاء التواصلي", ("01", "02", "03", "04", "05")),
}
PAR_PAGE = (1, 2, 3, 4, 6, 8)
_TAILLES = {1: 17, 2: 14, 3: 12, 4: 12, 6: 10.5, 8: 9}


def libelle(occasion: str, numero: str = "") -> str:
    if occasion not in OCCASIONS:
        raise ErreurConvocation("مناسبة غير معروفة.")
    titre, numeros = OCCASIONS[occasion]
    if numeros:
        if numero not in numeros:
            raise ErreurConvocation(f"اختر رقم «{titre}».")
        return f"{titre} رقم {numero}"
    return titre


def eleves(conn: sqlite3.Connection, classe_id: int | None = None, ids: list[int] | None = None) -> list[dict]:
    """تلاميذ السنة الجارية (قسم واحد أو الكل، أو تلاميذ بعينهم) مرتبين بالقسم ثم الاسم."""
    a = annee_srv.annee_courante(conn)
    if a is None:
        return []
    sql = ("SELECT e.id, e.nom_ar, e.prenom_ar, e.sexe, e.date_naissance, e.code_massar, c.code AS classe "
           "FROM inscription i JOIN eleve e ON e.id=i.eleve_id LEFT JOIN classe c ON c.id=i.classe_id "
           "WHERE i.annee_id=? AND i.statut IN ('inscrit','arrive')")
    args: list = [a["id"]]
    if classe_id is not None:
        sql += " AND i.classe_id=?"
        args.append(classe_id)
    lignes = [dict(r) for r in conn.execute(sql + " ORDER BY c.code, e.prenom_ar, e.nom_ar", args)]
    if ids is not None:
        voulus = set(ids)
        lignes = [l for l in lignes if l["id"] in voulus]
    return lignes


def _bordures_pointillees(t) -> None:
    b = OxmlElement("w:tblBorders")
    for cote in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement(f"w:{cote}")
        e.set(qn("w:val"), "dashed")
        e.set(qn("w:sz"), "6")
        e.set(qn("w:color"), "808080")
        b.append(e)
    t._tbl.tblPr.append(b)


def _marges_cellule(c, mm: float) -> None:
    tcpr = c._tc.get_or_add_tcPr()
    m = OxmlElement("w:tcMar")
    for cote in ("top", "left", "bottom", "right"):
        e = OxmlElement(f"w:{cote}")
        e.set(qn("w:w"), str(int(mm * 56.7)))
        e.set(qn("w:type"), "dxa")
        m.append(e)
    tcpr.append(m)


def _ligne(c, morceaux: list[tuple[str, bool]], taille: float, centre=False, apres=2.0):
    """فقرة من عدة مقاطع (نص، غامق؟)."""
    p = para(c, "", centre=centre, apres=apres)
    for texte, gras in morceaux:
        if texte:
            _rtl_run(p.add_run(texte), gras, taille)
    return p


def _carte(c, e: dict, t: float, entete: str, objet: str, quand: str, ordre: str, ville: str) -> None:
    c.paragraphs[0]._element.getparent().remove(c.paragraphs[0]._element)
    f = e["sexe"] == "F"
    if entete:
        _ligne(c, [(entete, False)], t * 0.8, centre=True, apres=1)
    _ligne(c, [("استدعاء", True)], t * 1.35, centre=True, apres=t * 0.25)
    _ligne(c, [("إلى السيد(ة) ولي(ة) أمر " + ("التلميذة: " if f else "التلميذ: "), False),
               (f"{e['prenom_ar']} {e['nom_ar']}", True)], t)
    details = [("المزدادة" if f else "المزداد") + f" بتاريخ: {ltr(tx.date_chiffres(e['date_naissance']))}"
               if e["date_naissance"] else "",
               f"رقم مسار: {ltr(e['code_massar'])}" if e["code_massar"] else "",
               f"القسم: {ltr(e['classe'])}" if e["classe"] else ""]
    _ligne(c, [("  ·  ".join(x for x in details if x), False)], t * 0.9, apres=t * 0.3)
    _ligne(c, [("تتشرف إدارة المؤسسة بدعوتكم لحضور ", False), (objet, True), ("، وذلك " + quand + ".", False)], t)
    if ordre:
        _ligne(c, [("جدول الأعمال: ", True), (ordre, False)], t * 0.92)
    _ligne(c, [("ونظراً لأهمية اللقاء، نرجو حضوركم في الموعد.", False)], t, apres=t * 0.25)
    _ligne(c, [((f"{ville}، في " if ville else "في ") + tx.date_ar(datetime.now().date()), False),
               ("          المدير(ة):", True)], t * 0.9, apres=0)


def generer(conn: sqlite3.Connection, dossier: DossierDonnees, occasion: str, numero: str, le: str, heure: str,
            lieu: str, ordre: str = "", par_page: int = 4, classe_id: int | None = None,
            ids: list[int] | None = None) -> Path:
    objet = libelle(occasion, numero)
    if par_page not in PAR_PAGE:
        raise ErreurConvocation("عدد الاستدعاءات في الصفحة: 1 أو 2 أو 3 أو 4 أو 6 أو 8.")
    try:
        jour = date.fromisoformat(le or "")
    except ValueError:
        raise ErreurConvocation("اكتب تاريخ اللقاء.") from None
    heure, lieu = " ".join(heure.split()), " ".join(lieu.split())
    if not heure:
        raise ErreurConvocation("اكتب ساعة اللقاء.")
    cibles = eleves(conn, classe_id, ids)
    if not cibles:
        raise ErreurConvocation("لا تلاميذ لتوليد استدعاءاتهم.")
    etab = etab_srv.lire_etablissement(conn)
    a = annee_srv.annee_courante(conn)
    entete = " · ".join(x for x in (etab.nom_ar if etab else "", f"السنة الدراسية {a['libelle']}" if a else "") if x)
    quand = f"يوم {tx.date_longue_ar(jour)} على الساعة {ltr(heure)}" + (f" بـ{lieu}" if lieu else "")
    ville = etab.ville_redaction_ar if etab and etab.ville_redaction_ar else ""
    ordre = "؛ ".join(x.strip() for x in ordre.splitlines() if x.strip())

    d = _nouveau()
    s = d.sections[0]
    for m in ("top_margin", "bottom_margin", "left_margin", "right_margin"):
        setattr(s, m, Cm(1.0))
    colonnes = 1 if par_page <= 3 else 2
    rangs = par_page // colonnes
    haut, larg = 26.6 / rangs, 19.0 / colonnes
    t = _TAILLES[par_page]
    for debut in range(0, len(cibles), par_page):
        lot = cibles[debut:debut + par_page]
        if debut:   # فقرة صغيرة تبدأ صفحة جديدة بين جدولين
            p = d.add_paragraph()
            _bidi(p)
            p.paragraph_format.page_break_before = True
            p.paragraph_format.space_after = Pt(0)
            _rtl_run(p.add_run(""), False, 1)
        n_rangs = -(-len(lot) // colonnes)
        tb = tableau(d, n_rangs, colonnes, bordures=False, largeurs=[larg] * colonnes)
        _bordures_pointillees(tb)
        for k in range(n_rangs * colonnes):
            li, co = divmod(k, colonnes)
            cell = tb.cell(li, co)
            tb.rows[li].height = Cm(haut)
            tb.rows[li].height_rule = WD_ROW_HEIGHT_RULE.EXACTLY
            _marges_cellule(cell, 5 if par_page <= 4 else 3.5)
            if k < len(lot):
                _carte(cell, lot[k], t, entete, objet, quand, ordre, ville)
    rep = dossier.archives / "الاستدعاءات"
    rep.mkdir(parents=True, exist_ok=True)
    chemin = rep / f"{datetime.now():%Y%m%d_%H%M%S}_استدعاء_{objet.replace(' ', '_')}.docx"
    d.save(chemin)
    return chemin
