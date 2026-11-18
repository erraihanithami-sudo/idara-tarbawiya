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
        self.definir_actif(False)

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
