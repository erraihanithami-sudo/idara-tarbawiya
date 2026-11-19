"""التواصل مع صاحب البرنامج (طلب المدير 2026-11-19): صفحة فاخرة بقناتين فقط.

- واتساب: رسالة صوتية فقط على الرقم 0666949280 (لا مكالمات).
- البريد الإلكتروني: erraihani.thami@gmail.com
الرقم والبريد نشرهما المدير بطلب صريح منه في هذه الصفحة.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFont, QGuiApplication, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from idara.ui.zellige import dessiner_etoile

TELEPHONE = "0666949280"
WHATSAPP_URL = "https://wa.me/212666949280"
EMAIL = "erraihani.thami@gmail.com"
SUJET = "الشامل في الإدارة التربوية"


def _police(t: float, gras=False) -> QFont:
    f = QFont()
    f.setPointSizeF(t)
    f.setBold(gras)
    return f


class Embleme(QWidget):
    """رسم القناة: فقاعة واتساب بسماعة وموجات صوت، أو ظرف بريد."""

    def __init__(self, nature: str):
        super().__init__()
        self.nature = nature
        self.setFixedSize(96, 96)

    def paintEvent(self, ev):   # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = QPointF(48, 48)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 50))
        p.drawEllipse(c, 46, 46)
        p.setBrush(QColor("#FFFFFF"))
        if self.nature == "wa":
            ch = QPainterPath()
            ch.addEllipse(c, 30, 30)
            q = QPainterPath()
            q.moveTo(24, 78)
            q.lineTo(30, 62)
            q.lineTo(40, 72)
            q.closeSubpath()
            p.drawPath(ch.united(q))
            vert = QColor("#128C7E")
            p.setPen(QPen(vert, 3.4, Qt.SolidLine, Qt.RoundCap))
            p.setBrush(Qt.NoBrush)
            # ميكروفون (رسالة صوتية)
            p.setBrush(vert)
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(QRectF(42, 30, 12, 22), 6, 6)
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(vert, 2.6, Qt.SolidLine, Qt.RoundCap))
            p.drawArc(QRectF(37, 34, 22, 24), 180 * 16, 180 * 16)
            p.drawLine(QPointF(48, 58), QPointF(48, 64))
            p.drawLine(QPointF(42, 64), QPointF(54, 64))
        else:
            r = QRectF(20, 30, 56, 38)
            p.drawRoundedRect(r, 6, 6)
            p.setPen(QPen(QColor("#B23121"), 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.setBrush(Qt.NoBrush)
            ch = QPainterPath()
            ch.moveTo(r.left() + 4, r.top() + 5)
            ch.lineTo(r.center().x(), r.top() + 22)
            ch.lineTo(r.right() - 4, r.top() + 5)
            p.drawPath(ch)
        p.end()


class CarteCanal(QFrame):
    """بطاقة قناة بتدرج لوني ونجوم زليج، وسطر القيمة كبير، وزران."""

    def __init__(self, nature: str, titre: str, valeur: str, note: str, couleurs: tuple[str, str]):
        super().__init__()
        self.couleurs = couleurs
        self.setMinimumHeight(250)
        v = QVBoxLayout(self)
        v.setContentsMargins(28, 24, 28, 24)
        v.setSpacing(8)
        h = QHBoxLayout()
        h.addWidget(Embleme(nature))
        tv = QVBoxLayout()
        t = QLabel(titre)
        t.setStyleSheet("color: white; font-size: 17pt; font-weight: 800; background: transparent;")
        tv.addWidget(t)
        n = QLabel(note)
        n.setWordWrap(True)
        n.setStyleSheet("color: rgba(255,255,255,0.92); font-size: 11pt; background: transparent;")
        tv.addWidget(n)
        h.addLayout(tv, 1)
        v.addLayout(h)
        self.valeur = QLabel(f"⁦{valeur}⁩")
        self.valeur.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.valeur.setAlignment(Qt.AlignCenter)
        self.valeur.setStyleSheet("color: white; font-size: 22pt; font-weight: 800; letter-spacing: 1px; "
                                  "background: rgba(255,255,255,0.16); border: 1px solid rgba(255,255,255,0.45); "
                                  "border-radius: 16px; padding: 10px;")
        v.addWidget(self.valeur)
        self.boutons = QHBoxLayout()
        self.boutons.setSpacing(10)
        v.addLayout(self.boutons)

    def bouton(self, texte: str, fn, plein: bool = True) -> QPushButton:
        b = QPushButton(texte)
        b.setObjectName("boutonCouleur")
        b.setCursor(Qt.PointingHandCursor)
        b.setMinimumHeight(44)
        fond, coul = ("#FFFFFF", self.couleurs[1]) if plein else ("rgba(255,255,255,0.18)", "#FFFFFF")
        b.setStyleSheet(f"QPushButton {{ background: {fond}; color: {coul}; border: 1px solid rgba(255,255,255,0.7); "
                        f"border-radius: 14px; padding: 8px 18px; font-weight: 800; font-size: 11pt; }}"
                        f"QPushButton:hover {{ background: rgba(255,255,255,0.85); color: {self.couleurs[1]}; }}")
        b.clicked.connect(fn)
        self.boutons.addWidget(b)
        return b

    def paintEvent(self, ev):   # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 40))
        p.drawRoundedRect(r.translated(2, 5), 26, 26)
        g = QLinearGradient(r.topRight(), r.bottomLeft())
        g.setColorAt(0, QColor(self.couleurs[0]))
        g.setColorAt(1, QColor(self.couleurs[1]))
        ch = QPainterPath()
        ch.addRoundedRect(r, 26, 26)
        p.fillPath(ch, g)
        p.save()
        p.setClipPath(ch)
        for x, y, s in ((r.left() + 40, r.bottom() - 30, 58), (r.right() - 30, r.top() + 26, 34),
                        (r.left() + 150, r.top() + 10, 20)):
            dessiner_etoile(p, x, y, s, "#FFFFFF", pleine=False)
        p.restore()
        p.end()


class PageContact(QWidget):
    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        self.ouverts: list[str] = []   # للاختبار: الروابط المفتوحة
        racine = QVBoxLayout(self)
        racine.setContentsMargins(48, 36, 48, 36)
        racine.setSpacing(22)
        self.bandeau = Bandeau()
        racine.addWidget(self.bandeau)
        h = QHBoxLayout()
        h.setSpacing(24)
        self.wa = CarteCanal("wa", "واتساب: رسالة صوتية", TELEPHONE,
                             "اترك رسالة صوتية تشرح فيها ملاحظتك أو حاجتك. لا مكالمات.", ("#25D366", "#075E54"))
        self.wa.bouton("فتح واتساب", lambda: self.ouvrir_url(WHATSAPP_URL))
        self.wa.bouton("نسخ الرقم", lambda: self.copier(TELEPHONE), plein=False)
        self.mail = CarteCanal("mail", "البريد الإلكتروني", EMAIL,
                               "للاقتراحات المفصلة وإرسال نماذج الوثائق أو لقطات الشاشة.", ("#EA4335", "#8E1B10"))
        self.mail.bouton("كتابة رسالة", lambda: self.ouvrir_url(f"mailto:{EMAIL}?subject={QUrl.toPercentEncoding(SUJET).data().decode()}"))
        self.mail.bouton("نسخ البريد", lambda: self.copier(EMAIL), plein=False)
        h.addWidget(self.wa, 1)
        h.addWidget(self.mail, 1)
        racine.addLayout(h)
        conseil = QLabel("لتسريع الجواب: اذكر اسم المؤسسة والصفحة المعنية، وأرفق لقطة شاشة إن أمكن.")
        conseil.setAlignment(Qt.AlignCenter)
        conseil.setWordWrap(True)
        conseil.setStyleSheet("color: #5C6B7A; font-size: 11pt; background: #FFF8E7; border: 1px solid #EAD7A4; "
                              "border-radius: 14px; padding: 12px;")
        racine.addWidget(conseil)
        self.l_copie = QLabel()
        self.l_copie.setAlignment(Qt.AlignCenter)
        self.l_copie.setStyleSheet("color: #2E7D32; font-weight: 700;")
        racine.addWidget(self.l_copie)
        racine.addStretch()

    def ouvrir_url(self, url: str) -> bool:
        self.ouverts.append(url)
        try:
            return QDesktopServices.openUrl(QUrl(url))
        except Exception:  # noqa: BLE001 — لا متصفح أو لا برنامج بريد
            return False

    def copier(self, texte: str) -> None:
        QGuiApplication.clipboard().setText(texte)
        self.l_copie.setText(f"نُسخ: ⁦{texte}⁩")


class Bandeau(QWidget):
    """رأس فاخر: تدرج ليلي، إطار ذهبي، نجوم زليج، والعنوان."""

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(170)

    def sizeHint(self):
        return QSize(800, 170)

    def paintEvent(self, ev):   # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        g = QLinearGradient(r.topRight(), r.bottomLeft())
        g.setColorAt(0, QColor("#0B1C2C"))
        g.setColorAt(1, QColor("#1F3B57"))
        ch = QPainterPath()
        ch.addRoundedRect(r, 26, 26)
        p.fillPath(ch, g)
        p.setPen(QPen(QColor("#C9A04A"), 2))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r.adjusted(8, 8, -8, -8), 20, 20)
        p.save()
        p.setClipPath(ch)
        for x, y, s in ((r.left() + 70, r.center().y(), 46), (r.left() + 150, r.top() + 34, 18),
                        (r.left() + 190, r.bottom() - 34, 12)):
            dessiner_etoile(p, x, y, s, "#C9A04A", pleine=False)
        p.restore()
        p.setPen(QColor("#F3D27A"))
        p.setFont(_police(22, True))
        p.drawText(r.adjusted(30, 26, -40, -70), Qt.AlignRight | Qt.AlignVCenter, "التواصل مع صاحب البرنامج")
        p.setPen(QColor("#E8EEF5"))
        p.setFont(_police(12))
        p.drawText(r.adjusted(30, 80, -40, -26), Qt.AlignRight | Qt.AlignVCenter,
                   "الشامل في الإدارة التربوية بالمغرب · ملاحظاتك تصنع النسخ القادمة")
        p.end()
