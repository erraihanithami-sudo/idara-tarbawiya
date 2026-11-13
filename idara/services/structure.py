"""البنية المادية للمؤسسة (طلب المدير 2026-11-13).

صفحة يُجرد فيها عدد كل مكوّن: الحجرات الدراسية، المباني الإدارية، حجرات التعليم الأولي، قاعة الموارد للدعم والتأهيل،
الملاعب، المرافق الصحية (للتلاميذ، للأساتذة، للتعليم الأولي، وللأشخاص في وضعية إعاقة). في المجموعة المدرسية يُدخل
العدد لكل وحدة ويُحسب المجموع. منها تُولَّد وثيقة البنية المادية، وتغذي محور «البنايات» في محضر تسليم المهام.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path

from idara.data.dossier import DossierDonnees
from idara.data.journal import journaliser
from idara.services import etablissement as etab_srv

# بترتيب نموذج المدير وتسمياته («البنية المادية للمؤسسة» في السبورة المرجعية، 2026-11-13)
ELEMENTS = [
    ("salles", "عدد حجرات التعليم العام"),
    ("salles_prescolaire", "عدد حجرات التعليم الأولي"),
    ("sanitaires_prescolaire", "المرافق الصحية للتعليم الأولي"),
    ("salle_ressources", "قاعة الموارد للتأهيل والدعم"),
    ("sanitaires_handicap", "مرافق صحية لذوي الاحتياجات الخاصة"),
    ("batiments_admin", "المكاتب الإدارية"),
    ("sanitaires_eleves", "مرافق صحية للتلاميذ"),
    ("sanitaires_enseignants", "مرافق صحية للأساتذة"),
    ("terrains", "ملاعب"),
    ("magasins", "مخازن"),
]


class ErreurStructure(ValueError):
    """رسالة موجهة للمدير بالعربية."""


def unites(conn: sqlite3.Connection) -> list[tuple[int | None, str]]:
    """أعمدة الجدول: وحدات المجموعة المدرسية، أو المؤسسة وحدها."""
    us = [(r[0], r[1]) for r in conn.execute("SELECT id, nom_ar FROM unite_scolaire ORDER BY id")]
    if us and etab_srv.est_groupe(conn):
        return us
    e = etab_srv.lire_etablissement(conn)
    return [(None, e.nom_ar if e else "المؤسسة")]


def elements(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    """المكونات المقترحة ثم ما أضافه المدير، بالترتيب."""
    autres = [(r[0], r[1]) for r in conn.execute(
        "SELECT element, libelle FROM structure_materielle WHERE element LIKE 'autre:%' GROUP BY element "
        "ORDER BY MIN(ordre), element")]
    return ELEMENTS + autres


def tableau(conn: sqlite3.Connection) -> dict:
    """{"unites": [...], "lignes": [{"element", "libelle", "nombres": {unite_id: n}, "total", "remarques"}]}"""
    us = unites(conn)
    valeurs = {(r["element"], r["unite_id"]): r["nombre"] for r in conn.execute(
        "SELECT element, unite_id, nombre FROM structure_materielle")}
    rem = {r[0]: r[1] or "" for r in conn.execute("SELECT element, remarques FROM structure_remarque")}
    lignes = []
    for cle, lib in elements(conn):
        nb = {uid: valeurs.get((cle, uid)) for uid, _ in us}
        connus = [v for v in nb.values() if v is not None]
        lignes.append({"element": cle, "libelle": lib, "nombres": nb,
                       "total": sum(connus) if connus else None, "remarques": rem.get(cle, "")})
    return {"unites": us, "lignes": lignes}


def saisi(conn: sqlite3.Connection) -> bool:
    return bool(conn.execute("SELECT 1 FROM structure_materielle LIMIT 1").fetchone())


def _nombre(v, lib: str) -> int | None:
    if v is None or str(v).strip() == "":
        return None
    try:
        n = int(str(v).strip())
    except ValueError:
        raise ErreurStructure(f"{lib}: عدد صحيح.") from None
    if n < 0:
        raise ErreurStructure(f"{lib}: لا يكون العدد سالباً.")
    return n


def enregistrer(conn: sqlite3.Connection, lignes: list[dict]) -> None:
    """lignes: [{"element", "libelle", "nombres": {unite_id: نص أو عدد}, "remarques"}]. الخانة الفارغة تُحذف."""
    us = {uid for uid, _ in unites(conn)}
    propres, vides, rems = [], [], []
    for k, l in enumerate(lignes):
        lib = " ".join((l.get("libelle") or "").split())
        cle = l["element"]
        if cle.startswith("autre:") or cle == "autre":
            if not lib:
                continue
            cle = "autre:" + lib
        for uid, v in l.get("nombres", {}).items():
            if uid not in us:
                continue
            n = _nombre(v, lib)
            (vides if n is None else propres).append((cle, lib, uid, n, k))
        rems.append((cle, (l.get("remarques") or "").strip() or None))
    with conn:
        for cle, lib, uid, n, k in propres:
            conn.execute("DELETE FROM structure_materielle WHERE element=? AND unite_id IS ?", (cle, uid))
            conn.execute("INSERT INTO structure_materielle(element, libelle, unite_id, nombre, ordre) VALUES (?,?,?,?,?)",
                         (cle, lib, uid, n, k))
        for cle, _, uid, _, _ in vides:
            conn.execute("DELETE FROM structure_materielle WHERE element=? AND unite_id IS ?", (cle, uid))
        for cle, r in rems:
            conn.execute("INSERT INTO structure_remarque(element, remarques) VALUES (?,?) ON CONFLICT(element) "
                         "DO UPDATE SET remarques=excluded.remarques", (cle, r))
    journaliser(conn, "structure", "structure_materielle", None, f"{len(propres)} خانة")


def supprimer_element(conn: sqlite3.Connection, cle: str) -> None:
    """حذف مكوّن أضافه المدير (المكونات المقترحة تبقى، ويكفي إفراغ خاناتها)."""
    if not cle.startswith("autre:"):
        raise ErreurStructure("لا يُحذف إلا مكوّن أضفتموه؛ المكونات المقترحة يكفي إفراغ خاناتها.")
    with conn:
        conn.execute("DELETE FROM structure_materielle WHERE element=?", (cle,))
        conn.execute("DELETE FROM structure_remarque WHERE element=?", (cle,))


def pour_passation(conn: sqlite3.Connection) -> list[list[str]]:
    """أسطر محور «البنايات» في محضر تسليم المهام: الوحدة، النوع، العدد، ثم خانات الحالة (يدوية)، والملاحظة."""
    t = tableau(conn)
    res = []
    for uid, nom in t["unites"]:
        for l in t["lignes"]:
            n = l["nombres"].get(uid)
            if n:
                res.append([nom, l["libelle"], f"{n:02d}", "", "", l["remarques"]])
    return res


def generer(conn: sqlite3.Connection, dossier: DossierDonnees) -> Path:
    """وثيقة البنية المادية للمؤسسة (Word)."""
    from idara.services.docs_association import _cellule, _nouveau, _ombre, para, tableau as tab
    from idara.services.soutien import _entete, _signature
    if not saisi(conn):
        raise ErreurStructure("لم يُدخل أي عدد في البنية المادية بعد.")
    t = tableau(conn)
    us = t["unites"]
    groupe = len(us) > 1
    d = _nouveau()
    _entete(d, conn, dossier, "البنية المادية للمؤسسة", f"الوضعية في {date.today():%d/%m/%Y}")
    entetes = ["المكوّن"] + [n for _, n in us] + (["المجموع"] if groupe else []) + ["ملاحظات"]
    reste = 17.4 - 5.0 - 3.6
    largeurs = [5.0] + [round(reste / (len(us) + (1 if groupe else 0)), 2)] * (len(us) + (1 if groupe else 0)) + [3.6]
    lignes = [l for l in t["lignes"] if l["total"] is not None or l["remarques"]]
    tb = tab(d, 1 + len(lignes), len(entetes), largeurs=largeurs)
    for j, h in enumerate(entetes):
        _cellule(tb.cell(0, j), h, gras=True, taille=10)
        _ombre(tb.cell(0, j), "E7E8F8")
    for i, l in enumerate(lignes, start=1):
        vals = [l["libelle"]] + ["" if l["nombres"][uid] is None else f"{l['nombres'][uid]:02d}" for uid, _ in us]
        if groupe:
            vals.append("" if l["total"] is None else f"{l['total']:02d}")
        vals.append(l["remarques"])
        for j, v in enumerate(vals):
            _cellule(tb.cell(i, j), v, gras=(j == 0), taille=10)
    para(d, "", apres=4)
    _signature(d, conn)
    rep = dossier.archives / "البنية المادية"
    rep.mkdir(parents=True, exist_ok=True)
    chemin = rep / f"{datetime.now():%Y%m%d_%H%M%S}_البنية_المادية.docx"
    n = 1
    while chemin.exists():
        n += 1
        chemin = chemin.with_name(f"{chemin.stem}_{n}.docx")
    d.save(chemin)
    return chemin
