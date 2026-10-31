"""سجل العمليات المهمة."""

from __future__ import annotations

import json
import sqlite3
from typing import Any


def journaliser(conn: sqlite3.Connection, action: str, cible: str,
                cible_id: int | None = None, details: Any = None) -> None:
    if details is not None and not isinstance(details, str):
        details = json.dumps(details, ensure_ascii=False)
    conn.execute(
        "INSERT INTO journal(action, cible, cible_id, details) VALUES (?,?,?,?)",
        (action, cible, cible_id, details),
    )
    conn.commit()


def dernieres_operations(conn: sqlite3.Connection, limite: int = 50) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM journal ORDER BY id DESC LIMIT ?", (limite,)
    ).fetchall()
