"""الوثائق: سجل القوالب، بناء قيم الحقول من البيانات، التوليد والأرشفة.

قيم كل وثيقة تُبنى هنا مرة واحدة، فتُستعمل نفس القواعد (التذكير والتأنيث، التواريخ)
في التوليد التجريبي الآن، وفي توليد الوثائق الفعلية في المراحل القادمة.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Mapping

from idara.data.dossier import DossierDonnees
from idara.data.journal import journaliser
from idara.services import annee as annee_srv
from idara.services import etablissement as etab_srv
from idara.services import moteur_docx as moteur
from idara.services.identite_docx import Image, appliquer_identite
from idara.services import textes as tx

DOSSIER_MODELES_DEFAUT = Path(__file__).resolve().parent.parent / "resources" / "modeles"


class ErreurDocument(ValueError):
    """رسالة موجهة للمدير بالعربية."""


@dataclass(frozen=True)
class DefModele:
    code: str
    titre: str
    langue: str
    champs: tuple[str, ...]
    cases_par_page: int = 0  # للوثائق التي تجمع عدة تلاميذ في الصفحة


_COMMUNS = ("etablissement", "etablissement_fr", "ville", "ville_fr", "directeur", "directeur_fr",
            "sayyid_directeur", "bisifat_directeur", "mudir", "mudir_moassasa", "soussigne",
            "titre_directeur_fr", "du_directeur")

MODELES: dict[str, DefModele] = {d.code: d for d in [
    DefModele("certificat_scolarite_ancien", "شهادة مدرسية (ما قبل مسار)", "ar", _COMMUNS + (
        "date_redaction", "sayyid", "nom_complet", "almozdad", "date_naissance", "lieu_naissance",
        "kana_yutabi", "num_registre", "date_entree", "date_sortie", "daras", "dernier_niveau",
        "inqata", "date_sortie_lettres", "lahu", "destinataire_nom", "destinataire_cin")),
    DefModele("attestation_vacances", "شهادة العطلة", "fr", _COMMUNS + (
        "date_redaction", "eleve_fr", "ne", "date_naissance", "lieu_naissance_fr", "inscrit",
        "code_massar", "niveau_fr", "interesse", "du", "au")),
    DefModele("convocation_parent", "استدعاء ولي الأمر", "ar",
              _COMMUNS + ("eleve_N", "tilmidh_N", "ibn_N"), cases_par_page=2),
    DefModele("visite_medicale", "ورقة الزيارة الطبية", "ar",
              _COMMUNS + ("tilmidh", "eleve", "niveau")),
]}


def champs_connus(code: str) -> set[str]:
    return set(MODELES[code].champs)


def champ_reconnu(code: str, champ: str) -> bool:
    connus = champs_connus(code)
    return champ in connus or re.sub(r"_\d+$", "_N", champ) in connus


# ---------- القوالب: الأصلي والنسخة الخاصة بالمؤسسة ----------

def chemin_defaut(code: str) -> Path:
    return DOSSIER_MODELES_DEFAUT / f"{code}.docx"


def chemin_modele(dossier: DossierDonnees, code: str) -> Path:
    """نسخة المؤسسة في مجلد البيانات (تُنشأ من الأصلي عند أول استعمال)."""
    if code not in MODELES:
        raise ErreurDocument(f"قالب غير معروف: {code}")
    cible = dossier.modeles / f"{code}.docx"
    if not cible.exists():
        cible.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(chemin_defaut(code), cible)
    elif _empreinte(cible) in _anciennes_versions().get(code, []):
        # نسخة أصلية من إصدار سابق لم يعدلها المدير: تُحدَّث إلى القالب الجديد
        shutil.copyfile(chemin_defaut(code), cible)
    return cible


def _empreinte(chemin: Path) -> str:
    return hashlib.sha256(chemin.read_bytes()).hexdigest()


def _anciennes_versions() -> dict[str, list[str]]:
    f = DOSSIER_MODELES_DEFAUT / "anciennes_versions.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


@dataclass
class EtatModele:
    definition: DefModele
    chemin: Path
    personnalise: bool
    inconnus: list[str]
    absents: list[str]

    @property
    def utilisable(self) -> bool:
        return not self.inconnus


def etat_modele(dossier: DossierDonnees, code: str) -> EtatModele:
    chemin = chemin_modele(dossier, code)
    try:
        champs = moteur.champs_du_modele(chemin)
    except Exception as e:  # noqa: BLE001 — ملف تالف أو ليس ملف Word
        return EtatModele(MODELES[code], chemin, True, [f"الملف غير صالح: {e}"], [])
    defaut = moteur.champs_du_modele(chemin_defaut(code))
    personnalise = chemin.read_bytes() != chemin_defaut(code).read_bytes()
    inconnus = sorted(c for c in champs if not champ_reconnu(code, c))
    absents = sorted(defaut - champs)
    return EtatModele(MODELES[code], chemin, personnalise, inconnus, absents)


def importer_modele(dossier: DossierDonnees, code: str, source: Path) -> EtatModele:
    """يعوّض قالب المؤسسة بملف Word يختاره المدير، بعد التحقق من حقوله."""
    source = Path(source)
    if source.suffix.lower() != ".docx":
        raise ErreurDocument("القالب يجب أن يكون ملف Word بصيغة ‎.docx")
    try:
        champs = moteur.champs_du_modele(source)
    except Exception as e:  # noqa: BLE001
        raise ErreurDocument(f"تعذرت قراءة الملف: {e}") from e
    inconnus = sorted(c for c in champs if not champ_reconnu(code, c))
    if inconnus:
        raise ErreurDocument("حقول غير معروفة في القالب: " + "، ".join(inconnus))
    cible = chemin_modele(dossier, code)
    shutil.copyfile(cible, cible.with_suffix(".docx.precedent"))
    shutil.copyfile(source, cible)
    return etat_modele(dossier, code)


def restaurer_modele(dossier: DossierDonnees, code: str) -> None:
    cible = chemin_modele(dossier, code)
    shutil.copyfile(cible, cible.with_suffix(".docx.precedent"))
    shutil.copyfile(chemin_defaut(code), cible)


# ---------- قيم الحقول ----------

def _txt(v) -> str:
    return " ".join(str(v).split()) if v else ""


def _requis(valeur, message: str) -> str:
    v = _txt(valeur)
    if not v:
        raise ErreurDocument(message)
    return v


def _optionnel(valeur, fonction=None) -> str:
    """القيمة غير المعروفة تُترك نقطاً، كما في النماذج المطبوعة."""
    if not valeur:
        return "............"
    return fonction(valeur) if fonction else _txt(valeur)


def champs_communs(conn: sqlite3.Connection) -> dict[str, str]:
    etab = etab_srv.lire_etablissement(conn)
    d = etab_srv.directeur_actuel(conn)
    if etab is None or d is None:
        raise ErreurDocument("أكمل إعداد المؤسسة والمدير أولاً.")
    s = d["sexe"]
    nom_fr = " ".join(x for x in (_txt(d["nom_fr"]).upper(), _txt(d["prenom_fr"]).upper()) if x)
    return {
        "etablissement": etab.nom_ar,
        "etablissement_fr": etab.nom_fr or "............",
        "ville": etab.ville_redaction_ar or etab.commune_ar or "............",
        "ville_fr": etab.ville_redaction_fr or etab.commune_fr or "............",
        "directeur": f"{_txt(d['prenom_ar'])} {_txt(d['nom_ar'])}",
        "directeur_fr": nom_fr or "............",
        "sayyid_directeur": tx.accord(s, "السيد", "السيدة"),
        "bisifat_directeur": tx.accord(s, "بصفته مديرا", "بصفتها مديرة"),
        "mudir": tx.accord(s, "مدير", "مديرة"),
        "mudir_moassasa": tx.accord(s, "مدير المؤسسة", "مديرة المؤسسة"),
        "soussigne": tx.accord(s, "soussigné", "soussignée"),
        "titre_directeur_fr": tx.accord(s, "directeur", "directrice"),
        "du_directeur": tx.accord(s, "du directeur", "de la directrice"),
    }


def _sexe(eleve: Mapping) -> str:
    s = eleve.get("sexe")
    if s not in ("M", "F"):
        raise ErreurDocument("نوع التلميذ (ذكر أو أنثى) غير مسجل.")
    return s


def _nom_ar(eleve: Mapping) -> str:
    return _requis(f"{_txt(eleve.get('prenom_ar'))} {_txt(eleve.get('nom_ar'))}",
                   "اسم التلميذ بالعربية غير مسجل.")


def champs_certificat_ancien(conn, eleve: Mapping, destinataire_nom: str,
                             destinataire_cin: str, le: date | None = None) -> dict[str, str]:
    """الشهادة المدرسية للتلاميذ ما قبل مسار. كل حقول النموذج إجبارية (قرار المدير)."""
    s = _sexe(eleve)
    entree = _requis(eleve.get("date_entree"), "تاريخ الالتحاق بالمؤسسة إجباري.")
    sortie = _requis(eleve.get("date_sortie"), "تاريخ الانقطاع إجباري.")
    naissance = _requis(eleve.get("date_naissance"), "تاريخ الازدياد إجباري.")
    if not (naissance < entree <= sortie):
        raise ErreurDocument("التواريخ غير منطقية: يجب أن يكون الازدياد قبل الالتحاق، والالتحاق قبل الانقطاع.")
    v = champs_communs(conn)
    v.update({
        "date_redaction": tx.date_ar(le or date.today()),
        "sayyid": tx.accord(s, "السيد", "السيدة"),
        "nom_complet": _nom_ar(eleve),
        "almozdad": tx.accord(s, "المزداد", "المزدادة"),
        "date_naissance": tx.date_chiffres(naissance),
        "lieu_naissance": _requis(eleve.get("lieu_ar"), "مكان الازدياد إجباري."),
        "kana_yutabi": tx.accord(s, "كان يتابع دراسته", "كانت تتابع دراستها"),
        "num_registre": _requis(eleve.get("num_registre"), "رقم التسجيل في السجل العام إجباري."),
        "date_entree": tx.date_chiffres(entree),
        "date_sortie": tx.date_chiffres(sortie),
        "daras": tx.accord(s, "درس", "درست"),
        "dernier_niveau": _requis(eleve.get("dernier_niveau"), "آخر قسم درس به إجباري."),
        "inqata": tx.accord(s, "انقطع", "انقطعت"),
        "date_sortie_lettres": tx.date_ar(sortie),
        "lahu": tx.accord(s, "له", "لها"),
        "destinataire_nom": _requis(destinataire_nom, "اسم متسلم الشهادة إجباري."),
        "destinataire_cin": _requis(destinataire_cin, "رقم بطاقة متسلم الشهادة إجباري."),
    })
    return v


def champs_attestation_vacances(conn, eleve: Mapping, niveau_code: str, du: date | str,
                                au: date | str, le: date | None = None) -> dict[str, str]:
    s = _sexe(eleve)
    if tx.en_date(au) < tx.en_date(du):
        raise ErreurDocument("تاريخ نهاية العطلة قبل تاريخ بدايتها.")
    nom = " ".join(x for x in (_txt(eleve.get("nom_fr")), _txt(eleve.get("prenom_fr"))) if x)
    v = champs_communs(conn)
    v.update({
        "date_redaction": tx.date_chiffres(le or date.today()),
        "eleve_fr": _requis(nom.upper(), "اسم التلميذ بالفرنسية غير مسجل (لازم لشهادة العطلة)."),
        "ne": tx.accord(s, "Né", "Née"),
        "date_naissance": _requis(eleve.get("date_naissance") and tx.date_chiffres(eleve["date_naissance"]),
                                  "تاريخ ازدياد التلميذ غير مسجل."),
        "lieu_naissance_fr": _requis(eleve.get("lieu_fr"),
                                     "مكان الازدياد بالفرنسية غير مسجل (لازم لشهادة العطلة)."),
        "inscrit": tx.accord(s, "Inscrit", "Inscrite"),
        "code_massar": _requis(eleve.get("code_massar"), "رمز مسار غير مسجل."),
        "niveau_fr": tx.niveau_fr(niveau_code),
        "interesse": tx.accord(s, "l’intéressé", "l’intéressée"),
        "du": tx.date_chiffres(du),
        "au": tx.date_chiffres(au),
    })
    return v


def champs_visite_medicale(conn, eleve: Mapping, niveau_code: str) -> dict[str, str]:
    s = _sexe(eleve)
    v = champs_communs(conn)
    v.update({"tilmidh": tx.accord(s, "التلميذ", "التلميذة"), "eleve": _nom_ar(eleve),
              "niveau": tx.niveau_ar(niveau_code)})
    return v


def champs_convocation(conn, eleves: list[Mapping]) -> tuple[dict[str, str], list[dict[str, str]]]:
    if not eleves:
        raise ErreurDocument("اختر تلميذاً واحداً على الأقل.")
    n = MODELES["convocation_parent"].cases_par_page
    pages = []
    for i in range(0, len(eleves), n):
        page = {}
        for k, e in enumerate(eleves[i:i + n], start=1):
            s = _sexe(e)
            page.update({f"eleve_{k}": _nom_ar(e), f"tilmidh_{k}": tx.accord(s, "التلميذ", "التلميذة"),
                         f"ibn_{k}": tx.accord(s, "ابنكم", "ابنتكم")})
        pages.append(page)
    return champs_communs(conn), pages


# ---------- الهوية البصرية ----------

def identite(conn: sqlite3.Connection, dossier: DossierDonnees) -> tuple[Image | None, Image | None, str]:
    """الترويسة والعلامة المائية والتذييل كما حُددت في إعداد المؤسسة."""
    etab = etab_srv.lire_etablissement(conn)
    if etab is None:
        return None, None, ""
    images = []
    for rel, nom in ((etab.logo_path, "الترويسة"), (etab.filigrane_path, "العلامة المائية")):
        if not rel:
            images.append(None)
            continue
        chemin = dossier.racine / rel
        try:
            images.append(Image.depuis_fichier(chemin))
        except Exception as e:  # noqa: BLE001
            raise ErreurDocument(f"تعذرت قراءة صورة {nom} ({chemin.name}). "
                                 "أعد اختيارها من إعداد المؤسسة.") from e
    return images[0], images[1], etab.pied_page or ""


# ---------- التوليد والأرشفة ----------

@dataclass
class DocumentGenere:
    id: int | None
    chemin: Path


def _slug(texte: str) -> str:
    t = re.sub(r"[^\w؀-ۿ-]+", "_", texte, flags=re.UNICODE).strip("_")
    return t[:40] or "document"


def generer(conn: sqlite3.Connection, dossier: DossierDonnees, code: str,
            valeurs: dict[str, str], pages: list[dict[str, str]] | None = None, *,
            libelle: str = "", eleve_id: int | None = None, personnel_id: int | None = None,
            conge_id: int | None = None, courrier_id: int | None = None,
            destinataire_nom: str | None = None, destinataire_cin: str | None = None,
            essai: bool = False) -> DocumentGenere:
    """يولد الوثيقة من قالب المؤسسة. الوثيقة الفعلية تُؤرشف مع لقطة من بياناتها؛
    التوليد التجريبي يُحفظ في مجلد essais دون أرشفة."""
    etat = etat_modele(dossier, code)
    if not etat.utilisable:
        raise ErreurDocument("القالب يحتاج تصحيحاً: " + "، ".join(etat.inconnus))
    try:
        contenu = moteur.remplir(etat.chemin, valeurs, pages)
    except moteur.ErreurModele as e:
        raise ErreurDocument(str(e)) from e
    contenu = appliquer_identite(contenu, *identite(conn, dossier))

    maintenant = datetime.now()
    a = annee_srv.annee_courante(conn)
    sous = "essais" if essai else (a["libelle"].replace("/", "-") if a else str(maintenant.year))
    rep = dossier.archives / sous / code
    rep.mkdir(parents=True, exist_ok=True)
    chemin = rep / f"{maintenant:%Y%m%d_%H%M%S}_{_slug(libelle or code)}.docx"
    n = 1
    while chemin.exists():
        n += 1
        chemin = chemin.with_name(f"{chemin.stem}_{n}.docx")
    chemin.write_bytes(contenu)
    if essai:
        return DocumentGenere(None, chemin)

    modele_id = conn.execute("SELECT id FROM modele_document WHERE code=?", (code,)).fetchone()[0]
    donnees = json.dumps({"valeurs": valeurs, "pages": pages, "libelle": libelle}, ensure_ascii=False)
    with conn:
        doc_id = conn.execute(
            "INSERT INTO document_genere(modele_id, eleve_id, personnel_id, conge_id, courrier_id,"
            " destinataire_nom, destinataire_cin, donnees, fichier_archive) VALUES (?,?,?,?,?,?,?,?,?)",
            (modele_id, eleve_id, personnel_id, conge_id, courrier_id, destinataire_nom,
             destinataire_cin, donnees, chemin.relative_to(dossier.racine).as_posix())).lastrowid
    journaliser(conn, "generation", "document_genere", doc_id, f"{code}: {libelle}")
    return DocumentGenere(doc_id, chemin)


def regenerer(conn: sqlite3.Connection, dossier: DossierDonnees, document_id: int) -> DocumentGenere:
    """إعادة الطباعة: نفس البيانات المحفوظة وقت التوليد الأول."""
    ligne = conn.execute(
        "SELECT d.*, m.code FROM document_genere d JOIN modele_document m ON m.id=d.modele_id "
        "WHERE d.id=?", (document_id,)).fetchone()
    if ligne is None:
        raise ErreurDocument("الوثيقة غير موجودة في الأرشيف.")
    donnees = json.loads(ligne["donnees"])
    return generer(conn, dossier, ligne["code"], donnees["valeurs"], donnees.get("pages"),
                   libelle=donnees.get("libelle", ""), eleve_id=ligne["eleve_id"],
                   personnel_id=ligne["personnel_id"], conge_id=ligne["conge_id"],
                   courrier_id=ligne["courrier_id"], destinataire_nom=ligne["destinataire_nom"],
                   destinataire_cin=ligne["destinataire_cin"])


def documents_recents(conn: sqlite3.Connection, limite: int = 20) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT d.id, d.date_generation, d.fichier_archive, d.destinataire_nom, m.titre, "
        "json_extract(d.donnees, '$.libelle') AS libelle FROM document_genere d "
        "JOIN modele_document m ON m.id=d.modele_id ORDER BY d.id DESC LIMIT ?", (limite,)).fetchall()


# ---------- أمثلة للتوليد التجريبي (بيانات وهمية) ----------

def _eleve_exemple(sexe="M", **k) -> dict:
    base = {"prenom_ar": "سعيد" if sexe == "M" else "سلمى", "nom_ar": "التجريبي",
            "prenom_fr": "SAID" if sexe == "M" else "SALMA", "nom_fr": "TAJRIBI",
            "sexe": sexe, "date_naissance": "2015-04-30", "lieu_ar": "المدينة",
            "lieu_fr": "VILLE", "code_massar": "X000000000"}
    base.update(k)
    return base


def exemple(conn: sqlite3.Connection, code: str, sexe: str = "M"):
    """قيم وهمية كاملة لمعاينة القالب قبل وجود بيانات التلاميذ."""
    if code == "certificat_scolarite_ancien":
        e = _eleve_exemple(sexe, date_naissance="1985-01-01", num_registre=1234,
                           date_entree="1992-10-15", date_sortie="1998-06-30", dernier_niveau="الخامس")
        return champs_certificat_ancien(conn, e, "[اسم المتسلم]", "[CIN]"), None
    if code == "attestation_vacances":
        an = date.today().year
        return champs_attestation_vacances(conn, _eleve_exemple(sexe), "5AP",
                                           date(an, 7, 7), date(an, 8, 31)), None
    if code == "visite_medicale":
        return champs_visite_medicale(conn, _eleve_exemple(sexe), "4AP"), None
    if code == "convocation_parent":
        eleves = [_eleve_exemple("M"), _eleve_exemple("F"), _eleve_exemple("M", prenom_ar="يوسف")]
        return champs_convocation(conn, eleves)
    raise ErreurDocument(f"قالب غير معروف: {code}")
