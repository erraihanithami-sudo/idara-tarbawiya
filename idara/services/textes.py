"""كتابة التواريخ بالعربية كما تُستعمل في الإدارة المغربية (تُوسَّع في المرحلة 2)."""

from __future__ import annotations

from datetime import date

MOIS_AR = ["يناير", "فبراير", "مارس", "أبريل", "ماي", "يونيو",
           "يوليوز", "غشت", "شتنبر", "أكتوبر", "نونبر", "دجنبر"]
JOURS_AR = ["الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]


def date_ar(d: date) -> str:
    """31 أكتوبر 2026"""
    return f"{d.day} {MOIS_AR[d.month - 1]} {d.year}"


def date_longue_ar(d: date) -> str:
    """السبت 31 أكتوبر 2026"""
    return f"{JOURS_AR[d.weekday()]} {date_ar(d)}"
