"""محاضر نهاية الأسدوس (ملف المدير «محاضر نهاية الأسدوس (إبتدائي)»، 2026-11-03).

لكل قسم: «قرار مجلس القسم» (لائحة التلاميذ بمعدلاتهم وميزاتهم ورتبهم، وفي الدورة الثانية القرار) و«محضر مجلس
القسم» (المعدلات، الاستحقاق، إحصائيات النتائج، التقديرات، توقيعات الأساتذة). لكل مستوى: «محضر نتائج المستوى».

القواعد المستخرجة من ملف المدير:
- عتبة النجاح 5/10؛ القرار في الدورة الثانية: «ينتقل» إن كان المعدل السنوي 5 فما فوق، وإلا «يكرر».
- الميزة (على 10): تنويه من 8 فما فوق، تشجيع من 7 إلى أقل من 8، لوحة الشرف من 6 إلى أقل من 7.
- الإنذار والتوبيخ قراران للمجلس (لا تحسبهما صيغ الملف من المعدل): يُسجلان لكل تلميذ.
- السادس في الدورة الثانية: المراقبة المستمرة للدورتين، الامتحان الموحد المحلي والإقليمي، المعدل السنوي
  (50% متوسط الدورتين + 25% المحلي + 25% الإقليمي) والتوجيه.
- المعدل الملاحظ: متوسط معدلات القسم؛ «الحاصلون عليه»: من بلغه.
"""

from __future__ import annotations

import math
import sqlite3
from datetime import datetime
from pathlib import Path

from idara.data.dossier import DossierDonnees
from idara.services import documents as dc
from idara.services import etablissement as etab_srv
from idara.services import textes as tx
from idara.services.docs_association import _cellule, _nouveau, _ombre, para, saut_page, tableau
from idara.services.evaluation import ORDINAUX, SEUIL, ErreurEvaluation


def _pct(n: int, total: int) -> str:
    """النسبة مقطوعة إلى رقمين كما في محاضر المدير."""
    if not total:
        return "—"
    return f"{math.floor(n * 10000 / total + 1e-9) / 100:.2f}%"


def _iso(v: str) -> str:
    """نص رقمي (نسبة، معدل) معزول الاتجاه حتى لا ينقلب داخل السطر العربي."""
    return f"\u2066{v}\u2069" if v and v != "—" else v


def _enregistrer(d, dossier: DossierDonnees, annee: str, nom: str) -> Path:
    rep_ = dossier.archives / annee.replace("/", "-") / "محاضر نهاية الأسدوس"
    rep_.mkdir(parents=True, exist_ok=True)
    chemin = rep_ / f"{datetime.now():%Y%m%d_%H%M%S}_{nom}.docx"
    d.save(chemin)
    return chemin

PERIODES = {"S1": "الأسدوس الأول", "S2": "الأسدوس الثاني"}
POUR = {"S1": "للأسدوس الأول", "S2": "للأسدوس الثاني"}
SANCTIONS = ("إنذار", "توبيخ")
MENTIONS = ("تنويه", "تشجيع", "لوحة الشرف")


def mention(m: float | None) -> str:
    if m is None:
        return ""
    if m >= 8:
        return "تنويه"
    if m >= 7:
        return "تشجيع"
    if m >= 6:
        return "لوحة الشرف"
    return ""


def _f(x) -> str:
    return "" if x is None else f"{x:.2f}"


def _annee_id(conn, annee: str) -> int:
    r = conn.execute("SELECT id FROM annee_scolaire WHERE libelle=?", (annee,)).fetchone()
    if r is None:
        raise ErreurEvaluation(f"لا نتائج مستوردة للسنة {annee}.")
    return r[0]


def classes(conn, annee: str) -> list[tuple[str, str | None]]:
    return [(r[0], r[1]) for r in conn.execute(
        "SELECT r.classe, MIN(r.niveau) FROM resultat r JOIN annee_scolaire a ON a.id=r.annee_id WHERE a.libelle=? "
        "GROUP BY r.classe ORDER BY r.classe", (annee,))]


def lignes(conn, annee: str, periode: str, classe: str | None = None, niveau: str | None = None) -> list[dict]:
    """التلاميذ بمعدل الدورة المعنية، الميزة، الرتبة (داخل المجموعة)، القرار، وقرارات المجلس."""
    if periode not in PERIODES:
        raise ErreurEvaluation("الدورة غير صحيحة.")
    aid = _annee_id(conn, annee)
    sql = ("SELECT r.*, e.sexe, d.sanction, d.orientation FROM resultat r "
           "LEFT JOIN eleve e ON e.code_massar=r.code_massar "
           "LEFT JOIN deliberation d ON d.annee_id=r.annee_id AND d.code_massar=r.code_massar AND d.periode=? "
           "WHERE r.annee_id=?")
    args: list = [periode, aid]
    if classe:
        sql += " AND r.classe=?"
        args.append(classe)
    if niveau:
        sql += " AND r.niveau=?"
        args.append(niveau)
    res = []
    for r in conn.execute(sql + " ORDER BY r.classe, r.nom", args):
        note = r["moyenne_s1"] if periode == "S1" else r["moyenne"]
        res.append({"code": r["code_massar"], "nom": r["nom"], "classe": r["classe"], "niveau": r["niveau"],
                    "sexe": r["sexe"], "s1": r["moyenne_s1"], "s2": r["moyenne_s2"], "local": r["exam_local"],
                    "prov": r["exam_prov"], "note": note, "mention": mention(note),
                    "sanction": r["sanction"] or "", "orientation": r["orientation"] or "",
                    "decision": ("" if periode == "S1" or note is None else "ينتقل" if note >= SEUIL else "يكرر")})
    notes = sorted((l["note"] for l in res if l["note"] is not None), reverse=True)
    for l in res:   # رتبة مشتركة عند التساوي
        l["rang"] = notes.index(l["note"]) + 1 if l["note"] is not None else None
    return res


def enregistrer_deliberation(conn, annee: str, periode: str, code: str, sanction: str = "",
                             orientation: str = "") -> None:
    if sanction and sanction not in SANCTIONS:
        raise ErreurEvaluation("القرار: إنذار أو توبيخ.")
    aid = _annee_id(conn, annee)
    orientation = " ".join((orientation or "").split())
    with conn:
        if not sanction and not orientation:
            conn.execute("DELETE FROM deliberation WHERE annee_id=? AND periode=? AND code_massar=?",
                         (aid, periode, code))
        else:
            conn.execute("INSERT INTO deliberation(annee_id, periode, code_massar, sanction, orientation) "
                         "VALUES (?,?,?,?,?) ON CONFLICT(annee_id, periode, code_massar) DO UPDATE SET "
                         "sanction=excluded.sanction, orientation=excluded.orientation",
                         (aid, periode, code, sanction or None, orientation or None))


def statistiques(ls: list[dict]) -> dict:
    notes = [l["note"] for l in ls if l["note"] is not None]
    moy = round(sum(notes) / len(notes), 2) if notes else None
    st = {"max": max(notes) if notes else None, "min": min(notes) if notes else None, "moyenne": moy,
          "au_dessus": sum(n >= moy for n in notes) if notes else 0, "total": len(ls), "sans_note": len(ls) - len(notes)}
    st["pct_au_dessus"] = _pct(st["au_dessus"], len(notes)) if notes else "—"
    for cle, sexe in (("garcons", "M"), ("filles", "F"), ("tous", None)):
        g = [l for l in ls if sexe is None or l["sexe"] == sexe]
        n5 = sum(1 for l in g if l["note"] is not None and l["note"] >= SEUIL)
        st[cle] = {"nombre": len(g), "moyenne": n5, "pct": _pct(n5, len(g)) if g else "—",
                   "admis": sum(1 for l in g if l["decision"] == "ينتقل"),
                   "redoublants": sum(1 for l in g if l["decision"] == "يكرر")}
    st["inconnus"] = sum(1 for l in ls if l["sexe"] not in ("M", "F"))
    st["taux_reussite"] = _pct(st["tous"]["admis"], len(ls)) if ls else "—"
    st["mentions"] = {m: sum(1 for l in ls if l["mention"] == m) for m in MENTIONS}
    st["mentions"].update({s: sum(1 for l in ls if l["sanction"] == s) for s in SANCTIONS})
    st["merite"] = sorted((l for l in ls if l["rang"] is not None), key=lambda l: (l["rang"], l["nom"]))[:3]
    return st


# ---------- الوثائق ----------

def _entete(conn, dossier: DossierDonnees, d, annee: str, periode: str, lignes_sup: list[str]) -> None:
    try:
        c = dc.champs_communs(conn)
    except dc.ErreurDocument as e:
        raise ErreurEvaluation(str(e)) from None
    etab = etab_srv.lire_etablissement(conn)
    if etab and etab.logo_path and (dossier.racine / etab.logo_path).exists():
        from docx.shared import Cm
        d.add_picture(str(dossier.racine / etab.logo_path), width=Cm(17))
    t = tableau(d, 2, 2, bordures=False, largeurs=[11, 7])
    _cellule(t.cell(0, 0), f"الأكاديمية الجهوية للتربية والتكوين: {etab.academie_ar or ''}", taille=10, centre=False)
    _cellule(t.cell(0, 1), f"السنة الدراسية: {annee}", taille=10, centre=False)
    _cellule(t.cell(1, 0), f"المديرية الإقليمية: {etab.direction_ar or ''} · المؤسسة: {c['etablissement']}",
             taille=10, centre=False)
    _cellule(t.cell(1, 1), f"الدورة: {'الأولى' if periode == 'S1' else 'الثانية'} · عتبة النجاح: {SEUIL:g}",
             taille=10, centre=False)
    for l in lignes_sup:
        para(d, l, gras=True, taille=11, apres=2)


def _signatures(conn, d, classe: str) -> None:
    para(d, "توقيعات السادة الأساتذة", gras=True, taille=12, centre=True, apres=4)
    profs = conn.execute(
        "SELECT DISTINCT p.prenom_ar, p.nom_ar, p.matiere FROM affectation_classe f JOIN classe c ON c.id=f.classe_id "
        "JOIN personnel p ON p.id=f.personnel_id JOIN annee_scolaire a ON a.id=c.annee_id "
        "WHERE c.code=? AND p.statut='actif' ORDER BY a.libelle DESC, p.matiere", (classe,)).fetchall()
    lignes_ = [(m, ", ".join(f"{p['prenom_ar']} {p['nom_ar']}" for p in profs if p["matiere"] in (m, "مزدوجة")))
               for m in ("عربية", "فرنسية")]
    t = tableau(d, 3, 3, largeurs=[4, 8, 5])
    for j, h in enumerate(("المادة", "الاسم الكامل", "التوقيع")):
        _cellule(t.cell(0, j), h, gras=True, taille=10)
        _ombre(t.cell(0, j))
    for i, (m, noms) in enumerate(lignes_, start=1):
        _cellule(t.cell(i, 0), "العربية" if m == "عربية" else "الفرنسية", taille=10)
        _cellule(t.cell(i, 1), noms, taille=10)
        _cellule(t.cell(i, 2), "", taille=10)
    para(d, "", apres=6)
    para(d, "طابع وتوقيع رئيس(ة) المؤسسة", gras=True, taille=11, apres=40)


def _table_stats(d, st: dict, periode: str) -> None:
    para(d, "المعدلات", gras=True, taille=12, apres=2)
    t = tableau(d, 2, 5, largeurs=[3.4, 3.4, 3.4, 3.4, 3.4])
    for j, (h, v) in enumerate((("أعلى معدل", _f(st["max"])), ("أدنى معدل", _f(st["min"])),
                                ("المعدل الملاحظ", _f(st["moyenne"])), ("الحاصلون عليه", str(st["au_dessus"])),
                                ("النسبة المئوية", _iso(st["pct_au_dessus"])))):
        _cellule(t.cell(0, j), h, gras=True, taille=10)
        _ombre(t.cell(0, j))
        _cellule(t.cell(1, j), v or "—", taille=10)
    para(d, "إحصائيات النتائج", gras=True, taille=12, apres=2)
    cols = ["التلاميذ", "العدد", "الحاصلون على 5 فما فوق", "النسبة المئوية"]
    if periode == "S2":
        cols += ["الناجحون", "المكررون"]
    t = tableau(d, 4, len(cols), largeurs=[3] * len(cols))
    for j, h in enumerate(cols):
        _cellule(t.cell(0, j), h, gras=True, taille=10)
        _ombre(t.cell(0, j))
    for i, (lib, k) in enumerate((("الذكور", "garcons"), ("الإناث", "filles"), ("المجموع", "tous")), start=1):
        g = st[k]
        vals = [lib, str(g["nombre"]), str(g["moyenne"]), _iso(g["pct"])]
        if periode == "S2":
            vals += [str(g["admis"]), str(g["redoublants"])]
        for j, v in enumerate(vals):
            _cellule(t.cell(i, j), v, gras=(k == "tous"), taille=10)
    if periode == "S2":
        para(d, f"نسبة النجاح: {_iso(st['taux_reussite'])}", gras=True, taille=11, apres=2)
    if st["inconnus"]:
        para(d, f"منهم {st['inconnus']} غير مسجلين في لوائح التلاميذ (النوع غير معروف): يُحسبون في المجموع فقط.",
             taille=9, apres=2)
    para(d, f"التقديرات ({PERIODES[periode]})", gras=True, taille=12, apres=2)
    noms = ("تنويه", "تشجيع", "لوحة الشرف", "إنذار", "توبيخ")
    t = tableau(d, 2, 5, largeurs=[3.4] * 5)
    for j, m in enumerate(noms):
        _cellule(t.cell(0, j), m, gras=True, taille=10)
        _ombre(t.cell(0, j))
        _cellule(t.cell(1, j), str(st["mentions"][m]), taille=10)


def _table_merite(d, st: dict, avec_classe: bool) -> None:
    para(d, "الاستحقاق", gras=True, taille=12, apres=2)
    cols = ["الترتيب", "الاسم الكامل", "المعدل"] + (["القسم"] if avec_classe else [])
    t = tableau(d, 1 + max(1, len(st["merite"])), len(cols), largeurs=[2.5, 8, 3] + ([4] if avec_classe else []))
    for j, h in enumerate(cols):
        _cellule(t.cell(0, j), h, gras=True, taille=10)
        _ombre(t.cell(0, j))
    for i, l in enumerate(st["merite"], start=1):
        vals = [str(l["rang"]), l["nom"], _f(l["note"])] + ([l["classe"]] if avec_classe else [])
        for j, v in enumerate(vals):
            _cellule(t.cell(i, j), v, taille=10)


def generer_classe(conn, dossier: DossierDonnees, annee: str, classe: str, periode: str) -> Path:
    """قرار مجلس القسم (صفحة) ثم محضر مجلس القسم (صفحة)."""
    ls = lignes(conn, annee, periode, classe=classe)
    if not ls:
        raise ErreurEvaluation(f"لا نتائج مستوردة للقسم {classe}.")
    niveau = next((l["niveau"] for l in ls if l["niveau"]), None)
    six = niveau == "6AP" and periode == "S2"
    manque = [l["nom"] for l in ls if l["note"] is None]
    if manque:
        raise ErreurEvaluation(("معدل غير متوفر (استورد ملف مسار «مجمل المعدلات» "
                                + ("بالدورتين والامتحانين المحلي والإقليمي" if six else "المناسب") + "): ")
                               + "، ".join(manque[:8]) + ("..." if len(manque) > 8 else ""))
    d = _nouveau(paysage=six)
    lib_niv = f"المستوى: {ORDINAUX.get(niveau, niveau or '—')} ابتدائي · القسم: {classe}"
    _entete(conn, dossier, d, annee, periode, [])
    para(d, f"قرار مجلس القسم {POUR[periode]}", gras=True, taille=16, centre=True, apres=2)
    para(d, lib_niv, gras=True, taille=11, centre=True, apres=4)
    if six:
        cols = ["ر.ت", "رمز التلميذ(ة)", "الاسم والنسب", "النوع", "م.م الدورة 1", "م.م الدورة 2", "الامتحان المحلي",
                "الامتحان الإقليمي", "المعدل السنوي", "الرتبة", "الميزة", "القرار", "التوجيه"]
        larg = [1, 2.6, 5, 1.2, 1.8, 1.8, 1.8, 1.8, 1.8, 1.3, 2, 1.6, 3]
    else:
        cols = ["ر.ت", "رمز التلميذ(ة)", "الاسم والنسب", "النوع"] + (
            ["معدل الدورة 1"] if periode == "S1" else ["معدل الدورة 1", "معدل الدورة 2", "المعدل السنوي"]) + (
            ["الميزة", "الرتبة"] + (["القرار"] if periode == "S2" else []))
        larg = [0.9, 2.4, 4.6, 1.1] + ([1.9] if periode == "S1" else [1.7, 1.7, 1.7]) + [1.9, 1.2] + (
            [1.5] if periode == "S2" else [])
    t = tableau(d, 1 + len(ls), len(cols), largeurs=larg)
    for j, h in enumerate(cols):
        _cellule(t.cell(0, j), h, gras=True, taille=9)
        _ombre(t.cell(0, j))
    for i, l in enumerate(ls, start=1):
        sexe = {"M": "ذكر", "F": "أنثى"}.get(l["sexe"], "—")
        mention_ = l["sanction"] or l["mention"]
        if six:
            vals = [str(i), l["code"], l["nom"], sexe, _f(l["s1"]), _f(l["s2"]), _f(l["local"]), _f(l["prov"]),
                    _f(l["note"]), str(l["rang"]), mention_, l["decision"], l["orientation"]]
        elif periode == "S1":
            vals = [str(i), l["code"], l["nom"], sexe, _f(l["note"]), mention_, str(l["rang"])]
        else:
            vals = [str(i), l["code"], l["nom"], sexe, _f(l["s1"]), _f(l["s2"]), _f(l["note"]), mention_,
                    str(l["rang"]), l["decision"]]
        for j, v in enumerate(vals):
            _cellule(t.cell(i, j), v, taille=9, centre=(j != 2))
    saut_page(d)
    _entete(conn, dossier, d, annee, periode, [])
    para(d, f"محضر مجلس القسم {POUR[periode]}", gras=True, taille=16, centre=True, apres=2)
    para(d, lib_niv, gras=True, taille=11, centre=True, apres=4)
    st = statistiques(ls)
    _table_stats(d, st, periode)
    _table_merite(d, st, avec_classe=False)
    para(d, "", apres=4)
    _signatures(conn, d, classe)
    return _enregistrer(d, dossier, annee,
                        f"قرار ومحضر مجلس القسم {classe} {'د1' if periode == 'S1' else 'د2'}")


def generer_niveau(conn, dossier: DossierDonnees, annee: str, niveau: str, periode: str) -> Path:
    ls = lignes(conn, annee, periode, niveau=niveau)
    if not ls:
        raise ErreurEvaluation(f"لا نتائج للمستوى {ORDINAUX.get(niveau, niveau)}.")
    if any(l["note"] is None for l in ls):
        raise ErreurEvaluation("معدلات ناقصة في المستوى: استورد ملف مسار الكامل.")
    d = _nouveau()
    _entete(conn, dossier, d, annee, periode, [])
    para(d, f"محضر نتائج المستوى {POUR[periode]}", gras=True, taille=16, centre=True, apres=2)
    n_cl = len({l["classe"] for l in ls})
    para(d, f"المستوى: {ORDINAUX.get(niveau, niveau)} ابتدائي · عدد الأقسام: {n_cl}", gras=True, taille=11,
         centre=True, apres=6)
    st = statistiques(ls)
    _table_stats(d, st, periode)
    _table_merite(d, st, avec_classe=True)
    para(d, "", apres=8)
    para(d, "طابع وتوقيع رئيس(ة) المؤسسة", gras=True, taille=11, apres=40)
    return _enregistrer(d, dossier, annee,
                        f"محضر نتائج المستوى {ORDINAUX.get(niveau, niveau)} {'د1' if periode == 'S1' else 'د2'}")
