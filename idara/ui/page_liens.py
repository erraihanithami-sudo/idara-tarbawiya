"""روابط مهمة (طلب المدير 2026-11-20): المنصات الرقمية التي يحتاجها مدير المؤسسة، في صفحة فاخرة على نسق صفحة
التواصل. الروابط لا تُعرض: كل بطاقة تفتح منصتها في المتصفح بزر واحد.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from idara.ui import page_contact as pc
from idara.ui.zellige import dessiner_etoile


@dataclass(frozen=True)
class Plateforme:
    cle: str
    titre: str
    sous: str
    description: str
    url: str
    couleurs: tuple[str, str]


PLATEFORMES = (
    Plateforme("massar", "منصة مسار", "منظومة تدبير التمدرس",
               "لوائح التلاميذ والأقسام، النقط والمعدلات، الغياب، الحركية، والشهادات المدرسية.",
               "https://idprovider.men.gov.ma/?RedirectUrl=https://massar.men.gov.ma", ("#1E88E5", "#0D3C7A")),
    Plateforme("masir", "منصة مسير", "تدبير الموارد البشرية",
               "الوضعيات الإدارية للموظفين، الرخص والتغيبات، الحركات الانتقالية، والملفات الإدارية.",
               "https://masirhnew.men.gov.ma/", ("#26A69A", "#00574B")),
    Plateforme("tabligh", "منصة تبليغ", "التبليغ والإشعارات",
               "تبليغ القرارات والمراسلات الإدارية إلى الموظفين وتتبع توصلهم بها.",
               "https://idprovider.men.gov.ma/?RedirectUrl=https://notifrh.men.gov.ma", ("#FB8C00", "#A23E00")),
    Plateforme("sise", "منصة أوسايز (SISE)", "الإحصاء المدرسي",
               "معطيات الإحصاء السنوي للمؤسسة: البنية، التلاميذ، الأطر، والتجهيزات.",
               "https://idprovider.men.gov.ma/?RedirectUrl=https://sise.men.gov.ma/ESISEV2", ("#8E24AA", "#4A0E68")),
)


class Embleme(QWidget):
    """رسم أبيض لكل منصة: قبعة تخرج (مسار)، أشخاص (مسير)، جرس (تبليغ)، أعمدة (أوسايز)."""

    def __init__(self, cle: str, couleur: str):
        super().__init__()
        self.cle, self.couleur = cle, QColor(couleur)
        self.setFixedSize(92, 92)

    def paintEvent(self, ev):   # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = QPointF(46, 46)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 55))
        p.drawEllipse(c, 44, 44)
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(c, 33, 33)
        coul = self.couleur
        p.setBrush(coul)
        p.setPen(QPen(coul, 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        if self.cle == "massar":
            ch = QPainterPath()
            ch.moveTo(22, 42)
            ch.lineTo(46, 31)
            ch.lineTo(70, 42)
            ch.lineTo(46, 53)
            ch.closeSubpath()
            p.drawPath(ch)
            p.setBrush(Qt.NoBrush)
            p.drawArc(QRectF(32, 40, 28, 22), 180 * 16, 180 * 16)
            p.drawLine(QPointF(66, 44), QPointF(66, 58))
        elif self.cle == "masir":
            for x, r in ((36, 7.5), (56, 7.5)):
                p.drawEllipse(QPointF(x, 38), r, r)
                p.drawPie(QRectF(x - 13, 50, 26, 22), 0, 180 * 16)
        elif self.cle == "tabligh":
            ch = QPainterPath()
            ch.moveTo(30, 60)
            ch.cubicTo(34, 54, 32, 34, 46, 32)
            ch.cubicTo(60, 34, 58, 54, 62, 60)
            ch.closeSubpath()
            p.drawPath(ch)
            p.drawEllipse(QPointF(46, 64), 4, 4)
            p.drawEllipse(QPointF(46, 29), 2.5, 2.5)
        else:
            for x, hgt in ((30, 14), (42, 24), (54, 32)):
                p.drawRoundedRect(QRectF(x, 62 - hgt, 9, hgt), 2, 2)
            p.setBrush(Qt.NoBrush)
            p.drawLine(QPointF(26, 64), QPointF(68, 64))
        p.end()


class CartePlateforme(QFrame):
    """بطاقة منصة بتدرج لوني ونجوم زليج، دون إظهار الرابط."""

    def __init__(self, pf: Plateforme, ouvrir):
        super().__init__()
        self.pf = pf
        self.setMinimumHeight(240)
        self.setCursor(Qt.PointingHandCursor)
        v = QVBoxLayout(self)
        v.setContentsMargins(26, 22, 26, 22)
        v.setSpacing(8)
        h = QHBoxLayout()
        h.addWidget(Embleme(pf.cle, pf.couleurs[1]))
        tv = QVBoxLayout()
        t = QLabel(pf.titre)
        t.setStyleSheet("color: white; font-size: 18pt; font-weight: 800; background: transparent;")
        tv.addWidget(t)
        s = QLabel(pf.sous)
        s.setStyleSheet("color: #FFE9A8; font-size: 11.5pt; font-weight: 700; background: transparent;")
        tv.addWidget(s)
        h.addLayout(tv, 1)
        v.addLayout(h)
        d = QLabel(pf.description)
        d.setWordWrap(True)
        d.setStyleSheet("color: rgba(255,255,255,0.93); font-size: 11pt; background: rgba(255,255,255,0.12); "
                        "border: 1px solid rgba(255,255,255,0.35); border-radius: 14px; padding: 10px 12px;")
        v.addWidget(d)
        v.addStretch()
        self.bouton = QPushButton(f"الدخول إلى {pf.titre}")
        self.bouton.setObjectName("boutonCouleur")
        self.bouton.setCursor(Qt.PointingHandCursor)
        self.bouton.setMinimumHeight(44)
        self.bouton.setToolTip("يُفتح في المتصفح")
        self.bouton.setStyleSheet(
            f"QPushButton {{ background: #FFFFFF; color: {pf.couleurs[1]}; border: 1px solid rgba(255,255,255,0.7); "
            f"border-radius: 14px; padding: 8px 18px; font-weight: 800; font-size: 11.5pt; }}"
            f"QPushButton:hover {{ background: #FFF6DA; }}")
        self.bouton.clicked.connect(lambda: ouvrir(pf))
        v.addWidget(self.bouton)
        self._ouvrir = ouvrir

    def mouseReleaseEvent(self, ev):   # noqa: N802
        if ev.button() == Qt.LeftButton:
            self._ouvrir(self.pf)
        super().mouseReleaseEvent(ev)

    def paintEvent(self, ev):   # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 40))
        p.drawRoundedRect(r.translated(2, 5), 26, 26)
        g = QLinearGradient(r.topRight(), r.bottomLeft())
        g.setColorAt(0, QColor(self.pf.couleurs[0]))
        g.setColorAt(1, QColor(self.pf.couleurs[1]))
        ch = QPainterPath()
        ch.addRoundedRect(r, 26, 26)
        p.fillPath(ch, g)
        p.save()
        p.setClipPath(ch)
        for x, y, s in ((r.left() + 40, r.bottom() - 30, 58), (r.right() - 30, r.top() + 26, 34),
                        (r.left() + 150, r.top() + 10, 20)):
            dessiner_etoile(p, x, y, s, "#FFFFFF", pleine=False)
        p.restore()
        p.setPen(QPen(QColor(255, 255, 255, 90), 1.2))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r.adjusted(6, 6, -6, -6), 21, 21)
        p.end()


class Bandeau(pc.Bandeau):
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
        p.setFont(pc._police(22, True))
        p.drawText(r.adjusted(30, 26, -40, -70), Qt.AlignRight | Qt.AlignVCenter, "روابط مهمة")
        p.setPen(QColor("#E8EEF5"))
        p.setFont(pc._police(12))
        p.drawText(r.adjusted(30, 80, -40, -26), Qt.AlignRight | Qt.AlignVCenter,
                   "المنصات الرقمية التي يحتاجها مدير المؤسسة · بنقرة واحدة")
        p.end()


class PageLiens(QWidget):
    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        self.ouverts: list[str] = []   # للاختبار: الروابط المفتوحة
        racine = QVBoxLayout(self)
        racine.setContentsMargins(48, 36, 48, 36)
        racine.setSpacing(22)
        racine.addWidget(Bandeau())
        g = QGridLayout()
        g.setSpacing(24)
        self.cartes: dict[str, CartePlateforme] = {}
        for k, pf in enumerate(PLATEFORMES):
            c = CartePlateforme(pf, self.ouvrir)
            self.cartes[pf.cle] = c
            g.addWidget(c, k // 2, k % 2)
        for j in range(2):
            g.setColumnStretch(j, 1)
        racine.addLayout(g)
        conseil = QLabel("تُفتح كل منصة في المتصفح. ادخل بحسابك المهني، ولا تحفظ كلمة المرور في حاسوب مشترك.")
        conseil.setAlignment(Qt.AlignCenter)
        conseil.setWordWrap(True)
        conseil.setStyleSheet("color: #5C6B7A; font-size: 11pt; background: #FFF8E7; border: 1px solid #EAD7A4; "
                              "border-radius: 14px; padding: 12px;")
        racine.addWidget(conseil)
        self.l_etat = QLabel()
        self.l_etat.setAlignment(Qt.AlignCenter)
        self.l_etat.setStyleSheet("font-weight: 700;")
        racine.addWidget(self.l_etat)
        racine.addStretch()

    def rafraichir(self) -> None:
        self.l_etat.clear()

    def ouvrir(self, pf: Plateforme) -> bool:
        self.ouverts.append(pf.url)
        try:
            ok = pc.ouvrir_externe(pf.url)
        except Exception:  # noqa: BLE001 — لا متصفح
            ok = False
        self.l_etat.setStyleSheet(f"color: {'#2E7D32' if ok else '#C62828'}; font-weight: 700;")
        self.l_etat.setText(f"فُتحت {pf.titre} في المتصفح." if ok else
                            f"تعذر فتح {pf.titre}: تأكد من وجود متصفح ومن الاتصال بالأنترنت.")
        return ok
