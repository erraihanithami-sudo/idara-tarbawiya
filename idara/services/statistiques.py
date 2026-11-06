"""إحصائيات المؤسسة (اقتراح المدير 2026-11-06): تحليل التلاميذ، البطاقة الإحصائية لكل مستوى، وتطور التحكم في
التعلمات الأساس بين الرائزين القبلي والبعدي.

- تحليل التلاميذ: كل من سُجّل هذه السنة (اللائحة الأولية + الوافدون)، ثم المغادرون والمنقطعون والمفصولون،
  والعدد بعد الحركية (من يتابعون دراستهم).
- البطاقة حسب المستوى: الأقسام والتلاميذ والجنس، وتوزيع التلاميذ حسب السن مقارنة بالسن النظامي للمستوى
  (السن في 31 دجنبر من بداية السنة الدراسية؛ السن النظامي للأولى ابتدائي 6 سنوات). مؤشر تقديري للتأخر
  الدراسي من تاريخ الازدياد، لا يعوّض معطى التكرار الذي لا تتضمنه لوائح مسار المستوردة.
- تطور التعلمات الأساس: نسبة من بلغوا المستوى المتوقع في كل رائز، حسب المستوى الدراسي.
"""

from __future__ import annotations

import sqlite3
from datetime import date

from idara.services import annee as annee_srv
from idara.services import tarl as tarl_srv
from idara.services import textes as tx

ACTIFS = ("inscrit", "arrive")
AGE_NORMAL = {"PS1": 4, "PS2": 5, "1AP": 6, "2AP": 7, "3AP": 8, "4AP": 9, "5AP": 10, "6AP": 11}


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


def _age(naissance: str | None, annee_debut: int) -> int | None:
    try:
        return annee_debut - int((naissance or "")[:4])
    except ValueError:
        return None


def par_niveau(conn: sqlite3.Connection, unite: str | None = None) -> list[dict]:
    aid, lib = _annee(conn)
    debut = int(lib[:4]) if lib[:4].isdigit() else date.today().year
    fc, args = _filtre(unite)
    rows = conn.execute(
        f"SELECT n.code AS niveau, i.classe_id, e.sexe, e.date_naissance FROM inscription i "
        f"JOIN classe c ON c.id=i.classe_id JOIN eleve e ON e.id=i.eleve_id LEFT JOIN niveau n ON n.id=i.niveau_id "
        f"WHERE i.annee_id=? AND i.statut IN ('inscrit','arrive'){fc}", [aid, *args]).fetchall()
    ordre = list(AGE_NORMAL)
    res = []
    for niv in sorted({r["niveau"] for r in rows if r["niveau"]}, key=lambda n: ordre.index(n) if n in ordre else 99):
        l = [r for r in rows if r["niveau"] == niv]
        normal = AGE_NORMAL.get(niv)
        a_l_heure = retard1 = retard2 = inconnu = 0
        for r in l:
            a = _age(r["date_naissance"], debut)
            if a is None or normal is None:
                inconnu += 1
            elif a <= normal:
                a_l_heure += 1
            elif a == normal + 1:
                retard1 += 1
            else:
                retard2 += 1
        connus = len(l) - inconnu
        res.append({"niveau": niv, "libelle": tx.niveau_ar(niv) if niv in tx.NIVEAUX else niv,
                    "classes": len({r["classe_id"] for r in l}), "eleves": len(l),
                    "garcons": sum(1 for r in l if r["sexe"] == "M"), "filles": sum(1 for r in l if r["sexe"] == "F"),
                    "age": [("في السن النظامي", a_l_heure, _pct(a_l_heure, connus)),
                            ("متأخر بسنة", retard1, _pct(retard1, connus)),
                            ("متأخر بسنتين فأكثر", retard2, _pct(retard2, connus))],
                    "taux_retard": _pct(retard1 + retard2, connus), "age_inconnu": inconnu})
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
    ordre = list(AGE_NORMAL)
    res = []
    for niv in sorted(cumul, key=lambda n: ordre.index(n) if n in ordre else 99):
        pre, post = _pct(*cumul[niv]["pre"]), _pct(*cumul[niv]["post"])
        res.append({"niveau": niv, "libelle": tx.niveau_ar(niv) if niv in tx.NIVEAUX else niv, "pre": pre, "post": post,
                    "evolution": round(post - pre, 1) if pre is not None and post is not None else None,
                    "effectif_pre": cumul[niv]["pre"][1], "effectif_post": cumul[niv]["post"][1]})
    return res
