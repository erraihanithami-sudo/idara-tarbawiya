"""ملف الموظفين: الإدخال مرة واحدة، ومنه تُملأ وثائق الرخص ومحضر الاستئناف ومحضر التسليم.

المدير موظف كباقي الموظفين، لكن تعيينه وتغييره يمرّان عبر «إعداد المؤسسة» (سجل المديرين المتعاقبين).
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field, fields
from datetime import date

from idara.services import annee as annee_srv
from idara.services import textes as tx
from idara.services.massar import niveaux_du_code_classe, normaliser

CATEGORIES = {"enseignant": ("أستاذ", "أستاذة", "الأساتذة"),
              "educatrice": ("مربي التعليم الأولي", "مربية التعليم الأولي", "المربيات والمربون"),
              "gardien": ("حارس", "حارسة", "الحراس"),
              "proprete": ("عون نظافة", "عونة نظافة", "أعوان النظافة"),
              "autre": ("موظف", "موظفة", "آخرون"),
              "directeur": ("المدير", "المديرة", "الإدارة")}
STATUTS = {"actif": "في العمل", "retraite": "متقاعد(ة)", "mute": "منتقل(ة)", "autre": "مغادر(ة) لسبب آخر"}
# الحقول ذات القيم المتكررة: تُقترح من القيم المدخلة سابقاً (لا قوائم رسمية مفترضة)
CHAMPS_SUGGERES = ("cadre", "grade", "fonction", "cycle", "matiere")

_CIN = re.compile(r"^[A-Z]{1,2}[0-9]{1,8}$")
_TEL = re.compile(r"^(\+212|0)[5-7][0-9]{8}$")


class ErreurPersonnel(ValueError):
    """رسالة موجهة للمدير بالعربية."""


def libelle_categorie(categorie: str, sexe: str = "M") -> str:
    m, f, _ = CATEGORIES.get(categorie, CATEGORIES["autre"])
    return f if sexe == "F" else m


@dataclass
class Personnel:
    nom_ar: str = ""
    prenom_ar: str = ""
    sexe: str = ""
    categorie: str = "enseignant"
    nom_fr: str = ""
    prenom_fr: str = ""
    ppr: str = ""
    cin: str = ""
    cadre: str = ""
    grade: str = ""
    fonction: str = ""
    cycle: str = ""
    matiere: str = ""
    niveau_enseigne: str = ""
    nb_eleves: int | None = None
    heures_hebdo: int | None = None
    adresse: str = ""
    telephone: str = ""
    unite: str = ""
    date_affectation: str = ""
    statut: str = "actif"
    date_depart: str = ""
    dossier_disponible: bool = False
    remarques: str = ""
    id: int | None = None
    classes: list[int] = field(default_factory=list)   # أقسام السنة الجارية

    def nettoyer(self) -> None:
        for f in fields(self):
            v = getattr(self, f.name)
            if isinstance(v, str):
                setattr(self, f.name, " ".join(v.split()))
        self.ppr = self.ppr.replace(" ", "")
        self.cin = self.cin.replace(" ", "").upper()
        self.telephone = re.sub(r"[\s.\-]", "", self.telephone)

    def valider(self) -> None:
        self.nettoyer()
        manquants = [lib for k, lib in (("nom_ar", "النسب"), ("prenom_ar", "الاسم"), ("sexe", "النوع"))
                     if not getattr(self, k)]
        if manquants:
            raise ErreurPersonnel("حقول إجبارية فارغة: " + "، ".join(manquants))
        if self.sexe not in ("M", "F"):
            raise ErreurPersonnel("النوع غير صحيح.")
        if self.categorie not in CATEGORIES:
            raise ErreurPersonnel("الفئة غير صحيحة.")
        if self.ppr and not self.ppr.isdigit():
            raise ErreurPersonnel("رقم التأجير يتكون من أرقام فقط.")
        if self.cin and not _CIN.match(self.cin):
            raise ErreurPersonnel("رقم البطاقة الوطنية غير صحيح (حرف أو حرفان ثم أرقام، مثال: AB123456).")
        if self.telephone and not _TEL.match(self.telephone):
            raise ErreurPersonnel("رقم الهاتف غير صحيح (مثال: 0612345678).")
        for k, lib in (("nb_eleves", "عدد التلاميذ"), ("heures_hebdo", "ساعات العمل")):
            v = getattr(self, k)
            if v in ("", None):
                setattr(self, k, None)
                continue
            try:
                v = int(v)
            except (TypeError, ValueError):
                raise ErreurPersonnel(f"{lib}: عدد صحيح فقط.") from None
            if v < 0 or (k == "heures_hebdo" and v > 60):
                raise ErreurPersonnel(f"{lib}: قيمة غير معقولة.")
            setattr(self, k, v)
        for k, lib in (("date_affectation", "تاريخ التعيين بالمؤسسة"), ("date_depart", "تاريخ المغادرة")):
            v = getattr(self, k)
            if v:
                try:
                    d = date.fromisoformat(v)
                except ValueError:
                    raise ErreurPersonnel(f"{lib} غير صحيح.") from None
                if d > date.today() and k == "date_affectation":
                    raise ErreurPersonnel(f"{lib} في المستقبل.")
        if self.statut not in STATUTS:
            raise ErreurPersonnel("الوضعية غير صحيحة.")
        if self.statut != "actif" and not self.date_depart:
            raise ErreurPersonnel("تاريخ المغادرة إجباري للموظف غير العامل.")
        if self.date_depart and self.date_affectation and self.date_depart < self.date_affectation:
            raise ErreurPersonnel("تاريخ المغادرة قبل تاريخ التعيين.")


# ---------- القراءة ----------

def _annee_id(conn) -> int:
    a = annee_srv.annee_courante(conn)
    return a["id"] if a else -1


def _ligne_vers(conn, r: sqlite3.Row) -> Personnel:
    p = Personnel()
    for f in fields(p):
        if f.name in r.keys():
            v = r[f.name]
            setattr(p, f.name, ("" if v is None else v) if f.type in ("str", str) else v)
    p.dossier_disponible = bool(r["dossier_disponible"])
    p.unite = r["unite"] or ""
    p.classes = [c[0] for c in conn.execute(
        "SELECT a.classe_id FROM affectation_classe a JOIN classe c ON c.id=a.classe_id "
        "WHERE a.personnel_id=? AND c.annee_id=? ORDER BY c.code", (p.id, _annee_id(conn)))]
    return p


_SELECT = ("SELECT p.*, u.nom_ar AS unite FROM personnel p "
           "LEFT JOIN unite_scolaire u ON u.id = p.unite_id")


def lire(conn: sqlite3.Connection, pid: int) -> Personnel:
    r = conn.execute(_SELECT + " WHERE p.id=?", (pid,)).fetchone()
    if r is None:
        raise ErreurPersonnel("الموظف غير موجود.")
    return _ligne_vers(conn, r)


_ORDRE_CAT = {c: i for i, c in enumerate(("directeur", "enseignant", "educatrice", "gardien", "proprete", "autre"))}


def lister(conn: sqlite3.Connection, texte: str = "", categorie: str | None = None,
           actifs_seulement: bool = True) -> list[Personnel]:
    """بالاسم أو النسب (عربي/فرنسي، بأي ترتيب)، أو برقم التأجير أو البطاقة الوطنية."""
    lignes = conn.execute(_SELECT).fetchall()
    cible = normaliser(texte)
    res = []
    for r in lignes:
        if actifs_seulement and r["statut"] != "actif":
            continue
        if categorie and r["categorie"] != categorie:
            continue
        if cible:
            noms = [f"{r['nom_ar']}{r['prenom_ar']}", f"{r['prenom_ar']}{r['nom_ar']}",
                    f"{r['nom_fr'] or ''}{r['prenom_fr'] or ''}", f"{r['prenom_fr'] or ''}{r['nom_fr'] or ''}",
                    r["ppr"] or "", r["cin"] or ""]
            if not any(cible in normaliser(n) for n in noms if n):
                continue
        res.append(_ligne_vers(conn, r))
    res.sort(key=lambda p: (p.statut != "actif", _ORDRE_CAT[p.categorie], p.nom_ar, p.prenom_ar))
    return res


def suggestions(conn: sqlite3.Connection, champ: str) -> list[str]:
    if champ not in CHAMPS_SUGGERES:
        raise ValueError(champ)
    return [r[0] for r in conn.execute(
        f"SELECT {champ}, COUNT(*) n FROM personnel WHERE {champ} IS NOT NULL AND {champ} != '' "
        f"GROUP BY {champ} ORDER BY n DESC, {champ}")]


def classes_annee(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """أقسام السنة الجارية مع عدد تلاميذها الحاضرين (مسجل أو وافد)."""
    return conn.execute(
        "SELECT c.id, c.code, (SELECT COUNT(*) FROM inscription i WHERE i.classe_id=c.id "
        "AND i.statut IN ('inscrit','arrive')) AS effectif, "
        "(SELECT GROUP_CONCAT(p.prenom_ar || ' ' || p.nom_ar, '، ') FROM affectation_classe a "
        " JOIN personnel p ON p.id=a.personnel_id WHERE a.classe_id=c.id AND p.statut='actif') AS enseignants "
        "FROM classe c WHERE c.annee_id=? ORDER BY c.code", (_annee_id(conn),)).fetchall()


def enseignement(conn: sqlite3.Connection, p: Personnel) -> dict:
    """مستوى التدريس وعدد التلاميذ: من الأقسام المسندة إن وُجدت، وإلا من الإدخال اليدوي."""
    if p.classes:
        marques = ",".join("?" * len(p.classes))
        lignes = conn.execute(
            f"SELECT c.code, (SELECT COUNT(*) FROM inscription i WHERE i.classe_id=c.id "
            f"AND i.statut IN ('inscrit','arrive')) AS n FROM classe c WHERE c.id IN ({marques})",
            p.classes).fetchall()
        niveaux = []
        for r in lignes:
            for n in niveaux_du_code_classe(r["code"]):
                if n not in niveaux:
                    niveaux.append(n)
        ordre = list(tx.NIVEAUX)
        niveaux.sort(key=ordre.index)
        return {"niveau": "، ".join(tx.niveau_ar(n) for n in niveaux) or p.niveau_enseigne,
                "nb_eleves": sum(r["n"] for r in lignes),
                "classes": [r["code"] for r in lignes], "source": "أقسام"}
    return {"niveau": p.niveau_enseigne, "nb_eleves": p.nb_eleves, "classes": [], "source": "يدوي"}


# البيانات التي تطلبها وثائق الرخص ومحضر الاستئناف (حسب نماذج المدير)
_REQUIS_RH = (("ppr", "رقم التأجير"), ("cin", "رقم البطاقة الوطنية"), ("cadre", "الإطار"),
              ("grade", "الدرجة"), ("fonction", "المهمة"), ("adresse", "العنوان الشخصي"),
              ("telephone", "الهاتف"))
_REQUIS_ENSEIGNANT = (("cycle", "السلك"), ("matiere", "مادة التدريس"), ("heures_hebdo", "ساعات العمل"))


def manquants_documents(conn: sqlite3.Connection, p: Personnel) -> list[str]:
    """ما ينقص الملف لتوليد وثائق الرخص دون نقط فارغة."""
    requis = list(_REQUIS_RH)
    if p.categorie in ("enseignant", "educatrice"):
        requis += _REQUIS_ENSEIGNANT
    res = [lib for k, lib in requis if getattr(p, k) in ("", None)]
    if p.categorie in ("enseignant", "educatrice"):
        e = enseignement(conn, p)
        if not e["niveau"]:
            res.append("مستوى التدريس (أو إسناد قسم)")
        if e["nb_eleves"] in (None, ""):
            res.append("عدد التلاميذ (أو إسناد قسم)")
    return res


def effectifs(conn: sqlite3.Connection) -> dict[str, int]:
    """البنية البشرية (محضر التسليم): عدد العاملين حسب الفئة."""
    d = {c: 0 for c in CATEGORIES}
    for r in conn.execute("SELECT categorie, COUNT(*) FROM personnel WHERE statut='actif' GROUP BY categorie"):
        d[r[0]] = r[1]
    return d


# ---------- الكتابة ----------

def _unite_id(conn, nom: str) -> int | None:
    if not nom:
        return None
    r = conn.execute("SELECT id FROM unite_scolaire WHERE nom_ar=?", (nom,)).fetchone()
    if r is None:
        raise ErreurPersonnel(f"الوحدة المدرسية «{nom}» غير موجودة في إعداد المؤسسة.")
    return r[0]


_COLONNES = ("nom_ar", "prenom_ar", "nom_fr", "prenom_fr", "sexe", "categorie", "ppr", "cin", "cadre",
             "grade", "fonction", "cycle", "matiere", "niveau_enseigne", "nb_eleves", "heures_hebdo",
             "adresse", "telephone", "date_affectation", "statut", "date_depart", "remarques")


def enregistrer(conn: sqlite3.Connection, p: Personnel) -> int:
    """ينشئ الموظف أو يحدّثه، ويسند أقسامه في السنة الجارية."""
    p.valider()
    ancien = conn.execute("SELECT categorie FROM personnel WHERE id=?", (p.id,)).fetchone() if p.id else None
    if p.id and ancien is None:
        raise ErreurPersonnel("الموظف غير موجود.")
    if bool(ancien and ancien["categorie"] == "directeur") != (p.categorie == "directeur"):
        raise ErreurPersonnel("المدير يُعيَّن ويُغيَّر من صفحة «إعداد المؤسسة».")
    if ancien and ancien["categorie"] == "directeur" and p.statut != "actif":
        raise ErreurPersonnel("مغادرة المدير تُسجَّل بتعيين مدير جديد من صفحة «إعداد المؤسسة».")
    for k, lib in (("ppr", "رقم التأجير"), ("cin", "رقم البطاقة الوطنية")):
        v = getattr(p, k)
        if v and conn.execute(f"SELECT 1 FROM personnel WHERE {k}=? AND id IS NOT ?", (v, p.id)).fetchone():
            raise ErreurPersonnel(f"{lib} {v} مسجل لموظف آخر.")
    valeurs = [getattr(p, k) if getattr(p, k) not in ("",) else None for k in _COLONNES]
    valeurs[_COLONNES.index("statut")] = p.statut
    unite = _unite_id(conn, p.unite)
    annee = _annee_id(conn)
    if p.classes:
        valides = {r[0] for r in conn.execute("SELECT id FROM classe WHERE annee_id=?", (annee,))}
        if not set(p.classes) <= valides:
            raise ErreurPersonnel("قسم غير موجود في السنة الجارية.")
    with conn:
        if p.id is None:
            cols = ", ".join(_COLONNES)
            p.id = conn.execute(
                f"INSERT INTO personnel({cols}, unite_id, dossier_disponible) VALUES "
                f"({', '.join('?' * len(_COLONNES))}, ?, ?)",
                (*valeurs, unite, int(p.dossier_disponible))).lastrowid
            action = "ajout"
        else:
            sets = ", ".join(f"{k}=?" for k in _COLONNES)
            conn.execute(f"UPDATE personnel SET {sets}, unite_id=?, dossier_disponible=? WHERE id=?",
                         (*valeurs, unite, int(p.dossier_disponible), p.id))
            action = "modification"
        conn.execute("DELETE FROM affectation_classe WHERE personnel_id=? AND classe_id IN "
                     "(SELECT id FROM classe WHERE annee_id=?)", (p.id, annee))
        if p.statut == "actif":
            conn.executemany("INSERT INTO affectation_classe(personnel_id, classe_id) VALUES (?,?)",
                             [(p.id, c) for c in p.classes])
        conn.execute("INSERT INTO journal(action, cible, cible_id, details) VALUES (?, 'personnel', ?, ?)",
                     (action, p.id, f"{p.prenom_ar} {p.nom_ar}"))
    return p.id


def depart(conn: sqlite3.Connection, pid: int, statut: str, le: str, remarque: str = "") -> None:
    """تقاعد أو انتقال: الملف يبقى (لا حذف)، وتُرفع أقسام السنة الجارية."""
    p = lire(conn, pid)
    if statut == "actif":
        raise ErreurPersonnel("اختر وضعية المغادرة.")
    p.statut, p.date_depart = statut, le
    if remarque:
        p.remarques = f"{p.remarques}\n{remarque}".strip()
    p.classes = []
    enregistrer(conn, p)


def reintegrer(conn: sqlite3.Connection, pid: int) -> None:
    p = lire(conn, pid)
    p.statut, p.date_depart = "actif", ""
    enregistrer(conn, p)
