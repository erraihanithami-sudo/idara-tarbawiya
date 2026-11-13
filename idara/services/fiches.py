"""مخزن JSON صغير للصفحات التي لا تحتاج جداول خاصة (2026-11-13)."""

from __future__ import annotations

import json
import sqlite3


def lire(conn: sqlite3.Connection, cle: str, defaut=None):
    r = conn.execute("SELECT donnees FROM fiche_json WHERE cle=?", (cle,)).fetchone()
    return json.loads(r[0]) if r else defaut


def ecrire(conn: sqlite3.Connection, cle: str, donnees) -> None:
    with conn:
        conn.execute("INSERT INTO fiche_json(cle, donnees) VALUES (?,?) ON CONFLICT(cle) DO UPDATE SET "
                     "donnees=excluded.donnees, maj_le=datetime('now','localtime')",
                     (cle, json.dumps(donnees, ensure_ascii=False)))


def supprimer(conn: sqlite3.Connection, prefixe: str) -> int:
    with conn:
        return conn.execute("DELETE FROM fiche_json WHERE cle LIKE ?", (prefixe + "%",)).rowcount


def compter(conn: sqlite3.Connection, prefixe: str) -> int:
    return conn.execute("SELECT COUNT(*) FROM fiche_json WHERE cle LIKE ?", (prefixe + "%",)).fetchone()[0]
