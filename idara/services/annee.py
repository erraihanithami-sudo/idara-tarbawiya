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
