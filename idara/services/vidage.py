"""تفريغ مكوّن واحد من مكونات البرنامج (طلب المدير 2026-11-07)، إلى جانب تصفير البرنامج كاملاً.

كل تفريغ تسبقه نسخة احتياطية كاملة (يمكن استرجاعها)، ويُنفذ في معاملة واحدة: إما يُحذف كل شيء أو لا شيء.
الوثائق المولَّدة سابقاً تبقى في الأرشيف (تُفك صلتها بالتلميذ أو الموظف المحذوف فقط).

مكوّن «لوائح التلاميذ» يقبل وحدة مدرسية واحدة: تُحذف أقسام هذه الوحدة في السنة الجارية وتلاميذها
(ومن لم يعد له تسجيل في أي قسم يُحذف ملفه)، وتبقى باقي الوحدات كما هي.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from idara.data.dossier import DossierDonnees
from idara.data.journal import journaliser
from idara.services import annee as annee_srv
from idara.services import sauvegarde


class ErreurVidage(ValueError):
    """رسالة موجهة للمدير بالعربية."""


@dataclass(frozen=True)
class Composant:
    cle: str
    libelle: str
    description: str
    compte: str          # SQL يرجع عدد العناصر الحالية


COMPOSANTS = [
    Composant("eleves", "لوائح التلاميذ (مسار)",
              "التلاميذ وتسجيلاتهم وأقسامهم، ومعها ما يخصهم: النتائج، مستويات التعلمات الأساس، الحركية، السلوك، "
              "التسجيلات، الغياب، الانخراط في الأندية، وإسناد الأقسام.",
              "SELECT COUNT(*) FROM eleve WHERE source='massar'"),
    Composant("resultats", "نتائج التقويم المستوردة",
              "معدلات التلاميذ المستوردة من مسار، ومعطيات مجالس الأقسام ومحاضر نهاية الأسدوس.",
              "SELECT COUNT(*) FROM resultat"),
    Composant("tarl", "التعلمات الأساس",
              "نتائج روائز الموضعة المستوردة والمستويات المتوقعة ومسارات المجموعات.",
              "SELECT COUNT(*) FROM niveau_apprentissage"),
    Composant("personnel", "الموارد البشرية",
              "الموظفون (عدا المدير) وما يخصهم: الرخص، إسناد الأقسام، عضوية المجالس، الحراسة، الدعم.",
              "SELECT COUNT(*) FROM personnel WHERE id NOT IN (SELECT personnel_id FROM mandat_directeur)"),
    Composant("anciens", "التلاميذ القدامى",
              "ملفات التلاميذ القدامى (ما قبل مسار) المدرجة أو المستوردة.",
              "SELECT COUNT(*) FROM eleve WHERE source='avant_massar'"),
    Composant("activites", "الأندية والأنشطة",
              "الأندية التربوية وأعضاؤها والبرنامج السنوي للأنشطة.",
              "SELECT COUNT(*) FROM club"),
    Composant("absences", "تتبع الغياب",
              "الأشهر المُدرجة وغياب الأقسام.",
              "SELECT COUNT(*) FROM absence_mois"),
    Composant("frais", "التسجيلات (واجبات التسجيل)",
              "تأشيرات التأمين والجمعية الرياضية والتعاون المدرسي.",
              "SELECT COUNT(*) FROM frais_inscription"),
    Composant("soutien", "الدعم التربوي",
              "مراحل الدعم وفئاته ومجموعاته وتلاميذها وحصصها.",
              "SELECT COUNT(*) FROM soutien_groupe"),
    Composant("examen", "الامتحان الموحد المحلي",
              "الامتحانات وموادها وقاعاتها ومترشحوها والحراسة.",
              "SELECT COUNT(*) FROM examen"),
    Composant("projet", "مشروع المؤسسة",
              "المشاريع المتتبَّعة ومستهدفاتها وعملياتها المستوردة من مسار وتتبعها.",
              "SELECT COUNT(*) FROM projet_operation"),
]
PAR_CLE = {c.cle: c for c in COMPOSANTS}


def compter(conn: sqlite3.Connection, cle: str) -> int:
    return conn.execute(PAR_CLE[cle].compte).fetchone()[0]


def _ids(conn, sql: str, args=()) -> list[int]:
    return [r[0] for r in conn.execute(sql, args)]


def _dans(ids) -> str:
    return "(" + ",".join(str(int(i)) for i in ids) + ")" if ids else "(NULL)"


def _supprimer_eleves(conn, eleves: list[int]) -> None:
    """يحذف ملفات التلاميذ وكل ما يرتبط بهم (والوثائق المولَّدة تبقى في الأرشيف)."""
    e = _dans(eleves)
    ins = _dans(_ids(conn, f"SELECT id FROM inscription WHERE eleve_id IN {e}"))
    for sql in (f"DELETE FROM soutien_eleve WHERE inscription_id IN {ins}",
                f"DELETE FROM frais_inscription WHERE eleve_id IN {e}",
                f"DELETE FROM club_membre WHERE eleve_id IN {e}",
                f"DELETE FROM examen_candidat WHERE eleve_id IN {e}",
                f"DELETE FROM resultat WHERE eleve_id IN {e}",
                f"DELETE FROM niveau_apprentissage WHERE eleve_id IN {e}",
                f"DELETE FROM observation_comportement WHERE eleve_id IN {e}",
                f"DELETE FROM mouvement WHERE eleve_id IN {e}",
                f"DELETE FROM eleve_avant_massar WHERE eleve_id IN {e}",
                f"UPDATE document_genere SET eleve_id=NULL WHERE eleve_id IN {e}",
                f"DELETE FROM inscription WHERE eleve_id IN {e}",
                f"DELETE FROM eleve WHERE id IN {e}"):
        conn.execute(sql)


def _vider_eleves(conn, unite: str | None) -> int:
    if unite:
        a = annee_srv.annee_courante(conn)
        u = conn.execute("SELECT id FROM unite_scolaire WHERE nom_ar=?", (unite,)).fetchone()
        if a is None or u is None:
            raise ErreurVidage("الوحدة المدرسية غير موجودة.")
        classes = _ids(conn, "SELECT id FROM classe WHERE annee_id=? AND unite_id=?", (a["id"], u[0]))
    else:
        classes = _ids(conn, "SELECT id FROM classe")
    c = _dans(classes)
    ins = _ids(conn, f"SELECT id FROM inscription WHERE classe_id IN {c}")
    concernes = _ids(conn, f"SELECT DISTINCT eleve_id FROM inscription WHERE id IN {_dans(ins)}")
    conn.execute(f"DELETE FROM soutien_eleve WHERE inscription_id IN {_dans(ins)}")
    conn.execute(f"DELETE FROM inscription WHERE id IN {_dans(ins)}")
    if unite:   # من بقي له تسجيل في وحدة أخرى أو سنة أخرى يبقى ملفه
        orphelins = [e for e in concernes
                     if not conn.execute("SELECT 1 FROM inscription WHERE eleve_id=?", (e,)).fetchone()]
    else:
        orphelins = _ids(conn, "SELECT id FROM eleve WHERE source='massar'")
    _supprimer_eleves(conn, orphelins)
    for sql in (f"DELETE FROM absence_classe WHERE classe_id IN {c}",
                f"DELETE FROM affectation_classe WHERE classe_id IN {c}",
                f"DELETE FROM classe WHERE id IN {c}"):
        conn.execute(sql)
    if not unite:
        conn.execute("DELETE FROM import_lot")
        conn.execute("DELETE FROM absence_mois")
    return len(orphelins)


def _vider_personnel(conn) -> int:
    p = _dans(_ids(conn, "SELECT id FROM personnel WHERE id NOT IN (SELECT personnel_id FROM mandat_directeur)"))
    conges = _dans(_ids(conn, f"SELECT id FROM conge WHERE personnel_id IN {p}"))
    groupes = _dans(_ids(conn, f"SELECT id FROM soutien_groupe WHERE personnel_id IN {p}"))
    n = conn.execute(f"SELECT COUNT(*) FROM personnel WHERE id IN {p}").fetchone()[0]
    for sql in (f"DELETE FROM reprise_travail WHERE personnel_id IN {p} OR conge_id IN {conges}",
                f"UPDATE courrier SET conge_id=NULL WHERE conge_id IN {conges}",
                f"UPDATE document_genere SET conge_id=NULL WHERE conge_id IN {conges}",
                f"UPDATE document_genere SET personnel_id=NULL WHERE personnel_id IN {p}",
                f"UPDATE conge SET prolongation_de=NULL WHERE id IN {conges}",
                f"DELETE FROM conge WHERE id IN {conges}",
                f"DELETE FROM affectation_classe WHERE personnel_id IN {p}",
                f"DELETE FROM affectation_equipement WHERE personnel_id IN {p}",
                f"DELETE FROM conseil_presence WHERE membre_id IN (SELECT id FROM conseil_membre WHERE "
                f"personnel_id IN {p})",
                f"DELETE FROM conseil_membre WHERE personnel_id IN {p}",
                f"UPDATE club SET animateur_id=NULL WHERE animateur_id IN {p}",
                f"DELETE FROM soutien_seance WHERE groupe_id IN {groupes}",
                f"DELETE FROM soutien_eleve WHERE groupe_id IN {groupes}",
                f"DELETE FROM soutien_groupe WHERE id IN {groupes}",
                f"DELETE FROM examen_affectation WHERE personnel_id IN {p}",
                f"DELETE FROM personnel WHERE id IN {p}"):
        conn.execute(sql)
    return n


def _executer(conn, cle: str, unite: str | None) -> int:
    n = compter(conn, cle)
    if cle == "eleves":
        return _vider_eleves(conn, unite)
    if cle == "personnel":
        return _vider_personnel(conn)
    if cle == "anciens":
        _supprimer_eleves(conn, _ids(conn, "SELECT id FROM eleve WHERE source='avant_massar'"))
        return n
    tables = {
        "resultats": ["resultat", "conseil_niveau", "isa_classe", "deliberation"],
        "tarl": ["niveau_apprentissage", "tarl_parcours", "niveau_attendu"],
        "activites": ["club_membre", "activite", "club"],
        "absences": ["absence_classe", "absence_mois"],
        "frais": ["frais_inscription"],
        "soutien": ["soutien_seance", "soutien_eleve", "soutien_groupe", "soutien_categorie", "soutien_etape"],
        "examen": ["examen_affectation", "examen_candidat", "examen_matiere", "examen_salle", "examen"],
        "projet": ["projet_operation", "projet_cible", "projet_etab"],
    }[cle]
    for t in tables:
        conn.execute(f"DELETE FROM {t}")
    return n


def vider(conn: sqlite3.Connection, dossier: DossierDonnees, cle: str, unite: str | None = None) -> tuple[int, Path]:
    """يفرغ المكوّن بعد نسخة احتياطية. يرجع (عدد العناصر المحذوفة، مسار النسخة)."""
    if cle not in PAR_CLE:
        raise ErreurVidage("مكوّن غير معروف.")
    if unite and cle != "eleves":
        raise ErreurVidage("التفريغ حسب الوحدة خاص بلوائح التلاميذ.")
    copie = sauvegarde.creer_sauvegarde(dossier, f"avant_vidage_{cle}")
    with conn:
        n = _executer(conn, cle, unite)
    journaliser(conn, "vidage", cle, None, PAR_CLE[cle].libelle + (f" · {unite}" if unite else "") + f" · {n}")
    return n, copie
