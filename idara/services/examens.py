"""الامتحان الموحد لنيل شهادة السلك الابتدائي: المحلي والإقليمي (تطبيق الامتحان الذي أرسله المدير، 2026-11-03).

- المحلي: المترشحون تلاميذ السادس من لوائح المؤسسة (مسار)، يُرقَّمون من الرقم الأول المختار ويوزعون على القاعات.
- الإقليمي: المترشحون من اللائحة التي تبعثها المديرية الإقليمية، بأرقامها كما هي (قد تبدأ بأي رقم حسب ترتيب
  المؤسسة في الإقليم) وبقاعاتها إن وُجدت في الملف. الأعمدة تُعرف من عناوينها (نموذج المديرية بانتظار المدير).
- المكلفون: رئيس المركز، مراقب جودة الإجراء، أعضاء الكتابة، المداومون لكل مادة، والمراقبون في القاعات.
"""

from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from idara.services import annee as annee_srv
from idara.services import etablissement as etab_srv
from idara.services.massar import MOTIF_CODE, normaliser

TYPES = {"local": "الامتحان الموحد المحلي", "provincial": "الامتحان الموحد الإقليمي"}
INTITULES = {t: f"{lib} لنيل شهادة السلك الابتدائي" for t, lib in TYPES.items()}
ROLES = ("رئيس(ة) مركز الامتحان", "مراقب(ة) جودة الإجراء", "عضو(ة) كتابة الامتحان", "أستاذ(ة) مداوم(ة)")
SURVEILLANCE = "مراقب(ة)"
MATIERES_SUGGEREES = ("اللغة العربية", "اللغة الفرنسية", "الرياضيات", "النشاط العلمي", "التربية الإسلامية",
                      "الاجتماعيات")


class ErreurExamen(ValueError):
    """رسالة موجهة للمدير بالعربية."""


def _annee(conn):
    a = annee_srv.annee_courante(conn)
    if a is None:
        raise ErreurExamen("لا سنة دراسية جارية.")
    return a


def examen(conn, type_: str) -> sqlite3.Row:
    """امتحان السنة الجارية من هذا النوع (يُنشأ بالقيم الافتراضية عند أول فتح)."""
    if type_ not in TYPES:
        raise ErreurExamen("نوع الامتحان: المحلي أو الإقليمي.")
    a = _annee(conn)
    r = conn.execute("SELECT * FROM examen WHERE annee_id=? AND type=?", (a["id"], type_)).fetchone()
    if r is None:
        etab = etab_srv.lire_etablissement(conn)
        fin = a["libelle"][-4:]
        with conn:
            conn.execute("INSERT INTO examen(annee_id, type, intitule, session, centre, code_centre) VALUES (?,?,?,?,?,?)",
                         (a["id"], type_, INTITULES[type_], f"يونيو {fin}", etab.nom_ar if etab else "",
                          (etab.code_etab if etab else "") or None))
        r = conn.execute("SELECT * FROM examen WHERE annee_id=? AND type=?", (a["id"], type_)).fetchone()
    return r


def modifier(conn, eid: int, intitule: str, session: str, centre: str, code_centre: str = "",
             premier_numero: int | str = 1, capacite: int | str = 20) -> None:
    intitule, session, centre = (" ".join((x or "").split()) for x in (intitule, session, centre))
    if not intitule or not centre:
        raise ErreurExamen("اسم الامتحان ومركز الامتحان إجباريان.")
    try:
        premier_numero, capacite = int(premier_numero), int(capacite)
    except (TypeError, ValueError):
        raise ErreurExamen("الرقم الأول وطاقة القاعة: أعداد صحيحة.") from None
    if premier_numero < 1 or not 1 <= capacite <= 60:
        raise ErreurExamen("الرقم الأول 1 فما فوق، وطاقة القاعة بين 1 و60.")
    with conn:
        conn.execute("UPDATE examen SET intitule=?, session=?, centre=?, code_centre=?, premier_numero=?, capacite=? "
                     "WHERE id=?", (intitule, session or None, centre, code_centre.strip() or None, premier_numero,
                                    capacite, eid))


# ---------- الجدولة ----------

def matieres(conn, eid: int) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM examen_matiere WHERE examen_id=? ORDER BY jour, debut, ordre", (eid,)).fetchall()


def _heure(v: str, lib: str) -> str:
    v = (v or "").strip().replace("h", ":").replace("س", ":")
    try:
        h, m = (int(x) for x in v.split(":"))
    except ValueError:
        raise ErreurExamen(f"{lib}: الساعة بصيغة 08:30.") from None
    if not (0 <= h < 24 and 0 <= m < 60):
        raise ErreurExamen(f"{lib}: ساعة غير صحيحة.")
    return f"{h:02d}:{m:02d}"


def definir_matieres(conn, eid: int, lignes: list[dict]) -> None:
    """يستبدل الجدولة. كل سطر: المادة، اليوم (YYYY-MM-DD)، من، إلى. المراقبة المرتبطة بمادة محذوفة تُحذف."""
    propres = []
    for i, l in enumerate(lignes):
        m = " ".join((l.get("matiere") or "").split())
        if not m and not l.get("jour"):
            continue
        if not m:
            raise ErreurExamen(f"السطر {i + 1}: المادة فارغة.")
        try:
            date.fromisoformat(l.get("jour") or "")
        except ValueError:
            raise ErreurExamen(f"{m}: تاريخ الاختبار غير صحيح.") from None
        debut, fin = _heure(l.get("debut"), f"{m} (من)"), _heure(l.get("fin"), f"{m} (إلى)")
        if fin <= debut:
            raise ErreurExamen(f"{m}: ساعة النهاية قبل ساعة البداية.")
        propres.append((m, l["jour"], debut, fin, l.get("id")))
    vus = set()
    for m, j, d, f, _ in propres:
        if (m, j) in vus:
            raise ErreurExamen(f"المادة {m} مكررة في نفس اليوم.")
        vus.add((m, j))
    with conn:
        gardes = [p[4] for p in propres if p[4]]
        if gardes:
            conn.execute(f"DELETE FROM examen_matiere WHERE examen_id=? AND id NOT IN ({','.join('?' * len(gardes))})",
                         (eid, *gardes))
        else:
            conn.execute("DELETE FROM examen_matiere WHERE examen_id=?", (eid,))
        for k, (m, j, d, f, mid) in enumerate(propres):
            if mid:
                conn.execute("UPDATE examen_matiere SET matiere=?, jour=?, debut=?, fin=?, ordre=? WHERE id=? AND examen_id=?",
                             (m, j, d, f, k, mid, eid))
            else:
                conn.execute("INSERT INTO examen_matiere(examen_id, matiere, jour, debut, fin, ordre) VALUES (?,?,?,?,?,?)",
                             (eid, m, j, d, f, k))


# ---------- المترشحون والقاعات ----------

def salles(conn, eid: int) -> list[sqlite3.Row]:
    return conn.execute("SELECT s.*, (SELECT COUNT(*) FROM examen_candidat c WHERE c.salle_id=s.id) AS n "
                        "FROM examen_salle s WHERE s.examen_id=? ORDER BY s.numero", (eid,)).fetchall()


def candidats(conn, eid: int, salle_id: int | None = None) -> list[sqlite3.Row]:
    sql = ("SELECT c.*, s.numero AS salle_numero, s.nom AS salle_nom FROM examen_candidat c "
           "LEFT JOIN examen_salle s ON s.id=c.salle_id WHERE c.examen_id=?")
    args: list = [eid]
    if salle_id is not None:
        sql += " AND c.salle_id=?"
        args.append(salle_id)
    return conn.execute(sql + " ORDER BY c.numero", args).fetchall()


def _remplacer(conn, eid: int, lignes: list[dict], noms_salles: dict[int, str]) -> None:
    conn.execute("DELETE FROM examen_candidat WHERE examen_id=?", (eid,))
    conn.execute("DELETE FROM examen_salle WHERE examen_id=?", (eid,))
    ids = {}
    for num, nom in sorted(noms_salles.items()):
        ids[num] = conn.execute("INSERT INTO examen_salle(examen_id, numero, nom) VALUES (?,?,?)",
                                (eid, num, nom)).lastrowid
    for l in lignes:
        e = conn.execute("SELECT id FROM eleve WHERE code_massar=?", (l.get("code"),)).fetchone() if l.get("code") else None
        conn.execute("INSERT INTO examen_candidat(examen_id, numero, salle_id, code_massar, eleve_id, nom, sexe, "
                     "date_naissance, classe) VALUES (?,?,?,?,?,?,?,?,?)",
                     (eid, l["numero"], ids.get(l.get("salle")), l.get("code") or None, e[0] if e else None, l["nom"],
                      l.get("sexe") or None, l.get("date_naissance") or None, l.get("classe") or None))


def preparer_local(conn, eid: int) -> int:
    """المحلي: تلاميذ السادس (يتابعون دراستهم أو وافدون) مرتبين حسب القسم ثم الاسم، مرقمين من الرقم الأول،
    موزعين على القاعات حسب طاقتها. يعوض اللائحة السابقة."""
    ex = conn.execute("SELECT * FROM examen WHERE id=?", (eid,)).fetchone()
    if ex is None or ex["type"] != "local":
        raise ErreurExamen("هذا خاص بالامتحان المحلي.")
    rows = conn.execute(
        "SELECT e.code_massar, e.nom_ar, e.prenom_ar, e.sexe, e.date_naissance, c.code AS classe FROM inscription i "
        "JOIN eleve e ON e.id=i.eleve_id JOIN niveau n ON n.id=i.niveau_id LEFT JOIN classe c ON c.id=i.classe_id "
        "WHERE i.annee_id=? AND n.code='6AP' AND i.statut IN ('inscrit','arrive') ORDER BY c.code, e.nom_ar, e.prenom_ar",
        (ex["annee_id"],)).fetchall()
    if not rows:
        raise ErreurExamen("لا تلاميذ في المستوى السادس في لوائح السنة الجارية (استورد لوائح مسار وأكد المستويات).")
    cap = ex["capacite"]
    lignes = [{"numero": ex["premier_numero"] + k, "salle": k // cap + 1, "code": r["code_massar"],
               "nom": f"{r['nom_ar']} {r['prenom_ar']}", "sexe": r["sexe"], "date_naissance": r["date_naissance"],
               "classe": r["classe"]} for k, r in enumerate(rows)]
    with conn:
        _remplacer(conn, eid, lignes, {k: f"القاعة {k}" for k in range(1, math.ceil(len(rows) / cap) + 1)})
    return len(rows)


@dataclass
class RapportListe:
    n: int
    salles: int
    hors_lister: list[str] = field(default_factory=list)   # رموز غير موجودة في لوائح المؤسسة
    alertes: list[str] = field(default_factory=list)


_ALIAS = {
    "numero": ("رقمالامتحان", "رقمالامتحان", "numeroexamen", "nexamen"),
    "code": ("الرقمالوطني", "رمزمسار", "رمزالتلميذ", "الرمز", "رقممسار", "codemassar", "code"),
    "nom_complet": ("الاسمالكامل", "اسمالتلميذ", "الاسموالنسب", "النسبوالاسم"),
    "nom": ("النسب", "الاسمالعائلي", "nom"),
    "prenom": ("الاسم", "الاسمالشخصي", "prenom"),
    "sexe": ("الجنس", "النوع", "genre", "sexe"),
    "naissance": ("تاريخالازدياد", "تاريخالإزدياد", "datedenaissance"),
    "salle": ("قاعةالامتحان", "القاعة", "رقمالقاعة", "قاعة", "salle"),
    "classe": ("القسم", "classe"),
    "etablissement": ("المؤسسة", "مؤسسةالتلميذ"),
}


def _sexe(v) -> str | None:
    t = normaliser(v)
    if t in ("ذكر", "m", "garcon", "garçon", "masculin"):
        return "M"
    if t in ("انثى", "أنثى", "f", "fille", "feminin", "féminin"):
        return "F"
    return None


def _date(v) -> str | None:
    if v in (None, ""):
        return None
    if hasattr(v, "date"):
        return v.date().isoformat()
    t = str(v).strip().replace("/", "-")
    p = t.split("-")
    if len(p) == 3 and len(p[0]) == 4:
        return f"{p[0]}-{int(p[1]):02d}-{int(p[2]):02d}"
    if len(p) == 3 and len(p[2]) == 4:
        return f"{p[2]}-{int(p[1]):02d}-{int(p[0]):02d}"
    return None


def lire_liste_provinciale(chemin: Path) -> tuple[list[dict], dict[int, str], list[str]]:
    """يقرأ لائحة المديرية: يبحث عن سطر العناوين الذي فيه «رقم الامتحان» ويعرف الأعمدة من أسمائها."""
    import openpyxl
    try:
        wb = openpyxl.load_workbook(chemin, read_only=True, data_only=True)
    except Exception as e:  # noqa: BLE001
        raise ErreurExamen(f"تعذرت قراءة الملف {Path(chemin).name}: ليس ملف Excel صالحاً.") from e
    lignes, noms_salles, alertes = [], {}, []
    for ws in wb.worksheets:
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
        ent = next((i for i, r in enumerate(rows) if any(normaliser(c) in _ALIAS["numero"] for c in r)), None)
        if ent is None:
            continue
        tete = [normaliser(c) for c in rows[ent]]
        col = {}
        for k, alias in _ALIAS.items():
            j = next((j for j, h in enumerate(tete) if h in alias), None)
            if j is not None:
                col[k] = j
        if "nom_complet" not in col and "nom" not in col:
            raise ErreurExamen("عمود اسم المترشح غير موجود في اللائحة.")
        auto_salle = {}
        for r in rows[ent + 1:]:
            v = lambda k: r[col[k]] if k in col and col[k] < len(r) else None  # noqa: E731
            try:
                numero = int(float(str(v("numero")).strip()))
            except (TypeError, ValueError):
                continue
            nom = " ".join(str(v("nom_complet") or "").split()) or " ".join(
                f"{v('nom') or ''} {v('prenom') or ''}".split())
            if not nom:
                continue
            code = str(v("code") or "").strip().upper()
            if code and not MOTIF_CODE.match(code):
                alertes.append(f"رمز غير صالح «{code}» للمترشح {numero}.")
                code = ""
            salle = None
            sv = v("salle")
            if sv not in (None, ""):
                t = str(sv).strip()
                tete_num = t.split("-")[0].strip()
                if tete_num.replace(".", "").isdigit():
                    salle = int(float(tete_num))
                    noms_salles.setdefault(salle, t.split("-", 1)[1].strip() if "-" in t else f"القاعة {salle}")
                else:
                    salle = auto_salle.setdefault(t, len(auto_salle) + 1)
                    noms_salles.setdefault(salle, t)
            lignes.append({"numero": numero, "code": code, "nom": nom, "sexe": _sexe(v("sexe")),
                           "date_naissance": _date(v("naissance")), "salle": salle,
                           "classe": str(v("classe") or "").strip() or None,
                           "etablissement": str(v("etablissement") or "").strip()})
    if not lignes:
        raise ErreurExamen("لم يُعثر على مترشحين: يلزم عمود «رقم الامتحان» وعمود اسم المترشح.")
    doublons = sorted({l["numero"] for l in lignes if sum(x["numero"] == l["numero"] for x in lignes) > 1})
    if doublons:
        raise ErreurExamen("أرقام امتحان مكررة في اللائحة: " + "، ".join(map(str, doublons[:10])))
    return lignes, noms_salles, alertes


def importer_provincial(conn, eid: int, chemin: Path) -> RapportListe:
    """الإقليمي: أرقام الامتحان والقاعات كما في ملف المديرية. القاعات غير المحددة: حسب الطاقة وبترتيب الأرقام."""
    ex = conn.execute("SELECT * FROM examen WHERE id=?", (eid,)).fetchone()
    if ex is None or ex["type"] != "provincial":
        raise ErreurExamen("هذا خاص بالامتحان الإقليمي.")
    lignes, noms_salles, alertes = lire_liste_provinciale(chemin)
    lignes.sort(key=lambda l: l["numero"])
    if any(l["salle"] is None for l in lignes):
        base = max(noms_salles, default=0)
        sans = [l for l in lignes if l["salle"] is None]
        for k, l in enumerate(sans):
            l["salle"] = base + k // ex["capacite"] + 1
            noms_salles.setdefault(l["salle"], f"القاعة {l['salle']}")
        alertes.append(f"{len(sans)} مترشحاً دون قاعة في الملف: وُزعوا حسب طاقة القاعة.")
    connus = {r[0] for r in conn.execute("SELECT code_massar FROM eleve WHERE code_massar IS NOT NULL")}
    with conn:
        _remplacer(conn, eid, lignes, noms_salles)
        conn.execute("INSERT INTO journal(action, cible, details) VALUES ('import','examen_provincial',?)",
                     (f"{len(lignes)} مترشحاً، الأرقام {lignes[0]['numero']}–{lignes[-1]['numero']}",))
    return RapportListe(len(lignes), len(noms_salles),
                        [f"{l['nom']} ({l['code']})" for l in lignes if l["code"] and l["code"] not in connus], alertes)


# ---------- المكلفون ----------

def enseignants(conn) -> list[sqlite3.Row]:
    return conn.execute("SELECT id, prenom_ar, nom_ar, ppr, cadre, matiere, categorie FROM personnel "
                        "WHERE statut='actif' AND categorie IN ('enseignant','educatrice','directeur') "
                        "ORDER BY categorie='directeur' DESC, nom_ar, prenom_ar").fetchall()


def affectations(conn, eid: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT a.*, s.numero AS salle_numero, m.matiere, m.jour, m.debut, m.fin FROM examen_affectation a "
        "LEFT JOIN examen_salle s ON s.id=a.salle_id LEFT JOIN examen_matiere m ON m.id=a.matiere_id "
        "WHERE a.examen_id=? ORDER BY a.role, m.jour, m.debut, s.numero, a.nom", (eid,)).fetchall()


def _personne(conn, pid: int) -> sqlite3.Row:
    r = conn.execute("SELECT id, prenom_ar, nom_ar, ppr, cadre FROM personnel WHERE id=?", (pid,)).fetchone()
    if r is None:
        raise ErreurExamen("الموظف غير موجود.")
    return r


def definir_roles(conn, eid: int, roles: dict[str, list[int]], mudawimun: dict[int, int | None]) -> None:
    """المهام العامة (رئيس المركز، مراقب الجودة، الكتابة) والمداوم لكل مادة (matiere_id ← personnel_id)."""
    for r in roles:
        if r not in ROLES:
            raise ErreurExamen(f"مهمة غير معروفة: {r}")
    if len(roles.get(ROLES[0], [])) > 1:
        raise ErreurExamen("رئيس(ة) مركز الامتحان واحد(ة).")
    with conn:
        conn.execute("DELETE FROM examen_affectation WHERE examen_id=? AND role<>?", (eid, SURVEILLANCE))
        for role, pids in roles.items():
            for pid in pids:
                p = _personne(conn, pid)
                conn.execute("INSERT INTO examen_affectation(examen_id, personnel_id, nom, ppr, cadre, role) "
                             "VALUES (?,?,?,?,?,?)", (eid, pid, f"{p['prenom_ar']} {p['nom_ar']}", p["ppr"],
                                                      p["cadre"], role))
        for mid, pid in mudawimun.items():
            if pid:
                p = _personne(conn, pid)
                conn.execute("INSERT INTO examen_affectation(examen_id, personnel_id, nom, ppr, cadre, role, matiere_id) "
                             "VALUES (?,?,?,?,?,?,?)", (eid, pid, f"{p['prenom_ar']} {p['nom_ar']}", p["ppr"],
                                                        p["cadre"], ROLES[3], mid))


def surveillance(conn, eid: int) -> dict[tuple[int, int], int]:
    """(personnel_id، matiere_id) ← رقم القاعة."""
    return {(r["personnel_id"], r["matiere_id"]): r["salle_numero"] for r in affectations(conn, eid)
            if r["role"] == SURVEILLANCE and r["salle_numero"] is not None}


def definir_surveillance(conn, eid: int, cases: dict[tuple[int, int], int | None]) -> None:
    """يستبدل توزيع المراقبين: (personnel_id، matiere_id) ← رقم القاعة (أو None)."""
    salles_ = {r["numero"]: r["id"] for r in salles(conn, eid)}
    mats = {r["id"] for r in matieres(conn, eid)}
    for (pid, mid), num in cases.items():
        if num is not None and num not in salles_:
            raise ErreurExamen(f"القاعة {num} غير موجودة.")
        if mid not in mats:
            raise ErreurExamen("مادة غير موجودة في الجدولة.")
    with conn:
        conn.execute("DELETE FROM examen_affectation WHERE examen_id=? AND role=?", (eid, SURVEILLANCE))
        for (pid, mid), num in cases.items():
            if num is None:
                continue
            p = _personne(conn, pid)
            conn.execute("INSERT INTO examen_affectation(examen_id, personnel_id, nom, ppr, cadre, role, salle_id, "
                         "matiere_id) VALUES (?,?,?,?,?,?,?,?)",
                         (eid, pid, f"{p['prenom_ar']} {p['nom_ar']}", p["ppr"], p["cadre"], SURVEILLANCE,
                          salles_[num], mid))


def distribuer(conn, eid: int, par_salle: int = 2) -> dict[tuple[int, int], int]:
    """توزيع آلي متوازن: لكل مادة، مراقبان (أو أكثر) في كل قاعة، بالتناوب بين الأساتذة، دون المكلفين بمهام
    عامة في نفس المادة (رئيس المركز، مراقب الجودة، الكتابة، المداوم)."""
    ms, ss = matieres(conn, eid), salles(conn, eid)
    if not ms or not ss:
        raise ErreurExamen("أدخل جدولة المواد وحضّر لائحة المترشحين (القاعات) أولاً.")
    aff = affectations(conn, eid)
    generaux = {r["personnel_id"] for r in aff if r["role"] in ROLES[:3]}
    profs = [r["id"] for r in enseignants(conn) if r["categorie"] != "directeur" and r["id"] not in generaux]
    charge = {p: 0 for p in profs}
    cases = {}
    for m in ms:
        occupes = {r["personnel_id"] for r in aff if r["role"] == ROLES[3] and r["matiere_id"] == m["id"]}
        dispo = sorted((p for p in profs if p not in occupes), key=lambda p: (charge[p], profs.index(p)))
        besoin = len(ss) * par_salle
        if len(dispo) < besoin:
            raise ErreurExamen(f"{m['matiere']}: يلزم {besoin} مراقباً ({par_salle} لكل قاعة) والمتاح {len(dispo)}. "
                               "خفّض عدد المراقبين في القاعة أو أضف أساتذة.")
        for k, p in enumerate(dispo[:besoin]):
            cases[(p, m["id"])] = ss[k // par_salle]["numero"]
            charge[p] += 1
    definir_surveillance(conn, eid, cases)
    return cases


def manquants(conn, eid: int) -> list[str]:
    ex = conn.execute("SELECT * FROM examen WHERE id=?", (eid,)).fetchone()
    res = []
    if not matieres(conn, eid):
        res.append("جدولة المواد")
    if not candidats(conn, eid):
        res.append("لائحة المترشحين" + (" (من تلاميذ السادس)" if ex["type"] == "local" else " (ملف المديرية)"))
    if not any(r["role"] == ROLES[0] for r in affectations(conn, eid)):
        res.append("رئيس(ة) مركز الامتحان")
    return res
