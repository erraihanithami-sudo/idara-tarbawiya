"""التلاميذ ما قبل مسار: تسجيلهم برقم السجل العام، والشهادة المدرسية بكل حقول النموذج.

يُنشأ التلميذ عند أول طلب شهادة، ويبقى في القاعدة لتيسير إعادة الطباعة.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date

from idara.data.dossier import DossierDonnees
from idara.services import documents as dc
from idara.services import eleves as el

NIVEAUX_ANCIENS = ["الأول", "الثاني", "الثالث", "الرابع", "الخامس", "السادس"]


class ErreurAncien(ValueError):
    """رسالة موجهة للمدير بالعربية."""


@dataclass
class Ancien:
    num_registre: str = ""
    nom_ar: str = ""
    prenom_ar: str = ""
    sexe: str = ""
    date_naissance: str = ""      # YYYY-MM-DD
    date_naissance_approx: bool = False
    lieu_ar: str = ""
    date_entree: str = ""
    date_sortie: str = ""
    dernier_niveau: str = ""
    num_cahier_registre: str = ""
    id: int | None = None
    erreurs: list[str] = field(default_factory=list)

    def valider(self) -> None:
        """كل حقول الشهادة إجبارية."""
        for k in ("num_registre", "nom_ar", "prenom_ar", "lieu_ar", "dernier_niveau"):
            setattr(self, k, " ".join(str(getattr(self, k)).split()))
        manquants = [lib for k, lib in [
            ("num_registre", "رقم التسجيل في السجل العام"), ("nom_ar", "النسب"), ("prenom_ar", "الاسم"),
            ("sexe", "النوع"), ("date_naissance", "تاريخ الازدياد"), ("lieu_ar", "مكان الازدياد"),
            ("date_entree", "تاريخ الالتحاق"), ("date_sortie", "تاريخ الانقطاع"),
            ("dernier_niveau", "آخر قسم درس به")] if not getattr(self, k)]
        if manquants:
            raise ErreurAncien("حقول إجبارية فارغة: " + "، ".join(manquants))
        if not self.num_registre.isdigit() or int(self.num_registre) <= 0:
            raise ErreurAncien("رقم التسجيل في السجل العام يتكون من أرقام فقط.")
        if self.sexe not in ("M", "F"):
            raise ErreurAncien("النوع غير صحيح.")
        try:
            n, e, s = (date.fromisoformat(x) for x in (self.date_naissance, self.date_entree, self.date_sortie))
        except ValueError as ex:
            raise ErreurAncien("أحد التواريخ غير صحيح.") from ex
        if not (n < e <= s <= date.today()):
            raise ErreurAncien("التواريخ غير منطقية: الازدياد قبل الالتحاق، والالتحاق قبل الانقطاع، "
                               "والانقطاع ليس في المستقبل.")


def lire(conn: sqlite3.Connection, eleve_id: int) -> Ancien:
    r = conn.execute(
        "SELECT e.*, l.nom_ar AS lieu_ar, a.date_entree, a.date_sortie, a.dernier_niveau "
        "FROM eleve e LEFT JOIN lieu l ON l.id=e.lieu_naissance_id "
        "LEFT JOIN eleve_avant_massar a ON a.eleve_id=e.id WHERE e.id=?", (eleve_id,)).fetchone()
    if r is None:
        raise ErreurAncien("التلميذ غير موجود.")
    return Ancien(str(r["num_registre"] or ""), r["nom_ar"], r["prenom_ar"], r["sexe"] or "",
                  r["date_naissance"] or "", bool(r["date_naissance_approx"]), r["lieu_ar"] or "",
                  r["date_entree"] or "", r["date_sortie"] or "", r["dernier_niveau"] or "",
                  r["num_cahier_registre"] or "", r["id"])


def par_numero(conn: sqlite3.Connection, num_registre: str) -> Ancien | None:
    r = conn.execute("SELECT id FROM eleve WHERE num_registre=?", (num_registre.strip(),)).fetchone() \
        if num_registre.strip().isdigit() else None
    return lire(conn, r["id"]) if r else None


def enregistrer(conn: sqlite3.Connection, a: Ancien) -> int:
    """ينشئ التلميذ القديم أو يحدّثه. رقم السجل فريد."""
    a.valider()
    num = int(a.num_registre)
    autre = conn.execute("SELECT id, source FROM eleve WHERE num_registre=?", (num,)).fetchone()
    if autre and autre["id"] != a.id:
        raise ErreurAncien(f"رقم التسجيل {num} مسجل لتلميذ آخر. ابحث عنه بهذا الرقم.")
    with conn:
        lid = el.lieu_id(conn, a.lieu_ar)
        valeurs = (num, a.num_cahier_registre or None, a.nom_ar, a.prenom_ar, a.sexe, a.date_naissance,
                   int(a.date_naissance_approx), lid)
        if a.id is None:
            a.id = conn.execute(
                "INSERT INTO eleve(num_registre, num_cahier_registre, nom_ar, prenom_ar, sexe, date_naissance,"
                " date_naissance_approx, lieu_naissance_id, source) VALUES (?,?,?,?,?,?,?,?,'avant_massar')",
                valeurs).lastrowid
        else:
            conn.execute(
                "UPDATE eleve SET num_registre=?, num_cahier_registre=?, nom_ar=?, prenom_ar=?, sexe=?,"
                " date_naissance=?, date_naissance_approx=?, lieu_naissance_id=?,"
                " modifie_le=datetime('now','localtime') WHERE id=?", (*valeurs, a.id))
        conn.execute(
            "INSERT INTO eleve_avant_massar(eleve_id, date_entree, date_sortie, dernier_niveau) VALUES (?,?,?,?) "
            "ON CONFLICT(eleve_id) DO UPDATE SET date_entree=excluded.date_entree, "
            "date_sortie=excluded.date_sortie, dernier_niveau=excluded.dernier_niveau",
            (a.id, a.date_entree, a.date_sortie, a.dernier_niveau))
        conn.execute("INSERT INTO journal(action, cible, cible_id, details) VALUES ('enregistrement','ancien',?,?)",
                     (a.id, f"{num} {a.prenom_ar} {a.nom_ar}"))
    return a.id


def generer_certificat(conn: sqlite3.Connection, dossier: DossierDonnees, eleve_id: int,
                       destinataire_nom: str, destinataire_cin: str,
                       le: date | None = None) -> dc.DocumentGenere:
    a = lire(conn, eleve_id)
    a.valider()
    donnees = {"nom_ar": a.nom_ar, "prenom_ar": a.prenom_ar, "sexe": a.sexe,
               "date_naissance": a.date_naissance, "lieu_ar": a.lieu_ar, "num_registre": a.num_registre,
               "date_entree": a.date_entree, "date_sortie": a.date_sortie, "dernier_niveau": a.dernier_niveau}
    v = dc.champs_certificat_ancien(conn, donnees, destinataire_nom, destinataire_cin.upper(), le)
    return dc.generer(conn, dossier, "certificat_scolarite_ancien", v, eleve_id=eleve_id,
                      destinataire_nom=v["destinataire_nom"], destinataire_cin=v["destinataire_cin"],
                      libelle=f"{a.prenom_ar} {a.nom_ar} ({a.num_registre})")


def remises(conn: sqlite3.Connection, eleve_id: int) -> list[sqlite3.Row]:
    """سجل تسليم الشهادات لهذا التلميذ."""
    return conn.execute(
        "SELECT d.id, d.date_generation, d.destinataire_nom, d.destinataire_cin, d.fichier_archive "
        "FROM document_genere d JOIN modele_document m ON m.id=d.modele_id "
        "WHERE d.eleve_id=? AND m.code='certificat_scolarite_ancien' ORDER BY d.id DESC", (eleve_id,)).fetchall()
