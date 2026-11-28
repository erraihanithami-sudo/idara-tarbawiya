"""ترقية الأساتذة (طلب المدير 2026-11-28): الترقية في الرتبة، والترقية في الدرجة بالاختيار، وبامتحان الكفاءة المهنية.

المرجع: المرسوم رقم 2.24.140 (23 فبراير 2024) في شأن النظام الأساسي الخاص بموظفي الوزارة المكلفة بالتربية الوطنية
(الجريدة الرسمية عدد 7277)، والمذكرة 115x26 (27 نونبر 2026) في شأن امتحانات الكفاءة المهنية برسم سنة 2026.

- المادة 49: أنساق الترقي من رتبة إلى أخرى (سريع، متوسط، بطيء) إلى الرتبة 10. وفي الدرجة الأولى لأساتذة التعليم
  الابتدائي من الرتبة 10 إلى 13 مباشرة كل سنتين. والرتبة الاستثنائية للدرجة الثانية بالاختيار بعد سنتين في الرتبة 10
  (في حدود 10% من المناصب). والدرجة الممتازة: رتبة كل ثلاث سنوات (من 1 إلى 8).
- المادة 50: من الثانية إلى الأولى بالامتحان (14%، 6 سنوات في الدرجة) أو بالاختيار (22%، 10 سنوات)، أو بالاختيار دون
  حصيص لمن لم يُرقَّ بعد تقييده للمرة الرابعة. ومن الأولى إلى الممتازة بالاختيار (36%، الرتبة 7 على الأقل و5 سنوات
  في الدرجة)، أو دون حصيص بعد التقييد الرابع.
- المادة 51: الأقدمية في الامتحان تُحتسب إلى غاية 31 دجنبر من سنة الامتحان.
- المادة 81: أقدمية اعتبارية 5 سنوات للترقي بالاختيار إلى الأولى لأساتذة الابتدائي المرتبين في الثانية والمزاولين
  في فاتح يناير 2023 الذين وُظّفوا أول مرة في الدرجة الثالثة؛ وسنة واحدة للترقي في الدرجة لمن رُقّي إلى الأولى برسم 2022.
- المادة 87: الترقي بالاختيار من الأولى إلى الممتازة لأساتذة التعليم الابتدائي ابتداء من فاتح يناير 2024.

الحساب تقديري من معطيات الإطار المسجلة (الدرجة وتاريخها، الرتبة وتاريخها، تاريخ التوظيف). لا يحتسب الفترات التي لا
تُعدّ خدمة فعلية (الاستيداع مثلاً)؛ واللوائح الرسمية تحصرها الإدارة.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from idara.services import fiches
from idara.services import personnel as pers
from idara.services import textes as tx


class ErreurTarqiya(ValueError):
    """رسالة موجهة للمدير بالعربية."""


TYPES = {"rang": "الترقية في الرتبة", "choix": "الترقية في الدرجة بالاختيار",
         "examen": "الترقية في الدرجة بامتحان الكفاءة المهنية"}
G2, G1, GX = "الدرجة الثانية", "الدرجة الأولى", "الدرجة الممتازة"
EXC = "الاستثنائية"
RYTHMES = {"rapide": "سريع", "moyen": "متوسط", "lent": "بطيء"}
# المادة 49: المدة بالأشهر من الرتبة k إلى k+1 (سريع، متوسط، بطيء)
DUREES = {1: (12, 12, 12), 2: (12, 18, 24), 3: (24, 30, 36), 4: (24, 30, 42), 5: (24, 30, 42),
          6: (24, 36, 48), 7: (24, 36, 48), 8: (24, 36, 48), 9: (24, 36, 48)}
MAX_RANG = {G2: 10, G1: 13, GX: 8}
INDICES = {G2: (275, 300, 326, 351, 377, 402, 428, 456, 484, 512), G1: (336, 369, 403, 436, 472, 509, 542, 574, 606, 639,
                                                                      675, 690, 704),
           GX: (704, 746, 779, 812, 840, 870, 900, 930)}
INDICE_EXC_G2 = 564
REFERENCE = "المرسوم رقم 2.24.140 بتاريخ 23 فبراير 2024 (النظام الأساسي الخاص بموظفي الوزارة المكلفة بالتربية الوطنية)"

# امتحانات الكفاءة المهنية: معطيات كل دورة من مذكرتها
EXAMENS = {
    2026: {"memo": "المذكرة 115x26 بتاريخ 27 نونبر 2026", "date": "2026-12-19",
           "candidature": ("2026-11-30", "2026-12-14"), "depot": "2026-12-15", "note_pro": "2027-01-15",
           "portail": "https://mihani.men.gov.ma",
           "epreuves": ("اختبار حول دراسة وضعية أو وضعيات مهنية: ثلاث ساعات، المعامل 1",
                        "اختبار في علوم التربية وديداكتيك المواد المدرسة بالتعليم الابتدائي: ثلاث ساعات، المعامل 1")},
}
REGLES = {
    "rang": ["أنساق الترقي (المادة 49): من الرتبة 1 إلى 2 سنة؛ من 2 إلى 3 سنة أو سنة ونصف أو سنتان؛ من 3 إلى 4 سنتان أو "
             "سنتان ونصف أو ثلاث؛ من 4 إلى 6 سنتان أو سنتان ونصف أو ثلاث ونصف؛ من 6 إلى 10 سنتان أو ثلاث أو أربع "
             "(سريع، متوسط، بطيء).",
             "الدرجة الأولى (أساتذة التعليم الابتدائي): من الرتبة 10 إلى 13 مباشرة كل سنتين.",
             "الدرجة الثانية: الرتبة الاستثنائية بالاختيار بعد سنتين على الأقل في الرتبة 10، في حدود 10% من المناصب.",
             "الدرجة الممتازة: رتبة كل ثلاث سنوات (من 1 إلى 8)."],
    "choix": ["من الثانية إلى الأولى: 10 سنوات على الأقل في الدرجة، في حدود 22% من عدد المترشحين؛ ودون حصيص لمن "
              "لم يُرقَّ بعد تقييده للمرة الرابعة (المادة 50).",
              "أقدمية اعتبارية 5 سنوات لأساتذة الدرجة الثانية في فاتح يناير 2023 الذين وُظّفوا أول مرة في الدرجة الثالثة "
              "(المادة 81).",
              "من الأولى إلى الممتازة: الرتبة 7 على الأقل و5 سنوات في الدرجة، في حدود 36%؛ ودون حصيص بعد التقييد "
              "الرابع (المادة 50؛ وتسري على أساتذة الابتدائي من فاتح يناير 2024، المادة 87). ولمن رُقّي إلى الأولى "
              "برسم 2022 سنة اعتبارية (المادة 81).",
              "الترتيب: الأقدمية في الدرجة، ثم الأقدمية العامة، ثم النقطة المهنية برسم سنة الترقي."],
    "examen": ["امتحان الكفاءة المهنية لولوج الدرجة الأولى: أساتذة التعليم الابتدائي المرسمون في الدرجة الثانية الذين "
               "قضوا 6 سنوات على الأقل من الخدمة الفعلية بهذه الصفة إلى غاية 31 دجنبر من سنة الامتحان (المادة 51).",
               "النجاح في حدود 14% سنوياً من عدد المترشحين المتوفرين على الشروط (المادة 50).",
               "النقطة الإقصائية أقل من 5/20 في كل اختبار، وتضاف نقطة مهنية من 20 بمعامل يعادل 30% من مجموع النقط "
               "(المرسوم 2.04.403)."],
}


def _d(v: str | None) -> date | None:
    try:
        return date.fromisoformat(v) if v else None
    except ValueError:
        return None


def _ajouter_mois(d: date, mois: int) -> date:
    m = d.month - 1 + mois
    y, m = d.year + m // 12, m % 12 + 1
    import calendar
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def annees(debut: date, fin: date) -> float:
    """الأقدمية بالسنوات (عشرية) من تاريخ إلى آخر."""
    return round((fin - debut).days / 365.25, 2)


def _rang(echelon: str) -> int | None:
    if echelon == EXC:
        return 11
    try:
        return int(echelon)
    except (TypeError, ValueError):
        return None


def _libelle_rang(r: int | None, grade: str) -> str:
    if r is None:
        return ""
    if grade == G2 and r == 11:
        return "الرتبة الاستثنائية"
    return f"الرتبة {r}"


def est_enseignant(p: pers.Personnel) -> bool:
    return (p.cadre or "").startswith("أستاذ") or (p.categorie == "enseignant" and not p.cadre)


def rythmes(conn) -> dict[str, str]:
    return fiches.lire(conn, "tarqiya_rythmes") or {}


def definir_rythme(conn, pid: int, rythme: str) -> None:
    if rythme not in RYTHMES:
        raise ErreurTarqiya("نسق غير معروف.")
    d = rythmes(conn)
    d[str(pid)] = rythme
    fiches.ecrire(conn, "tarqiya_rythmes", d)


def duree(grade: str, r: int, rythme: str = "rapide") -> int | None:
    """مدة الانتقال من الرتبة r إلى الموالية بالأشهر (None: آخر رتبة، أو استثنائية بالاختيار)."""
    if grade == GX:
        return 36 if r < MAX_RANG[GX] else None
    if r in DUREES:
        return DUREES[r][list(RYTHMES).index(rythme)]
    if grade == G1 and 10 <= r < 13:
        return 24
    return None


def rang_au(grade: str, r: int, depuis: date, le: date, rythme: str = "rapide") -> tuple[int, date]:
    """الرتبة المتوقعة في تاريخ معين (إن لم تُسجَّل ترقيات بعد آخر تحيين)، وتاريخ ولوجها."""
    while True:
        m = duree(grade, r, rythme)
        if m is None:
            return r, depuis
        suivant = _ajouter_mois(depuis, m)
        if suivant > le:
            return r, depuis
        r, depuis = r + 1, suivant


@dataclass
class Concerne:
    pid: int
    nom: str
    ppr: str
    grade: str
    echelon: str
    date_grade: str
    date_echelon: str
    vers: str                     # الرتبة أو الدرجة المرتقبة
    date_droit: str = ""          # تاريخ الاستحقاق (الرتبة) أو 31 دجنبر (الدرجة)
    anciennete: float = 0.0       # الأقدمية في الدرجة (أو في الرتبة) في 31 دجنبر
    anc_generale: float = 0.0
    bonus: float = 0.0            # الأقدمية الاعتبارية
    inscription: int = 0          # رقم التقييد في جدول الترقي (تقديري)
    sans_quota: bool = False
    remarque: str = ""
    rythme: str = ""
    extra: dict = field(default_factory=dict)


def _enseignants(conn) -> list[pers.Personnel]:
    return [p for p in pers.lister(conn) if est_enseignant(p)]


def manquants(conn, type_: str) -> list[tuple[str, str]]:
    """الأساتذة الذين تنقصهم معطيات الحساب: (الاسم، الناقص)."""
    res = []
    for p in _enseignants(conn):
        champs = [("grade", "الدرجة"), ("date_grade", "تاريخ الدرجة")]
        if type_ == "rang" or p.grade == G1:
            champs += [("echelon", "الرتبة"), ("date_echelon", "تاريخ الرتبة")]
        if type_ == "choix":
            champs.append(("date_recrutement", "تاريخ التوظيف"))
        ko = [lib for c, lib in champs if not getattr(p, c)]
        if ko:
            res.append((f"{p.prenom_ar} {p.nom_ar}", "، ".join(ko)))
    return res


def _fin(annee: int) -> date:
    return date(annee, 12, 31)


def concernes_rang(conn, annee: int) -> tuple[list[Concerne], list[Concerne]]:
    """(المعنيون بالترقية في الرتبة برسم السنة، الترقيات المستحقة قبلها ولم تُحيَّن الرتبة بعدها)."""
    ry = rythmes(conn)
    debut, fin = date(annee, 1, 1), _fin(annee)
    res, retard = [], []
    for p in _enseignants(conn):
        r, de = _rang(p.echelon), _d(p.date_echelon)
        if p.grade not in MAX_RANG or r is None or de is None:
            continue
        rythme = ry.get(str(p.id), "rapide")
        nom = f"{p.prenom_ar} {p.nom_ar}"
        base = dict(pid=p.id, nom=nom, ppr=p.ppr, grade=p.grade, echelon=p.echelon, date_grade=p.date_grade,
                    date_echelon=p.date_echelon)
        if p.grade == G2 and r == 10:   # الرتبة الاستثنائية بالاختيار
            droit = _ajouter_mois(de, 24)
            c = Concerne(**base, vers="الرتبة الاستثنائية", date_droit=droit.isoformat(),
                         anciennete=annees(de, fin), rythme="بالاختيار",
                         remarque="بالاختيار بعد التقييد في جدول الترقي، في حدود 10% من المناصب المقيدة في الميزانية.")
            if droit <= fin:   # بالاختيار: يبقى معنياً كل سنة بعد استيفاء السنتين إلى أن يُرقّى
                res.append(c)
            continue
        m = duree(p.grade, r, rythme)
        if m is None:
            continue
        droit = _ajouter_mois(de, m)
        c = Concerne(**base, vers=_libelle_rang(r + 1, p.grade), date_droit=droit.isoformat(),
                     anciennete=annees(de, min(fin, droit)), rythme=RYTHMES[rythme] if r in DUREES else "مباشرة",
                     extra={"indice": _indice(p.grade, r + 1)})
        if debut <= droit <= fin:
            res.append(c)
        elif droit < debut:
            c.remarque = f"مستحقة منذ {tx.date_chiffres(droit)}: حيّن الرتبة في بطاقة الأستاذ(ة) إن تمت الترقية."
            retard.append(c)
    res.sort(key=lambda c: (c.date_droit, c.nom))
    retard.sort(key=lambda c: c.date_droit)
    return res, retard


def _indice(grade: str, r: int) -> int | None:
    t = INDICES.get(grade, ())
    if grade == G2 and r == 11:
        return INDICE_EXC_G2
    return t[r - 1] if 1 <= r <= len(t) else None


def _bonus_81(p: pers.Personnel, annee: int) -> float:
    """5 سنوات: في الثانية في فاتح يناير 2023 ووُظّف أول مرة في الثالثة (تاريخ التوظيف قبل تاريخ الدرجة الثانية)."""
    dg, dr = _d(p.date_grade), _d(p.date_recrutement)
    if annee < 2023 or not dg or not dr or dg > date(2023, 1, 1):
        return 0.0
    return 5.0 if dr < dg else 0.0


def concernes_choix(conn, annee: int) -> list[Concerne]:
    """المستوفون لشروط الترقي في الدرجة بالاختيار برسم السنة (إلى غاية 31 دجنبر)."""
    fin = _fin(annee)
    ry = rythmes(conn)
    res = []
    for p in _enseignants(conn):
        dg = _d(p.date_grade)
        if not dg or p.grade not in (G2, G1) or dg > fin:
            continue
        nom = f"{p.prenom_ar} {p.nom_ar}"
        dr = _d(p.date_recrutement)
        gen = annees(dr, fin) if dr else 0.0
        base = dict(pid=p.id, nom=nom, ppr=p.ppr, grade=p.grade, echelon=p.echelon, date_grade=p.date_grade,
                    date_echelon=p.date_echelon, date_droit=fin.isoformat(), anc_generale=gen)
        if p.grade == G2:
            bonus = _bonus_81(p, annee)
            anc = annees(dg, fin) + bonus
            if anc < 10:
                continue
            premiere = _premiere_annee(dg, 10 - bonus, 2023 if bonus else 0)
            n = annee - premiere + 1
            c = Concerne(**base, vers=G1, anciennete=anc, bonus=bonus, inscription=n, sans_quota=n >= 5,
                         remarque=("أقدمية اعتبارية 5 سنوات (المادة 81). " if bonus else "")
                         + ("دون حصيص (بعد التقييد الرابع)." if n >= 5 else "في حدود 22%."))
            res.append(c)
        else:
            if annee < 2024:
                continue
            r, de = _rang(p.echelon), _d(p.date_echelon)
            if r is None or de is None:
                continue
            r31, _ = rang_au(G1, r, de, fin, ry.get(str(p.id), "rapide"))
            bonus = 1.0 if dg.year == 2022 and annee >= 2023 else 0.0
            anc = annees(dg, fin) + bonus
            if r31 < 7 or anc < 5:
                continue
            rythme = ry.get(str(p.id), "rapide")
            premiere = max(2024, _premiere_annee(dg, 5 - bonus, 0))
            while premiere < annee and rang_au(G1, r, de, _fin(premiere), rythme)[0] < 7:
                premiere += 1
            n = annee - premiere + 1
            c = Concerne(**base, vers=GX, anciennete=anc, bonus=bonus, inscription=n, sans_quota=n >= 5,
                         remarque=(f"الرتبة {r31} في 31 دجنبر. " if str(r31) != p.echelon else "")
                         + ("سنة اعتبارية (المادة 81، ترقية 2022). " if bonus else "")
                         + ("دون حصيص (بعد التقييد الرابع)." if n >= 5 else "في حدود 36%."),
                         extra={"rang_31": r31})
            res.append(c)
    res.sort(key=lambda c: (c.grade != G1, -c.anciennete, -c.anc_generale, c.nom))
    return res


def _premiere_annee(dg: date, seuil: float, plancher: int) -> int:
    """أول سنة تكتمل فيها الأقدمية المطلوبة في 31 دجنبر."""
    y = max(dg.year, plancher)
    while annees(dg, _fin(y)) < seuil - 1e-9:
        y += 1
    return y


def concernes_examen(conn, annee: int) -> list[Concerne]:
    """المستوفون لشرط امتحان الكفاءة المهنية لولوج الدرجة الأولى برسم السنة (6 سنوات في الثانية في 31 دجنبر)."""
    fin = _fin(annee)
    res = []
    choix = {c.pid for c in concernes_choix(conn, annee) if c.grade == G2}
    for p in _enseignants(conn):
        dg = _d(p.date_grade)
        if p.grade != G2 or not dg:
            continue
        anc = annees(dg, fin)
        if anc < 6:
            continue
        dr = _d(p.date_recrutement)
        res.append(Concerne(pid=p.id, nom=f"{p.prenom_ar} {p.nom_ar}", ppr=p.ppr, grade=p.grade, echelon=p.echelon,
                            date_grade=p.date_grade, date_echelon=p.date_echelon, vers=G1,
                            date_droit=fin.isoformat(), anciennete=anc, anc_generale=annees(dr, fin) if dr else 0.0,
                            remarque="مستوفٍ أيضاً لشروط الترقي بالاختيار." if p.id in choix else "",
                            extra={"matiere": p.matiere}))
    res.sort(key=lambda c: (-c.anciennete, c.nom))
    return res


def concernes(conn, type_: str, annee: int):
    if type_ == "rang":
        return concernes_rang(conn, annee)[0]
    if type_ == "choix":
        return concernes_choix(conn, annee)
    if type_ == "examen":
        return concernes_examen(conn, annee)
    raise ErreurTarqiya("نوع ترقية غير معروف.")


def annee_defaut(type_: str, aujourdhui: date | None = None) -> int:
    """الترقيات تتم متأخرة: في 2026 تُعرض المعنيات برسم 2025، إلا الامتحان المهني فبرسم السنة الجارية."""
    y = (aujourdhui or date.today()).year
    return y if type_ == "examen" else y - 1


def annees_proposees(aujourdhui: date | None = None) -> list[int]:
    y = (aujourdhui or date.today()).year
    return list(range(y + 1, y - 6, -1))


# ---------- تسجيل الترقية ----------

def reclassement(c: Concerne) -> tuple[str, str]:
    """الدرجة والرتبة بعد الترقية في الدرجة (المادة 52): الرتبة التي تقل مباشرة عن الرتبة الأصلية (ولا تقل عن 1)؛
    والممتازة في الرتبة 1."""
    if c.vers == GX:
        return GX, "1"
    r = _rang(c.echelon) or 1
    return G1, str(max(1, r - 1))


def enregistrer_promotion(conn, pid: int, type_: str, le: str, echelon: str, grade: str | None = None,
                          annee: int | None = None) -> None:
    """يحيّن بطاقة الأستاذ(ة): الرتبة وتاريخها، والدرجة وتاريخها إن كانت ترقية في الدرجة. وتُحفظ في سجل الترقيات."""
    d = _d(le)
    if d is None:
        raise ErreurTarqiya("تاريخ المفعول إجباري.")
    if echelon not in pers.ECHELONS:
        raise ErreurTarqiya("الرتبة: اختر من القائمة.")
    if grade and grade not in pers.GRADES:
        raise ErreurTarqiya("الدرجة: اختر من القائمة.")
    p = pers.lire(conn, pid)
    avant = {"grade": p.grade, "echelon": p.echelon, "date_grade": p.date_grade, "date_echelon": p.date_echelon}
    p.echelon, p.date_echelon = echelon, d.isoformat()
    if grade and grade != p.grade:
        p.grade, p.date_grade = grade, d.isoformat()
    pers.enregistrer(conn, p)
    h = fiches.lire(conn, "tarqiya_historique") or []
    h.append({"pid": pid, "type": type_, "annee": annee, "le": d.isoformat(), "avant": avant,
              "apres": {"grade": p.grade, "echelon": p.echelon}, "saisi": datetime.now().isoformat(timespec="seconds")})
    fiches.ecrire(conn, "tarqiya_historique", h)


def historique(conn, pid: int | None = None) -> list[dict]:
    h = fiches.lire(conn, "tarqiya_historique") or []
    return [x for x in h if pid is None or x["pid"] == pid]


# ---------- الوثائق ----------

def _ans(v: float) -> str:
    a = int(v + 1e-9)
    m = int(round((v - a) * 12))
    if m == 12:
        a, m = a + 1, 0
    return f"{a} سنة" + (f" و{m} أشهر" if m else "")


def _doc(conn, dossier, paysage: bool = False):
    from docx.shared import Cm
    from idara.services import documents as dc
    from idara.services import etablissement as etab_srv
    from idara.services.docs_association import _nouveau
    try:
        c = dc.champs_communs(conn)
    except dc.ErreurDocument as e:
        raise ErreurTarqiya(str(e)) from None
    d = _nouveau(paysage)
    e = etab_srv.lire_etablissement(conn)
    if e and e.logo_path and (dossier.racine / e.logo_path).exists():
        d.add_picture(str(dossier.racine / e.logo_path), width=Cm(26 if paysage else 17.4))
    return d, c


def generer_liste(conn, dossier, type_: str, annee: int) -> Path:
    """لائحة المعنيين بالترقية برسم السنة (للمراسلة أو الإعلان الداخلي)."""
    from idara.services.docs_association import _cellule, _ombre, para, tableau
    lignes = concernes(conn, type_, annee)
    if not lignes:
        raise ErreurTarqiya(f"لا معنيين ب{TYPES[type_]} برسم سنة {annee} حسب المعطيات المسجلة.")
    d, c = _doc(conn, dossier, paysage=True)
    para(d, f"لائحة الأساتذة المعنيين ب{TYPES[type_]} برسم سنة {annee}", gras=True, centre=True, taille=16, apres=2)
    para(d, f"المؤسسة: {c['etablissement']}", centre=True, taille=12, apres=6)
    if type_ == "rang":
        ent = ("ر.ت", "الاسم الكامل", "رقم التأجير", "الدرجة", "الرتبة الحالية", "تاريخها", "النسق", "الرتبة المرتقبة",
               "تاريخ الاستحقاق")
        vals = [(c_.nom, c_.ppr, c_.grade, _libelle_rang(_rang(c_.echelon), c_.grade), tx.date_chiffres(c_.date_echelon),
                 c_.rythme, c_.vers, tx.date_chiffres(c_.date_droit)) for c_ in lignes]
    elif type_ == "choix":
        ent = ("ر.ت", "الاسم الكامل", "رقم التأجير", "الدرجة الحالية", "تاريخها", "الرتبة", "الأقدمية في الدرجة",
               "الدرجة المرتقبة", "ملاحظات")
        vals = [(c_.nom, c_.ppr, c_.grade, tx.date_chiffres(c_.date_grade), c_.echelon, _ans(c_.anciennete), c_.vers,
                 c_.remarque) for c_ in lignes]
    else:
        ent = ("ر.ت", "الاسم الكامل", "رقم التأجير", "التخصص", "تاريخ الدرجة الثانية", "الرتبة",
               "الأقدمية في 31 دجنبر", "ملاحظات")
        vals = [(c_.nom, c_.ppr, c_.extra.get("matiere", ""), tx.date_chiffres(c_.date_grade), c_.echelon,
                 _ans(c_.anciennete), c_.remarque) for c_ in lignes]
    t = tableau(d, 1 + len(vals), len(ent))
    for j, h in enumerate(ent):
        _cellule(t.cell(0, j), h, gras=True, taille=10)
        _ombre(t.cell(0, j))
    for i, v in enumerate(vals, start=1):
        _cellule(t.cell(i, 0), f"{i:02d}", taille=10)
        for j, x in enumerate(v, start=1):
            _cellule(t.cell(i, j), x or "", taille=10)
    para(d, apres=4)
    for r in REGLES[type_][:2]:
        para(d, f"* {r}", taille=9, apres=0)
    para(d, f"* المرجع: {REFERENCE}. لائحة تقديرية من المعطيات المسجلة بالمؤسسة، تحصر الإدارة اللوائح الرسمية.",
         taille=9, apres=6)
    para(d, f"حرر ب{c['ville']} في: {tx.date_chiffres(date.today())}", taille=12, apres=2)
    para(d, "توقيع وخاتم المدير(ة)", gras=True, taille=12, apres=40)
    rep = dossier.archives / str(annee) / "الترقية"
    rep.mkdir(parents=True, exist_ok=True)
    chemin = rep / f"{datetime.now():%Y%m%d_%H%M%S}_{TYPES[type_].replace(' ', '_')}_{annee}.docx"
    d.save(chemin)
    return chemin


def generer_fiches_note(conn, dossier, pids: list[int], annee: int) -> Path:
    """بطاقة النقطة المهنية لاجتياز امتحان الكفاءة المهنية (نموذج رقم 1)، مملوءة بمعطيات كل مترشح(ة)؛ صفحة لكل واحد.
    النقطة يمنحها المدير(ة)، ونقطة آخر تفتيش تدونها مصالح المديرية الإقليمية."""
    from docx.enum.text import WD_BREAK
    from idara.services import etablissement as etab_srv
    from idara.services.docs_association import _cellule, _ombre, para, tableau
    if not pids:
        raise ErreurTarqiya("اختر مترشحاً واحداً على الأقل.")
    d, c = _doc(conn, dossier)
    e = etab_srv.lire_etablissement(conn)
    for k, pid in enumerate(pids):
        p = pers.lire(conn, pid)
        if k:
            d.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
        para(d, f"امتحانات الكفاءة المهنية - دورة {annee}", gras=True, centre=True, taille=15, apres=0)
        para(d, "- هيئة التربية والتعليم -", gras=True, centre=True, taille=13, apres=0)
        para(d, "بطاقة النقطة المهنية لاجتياز امتحان الكفاءة المهنية (نموذج رقم 1)", gras=True, centre=True,
             taille=14, apres=4)
        para(d, "[ X ]  لولوج الدرجة الأولى من إطار أساتذة التعليم الابتدائي", gras=True, taille=12, apres=4)
        for lib, v in (("التخصص", p.matiere), ("الاسم الشخصي", p.prenom_ar), ("الاسم العائلي", p.nom_ar),
                       ("رقم التأجير", p.ppr), ("رقم البطاقة الوطنية للتعريف", p.cin),
                       ("الإطار والدرجة", f"{pers.cadre_accorde(p.cadre or 'أستاذ(ة) التعليم الابتدائي', p.sexe)} - "
                                         f"{p.grade}"),
                       ("تاريخ التسمية في الدرجة", tx.date_chiffres(p.date_grade) if p.date_grade else ""),
                       ("مقر العمل", c["etablissement"]),
                       ("المديرية الإقليمية", (e.direction_ar if e else "") or "")):
            para(d, f"{lib}: {v or '........................................'}", taille=12, apres=0)
        para(d, "توقيع المترشح(ة):", gras=True, taille=12, apres=8)
        para(d, "النقطة المهنية", gras=True, taille=13, apres=2)
        t = tableau(d, 8, 4, largeurs=[4.6, 2.2, 5.2, 5.4])
        for j, h in enumerate(("عناصر التنقيط", "سلم التنقيط", "توقيع وخاتم الرئيس المباشر",
                               "مصادقة المدير(ة) الإقليمي(ة)")):
            _cellule(t.cell(0, j), h, gras=True, taille=10)
            _ombre(t.cell(0, j))
        for i, (lib, s) in enumerate((("إنجاز الأعمال المرتبطة بالوظيفة", 5), ("المردودية", 5),
                                      ("السلوك المهني", 5), ("القدرة على التنظيم", 3), ("البحث والابتكار", 2),
                                      ("مجموع النقط الجزئية", 20)), start=1):
            _cellule(t.cell(i, 0), lib, gras=i == 6, taille=10)
            _cellule(t.cell(i, 1), f"..... / {s}", gras=i == 6, taille=10)
        _cellule(t.cell(7, 0), "نقطة آخر تفتيش (تدونها مصالح المديرية الإقليمية بالاستناد إلى الملف الإداري)",
                 taille=9)
        _cellule(t.cell(7, 1), "..... / 20", taille=10)
        c2 = t.cell(1, 2).merge(t.cell(7, 2))
        _cellule(c2, "بعد التأكد من توفر المترشح(ة) على الأقدمية المطلوبة", taille=9)
        c3 = t.cell(1, 3).merge(t.cell(7, 3))
        _cellule(c3, "", taille=9)
        para(d, apres=4)
        para(d, f"حرر ب{c['ville']} في: ........................", taille=12, apres=2)
        para(d, "- ترفق البطاقة بنسخة من آخر تقرير للتفتيش، وترسل في ظرف سري مختوم.", taille=9, apres=0)
    rep = dossier.archives / str(annee) / "الترقية"
    rep.mkdir(parents=True, exist_ok=True)
    chemin = rep / f"{datetime.now():%Y%m%d_%H%M%S}_بطاقات_النقطة_المهنية_{annee}.docx"
    d.save(chemin)
    return chemin
