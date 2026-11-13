"""تتبع الحضور الشهري (طلب المدير 2026-11-07، ثم 2026-11-13).

قرار 2026-11-13: تُدخل نسبة الحضور الشهرية لكل قسم يدوياً (كما تُحسب في القسم)، ويحسب البرنامج نسبة الوحدة
المدرسية والمؤسسة كاملة. المحسوب هو نسبة الحضور لا نسبة الغياب.
نسبة الوحدة أو المؤسسة = مجموع (نسبة القسم × عدد تلاميذه) ÷ مجموع التلاميذ (متوسط مرجح بعدد التلاميذ).
تقرير شهري (Word): جدول الأقسام والوحدات ونسبة المؤسسة، ومبيان المؤسسة كاملة عبر الأشهر المُدرجة.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from idara.data.dossier import DossierDonnees
from idara.services import annee as annee_srv
from idara.services import etablissement as etab_srv
from idara.services import textes as tx

MOIS_SCOLAIRES = (9, 10, 11, 12, 1, 2, 3, 4, 5, 6)


class ErreurAbsence(ValueError):
    """رسالة موجهة للمدير بالعربية."""


def _annee(conn) -> tuple[int, str]:
    a = annee_srv.annee_courante(conn)
    if a is None:
        raise ErreurAbsence("لا سنة دراسية جارية.")
    return a["id"], a["libelle"]


def mois_de_l_annee(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    """(YYYY-MM، «شتنبر 2026») من شتنبر إلى يونيو."""
    _, lib = _annee(conn)
    debut = int(lib[:4])
    res = []
    for m in MOIS_SCOLAIRES:
        y = debut if m >= 9 else debut + 1
        res.append((f"{y:04d}-{m:02d}", f"{tx.MOIS_AR[m - 1]} {y}"))
    return res


def libelle_mois(mois: str) -> str:
    y, m = mois.split("-")
    return f"{tx.MOIS_AR[int(m) - 1]} {y}"


def jours_etude(conn: sqlite3.Connection, mois: str) -> float | None:
    """أيام الدراسة الفعلية (اختيارية، للإخبار فقط)."""
    aid, _ = _annee(conn)
    r = conn.execute("SELECT jours_etude FROM absence_mois WHERE annee_id=? AND mois=?", (aid, mois)).fetchone()
    return r[0] if r else None


def lignes(conn: sqlite3.Connection, mois: str) -> list[dict]:
    """كل أقسام السنة (مع وحدتها)، بالنسبة المسجلة لهذا الشهر، وبعدد التلاميذ الحالي إن لم يُسجَّل شيء."""
    aid, _ = _annee(conn)
    res = []
    for r in conn.execute(
            "SELECT c.id, c.code, u.nom_ar AS unite, (SELECT COUNT(*) FROM inscription i WHERE i.classe_id=c.id AND "
            "i.statut IN ('inscrit','arrive')) AS n, a.effectif, a.taux_presence FROM classe c "
            "LEFT JOIN unite_scolaire u ON u.id=c.unite_id LEFT JOIN absence_classe a ON a.classe_id=c.id AND "
            "a.annee_id=c.annee_id AND a.mois=? WHERE c.annee_id=? ORDER BY u.id IS NULL, u.id, c.code", (mois, aid)):
        saisi = r["taux_presence"] is not None
        res.append({"classe_id": r["id"], "classe": r["code"], "unite": r["unite"] or "",
                    "effectif": r["effectif"] if r["effectif"] is not None else r["n"], "saisi": saisi,
                    "taux": r["taux_presence"] if saisi else None})
    return res


def _taux(v) -> float | None:
    if v is None or str(v).strip() == "":
        return None
    try:
        t = float(str(v).replace(",", ".").replace("%", "").strip())
    except ValueError:
        raise ErreurAbsence("نسبة الحضور: رقم بين 0 و100.") from None
    if not 0 <= t <= 100:
        raise ErreurAbsence("نسبة الحضور: رقم بين 0 و100.")
    return round(t, 2)


def enregistrer(conn: sqlite3.Connection, mois: str, valeurs: list[tuple[int, int, object]],
                jours: float | None = None) -> None:
    """valeurs: (القسم، عدد التلاميذ، نسبة الحضور %). القسم دون نسبة لا يُحتسب (ويُحذف ما سُجل له)."""
    aid, _ = _annee(conn)
    if mois not in dict(mois_de_l_annee(conn)):
        raise ErreurAbsence("الشهر خارج السنة الدراسية.")
    if jours is not None and jours != "" and float(jours) != 0:
        jours = float(jours)
        if not 0 < jours <= 31:
            raise ErreurAbsence("أيام الدراسة الفعلية في الشهر: بين 1 و31.")
    else:
        jours = None
    codes = {r[0]: r[1] for r in conn.execute("SELECT id, code FROM classe WHERE annee_id=?", (aid,))}
    propres, vides = [], []
    for cid, eff, taux in valeurs:
        if cid not in codes:
            raise ErreurAbsence("قسم غير معروف.")
        c = codes[cid]
        try:
            t = _taux(taux)
        except ErreurAbsence as e:
            raise ErreurAbsence(f"{c}: {e}") from None
        if t is None:
            vides.append(cid)
            continue
        if eff is None or int(eff) <= 0:
            raise ErreurAbsence(f"{c}: عدد التلاميذ غير صحيح.")
        propres.append((aid, mois, cid, int(eff), t))
    if not propres:
        raise ErreurAbsence("أدخل نسبة الحضور لقسم واحد على الأقل.")
    with conn:
        conn.execute("INSERT INTO absence_mois(annee_id, mois, jours_etude) VALUES (?,?,?) ON CONFLICT(annee_id, mois) "
                     "DO UPDATE SET jours_etude=excluded.jours_etude", (aid, mois, jours))
        conn.executemany("INSERT INTO absence_classe(annee_id, mois, classe_id, effectif, taux_presence) "
                         "VALUES (?,?,?,?,?) ON CONFLICT(annee_id, mois, classe_id) DO UPDATE SET "
                         "effectif=excluded.effectif, taux_presence=excluded.taux_presence", propres)
        conn.executemany("DELETE FROM absence_classe WHERE annee_id=? AND mois=? AND classe_id=?",
                         [(aid, mois, c) for c in vides])


def _agreger(ls: list[dict]) -> dict:
    eff = sum(x["effectif"] for x in ls)
    t = round(sum(x["taux"] * x["effectif"] for x in ls) / eff, 2) if eff else None
    return {"effectif": eff, "classes": len(ls), "taux": t}


def synthese_mois(conn: sqlite3.Connection, mois: str) -> dict | None:
    """نسب حضور الشهر: كل قسم، كل وحدة، والمؤسسة كاملة (None إن لم يُدرج الشهر)."""
    ls = [x for x in lignes(conn, mois) if x["saisi"]]
    if not ls:
        return None
    unites = []
    if etab_srv.est_groupe(conn):
        for u in dict.fromkeys(x["unite"] for x in ls):
            unites.append({"unite": u or "دون وحدة", **_agreger([x for x in ls if x["unite"] == u])})
    return {"mois": mois, "libelle": libelle_mois(mois), "jours_etude": jours_etude(conn, mois), "classes": ls,
            "unites": unites, "etablissement": _agreger(ls)}


def evolution(conn: sqlite3.Connection) -> list[dict]:
    """الأشهر المُدرجة بالترتيب، مع نسبة المؤسسة ونسبة كل وحدة."""
    res = []
    for m, _ in mois_de_l_annee(conn):
        s = synthese_mois(conn, m)
        if s:
            res.append(s)
    return res


def dernier_taux(conn: sqlite3.Connection) -> tuple[str, float] | None:
    """لوحة القيادة: نسبة حضور آخر شهر مُدرج."""
    try:
        ev = evolution(conn)
    except ErreurAbsence:
        return None
    return (ev[-1]["libelle"], ev[-1]["etablissement"]["taux"]) if ev else None


def generer_rapport(conn: sqlite3.Connection, dossier: DossierDonnees, mois: str,
                    graphique_png: bytes | None = None) -> Path:
    """التقرير الشهري للحضور (Word). graphique_png: مبيان المؤسسة عبر الأشهر، ترسمه الواجهة."""
    import io

    from docx.shared import Cm

    from idara.services.docs_association import _cellule, _nouveau, _ombre, para, tableau
    s = synthese_mois(conn, mois)
    if s is None:
        raise ErreurAbsence("لم تُدرج إحصاءات هذا الشهر بعد.")
    etab = etab_srv.lire_etablissement(conn)
    _, annee = _annee(conn)
    d = _nouveau()
    if etab and etab.logo_path and (dossier.racine / etab.logo_path).exists():
        d.add_picture(str(dossier.racine / etab.logo_path), width=Cm(17))
    elif etab:
        for l in ("المملكة المغربية", f"المديرية الإقليمية: {etab.direction_ar}", f"المؤسسة: {etab.nom_ar}"):
            para(d, l, gras=True, taille=10, apres=0)
    para(d, f"تقرير الحضور الشهري: {s['libelle']}", gras=True, taille=16, centre=True, souligne=True, apres=2)
    para(d, f"السنة الدراسية {annee}" + (f" · أيام الدراسة الفعلية: {s['jours_etude']:g}" if s["jours_etude"] else ""),
         taille=10, centre=True, apres=6)
    groupe = bool(s["unites"])
    entetes = (["الوحدة"] if groupe else []) + ["القسم", "عدد التلاميذ", "نسبة الحضور"]
    largeurs = ([4.2] if groupe else []) + [5, 3.4, 3.6]
    t = tableau(d, 1 + len(s["classes"]), len(entetes), largeurs=largeurs)
    for j, h in enumerate(entetes):
        _cellule(t.cell(0, j), h, gras=True, taille=10)
        _ombre(t.cell(0, j))
    for i, x in enumerate(s["classes"], start=1):
        vals = ([x["unite"] or "—"] if groupe else []) + [x["classe"], str(x["effectif"]), _fmt(x["taux"])]
        for j, v in enumerate(vals):
            _cellule(t.cell(i, j), v, taille=10)
    para(d, "", apres=4)
    lignes_synth = [(u["unite"], u) for u in s["unites"]] + [("المؤسسة كاملة", s["etablissement"])]
    t2 = tableau(d, 1 + len(lignes_synth), 4, largeurs=[6, 3.2, 3.2, 3.6])
    for j, h in enumerate(("", "الأقسام", "عدد التلاميذ", "نسبة الحضور")):
        _cellule(t2.cell(0, j), h, gras=True, taille=10)
        _ombre(t2.cell(0, j))
    for i, (lib, a) in enumerate(lignes_synth, start=1):
        for j, v in enumerate((lib, str(a["classes"]), str(a["effectif"]), _fmt(a["taux"]))):
            _cellule(t2.cell(i, j), v, gras=(lib == "المؤسسة كاملة"), taille=10)
    if graphique_png:
        para(d, "", apres=4)
        para(d, "تطور نسبة الحضور بالمؤسسة كاملة حسب الأشهر المُدرجة", gras=True, taille=12, centre=True, apres=2)
        d.add_picture(io.BytesIO(graphique_png), width=Cm(16))
        d.paragraphs[-1].alignment = 1
    para(d, "", apres=6)
    para(d, f"حرر في: {etab.ville_redaction_ar if etab and etab.ville_redaction_ar else ''} بتاريخ "
            f"{tx.date_ar(datetime.now().date())}", taille=11, apres=2)
    para(d, "توقيع المدير(ة):", gras=True, taille=11)
    rep = dossier.archives / annee.replace("/", "-") / "الغياب"
    rep.mkdir(parents=True, exist_ok=True)
    chemin = rep / f"{datetime.now():%Y%m%d_%H%M%S}_تقرير_الحضور_{mois}.docx"
    d.save(chemin)
    return chemin


def _fmt(v: float | None) -> str:
    return "—" if v is None else f"{v:g}%"
