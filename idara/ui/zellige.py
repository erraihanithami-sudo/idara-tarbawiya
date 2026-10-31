"""الزليج في الواجهة: ثلاثة استعمالات فقط (الشريط، الخلفية الخافتة، النجمة)."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

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
            dessiner_etoile(p, x + 14, 9, 6, theme.VERT, pleine=False)
            p.setPen(QPen(QColor(theme.ROUGE), 1))
            p.setBrush(Qt.NoBrush)
            p.drawPolygon(_losange(x, 9, 4))
        p.end()


class FondZellige(QWidget):
    """2. الخلفية الخافتة: شفافية 8% في المساحات الفارغة فقط، لا خلف النصوص الكثيفة."""

    PAS = 56

    def __init__(self, parent=None, opacite: float = 0.08, couleur_fond: str = theme.BLANC):
        super().__init__(parent)
        self.opacite = opacite
        self.couleur_fond = couleur_fond

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(self.couleur_fond))
        p.setRenderHint(QPainter.Antialiasing)
        p.setOpacity(self.opacite)
        pen = QPen(QColor(theme.VERT), 1.2)
        for y in range(0, self.height() + self.PAS, self.PAS):
            for x in range(0, self.width() + self.PAS, self.PAS):
                dessiner_etoile(p, x + 28, y + 28, 12, theme.VERT, pleine=False)
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
        dessiner_etoile(p, t / 2, t / 2, t * 0.28, theme.VERT, pleine=True, trou=True)
        p.end()
