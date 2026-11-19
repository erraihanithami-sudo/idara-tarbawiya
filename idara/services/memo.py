"""مفكرة المدير (طلب المدير 2026-11-19): بطاقات تذكير بموضوع وتاريخ وساعة، تُلصق على السبورة، ويومية تُبرز
الأيام التي فيها تذكير أو محطة من برنامج العمل السنوي أو من المقرر الوزاري."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta

COULEURS = {"jaune": ("#FFE45C", "أصفر"), "rose": ("#FF9EC4", "وردي"), "vert": ("#A5E887", "أخضر"),
            "bleu": ("#8FD3FF", "أزرق"), "orange": ("#FFB766", "برتقالي"), "violet": ("#CDB4FF", "بنفسجي")}


class ErreurMemo(ValueError):
    """رسالة موجهة للمدير بالعربية."""


@dataclass
class Memo:
    sujet: str
    date_memo: str
    heure: str = ""
    details: str = ""
    couleur: str = "jaune"
    fait: bool = False
    id: int | None = None

    @property
    def resume(self) -> str:
        s = " ".join(self.sujet.split())
        return s if len(s) <= 60 else s[:57] + "…"


def _heure(h: str) -> str:
    h = (h or "").strip().replace(".", ":").replace("h", ":")
    if not h:
        return ""
    try:
        hh, mm = (h.split(":") + ["0"])[:2]
        hh, mm = int(hh), int(mm or 0)
    except ValueError:
        raise ErreurMemo("الساعة غير صحيحة: اكتبها هكذا 14:30") from None
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        raise ErreurMemo("الساعة غير صحيحة: اكتبها هكذا 14:30")
    return f"{hh:02d}:{mm:02d}"


def enregistrer(conn: sqlite3.Connection, m: Memo) -> int:
    sujet = " ".join((m.sujet or "").split())
    if not sujet:
        raise ErreurMemo("اكتب موضوع التذكير.")
    try:
        date.fromisoformat(m.date_memo)
    except (TypeError, ValueError):
        raise ErreurMemo("تاريخ التذكير غير صحيح.") from None
    if m.couleur not in COULEURS:
        raise ErreurMemo("لون غير معروف.")
    vals = (sujet, (m.details or "").strip(), m.date_memo, _heure(m.heure) or None, m.couleur, int(m.fait))
    with conn:
        if m.id:
            conn.execute("UPDATE memo_directeur SET sujet=?, details=?, date_memo=?, heure=?, couleur=?, fait=? "
                         "WHERE id=?", (*vals, m.id))
            return m.id
        return conn.execute("INSERT INTO memo_directeur(sujet, details, date_memo, heure, couleur, fait) "
                            "VALUES (?,?,?,?,?,?)", vals).lastrowid


def _memo(r) -> Memo:
    return Memo(r["sujet"], r["date_memo"], r["heure"] or "", r["details"], r["couleur"], bool(r["fait"]), r["id"])


def lister(conn, inclure_faits: bool = False) -> list[Memo]:
    sql = "SELECT * FROM memo_directeur" + ("" if inclure_faits else " WHERE fait=0")
    return [_memo(r) for r in conn.execute(sql + " ORDER BY date_memo, COALESCE(heure, '99:99'), id")]


def lire(conn, mid: int) -> Memo:
    r = conn.execute("SELECT * FROM memo_directeur WHERE id=?", (mid,)).fetchone()
    if r is None:
        raise ErreurMemo("التذكير غير موجود.")
    return _memo(r)


def marquer_fait(conn, mid: int, fait: bool = True) -> None:
    with conn:
        conn.execute("UPDATE memo_directeur SET fait=? WHERE id=?", (int(fait), mid))


def supprimer(conn, mid: int) -> None:
    with conn:
        conn.execute("DELETE FROM memo_directeur WHERE id=?", (mid,))


def echeance(m: Memo, aujourdhui: date | None = None) -> str:
    """نص قصير: اليوم، غداً، بعد n أيام، أو متأخر."""
    j = aujourdhui or date.today()
    n = (date.fromisoformat(m.date_memo) - j).days
    if n == 0:
        return "اليوم"
    if n == 1:
        return "غداً"
    if n < 0:
        return f"متأخر {-n} يوماً" if n < -1 else "أمس"
    return f"بعد {n} أيام" if n <= 10 else f"بعد {n} يوماً"


def evenements(conn, debut: date, fin: date) -> dict[str, list[tuple[str, str]]]:
    """التاريخ (ISO) ← [(النوع، النص)] بين تاريخين: تذكيرات المدير، ومحطات برنامج العمل السنوي والمقرر الوزاري.
    النوع: memo، ministere، local."""
    res: dict[str, list[tuple[str, str]]] = {}
    for m in lister(conn):
        d = date.fromisoformat(m.date_memo)
        if debut <= d <= fin:
            res.setdefault(m.date_memo, []).append(("memo", f"تذكير{(' ' + m.heure) if m.heure else ''}: {m.sujet}"))
    try:
        from idara.services import calendrier as cal
        stations = cal.stations(conn)
    except Exception:  # noqa: BLE001 — لا سنة جارية أو لا مقرر: اليومية تبقى بالتذكيرات وحدها
        stations = []
    for s in stations:
        d = max(s.debut, debut)
        while d <= min(s.fin, fin):
            res.setdefault(d.isoformat(), []).append(("local" if s.locale else "ministere",
                                                       f"{s.libelle_type}: {s.titre}"))
            d += timedelta(days=1)
    return res
