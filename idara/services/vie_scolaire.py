"""الأندية التربوية والأنشطة الموازية.

- الأندية: لكل سنة دراسية، بمنشط(ة) من الأطر وأعضاء من التلاميذ وتوقيت.
- الأنشطة: البرنامج السنوي بأعمدة نموذج المدير («البرنامج السنوي للعمل التربوي والأنشطة المندمجة والأنشطة
  الموازية»: نوع النشاط، العمليات والأنشطة المبرمجة، المتدخلون فيه، المستهدفون منه، فترة الإنجاز، آليات التنفيذ)،
  ثم الإنجاز: الحالة، المشاركون (ذكور/إناث)، الحصيلة.
- الوثائق: البرنامج السنوي، وحصيلة الأنشطة المنجزة، ولائحة أعضاء نادٍ.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, fields
from datetime import date
from pathlib import Path

from idara.data.dossier import DossierDonnees
from idara.services import annee as annee_srv
from idara.services import documents as dc
from idara.services import textes as tx
from idara.services.docs_association import _cellule, _nouveau, _ombre, ajouter, para, tableau

TYPES = ("نشاط نادٍ تربوي", "نشاط موازٍ", "يوم وطني أو دولي", "مسابقة", "خرجة تربوية", "حملة تحسيسية",
         "نشاط مندمج (التفتح والتوجيه)", "نشاط مرتبط بمشروع المؤسسة")
STATUTS = {"prevue": "مبرمج", "realisee": "منجز", "annulee": "ملغى"}


class ErreurVie(ValueError):
    """رسالة موجهة للمدير بالعربية."""


def _txt(v) -> str:
    return " ".join(str(v or "").split())


def _annee(conn, annee_id: int | None = None) -> sqlite3.Row:
    if annee_id is None:
        a = annee_srv.annee_courante(conn)
        if a is None:
            raise ErreurVie("حدد السنة الدراسية الجارية أولاً (الإعدادات).")
        return a
    a = conn.execute("SELECT * FROM annee_scolaire WHERE id=?", (annee_id,)).fetchone()
    if a is None:
        raise ErreurVie("السنة الدراسية غير موجودة.")
    return a


# ---------- الأندية ----------

def enregistrer_club(conn, nom: str, animateur_id: int | None = None, objectifs: str = "", horaire: str = "",
                     club_id: int | None = None, annee_id: int | None = None) -> int:
    nom = _txt(nom)
    if not nom:
        raise ErreurVie("اسم النادي إجباري.")
    a = _annee(conn, annee_id)
    try:
        with conn:
            if club_id is None:
                return conn.execute("INSERT INTO club(annee_id, nom, animateur_id, objectifs, horaire) VALUES (?,?,?,?,?)",
                                    (a["id"], nom, animateur_id, objectifs.strip() or None, _txt(horaire) or None)).lastrowid
            conn.execute("UPDATE club SET nom=?, animateur_id=?, objectifs=?, horaire=? WHERE id=?",
                         (nom, animateur_id, objectifs.strip() or None, _txt(horaire) or None, club_id))
            return club_id
    except sqlite3.IntegrityError:
        raise ErreurVie("نادٍ بنفس الاسم موجود هذه السنة.") from None


def clubs(conn, annee_id: int | None = None) -> list[sqlite3.Row]:
    a = _annee(conn, annee_id)
    return conn.execute(
        "SELECT c.*, p.prenom_ar || ' ' || p.nom_ar AS animateur, "
        "(SELECT COUNT(*) FROM club_membre m WHERE m.club_id=c.id) AS membres, "
        "(SELECT COUNT(*) FROM activite t WHERE t.club_id=c.id AND t.statut='realisee') AS activites "
        "FROM club c LEFT JOIN personnel p ON p.id=c.animateur_id WHERE c.annee_id=? ORDER BY c.nom", (a["id"],)).fetchall()


def club(conn, club_id: int) -> sqlite3.Row:
    r = conn.execute("SELECT c.*, p.prenom_ar || ' ' || p.nom_ar AS animateur FROM club c LEFT JOIN personnel p "
                     "ON p.id=c.animateur_id WHERE c.id=?", (club_id,)).fetchone()
    if r is None:
        raise ErreurVie("النادي غير موجود.")
    return r


def supprimer_club(conn, club_id: int) -> None:
    with conn:
        conn.execute("DELETE FROM club WHERE id=?", (club_id,))


def ajouter_membre(conn, club_id: int, eleve_id: int, role: str = "") -> None:
    club(conn, club_id)
    if conn.execute("SELECT 1 FROM eleve WHERE id=?", (eleve_id,)).fetchone() is None:
        raise ErreurVie("التلميذ غير موجود.")
    with conn:
        conn.execute("INSERT INTO club_membre(club_id, eleve_id, role) VALUES (?,?,?) "
                     "ON CONFLICT(club_id, eleve_id) DO UPDATE SET role=excluded.role", (club_id, eleve_id,
                                                                                      _txt(role) or None))


def retirer_membre(conn, club_id: int, eleve_id: int) -> None:
    with conn:
        conn.execute("DELETE FROM club_membre WHERE club_id=? AND eleve_id=?", (club_id, eleve_id))


def membres(conn, club_id: int) -> list[sqlite3.Row]:
    c = club(conn, club_id)
    return conn.execute(
        "SELECT m.role, e.id, e.code_massar, e.prenom_ar, e.nom_ar, e.sexe, cl.code AS classe FROM club_membre m "
        "JOIN eleve e ON e.id=m.eleve_id LEFT JOIN inscription i ON i.eleve_id=e.id AND i.annee_id=? "
        "LEFT JOIN classe cl ON cl.id=i.classe_id WHERE m.club_id=? ORDER BY cl.code, e.nom_ar, e.prenom_ar",
        (c["annee_id"], club_id)).fetchall()


# ---------- الأنشطة ----------

@dataclass
class Activite:
    type: str
    titre: str
    club_id: int | None = None
    intervenants: str = ""
    cibles: str = ""
    periode: str = ""
    date_debut: str = ""
    date_fin: str = ""
    mecanismes: str = ""
    statut: str = "prevue"
    nb_garcons: int | str | None = None
    nb_filles: int | str | None = None
    bilan: str = ""
    id: int | None = None


def _entier(v, lib: str) -> int | None:
    if v in (None, ""):
        return None
    try:
        n = int(str(v).strip())
    except ValueError:
        raise ErreurVie(f"{lib}: عدد صحيح.") from None
    if n < 0:
        raise ErreurVie(f"{lib}: لا يكون سالباً.")
    return n


def enregistrer_activite(conn, a: Activite, annee_id: int | None = None) -> int:
    an = _annee(conn, annee_id)
    if a.type not in TYPES:
        raise ErreurVie("نوع النشاط غير معروف.")
    if not _txt(a.titre):
        raise ErreurVie("النشاط (العمليات والأنشطة المبرمجة) إجباري.")
    if a.statut not in STATUTS:
        raise ErreurVie("حالة النشاط غير صحيحة.")
    for lib, d in (("تاريخ البداية", a.date_debut), ("تاريخ النهاية", a.date_fin)):
        if d:
            try:
                date.fromisoformat(d)
            except ValueError:
                raise ErreurVie(f"{lib} غير صحيح.") from None
    if a.date_debut and a.date_fin and a.date_fin < a.date_debut:
        raise ErreurVie("تاريخ النهاية قبل تاريخ البداية.")
    if not (_txt(a.periode) or a.date_debut):
        raise ErreurVie("حدد فترة الإنجاز (نصاً مثل «شهر أكتوبر» أو تاريخاً).")
    g, f = _entier(a.nb_garcons, "عدد الذكور"), _entier(a.nb_filles, "عدد الإناث")
    if a.statut == "realisee":
        if not a.date_debut:
            raise ErreurVie("النشاط المنجز: تاريخ الإنجاز إجباري.")
        if g is None or f is None:
            raise ErreurVie("النشاط المنجز: عدد المشاركين (ذكور وإناث) إجباري.")
    if a.club_id is not None:
        club(conn, a.club_id)
    vals = (a.type, _txt(a.titre), a.club_id, _txt(a.intervenants) or None, _txt(a.cibles) or None,
            _txt(a.periode) or None, a.date_debut or None, a.date_fin or None, _txt(a.mecanismes) or None, a.statut,
            g, f, (a.bilan or "").strip() or None)
    cols = "type, titre, club_id, intervenants, cibles, periode, date_debut, date_fin, mecanismes, statut, nb_garcons, " \
           "nb_filles, bilan"
    with conn:
        if a.id is None:
            a.id = conn.execute(f"INSERT INTO activite(annee_id, {cols}) VALUES (?,{','.join('?' * 13)})",
                                (an["id"], *vals)).lastrowid
        else:
            conn.execute("UPDATE activite SET " + ", ".join(f"{c.strip()}=?" for c in cols.split(",")) + " WHERE id=?",
                         (*vals, a.id))
    return a.id


def activite(conn, aid: int) -> Activite:
    r = conn.execute("SELECT * FROM activite WHERE id=?", (aid,)).fetchone()
    if r is None:
        raise ErreurVie("النشاط غير موجود.")
    return Activite(**{f.name: (r[f.name] if r[f.name] is not None else ("" if f.name not in
                                                                          ("club_id", "nb_garcons", "nb_filles", "id")
                                                                          else None)) for f in fields(Activite)})


def activites(conn, annee_id: int | None = None, statut: str | None = None, club_id: int | None = None) -> list[sqlite3.Row]:
    an = _annee(conn, annee_id)
    sql = "SELECT t.*, c.nom AS club FROM activite t LEFT JOIN club c ON c.id=t.club_id WHERE t.annee_id=?"
    args: list = [an["id"]]
    if statut:
        sql += " AND t.statut=?"
        args.append(statut)
    if club_id:
        sql += " AND t.club_id=?"
        args.append(club_id)
    return conn.execute(sql + " ORDER BY COALESCE(t.date_debut, '9999'), t.id", args).fetchall()


def supprimer_activite(conn, aid: int) -> None:
    with conn:
        conn.execute("DELETE FROM activite WHERE id=?", (aid,))


def bilan(conn, annee_id: int | None = None) -> dict:
    """مؤشرات الحياة المدرسية: الأنشطة المبرمجة والمنجزة، المشاركون، الأندية وأعضاؤها."""
    ts = activites(conn, annee_id)
    real = [t for t in ts if t["statut"] == "realisee"]
    cs = clubs(conn, annee_id)
    par_type = {}
    for t in real:
        par_type[t["type"]] = par_type.get(t["type"], 0) + 1
    return {"programmees": len([t for t in ts if t["statut"] != "annulee"]), "realisees": len(real),
            "annulees": len([t for t in ts if t["statut"] == "annulee"]),
            "taux": round(len(real) / len([t for t in ts if t["statut"] != "annulee"]) * 100, 2)
            if any(t["statut"] != "annulee" for t in ts) else None,
            "garcons": sum(t["nb_garcons"] or 0 for t in real), "filles": sum(t["nb_filles"] or 0 for t in real),
            "par_type": par_type, "clubs": len(cs), "membres": sum(c["membres"] for c in cs)}


# ---------- الوثائق ----------

def _entete(conn, d, titre: str, sous: str) -> dict:
    try:
        c = dc.champs_communs(conn)
    except dc.ErreurDocument as e:
        raise ErreurVie(str(e)) from None
    para(d, f"المؤسسة: {c['etablissement']}", gras=True, taille=13, apres=0)
    para(d, titre, gras=True, taille=20, centre=True, apres=0)
    para(d, sous, centre=True, taille=14, apres=8)
    return c


def _enregistrer(d, dossier: DossierDonnees, annee: str, nom: str) -> Path:
    rep = dossier.archives / annee.replace("/", "-") / "الحياة المدرسية"
    rep.mkdir(parents=True, exist_ok=True)
    from datetime import datetime
    chemin = rep / f"{datetime.now():%Y%m%d_%H%M%S}_{nom}.docx"
    d.save(chemin)
    return chemin


def _paysage(d) -> None:
    from docx.enum.section import WD_ORIENT
    from docx.shared import Cm
    s = d.sections[0]
    s.orientation = WD_ORIENT.LANDSCAPE
    s.page_width, s.page_height = Cm(29.7), Cm(21)


def generer_programme(conn, dossier: DossierDonnees, annee_id: int | None = None) -> Path:
    """البرنامج السنوي للأنشطة بأعمدة نموذج المدير، مجمعاً حسب نوع النشاط."""
    an = _annee(conn, annee_id)
    ts = [t for t in activites(conn, an["id"]) if t["statut"] != "annulee"]
    if not ts:
        raise ErreurVie("لا أنشطة مبرمجة هذه السنة.")
    d = _nouveau()
    _paysage(d)
    c = _entete(conn, d, "البرنامج السنوي للعمل التربوي والأنشطة المندمجة والأنشطة الموازية",
                f"الموسم الدراسي {an['libelle']}")
    larg = [3.6, 6.6, 4.0, 3.8, 3.2, 4.4]
    t = tableau(d, 1 + len(ts), 6, largeurs=larg)
    for j, lib in enumerate(("نوع النشاط", "العمليات والأنشطة المبرمجة", "المتدخلون فيه", "المستهدفون منه",
                             "فترة الإنجاز", "آليات التنفيذ")):
        _cellule(t.cell(0, j), lib, gras=True, taille=13)
        _ombre(t.cell(0, j))
    for i, a in enumerate(ts, start=1):
        periode = a["periode"] or ""
        if a["date_debut"]:
            dd = tx.date_chiffres(a["date_debut"]) + (f" — {tx.date_chiffres(a['date_fin'])}" if a["date_fin"] else "")
            periode = f"{periode} ({dd})" if periode else dd
        type_ = a["type"] + (f": {a['club']}" if a["club"] else "")
        for j, v in enumerate((type_, a["titre"], a["intervenants"] or "", a["cibles"] or "", periode,
                               a["mecanismes"] or "")):
            _cellule(t.cell(i, j), v, taille=12, centre=j in (0, 4))
    para(d, apres=10)
    para(d, f"{c['mudir_moassasa']}", gras=True, centre=True)
    return _enregistrer(d, dossier, an["libelle"], "البرنامج السنوي للأنشطة")


def generer_bilan(conn, dossier: DossierDonnees, annee_id: int | None = None) -> Path:
    """حصيلة الأنشطة المنجزة مع أعداد المشاركين، ومؤشرات إجمالية."""
    an = _annee(conn, annee_id)
    ts = activites(conn, an["id"], "realisee")
    if not ts:
        raise ErreurVie("لا أنشطة منجزة مسجلة هذه السنة.")
    b = bilan(conn, an["id"])
    d = _nouveau()
    _paysage(d)
    c = _entete(conn, d, "حصيلة الأنشطة التربوية والموازية", f"الموسم الدراسي {an['libelle']}")
    p = para(d, apres=6)
    ajouter(p, "المؤشرات: ", gras=True)
    ajouter(p, f"الأنشطة المبرمجة {b['programmees']}، المنجزة {b['realisees']}"
               + (f" (نسبة الإنجاز {b['taux']:.2f}%)" if b["taux"] is not None else "")
               + f"، المشاركون {b['garcons'] + b['filles']} (ذكور {b['garcons']}، إناث {b['filles']})، "
                 f"الأندية {b['clubs']} بـ{b['membres']} عضواً.")
    t = tableau(d, 1 + len(ts), 7, largeurs=[2.6, 3.6, 6.2, 3.2, 1.6, 1.6, 6.8])
    for j, lib in enumerate(("التاريخ", "نوع النشاط", "النشاط", "المتدخلون", "ذكور", "إناث", "الحصيلة والملاحظات")):
        _cellule(t.cell(0, j), lib, gras=True, taille=13)
        _ombre(t.cell(0, j))
    for i, a in enumerate(ts, start=1):
        dd = tx.date_chiffres(a["date_debut"]) + (f" — {tx.date_chiffres(a['date_fin'])}" if a["date_fin"] else "")
        for j, v in enumerate((dd, a["type"] + (f": {a['club']}" if a["club"] else ""), a["titre"],
                               a["intervenants"] or "", str(a["nb_garcons"]), str(a["nb_filles"]), a["bilan"] or "")):
            _cellule(t.cell(i, j), v, taille=12, centre=j in (0, 4, 5))
    para(d, apres=10)
    para(d, f"{c['mudir_moassasa']}", gras=True, centre=True)
    return _enregistrer(d, dossier, an["libelle"], "حصيلة الأنشطة")


def generer_liste_club(conn, dossier: DossierDonnees, club_id: int) -> Path:
    c = club(conn, club_id)
    ms = membres(conn, club_id)
    if not ms:
        raise ErreurVie("لا أعضاء في النادي بعد.")
    an = _annee(conn, c["annee_id"])
    d = _nouveau()
    _entete(conn, d, c["nom"], f"لائحة الأعضاء — الموسم الدراسي {an['libelle']}")
    for lib, v in (("المنشط(ة): ", c["animateur"] or "—"), ("التوقيت: ", c["horaire"] or "—")):
        p = para(d, apres=0)
        ajouter(p, lib, gras=True)
        ajouter(p, v)
    if c["objectifs"]:
        p = para(d, apres=4)
        ajouter(p, "الأهداف: ", gras=True)
        ajouter(p, c["objectifs"])
    para(d, apres=4)
    t = tableau(d, 1 + len(ms), 5, largeurs=[1.4, 3.2, 6.6, 2.6, 3.6])
    for j, lib in enumerate(("ر.ت", "رمز مسار", "الاسم الكامل", "القسم", "المهمة")):
        _cellule(t.cell(0, j), lib, gras=True, taille=13)
        _ombre(t.cell(0, j))
    for i, m in enumerate(ms, start=1):
        for j, v in enumerate((f"{i:02d}", m["code_massar"] or "", f"{m['prenom_ar']} {m['nom_ar']}",
                               (m["classe"] or "").replace("-", ""), m["role"] or "عضو(ة)")):
            _cellule(t.cell(i, j), v, taille=12, centre=j != 2)
    para(d, apres=10)
    tb = tableau(d, 1, 2, bordures=False, largeurs=[8.7, 8.7])
    _cellule(tb.cell(0, 0), "توقيع المنشط(ة)", gras=True)
    _cellule(tb.cell(0, 1), "توقيع المدير(ة)", gras=True)
    return _enregistrer(d, dossier, an["libelle"], f"لائحة أعضاء {c['nom']}")
