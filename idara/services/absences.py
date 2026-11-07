"""تتبع الغياب الشهري (طلب المدير 2026-11-07).

لكل شهر: أيام الدراسة الفعلية؛ ولكل قسم: عدد التلاميذ، مجموع أيام الغياب (أنصاف الأيام مقبولة)، عدد المتغيبين.
نسبة الغياب = مجموع أيام الغياب ÷ (عدد التلاميذ × أيام الدراسة الفعلية) × 100، للقسم وللوحدة المدرسية
وللمؤسسة كاملة (الوحدة والمؤسسة: مجموع أيام الغياب ÷ مجموع أيام الحضور الممكنة).
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


def _pct(n: float, d: float) -> float | None:
    return round(n * 100 / d, 2) if d else None


def jours_etude(conn: sqlite3.Connection, mois: str) -> float | None:
    aid, _ = _annee(conn)
    r = conn.execute("SELECT jours_etude FROM absence_mois WHERE annee_id=? AND mois=?", (aid, mois)).fetchone()
    return r[0] if r else None


def lignes(conn: sqlite3.Connection, mois: str) -> list[dict]:
    """كل أقسام السنة (مع وحدتها)، بالقيم المسجلة لهذا الشهر أو بعدد التلاميذ الحالي إن لم يُسجَّل شيء."""
    aid, _ = _annee(conn)
    j = jours_etude(conn, mois)
    res = []
    for r in conn.execute(
            "SELECT c.id, c.code, u.nom_ar AS unite, (SELECT COUNT(*) FROM inscription i WHERE i.classe_id=c.id AND "
            "i.statut IN ('inscrit','arrive')) AS n, a.effectif, a.jours_absence, a.absents FROM classe c "
            "LEFT JOIN unite_scolaire u ON u.id=c.unite_id LEFT JOIN absence_classe a ON a.classe_id=c.id AND "
            "a.annee_id=c.annee_id AND a.mois=? WHERE c.annee_id=? ORDER BY u.id IS NULL, u.id, c.code", (mois, aid)):
        saisi = r["effectif"] is not None
        eff = r["effectif"] if saisi else r["n"]
        ja = r["jours_absence"] if saisi else 0
        res.append({"classe_id": r["id"], "classe": r["code"], "unite": r["unite"] or "", "effectif": eff,
                    "jours_absence": ja, "absents": r["absents"] if saisi else 0, "saisi": saisi,
                    "taux": _pct(ja, eff * j) if saisi and j else None})
    return res


def enregistrer(conn: sqlite3.Connection, mois: str, jours: float, valeurs: list[tuple[int, int, float, int]]) -> None:
    """valeurs: (القسم، عدد التلاميذ، مجموع أيام الغياب، عدد المتغيبين)."""
    aid, _ = _annee(conn)
    if mois not in dict(mois_de_l_annee(conn)):
        raise ErreurAbsence("الشهر خارج السنة الدراسية.")
    try:
        jours = float(jours)
    except (TypeError, ValueError):
        raise ErreurAbsence("أيام الدراسة الفعلية: رقم.") from None
    if not 0 < jours <= 31:
        raise ErreurAbsence("أيام الدراسة الفعلية في الشهر: بين 1 و31.")
    codes = {r[0]: r[1] for r in conn.execute("SELECT id, code FROM classe WHERE annee_id=?", (aid,))}
    propres = []
    for cid, eff, ja, ab in valeurs:
        if cid not in codes:
            raise ErreurAbsence("قسم غير معروف.")
        c = codes[cid]
        if eff is None or int(eff) < 0:
            raise ErreurAbsence(f"{c}: عدد التلاميذ غير صحيح.")
        eff, ja, ab = int(eff), float(ja or 0), int(ab or 0)
        if ja < 0 or ja * 2 != int(ja * 2):
            raise ErreurAbsence(f"{c}: أيام الغياب عدد صحيح أو بنصف يوم (مثلاً 12.5).")
        if ja > eff * jours:
            raise ErreurAbsence(f"{c}: أيام الغياب ({ja:g}) تتجاوز عدد التلاميذ × أيام الدراسة ({eff * jours:g}).")
        if ab > eff:
            raise ErreurAbsence(f"{c}: عدد المتغيبين ({ab}) يتجاوز عدد التلاميذ ({eff}).")
        if ja and not ab:
            raise ErreurAbsence(f"{c}: سُجلت أيام غياب دون عدد المتغيبين.")
        propres.append((aid, mois, cid, eff, ja, ab))
    with conn:
        conn.execute("INSERT INTO absence_mois(annee_id, mois, jours_etude) VALUES (?,?,?) ON CONFLICT(annee_id, mois) "
                     "DO UPDATE SET jours_etude=excluded.jours_etude", (aid, mois, jours))
        conn.executemany("INSERT INTO absence_classe(annee_id, mois, classe_id, effectif, jours_absence, absents) "
                         "VALUES (?,?,?,?,?,?) ON CONFLICT(annee_id, mois, classe_id) DO UPDATE SET "
                         "effectif=excluded.effectif, jours_absence=excluded.jours_absence, absents=excluded.absents",
                         propres)


def _agreger(ls: list[dict], j: float) -> dict:
    eff = sum(x["effectif"] for x in ls)
    ja = sum(x["jours_absence"] for x in ls)
    ab = sum(x["absents"] for x in ls)
    return {"effectif": eff, "jours_absence": ja, "absents": ab, "taux": _pct(ja, eff * j),
            "taux_absents": _pct(ab, eff)}


def synthese_mois(conn: sqlite3.Connection, mois: str) -> dict | None:
    """نسب الشهر: كل قسم، كل وحدة، والمؤسسة كاملة (None إن لم يُدرج الشهر)."""
    j = jours_etude(conn, mois)
    ls = [x for x in lignes(conn, mois) if x["saisi"]]
    if not j or not ls:
        return None
    unites = []
    if etab_srv.est_groupe(conn):
        for u in dict.fromkeys(x["unite"] for x in ls):
            unites.append({"unite": u or "دون وحدة", **_agreger([x for x in ls if x["unite"] == u], j)})
    return {"mois": mois, "libelle": libelle_mois(mois), "jours_etude": j, "classes": ls, "unites": unites,
            "etablissement": _agreger(ls, j)}


def evolution(conn: sqlite3.Connection) -> list[dict]:
    """الأشهر المُدرجة بالترتيب، مع نسبة المؤسسة ونسبة كل وحدة."""
    res = []
    for m, _ in mois_de_l_annee(conn):
        s = synthese_mois(conn, m)
        if s:
            res.append(s)
    return res


def dernier_taux(conn: sqlite3.Connection) -> tuple[str, float] | None:
    """لوحة القيادة: نسبة غياب آخر شهر مُدرج."""
    try:
        ev = evolution(conn)
    except ErreurAbsence:
        return None
    return (ev[-1]["libelle"], ev[-1]["etablissement"]["taux"]) if ev else None


def generer_rapport(conn: sqlite3.Connection, dossier: DossierDonnees, mois: str,
                    graphique_png: bytes | None = None) -> Path:
    """التقرير الشهري للغياب (Word). graphique_png: مبيان المؤسسة عبر الأشهر، ترسمه الواجهة."""
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
    para(d, f"تقرير الغياب الشهري: {s['libelle']}", gras=True, taille=16, centre=True, souligne=True, apres=2)
    para(d, f"السنة الدراسية {annee} · أيام الدراسة الفعلية: {s['jours_etude']:g}", taille=10, centre=True, apres=6)
    groupe = bool(s["unites"])
    entetes = (["الوحدة"] if groupe else []) + ["القسم", "عدد التلاميذ", "المتغيبون", "أيام الغياب", "نسبة الغياب"]
    largeurs = ([3.2] if groupe else []) + [4.2, 2.4, 2.4, 2.4, 2.6]
    t = tableau(d, 1 + len(s["classes"]), len(entetes), largeurs=largeurs)
    for j, h in enumerate(entetes):
        _cellule(t.cell(0, j), h, gras=True, taille=10)
        _ombre(t.cell(0, j))
    for i, x in enumerate(s["classes"], start=1):
        vals = ([x["unite"] or "—"] if groupe else []) + [x["classe"], str(x["effectif"]), str(x["absents"]),
                                                         f"{x['jours_absence']:g}", _fmt(x["taux"])]
        for j, v in enumerate(vals):
            _cellule(t.cell(i, j), v, taille=10)
    para(d, "", apres=4)
    lignes_synth = [(u["unite"], u) for u in s["unites"]] + [("المؤسسة كاملة", s["etablissement"])]
    t2 = tableau(d, 1 + len(lignes_synth), 5, largeurs=[5, 2.6, 2.6, 2.6, 2.8])
    for j, h in enumerate(("", "عدد التلاميذ", "المتغيبون", "أيام الغياب", "نسبة الغياب")):
        _cellule(t2.cell(0, j), h, gras=True, taille=10)
        _ombre(t2.cell(0, j))
    for i, (lib, a) in enumerate(lignes_synth, start=1):
        for j, v in enumerate((lib, str(a["effectif"]), str(a["absents"]), f"{a['jours_absence']:g}", _fmt(a["taux"]))):
            _cellule(t2.cell(i, j), v, gras=(lib == "المؤسسة كاملة"), taille=10)
    if graphique_png:
        para(d, "", apres=4)
        para(d, "تطور نسبة الغياب بالمؤسسة كاملة حسب الأشهر المُدرجة", gras=True, taille=12, centre=True, apres=2)
        d.add_picture(io.BytesIO(graphique_png), width=Cm(16))
        d.paragraphs[-1].alignment = 1
    para(d, "", apres=6)
    para(d, f"حرر في: {etab.ville_redaction_ar if etab and etab.ville_redaction_ar else '……………'} بتاريخ "
            f"{tx.date_ar(datetime.now().date())}", taille=11, apres=2)
    para(d, "توقيع المدير(ة):", gras=True, taille=11)
    rep = dossier.archives / annee.replace("/", "-") / "الغياب"
    rep.mkdir(parents=True, exist_ok=True)
    chemin = rep / f"{datetime.now():%Y%m%d_%H%M%S}_تقرير_الغياب_{mois}.docx"
    d.save(chemin)
    return chemin


def _fmt(v: float | None) -> str:
    return "—" if v is None else f"{v:g}%"
