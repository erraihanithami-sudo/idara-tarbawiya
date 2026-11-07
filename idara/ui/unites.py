"""شريط الوحدات المدرسية (طلب المدير 2026-11-07): «المؤسسة كاملة» ثم زر لكل وحدة. يُخفى في المؤسسة المستقلة."""

from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from idara.services import etablissement as etab_srv


class BarreUnites(QWidget):
    def __init__(self, conn_fn: Callable, quand_change: Callable[[str | None], None], libelle: str = "الوحدة:"):
        super().__init__()
        self.conn_fn, self.quand_change = conn_fn, quand_change
        self.unite: str | None = None
        self.h = QHBoxLayout(self)
        self.h.setContentsMargins(0, 0, 0, 0)
        self.h.setSpacing(8)
        self.libelle = libelle
        self.boutons: dict[str | None, QPushButton] = {}
        self.actualiser()

    def actualiser(self) -> None:
        while self.h.count():
            it = self.h.takeAt(0)
            if it.widget():
                it.widget().hide()
                it.widget().setParent(None)
                it.widget().deleteLater()
        unites = etab_srv.unites(self.conn_fn())
        if self.unite not in unites:
            self.unite = None
        self.boutons = {}
        if not unites:
            self.hide()
            return
        self.h.addWidget(QLabel(self.libelle))
        for u in [None, *unites]:
            b = QPushButton("المؤسسة كاملة" if u is None else u)
            b.setCheckable(True)
            b.setChecked(u == self.unite)
            if u == self.unite:
                b.setObjectName("principal")
            b.clicked.connect(lambda _=False, u=u: self.choisir(u))
            self.boutons[u] = b
            self.h.addWidget(b)
        self.h.addStretch()
        self.show()

    def choisir(self, u: str | None) -> None:
        self.unite = u
        self.actualiser()
        self.quand_change(u)
