"""عناصر الإحصائيات المرسومة بالكود (اقتراح المدير 2026-11-06): بطاقة رقم بخط جانبي ملون، حلقة توزيع،
وأعمدة مزدوجة (قبلي/بعدي)."""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from idara.ui import icones, theme


def _ltr(t: str) -> str:
    return f"⁦{t}⁩"


class Tuile(QFrame):
    """بطاقة رقم: أيقونة في مربع ملون، الرقم بخط عريض، العنوان تحته، وخط جانبي بلون المؤشر."""

    def __init__(self, libelle: str, valeur: str, couleur: str, section: str = "لوحة القيادة", note: str = ""):
        super().__init__()
        self.setObjectName("tuile")
        self.setMinimumHeight(76)
        self.setStyleSheet(f"QFrame#tuile {{ border-right: 5px solid {couleur}; }}")
        h = QHBoxLayout(self)
        h.setContentsMargins(16, 12, 14, 12)
        h.setSpacing(14)
        ic = QLabel()
        ic.setPixmap(icones.tuile(section, 40, sombre=False))
        ic.setFixedSize(40, 40)
        v = QVBoxLayout()
        v.setSpacing(0)
        self.chiffre = QLabel(valeur)
        self.chiffre.setObjectName("tuileChiffre")
        l = QLabel(libelle)
        l.setObjectName("tuileLib")
        l.setWordWrap(True)
        v.addWidget(self.chiffre)
        v.addWidget(l)
        if note:
            n = QLabel(note)
            n.setObjectName("etiquette")
            n.setWordWrap(True)
            v.addWidget(n)
        h.addWidget(ic)
        h.addLayout(v, 1)


class Anneau(QWidget):
    """حلقة توزيع (أجزاء بألوان) مع نسبة في الوسط ومفتاح على الجانب."""

    def __init__(self, parts: list[tuple[str, int, float | None]], couleurs: list[str], centre: str = "",
                 sous_centre: str = ""):
        super().__init__()
        self.parts, self.couleurs, self.centre, self.sous_centre = parts, couleurs, centre, sous_centre
        self.setMinimumHeight(190)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def sizeHint(self):
        return QSize(520, 190)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        d = 160
        r = QRectF(self.width() - d - 16, 15, d, d)   # الحلقة على اليمين (RTL)
        total = sum(n for _, n, _ in self.parts)
        p.setPen(QPen(QColor(theme.LIGNE), 26, Qt.SolidLine, Qt.FlatCap))
        p.drawArc(r.adjusted(13, 13, -13, -13), 0, 360 * 16)
        debut = 90 * 16
        for (lib, n, _), c in zip(self.parts, self.couleurs):
            if not total or not n:
                continue
            etendue = -int(n / total * 360 * 16)
            p.setPen(QPen(QColor(c), 26, Qt.SolidLine, Qt.FlatCap))
            p.drawArc(r.adjusted(13, 13, -13, -13), debut, etendue)
            debut += etendue
        f = QFont(self.font())
        f.setPointSize(15)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor(theme.ENCRE))
        p.drawText(r.adjusted(0, -10, 0, -10), Qt.AlignCenter, self.centre)
        f.setPointSize(8)
        f.setBold(False)
        p.setFont(f)
        p.setPen(QColor(theme.GRIS))
        p.drawText(r.adjusted(0, 26, 0, 26), Qt.AlignCenter, self.sous_centre)
        # المفتاح
        x_fin = self.width() - d - 40
        y = 40
        for (lib, n, pct), c in zip(self.parts, self.couleurs):
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(c))
            p.drawEllipse(QRectF(x_fin - 12, y + 4, 11, 11))
            f.setPointSize(10)
            f.setBold(False)
            p.setFont(f)
            p.setPen(QColor(theme.ENCRE))
            p.drawText(QRectF(140, y, x_fin - 160, 22), Qt.AlignRight | Qt.AlignVCenter, lib)
            f.setBold(True)
            p.setFont(f)
            p.drawText(QRectF(70, y, 60, 22), Qt.AlignRight | Qt.AlignVCenter, str(n))
            f.setBold(False)
            p.setFont(f)
            p.setPen(QColor(theme.GRIS))
            p.drawText(QRectF(0, y, 64, 22), Qt.AlignLeft | Qt.AlignVCenter, _ltr("—" if pct is None else f"{pct:g}%"))
            y += 40
        p.end()


class BarresGroupees(QWidget):
    """أعمدة مزدوجة لكل فئة (مثلاً: قبلي/بعدي لكل مستوى)، بالنسب المئوية من 0 إلى 100."""

    def __init__(self, categories: list[str], series: list[tuple[str, list[float | None], str]],
                 maximum: float | None = 100):
        """maximum=None: سلّم آلي حسب أكبر قيمة (نسب الغياب الصغيرة مثلاً)."""
        super().__init__()
        self.categories, self.series = categories, series
        if maximum is None:
            vals = [v for _, l, _ in series for v in l if v is not None]
            haut = max(vals, default=0)
            pas = next((p for p in (1, 2, 5, 10, 20, 25) if haut <= p * 4), 25)
            maximum = pas * 4
        self.maximum = maximum
        self.setMinimumHeight(300)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def sizeHint(self):
        return QSize(700, 300)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        f = QFont(self.font())
        f.setPointSize(8)
        p.setFont(f)
        gauche, droite, haut, bas = 48, 12, 34, 40
        h = self.height() - haut - bas
        w = self.width() - gauche - droite
        # المفتاح
        x = self.width() - droite
        for nom, _, c in self.series:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(c))
            p.drawRoundedRect(QRectF(x - 12, 8, 12, 12), 3, 3)
            p.setPen(QColor(theme.ENCRE))
            tw = p.fontMetrics().horizontalAdvance(nom) + 8
            p.drawText(QRectF(x - 18 - tw, 4, tw, 20), Qt.AlignRight | Qt.AlignVCenter, nom)
            x -= 30 + tw
        # المحاور
        for k in range(5):
            y = haut + h - h * k / 4
            p.setPen(QPen(QColor(theme.LIGNE), 1))
            p.drawLine(gauche, int(y), gauche + w, int(y))
            p.setPen(QColor(theme.GRIS))
            p.drawText(QRectF(0, y - 9, gauche - 6, 18), Qt.AlignRight | Qt.AlignVCenter,
                       _ltr(f"{self.maximum * k / 4:g}%"))
        n = max(1, len(self.categories))
        pas = w / n
        larg = min(46, pas / (len(self.series) + 1.2))
        # الفئات من اليمين إلى اليسار (RTL)
        for i, cat in enumerate(self.categories):
            cx = gauche + w - pas * (i + 0.5)
            total_l = larg * len(self.series) + 6 * (len(self.series) - 1)
            x0 = cx + total_l / 2
            for j, (_, vals, c) in enumerate(self.series):
                v = vals[i]
                xb = x0 - (j + 1) * larg - j * 6
                if v is not None:
                    hb = h * min(v, self.maximum) / self.maximum
                    p.setPen(Qt.NoPen)
                    p.setBrush(QColor(c))
                    p.drawRoundedRect(QRectF(xb, haut + h - hb, larg, hb), 4, 4)
                    p.setPen(QColor(theme.ENCRE))
                    f.setBold(True)
                    p.setFont(f)
                    p.drawText(QRectF(xb - 10, haut + h - hb - 18, larg + 20, 16), Qt.AlignCenter, _ltr(f"{v:g}"))
                    f.setBold(False)
                    p.setFont(f)
            p.setPen(QColor(theme.ENCRE))
            f.setBold(True)
            p.setFont(f)
            p.drawText(QRectF(cx - pas / 2, haut + h + 8, pas, 22), Qt.AlignCenter, cat)
            f.setBold(False)
            p.setFont(f)
        p.end()
