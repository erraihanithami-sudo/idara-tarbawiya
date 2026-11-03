"""أيقونات الأقسام الرئيسية: رسوم مسطحة بلونين (الكحلي ولون القسم) على نمط إنفوغرافيا المدير.

تُرسم بالكود (QPainter) على شبكة 24×24 ثم تُكبَّر، فلا ملفات خارجية ولا حقوق صور.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF

from idara.ui import theme

# لون كل قسم (ألوان الإنفوغرافيا)
COULEURS = {
    "القيادة والتدبير": theme.SARCELLE,
    "تسليم المهام": theme.ORANGE,
    "لوحة القيادة": theme.SARCELLE,
    "التلاميذ": theme.SARCELLE,
    "الموارد البشرية": theme.BLEU,
    "التدبير التربوي": theme.VIOLET,
    "التقييم": theme.ROSE,
    "مجالس المؤسسة": theme.SARCELLE,
    "التدبير المالي والمادي": theme.ORANGE,
    "المراسلات": theme.BLEU,
    "مشروع المؤسسة": theme.VIOLET,
    "الإعدادات": theme.GRIS,
}


def _rr(p: QPainter, x, y, w, h, r, c) -> None:
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(c))
    p.drawRoundedRect(QRectF(x, y, w, h), r, r)


def _tableau(p, a, m):          # لوحة القيادة: أربع بطاقات
    _rr(p, 3, 3, 8, 10, 2, m)
    _rr(p, 13, 3, 8, 6, 2, a)
    _rr(p, 3, 15, 8, 6, 2, a)
    _rr(p, 13, 11, 8, 10, 2, m)


def _personne(p, cx, top, s, c):
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(c))
    p.drawEllipse(QPointF(cx, top + 3.2 * s), 3.2 * s, 3.2 * s)
    chemin = QPainterPath()
    chemin.addRoundedRect(QRectF(cx - 5.5 * s, top + 7.4 * s, 11 * s, 8 * s), 4.5 * s, 4.5 * s)
    p.drawPath(chemin)


def _eleves(p, a, m):            # التلاميذ: شخصان
    _personne(p, 15.5, 3, 0.85, m)
    _personne(p, 9, 6, 1.0, a)


def _personnel(p, a, m):         # الموارد البشرية: بطاقة مهنية
    _rr(p, 2, 5, 20, 15, 3, m)
    _rr(p, 9, 2.5, 6, 4, 1.5, a)
    p.setBrush(QColor(a))
    p.drawEllipse(QPointF(8, 12), 2.6, 2.6)
    _rr(p, 4.5, 15.2, 7, 2.6, 1.3, a)
    for y in (10.5, 14.5):
        _rr(p, 13.5, y, 6, 1.8, 0.9, theme.BLANC)


def _pedagogie(p, a, m):         # التدبير التربوي: كتاب مفتوح
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(a))
    p.drawPolygon(QPolygonF([QPointF(2, 5), QPointF(11.2, 7), QPointF(11.2, 21), QPointF(2, 19)]))
    p.setBrush(QColor(m))
    p.drawPolygon(QPolygonF([QPointF(22, 5), QPointF(12.8, 7), QPointF(12.8, 21), QPointF(22, 19)]))
    p.setPen(QPen(QColor(theme.BLANC), 1.3, Qt.SolidLine, Qt.RoundCap))
    for i in range(3):
        y = 10 + i * 3
        p.drawLine(QPointF(4.5, y), QPointF(9, y + 0.9))


def _evaluation(p, a, m):        # التقييم: أعمدة بيانية
    _rr(p, 3, 12, 4.5, 9, 1.5, m)
    _rr(p, 9.75, 4, 4.5, 17, 1.5, a)
    _rr(p, 16.5, 8, 4.5, 13, 1.5, m)
    _rr(p, 2, 21, 20, 1.6, 0.8, m)


def _conseils(p, a, m):          # مجالس المؤسسة: فقاعتا حوار (كأيقونة الإنفوغرافيا)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(a))
    p.drawRoundedRect(QRectF(2, 3, 13, 9.5), 1.5, 1.5)
    p.drawPolygon(QPolygonF([QPointF(4, 12), QPointF(4, 16), QPointF(8, 12)]))
    p.setBrush(QColor(m))
    p.drawRoundedRect(QRectF(8, 8.5, 14, 10), 1.5, 1.5)
    p.drawPolygon(QPolygonF([QPointF(20, 18), QPointF(20, 22), QPointF(16, 18)]))


def _finance(p, a, m):           # التدبير المالي والمادي: محفظة وقطعة نقدية
    _rr(p, 2, 7, 20, 14, 3, m)
    _rr(p, 4, 3.5, 13, 5, 2, a)
    _rr(p, 14, 11.5, 8, 5, 2.5, a)
    p.setBrush(QColor(theme.BLANC))
    p.drawEllipse(QPointF(17, 14), 1.3, 1.3)


def _correspondance(p, a, m):    # المراسلات: ظرف
    _rr(p, 2, 5, 20, 15, 2.5, a)
    p.setPen(QPen(QColor(m), 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    p.drawPolyline(QPolygonF([QPointF(3.5, 7), QPointF(12, 13.5), QPointF(20.5, 7)]))


def _projet(p, a, m):            # مشروع المؤسسة: مكعبات وراية (كأيقونة الإنفوغرافيا)
    _rr(p, 2, 15, 6, 6, 0.5, a)
    _rr(p, 8, 15, 6, 6, 0.5, m)
    _rr(p, 14, 15, 6, 6, 0.5, a)
    _rr(p, 5, 9, 6, 6, 0.5, m)
    _rr(p, 11, 9, 6, 6, 0.5, QColor(a).lighter(140).name())
    _rr(p, 15.2, 2, 1.6, 7.5, 0.5, m)
    p.setBrush(QColor(m))
    p.drawPolygon(QPolygonF([QPointF(16.8, 2), QPointF(21.5, 3.2), QPointF(16.8, 5.2)]))


def _passation(p, a, m):         # تسليم المهام: ملف يُسلَّم (سهم بين يدين)
    _rr(p, 2, 6, 13, 15, 2, m)
    _rr(p, 2, 4, 6, 4, 1.5, m)
    _rr(p, 4.5, 11, 8, 1.6, 0.8, theme.BLANC)
    _rr(p, 4.5, 14.5, 8, 1.6, 0.8, theme.BLANC)
    p.setPen(QPen(QColor(a), 2.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    p.drawLine(QPointF(12, 17), QPointF(21, 17))
    p.drawPolyline(QPolygonF([QPointF(18, 13.5), QPointF(21.5, 17), QPointF(18, 20.5)]))


def _parametres(p, a, m):        # الإعدادات: مسنن
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(m))
    c = QPointF(12, 12)
    for i in range(8):
        t = i * math.pi / 4
        p.save()
        p.translate(c)
        p.rotate(math.degrees(t))
        p.drawRoundedRect(QRectF(-2.2, -10.5, 4.4, 5), 1, 1)
        p.restore()
    p.drawEllipse(c, 7.2, 7.2)
    p.setBrush(QColor(a))
    p.drawEllipse(c, 3.4, 3.4)


DESSINS = {
    "القيادة والتدبير": _tableau, "تسليم المهام": _passation,
    "لوحة القيادة": _tableau, "التلاميذ": _eleves, "الموارد البشرية": _personnel,
    "التدبير التربوي": _pedagogie, "التقييم": _evaluation, "مجالس المؤسسة": _conseils,
    "التدبير المالي والمادي": _finance, "المراسلات": _correspondance, "مشروع المؤسسة": _projet,
    "الإعدادات": _parametres,
}


def pixmap(section: str, taille: int = 24, echelle: float = 2.0) -> QPixmap:
    n = int(taille * echelle)
    pm = QPixmap(n, n)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(n / 24, n / 24)
    DESSINS.get(section, _tableau)(p, COULEURS.get(section, theme.SARCELLE), theme.MARINE)
    p.end()
    pm.setDevicePixelRatio(echelle)
    return pm


def icone(section: str, taille: int = 24) -> QIcon:
    return QIcon(pixmap(section, taille))
