"""السنة الدراسية الجارية."""

from __future__ import annotations

import re
import sqlite3
from datetime import date

from idara.data.journal import journaliser

_MOTIF = re.compile(r"^(\d{4})/(\d{4})$")


class ErreurAnnee(ValueError):
    pass


def libelle_pour_date(d: date | None = None) -> str:
    """من شتنبر تبدأ سنة جديدة: أكتوبر 2026 ← 2026/2027، مارس 2027 ← 2026/2027."""
    d = d or date.today()
    debut = d.year if d.month >= 9 else d.year - 1
    return f"{debut}/{debut + 1}"


def code_court(libelle: str) -> str:
    m = _MOTIF.match(libelle)
    if not m or int(m.group(2)) != int(m.group(1)) + 1:
        raise ErreurAnnee(f"صيغة السنة الدراسية غير صحيحة: {libelle}")
    return f"{m.group(1)[2:]}-{m.group(2)[2:]}"


def activer_annee(conn: sqlite3.Connection, libelle: str) -> int:
    """ينشئ السنة إن لم توجد، ويجعلها السنة الجارية الوحيدة."""
    court = code_court(libelle)
    ligne = conn.execute("SELECT id FROM annee_scolaire WHERE libelle=?", (libelle,)).fetchone()
    with conn:
        conn.execute("UPDATE annee_scolaire SET est_courante=0 WHERE est_courante=1")
        if ligne:
            annee_id = ligne[0]
            conn.execute("UPDATE annee_scolaire SET est_courante=1 WHERE id=?", (annee_id,))
        else:
            annee_id = conn.execute(
                "INSERT INTO annee_scolaire(libelle, code_court, est_courante) VALUES (?,?,1)",
                (libelle, court)).lastrowid
    journaliser(conn, "annee_courante", "annee_scolaire", annee_id, libelle)
    return annee_id


def annee_courante(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM annee_scolaire WHERE est_courante=1").fetchone()


# ---------- السنوات الدراسية: فتح سنة جديدة مع الأرشفة، والاطلاع على السنوات الماضية (طلب المدير 2026-11-12) ----------

def suivante(libelle: str) -> str:
    code_court(libelle)
    a = int(libelle[:4]) + 1
    return f"{a}/{a + 1}"


def lister(conn: sqlite3.Connection) -> list[dict]:
    """كل السنوات، من الأحدث إلى الأقدم، مع عدد الأقسام والتلاميذ المسجلين."""
    res = []
    for r in conn.execute("SELECT * FROM annee_scolaire ORDER BY libelle DESC"):
        res.append({"libelle": r["libelle"], "courante": bool(r["est_courante"]),
                    "classes": conn.execute("SELECT COUNT(*) FROM classe WHERE annee_id=?", (r["id"],)).fetchone()[0],
                    "eleves": conn.execute("SELECT COUNT(*) FROM inscription WHERE annee_id=?",
                                           (r["id"],)).fetchone()[0]})
    return res


def la_plus_recente(conn: sqlite3.Connection) -> str | None:
    r = conn.execute("SELECT MAX(libelle) FROM annee_scolaire").fetchone()
    return r[0] if r else None


def en_consultation(conn: sqlite3.Connection) -> bool:
    """السنة المفتوحة ليست أحدث سنة: المدير يطّلع على أرشيف سنة ماضية."""
    a = annee_courante(conn)
    return bool(a) and a["libelle"] != la_plus_recente(conn)


def ouvrir_annee(conn: sqlite3.Connection, dossier, libelle: str):
    """يفتح سنة دراسية (جديدة أو سابقة للتجريب). قبل ذلك تُحفظ نسخة كاملة من القاعدة (أرشيف السنة المغلقة).
    يرجع مسار نسخة الأرشيف."""
    from idara.services import sauvegarde
    libelle = " ".join(str(libelle).split())
    code_court(libelle)
    if conn.execute("SELECT 1 FROM annee_scolaire WHERE libelle=?", (libelle,)).fetchone():
        raise ErreurAnnee(f"السنة {libelle} موجودة. اخترها من اللائحة للاطلاع عليها.")
    a = annee_courante(conn)
    archive = sauvegarde.creer_sauvegarde(dossier, f"archive_{(a['libelle'] if a else 'debut').replace('/', '-')}")
    activer_annee(conn, libelle)
    journaliser(conn, "annee_ouverte", "annee_scolaire", None, {"annee": libelle, "archive": archive.name})
    return archive


def consulter(conn: sqlite3.Connection, libelle: str) -> None:
    """يجعل سنة موجودة هي المفتوحة (للاطلاع على معطياتها أو العودة إلى السنة الجارية)."""
    if not conn.execute("SELECT 1 FROM annee_scolaire WHERE libelle=?", (libelle,)).fetchone():
        raise ErreurAnnee(f"السنة {libelle} غير موجودة.")
    activer_annee(conn, libelle)
