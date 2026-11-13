"""سجل الجرد (طلب المدير 2026-11-13) على نموذج السجل الورقي المعتمد، مع فرز معطياته حسب نوع التجهيز.

أعمدة السجل: الرقم الترتيبي، تاريخ التسجيل، وصف التجهيزات، مصدرها (رقم الفاتورة وتاريخها، اسم التاجر)، عدد الأشياء،
ثمن الشراء (الوحدة والمجموع)، تخصيص التجهيزات، حالة صيانتها، محو التجهيزات من السجل (التاريخ، السبب، رقم القرار)،
ملاحظات. المحو لا يحذف السطر: يبقى في السجل مؤشراً عليه كما في السجل الورقي.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, fields
from datetime import date, datetime
from pathlib import Path

from idara.data.dossier import DossierDonnees
from idara.data.journal import journaliser
from idara.services import textes as tx

TYPES = ("أثاث مكتبي", "تجهيزات الحجرات الدراسية", "معلوميات ووسائل رقمية", "وسائل تعليمية", "تجهيزات رياضية",
         "تجهيزات النظافة والصيانة", "تجهيزات التعليم الأولي", "أخرى")
ETATS = ("صالح", "يحتاج صيانة", "معطل")


class ErreurInventaire(ValueError):
    """رسالة موجهة للمدير بالعربية."""


@dataclass
class Article:
    designation: str
    date_inscription: str
    quantite: int = 1
    type: str = "أخرى"
    numero: int | None = None
    facture_numero: str = ""
    facture_date: str = ""
    fournisseur: str = ""
    prix_unitaire: float | None = None
    affectation: str = ""
    entretien: str = ""
    remarques: str = ""
    unite_id: int | None = None
    radie_le: str = ""
    radiation_motif: str = ""
    radiation_decision: str = ""
    id: int | None = None

    @property
    def total(self) -> float | None:
        return None if self.prix_unitaire is None else round(self.prix_unitaire * self.quantite, 2)

    @property
    def radie(self) -> bool:
        return bool(self.radie_le)


_CHAMPS = [f.name for f in fields(Article) if f.name != "id"]


def _date(v: str, nom: str, obligatoire: bool = False) -> str:
    v = (v or "").strip()
    if not v:
        if obligatoire:
            raise ErreurInventaire(f"{nom}: إجباري.")
        return ""
    try:
        d = date.fromisoformat(v)
    except ValueError:
        raise ErreurInventaire(f"{nom}: تاريخ غير صحيح.") from None
    if d > date.today():
        raise ErreurInventaire(f"{nom}: تاريخ في المستقبل.")
    return v


def prochain_numero(conn: sqlite3.Connection) -> int:
    return (conn.execute("SELECT MAX(numero) FROM inventaire").fetchone()[0] or 0) + 1


def _ligne(r: sqlite3.Row) -> Article:
    return Article(**{k: (r[k] if r[k] is not None else ("" if k not in ("prix_unitaire", "unite_id", "numero")
                                                             else None)) for k in _CHAMPS}, id=r["id"])


def lire(conn: sqlite3.Connection, aid: int) -> Article:
    r = conn.execute("SELECT * FROM inventaire WHERE id=?", (aid,)).fetchone()
    if r is None:
        raise ErreurInventaire("سطر غير موجود في السجل.")
    return _ligne(r)


def enregistrer(conn: sqlite3.Connection, a: Article) -> int:
    a.designation = " ".join((a.designation or "").split())
    if not a.designation:
        raise ErreurInventaire("وصف التجهيزات إجباري.")
    a.date_inscription = _date(a.date_inscription, "تاريخ التسجيل", True)
    a.facture_date = _date(a.facture_date, "تاريخ الفاتورة")
    try:
        a.quantite = int(a.quantite)
    except (TypeError, ValueError):
        raise ErreurInventaire("عدد الأشياء: رقم.") from None
    if a.quantite <= 0:
        raise ErreurInventaire("عدد الأشياء: واحد على الأقل.")
    if a.prix_unitaire not in (None, ""):
        try:
            a.prix_unitaire = round(float(str(a.prix_unitaire).replace(",", ".").replace(" ", "")), 2)
        except ValueError:
            raise ErreurInventaire("ثمن الوحدة: رقم.") from None
        if a.prix_unitaire < 0:
            raise ErreurInventaire("ثمن الوحدة لا يكون سالباً.")
    else:
        a.prix_unitaire = None
    a.type = " ".join((a.type or "").split()) or "أخرى"
    if a.numero in (None, ""):
        a.numero = prochain_numero(conn)
    try:
        a.numero = int(a.numero)
    except (TypeError, ValueError):
        raise ErreurInventaire("الرقم الترتيبي: رقم.") from None
    if a.numero <= 0:
        raise ErreurInventaire("الرقم الترتيبي: رقم موجب.")
    autre = conn.execute("SELECT id FROM inventaire WHERE numero=? AND id IS NOT ?", (a.numero, a.id)).fetchone()
    if autre:
        raise ErreurInventaire(f"الرقم الترتيبي {a.numero} مستعمل في سطر آخر من السجل.")
    a.radie_le = _date(a.radie_le, "تاريخ المحو")
    if a.radie_le and not (a.radiation_motif or "").strip():
        raise ErreurInventaire("سبب محو التجهيزات من السجل إجباري.")
    if not a.radie_le:
        a.radiation_motif = a.radiation_decision = ""
    vals = {k: getattr(a, k) for k in _CHAMPS}
    for k, v in vals.items():
        if isinstance(v, str):
            vals[k] = v.strip() or None
    vals["designation"], vals["date_inscription"], vals["type"] = a.designation, a.date_inscription, a.type
    with conn:
        if a.id is None:
            cur = conn.execute(f"INSERT INTO inventaire({', '.join(_CHAMPS)}) VALUES ({', '.join('?' * len(_CHAMPS))})",
                               [vals[k] for k in _CHAMPS])
            a.id = cur.lastrowid
        else:
            conn.execute(f"UPDATE inventaire SET {', '.join(k + '=?' for k in _CHAMPS)} WHERE id=?",
                         [vals[k] for k in _CHAMPS] + [a.id])
    journaliser(conn, "inventaire", "inventaire", a.id, f"{a.numero} {a.designation}")
    return a.id


def radier(conn: sqlite3.Connection, aid: int, le: str, motif: str, decision: str = "") -> None:
    """محو التجهيزات من السجل: يبقى السطر مؤشراً عليه (التاريخ، السبب، رقم القرار)."""
    a = lire(conn, aid)
    a.radie_le, a.radiation_motif, a.radiation_decision = le, motif, decision
    if not (le or "").strip():
        raise ErreurInventaire("تاريخ المحو إجباري.")
    enregistrer(conn, a)


def supprimer(conn: sqlite3.Connection, aid: int) -> None:
    """حذف سطر أُدخل خطأً (المحو العادي يمر عبر radier)."""
    a = lire(conn, aid)
    with conn:
        conn.execute("DELETE FROM inventaire WHERE id=?", (aid,))
    journaliser(conn, "suppression", "inventaire", aid, f"{a.numero} {a.designation}")


def lister(conn: sqlite3.Connection, type_: str | None = None, texte: str = "", radies: bool = True,
           ordre: str = "type") -> list[Article]:
    """ordre: «type» (حسب نوع التجهيز ثم الرقم) أو «numero» (ترتيب السجل)."""
    sql = "SELECT * FROM inventaire WHERE 1=1"
    args: list = []
    if type_:
        sql += " AND type=?"
        args.append(type_)
    if not radies:
        sql += " AND radie_le IS NULL"
    t = " ".join((texte or "").split())
    if t:
        sql += (" AND (designation LIKE ? OR fournisseur LIKE ? OR affectation LIKE ? OR facture_numero LIKE ? "
                "OR CAST(numero AS TEXT)=?)")
        args += [f"%{t}%"] * 4 + [t]
    sql += " ORDER BY " + ("type, numero" if ordre == "type" else "numero")
    return [_ligne(r) for r in conn.execute(sql, args)]


def types_utilises(conn: sqlite3.Connection) -> list[str]:
    deja = [r[0] for r in conn.execute("SELECT DISTINCT type FROM inventaire ORDER BY type")]
    return list(dict.fromkeys(list(TYPES) + deja))


def synthese(conn: sqlite3.Connection) -> list[dict]:
    """حسب النوع: عدد الأسطر، عدد الأشياء (القائمة والممحوة)، القيمة، والحالة."""
    res = []
    for t in types_utilises(conn):
        ls = lister(conn, t)
        if not ls:
            continue
        actifs = [a for a in ls if not a.radie]
        res.append({"type": t, "lignes": len(ls), "quantite": sum(a.quantite for a in actifs),
                    "radies": sum(a.quantite for a in ls if a.radie),
                    "valeur": round(sum(a.total or 0 for a in actifs), 2),
                    "etats": {e: sum(a.quantite for a in actifs if a.entretien == e) for e in ETATS}})
    return res


def pour_passation(conn: sqlite3.Connection) -> list[list[str]]:
    """أسطر محضر تسليم المهام (تجهيزات الإدارة): النوع، العدد، رقم الجرد، صالح، يحتاج صيانة، معطل، ملاحظات."""
    lignes = []
    for a in lister(conn, radies=False, ordre="numero"):
        e = {k: (f"{a.quantite:02d}" if a.entretien == k else "") for k in ETATS}
        rem = a.entretien if a.entretien and a.entretien not in ETATS else ""
        lignes.append([a.designation, f"{a.quantite:02d}", str(a.numero), e["صالح"], e["يحتاج صيانة"], e["معطل"],
                       "، ".join(x for x in (a.affectation, rem) if x)])
    return lignes


# ---------- الوثيقة ----------

def _mt(v: float | None) -> str:
    return "" if v is None else f"{v:,.2f}".replace(",", " ")


def generer_registre(conn: sqlite3.Connection, dossier: DossierDonnees, type_: str | None = None,
                     radies: bool = True) -> Path:
    """سجل الجرد (Word، أفقي) بأعمدة النموذج الورقي، لكل الأنواع أو لنوع واحد، مع المجموع."""
    from docx.enum.section import WD_ORIENT
    from docx.shared import Cm

    from idara.services.docs_association import _cellule, _nouveau, _ombre, para, tableau
    from idara.services.soutien import _entete
    ls = lister(conn, type_, radies=radies)
    if not ls:
        raise ErreurInventaire("لا تجهيزات في السجل" + (f" من نوع «{type_}»" if type_ else "") + ".")
    d = _nouveau()
    s = d.sections[0]
    s.orientation = WD_ORIENT.LANDSCAPE
    s.page_width, s.page_height = s.page_height, s.page_width
    s.left_margin = s.right_margin = Cm(1.0)
    s.top_margin = s.bottom_margin = Cm(1.0)
    _entete(d, conn, dossier, "سجل الجرد", (f"نوع التجهيز: {type_}" if type_ else "كل أنواع التجهيزات")
            + f" · الوضعية في {date.today():%d/%m/%Y}")
    # رأس من مستويين كما في السجل الورقي
    cols = [("الرقم الترتيبي", None), ("تاريخ التسجيل", None), ("وصف التجهيزات", None),
            ("مصدرها", "رقم الفاتورة وتاريخها"), ("مصدرها", "اسم التاجر"), ("عدد الأشياء", None),
            ("ثمن الشراء", "الوحدة"), ("ثمن الشراء", "المجموع"), ("تخصيص التجهيزات", None),
            ("حالة صيانتها", None), ("محو التجهيزات من السجل", "التاريخ"), ("محو التجهيزات من السجل", "السبب"),
            ("محو التجهيزات من السجل", "رقم القرار"), ("ملاحظات", None)]
    larg = [1.5, 1.9, 4.0, 2.4, 2.2, 1.3, 1.7, 1.9, 2.4, 1.9, 1.7, 2.0, 1.4, 1.6]
    t = tableau(d, 2 + len(ls) + 1, len(cols), largeurs=larg)
    j = 0
    while j < len(cols):
        titre, sous = cols[j]
        if sous is None:
            c = t.cell(0, j).merge(t.cell(1, j))
            _cellule(c, titre, gras=True, taille=8)
            j += 1
            continue
        k = j
        while k + 1 < len(cols) and cols[k + 1][0] == titre:
            k += 1
        c = t.cell(0, j).merge(t.cell(0, k)) if k > j else t.cell(0, j)
        _cellule(c, titre, gras=True, taille=8)
        for m in range(j, k + 1):
            _cellule(t.cell(1, m), cols[m][1], gras=True, taille=7)
        j = k + 1
    for i in range(2):
        for c in t.rows[i].cells:
            _ombre(c, "E7E8F8")
    total_q, total_v = 0, 0.0
    for i, a in enumerate(ls, start=2):
        fact = " ".join(x for x in (a.facture_numero, tx.date_chiffres(a.facture_date) if a.facture_date else "") if x)
        vals = [str(a.numero), tx.date_chiffres(a.date_inscription), a.designation, fact, a.fournisseur,
                str(a.quantite), _mt(a.prix_unitaire), _mt(a.total), a.affectation, a.entretien,
                tx.date_chiffres(a.radie_le) if a.radie_le else "", a.radiation_motif, a.radiation_decision,
                a.remarques]
        for jj, v in enumerate(vals):
            _cellule(t.cell(i, jj), v or "", taille=8)
        if not a.radie:
            total_q += a.quantite
            total_v += a.total or 0
    r = 2 + len(ls)
    c = t.cell(r, 0).merge(t.cell(r, 4))
    _cellule(c, "المجموع (دون التجهيزات الممحوة)", gras=True, taille=8)
    _cellule(t.cell(r, 5), str(total_q), gras=True, taille=8)
    _cellule(t.cell(r, 7), _mt(round(total_v, 2)), gras=True, taille=8)
    para(d, "", apres=2)
    rep = dossier.archives / "الجرد"
    rep.mkdir(parents=True, exist_ok=True)
    nom = "سجل_الجرد" + (f"_{type_}" if type_ else "")
    chemin = rep / f"{datetime.now():%Y%m%d_%H%M%S}_{nom}.docx"
    n = 1
    while chemin.exists():
        n += 1
        chemin = chemin.with_name(f"{chemin.stem}_{n}.docx")
    d.save(chemin)
    return chemin
