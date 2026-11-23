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
                                     "أشّر أمام كل تلميذ على ما أدّاه من واجبات التسجيل؛ العدّاد يُحدَّث فوراً. "
                                     "تلاميذ التعليم الأولي يُؤمَّنون من خلال جمعيتهم فلا يظهرون هنا.")
        self.setLayout(racine)
        from idara.ui.vitrine import bouton_couleur
        h0 = QHBoxLayout()
        self.l_milieu = QLabel()
        self.l_milieu.setWordWrap(True)
        h0.addWidget(self.l_milieu, 1)
        self.b_montants = bouton_couleur("تهيئة مبالغ التسجيل", "#EF6C00", "statistiques",
                                         "قيمة التأمين والانخراط في الجمعية الرياضية وجمعية تنمية التعاون المدرسي")
        self.b_montants.clicked.connect(lambda: self.ouvrir_montants())
        h0.addWidget(self.b_montants)
        self.b_releve = bouton_couleur("مخرجات الواجبات المدرسية", "#2E7D32", "document",
                                       "وثيقة الواجبات المتحصل عليها حسب الأقسام أو للمؤسسة كاملة")
        self.b_releve.clicked.connect(lambda: self.ouvrir_releve())
        h0.addWidget(self.b_releve)
        racine.addLayout(h0)

        c, v = carte("المجموع التراكمي")
        self.grille = QGridLayout()
        self.grille.setSpacing(12)
        v.addLayout(self.grille)
        racine.addWidget(c)

        c, v = carte("مسك المساهمات: لائحة التلاميذ حسب القسم")
        self.classe, self.unite = QComboBox(), QComboBox()
        self.classe.setMinimumWidth(220)
        self.classe.currentIndexChanged.connect(lambda _: self.afficher())
        self.unite.currentIndexChanged.connect(lambda _: self._remplir_classes())
        v.addLayout(_grille([("القسم", self.classe), ("الوحدة المدرسية", self.unite)]))
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
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(hh.ResizeMode.Interactive)
        for j, w in enumerate((130, 260, 120, 150, 150, 210)):
            self.table.setColumnWidth(j, w)
        self.table.setMinimumHeight(520)
        self.table.itemChanged.connect(self._coche)
        v.addWidget(self.table)
        racine.addWidget(c)
        racine.addStretch()
        self.rafraichir()

    def rafraichir(self) -> None:
        conn = self.f.conn
        m = fr.montants(conn)
        saisis = fr.montants_saisis(conn)
        if m["assurance"] is None:
            self.l_milieu.setText("حدّد مبالغ التسجيل في «تهيئة مبالغ التسجيل»: قيمة التأمين والانخراط في "
                                  "الجمعيتين.")
            self.l_milieu.setObjectName("alerte")
        else:
            self.l_milieu.setText(" · ".join(f"{lib}: {m[k]:g} درهم" for k, lib in fr.ELEMENTS.items())
                                  + " لكل تلميذ" + ("" if len(saisis) == len(fr.ELEMENTS)
                                                     else " (قيم افتراضية: صحّحها في «تهيئة مبالغ التسجيل»)"))
            self.l_milieu.setObjectName("etiquette")
        self.l_milieu.style().unpolish(self.l_milieu)
        self.l_milieu.style().polish(self.l_milieu)
        actuel = self.unite.currentData()
        self.unite.blockSignals(True)
        self.unite.clear()
        self.unite.addItem("المؤسسة كاملة", None)
        for u in etab_srv.unites(conn):
            self.unite.addItem(u, u)
        self.unite.setCurrentIndex(max(0, self.unite.findData(actuel)))
        self.unite.blockSignals(False)
        visible = self.unite.count() > 1
        self.unite.setVisible(visible)
        for l in self.findChildren(QLabel):
            if l.text() == "الوحدة المدرسية":
                l.setVisible(visible)
        self._remplir_classes()

    def _remplir_classes(self) -> None:
        actuel = self.classe.currentData()
        try:
            cls = fr.classes(self.f.conn, self.unite.currentData())
        except fr.ErreurFrais:
            cls = []
        self.classe.blockSignals(True)
        self.classe.clear()
        self.classe.addItem("كل الأقسام", None)
        for c in cls:
            self.classe.addItem(c, c)
        self.classe.setCurrentIndex(max(0, self.classe.findData(actuel)))
        self.classe.blockSignals(False)
        self.afficher()

    # ---- تهيئة المبالغ في نافذة منبثقة (طلب المدير 2026-11-19) ----
    def ouvrir_montants(self):
        from PySide6.QtWidgets import QFormLayout, QVBoxLayout

        from idara.ui.formulaires import champ
        from idara.ui.vitrine import FenetreFiche, bouton_couleur
        if not hasattr(self, "fiche_montants"):
            w = QWidget()
            v = QVBoxLayout(w)
            aide = QLabel("اكتب المبالغ بالدرهم لكل تلميذ، كما حددتها المؤسسة لهذه السنة.")
            aide.setObjectName("etiquette")
            aide.setWordWrap(True)
            v.addWidget(aide)
            fl = QFormLayout()
            self.c_montants = {}
            for k, lib in (("assurance", "قيمة التأمين المدرسي"), ("sport", "الانخراط في الجمعية الرياضية"),
                           ("cooperative", "الانخراط في جمعية تنمية التعاون المدرسي")):
                c = champ("بالدرهم", ltr=True)
                c.setMaximumWidth(160)
                self.c_montants[k] = c
                fl.addRow(lib, c)
            v.addLayout(fl)
            b = bouton_couleur("حفظ المبالغ", "#EF6C00", "enregistrer")
            b.clicked.connect(lambda: self.enregistrer_montants())
            v.addWidget(b, 0, Qt.AlignLeft)
            self.message_montants = QLabel()
            self.message_montants.setWordWrap(True)
            self.message_montants.hide()
            v.addWidget(self.message_montants)
            self.fiche_montants = FenetreFiche(self, "تهيئة مبالغ التسجيل", "", w, largeur=560)
        m = fr.montants(self.f.conn)
        for k, c in self.c_montants.items():
            c.setText("" if m[k] is None else f"{m[k]:g}")
        self.message_montants.hide()
        self.fiche_montants.ouvrir()
        return self.fiche_montants

    def enregistrer_montants(self) -> bool:
        try:
            fr.definir_montants(self.f.conn, {k: c.text() for k, c in self.c_montants.items()})
        except fr.ErreurFrais as e:
            message(self.message_montants, str(e), True)
            return False
        self.fiche_montants.hide()
        self.rafraichir()
        message(self.message, "حُفظت مبالغ التسجيل، وتحيّن العدّاد.")
        return True

    # ---- وثيقة «مخرجات الواجبات المدرسية» في نافذة منبثقة (طلب المدير 2026-11-23) ----
    def ouvrir_releve(self):
        from PySide6.QtWidgets import QFormLayout, QVBoxLayout

        from idara.ui.vitrine import FenetreFiche, bouton_couleur
        if not hasattr(self, "fiche_releve"):
            w = QWidget()
            v = QVBoxLayout(w)
            fl = QFormLayout()
            self.c_portee = QComboBox(w)
            for k, lib in fr.PORTEES.items():
                self.c_portee.addItem(lib, k)
            self.c_portee.setCurrentIndex(1)
            self.c_classe_rel = QComboBox(w)
            self.c_portee.currentIndexChanged.connect(
                lambda _: self.c_classe_rel.setEnabled(self.c_portee.currentData() == "classe"))
            fl.addRow("النطاق", self.c_portee)
            fl.addRow("القسم", self.c_classe_rel)
            v.addLayout(fl)
            aide = QLabel("«حسب الأقسام»: سطر لكل قسم. «المؤسسة كاملة»: سطر لكل مستوى مع المجموع. "
                          "«قسم واحد»: لائحة تلاميذ القسم وما أدّاه كل واحد.")
            aide.setObjectName("etiquette")
            aide.setWordWrap(True)
            v.addWidget(aide)
            b = bouton_couleur("توليد الوثيقة", "#2E7D32", "document")
            b.clicked.connect(lambda: self.generer_releve())
            v.addWidget(b, 0, Qt.AlignLeft)
            self.message_releve = QLabel()
            self.message_releve.setWordWrap(True)
            self.message_releve.hide()
            v.addWidget(self.message_releve)
            self.fiche_releve = FenetreFiche(self, "مخرجات الواجبات المدرسية", "الواجبات المتحصل عليها هذه السنة.",
                                             w, largeur=560)
        self.c_classe_rel.clear()
        try:
            for c in fr.classes(self.f.conn, self.unite.currentData()):
                self.c_classe_rel.addItem(c, c)
        except fr.ErreurFrais:
            pass
        if self.classe.currentData():
            self.c_classe_rel.setCurrentIndex(max(0, self.c_classe_rel.findData(self.classe.currentData())))
        self.c_classe_rel.setEnabled(self.c_portee.currentData() == "classe")
        self.message_releve.hide()
        self.fiche_releve.ouvrir()
        return self.fiche_releve

    def generer_releve(self, portee: str | None = None, classe: str | None = None):
        from idara.services import bureautique
        portee = portee or self.c_portee.currentData()
        classe = classe or (self.c_classe_rel.currentData() if portee == "classe" else None)
        try:
            p = fr.generer_releve(self.f.conn, self.f.dossier, portee, classe, self.unite.currentData())
        except fr.ErreurFrais as e:
            message(self.message_releve, str(e), True)
            return None
        self.fiche_releve.hide()
        message(self.message, f"وُلّدت الوثيقة: ⁦{p.name}⁩")
        try:
            bureautique.ouvrir(p)
        except OSError:
            pass
        return p

    def afficher(self) -> None:
        try:
            self.liste = fr.lister(self.f.conn, unite=self.unite.currentData(), classe=self.classe.currentData())
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
        t = fr.totaux(self.f.conn, unite=self.unite.currentData(), classe=self.classe.currentData())
        self.totaux = t
        while self.grille.count():
            w = self.grille.takeAt(0).widget()
            if w:
                w.hide()
                w.setParent(None)
                w.deleteLater()
        for i, (k, e) in enumerate(t["elements"].items()):
            mt = "—" if e["montant"] is None else f"{e['montant']:g} درهم"
            self.grille.addWidget(Tuile(e["libelle"], mt, COULEURS[k], "التدبير المالي والمادي",
                                        f"{e['payes']} / {t['eleves']} تلميذاً"), 0, i)
        self.grille.addWidget(Tuile("المجموع التراكمي لكل العناصر", f"{t['total']:g} درهم", theme.ORANGE,
                                    "التدبير المالي والمادي", f"{t['eleves']} تلميذاً في اللائحة"), 1, 0, 1, 3)
