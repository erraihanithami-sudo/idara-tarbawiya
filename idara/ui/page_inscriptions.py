"""تدبير تسجيلات التلاميذ (طلب المدير 2026-11-07): خانات الواجبات أمام كل تلميذ، وعدّاد تراكمي لكل عنصر."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QGridLayout, QHBoxLayout, QLabel, QPushButton, QTableWidgetItem, QWidget

from idara.services import etablissement as etab_srv
from idara.services import frais_inscription as fr
from idara.services import textes as tx
from idara.ui import theme
from idara.ui.composants import carte
from idara.ui.graphiques import Tuile
from idara.ui.page_pedagogie import _grille, _page
from idara.ui.saisie import cellule, message, tableau

COLONNES = list(fr.ELEMENTS)          # الأعمدة 3، 4، 5
DEBUT = 3
COULEURS = {"assurance": theme.BLEU, "sport": theme.SARCELLE, "cooperative": theme.VIOLET}


class PageInscriptions(QWidget):
    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        self._chargement = False
        racine, self.message = _page("تدبير التسجيلات",
                                     "أشّر أمام كل تلميذ على ما أدّاه من واجبات التسجيل؛ العدّاد يُحدَّث فوراً.")
        self.setLayout(racine)
        self.l_milieu = QLabel()
        self.l_milieu.setWordWrap(True)
        racine.addWidget(self.l_milieu)

        c, v = carte("المجموع التراكمي")
        self.grille = QGridLayout()
        self.grille.setSpacing(12)
        v.addLayout(self.grille)
        racine.addWidget(c)

        c, v = carte("لائحة التلاميذ حسب المستوى")
        self.niveau, self.unite = QComboBox(), QComboBox()
        self.niveau.currentIndexChanged.connect(lambda _: self.afficher())
        self.unite.currentIndexChanged.connect(lambda _: self.afficher())
        v.addLayout(_grille([("المستوى", self.niveau), ("الوحدة المدرسية", self.unite)]))
        h = QHBoxLayout()
        self.boutons_tous = {}
        for k, lib in fr.ELEMENTS.items():
            b = QPushButton(f"تأشير الكل: {lib}")
            b.clicked.connect(lambda _=False, k=k: self.tout_cocher(k))
            self.boutons_tous[k] = b
            h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        self.table = tableau(["الرمز", "الاسم الكامل", "القسم"] + list(fr.ELEMENTS.values()), etirer=1)
        self.table.setMinimumHeight(520)
        self.table.itemChanged.connect(self._coche)
        v.addWidget(self.table)
        racine.addWidget(c)
        racine.addStretch()
        self.rafraichir()

    def rafraichir(self) -> None:
        conn = self.f.conn
        e = etab_srv.lire_etablissement(conn)
        m = fr.montants(conn)
        if m["assurance"] is None:
            self.l_milieu.setText("حدّد وسط المؤسسة (حضري أو قروي) في الإعدادات ← المؤسسة لحساب مبلغ التأمين: "
                                  "8 دراهم في الوسط القروي و12 درهماً في الوسط الحضري.")
            self.l_milieu.setObjectName("alerte")
        else:
            self.l_milieu.setText(f"الوسط: {etab_srv.MILIEUX[e.milieu]} · التأمين {m['assurance']} دراهم، "
                                  f"الجمعية الرياضية {m['sport']} دراهم، التعاون المدرسي {m['cooperative']} دراهم "
                                  "لكل تلميذ.")
            self.l_milieu.setObjectName("etiquette")
        self.l_milieu.style().unpolish(self.l_milieu)
        self.l_milieu.style().polish(self.l_milieu)
        for combo, valeurs, tous in ((self.niveau, self._niveaux(), "كل المستويات"),
                                     (self.unite, [(u, u) for u in etab_srv.unites(conn)], "المؤسسة كاملة")):
            actuel = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(tous, None)
            for lib, d in valeurs:
                combo.addItem(lib, d)
            combo.setCurrentIndex(max(0, combo.findData(actuel)))
            combo.blockSignals(False)
        visible = self.unite.count() > 1
        self.unite.setVisible(visible)
        for l in self.findChildren(QLabel):
            if l.text() == "الوحدة المدرسية":
                l.setVisible(visible)
        self.afficher()

    def _niveaux(self) -> list[tuple[str, str]]:
        try:
            codes = []
            for x in fr.lister(self.f.conn):
                if x["niveau"] and x["niveau"] not in codes:
                    codes.append(x["niveau"])
        except fr.ErreurFrais:
            return []
        return [(tx.niveau_ar(n) if n in tx.NIVEAUX else n, n) for n in codes]

    def afficher(self) -> None:
        try:
            self.liste = fr.lister(self.f.conn, self.niveau.currentData(), self.unite.currentData())
        except fr.ErreurFrais as e:
            message(self.message, str(e), True)
            self.liste = []
        self._chargement = True
        self.table.setRowCount(len(self.liste))
        for i, x in enumerate(self.liste):
            self.table.setItem(i, 0, cellule(x["code_massar"] or "", x["id"]))
            self.table.setItem(i, 1, cellule(f"{x['prenom_ar']} {x['nom_ar']}"))
            self.table.setItem(i, 2, cellule(x["classe"]))
            for j, k in enumerate(COLONNES):
                it = QTableWidgetItem()
                it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
                it.setCheckState(Qt.Checked if x[k] else Qt.Unchecked)
                self.table.setItem(i, DEBUT + j, it)
        self._chargement = False
        self.compteurs()

    def _coche(self, it) -> None:
        if self._chargement or it.column() < DEBUT:
            return
        eid = self.table.item(it.row(), 0).data(Qt.UserRole)
        fr.marquer(self.f.conn, eid, COLONNES[it.column() - DEBUT], it.checkState() == Qt.Checked)
        self.compteurs()

    def tout_cocher(self, element: str) -> int:
        n = fr.marquer_tous(self.f.conn, [x["id"] for x in self.liste], element, True)
        self.afficher()
        message(self.message, f"أُشّر على «{fr.ELEMENTS[element]}» لـ {n} تلميذاً.")
        return n

    def compteurs(self) -> None:
        t = fr.totaux(self.f.conn, self.niveau.currentData(), self.unite.currentData())
        self.totaux = t
        while self.grille.count():
            w = self.grille.takeAt(0).widget()
            if w:
                w.hide()
                w.setParent(None)
                w.deleteLater()
        for i, (k, e) in enumerate(t["elements"].items()):
            mt = "—" if e["montant"] is None else f"{e['montant']} درهم"
            self.grille.addWidget(Tuile(e["libelle"], mt, COULEURS[k], "التدبير المالي والمادي",
                                        f"{e['payes']} / {t['eleves']} تلميذاً"), 0, i)
        self.grille.addWidget(Tuile("المجموع التراكمي لكل العناصر", f"{t['total']} درهم", theme.ORANGE,
                                    "التدبير المالي والمادي", f"{t['eleves']} تلميذاً في اللائحة"), 1, 0, 1, 3)
