"""التلاميذ: البحث، البطاقة، التعديل، الوضعيات، وتوليد وثائقهم."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from idara.data.dossier import DossierDonnees
from idara.services import annee as annee_srv
from idara.services import documents as dc
from idara.services import textes as tx
from idara.services.massar import MOTIF_CODE, normaliser

STATUTS = {"inscrit": "مسجّل", "arrive": "وافد", "parti": "مغادر", "interrompu": "منقطع", "exclu": "مفصول"}
SORTIES = ("parti", "interrompu", "exclu")  # وضعيات تُخرج التلميذ من لائحة الحاضرين
CHAMPS_MODIFIABLES = ("nom_ar", "prenom_ar", "nom_fr", "prenom_fr", "sexe", "date_naissance")


class ErreurEleve(ValueError):
    """رسالة موجهة للمدير بالعربية."""


# ---------- البحث ----------

_SELECT = """
SELECT e.id, e.code_massar, e.num_registre, e.nom_ar, e.prenom_ar, e.nom_fr, e.prenom_fr, e.sexe,
       e.date_naissance, e.source, l.nom_ar AS lieu_ar, l.nom_fr AS lieu_fr,
       i.id AS inscription_id, i.statut, c.code AS classe, n.code AS niveau, i.niveau_confirme
FROM eleve e
LEFT JOIN lieu l ON l.id = e.lieu_naissance_id
LEFT JOIN inscription i ON i.eleve_id = e.id AND i.annee_id = ?
LEFT JOIN classe c ON c.id = i.classe_id
LEFT JOIN niveau n ON n.id = i.niveau_id
"""


def _annee_id(conn) -> int:
    a = annee_srv.annee_courante(conn)
    return a["id"] if a else -1


def rechercher(conn: sqlite3.Connection, texte: str, source: str = "massar",
               limite: int = 60) -> list[sqlite3.Row]:
    """بالرمز (أو جزء منه)، أو برقم السجل، أو بالاسم والنسب بالعربية أو الفرنسية وبأي ترتيب.
    البحث يتجاهل الهمزات والمسافات وحالة الأحرف. نص فارغ ← تلاميذ السنة الجارية."""
    t = (texte or "").strip()
    lignes = conn.execute(_SELECT + " WHERE e.source = ? ORDER BY c.code, e.nom_ar, e.prenom_ar",
                          (_annee_id(conn), source)).fetchall()
    if not t:
        return [r for r in lignes if r["inscription_id"] is not None][:limite] if source == "massar" \
            else lignes[:limite]
    cible = normaliser(t)
    res = []
    for r in lignes:
        noms = [f"{r['nom_ar']}{r['prenom_ar']}", f"{r['prenom_ar']}{r['nom_ar']}",
                f"{r['nom_fr'] or ''}{r['prenom_fr'] or ''}", f"{r['prenom_fr'] or ''}{r['nom_fr'] or ''}"]
        if (r["code_massar"] and cible in normaliser(r["code_massar"])) \
                or (r["num_registre"] is not None and t == str(r["num_registre"])) \
                or any(cible in normaliser(n) for n in noms):
            res.append(r)
        if len(res) >= limite:
            break
    return res


# ---------- البطاقة ----------

def fiche(conn: sqlite3.Connection, eleve_id: int) -> sqlite3.Row:
    r = conn.execute(_SELECT + " WHERE e.id = ?", (_annee_id(conn), eleve_id)).fetchone()
    if r is None:
        raise ErreurEleve("التلميذ غير موجود.")
    return r


def parcours(conn: sqlite3.Connection, eleve_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT a.libelle AS annee, c.code AS classe, n.code AS niveau, i.niveau_confirme, i.statut, "
        "i.date_entree, i.date_sortie, i.etab_origine, i.etab_destination, i.motif_sortie "
        "FROM inscription i JOIN annee_scolaire a ON a.id=i.annee_id LEFT JOIN classe c ON c.id=i.classe_id "
        "LEFT JOIN niveau n ON n.id=i.niveau_id WHERE i.eleve_id=? ORDER BY a.libelle DESC",
        (eleve_id,)).fetchall()


def documents(conn: sqlite3.Connection, eleve_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT d.id, d.date_generation, d.fichier_archive, d.destinataire_nom, m.titre "
        "FROM document_genere d JOIN modele_document m ON m.id=d.modele_id "
        "WHERE d.eleve_id=? ORDER BY d.id DESC", (eleve_id,)).fetchall()


def champs_verrouilles(conn, eleve_id: int) -> set[str]:
    r = conn.execute("SELECT champs_verrouilles FROM eleve WHERE id=?", (eleve_id,)).fetchone()
    return set(json.loads(r[0] or "[]")) if r else set()


# ---------- التعديل ----------

def lieu_id(conn: sqlite3.Connection, nom_ar: str, nom_fr: str = "") -> int | None:
    """يجد المكان أو ينشئه. تصحيح الاسم الفرنسي لمكان يصحح كل التلاميذ المزدادين فيه."""
    nom_ar, nom_fr = " ".join(nom_ar.split()), " ".join(nom_fr.split()).upper()
    if not nom_ar:
        return None
    r = conn.execute("SELECT id, nom_fr FROM lieu WHERE nom_ar=?", (nom_ar,)).fetchone()
    if r is None:
        return conn.execute("INSERT INTO lieu(nom_ar, nom_fr) VALUES (?,?)", (nom_ar, nom_fr or None)).lastrowid
    if nom_fr and nom_fr != (r["nom_fr"] or ""):
        conn.execute("UPDATE lieu SET nom_fr=? WHERE id=?", (nom_fr, r["id"]))
    return r["id"]


def modifier(conn: sqlite3.Connection, eleve_id: int, valeurs: dict[str, str]) -> list[str]:
    """يعدّل بيانات التلميذ. الحقول المعدّلة تُقفل فلا يمحوها الاستيراد اللاحق من مسار.
    valeurs: من CHAMPS_MODIFIABLES، و lieu_ar / lieu_fr. يعيد الحقول التي تغيرت."""
    actuel = fiche(conn, eleve_id)
    propres = {k: " ".join(str(v).split()) for k, v in valeurs.items() if v is not None}
    for k in ("nom_fr", "prenom_fr"):
        if k in propres:
            propres[k] = propres[k].upper()
    if "nom_ar" in propres and not propres["nom_ar"] or "prenom_ar" in propres and not propres["prenom_ar"]:
        raise ErreurEleve("الاسم والنسب بالعربية إجباريان.")
    if propres.get("sexe") not in (None, "M", "F"):
        raise ErreurEleve("النوع غير صحيح.")
    if propres.get("date_naissance"):
        try:
            if date.fromisoformat(propres["date_naissance"]) > date.today():
                raise ErreurEleve("تاريخ الازدياد في المستقبل.")
        except ValueError as e:
            raise ErreurEleve("تاريخ الازدياد غير صحيح.") from e
    changes = [k for k in CHAMPS_MODIFIABLES if k in propres and propres[k] != (actuel[k] or "")]
    lieu_change = ("lieu_ar" in propres and propres["lieu_ar"] != (actuel["lieu_ar"] or "")) or \
                  ("lieu_fr" in propres and propres["lieu_fr"].upper() != (actuel["lieu_fr"] or ""))
    with conn:
        if changes:
            sets = ", ".join(f"{k}=?" for k in changes)
            conn.execute(f"UPDATE eleve SET {sets}, modifie_le=datetime('now','localtime') WHERE id=?",
                         (*[propres[k] or None for k in changes], eleve_id))
        if lieu_change:
            lid = lieu_id(conn, propres.get("lieu_ar", actuel["lieu_ar"] or ""),
                          propres.get("lieu_fr", actuel["lieu_fr"] or ""))
            conn.execute("UPDATE eleve SET lieu_naissance_id=? WHERE id=?", (lid, eleve_id))
            changes.append("lieu")
        if changes:
            verrous = champs_verrouilles(conn, eleve_id) | set(changes)
            conn.execute("UPDATE eleve SET champs_verrouilles=? WHERE id=?",
                         (json.dumps(sorted(verrous)), eleve_id))
            conn.execute("INSERT INTO journal(action, cible, cible_id, details) VALUES ('modification','eleve',?,?)",
                         (eleve_id, ", ".join(changes)))
    return changes


# ---------- الوضعيات ----------

def changer_statut(conn: sqlite3.Connection, eleve_id: int, statut: str, le: str | None = None,
                   etablissement: str = "", motif: str = "") -> None:
    """مغادر (parti) أو منقطع (interrompu): تاريخ إجباري. وافد (arrive): المؤسسة الأصلية.
    مسجّل (inscrit): إلغاء المغادرة أو الانقطاع. لا يُحذف أي شيء من التاريخ المدرسي."""
    if statut not in STATUTS:
        raise ErreurEleve("وضعية غير معروفة.")
    r = fiche(conn, eleve_id)
    if r["inscription_id"] is None:
        raise ErreurEleve("التلميذ غير مسجل في السنة الجارية.")
    if statut in SORTIES and not le:
        raise ErreurEleve("تاريخ المغادرة أو الانقطاع أو الفصل إجباري.")
    if statut == "exclu" and not motif.strip():
        raise ErreurEleve("سبب الفصل ومرجع القرار إجباريان.")
    if statut == "parti" and not etablissement.strip():
        raise ErreurEleve("المؤسسة المستقبلة إجبارية للمغادر.")
    with conn:
        if statut in SORTIES:
            conn.execute("UPDATE inscription SET statut=?, date_sortie=?, etab_destination=?, motif_sortie=? "
                         "WHERE id=?", (statut, le, etablissement.strip() or None, motif.strip() or None,
                                        r["inscription_id"]))
        elif statut == "arrive":
            conn.execute("UPDATE inscription SET statut='arrive', date_entree=?, etab_origine=?, "
                         "date_sortie=NULL WHERE id=?", (le, etablissement.strip() or None, r["inscription_id"]))
        else:
            conn.execute("UPDATE inscription SET statut='inscrit', date_sortie=NULL, etab_destination=NULL, "
                         "motif_sortie=NULL WHERE id=?", (r["inscription_id"],))
        conn.execute("INSERT INTO journal(action, cible, cible_id, details) VALUES ('statut','eleve',?,?)",
                     (eleve_id, f"{STATUTS[statut]} {le or ''} {etablissement}".strip()))


# ---------- الوثائق ----------

def donnees_document(r: sqlite3.Row) -> dict:
    return {k: r[k] for k in ("nom_ar", "prenom_ar", "nom_fr", "prenom_fr", "sexe", "date_naissance",
                              "lieu_ar", "lieu_fr", "code_massar", "num_registre")}


def _niveau_confirme(r) -> str:
    if not r["niveau"]:
        raise ErreurEleve("مستوى التلميذ غير محدد. أكّده من صفحة «الاستيراد من مسار».")
    if not r["niveau_confirme"]:
        raise ErreurEleve("مستوى التلميذ مقترح ولم يُؤكَّد بعد. أكّده من صفحة «الاستيراد من مسار».")
    return r["niveau"]


def nom_complet(r) -> str:
    return f"{r['prenom_ar']} {r['nom_ar']}"


def generer_attestation_vacances(conn, dossier: DossierDonnees, eleve_id: int, du: date, au: date,
                                 le: date | None = None) -> dc.DocumentGenere:
    r = fiche(conn, eleve_id)
    v = dc.champs_attestation_vacances(conn, donnees_document(r), _niveau_confirme(r), du, au, le)
    return dc.generer(conn, dossier, "attestation_vacances", v, eleve_id=eleve_id,
                      libelle=f"{nom_complet(r)} {tx.date_chiffres(du)}-{tx.date_chiffres(au)}")


def generer_visite_medicale(conn, dossier: DossierDonnees, eleve_id: int) -> dc.DocumentGenere:
    r = fiche(conn, eleve_id)
    v = dc.champs_visite_medicale(conn, donnees_document(r), _niveau_confirme(r))
    return dc.generer(conn, dossier, "visite_medicale", v, eleve_id=eleve_id, libelle=nom_complet(r))


def generer_convocations(conn, dossier: DossierDonnees, eleve_ids: list[int]) -> list[dc.DocumentGenere]:
    """ملف واحد لكل المختارين (تلميذان في الصفحة)، ويُسجَّل في وثائق كل تلميذ."""
    if not eleve_ids:
        raise ErreurEleve("اختر تلميذاً واحداً على الأقل.")
    lignes = [fiche(conn, i) for i in eleve_ids]
    valeurs, pages = dc.champs_convocation(conn, [donnees_document(r) for r in lignes])
    premier = dc.generer(conn, dossier, "convocation_parent", valeurs, pages, eleve_id=lignes[0]["id"],
                         libelle="، ".join(nom_complet(r) for r in lignes))
    docs = [premier]
    # بقية التلاميذ: نفس الملف مسجل في أرشيف كل واحد منهم
    with conn:
        for r in lignes[1:]:
            i = conn.execute(
                "INSERT INTO document_genere(modele_id, eleve_id, donnees, fichier_archive) "
                "SELECT modele_id, ?, donnees, fichier_archive FROM document_genere WHERE id=?",
                (r["id"], premier.id)).lastrowid
            docs.append(dc.DocumentGenere(i, premier.chemin))
    return docs


def code_valide(code: str) -> bool:
    return bool(MOTIF_CODE.match(code or ""))


def chemin_archive(dossier: DossierDonnees, fichier_archive: str) -> Path:
    return dossier.racine / fichier_archive
