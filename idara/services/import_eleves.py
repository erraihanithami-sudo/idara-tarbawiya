"""استيراد لوائح مسار إلى القاعدة: تحليل أولاً (دون أي كتابة)، ثم تطبيق بعد موافقة المدير.

القواعد المعتمدة:
- رمز مسار هو مفتاح المطابقة: إعادة الاستيراد تحدّث ولا تكرر.
- لا حذف آلي: الغائب عن اللائحة يُعرض كمغادر محتمل فقط.
- الحقل الذي عدّله المدير يدوياً لا يُمحى بالاستيراد.
- القيمة الفارغة في مسار لا تمحو قيمة موجودة.
- نسخة احتياطية قبل كل استيراد، والتطبيق في معاملة واحدة.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from idara.data.dossier import DossierDonnees
from idara.services import annee as annee_srv
from idara.services import etablissement as etab_srv
from idara.services import massar as ms
from idara.services import sauvegarde

CHAMPS = {"nom_ar": "النسب", "prenom_ar": "الاسم", "nom_fr": "النسب بالفرنسية",
          "prenom_fr": "الاسم بالفرنسية", "sexe": "النوع", "date_naissance": "تاريخ الازدياد",
          "lieu": "مكان الازدياد"}


class ErreurImport(ValueError):
    """رسالة موجهة للمدير بالعربية."""


@dataclass
class Changement:
    champ: str
    ancien: str
    nouveau: str
    verrouille: bool = False


@dataclass
class EleveAnalyse:
    massar: ms.EleveMassar
    eleve_id: int | None = None
    changements: list[Changement] = field(default_factory=list)
    ancienne_classe: str | None = None

    @property
    def nom(self) -> str:
        return f"{self.massar.prenom_ar or self.massar.prenom_fr} {self.massar.nom_ar or self.massar.nom_fr}".strip()


@dataclass
class RapportImport:
    liste: ms.ListeMassar
    annee: str
    nouvelle_annee: bool
    nouveaux: list[EleveAnalyse]
    mis_a_jour: list[EleveAnalyse]
    inchanges: int
    changements_classe: list[EleveAnalyse]
    absents: list[sqlite3.Row]
    alertes: list[str]
    fichiers: list[str]

    @property
    def nb_eleves(self) -> int:
        return len(self.liste.eleves)


def _lieu_existant(conn, nom_ar: str):
    return conn.execute("SELECT * FROM lieu WHERE nom_ar=?", (nom_ar,)).fetchone() if nom_ar else None


def analyser(conn: sqlite3.Connection, chemins: list[Path | str]) -> RapportImport:
    """يقرأ اللوائح ويقارنها بالقاعدة دون أي كتابة."""
    fichiers = [ms.lire_fichier(c) for c in chemins]
    liste = ms.fusionner(fichiers)
    alertes = list(liste.alertes)

    courante = annee_srv.annee_courante(conn)
    if courante is None:
        raise ErreurImport("لا توجد سنة دراسية جارية. أكمل إعداد المؤسسة أولاً.")
    annee = liste.annee or courante["libelle"]
    try:
        annee_srv.code_court(annee)
    except annee_srv.ErreurAnnee as e:
        raise ErreurImport(f"السنة الدراسية في اللائحة غير مفهومة: {annee}") from e
    if annee < courante["libelle"]:
        raise ErreurImport(f"اللائحة تخص السنة الدراسية {annee}، وهي أقدم من السنة الجارية "
                           f"{courante['libelle']}. لا يمكن استيرادها.")
    nouvelle_annee = annee > courante["libelle"]

    etab = etab_srv.lire_etablissement(conn)
    if etab and liste.etablissement and \
            ms.normaliser(liste.etablissement) not in ms.normaliser(etab.nom_ar):
        alertes.append(f"اسم المؤسسة في اللائحة «{liste.etablissement}» لا يطابق اسمها في الإعداد "
                       f"«{etab.nom_ar}». تأكد أنها لائحة مؤسستك.")

    a = conn.execute("SELECT id FROM annee_scolaire WHERE libelle=?", (annee,)).fetchone()
    annee_id = a["id"] if a else None

    nouveaux, mis_a_jour, changements_classe = [], [], []
    inchanges = 0
    for code, m in liste.eleves.items():
        row = conn.execute(
            "SELECT e.*, l.nom_ar AS lieu_ar FROM eleve e LEFT JOIN lieu l ON l.id=e.lieu_naissance_id "
            "WHERE e.code_massar=?", (code,)).fetchone()
        if row is None:
            nouveaux.append(EleveAnalyse(m))
            if not m.lieu_ar:
                alertes.append(f"{code} ({m.prenom_ar} {m.nom_ar}): مكان الازدياد فارغ في مسار.")
            continue
        verrous = set(json.loads(row["champs_verrouilles"] or "[]"))
        an = EleveAnalyse(m, row["id"])
        valeurs = {"nom_ar": m.nom_ar, "prenom_ar": m.prenom_ar, "nom_fr": m.nom_fr,
                   "prenom_fr": m.prenom_fr, "sexe": m.sexe, "date_naissance": m.date_naissance,
                   "lieu": m.lieu_ar}
        actuels = {**{k: row[k] for k in valeurs if k != "lieu"}, "lieu": row["lieu_ar"]}
        for champ, nouveau in valeurs.items():
            if nouveau and (actuels[champ] or "") != nouveau:
                an.changements.append(Changement(champ, actuels[champ] or "", nouveau, champ in verrous))
        if annee_id is not None:
            ins = conn.execute(
                "SELECT c.code FROM inscription i LEFT JOIN classe c ON c.id=i.classe_id "
                "WHERE i.eleve_id=? AND i.annee_id=?", (row["id"], annee_id)).fetchone()
            if ins and ins["code"] and ins["code"] != m.classe:
                an.ancienne_classe = ins["code"]
                changements_classe.append(an)
        if any(not c.verrouille for c in an.changements):
            mis_a_jour.append(an)
        else:
            inchanges += 1
        for c in an.changements:
            if c.verrouille:
                alertes.append(f"{code}: {CHAMPS[c.champ]} معدّل يدوياً ({c.ancien}) ويختلف عن مسار "
                               f"({c.nouveau}): أُبقي على التعديل اليدوي.")

    absents = []
    if annee_id is not None and liste.classes:
        marques = ",".join("?" for _ in liste.classes)
        for r in conn.execute(
                f"SELECT i.id, e.code_massar, e.nom_ar, e.prenom_ar, c.code AS classe "
                f"FROM inscription i JOIN eleve e ON e.id=i.eleve_id JOIN classe c ON c.id=i.classe_id "
                f"WHERE i.annee_id=? AND i.statut IN ('inscrit','arrive') AND c.code IN ({marques})",
                (annee_id, *liste.classes)):
            if r["code_massar"] not in liste.eleves:
                absents.append(r)

    return RapportImport(liste, annee, nouvelle_annee, nouveaux, mis_a_jour, inchanges,
                         changements_classe, absents, alertes, [Path(c).name for c in chemins])


# ---------- التطبيق ----------

def _lieu_id(conn, nom_ar: str, nom_fr: str) -> int | None:
    if not nom_ar:
        return None
    l = _lieu_existant(conn, nom_ar)
    if l is None:
        return conn.execute("INSERT INTO lieu(nom_ar, nom_fr) VALUES (?,?)",
                            (nom_ar, nom_fr or None)).lastrowid
    if nom_fr and not l["nom_fr"]:
        conn.execute("UPDATE lieu SET nom_fr=? WHERE id=?", (nom_fr, l["id"]))
    return l["id"]


def _ecritures_majoritaires(liste: ms.ListeMassar) -> dict[str, str]:
    from collections import Counter
    votes: dict[str, Counter] = {}
    for m in liste.eleves.values():
        if m.lieu_ar and m.lieu_fr:
            votes.setdefault(m.lieu_ar, Counter())[m.lieu_fr] += 1
    return {ar: c.most_common(1)[0][0] for ar, c in votes.items()}


def _niveau_id(conn, code: str | None) -> int | None:
    if not code:
        return None
    r = conn.execute("SELECT id FROM niveau WHERE code=?", (code,)).fetchone()
    return r["id"] if r else None


def _proposition(conn, eleve_id: int | None, classe: str, date_naissance: str | None,
                 annee: str) -> tuple[str | None, bool]:
    """المستوى المقترح: المستوى المؤكد في السنة السابقة + 1 إن كان ضمن مستويات القسم،
    وإلا حسب السن. يعيد (المستوى، مؤكد؟)."""
    candidats = ms.niveaux_du_code_classe(classe)
    if len(candidats) == 1:
        return candidats[0], True
    if eleve_id is not None:
        prec = conn.execute(
            "SELECT n.code FROM inscription i JOIN annee_scolaire a ON a.id=i.annee_id "
            "JOIN niveau n ON n.id=i.niveau_id WHERE i.eleve_id=? AND i.niveau_confirme=1 "
            "AND a.libelle<? ORDER BY a.libelle DESC LIMIT 1", (eleve_id, annee)).fetchone()
        if prec and prec["code"] in ms.ORDRE:
            i = ms.ORDRE.index(prec["code"])
            suivant = ms.ORDRE[min(i + 1, len(ms.ORDRE) - 1)]
            if suivant in candidats:
                return suivant, False
    niveau, _ = ms.proposer_niveau(classe, date_naissance, int(annee[:4]))
    return niveau, False


@dataclass
class ResultatImport:
    lot_id: int
    ajoutes: int
    mis_a_jour: int
    sauvegarde: Path


def appliquer(conn: sqlite3.Connection, dossier: DossierDonnees, rapport: RapportImport) -> ResultatImport:
    copie = sauvegarde.creer_sauvegarde(dossier, "avant_import")
    liste = rapport.liste
    with conn:
        if rapport.nouvelle_annee:
            conn.execute("UPDATE annee_scolaire SET est_courante=0 WHERE est_courante=1")
            a = conn.execute("SELECT id FROM annee_scolaire WHERE libelle=?", (rapport.annee,)).fetchone()
            if a:
                annee_id = a["id"]
                conn.execute("UPDATE annee_scolaire SET est_courante=1 WHERE id=?", (annee_id,))
            else:
                annee_id = conn.execute(
                    "INSERT INTO annee_scolaire(libelle, code_court, est_courante) VALUES (?,?,1)",
                    (rapport.annee, annee_srv.code_court(rapport.annee))).lastrowid
        else:
            annee_id = conn.execute("SELECT id FROM annee_scolaire WHERE libelle=?",
                                    (rapport.annee,)).fetchone()["id"]

        classes = {}
        for code in liste.classes:
            r = conn.execute("SELECT id FROM classe WHERE annee_id=? AND code=?", (annee_id, code)).fetchone()
            classes[code] = r["id"] if r else conn.execute(
                "INSERT INTO classe(annee_id, code) VALUES (?,?)", (annee_id, code)).lastrowid

        majoritaires = _ecritures_majoritaires(liste)
        ajoutes = 0
        for an in rapport.nouveaux:
            m = an.massar
            eid = conn.execute(
                "INSERT INTO eleve(code_massar, nom_ar, prenom_ar, nom_fr, prenom_fr, sexe, date_naissance,"
                " lieu_naissance_id, source) VALUES (?,?,?,?,?,?,?,?,'massar')",
                (m.code, m.nom_ar or m.nom_fr, m.prenom_ar or m.prenom_fr, m.nom_fr or None,
                 m.prenom_fr or None, m.sexe, m.date_naissance,
                 _lieu_id(conn, m.lieu_ar, majoritaires.get(m.lieu_ar, m.lieu_fr)))
            ).lastrowid
            an.eleve_id = eid
            ajoutes += 1

        maj = 0
        for an in rapport.mis_a_jour:
            sets, vals = [], []
            for c in an.changements:
                if c.verrouille:
                    continue
                if c.champ == "lieu":
                    sets.append("lieu_naissance_id=?")
                    vals.append(_lieu_id(conn, c.nouveau, an.massar.lieu_fr))
                else:
                    sets.append(f"{c.champ}=?")
                    vals.append(c.nouveau)
            if sets:
                conn.execute(f"UPDATE eleve SET {', '.join(sets)}, modifie_le=datetime('now','localtime') "
                             f"WHERE id=?", (*vals, an.eleve_id))
                maj += 1
        # المكان بالفرنسية: الكتابة الأكثر تكراراً في اللائحة لكل مكان (TAFOUGHALT/TAFOUGHALTE...)
        for nom_ar, nom_fr in _ecritures_majoritaires(liste).items():
            _lieu_id(conn, nom_ar, nom_fr)

        for code, m in liste.eleves.items():
            eid = conn.execute("SELECT id FROM eleve WHERE code_massar=?", (code,)).fetchone()["id"]
            ins = conn.execute("SELECT * FROM inscription WHERE eleve_id=? AND annee_id=?",
                               (eid, annee_id)).fetchone()
            if ins is None:
                niveau, confirme = _proposition(conn, eid, m.classe, m.date_naissance, rapport.annee)
                conn.execute(
                    "INSERT INTO inscription(eleve_id, annee_id, classe_id, niveau_id, niveau_confirme, statut)"
                    " VALUES (?,?,?,?,?,'inscrit')",
                    (eid, annee_id, classes[m.classe], _niveau_id(conn, niveau), int(confirme)))
            elif ins["classe_id"] != classes[m.classe]:
                if ins["niveau_confirme"]:
                    conn.execute("UPDATE inscription SET classe_id=? WHERE id=?",
                                 (classes[m.classe], ins["id"]))
                else:
                    niveau, confirme = _proposition(conn, eid, m.classe, m.date_naissance, rapport.annee)
                    conn.execute("UPDATE inscription SET classe_id=?, niveau_id=?, niveau_confirme=? "
                                 "WHERE id=?", (classes[m.classe], _niveau_id(conn, niveau),
                                                int(confirme), ins["id"]))

        resume = {"fichiers": rapport.fichiers, "langues": liste.langues, "annee": rapport.annee,
                  "nouveaux": [a.massar.code for a in rapport.nouveaux],
                  "mis_a_jour": [a.massar.code for a in rapport.mis_a_jour],
                  "absents": [r["code_massar"] for r in rapport.absents],
                  "alertes": rapport.alertes}
        lot_id = conn.execute(
            "INSERT INTO import_lot(fichier, langue, annee_id, nb_ajoutes, nb_mis_a_jour, nb_absents,"
            " nb_alertes, rapport) VALUES (?,?,?,?,?,?,?,?)",
            (" + ".join(rapport.fichiers), "ar" if "ar" in liste.langues else "fr", annee_id, ajoutes,
             maj, len(rapport.absents), len(rapport.alertes), json.dumps(resume, ensure_ascii=False))
        ).lastrowid
        conn.execute("INSERT INTO journal(action, cible, cible_id, details) VALUES ('import','import_lot',?,?)",
                     (lot_id, f"{ajoutes} جديد، {maj} محدث، {len(rapport.absents)} غائب"))
    return ResultatImport(lot_id, ajoutes, maj, copie)


# ---------- تأكيد المستوى ----------

def niveaux_a_confirmer(conn: sqlite3.Connection, annee_id: int | None = None) -> list[sqlite3.Row]:
    if annee_id is None:
        a = annee_srv.annee_courante(conn)
        if a is None:
            return []
        annee_id = a["id"]
    return conn.execute(
        "SELECT i.id AS inscription_id, e.code_massar, e.nom_ar, e.prenom_ar, e.date_naissance, "
        "c.code AS classe, n.code AS niveau, a.libelle AS annee FROM inscription i "
        "JOIN eleve e ON e.id=i.eleve_id JOIN classe c ON c.id=i.classe_id "
        "JOIN annee_scolaire a ON a.id=i.annee_id LEFT JOIN niveau n ON n.id=i.niveau_id "
        "WHERE i.annee_id=? AND i.niveau_confirme=0 AND i.statut IN ('inscrit','arrive') "
        "ORDER BY c.code, e.date_naissance, e.nom_ar", (annee_id,)).fetchall()


def age_hors_norme(niveau: str | None, date_naissance: str | None, annee: str) -> bool:
    if not niveau or not date_naissance or niveau not in ms.AGE_NORMAL:
        return False
    return abs(int(annee[:4]) - int(date_naissance[:4]) - ms.AGE_NORMAL[niveau]) > 1


def confirmer_niveaux(conn: sqlite3.Connection, choix: dict[int, str]) -> int:
    """{inscription_id: رمز المستوى}. يعيد عدد التأكيدات."""
    n = 0
    with conn:
        for ins_id, code in choix.items():
            nid = _niveau_id(conn, code)
            if nid is None:
                raise ErreurImport(f"مستوى غير معروف: {code}")
            n += conn.execute("UPDATE inscription SET niveau_id=?, niveau_confirme=1 WHERE id=?",
                              (nid, ins_id)).rowcount
        conn.execute("INSERT INTO journal(action, cible, details) VALUES ('confirmation_niveau','inscription',?)",
                     (f"{n} تلميذ",))
    return n


def historique(conn: sqlite3.Connection, limite: int = 10) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM import_lot ORDER BY id DESC LIMIT ?", (limite,)).fetchall()

