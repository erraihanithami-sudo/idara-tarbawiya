"""كتابة النصوص كما تُستعمل في الوثائق الإدارية المغربية:
التواريخ بالشهور المغربية والفرنسية، المدد بالحروف، صيغ التذكير والتأنيث، أسماء المستويات.
"""

from __future__ import annotations

from datetime import date

MOIS_AR = ["يناير", "فبراير", "مارس", "أبريل", "ماي", "يونيو",
           "يوليوز", "غشت", "شتنبر", "أكتوبر", "نونبر", "دجنبر"]
JOURS_AR = ["الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
MOIS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
           "septembre", "octobre", "novembre", "décembre"]


def en_date(d: date | str) -> date:
    return d if isinstance(d, date) else date.fromisoformat(d)


# ---------- التواريخ ----------

def date_ar(d: date | str) -> str:
    """23 دجنبر 2025"""
    d = en_date(d)
    return f"{d.day} {MOIS_AR[d.month - 1]} {d.year}"


def date_longue_ar(d: date | str) -> str:
    """السبت 31 أكتوبر 2026"""
    d = en_date(d)
    return f"{JOURS_AR[d.weekday()]} {date_ar(d)}"


def date_chiffres(d: date | str) -> str:
    """06/07/2026 (الصيغة نفسها بالعربية والفرنسية)"""
    d = en_date(d)
    return f"{d.day:02d}/{d.month:02d}/{d.year}"


def date_fr(d: date | str) -> str:
    """1er novembre 2026"""
    d = en_date(d)
    jour = "1er" if d.day == 1 else str(d.day)
    return f"{jour} {MOIS_FR[d.month - 1]} {d.year}"


# ---------- المدد بالحروف ----------

_UNITES = ["", "واحد", "اثنان", "ثلاثة", "أربعة", "خمسة", "ستة", "سبعة", "ثمانية", "تسعة", "عشرة"]
_DIZAINES = {20: "عشرون", 30: "ثلاثون", 40: "أربعون", 50: "خمسون",
             60: "ستون", 70: "سبعون", 80: "ثمانون", 90: "تسعون"}


def duree_jours_ar(n: int) -> str:
    """المدة بالأيام كما تُكتب في طلبات الرخص: ثلاثة أيام، عشرة أيام، أحد عشر يوماً..."""
    if n < 1:
        raise ValueError("المدة يجب أن تكون يوماً واحداً على الأقل")
    if n == 1:
        return "يوم واحد"
    if n == 2:
        return "يومان"
    if n <= 10:
        return f"{_UNITES[n]} أيام"
    if n == 11:
        return "أحد عشر يوماً"
    if n == 12:
        return "اثنا عشر يوماً"
    if n < 20:
        return f"{_UNITES[n - 10]} عشر يوماً"
    if n < 100:
        dizaine, unite = n - n % 10, n % 10
        if unite == 0:
            return f"{_DIZAINES[dizaine]} يوماً"
        u = "واحد" if unite == 1 else _UNITES[unite]
        return f"{u} و{_DIZAINES[dizaine]} يوماً"
    return f"{n} يوماً"


# ---------- التذكير والتأنيث ----------

def accord(sexe: str | None, masculin: str, feminin: str) -> str:
    """يختار الصيغة حسب النوع ('M' أو 'F')."""
    if sexe == "F":
        return feminin
    if sexe == "M":
        return masculin
    raise ValueError("نوع الشخص غير محدد (ذكر أو أنثى)")


# ---------- المستويات ----------

# الرمز ← (الاسم المختصر بالعربية، الصيغة الفرنسية في الوثائق)
NIVEAUX = {
    "PS1": ("الأولى أولي", "1ère année du préscolaire"),
    "PS2": ("الثانية أولي", "2ème année du préscolaire"),
    "1AP": ("الأول", "1ère année de l’enseignement primaire"),
    "2AP": ("الثاني", "2ème année de l’enseignement primaire"),
    "3AP": ("الثالث", "3ème année de l’enseignement primaire"),
    "4AP": ("الرابع", "4ème année de l’enseignement primaire"),
    "5AP": ("الخامس", "5ème année de l’enseignement primaire"),
    "6AP": ("السادس", "6ème année de l’enseignement primaire"),
}


def niveau_ar(code: str) -> str:
    return NIVEAUX[code][0]


def niveau_fr(code: str) -> str:
    return NIVEAUX[code][1]
