"""مؤسسات الريادة: مؤشر ISA2 حسب مراحل التعليم الصريح، مراسلة الأساتذة بنتائج المرحلة، ملف شارة الريادة،
والتقرير التركيبي لأداء المؤسسة والتعلمات الأساس.

- ISA2: يُدخله المدير لكل قسم ومادة ومرحلة (الرائز البعدي ثم المراحل)، كما يقرؤه في مسار. لا يُحتسب هنا:
  صيغة احتسابه من اختصاص مسار.
- مراسلة «بخصوص نتائج المرحلة»: على نموذج المدير (13 ماي 2026): جدول لكل قسم ومادة بنسبة التحكم في التعلمات
  الأساس من الرائز البعدي إلى المرحلة المختارة، وسطر «التطور».
- ملف شارة الريادة: الوثائق العشرون و«حقيبة المعلومات» كما في وثيقة «معايير الريادة».
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path

from idara.data.dossier import DossierDonnees
from idara.services import annee as annee_srv
from idara.services import documents as dc
from idara.services import evaluation as ev
from idara.services import tarl
from idara.services import textes as tx
from idara.services import vie_scolaire as vs
from idara.services.docs_association import _cellule, _nouveau, _ombre, ajouter, para, saut_page, tableau
from idara.services.massar import niveaux_du_code_classe

MATIERES = {"ar": "العربية", "fr": "الفرنسية", "ma": "الرياضيات"}
ORDINAUX_F = ["", "الأولى", "الثانية", "الثالثة", "الرابعة", "الخامسة", "السادسة", "السابعة", "الثامنة"]
GROUPES = ["", "الأول", "الثاني", "الثالث", "الرابع", "الخامس", "السادس"]
MATIERE_ENSEIGNANT = {"عربية": ("ar",), "فرنسية": ("fr",), "مزدوجة": ("ar", "fr", "ma")}

PIECES = (
    "النظام الأساسي للمؤسسة مصادق عليه من طرف مجلس التدبير.",
    "مشروع المؤسسة المندمج المصادق عليه.",
    "محضر مصادقة المديرية الإقليمية على مشروع المؤسسة.",
    "وثيقة الإشعار بالتحويل المالي.",
    "آخر تقرير مالي سنوي للمؤسسة.",
    "محاضر اجتماعات تفعيل مشروع المؤسسة.",
    "استعمال الزمن المعتمد من طرف المؤسسة.",
    "سجل غياب وتأخر الأساتذة الخاص بالأسبوع الأول من شهر أكتوبر.",
    "لوائح غياب التلاميذ لشهر أكتوبر لكل الأفواج من المستوى الأول إلى المستوى السادس.",
    "قائمة محينة بأسماء التلاميذ الذين يعانون من صعوبات في التعلم (المرحلة ما بعد الدعم المكثف شتنبر أكتوبر).",
    "وصل تأسيس أو تجديد جمعية آباء وأمهات وأولياء التلاميذ.",
    "المحاضر، التقارير تؤكد حضور ومشاركة ممثل جمعية آباء وأمهات وأولياء التلاميذ في آخر مجلس تدبير انعقد بالمؤسسة.",
    "مسك نتائج الرائز القبلي في مسار.",
    "مسك نتائج الرائز البعدي في مسار.",
    "لوائح التلاميذ المستفيدين من الدعم خارج أوقات الدراسة.",
    "لائحة الأساتذة المنخرطين في الدعم المؤسساتي.",
    "برنامج حصص الدعم المؤسساتي خارج أوقات الدراسة.",
    "سجل تتبع حصص الدعم خارج أوقات الدراسة مكتمل مئة بالمئة (متوفر لدى المدير).",
    "بطائق التتبع الفردي للتلاميذ المستفيدين من الدعم المؤسساتي خارج أوقات الدراسة.",
    "لائحة حضور الأساتذة المستفيدين من التكوينات في التدريس الصريح وطارل.",
)
INFOS_MANUELLES = (("riyada_date_construction", "تاريخ بناء المؤسسة"),
                   ("riyada_date_fonctionnement", "تاريخ تشغيل المؤسسة"),
                   ("riyada_formes_tarl", "عدد الأساتذة المستفيدين من التكوين في مقاربة التدريس وفق المستوى المناسب "
                                          "(بما في ذلك الدورة الاستدراكية)"),
                   ("riyada_formes_explicite", "عدد الأساتذة المستفيدين من التكوين في مقاربة التدريس الصريح "
                                               "(بما في ذلك الدورة الاستدراكية)"))


class ErreurRiyada(ValueError):
    """رسالة موجهة للمدير بالعربية."""


def libelle_phase(p: int) -> str:
    return "الرائز البعدي" if p == 0 else f"المرحلة {p}"


def _aid(conn, annee: str) -> int:
    return ev._annee_id(conn, annee)


# ---------- ISA2 حسب المراحل ----------

def _taux(v) -> float | None:
    s = str(v or "").replace("%", "").replace(",", ".").strip()
    if not s:
        return None
    try:
        x = round(float(s), 2)
    except ValueError:
        raise ErreurRiyada(f"قيمة غير صحيحة «{v}»: نسبة مئوية مثل 64.93") from None
    if not 0 <= x <= 100:
        raise ErreurRiyada(f"النسبة «{v}» خارج المجال 0 – 100.")
    return x


def enregistrer_isa(conn, annee: str, classe: str, phase: int, valeurs: dict[str, object]) -> None:
    if not 0 <= int(phase) <= 8:
        raise ErreurRiyada("مرحلة غير صحيحة.")
    aid = _aid(conn, annee)
    parsed = {m: _taux(valeurs.get(m)) for m in MATIERES}
    with conn:
        for m, x in parsed.items():
            if x is None:
                conn.execute("DELETE FROM isa_phase WHERE annee_id=? AND classe=? AND phase=? AND matiere=?",
                             (aid, classe, phase, m))
            else:
                conn.execute("INSERT INTO isa_phase(annee_id, classe, phase, matiere, valeur) VALUES (?,?,?,?,?) "
                             "ON CONFLICT(annee_id, classe, phase, matiere) DO UPDATE SET valeur=excluded.valeur",
                             (aid, classe, phase, m, x))


def isa(conn, annee: str) -> dict[str, dict[str, dict[int, float]]]:
    """القسم ← المادة ← المرحلة ← النسبة."""
    res: dict = {}
    for r in conn.execute("SELECT i.* FROM isa_phase i JOIN annee_scolaire a ON a.id=i.annee_id WHERE a.libelle=?",
                          (annee,)):
        res.setdefault(r["classe"], {}).setdefault(r["matiere"], {})[r["phase"]] = r["valeur"]
    return res


def classes(conn, annee: str) -> list[str]:
    """أقسام السنة: من الأقسام المسجلة، أو من النتائج ومستويات التعلم إن لم تكن السنة جارية."""
    l = {r[0] for r in conn.execute("SELECT c.code FROM classe c JOIN annee_scolaire a ON a.id=c.annee_id "
                                    "WHERE a.libelle=?", (annee,))}
    l |= {r[0] for r in conn.execute("SELECT DISTINCT n.classe FROM niveau_apprentissage n JOIN annee_scolaire a "
                                     "ON a.id=n.annee_id WHERE a.libelle=?", (annee,))}
    l |= set(isa(conn, annee))
    return sorted(c for c in l if not c.upper().startswith(("PS", "MS", "GS")))


def evolution(valeurs: dict[int, float], jusqu_a: int | None = None) -> list[tuple[int, float, float | None]]:
    """[(المرحلة، النسبة، التطور مقارنة بالمرحلة السابقة المتوفرة)]."""
    res, avant = [], None
    for p in sorted(valeurs):
        if jusqu_a is not None and p > jusqu_a:
            break
        v = valeurs[p]
        res.append((p, v, None if avant is None else round(v - avant, 2)))
        avant = v
    return res


def _niveau_groupe(classe: str) -> tuple[str, str]:
    ns = niveaux_du_code_classe(classe)
    niveau = "، ".join(ev.ORDINAUX[n] for n in ns) if ns else classe
    try:
        g = int(classe.rsplit("-", 1)[1])
        groupe = GROUPES[g] if g < len(GROUPES) else str(g)
    except (IndexError, ValueError):
        groupe = classe
    return niveau, groupe


def enseignants(conn, annee: str, maths: str = "fr") -> list[dict]:
    """الأساتذة وأقسامهم ومواد مراسلتهم. maths: من تُدرج له الرياضيات (fr، ar، tous)."""
    a = annee_srv.annee_courante(conn)
    if a is None or a["libelle"] != annee:
        raise ErreurRiyada("المراسلة تخص السنة الدراسية الجارية (إسناد الأقسام في الموارد البشرية).")
    par: dict[int, dict] = {}
    for r in conn.execute(
            "SELECT p.id, p.prenom_ar, p.nom_ar, p.sexe, p.matiere, c.code FROM affectation_classe f "
            "JOIN classe c ON c.id=f.classe_id JOIN personnel p ON p.id=f.personnel_id "
            "WHERE c.annee_id=? AND p.statut='actif' ORDER BY p.nom_ar, c.code", (a["id"],)):
        mats = list(MATIERE_ENSEIGNANT.get(r["matiere"] or "", ()))
        if maths != "aucun" and "ma" not in mats and (maths == "tous" or (maths == "fr" and "fr" in mats) or (maths == "ar" and "ar" in mats)):
            mats.append("ma")
        e = par.setdefault(r["id"], {"nom": f"{r['prenom_ar']} {r['nom_ar']}", "sexe": r["sexe"], "classes": [],
                                     "matieres": mats})
        e["classes"].append(r["code"])
    return list(par.values())


def generer_lettres(conn, dossier: DossierDonnees, annee: str, phase: int, maths: str = "fr",
                    felicitations: bool = True, date_lettre: str | None = None) -> Path:
    """مراسلة كل أستاذ(ة) بنتائج أقسامه حسب مؤشر ISA2 (نموذج المدير)، صفحة لكل أستاذ(ة)."""
    if not 1 <= phase <= 8:
        raise ErreurRiyada("اختر مرحلة (1 فما فوق).")
    try:
        c = dc.champs_communs(conn)
    except dc.ErreurDocument as e:
        raise ErreurRiyada(str(e)) from None
    donnees = isa(conn, annee)
    d_iso = date_lettre or date.today().isoformat()
    lettres = []
    for e in enseignants(conn, annee, maths):
        blocs = [(cl, m, evolution(donnees[cl][m], phase)) for cl in e["classes"] for m in e["matieres"]
                 if phase in donnees.get(cl, {}).get(m, {})]
        if blocs:
            lettres.append((e, blocs))
    if not lettres:
        raise ErreurRiyada(f"لا نسب ISA2 مسجلة للمرحلة {phase} في أقسام الأساتذة المسندة إليهم.")
    d = _nouveau()
    ordinal = ORDINAUX_F[phase]
    for k, (e, blocs) in enumerate(lettres):
        if k:
            saut_page(d)
        para(d, apres=10)
        para(d, f"{c['ville']} في: {tx.date_longue_ar(d_iso)}", apres=2)
        para(d, f"من {c['mudir']} {c['etablissement']}", apres=2)
        p = para(d, apres=2)
        ajouter(p, f"إلى {tx.accord(e['sexe'], 'الأستاذ', 'الأستاذة')}: ", gras=True)
        ajouter(p, e["nom"])
        p = para(d, apres=8)
        ajouter(p, "الموضوع: ", gras=True)
        ajouter(p, f"بخصوص نتائج المرحلة {ordinal}.")
        corps = (f"وبعد، أتشرف بتهنئتكم بالنتائج الجيدة المحصل عليها في المرحلة {ordinal} وأوافيكم بالإحصائيات "
                 "التفصيلية الخاصة بالمرحلة وبالتطور الحاصل انطلاقا من مرحلة الرائز البعدي حسب مؤشر ISA2."
                 if felicitations else
                 f"وبعد، أوافيكم بالإحصائيات التفصيلية الخاصة بنتائج المرحلة {ordinal} وبالتطور الحاصل انطلاقا من "
                 "مرحلة الرائز البعدي حسب مؤشر ISA2.")
        para(d, corps, apres=8)
        for cl, m, ev_ in blocs:
            niveau, groupe = _niveau_groupe(cl)
            n = len(ev_)
            t = tableau(d, 4, 3 + n, largeurs=[2.2, 2.0, 2.4] + [10.8 / n] * n)
            for j, lib in enumerate(("المستوى", "الفوج", "المادة")):
                t.cell(0, j).merge(t.cell(1, j))
                _cellule(t.cell(0, j), lib, gras=True, taille=12)
                t.cell(2, j).merge(t.cell(3, j))
            _cellule(t.cell(2, 0), niveau, taille=12)
            _cellule(t.cell(2, 1), groupe, taille=12)
            _cellule(t.cell(2, 2), MATIERES[m], taille=12)
            t.cell(0, 3).merge(t.cell(0, 2 + n))
            _cellule(t.cell(0, 3), "نسبة التحكم في التعلمات الأساس", gras=True, taille=12)
            _ombre(t.cell(0, 3))
            for j, (p_, v, dlt) in enumerate(ev_, start=3):
                _cellule(t.cell(1, j), libelle_phase(p_), gras=True, taille=11)
                _cellule(t.cell(2, j), f"{v:.2f}%", taille=12)
                _cellule(t.cell(3, j), "التطور" if dlt is None else ("‎+" if dlt > 0 else "‎") + f"{dlt:.2f}",
                         taille=11, gras=dlt is None)
            para(d, apres=6)
        para(d, apres=10)
        para(d, c["mudir_moassasa"], gras=True, centre=True)
    rep = dossier.archives / annee.replace("/", "-") / "الريادة"
    rep.mkdir(parents=True, exist_ok=True)
    chemin = rep / f"{datetime.now():%Y%m%d_%H%M%S}_نتائج المرحلة {phase}.docx"
    d.save(chemin)
    return chemin


# ---------- ملف شارة الريادة ----------

def _param(conn, cle: str) -> str:
    r = conn.execute("SELECT valeur FROM parametre WHERE cle=?", (cle,)).fetchone()
    return r[0] if r else ""


def enregistrer_infos(conn, valeurs: dict[str, str]) -> None:
    with conn:
        for cle, _ in INFOS_MANUELLES:
            v = " ".join(str(valeurs.get(cle) or "").split())
            if v:
                conn.execute("INSERT INTO parametre(cle, valeur) VALUES (?,?) ON CONFLICT(cle) DO UPDATE SET "
                             "valeur=excluded.valeur", (cle, v))
            else:
                conn.execute("DELETE FROM parametre WHERE cle=?", (cle,))


def infos(conn) -> list[tuple[str, str, bool]]:
    """حقيبة المعلومات: (البند، القيمة، آلي؟). الآلي من معطيات التطبيق."""
    a = annee_srv.annee_courante(conn)
    perso = conn.execute("SELECT categorie, sexe, COUNT(*) FROM personnel WHERE statut='actif' GROUP BY categorie, sexe"
                         ).fetchall()
    n = lambda cats, s: sum(r[2] for r in perso if r[0] in cats and r[1] == s)  # noqa: E731
    el = conn.execute("SELECT e.sexe, COUNT(*) FROM inscription i JOIN eleve e ON e.id=i.eleve_id WHERE i.annee_id=? "
                      "AND i.statut IN ('inscrit','arrive') GROUP BY e.sexe", (a["id"] if a else -1,)).fetchall()
    ne = {r[0]: r[1] for r in el}
    nb_classes = conn.execute("SELECT COUNT(*) FROM classe WHERE annee_id=?", (a["id"] if a else -1,)).fetchone()[0]
    from idara.services import etablissement as etab_srv
    dr = etab_srv.directeur_actuel(conn)
    date_dir = (dr["mandat_debut"] or "") if dr else ""
    res = [(INFOS_MANUELLES[0][1], _param(conn, INFOS_MANUELLES[0][0]), False),
           (INFOS_MANUELLES[1][1], _param(conn, INFOS_MANUELLES[1][0]), False),
           ("تاريخ تعيين المدير الحالي بالمؤسسة", tx.date_chiffres(date_dir) if date_dir else "", True),
           ("عدد الأساتذة نساء", str(n(("enseignant",), "F")), True),
           ("عدد الأساتذة رجال", str(n(("enseignant",), "M")), True),
           ("عدد أطر الإدارة نساء", str(n(("directeur",), "F")), True),
           ("عدد أطر الإدارة رجال", str(n(("directeur",), "M")), True),
           ("عدد تلاميذ المؤسسة إناث", str(ne.get("F", 0)), True),
           ("عدد تلاميذ المؤسسة ذكور", str(ne.get("M", 0)), True),
           ("عدد الأقسام الدراسية", str(nb_classes), True),
           (INFOS_MANUELLES[2][1], _param(conn, INFOS_MANUELLES[2][0]), False),
           (INFOS_MANUELLES[3][1], _param(conn, INFOS_MANUELLES[3][0]), False)]
    return res


def pieces(conn, annee: str) -> list[dict]:
    aid = _aid(conn, annee)
    etat = {r["numero"]: r for r in conn.execute("SELECT * FROM riyada_piece WHERE annee_id=?", (aid,))}
    indices = {}
    for ep, n in (("pre", 13), ("post", 14)):
        k = conn.execute("SELECT COUNT(DISTINCT code_massar) FROM niveau_apprentissage WHERE annee_id=? AND epreuve=?",
                         (aid, ep)).fetchone()[0]
        if k:
            indices[n] = f"مستويات {k} تلميذاً مستوردة من مسار"
    nd = sum(len(tarl.eleves_en_difficulte(conn, annee, "*", m)) for m in tarl.MATIERES) if annee in tarl.annees(conn) else 0
    if nd:
        indices[10] = "اللائحة تُولَّد من التطبيق (التلاميذ دون المستوى المتوقع في الرائز البعدي)"
    return [{"numero": i, "libelle": t, "disponible": bool(etat[i]["disponible"]) if i in etat else False,
             "observation": (etat[i]["observation"] or "") if i in etat else "", "indice": indices.get(i, "")}
            for i, t in enumerate(PIECES, start=1)]


def enregistrer_piece(conn, annee: str, numero: int, disponible: bool, observation: str = "") -> None:
    if not 1 <= numero <= len(PIECES):
        raise ErreurRiyada("رقم الوثيقة غير صحيح.")
    with conn:
        conn.execute("INSERT INTO riyada_piece(annee_id, numero, disponible, observation) VALUES (?,?,?,?) "
                     "ON CONFLICT(annee_id, numero) DO UPDATE SET disponible=excluded.disponible, "
                     "observation=excluded.observation", (_aid(conn, annee), numero, int(bool(disponible)),
                                                         " ".join(observation.split()) or None))


def _sauver(d, dossier: DossierDonnees, annee: str, nom: str) -> Path:
    rep = dossier.archives / annee.replace("/", "-") / "الريادة"
    rep.mkdir(parents=True, exist_ok=True)
    chemin = rep / f"{datetime.now():%Y%m%d_%H%M%S}_{nom}.docx"
    d.save(chemin)
    return chemin


def generer_dossier(conn, dossier: DossierDonnees, annee: str) -> Path:
    try:
        c = dc.champs_communs(conn)
    except dc.ErreurDocument as e:
        raise ErreurRiyada(str(e)) from None
    d = _nouveau()
    para(d, f"المؤسسة: {c['etablissement']}", gras=True, taille=13, apres=0)
    para(d, "ملف شارة الريادة", gras=True, taille=22, centre=True, apres=0)
    para(d, f"السنة الدراسية {annee}", centre=True, apres=8)
    para(d, "حقيبة المعلومات", gras=True, taille=17, apres=2)
    inf = infos(conn)
    t = tableau(d, len(inf), 2, largeurs=[11.4, 6.0])
    for i, (lib, v, _) in enumerate(inf, start=0):
        _cellule(t.cell(i, 0), f"{i + 1}- {lib}", taille=13, centre=False)
        _cellule(t.cell(i, 1), v or "", taille=13)
    para(d, apres=8)
    ps = pieces(conn, annee)
    para(d, f"الوثائق ({len(PIECES)} وثيقة) — المتوفر منها: {sum(p['disponible'] for p in ps)}", gras=True, taille=17,
         apres=2)
    t = tableau(d, 1 + len(ps), 4, largeurs=[1.2, 10.4, 2.2, 3.6])
    for j, lib in enumerate(("ر.ت", "الوثيقة", "الحالة", "ملاحظات")):
        _cellule(t.cell(0, j), lib, gras=True, taille=13)
        _ombre(t.cell(0, j))
    for i, p in enumerate(ps, start=1):
        for j, v in enumerate((str(p["numero"]), p["libelle"], "متوفرة" if p["disponible"] else "غير متوفرة",
                               p["observation"])):
            _cellule(t.cell(i, j), v, taille=12, centre=j in (0, 2))
    para(d, apres=10)
    para(d, c["mudir_moassasa"], gras=True, centre=True)
    return _sauver(d, dossier, annee, "ملف شارة الريادة")


def generer_liste_difficultes(conn, dossier: DossierDonnees, annee: str) -> Path:
    """الوثيقة 10: التلاميذ الذين يعانون من صعوبات (دون المستوى المتوقع في الرائز البعدي)، حسب القسم والمادة."""
    try:
        c = dc.champs_communs(conn)
    except dc.ErreurDocument as e:
        raise ErreurRiyada(str(e)) from None
    lignes = {}
    for m, lib in tarl.MATIERES.items():
        for r in tarl.eleves_en_difficulte(conn, annee, "*", m):
            e = lignes.setdefault(r["code_massar"], {"classe": r["classe"], "nom": r["nom"], "code": r["code_massar"]})
            e[m] = f"{r['valeur']} (المتوقع: {tarl.attendu(conn, annee, r['niveau'], m)})"
    if not lignes:
        raise ErreurRiyada("لا تلاميذ دون المستوى المتوقع في الرائز البعدي (أو لم تُستورد مستويات التعلم).")
    rows = sorted(lignes.values(), key=lambda x: (x["classe"], x["nom"]))
    d = _nouveau()
    para(d, f"المؤسسة: {c['etablissement']}", gras=True, taille=13, apres=0)
    para(d, "قائمة محينة بأسماء التلاميذ الذين يعانون من صعوبات في التعلم", gras=True, taille=18, centre=True, apres=0)
    para(d, f"حسب نتائج رائز الموضعة البعدي — السنة الدراسية {annee}", centre=True, apres=8)
    t = tableau(d, 1 + len(rows), 6, largeurs=[1.6, 4.4, 2.2, 3.0, 3.0, 3.2])
    for j, lib in enumerate(("القسم", "الاسم الكامل", "رمز مسار", "العربية", "الفرنسية", "الرياضيات")):
        _cellule(t.cell(0, j), lib, gras=True, taille=12)
        _ombre(t.cell(0, j))
    for i, r in enumerate(rows, start=1):
        for j, v in enumerate((r["classe"].replace("-", ""), r["nom"], r["code"], r.get("ar", "—"), r.get("fr", "—"),
                               r.get("ma", "—"))):
            _cellule(t.cell(i, j), v, taille=11, centre=j != 1)
    para(d, apres=10)
    para(d, c["mudir_moassasa"], gras=True, centre=True)
    return _sauver(d, dossier, annee, "التلاميذ ذوو الصعوبات")


# ---------- التقرير التركيبي ----------

def generer_synthese(conn, dossier: DossierDonnees, annee: str, observations: str = "") -> Path:
    """تقرير تركيبي لمجالس المؤسسة واللقاءات التواصلية: النتائج بالأسدوس، التعلمات الأساس، ISA2، الأنشطة."""
    try:
        c = dc.champs_communs(conn)
    except dc.ErreurDocument as e:
        raise ErreurRiyada(str(e)) from None
    d = _nouveau()
    para(d, f"{c['ville']} في: {tx.date_longue_ar(date.today().isoformat())}", apres=0)
    para(d, f"المؤسسة: {c['etablissement']}", gras=True, apres=6)
    para(d, "تقرير تركيبي حول أداء المؤسسة والتحكم في التعلمات الأساس", gras=True, taille=20, centre=True, apres=0)
    para(d, f"السنة الدراسية {annee}", centre=True, apres=10)
    vide = True

    # 1. النتائج الدراسية
    ps = [p for p in ev.periodes(conn) if p[0] == annee]
    if ps:
        vide = False
        cmp = ev.comparaison(conn, ps[-1])
        para(d, f"1. النتائج الدراسية: {cmp[0]['periode']}" + (f" مقارنة ب{cmp[0]['avant']}" if cmp[0]["avant"] else ""),
             gras=True, taille=16, apres=2)
        t = tableau(d, 1 + len(cmp), 6, largeurs=[3.6, 1.8, 2.6, 3.2, 3.0, 3.2])
        for j, lib in enumerate(("الفئة", "العدد", "المعدل", "نسبة النجاح", "تطور المعدل", "تطور النسبة")):
            _cellule(t.cell(0, j), lib, gras=True, taille=12)
            _ombre(t.cell(0, j))
        sig = lambda x: "—" if x is None else ("‎+" if x > 0 else "‎") + f"{x:.2f}"  # noqa: E731
        for i, l in enumerate(cmp, start=1):
            for j, v in enumerate((l["libelle"], str(l["effectif"]), "—" if l["moyenne"] is None else f"{l['moyenne']:.2f}",
                                   "—" if l["taux"] is None else f"{l['taux']:.2f}%", sig(l["ecart_moyenne"]),
                                   sig(l["ecart_taux"]))):
                _cellule(t.cell(i, j), v, taille=12, gras=l["cle"] == "المؤسسة")
        para(d, apres=6)

    # 2. التعلمات الأساس (TaRL)
    if annee in tarl.annees(conn):
        vide = False
        para(d, "2. التعلمات الأساس: نسبة بلوغ المستوى المتوقع في رائزي الموضعة", gras=True, taille=16, apres=2)
        gs = [g for g in tarl.groupes(conn, annee) if not g[0].startswith("c:")]
        t = tableau(d, 2 + len(gs), 7, largeurs=[3.8, 2.3, 2.3, 2.3, 2.3, 2.2, 2.2])
        t.cell(0, 0).merge(t.cell(1, 0))
        _cellule(t.cell(0, 0), "الفئة", gras=True, taille=12)
        for k, (m, lib) in enumerate(tarl.MATIERES.items()):
            t.cell(0, 1 + 2 * k).merge(t.cell(0, 2 + 2 * k))
            _cellule(t.cell(0, 1 + 2 * k), lib, gras=True, taille=12)
            _cellule(t.cell(1, 1 + 2 * k), "القبلي", gras=True, taille=11)
            _cellule(t.cell(1, 2 + 2 * k), "البعدي", gras=True, taille=11)
        for i, (g, lib) in enumerate(gs, start=2):
            _cellule(t.cell(i, 0), lib, taille=12, gras=g == "*")
            for k, m in enumerate(tarl.MATIERES):
                tb = tarl.tableau_bord(conn, annee, g, m)["taux_attendu"]
                for e, ep in enumerate(("pre", "post")):
                    _cellule(t.cell(i, 1 + 2 * k + e), "—" if tb[ep] is None else f"{tb[ep]:.2f}%", taille=12)
        para(d, apres=6)

    # 3. ISA2 حسب المراحل
    donnees = isa(conn, annee)
    if donnees:
        vide = False
        phases = sorted({p for cl in donnees.values() for m in cl.values() for p in m})
        para(d, "3. مؤشر ISA2 حسب مراحل التعليم الصريح (نسبة التحكم في التعلمات الأساس)", gras=True, taille=16, apres=2)
        lignes = [(cl, m) for cl in sorted(donnees) for m in MATIERES if m in donnees[cl]]
        n = len(phases)
        t = tableau(d, 1 + len(lignes), 2 + n, largeurs=[2.6, 2.6] + [12.2 / n] * n)
        for j, lib in enumerate(["القسم", "المادة"] + [libelle_phase(p) for p in phases]):
            _cellule(t.cell(0, j), lib, gras=True, taille=11)
            _ombre(t.cell(0, j))
        for i, (cl, m) in enumerate(lignes, start=1):
            _cellule(t.cell(i, 0), cl.replace("-", ""), taille=11)
            _cellule(t.cell(i, 1), MATIERES[m], taille=11)
            for j, p in enumerate(phases, start=2):
                v = donnees[cl][m].get(p)
                _cellule(t.cell(i, j), "—" if v is None else f"{v:.2f}%", taille=11)
        para(d, apres=6)

    # 4. الحياة المدرسية
    a = annee_srv.annee_courante(conn)
    if a and a["libelle"] == annee:
        b = vs.bilan(conn)
        if b["programmees"] or b["clubs"]:
            vide = False
            para(d, "4. الأنشطة التربوية والموازية", gras=True, taille=16, apres=2)
            para(d, f"الأنشطة المبرمجة: {b['programmees']}، المنجزة: {b['realisees']}"
                    + (f" (نسبة الإنجاز {b['taux']:.2f}%)" if b["taux"] is not None else "")
                    + f"؛ المشاركون: {b['garcons'] + b['filles']} (ذكور {b['garcons']}، إناث {b['filles']})؛ "
                      f"الأندية التربوية: {b['clubs']} بـ{b['membres']} عضواً.", apres=6)
    if vide:
        raise ErreurRiyada(f"لا معطيات للسنة {annee}: استورد النتائج أو مستويات التعلم أو أدخل مؤشر ISA2.")
    para(d, "ملاحظات وتوصيات:", gras=True, taille=16, apres=2)
    if observations.strip():
        for l in observations.strip().splitlines():
            para(d, l, apres=2)
    else:
        for _ in range(5):
            para(d, "." * 150, taille=11, apres=2)
    para(d, apres=10)
    para(d, c["mudir_moassasa"], gras=True, centre=True)
    return _sauver(d, dossier, annee, "التقرير التركيبي")
