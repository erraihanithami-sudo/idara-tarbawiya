"""عناصر الواجهة المشتركة بين الصفحات."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget


def carte(titre: str | None = None) -> tuple[QFrame, QVBoxLayout]:
    c = QFrame()
    c.setObjectName("carte")
    v = QVBoxLayout(c)
    v.setContentsMargins(24, 20, 24, 20)
    v.setSpacing(10)
    if titre:
        t = QLabel(titre)
        t.setObjectName("titreCarte")
        v.addWidget(t)
    return c, v


def page_defilante(contenu: QWidget) -> QScrollArea:
    z = QScrollArea()
    z.setWidgetResizable(True)
    z.setFrameShape(QFrame.NoFrame)
    contenu.setObjectName("fond")
    contenu.setAttribute(Qt.WA_StyledBackground, True)
    z.setWidget(contenu)
    return z


class EnTete(QFrame):
    """رأس كل صفحة داخلية (طلب المدير 2026-11-17: محتوى فخم مثل الشريط الجانبي): تدرّج بلون قسم الصفحة،
    نجوم زليج خافتة في الجهة اليسرى، أيقونة القسم، العنوان بالأبيض وسطر تعريفي. القسم تحدده النافذة الرئيسية
    بعد بناء الصفحات (definir_section)؛ قبله يُرسم بألوان المظهر."""

    def __init__(self, titre: str, sous_titre: str = ""):
        super().__init__()
        self.setObjectName("enTete")
        self.section: str | None = None
        self.setMinimumHeight(104)
        h = QHBoxLayout(self)
        h.setContentsMargins(26, 16, 26, 18)
        h.setSpacing(16)
        self.icone = QLabel()
        self.icone.setFixedSize(QSize(54, 54))
        self.icone.setStyleSheet("background: transparent;")
        self.icone.hide()
        h.addWidget(self.icone, 0, Qt.AlignVCenter)
        v = QVBoxLayout()
        v.setSpacing(2)
        self.titre = QLabel(titre)
        self.titre.setObjectName("heroTitre")
        self.titre.setWordWrap(True)
        v.addStretch()
        v.addWidget(self.titre)
        self.sous = QLabel(sous_titre)
        self.sous.setObjectName("heroSous")
        self.sous.setWordWrap(True)
        v.addWidget(self.sous)   # الإخفاء بعد الإضافة: عنصر بلا أب يُظهَر يصير نافذة طارئة (بلاغ 2026-11-21)
        self.sous.setVisible(bool(sous_titre))
        v.addStretch()
        h.addLayout(v, 1)

    def definir_section(self, section: str | None) -> None:
        from idara.ui import icones
        self.section = section
        if section:
            self.icone.setPixmap(icones.tuile(section, 54, sombre=True))
            self.icone.show()
        self.update()

    def paintEvent(self, ev):
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath

        from idara.ui import icones, theme
        from idara.ui.zellige import dessiner_etoile
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if theme.LUXE:   # الليلي والذهبي: مظهر صفحة التواصل على كل الصفحات (2026-11-20)
            from idara.ui.zellige import peindre_luxe
            peindre_luxe(p, QRectF(self.rect()).adjusted(1, 1, -1, -1), 20)
            p.end()
            return
        g = QLinearGradient(self.width(), 0, 0, self.height())
        if self.section:
            c = QColor(icones.COULEURS.get(self.section, theme.VERT))
            g.setColorAt(0, c.darker(170))
            g.setColorAt(1, c.darker(120))
        else:
            g.setColorAt(0, QColor(theme.HERO_FOND))
            g.setColorAt(1, QColor(theme.HERO_FOND2))
        ch = QPainterPath()
        ch.addRoundedRect(QRectF(self.rect()), 18, 18)
        p.fillPath(ch, g)
        p.setClipPath(ch)
        p.setOpacity(0.12)
        for k, y in enumerate(range(-8, self.height() + 50, 42)):
            for x in range(16 + (21 if k % 2 else 0), int(self.width() * 0.38), 42):
                dessiner_etoile(p, x, y, 12, "#FFFFFF", pleine=False)
        p.setOpacity(1)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(theme.DORE))
        p.drawRect(QRectF(0, self.height() - 4, self.width(), 4))
        p.end()


def entete(titre: str, sous_titre: str = "") -> QWidget:
    return EnTete(titre, sous_titre)


def bouton(texte: str) -> QPushButton:
    """زر عادي؛ أزرار الحذف بالأحمر مع علامة الحذف (اقتراح المدير 2026-11-03)."""
    b = QPushButton(texte)
    if texte.strip().startswith("حذف"):
        from idara.ui import icones
        b.setObjectName("danger")
        b.setIcon(icones.corbeille())
    return b
