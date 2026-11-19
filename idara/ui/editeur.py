"""محرر الوثائق داخل البرنامج (طلب المدير 2026-11-15)، مدمج في النافذة منذ 2026-11-16.

بلاغ المدير 2026-11-19: المعاينة صغيرة، والفتح ببرنامج الحاسوب يُغلق البرنامج، والمحرر ضعيف. لذلك:
- المعاينة صفحات بيضاء حقيقية على خلفية رمادية (كما في معاينة Word)، بعرض الشاشة آلياً، مع تكبير وتصغير
  و«ملء العرض» و«الصفحة كاملة» وعدد الصفحات. ما يُرى هو ما يُطبع (نفس تقطيع الصفحات).
- «تعديل الوثيقة» يفتح المحرر بشريط أدوات كامل: نوع الخط وحجمه، غامق ومائل وتسطير وشطب، لون النص ولون الإبراز،
  المحاذاة الأربع، القوائم المنقطة والمرقمة، الإزاحة، تباعد الأسطر، جدول، صورة، فاصل صفحات، خط أفقي، التاريخ،
  البحث والاستبدال، مسح التنسيق، التراجع والإعادة.
- الفتح ببرنامج الحاسوب عبر Qt (QDesktopServices) لا عبر os.startfile، ولا يمكن لخطئه أن يُسقط البرنامج.

الوثيقة تُحوَّل من Word إلى صفحة يحررها QTextEdit (finition.en_html). التعديلات تُحفظ بجانب الملف الأصلي
(«‎.تعديل.html‎») فيُعاد فتحها كما تُركت؛ الملف الأصلي لا يُمَس.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtCore import QMarginsF, QPointF, QRectF, QSize, QSizeF, Qt, QUrl
from PySide6.QtGui import (QColor, QFont, QImage, QPageLayout, QPageSize, QPainter, QPen, QPixmap, QPolygonF, QTextBlockFormat,
                           QTextCharFormat, QTextCursor, QTextDocument, QTextFormat, QTextImageFormat, QTextLength,
                           QTextFrameFormat, QTextListFormat, QTextTableFormat)
from PySide6.QtPrintSupport import QPrintDialog, QPrinter, QPrintPreviewDialog
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QDialog, QFileDialog, QFontComboBox, QFrame,
                               QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QSizePolicy,
                               QSpinBox, QTextEdit, QToolButton, QVBoxLayout, QWidget)

from idara.services import bureautique, finition
from idara.ui.saisie import message

PX_PAR_MM = 96 / 25.4
MARGE_ECRAN = 44   # هامش الورقة على الشاشة في وضع التحرير (بكسل)
GRIS_FOND = "#7D7F8C"


def fichier_modifie(chemin: Path) -> Path:
    return chemin.with_name(chemin.stem + ".تعديل.html")


# ======================================================================
# أيقونات شريط التحرير (مرسومة، لا صور ولا رموز قد لا يتضمنها الخط)
# ======================================================================

def _icone(dessin, couleur="#33364D", taille=20) -> QPixmap:
    n = taille * 3
    pm = QPixmap(n, n)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(n / 24, n / 24)
    p.setPen(QPen(QColor(couleur), 1.9, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    dessin(p)
    p.end()
    pm.setDevicePixelRatio(3)
    return pm


def _lignes(*specs):
    def d(p):
        for y, x0, x1 in specs:
            p.drawLine(QPointF(x0, y), QPointF(x1, y))
    return d


ICONES = {
    "droite": _lignes((6, 4, 20), (10, 9, 20), (14, 4, 20), (18, 9, 20)),
    "centre": _lignes((6, 4, 20), (10, 7, 17), (14, 4, 20), (18, 7, 17)),
    "gauche": _lignes((6, 4, 20), (10, 4, 15), (14, 4, 20), (18, 4, 15)),
    "justifier": _lignes((6, 4, 20), (10, 4, 20), (14, 4, 20), (18, 4, 20)),
}


def _puces(p):
    for y in (7, 12, 17):
        p.drawLine(QPointF(4, y), QPointF(15, y))
        p.drawEllipse(QPointF(19, y), 1.2, 1.2)


def _numeros(p):
    for y in (7, 12, 17):
        p.drawLine(QPointF(4, y), QPointF(14, y))
    f = QFont()
    f.setPixelSize(6)
    f.setBold(True)
    p.setFont(f)
    for k, y in enumerate((9, 14, 19)):
        p.drawText(QPointF(17, y), str(k + 1))


def _retrait(signe):
    def d(p):
        for y in (6, 18):
            p.drawLine(QPointF(4, y), QPointF(20, y))
        for y in (10, 14):
            p.drawLine(QPointF(4, y), QPointF(13, y))
        if signe > 0:
            p.drawPolyline(QPolygonF([QPointF(16, 9), QPointF(19.5, 12), QPointF(16, 15)]))
        else:
            p.drawPolyline(QPolygonF([QPointF(19.5, 9), QPointF(16, 12), QPointF(19.5, 15)]))
    return d


def _table(p):
    p.drawRect(QRectF(4, 5, 16, 14))
    p.drawLine(QPointF(4, 9.7), QPointF(20, 9.7))
    p.drawLine(QPointF(4, 14.3), QPointF(20, 14.3))
    p.drawLine(QPointF(9.3, 5), QPointF(9.3, 19))
    p.drawLine(QPointF(14.7, 5), QPointF(14.7, 19))


def _image(p):
    p.drawRoundedRect(QRectF(3.5, 5, 17, 14), 2, 2)
    p.drawEllipse(QPointF(9, 10), 1.6, 1.6)
    p.drawPolyline(QPolygonF([QPointF(4, 17.5), QPointF(10, 12.5), QPointF(13.5, 15.5), QPointF(16, 13.5), QPointF(20, 17)]))


def _saut(p):
    p.drawRect(QRectF(6, 3, 12, 6))
    p.drawRect(QRectF(6, 15, 12, 6))
    pen = p.pen()
    pen.setStyle(Qt.DashLine)
    p.setPen(pen)
    p.drawLine(QPointF(3, 12), QPointF(21, 12))


def _trait(p):
    p.drawLine(QPointF(3, 12), QPointF(21, 12))
    p.drawLine(QPointF(5, 7), QPointF(19, 7))
    p.drawLine(QPointF(5, 17), QPointF(19, 17))


def _loupe(p):
    p.drawEllipse(QPointF(10.5, 10.5), 6, 6)
    p.drawLine(QPointF(15, 15), QPointF(20, 20))


def _gomme(p):
    p.drawPolygon(QPolygonF([QPointF(4, 15), QPointF(13, 6), QPointF(20, 13), QPointF(13, 20), QPointF(8, 20)]))
    p.drawLine(QPointF(8.5, 10.5), QPointF(15.5, 17.5))


def _undo(sens):
    def d(p):
        if sens < 0:
            p.drawArc(QRectF(6, 7, 13, 12), 90 * 16, -200 * 16)
            p.drawPolyline(QPolygonF([QPointF(10, 4), QPointF(6.5, 7.5), QPointF(10, 11)]))
        else:
            p.drawArc(QRectF(5, 7, 13, 12), 90 * 16, 200 * 16)
            p.drawPolyline(QPolygonF([QPointF(14, 4), QPointF(17.5, 7.5), QPointF(14, 11)]))
    return d


def _calendrier(p):
    p.drawRoundedRect(QRectF(4, 5.5, 16, 15), 2, 2)
    p.drawLine(QPointF(4, 10), QPointF(20, 10))
    p.drawLine(QPointF(8.5, 3.5), QPointF(8.5, 7))
    p.drawLine(QPointF(15.5, 3.5), QPointF(15.5, 7))


def _presse_papier(p):
    p.drawRoundedRect(QRectF(5, 5, 14, 16), 2, 2)
    p.drawRoundedRect(QRectF(9, 3, 6, 4), 1, 1)
    for y in (11, 14.5, 18):
        p.drawLine(QPointF(8.5, y), QPointF(15.5, y))


def _ciseaux(p):
    p.drawEllipse(QPointF(7, 17), 2.8, 2.8)
    p.drawEllipse(QPointF(17, 17), 2.8, 2.8)
    p.drawLine(QPointF(9, 15), QPointF(17, 4))
    p.drawLine(QPointF(15, 15), QPointF(7, 4))


def _copier(p):
    p.drawRoundedRect(QRectF(8, 8, 11, 13), 1.5, 1.5)
    p.drawPolyline(QPolygonF([QPointF(5, 16), QPointF(5, 3.5), QPointF(15, 3.5)]))


def _pinceau(p):
    p.drawRoundedRect(QRectF(4, 3.5, 14, 6), 1.5, 1.5)
    p.drawPolyline(QPolygonF([QPointF(18, 6.5), QPointF(20.5, 6.5), QPointF(20.5, 12), QPointF(12, 12),
                              QPointF(12, 15)]))
    p.drawRoundedRect(QRectF(10.5, 15, 3, 6), 1, 1)


def _indice(haut: bool):
    def d(p):
        f = QFont()
        f.setPixelSize(13)
        f.setBold(True)
        p.setFont(f)
        p.drawText(QPointF(3, 17), "x")
        f.setPixelSize(8)
        p.setFont(f)
        p.drawText(QPointF(13, 9 if haut else 21), "2")
    return d


def _selection(p):
    pen = p.pen()
    pen.setStyle(Qt.DashLine)
    p.setPen(pen)
    p.drawRect(QRectF(3.5, 4, 17, 16))
    pen.setStyle(Qt.SolidLine)
    p.setPen(pen)
    for y in (9, 12.5, 16):
        p.drawLine(QPointF(7, y), QPointF(17, y))


def _orientation(paysage: bool):
    def d(p):
        r = QRectF(3, 6.5, 18, 12) if paysage else QRectF(6.5, 3, 11, 18)
        p.drawRect(r)
        p.drawLine(QPointF(r.left() + 2.5, r.top() + 4), QPointF(r.right() - 2.5, r.top() + 4))
    return d


def _marges(p):
    p.drawRect(QRectF(5, 3, 14, 18))
    pen = p.pen()
    pen.setStyle(Qt.DotLine)
    p.setPen(pen)
    p.drawRect(QRectF(8, 6, 8, 12))


def _regle(p):
    p.drawRect(QRectF(3, 8, 18, 8))
    for x in (6, 9, 12, 15, 18):
        p.drawLine(QPointF(x, 8), QPointF(x, 11 if x % 2 else 12.5))


def _oeil(p):
    ch = QPolygonF([QPointF(2.5, 12), QPointF(7, 7.5), QPointF(12, 6), QPointF(17, 7.5), QPointF(21.5, 12),
                    QPointF(17, 16.5), QPointF(12, 18), QPointF(7, 16.5)])
    p.drawPolygon(ch)
    p.drawEllipse(QPointF(12, 12), 3, 3)


def _symbole(p):
    f = QFont()
    f.setPixelSize(15)
    p.setFont(f)
    p.drawText(QRectF(2, 2, 20, 20), Qt.AlignCenter, "Ω")


def _direction(rtl: bool):
    def d(p):
        for y in (6, 10, 14):
            p.drawLine(QPointF(9 if rtl else 4, y), QPointF(20 if rtl else 15, y))
        y = 19
        p.drawLine(QPointF(4, y), QPointF(20, y))
        if rtl:
            p.drawPolyline(QPolygonF([QPointF(7, 16.5), QPointF(4, 19), QPointF(7, 21.5)]))
        else:
            p.drawPolyline(QPolygonF([QPointF(17, 16.5), QPointF(20, 19), QPointF(17, 21.5)]))
    return d


def _crayon_titre(p):
    p.drawPolygon(QPolygonF([QPointF(4, 20), QPointF(5, 15), QPointF(16, 4), QPointF(20, 8), QPointF(9, 19)]))
    p.drawLine(QPointF(13.5, 6.5), QPointF(17.5, 10.5))


def _imprimante_ap(p):
    p.drawRect(QRectF(7, 3.5, 10, 5))
    p.drawRoundedRect(QRectF(3.5, 8.5, 17, 8), 1.5, 1.5)
    p.drawRect(QRectF(7, 13.5, 10, 7))
    p.drawEllipse(QPointF(15.5, 17), 2.2, 2.2)


ICONES.update({"coller": _presse_papier, "imprimante_ap": _imprimante_ap, "couper": _ciseaux, "copier": _copier, "pinceau": _pinceau,
               "exposant": _indice(True), "indice": _indice(False), "tout": _selection,
               "portrait": _orientation(False), "paysage": _orientation(True), "marges": _marges,
               "regle": _regle, "oeil": _oeil, "symbole": _symbole, "rtl": _direction(True),
               "ltr": _direction(False)})

ICONES.update({"puces": _puces, "numeros": _numeros, "retrait+": _retrait(1), "retrait-": _retrait(-1),
               "table": _table, "image": _image, "saut": _saut, "trait": _trait, "loupe": _loupe,
               "gomme": _gomme, "annuler": _undo(-1), "refaire": _undo(1), "date": _calendrier})


def _icone_couleur(lettre: str, couleur: str, fond: bool = False) -> QPixmap:
    n = 60
    pm = QPixmap(n, n)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    if fond:
        p.fillRect(QRectF(8, 8, 44, 34), QColor(couleur))
    f = QFont()
    f.setPixelSize(32)
    f.setBold(True)
    p.setFont(f)
    p.setPen(QColor("#33364D"))
    p.drawText(QRectF(0, 4, n, 40), Qt.AlignCenter, lettre)
    p.fillRect(QRectF(8, 46, 44, 9), QColor(couleur))
    p.end()
    pm.setDevicePixelRatio(3)
    return pm


# ======================================================================
# المعاينة: صفحات حقيقية
# ======================================================================

class VuePages(QWidget):
    """يرسم صفحات الوثيقة بيضاء على خلفية رمادية، بالتقطيع نفسه الذي يُطبع به."""

    ECART = 26

    def __init__(self, editeur: "EditeurDocument"):
        super().__init__()
        self.e = editeur
        self.zoom = 1.0
        self.doc: QTextDocument | None = None
        self.n = 1
        self.setAttribute(Qt.WA_OpaquePaintEvent)

    def actualiser(self) -> None:
        e = self.e
        if self.doc is not None:
            self.doc.deleteLater()
        self.doc = e.edit.document().clone(self)
        self.doc.setDocumentMargin(0)
        self.doc.setPageSize(QSizeF(e.largeur_contenu, e.hauteur_contenu))
        self.n = max(1, self.doc.pageCount())
        self._taille()

    def _taille(self) -> None:
        e = self.e
        w = e.page.largeur_mm * PX_PAR_MM * self.zoom
        h = e.page.hauteur_mm * PX_PAR_MM * self.zoom
        self.setFixedSize(int(w + 2 * self.ECART), int(self.n * (h + self.ECART) + self.ECART))
        self.update()

    def definir_zoom(self, z: float) -> None:
        self.zoom = max(0.3, min(3.0, z))
        self._taille()

    def paintEvent(self, ev):   # noqa: N802
        e = self.e
        p = QPainter(self)
        p.fillRect(ev.rect(), QColor(GRIS_FOND))
        if self.doc is None:
            p.end()
            return
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        z = self.zoom
        w, h = e.page.largeur_mm * PX_PAR_MM * z, e.page.hauteur_mm * PX_PAR_MM * z
        g, haut_m, _, _ = (m * PX_PAR_MM for m in e.page.marges_mm)
        for i in range(self.n):
            y = self.ECART + i * (h + self.ECART)
            cadre = QRectF(self.ECART, y, w, h)
            if not cadre.adjusted(-8, -8, 8, 8).intersects(QRectF(ev.rect())):
                continue
            for k, a in ((6, 22), (3, 34)):   # ظل الورقة
                p.fillRect(cadre.translated(k, k), QColor(0, 0, 0, a))
            p.fillRect(cadre, QColor("white"))
            p.save()
            p.translate(cadre.left() + g * z, cadre.top() + haut_m * z)
            p.scale(z, z)
            p.translate(0, -i * e.hauteur_contenu)
            p.setClipRect(QRectF(0, i * e.hauteur_contenu, e.largeur_contenu, e.hauteur_contenu))
            self.doc.drawContents(p, QRectF(0, i * e.hauteur_contenu, e.largeur_contenu, e.hauteur_contenu))
            p.restore()
        p.end()


class ZoneApercu(QScrollArea):
    def __init__(self, vue: VuePages, au_redimensionnement):
        super().__init__()
        self.setWidget(vue)
        self.setWidgetResizable(False)
        self.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.setFrameShape(QFrame.NoFrame)
        self.setStyleSheet(f"QScrollArea {{ background: {GRIS_FOND}; border-radius: 10px; }}")
        self.viewport().setStyleSheet(f"background: {GRIS_FOND};")
        self._rappel = au_redimensionnement

    def resizeEvent(self, ev):   # noqa: N802
        super().resizeEvent(ev)
        self._rappel()


# ======================================================================
# البحث والاستبدال
# ======================================================================

class DialogueRecherche(QDialog):
    def __init__(self, editeur: "EditeurDocument"):
        super().__init__(editeur)
        self.e = editeur
        self.setWindowTitle("بحث واستبدال")
        self.setLayoutDirection(Qt.RightToLeft)
        g = QGridLayout(self)
        self.cherche, self.remplace = QLineEdit(), QLineEdit()
        g.addWidget(QLabel("ابحث عن:"), 0, 0)
        g.addWidget(self.cherche, 0, 1, 1, 3)
        g.addWidget(QLabel("استبدل بـ:"), 1, 0)
        g.addWidget(self.remplace, 1, 1, 1, 3)
        self.casse = QCheckBox("مطابقة الحالة")
        g.addWidget(self.casse, 2, 1)
        self.etat = QLabel()
        g.addWidget(self.etat, 3, 0, 1, 4)
        for j, (lib, f) in enumerate((("التالي", self.suivant), ("استبدال", self.remplacer),
                                      ("استبدال الكل", self.tout_remplacer))):
            b = QPushButton(lib)
            b.clicked.connect(f)
            g.addWidget(b, 4, j + 1)

    def _drapeaux(self):
        return QTextDocument.FindCaseSensitively if self.casse.isChecked() else QTextDocument.FindFlag(0)

    def suivant(self) -> bool:
        t = self.cherche.text()
        if not t:
            return False
        if not self.e.edit.find(t, self._drapeaux()):
            c = self.e.edit.textCursor()
            c.movePosition(QTextCursor.Start)
            self.e.edit.setTextCursor(c)
            if not self.e.edit.find(t, self._drapeaux()):
                self.etat.setText("لا توجد نتيجة.")
                return False
        self.etat.setText("")
        return True

    def remplacer(self) -> None:
        c = self.e.edit.textCursor()
        if c.hasSelection() and c.selectedText() == self.cherche.text():
            c.insertText(self.remplace.text())
        self.suivant()

    def tout_remplacer(self) -> int:
        t = self.cherche.text()
        if not t:
            return 0
        doc = self.e.edit.document()
        n = 0
        c = QTextCursor(doc)
        c.beginEditBlock()
        while True:
            c = doc.find(t, c, self._drapeaux())
            if c.isNull():
                break
            c.insertText(self.remplace.text())
            n += 1
        c.endEditBlock()
        self.etat.setText(f"استُبدلت {n} مرة.")
        return n


# ======================================================================
# المسطرة وشريط الحالة (طلب المدير 2026-11-19: «أريد مثل هذا المحرر»)
# ======================================================================

VERT_FONCE = "#0E3B2E"
VERT = "#1B5E46"
DORE = "#C9A04A"


class Regle(QWidget):
    """مسطرة بالسنتيمتر فوق الورقة: الهامشان رماديان، ومنطقة الكتابة بيضاء، والترقيم من اليمين (RTL)."""

    def __init__(self, editeur: "EditeurDocument"):
        super().__init__()
        self.e = editeur
        self.setFixedHeight(26)

    def paintEvent(self, ev):   # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        m = MARGE_ECRAN
        p.fillRect(self.rect(), QColor("#ECEAE4"))
        p.fillRect(QRectF(m, 3, max(0, w - 2 * m), self.height() - 6), QColor("#FFFFFF"))
        p.setPen(QPen(QColor("#9A968C"), 1))
        f = QFont()
        f.setPixelSize(9)
        p.setFont(f)
        cm = PX_PAR_MM * 10
        x = w - m
        k = 0
        while x >= m - 0.5:
            p.drawLine(QPointF(x, self.height() - 4), QPointF(x, self.height() - 11))
            if k:
                p.drawText(QRectF(x - 10, 2, 20, 12), Qt.AlignCenter, str(k))
            demi = x - cm / 2
            if demi > m:
                p.drawLine(QPointF(demi, self.height() - 4), QPointF(demi, self.height() - 7))
            x -= cm
            k += 1
        # علامتا الهامشين (مثلثان ذهبيان)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(DORE))
        for xx in (m, w - m):
            p.drawPolygon(QPolygonF([QPointF(xx - 5, 0), QPointF(xx + 5, 0), QPointF(xx, 7)]))
        p.end()


class BarreEtat(QFrame):
    """شريط الحالة: الصفحات والكلمات والحروف، ووضع الوثيقة."""

    def __init__(self):
        super().__init__()
        self.setObjectName("barreEtatEditeur")
        self.setStyleSheet(f"QFrame#barreEtatEditeur {{ background: qlineargradient(x1:1, y1:0, x2:0, y2:0, "
                           f"stop:0 {VERT_FONCE}, stop:1 {VERT}); border-radius: 8px; }} "
                           f"QLabel {{ color: #F2EEDF; background: transparent; font-weight: 600; }}")
        h = QHBoxLayout(self)
        h.setContentsMargins(14, 4, 14, 4)
        h.setSpacing(22)
        self.l_page, self.l_mots, self.l_car, self.l_mode = QLabel(), QLabel(), QLabel(), QLabel()
        for l in (self.l_page, self.l_mots, self.l_car):
            h.addWidget(l)
        h.addStretch()
        h.addWidget(self.l_mode)

    def definir(self, pages: int, mots: int, caracteres: int, mode: str) -> None:
        self.l_page.setText(f"الصفحات: {pages}")
        self.l_mots.setText(f"{mots} كلمة")
        self.l_car.setText(f"{caracteres} حرفاً")
        self.l_mode.setText(mode)


# ======================================================================
# المحرر
# ======================================================================

class EditeurDocument(QWidget):
    """معاينة الوثيقة وتحريرها داخل النافذة. retour: ما يُنفَّذ عند «رجوع» (العودة إلى الصفحة السابقة)."""

    def __init__(self, chemin: Path, parent=None, retour=None):
        super().__init__(parent)
        self.chemin = Path(chemin)
        self.retour = retour
        self.page = finition.en_html(self.chemin)
        self.setWindowTitle(f"محرر الوثائق · ⁦{self.chemin.name}⁩")
        self.setLayoutDirection(Qt.RightToLeft)
        g, h_, d, b_ = self.page.marges_mm
        self.largeur_contenu = round((self.page.largeur_mm - g - d) * PX_PAR_MM)
        self.hauteur_contenu = max(100.0, (self.page.hauteur_mm - h_ - b_) * PX_PAR_MM)
        self.mode_zoom = "largeur"   # largeur: ملء العرض؛ page: الصفحة كاملة؛ fixe: نسبة يحددها المدير
        v = QVBoxLayout(self)
        v.setContentsMargins(20, 14, 20, 14)
        v.setSpacing(8)

        def bouton(texte, action, aide="", principal=False):
            b = QPushButton(texte)
            if principal:
                b.setObjectName("principal")
            if aide:
                b.setToolTip(aide)
            b.clicked.connect(lambda: action())
            return b

        # ---- الشريط العلوي: عنوان الوثيقة وأفعالها، بلون البرنامج (2026-11-19) ----
        self.entete = QFrame()
        self.entete.setObjectName("enteteEditeur")
        self.entete.setStyleSheet(
            f"QFrame#enteteEditeur {{ background: qlineargradient(x1:1, y1:0, x2:0, y2:0, stop:0 {VERT_FONCE}, "
            f"stop:1 {VERT}); border-radius: 12px; border-bottom: 3px solid {DORE}; }}"
            "QFrame#enteteEditeur QLabel { color: #FFFFFF; background: transparent; }"
            "QFrame#enteteEditeur QPushButton { background: rgba(255,255,255,0.10); color: #FFFFFF; "
            "border: 1px solid rgba(255,255,255,0.35); border-radius: 9px; padding: 6px 12px; font-weight: 700; }"
            "QFrame#enteteEditeur QPushButton:hover { background: rgba(255,255,255,0.22); }"
            "QFrame#enteteEditeur QPushButton:checked { background: #F3D27A; color: #0E3B2E; }"
            "QFrame#enteteEditeur QPushButton:disabled { color: rgba(255,255,255,0.4); }"
            "QFrame#enteteEditeur QPushButton#principal { background: #EF8A00; border: none; }"
            "QFrame#enteteEditeur QPushButton#principal:hover { background: #F59E1B; }")
        h = QHBoxLayout(self.entete)
        h.setContentsMargins(14, 8, 14, 8)
        h.setSpacing(6)
        self.b_retour = bouton("رجوع", self.revenir_page, "العودة إلى الصفحة التي فُتحت منها الوثيقة")
        h.addWidget(self.b_retour)
        ic = QLabel()
        ic.setPixmap(_icone(_crayon_titre, "#F3D27A", 22))
        h.addWidget(ic)
        tv = QVBoxLayout()
        tv.setSpacing(0)
        titre = QLabel(self.chemin.stem.split("_", 2)[-1].replace("_", " "))
        titre.setStyleSheet("font-size: 13pt; font-weight: 800;")
        tv.addWidget(titre)
        sous = QLabel("محرر على طريقة Word: النسخ والقص واللصق والتنسيق داخل البرنامج")
        sous.setStyleSheet("color: rgba(255,255,255,0.75); font-size: 9pt;")
        tv.addWidget(sous)
        h.addLayout(tv, 1)
        self.b_modifier = bouton("تعديل الوثيقة", self.basculer_edition, "الكتابة على الورقة وأدوات التنسيق")
        self.b_modifier.setCheckable(True)
        self.b_enregistrer = bouton("حفظ التعديلات", lambda: self.enregistrer(),
                                    "تُحفظ بجانب الوثيقة وتُفتح بها في المرة المقبلة")
        self.b_original = bouton("العودة إلى الأصل", lambda: self.revenir(),
                                 "حذف التعديلات المحفوظة وعرض الوثيقة كما وُلّدت")
        self.b_pdf = bouton("حفظ PDF", self.exporter_pdf, "ملف للقراءة فقط يُرسل بالبريد أو واتساب")
        self.b_image = bouton("حفظ كصورة", self.exporter_image, "صورة لكل صفحة (للنشر أو الإرسال)")
        self.b_externe = bouton("فتح ببرنامج الحاسوب", self.ouvrir_externe,
                                "يفتح الملف الأصلي (دون تعديلات هذا المحرر) ببرنامج تحرير النصوص المثبت")
        self.b_imprimer = bouton("طباعة", self.imprimer, "اختيار الطابعة وعدد النسخ ثم الطبع", True)
        for b in (self.b_modifier, self.b_enregistrer, self.b_original, self.b_pdf, self.b_image, self.b_externe,
                  self.b_imprimer):
            h.addWidget(b)
        v.addWidget(self.entete)

        # ---- شريط التكبير (المعاينة) ----
        self.barre_zoom = QWidget()
        hz = QHBoxLayout(self.barre_zoom)
        hz.setContentsMargins(0, 0, 0, 0)
        hz.setSpacing(6)
        self.l_pages = QLabel()
        self.l_pages.setObjectName("etiquette")
        hz.addWidget(self.l_pages)
        hz.addStretch()
        self.b_moins = self._outil("−", "تصغير", lambda: self.zoomer(1 / 1.15))
        self.b_plus = self._outil("+", "تكبير", lambda: self.zoomer(1.15))
        self.c_zoom = QComboBox()
        for lib in ("ملء العرض", "الصفحة كاملة", "75%", "100%", "125%", "150%", "200%"):
            self.c_zoom.addItem(lib)
        self.c_zoom.currentTextChanged.connect(self._choisir_zoom)
        self.c_zoom.setMinimumWidth(130)
        for w in (self.b_moins, self.c_zoom, self.b_plus):
            hz.addWidget(w)
        v.addWidget(self.barre_zoom)

        # ---- الشريط (تبويبات ومجموعات، على طريقة Word) ----
        self.outils = QFrame()
        self.outils.setObjectName("ruban")
        self.outils.setStyleSheet(
            "QFrame#ruban { background: #F7F5EF; border: 1px solid #DCD7CB; border-radius: 12px; }"
            "QFrame#ruban QToolButton { border: none; border-radius: 6px; padding: 3px; min-width: 28px; "
            "min-height: 28px; color: #2B2E3A; }"
            "QFrame#ruban QToolButton:hover { background: #E6E1D3; }"
            "QFrame#ruban QToolButton:checked { background: #D9EBDD; border: 1px solid #8DBF9F; }"
            "QFrame#ruban QToolButton#grand { min-width: 56px; min-height: 58px; font-size: 9pt; }"
            "QFrame#ruban QPushButton#onglet { background: transparent; border: none; border-bottom: 3px solid "
            "transparent; padding: 6px 14px; font-weight: 700; color: #4A4D5A; }"
            "QFrame#ruban QPushButton#onglet:checked { color: #0E3B2E; border-bottom: 3px solid #C9A04A; }"
            "QFrame#ruban QPushButton#onglet:hover { color: #0E3B2E; }"
            "QFrame#ruban QLabel#legende { color: #8A8678; font-size: 8pt; background: transparent; }"
            "QFrame#ruban QFrame#separateur { background: #DCD7CB; }")
        self._construire_outils()
        v.addWidget(self.outils)
        h = QHBoxLayout()
        h.addStretch()
        self.etat = QLabel()
        self.etat.setObjectName("pastille")
        h.addWidget(self.etat)
        v.addLayout(h)
        self.message = QLabel()
        self.message.setObjectName("message")
        self.message.setWordWrap(True)
        self.message.hide()
        v.addWidget(self.message)

        # ---- الورقة (التحرير): مسطرة فوقها، والورقة البيضاء بظل على خلفية رمادية ----
        self.fond = QFrame()
        self.fond.setObjectName("fondPapier")
        self.fond.setStyleSheet(f"QFrame#fondPapier {{ background: {GRIS_FOND}; border-radius: 10px; }}")
        vf = QVBoxLayout(self.fond)
        vf.setContentsMargins(0, 8, 0, 14)
        vf.setSpacing(6)
        hr = QHBoxLayout()
        hr.addStretch()
        self.regle = Regle(self)
        hr.addWidget(self.regle)
        hr.addStretch()
        vf.addLayout(hr)
        hf = QHBoxLayout()
        self.edit = QTextEdit()
        self.edit.setObjectName("papier")
        self.edit.setStyleSheet("QTextEdit#papier { background: #FFFFFF; color: #000000; border: none; "
                                "border-radius: 0; selection-background-color: #2E3192; selection-color: #FFFFFF; }")
        from PySide6.QtWidgets import QGraphicsDropShadowEffect
        ombre = QGraphicsDropShadowEffect(self.edit)
        ombre.setBlurRadius(22)
        ombre.setOffset(0, 4)
        ombre.setColor(QColor(0, 0, 0, 110))
        self.edit.setGraphicsEffect(ombre)
        self.edit.setLayoutDirection(Qt.RightToLeft)
        self.edit.setAcceptRichText(True)
        self.edit.document().setDocumentMargin(MARGE_ECRAN)
        self.edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.edit.setLineWrapMode(QTextEdit.FixedPixelWidth)
        self.edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.edit.cursorPositionChanged.connect(self._synchroniser)
        self.edit.viewport().installEventFilter(self)
        hf.addStretch()
        hf.addWidget(self.edit)
        hf.addStretch()
        vf.addLayout(hf, 1)
        v.addWidget(self.fond, 1)
        self._geometrie_page()

        # ---- المعاينة ----
        self.vue = VuePages(self)
        self.zone = ZoneApercu(self.vue, self._ajuster_zoom)
        v.addWidget(self.zone, 1)

        # ---- شريط الحالة ----
        self.barre_etat = BarreEtat()
        v.addWidget(self.barre_etat)
        from PySide6.QtCore import QTimer
        self._minuteur_etat = QTimer(self)
        self._minuteur_etat.setSingleShot(True)
        self._minuteur_etat.setInterval(450)
        self._minuteur_etat.timeout.connect(self._maj_barre_etat)
        self.edit.textChanged.connect(self._minuteur_etat.start)
        self._format_copie: QTextCharFormat | None = None

        self.edit.document().modificationChanged.connect(lambda _: self._etat())
        self.charger()
        self.basculer_edition(False)

    # ---------- شريط الأدوات ----------
    def _outil(self, texte_ou_icone, aide: str, action, checkable: bool = False, police: QFont | None = None):
        b = QToolButton()
        if texte_ou_icone in ICONES:
            b.setIcon(_icone(ICONES[texte_ou_icone]))
            b.setIconSize(QSize(20, 20))
        else:
            b.setText(texte_ou_icone)
            if police is not None:
                b.setFont(police)
        b.setToolTip(aide)
        b.setCheckable(checkable)
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(lambda _=False: action())
        return b

    def _grand(self, icone: str, texte: str, aide: str, action, checkable: bool = False) -> QToolButton:
        b = self._outil(icone, aide, action, checkable)
        b.setObjectName("grand")
        b.setText(texte)
        b.setIconSize(QSize(28, 28))
        b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        return b

    def _groupe(self, panneau: QHBoxLayout, legende: str) -> QGridLayout:
        """مجموعة في الشريط: أدوات في شبكة، وتسميتها تحتها، وفاصل بعدها."""
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        v = QVBoxLayout(w)
        v.setContentsMargins(4, 2, 4, 0)
        v.setSpacing(2)
        g = QGridLayout()
        g.setHorizontalSpacing(3)
        g.setVerticalSpacing(3)
        v.addLayout(g, 1)
        l = QLabel(legende)
        l.setObjectName("legende")
        l.setAlignment(Qt.AlignCenter)
        v.addWidget(l)
        panneau.addWidget(w)
        sep = QFrame()
        sep.setObjectName("separateur")
        sep.setFixedWidth(1)
        panneau.addWidget(sep)
        return g

    def _rangee(self, g: QGridLayout, ligne: int, widgets, col0: int = 0) -> None:
        h = QHBoxLayout()
        h.setSpacing(3)
        for w in widgets:
            h.addWidget(w)
        h.addStretch()
        g.addLayout(h, ligne, col0)

    def _construire_outils(self) -> None:
        from PySide6.QtWidgets import QButtonGroup, QStackedWidget
        vo = QVBoxLayout(self.outils)
        vo.setContentsMargins(10, 4, 10, 6)
        vo.setSpacing(4)
        # التبويبات
        ho = QHBoxLayout()
        ho.setSpacing(2)
        self.onglets: dict[str, QPushButton] = {}
        self.pile_ruban = QStackedWidget()
        self._groupe_onglets = QButtonGroup(self)
        for i, nom in enumerate(("الصفحة الرئيسية", "إدراج", "تخطيط الصفحة", "عرض")):
            b = QPushButton(nom)
            b.setObjectName("onglet")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, i=i: self.choisir_onglet(i))
            self._groupe_onglets.addButton(b)
            self.onglets[nom] = b
            ho.addWidget(b)
        ho.addStretch()
        for cle, aide, f in (("annuler", "تراجع (Ctrl+Z)", lambda: self.edit.undo()),
                             ("refaire", "إعادة (Ctrl+Y)", lambda: self.edit.redo())):
            ho.addWidget(self._outil(cle, aide, f))
        self.b_simple = QPushButton("الوضع البسيط")
        self.b_simple.setObjectName("onglet")
        self.b_simple.setCheckable(True)
        self.b_simple.setToolTip("طي الشريط لإفساح المجال للورقة")
        self.b_simple.toggled.connect(lambda c: self.pile_ruban.setVisible(not c))
        ho.addWidget(self.b_simple)
        vo.addLayout(ho)
        vo.addWidget(self.pile_ruban)

        def panneau():
            w = QWidget()
            w.setStyleSheet("background: transparent;")
            h = QHBoxLayout(w)
            h.setContentsMargins(0, 2, 0, 0)
            h.setSpacing(6)
            self.pile_ruban.addWidget(w)
            return h

        def pol(gras=False, ital=False, soul=False, barre=False):
            f = QFont()
            f.setPixelSize(16)
            f.setBold(gras)
            f.setItalic(ital)
            f.setUnderline(soul)
            f.setStrikeOut(barre)
            return f

        # ===== الصفحة الرئيسية =====
        p = panneau()
        g = self._groupe(p, "الحافظة")
        g.addWidget(self._grand("coller", "لصق", "لصق (Ctrl+V)", lambda: self.edit.paste()), 0, 0, 2, 1)
        self.b_pinceau = self._outil("pinceau", "نسخ التنسيق: انقر ثم حدد النص الذي يأخذ التنسيق",
                                     self.copier_format, True)
        g.addWidget(self._outil("couper", "قص (Ctrl+X)", lambda: self.edit.cut()), 0, 1)
        g.addWidget(self._outil("copier", "نسخ (Ctrl+C)", lambda: self.edit.copy()), 1, 1)
        g.addWidget(self.b_pinceau, 0, 2)

        g = self._groupe(p, "الخط")
        self.c_police = QFontComboBox()
        self.c_police.setMaximumWidth(190)
        self.c_police.setToolTip("نوع الخط")
        self.c_police.currentFontChanged.connect(self.police)
        self.c_taille = QComboBox()
        self.c_taille.setEditable(True)
        self.c_taille.addItems([str(n) for n in (8, 9, 10, 11, 12, 13, 14, 16, 18, 20, 22, 24, 28, 32, 36, 48)])
        self.c_taille.setMaximumWidth(64)
        self.c_taille.setToolTip("حجم الخط")
        self.c_taille.textActivated.connect(lambda t: t.replace(".", "", 1).isdigit() and self.taille_fixe(float(t)))
        b_plus = self._outil("A+", "تكبير الخط", lambda: self.taille(+1), police=pol(gras=True))
        b_moins = self._outil("A−", "تصغير الخط", lambda: self.taille(-1), police=pol())
        self._rangee(g, 0, (self.c_police, self.c_taille, b_plus, b_moins))
        self.b_gras = self._outil("B", "غامق (Ctrl+B)", self.gras, True, pol(gras=True))
        self.b_italique = self._outil("I", "مائل (Ctrl+I)", self.italique, True, pol(ital=True))
        self.b_souligne = self._outil("U", "تسطير (Ctrl+U)", self.souligner, True, pol(soul=True))
        self.b_barre = self._outil("S", "شطب", self.barrer, True, pol(barre=True))
        self.b_exposant = self._outil("exposant", "نص مرتفع", lambda: self.position_texte(True), True)
        self.b_indice = self._outil("indice", "نص منخفض", lambda: self.position_texte(False), True)
        self.b_couleur = self._outil("", "لون النص", self.couleur_texte)
        self.b_couleur.setIcon(_icone_couleur("A", "#C62828"))
        self.b_couleur.setIconSize(QSize(20, 20))
        self.b_surligner = self._outil("", "لون الإبراز", self.surligner)
        self.b_surligner.setIcon(_icone_couleur("ab", "#FFEB3B", fond=True))
        self.b_surligner.setIconSize(QSize(20, 20))
        self._rangee(g, 1, (self.b_gras, self.b_italique, self.b_souligne, self.b_barre, self.b_exposant,
                            self.b_indice, self.b_couleur, self.b_surligner,
                            self._outil("gomme", "مسح التنسيق", self.effacer_format)))

        g = self._groupe(p, "فقرة")
        self.b_align = {}
        for cle, aide, al in (("droite", "محاذاة لليمين", Qt.AlignRight | Qt.AlignAbsolute),
                              ("centre", "توسيط", Qt.AlignHCenter),
                              ("gauche", "محاذاة لليسار", Qt.AlignLeft | Qt.AlignAbsolute),
                              ("justifier", "ضبط من الجهتين", Qt.AlignJustify)):
            self.b_align[cle] = self._outil(cle, aide, lambda a=al: self.aligner(a), True)
        self.c_interligne = QComboBox()
        for lib in ("تباعد 1", "تباعد 1.15", "تباعد 1.5", "تباعد 2"):
            self.c_interligne.addItem(lib)
        self.c_interligne.setToolTip("تباعد الأسطر")
        self.c_interligne.textActivated.connect(lambda t: self.interligne(float(t.split()[-1])))
        self._rangee(g, 0, (self._outil("puces", "قائمة منقطة", lambda: self.liste(QTextListFormat.ListDisc)),
                            self._outil("numeros", "قائمة مرقمة", lambda: self.liste(QTextListFormat.ListDecimal)),
                            self._outil("retrait-", "تقليص الإزاحة", lambda: self.retrait(-1)),
                            self._outil("retrait+", "زيادة الإزاحة", lambda: self.retrait(+1)),
                            self._outil("rtl", "فقرة عربية (من اليمين إلى اليسار)", lambda: self.direction(True)),
                            self._outil("ltr", "فقرة فرنسية (من اليسار إلى اليمين)", lambda: self.direction(False))))
        self._rangee(g, 1, (*self.b_align.values(), self.c_interligne))

        g = self._groupe(p, "الأنماط")
        self.c_style = QComboBox()
        for lib in ("عادي", "عنوان رئيسي", "عنوان 1", "عنوان 2", "عنوان 3"):
            self.c_style.addItem(lib)
        self.c_style.setMinimumWidth(130)
        self.c_style.setToolTip("نمط الفقرة")
        self.c_style.textActivated.connect(self.appliquer_style)
        g.addWidget(self.c_style, 0, 0)

        g = self._groupe(p, "تحرير")
        g.addWidget(self._grand("loupe", "بحث", "بحث واستبدال (Ctrl+F)", self.rechercher), 0, 0, 2, 1)
        g.addWidget(self._grand("tout", "تحديد الكل", "تحديد الكل (Ctrl+A)", lambda: self.edit.selectAll()), 0, 1, 2, 1)
        p.addStretch()

        # ===== إدراج =====
        p = panneau()
        g = self._groupe(p, "الجداول")
        g.addWidget(self._grand("table", "جدول", "إدراج جدول بعدد الأسطر والأعمدة المحدد",
                                lambda: self.inserer_tableau(self.s_lignes.value(), self.s_colonnes.value())), 0, 0, 2, 1)
        self.s_lignes, self.s_colonnes = QSpinBox(), QSpinBox()
        for s, n, lib in ((self.s_lignes, 3, " أسطر"), (self.s_colonnes, 3, " أعمدة")):
            s.setRange(1, 40)
            s.setValue(n)
            s.setSuffix(lib)
        g.addWidget(self.s_lignes, 0, 1)
        g.addWidget(self.s_colonnes, 1, 1)
        g = self._groupe(p, "رسوم")
        g.addWidget(self._grand("image", "صورة", "إدراج صورة من الحاسوب", self.inserer_image), 0, 0, 2, 1)
        g.addWidget(self._grand("trait", "خط أفقي", "خط أفقي", self.inserer_trait), 0, 1, 2, 1)
        g = self._groupe(p, "عناصر")
        g.addWidget(self._grand("saut", "فاصل صفحات", "بداية صفحة جديدة", self.saut_page), 0, 0, 2, 1)
        g.addWidget(self._grand("date", "التاريخ", "إدراج تاريخ اليوم", self.inserer_date), 0, 1, 2, 1)
        self.c_symbole = QComboBox()
        self.c_symbole.addItem("رمز…")
        self.c_symbole.addItems(["☐", "☑", "✔", "✘", "•", "◄", "►", "★", "№", "℅", "…", "«", "»"])
        self.c_symbole.setToolTip("إدراج رمز (خانات الاختيار في المطبوعات…)")
        self.c_symbole.textActivated.connect(self.inserer_symbole)
        g.addWidget(self.c_symbole, 0, 2)
        p.addStretch()

        # ===== تخطيط الصفحة =====
        p = panneau()
        g = self._groupe(p, "الاتجاه")
        self.b_portrait = self._grand("portrait", "عمودي", "ورقة عمودية", lambda: self.orientation(False), True)
        self.b_paysage = self._grand("paysage", "أفقي", "ورقة أفقية (نسختان في الصفحة…)", lambda: self.orientation(True),
                                     True)
        g.addWidget(self.b_portrait, 0, 0, 2, 1)
        g.addWidget(self.b_paysage, 0, 1, 2, 1)
        g = self._groupe(p, "الهوامش")
        self.c_marges = QComboBox()
        for lib, mm in (("عادية (2 سم)", 20.0), ("ضيقة (1.27 سم)", 12.7), ("متوسطة (1.5 سم)", 15.0),
                        ("واسعة (2.5 سم)", 25.0)):
            self.c_marges.addItem(lib, mm)
        self.c_marges.setCurrentIndex(-1)
        self.c_marges.setPlaceholderText("هوامش الوثيقة")
        self.c_marges.activated.connect(lambda i: self.marges(self.c_marges.itemData(i)))
        g.addWidget(self._outil("marges", "هوامش الصفحة", lambda: self.c_marges.showPopup()), 0, 0)
        g.addWidget(self.c_marges, 0, 1)
        g = self._groupe(p, "الصفحة")
        g.addWidget(self._grand("saut", "فاصل صفحات", "بداية صفحة جديدة", self.saut_page), 0, 0, 2, 1)
        p.addStretch()

        # ===== عرض =====
        p = panneau()
        g = self._groupe(p, "طرق العرض")
        g.addWidget(self._grand("oeil", "الصفحات", "معاينة الصفحات كما تُطبع", lambda: self.basculer_edition(False)),
                    0, 0, 2, 1)
        g.addWidget(self._grand("imprimante_ap", "معاينة الطبع", "معاينة الطبع", lambda: self.apercu()), 0, 1, 2, 1)
        g = self._groupe(p, "إظهار")
        self.b_regle = self._grand("regle", "المسطرة", "إظهار المسطرة أو إخفاؤها", self._basculer_regle, True)
        self.b_regle.setChecked(True)
        g.addWidget(self.b_regle, 0, 0, 2, 1)
        p.addStretch()
        self.choisir_onglet(0)

        from PySide6.QtGui import QKeySequence, QShortcut
        for seq, f in (("Ctrl+B", self.gras), ("Ctrl+I", self.italique), ("Ctrl+U", self.souligner),
                       ("Ctrl+F", self.rechercher), ("Ctrl+S", self.enregistrer)):
            sc = QShortcut(QKeySequence(seq), self)
            sc.activated.connect(lambda f=f: self.edit.isReadOnly() or f())

    def choisir_onglet(self, i: int) -> None:
        self.pile_ruban.setCurrentIndex(i)
        list(self.onglets.values())[i].setChecked(True)
        if hasattr(self, "b_simple") and self.b_simple.isChecked():
            self.b_simple.setChecked(False)

    def _basculer_regle(self) -> None:
        self.regle.setVisible(self.b_regle.isChecked())

    # ---------- هندسة الورقة (الاتجاه والهوامش) ----------
    def _geometrie_page(self) -> None:
        g, h_, d, b_ = self.page.marges_mm
        self.largeur_contenu = round((self.page.largeur_mm - g - d) * PX_PAR_MM)
        self.hauteur_contenu = max(100.0, (self.page.hauteur_mm - h_ - b_) * PX_PAR_MM)
        larg = self.largeur_contenu + 2 * MARGE_ECRAN
        self.edit.setLineWrapColumnOrWidth(larg)
        self.edit.setMaximumWidth(larg + 24)
        self.edit.setMinimumWidth(min(larg + 24, 560))
        self.regle.setFixedWidth(larg)
        if hasattr(self, "b_portrait"):
            self.b_portrait.setChecked(not self.page.paysage)
            self.b_paysage.setChecked(self.page.paysage)

    def orientation(self, paysage: bool) -> None:
        """ورقة عمودية أو أفقية: تتغير الورقة على الشاشة والمعاينة والطبع."""
        from dataclasses import replace
        if self.page.paysage != paysage:
            self.page = replace(self.page, paysage=paysage, largeur_mm=self.page.hauteur_mm,
                                hauteur_mm=self.page.largeur_mm)
        self._geometrie_page()
        self._maj_barre_etat()
        if self.edit.isReadOnly():
            self.actualiser_apercu()
        message(self.message, "الورقة أفقية." if paysage else "الورقة عمودية.")

    def marges(self, mm: float | None) -> None:
        from dataclasses import replace
        if not mm:
            return
        self.page = replace(self.page, marges_mm=(mm, mm, mm, mm))
        self._geometrie_page()
        self._maj_barre_etat()
        if self.edit.isReadOnly():
            self.actualiser_apercu()

    def _maj_barre_etat(self) -> None:
        texte = self.edit.toPlainText()
        doc = self.edit.document().clone(self)
        doc.setDocumentMargin(0)
        doc.setPageSize(QSizeF(self.largeur_contenu, self.hauteur_contenu))
        self.n_pages = max(1, doc.pageCount())
        doc.deleteLater()
        self.barre_etat.definir(self.n_pages, len(texte.split()), sum(1 for c in texte if not c.isspace()),
                                "وضع التحرير" if not self.edit.isReadOnly() else "معاينة للقراءة")

    # ---------- أدوات إضافية ----------
    def copier_format(self) -> None:
        """نسخ التنسيق: يُحفظ تنسيق موضع المؤشر، ويُطبَّق على أول نص يُحدَّد بعده."""
        if self.b_pinceau.isChecked():
            self._format_copie = QTextCharFormat(self.edit.currentCharFormat())
            self.edit.viewport().setCursor(Qt.IBeamCursor)
            message(self.message, "حدد النص الذي يأخذ هذا التنسيق.")
        else:
            self._format_copie = None

    def eventFilter(self, obj, ev):   # noqa: N802
        from PySide6.QtCore import QEvent
        if ev.type() == QEvent.Type.MouseButtonRelease and getattr(self, "_format_copie", None) is not None \
                and self.edit.textCursor().hasSelection():
            self.edit.textCursor().mergeCharFormat(self._format_copie)
            self._format_copie = None
            self.b_pinceau.setChecked(False)
        return super().eventFilter(obj, ev)

    def position_texte(self, haut: bool) -> None:
        f = self.edit.currentCharFormat()
        cible = QTextCharFormat.AlignSuperScript if haut else QTextCharFormat.AlignSubScript
        fmt = QTextCharFormat()
        fmt.setVerticalAlignment(QTextCharFormat.AlignNormal if f.verticalAlignment() == cible else cible)
        self._appliquer(fmt)

    def direction(self, rtl: bool) -> None:
        """فقرة عربية (يمين ← يسار) أو فرنسية (يسار ← يمين)."""
        bf = QTextBlockFormat()
        bf.setLayoutDirection(Qt.RightToLeft if rtl else Qt.LeftToRight)
        bf.setAlignment((Qt.AlignRight if rtl else Qt.AlignLeft) | Qt.AlignAbsolute)
        self.edit.textCursor().mergeBlockFormat(bf)

    STYLES = {"عادي": (0, 12, False, None), "عنوان رئيسي": (1, 22, True, Qt.AlignHCenter),
              "عنوان 1": (1, 18, True, None), "عنوان 2": (2, 15, True, None), "عنوان 3": (3, 13, True, None)}

    def appliquer_style(self, nom: str) -> None:
        niveau, pt, gras, al = self.STYLES.get(nom, self.STYLES["عادي"])
        c = self.edit.textCursor()
        c.beginEditBlock()
        debut, fin = sorted((c.selectionStart(), c.selectionEnd()))
        c.setPosition(debut)
        c.movePosition(QTextCursor.StartOfBlock)
        c.setPosition(fin, QTextCursor.KeepAnchor)
        c.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
        bf = QTextBlockFormat()
        bf.setHeadingLevel(niveau)
        if al is not None:
            bf.setAlignment(al)
        c.mergeBlockFormat(bf)
        cf = QTextCharFormat()
        cf.setFontPointSize(pt)
        cf.setFontWeight(QFont.Weight.Bold if gras else QFont.Weight.Normal)
        c.mergeCharFormat(cf)
        c.endEditBlock()

    def inserer_symbole(self, s: str) -> None:
        if s and not s.startswith("رمز"):
            self.edit.textCursor().insertText(s)
        self.c_symbole.setCurrentIndex(0)

    def _synchroniser(self) -> None:
        """أزرار الشريط تعكس تنسيق موضع المؤشر."""
        f = self.edit.currentCharFormat()
        for b, v in ((self.b_gras, f.fontWeight() > 500), (self.b_italique, f.fontItalic()),
                     (self.b_souligne, f.fontUnderline()), (self.b_barre, f.fontStrikeOut()),
                     (self.b_exposant, f.verticalAlignment() == QTextCharFormat.AlignSuperScript),
                     (self.b_indice, f.verticalAlignment() == QTextCharFormat.AlignSubScript)):
            b.setChecked(bool(v))
        al = self.edit.alignment()
        for cle, flag in (("droite", Qt.AlignRight), ("centre", Qt.AlignHCenter), ("gauche", Qt.AlignLeft),
                          ("justifier", Qt.AlignJustify)):
            self.b_align[cle].setChecked(bool(al & flag) and (cle != "droite" or not al & Qt.AlignJustify))
        if f.fontPointSize():
            self.c_taille.blockSignals(True)
            self.c_taille.setEditText(f"{f.fontPointSize():g}")
            self.c_taille.blockSignals(False)

    # ---------- المعاينة والتحرير ----------
    def basculer_edition(self, actif: bool | None = None) -> None:
        actif = self.b_modifier.isChecked() if actif is None else actif
        self.b_modifier.setChecked(actif)
        self.edit.setReadOnly(not actif)
        self.outils.setVisible(actif)
        self.fond.setVisible(actif)
        self.zone.setVisible(not actif)
        self.barre_zoom.setVisible(not actif)
        self.edit.setTextInteractionFlags(Qt.TextEditorInteraction if actif else
                                          Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        self.b_enregistrer.setVisible(actif)
        if actif:
            self.edit.setFocus()
        else:
            self.actualiser_apercu()
        if hasattr(self, "barre_etat"):
            self._maj_barre_etat()

    def actualiser_apercu(self) -> None:
        self.vue.actualiser()
        self._ajuster_zoom()
        n = self.vue.n
        self.l_pages.setText("صفحة واحدة" if n == 1 else "صفحتان" if n == 2 else f"{n} صفحات")

    def _ajuster_zoom(self) -> None:
        if self.mode_zoom == "fixe" or not hasattr(self, "vue"):
            return
        larg = max(200, self.zone.viewport().width() - 2 * VuePages.ECART - 6)
        haut = max(200, self.zone.viewport().height() - 2 * VuePages.ECART)
        zl = larg / (self.page.largeur_mm * PX_PAR_MM)
        if self.mode_zoom == "page":
            zl = min(zl, haut / (self.page.hauteur_mm * PX_PAR_MM))
        else:
            zl = min(zl, 1.8)   # ملء العرض دون تضخيم مبالغ فيه على الشاشات الكبيرة
        self.vue.definir_zoom(zl)

    def _choisir_zoom(self, t: str) -> None:
        if t == "ملء العرض":
            self.mode_zoom = "largeur"
        elif t == "الصفحة كاملة":
            self.mode_zoom = "page"
        else:
            self.mode_zoom = "fixe"
            self.vue.definir_zoom(int(t.rstrip("%")) / 100)
        self._ajuster_zoom()

    def zoomer(self, facteur: float) -> None:
        self.mode_zoom = "fixe"
        self.vue.definir_zoom(self.vue.zoom * facteur)
        self.c_zoom.setToolTip(f"التكبير الحالي: {round(self.vue.zoom * 100)}%")

    def revenir_page(self) -> None:
        if self.edit.document().isModified():
            self.enregistrer()   # لا تضيع تعديلات المدير بالرجوع
        if self.retour is not None:
            self.retour(self)
        else:
            self.close()

    # ---------- التحميل والحفظ ----------
    def charger(self) -> None:
        f = fichier_modifie(self.chemin)
        self.modifie_sur_disque = f.exists()
        self.edit.setHtml(f.read_text(encoding="utf-8") if self.modifie_sur_disque else self.page.html)
        self.edit.document().setModified(False)
        self.b_original.setEnabled(self.modifie_sur_disque)
        self._etat()
        if hasattr(self, "vue") and not self.b_modifier.isChecked():
            self.actualiser_apercu()

    def _etat(self) -> None:
        if self.edit.document().isModified():
            self.etat.setText("تعديلات غير محفوظة")
        else:
            self.etat.setText("نسخة معدَّلة محفوظة" if self.modifie_sur_disque else "الوثيقة كما وُلّدت")

    def enregistrer(self) -> Path:
        f = fichier_modifie(self.chemin)
        f.write_text(self.edit.toHtml(), encoding="utf-8")
        self.modifie_sur_disque = True
        self.edit.document().setModified(False)
        self.b_original.setEnabled(True)
        self._etat()
        message(self.message, "حُفظت التعديلات. الملف الأصلي لم يتغير.")
        return f

    def revenir(self) -> None:
        fichier_modifie(self.chemin).unlink(missing_ok=True)
        self.charger()
        message(self.message, "عادت الوثيقة كما وُلّدت.")

    def ouvrir_externe(self) -> None:
        """بلاغ المدير 2026-11-19: كان الفتح ببرنامج الحاسوب يُغلق البرنامج. الآن عبر Qt، وأي خطأ يظهر رسالةً."""
        try:
            bureautique.ouvrir_externe(self.chemin)
        except Exception as e:  # noqa: BLE001 — لا شيء هنا يُسقط البرنامج
            message(self.message, f"تعذر فتح الملف ببرنامج الحاسوب: {e}", True)
            return
        message(self.message, "فُتح الملف الأصلي ببرنامج الحاسوب. تعديلاته هناك لا تظهر في هذا المحرر.")

    # ---------- التنسيق ----------
    def _appliquer(self, fmt: QTextCharFormat) -> None:
        c = self.edit.textCursor()
        if not c.hasSelection():
            c.select(QTextCursor.WordUnderCursor)
        c.mergeCharFormat(fmt)
        self.edit.mergeCurrentCharFormat(fmt)

    def gras(self) -> None:
        fmt = QTextCharFormat()
        fmt.setFontWeight(QFont.Weight.Normal if int(self.edit.fontWeight()) > 400 else QFont.Weight.Bold)
        self._appliquer(fmt)

    def italique(self) -> None:
        fmt = QTextCharFormat()
        fmt.setFontItalic(not self.edit.fontItalic())
        self._appliquer(fmt)

    def souligner(self) -> None:
        fmt = QTextCharFormat()
        fmt.setFontUnderline(not self.edit.fontUnderline())
        self._appliquer(fmt)

    def barrer(self) -> None:
        fmt = QTextCharFormat()
        fmt.setFontStrikeOut(not self.edit.currentCharFormat().fontStrikeOut())
        self._appliquer(fmt)

    def police(self, f: QFont) -> None:
        if self.edit.isReadOnly():
            return
        fmt = QTextCharFormat()
        fmt.setFontFamilies([f.family()])
        self._appliquer(fmt)

    def taille(self, delta: int) -> None:
        actuelle = self.edit.fontPointSize() or self.edit.document().defaultFont().pointSizeF() or 15
        self.taille_fixe(max(6.0, actuelle + delta))

    def taille_fixe(self, pt: float) -> None:
        fmt = QTextCharFormat()
        fmt.setFontPointSize(max(6.0, min(96.0, pt)))
        self._appliquer(fmt)

    def couleur_texte(self, couleur: QColor | None = None) -> None:
        couleur = couleur or QColorDialog.getColor(QColor("#C62828"), self, "لون النص")
        if couleur.isValid():
            fmt = QTextCharFormat()
            fmt.setForeground(couleur)
            self._appliquer(fmt)
            self.b_couleur.setIcon(_icone_couleur("A", couleur.name()))

    def surligner(self, couleur: QColor | None = None) -> None:
        couleur = couleur or QColorDialog.getColor(QColor("#FFEB3B"), self, "لون الإبراز")
        if couleur.isValid():
            fmt = QTextCharFormat()
            fmt.setBackground(couleur)
            self._appliquer(fmt)

    def aligner(self, alignement) -> None:
        self.edit.setAlignment(alignement)
        self._synchroniser()

    def liste(self, style) -> None:
        c = self.edit.textCursor()
        lst = c.currentList()
        if lst is not None and lst.format().style() == style:   # ضغطة ثانية: إزالة القائمة
            bf = c.blockFormat()
            lst.remove(c.block())
            bf.setIndent(0)
            c.setBlockFormat(bf)
            return
        fmt = QTextListFormat()
        fmt.setStyle(style)
        fmt.setIndent(1)
        c.createList(fmt)

    def retrait(self, sens: int) -> None:
        c = self.edit.textCursor()
        bf = c.blockFormat()
        bf.setIndent(max(0, bf.indent() + sens))
        c.setBlockFormat(bf)

    def interligne(self, facteur: float) -> None:
        c = self.edit.textCursor()
        bf = c.blockFormat()
        bf.setLineHeight(facteur * 100, int(QTextBlockFormat.LineHeightTypes.ProportionalHeight.value))
        c.setBlockFormat(bf)

    def inserer_tableau(self, lignes: int | None = None, colonnes: int | None = None):
        if lignes is None or colonnes is None:
            d = QDialog(self)
            d.setWindowTitle("إدراج جدول")
            d.setLayoutDirection(Qt.RightToLeft)
            g = QGridLayout(d)
            sl, sc = QSpinBox(), QSpinBox()
            sl.setRange(1, 60)
            sc.setRange(1, 12)
            sl.setValue(3)
            sc.setValue(3)
            g.addWidget(QLabel("عدد الأسطر"), 0, 0)
            g.addWidget(sl, 0, 1)
            g.addWidget(QLabel("عدد الأعمدة"), 1, 0)
            g.addWidget(sc, 1, 1)
            b = QPushButton("إدراج")
            b.setObjectName("principal")
            b.clicked.connect(d.accept)
            g.addWidget(b, 2, 1)
            if d.exec() != QDialog.Accepted:
                return None
            lignes, colonnes = sl.value(), sc.value()
        fmt = QTextTableFormat()
        fmt.setBorder(1)
        fmt.setBorderStyle(QTextFrameFormat.BorderStyle.BorderStyle_Solid)
        fmt.setCellPadding(5)
        fmt.setCellSpacing(0)
        fmt.setWidth(QTextLength(QTextLength.PercentageLength, 100))
        return self.edit.textCursor().insertTable(lignes, colonnes, fmt)

    def inserer_image(self, chemin: Path | None = None) -> bool:
        if chemin is None:
            nom, _ = QFileDialog.getOpenFileName(self, "إدراج صورة", "", "صور (*.png *.jpg *.jpeg *.bmp)")
            if not nom:
                return False
            chemin = Path(nom)
        img = QImage(str(chemin))
        if img.isNull():
            message(self.message, "تعذر قراءة الصورة.", True)
            return False
        url = QUrl.fromLocalFile(str(chemin)).toString()
        self.edit.document().addResource(QTextDocument.ImageResource, QUrl(url), img)
        fmt = QTextImageFormat()
        fmt.setName(url)
        largeur = min(img.width(), self.largeur_contenu)
        fmt.setWidth(largeur)
        fmt.setHeight(img.height() * largeur / max(1, img.width()))
        self.edit.textCursor().insertImage(fmt)
        return True

    def inserer_trait(self) -> None:
        self.edit.textCursor().insertHtml("<hr/>")

    def saut_page(self) -> None:
        c = self.edit.textCursor()
        c.insertBlock()
        bf = c.blockFormat()
        bf.setPageBreakPolicy(QTextFormat.PageBreak_AlwaysBefore)
        c.setBlockFormat(bf)

    def inserer_date(self) -> None:
        from idara.services import textes as tx
        self.edit.textCursor().insertText(tx.date_ar(date.today()))

    def rechercher(self) -> DialogueRecherche:
        if not hasattr(self, "_recherche"):
            self._recherche = DialogueRecherche(self)
        c = self.edit.textCursor()
        if c.hasSelection():
            self._recherche.cherche.setText(c.selectedText())
        self._recherche.show()
        self._recherche.raise_()
        return self._recherche

    def effacer_format(self) -> None:
        c = self.edit.textCursor()
        if not c.hasSelection():
            c.select(QTextCursor.WordUnderCursor)
        c.setCharFormat(QTextCharFormat())

    # ---------- الطبع ----------
    def imprimante(self, pdf: Path | None = None) -> QPrinter:
        pr = QPrinter(QPrinter.HighResolution)
        if pdf is not None:   # قبل ضبط الصفحة: تغيير الصيغة يعيد تهيئة إعداداتها
            pr.setOutputFormat(QPrinter.PdfFormat)
            pr.setOutputFileName(str(pdf))
        pr.setPageSize(QPageSize(QPageSize.A4))
        pr.setPageOrientation(QPageLayout.Landscape if self.page.paysage else QPageLayout.Portrait)
        pr.setPageMargins(QMarginsF(*self.page.marges_mm), QPageLayout.Millimeter)
        pr.setDocName(self.chemin.stem)
        return pr

    def rendre(self, pr: QPrinter) -> None:
        """يرسم الوثيقة على الطابعة بنفس عرض السطر الظاهر في المحرر (ما تراه هو ما يُطبع)."""
        doc = self.edit.document().clone(self)
        doc.setDocumentMargin(0)
        rect = pr.pageLayout().paintRect(QPageLayout.Millimeter)
        doc.setPageSize(QSizeF(self.largeur_contenu, self.largeur_contenu * rect.height() / rect.width()))
        doc.print_(pr)
        self._doc_rendu = doc   # يبقى حياً حتى الرسم التالي (لا حذف أثناء رسم المعاينة)

    def imprimer(self) -> bool:
        pr = self.imprimante()
        if QPrintDialog(pr, self).exec() != QDialog.Accepted:
            return False
        self.rendre(pr)
        message(self.message, "أُرسلت الوثيقة إلى الطابعة.")
        return True

    def apercu(self) -> None:
        # بلاغ المدير 2026-11-18: «معاينة الطبع» كانت تُغلق البرنامج (طابعة مؤقتة يحذفها بايثون): نحتفظ بها.
        self._imprimante_apercu = self.imprimante()
        d = QPrintPreviewDialog(self._imprimante_apercu, self)
        self._apercu = d
        d.setLayoutDirection(Qt.RightToLeft)
        d.setWindowTitle("معاينة الطبع · " + self.chemin.stem)
        d.paintRequested.connect(self.rendre)
        ecran = self.screen().availableGeometry() if self.screen() else None
        if ecran is not None:
            d.resize(int(ecran.width() * 0.9), int(ecran.height() * 0.9))
        d.exec()
        self._apercu = None

    def pages_images(self, echelle: float = 2.0) -> list[QImage]:
        """كل صفحة صورةً بحجم الورقة (هوامشها بيضاء)، بنفس تقطيع الطبع."""
        doc = self.edit.document().clone(self)
        doc.setDocumentMargin(0)
        g, h_, d, b = (m * PX_PAR_MM for m in self.page.marges_mm)
        larg, haut = self.largeur_contenu, self.hauteur_contenu
        doc.setPageSize(QSizeF(larg, haut))
        images = []
        for i in range(max(1, doc.pageCount())):
            img = QImage(int((larg + g + d) * echelle), int((haut + h_ + b) * echelle), QImage.Format_RGB32)
            img.fill(QColor("white"))
            p = QPainter(img)
            p.setRenderHint(QPainter.Antialiasing)
            p.setRenderHint(QPainter.TextAntialiasing)
            p.scale(echelle, echelle)
            p.translate(g, h_ - i * haut)
            doc.drawContents(p, QRectF(0, i * haut, larg, haut))
            p.end()
            images.append(img)
        doc.deleteLater()
        return images

    def exporter_image(self, cible: Path | None = None) -> list[Path] | None:
        if cible is None:
            nom, _ = QFileDialog.getSaveFileName(self, "حفظ كصورة", str(self.chemin.with_suffix(".png")),
                                                 "صورة (*.png *.jpg)")
            if not nom:
                return None
            cible = Path(nom)
        cible = Path(cible)
        if cible.suffix.lower() not in (".png", ".jpg", ".jpeg"):
            cible = cible.with_suffix(".png")
        chemins = []
        for i, img in enumerate(self.pages_images()):
            c = cible if i == 0 else cible.with_name(f"{cible.stem}_{i + 1}{cible.suffix}")
            img.save(str(c))
            chemins.append(c)
        message(self.message, f"حُفظت {len(chemins)} صورة: ⁦{chemins[0].name}⁩" if len(chemins) > 1
                else f"حُفظت الصورة: ⁦{chemins[0].name}⁩")
        return chemins

    def exporter_pdf(self, cible: Path | None = None) -> Path | None:
        if cible is None:
            nom, _ = QFileDialog.getSaveFileName(self, "حفظ الوثيقة", str(self.chemin.with_suffix(".pdf")), "PDF (*.pdf)")
            if not nom:
                return None
            cible = Path(nom)
        self.rendre(self.imprimante(cible))
        message(self.message, f"حُفظ الملف: ⁦{Path(cible).name}⁩")
        return Path(cible)
