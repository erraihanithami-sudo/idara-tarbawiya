"""حقول إدخال مشتركة: التاريخ بالكتابة (يوم/شهر/سنة)، رسائل الصفحة، جداول للقراءة فقط."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate, QLocale, QPoint, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from idara.ui import theme
from PySide6.QtWidgets import (QAbstractItemView, QCalendarWidget, QFrame, QHeaderView, QLabel, QLineEdit,
                               QTableWidget, QTableWidgetItem, QVBoxLayout)


def _icone_calendrier() -> QIcon:
    pm = QPixmap(32, 32)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    vert = QColor(theme.VERT)
    p.setPen(QPen(vert, 2.4))
    p.drawRoundedRect(QRectF(5, 7, 22, 20), 3, 3)
    p.fillRect(QRectF(5, 7, 22, 6), vert)
    p.drawLine(11, 4, 11, 9)
    p.drawLine(21, 4, 21, 9)
    p.setPen(Qt.NoPen)
    p.setBrush(vert)
    for x in (10, 16, 22):
        for y in (17, 22):
            p.drawEllipse(QRectF(x - 1.6, y - 1.6, 3.2, 3.2))
    p.end()
    return QIcon(pm)


class ChampDate(QLineEdit):
    """تاريخ يُكتب مباشرة 01/01/1985، أو يُختار من يومية (طلب المدير: كما في صفحة الإعدادات).
    اليومية تُفتح بأيقونتها، أو بالنقر على الحقل وهو فارغ."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setInputMask("00/00/0000;_")
        self.setLayoutDirection(Qt.LeftToRight)
        self.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setMaximumWidth(190)
        self.action_calendrier = self.addAction(_icone_calendrier(), QLineEdit.ActionPosition.TrailingPosition)
        self.action_calendrier.setToolTip("اختيار التاريخ من اليومية")
        self.action_calendrier.triggered.connect(self.ouvrir_calendrier)
        self.popup: QFrame | None = None

    def ouvrir_calendrier(self) -> QCalendarWidget:
        self.popup = QFrame(self, Qt.Popup)
        self.popup.setObjectName("carte")
        v = QVBoxLayout(self.popup)
        v.setContentsMargins(6, 6, 6, 6)
        cal = QCalendarWidget()
        cal.setLocale(QLocale("ar_MA"))
        cal.setLayoutDirection(Qt.RightToLeft)
        cal.setGridVisible(False)
        cal.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        try:
            actuelle = self.iso()
        except ValueError:
            actuelle = ""
        if actuelle:
            d = date.fromisoformat(actuelle)
            cal.setSelectedDate(QDate(d.year, d.month, d.day))
        cal.clicked.connect(self._choisir)
        cal.activated.connect(self._choisir)
        v.addWidget(cal)
        self.popup.adjustSize()
        pos = self.mapToGlobal(QPoint(0, self.height()))
        self.popup.move(pos.x() + self.width() - self.popup.width(), pos.y() + 2)
        self.popup.show()
        self.calendrier = cal
        return cal

    def _choisir(self, q: QDate) -> None:
        self.setText(f"{q.day():02d}/{q.month():02d}/{q.year()}")
        if self.popup:
            self.popup.close()
            self.popup = None

    def mousePressEvent(self, e) -> None:
        super().mousePressEvent(e)
        if self.isEnabled() and not self.text().replace("_", "").strip("/ "):
            self.ouvrir_calendrier()

    def iso(self) -> str:
        """YYYY-MM-DD، أو نص فارغ إن لم يُكتب شيء. يرفع ValueError إن كان غير صحيح."""
        t = self.text().replace("_", "").strip("/ ")
        if not t.replace("/", ""):
            return ""
        j, m, a = self.text().split("/")
        return date(int(a), int(m), int(j)).isoformat()

    def definir(self, iso: str | None) -> None:
        if iso:
            d = date.fromisoformat(iso)
            self.setText(f"{d.day:02d}/{d.month:02d}/{d.year}")
        else:
            self.clear()


def message(label: QLabel, texte: str, erreur: bool = False) -> None:
    label.setObjectName("erreur" if erreur else "info")
    label.setText(texte)
    label.style().unpolish(label)
    label.style().polish(label)
    label.show()


class TableauRapide(QTableWidget):
    """جدول لا يعيد حساب عرض الأعمدة عند كل خانة (بلاغ المدير 2026-11-10: توقف البرنامج مع 347 تلميذاً).

    الأعمدة «على قدر المحتوى» كانت تُحسب من جديد بعد كل setItem، فملء 350 سطراً × 6 أعمدة يأخذ 5 ثوان أو أكثر.
    عند تغيير عدد الأسطر تُجمَّد هذه الأعمدة، ثم يُحسب عرضها مرة واحدة بعد انتهاء الملء."""

    def __init__(self, *args):
        super().__init__(*args)
        self._modes: list | None = None

    def setRowCount(self, n: int) -> None:   # noqa: N802 (اسم Qt)
        self.suspendre()
        super().setRowCount(n)

    def insertRow(self, r: int) -> None:   # noqa: N802
        self.suspendre()
        super().insertRow(r)

    def suspendre(self) -> None:
        if self._modes is not None:
            return
        h = self.horizontalHeader()
        self._modes = [h.sectionResizeMode(i) for i in range(self.columnCount())]
        for i, m in enumerate(self._modes):
            if m == QHeaderView.ResizeToContents:
                h.setSectionResizeMode(i, QHeaderView.Interactive)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self.reprendre)

    def reprendre(self) -> None:
        if self._modes is None:
            return
        h = self.horizontalHeader()
        modes, self._modes = self._modes, None
        for i, m in enumerate(modes):
            if i < self.columnCount() and m == QHeaderView.ResizeToContents:
                h.setSectionResizeMode(i, m)


def tableau(colonnes: list[str], etirer: int = 1) -> QTableWidget:
    t = TableauRapide(0, len(colonnes))
    t.setHorizontalHeaderLabels(colonnes)
    t.verticalHeader().setVisible(False)
    t.verticalHeader().setDefaultSectionSize(40)
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    h = t.horizontalHeader()
    h.setSectionResizeMode(QHeaderView.ResizeToContents)
    h.setSectionResizeMode(etirer, QHeaderView.Stretch)
    h.setStretchLastSection(False)
    t.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    t.setTextElideMode(Qt.ElideLeft)
    return t


def cellule(texte, donnee=None) -> QTableWidgetItem:
    it = QTableWidgetItem("" if texte is None else str(texte))
    if donnee is not None:
        it.setData(Qt.UserRole, donnee)
    return it


def selectionner(t, ligne: int) -> None:
    """تحديد سطر برمجياً (لا يعتمد على حالة لوحة المفاتيح)."""
    from PySide6.QtCore import QItemSelectionModel
    t.selectionModel().select(t.model().index(ligne, 0),
                              QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)
