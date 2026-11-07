"""إحصائيات المؤسسة (اقتراح المدير 2026-11-06): تحليل التلاميذ، البطاقة الإحصائية لكل مستوى، وتطور التحكم في
التعلمات الأساس بين الرائزين القبلي والبعدي.

- تحليل التلاميذ: كل من سُجّل هذه السنة (اللائحة الأولية + الوافدون)، ثم المغادرون والمنقطعون والمفصولون،
  والعدد بعد الحركية (من يتابعون دراستهم).
- البطاقة حسب المستوى: الأقسام والتلاميذ والجنس. التكرار لا يُقدَّر من السن (قرار المدير 2026-11-07)، ويُضاف
  لاحقاً بطريقة أخرى أو يدوياً.
- تطور التعلمات الأساس: نسبة من بلغوا المستوى المتوقع في كل رائز، حسب المستوى الدراسي.
"""

from __future__ import annotations

import sqlite3

from idara.services import annee as annee_srv
from idara.services import tarl as tarl_srv
from idara.services import textes as tx

ACTIFS = ("inscrit", "arrive")
ORDRE_NIVEAUX = ["PS1", "PS2", "1AP", "2AP", "3AP", "4AP", "5AP", "6AP"]


def _pct(n: int, d: int) -> float | None:
    return round(n * 100 / d, 1) if d else None


def _annee(conn) -> tuple[int, str]:
    a = annee_srv.annee_courante(conn)
    return (a["id"], a["libelle"]) if a else (-1, "")


def _filtre(unite: str | None) -> tuple[str, list]:
    if not unite:
        return "", []
    return " AND c.unite_id=(SELECT id FROM unite_scolaire WHERE nom_ar=?)", [unite]


def analyse_eleves(conn: sqlite3.Connection, unite: str | None = None) -> dict:
    aid, _ = _annee(conn)
    fc, args = _filtre(unite)
    rows = conn.execute(
        f"SELECT i.statut, e.sexe FROM inscription i JOIN classe c ON c.id=i.classe_id JOIN eleve e ON e.id=i.eleve_id "
        f"WHERE i.annee_id=?{fc}", [aid, *args]).fetchall()
    total = len(rows)
    par = {s: sum(1 for r in rows if r["statut"] == s) for s in ("inscrit", "arrive", "parti", "interrompu", "exclu")}
    g = sum(1 for r in rows if r["sexe"] == "M")
    f = sum(1 for r in rows if r["sexe"] == "F")
    apres = par["inscrit"] + par["arrive"]
    lignes = [("ذكور", g), ("إناث", f), ("الوافدون", par["arrive"]), ("المغادرون", par["parti"]),
              ("المنقطعون", par["interrompu"]), ("المفصولون", par["exclu"])]
    return {"total": total, "apres_mouvement": apres, "garcons": g, "filles": f,
            "details": [(lib, n, _pct(n, total)) for lib, n in lignes]}


def par_niveau(conn: sqlite3.Connection, unite: str | None = None) -> list[dict]:
    aid, _ = _annee(conn)
    fc, args = _filtre(unite)
    rows = conn.execute(
        f"SELECT n.code AS niveau, i.classe_id, e.sexe FROM inscription i "
        f"JOIN classe c ON c.id=i.classe_id JOIN eleve e ON e.id=i.eleve_id LEFT JOIN niveau n ON n.id=i.niveau_id "
        f"WHERE i.annee_id=? AND i.statut IN ('inscrit','arrive'){fc}", [aid, *args]).fetchall()
    ordre = ORDRE_NIVEAUX
    res = []
    for niv in sorted({r["niveau"] for r in rows if r["niveau"]}, key=lambda n: ordre.index(n) if n in ordre else 99):
        l = [r for r in rows if r["niveau"] == niv]
        g = sum(1 for r in l if r["sexe"] == "M")
        f = sum(1 for r in l if r["sexe"] == "F")
        res.append({"niveau": niv, "libelle": tx.niveau_ar(niv) if niv in tx.NIVEAUX else niv,
                    "classes": len({r["classe_id"] for r in l}), "eleves": len(l), "garcons": g, "filles": f,
                    "pct_garcons": _pct(g, len(l)), "pct_filles": _pct(f, len(l))})
    return res


def evolution_tarl(conn: sqlite3.Connection, matiere: str | None = None, unite: str | None = None) -> list[dict]:
    """لكل مستوى: نسبة من بلغوا المستوى المتوقع في الرائز القبلي ثم البعدي (مادة واحدة أو كل المواد)."""
    aid, lib = _annee(conn)
    classes = None
    if unite:
        fc, args = _filtre(unite)
        classes = {r[0] for r in conn.execute(f"SELECT c.code FROM classe c WHERE c.annee_id=?{fc}", [aid, *args])}
    mats = [matiere] if matiere else list(tarl_srv.MATIERES)
    cumul: dict[str, dict[str, list[int]]] = {}
    attendus: dict[tuple[str, str], str | None] = {}
    for m in mats:
        for r in conn.execute("SELECT classe, niveau, epreuve, valeur FROM niveau_apprentissage WHERE annee_id=? AND "
                              "matiere=?", (aid, m)):
            if not r["niveau"] or (classes is not None and r["classe"] not in classes):
                continue
            k = (r["niveau"], m)
            if k not in attendus:
                attendus[k] = tarl_srv.attendu(conn, lib, r["niveau"], m)
            att = attendus[k]
            if not att:
                continue
            try:
                ok = tarl_srv.rang(m, r["valeur"]) >= tarl_srv.rang(m, att)
            except ValueError:
                continue
            c = cumul.setdefault(r["niveau"], {"pre": [0, 0], "post": [0, 0]}).setdefault(r["epreuve"], [0, 0])
            c[0] += ok
            c[1] += 1
    ordre = ORDRE_NIVEAUX
    res = []
    for niv in sorted(cumul, key=lambda n: ordre.index(n) if n in ordre else 99):
        pre, post = _pct(*cumul[niv]["pre"]), _pct(*cumul[niv]["post"])
        res.append({"niveau": niv, "libelle": tx.niveau_ar(niv) if niv in tx.NIVEAUX else niv, "pre": pre, "post": post,
                    "evolution": round(post - pre, 1) if pre is not None and post is not None else None,
                    "effectif_pre": cumul[niv]["pre"][1], "effectif_post": cumul[niv]["post"][1]})
    return res
