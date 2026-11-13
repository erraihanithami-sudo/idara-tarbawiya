"""هوية «الشامل في الإدارة التربوية بالمغرب» (اختيار المدير 2026-11-13: الاتجاه «رحاب»).

الرمز: باب مدرسة بقوس مغربي (حدوة) أبيض، في داخله باب أصفر ومعين أزرق، على مربع بأزرق ماجوريل.
الأشكال معرَّفة هنا بإحداثيات مربع 256×256 ودون Qt، حتى يرسمها البرنامج (الشريط الجانبي، المساعد)
ويولّد منها ملف الأيقونة (outils/generer_icone.py) بنفس الهندسة.
"""

from __future__ import annotations

import math

NOM_COURT = "الشامل"
SOUS_TITRE = "في الإدارة التربوية بالمغرب"

MAJORELLE = "#3B3FB6"
MAJORELLE_FONCE = "#2E3192"
JAUNE = "#F2C14E"
BLANC = "#FFFFFF"
NUIT = "#1B1B3A"

COTE = 256.0
RAYON_TUILE = 56.0


def _arc(cx: float, cy: float, r: float, x0: float, x1: float, y: float, n: int = 48) -> list[tuple[float, float]]:
    """قوس حدوة من (x0، y) إلى (x1، y) مروراً بالأعلى، مركزه (cx، cy) فوق الوتر."""
    a0 = math.atan2(y - cy, x0 - cx)          # إحداثيات الشاشة: y نحو الأسفل
    a1 = math.atan2(y - cy, x1 - cx) + 2 * math.pi
    return [(cx + r * math.cos(a0 + (a1 - a0) * k / n), cy + r * math.sin(a0 + (a1 - a0) * k / n))
            for k in range(n + 1)]


def _porte(x0: float, x1: float, haut: float, r: float, bas: float) -> list[tuple[float, float]]:
    cx = (x0 + x1) / 2
    demi = (x1 - x0) / 2
    cy = haut - math.sqrt(r * r - demi * demi)
    return [(x0, bas)] + _arc(cx, cy, r, x0, x1, haut) + [(x1, bas)]


ARC_EXTERIEUR = _porte(80, 176, 150, 52, 212)
ARC_INTERIEUR = _porte(98, 158, 154, 34, 212)
LOSANGE = [(128, 132), (140, 146), (128, 160), (116, 146)]
SEUIL = (64, 212, 192, 224, 4)        # x0, y0, x1, y1, rayon


def couleurs(inverse: bool = False) -> dict[str, str]:
    """inverse: على خلفية زرقاء داكنة (الشريط الجانبي) تصير التربيعة بيضاء والقوس أزرق."""
    if inverse:
        return {"tuile": BLANC, "arc": MAJORELLE, "porte": JAUNE, "losange": MAJORELLE, "seuil": MAJORELLE}
    return {"tuile": MAJORELLE, "arc": BLANC, "porte": JAUNE, "losange": MAJORELLE, "seuil": BLANC}


def formes(inverse: bool = False) -> list[tuple[str, str, object]]:
    """(النوع، اللون، الهندسة) بترتيب الرسم: tuile ثم المضلعات ثم العتبة."""
    c = couleurs(inverse)
    return [("tuile", c["tuile"], (0, 0, COTE, COTE, RAYON_TUILE)),
            ("poly", c["arc"], ARC_EXTERIEUR),
            ("poly", c["porte"], ARC_INTERIEUR),
            ("poly", c["losange"], LOSANGE),
            ("rect", c["seuil"], SEUIL)]
