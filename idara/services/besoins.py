"""تحديد حاجيات المؤسسة في إطار مشروع المؤسسة المندمج (طلب المدير 2026-11-23).

الحاجيات تُدخل في نافذة منبثقة (المجال، الحاجة، المبررات، الكمية، الكلفة التقديرية، الأولوية، مصدر التمويل،
وارتباطها بعملية من عمليات المشروع)، وتُحفظ لكل سنة دراسية. والوثيقة تُطبع ممهورة بجدول توقيعات أعضاء مجلس
التدبير (من تركيبة المجلس المسجلة في «مجالس المؤسسة») وتوقيع مدير المؤسسة وخاتمها.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path

from idara.data.dossier import DossierDonnees
from idara.services import annee as annee_srv
from idara.services import documents as dc
from idara.services import fiches
from idara.services import textes as tx
from idara.services.docs_association import _cellule, _nouveau, _ombre, para, tableau

DOMAINES = ("الحاجيات التربوية والديداكتيكية", "التجهيزات والعتاد", "البنايات والصيانة والتأهيل",
            "الموارد البشرية", "التكوين والتأطير", "الحياة المدرسية والأنشطة", "الدعم الاجتماعي",
            "الرقمنة وتكنولوجيا المعلومات", "حاجيات أخرى")
PRIORITES = ("عالية", "متوسطة", "عادية")
SOURCES = ("جمعية دعم مدرسة النجاح", "المديرية الإقليمية", "الأكاديمية الجهوية", "الجماعة الترابية",
           "جمعية آباء وأولياء التلاميذ", "الشركاء", "المبادرة الوطنية للتنمية البشرية", "أخرى")


class ErreurBesoin(ValueError):
    """رسالة موجهة للمدير بالعربية."""


def _txt(v) -> str:
    return " ".join(str(v or "").split())


def _annee(conn, annee: str | None = None) -> str:
    if annee:
        return annee
    a = annee_srv.annee_courante(conn)
    if a is None:
        raise ErreurBesoin("لا سنة دراسية جارية.")
    return a["libelle"]


def _cle(conn, annee: str | None) -> str:
    return f"besoins_pe_{_annee(conn, annee)}"


def _charger(conn, annee=None) -> dict:
    d = fiches.lire(conn, _cle(conn, annee)) or {}
    return {"suivant": int(d.get("suivant", 1)), "lignes": list(d.get("lignes", [])),
            "seance": d.get("seance", "")}


def besoins(conn: sqlite3.Connection, annee: str | None = None) -> list[dict]:
    """مرتبة حسب المجال ثم الأولوية."""
    rang = {p: i for i, p in enumerate(PRIORITES)}
    dom = {p: i for i, p in enumerate(DOMAINES)}
    return sorted(_charger(conn, annee)["lignes"],
                  key=lambda b: (dom.get(b["domaine"], 99), rang.get(b["priorite"], 9), b["id"]))


def besoin(conn, bid: int, annee: str | None = None) -> dict:
    for b in _charger(conn, annee)["lignes"]:
        if b["id"] == bid:
            return b
    raise ErreurBesoin("الحاجة غير موجودة.")


def _nombre(v, lib: str, entier: bool = False):
    t = _txt(v).replace(",", ".").replace(" ", "")
    if not t:
        return None
    try:
        x = float(t)
    except ValueError:
        raise ErreurBesoin(f"«{lib}» رقم.") from None
    if x < 0:
        raise ErreurBesoin(f"«{lib}» لا يكون سالباً.")
    return int(x) if (entier or x.is_integer()) else round(x, 2)


def _valider(v: dict) -> dict:
    b = {"domaine": _txt(v.get("domaine")), "besoin": _txt(v.get("besoin")),
         "justification": _txt(v.get("justification")), "quantite": _nombre(v.get("quantite"), "الكمية", True),
         "cout": _nombre(v.get("cout"), "الكلفة التقديرية"), "priorite": _txt(v.get("priorite")) or "متوسطة",
         "source": _txt(v.get("source")), "operation": _txt(v.get("operation"))}
    if b["domaine"] not in DOMAINES:
        raise ErreurBesoin("اختر مجال الحاجة.")
    if not b["besoin"]:
        raise ErreurBesoin("اكتب الحاجة.")
    if b["priorite"] not in PRIORITES:
        raise ErreurBesoin("الأولوية: عالية أو متوسطة أو عادية.")
    return b


def enregistrer(conn: sqlite3.Connection, valeurs: dict, bid: int | None = None, annee: str | None = None) -> int:
    b = _valider(valeurs)
    d = _charger(conn, annee)
    if bid is None:
        bid = d["suivant"]
        d["suivant"] += 1
        d["lignes"].append({"id": bid, **b})
    else:
        for i, x in enumerate(d["lignes"]):
            if x["id"] == bid:
                d["lignes"][i] = {"id": bid, **b}
                break
        else:
            raise ErreurBesoin("الحاجة غير موجودة.")
    fiches.ecrire(conn, _cle(conn, annee), d)
    return bid


def supprimer(conn: sqlite3.Connection, bid: int, annee: str | None = None) -> None:
    d = _charger(conn, annee)
    d["lignes"] = [x for x in d["lignes"] if x["id"] != bid]
    fiches.ecrire(conn, _cle(conn, annee), d)


def synthese(conn: sqlite3.Connection, annee: str | None = None) -> dict:
    bs = besoins(conn, annee)
    par = {}
    for b in bs:
        s = par.setdefault(b["domaine"], {"nombre": 0, "cout": 0})
        s["nombre"] += 1
        s["cout"] += b["cout"] or 0
    return {"nombre": len(bs), "cout": sum(b["cout"] or 0 for b in bs), "par_domaine": par,
            "prioritaires": sum(1 for b in bs if b["priorite"] == "عالية")}


def operations_projet(conn: sqlite3.Connection) -> list[str]:
    """عمليات مشروع المؤسسة النشيط (لربط الحاجة بعملية)."""
    from idara.services import projet_etab as pe
    p = pe.projet_actif(conn)
    return [o["intitule"] for o in pe.operations(conn, p["id"])] if p else []


def _dh(v) -> str:
    if v is None:
        return "—"
    return f"{v:,.2f}".replace(",", " ").replace(".00", "")


def generer(conn: sqlite3.Connection, dossier: DossierDonnees, annee: str | None = None,
            date_seance: str = "") -> Path:
    """الوثيقة: الحاجيات حسب المجال، والكلفة الإجمالية، ثم توقيعات أعضاء مجلس التدبير."""
    from docx.shared import Cm
    from idara.services import conseils_etab as ce
    from idara.services import projet_etab as pe
    annee = _annee(conn, annee)
    bs = besoins(conn, annee)
    if not bs:
        raise ErreurBesoin("لا حاجيات مسجلة لهذه السنة. أضف الحاجيات أولاً.")
    try:
        ms = ce.membres_actifs(conn, "gestion", annee)
    except ce.ErreurConseil:
        ms = []
    if not ms:
        raise ErreurBesoin("سجّل تركيبة مجلس التدبير أولاً (مجالس المؤسسة) لتُطبع توقيعات أعضائه.")
    try:
        c = dc.champs_communs(conn)
    except dc.ErreurDocument as e:
        raise ErreurBesoin(str(e)) from None
    d = _nouveau(paysage=True)
    from idara.services import etablissement as etab_srv
    e = etab_srv.lire_etablissement(conn)
    if e and e.logo_path and (dossier.racine / e.logo_path).exists():
        d.add_picture(str(dossier.racine / e.logo_path), width=Cm(24))
    para(d, "وثيقة تحديد حاجيات المؤسسة", gras=True, taille=20, centre=True, apres=0)
    para(d, "في إطار مشروع المؤسسة المندمج", gras=True, taille=15, centre=True, apres=0)
    p = pe.projet_actif(conn)
    sous = f"الموسم الدراسي {annee}" + (f" · {p['intitule']} ({p['annee_debut']} – {p['annee_fin']})" if p else "")
    para(d, sous, centre=True, taille=12, apres=6)
    quand = f" المنعقد بتاريخ {tx.date_chiffres(date_seance)}" if date_seance else ""
    para(d, f"بناءً على تشخيص وضعية المؤسسة وعلى أولويات مشروعها المندمج، وبعد التداول في اجتماع مجلس تدبير "
            f"{c['etablissement']}{quand}، حُددت حاجيات المؤسسة كما يلي:", taille=12, apres=6)
    entetes = ("ر.ت", "الحاجة", "المبررات", "الكمية", "الكلفة التقديرية (درهم)", "الأولوية",
               "مصدر التمويل المقترح", "العملية المرتبطة")
    largeurs = [1.0, 5.4, 5.6, 1.6, 2.8, 1.9, 3.6, 3.6]
    groupes: list[tuple[str, list[dict]]] = []
    for b in bs:
        if not groupes or groupes[-1][0] != b["domaine"]:
            groupes.append((b["domaine"], []))
        groupes[-1][1].append(b)
    n_lignes = 1 + sum(1 + len(g) for _, g in groupes) + 1
    t = tableau(d, n_lignes, len(entetes), largeurs=largeurs)
    for j, lib in enumerate(entetes):
        _cellule(t.cell(0, j), lib, gras=True, taille=10)
        _ombre(t.cell(0, j))
    i, k = 1, 0
    for dom, g in groupes:
        cel = t.cell(i, 0).merge(t.cell(i, len(entetes) - 1))
        _cellule(cel, f"{dom} ({len(g)})", gras=True, taille=11)
        _ombre(cel, "F3EAD3")
        i += 1
        for b in g:
            k += 1
            for j, v in enumerate((str(k), b["besoin"], b["justification"] or "—",
                                   "—" if b["quantite"] is None else str(b["quantite"]), _dh(b["cout"]),
                                   b["priorite"], b["source"] or "—", b["operation"] or "—")):
                _cellule(t.cell(i, j), v, taille=10, centre=j not in (1, 2))
            i += 1
    cel = t.cell(i, 0).merge(t.cell(i, 3))
    _cellule(cel, "الكلفة الإجمالية التقديرية", gras=True, taille=11)
    _ombre(cel)
    _cellule(t.cell(i, 4), _dh(synthese(conn, annee)["cout"]), gras=True, taille=11)
    _ombre(t.cell(i, 4))
    cel = t.cell(i, 5).merge(t.cell(i, len(entetes) - 1))
    _cellule(cel, f"{len(bs)} حاجة، منها {synthese(conn, annee)['prioritaires']} ذات أولوية عالية", taille=10)
    para(d, apres=8)
    para(d, f"حرر ب{c['ville']} في: {tx.date_chiffres(date.today().isoformat())}", taille=12, apres=6)
    para(d, "توقيعات أعضاء مجلس التدبير", gras=True, taille=15, centre=True, apres=2)
    ts = tableau(d, 1 + len(ms), 4, largeurs=[1.2, 8.5, 8.5, 6.5])
    for j, lib in enumerate(("ر.ت", "الاسم", "الصفة", "التوقيع")):
        _cellule(ts.cell(0, j), lib, gras=True)
        _ombre(ts.cell(0, j))
    for r, m in enumerate(ms, start=1):
        _cellule(ts.cell(r, 0), str(r), taille=12)
        _cellule(ts.cell(r, 1), m["nom"], taille=12)
        _cellule(ts.cell(r, 2), m["qualite"], taille=12)
        ts.rows[r].height = Cm(1.0)
    para(d, apres=8)
    para(d, f"{c['mudir_moassasa']} (الخاتم والتوقيع)", gras=True, taille=13)
    rep = dossier.archives / annee.replace("/", "-") / "مشروع المؤسسة"
    rep.mkdir(parents=True, exist_ok=True)
    chemin = rep / f"{datetime.now():%Y%m%d_%H%M%S}_وثيقة تحديد حاجيات المؤسسة.docx"
    d.save(chemin)
    return chemin
