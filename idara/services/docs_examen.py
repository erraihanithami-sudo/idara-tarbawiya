"""وثائق الامتحان (تطبيق الامتحان الذي أرسله المدير، 2026-11-03). النصوص من أوراقه كما هي، مع تكييف ما يخص
السلك الإعدادي: «المسلك» حُذف، و«المستوى» هو السادس ابتدائي.

1. لوائح المترشحين حسب القاعة، أوراق الحضور، ترقيم الطاولات، استدعاءات المترشحين.
2. توزيع المراقبين على القاعات، استدعاءات المكلفين، الشارات، كتابة الامتحان.
3. الإعلان والجدولة الزمنية، أوراق التنقيط.
4. محضرا فتح أظرفة المواضيع وإغلاق أظرفة الامتحان، بطاقة مركز الامتحان وبطاقة مركز التصحيح، تقرير رئيس
   المركز، تقرير الملاحظ، محضر تقرير حول حالة غش.
المطبوعات (المحاضر والتقارير) تبقى فيها أسطر للكتابة باليد كما في النموذج؛ المعطيات المتوفرة تُملأ آلياً.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from docx.shared import Cm

from idara.data.dossier import DossierDonnees
from idara.services import documents as dc
from idara.services import etablissement as etab_srv
from idara.services import examens as exs
from idara.services import textes as tx
from idara.services.docs_association import _cellule, _nouveau, _ombre, para, saut_page, tableau

NIVEAU = "السادس ابتدائي"
POINTS = "." * 70
CASE = "☐"

DOCUMENTS = {
    "listes": ("لوائح المترشحين حسب القاعة", 1), "presence": ("أوراق حضور المترشحين", 1),
    "tables": ("ترقيم الطاولات", 1), "convocations": ("استدعاءات المترشحين", 1),
    "repartition": ("توزيع المراقبين على القاعات", 2), "convocations_profs": ("استدعاءات المكلفين بمهام", 2),
    "badges": ("الشارات", 2), "secretariat": ("كتابة الامتحان", 2),
    "annonce": ("الإعلان والجدولة الزمنية", 3), "notation": ("أوراق التنقيط", 3),
    "ouverture": ("محاضر فتح أظرفة المواضيع", 4), "fermeture": ("محاضر إغلاق أظرفة الامتحان", 4),
    "centre": ("بطاقة مركز الامتحان", 4), "correction": ("بطاقة مركز التصحيح", 4),
    "rapport_president": ("تقرير رئيس المركز", 4), "rapport_observateur": ("تقرير الملاحظ", 4),
    "fraude": ("محضر تقرير حول حالة غش", 4),
}


def _jour(j: str) -> str:
    return f"{tx.JOURS_AR[date.fromisoformat(j).weekday()]} {tx.date_chiffres(j)}"


def _ctx(conn, eid: int) -> dict:
    ex = conn.execute("SELECT e.*, a.libelle AS annee FROM examen e JOIN annee_scolaire a ON a.id=e.annee_id "
                      "WHERE e.id=?", (eid,)).fetchone()
    if ex is None:
        raise exs.ErreurExamen("الامتحان غير موجود.")
    try:
        c = dc.champs_communs(conn)
    except dc.ErreurDocument as e:
        raise exs.ErreurExamen(str(e)) from None
    return {"ex": ex, "etab": etab_srv.lire_etablissement(conn), "c": c, "matieres": exs.matieres(conn, eid),
            "salles": exs.salles(conn, eid), "candidats": exs.candidats(conn, eid), "aff": exs.affectations(conn, eid)}


def _exiger(ctx: dict, *quoi: str) -> None:
    m = []
    if "matieres" in quoi and not ctx["matieres"]:
        m.append("جدولة المواد")
    if "candidats" in quoi and not ctx["candidats"]:
        m.append("لائحة المترشحين")
    if "surveillance" in quoi and not any(a["role"] == exs.SURVEILLANCE for a in ctx["aff"]):
        m.append("توزيع المراقبين")
    if "roles" in quoi and not any(a["role"] != exs.SURVEILLANCE for a in ctx["aff"]):
        m.append("المكلفون بالمهام (رئيس المركز...)")
    if m:
        raise exs.ErreurExamen("أكمل أولاً: " + "، ".join(m) + ".")


def _entete(conn, dossier: DossierDonnees, d, ctx: dict, titre: str, sous: str = "") -> None:
    etab, ex = ctx["etab"], ctx["ex"]
    if etab.logo_path and (dossier.racine / etab.logo_path).exists():
        d.add_picture(str(dossier.racine / etab.logo_path), width=Cm(16))
    else:
        for l in ("المملكة المغربية", "وزارة التربية الوطنية والتعليم الأولي والرياضة",
                  f"الأكاديمية الجهوية للتربية والتكوين: {etab.academie_ar or ''}",
                  f"المديرية الإقليمية: {etab.direction_ar or ''}"):
            para(d, l, gras=True, taille=10, apres=0)
    t = tableau(d, 2, 2, bordures=False, largeurs=[11, 6])
    _cellule(t.cell(0, 0), f"مركز الامتحان: {ex['centre']}" + (f" ({ex['code_centre']})" if ex["code_centre"] else ""),
             taille=10, centre=False)
    _cellule(t.cell(0, 1), f"السنة الدراسية: {ex['annee']}", taille=10, centre=False)
    _cellule(t.cell(1, 0), ex["intitule"], gras=True, taille=10, centre=False)
    _cellule(t.cell(1, 1), f"الدورة: {ex['session'] or '—'}", taille=10, centre=False)
    para(d, titre, gras=True, taille=15, centre=True, souligne=True, apres=2)
    if sous:
        para(d, sous, gras=True, taille=11, centre=True, apres=4)


def _table(d, entetes: list[str], lignes: list[list[str]], largeurs: list[float], taille=10, hauteur_vide=0):
    t = tableau(d, 1 + len(lignes), len(entetes), largeurs=largeurs)
    for j, h in enumerate(entetes):
        _cellule(t.cell(0, j), h, gras=True, taille=taille)
        _ombre(t.cell(0, j))
    for i, l in enumerate(lignes, start=1):
        for j, v in enumerate(l):
            _cellule(t.cell(i, j), v, taille=taille, centre=True)
    return t


def _sauver(d, dossier: DossierDonnees, ctx: dict, nom: str) -> Path:
    ex = ctx["ex"]
    rep = dossier.archives / ex["annee"].replace("/", "-") / ("الامتحان المحلي" if ex["type"] == "local"
                                                              else "الامتحان الإقليمي")
    rep.mkdir(parents=True, exist_ok=True)
    chemin = rep / f"{datetime.now():%Y%m%d_%H%M%S}_{nom}.docx"
    d.save(chemin)
    return chemin


def _par_salle(ctx: dict) -> list[tuple[dict, list]]:
    return [(s, [c for c in ctx["candidats"] if c["salle_id"] == s["id"]]) for s in ctx["salles"]]


def _surveillants(ctx: dict, salle_num: int, matiere_id: int) -> list:
    return [a for a in ctx["aff"] if a["role"] == exs.SURVEILLANCE and a["salle_numero"] == salle_num
            and a["matiere_id"] == matiere_id]


def _role(ctx: dict, role: str, matiere_id: int | None = None) -> list:
    return [a for a in ctx["aff"] if a["role"] == role and (matiere_id is None or a["matiere_id"] == matiere_id)]


# ======================= 1. المترشحون =======================

def _listes(conn, dossier, ctx) -> Path:
    _exiger(ctx, "candidats")
    d = _nouveau()
    for k, (s, cs) in enumerate(_par_salle(ctx)):
        if k:
            saut_page(d)
        _entete(conn, dossier, d, ctx, "لائحة المترشحين", f"المستوى: {NIVEAU} · {s['nom']} (رقم {s['numero']})")
        _table(d, ["ر.ت", "رقم الامتحان", "الاسم الكامل", "الرقم الوطني", "تاريخ الازدياد", "القسم"],
               [[str(i), str(c["numero"]), c["nom"], c["code_massar"] or "", tx.date_chiffres(c["date_naissance"])
                 if c["date_naissance"] else "", c["classe"] or ""] for i, c in enumerate(cs, 1)],
               [1, 2.2, 6, 2.8, 2.4, 2.6])
        para(d, f"عدد المترشحين بالقاعة: {len(cs)}", gras=True, apres=2)
    return _sauver(d, dossier, ctx, "لوائح المترشحين حسب القاعة")


def _presence(conn, dossier, ctx) -> Path:
    _exiger(ctx, "candidats", "matieres")
    d = _nouveau()
    k = 0
    for m in ctx["matieres"]:
        for s, cs in _par_salle(ctx):
            if k:
                saut_page(d)
            k += 1
            _entete(conn, dossier, d, ctx, "ورقة حضور المترشحين",
                    f"{s['nom']} · المادة: {m['matiere']} · {_jour(m['jour'])} من {m['debut']} إلى {m['fin']}")
            _table(d, ["ر.ت", "رقم الامتحان", "الاسم الكامل", "الرقم الوطني", "التوقيع", "ملاحظات"],
                   [[str(i), str(c["numero"]), c["nom"], c["code_massar"] or "", "", ""] for i, c in enumerate(cs, 1)],
                   [1, 2.2, 6, 2.8, 2.6, 2.4])
            para(d, f"عدد المترشحين: {len(cs)}      عدد الحاضرين: ..........      عدد الغائبين: ..........",
                 gras=True, taille=10, apres=4)
            sv = _surveillants(ctx, s["numero"], m["id"])
            _table(d, ["الأستاذ(ة) المراقب(ة)", "رقم التأجير", "التوقيع"],
                   [[a["nom"], a["ppr"] or "", ""] for a in sv] or [["", "", ""], ["", "", ""]], [7, 3, 4])
    return _sauver(d, dossier, ctx, "أوراق حضور المترشحين")


def _tables(conn, dossier, ctx) -> Path:
    """ترقيم الطاولات: بطاقتان في كل سطر (الاسم، رقم الامتحان، القاعة، رقم مسار)."""
    _exiger(ctx, "candidats")
    d = _nouveau()
    cs = ctx["candidats"]
    lignes = (len(cs) + 1) // 2
    t = tableau(d, lignes, 2, largeurs=[8.6, 8.6])
    for k, c in enumerate(cs):
        cell = t.cell(k // 2, k % 2)
        _cellule(cell, f"رقم الامتحان: {c['numero']}", gras=True, taille=16)
        para(cell, c["nom"], gras=True, taille=12, centre=True, apres=0)
        para(cell, f"{c['salle_nom'] or ''} · رقم مسار: {c['code_massar'] or '—'}", taille=10, centre=True, apres=4)
    return _sauver(d, dossier, ctx, "ترقيم الطاولات")


def _convocations(conn, dossier, ctx) -> Path:
    """استدعاء لكل مترشح (اثنان في الصفحة)."""
    _exiger(ctx, "candidats", "matieres")
    d = _nouveau()
    etab, ex = ctx["etab"], ctx["ex"]
    for k, c in enumerate(ctx["candidats"]):
        if k and k % 2 == 0:
            saut_page(d)
        cadre = tableau(d, 1, 1, largeurs=[17.4])
        cell = cadre.cell(0, 0)
        _cellule(cell, f"الأكاديمية: {etab.academie_ar or ''} · مديرية: {etab.direction_ar or ''}", taille=9,
                 centre=False)
        para(cell, f"المؤسسة: {ex['centre']}", taille=9, apres=2)
        para(cell, f"استدعاء لاجتياز {ex['intitule']} ({ex['session'] or ''})", gras=True, taille=12, centre=True,
             apres=2)
        para(cell, f"المترشح(ة): {c['nom']} · الرمز: {c['code_massar'] or '—'}", gras=True, taille=11, apres=0)
        para(cell, f"القاعة: {c['salle_nom'] or '—'} · رقم الامتحان: {c['numero']}", gras=True, taille=11, apres=2)
        t = tableau(cell, 1 + len(ctx["matieres"]), 4, largeurs=[5, 4, 3, 3])
        for j, h in enumerate(("المادة", "التاريخ", "من الساعة", "إلى الساعة")):
            _cellule(t.cell(0, j), h, gras=True, taille=9)
            _ombre(t.cell(0, j))
        for i, m in enumerate(ctx["matieres"], 1):
            for j, v in enumerate((m["matiere"], _jour(m["jour"]), m["debut"], m["fin"])):
                _cellule(t.cell(i, j), v, taille=9)
        para(cell, "يجب على المترشحين الحضور لمركز الامتحان نصف ساعة قبل وقت الإجراء", gras=True, taille=9,
             centre=True, apres=2)
        para(d, "", apres=10)
    return _sauver(d, dossier, ctx, "استدعاءات المترشحين")


# ======================= 2. المكلفون =======================

def _repartition(conn, dossier, ctx) -> Path:
    _exiger(ctx, "matieres", "surveillance")
    d = _nouveau(paysage=True)
    _entete(conn, dossier, d, ctx, "توزيع المراقبين على القاعات")
    profs = {}
    for a in ctx["aff"]:
        if a["role"] == exs.SURVEILLANCE:
            profs.setdefault(a["personnel_id"], a)
    mat = {r["id"]: r["matiere"] for r in exs.enseignants(conn)}
    cols = ["ر.ت", "الأستاذ(ة)", "رقم التأجير", "مادة التدريس"] + [f"{m['matiere']}\n{_jour(m['jour'])}"
                                                                 for m in ctx["matieres"]]
    lignes = []
    for i, (pid, a) in enumerate(sorted(profs.items(), key=lambda x: x[1]["nom"]), 1):
        l = [str(i), a["nom"], a["ppr"] or "", mat.get(pid) or ""]
        for m in ctx["matieres"]:
            s = next((x["salle_numero"] for x in ctx["aff"] if x["role"] == exs.SURVEILLANCE
                      and x["personnel_id"] == pid and x["matiere_id"] == m["id"]), None)
            l.append(f"القاعة {s}" if s else "—")
        lignes.append(l)
    n = len(ctx["matieres"])
    _table(d, cols, lignes, [1, 5, 2.4, 2.4] + [max(2.2, 14 / max(n, 1))] * n, taille=9)
    para(d, "", apres=10)
    para(d, "طابع وتوقيع رئيس(ة) مركز الامتحان", gras=True, apres=30)
    return _sauver(d, dossier, ctx, "توزيع المراقبين على القاعات")


def _missions(ctx: dict, pid: int) -> list[list[str]]:
    res = []   # (اليوم ISO، الساعة، السطر)
    for a in ctx["aff"]:
        if a["personnel_id"] != pid:
            continue
        if a["matiere_id"]:
            mission = f"مراقبة القاعة {a['salle_numero']}" if a["role"] == exs.SURVEILLANCE else a["role"]
            res.append((a["jour"], a["debut"], [a["matiere"], _jour(a["jour"]), a["debut"], a["fin"], mission]))
        else:
            for m in ctx["matieres"]:
                res.append((m["jour"], m["debut"], [m["matiere"], _jour(m["jour"]), m["debut"], m["fin"], a["role"]]))
    return [l for _, _, l in sorted(res, key=lambda x: (x[0], x[1]))]


def _convocations_profs(conn, dossier, ctx) -> Path:
    _exiger(ctx, "matieres")
    pids = list(dict.fromkeys(a["personnel_id"] for a in ctx["aff"] if a["personnel_id"]))
    if not pids:
        raise exs.ErreurExamen("أكمل أولاً: المكلفون بالمهام أو توزيع المراقبين.")
    d = _nouveau()
    etab, ex, c = ctx["etab"], ctx["ex"], ctx["c"]
    for k, pid in enumerate(pids):
        if k:
            saut_page(d)
        a = next(x for x in ctx["aff"] if x["personnel_id"] == pid)
        sexe = (conn.execute("SELECT sexe FROM personnel WHERE id=?", (pid,)).fetchone() or ["M"])[0]
        _entete(conn, dossier, d, ctx, "", "")
        para(d, f"{etab.ville_redaction_ar or ''} في: {tx.date_chiffres(date.today().isoformat())}", apres=6)
        para(d, f"من {c['mudir_moassasa']}", gras=True, apres=0)
        para(d, f"إلى {tx.accord(sexe, 'السيد', 'السيدة')}: {a['nom']} · رقم التأجير: {a['ppr'] or '—'}", gras=True,
             apres=6)
        para(d, f"الموضوع: استدعاء لمهام {ex['intitule']}", gras=True, souligne=True, apres=6)
        para(d, "سلام تام بوجود مولانا الإمام المؤيد بالله", centre=True, apres=4)
        roles = list(dict.fromkeys("المراقبة" if x["role"] == exs.SURVEILLANCE else x["role"]
                                   for x in ctx["aff"] if x["personnel_id"] == pid))
        para(d, f"وبعد، يشرفني أن أدعوكم للحضور لأداء مهام: {'، '.join(roles)}، على الشكل التالي:", apres=4)
        _table(d, ["مادة الاختبار", "اليوم", "من", "إلى", "المهمة"], _missions(ctx, pid), [4, 4, 1.8, 1.8, 5])
        para(d, "ولهذا أهيب بكم أن تولوا هذه المهمة المنوطة بكم ما تستحقه من العناية المعهودة فيكم حتى تمر "
                "الامتحانات في أحسن الظروف.", apres=4)
        para(d, "ملحوظة: يجب الحضور إلى مركز الامتحان 45 دقيقة قبل موعد الامتحان.", gras=True, apres=10)
        t = tableau(d, 1, 2, bordures=False, largeurs=[8.5, 8.5])
        _cellule(t.cell(0, 0), "توقيع المعني(ة) بالأمر:", gras=True)
        _cellule(t.cell(0, 1), "طابع وتوقيع رئيس(ة) مركز الامتحان:", gras=True)
    return _sauver(d, dossier, ctx, "استدعاءات المكلفين بمهام")


def _badges(conn, dossier, ctx) -> Path:
    _exiger(ctx, "matieres")
    vus, personnes = set(), []
    for a in ctx["aff"]:
        if a["personnel_id"] not in vus:
            vus.add(a["personnel_id"])
            roles = list(dict.fromkeys("لجنة المراقبة" if x["role"] == exs.SURVEILLANCE else x["role"]
                                       for x in ctx["aff"] if x["personnel_id"] == a["personnel_id"]))
            personnes.append((a["nom"], "، ".join(roles)))
    if not personnes:
        raise exs.ErreurExamen("أكمل أولاً: المكلفون بالمهام أو توزيع المراقبين.")
    d = _nouveau()
    etab, ex = ctx["etab"], ctx["ex"]
    t = tableau(d, (len(personnes) + 1) // 2, 2, largeurs=[8.6, 8.6])
    for k, (nom, mission) in enumerate(personnes):
        cell = t.cell(k // 2, k % 2)
        _cellule(cell, f"الأكاديمية الجهوية: {etab.academie_ar or ''}", taille=8)
        para(cell, f"المديرية الإقليمية: {etab.direction_ar or ''}", taille=8, centre=True, apres=0)
        para(cell, f"مركز الامتحان: {ex['centre']}", gras=True, taille=10, centre=True, apres=2)
        para(cell, f"الاسم: {nom}", gras=True, taille=12, centre=True, apres=0)
        para(cell, f"المهمة: {mission}", gras=True, taille=11, centre=True, apres=2)
        para(cell, f"{ex['intitule']} · دورة {ex['session'] or ''}", taille=8, centre=True, apres=6)
    return _sauver(d, dossier, ctx, "الشارات")


def _secretariat(conn, dossier, ctx) -> Path:
    _exiger(ctx, "roles")
    d = _nouveau()
    _entete(conn, dossier, d, ctx, "كتابة الامتحان")
    lignes = []
    for role in exs.ROLES[:3]:
        for k, a in enumerate(_role(ctx, role), 1):
            lib = f"{role} {k}" if role == exs.ROLES[2] else role
            lignes.append([lib, a["nom"], a["ppr"] or ""])
    for m in ctx["matieres"]:
        for a in _role(ctx, exs.ROLES[3], m["id"]):
            lignes.append([f"أستاذ(ة) مداوم(ة): {m['matiere']} ({_jour(m['jour'])})", a["nom"], a["ppr"] or ""])
    _table(d, ["الصفة", "الاسم الكامل", "رقم التأجير"], lignes, [7, 7, 3])
    return _sauver(d, dossier, ctx, "كتابة الامتحان")


# ======================= 3. الإعلان والتنقيط =======================

def _annonce(conn, dossier, ctx) -> Path:
    _exiger(ctx, "matieres")
    d = _nouveau()
    ex, ms = ctx["ex"], ctx["matieres"]
    _entete(conn, dossier, d, ctx, "إعـــلان")
    para(d, f"تعلن إدارة المؤسسة إلى كافة التلميذات والتلاميذ أن {ex['intitule']} سيجرى من: {_jour(ms[0]['jour'])} "
            f"إلى: {_jour(ms[-1]['jour'])} حسب الجدول التالي:", taille=12, apres=4)
    _table(d, ["اليوم", "المادة", "من", "إلى"], [[_jour(m["jour"]), m["matiere"], m["debut"], m["fin"]] for m in ms],
           [5, 6, 2.5, 2.5], taille=11)
    para(d, "فعلى الجميع التقيد بما يلي:", gras=True, taille=12, apres=2)
    for l in ("1- عدم دخول المركز إلا باستدعاء متضمن لمهمة.",
              "2- جميع الإجراءات الإدارية العادية ستتوقف طيلة أيام إجراء الامتحانات.",
              "3- يجب على المكلفين بمهام، والمترشحين الحضور إلى مركز الامتحان بنصف ساعة قبل التوقيت المحدد للامتحان.",
              "4- يمنع منعاً كلياً على المترشحين والمكلفين بمهام إدخال الهاتف النقال أو أية وسيلة إلكترونية إلى "
              "مركز الامتحان."):
        para(d, l, taille=11, apres=2)
    para(d, "عن الإدارة", gras=True, taille=12, apres=30)
    saut_page(d)
    _entete(conn, dossier, d, ctx, "الجدولة الزمنية للامتحان")
    para(d, f"تعلن إدارة المؤسسة أن {ex['intitule']} (دورة {ex['session'] or ''}) سيجرى وفق ما يلي:", apres=4)
    _table(d, ["ر.ت", "المادة", "اليوم", "من", "إلى"],
           [[str(i), m["matiere"], _jour(m["jour"]), m["debut"], m["fin"]] for i, m in enumerate(ms, 1)],
           [1, 6, 5, 2.5, 2.5], taille=11)
    return _sauver(d, dossier, ctx, "الإعلان والجدولة الزمنية")


def _notation(conn, dossier, ctx) -> Path:
    _exiger(ctx, "candidats", "matieres")
    d = _nouveau()
    k = 0
    for m in ctx["matieres"]:
        for s, cs in _par_salle(ctx):
            if k:
                saut_page(d)
            k += 1
            _entete(conn, dossier, d, ctx, "ورقة التنقيط", f"المادة: {m['matiere']} · {s['nom']}")
            _table(d, ["ر.ت", "رقم القاعة", "رقم الامتحان", "رمز مسار", "الاسم الكامل", "النقطة", "ملاحظات"],
                   [[str(i), str(s["numero"]), str(c["numero"]), c["code_massar"] or "", c["nom"], "", ""]
                    for i, c in enumerate(cs, 1)], [1, 1.6, 2, 2.6, 5.4, 1.8, 2.6])
            para(d, "", apres=6)
            para(d, "اسم وتوقيع المصحح(ة): ....................................", gras=True, apres=4)
    return _sauver(d, dossier, ctx, "أوراق التنقيط")


# ======================= 4. المحاضر والتقارير =======================

def _ligne_membre(ctx, role: str, matiere_id=None) -> list[str]:
    a = (_role(ctx, role, matiere_id) or [None])[0]
    return [a["nom"] if a else "", a["ppr"] or "" if a else ""]


def _pv_plis(conn, dossier, ctx, fermeture: bool) -> Path:
    _exiger(ctx, "matieres")
    d = _nouveau()
    for k, m in enumerate(ctx["matieres"]):
        if k:
            saut_page(d)
        if fermeture:
            _entete(conn, dossier, d, ctx, "محضر إغلاق أظرفة الامتحان")
        else:
            _entete(conn, dossier, d, ctx, "محضر التأكد من معلومات ظرف الموضوع ومن فتحه")
        para(d, f"الدورة: العادية {CASE}    الاستدراكية {CASE}", apres=4)
        para(d, "نحن الموقعين أسفله:", gras=True, apres=2)
        if fermeture:
            para(d, "نشهد أننا تأكدنا من تطابق معلومات ظرف أوراق التحرير مع جدولة الامتحانات قبل إغلاقه والذي يخص",
                 apres=2)
        else:
            para(d, "نشهد أننا تأكدنا من تطابق معلومات ظرف الموضوع مع جدولة الامتحانات قبل فتحه والذي يخص", apres=2)
        para(d, f"مادة: {m['matiere']}      المستوى: {NIVEAU}", gras=True, apres=0)
        para(d, f"اليوم: {_jour(m['jour'])}      الساعة: {m['debut']}      إلى الساعة: {m['fin']}", gras=True, apres=4)
        para(d, f"ونشهد بأن هذا الظرف قد تم {'إغلاقه' if fermeture else 'فتحه'} أمامنا", apres=0)
        para(d, "يوم: ..................................  على الساعة: ..................................", apres=4)
        if not fermeture:
            para(d, "بعد التأكد من:", gras=True, apres=0)
            para(d, "1 - مطابقة المادة المذكورة أعلاه لليومية المنظمة لمواقيت إجراء مختلف المواد.", apres=0)
            para(d, "2 - كون الغلاف البلاستيكي الداخلي محكم الإغلاق وسليم من كل تمزيق.", apres=4)
        lignes = [["رئيس(ة) المركز", *_ligne_membre(ctx, exs.ROLES[0]), "", ""],
                  ["مراقب جودة الإجراء", *_ligne_membre(ctx, exs.ROLES[1]), "", ""],
                  ["أستاذ مداوم", *_ligne_membre(ctx, exs.ROLES[3], m["id"]), "", ""],
                  ["ممثل لجنة الحراسة", "", "", "", ""]]
        lignes += ([["عضو كتابة الامتحان", *_ligne_membre(ctx, exs.ROLES[2]), "", ""]] if fermeture else
                   [["مترشح 1", "", "", "", ""], ["مترشح 2", "", "", "", ""]])
        _table(d, ["المهمة", "الاسم والنسب", "رقم التأجير", "التوقيع", "ملاحظات حول الظرف"], lignes, [3.6, 5, 2.4, 3, 3.4])
        para(d, "", apres=6)
        para(d, "توقيع رئيس(ة) المركز:", gras=True, apres=30)
    return _sauver(d, dossier, ctx, "محاضر إغلاق أظرفة الامتحان" if fermeture else "محاضر فتح أظرفة المواضيع")


def _carte(conn, dossier, ctx, correction: bool) -> Path:
    d = _nouveau()
    _entete(conn, dossier, d, ctx, "بطاقة مركز التصحيح" if correction else "بطاقة مركز الامتحان")
    para(d, f"الدورة: العادية {CASE}    الاستدراكية {CASE}", apres=4)
    if correction:
        lignes = [[str(i), "", "", "", "", ""] for i in range(1, 13)]
    else:
        _exiger(ctx, "roles")
        vus, lignes = set(), []
        for a in ctx["aff"]:
            if a["personnel_id"] in vus:
                continue
            vus.add(a["personnel_id"])
            roles = list(dict.fromkeys("مراقب(ة)" if x["role"] == exs.SURVEILLANCE else x["role"]
                                       for x in ctx["aff"] if x["personnel_id"] == a["personnel_id"]))
            lignes.append([str(len(lignes) + 1), a["nom"], a["ppr"] or "", a["cadre"] or "", "، ".join(roles), ""])
    _table(d, ["ر.ت", "الاسم الكامل", "رقم التأجير", "الإطار", "المهمة أثناء الامتحان *", "ملاحظات"], lignes,
           [1, 4.6, 2.2, 3.6, 3.8, 2.2], taille=9)
    para(d, "* يتعين تحديد المهمة المنوطة بكل عضو داخل مركز " + ("التصحيح." if correction else "الامتحان."),
         taille=9, apres=10)
    t = tableau(d, 1, 2, bordures=False, largeurs=[8.5, 8.5])
    _cellule(t.cell(0, 0), "مصادقة السيد المدير الإقليمي:", gras=True)
    _cellule(t.cell(0, 1), f"توقيع السيد(ة) رئيس(ة) مركز {'التصحيح' if correction else 'الامتحان'}:", gras=True)
    return _sauver(d, dossier, ctx, "بطاقة مركز التصحيح" if correction else "بطاقة مركز الامتحان")


def _oui_non(texte: str) -> str:
    return f"{texte}   نعم {CASE}   لا {CASE}"


def _rapport(conn, dossier, ctx, observateur: bool) -> Path:
    d = _nouveau()
    _entete(conn, dossier, d, ctx, "تقرير الملاحظ" if observateur else "تقرير رئيس المركز")
    para(d, f"الدورة العادية {CASE}    الدورة الاستدراكية {CASE}", apres=4)
    L = lambda t, g=False: para(d, t, gras=g, taille=10, apres=1)  # noqa: E731
    L("عملية فتح أظرفة المواضيع:", True)
    L(f"مكان فتح الأظرفة: {POINTS}")
    L("توقيت فتح الأظرفة: اليوم: .................. الساعة: .......... الدقيقة: ..........")
    L("حضور أعضاء لجنة فتح أظرفة المواضيع:", True)
    for a, b in (("رئيس مركز الامتحان:", "ممثل عن لجنة الحراسة:"), ("الملاحظ(ة):", "المترشح الأول:"),
                 ("الأستاذ(ة) المداوم(ة):", "المترشح الثاني:")):
        L(f"{_oui_non(a)}        {_oui_non(b)}")
    L(_oui_non("مطابقة محتوى الظرف مع مادة الاختبار:"))
    L(f"في حالة الإجابة بلا، ما هي الإجراءات التي تم اتخاذها؟ {POINTS}")
    L(_oui_non("عدد نسخ الموضوع كافية:"))
    L(f"في حالة الإجابة بلا، ما هي الطريقة التي تم اعتمادها لحل المشكل؟ {POINTS}")
    L("1 - انطلاق الاختبارات:", True)
    L("توقيت انطلاق الاختبارات: الساعة: .......... الدقيقة: ..........")
    L(_oui_non("هل تم تسجيل تأخر في انطلاق اختبار ما؟"))
    L(f"في حالة الإجابة بنعم أذكر الأسباب: {POINTS}")
    L("2 - الالتزام بمساطر الإجراء:", True)
    L(_oui_non("خلال زيارتكم لقاعات مركز الامتحان هل تم التزام المكلفين بالإجراء بجميع المساطر المحددة في دليل "
               "المكلف بالإجراء؟"))
    L(f"في حالة الإجابة بلا، ما هي المساطر التي لم يتم الالتزام بها: {POINTS}")
    L("3 - زيارة مركز الامتحان:", True)
    _table(d, ["اسم الزائر", "الصفة", "موضوع الزيارة"], [["", "", ""] for _ in range(3)], [6, 4, 7], taille=9)
    L("4 - تسليم أوراق التحرير إلى كتابة مركز الامتحان:", True)
    L("* هل تمت عملية تسليم أوراق التحرير وفق المساطر الآتية:")
    for t in ("وضع أوراق التحرير الخاصة بكل قاعة في ظرف خاص:", "إرفاق أوراق التحرير بلائحة الحضور:",
              "إرفاق أوراق التحرير بتقارير الغش إن وجدت:", "* هل تم توقيع الأظرفة من طرف المعنيين؟",
              "* هل تم إحكام إغلاق الأظرفة؟"):
        L(_oui_non(t))
    L("5 - لائحة بأسماء المترشحين الذين ضبطوا في حالة غش:", True)
    _table(d, ["ر.ت", "رقم الامتحان", "اسم المترشح(ة)", "المادة المعنية بالغش", "وسيلة الغش"],
           [["", "", "", "", ""] for _ in range(3)], [1, 2.4, 6, 4, 4], taille=9)
    L("6 - تقرير مفصل حول سير عملية الإجراء بمركز الامتحان:", True)
    for _ in range(8):
        L("." * 150)
    L("اسم وتوقيع رئيس(ة) المركز:" if not observateur else "اسم وتوقيع الملاحظ(ة):", True)
    para(d, "", apres=20)
    L("ملحوظة: المرجو من السيد(ة) " + ("الملاحظ(ة)" if observateur else "رئيس(ة) المركز")
      + " تعبئة هذا المطبوع بكل دقة وعناية ووضعه في ظرف سري يوجه إلى الأكاديمية.")
    return _sauver(d, dossier, ctx, "تقرير الملاحظ" if observateur else "تقرير رئيس المركز")


def _fraude(conn, dossier, ctx) -> Path:
    d = _nouveau()
    _entete(conn, dossier, d, ctx, "محضر تقرير حول حالة غش")
    L = lambda t, g=False: para(d, t, gras=g, taille=10, apres=2)  # noqa: E731
    L("المرجو من المسؤولين عن الإجراء تعبئة هذا المطبوع بكل عناية، لكل حالة غش، وتسليمه إلى رئيس(ة) مركز "
      "الامتحان عند نهاية حصة الإجراء.")
    L(f"1- تاريخ إجراء الامتحان: ....................    4- المدة الزمنية المخصصة لإنجاز الامتحان: ..........")
    L(f"2- المستوى: {NIVEAU}    5- توقيت بداية إنجاز الامتحان: ..........")
    L("3- المادة: ....................................    6- توقيت ضبط حالة الغش: ..........")
    L(f"7- الاسم الكامل للمترشح الغاش: {POINTS}")
    L("8- رقم امتحان المترشح الغاش: ....................")
    L(f"9- اسم المترشح المساهم في عملية الغش (إن وجد) ورقم امتحانه: {POINTS}")
    L("10- الوسيلة المستعملة في الغش:", True)
    for t in ("وثيقة مطبوعة أو مكتوبة باليد", "ورقة تحرير أو تسويد أحد المترشحين", "الهاتف النقال",
              "وسيلة أخرى، حددها: ...................."):
        L(f"{CASE} {t}")
    L("11- ما هو الإجراء المتخذ في حق هذا التلميذ؟", True)
    for t in ("الاقتصار على سحب وسيلة الغش", "سحب وسيلة الغش مع تنبيه شفوي", "إخراج الغاش من قاعة الامتحان",
              "آخر، أذكره: ...................."):
        L(f"{CASE} {t}")
    L("12- ما هو رد فعل هذا التلميذ؟", True)
    for t in ("انضبط للإجراء والتزم الصمت", "احتج شفوياً دون استعمال ألفاظ نابية أو غير أخلاقية",
              "احتج شفوياً باستعمال ألفاظ نابية أو غير أخلاقية", "هدد باستعمال العنف المادي",
              "آخر، أذكره: ...................."):
        L(f"{CASE} {t}")
    L("إضافات لتوضيح ملابسات عملية الغش:", True)
    for _ in range(3):
        L("." * 150)
    _table(d, ["الاسم الكامل للأستاذ(ة) المراقب(ة)", "رقم التأجير", "الإطار والمهمة", "التوقيع"],
           [["", "", "", ""], ["", "", "", ""]], [6, 3, 4, 4], taille=9)
    para(d, "", apres=6)
    L("خاتم وتوقيع السيد(ة) رئيس(ة) مركز الامتحان", True)
    return _sauver(d, dossier, ctx, "محضر تقرير حول حالة غش")


_GENERATEURS = {
    "listes": _listes, "presence": _presence, "tables": _tables, "convocations": _convocations,
    "repartition": _repartition, "convocations_profs": _convocations_profs, "badges": _badges,
    "secretariat": _secretariat, "annonce": _annonce, "notation": _notation,
    "ouverture": lambda c, d_, x: _pv_plis(c, d_, x, False), "fermeture": lambda c, d_, x: _pv_plis(c, d_, x, True),
    "centre": lambda c, d_, x: _carte(c, d_, x, False), "correction": lambda c, d_, x: _carte(c, d_, x, True),
    "rapport_president": lambda c, d_, x: _rapport(c, d_, x, False),
    "rapport_observateur": lambda c, d_, x: _rapport(c, d_, x, True), "fraude": _fraude,
}


def generer(conn, dossier: DossierDonnees, eid: int, code: str) -> Path:
    if code not in _GENERATEURS:
        raise exs.ErreurExamen(f"وثيقة غير معروفة: {code}")
    ctx = _ctx(conn, eid)
    p = _GENERATEURS[code](conn, dossier, ctx)
    with conn:
        conn.execute("INSERT INTO journal(action, cible, cible_id, details) VALUES ('generation','examen',?,?)",
                     (eid, DOCUMENTS[code][0]))
    return p
