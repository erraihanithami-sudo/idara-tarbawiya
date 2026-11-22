"""المدرسة الرائدة (طلب المدير 2026-11-19): مكونات فرعية حول شارة الريادة.

- تتبع النتائج حسب الفترات (الرائز القبلي، المراحل، الرائز البعدي) من جدول ISA2 حسب المراحل، وتقرير تركيبي.
- التواصل: الأيام التواصلية والأبواب المفتوحة، تُسجَّل لكل لقاء معطياته، ويُولَّد تقرير اللقاء وتقرير تركيبي.
- المؤشرات العامة: التحكم في التعلمات الأساس، تطور ISA2، مضاعفة عدد المستفيدين من الأنشطة الموازية، تقليص
  الهدر. تُحسب من معطيات البرنامج للسنة الجارية والسنة السابقة، ولا تُعرض قيمة لا معطيات لها.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from idara.data.dossier import DossierDonnees
from idara.services import documents as dc
from idara.services import projet_etab as pe
from idara.services import riyada as ry
from idara.services import textes as tx
from idara.services.docs_association import _cellule, _nouveau, _ombre, para, tableau

TYPES_RENCONTRE = {"rencontre": "اليوم التواصلي", "portes": "الأبواب المفتوحة"}


class ErreurPionniere(ValueError):
    """رسالة موجهة للمدير بالعربية."""


def _moy(xs) -> float | None:
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 2) if xs else None


def annee_precedente(libelle: str) -> str:
    y = int(libelle[:4])
    return f"{y - 1}/{y}"


# ---------- تتبع النتائج حسب الفترات ----------

def resultats_periode(conn, annee: str, phase: int) -> list[dict]:
    """لكل قسم: نسبة كل مادة في الفترة، ومعدل المواد."""
    d = ry.isa(conn, annee)
    res = []
    for cl in sorted(d):
        v = {m: d[cl].get(m, {}).get(phase) for m in ry.MATIERES}
        if any(x is not None for x in v.values()):
            res.append({"classe": cl, **v, "moyenne": _moy(v.values())})
    return res


def moyennes_par_phase(conn, annee: str) -> dict[int, dict[str, float | None]]:
    """الفترة ← المادة ← معدل الأقسام (و«all» لمعدل المواد). الفترات التي لا معطيات لها لا تظهر."""
    res = {}
    for p in ry.PHASES:
        lignes = resultats_periode(conn, annee, p)
        if lignes:
            v = {m: _moy(l[m] for l in lignes) for m in ry.MATIERES}
            v["all"] = _moy(v.values())
            res[p] = v
    return res


def _entete(conn, d, titre: str, annee: str) -> None:
    try:
        c = dc.champs_communs(conn)
    except dc.ErreurDocument as e:
        raise ErreurPionniere(str(e)) from None
    para(d, f"{c['ville']} في: {tx.date_longue_ar(date.today().isoformat())}", apres=0)
    para(d, f"المؤسسة: {c['etablissement']}", gras=True, apres=6)
    para(d, titre, gras=True, taille=20, centre=True, apres=0)
    para(d, f"السنة الدراسية {annee}", centre=True, apres=10)


def _sauver(d, dossier: DossierDonnees, annee: str, nom: str) -> Path:
    rep = dossier.archives / annee.replace("/", "-") / "المدرسة الرائدة"
    rep.mkdir(parents=True, exist_ok=True)
    chemin = rep / f"{datetime.now():%Y%m%d_%H%M%S}_{nom}.docx"
    d.save(chemin)
    return chemin


def _f(x) -> str:
    return "—" if x is None else f"{x:.2f}%"


def _tete(t, libs) -> None:
    for j, lib in enumerate(libs):
        _cellule(t.cell(0, j), lib, gras=True, taille=12)
        _ombre(t.cell(0, j))


def generer_rapport_resultats(conn, dossier: DossierDonnees, annee: str) -> Path:
    """تقرير تركيبي حول النتائج: تطور المعدل حسب الفترات، ثم جدول الأقسام لكل فترة، وقراءة موجزة."""
    moy = moyennes_par_phase(conn, annee)
    if not moy:
        raise ErreurPionniere("لا نتائج مسجلة لهذه السنة: أدخل نسب الفترات أو استورد نتائج الروائز أولاً.")
    d = _nouveau()
    _entete(conn, d, "تقرير تركيبي حول النتائج حسب الفترات", annee)
    para(d, "1. تطور نسب التحكم حسب الفترات (معدل الأقسام)", gras=True, taille=16, apres=2)
    libs = ["الفترة", *ry.MATIERES.values(), "معدل المواد", "التطور"]
    t = tableau(d, 1 + len(moy), len(libs), largeurs=[3.6, 2.6, 2.6, 2.6, 2.8, 2.6])
    _tete(t, libs)
    avant = None
    for i, (p, v) in enumerate(moy.items(), start=1):
        ec = None if avant is None or v["all"] is None else round(v["all"] - avant, 2)
        for j, x in enumerate((ry.libelle_phase(p), *(_f(v[m]) for m in ry.MATIERES), _f(v["all"]),
                               "—" if ec is None else f"‎{ec:+.2f}")):
            _cellule(t.cell(i, j), x, taille=11)
        avant = v["all"] if v["all"] is not None else avant
    for n, (p, _) in enumerate(moy.items(), start=2):
        lignes = resultats_periode(conn, annee, p)
        para(d, "", apres=4)
        para(d, f"{n}. {ry.libelle_phase(p)}: النسب حسب الأقسام", gras=True, taille=15, apres=2)
        libs = ["القسم", *ry.MATIERES.values(), "المعدل"]
        t = tableau(d, 1 + len(lignes), len(libs), largeurs=[3.4, 3, 3, 3, 3])
        _tete(t, libs)
        for i, l in enumerate(lignes, start=1):
            for j, x in enumerate((l["classe"], *(_f(l[m]) for m in ry.MATIERES), _f(l["moyenne"]))):
                _cellule(t.cell(i, j), x, taille=11)
    # قراءة موجزة: آخر فترة متوفرة
    p_fin = list(moy)[-1]
    v = moy[p_fin]
    meilleures = sorted(((v[m], lib) for m, lib in ry.MATIERES.items() if v[m] is not None), reverse=True)
    para(d, "", apres=4)
    para(d, "قراءة موجزة", gras=True, taille=15, apres=2)
    if meilleures:
        para(d, f"• في {ry.libelle_phase(p_fin)}: أعلى نسبة في {meilleures[0][1]} ({meilleures[0][0]:.2f}%)"
                + (f"، وأدناها في {meilleures[-1][1]} ({meilleures[-1][0]:.2f}%)." if len(meilleures) > 1 else "."))
    if len(moy) > 1:
        p0 = list(moy)[0]
        if moy[p0]["all"] is not None and v["all"] is not None:
            e = round(v["all"] - moy[p0]["all"], 2)
            para(d, f"• تطور معدل المواد من {ry.libelle_phase(p0)} إلى {ry.libelle_phase(p_fin)}: ‎{e:+.2f} نقطة.")
    faibles = [l["classe"] for l in resultats_periode(conn, annee, p_fin) if l["moyenne"] is not None
               and l["moyenne"] < 50]
    if faibles:
        para(d, "• أقسام دون 50% تحتاج دعماً مركزاً: " + "، ".join(faibles) + ".")
    return _sauver(d, dossier, annee, "تقرير تركيبي حول النتائج")


# ---------- التواصل: الأيام التواصلية والأبواب المفتوحة ----------

@dataclass
class Rencontre:
    type: str
    date_rencontre: str
    theme: str = ""
    heure: str = ""
    invites: int | None = None
    presents: int | None = None
    deroulement: str = ""
    recommandations: str = ""
    id: int | None = None


def _aid(conn, annee: str | None) -> tuple[int, str]:
    from idara.services import annee as annee_srv
    if annee:
        r = conn.execute("SELECT id, libelle FROM annee_scolaire WHERE libelle=?", (annee,)).fetchone()
    else:
        r = annee_srv.annee_courante(conn)
    if r is None:
        raise ErreurPionniere("لا سنة دراسية جارية.")
    return r["id"], r["libelle"]


def enregistrer_rencontre(conn, r: Rencontre) -> int:
    if r.type not in TYPES_RENCONTRE:
        raise ErreurPionniere("نوع اللقاء غير معروف.")
    try:
        date.fromisoformat(r.date_rencontre)
    except ValueError:
        raise ErreurPionniere("تاريخ اللقاء غير صحيح.") from None
    if r.invites is not None and r.presents is not None and r.presents > r.invites:
        raise ErreurPionniere("عدد الحاضرين أكبر من عدد المدعوين.")
    aid, _ = _aid(conn, None)
    vals = (r.type, r.date_rencontre, r.heure or None, r.theme.strip(), r.invites, r.presents,
            r.deroulement.strip(), r.recommandations.strip())
    with conn:
        if r.id:
            conn.execute("UPDATE rencontre_parents SET type=?, date_rencontre=?, heure=?, theme=?, invites=?, "
                         "presents=?, deroulement=?, recommandations=? WHERE id=?", (*vals, r.id))
            return r.id
        return conn.execute("INSERT INTO rencontre_parents(type, date_rencontre, heure, theme, invites, presents, "
                            "deroulement, recommandations, annee_id) VALUES (?,?,?,?,?,?,?,?,?)",
                            (*vals, aid)).lastrowid


def rencontres(conn, type_: str | None = None, annee: str | None = None) -> list[Rencontre]:
    try:
        aid, _ = _aid(conn, annee)
    except ErreurPionniere:
        return []
    sql = "SELECT * FROM rencontre_parents WHERE annee_id=?"
    args: list = [aid]
    if type_:
        sql += " AND type=?"
        args.append(type_)
    return [Rencontre(r["type"], r["date_rencontre"], r["theme"], r["heure"] or "", r["invites"], r["presents"],
                      r["deroulement"], r["recommandations"], r["id"])
            for r in conn.execute(sql + " ORDER BY date_rencontre DESC, id DESC", args)]


def rencontre(conn, rid: int) -> Rencontre:
    r = next((x for x in rencontres(conn) if x.id == rid), None)
    if r is None:
        raise ErreurPionniere("اللقاء غير موجود.")
    return r


def supprimer_rencontre(conn, rid: int) -> None:
    with conn:
        conn.execute("DELETE FROM rencontre_parents WHERE id=?", (rid,))


def taux_presence(r: Rencontre) -> float | None:
    return round(100 * r.presents / r.invites, 1) if r.invites and r.presents is not None else None


def generer_rapport_rencontre(conn, dossier: DossierDonnees, rid: int) -> Path:
    r = rencontre(conn, rid)
    _, annee = _aid(conn, None)
    lib = TYPES_RENCONTRE[r.type]
    d = _nouveau()
    _entete(conn, d, f"تقرير حول {lib}", annee)
    t = tableau(d, 5, 2, largeurs=[5, 11])
    tp = taux_presence(r)
    for i, (k, v) in enumerate((("التاريخ", tx.date_longue_ar(r.date_rencontre) + (f" على الساعة {r.heure}"
                                                                                     if r.heure else "")),
                                ("الموضوع", r.theme or "—"),
                                ("المدعوون", "—" if r.invites is None else str(r.invites)),
                                ("الحاضرون", "—" if r.presents is None else str(r.presents)),
                                ("نسبة الحضور", "—" if tp is None else f"{tp:.1f}%"))):
        _cellule(t.cell(i, 0), k, gras=True, taille=12)
        _ombre(t.cell(i, 0))
        _cellule(t.cell(i, 1), v, taille=12, centre=False)
    for titre, texte in (("سير اللقاء", r.deroulement), ("التوصيات والالتزامات", r.recommandations)):
        para(d, "", apres=4)
        para(d, titre, gras=True, taille=15, apres=2)
        for l in [x for x in (texte or "").splitlines() if x.strip()] or ["—"]:
            para(d, "• " + l.strip())
    from idara.services import photos as ph
    ph.inserer_docx(d, conn, dossier, "rencontre", rid, f"صور من {lib}")
    para(d, "", apres=10)
    para(d, "توقيع مدير المؤسسة", gras=True)
    return _sauver(d, dossier, annee, f"تقرير {lib} {r.date_rencontre}")


def generer_rapport_rencontres(conn, dossier: DossierDonnees, type_: str | None = None) -> Path:
    """تقرير تركيبي حول الأيام التواصلية والأبواب المفتوحة (أو نوع واحد)."""
    _, annee = _aid(conn, None)
    rs = sorted(rencontres(conn, type_), key=lambda x: x.date_rencontre)
    if not rs:
        raise ErreurPionniere("لا لقاءات مسجلة لهذه السنة.")
    titre = TYPES_RENCONTRE[type_] if type_ else "الأيام التواصلية والأبواب المفتوحة"
    d = _nouveau()
    _entete(conn, d, f"تقرير تركيبي حول {titre}", annee)
    libs = ["التاريخ", "النوع", "الموضوع", "المدعوون", "الحاضرون", "النسبة"]
    t = tableau(d, 2 + len(rs), len(libs), largeurs=[2.6, 3, 5, 2, 2, 2])
    _tete(t, libs)
    for i, r in enumerate(rs, start=1):
        tp = taux_presence(r)
        for j, x in enumerate((tx.date_chiffres(r.date_rencontre), TYPES_RENCONTRE[r.type], r.theme or "—",
                               "—" if r.invites is None else str(r.invites),
                               "—" if r.presents is None else str(r.presents), "—" if tp is None else f"{tp:.1f}%")):
            _cellule(t.cell(i, j), x, taille=11)
    inv = sum(r.invites or 0 for r in rs if r.presents is not None)
    pres = sum(r.presents or 0 for r in rs if r.invites)
    k = len(rs) + 1
    _cellule(t.cell(k, 0), "المجموع", gras=True, taille=11)
    _cellule(t.cell(k, 3), str(inv) if inv else "—", gras=True, taille=11)
    _cellule(t.cell(k, 4), str(pres) if inv else "—", gras=True, taille=11)
    _cellule(t.cell(k, 5), f"{100 * pres / inv:.1f}%" if inv else "—", gras=True, taille=11)
    recs = [l.strip() for r in rs for l in r.recommandations.splitlines() if l.strip()]
    if recs:
        para(d, "", apres=4)
        para(d, "أبرز التوصيات", gras=True, taille=15, apres=2)
        for l in recs:
            para(d, "• " + l)
    return _sauver(d, dossier, annee, f"تقرير تركيبي حول {titre}")


# ---------- المؤشرات العامة ----------

def _isa_global(conn, annee: str) -> dict[int, float]:
    """معدل ISA2 للمؤسسة لكل مرحلة (المراحل 1 فما فوق)."""
    return {p: v["all"] for p, v in moyennes_par_phase(conn, annee).items() if p >= 1 and v["all"] is not None}


def indicateurs(conn: sqlite3.Connection) -> list[dict]:
    """المؤشرات الأربعة: القيمة الحالية، المرجع (السنة السابقة أو أول مرحلة)، الهدف والاتجاه، والحالة."""
    _, annee = _aid(conn, None)
    prec = annee_precedente(annee)
    res = []
    t1, t0 = pe.mesure_tarl(conn, annee), pe.mesure_tarl(conn, prec)
    res.append({"cle": "tarl", "titre": "التحكم في التعلمات الأساس", "valeur": t1["valeur"],
                "reference": t0["valeur"], "ref_lib": f"السنة {prec}", "unite": "%", "sens": 1,
                "detail": (f"{t1['maitrise']} من {t1['total']} (تلميذ × مادة) بلغوا المستوى المتوقع"
                           if t1["total"] else "لا نتائج رائز بعد"), "cible": None})
    isa = _isa_global(conn, annee)
    if isa:
        p0, p1 = min(isa), max(isa)
        res.append({"cle": "isa2", "titre": "تطور مؤشر ISA2", "valeur": isa[p1],
                    "reference": isa[p0] if p1 != p0 else None, "ref_lib": ry.libelle_phase(p0), "unite": "%",
                    "sens": 1, "detail": f"آخر مرحلة: {ry.libelle_phase(p1)}", "points": isa, "cible": None})
    else:
        res.append({"cle": "isa2", "titre": "تطور مؤشر ISA2", "valeur": None, "reference": None, "ref_lib": "",
                    "unite": "%", "sens": 1, "detail": "لا نسب مراحل مسجلة بعد", "points": {}, "cible": None})
    a1, a0 = pe.mesure_activites(conn, annee), pe.mesure_activites(conn, prec)
    ref = a0["participants"] or None
    res.append({"cle": "activites", "titre": "مضاعفة المستفيدين من الأنشطة الموازية",
                "valeur": float(a1["participants"]) if a1["eleves"] else None, "reference": ref,
                "ref_lib": f"السنة {prec}", "unite": "", "sens": 1, "cible": 2 * ref if ref else None,
                "detail": (f"{a1['participants']} تلميذاً في الأندية من {a1['eleves']}" if a1["eleves"]
                           else "لا تلاميذ مسجلون")})
    h1, h0 = pe.mesure_hadar(conn, annee), pe.mesure_hadar(conn, prec)
    res.append({"cle": "hadar", "titre": "تقليص نسب الهدر المدرسي", "valeur": h1["valeur"],
                "reference": h0["valeur"], "ref_lib": f"السنة {prec}", "unite": "%", "sens": -1, "cible": None,
                "detail": (f"منقطعون {h1['interrompus']} · مفصولون {h1['exclus']} من {h1['concernes']}"
                           if h1["concernes"] else "لا تلاميذ مسجلون")})
    for x in res:
        v, r = x["valeur"], x["reference"]
        x["ecart"] = None if v is None or r is None else round(v - r, 2)
        if v is None:
            x["etat"] = "لا معطيات"
        elif x["cible"] is not None:
            x["etat"] = "بلغ الهدف" if v >= x["cible"] else f"الهدف: {x['cible']:g}"
        elif x["ecart"] is None:
            x["etat"] = "لا مرجع للمقارنة"
        elif x["ecart"] * x["sens"] > 0:
            x["etat"] = "في تحسن"
        elif x["ecart"] == 0:
            x["etat"] = "مستقر"
        else:
            x["etat"] = "في تراجع"
    return res
