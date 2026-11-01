"""تتبع سلوك التلاميذ: ملاحظات مؤرخة، والإجراء المتخذ، واستدعاء ولي الأمر منها.

لا تصنيف رسمي مفترض للمخالفات: طبيعة الملاحظة والإجراء نص حر، ويقترح التطبيق ما سبق إدخاله.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date

from idara.data.dossier import DossierDonnees
from idara.services import annee as annee_srv
from idara.services import documents as dc
from idara.services import eleves as el


class ErreurComportement(ValueError):
    """رسالة موجهة للمدير بالعربية."""


@dataclass
class Observation:
    eleve_id: int
    date_obs: str
    nature: str
    description: str = ""
    signale_par: str = ""
    mesure: str = ""
    id: int | None = None

    def valider(self) -> None:
        for k in ("nature", "description", "signale_par", "mesure"):
            setattr(self, k, " ".join((getattr(self, k) or "").split()))
        if not self.nature:
            raise ErreurComportement("طبيعة الملاحظة إجبارية.")
        try:
            d = date.fromisoformat(self.date_obs)
        except (TypeError, ValueError):
            raise ErreurComportement("تاريخ الملاحظة غير صحيح.") from None
        if d > date.today():
            raise ErreurComportement("تاريخ الملاحظة في المستقبل.")


def _annee(conn):
    a = annee_srv.annee_courante(conn)
    if a is None:
        raise ErreurComportement("لا توجد سنة دراسية جارية.")
    return a


def enregistrer(conn: sqlite3.Connection, o: Observation) -> int:
    o.valider()
    if el.fiche(conn, o.eleve_id)["inscription_id"] is None:
        raise ErreurComportement("التلميذ غير مسجل في السنة الجارية.")
    a = _annee(conn)
    vals = (o.date_obs, o.nature, o.description or None, o.signale_par or None, o.mesure or None)
    with conn:
        if o.id is None:
            o.id = conn.execute(
                "INSERT INTO observation_comportement(eleve_id, annee_id, date_obs, nature, description, signale_par,"
                " mesure) VALUES (?,?,?,?,?,?,?)", (o.eleve_id, a["id"], *vals)).lastrowid
        else:
            conn.execute("UPDATE observation_comportement SET date_obs=?, nature=?, description=?, signale_par=?, "
                         "mesure=? WHERE id=?", (*vals, o.id))
    return o.id


def supprimer(conn: sqlite3.Connection, obs_id: int) -> None:
    """حذف ملاحظة سُجلت خطأً (لا تُحذف إن صدر عنها استدعاء)."""
    r = conn.execute("SELECT convocation_document_id FROM observation_comportement WHERE id=?", (obs_id,)).fetchone()
    if r is None:
        raise ErreurComportement("الملاحظة غير موجودة.")
    if r[0]:
        raise ErreurComportement("صدر عن هذه الملاحظة استدعاء: لا تُحذف.")
    with conn:
        conn.execute("DELETE FROM observation_comportement WHERE id=?", (obs_id,))


def observations(conn: sqlite3.Connection, eleve_id: int) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM observation_comportement WHERE eleve_id=? AND annee_id=? "
                        "ORDER BY date_obs DESC, id DESC", (eleve_id, _annee(conn)["id"])).fetchall()


def recapitulatif(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """التلاميذ الذين لهم ملاحظات هذه السنة، الأكثر أولاً."""
    return conn.execute(
        "SELECT e.id, e.code_massar, e.nom_ar, e.prenom_ar, COUNT(o.id) AS n, MAX(o.date_obs) AS derniere, "
        "SUM(o.convocation_document_id IS NOT NULL) AS convocations "
        "FROM observation_comportement o JOIN eleve e ON e.id=o.eleve_id WHERE o.annee_id=? "
        "GROUP BY e.id ORDER BY n DESC, derniere DESC", (_annee(conn)["id"],)).fetchall()


def suggestions(conn: sqlite3.Connection, champ: str) -> list[str]:
    if champ not in ("nature", "mesure", "signale_par"):
        raise ValueError(champ)
    return [r[0] for r in conn.execute(
        f"SELECT {champ}, COUNT(*) n FROM observation_comportement WHERE {champ} IS NOT NULL "
        f"GROUP BY {champ} ORDER BY n DESC")]


def convoquer(conn: sqlite3.Connection, dossier: DossierDonnees, obs_id: int,
              le: str | None = None) -> dc.DocumentGenere:
    """استدعاء ولي الأمر انطلاقاً من ملاحظة؛ يُربط بها ويُسجل في وثائق التلميذ."""
    r = conn.execute("SELECT * FROM observation_comportement WHERE id=?", (obs_id,)).fetchone()
    if r is None:
        raise ErreurComportement("الملاحظة غير موجودة.")
    try:
        doc = el.generer_convocations(conn, dossier, [r["eleve_id"]])[0]
    except el.ErreurEleve as e:
        raise ErreurComportement(str(e)) from None
    with conn:
        conn.execute("UPDATE observation_comportement SET convocation_document_id=?, date_convocation=?, "
                     "mesure=COALESCE(mesure, 'استدعاء ولي الأمر') WHERE id=?",
                     (doc.id, le or date.today().isoformat(), obs_id))
    return doc
