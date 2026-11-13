"""الزليج في الواجهة: ثلاثة استعمالات فقط (الشريط، الخلفية الخافتة، النجمة)."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

from idara import marque
from idara.ui import theme

RACINE2 = math.sqrt(2)


def _carres_etoile(cx: float, cy: float, a: float) -> tuple[QPolygonF, QPolygonF]:
    """النجمة الثمانية = مربعان متراكبان، أحدهما مدار بـ 45 درجة."""
    droit = QPolygonF([QPointF(cx - a, cy - a), QPointF(cx + a, cy - a),
                       QPointF(cx + a, cy + a), QPointF(cx - a, cy + a)])
    r = a * RACINE2
    tourne = QPolygonF([QPointF(cx, cy - r), QPointF(cx + r, cy),
                        QPointF(cx, cy + r), QPointF(cx - r, cy)])
    return droit, tourne


def _losange(cx: float, cy: float, d: float) -> QPolygonF:
    return QPolygonF([QPointF(cx, cy - d), QPointF(cx + d, cy),
                      QPointF(cx, cy + d), QPointF(cx - d, cy)])


def dessiner_etoile(p: QPainter, cx: float, cy: float, a: float,
                    couleur: str = theme.VERT, pleine: bool = True, trou: bool = False) -> None:
    droit, tourne = _carres_etoile(cx, cy, a)
    if pleine:
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(couleur))
    else:
        p.setPen(QPen(QColor(couleur), 1))
        p.setBrush(Qt.NoBrush)
    p.drawPolygon(droit)
    p.drawPolygon(tourne)
    if trou:
        p.setBrush(QColor(theme.BLANC))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx, cy), a * 0.5, a * 0.5)


class BandeZellige(QWidget):
    """1. الشريط: 18 بكسل أعلى القائمة الجانبية فقط."""

    PAS = 28

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(18)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        for x in range(0, self.width() + self.PAS, self.PAS):
            dessiner_etoile(p, x + 14, 9, 6, theme.NAV_ACCENT, pleine=False)
            p.setPen(QPen(QColor(theme.ROUGE if not theme.NAV_SOMBRE else theme.NAV_MOTIF), 1))
            p.setBrush(Qt.NoBrush)
            p.drawPolygon(_losange(x, 9, 4))
        p.end()


class FondZellige(QWidget):
    """2. الخلفية الخافتة: شفافية 8% في المساحات الفارغة فقط، لا خلف النصوص الكثيفة."""

    PAS = 56

    def __init__(self, parent=None, opacite: float = 0.08, couleur_fond: str | None = None):
        super().__init__(parent)
        self.opacite = opacite
        self.couleur_fond = couleur_fond

    def paintEvent(self, _):
        p = QPainter(self)
        if self.couleur_fond:   # دون لون: شفاف فوق خلفية الشريط الجانبي
            p.fillRect(self.rect(), QColor(self.couleur_fond))
        p.setRenderHint(QPainter.Antialiasing)
        p.setOpacity(self.opacite)
        motif = theme.NAV_MOTIF
        pen = QPen(QColor(motif), 1.2)
        for y in range(0, self.height() + self.PAS, self.PAS):
            for x in range(0, self.width() + self.PAS, self.PAS):
                dessiner_etoile(p, x + 28, y + 28, 12, motif, pleine=False)
                p.setPen(pen)
                p.setBrush(Qt.NoBrush)
                p.drawPolygon(_losange(x, y, 8))
        p.end()


class LogoEtoile(QWidget):
    """3. النجمة: شعار التطبيق."""

    def __init__(self, taille: int = 36, parent=None):
        super().__init__(parent)
        self.setFixedSize(taille, taille)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        t = self.width()
        dessiner_etoile(p, t / 2, t / 2, t * 0.28, theme.NAV_ACCENT, pleine=True, trou=True)
        p.end()


class LogoMarque(QWidget):
    """رمز البرنامج (باب بقوس مغربي، هوية «رحاب»: اختيار المدير 2026-11-13)، من هندسة idara/marque.py.
    على شريط جانبي داكن تصير التربيعة بيضاء حتى يظهر الرمز."""

    def __init__(self, taille: int = 36, parent=None, inverse: bool | None = None):
        super().__init__(parent)
        self.setFixedSize(taille, taille)
        self.inverse = inverse
        self.setToolTip(f"{marque.NOM_COURT} {marque.SOUS_TITRE}")

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        k = self.width() / marque.COTE
        inverse = theme.NAV_SOMBRE if self.inverse is None else self.inverse
        for nature, couleur, g in marque.formes(inverse):
            p.setBrush(QColor(couleur))
            if nature in ("tuile", "rect"):
                x0, y0, x1, y1, r = g
                p.drawRoundedRect(QRectF(x0 * k, y0 * k, (x1 - x0) * k, (y1 - y0) * k), r * k, r * k)
            else:
                p.drawPolygon(QPolygonF([QPointF(x * k, y * k) for x, y in g]))
        p.end()
