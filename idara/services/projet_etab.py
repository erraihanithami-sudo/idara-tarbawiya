"""تتبع مشروع المؤسسة المندمج (قرار المدير 2026-11-07).

الصياغة تتم في منظومة مسار؛ البرنامج لا يصوغ المشروع. ما يقوم به:
- المؤشرات الثلاثة لخارطة الطريق، تُحسب من معطيات البرنامج نفسه لكل سنة من سنوات المشروع:
  1. التحكم في التعلمات الأساس: نسبة من بلغوا المستوى المتوقع (آخر رائز في السنة: البعدي وإلا القبلي)،
     لكل مادة وللمواد الثلاث مجتمعة (تلميذ × مادة).
  2. الهدر المدرسي: المنقطعون والمفصولون إلى التلاميذ المعنيين (نفس حساب لوحة القيادة).
  3. الأنشطة الموازية: نسبة التلاميذ المنخرطين في نادٍ واحد على الأقل.
  مع القيمة المرجعية والمستهدف لكل سنة (يُدخلها المدير من وثيقة المشروع في مسار)، وقيمة يدوية لسنة لا معطيات لها.
- تتبع تنزيل العمليات: تُستورد من تقرير «خطة العمل» أو ملف التصدير من مسار، ثم تُتابع حالتها ونسبة إنجازها
  والمبلغ المصروف. إعادة الاستيراد تُحدّث المعطيات المبرمجة ولا تمس التتبع.
- التقارير (Word): تقرير تركيبي للإنجاز، وحصيلة نهاية المشروع لاستثمارها في صياغة مشروع جديد.
"""

from __future__ import annotations

import io
import re
import sqlite3
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from idara.data.dossier import DossierDonnees
from idara.services import annee as annee_srv
from idara.services import tableau_bord as tb

INDICATEURS = {
    "tarl": "المتحكمون في التعلمات الأساس",
    "hadar": "نسبة الهدر المدرسي",
    "activites": "المستفيدون من الأنشطة الموازية",
}
OBJECTIFS = {
    "tarl": "الهدف 1: تحسين التحكم في التعلمات الأساس",
    "hadar": "الهدف 2: تقليص الهدر المدرسي",
    "activites": "الهدف 3: تعميم الاستفادة من الأنشطة الموازية",
}
SENS = {"tarl": 1, "hadar": -1, "activites": 1}   # الهدر: كلما انخفض كان أفضل
STATUTS = {"programmee": "مبرمجة", "en_cours": "في طور الإنجاز", "realisee": "منجزة", "reportee": "مؤجلة",
           "annulee": "ملغاة"}
EXTENSIONS = {".xlsx", ".xlsm", ".xls"}


class ErreurProjet(ValueError):
    """رسالة موجهة للمدير بالعربية."""


def _pct(n, d) -> float | None:
    return round(n * 100 / d, 1) if d else None


def _propre(t) -> str:
    return " ".join(str(t or "").split())


# ---------- المشروع ----------

def annees_projet(debut: str, fin: str) -> list[str]:
    annee_srv.code_court(debut)
    annee_srv.code_court(fin)
    a, b = int(debut[:4]), int(fin[:4])
    if b < a:
        raise ErreurProjet("سنة النهاية قبل سنة البداية.")
    if b - a > 5:
        raise ErreurProjet("مدة المشروع لا تتجاوز ست سنوات.")
    return [f"{y}/{y + 1}" for y in range(a, b + 1)]


def projet_actif(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM projet_etab WHERE actif=1 ORDER BY id DESC LIMIT 1").fetchone()


def projets(conn) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM projet_etab ORDER BY annee_debut DESC, id DESC").fetchall()


def enregistrer_projet(conn: sqlite3.Connection, intitule: str, debut: str, fin: str, pid: int | None = None) -> int:
    intitule = _propre(intitule) or "مشروع المؤسسة المندمج"
    try:
        annees_projet(debut, fin)
    except annee_srv.ErreurAnnee as e:
        raise ErreurProjet(str(e)) from None
    with conn:
        if pid:
            conn.execute("UPDATE projet_etab SET intitule=?, annee_debut=?, annee_fin=? WHERE id=?",
                         (intitule, debut, fin, pid))
            return pid
        conn.execute("UPDATE projet_etab SET actif=0")
        return conn.execute("INSERT INTO projet_etab(intitule, annee_debut, annee_fin) VALUES (?,?,?)",
                            (intitule, debut, fin)).lastrowid


def activer(conn, pid: int) -> None:
    with conn:
        conn.execute("UPDATE projet_etab SET actif=(id=?)", (pid,))


def supprimer_projet(conn, pid: int) -> None:
    with conn:
        conn.execute("DELETE FROM projet_etab WHERE id=?", (pid,))


def projet(conn, pid: int) -> sqlite3.Row:
    p = conn.execute("SELECT * FROM projet_etab WHERE id=?", (pid,)).fetchone()
    if p is None:
        raise ErreurProjet("المشروع غير موجود.")
    return p


# ---------- المؤشرات ----------

def _annee_id(conn, libelle: str) -> int | None:
    r = conn.execute("SELECT id FROM annee_scolaire WHERE libelle=?", (libelle,)).fetchone()
    return r[0] if r else None


def mesure_tarl(conn, libelle: str) -> dict:
    """لكل مادة وللمجموع: المتحكمون/المقوَّمون في آخر رائز من السنة."""
    par = tb._maitrise(conn, libelle, None)
    ok = sum(m["maitrise"] for m in par.values())
    tot = sum(m["total"] for m in par.values())
    return {"valeur": _pct(ok, tot), "maitrise": ok, "total": tot,
            "matieres": {k: {"libelle": m["matiere"], "valeur": None if m["taux"] is None else round(m["taux"], 1),
                             "epreuve": m["epreuve"]} for k, m in par.items()}}


def mesure_hadar(conn, libelle: str) -> dict:
    aid = _annee_id(conn, libelle)
    st = {r[0]: r[1] for r in conn.execute("SELECT statut, COUNT(*) FROM inscription WHERE annee_id=? GROUP BY statut",
                                           (aid if aid else -1,))}
    actifs = st.get("inscrit", 0) + st.get("arrive", 0)
    perdus = st.get("interrompu", 0) + st.get("exclu", 0)
    concernes = actifs + perdus
    return {"valeur": _pct(perdus, concernes), "interrompus": st.get("interrompu", 0), "exclus": st.get("exclu", 0),
            "concernes": concernes}


def mesure_activites(conn, libelle: str) -> dict:
    aid = _annee_id(conn, libelle) or -1
    actifs = conn.execute("SELECT COUNT(*) FROM inscription WHERE annee_id=? AND statut IN ('inscrit','arrive')",
                          (aid,)).fetchone()[0]
    n = conn.execute(
        "SELECT COUNT(DISTINCT m.eleve_id) FROM club_membre m JOIN club k ON k.id=m.club_id JOIN inscription i ON "
        "i.eleve_id=m.eleve_id AND i.annee_id=k.annee_id WHERE k.annee_id=? AND i.statut IN ('inscrit','arrive')",
        (aid,)).fetchone()[0]
    return {"valeur": _pct(n, actifs) if n else None, "participants": n, "eleves": actifs}


MESURES = {"tarl": mesure_tarl, "hadar": mesure_hadar, "activites": mesure_activites}


def cibles(conn, pid: int) -> dict[tuple[str, str], sqlite3.Row]:
    return {(r["indicateur"], r["annee"]): r for r in conn.execute("SELECT * FROM projet_cible WHERE projet_id=?",
                                                                   (pid,))}


def _nombre(v, nom: str) -> float | None:
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    try:
        x = float(str(v).replace(",", ".").replace("%", "").strip())
    except ValueError:
        raise ErreurProjet(f"{nom}: أدخل نسبة مئوية (رقم).") from None
    if not 0 <= x <= 100:
        raise ErreurProjet(f"{nom}: النسبة بين 0 و100.")
    return x


def enregistrer_cibles(conn: sqlite3.Connection, pid: int,
                       valeurs: list[tuple[str, str, object, object]]) -> None:
    """valeurs: (المؤشر، السنة أو 'ref'، المستهدف، المحقق يدوياً)."""
    propres = []
    for ind, an, c, m in valeurs:
        if ind not in INDICATEURS:
            raise ErreurProjet("مؤشر غير معروف.")
        nom = INDICATEURS[ind] + ("" if an == "ref" else f" ({an})")
        propres.append((pid, ind, an, _nombre(c, nom), _nombre(m, nom)))
    with conn:
        conn.executemany("INSERT INTO projet_cible(projet_id, indicateur, annee, cible, realise_manuel) VALUES "
                         "(?,?,?,?,?) ON CONFLICT(projet_id, indicateur, annee) DO UPDATE SET cible=excluded.cible, "
                         "realise_manuel=excluded.realise_manuel", propres)


def tableau_indicateurs(conn: sqlite3.Connection, pid: int) -> dict:
    """لكل مؤشر: المرجعية، ولكل سنة المستهدف والمحقق (من البرنامج، وإلا اليدوي) ومصدره."""
    p = projet(conn, pid)
    ans = annees_projet(p["annee_debut"], p["annee_fin"])
    cs = cibles(conn, pid)
    res = {}
    for ind in INDICATEURS:
        ref = cs.get((ind, "ref"))
        lignes = []
        for an in ans:
            m = MESURES[ind](conn, an)
            c = cs.get((ind, an))
            manuel = c["realise_manuel"] if c else None
            valeur, source = (m["valeur"], "البرنامج") if m["valeur"] is not None else \
                (manuel, "يدوي") if manuel is not None else (None, "")
            cible = c["cible"] if c else None
            atteint = None
            if valeur is not None and cible is not None:
                atteint = valeur >= cible if SENS[ind] > 0 else valeur <= cible
            lignes.append({"annee": an, "cible": cible, "realise": valeur, "source": source, "atteint": atteint,
                           "manuel": manuel, "detail": m})
        reference = ref["cible"] if ref else None
        derniere = next((l for l in reversed(lignes) if l["realise"] is not None), None)
        evolution = (round(derniere["realise"] - reference, 1)
                     if derniere is not None and reference is not None else None)
        res[ind] = {"libelle": INDICATEURS[ind], "objectif": OBJECTIFS[ind], "reference": reference,
                    "annees": lignes, "derniere": derniere, "evolution": evolution, "sens": SENS[ind]}
    return res


# ---------- العمليات ----------

def operations(conn: sqlite3.Connection, pid: int) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM projet_operation WHERE projet_id=? ORDER BY id", (pid,)).fetchall()


def ajouter_operation(conn: sqlite3.Connection, pid: int, intitule: str, axe: str = "", critere: str = "",
                      montant=None, date_debut: str = "", date_fin: str = "", priorite: int | None = None) -> int:
    projet(conn, pid)
    intitule = _propre(intitule)
    if not intitule:
        raise ErreurProjet("اسم العملية إجباري.")
    m = _montant(montant)
    with conn:
        return conn.execute(
            "INSERT INTO projet_operation(projet_id, intitule, axe, critere, montant, date_debut, date_fin, priorite) "
            "VALUES (?,?,?,?,?,?,?,?)", (pid, intitule, _propre(axe) or None, _propre(critere) or None, m,
                                         date_debut or None, date_fin or None, priorite)).lastrowid


def _montant(v) -> float | None:
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    try:
        x = float(str(v).replace(" ", "").replace(",", "."))
    except ValueError:
        raise ErreurProjet("المبلغ رقم بالدرهم.") from None
    if x < 0:
        raise ErreurProjet("المبلغ لا يكون سالباً.")
    return x


def suivre(conn: sqlite3.Connection, oid: int, statut: str, taux=None, depense=None, observation: str = "") -> None:
    if statut not in STATUTS:
        raise ErreurProjet("حالة العملية غير معروفة.")
    t = 100.0 if statut == "realisee" else (0.0 if taux in (None, "") else _nombre(taux, "نسبة الإنجاز"))
    with conn:
        conn.execute("UPDATE projet_operation SET statut=?, taux=?, montant_depense=?, observation=? WHERE id=?",
                     (statut, t, _montant(depense), _propre(observation) or None, oid))


def supprimer_operation(conn, oid: int) -> None:
    with conn:
        conn.execute("DELETE FROM projet_operation WHERE id=?", (oid,))


def synthese_operations(conn: sqlite3.Connection, pid: int) -> dict:
    ops = [o for o in operations(conn, pid)]
    actives = [o for o in ops if o["statut"] != "annulee"]
    par_statut = {k: sum(1 for o in ops if o["statut"] == k) for k in STATUTS}
    prog = sum(o["montant"] or 0 for o in actives)
    dep = sum(o["montant_depense"] or 0 for o in ops)
    najah = sum(o["budget_najah"] or 0 for o in actives)

    def taux_moyen(l):
        return round(sum(o["taux"] for o in l) / len(l), 1) if l else None

    axes = []
    for axe in dict.fromkeys((o["axe"] or "بدون محور") for o in ops):
        l = [o for o in actives if (o["axe"] or "بدون محور") == axe]
        crits = []
        for cr in dict.fromkeys((o["critere"] or "بدون معيار") for o in l):
            lc = [o for o in l if (o["critere"] or "بدون معيار") == cr]
            crits.append({"critere": cr, "operations": len(lc),
                          "realisees": sum(1 for o in lc if o["statut"] == "realisee"), "taux": taux_moyen(lc)})
        axes.append({"axe": axe, "operations": len(l), "realisees": sum(1 for o in l if o["statut"] == "realisee"),
                     "taux": taux_moyen(l), "montant": sum(o["montant"] or 0 for o in l),
                     "depense": sum(o["montant_depense"] or 0 for o in l), "criteres": crits})
    return {"total": len(ops), "actives": len(actives), "par_statut": par_statut,
            "taux_global": taux_moyen(actives), "pct_realisees": _pct(par_statut["realisee"], len(actives)),
            "montant_programme": prog, "montant_depense": dep, "budget_najah": najah,
            "pct_depense": _pct(dep, prog), "axes": axes}


# ---------- الاستيراد من مسار ----------

def _norm(t) -> str:
    t = unicodedata.normalize("NFKC", str(t or ""))
    t = re.sub(r"[ًٌٍَُِّْـ]", "", t)
    for a, b in (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ى", "ي")):
        t = t.replace(a, b)
    return re.sub(r"\s+", "", t).lower()


# (المفتاح، الصيغ المقبولة بالتطابق التام، الصيغ المقبولة كبداية)
_COLONNES = [
    ("ref", ["actionid"], []),
    ("axe", ["المحور"], []),
    ("sous_critere", ["المعيارالفرعي", "السؤال/المعيارالفرعي", "السؤال"], ["السؤال"]),
    ("critere", ["المعيار"], []),
    ("evaluation", ["التقييم"], []),
    ("numero", ["رقم", "رقمالعمليه", "رقمالعملية"], []),
    ("intitule", ["العمليه", "العملية"], []),
    ("priorite", ["اولويه", "اولوية", "الاولويه", "الاولوية"], []),
    ("montant", ["المبلغ", "المبلغالاجمالي"], ["المبلغ"]),
    ("budget_najah", [], ["ميزانيهجمعيه", "ميزانيةجمعية"]),
    ("contributeur", ["الجهةالمساهمة", "الجهةالمساهمه", "جهةالمساهمة", "جهةالمساهمه"], []),
    ("contribution", ["قيمةالمساهمة", "قيمةالمساهمه"], []),
    ("domaine", ["مجالاتالصرف"], []),
    ("ligne", ["اسطرالصرف"], []),
    ("date_debut", ["تاريخالبداية", "تاريخالبدايه"], []),
    ("date_fin", ["تاريخالنهاية", "تاريخالنهايه"], []),
    ("etat_massar", ["وضعيةالعملية", "وضعيةالعمليه"], []),
]


def _colonnes(ligne) -> dict[str, int]:
    res: dict[str, int] = {}
    for j, v in enumerate(ligne):
        n = _norm(v)
        if not n:
            continue
        for cle, exacts, debuts in _COLONNES:
            if cle in res:
                continue
            if n in exacts or any(n.startswith(d) for d in debuts):
                res[cle] = j
                break
    return res


def _date(v) -> str | None:
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    s = str(v).strip()
    for f in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, f).date().isoformat()
        except ValueError:
            pass
    return None


def _num(v) -> float | None:
    try:
        return None if v in (None, "") else float(str(v).replace(" ", "").replace(",", "."))
    except ValueError:
        return None


def _libelle_marque(ligne, marque: str) -> str | None:
    """سطر «المحور: …» أو «المعيار: …» في تقرير خطة العمل."""
    cellules = [_propre(v) for v in ligne]
    if not any(_norm(c) == _norm(marque) for c in cellules):
        return None
    autres = [c for c in cellules if c and _norm(c) != _norm(marque)]
    return autres[0] if autres else ""


@dataclass
class RapportImport:
    ajoutees: int = 0
    mises_a_jour: int = 0
    ignorees: int = 0
    avertissements: list[str] = field(default_factory=list)


def _xls_vers_xlsx(chemin: Path) -> Path:
    """ملفات مسار .xls: تُحوَّل عبر Excel المثبت على الحاسوب."""
    import tempfile
    try:
        import win32com.client  # type: ignore
    except ImportError:
        raise ErreurProjet("ملف .xls: افتحه في Excel واحفظه بصيغة .xlsx ثم أعد الاستيراد.") from None
    cible = Path(tempfile.mkdtemp()) / (chemin.stem + ".xlsx")
    try:
        xl = win32com.client.DispatchEx("Excel.Application")
        xl.Visible = False
        xl.DisplayAlerts = False
        try:
            wb = xl.Workbooks.Open(str(chemin.resolve()), ReadOnly=True)
            wb.SaveAs(str(cible), FileFormat=51)
            wb.Close(False)
        finally:
            xl.Quit()
    except Exception:  # noqa: BLE001
        raise ErreurProjet("تعذر فتح ملف .xls: افتحه في Excel واحفظه بصيغة .xlsx ثم أعد الاستيراد.") from None
    return cible


def lire_operations(chemin: Path | str) -> list[dict]:
    """يقرأ عمليات خطة العمل من ملف مسار: تقرير «خطة العمل» (محاور ومعايير في أسطر مستقلة) أو ملف التصدير
    (عمود لكل معطى)."""
    from openpyxl import load_workbook
    chemin = Path(chemin)
    if chemin.suffix.lower() not in EXTENSIONS:
        raise ErreurProjet("الملف المنتظر: Excel مصدَّر من مسار (.xlsx أو .xls).")
    if chemin.suffix.lower() == ".xls":
        chemin = _xls_vers_xlsx(chemin)
    try:
        wb = load_workbook(chemin, read_only=True, data_only=True)
    except Exception:  # noqa: BLE001
        raise ErreurProjet("تعذرت قراءة الملف.") from None
    res: list[dict] = []
    for ws in wb.worksheets:
        cols: dict[str, int] = {}
        axe = critere = sous = ""
        for ligne in ws.iter_rows(values_only=True):
            ligne = list(ligne)
            c = _colonnes(ligne)
            if "intitule" in c and len(c) >= 4:
                cols = c
                continue
            m = _libelle_marque(ligne, "المحور")
            if m is not None and "axe" not in cols:
                axe, critere, sous = m, "", ""
                continue
            m = _libelle_marque(ligne, "المعيار")
            if m is not None and "critere" not in cols:
                critere, sous = m, ""
                continue
            if not cols:
                continue

            def val(k):
                j = cols.get(k)
                return ligne[j] if j is not None and j < len(ligne) else None
            intitule = _propre(val("intitule"))
            if not intitule:
                continue
            sous = _propre(val("sous_critere")) or sous
            prio = _num(val("priorite"))
            res.append({
                "ref_massar": _propre(val("ref")) or None,
                "axe": _propre(val("axe")) or axe or None,
                "critere": _propre(val("critere")) or critere or None,
                "sous_critere": sous or None,
                "evaluation": _propre(val("evaluation")) or None,
                "intitule": intitule,
                "priorite": int(prio) if prio in (1, 2, 3) else None,
                "montant": _num(val("montant")),
                "budget_najah": _num(val("budget_najah")),
                "contributeur": _propre(val("contributeur")) or None,
                "contribution": _num(val("contribution")),
                "domaine": _propre(val("domaine")) or None,
                "ligne": _propre(val("ligne")) or None,
                "date_debut": _date(val("date_debut")),
                "date_fin": _date(val("date_fin")),
            })
    wb.close()
    if not res:
        raise ErreurProjet("لم يُعثر على عمليات في الملف: استعمل تقرير «خطة العمل» أو ملف تصدير العمليات من مسار.")
    return res


CHAMPS_MASSAR = ["ref_massar", "axe", "critere", "sous_critere", "evaluation", "intitule", "priorite", "montant",
                 "budget_najah", "contributeur", "contribution", "domaine", "ligne", "date_debut", "date_fin"]


def importer_operations(conn: sqlite3.Connection, pid: int, chemin: Path | str) -> RapportImport:
    projet(conn, pid)
    ops = lire_operations(chemin)
    r = RapportImport()
    existantes = operations(conn, pid)
    par_ref = {o["ref_massar"]: o["id"] for o in existantes if o["ref_massar"]}
    par_nom = {(_norm(o["critere"]), _norm(o["intitule"])): o["id"] for o in existantes}
    vues: set = set()
    with conn:
        for o in ops:
            cle = (_norm(o["critere"]), _norm(o["intitule"]))
            if (o["ref_massar"] or cle) in vues:
                r.ignorees += 1
                continue
            vues.add(o["ref_massar"] or cle)
            oid = par_ref.get(o["ref_massar"]) if o["ref_massar"] else None
            oid = oid or par_nom.get(cle)
            if oid:
                sets = ", ".join(f"{k}=?" for k in CHAMPS_MASSAR)
                conn.execute(f"UPDATE projet_operation SET {sets} WHERE id=?", [o[k] for k in CHAMPS_MASSAR] + [oid])
                r.mises_a_jour += 1
            else:
                conn.execute(f"INSERT INTO projet_operation(projet_id, {', '.join(CHAMPS_MASSAR)}) VALUES "
                             f"(?{', ?' * len(CHAMPS_MASSAR)})", [pid] + [o[k] for k in CHAMPS_MASSAR])
                r.ajoutees += 1
    sans_date = sum(1 for o in ops if not o["date_debut"])
    if sans_date:
        r.avertissements.append(f"{sans_date} عملية بدون تاريخ بداية.")
    return r


# ---------- التقارير ----------

def _n(v, suffixe: str = "%") -> str:
    return "—" if v is None else f"{v:g}{suffixe}"


def _dh(v) -> str:
    return f"{v:,.2f}".replace(",", " ") + " درهم"


def _table(d, entetes, lignes, largeurs, taille=9):
    from idara.services.soutien import _table as t
    return t(d, entetes, lignes, largeurs, taille)


def generer_rapport(conn: sqlite3.Connection, dossier: DossierDonnees, pid: int, final: bool = False,
                    graphiques: dict[str, bytes] | None = None) -> Path:
    """final=False: تقرير تركيبي للإنجاز (في أي وقت). final=True: حصيلة نهاية المشروع مع ما يُستثمر في مشروع جديد."""
    from docx.shared import Cm

    from idara.services.docs_association import _nouveau, para
    from idara.services.soutien import _entete, _signature
    p = projet(conn, pid)
    ind = tableau_indicateurs(conn, pid)
    so = synthese_operations(conn, pid)
    a = annee_srv.annee_courante(conn)
    titre = "حصيلة نهاية مشروع المؤسسة المندمج" if final else "التقرير التركيبي لتنزيل مشروع المؤسسة المندمج"
    d = _nouveau()
    _entete(d, conn, dossier, titre, f"{p['intitule']} · {p['annee_debut']} - {p['annee_fin']}")
    if a:
        para(d, f"وضعية التتبع إلى غاية {date.today():%d/%m/%Y} (السنة الدراسية {a['libelle']}).", taille=10, apres=4)

    para(d, "1. مؤشرات أهداف المشروع", gras=True, taille=12, apres=2)
    for k, x in ind.items():
        para(d, x["objectif"] + f" (المؤشر: {x['libelle']})", gras=True, taille=10, apres=1)
        _table(d, ["السنة", "المستهدف", "المحقق", "المصدر", "بلوغ المستهدف"],
               [["المرجعية", _n(x["reference"]), "", "", ""]] +
               [[l["annee"], _n(l["cible"]), _n(l["realise"]), l["source"] or "—",
                 "—" if l["atteint"] is None else ("نعم" if l["atteint"] else "لا")] for l in x["annees"]],
               [3, 2.6, 2.6, 2.6, 3])
        if graphiques and graphiques.get(k):
            d.add_picture(io.BytesIO(graphiques[k]), width=Cm(14))
            d.paragraphs[-1].alignment = 1
        if k == "tarl" and x["derniere"]:
            mats = x["derniere"]["detail"]["matieres"]
            para(d, "حسب المادة (" + x["derniere"]["annee"] + "): " + "، ".join(
                f"{m['libelle']} {_n(m['valeur'])}" for m in mats.values()), taille=9, apres=3)
        para(d, "", apres=2)

    para(d, "2. تنزيل العمليات", gras=True, taille=12, apres=2)
    ps = so["par_statut"]
    _table(d, ["العمليات", "منجزة", "في طور الإنجاز", "مبرمجة", "مؤجلة", "ملغاة", "نسبة الإنجاز"],
           [[str(so["total"]), str(ps["realisee"]), str(ps["en_cours"]), str(ps["programmee"]), str(ps["reportee"]),
             str(ps["annulee"]), _n(so["taux_global"])]], [2.2, 2, 2.4, 2, 2, 2, 2.4])
    para(d, f"الميزانية المبرمجة: {_dh(so['montant_programme'])} · منها ميزانية جمعية دعم مدرسة النجاح: "
            f"{_dh(so['budget_najah'])} · المصروف: {_dh(so['montant_depense'])} ({_n(so['pct_depense'])})",
         taille=9, apres=3)
    if so["axes"]:
        _table(d, ["المحور", "المعيار", "العمليات", "المنجزة", "نسبة الإنجاز"],
               [[ax["axe"], c["critere"], str(c["operations"]), str(c["realisees"]), _n(c["taux"])]
                for ax in so["axes"] for c in ax["criteres"]], [3, 6, 2, 2, 2.4])
    para(d, "", apres=3)
    ops = operations(conn, pid)
    para(d, "3. لائحة العمليات وحالتها", gras=True, taille=12, apres=2)
    if ops:
        _table(d, ["ر.ت", "العملية", "المعيار", "الفترة", "المبلغ", "الحالة", "الإنجاز", "ملاحظات"],
               [[str(i), o["intitule"], o["critere"] or "—",
                 f"{o['date_debut'] or ''} → {o['date_fin'] or ''}".strip(" →") or "—",
                 "—" if o["montant"] is None else f"{o['montant']:g}", STATUTS[o["statut"]], _n(o["taux"]),
                 o["observation"] or ""] for i, o in enumerate(ops, start=1)],
               [0.8, 4.6, 3, 2.6, 1.6, 1.8, 1.4, 2.6], taille=8)
    else:
        para(d, "لم تُستورد العمليات بعد.", taille=9)

    if final:
        para(d, "", apres=3)
        para(d, "4. خلاصات لاستثمارها في صياغة المشروع الجديد", gras=True, taille=12, apres=2)
        for k, x in ind.items():
            dl = x["derniere"]
            if dl is None:
                para(d, f"• {x['libelle']}: لا معطيات محققة.", taille=10, apres=1)
                continue
            evo = "" if x["evolution"] is None else f"، تطور بـ {x['evolution']:+g} نقطة مقارنة بالمرجعية"
            etat = ("بلغ المستهدف" if dl["atteint"] else "لم يبلغ المستهدف") if dl["atteint"] is not None else \
                "بدون مستهدف"
            para(d, f"• {x['libelle']}: {_n(dl['realise'])} سنة {dl['annee']}{evo} ({etat}).", taille=10, apres=1)
        restantes = [o for o in ops if o["statut"] in ("programmee", "en_cours", "reportee")]
        para(d, f"• العمليات غير المنجزة: {len(restantes)} (يمكن إعادة برمجتها في المشروع الجديد).", taille=10,
             apres=1)
        faibles = sorted([c for ax in so["axes"] for c in ax["criteres"] if c["taux"] is not None],
                         key=lambda c: c["taux"])[:3]
        if faibles:
            para(d, "• المعايير الأقل إنجازاً: " + "، ".join(f"{c['critere']} ({_n(c['taux'])})" for c in faibles),
                 taille=10, apres=1)
        if restantes:
            para(d, "", apres=2)
            _table(d, ["العملية", "المعيار", "الحالة", "الإنجاز"],
                   [[o["intitule"], o["critere"] or "—", STATUTS[o["statut"]], _n(o["taux"])] for o in restantes],
                   [7, 4.5, 2.5, 2])
    _signature(d, conn)
    an = a["libelle"] if a else p["annee_debut"]
    return _sauver_projet(d, dossier, an, "حصيلة_مشروع_المؤسسة" if final else "تقرير_تنزيل_مشروع_المؤسسة")


def generer_tableau_bord(conn: sqlite3.Connection, dossier: DossierDonnees, pid: int,
                         graphiques: dict[str, bytes] | None = None) -> Path:
    """وثيقة لوحة قيادة مشروع المؤسسة (طلب المدير 2026-11-13): صفحة أفقية واحدة، فيها لكل هدف بطاقة
    (المرجعية، آخر قيمة محققة، المستهدف، بلوغه) ومبيانه، ثم وضعية تنزيل العمليات والميزانية."""
    from docx.enum.section import WD_ORIENT
    from docx.shared import Cm

    from idara.services.docs_association import _cellule, _ombre, _nouveau, para, tableau
    from idara.services.soutien import _entete
    p = projet(conn, pid)
    ind = tableau_indicateurs(conn, pid)
    so = synthese_operations(conn, pid)
    a = annee_srv.annee_courante(conn)
    d = _nouveau()
    s = d.sections[0]
    s.orientation = WD_ORIENT.LANDSCAPE
    s.page_width, s.page_height = s.page_height, s.page_width
    s.left_margin = s.right_margin = Cm(1.4)
    s.top_margin = s.bottom_margin = Cm(1.0)
    _entete(d, conn, dossier, "لوحة قيادة مشروع المؤسسة المندمج",
            f"{p['intitule']} · {p['annee_debut']} - {p['annee_fin']}"
            + (f" · الوضعية في {date.today():%d/%m/%Y}" if a else ""))
    cles = list(ind)
    t = tableau(d, 3, len(cles), largeurs=[8.9] * len(cles))
    for j, k in enumerate(cles):
        x = ind[k]
        der = x["derniere"]
        cible = next((l["cible"] for l in reversed(x["annees"]) if l["cible"] is not None), None)
        if der and der["atteint"] is not None:
            etat = "بُلغ المستهدف" if der["atteint"] else "لم يُبلغ المستهدف بعد"
        else:
            etat = "في انتظار المعطيات"
        _cellule(t.cell(0, j), x["objectif"], gras=True, taille=10)
        _ombre(t.cell(0, j), "E7E8F8")
        _cellule(t.cell(1, j), (_n(der["realise"]) + f" ({der['annee']})") if der else "لا قيمة محققة بعد",
                 gras=True, taille=16)
        _cellule(t.cell(2, j), f"المرجعية: {_n(x['reference'])} · المستهدف: {_n(cible)} · {etat}", taille=9)
    if graphiques:
        g = tableau(d, 1, len(cles), bordures=False, largeurs=[8.9] * len(cles))
        for j, k in enumerate(cles):
            c = g.cell(0, j)
            if graphiques.get(k):
                c.paragraphs[0].add_run().add_picture(io.BytesIO(graphiques[k]), width=Cm(8.4))
                c.paragraphs[0].alignment = 1
    para(d, "", apres=2, taille=4)
    ps = so["par_statut"]
    t = tableau(d, 2, 8, largeurs=[3.2, 3.2, 3.6, 3.2, 3.2, 3.2, 3.6, 3.5])
    for j, (lib, v) in enumerate((("العمليات", so["total"]), ("منجزة", ps["realisee"]),
                                  ("في طور الإنجاز", ps["en_cours"]), ("مبرمجة", ps["programmee"]),
                                  ("مؤجلة", ps["reportee"]), ("ملغاة", ps["annulee"]),
                                  ("نسبة الإنجاز", _n(so["taux_global"])),
                                  ("المصروف من الميزانية", _n(so["pct_depense"])))):
        _cellule(t.cell(0, j), lib, gras=True, taille=9)
        _ombre(t.cell(0, j), "E7E8F8")
        _cellule(t.cell(1, j), str(v), gras=True, taille=12)
    para(d, f"الميزانية المبرمجة: {_dh(so['montant_programme'])} · المصروف: {_dh(so['montant_depense'])}",
         taille=9, apres=0)
    return _sauver_projet(d, dossier, a["libelle"] if a else p["annee_debut"], "لوحة_قيادة_مشروع_المؤسسة")


def _sauver_projet(d, dossier, annee: str, nom: str) -> Path:
    rep = dossier.archives / annee.replace("/", "-") / "مشروع المؤسسة"
    rep.mkdir(parents=True, exist_ok=True)
    chemin = rep / f"{datetime.now():%Y%m%d_%H%M%S}_{nom}.docx"
    n = 1
    while chemin.exists():
        n += 1
        chemin = chemin.with_name(f"{chemin.stem}_{n}.docx")
    d.save(chemin)
    return chemin

