"""صفحة «ملفات الأساتذة»: طلب ملف أستاذ وإرسال ملف أستاذ (توجيه المدير 2026-11-15)."""

from __future__ import annotations

from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QGridLayout, QHBoxLayout, QLineEdit,
                               QPushButton, QTableWidgetItem, QWidget)

from idara.services import bureautique
from idara.services import dossier_enseignant as de
from idara.services import personnel as rh
from idara.ui.composants import carte
from idara.ui.formulaires import etiquette
from idara.ui.page_pedagogie import _page
from idara.ui.saisie import ChampDate, TableauRapide, message


class PageDossierProf(QWidget):
    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        racine, self.message = _page(
            "ملفات الأساتذة", "طلب الملف الإداري والتربوي لأستاذ التحق بالمؤسسة، أو إرسال ملف أستاذ غادرها. "
                              "المراسلة تأخذ رقمها من سجل الصادر.")
        self.setLayout(racine)
        c, v = carte("المراسلة")
        self.sens = QComboBox()
        for k, lib in de.SENS.items():
            self.sens.addItem(lib, k)
        self.sens.currentIndexChanged.connect(lambda _: self._sens())
        self.rappel = QCheckBox("تذكير بطلب سابق")
        self.cible = QLineEdit()
        self.cible.setPlaceholderText("مثال: مدرسة ... بجماعة ...")
        self.couvert = QLineEdit()
        self.couvert.setPlaceholderText("فارغ إن كانت المؤسستان في المديرية نفسها، مثال: بإقليم ...")
        self.reference = QLineEdit()
        self.reference.setPlaceholderText("اختياري، مثال: مراسلتكم رقم ... بتاريخ ...")
        self.le = ChampDate()
        g = QGridLayout()
        g.setHorizontalSpacing(16)
        for k, (lib, w) in enumerate((("نوع المراسلة", self.sens), ("التاريخ", self.le),
                                      ("المؤسسة المرسل إليها", self.cible),
                                      ("تحت إشراف المدير الإقليمي", self.couvert), ("المرجع", self.reference))):
            g.addWidget(etiquette(lib, w), (k // 2) * 2, k % 2)
            g.addWidget(w, (k // 2) * 2 + 1, k % 2)
        g.addWidget(self.rappel, 5, 0)
        v.addLayout(g)
        racine.addWidget(c)

        c, v = carte("الأساتذة المعنيون")
        h = QHBoxLayout()
        self.choix = QComboBox()
        self.choix.setMinimumWidth(260)
        h.addWidget(self.choix, 1)
        b = QPushButton("إضافة من الأطر")
        b.clicked.connect(lambda: self.ajouter_personnel())
        h.addWidget(b)
        b = QPushButton("سطر فارغ")
        b.setToolTip("لأستاذ(ة) غير مسجل(ة) بعد في لائحة الأطر")
        b.clicked.connect(lambda: self.ajouter("", "", ""))
        h.addWidget(b)
        b = QPushButton("حذف السطر")
        b.clicked.connect(lambda: self.supprimer())
        h.addWidget(b)
        v.addLayout(h)
        self.table = TableauRapide(0, 3)
        self.table.setHorizontalHeaderLabels(["الاسم والنسب", "رقم التأجير", "ملاحظات"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QAbstractItemView.AllEditTriggers)
        self.table.setMinimumHeight(180)
        v.addWidget(self.table)
        h = QHBoxLayout()
        b = QPushButton("توليد المراسلة")
        b.setObjectName("principal")
        b.clicked.connect(lambda: self.generer())
        h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        racine.addWidget(c)
        racine.addStretch()
        self.rafraichir()
        self._sens()

    def rafraichir(self) -> None:
        self.choix.clear()
        for p in rh.lister(self.f.conn):
            if p.categorie in ("enseignant", "educatrice", "directeur"):
                self.choix.addItem(f"{p.nom_ar} {p.prenom_ar}".strip(), p.ppr or "")

    def _sens(self) -> None:
        self.rappel.setVisible(self.sens.currentData() == "demande")
        if self.sens.currentData() != "demande":
            self.rappel.setChecked(False)

    def ajouter(self, nom: str, ppr: str, obs: str) -> None:
        i = self.table.rowCount()
        self.table.insertRow(i)
        for j, x in enumerate((nom, ppr, obs)):
            self.table.setItem(i, j, QTableWidgetItem(x))

    def ajouter_personnel(self) -> None:
        if self.choix.currentIndex() >= 0:
            self.ajouter(self.choix.currentText(), self.choix.currentData() or "", "")

    def supprimer(self) -> None:
        r = self.table.currentRow()
        if r >= 0:
            self.table.removeRow(r)

    def generer(self):
        self.table.setCurrentItem(None)
        profs = [tuple((self.table.item(i, j).text() if self.table.item(i, j) else "") for j in range(3))
                 for i in range(self.table.rowCount())]
        try:
            le = self.le.iso() or None
            p, num = de.generer(self.f.conn, self.f.dossier, self.sens.currentData(), self.cible.text(), profs, le,
                                self.couvert.text(), self.reference.text(), self.rappel.isChecked())
        except ValueError as e:   # ErreurDossierProf أو تاريخ غير صحيح
            message(self.message, str(e) if isinstance(e, de.ErreurDossierProf) else "التاريخ غير صحيح.", True)
            return None
        message(self.message, f"وُلّدت المراسلة وسُجلت في الصادر تحت عدد ⁦{num}⁩.")
        try:
            bureautique.ouvrir(p)
        except OSError:
            pass
        return p
