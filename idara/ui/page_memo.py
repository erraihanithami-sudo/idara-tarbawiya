"""مفكرة المدير (طلب المدير 2026-11-19، والصورة المرفقة: سبورة فلين بإطار خشبي وأوراق ملونة مثبتة بدبابيس).

- يمين الصفحة: رزمة بطاقات post-it بألوانها؛ الضغط على بطاقة يفتح نافذة الموضوع والتاريخ والساعة.
- وسط الصفحة: السبورة، تُلصق عليها التذكيرات بعد الحفظ (ملخص الموضوع، التاريخ، الساعة) مائلة قليلاً بدبوس.
  الضغط على ورقة يفتحها للتعديل أو «تم» أو الحذف.
- يسار الصفحة: ساعة حقيقية (عقارب) والتاريخ، ويومية فاخرة تُبرز الأيام التي فيها تذكير أو محطة من برنامج
  العمل السنوي أو من المقرر الوزاري، وتظهر تفاصيلها عند الوقوف عليها بالفأرة.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta

from PySide6.QtCore import QEvent, QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import (QComboBox, QFormLayout, QGridLayout, QHBoxLayout, QLabel, QPlainTextEdit,
                               QPushButton, QToolTip, QVBoxLayout, QWidget)

from idara.services import memo as mm
from idara.services import textes as tx
from idara.ui.composants import entete
from idara.ui.formulaires import champ
from idara.ui.saisie import ChampDate, message
from idara.ui.vitrine import FenetreFiche, bouton_couleur

JOURS = ["الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
COUL_EV = {"memo": "#EF6C00", "ministere": "#3949AB", "local": "#00897B"}
LIB_EV = {"memo": "تذكير", "ministere": "المقرر الوزاري", "local": "برنامج العمل السنوي"}


def _police(taille: float, gras: bool = False) -> QFont:
    f = QFont()
    f.setPointSizeF(taille)
    f.setBold(gras)
    return f


# ---------------------------------------------------------------- الأوراق

class PostIt(QWidget):
    """ورقة تذكير: لون، ميل خفيف، ظل، دبوس، الموضوع والتاريخ والساعة. فارغة في الرزمة (زائد كبير)."""

    clique = Signal(object)

    def __init__(self, couleur: str, memo: mm.Memo | None = None, angle: float = 0.0, taille: QSize = QSize(176, 150)):
        super().__init__()
        self.couleur, self.memo, self.angle = couleur, memo, angle
        self.setFixedSize(taille)
        self.setCursor(Qt.PointingHandCursor)
        if memo is not None:
            self.setToolTip(f"<div dir='rtl'><b>{memo.sujet}</b><br>{tx.date_ar(date.fromisoformat(memo.date_memo))}"
                            f"{(' · ' + memo.heure) if memo.heure else ''}"
                            f"{('<br>' + memo.details.replace(chr(10), '<br>')) if memo.details else ''}</div>")

    def mouseReleaseEvent(self, ev):   # noqa: N802
        if ev.button() == Qt.LeftButton and self.rect().contains(ev.position().toPoint()):
            self.clique.emit(self.memo if self.memo is not None else self.couleur)
        super().mouseReleaseEvent(ev)

    def paintEvent(self, ev):   # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        w, h = self.width(), self.height()
        p.translate(w / 2, h / 2)
        p.rotate(self.angle)
        r = QRectF(-w / 2 + 12, -h / 2 + 14, w - 24, h - 26)
        # الظل
        for k, a in ((5, 30), (3, 40)):
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 0, 0, a))
            p.drawRoundedRect(r.translated(k * 0.6, k), 3, 3)
        base = QColor(mm.COULEURS.get(self.couleur, mm.COULEURS["jaune"])[0])
        g = QLinearGradient(r.topLeft(), r.bottomRight())
        g.setColorAt(0, base.lighter(112))
        g.setColorAt(1, base.darker(106))
        ch = QPainterPath()
        ch.moveTo(r.topLeft())
        ch.lineTo(r.topRight())
        ch.lineTo(r.right(), r.bottom() - 14)
        ch.quadTo(r.right() - 2, r.bottom() - 2, r.right() - 16, r.bottom())   # الزاوية المرفوعة
        ch.lineTo(r.left(), r.bottom())
        ch.closeSubpath()
        p.setPen(Qt.NoPen)
        p.fillPath(ch, g)
        # شريط أعلى أغمق قليلاً
        p.fillRect(QRectF(r.left(), r.top(), r.width(), 16), QColor(base.darker(112)))
        if self.memo is None:
            p.setPen(QPen(QColor(0, 0, 0, 120), 3.2, Qt.SolidLine, Qt.RoundCap))
            c = r.center() + QPointF(0, 6)
            p.drawLine(c + QPointF(-14, 0), c + QPointF(14, 0))
            p.drawLine(c + QPointF(0, -14), c + QPointF(0, 14))
        else:
            m = self.memo
            zone = r.adjusted(10, 20, -10, -10)
            p.setPen(QColor("#2B2B2B"))
            p.setFont(_police(10.5, True))
            p.drawText(zone.adjusted(0, 0, 0, -30), Qt.AlignRight | Qt.AlignTop | Qt.TextWordWrap, m.resume)
            p.setFont(_police(9))
            p.setPen(QColor("#4E342E"))
            d = date.fromisoformat(m.date_memo)
            ligne = f"{d.day:02d}/{d.month:02d}/{d.year}" + (f"  ·  {m.heure}" if m.heure else "")
            p.drawText(zone, Qt.AlignLeft | Qt.AlignBottom, ligne)
            ech = mm.echeance(m)
            coul = "#C62828" if ech.startswith(("اليوم", "متأخر", "أمس")) else "#5D4037"
            p.setPen(QColor(coul))
            p.setFont(_police(8.5, True))
            p.drawText(zone, Qt.AlignRight | Qt.AlignBottom, ech)
        # الدبوس
        cp = QPointF(r.center().x(), r.top() + 2)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 60))
        p.drawEllipse(cp + QPointF(2, 3), 7, 7)
        rg = QRadialGradient(cp + QPointF(-2, -2), 9)
        epingle = {"jaune": "#D32F2F", "rose": "#1565C0", "vert": "#6A1B9A", "bleu": "#E65100",
                   "orange": "#2E7D32", "violet": "#C62828"}.get(self.couleur, "#D32F2F")
        rg.setColorAt(0, QColor("#FFFFFF"))
        rg.setColorAt(0.25, QColor(epingle).lighter(130))
        rg.setColorAt(1, QColor(epingle).darker(140))
        p.setBrush(rg)
        p.drawEllipse(cp, 7.5, 7.5)
        p.end()


class Sabboura(QWidget):
    """السبورة: إطار خشبي وفلين، والأوراق فوقها في شبكة."""

    def __init__(self):
        super().__init__()
        self.setMinimumSize(560, 560)
        self.grille = QGridLayout(self)
        self.grille.setContentsMargins(42, 42, 42, 42)
        self.grille.setSpacing(4)
        self.grille.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.vide = QLabel("السبورة فارغة: اضغط على بطاقة من البطاقات الملونة لكتابة تذكير.")
        self.vide.setAlignment(Qt.AlignCenter)
        self.vide.setWordWrap(True)
        self.vide.setStyleSheet("color: #5D4037; font-size: 13pt; font-weight: 700; background: rgba(255,255,255,0.55);"
                                " border-radius: 14px; padding: 18px;")

    def paintEvent(self, ev):   # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        # الإطار الخشبي
        g = QLinearGradient(r.topLeft(), r.bottomRight())
        g.setColorAt(0, QColor("#A0703C"))
        g.setColorAt(0.5, QColor("#7B4F25"))
        g.setColorAt(1, QColor("#5C3A1A"))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 50))
        p.drawRoundedRect(r.translated(3, 5), 14, 14)
        p.setBrush(g)
        p.drawRoundedRect(r, 14, 14)
        p.setPen(QPen(QColor(255, 255, 255, 40), 1))
        for k in range(6, 26, 5):   # عروق الخشب
            p.drawLine(QPointF(r.left() + 20, r.top() + k), QPointF(r.right() - 20, r.top() + k + 1))
            p.drawLine(QPointF(r.left() + 20, r.bottom() - k), QPointF(r.right() - 20, r.bottom() - k - 1))
        # الفلين
        c = r.adjusted(26, 26, -26, -26)
        p.setPen(QPen(QColor("#3E2510"), 2))
        cg = QRadialGradient(c.center(), max(c.width(), c.height()) * 0.75)
        cg.setColorAt(0, QColor("#D9A86C"))
        cg.setColorAt(1, QColor("#B57C42"))
        p.setBrush(cg)
        p.drawRect(c)
        # حبيبات الفلين (ثابتة لكل حجم)
        p.setPen(Qt.NoPen)
        n = int(c.width() * c.height() / 260)
        for i in range(n):
            x = c.left() + ((i * 7919) % 10007) / 10007 * c.width()
            y = c.top() + ((i * 104729) % 9973) / 9973 * c.height()
            a = 40 + (i * 31) % 70
            p.setBrush(QColor(110, 66, 28, a) if i % 3 else QColor(245, 214, 170, a))
            s = 1.2 + (i % 4) * 0.6
            p.drawEllipse(QPointF(x, y), s, s * 0.8)
        p.end()


# ---------------------------------------------------------------- الساعة واليومية

class Horloge(QWidget):
    """ساعة حائط بعقارب حقيقية، إطار ذهبي، وتتحدث كل ثانية."""

    def __init__(self):
        super().__init__()
        self.setFixedSize(230, 230)
        self.minuteur = QTimer(self)
        self.minuteur.timeout.connect(self.update)
        self.minuteur.start(1000)

    def paintEvent(self, ev):   # noqa: N802
        n = datetime.now()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = QPointF(self.width() / 2, self.height() / 2)
        R = min(self.width(), self.height()) / 2 - 6
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 45))
        p.drawEllipse(c + QPointF(2, 4), R, R)
        g = QLinearGradient(c - QPointF(R, R), c + QPointF(R, R))
        g.setColorAt(0, QColor("#F7E3A1"))
        g.setColorAt(0.5, QColor("#C9A04A"))
        g.setColorAt(1, QColor("#8C6A1F"))
        p.setBrush(g)
        p.drawEllipse(c, R, R)
        fg = QRadialGradient(c - QPointF(R * 0.3, R * 0.3), R * 1.2)
        fg.setColorAt(0, QColor("#1F3B57"))
        fg.setColorAt(1, QColor("#0B1C2C"))
        p.setBrush(fg)
        p.drawEllipse(c, R - 10, R - 10)
        for i in range(60):
            t = math.radians(i * 6)
            r1 = R - 16
            r2 = r1 - (12 if i % 5 == 0 else 5)
            p.setPen(QPen(QColor("#F3D27A" if i % 5 == 0 else "#7FA2C2"), 3 if i % 5 == 0 else 1.2, Qt.SolidLine,
                          Qt.RoundCap))
            p.drawLine(c + QPointF(r1 * math.sin(t), -r1 * math.cos(t)), c + QPointF(r2 * math.sin(t), -r2 * math.cos(t)))
        p.setFont(_police(11, True))
        p.setPen(QColor("#F3D27A"))
        for k in range(1, 13):
            t = math.radians(k * 30)
            q = c + QPointF((R - 44) * math.sin(t), -(R - 44) * math.cos(t))
            p.drawText(QRectF(q.x() - 14, q.y() - 10, 28, 20), Qt.AlignCenter, str(k))

        def aiguille(angle, longueur, larg, coul):
            t = math.radians(angle)
            p.setPen(QPen(QColor(coul), larg, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(c - QPointF(12 * math.sin(t), -12 * math.cos(t)),
                       c + QPointF(longueur * math.sin(t), -longueur * math.cos(t)))
        aiguille((n.hour % 12 + n.minute / 60) * 30, R * 0.45, 6, "#FFFFFF")
        aiguille((n.minute + n.second / 60) * 6, R * 0.66, 4, "#E8EEF5")
        aiguille(n.second * 6, R * 0.72, 1.8, "#FF7043")
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#F3D27A"))
        p.drawEllipse(c, 6, 6)
        p.end()


class Agenda(QWidget):
    """يومية شهرية مرسومة: الأيام ذات الأحداث بلون لافت، اليوم الحالي بإطار ذهبي، والتفاصيل عند الوقوف."""

    jour_clique = Signal(str)

    def __init__(self):
        super().__init__()
        self.mois = date.today().replace(day=1)
        self.evenements: dict[str, list[tuple[str, str]]] = {}
        self.setMinimumSize(300, 330)
        self.setMouseTracking(True)
        self.source = None

    def definir_source(self, fn) -> None:
        self.source = fn
        self.recharger()

    def recharger(self) -> None:
        debut = self.mois - timedelta(days=7)
        fin = (self.mois + timedelta(days=45))
        self.evenements = self.source(debut, fin) if self.source else {}
        self.update()

    def changer_mois(self, d: int) -> None:
        m = self.mois.month - 1 + d
        self.mois = date(self.mois.year + m // 12, m % 12 + 1, 1)
        self.recharger()

    def _geometrie(self):
        w = self.width()
        haut = 64
        cw = (w - 16) / 7
        ch = (self.height() - haut - 30) / 6
        return haut, cw, ch

    def _cases(self):
        """[(date, QRectF)] للأيام الظاهرة، الأسبوع يبدأ الإثنين، والأعمدة من اليمين (RTL)."""
        haut, cw, ch = self._geometrie()
        premier = self.mois - timedelta(days=self.mois.weekday())
        res = []
        for i in range(42):
            d = premier + timedelta(days=i)
            col, lig = i % 7, i // 7
            x = self.width() - 8 - (col + 1) * cw
            res.append((d, QRectF(x, haut + 30 + lig * ch, cw, ch)))
        return res

    def jour_a(self, pos: QPointF) -> date | None:
        return next((d for d, r in self._cases() if r.contains(pos)), None)

    def event(self, e):
        if e.type() == QEvent.Type.ToolTip:
            d = self.jour_a(QPointF(e.pos()))
            evs = self.evenements.get(d.isoformat(), []) if d else []
            if evs:
                lignes = "".join(f"<li><span style='color:{COUL_EV[t]}'>●</span> {x}</li>" for t, x in evs)
                QToolTip.showText(e.globalPos(), f"<div dir='rtl'><b>{tx.date_ar(d)}</b><ul style='margin:4px 0'>"
                                                 f"{lignes}</ul></div>", self)
            else:
                QToolTip.hideText()
                e.ignore()
            return True
        return super().event(e)

    def mouseReleaseEvent(self, ev):   # noqa: N802
        haut, cw, ch = self._geometrie()
        pos = ev.position()
        if pos.y() < haut:
            if pos.x() < 50:
                self.changer_mois(1)    # السهم الأيسر: الشهر الموالي (RTL)
            elif pos.x() > self.width() - 50:
                self.changer_mois(-1)
            return
        d = self.jour_a(pos)
        if d:
            self.jour_clique.emit(d.isoformat())

    def paintEvent(self, ev):   # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 35))
        p.drawRoundedRect(r.translated(2, 4), 18, 18)
        p.setBrush(QColor("#FFFFFF"))
        p.drawRoundedRect(r, 18, 18)
        haut, cw, ch = self._geometrie()
        g = QLinearGradient(r.topRight(), QPointF(r.left(), r.top() + haut))
        g.setColorAt(0, QColor("#1F3B57"))
        g.setColorAt(1, QColor("#3949AB"))
        tete = QPainterPath()
        tete.addRoundedRect(QRectF(r.left(), r.top(), r.width(), haut + 18), 18, 18)
        bas = QPainterPath()
        bas.addRect(QRectF(r.left(), r.top() + haut, r.width(), 18))
        p.fillPath(tete.subtracted(bas), g)
        p.setPen(QColor("#F3D27A"))
        p.setFont(_police(14, True))
        p.drawText(QRectF(r.left(), r.top(), r.width(), haut), Qt.AlignCenter,
                   f"{tx.MOIS_AR[self.mois.month - 1]} {self.mois.year}")
        p.setFont(_police(16, True))
        p.setPen(QColor("#FFFFFF"))
        p.drawText(QRectF(r.left() + 10, r.top(), 34, haut), Qt.AlignCenter, "‹")
        p.drawText(QRectF(r.right() - 44, r.top(), 34, haut), Qt.AlignCenter, "›")
        p.setFont(_police(8.5, True))
        p.setPen(QColor("#5C6B7A"))
        for col, j in enumerate(JOURS):
            x = self.width() - 8 - (col + 1) * cw
            p.drawText(QRectF(x, haut + 4, cw, 24), Qt.AlignCenter, j[:3] if len(j) > 4 else j)
        auj = date.today()
        for d, c in self._cases():
            evs = self.evenements.get(d.isoformat(), [])
            dans = d.month == self.mois.month
            cc = c.adjusted(3, 3, -3, -3)
            if evs and dans:
                types = [t for t, _ in evs]
                t = "memo" if "memo" in types else "ministere" if "ministere" in types else "local"
                gg = QLinearGradient(cc.topLeft(), cc.bottomRight())
                gg.setColorAt(0, QColor(COUL_EV[t]).lighter(115))
                gg.setColorAt(1, QColor(COUL_EV[t]).darker(110))
                p.setPen(Qt.NoPen)
                p.setBrush(gg)
                p.drawRoundedRect(cc, 9, 9)
                # نقاط الأنواع الأخرى
                autres = [x for x in dict.fromkeys(types) if x != t]
                for k, x in enumerate(autres):
                    p.setBrush(QColor("#FFFFFF"))
                    p.drawEllipse(QPointF(cc.left() + 7 + k * 8, cc.bottom() - 6), 3, 3)
                    p.setBrush(QColor(COUL_EV[x]))
                    p.drawEllipse(QPointF(cc.left() + 7 + k * 8, cc.bottom() - 6), 2, 2)
                p.setPen(QColor("#FFFFFF"))
            else:
                p.setPen(QColor("#263238" if dans else "#B0BEC5"))
            if d == auj:
                p.setBrush(Qt.NoBrush)
                pen = QPen(QColor("#C9A04A"), 2.6)
                p.setPen(pen)
                p.drawRoundedRect(cc, 9, 9)
                p.setPen(QColor("#FFFFFF") if evs and dans else QColor("#8C6A1F"))
            p.setFont(_police(10.5, d == auj or bool(evs)))
            p.drawText(cc, Qt.AlignCenter, str(d.day))
        # المفتاح
        p.setFont(_police(8))
        x = r.right() - 10
        for t in ("memo", "ministere", "local"):
            lib = LIB_EV[t]
            larg = p.fontMetrics().horizontalAdvance(lib) + 22
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(COUL_EV[t]))
            p.drawEllipse(QPointF(x - 6, r.bottom() - 13), 5, 5)
            p.setPen(QColor("#455A64"))
            p.drawText(QRectF(x - larg, r.bottom() - 22, larg - 14, 18), Qt.AlignRight | Qt.AlignVCenter, lib)
            x -= larg + 6
        p.end()


# ---------------------------------------------------------------- الصفحة

class PageMemo(QWidget):
    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        self.mid: int | None = None
        racine = QVBoxLayout(self)
        racine.setContentsMargins(32, 28, 32, 28)
        racine.setSpacing(14)
        racine.addWidget(entete("مفكرة المدير", ""))
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.hide()
        racine.addWidget(self.message)
        corps = QHBoxLayout()
        corps.setSpacing(18)
        # يمين: رزمة البطاقات
        droite = QVBoxLayout()
        droite.setSpacing(2)
        t = QLabel("تذكير جديد")
        t.setAlignment(Qt.AlignCenter)
        t.setStyleSheet("font-size: 13pt; font-weight: 800; color: #5D4037;")
        droite.addWidget(t)
        self.paquet: dict[str, PostIt] = {}
        for i, k in enumerate(mm.COULEURS):
            pi = PostIt(k, None, (-4, 3, -2, 4, -3, 2)[i], QSize(150, 112))
            pi.setToolTip(f"تذكير بلون {mm.COULEURS[k][1]}")
            pi.clique.connect(lambda c: self.nouveau(c))
            self.paquet[k] = pi
            droite.addWidget(pi, 0, Qt.AlignHCenter)
        droite.addStretch()
        corps.addLayout(droite)
        # الوسط: السبورة
        self.sabboura = Sabboura()
        corps.addWidget(self.sabboura, 1)
        # يسار: الساعة واليومية
        gauche = QVBoxLayout()
        gauche.setSpacing(10)
        self.horloge = Horloge()
        gauche.addWidget(self.horloge, 0, Qt.AlignHCenter)
        self.l_date = QLabel()
        self.l_date.setAlignment(Qt.AlignCenter)
        self.l_date.setStyleSheet("font-size: 13pt; font-weight: 800; color: #1F3B57;")
        gauche.addWidget(self.l_date)
        self.l_heure = QLabel()
        self.l_heure.setAlignment(Qt.AlignCenter)
        self.l_heure.setStyleSheet("font-size: 20pt; font-weight: 800; color: #8C6A1F; letter-spacing: 2px;")
        gauche.addWidget(self.l_heure)
        self.agenda = Agenda()
        self.agenda.setFixedWidth(330)
        self.agenda.jour_clique.connect(lambda d: self.nouveau("jaune", d))
        gauche.addWidget(self.agenda)
        gauche.addStretch()
        corps.addLayout(gauche)
        racine.addLayout(corps, 1)
        self.minuteur = QTimer(self)
        self.minuteur.timeout.connect(self._tic)
        self.minuteur.start(1000)
        self._tic()
        self._construire_fiche()
        self.agenda.definir_source(lambda a, b: mm.evenements(self.f.conn, a, b))

    def _tic(self) -> None:
        n = datetime.now()
        self.l_heure.setText(f"⁦{n:%H:%M:%S}⁩")
        self.l_date.setText(tx.date_ar(n.date()))

    def _construire_fiche(self) -> None:
        w = QWidget()
        fl = QFormLayout(w)
        fl.setSpacing(10)
        self.c_sujet = champ("موضوع التذكير")
        self.c_date = ChampDate()
        self.c_heure = champ("09:00", ltr=True)
        self.c_heure.setMaximumWidth(120)
        self.c_couleur = QComboBox()
        for k, (_, lib) in mm.COULEURS.items():
            self.c_couleur.addItem(lib, k)
        self.c_details = QPlainTextEdit()
        self.c_details.setPlaceholderText("تفاصيل اختيارية")
        self.c_details.setMinimumHeight(90)
        for lib, wdg in (("الموضوع", self.c_sujet), ("التاريخ", self.c_date), ("الساعة", self.c_heure),
                         ("اللون", self.c_couleur), ("التفاصيل", self.c_details)):
            fl.addRow(lib, wdg)
        h = QHBoxLayout()
        self.b_coller = bouton_couleur("حفظ ولصق على السبورة", "#EF6C00", "enregistrer")
        self.b_coller.clicked.connect(lambda: self.enregistrer())
        self.b_fait = bouton_couleur("تم", "#2E7D32", "valider")
        self.b_fait.clicked.connect(lambda: self.marquer_fait())
        self.b_suppr = QPushButton("حذف")
        self.b_suppr.setObjectName("danger")
        self.b_suppr.clicked.connect(lambda: self.supprimer())
        for b in (self.b_coller, self.b_fait, self.b_suppr):
            h.addWidget(b)
        h.addStretch()
        fl.addRow(h)
        self.message_fiche = QLabel()
        self.message_fiche.setWordWrap(True)
        self.message_fiche.hide()
        fl.addRow(self.message_fiche)
        self.fiche = FenetreFiche(self, "تذكير", "", w, largeur=620)

    def rafraichir(self) -> None:
        g = self.sabboura.grille
        while g.count():
            it = g.takeAt(0)
            if it.widget() is not None and it.widget() is not self.sabboura.vide:
                it.widget().deleteLater()
        self.memos = mm.lister(self.f.conn)
        self.notes: list[PostIt] = []
        cols = self._cols = self._colonnes()
        angles = (-3.5, 2.5, -1.5, 3.5, -2.5, 1.5, -4, 2)
        for i, m in enumerate(self.memos):
            pi = PostIt(m.couleur, m, angles[(m.id or i) % len(angles)])
            pi.clique.connect(lambda x: self.ouvrir(x.id))
            g.addWidget(pi, i // cols, i % cols)
            self.notes.append(pi)
        if not self.memos:
            g.addWidget(self.sabboura.vide, 0, 0)
        if self.sabboura.vide.parent() is None:
            self.sabboura.vide.setParent(self.sabboura)
        self.sabboura.vide.setVisible(not self.memos)
        self.agenda.recharger()

    def _colonnes(self) -> int:
        return max(2, (self.sabboura.width() - 84) // 182) if self.sabboura.width() > 300 else 3

    def resizeEvent(self, ev):   # noqa: N802
        super().resizeEvent(ev)
        if getattr(self, "memos", None) and self._colonnes() != getattr(self, "_cols", None):
            QTimer.singleShot(0, self.rafraichir)

    def nouveau(self, couleur: str = "jaune", jour: str | None = None) -> FenetreFiche:
        self.mid = None
        self.c_sujet.clear()
        self.c_details.clear()
        self.c_heure.clear()
        self.c_date.definir(jour or date.today().isoformat())
        self.c_couleur.setCurrentIndex(max(0, self.c_couleur.findData(couleur)))
        self.b_fait.hide()
        self.b_suppr.hide()
        self.message_fiche.hide()
        self.fiche.definir_titre("تذكير جديد")
        self.fiche.ouvrir()
        self.c_sujet.setFocus()
        return self.fiche

    def ouvrir(self, mid: int) -> FenetreFiche:
        m = mm.lire(self.f.conn, mid)
        self.mid = mid
        self.c_sujet.setText(m.sujet)
        self.c_details.setPlainText(m.details)
        self.c_heure.setText(m.heure)
        self.c_date.definir(m.date_memo)
        self.c_couleur.setCurrentIndex(max(0, self.c_couleur.findData(m.couleur)))
        self.b_fait.show()
        self.b_suppr.show()
        self.message_fiche.hide()
        self.fiche.definir_titre(f"تذكير: {m.resume}")
        self.fiche.ouvrir()
        return self.fiche

    def enregistrer(self) -> int | None:
        try:
            d = self.c_date.iso()
            mid = mm.enregistrer(self.f.conn, mm.Memo(self.c_sujet.text(), d, self.c_heure.text(),
                                                      self.c_details.toPlainText(), self.c_couleur.currentData(),
                                                      False, self.mid))
        except (mm.ErreurMemo, ValueError) as e:
            message(self.message_fiche, str(e) or "تاريخ غير صحيح.", True)
            return None
        self.fiche.hide()
        message(self.message, "أُلصق التذكير على السبورة.")
        self.rafraichir()
        return mid

    def marquer_fait(self) -> None:
        if self.mid:
            mm.marquer_fait(self.f.conn, self.mid)
            self.fiche.hide()
            message(self.message, "أُزيل التذكير من السبورة (تم).")
            self.rafraichir()

    def supprimer(self) -> None:
        if self.mid:
            mm.supprimer(self.f.conn, self.mid)
            self.fiche.hide()
            message(self.message, "حُذف التذكير.")
            self.rafraichir()
