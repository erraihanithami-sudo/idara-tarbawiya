"""عناصر الواجهة المشتركة بين الصفحات."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QVBoxLayout, QWidget


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


def entete(titre: str, sous_titre: str = "") -> QWidget:
    w = QWidget()
    v = QVBoxLayout(w)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(4)
    t = QLabel(titre)
    t.setObjectName("titrePage")
    v.addWidget(t)
    if sous_titre:
        s = QLabel(sous_titre)
        s.setObjectName("sousTitre")
        s.setWordWrap(True)
        v.addWidget(s)
    return w
