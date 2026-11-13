"""صفحة «البنية المادية» (طلب المدير 2026-11-13): عدد كل مكوّن لكل وحدة، ووثيقة البنية المادية، وربطها بمحضر
تسليم المهام."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QHBoxLayout, QLabel, QPushButton, QTableWidgetItem, QWidget

from idara.services import bureautique
from idara.services import structure as st
from idara.ui.composants import bouton, carte
from idara.ui.page_pedagogie import _page
from idara.ui.saisie import message, tableau


def _item(texte: str, editable: bool = True, cle: str | None = None) -> QTableWidgetItem:
    it = QTableWidgetItem(texte)
    it.setTextAlignment(Qt.AlignCenter)
    if cle is not None:
        it.setData(Qt.UserRole, cle)
    if not editable:
        it.setFlags(it.flags() & ~Qt.ItemIsEditable)
    return it


class PageStructure(QWidget):
    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        racine, self.message = _page(
            "البنية المادية", "اكتب عدد كل مكوّن (لكل وحدة مدرسية في المجموعة المدرسية). منها تُولَّد وثيقة البنية "
                              "المادية، وتُقترح أسطر «البنايات» في محضر تسليم المهام.")
        self.setLayout(racine)
        c, v = carte("مكونات البنية المادية")
        self.table = tableau(["المكوّن"], etirer=0)
        self.table.setEditTriggers(QAbstractItemView.AllEditTriggers)
        self.table.setMinimumHeight(420)
        v.addWidget(self.table)
        aide = QLabel("الخانة الفارغة تعني أن المكوّن غير موجود أو لم يُعدّ بعد؛ لا يُطبع في الوثيقة.")
        aide.setObjectName("etiquette")
        aide.setWordWrap(True)
        v.addWidget(aide)
        h = QHBoxLayout()
        b = QPushButton("حفظ")
        b.setObjectName("principal")
        b.clicked.connect(lambda: self.enregistrer())
        h.addWidget(b)
        b = QPushButton("إضافة مكوّن")
        b.clicked.connect(self.ajouter)
        h.addWidget(b)
        self.b_suppr = bouton("حذف المكوّن المضاف")
        self.b_suppr.clicked.connect(lambda: self.supprimer())
        h.addWidget(self.b_suppr)
        h.addStretch()
        b = QPushButton("توليد وثيقة البنية المادية (Word)")
        b.clicked.connect(lambda: self.generer())
        h.addWidget(b)
        v.addLayout(h)
        racine.addWidget(c)
        racine.addStretch()
        self.rafraichir()

    def rafraichir(self) -> None:
        t = st.tableau(self.f.conn)
        self.unites = t["unites"]
        groupe = len(self.unites) > 1
        cols = ["المكوّن"] + [n for _, n in self.unites] + (["المجموع"] if groupe else []) + ["ملاحظات"]
        self.col_total = 1 + len(self.unites) if groupe else None
        self.col_rem = len(cols) - 1
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.setRowCount(len(t["lignes"]))
        for i, l in enumerate(t["lignes"]):
            self._ligne(i, l)

    def _ligne(self, i: int, l: dict) -> None:
        autre = l["element"].startswith("autre")
        self.table.setItem(i, 0, _item(l["libelle"], editable=autre, cle=l["element"]))
        for j, (uid, _) in enumerate(self.unites, start=1):
            n = l["nombres"].get(uid)
            self.table.setItem(i, j, _item("" if n is None else str(n)))
        if self.col_total is not None:
            self.table.setItem(i, self.col_total, _item("" if l["total"] is None else str(l["total"]), editable=False))
        self.table.setItem(i, self.col_rem, _item(l["remarques"]))

    def ajouter(self) -> None:
        i = self.table.rowCount()
        self.table.insertRow(i)
        self._ligne(i, {"element": "autre:", "libelle": "", "nombres": {}, "total": None, "remarques": ""})
        self.table.setCurrentCell(i, 0)

    def lignes(self) -> list[dict]:
        self.table.setCurrentItem(None)
        res = []
        for i in range(self.table.rowCount()):
            it = self.table.item(i, 0)
            res.append({"element": it.data(Qt.UserRole), "libelle": it.text(),
                        "nombres": {uid: self.table.item(i, j).text() for j, (uid, _) in enumerate(self.unites, 1)},
                        "remarques": self.table.item(i, self.col_rem).text()})
        return res

    def enregistrer(self) -> bool:
        try:
            st.enregistrer(self.f.conn, self.lignes())
        except st.ErreurStructure as e:
            message(self.message, str(e), True)
            return False
        self.rafraichir()
        message(self.message, "حُفظت البنية المادية.")
        return True

    def supprimer(self) -> bool:
        i = self.table.currentRow()
        if i < 0:
            return False
        cle = self.table.item(i, 0).data(Qt.UserRole)
        if cle == "autre:":            # سطر لم يُحفظ بعد
            self.table.removeRow(i)
            return True
        try:
            st.supprimer_element(self.f.conn, cle)
        except st.ErreurStructure as e:
            message(self.message, str(e), True)
            return False
        self.rafraichir()
        return True

    def generer(self):
        if not self.enregistrer():
            return None
        try:
            p = st.generer(self.f.conn, self.f.dossier)
        except (st.ErreurStructure, OSError) as e:
            message(self.message, str(e), True)
            return None
        message(self.message, f"وُلّدت وثيقة البنية المادية: ⁦{p.name}⁩")
        try:
            bureautique.ouvrir(p)
        except OSError:
            pass
        return p
