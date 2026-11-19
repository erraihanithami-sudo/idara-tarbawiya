"""تدبير تسجيلات التلاميذ (طلب المدير 2026-11-07): لائحة التلاميذ حسب المستوى، وأمام كل تلميذ خانات واجبات
التسجيل (التأمين المدرسي، الجمعية الرياضية، جمعية تنمية التعاون المدرسي)، مع عدّاد تراكمي لكل عنصر.

المبالغ (كما حددها المدير): التأمين 8 دراهم في الوسط القروي و12 درهماً في الوسط الحضري (وسط المؤسسة يُحدَّد في
الإعدادات)، الجمعية الرياضية 10 دراهم، جمعية تنمية التعاون المدرسي 10 دراهم.

طلب المدير 2026-11-19: المدير يكتب المبالغ بنفسه في «تهيئة المبالغ» (نافذة منبثقة)، وتُعتمد بدل ما سبق. ولا يظهر
تلاميذ التعليم الأولي في اللائحة لأنهم يُؤمَّنون من خلال جمعيتهم. واللائحة تُعرض حسب القسم.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime

from idara.services import annee as annee_srv
from idara.services import etablissement as etab_srv

ELEMENTS = {"assurance": "التأمين المدرسي", "sport": "الجمعية الرياضية", "cooperative": "جمعية تنمية التعاون المدرسي"}
ASSURANCE = {"rural": 8, "urbain": 12}
MONTANTS_FIXES = {"sport": 10, "cooperative": 10}


class ErreurFrais(ValueError):
    """رسالة موجهة للمدير بالعربية."""


def montants_saisis(conn: sqlite3.Connection) -> dict[str, float]:
    """المبالغ التي كتبها المدير في «تهيئة المبالغ»."""
    from idara.services import fiches
    return {k: v for k, v in (fiches.lire(conn, "frais_montants") or {}).items() if k in ELEMENTS and v is not None}


def _nombre(v):
    return int(v) if float(v).is_integer() else round(float(v), 2)


def montants(conn: sqlite3.Connection) -> dict[str, int | float | None]:
    """مبلغ كل عنصر: ما كتبه المدير، وإلا القيم السابقة (التأمين حسب الوسط، None إن لم يُحدَّد)."""
    e = etab_srv.lire_etablissement(conn)
    res = {"assurance": ASSURANCE.get(e.milieu if e else ""), **MONTANTS_FIXES}
    res.update({k: _nombre(v) for k, v in montants_saisis(conn).items()})
    return res


def definir_montants(conn: sqlite3.Connection, valeurs: dict[str, object]) -> dict:
    from idara.services import fiches
    propres = {}
    for k, v in valeurs.items():
        if k not in ELEMENTS:
            raise ErreurFrais("عنصر تسجيل غير معروف.")
        t = str(v if v is not None else "").replace(",", ".").strip()
        if not t:
            raise ErreurFrais(f"اكتب مبلغ «{ELEMENTS[k]}».")
        try:
            x = float(t)
        except ValueError:
            raise ErreurFrais(f"مبلغ «{ELEMENTS[k]}» رقم بالدرهم.") from None
        if x < 0:
            raise ErreurFrais(f"مبلغ «{ELEMENTS[k]}» لا يكون سالباً.")
        propres[k] = x
    fiches.ecrire(conn, "frais_montants", {**montants_saisis(conn), **propres})
    return montants(conn)


def _prescolaire(x) -> bool:
    from idara.services.massar import niveaux_du_code_classe
    if x["niveau"]:
        return x["niveau"].startswith("PS")
    ns = niveaux_du_code_classe(x["classe"] or "")
    return bool(ns) and all(n.startswith("PS") for n in ns) or (x["classe"] or "").upper().startswith(("PS", "MS", "GS"))


def classes(conn: sqlite3.Connection, unite: str | None = None) -> list[str]:
    """أقسام اللائحة (دون أقسام التعليم الأولي)."""
    return list(dict.fromkeys(x["classe"] for x in lister(conn, unite=unite)))


def _annee(conn) -> int:
    a = annee_srv.annee_courante(conn)
    if a is None:
        raise ErreurFrais("لا سنة دراسية جارية.")
    return a["id"]


def lister(conn: sqlite3.Connection, niveau: str | None = None, unite: str | None = None,
           classe: str | None = None) -> list[dict]:
    """التلاميذ الذين يتابعون دراستهم (دون التعليم الأولي)، مرتبين حسب المستوى ثم القسم ثم الاسم، مع ما أدّوه."""
    aid = _annee(conn)
    sql = ("SELECT e.id, e.code_massar, e.nom_ar, e.prenom_ar, c.code AS classe, n.code AS niveau, "
           "COALESCE(f.assurance,0) AS assurance, COALESCE(f.sport,0) AS sport, "
           "COALESCE(f.cooperative,0) AS cooperative FROM inscription i JOIN eleve e ON e.id=i.eleve_id "
           "JOIN classe c ON c.id=i.classe_id LEFT JOIN niveau n ON n.id=i.niveau_id "
           "LEFT JOIN frais_inscription f ON f.eleve_id=e.id AND f.annee_id=i.annee_id "
           "WHERE i.annee_id=? AND i.statut IN ('inscrit','arrive')")
    args: list = [aid]
    if niveau:
        sql += " AND n.code=?"
        args.append(niveau)
    if unite:
        sql += " AND c.unite_id=(SELECT id FROM unite_scolaire WHERE nom_ar=?)"
        args.append(unite)
    if classe:
        sql += " AND c.code=?"
        args.append(classe)
    sql += " ORDER BY c.code, n.ordre, e.nom_ar, e.prenom_ar"
    return [x for x in (dict(r) for r in conn.execute(sql, args)) if not _prescolaire(x)]


def marquer(conn: sqlite3.Connection, eleve_id: int, element: str, paye: bool) -> None:
    if element not in ELEMENTS:
        raise ErreurFrais("عنصر تسجيل غير معروف.")
    aid = _annee(conn)
    with conn:
        conn.execute("INSERT INTO frais_inscription(annee_id, eleve_id) VALUES (?,?) ON CONFLICT DO NOTHING",
                     (aid, eleve_id))
        conn.execute(f"UPDATE frais_inscription SET {element}=?, maj_le=? WHERE annee_id=? AND eleve_id=?",
                     (1 if paye else 0, datetime.now().isoformat(timespec="seconds"), aid, eleve_id))


def marquer_tous(conn: sqlite3.Connection, eleves: list[int], element: str, paye: bool = True) -> int:
    for e in eleves:
        marquer(conn, e, element, paye)
    return len(eleves)


def totaux(conn: sqlite3.Connection, niveau: str | None = None, unite: str | None = None,
           classe: str | None = None) -> dict:
    """العدد والمبلغ لكل عنصر، والمجموع التراكمي."""
    liste = lister(conn, niveau, unite, classe)
    m = montants(conn)
    res = {"eleves": len(liste), "elements": {}, "total": 0}
    for k, lib in ELEMENTS.items():
        n = sum(1 for x in liste if x[k])
        mt = n * m[k] if m[k] is not None else None
        res["elements"][k] = {"libelle": lib, "payes": n, "montant_unitaire": m[k], "montant": mt}
        res["total"] += mt or 0
    res["total"] = _nombre(res["total"])
    return res
