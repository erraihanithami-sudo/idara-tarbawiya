"""مؤشرات لوحة القيادة (اقتراح المدير 2026-11-03)، للمؤسسة كاملة أو لوحدة مدرسية واحدة.

- ما هو كائن: التلاميذ (حسب الجنس)، الأقسام، الموظفون، التوزيع حسب القسم.
- الهدر المدرسي: المنقطعون والمفصولون خلال السنة، نسبة إلى التلاميذ المعنيين (من يتابعون دراستهم + الوافدون +
  المنقطعون + المفصولون؛ المغادرون بشهادة مغادرة لا يُحسبون هدراً).
- المشاركون في الأنشطة الموازية: التلاميذ المنخرطون في نادٍ تربوي واحد على الأقل هذه السنة.
- المؤسسة الرائدة: نسبة المتحكمين في التعلمات الأساس (بلغوا المستوى المتوقع) لكل مادة، في آخر رائز مستورد.
- غير الرائدة: نسبة الحاصلين على المعدل (5/10) إلى مجموع التلاميذ الذين لهم نتائج مستوردة.
- الغياب: يُحسب عند برمجة تتبع الغياب (لا معطيات بعد).
"""

from __future__ import annotations

import sqlite3

from idara.services import annee as annee_srv
from idara.services import etablissement as etab_srv
from idara.services import tarl as tarl_srv

ACTIFS = ("inscrit", "arrive")


def _pct(n: int, d: int) -> float | None:
    return round(n * 100 / d, 2) if d else None


def _filtre_classe(conn, annee_id: int, unite: str | None) -> tuple[str, list]:
    """شرط SQL على القسم (c) حسب الوحدة المدرسية."""
    if not unite:
        return "", []
    return " AND c.unite_id=(SELECT id FROM unite_scolaire WHERE nom_ar=?)", [unite]


def indicateurs(conn: sqlite3.Connection, unite: str | None = None) -> dict:
    a = annee_srv.annee_courante(conn)
    aid = a["id"] if a else -1
    etab = etab_srv.lire_etablissement(conn)
    fc, args = _filtre_classe(conn, aid, unite)
    base = (f"FROM inscription i JOIN classe c ON c.id=i.classe_id JOIN eleve e ON e.id=i.eleve_id "
            f"WHERE i.annee_id=?{fc}")
    par_statut = {r[0]: r[1] for r in conn.execute(f"SELECT i.statut, COUNT(*) {base} GROUP BY i.statut",
                                                   [aid, *args])}
    actifs = sum(par_statut.get(s, 0) for s in ACTIFS)
    sexes = {r[0]: r[1] for r in conn.execute(
        f"SELECT e.sexe, COUNT(*) {base} AND i.statut IN ('inscrit','arrive') GROUP BY e.sexe", [aid, *args])}
    classes = conn.execute(
        f"SELECT c.code, (SELECT COUNT(*) FROM inscription i WHERE i.classe_id=c.id AND i.statut IN "
        f"('inscrit','arrive')) AS n FROM classe c WHERE c.annee_id=?{fc} ORDER BY c.code", [aid, *args]).fetchall()
    pers_sql = "SELECT COUNT(*) FROM personnel WHERE statut='actif' AND categorie<>'directeur'"
    pers_args: list = []
    if unite:
        pers_sql += " AND unite_id=(SELECT id FROM unite_scolaire WHERE nom_ar=?)"
        pers_args.append(unite)
    n_pers = conn.execute(pers_sql, pers_args).fetchone()[0]

    interrompus, exclus = par_statut.get("interrompu", 0), par_statut.get("exclu", 0)
    concernes = actifs + interrompus + exclus
    hadar = {"interrompus": interrompus, "exclus": exclus, "concernes": concernes,
             "taux_interruption": _pct(interrompus, concernes), "taux_exclusion": _pct(exclus, concernes),
             "taux": _pct(interrompus + exclus, concernes)}

    n_act = conn.execute(
        f"SELECT COUNT(DISTINCT m.eleve_id) FROM club_membre m JOIN club k ON k.id=m.club_id "
        f"JOIN inscription i ON i.eleve_id=m.eleve_id AND i.annee_id=k.annee_id JOIN classe c ON c.id=i.classe_id "
        f"WHERE k.annee_id=? AND i.statut IN ('inscrit','arrive'){fc}", [aid, *args]).fetchone()[0]
    activites = {"participants": n_act, "taux": _pct(n_act, actifs)}

    pionniere = bool(etab and etab.est_pionniere)
    res = {"annee": a["libelle"] if a else "", "unite": unite, "eleves": actifs, "garcons": sexes.get("M", 0),
           "filles": sexes.get("F", 0), "classes": classes, "personnel": n_pers, "hadar": hadar,
           "activites": activites, "pionniere": pionniere, "absences": None}
    codes = [r["code"] for r in classes]
    res["maitrise"] = _maitrise(conn, res["annee"], codes if unite else None) if pionniere else None
    res["reussite"] = None if pionniere else _reussite(conn, aid, codes if unite else None)
    return res


def _maitrise(conn, annee: str, classes: list[str] | None) -> dict:
    """لكل مادة: نسبة من بلغوا المستوى المتوقع في آخر رائز متوفر (البعدي ثم القبلي)."""
    res = {}
    for m, lib in tarl_srv.MATIERES.items():
        rows = conn.execute(
            "SELECT n.* FROM niveau_apprentissage n JOIN annee_scolaire a ON a.id=n.annee_id WHERE a.libelle=? "
            "AND n.matiere=?", (annee, m)).fetchall()
        if classes is not None:
            rows = [r for r in rows if r["classe"] in classes]
        epreuve = "post" if any(r["epreuve"] == "post" for r in rows) else "pre"
        ok = tot = 0
        for r in rows:
            if r["epreuve"] != epreuve or not r["niveau"]:
                continue
            att = tarl_srv.attendu(conn, annee, r["niveau"], m)
            if att:
                tot += 1
                ok += tarl_srv.rang(m, r["valeur"]) >= tarl_srv.rang(m, att)
        res[m] = {"matiere": lib, "maitrise": ok, "total": tot, "taux": _pct(ok, tot),
                  "epreuve": tarl_srv.EPREUVES[epreuve] if tot else ""}
    return res


def _reussite(conn, aid: int, classes: list[str] | None) -> dict:
    """الحاصلون على المعدل (5/10): المعدل السنوي إن وُجد، وإلا معدل آخر دورة مستوردة."""
    rows = conn.execute("SELECT classe, moyenne, moyenne_s1, moyenne_s2 FROM resultat WHERE annee_id=?",
                        (aid,)).fetchall()
    if classes is not None:
        rows = [r for r in rows if r["classe"] in classes]
    notes = []
    source = ""
    for r in rows:
        n = r["moyenne"] if r["moyenne"] is not None else r["moyenne_s2"] if r["moyenne_s2"] is not None \
            else r["moyenne_s1"]
        if n is not None:
            notes.append(n)
    if rows:
        source = ("المعدل السنوي" if any(r["moyenne"] is not None for r in rows) else
                  "الدورة الثانية" if any(r["moyenne_s2"] is not None for r in rows) else "الدورة الأولى")
    ok = sum(1 for n in notes if n >= 5)
    return {"admis": ok, "total": len(notes), "taux": _pct(ok, len(notes)), "source": source}
