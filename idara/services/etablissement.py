"""إعداد المؤسسة والمدير والهوية البصرية."""

from __future__ import annotations

import shutil
import sqlite3
from dataclasses import dataclass, field, asdict
from datetime import date
from pathlib import Path

from idara.data.dossier import DossierDonnees
from idara.data.journal import journaliser
from idara.services import annee as annee_srv

TYPES = {"independant": "مؤسسة مستقلة", "groupe": "مجموعة مدرسية"}
EXTENSIONS_IMAGES = {".png", ".jpg", ".jpeg", ".bmp", ".gif"}


class ErreurValidation(ValueError):
    """رسالة موجهة للمدير بالعربية."""


@dataclass
class Etablissement:
    nom_ar: str = ""
    nom_fr: str = ""
    code_etab: str = ""
    type_etab: str = "groupe"
    commune_ar: str = ""
    commune_fr: str = ""
    direction_ar: str = ""
    direction_fr: str = ""
    academie_ar: str = ""
    academie_fr: str = ""
    ville_redaction_ar: str = ""
    ville_redaction_fr: str = ""
    telephone: str = ""
    adresse: str = ""
    logo_path: str = ""
    filigrane_path: str = ""
    pied_page: str = ""
    est_pionniere: str = ""   # «1»: مؤسسة رائدة

    def valider(self) -> None:
        self.nettoyer()
        if not self.nom_ar:
            raise ErreurValidation("اسم المؤسسة بالعربية إجباري.")
        if self.type_etab not in TYPES:
            raise ErreurValidation("نوع المؤسسة غير معروف.")
        if not self.direction_ar:
            raise ErreurValidation("المديرية الإقليمية إجبارية.")
        if not self.academie_ar:
            raise ErreurValidation("الأكاديمية الجهوية إجبارية.")

    def nettoyer(self) -> None:
        for k, v in asdict(self).items():
            if isinstance(v, str):
                setattr(self, k, v.strip() if k.endswith("_path") else " ".join(v.split()))


@dataclass
class Directeur:
    nom_ar: str = ""
    prenom_ar: str = ""
    nom_fr: str = ""
    prenom_fr: str = ""
    sexe: str = "M"
    ppr: str = ""
    telephone: str = ""
    date_affectation: str = ""

    def valider(self) -> None:
        for k, v in asdict(self).items():
            setattr(self, k, " ".join(v.split()))
        if not self.nom_ar or not self.prenom_ar:
            raise ErreurValidation("اسم المدير ونسبه بالعربية إجباريان.")
        if self.sexe not in ("M", "F"):
            raise ErreurValidation("النوع غير صحيح.")
        if self.ppr and not self.ppr.isdigit():
            raise ErreurValidation("رقم التأجير يتكون من أرقام فقط.")
        if self.date_affectation:
            try:
                date.fromisoformat(self.date_affectation)
            except ValueError as e:
                raise ErreurValidation("تاريخ التعيين غير صحيح.") from e


# ---------- المؤسسة ----------

def lire_etablissement(conn: sqlite3.Connection) -> Etablissement | None:
    ligne = conn.execute("SELECT * FROM etablissement WHERE id=1").fetchone()
    if not ligne:
        return None
    noms = Etablissement.__dataclass_fields__.keys()
    return Etablissement(**{k: (ligne[k] or "") for k in noms})


def enregistrer_etablissement(conn: sqlite3.Connection, etab: Etablissement) -> None:
    etab.valider()
    valeurs = asdict(etab)
    colonnes = ", ".join(valeurs)
    marques = ", ".join("?" for _ in valeurs)
    maj = ", ".join(f"{k}=excluded.{k}" for k in valeurs)
    with conn:
        conn.execute(
            f"INSERT INTO etablissement(id, {colonnes}) VALUES (1, {marques}) "
            f"ON CONFLICT(id) DO UPDATE SET {maj}",
            tuple(v or None for v in valeurs.values()))
    journaliser(conn, "enregistrement", "etablissement", 1, etab.nom_ar)


def definir_unites(conn: sqlite3.Connection, noms: list[str]) -> list[str]:
    """يضيف الوحدات الجديدة فقط؛ لا يحذف وحدة مرتبطة بأقسام."""
    propres = []
    for n in noms:
        n = " ".join(n.split())
        if n and n not in propres:
            propres.append(n)
    with conn:
        for n in propres:
            conn.execute("INSERT OR IGNORE INTO unite_scolaire(nom_ar) VALUES (?)", (n,))
    return [r[0] for r in conn.execute("SELECT nom_ar FROM unite_scolaire ORDER BY id")]


def est_groupe(conn: sqlite3.Connection) -> bool:
    e = lire_etablissement(conn)
    return bool(e and e.type_etab == "groupe")


def unites(conn: sqlite3.Connection, toutes: bool = False) -> list[str]:
    """الوحدات المدرسية. في المؤسسة المستقلة لا وحدات: كل ما يخص الوحدات يُخفى في الواجهة (قرار المدير
    2026-11-07). toutes=True يرجع ما هو مسجل في القاعدة مهما كان النوع."""
    if not toutes and not est_groupe(conn):
        return []
    return [r[0] for r in conn.execute("SELECT nom_ar FROM unite_scolaire ORDER BY id")]


def importer_image(dossier: DossierDonnees, source: Path | str, nom: str) -> str:
    """ينسخ صورة الهوية إلى مجلد البيانات ويعيد مسارها النسبي."""
    source = Path(source)
    if source.suffix.lower() not in EXTENSIONS_IMAGES:
        raise ErreurValidation("نوع الصورة غير مدعوم (PNG أو JPG).")
    if not source.is_file():
        raise ErreurValidation("الصورة غير موجودة.")
    cible_dir = dossier.modeles / "identite"
    cible_dir.mkdir(parents=True, exist_ok=True)
    for ancienne in cible_dir.glob(f"{nom}.*"):
        ancienne.unlink()
    cible = cible_dir / f"{nom}{source.suffix.lower()}"
    shutil.copyfile(source, cible)
    return cible.relative_to(dossier.racine).as_posix()


# ---------- المدير ----------

def directeur_actuel(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT p.*, m.id AS mandat_id, m.date_affectation AS mandat_debut "
        "FROM mandat_directeur m JOIN personnel p ON p.id = m.personnel_id "
        "WHERE m.date_fin IS NULL ORDER BY m.id DESC LIMIT 1").fetchone()


def enregistrer_directeur(conn: sqlite3.Connection, d: Directeur, nouveau: bool = False) -> int:
    """يحدّث بيانات المدير الحالي، أو يسجل مديراً جديداً مع حفظ السابق في التاريخ."""
    d.valider()
    actuel = directeur_actuel(conn)
    champs = dict(nom_ar=d.nom_ar, prenom_ar=d.prenom_ar, nom_fr=d.nom_fr or None,
                  prenom_fr=d.prenom_fr or None, sexe=d.sexe, ppr=d.ppr or None,
                  telephone=d.telephone or None)
    with conn:
        if actuel and not nouveau:
            sets = ", ".join(f"{k}=?" for k in champs)
            conn.execute(f"UPDATE personnel SET {sets} WHERE id=?",
                         (*champs.values(), actuel["id"]))
            if d.date_affectation:
                conn.execute("UPDATE mandat_directeur SET date_affectation=? WHERE id=?",
                             (d.date_affectation, actuel["mandat_id"]))
            pid = actuel["id"]
        else:
            if actuel:
                conn.execute("UPDATE mandat_directeur SET date_fin=? WHERE id=?",
                             (date.today().isoformat(), actuel["mandat_id"]))
            cols = ", ".join(champs)
            marques = ", ".join("?" for _ in champs)
            try:
                pid = conn.execute(
                    f"INSERT INTO personnel({cols}, categorie, fonction, date_affectation) "
                    f"VALUES ({marques}, 'directeur', 'الإدارة', ?)",
                    (*champs.values(), d.date_affectation or None)).lastrowid
            except sqlite3.IntegrityError as e:
                raise ErreurValidation("رقم التأجير مسجل لموظف آخر.") from e
            conn.execute("INSERT INTO mandat_directeur(personnel_id, date_affectation) VALUES (?,?)",
                         (pid, d.date_affectation or date.today().isoformat()))
    journaliser(conn, "nouveau_directeur" if (nouveau or not actuel) else "modification",
                "personnel", pid, f"{d.prenom_ar} {d.nom_ar}")
    return pid


# ---------- الإعداد الأول ----------

@dataclass
class ConfigurationInitiale:
    etablissement: Etablissement
    directeur: Directeur
    annee: str = field(default_factory=annee_srv.libelle_pour_date)
    unites: list[str] = field(default_factory=list)
    logo_source: str = ""
    filigrane_source: str = ""


def appliquer_configuration_initiale(conn: sqlite3.Connection, dossier: DossierDonnees,
                                     cfg: ConfigurationInitiale) -> None:
    """يُطبَّق كل شيء في نهاية المعالج، بعد التحقق من كل الخطوات."""
    cfg.etablissement.valider()
    cfg.directeur.valider()
    annee_srv.code_court(cfg.annee)
    if cfg.logo_source:
        cfg.etablissement.logo_path = importer_image(dossier, cfg.logo_source, "logo")
    if cfg.filigrane_source:
        cfg.etablissement.filigrane_path = importer_image(dossier, cfg.filigrane_source, "filigrane")
    enregistrer_etablissement(conn, cfg.etablissement)
    enregistrer_directeur(conn, cfg.directeur)
    if cfg.etablissement.type_etab == "groupe":
        definir_unites(conn, cfg.unites)
    annee_srv.activer_annee(conn, cfg.annee)


def configuration_complete(conn: sqlite3.Connection) -> bool:
    return (lire_etablissement(conn) is not None
            and directeur_actuel(conn) is not None
            and annee_srv.annee_courante(conn) is not None)
