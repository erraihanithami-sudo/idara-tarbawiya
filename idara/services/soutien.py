"""الدعم التربوي (طلب المدير 2026-11-07).

- المراحل: مرحلة دعم (مثلاً: الدعم المرحلي الأول) بتاريخ بداية ونهاية.
- الفئات: فئات التلاميذ المتعثرين (تعثر في القراءة، الحساب...)، قابلة للتعديل.
- المجموعات: لكل مجموعة فئة وأستاذ متدخل ومادة، والتلاميذ المستفيدون من أقسام مختلفة.
- النتائج: نقطة قبل الدعم وبعده (على 10) لكل تلميذ؛ المقارنة تدخل في تقرير كل مرحلة.
- استعمال الزمن: حصص كل مجموعة، مع منع تداخل حصتين لنفس الأستاذ.
- الوثائق (Word): سجل الدعم لكل أستاذ، برنامج الدعم للمرحلة، وتقرير المرحلة.

عتبة التحكم 5/10 اختيار تقني قابل للتعديل (SEUIL)، لا مرجع رسمي.
"""

from __future__ import annotations

import io
import re
import sqlite3
from datetime import date, datetime
from pathlib import Path

from idara.data.dossier import DossierDonnees
from idara.services import annee as annee_srv
from idara.services import etablissement as etab_srv
from idara.services import textes as tx

CATEGORIES_DEFAUT = ["تعثر في القراءة", "تعثر في الكتابة", "تعثر في الحساب والرياضيات", "صعوبات في الفهم",
                     "تعثر في اللغة الفرنسية"]
JOURS = tx.JOURS_AR[:6]
SEUIL = 5.0
COLONNES_REGISTRE = 8


class ErreurSoutien(ValueError):
    """رسالة موجهة للمدير بالعربية."""


def _annee(conn) -> tuple[int, str]:
    a = annee_srv.annee_courante(conn)
    if a is None:
        raise ErreurSoutien("لا سنة دراسية جارية.")
    return a["id"], a["libelle"]


def _propre(t: str | None) -> str:
    return " ".join((t or "").split())


# ---------- الفئات ----------

def categories(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """فئات السنة؛ تُنشأ الفئات الافتراضية أول مرة."""
    aid, _ = _annee(conn)
    if not conn.execute("SELECT 1 FROM soutien_categorie WHERE annee_id=?", (aid,)).fetchone():
        with conn:
            conn.executemany("INSERT INTO soutien_categorie(annee_id, nom) VALUES (?,?)",
                             [(aid, n) for n in CATEGORIES_DEFAUT])
    return conn.execute("SELECT * FROM soutien_categorie WHERE annee_id=? ORDER BY id", (aid,)).fetchall()


def ajouter_categorie(conn: sqlite3.Connection, nom: str) -> int:
    aid, _ = _annee(conn)
    categories(conn)
    nom = _propre(nom)
    if not nom:
        raise ErreurSoutien("اسم الفئة إجباري.")
    try:
        with conn:
            return conn.execute("INSERT INTO soutien_categorie(annee_id, nom) VALUES (?,?)", (aid, nom)).lastrowid
    except sqlite3.IntegrityError:
        raise ErreurSoutien("هذه الفئة موجودة.") from None


def supprimer_categorie(conn: sqlite3.Connection, cid: int) -> None:
    if conn.execute("SELECT 1 FROM soutien_groupe WHERE categorie_id=?", (cid,)).fetchone():
        raise ErreurSoutien("لا يمكن حذف فئة مرتبطة بمجموعات دعم.")
    with conn:
        conn.execute("DELETE FROM soutien_categorie WHERE id=?", (cid,))


# ---------- المراحل ----------

def etapes(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    aid, _ = _annee(conn)
    return conn.execute("SELECT * FROM soutien_etape WHERE annee_id=? ORDER BY COALESCE(date_debut, ''), id",
                        (aid,)).fetchall()


def enregistrer_etape(conn: sqlite3.Connection, nom: str, debut: str = "", fin: str = "",
                      eid: int | None = None) -> int:
    aid, _ = _annee(conn)
    nom = _propre(nom)
    if not nom:
        raise ErreurSoutien("اسم المرحلة إجباري.")
    for d in (debut, fin):
        if d:
            try:
                date.fromisoformat(d)
            except ValueError:
                raise ErreurSoutien("تاريخ غير صحيح.") from None
    if debut and fin and fin < debut:
        raise ErreurSoutien("تاريخ النهاية قبل تاريخ البداية.")
    try:
        with conn:
            if eid:
                conn.execute("UPDATE soutien_etape SET nom=?, date_debut=?, date_fin=? WHERE id=?",
                             (nom, debut or None, fin or None, eid))
                return eid
            return conn.execute("INSERT INTO soutien_etape(annee_id, nom, date_debut, date_fin) VALUES (?,?,?,?)",
                                (aid, nom, debut or None, fin or None)).lastrowid
    except sqlite3.IntegrityError:
        raise ErreurSoutien("توجد مرحلة بنفس الاسم.") from None


def supprimer_etape(conn: sqlite3.Connection, eid: int) -> None:
    with conn:
        conn.execute("DELETE FROM soutien_etape WHERE id=?", (eid,))


def etape(conn, eid: int) -> sqlite3.Row:
    e = conn.execute("SELECT * FROM soutien_etape WHERE id=?", (eid,)).fetchone()
    if e is None:
        raise ErreurSoutien("المرحلة غير موجودة.")
    return e


# ---------- المتدخلون والمجموعات ----------

def intervenants(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """الأساتذة النشطون (والمدير إن تدخل بنفسه)."""
    return conn.execute(
        "SELECT id, prenom_ar || ' ' || nom_ar AS nom, categorie FROM personnel WHERE statut='actif' AND "
        "categorie IN ('enseignant','directeur') ORDER BY categorie='directeur', nom_ar, prenom_ar").fetchall()


def creer_groupe(conn: sqlite3.Connection, etape_id: int, categorie_id: int, personnel_id: int, matiere: str = "",
                 nom: str = "") -> int:
    etape(conn, etape_id)
    cat = conn.execute("SELECT nom FROM soutien_categorie WHERE id=?", (categorie_id,)).fetchone()
    if cat is None:
        raise ErreurSoutien("اختر فئة التعثر.")
    if not conn.execute("SELECT 1 FROM personnel WHERE id=?", (personnel_id,)).fetchone():
        raise ErreurSoutien("اختر الأستاذ المتدخل.")
    nom = _propre(nom)
    if not nom:
        n = conn.execute("SELECT COUNT(*) FROM soutien_groupe WHERE etape_id=? AND categorie_id=?",
                         (etape_id, categorie_id)).fetchone()[0]
        nom = f"{cat[0]} - المجموعة {n + 1}"
    with conn:
        return conn.execute("INSERT INTO soutien_groupe(etape_id, categorie_id, personnel_id, matiere, nom) "
                            "VALUES (?,?,?,?,?)", (etape_id, categorie_id, personnel_id, _propre(matiere) or None,
                                                   nom)).lastrowid


def supprimer_groupe(conn: sqlite3.Connection, gid: int) -> None:
    with conn:
        conn.execute("DELETE FROM soutien_groupe WHERE id=?", (gid,))


def groupes(conn: sqlite3.Connection, etape_id: int, personnel_id: int | None = None) -> list[dict]:
    q = ("SELECT g.*, c.nom AS categorie, p.prenom_ar || ' ' || p.nom_ar AS intervenant FROM soutien_groupe g "
         "JOIN soutien_categorie c ON c.id=g.categorie_id JOIN personnel p ON p.id=g.personnel_id WHERE g.etape_id=?")
    args: list = [etape_id]
    if personnel_id:
        q += " AND g.personnel_id=?"
        args.append(personnel_id)
    res = []
    for g in conn.execute(q + " ORDER BY c.id, g.id", args):
        m = membres(conn, g["id"])
        res.append({**dict(g), "effectif": len(m),
                    "classes": sorted({x["classe"] for x in m if x["classe"]}),
                    "seances": seances(conn, g["id"])})
    return res


def groupe(conn, gid: int) -> dict:
    g = conn.execute("SELECT etape_id FROM soutien_groupe WHERE id=?", (gid,)).fetchone()
    if g is None:
        raise ErreurSoutien("المجموعة غير موجودة.")
    return next(x for x in groupes(conn, g[0]) if x["id"] == gid)


# ---------- التلاميذ ----------

def eleves_classe(conn: sqlite3.Connection, classe_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT i.id AS inscription_id, e.nom_ar, e.prenom_ar, e.code_massar, e.sexe FROM inscription i "
        "JOIN eleve e ON e.id=i.eleve_id WHERE i.classe_id=? AND i.statut IN ('inscrit','arrive') "
        "ORDER BY e.nom_ar, e.prenom_ar", (classe_id,)).fetchall()


def affecter(conn: sqlite3.Connection, gid: int, inscriptions: list[int]) -> int:
    """يضيف التلاميذ إلى المجموعة (من سبق تسجيله يبقى بنتائجه). يعيد عدد المضافين."""
    eid = conn.execute("SELECT etape_id FROM soutien_groupe WHERE id=?", (gid,)).fetchone()
    if eid is None:
        raise ErreurSoutien("المجموعة غير موجودة.")
    if not inscriptions:
        raise ErreurSoutien("حدد تلميذاً واحداً على الأقل.")
    n = 0
    with conn:
        for i in inscriptions:
            n += conn.execute("INSERT OR IGNORE INTO soutien_eleve(groupe_id, inscription_id) VALUES (?,?)",
                              (gid, i)).rowcount
    return n


def retirer(conn: sqlite3.Connection, gid: int, inscription_id: int) -> None:
    with conn:
        conn.execute("DELETE FROM soutien_eleve WHERE groupe_id=? AND inscription_id=?", (gid, inscription_id))


def evolution_eleve(avant: float | None, apres: float | None) -> str:
    if avant is None or apres is None:
        return "—"
    if apres > avant:
        return "تحسن"
    return "استقرار" if apres == avant else "تراجع"


def membres(conn: sqlite3.Connection, gid: int) -> list[dict]:
    res = []
    for r in conn.execute(
            "SELECT s.*, e.nom_ar, e.prenom_ar, e.code_massar, e.sexe, c.code AS classe FROM soutien_eleve s "
            "JOIN inscription i ON i.id=s.inscription_id JOIN eleve e ON e.id=i.eleve_id "
            "LEFT JOIN classe c ON c.id=i.classe_id WHERE s.groupe_id=? ORDER BY c.code, e.nom_ar, e.prenom_ar",
            (gid,)):
        d = dict(r)
        d["nom"] = f"{r['nom_ar']} {r['prenom_ar']}"
        d["evolution"] = evolution_eleve(r["note_avant"], r["note_apres"])
        res.append(d)
    return res


def _note(v) -> float | None:
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    try:
        x = float(str(v).replace(",", "."))
    except ValueError:
        raise ErreurSoutien("النقطة رقم بين 0 و10.") from None
    if not 0 <= x <= 10:
        raise ErreurSoutien("النقطة بين 0 و10.")
    return x


def noter(conn: sqlite3.Connection, gid: int, valeurs: list[tuple[int, object, object, str]]) -> None:
    """valeurs: (التسجيل، قبل، بعد، ملاحظة)."""
    propres = [(_note(a), _note(b), _propre(o) or None, gid, i) for i, a, b, o in valeurs]
    with conn:
        conn.executemany("UPDATE soutien_eleve SET note_avant=?, note_apres=?, observation=? WHERE groupe_id=? AND "
                         "inscription_id=?", propres)


# ---------- استعمال الزمن ----------

_HEURE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def seances(conn: sqlite3.Connection, gid: int) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM soutien_seance WHERE groupe_id=? ORDER BY jour, heure_debut", (gid,)).fetchall()


def ajouter_seance(conn: sqlite3.Connection, gid: int, jour: int, debut: str, fin: str, lieu: str = "") -> int:
    g = conn.execute("SELECT etape_id, personnel_id FROM soutien_groupe WHERE id=?", (gid,)).fetchone()
    if g is None:
        raise ErreurSoutien("المجموعة غير موجودة.")
    if jour not in range(6):
        raise ErreurSoutien("اليوم غير صحيح.")
    if not (_HEURE.match(debut or "") and _HEURE.match(fin or "")):
        raise ErreurSoutien("الساعة بصيغة 14:30.")
    if fin <= debut:
        raise ErreurSoutien("نهاية الحصة قبل بدايتها.")
    conflit = conn.execute(
        "SELECT g.nom FROM soutien_seance s JOIN soutien_groupe g ON g.id=s.groupe_id WHERE g.etape_id=? AND "
        "g.personnel_id=? AND s.jour=? AND s.heure_debut < ? AND s.heure_fin > ?",
        (g["etape_id"], g["personnel_id"], jour, fin, debut)).fetchone()
    if conflit:
        raise ErreurSoutien(f"تتداخل هذه الحصة مع حصة أخرى لنفس الأستاذ ({conflit[0]}).")
    with conn:
        return conn.execute("INSERT INTO soutien_seance(groupe_id, jour, heure_debut, heure_fin, lieu) VALUES "
                            "(?,?,?,?,?)", (gid, jour, debut, fin, _propre(lieu) or None)).lastrowid


def supprimer_seance(conn: sqlite3.Connection, sid: int) -> None:
    with conn:
        conn.execute("DELETE FROM soutien_seance WHERE id=?", (sid,))


def emploi_du_temps(conn: sqlite3.Connection, etape_id: int) -> list[dict]:
    return [{"jour": JOURS[r["jour"]], "jour_n": r["jour"], "debut": r["heure_debut"], "fin": r["heure_fin"],
             "lieu": r["lieu"] or "", "groupe": r["nom"], "intervenant": r["intervenant"], "id": r["id"]}
            for r in conn.execute(
                "SELECT s.*, g.nom, p.prenom_ar || ' ' || p.nom_ar AS intervenant FROM soutien_seance s "
                "JOIN soutien_groupe g ON g.id=s.groupe_id JOIN personnel p ON p.id=g.personnel_id "
                "WHERE g.etape_id=? ORDER BY s.jour, s.heure_debut", (etape_id,))]


def _libelle_seances(ss) -> str:
    return "، ".join(f"{JOURS[s['jour']]} {s['heure_debut']}-{s['heure_fin']}" for s in ss) or "—"


# ---------- الحصيلة ----------

def _moy(v: list[float]) -> float | None:
    return round(sum(v) / len(v), 2) if v else None


def _pct(n: int, d: int) -> float | None:
    return round(n * 100 / d, 1) if d else None


def bilan_membres(ms: list[dict]) -> dict:
    av = [m["note_avant"] for m in ms if m["note_avant"] is not None]
    ap = [m["note_apres"] for m in ms if m["note_apres"] is not None]
    deux = [m for m in ms if m["note_avant"] is not None and m["note_apres"] is not None]
    return {"effectif": len(ms), "moy_avant": _moy(av), "moy_apres": _moy(ap),
            "maitrise_avant": _pct(sum(1 for x in av if x >= SEUIL), len(av)),
            "maitrise_apres": _pct(sum(1 for x in ap if x >= SEUIL), len(ap)),
            "evalues": len(deux), "ameliores": sum(1 for m in deux if m["note_apres"] > m["note_avant"]),
            "pct_ameliores": _pct(sum(1 for m in deux if m["note_apres"] > m["note_avant"]), len(deux))}


def bilan_etape(conn: sqlite3.Connection, etape_id: int) -> dict:
    """حصيلة المرحلة: لكل مجموعة ولكل فئة وللمرحلة كاملة."""
    gs = groupes(conn, etape_id)
    tous: list[dict] = []
    par_groupe = []
    for g in gs:
        ms = membres(conn, g["id"])
        tous += ms
        par_groupe.append({**g, "membres": ms, "bilan": bilan_membres(ms)})
    par_cat = []
    for cat in dict.fromkeys(g["categorie"] for g in gs):
        ms = [m for g in par_groupe if g["categorie"] == cat for m in g["membres"]]
        par_cat.append({"categorie": cat, "groupes": sum(1 for g in gs if g["categorie"] == cat),
                        "bilan": bilan_membres(ms)})
    beneficiaires = {m["inscription_id"] for m in tous}
    return {"groupes": par_groupe, "categories": par_cat, "global": bilan_membres(tous),
            "beneficiaires": len(beneficiaires), "intervenants": len({g["personnel_id"] for g in gs})}


# ---------- الوثائق ----------

def _entete(d, conn, dossier, titre: str, sous_titre: str) -> None:
    from docx.shared import Cm

    from idara.services.docs_association import para
    etab = etab_srv.lire_etablissement(conn)
    if etab and etab.logo_path and (dossier.racine / etab.logo_path).exists():
        d.add_picture(str(dossier.racine / etab.logo_path), width=Cm(17))
    elif etab:
        for l in ("المملكة المغربية", f"المديرية الإقليمية: {etab.direction_ar}", f"المؤسسة: {etab.nom_ar}"):
            para(d, l, gras=True, taille=10, apres=0)
    para(d, titre, gras=True, taille=16, centre=True, souligne=True, apres=2)
    para(d, sous_titre, taille=10, centre=True, apres=6)


def _signature(d, conn, qui: str = "توقيع المدير(ة):") -> None:
    from idara.services.docs_association import para
    etab = etab_srv.lire_etablissement(conn)
    para(d, "", apres=6)
    ville = etab.ville_redaction_ar if etab and etab.ville_redaction_ar else ""
    para(d, (f"حرر في: {ville} " if ville else "") + f"بتاريخ {tx.date_ar(datetime.now().date())}", taille=11, apres=2)
    para(d, qui, gras=True, taille=11)


def _table(d, entetes: list[str], lignes: list[list[str]], largeurs: list[float], taille=10):
    from idara.services.docs_association import _cellule, _ombre, tableau
    t = tableau(d, 1 + len(lignes), len(entetes), largeurs=largeurs)
    for j, h in enumerate(entetes):
        _cellule(t.cell(0, j), h, gras=True, taille=taille)
        _ombre(t.cell(0, j))
    for i, l in enumerate(lignes, start=1):
        for j, v in enumerate(l):
            _cellule(t.cell(i, j), v, taille=taille)
    return t


def _sauver(d, dossier: DossierDonnees, annee: str, nom: str) -> Path:
    rep = dossier.archives / annee.replace("/", "-") / "الدعم التربوي"
    rep.mkdir(parents=True, exist_ok=True)
    chemin = rep / f"{datetime.now():%Y%m%d_%H%M%S}_{nom}.docx"
    n = 1
    while chemin.exists():
        n += 1
        chemin = chemin.with_name(f"{chemin.stem}_{n}.docx")
    d.save(chemin)
    return chemin


def _periode(e) -> str:
    if e["date_debut"] and e["date_fin"]:
        return f"من {tx.date_ar(date.fromisoformat(e['date_debut']))} إلى {tx.date_ar(date.fromisoformat(e['date_fin']))}"
    return ""


def _n(v: float | None, suffixe: str = "") -> str:
    return "—" if v is None else f"{v:g}{suffixe}"


def generer_registre(conn: sqlite3.Connection, dossier: DossierDonnees, etape_id: int, personnel_id: int) -> Path:
    """سجل الدعم للأستاذ المتدخل: لكل مجموعة لائحة التلاميذ وخانات الحضور والنتائج قبل الدعم وبعده."""
    from idara.services.docs_association import _nouveau, para, saut_page
    _, annee = _annee(conn)
    e = etape(conn, etape_id)
    gs = groupes(conn, etape_id, personnel_id)
    if not gs:
        raise ErreurSoutien("لا مجموعات دعم لهذا الأستاذ في هذه المرحلة.")
    d = _nouveau(paysage=True)
    for k, g in enumerate(gs):
        if k:
            saut_page(d)
        _entete(d, conn, dossier, f"سجل الدعم التربوي: {e['nom']}", f"السنة الدراسية {annee} {_periode(e)}".strip())
        para(d, f"الأستاذ(ة) المتدخل(ة): {g['intervenant']}    المجموعة: {g['nom']}    الفئة: {g['categorie']}"
                + (f"    المادة: {g['matiere']}" if g["matiere"] else ""), gras=True, taille=11, apres=1)
        para(d, f"الحصص: {_libelle_seances(g['seances'])}    الأقسام: {'، '.join(g['classes']) or '—'}", taille=10,
             apres=4)
        ms = membres(conn, g["id"])
        entetes = ["ر.ت", "الاسم الكامل", "القسم", "قبل الدعم"] + [""] * COLONNES_REGISTRE + ["بعد الدعم",
                                                                                          "ملاحظات"]
        lignes = [[str(i), m["nom"], m["classe"] or "", _n(m["note_avant"])] + [""] * COLONNES_REGISTRE
                  + [_n(m["note_apres"]), m["observation"] or ""] for i, m in enumerate(ms, start=1)]
        lignes += [[""] * len(entetes) for _ in range(max(0, 3 - len(ms)))]
        _table(d, entetes, lignes, [0.9, 4.6, 1.8, 1.6] + [1.2] * COLONNES_REGISTRE + [1.6, 3.4], taille=9)
        para(d, "خانات الحصص: يكتب الأستاذ تاريخ الحصة في رأس الخانة ويؤشر حضور التلميذ (ح) أو غيابه (غ).",
             taille=9, apres=2)
        _signature(d, conn, "توقيع الأستاذ(ة):                                  توقيع المدير(ة):")
    p = conn.execute("SELECT nom_ar FROM personnel WHERE id=?", (personnel_id,)).fetchone()
    return _sauver(d, dossier, annee, f"سجل_الدعم_{p[0] if p else personnel_id}")


def generer_programme(conn: sqlite3.Connection, dossier: DossierDonnees, etape_id: int) -> Path:
    """برنامج الدعم للمرحلة: المجموعات والمتدخلون والأقسام، ثم استعمال الزمن."""
    from idara.services.docs_association import _nouveau, para
    _, annee = _annee(conn)
    e = etape(conn, etape_id)
    gs = groupes(conn, etape_id)
    if not gs:
        raise ErreurSoutien("لا مجموعات دعم في هذه المرحلة بعد.")
    d = _nouveau(paysage=True)
    _entete(d, conn, dossier, f"برنامج الدعم التربوي: {e['nom']}", f"السنة الدراسية {annee} {_periode(e)}".strip())
    para(d, "1. مجموعات الدعم", gras=True, taille=12, apres=2)
    _table(d, ["الفئة", "المجموعة", "الأستاذ(ة) المتدخل(ة)", "المادة", "الأقسام", "عدد التلاميذ", "الحصص"],
           [[g["categorie"], g["nom"], g["intervenant"], g["matiere"] or "—", "، ".join(g["classes"]) or "—",
             str(g["effectif"]), _libelle_seances(g["seances"])] for g in gs],
           [3.6, 3.8, 3.8, 2.4, 3.2, 1.8, 6.4])
    edt = emploi_du_temps(conn, etape_id)
    if edt:
        para(d, "", apres=4)
        para(d, "2. استعمال زمن الدعم", gras=True, taille=12, apres=2)
        _table(d, ["اليوم", "التوقيت", "المجموعة", "الأستاذ(ة)", "المكان"],
               [[s["jour"], f"{s['debut']} - {s['fin']}", s["groupe"], s["intervenant"], s["lieu"] or "—"]
                for s in edt], [3, 3.4, 6, 5, 4])
    _signature(d, conn)
    return _sauver(d, dossier, annee, f"برنامج_الدعم_{e['nom']}")


def generer_rapport(conn: sqlite3.Connection, dossier: DossierDonnees, etape_id: int,
                    graphique_png: bytes | None = None) -> Path:
    """تقرير المرحلة: الحصيلة العامة، حسب الفئة وحسب المجموعة، ومقارنة نتائج كل تلميذ قبل الدعم وبعده."""
    from docx.shared import Cm

    from idara.services.docs_association import _nouveau, para
    _, annee = _annee(conn)
    e = etape(conn, etape_id)
    b = bilan_etape(conn, etape_id)
    if not b["groupes"]:
        raise ErreurSoutien("لا مجموعات دعم في هذه المرحلة بعد.")
    d = _nouveau()
    _entete(d, conn, dossier, f"تقرير الدعم التربوي: {e['nom']}", f"السنة الدراسية {annee} {_periode(e)}".strip())
    gl = b["global"]
    para(d, "1. الحصيلة العامة", gras=True, taille=12, apres=2)
    _table(d, ["التلاميذ المستفيدون", "الأساتذة المتدخلون", "المجموعات", "المعدل قبل", "المعدل بعد",
               "نسبة التحكم قبل", "نسبة التحكم بعد", "نسبة من تحسنوا"],
           [[str(b["beneficiaires"]), str(b["intervenants"]), str(len(b["groupes"])), _n(gl["moy_avant"]),
             _n(gl["moy_apres"]), _n(gl["maitrise_avant"], "%"), _n(gl["maitrise_apres"], "%"),
             _n(gl["pct_ameliores"], "%")]], [2.2, 2.2, 1.8, 1.8, 1.8, 2.2, 2.2, 2.2], taille=9)
    para(d, f"النقط على 10؛ التحكم: نقطة {SEUIL:g}/10 فما فوق.", taille=9, apres=4)
    para(d, "2. الحصيلة حسب فئة التعثر", gras=True, taille=12, apres=2)
    _table(d, ["الفئة", "المجموعات", "التلاميذ", "المعدل قبل", "المعدل بعد", "التحكم قبل", "التحكم بعد",
               "تحسنوا"],
           [[c["categorie"], str(c["groupes"]), str(c["bilan"]["effectif"]), _n(c["bilan"]["moy_avant"]),
             _n(c["bilan"]["moy_apres"]), _n(c["bilan"]["maitrise_avant"], "%"),
             _n(c["bilan"]["maitrise_apres"], "%"), _n(c["bilan"]["pct_ameliores"], "%")] for c in b["categories"]],
           [3.6, 1.6, 1.6, 1.8, 1.8, 1.9, 1.9, 1.8], taille=9)
    if graphique_png:
        para(d, "", apres=4)
        para(d, "نسبة التحكم قبل الدعم وبعده حسب الفئة", gras=True, taille=11, centre=True, apres=2)
        d.add_picture(io.BytesIO(graphique_png), width=Cm(16))
        d.paragraphs[-1].alignment = 1
    para(d, "", apres=4)
    para(d, "3. تتبع التلاميذ: النتائج قبل الدعم وبعده", gras=True, taille=12, apres=2)
    for g in b["groupes"]:
        para(d, f"{g['nom']} · {g['intervenant']}" + (f" · {g['matiere']}" if g["matiere"] else ""), gras=True,
             taille=10, apres=1)
        if not g["membres"]:
            para(d, "لا تلاميذ في هذه المجموعة.", taille=9, apres=3)
            continue
        _table(d, ["ر.ت", "الاسم الكامل", "القسم", "قبل", "بعد", "التطور", "ملاحظات"],
               [[str(i), m["nom"], m["classe"] or "", _n(m["note_avant"]), _n(m["note_apres"]), m["evolution"],
                 m["observation"] or ""] for i, m in enumerate(g["membres"], start=1)],
               [0.9, 4.8, 1.8, 1.3, 1.3, 1.6, 4.6], taille=9)
        para(d, "", apres=3)
    _signature(d, conn)
    return _sauver(d, dossier, annee, f"تقرير_الدعم_{e['nom']}")
