"""تدبير تسجيلات التلاميذ (طلب المدير 2026-11-07): لائحة التلاميذ حسب المستوى، وأمام كل تلميذ خانات واجبات
التسجيل (التأمين المدرسي، الجمعية الرياضية، جمعية تنمية التعاون المدرسي)، مع عدّاد تراكمي لكل عنصر.

المبالغ (كما حددها المدير): التأمين 8 دراهم في الوسط القروي و12 درهماً في الوسط الحضري (وسط المؤسسة يُحدَّد في
الإعدادات)، الجمعية الرياضية 10 دراهم، جمعية تنمية التعاون المدرسي 10 دراهم.
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


def montants(conn: sqlite3.Connection) -> dict[str, int | None]:
    """مبلغ كل عنصر؛ التأمين None إن لم يُحدَّد وسط المؤسسة بعد."""
    e = etab_srv.lire_etablissement(conn)
    return {"assurance": ASSURANCE.get(e.milieu if e else ""), **MONTANTS_FIXES}


def _annee(conn) -> int:
    a = annee_srv.annee_courante(conn)
    if a is None:
        raise ErreurFrais("لا سنة دراسية جارية.")
    return a["id"]


def lister(conn: sqlite3.Connection, niveau: str | None = None, unite: str | None = None) -> list[dict]:
    """التلاميذ الذين يتابعون دراستهم، مرتبين حسب المستوى ثم القسم ثم الاسم، مع ما أدّوه."""
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
    sql += " ORDER BY n.ordre, c.code, e.nom_ar, e.prenom_ar"
    return [dict(r) for r in conn.execute(sql, args)]


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


def totaux(conn: sqlite3.Connection, niveau: str | None = None, unite: str | None = None) -> dict:
    """العدد والمبلغ لكل عنصر، والمجموع التراكمي."""
    liste = lister(conn, niveau, unite)
    m = montants(conn)
    res = {"eleves": len(liste), "elements": {}, "total": 0}
    for k, lib in ELEMENTS.items():
        n = sum(1 for x in liste if x[k])
        mt = n * m[k] if m[k] is not None else None
        res["elements"][k] = {"libelle": lib, "payes": n, "montant_unitaire": m[k], "montant": mt}
        res["total"] += mt or 0
    return res
