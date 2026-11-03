"""قسم التقييم: استيراد «مجمل المعدلات السنوية» من مسار، وإحصاء الحاصلين على المعدل، ومحاضر مجالس الأقسام.

قاعدة متحقق منها على نتائج المدير (2025/2026، المستوى الرابع، 59 تلميذاً، مطابقة لمحضره):
- المعدل السنوي = المتوسط الحسابي لمعدلات المواد في ملف مسار (كما في بيان النتائج: 8,15).
- الحاصل على المعدل: 5/10 فما فوق.
- إن وُجد «المعدل السنوي» مملوءاً في الملف يُعتمد كما هو. السادس: 50% متوسط الدورتين + 25% المحلي + 25% الإقليمي
  (ملف المدير «محاضر نهاية الأسدوس»)، ولا يُحسب إن نقص أحدها.
- النسبة المئوية تُقطع إلى رقمين بعد الفاصلة كما في محاضر المدير (18/19 = 94.73%).
"""

from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from idara.data.dossier import DossierDonnees
from idara.services import annee as annee_srv
from idara.services import documents as dc
from idara.services import textes as tx
from idara.services.massar import MOTIF_CODE, niveaux_du_code_classe, normaliser
from idara.services.moteur_docx import SUPPRIMER_LIGNE

SEUIL = 5.0
ORDINAUX = {"1AP": "الأول", "2AP": "الثاني", "3AP": "الثالث", "4AP": "الرابع", "5AP": "الخامس", "6AP": "السادس"}
_COLONNES_FIN = ("الدورةالاولى", "الدورةالأولى", "الدورةالثانية", "م.إمالمحلي", "م.إمالإقليمي", "المعدلالسنوي")


class ErreurEvaluation(ValueError):
    """رسالة موجهة للمدير بالعربية."""


def _nombre(v) -> float | None:
    if v in (None, ""):
        return None
    try:
        return float(str(v).replace(",", ".").strip())
    except ValueError:
        return None


# ---------- القراءة ----------

@dataclass
class LigneResultat:
    code: str
    nom: str
    classe: str
    moyennes: dict[str, float]
    moyenne_massar: float | None
    s1: float | None = None   # معدل الدورة الأولى
    s2: float | None = None   # معدل الدورة الثانية
    local: float | None = None   # م.إ.م المحلي (السادس)
    prov: float | None = None    # م.إ.م الإقليمي (السادس)


@dataclass
class FichierResultats:
    annee: str = ""
    lignes: list[LigneResultat] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)
    alertes: list[str] = field(default_factory=list)


def _niveau_libelle(texte: str) -> str | None:
    t = normaliser(texte)
    for code, o in ORDINAUX.items():
        if normaliser(o) in t:
            return code
    return None


def lire_fichier(chemin: Path) -> FichierResultats:
    """«مجمل المعدلات السنوية» (MoyenneCc): ورقة لكل قسم."""
    import openpyxl
    try:
        wb = openpyxl.load_workbook(chemin, read_only=True, data_only=True)
    except Exception as e:  # noqa: BLE001
        raise ErreurEvaluation(f"تعذرت قراءة الملف {Path(chemin).name}: ليس ملف Excel صالحاً.") from e
    res = FichierResultats()
    for ws in wb.worksheets:
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
        entete = next((i for i, r in enumerate(rows) if any(normaliser(c) == "رقمالتلميذ" for c in r)), None)
        if entete is None:
            continue
        haut = rows[:entete]
        for r in haut:
            for j, c in enumerate(r):
                n = normaliser(c)
                if "السنةالدراسية" in n:
                    v = next((x for x in r[j + 1:] if x not in (None, "")), "")
                    res.annee = res.annee or str(v).strip()
        classe = ws.title.strip()
        for r in haut:
            for j, c in enumerate(r):
                if normaliser(c) == "القسم":
                    v = next((x for x in r[j + 1:] if x not in (None, "")), None)
                    if v:
                        classe = str(v).strip()
        tete = [normaliser(c) for c in rows[entete]]
        i_code, i_nom = tete.index("رقمالتلميذ"), tete.index("اسمالتلميذ")
        fin = next((j for j, h in enumerate(tete) if h in _COLONNES_FIN), len(tete))
        matieres = [(j, str(rows[entete][j]).strip()) for j in range(i_nom + 1, fin) if rows[entete][j]]
        i_annuel = tete.index("المعدلالسنوي") if "المعدلالسنوي" in tete else None
        i_s1 = next((j for j, h in enumerate(tete) if h in ("الدورةالاولى", "الدورةالأولى")), None)
        i_s2 = tete.index("الدورةالثانية") if "الدورةالثانية" in tete else None
        n_loc, n_prov = normaliser("م.إم المحلي"), normaliser("م.إم الإقليمي")
        i_loc = tete.index(n_loc) if n_loc in tete else None
        i_prov = tete.index(n_prov) if n_prov in tete else None
        val = lambda r, i: _nombre(r[i]) if i is not None and i < len(r) else None  # noqa: E731
        n_avant = len(res.lignes)
        for r in rows[entete + 1:]:
            code = str(r[i_code] or "").strip().upper()
            if not code:
                continue
            if not MOTIF_CODE.match(code):
                res.alertes.append(f"{classe}: رمز غير صالح «{code}» (تُجوهل السطر).")
                continue
            moy = {m: _nombre(r[j]) for j, m in matieres if j < len(r)}
            moy = {k: v for k, v in moy.items() if v is not None}
            annuel = _nombre(r[i_annuel]) if i_annuel is not None and i_annuel < len(r) else None
            res.lignes.append(LigneResultat(code, " ".join(str(r[i_nom] or "").split()), classe, moy, annuel,
                                            val(r, i_s1), val(r, i_s2), val(r, i_loc), val(r, i_prov)))
        if len(res.lignes) > n_avant:
            res.classes.append(classe)
    if not res.lignes:
        raise ErreurEvaluation("لم يُعثر على نتائج في الملف. صدِّر «مجمل المعدلات السنوية» من مسار.")
    try:
        annee_srv.code_court(res.annee)
    except Exception:  # noqa: BLE001
        raise ErreurEvaluation(f"السنة الدراسية غير مقروءة في الملف («{res.annee}»).") from None
    return res


# ---------- الاستيراد ----------

def _annee_id(conn, libelle: str) -> int:
    r = conn.execute("SELECT id FROM annee_scolaire WHERE libelle=?", (libelle,)).fetchone()
    if r:
        return r[0]
    with conn:
        return conn.execute("INSERT INTO annee_scolaire(libelle, code_court) VALUES (?,?)",
                            (libelle, annee_srv.code_court(libelle))).lastrowid


def _niveau(conn, code_massar: str, classe: str, annee_id: int) -> str | None:
    r = conn.execute("SELECT n.code FROM inscription i JOIN eleve e ON e.id=i.eleve_id JOIN niveau n ON n.id=i.niveau_id "
                     "WHERE e.code_massar=? AND i.annee_id=? AND i.niveau_confirme=1", (code_massar, annee_id)).fetchone()
    if r:
        return r[0]
    niveaux = niveaux_du_code_classe(classe)
    return niveaux[0] if len(niveaux) == 1 else None


def moyenne_annuelle(l: LigneResultat, niveau: str | None) -> tuple[float | None, str | None]:
    if l.moyenne_massar is not None:
        return l.moyenne_massar, "massar"
    if l.s1 is not None and l.s2 is None:
        return None, None  # ملف منتصف السنة (الدورة الأولى فقط): لا معدل سنوي
    if niveau == "6AP":
        # ملف المدير «محاضر نهاية الأسدوس» (متحقق منه): 50% متوسط المراقبة المستمرة للدورتين + 25% الامتحان
        # الموحد المحلي + 25% الإقليمي
        if None in (l.s1, l.s2, l.local, l.prov):
            return None, None
        return round(0.25 * (l.s1 + l.s2) + 0.25 * l.local + 0.25 * l.prov + 1e-9, 2), "calcul"
    if not l.moyennes:
        return None, None
    return round(sum(l.moyennes.values()) / len(l.moyennes), 2), "calcul"


@dataclass
class RapportImport:
    annee: str
    eleves: int
    classes: list[str]
    sans_niveau: list[str]
    sans_moyenne: list[str]
    inconnus: list[str]
    alertes: list[str]


def importer(conn: sqlite3.Connection, chemins: list[Path]) -> RapportImport:
    """يستورد ملفاً أو أكثر (نفس السنة). إعادة الاستيراد تحدّث ولا تكرر."""
    fichiers = [lire_fichier(c) for c in chemins]
    annees = {f.annee for f in fichiers}
    if len(annees) > 1:
        raise ErreurEvaluation("الملفات المختارة من سنوات دراسية مختلفة: " + "، ".join(sorted(annees)))
    annee = annees.pop()
    aid = _annee_id(conn, annee)
    sans_niveau, sans_moyenne, inconnus, classes = [], [], [], []
    with conn:
        for f in fichiers:
            classes += f.classes
            for l in f.lignes:
                niv = _niveau(conn, l.code, l.classe, aid)
                moy, src = moyenne_annuelle(l, niv)
                e = conn.execute("SELECT id FROM eleve WHERE code_massar=?", (l.code,)).fetchone()
                if niv is None:
                    sans_niveau.append(f"{l.nom} ({l.classe})")
                if moy is None:
                    sans_moyenne.append(f"{l.nom} ({l.classe})")
                if e is None:
                    inconnus.append(f"{l.nom} ({l.code})")
                conn.execute(
                    "INSERT INTO resultat(annee_id, code_massar, eleve_id, nom, classe, niveau, moyennes, moyenne, "
                    "source_moyenne, moyenne_s1, moyenne_s2, exam_local, exam_prov) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) "
                    "ON CONFLICT(annee_id, code_massar) DO UPDATE SET "
                    "eleve_id=excluded.eleve_id, nom=excluded.nom, classe=excluded.classe, niveau=excluded.niveau, "
                    "moyennes=excluded.moyennes, moyenne=excluded.moyenne, source_moyenne=excluded.source_moyenne, "
                    "moyenne_s1=COALESCE(excluded.moyenne_s1, resultat.moyenne_s1), "
                    "moyenne_s2=COALESCE(excluded.moyenne_s2, resultat.moyenne_s2), "
                    "exam_local=COALESCE(excluded.exam_local, resultat.exam_local), "
                    "exam_prov=COALESCE(excluded.exam_prov, resultat.exam_prov), "
                    "importe_le=datetime('now','localtime')",
                    (aid, l.code, e[0] if e else None, l.nom, l.classe, niv,
                     json.dumps(l.moyennes, ensure_ascii=False), moy, src, l.s1, l.s2, l.local, l.prov))
        conn.execute("INSERT INTO journal(action, cible, details) VALUES ('import','resultats',?)",
                     (f"{annee}: {sum(len(f.lignes) for f in fichiers)} تلميذاً",))
    return RapportImport(annee, sum(len(f.lignes) for f in fichiers), classes, sans_niveau, sans_moyenne, inconnus,
                         [a for f in fichiers for a in f.alertes])


def annees_disponibles(conn) -> list[str]:
    return [r[0] for r in conn.execute("SELECT DISTINCT a.libelle FROM resultat r JOIN annee_scolaire a "
                                       "ON a.id=r.annee_id ORDER BY a.libelle DESC")]


def definir_niveau(conn, annee: str, code_massar: str, niveau: str) -> None:
    """للأقسام المشتركة: تحديد مستوى تلميذ لم يُؤكد مستواه."""
    if niveau not in ORDINAUX:
        raise ErreurEvaluation("مستوى غير صحيح.")
    aid = _annee_id(conn, annee)
    r = conn.execute("SELECT moyennes, moyenne, source_moyenne FROM resultat WHERE annee_id=? AND code_massar=?",
                     (aid, code_massar)).fetchone()
    if r is None:
        raise ErreurEvaluation("التلميذ غير موجود في النتائج.")
    moy, src = r["moyenne"], r["source_moyenne"]
    if moy is None and niveau != "6AP":
        notes = json.loads(r["moyennes"])
        moy, src = (round(sum(notes.values()) / len(notes), 2), "calcul") if notes else (None, None)
    with conn:
        conn.execute("UPDATE resultat SET niveau=?, moyenne=?, source_moyenne=? WHERE annee_id=? AND code_massar=?",
                     (niveau, moy, src, aid, code_massar))


# ---------- الإحصاء ----------

@dataclass
class Stats:
    libelle: str
    g: int = 0
    f: int = 0
    t: int = 0
    rg: int = 0
    rf: int = 0
    rt: int = 0
    sans_sexe: int = 0
    sans_moyenne: int = 0

    @property
    def eg(self) -> int:
        return self.g - self.rg

    @property
    def ef(self) -> int:
        return self.f - self.rf

    @property
    def et(self) -> int:
        return self.t - self.rt

    @property
    def pourcentage(self) -> str:
        if not self.t:
            return "—"
        p = math.floor(self.rt / self.t * 10000) / 100
        return "100%" if p == 100 else f"{p:.2f}%"

    def ajouter(self, sexe: str | None, moyenne: float | None) -> None:
        self.t += 1
        if moyenne is None:
            self.sans_moyenne += 1
        reussi = moyenne is not None and moyenne >= SEUIL
        self.rt += reussi
        if sexe == "M":
            self.g += 1
            self.rg += reussi
        elif sexe == "F":
            self.f += 1
            self.rf += reussi
        else:
            self.sans_sexe += 1

    def plus(self, autre: "Stats") -> None:
        for k in ("g", "f", "t", "rg", "rf", "rt", "sans_sexe", "sans_moyenne"):
            setattr(self, k, getattr(self, k) + getattr(autre, k))

    def valeurs(self, prefixe: str, i: int) -> dict[str, str]:
        d = lambda n: f"{n:02d}"  # noqa: E731
        return {f"{prefixe}lib_{i}": self.libelle, f"{prefixe}g_{i}": d(self.g), f"{prefixe}f_{i}": d(self.f),
                f"{prefixe}t_{i}": d(self.t), f"{prefixe}rg_{i}": d(self.rg), f"{prefixe}rf_{i}": d(self.rf),
                f"{prefixe}rt_{i}": d(self.rt), f"{prefixe}eg_{i}": d(self.eg), f"{prefixe}ef_{i}": d(self.ef),
                f"{prefixe}et_{i}": d(self.et), f"{prefixe}pc_{i}": self.pourcentage}


def _lignes(conn, annee: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT r.*, e.sexe FROM resultat r JOIN annee_scolaire a ON a.id=r.annee_id "
        "LEFT JOIN eleve e ON e.code_massar=r.code_massar WHERE a.libelle=? ORDER BY r.classe, r.nom", (annee,)).fetchall()


def libelle_classe(classe: str) -> str:
    return classe.replace("-", "")


def stats_par_classe(conn, annee: str, niveau: str) -> list[Stats]:
    par = {}
    for r in _lignes(conn, annee):
        if r["niveau"] != niveau:
            continue
        s = par.setdefault(r["classe"], Stats(libelle_classe(r["classe"])))
        s.ajouter(r["sexe"], r["moyenne"])
    return [par[k] for k in sorted(par)]


def stats_par_niveau(conn, annee: str) -> list[Stats]:
    par = {n: Stats(f"القسم {o}") for n, o in ORDINAUX.items()}
    for r in _lignes(conn, annee):
        if r["niveau"] in par:
            par[r["niveau"]].ajouter(r["sexe"], r["moyenne"])
    return [s for s in par.values() if s.t]


def niveaux(conn, annee: str) -> list[str]:
    presents = {r["niveau"] for r in _lignes(conn, annee)}
    return [n for n in ORDINAUX if n in presents]


def a_verifier(conn, annee: str) -> dict[str, list[str]]:
    """ما يمنع إحصاءً كاملاً: مستوى غير محدد، معدل غير متوفر، نوع غير معروف."""
    l = _lignes(conn, annee)
    return {"niveau": [f"{r['nom']} ({r['classe']})" for r in l if not r["niveau"]],
            "moyenne": [f"{r['nom']} ({r['classe']})" for r in l if r["moyenne"] is None],
            "sexe": [f"{r['nom']} ({r['code_massar']})" for r in l if r["sexe"] not in ("M", "F")]}


def resultats_classe(conn, annee: str, classe: str) -> list[sqlite3.Row]:
    return [r for r in _lignes(conn, annee) if r["classe"] == classe]


# ---------- المجالس ----------

def lire_conseil(conn, annee: str, niveau: str) -> dict:
    aid = _annee_id(conn, annee)
    r = conn.execute("SELECT * FROM conseil_niveau WHERE annee_id=? AND niveau=?", (aid, niveau)).fetchone()
    return dict(r) if r else {"date_conseil": "", "phase_isa": "الخامسة", "difficultes": "", "solutions": ""}


def enregistrer_conseil(conn, annee: str, niveau: str, date_conseil: str, phase_isa: str,
                        difficultes: str, solutions: str) -> None:
    if date_conseil:
        try:
            date.fromisoformat(date_conseil)
        except ValueError:
            raise ErreurEvaluation("تاريخ المجلس غير صحيح.") from None
    aid = _annee_id(conn, annee)
    with conn:
        conn.execute("INSERT INTO conseil_niveau(annee_id, niveau, date_conseil, phase_isa, difficultes, solutions) "
                     "VALUES (?,?,?,?,?,?) ON CONFLICT(annee_id, niveau) DO UPDATE SET date_conseil=excluded.date_conseil, "
                     "phase_isa=excluded.phase_isa, difficultes=excluded.difficultes, solutions=excluded.solutions",
                     (aid, niveau, date_conseil or None, phase_isa.strip() or None, difficultes.strip() or None,
                      solutions.strip() or None))


def lire_isa(conn, annee: str, classe: str) -> dict:
    aid = _annee_id(conn, annee)
    r = conn.execute("SELECT ar, fr, ma, gl FROM isa_classe WHERE annee_id=? AND classe=?", (aid, classe)).fetchone()
    return dict(r) if r else {"ar": None, "fr": None, "ma": None, "gl": None}


def enregistrer_isa(conn, annee: str, classe: str, valeurs: dict[str, str | float | None]) -> None:
    """نسب ISA2 (من نتائج المدرسة الرائدة)، بالمائة. الفارغ مقبول."""
    v = {}
    for k in ("ar", "fr", "ma", "gl"):
        x = valeurs.get(k)
        x = _nombre(str(x).replace("%", "")) if x not in (None, "") else None
        if x is not None and not 0 <= x <= 100:
            raise ErreurEvaluation("نسب ISA2 بين 0 و100.")
        v[k] = x
    aid = _annee_id(conn, annee)
    with conn:
        conn.execute("INSERT INTO isa_classe(annee_id, classe, ar, fr, ma, gl) VALUES (?,?,?,?,?,?) "
                     "ON CONFLICT(annee_id, classe) DO UPDATE SET ar=excluded.ar, fr=excluded.fr, ma=excluded.ma, "
                     "gl=excluded.gl", (aid, classe, v["ar"], v["fr"], v["ma"], v["gl"]))


def _pct(x) -> str:
    return "—" if x is None else f"{x:.2f}%"


def membres(conn, annee: str, niveau: str) -> list[str]:
    """أساتذة أقسام المستوى (من إسناد الأقسام في الموارد البشرية، السنة الجارية)."""
    classes = {r["classe"] for r in _lignes(conn, annee) if r["niveau"] == niveau}
    a = annee_srv.annee_courante(conn)
    if not classes or a is None or a["libelle"] != annee:
        return []
    marques = ",".join("?" * len(classes))
    return [f"{r[0]} {r[1]}" for r in conn.execute(
        f"SELECT DISTINCT p.prenom_ar, p.nom_ar FROM affectation_classe f JOIN classe c ON c.id=f.classe_id "
        f"JOIN personnel p ON p.id=f.personnel_id WHERE c.annee_id=? AND c.code IN ({marques}) "
        f"AND p.statut='actif' ORDER BY p.nom_ar", (a["id"], *classes))]


_LIGNES_POINTILLES = "\n".join(["." * 120] * 6)  # فارغ: أسطر للكتابة باليد كما في النموذج


def valeurs_conseil(conn, annee: str, niveau: str, membres_extra: list[str] | None = None) -> dict[str, str]:
    stats = stats_par_classe(conn, annee, niveau)
    if not stats:
        raise ErreurEvaluation("لا نتائج لهذا المستوى.")
    if len(stats) > 4:
        raise ErreurEvaluation("المحضر يتسع لأربعة أقسام في المستوى.")
    c = lire_conseil(conn, annee, niveau)
    v = dc.champs_communs(conn)
    v.update({"date_conseil": tx.date_longue_ar(c["date_conseil"] or date.today().isoformat()),
              "ordinal": ORDINAUX[niveau], "annee": annee, "phase_isa": c.get("phase_isa") or "الخامسة",
              "difficultes": c.get("difficultes") or _LIGNES_POINTILLES,
              "solutions": c.get("solutions") or _LIGNES_POINTILLES})
    for i in range(1, 5):
        if i <= len(stats):
            s = stats[i - 1]
            v.update(s.valeurs("s_", i))
            classe = next(r["classe"] for r in _lignes(conn, annee) if libelle_classe(r["classe"]) == s.libelle)
            isa = lire_isa(conn, annee, classe)
            v.update({f"i_lib_{i}": s.libelle, f"i_ar_{i}": _pct(isa["ar"]), f"i_fr_{i}": _pct(isa["fr"]),
                      f"i_ma_{i}": _pct(isa["ma"]), f"i_gl_{i}": _pct(isa["gl"])})
        else:
            for k in ("lib", "g", "f", "t", "rg", "rf", "rt", "eg", "ef", "et", "pc"):
                v[f"s_{k}_{i}"] = SUPPRIMER_LIGNE
            for k in ("lib", "ar", "fr", "ma", "gl"):
                v[f"i_{k}_{i}"] = SUPPRIMER_LIGNE
    noms = membres(conn, annee, niveau) + (membres_extra or [])
    lignes_sig = max(2, math.ceil(len(noms) / 2))
    for i in range(1, 5):
        a, b = (noms[2 * i - 2] if 2 * i - 2 < len(noms) else ""), (noms[2 * i - 1] if 2 * i - 1 < len(noms) else "")
        if i > lignes_sig:
            v.update({f"m_a_{i}": SUPPRIMER_LIGNE, f"m_b_{i}": "", f"m_sa_{i}": "", f"m_sb_{i}": ""})
        else:
            v.update({f"m_a_{i}": a, f"m_b_{i}": b, f"m_sa_{i}": "", f"m_sb_{i}": ""})
    return v


def generer_conseil(conn, dossier: DossierDonnees, annee: str, niveau: str) -> dc.DocumentGenere:
    v = valeurs_conseil(conn, annee, niveau)
    return dc.generer(conn, dossier, "conseil_niveau", v, libelle=f"مجلس القسم {ORDINAUX[niveau]} {annee}")


def valeurs_synthese(conn, annee: str, periode: str = "للأسدوس الثاني", le: str | None = None) -> dict[str, str]:
    stats = stats_par_niveau(conn, annee)
    if not stats:
        raise ErreurEvaluation("لا نتائج لهذه السنة.")
    total = Stats("المجموع")
    for s in stats:
        total.plus(s)
    lignes = stats + [total]
    v = dc.champs_communs(conn)
    v.update({"date_conseil": tx.date_longue_ar(le or date.today().isoformat()), "annee": annee, "periode": periode})
    for i in range(1, 9):
        if i <= len(lignes):
            v.update(lignes[i - 1].valeurs("s_", i))
        else:
            for k in ("lib", "g", "f", "t", "rg", "rf", "rt", "eg", "ef", "et", "pc"):
                v[f"s_{k}_{i}"] = SUPPRIMER_LIGNE
    return v


def generer_synthese(conn, dossier: DossierDonnees, annee: str, periode: str = "للأسدوس الثاني",
                     le: str | None = None) -> dc.DocumentGenere:
    v = valeurs_synthese(conn, annee, periode, le)
    return dc.generer(conn, dossier, "synthese_conseils", v, libelle=f"تقرير مجالس الأقسام {annee}")


# ---------- أداء المؤسسة: كل أسدوس مقارنة بالذي قبله ----------

SEMESTRES = {1: "الأسدوس الأول", 2: "الأسدوس الثاني"}


@dataclass
class Indicateur:
    effectif: int = 0
    somme: float = 0.0
    reussis: int = 0

    def ajouter(self, m: float) -> None:
        self.effectif += 1
        self.somme += m
        self.reussis += m >= SEUIL

    @property
    def moyenne(self) -> float | None:
        return round(self.somme / self.effectif, 2) if self.effectif else None

    @property
    def taux(self) -> float | None:
        return round(self.reussis / self.effectif * 100, 2) if self.effectif else None


def periodes(conn) -> list[tuple[str, int]]:
    """الأسدوسات المتوفرة نتائجها، بالترتيب الزمني: (السنة، 1 أو 2)."""
    res = []
    for annee in sorted(annees_disponibles(conn)):
        for sem, col in ((1, "moyenne_s1"), (2, "moyenne_s2")):
            if conn.execute(f"SELECT 1 FROM resultat r JOIN annee_scolaire a ON a.id=r.annee_id WHERE a.libelle=? "
                            f"AND r.{col} IS NOT NULL LIMIT 1", (annee,)).fetchone():
                res.append((annee, sem))
    return res


def libelle_periode(p: tuple[str, int]) -> str:
    return f"{SEMESTRES[p[1]]} {p[0]}"


def indicateurs(conn, periode: tuple[str, int], par: str = "niveau") -> dict[str, Indicateur]:
    """par «niveau» (المستويات + المؤسسة) أو «classe». المفتاح «المؤسسة» = المجموع."""
    col = "moyenne_s1" if periode[1] == 1 else "moyenne_s2"
    res: dict[str, Indicateur] = {}
    for r in _lignes(conn, periode[0]):
        m = r[col]
        if m is None:
            continue
        cle = r["niveau"] if par == "niveau" else r["classe"]
        if cle:
            res.setdefault(cle, Indicateur()).ajouter(m)
        res.setdefault("المؤسسة", Indicateur()).ajouter(m)
    return res


def comparaison(conn, periode: tuple[str, int] | None = None, par: str = "niveau") -> list[dict]:
    """الأسدوس المختار (الأخير افتراضياً) مقارنة بالأسدوس الذي قبله: المعدل ونسبة الحاصلين على المعدل وتطورهما."""
    ps = periodes(conn)
    if not ps:
        return []
    periode = periode or ps[-1]
    i = ps.index(periode)
    avant = ps[i - 1] if i else None
    act, prec = indicateurs(conn, periode, par), (indicateurs(conn, avant, par) if avant else {})
    if par == "niveau":
        cles = [n for n in ORDINAUX if n in act or n in prec] + ["المؤسسة"]
    else:
        cles = sorted(k for k in set(act) | set(prec) if k != "المؤسسة") + ["المؤسسة"]
    lignes = []
    for k in cles:
        a, b = act.get(k), prec.get(k)
        d = lambda x, y: round(x - y, 2) if x is not None and y is not None else None  # noqa: E731
        lignes.append({"cle": k, "libelle": (f"المستوى {ORDINAUX[k]}" if k in ORDINAUX else
                                             (k if k == "المؤسسة" else libelle_classe(k))),
                       "effectif": a.effectif if a else 0, "moyenne": a.moyenne if a else None,
                       "taux": a.taux if a else None, "moyenne_avant": b.moyenne if b else None,
                       "taux_avant": b.taux if b else None,
                       "ecart_moyenne": d(a.moyenne if a else None, b.moyenne if b else None),
                       "ecart_taux": d(a.taux if a else None, b.taux if b else None),
                       "periode": libelle_periode(periode), "avant": libelle_periode(avant) if avant else None})
    return lignes
