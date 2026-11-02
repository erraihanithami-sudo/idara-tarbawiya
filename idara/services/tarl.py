"""تتبع التعلمات الأساس بمؤسسات الريادة (TaRL: التدريس وفق المستوى المناسب).

المصدر: تصدير مسار «مستويات التعلم» (ExportNiveauxApprentissage): ورقة لكل قسم (TARL-2APG-1...)، وفيها لكل
تلميذ مستواه في رائز الموضعة القبلي والبعدي في اللغة العربية واللغة الفرنسية والرياضيات، مع المستوى المتوقع
لكل مادة في رأس الورقة. سلالم المستويات كما يكتبها مسار (رأس تصدير «نتائج الاختبار الخاص بتلاميذ المؤسسة»).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from idara.services import annee as annee_srv
from idara.services.evaluation import ORDINAUX, _annee_id, _niveau_libelle
from idara.services.massar import MOTIF_CODE, normaliser

MATIERES = {"ar": "اللغة العربية", "fr": "اللغة الفرنسية", "ma": "الرياضيات"}
ECHELLES = {
    "ar": ("مبتدئ", "حرف", "كلمة", "فقرة", "أقصوصة"),
    "fr": ("débutant", "lettre", "Mot simple", "Mot avancé", "Graphème complexe", "Phrase (D.P)", "Texte"),
    "ma": ("مبتدئ", "رقم واحد", "رقمان", "جمع", "طرح", "ضرب", "قسمة"),
}
EPREUVES = {"pre": "رائز الموضعة القبلي", "post": "رائز الموضعة البعدي"}


class ErreurTarl(ValueError):
    """رسالة موجهة للمدير بالعربية."""


def _cle(v) -> str:
    return "".join(str(v or "").lower().split()).replace("é", "e").replace("è", "e")


_INDEX = {m: {_cle(n): n for n in e} for m, e in ECHELLES.items()}


def niveau_canonique(matiere: str, valeur) -> str | None:
    """«Mot  simple»، «مبتدئ » ... ← التسمية الموحدة؛ None إن لم تكن من السلم."""
    return _INDEX[matiere].get(_cle(valeur))


def rang(matiere: str, valeur: str) -> int:
    return ECHELLES[matiere].index(valeur)


def _matiere(texte) -> str | None:
    t = normaliser(texte)
    for k, lib in MATIERES.items():
        if normaliser(lib) in t:
            return k
    return None


def _epreuve(texte) -> str | None:
    t = normaliser(texte)
    if "البعدي" in t:
        return "post"
    if "القبلي" in t:
        return "pre"
    return None


@dataclass
class FichierNiveaux:
    annee: str = ""
    lignes: list[tuple] = field(default_factory=list)       # (code, nom, classe, niveau, matiere, epreuve, valeur)
    attendus: dict[tuple[str, str], str] = field(default_factory=dict)   # (niveau, matiere) ← المستوى المتوقع
    classes: list[str] = field(default_factory=list)
    alertes: list[str] = field(default_factory=list)
    parcours: list[tuple[str, str, str]] = field(default_factory=list)   # (القسم، المادة، المسار)


def lire_fichier(chemin: Path) -> FichierNiveaux:
    import openpyxl
    try:
        wb = openpyxl.load_workbook(chemin, read_only=True, data_only=True)
    except Exception as e:  # noqa: BLE001
        raise ErreurTarl(f"تعذرت قراءة الملف {Path(chemin).name}: ليس ملف Excel صالحاً.") from e
    res = FichierNiveaux()
    for ws in wb.worksheets:
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
        entete = next((i for i, r in enumerate(rows) if any(normaliser(c) == "رقمالتلميذ" for c in r)), None)
        if entete is None:
            continue
        niveau, i_attendu = None, None
        for i, r in enumerate(rows[:entete]):
            for j, c in enumerate(r):
                n = normaliser(c)
                suivant = next((x for x in r[j + 1:] if x not in (None, "")), None)
                if "السنةالدراسية" in n and suivant:
                    res.annee = res.annee or str(suivant).strip()
                elif n == "المستوى" and suivant:
                    niveau = _niveau_libelle(str(suivant))
                elif "المستوىالمتوقع" in n:
                    i_attendu = i
        if i_attendu is not None and niveau:
            mats = rows[i_attendu]
            vals = rows[i_attendu + 1] if i_attendu + 1 < len(rows) else []
            for j, c in enumerate(mats):
                m = _matiere(c)
                if m and j < len(vals) and niveau_canonique(m, vals[j]):
                    res.attendus[(niveau, m)] = niveau_canonique(m, vals[j])
        classe = ws.title.strip()
        classe = classe[5:] if classe.upper().startswith("TARL-") else classe
        # تصدير «مجموعات الدعم»: سطر المواد ثم سطر المسارات (المسار 2، parcours 2) فوق رأس الجدول
        for i in range(max(0, entete - 6), entete - 1):
            mats = rows[i]
            for j, c in enumerate(mats):
                m = _matiere(c)
                v = rows[i + 1][j] if j < len(rows[i + 1]) else None
                if m and v and any(k in normaliser(v) for k in ("المسار", "parcours")):
                    res.parcours.append((classe, m, " ".join(str(v).split())))
        tete, dessus = rows[entete], rows[entete - 1] if entete else []
        i_code = next(j for j, c in enumerate(tete) if normaliser(c) == "رقمالتلميذ")
        i_nom = next((j for j, c in enumerate(tete) if "الإسم" in normaliser(c) or "الاسم" in normaliser(c)), i_code + 1)
        colonnes = []
        for j, c in enumerate(tete):
            ep, m = _epreuve(c), _matiere(dessus[j] if j < len(dessus) else None)
            if ep and m:
                colonnes.append((j, m, ep))
        if not colonnes:
            if any(x[0] == classe for x in res.parcours):
                res.classes.append(classe)
            continue
        n_avant = len(res.lignes)
        for r in rows[entete + 1:]:
            code = str(r[i_code] or "").strip().upper() if i_code < len(r) else ""
            if not code:
                continue
            if not MOTIF_CODE.match(code):
                res.alertes.append(f"{classe}: رمز غير صالح «{code}».")
                continue
            nom = " ".join(str(r[i_nom] or "").split()) if i_nom < len(r) else ""
            for j, m, ep in colonnes:
                v = r[j] if j < len(r) else None
                if v in (None, ""):
                    continue
                can = niveau_canonique(m, v)
                if can is None:
                    res.alertes.append(f"{classe}: مستوى غير معروف «{v}» ({MATIERES[m]}) لـ {code}.")
                    continue
                res.lignes.append((code, nom, classe, niveau, m, ep, can))
        if len(res.lignes) > n_avant:
            res.classes.append(classe)
    if not res.lignes and not res.parcours:
        raise ErreurTarl("لم يُعثر على مستويات تعلم في الملف. صدِّر «مستويات التعلم» من مسار (فضاء مؤسسات الريادة).")
    try:
        annee_srv.code_court(res.annee)
    except Exception:  # noqa: BLE001
        raise ErreurTarl(f"السنة الدراسية غير مقروءة في الملف («{res.annee}»).") from None
    return res


@dataclass
class RapportTarl:
    annee: str
    eleves: int
    classes: list[str]
    alertes: list[str]
    parcours: int = 0


def importer(conn: sqlite3.Connection, chemins: list[Path]) -> RapportTarl:
    fichiers = [lire_fichier(c) for c in chemins]
    annees = {f.annee for f in fichiers}
    if len(annees) > 1:
        raise ErreurTarl("الملفات المختارة من سنوات دراسية مختلفة: " + "، ".join(sorted(annees)))
    annee = annees.pop()
    aid = _annee_id(conn, annee)
    codes = set()
    with conn:
        for f in fichiers:
            for (niv, m), v in f.attendus.items():
                conn.execute("INSERT INTO niveau_attendu(annee_id, niveau, matiere, valeur) VALUES (?,?,?,?) "
                             "ON CONFLICT(annee_id, niveau, matiere) DO UPDATE SET valeur=excluded.valeur", (aid, niv, m, v))
            for classe, m, parc in f.parcours:
                conn.execute("INSERT INTO tarl_parcours(annee_id, classe, matiere, parcours) VALUES (?,?,?,?) "
                             "ON CONFLICT(annee_id, classe, matiere) DO UPDATE SET parcours=excluded.parcours",
                             (aid, classe, m, parc))
            for code, nom, classe, niv, m, ep, v in f.lignes:
                codes.add(code)
                e = conn.execute("SELECT id FROM eleve WHERE code_massar=?", (code,)).fetchone()
                conn.execute(
                    "INSERT INTO niveau_apprentissage(annee_id, code_massar, eleve_id, nom, classe, niveau, matiere, "
                    "epreuve, valeur) VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(annee_id, code_massar, matiere, epreuve) "
                    "DO UPDATE SET eleve_id=excluded.eleve_id, nom=excluded.nom, classe=excluded.classe, "
                    "niveau=excluded.niveau, valeur=excluded.valeur, importe_le=datetime('now','localtime')",
                    (aid, code, e[0] if e else None, nom, classe, niv, m, ep, v))
        conn.execute("INSERT INTO journal(action, cible, details) VALUES ('import','niveaux_apprentissage',?)",
                     (f"{annee}: {len(codes)} تلميذاً",))
    return RapportTarl(annee, len(codes), [c for f in fichiers for c in f.classes],
                       [a for f in fichiers for a in f.alertes], sum(len(f.parcours) for f in fichiers))


# ---------- الإحصاء ----------

def annees(conn) -> list[str]:
    return [r[0] for r in conn.execute(
        "SELECT a.libelle FROM annee_scolaire a WHERE a.id IN (SELECT annee_id FROM niveau_apprentissage UNION "
        "SELECT annee_id FROM tarl_parcours) ORDER BY a.libelle DESC")]


def groupes(conn, annee: str) -> list[tuple[str, str]]:
    """(المفتاح، التسمية): المستويات ثم الأقسام."""
    rows = conn.execute("SELECT DISTINCT n.niveau, n.classe FROM niveau_apprentissage n JOIN annee_scolaire a "
                        "ON a.id=n.annee_id WHERE a.libelle=?", (annee,)).fetchall()
    niv = sorted({r[0] for r in rows if r[0]}, key=lambda x: list(ORDINAUX).index(x))
    return ([("*", "المؤسسة")] + [(f"n:{n}", f"المستوى {ORDINAUX[n]}") for n in niv]
            + [(f"c:{c}", f"القسم {c.replace('-', '')}") for c in sorted({r[1] for r in rows})])


def attendu(conn, annee: str, niveau: str, matiere: str) -> str | None:
    r = conn.execute("SELECT valeur FROM niveau_attendu t JOIN annee_scolaire a ON a.id=t.annee_id WHERE a.libelle=? "
                     "AND t.niveau=? AND t.matiere=?", (annee, niveau, matiere)).fetchone()
    return r[0] if r else None


def _donnees(conn, annee: str, groupe: str, matiere: str) -> dict[str, dict[str, sqlite3.Row]]:
    sql = ("SELECT n.* FROM niveau_apprentissage n JOIN annee_scolaire a ON a.id=n.annee_id "
           "WHERE a.libelle=? AND n.matiere=?")
    args: list = [annee, matiere]
    if groupe.startswith("n:"):
        sql += " AND n.niveau=?"
        args.append(groupe[2:])
    elif groupe.startswith("c:"):
        sql += " AND n.classe=?"
        args.append(groupe[2:])
    par: dict[str, dict[str, sqlite3.Row]] = {}
    for r in conn.execute(sql, args):
        par.setdefault(r["code_massar"], {})[r["epreuve"]] = r
    return par


def tableau_bord(conn, annee: str, groupe: str, matiere: str) -> dict:
    """توزيع التلاميذ على مستويات السلم في الرائزين، ونسبة بلوغ المستوى المتوقع، والتطور بين الرائزين."""
    par = _donnees(conn, annee, groupe, matiere)
    echelle = ECHELLES[matiere]
    dist = {ep: {v: 0 for v in echelle} for ep in EPREUVES}
    atteint = {ep: [0, 0] for ep in EPREUVES}   # [بلغ المتوقع، من له مستوى متوقع]
    evol = {"progres": 0, "stable": 0, "recul": 0}
    for code, eps in par.items():
        for ep, r in eps.items():
            dist[ep][r["valeur"]] += 1
            att = attendu(conn, annee, r["niveau"], matiere) if r["niveau"] else None
            if att:
                atteint[ep][1] += 1
                atteint[ep][0] += rang(matiere, r["valeur"]) >= rang(matiere, att)
        if "pre" in eps and "post" in eps:
            d = rang(matiere, eps["post"]["valeur"]) - rang(matiere, eps["pre"]["valeur"])
            evol["progres" if d > 0 else "stable" if d == 0 else "recul"] += 1
    effectifs = {ep: sum(dist[ep].values()) for ep in EPREUVES}
    pct = lambda a, b: round(a / b * 100, 2) if b else None  # noqa: E731
    return {"echelle": echelle, "distribution": dist, "effectifs": effectifs,
            "taux_attendu": {ep: pct(*atteint[ep]) for ep in EPREUVES},
            "evolution": evol, "compares": sum(evol.values())}


def eleves_en_difficulte(conn, annee: str, groupe: str, matiere: str, epreuve: str = "post") -> list[sqlite3.Row]:
    """التلاميذ دون المستوى المتوقع في الرائز (للدعم)."""
    res = []
    for code, eps in _donnees(conn, annee, groupe, matiere).items():
        r = eps.get(epreuve)
        if r is None or not r["niveau"]:
            continue
        att = attendu(conn, annee, r["niveau"], matiere)
        if att and rang(matiere, r["valeur"]) < rang(matiere, att):
            res.append(r)
    return sorted(res, key=lambda r: (r["classe"], rang(matiere, r["valeur"]), r["nom"]))


def parcours(conn, annee: str) -> dict[str, dict[str, str]]:
    """القسم ← المادة ← مسار الدعم (من تصدير «مجموعات الدعم»)."""
    res: dict = {}
    for r in conn.execute("SELECT p.* FROM tarl_parcours p JOIN annee_scolaire a ON a.id=p.annee_id WHERE a.libelle=? "
                          "ORDER BY p.classe", (annee,)):
        res.setdefault(r["classe"], {})[r["matiere"]] = r["parcours"]
    return res
