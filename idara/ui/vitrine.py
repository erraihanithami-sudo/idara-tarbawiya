"""مكونات الصفحات «المعلومات أولاً» (طلب المدير 2026-11-17 و2026-11-18): الصفحة تعرض المعطيات والإحصائيات،
والإدخال والتعديل في نوافذ منبثقة.

- CarteFiltre: بطاقة رقم بلون وأيقونة، تعمل معياراً للجدول عند الضغط عليها.
- FenetreFiche: نافذة منبثقة تحتضن استمارة موجودة (ملف موظف، ملف رخصة...) داخل منطقة تمرير، دون إعادة كتابتها.
- grille_cartes: صف أو صفان من البطاقات.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout,
                               QWidget)

from idara.ui import pictos, theme


class CarteFiltre(QFrame):
    """بطاقة رقم تعمل معياراً: أيقونة في دائرة، العدد، الفئة، وسطر تعريفي. الضغط عليها يعرض فئتها."""

    clique = Signal(str)

    def __init__(self, cle: str, libelle: str, couleur: str, picto: str, note: str = "", compacte: bool = False):
        super().__init__()
        self.cle, self.couleur = cle, couleur
        self.setObjectName("carteFiltre")
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(70 if compacte else 96)
        h = QHBoxLayout(self)
        h.setContentsMargins(14, 8 if compacte else 12, 12, 8 if compacte else 12)
        h.setSpacing(10 if compacte else 12)
        t = 36 if compacte else 48
        ic = QLabel()
        ic.setPixmap(pictos.pastille(picto, couleur, t))
        ic.setFixedSize(t, t)
        ic.setStyleSheet("background: transparent;")
        h.addWidget(ic, 0, Qt.AlignVCenter)
        v = QVBoxLayout()
        v.setSpacing(0)
        self.chiffre = QLabel("0")
        self.chiffre.setStyleSheet(f"font-size: {16 if compacte else 22}pt; font-weight: 700; color: {couleur}; "
                                   "background: transparent;")
        self.libelle = QLabel(libelle)
        self.libelle.setWordWrap(True)
        self.libelle.setStyleSheet("font-weight: 700; background: transparent;")
        v.addWidget(self.chiffre)
        v.addWidget(self.libelle)
        if note:
            n = QLabel(note)
            n.setObjectName("etiquette")
            n.setStyleSheet("background: transparent;")
            n.setWordWrap(True)
            v.addWidget(n)
        h.addLayout(v, 1)
        self.triangle = QLabel()
        self.triangle.setPixmap(pixmap_triangle(20))
        self.triangle.setStyleSheet("background: transparent;")
        self.triangle.hide()
        h.addWidget(self.triangle, 0, Qt.AlignTop)
        self.definir_actif(False)

    def definir_alerte(self, texte: str) -> None:
        """مثلث برتقالي في زاوية البطاقة، ونص المشكل عند مرور الفأرة."""
        self.triangle.setVisible(bool(texte))
        self.triangle.setToolTip(info_bulle(texte) if texte else "")

    def definir(self, n) -> None:
        self.chiffre.setText(str(n))

    def definir_actif(self, actif: bool) -> None:
        self.actif = actif
        c = QColor(self.couleur)
        teinte = f"rgba({c.red()}, {c.green()}, {c.blue()}, {30 if actif else 0})"
        bord = f"2px solid {self.couleur}" if actif else f"1px solid {theme.LIGNE}"
        self.setStyleSheet(f"QFrame#carteFiltre {{ background: qlineargradient(x1:1, y1:0, x2:0, y2:1, "
                           f"stop:0 {teinte}, stop:1 {theme.BLANC}); border: {bord}; border-radius: 16px; "
                           f"border-right: 6px solid {self.couleur}; }}")

    def mouseReleaseEvent(self, ev):   # noqa: N802
        if ev.button() == Qt.LeftButton:
            self.clique.emit(self.cle)
        super().mouseReleaseEvent(ev)


def grille_cartes(cartes: list[QWidget], colonnes: int = 3) -> QGridLayout:
    g = QGridLayout()
    g.setSpacing(14)
    for i, c in enumerate(cartes):
        g.addWidget(c, i // colonnes, i % colonnes)
    return g


class FenetreFiche(QDialog):
    """نافذة منبثقة لاستمارة: رأس ملون، ثم الاستمارة داخل منطقة تمرير. الاستمارة تبقى ملكاً للصفحة (حقولها
    وأزرارها ودوالها كما هي)، والنافذة إطار لها فقط."""

    def __init__(self, parent: QWidget, titre: str, sous: str, contenu: QWidget, largeur: int = 940):
        super().__init__(parent)
        from idara.ui.composants import entete
        self.setWindowTitle(titre)
        self.setLayoutDirection(Qt.RightToLeft)
        self.setModal(True)
        self.setProperty("cederDocument", True)
        v = QVBoxLayout(self)
        v.setContentsMargins(18, 16, 18, 16)
        v.setSpacing(10)
        self.entete = entete(titre, sous)
        v.addWidget(self.entete)
        zone = QScrollArea()
        zone.setWidgetResizable(True)
        zone.setFrameShape(QFrame.NoFrame)
        zone.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        zone.setWidget(contenu)
        v.addWidget(zone, 1)
        self.resize(largeur, 780)

    def definir_titre(self, titre: str, sous: str | None = None) -> None:
        self.setWindowTitle(titre)
        self.entete.titre.setText(titre)
        if sous is not None:
            self.entete.sous.setText(sous)
            self.entete.sous.setVisible(bool(sous))

    def ouvrir(self) -> None:
        ecran = self.screen().availableGeometry() if self.screen() else None
        if ecran is not None:
            self.resize(min(self.width(), ecran.width() - 60), min(self.height(), ecran.height() - 60))
        self.show()
        self.raise_()
        self.activateWindow()


def bouton_couleur(texte: str, couleur: str, picto: str | None = None, aide: str = ""):
    """زر وثيقة بلون مميز وأيقونة بيضاء (أزرار توليد الوثائق)."""
    from PySide6.QtCore import QSize
    from PySide6.QtWidgets import QPushButton
    b = QPushButton(texte)
    b.setObjectName("boutonCouleur")
    b.setCursor(Qt.PointingHandCursor)
    b.setMinimumHeight(46)
    c = QColor(couleur)
    fonce = c.darker(125).name()
    b.setStyleSheet(
        f"QPushButton#boutonCouleur {{ background: qlineargradient(x1:1, y1:0, x2:0, y2:1, stop:0 {couleur}, "
        f"stop:1 {fonce}); color: white; border: none; border-radius: 12px; padding: 8px 16px; font-weight: 700; }}"
        f"QPushButton#boutonCouleur:hover {{ background: {fonce}; }}"
        f"QPushButton#boutonCouleur:disabled {{ background: #CFCFCF; color: #F5F5F5; }}")
    if picto:
        b.setIcon(pictos.icone(picto, "#FFFFFF", 20))
        b.setIconSize(QSize(20, 20))
        b.setProperty("picto", picto)
    if aide:
        b.setToolTip(aide)
    return b


class CarteDocument(QFrame):
    """بطاقة وثيقة في معرض الوثائق: شريط ملون، أيقونة كبيرة، العنوان، وصف قصير، وعدد ما وُلّد منها.
    الضغط عليها يفتح نافذة توليدها."""

    clique = Signal(str)

    def __init__(self, cle: str, titre: str, description: str, couleur: str, picto: str):
        super().__init__()
        self.cle, self.couleur = cle, couleur
        self.setObjectName("carteDocument")
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(150)
        c = QColor(couleur)
        self.setStyleSheet(
            f"QFrame#carteDocument {{ background: qlineargradient(x1:1, y1:0, x2:0, y2:1, stop:0 "
            f"rgba({c.red()},{c.green()},{c.blue()},38), stop:0.55 {theme.BLANC}, stop:1 {theme.BLANC}); "
            f"border: 1px solid {theme.LIGNE}; border-top: 5px solid {couleur}; border-radius: 18px; }}"
            f"QFrame#carteDocument:hover {{ border: 2px solid {couleur}; border-top: 5px solid {couleur}; }}")
        v = QVBoxLayout(self)
        v.setContentsMargins(18, 14, 18, 14)
        v.setSpacing(6)
        h = QHBoxLayout()
        ic = QLabel()
        ic.setPixmap(pictos.pastille(picto, couleur, 54))
        ic.setFixedSize(54, 54)
        ic.setStyleSheet("background: transparent;")
        h.addWidget(ic)
        h.addStretch()
        self.compteur = QLabel()
        self.compteur.setStyleSheet(f"background: {couleur}; color: white; border-radius: 10px; padding: 2px 10px; "
                                    "font-weight: 700;")
        self.compteur.hide()
        h.addWidget(self.compteur, 0, Qt.AlignTop)
        v.addLayout(h)
        t = QLabel(titre)
        t.setWordWrap(True)
        t.setStyleSheet(f"font-size: 13pt; font-weight: 700; color: {c.darker(130).name()}; background: transparent;")
        v.addWidget(t)
        d = QLabel(description)
        d.setObjectName("etiquette")
        d.setWordWrap(True)
        d.setStyleSheet("background: transparent;")
        v.addWidget(d)
        v.addStretch()
        self.titre = titre

    def definir_compte(self, n: int | None) -> None:
        self.compteur.setVisible(bool(n))
        if n:
            self.compteur.setText(f"وُلّدت {n}")

    def mouseReleaseEvent(self, ev):   # noqa: N802
        if ev.button() == Qt.LeftButton:
            self.clique.emit(self.cle)
        super().mouseReleaseEvent(ev)


# ======================================================================
# مثلث التنبيه البرتقالي (طلب المدير 2026-11-19): بدل فقرات التحذير، مثلث صغير قرب المكون المعني، والمشكل
# يظهر في نافذة صغيرة عند مرور الفأرة.
# ======================================================================

ORANGE = "#EF8A00"


def pixmap_triangle(taille: int = 22, couleur: str = ORANGE):
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QPainter, QPainterPath, QPen, QPixmap
    n = taille * 3
    pm = QPixmap(n, n)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    ch = QPainterPath()
    ch.moveTo(n / 2, n * 0.08)
    ch.lineTo(n * 0.96, n * 0.9)
    ch.lineTo(n * 0.04, n * 0.9)
    ch.closeSubpath()
    p.fillPath(ch, QColor(couleur))
    p.setPen(QPen(QColor(couleur).darker(130), n * 0.03))
    p.drawPath(ch)
    p.setPen(QPen(QColor("white"), n * 0.09, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(QPointF(n / 2, n * 0.36), QPointF(n / 2, n * 0.6))
    p.drawPoint(QPointF(n / 2, n * 0.75))
    p.end()
    pm.setDevicePixelRatio(3)
    return pm


def icone_triangle(taille: int = 16):
    from PySide6.QtGui import QIcon
    return QIcon(pixmap_triangle(taille))


def info_bulle(texte: str) -> str:
    """نص النافذة الصغيرة: عنوان وقائمة، بخط مقروء."""
    lignes = [l for l in (texte or "").splitlines() if l.strip()]
    corps = "".join(f"<li style='margin-bottom:4px'>{l}</li>" for l in lignes)
    return (f"<div dir='rtl' style='font-size:11pt'><b style='color:{ORANGE}'>تنبيه</b>"
            f"<ul style='margin:4px 0 0 0'>{corps}</ul></div>")


class AlerteTriangle(QWidget):
    """يحل محل فقرة التحذير: مثلث برتقالي (وعدد التنبيهات)، والنص كاملاً في النافذة الصغيرة عند مرور الفأرة.
    يحتفظ بواجهة QLabel التي تستعملها الصفحات (setText، text، setWordWrap)."""

    def __init__(self, libelle: str = ""):
        super().__init__()
        self._texte = ""
        self.setObjectName("alerteTriangle")
        self.setCursor(Qt.WhatsThisCursor)
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)
        self.icone = QLabel()
        self.icone.setPixmap(pixmap_triangle(24))
        self.icone.setFixedSize(26, 26)
        h.addWidget(self.icone)
        self.compte = QLabel()
        self.compte.setStyleSheet(f"color: {ORANGE}; font-weight: 700;")
        h.addWidget(self.compte)
        self.libelle = libelle
        h.addStretch()
        self.hide()

    def setText(self, texte: str) -> None:   # noqa: N802
        self._texte = texte or ""
        n = len([l for l in self._texte.splitlines() if l.strip()])
        self.compte.setText(f"{self.libelle} ({n})" if self.libelle and n else "")
        self.setToolTip(info_bulle(self._texte) if self._texte else "")
        self.icone.setToolTip(self.toolTip())
        self.setVisible(bool(self._texte))

    def text(self) -> str:
        return self._texte

    def setWordWrap(self, _v) -> None:   # noqa: N802
        pass

    def clear(self) -> None:
        self.setText("")
