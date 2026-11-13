"""أولياء الأمور (طلب المدير 2026-11-13): استيراد ملف «معلومات أولياء الأمور» المصدَّر من مسار، وعرضه وتعديله،
ولائحة أولياء الأمور حسب القسم.

بنية الملف (ورقة لكل قسم، أو ورقة واحدة): رأس فيه الأكاديمية والمديرية والمؤسسة والمستوى والقسم، ثم سطر العناوين
(رقم التلميذ، النسب بالعربية، الإسم بالعربية، نوع الوصاية، ثم ثلاث مجموعات: معلومات عن ولي الأمر، عن الأب، عن الأم)
وتحته سطر العناوين الفرعية لكل مجموعة (ر.ب.و، الإسم بالعربية، النسب بالعربية، الإسم بالفرنسية، النسب بالفرنسية،
المهنة، الهاتف، العنوان). يُبحث عن العناوين بالنص لا بالموضع.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from idara.data.dossier import DossierDonnees
from idara.data.journal import journaliser
from idara.services import annee as annee_srv

ROLES = {"tuteur": "ولي الأمر", "pere": "الأب", "mere": "الأم"}
CHAMPS = ("cin", "prenom_ar", "nom_ar", "prenom_fr", "nom_fr", "profession", "telephone", "adresse")
LIBELLES = {"cin": "رقم البطاقة الوطنية", "prenom_ar": "الاسم بالعربية", "nom_ar": "النسب بالعربية",
            "prenom_fr": "الاسم بالفرنسية", "nom_fr": "النسب بالفرنسية", "profession": "المهنة",
            "telephone": "الهاتف", "adresse": "العنوان"}
TUTELLES = ("أب", "أم", "وصي")


class ErreurParents(ValueError):
    """رسالة موجهة للمدير بالعربية."""


def _n(t) -> str:
    """تطبيع عنوان: دون مسافات زائدة، والهمزات والتاء المربوطة موحدة (الإسم = الاسم، الامر = الأمر)."""
    t = " ".join(str(t or "").split())
    t = re.sub("[أإآ]", "ا", t).replace("ة", "ه").replace("ى", "ي")
    return t.strip(" :")


_SOUS = {"ر.ب.و": "cin", "ر ب و": "cin", "رقم البطاقه الوطنيه": "cin", "الاسم بالعربيه": "prenom_ar",
         "النسب بالعربيه": "nom_ar", "الاسم بالفرنسيه": "prenom_fr", "النسب بالفرنسيه": "nom_fr",
         "المهنه": "profession", "الهاتف": "telephone", "العنوان": "adresse"}
_GROUPES = (("ولي", "tuteur"), ("الاب", "pere"), ("الام", "mere"))


@dataclass
class Rapport:
    eleves: int = 0
    ajoutes: int = 0
    mis_a_jour: int = 0
    inconnus: list[str] = field(default_factory=list)
    feuilles: int = 0


def _texte(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return " ".join(str(v).split())


def _telephone(v) -> str:
    t = _texte(v)
    chiffres = re.sub(r"\D", "", t)
    if len(chiffres) == 9 and chiffres[0] in "5678":    # صفر البداية يضيع حين يُخزَّن الهاتف رقماً في Excel
        chiffres = "0" + chiffres
    return chiffres if len(chiffres) == 10 else t


def _lire_feuille(lignes: list[tuple]) -> list[dict]:
    """أسطر التلاميذ في ورقة واحدة (لا شيء إن لم تكن ورقة أولياء)."""
    h = next((i for i, l in enumerate(lignes) if any(_n(v) == "رقم التلميذ" for v in l)), None)
    if h is None or h + 1 >= len(lignes):
        return []
    tete, sous = lignes[h], lignes[h + 1]
    col = {}
    for j, v in enumerate(tete):
        t = _n(v)
        if t == "رقم التلميذ":
            col["code"] = j
        elif t.startswith("النسب"):
            col.setdefault("nom", j)
        elif t.startswith("الاسم"):
            col.setdefault("prenom", j)
        elif t.startswith("نوع الوصايه"):
            col["tutelle"] = j
    # بداية كل مجموعة في سطر العناوين، ثم أعمدتها من السطر الفرعي حتى بداية المجموعة التالية
    debuts = []
    for j, v in enumerate(tete):
        t = _n(v)
        if t.startswith("معلومات"):
            role = next((r for mot, r in _GROUPES if mot in t), None)
            if role:
                debuts.append((j, role))
    blocs = {}
    for k, (j0, role) in enumerate(debuts):
        j1 = debuts[k + 1][0] if k + 1 < len(debuts) else max(len(sous), len(tete))
        m = {}
        for j in range(j0, min(j1, len(sous))):
            c = _SOUS.get(_n(sous[j]))
            if c and c not in m:
                m[c] = j
        blocs[role] = m
    if "code" not in col or not blocs:
        return []
    res = []
    for l in lignes[h + 2:]:
        code = _texte(l[col["code"]] if col["code"] < len(l) else "").upper()
        if not re.fullmatch(r"[A-Z]\d{9}", code):
            continue
        e = {"code": code, "tutelle": _texte(l[col["tutelle"]]) if "tutelle" in col and col["tutelle"] < len(l) else "",
             "roles": {}}
        for role, m in blocs.items():
            d = {c: (_telephone if c == "telephone" else _texte)(l[j] if j < len(l) else None) for c, j in m.items()}
            if any(d.values()):
                e["roles"][role] = d
        res.append(e)
    return res


def lire_fichier(chemin: Path | str) -> tuple[list[dict], int]:
    chemin = Path(chemin)
    if chemin.suffix.lower() not in (".xlsx", ".xlsm"):
        raise ErreurParents("الملف المنتظر: Excel (xlsx) المصدَّر من مسار.")
    import warnings

    import openpyxl
    eleves, feuilles = [], 0
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")      # امتدادات التحقق من البيانات في ملفات مسار
        wb = openpyxl.load_workbook(chemin, read_only=True, data_only=True)
        try:
            for ws in wb.worksheets:
                ls = _lire_feuille(list(ws.iter_rows(values_only=True)))
                if ls:
                    feuilles += 1
                    eleves += ls
        finally:
            wb.close()
    if not eleves:
        raise ErreurParents("لم يُعثر في الملف على لائحة أولياء الأمور (عمود «رقم التلميذ» ومعلومات الولي).")
    return eleves, feuilles


def importer(conn: sqlite3.Connection, chemins: list[Path | str]) -> Rapport:
    """يطابق التلاميذ برمز مسار. إعادة الاستيراد تحدّث، والخانة الفارغة في الملف لا تمحو ما أُدخل يدوياً."""
    r = Rapport()
    lus = []
    for c in chemins:
        ls, nf = lire_fichier(c)
        lus += ls
        r.feuilles += nf
    ids = {row[0]: row[1] for row in conn.execute("SELECT code_massar, id FROM eleve")}
    with conn:
        for e in lus:
            eid = ids.get(e["code"])
            if eid is None:
                r.inconnus.append(e["code"])
                continue
            r.eleves += 1
            for role, d in e["roles"].items():
                if role == "tuteur":
                    d = {**d, "tutelle": e["tutelle"]}
                actuel = conn.execute("SELECT * FROM tuteur WHERE eleve_id=? AND role=?", (eid, role)).fetchone()
                if actuel is None:
                    cols = ["eleve_id", "role"] + list(d)
                    conn.execute(f"INSERT INTO tuteur({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                                 [eid, role] + [v or None for v in d.values()])
                    r.ajoutes += 1
                else:
                    nouveaux = {k: v for k, v in d.items() if v and v != (actuel[k] or "")}
                    if nouveaux:
                        conn.execute(f"UPDATE tuteur SET {', '.join(k + '=?' for k in nouveaux)}, "
                                     "maj_le=datetime('now','localtime') WHERE id=?", [*nouveaux.values(), actuel["id"]])
                        r.mis_a_jour += 1
    journaliser(conn, "import", "tuteur", None, f"{r.eleves} تلميذاً · {r.ajoutes} جديد · {r.mis_a_jour} محيَّن")
    return r


def fiche(conn: sqlite3.Connection, eleve_id: int) -> dict[str, dict]:
    return {row["role"]: dict(row) for row in conn.execute("SELECT * FROM tuteur WHERE eleve_id=?", (eleve_id,))}


def enregistrer(conn: sqlite3.Connection, eleve_id: int, role: str, valeurs: dict) -> None:
    if role not in ROLES:
        raise ErreurParents("صفة غير معروفة.")
    d = {k: _texte(valeurs.get(k)) or None for k in CHAMPS}
    if d["telephone"]:
        d["telephone"] = _telephone(d["telephone"])
        if not re.fullmatch(r"\+?\d{9,14}", d["telephone"].replace(" ", "")):
            raise ErreurParents(f"{ROLES[role]}: رقم الهاتف غير صحيح.")
    tutelle = _texte(valeurs.get("tutelle")) or None if role == "tuteur" else None
    with conn:
        if not any(d.values()) and not tutelle:
            conn.execute("DELETE FROM tuteur WHERE eleve_id=? AND role=?", (eleve_id, role))
            return
        conn.execute(
            f"INSERT INTO tuteur(eleve_id, role, tutelle, {', '.join(CHAMPS)}) VALUES (?,?,?,{','.join('?' * len(CHAMPS))}) "
            f"ON CONFLICT(eleve_id, role) DO UPDATE SET tutelle=excluded.tutelle, "
            f"{', '.join(f'{k}=excluded.{k}' for k in CHAMPS)}, maj_le=datetime('now','localtime')",
            [eleve_id, role, tutelle] + [d[k] for k in CHAMPS])


def lister(conn: sqlite3.Connection, classe_id: int | None = None, texte: str = "") -> list[dict]:
    """تلاميذ السنة الجارية مع وليهم (الاسم، صلة القرابة، الهاتف)، وإن لم يُسجَّل ولي فالأب ثم الأم."""
    a = annee_srv.annee_courante(conn)
    if a is None:
        return []
    sql = ("SELECT e.id, e.code_massar, e.nom_ar, e.prenom_ar, c.code AS classe, c.id AS classe_id "
           "FROM inscription i JOIN eleve e ON e.id=i.eleve_id LEFT JOIN classe c ON c.id=i.classe_id "
           "WHERE i.annee_id=? AND i.statut IN ('inscrit','arrive')")
    args: list = [a["id"]]
    if classe_id:
        sql += " AND i.classe_id=?"
        args.append(classe_id)
    sql += " ORDER BY c.code, e.nom_ar, e.prenom_ar"
    t = " ".join((texte or "").split())
    res = []
    for r in conn.execute(sql, args):
        f = fiche(conn, r["id"])
        w = f.get("tuteur") or f.get("pere") or f.get("mere") or {}
        role = next((k for k in ("tuteur", "pere", "mere") if k in f), None)
        lien = (w.get("tutelle") or "") if role == "tuteur" else ROLES.get(role, "")
        ligne = {"eleve_id": r["id"], "code": r["code_massar"], "eleve": f"{r['prenom_ar']} {r['nom_ar']}",
                 "classe": r["classe"] or "", "classe_id": r["classe_id"],
                 "tuteur": " ".join(x for x in (w.get("prenom_ar"), w.get("nom_ar")) if x), "lien": lien or "",
                 "telephone": w.get("telephone") or "", "adresse": w.get("adresse") or "", "renseigne": bool(f)}
        if t and t not in " ".join(str(v) for v in ligne.values()):
            continue
        res.append(ligne)
    return res


def generer_liste(conn: sqlite3.Connection, dossier: DossierDonnees, classe_id: int | None = None) -> Path:
    """لائحة أولياء الأمور (Word): ر.ت، التلميذ، رمز مسار، الولي، صلة القرابة، الهاتف، حسب القسم."""
    from idara.services.docs_association import _cellule, _nouveau, _ombre, para, saut_page, tableau
    from idara.services.soutien import _entete
    ls = lister(conn, classe_id)
    if not ls:
        raise ErreurParents("لا تلاميذ في هذا القسم.")
    a = annee_srv.annee_courante(conn)
    d = _nouveau()
    par_classe: dict[str, list[dict]] = {}
    for l in ls:
        par_classe.setdefault(l["classe"] or "دون قسم", []).append(l)
    for k, (classe, lignes) in enumerate(par_classe.items()):
        if k:
            saut_page(d)
        _entete(d, conn, dossier, "لائحة أولياء الأمور", f"القسم: {classe} · السنة الدراسية {a['libelle']}")
        t = tableau(d, 1 + len(lignes), 6, largeurs=[1.0, 4.4, 2.6, 4.4, 1.8, 3.2])
        for j, h in enumerate(("ر.ت", "التلميذ(ة)", "رمز مسار", "ولي الأمر", "الصفة", "الهاتف")):
            _cellule(t.cell(0, j), h, gras=True, taille=10)
            _ombre(t.cell(0, j), "E7E8F8")
        for i, l in enumerate(lignes, start=1):
            for j, v in enumerate((f"{i:02d}", l["eleve"], l["code"], l["tuteur"], l["lien"], l["telephone"])):
                _cellule(t.cell(i, j), v, taille=10)
        para(d, "", apres=2)
    rep = dossier.archives / (a["libelle"].replace("/", "-") if a else "") / "أولياء الأمور"
    rep.mkdir(parents=True, exist_ok=True)
    chemin = rep / f"{datetime.now():%Y%m%d_%H%M%S}_لائحة_أولياء_الأمور.docx"
    n = 1
    while chemin.exists():
        n += 1
        chemin = chemin.with_name(f"{chemin.stem}_{n}.docx")
    d.save(chemin)
    return chemin
