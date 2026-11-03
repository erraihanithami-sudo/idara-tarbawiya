"""مجالس المؤسسة حسب المرسوم رقم 2.02.376 (17 يوليوز 2002) بمثابة النظام الأساسي الخاص بمؤسسات التربية
والتعليم العمومي، كما وقع تغييره وتتميمه، بالنسبة للمدرسة الابتدائية:

- مجلس التدبير (المواد 18-22): المدير رئيساً؛ ممثل عن هيئة التدريس عن كل مستوى؛ ممثل عن الأطر الإدارية
  والتقنية؛ رئيس جمعية آباء وأولياء التلاميذ؛ ممثل عن المجلس الجماعي. يجتمع مرتين على الأقل (بداية السنة
  ونهايتها)، والنصاب نصف الأعضاء في الجلسة الأولى، وإلا فاستدعاء ثانٍ داخل أسبوع والنصاب بالحاضرين؛
  القرارات بأغلبية الأصوات، وعند التعادل يرجح جانب الرئيس.
- المجلس التربوي (المواد 23-25): المدير رئيساً؛ ممثل عن هيئة التدريس عن كل مستوى؛ رئيس جمعية الآباء.
  دورتان على الأقل.
- المجالس التعليمية (المواد 26-28): لكل مادة: المدير رئيساً وجميع مدرسي المادة. دورتان على الأقل.
- مجالس الأقسام (المواد 29-31): في قسم التقييم.

المحاضر على نموذج المدير: «الحمد لله وحده»، التاريخ، جدول الأعمال، المداولات، ثم جدول التوقيعات
(الاسم، الصفة، التوقيع)؛ وللمجالس التعليمية جدول لكل مادة.
"""

from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from idara.data.dossier import DossierDonnees
from idara.services import annee as annee_srv
from idara.services import documents as dc
from idara.services import etablissement as etab_srv
from idara.services import evaluation as ev
from idara.services import textes as tx
from idara.services.docs_association import _cellule, _nouveau, _ombre, ajouter, para, tableau

CONSEILS = {"gestion": "مجلس التدبير", "pedagogique": "المجلس التربوي", "enseignement": "المجالس التعليمية"}
TITRES_SIGNATURES = {"gestion": "توقيعات أعضاء مجلس التدبير", "pedagogique": "توقيعات أعضاء المجلس التربوي",
                     "enseignement": "المجالس التعليمية"}
MINIMUM_ANNUEL = {"gestion": 2, "pedagogique": 2, "enseignement": 2}
GROUPES_ENSEIGNEMENT = ("عربية", "فرنسية")
NIVEAUX = ("الأول", "الثاني", "الثالث", "الرابع", "الخامس", "السادس")

# نقط مقترحة لجدول الأعمال: مهام كل مجلس كما في المرسوم، ثم صيغ محاضر المدير
SUGGESTIONS = {
    "gestion": (
        "دراسة برنامج العمل السنوي الخاص بأنشطة المؤسسة والموافقة عليه",
        "تحديد الإجراءات المتعلقة بتنظيم الدخول المدرسي",
        "النظر في التقرير السنوي العام المتعلق بنشاط وسير المؤسسة والمصادقة عليه",
        "تحديد حاجيات المؤسسة للسنة الدراسية الموالية والموافقة عليها",
        "اقتراح النظام الداخلي للمؤسسة",
        "دراسة برامج عمل المجلس التربوي والمجالس التعليمية والمصادقة عليها",
        "الاطلاع على قرارات مجالس المؤسسة ومناقشتها والمصادقة عليها",
        "دراسة التدابير الملائمة لضمان صيانة المؤسسة والمحافظة على ممتلكاتها",
        "إبداء الرأي بشأن مشاريع اتفاقيات الشراكة",
        "المصادقة على مشروع المؤسسة المندمج",
        "تتبع تنزيل البرامج المتعلقة بالمدرسة الرائدة",
        "قراءة في التقارير المرفوعة من طرف المجالس التعليمية والمجلس التربوي",
        "حصيلة السنة الدراسية",
    ),
    "pedagogique": (
        "برنامج عمل المؤسسة في المجال التربوي",
        "إعداد مشاريع البرامج السنوية للعمل التربوي وبرامج الأنشطة الداعمة والموازية",
        "التنسيق بين مختلف المواد الدراسية",
        "إبداء الرأي بشأن توزيع التلاميذ على الأقسام واستعمالات الزمن",
        "برمجة الاختبارات والامتحانات على صعيد المؤسسة",
        "دراسة طلبات المساعدة الاجتماعية واقتراح المستفيدين",
        "تنظيم الأنشطة والمسابقات الثقافية والرياضية والفنية",
        "المصادقة على توصيات المجالس التعليمية",
        "تقييم نسب النجاح وتطور مؤشر ISA2",
        "مقترحات من أجل تجويد العمل التربوي بالمؤسسة",
    ),
    "enseignement": (
        "دراسة وضعية تدريس المادة وتحديد حاجياتها التربوية",
        "الصعوبات المتعلقة بتدريس اللغتين العربية والفرنسية",
        "بعض المقترحات المتعلقة بتدريس اللغتين العربية والفرنسية",
        "تتبع نتائج تحصيل التلاميذ في المادة الدراسية",
        "تحديد الإكراهات المرتبطة بتدريس المادة وسبل تجاوزها والدعم التربوي الممتد",
        "وضع برمجة للعمليات التقويمية الخاصة بالمادة",
        "اختيار الكتب المدرسية الملائمة",
        "تحديد الحاجيات من التكوين لفائدة المدرسين",
        "اقتراح برنامج الأنشطة التربوية الخاصة بالمادة",
    ),
}


class ErreurConseil(ValueError):
    """رسالة موجهة للمدير بالعربية."""


def _txt(v) -> str:
    return " ".join(str(v or "").split())


def _annee(conn, annee: str | None = None) -> sqlite3.Row:
    if annee:
        r = conn.execute("SELECT * FROM annee_scolaire WHERE libelle=?", (annee,)).fetchone()
    else:
        r = annee_srv.annee_courante(conn)
    if r is None:
        raise ErreurConseil("السنة الدراسية غير محددة.")
    return r


# ---------- التركيبة ----------

def membres(conn, conseil: str, annee: str | None = None) -> list[sqlite3.Row]:
    a = _annee(conn, annee)
    return conn.execute("SELECT * FROM conseil_membre WHERE annee_id=? AND conseil=? ORDER BY COALESCE(groupe,''), "
                        "ordre, id", (a["id"], conseil)).fetchall()


def enregistrer_membres(conn, conseil: str, lignes: list[tuple], annee: str | None = None) -> None:
    """lignes: (الاسم، الصفة[، المادة]). يعوض التركيبة كاملة (الحضور المسجل لاجتماعات سابقة يبقى بأسمائه)."""
    if conseil not in CONSEILS:
        raise ErreurConseil("مجلس غير معروف.")
    a = _annee(conn, annee)
    propres = []
    for l in lignes:
        nom, qualite = _txt(l[0]), _txt(l[1] if len(l) > 1 else "")
        groupe = _txt(l[2]) if len(l) > 2 else ""
        if not nom and not qualite:
            continue
        if not nom or not qualite:
            raise ErreurConseil(f"العضو «{nom or qualite}»: الاسم والصفة معاً.")
        if conseil == "enseignement" and not groupe:
            raise ErreurConseil(f"العضو «{nom}»: حدد المادة (المجالس التعليمية لكل مادة).")
        propres.append((nom, qualite, groupe or None))
    if not propres:
        raise ErreurConseil("التركيبة فارغة.")
    anciens = {(r["nom"], r["qualite"], r["groupe"]): r["id"] for r in membres(conn, conseil, a["libelle"])}
    with conn:
        garder = set()
        for i, (nom, qualite, groupe) in enumerate(propres):
            mid = anciens.get((nom, qualite, groupe))
            if mid:
                conn.execute("UPDATE conseil_membre SET ordre=? WHERE id=?", (i, mid))
            else:
                mid = conn.execute("INSERT INTO conseil_membre(annee_id, conseil, groupe, nom, qualite, ordre) "
                                   "VALUES (?,?,?,?,?,?)", (a["id"], conseil, groupe, nom, qualite, i)).lastrowid
            garder.add(mid)
        for mid in set(anciens.values()) - garder:
            if conn.execute("SELECT 1 FROM conseil_presence WHERE membre_id=?", (mid,)).fetchone():
                conn.execute("UPDATE conseil_membre SET ordre=-1 WHERE id=?", (mid,))  # يبقى في المحاضر السابقة
            else:
                conn.execute("DELETE FROM conseil_membre WHERE id=?", (mid,))


def membres_actifs(conn, conseil: str, annee: str | None = None) -> list[sqlite3.Row]:
    return [m for m in membres(conn, conseil, annee) if m["ordre"] >= 0]


# أعضاء مجلس التدبير الذين يبقى حضورهم اختيارياً في الممارسة (قرار المدير 2026-11-03): يُضافون بخانة
OPTIONNELS = {"gestion": ["ممثل الأطر الإدارية والتقنية", "رئيس جمعية آباء وأولياء التلاميذ",
                          "ممثل المجلس الجماعي"]}


def optionnels(conseil: str) -> list[str]:
    return OPTIONNELS.get(conseil, [])


def proposition(conn, conseil: str, avec_optionnels: bool = False) -> list[tuple[str, str, str]]:
    """تركيبة مقترحة حسب المرسوم، من معطيات التطبيق: المدير، أساتذة كل مستوى (إسناد الأقسام)، والمقاعد الأخرى
    بصفتها فقط ليُكتب الاسم."""
    a = _annee(conn)
    d = etab_srv.directeur_actuel(conn)
    directeur = f"{d['prenom_ar']} {d['nom_ar']}" if d else ""
    res = [(directeur, "رئيس المجلس" if conseil != "enseignement" else "مدير المؤسسة", "")]
    par_niveau: dict[str, list[tuple[str, str]]] = {}
    for r in conn.execute(
            "SELECT DISTINCT p.prenom_ar, p.nom_ar, p.matiere, c.code FROM affectation_classe f JOIN classe c "
            "ON c.id=f.classe_id JOIN personnel p ON p.id=f.personnel_id WHERE c.annee_id=? AND p.statut='actif' "
            "ORDER BY c.code, p.nom_ar", (a["id"],)):
        from idara.services.massar import niveaux_du_code_classe
        for n in niveaux_du_code_classe(r["code"]):
            par_niveau.setdefault(n, []).append((f"{r['prenom_ar']} {r['nom_ar']}", r["matiere"] or ""))
    for i, o in enumerate(NIVEAUX, start=1):
        profs = par_niveau.get(f"{i}AP", [])
        if conseil == "enseignement":
            for g in GROUPES_ENSEIGNEMENT:
                noms = [n for n, m in profs if m in (g, "مزدوجة")]
                res.append((" + ".join(dict.fromkeys(noms)), f"ممثل القسم {o}", g))
        else:
            res.append((profs[0][0] if profs else "", f"ممثل القسم {o}", ""))
    if conseil == "enseignement":
        res = [(directeur, "مدير المؤسسة", g) for g in GROUPES_ENSEIGNEMENT] + res[1:]
    if avec_optionnels:
        res += [("", q, "") for q in optionnels(conseil)]
    if conseil == "pedagogique":
        res.append(("", "رئيس جمعية آباء وأولياء التلاميذ", ""))
    return res


def ecarts_decret(conn, conseil: str, annee: str | None = None) -> list[str]:
    """مقاعد ينص عليها المرسوم وليست في التركيبة المسجلة (تنبيه، لا منع). الأعضاء الاختياريون لا ينبَّه إليهم."""
    q = {m["qualite"] for m in membres_actifs(conn, conseil, annee)}
    attendus = {"gestion": [f"ممثل القسم {o}" for o in NIVEAUX],
                "pedagogique": [f"ممثل القسم {o}" for o in NIVEAUX] + ["رئيس جمعية آباء وأولياء التلاميذ"],
                "enseignement": []}[conseil]
    return [x for x in attendus if x not in q]


# ---------- الاجتماعات ----------

@dataclass
class Seance:
    conseil: str
    date_seance: str
    ordre_du_jour: list[str]
    heure: str = ""
    nature: str = "ordinaire"
    convocation: str = "premiere"
    deliberations: str = ""
    decisions: list[str] = field(default_factory=list)
    presents: list[int] | None = None        # معرفات الأعضاء الحاضرين (None: الجميع)
    inclure_resultats: bool = False
    inclure_isa: bool = False
    id: int | None = None


def quorum(conseil: str, n_membres: int, n_presents: int, convocation: str) -> tuple[bool, str]:
    if conseil != "gestion":
        return True, ""
    seuil = math.ceil(n_membres / 2)
    if convocation == "seconde":
        return True, "استدعاء ثانٍ: النصاب بالحاضرين (المادة 21)."
    if n_presents >= seuil:
        return True, f"النصاب مكتمل: {n_presents} من {n_membres} (المطلوب {seuil})."
    return False, (f"النصاب غير مكتمل: {n_presents} من {n_membres} والمطلوب نصف الأعضاء ({seuil}). يوجه استدعاء "
                   "ثانٍ داخل أسبوع ويكون النصاب بالحاضرين (المادة 21).")


def enregistrer_seance(conn, s: Seance, annee: str | None = None) -> int:
    if s.conseil not in CONSEILS:
        raise ErreurConseil("مجلس غير معروف.")
    a = _annee(conn, annee)
    try:
        d = date.fromisoformat(s.date_seance)
    except (TypeError, ValueError):
        raise ErreurConseil("تاريخ الاجتماع غير صحيح.") from None
    if d > date.today():
        raise ErreurConseil("تاريخ الاجتماع في المستقبل: يُسجل المحضر بعد انعقاد الاجتماع (والاستدعاء قبله).")
    odj = [_txt(x) for x in s.ordre_du_jour if _txt(x)]
    if not odj:
        raise ErreurConseil("جدول الأعمال إجباري.")
    ms = membres_actifs(conn, s.conseil, a["libelle"])
    if not ms:
        raise ErreurConseil(f"سجل تركيبة {CONSEILS[s.conseil]} أولاً.")
    ids = {m["id"] for m in ms}
    presents = ids if s.presents is None else set(s.presents) & ids
    ok, msg = quorum(s.conseil, len(ids), len(presents), s.convocation)
    if not ok:
        raise ErreurConseil(msg)
    vals = (d.isoformat(), _txt(s.heure) or None, s.nature, s.convocation, json.dumps(odj, ensure_ascii=False),
            (s.deliberations or "").strip() or None,
            json.dumps([_txt(x) for x in s.decisions if _txt(x)], ensure_ascii=False),
            int(s.inclure_resultats), int(s.inclure_isa))
    with conn:
        if s.id is None:
            n = conn.execute("SELECT COALESCE(MAX(numero),0)+1 FROM conseil_seance WHERE annee_id=? AND conseil=?",
                             (a["id"], s.conseil)).fetchone()[0]
            s.id = conn.execute(
                "INSERT INTO conseil_seance(annee_id, conseil, numero, date_seance, heure, nature, convocation, "
                "ordre_du_jour, deliberations, decisions, inclure_resultats, inclure_isa) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (a["id"], s.conseil, n, *vals)).lastrowid
        else:
            conn.execute("UPDATE conseil_seance SET date_seance=?, heure=?, nature=?, convocation=?, ordre_du_jour=?, "
                         "deliberations=?, decisions=?, inclure_resultats=?, inclure_isa=? WHERE id=?", (*vals, s.id))
            conn.execute("DELETE FROM conseil_presence WHERE seance_id=?", (s.id,))
        conn.executemany("INSERT INTO conseil_presence(seance_id, membre_id, present) VALUES (?,?,?)",
                         [(s.id, m, int(m in presents)) for m in ids])
    return s.id


def seances(conn, conseil: str | None = None, annee: str | None = None) -> list[sqlite3.Row]:
    a = _annee(conn, annee)
    sql, args = "SELECT * FROM conseil_seance WHERE annee_id=?", [a["id"]]
    if conseil:
        sql += " AND conseil=?"
        args.append(conseil)
    return conn.execute(sql + " ORDER BY date_seance, numero", args).fetchall()


def seance(conn, sid: int) -> Seance:
    r = conn.execute("SELECT * FROM conseil_seance WHERE id=?", (sid,)).fetchone()
    if r is None:
        raise ErreurConseil("الاجتماع غير موجود.")
    pres = [x[0] for x in conn.execute("SELECT membre_id FROM conseil_presence WHERE seance_id=? AND present=1", (sid,))]
    return Seance(r["conseil"], r["date_seance"], json.loads(r["ordre_du_jour"]), r["heure"] or "", r["nature"],
                  r["convocation"], r["deliberations"] or "", json.loads(r["decisions"] or "[]"), pres,
                  bool(r["inclure_resultats"]), bool(r["inclure_isa"]), r["id"])


def supprimer_seance(conn, sid: int) -> None:
    with conn:
        conn.execute("DELETE FROM conseil_seance WHERE id=?", (sid,))


def suivi(conn, annee: str | None = None) -> list[dict]:
    """لكل مجلس: عدد الاجتماعات مقابل الحد الأدنى في المرسوم، وتنبيهات."""
    a = _annee(conn, annee)
    res = []
    for c, lib in CONSEILS.items():
        ss = seances(conn, c, a["libelle"])
        alertes = []
        if len(ss) < MINIMUM_ANNUEL[c]:
            alertes.append(f"{len(ss)} من {MINIMUM_ANNUEL[c]} اجتماعات على الأقل في السنة")
        if c == "gestion":
            debut = [s for s in ss if s["date_seance"][5:7] in ("09", "10")]
            fin = [s for s in ss if s["date_seance"][5:7] in ("06", "07")]
            if not debut:
                alertes.append("دورة بداية السنة (برنامج العمل السنوي، الدخول المدرسي) غير مسجلة")
            if not fin:
                alertes.append("دورة نهاية السنة (التقرير السنوي العام، حاجيات السنة الموالية) غير مسجلة")
        ec = ecarts_decret(conn, c, a["libelle"])
        if not membres_actifs(conn, c, a["libelle"]):
            alertes.append("التركيبة غير مسجلة")
        elif ec:
            alertes.append("مقاعد ينص عليها المرسوم غير مسجلة: " + "، ".join(ec))
        res.append({"conseil": c, "libelle": lib, "nombre": len(ss), "minimum": MINIMUM_ANNUEL[c],
                    "derniere": ss[-1]["date_seance"] if ss else None, "alertes": alertes})
    return res


# ---------- الوثائق ----------

def _entete(conn, dossier: DossierDonnees, d) -> dict:
    try:
        c = dc.champs_communs(conn)
    except dc.ErreurDocument as e:
        raise ErreurConseil(str(e)) from None
    etab = etab_srv.lire_etablissement(conn)
    if etab and etab.logo_path:
        chemin = dossier.racine / etab.logo_path
        if chemin.exists():
            from docx.shared import Cm
            d.add_picture(str(chemin), width=Cm(17))
    return c


def _table_signatures(d, titre: str, ms: list, presents: set[int] | None) -> None:
    para(d, titre, gras=True, taille=16, centre=True, apres=2)
    lignes = [m for m in ms if presents is None or m["id"] in presents]
    t = tableau(d, 1 + len(lignes), 3, largeurs=[6.4, 5.6, 5.4])
    for j, lib in enumerate(("الاسم", "الصفة", "التوقيع")):
        _cellule(t.cell(0, j), lib, gras=True)
        _ombre(t.cell(0, j))
    from docx.shared import Cm
    for i, m in enumerate(lignes, start=1):
        _cellule(t.cell(i, 0), m["nom"], taille=14)
        _cellule(t.cell(i, 1), m["qualite"], taille=14)
        t.rows[i].height = Cm(1.0)
    para(d, apres=8)


def _table_resultats(conn, d, annee: str) -> None:
    stats = ev.stats_par_niveau(conn, annee)
    if not stats:
        return
    para(d, "المحصلة النهائية لنتائج المتعلمين على صعيد المؤسسة", gras=True, centre=True, apres=2)
    t = tableau(d, 3 + len(stats), 11, largeurs=[2.3] + [1.45] * 9 + [2.0])
    t.cell(0, 0).merge(t.cell(1, 0))
    _cellule(t.cell(0, 0), "المستويات", gras=True, taille=11)
    for k, lib in enumerate(("عدد التلاميذ", "عدد الحاصلين على المعدل", "عدد غير الحاصلين على المعدل")):
        t.cell(0, 1 + 3 * k).merge(t.cell(0, 3 + 3 * k))
        _cellule(t.cell(0, 1 + 3 * k), lib, gras=True, taille=11)
        for j, s in enumerate(("ذكور", "إناث", "مجموع")):
            _cellule(t.cell(1, 1 + 3 * k + j), s, gras=True, taille=10)
    t.cell(0, 10).merge(t.cell(1, 10))
    _cellule(t.cell(0, 10), "النسبة المئوية للحاصلين على المعدل", gras=True, taille=10)
    total = ev.Stats("المجموع")
    for i, s in enumerate(stats, start=2):
        total.plus(s)
        for j, v in enumerate((s.libelle, s.g, s.f, s.t, s.rg, s.rf, s.rt, s.eg, s.ef, s.et, s.pourcentage)):
            _cellule(t.cell(i, j), v if isinstance(v, str) else f"{v:02d}", taille=11)
    i = 2 + len(stats)
    for j, v in enumerate(("المجموع", total.g, total.f, total.t, total.rg, total.rf, total.rt, total.eg, total.ef,
                           total.et, total.pourcentage)):
        _cellule(t.cell(i, j), v if isinstance(v, str) else f"{v:02d}", taille=11, gras=True)
    para(d, apres=6)


def _table_isa(conn, d, annee: str) -> None:
    from idara.services import riyada as ry
    donnees = ry.isa(conn, annee)
    if not donnees:
        return
    phases = sorted({p for cl in donnees.values() for m in cl.values() for p in m})
    para(d, "تطور أداء المؤسسة حسب مؤشر ISA2", gras=True, centre=True, apres=2)
    # متوسط المؤسسة لكل مادة ومرحلة (متوسط نسب الأقسام)
    t = tableau(d, 1 + len(ry.MATIERES), 1 + len(phases), largeurs=[3.0] + [14.4 / len(phases)] * len(phases))
    _cellule(t.cell(0, 0), "المادة", gras=True, taille=11)
    for j, p in enumerate(phases, start=1):
        _cellule(t.cell(0, j), ry.libelle_phase(p), gras=True, taille=11)
    for i, (m, lib) in enumerate(ry.MATIERES.items(), start=1):
        _cellule(t.cell(i, 0), lib, taille=11)
        for j, p in enumerate(phases, start=1):
            vs = [cl[m][p] for cl in donnees.values() if m in cl and p in cl[m]]
            _cellule(t.cell(i, j), f"{sum(vs) / len(vs):.2f}%" if vs else "—", taille=11)
    para(d, "(متوسط نسب الأقسام)", taille=11, centre=True, apres=6)


def generer_pv(conn, dossier: DossierDonnees, sid: int) -> Path:
    s = seance(conn, sid)
    r = conn.execute("SELECT s.*, a.libelle FROM conseil_seance s JOIN annee_scolaire a ON a.id=s.annee_id WHERE s.id=?",
                     (sid,)).fetchone()
    annee = r["libelle"]
    d = _nouveau()
    c = _entete(conn, dossier, d)
    para(d, "الحمد لله وحده", gras=True, centre=True, apres=2)
    para(d, tx.date_longue_ar(s.date_seance), centre=True, apres=6)
    lib = CONSEILS[s.conseil]
    para(d, f"محضر اجتماع {lib} رقم {r['numero']}", gras=True, taille=20, centre=True, souligne=True, apres=8)
    heure = f" على الساعة {s.heure}" if s.heure else ""
    nature = "عادياً" if s.nature == "ordinaire" else "استثنائياً"
    sujet = {"gestion": f"مجلس تدبير {c['etablissement']}", "pedagogique": f"المجلس التربوي ل{c['etablissement']}",
             "enseignement": f"المجالس التعليمية ل{c['etablissement']}"}[s.conseil]
    verbe = "عقدت" if s.conseil == "enseignement" else "عقد"
    para(d, f"{verbe} {sujet} اجتماعاً {nature} يومه {tx.date_longue_ar(s.date_seance)}{heure} لتدارس النقاط المحددة "
            "في جدول الأعمال:", apres=2)
    for x in s.ordre_du_jour:
        para(d, f"- {x}", apres=0)
    para(d, apres=4)
    # أعضاء المجلس يوم الاجتماع (كما سُجل حضورهم)، لا التركيبة الحالية
    ms = conn.execute("SELECT m.* FROM conseil_presence p JOIN conseil_membre m ON m.id=p.membre_id WHERE p.seance_id=? "
                      "ORDER BY COALESCE(m.groupe,''), m.ordre, m.id", (sid,)).fetchall()
    presents = set(s.presents or [])
    absents = [m for m in ms if m["id"] not in presents]
    if s.conseil == "gestion":
        ok, msg = quorum(s.conseil, len(ms), len(presents), s.convocation)
        para(d, f"حضر الاجتماع {len(presents)} عضواً من أصل {len(ms)}. {msg}", taille=13, apres=2)
    if absents:
        para(d, "وتغيب: " + "، ".join(f"{m['nom']} ({m['qualite']})" for m in absents) + ".", taille=13, apres=4)
    if s.deliberations:
        for l in s.deliberations.splitlines():
            if l.strip():
                para(d, l.strip(), apres=3)
    else:
        for _ in range(10):
            para(d, "." * 150, taille=11, apres=2)
    if s.inclure_resultats:
        _table_resultats(conn, d, annee)
    if s.inclure_isa:
        _table_isa(conn, d, annee)
    if s.decisions:
        para(d, "القرارات والتوصيات:", gras=True, apres=2)
        for i, x in enumerate(s.decisions, start=1):
            para(d, f"{i}- {x}", apres=1)
    if s.conseil == "gestion":
        para(d, "تتخذ القرارات بأغلبية أصوات الحاضرين، وعند التعادل يرجح الجانب الذي ينتمي إليه رئيس المجلس.",
             taille=11, apres=4)
    para(d, apres=6)
    para(d, "رئيس المؤسسة", gras=True, centre=True, apres=12)
    if s.conseil == "enseignement":
        for g in dict.fromkeys(m["groupe"] for m in ms):
            _table_signatures(d, f"المجالس التعليمية {g}", [m for m in ms if m["groupe"] == g], presents)
    else:
        _table_signatures(d, TITRES_SIGNATURES[s.conseil], ms, presents)
    return _sauver(d, dossier, annee, f"محضر {lib} {r['numero']}")


def generer_convocation(conn, dossier: DossierDonnees, conseil: str, date_seance: str, heure: str,
                        ordre_du_jour: list[str], annee: str | None = None) -> Path:
    """استدعاء الأعضاء لحضور الاجتماع، مع لائحة التوقيع بالتوصل."""
    a = _annee(conn, annee)
    try:
        date.fromisoformat(date_seance)
    except (TypeError, ValueError):
        raise ErreurConseil("تاريخ الاجتماع غير صحيح.") from None
    odj = [_txt(x) for x in ordre_du_jour if _txt(x)]
    if not odj:
        raise ErreurConseil("جدول الأعمال إجباري.")
    if not _txt(heure):
        raise ErreurConseil("ساعة الاجتماع إجبارية في الاستدعاء.")
    ms = membres_actifs(conn, conseil, a["libelle"])
    if not ms:
        raise ErreurConseil(f"سجل تركيبة {CONSEILS[conseil]} أولاً.")
    d = _nouveau()
    c = _entete(conn, dossier, d)
    para(d, f"{c['ville']} في: {tx.date_longue_ar(date.today().isoformat())}", apres=6)
    para(d, f"استدعاء لحضور اجتماع {CONSEILS[conseil]}", gras=True, taille=20, centre=True, souligne=True, apres=8)
    para(d, f"يتشرف {c['mudir']} {c['etablissement']}، بصفته رئيساً ل{CONSEILS[conseil]}، بدعوة السادة الأعضاء "
            f"لحضور الاجتماع الذي سينعقد يوم {tx.date_longue_ar(date_seance)} على الساعة {_txt(heure)} بمقر المؤسسة، "
            "وذلك لتدارس النقط التالية:", apres=4)
    for x in odj:
        para(d, f"- {x}", apres=0)
    para(d, apres=4)
    para(d, "ونظراً لأهمية النقط المدرجة، يرجى الحرص على الحضور في الموعد المحدد.", apres=8)
    para(d, c["mudir_moassasa"], gras=True, centre=True, apres=12)
    para(d, "لائحة الأعضاء المستدعين", gras=True, centre=True, apres=2)
    t = tableau(d, 1 + len(ms), 4, largeurs=[5.4, 5.0, 3.0, 4.0])
    for j, lib in enumerate(("الاسم", "الصفة", "تاريخ التوصل", "التوقيع")):
        _cellule(t.cell(0, j), lib, gras=True, taille=13)
        _ombre(t.cell(0, j))
    for i, m in enumerate(ms, start=1):
        _cellule(t.cell(i, 0), m["nom"] + (f" ({m['groupe']})" if m["groupe"] else ""), taille=13)
        _cellule(t.cell(i, 1), m["qualite"], taille=13)
    return _sauver(d, dossier, a["libelle"], f"استدعاء {CONSEILS[conseil]}")


def _sauver(d, dossier: DossierDonnees, annee: str, nom: str) -> Path:
    rep = dossier.archives / annee.replace("/", "-") / "مجالس المؤسسة"
    rep.mkdir(parents=True, exist_ok=True)
    chemin = rep / f"{datetime.now():%Y%m%d_%H%M%S}_{nom}.docx"
    d.save(chemin)
    return chemin
