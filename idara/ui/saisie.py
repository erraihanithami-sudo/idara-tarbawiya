"""حقول إدخال مشتركة: التاريخ بالكتابة (يوم/شهر/سنة)، رسائل الصفحة، جداول للقراءة فقط."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QHeaderView, QLabel, QLineEdit, QTableWidget,
                               QTableWidgetItem)


class ChampDate(QLineEdit):
    """تاريخ يُكتب مباشرة 01/01/1985 (أسرع من التقويم للتواريخ القديمة)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setInputMask("00/00/0000;_")
        self.setLayoutDirection(Qt.LeftToRight)
        self.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setMaximumWidth(180)

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


def tableau(colonnes: list[str], etirer: int = 1) -> QTableWidget:
    t = QTableWidget(0, len(colonnes))
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
