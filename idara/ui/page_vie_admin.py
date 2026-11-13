"""صفحات: الوثائق القانونية للجمعيات، جدول الحراسة، النقل المدرسي، استعمالات الزمن (2026-11-13)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPlainTextEdit, QPushButton, QTableWidgetItem, QWidget)

from idara.services import bureautique
from idara.services import personnel as rh
from idara.services import vie_admin as va
from idara.ui.composants import bouton, carte
from idara.ui.formulaires import etiquette
from idara.ui.page_pedagogie import _page
from idara.ui.saisie import ChampDate, TableauRapide, message, tableau


def _item(v: str, editable: bool = True, data=None) -> QTableWidgetItem:
    it = QTableWidgetItem(v)
    it.setTextAlignment(Qt.AlignCenter)
    if data is not None:
        it.setData(Qt.UserRole, data)
    if not editable:
        it.setFlags(it.flags() & ~Qt.ItemIsEditable)
    return it


def _grille(colonnes, hauteur: int = 300) -> TableauRapide:
    t = TableauRapide(0, len(colonnes))
    t.setHorizontalHeaderLabels(list(colonnes))
    t.setEditTriggers(QAbstractItemView.AllEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.horizontalHeader().setStretchLastSection(True)
    t.setMinimumHeight(hauteur)
    return t


def _remplir(t, lignes) -> None:
    t.setRowCount(len(lignes))
    for i, l in enumerate(lignes):
        for j, v in enumerate(l):
            t.setItem(i, j, _item(str(v)))


def _lire(t) -> list[list[str]]:
    t.setCurrentItem(None)
    return [[(t.item(i, j).text() if t.item(i, j) else "") for j in range(t.columnCount())]
            for i in range(t.rowCount())]


def _ajouter(t) -> None:
    n = t.rowCount()
    t.insertRow(n)
    for j in range(t.columnCount()):
        t.setItem(n, j, _item(""))
    t.setCurrentCell(n, 0)


def _supprimer(t) -> None:
    for r in sorted({i.row() for i in t.selectedIndexes()}, reverse=True):
        t.removeRow(r)


def _ouvrir(page, chemin, texte: str):
    message(page.message, f"{texte}: ⁦{chemin.name}⁩")
    try:
        bureautique.ouvrir(chemin)
    except OSError:
        pass
    return chemin


def _boutons_lignes(h, t) -> None:
    b = QPushButton("إضافة سطر")
    b.clicked.connect(lambda: _ajouter(t))
    h.addWidget(b)
    b = bouton("حذف الأسطر المحددة")
    b.clicked.connect(lambda: _supprimer(t))
    h.addWidget(b)


# ====================== الوثائق القانونية للجمعيات ======================

class PageAssoLegal(QWidget):
    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        racine, self.message = _page(
            "الوثائق القانونية للجمعيات",
            "أعضاء مكتب كل جمعية ومعطيات جمعها العام، ومنها: تصريح بتجديد المكتب، لائحة الأعضاء، محضر الجمع العام. "
            "الموقّع هو رئيس الجمعية. الصياغة عامة: راجعوها في Word قبل الإيداع لدى السلطة المحلية.")
        self.setLayout(racine)
        c, v = carte("الجمعية")
        self.asso = QComboBox()
        for k, lib in va.ASSOCIATIONS.items():
            self.asso.addItem(lib, k)
        self.asso.currentIndexChanged.connect(lambda _: self.charger())
        v.addWidget(self.asso)
        g = QGridLayout()
        g.setHorizontalSpacing(16)
        self.champs: dict[str, QWidget] = {}
        for k, (cle, lib) in enumerate(va.CHAMPS_ASSO):
            if cle in ("ordre", "deroulement"):
                w = QPlainTextEdit()
                w.setFixedHeight(80)
                g.addWidget(etiquette(lib, w), 4 + (0 if cle == "ordre" else 2), 0, 1, 3)
                g.addWidget(w, 5 + (0 if cle == "ordre" else 2), 0, 1, 3)
            else:
                w = ChampDate() if cle == "date_ag" else QLineEdit()
                g.addWidget(etiquette(lib, w), (k // 3) * 2, k % 3)
                g.addWidget(w, (k // 3) * 2 + 1, k % 3)
            self.champs[cle] = w
        v.addLayout(g)
        racine.addWidget(c)
        c, v = carte("أعضاء المكتب")
        self.table = _grille(va.COLS_BUREAU, 280)
        v.addWidget(self.table)
        h = QHBoxLayout()
        b = QPushButton("حفظ")
        b.setObjectName("principal")
        b.clicked.connect(lambda: self.enregistrer(True))
        h.addWidget(b)
        _boutons_lignes(h, self.table)
        self.personnel = QComboBox()
        h.addWidget(self.personnel)
        b = QPushButton("إضافة من لائحة العاملين")
        b.clicked.connect(self.ajouter_personnel)
        h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        h = QHBoxLayout()
        for cle, lib in va.DOCS_ASSO.items():
            b = QPushButton(f"{lib} (Word)")
            b.clicked.connect(lambda _=False, d=cle: self.generer(d))
            h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        racine.addWidget(c)
        racine.addStretch()
        self.cle: str | None = None
        self.rafraichir()

    def rafraichir(self) -> None:
        self.liste_personnel = va.personnel_pour_bureau(self.f.conn)
        self.personnel.clear()
        for l in self.liste_personnel:
            self.personnel.addItem(l[0])
        self.charger()

    def charger(self) -> None:
        if self.cle:
            self.enregistrer()
        self.cle = None
        cle = self.asso.currentData()
        d = va.lire_asso(self.f.conn, cle)
        for k, w in self.champs.items():
            v = d["champs"].get(k, "")
            if isinstance(w, ChampDate):
                w.definir(v or None)
            elif isinstance(w, QPlainTextEdit):
                w.setPlainText(v)
            else:
                w.setText(v)
        _remplir(self.table, d["membres"])
        self.cle = cle

    def donnees(self) -> dict:
        ch = {}
        for k, w in self.champs.items():
            if isinstance(w, ChampDate):
                try:
                    ch[k] = w.iso() or ""
                except ValueError:
                    ch[k] = ""
            else:
                ch[k] = w.toPlainText() if isinstance(w, QPlainTextEdit) else w.text()
        return {"champs": ch, "membres": _lire(self.table)}

    def enregistrer(self, afficher: bool = False) -> bool:
        if self.cle is None:
            return False
        va.enregistrer_asso(self.f.conn, self.cle, self.donnees())
        if afficher:
            message(self.message, f"حُفظت معطيات «{va.ASSOCIATIONS[self.cle]}».")
        return True

    def ajouter_personnel(self) -> None:
        i = self.personnel.currentIndex()
        if i < 0:
            return
        n = self.table.rowCount()
        self.table.insertRow(n)
        for j, v in enumerate(self.liste_personnel[i]):
            self.table.setItem(n, j, _item(v))

    def generer(self, doc: str):
        self.enregistrer()
        try:
            return _ouvrir(self, va.generer_asso(self.f.conn, self.f.dossier, self.cle, doc), "وُلّدت الوثيقة")
        except (va.ErreurVieAdmin, OSError) as e:
            message(self.message, str(e), True)
            return None


# ====================== جدول الحراسة ======================

class PageGarde(QWidget):
    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        racine, self.message = _page(
            "جدول الحراسة", "في كل خانة الأساتذة المكلفون بالحراسة (مفصولون بفاصلة). عناوين الفترات تُعدَّل بالنقر "
                            "المزدوج على رأس العمود.")
        self.setLayout(racine)
        c, v = carte("الحراسة حسب الأيام والفترات")
        self.table = TableauRapide(len(va.JOURS), 6)
        self.table.setVerticalHeaderLabels(list(va.JOURS))
        self.table.verticalHeader().setVisible(True)
        self.table.setEditTriggers(QAbstractItemView.AllEditTriggers)
        self.table.horizontalHeader().sectionDoubleClicked.connect(self.renommer)
        self.table.setMinimumHeight(300)
        v.addWidget(self.table)
        self.consignes = QPlainTextEdit()
        self.consignes.setFixedHeight(80)
        v.addWidget(etiquette("توجيهات (تُطبع أسفل الجدول)", self.consignes))
        v.addWidget(self.consignes)
        h = QHBoxLayout()
        b = QPushButton("حفظ")
        b.setObjectName("principal")
        b.clicked.connect(lambda: self.enregistrer(True))
        h.addWidget(b)
        b = QPushButton("توليد جدول الحراسة (Word)")
        b.clicked.connect(lambda: self.generer())
        h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        self.bilan = QLabel()
        self.bilan.setObjectName("etiquette")
        self.bilan.setWordWrap(True)
        v.addWidget(self.bilan)
        racine.addWidget(c)
        racine.addStretch()
        self.rafraichir()

    def rafraichir(self) -> None:
        g = va.lire_garde(self.f.conn)
        self.periodes = list(g["periodes"])
        self.table.setColumnCount(len(self.periodes))
        self.table.setHorizontalHeaderLabels(self.periodes)
        for i, j in enumerate(va.JOURS):
            for k, val in enumerate(g["grille"][j]):
                self.table.setItem(i, k, _item(val))
        self.consignes.setPlainText(g["consignes"])
        self._bilan()

    def _bilan(self) -> None:
        b = va.bilan_garde(self.f.conn)
        self.bilan.setText("عدد فترات الحراسة لكل أستاذ: " + " · ".join(f"{n} ({k})" for n, k in b) if b else "")

    def renommer(self, col: int, nom: str | None = None) -> None:
        if nom is None:
            from PySide6.QtWidgets import QInputDialog
            nom, ok = QInputDialog.getText(self, "فترة الحراسة", "عنوان الفترة:", text=self.periodes[col])
            if not ok:
                return
        if nom.strip():
            self.periodes[col] = nom.strip()
            self.table.setHorizontalHeaderLabels(self.periodes)

    def enregistrer(self, afficher: bool = False) -> bool:
        self.table.setCurrentItem(None)
        grille = {j: [(self.table.item(i, k).text() if self.table.item(i, k) else "")
                      for k in range(self.table.columnCount())] for i, j in enumerate(va.JOURS)}
        try:
            va.enregistrer_garde(self.f.conn, {"periodes": self.periodes, "grille": grille,
                                               "consignes": self.consignes.toPlainText()})
        except va.ErreurVieAdmin as e:
            message(self.message, str(e), True)
            return False
        self._bilan()
        if afficher:
            message(self.message, "حُفظ جدول الحراسة.")
        return True

    def generer(self):
        if not self.enregistrer():
            return None
        try:
            return _ouvrir(self, va.generer_garde(self.f.conn, self.f.dossier), "وُلّد جدول الحراسة")
        except (va.ErreurVieAdmin, OSError) as e:
            message(self.message, str(e), True)
            return None


# ====================== النقل المدرسي ======================

class PageTransport(QWidget):
    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        racine, self.message = _page(
            "النقل المدرسي", "وسائل النقل ومساراتها، والمستفيدون من لوائح التلاميذ، ولائحة لكل وسيلة وإحصاء الدواوير. "
                             "النقل تسيّره جمعيته، فوثائقه دون توقيع المدير.")
        self.setLayout(racine)
        c, v = carte("وسائل النقل")
        self.t_veh = _grille(va.COLS_VEHICULE, 170)
        v.addWidget(self.t_veh)
        h = QHBoxLayout()
        _boutons_lignes(h, self.t_veh)
        h.addStretch()
        v.addLayout(h)
        racine.addWidget(c)
        c, v = carte("المستفيدون")
        h = QHBoxLayout()
        self.recherche = QLineEdit()
        self.recherche.setPlaceholderText("بحث: اسم التلميذ أو القسم أو الدوار")
        self.recherche.textChanged.connect(self._filtrer)
        h.addWidget(self.recherche, 1)
        v.addLayout(h)
        self.t_el = tableau(["التلميذ(ة)", "القسم", "وسيلة النقل", "الدوار"], etirer=0)
        self.t_el.setEditTriggers(QAbstractItemView.AllEditTriggers)
        self.t_el.setMinimumHeight(360)
        v.addWidget(self.t_el)
        aide = QLabel("اكتب أمام التلميذ رقم وسيلة النقل كما في الجدول أعلاه، ودواره. الخانة الفارغة: غير مستفيد.")
        aide.setObjectName("etiquette")
        aide.setWordWrap(True)
        v.addWidget(aide)
        h = QHBoxLayout()
        b = QPushButton("حفظ")
        b.setObjectName("principal")
        b.clicked.connect(lambda: self.enregistrer(True))
        h.addWidget(b)
        b = QPushButton("لوائح المستفيدين وإحصاء الدواوير (Word)")
        b.clicked.connect(lambda: self.generer())
        h.addWidget(b)
        self.stats = QLabel()
        self.stats.setObjectName("etiquette")
        h.addWidget(self.stats, 1)
        v.addLayout(h)
        racine.addWidget(c)
        racine.addStretch()
        self.rafraichir()

    def rafraichir(self) -> None:
        t = va.lire_transport(self.f.conn)
        _remplir(self.t_veh, t["vehicules"])
        self.eleves = va.eleves_transport(self.f.conn)
        self.t_el.setRowCount(len(self.eleves))
        for i, x in enumerate(self.eleves):
            self.t_el.setItem(i, 0, _item(x["eleve"], False, x["eleve_id"]))
            self.t_el.setItem(i, 1, _item(x["classe"], False))
            self.t_el.setItem(i, 2, _item(x["vehicule"]))
            self.t_el.setItem(i, 3, _item(x["douar"]))
        st = va.stats_transport(self.f.conn)
        self.stats.setText(f"المستفيدون: {st['total']}" + ("".join(f" · {k}: {n}" for k, n in st["vehicules"].items())))
        self._filtrer()

    def _filtrer(self) -> None:
        t = self.recherche.text().strip()
        for i in range(self.t_el.rowCount()):
            ligne = " ".join(self.t_el.item(i, j).text() for j in range(4))
            self.t_el.setRowHidden(i, bool(t) and t not in ligne)

    def enregistrer(self, afficher: bool = False) -> bool:
        self.t_el.setCurrentItem(None)
        ben = {self.t_el.item(i, 0).data(Qt.UserRole): {"vehicule": self.t_el.item(i, 2).text(),
                                                         "douar": self.t_el.item(i, 3).text()}
               for i in range(self.t_el.rowCount())}
        try:
            va.enregistrer_transport(self.f.conn, {"vehicules": _lire(self.t_veh), "beneficiaires": ben})
        except va.ErreurVieAdmin as e:
            message(self.message, str(e), True)
            return False
        self.rafraichir()
        if afficher:
            message(self.message, "حُفظت معطيات النقل المدرسي.")
        return True

    def generer(self):
        if not self.enregistrer():
            return None
        try:
            return _ouvrir(self, va.generer_transport(self.f.conn, self.f.dossier), "وُلّدت لوائح النقل المدرسي")
        except (va.ErreurVieAdmin, OSError) as e:
            message(self.message, str(e), True)
            return None


# ====================== استعمالات الزمن ======================

class PageEmplois(QWidget):
    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        self.pid: int | None = None
        racine, self.message = _page(
            "استعمالات الزمن", "حصص كل أستاذ(ة): اليوم، من، إلى، المادة، المستوى. يراقب البرنامج التداخل والحصيص "
                               "الأسبوعي لكل مادة، ويغذي لوحة «استعمال الزمن الجماعي» في السبورة المرجعية.")
        self.setLayout(racine)
        c, v = carte("حصص الأستاذ(ة)")
        self.prof = QComboBox()
        self.prof.currentIndexChanged.connect(lambda _: self.charger())
        v.addWidget(self.prof)
        self.table = _grille(va.COLS_SEANCE, 320)
        v.addWidget(self.table)
        aide = QLabel("اليوم: " + "، ".join(va.JOURS) + ". التوقيت مثل 08:30. المادة من القائمة المقترحة أو كتابة حرة.")
        aide.setObjectName("etiquette")
        aide.setWordWrap(True)
        v.addWidget(aide)
        h = QHBoxLayout()
        b = QPushButton("حفظ")
        b.setObjectName("principal")
        b.clicked.connect(lambda: self.enregistrer(True))
        h.addWidget(b)
        self.jour = QComboBox()
        self.jour.addItems(list(va.JOURS))
        self.matiere = QComboBox()
        self.matiere.setEditable(True)
        self.matiere.addItems(list(va.MATIERES))
        h.addWidget(self.jour)
        h.addWidget(self.matiere)
        b = QPushButton("إضافة حصة")
        b.clicked.connect(self.ajouter)
        h.addWidget(b)
        b = bouton("حذف الأسطر المحددة")
        b.clicked.connect(lambda: _supprimer(self.table))
        h.addWidget(b)
        h.addStretch()
        b = QPushButton("توليد استعمال الزمن (Word)")
        b.clicked.connect(lambda: self.generer())
        h.addWidget(b)
        v.addLayout(h)
        racine.addWidget(c)
        c, v = carte("مراقبة الحصيص الأسبوعي")
        self.total = QLabel()
        self.total.setObjectName("titreCarte")
        v.addWidget(self.total)
        self.t_ctrl = tableau(["المادة", "المنجز (دقيقة)", "الحصيص (دقيقة)", "الملاحظة"], etirer=3)
        self.t_ctrl.setMinimumHeight(200)
        v.addWidget(self.t_ctrl)
        racine.addWidget(c)
        c, v = carte("الحصيص الأسبوعي للمواد")
        aide = QLabel("أدخلوا مرة واحدة عدد الدقائق الأسبوعي لكل مادة حسب المنهاج المعتمد عندكم. البرنامج لا يفترض "
                      "أي حصيص: المادة دون حصيص لا تُراقب.")
        aide.setObjectName("etiquette")
        aide.setWordWrap(True)
        v.addWidget(aide)
        self.t_quotas = _grille(("المادة", "الدقائق في الأسبوع"), 260)
        v.addWidget(self.t_quotas)
        h = QHBoxLayout()
        b = QPushButton("حفظ الحصيص")
        b.clicked.connect(lambda: self.enregistrer_quotas())
        h.addWidget(b)
        _boutons_lignes(h, self.t_quotas)
        h.addStretch()
        v.addLayout(h)
        racine.addWidget(c)
        racine.addStretch()
        self.rafraichir()

    def rafraichir(self) -> None:
        actuel = self.pid
        self.pid = None
        self.prof.blockSignals(True)
        self.prof.clear()
        for p in rh.lister(self.f.conn):
            if p.categorie in ("enseignant", "educatrice"):
                self.prof.addItem(f"{p.prenom_ar} {p.nom_ar}", p.id)
        self.prof.setCurrentIndex(max(0, self.prof.findData(actuel)))
        self.prof.blockSignals(False)
        q = va.lire_quotas(self.f.conn)
        _remplir(self.t_quotas, [[m, str(q.get(m, ""))] for m in list(dict.fromkeys(list(va.MATIERES) + list(q)))])
        self.charger()

    def charger(self) -> None:
        self.pid = self.prof.currentData()
        _remplir(self.table, va.lire_emploi(self.f.conn, self.pid) if self.pid else [])
        self._controle()

    def _controle(self) -> None:
        if not self.pid:
            self.total.setText("")
            self.t_ctrl.setRowCount(0)
            return
        c = va.controle_emploi(self.f.conn, self.pid)
        self.total.setText(f"المجموع الأسبوعي: {c['heures']} · {c['seances']} حصة")
        self.t_ctrl.setRowCount(len(c["matieres"]))
        for i, m in enumerate(c["matieres"]):
            for j, x in enumerate((m["matiere"], m["minutes"], "" if m["quota"] is None else m["quota"], m["etat"])):
                self.t_ctrl.setItem(i, j, _item(str(x), False))

    def ajouter(self) -> None:
        n = self.table.rowCount()
        self.table.insertRow(n)
        for j, v in enumerate((self.jour.currentText(), "", "", self.matiere.currentText(), "", "")):
            self.table.setItem(n, j, _item(v))
        self.table.setCurrentCell(n, 1)

    def enregistrer(self, afficher: bool = False) -> bool:
        if not self.pid:
            message(self.message, "لا أستاذ مسجل: أضف الأساتذة في الموارد البشرية أولاً.", True)
            return False
        try:
            va.enregistrer_emploi(self.f.conn, self.pid, _lire(self.table))
        except va.ErreurVieAdmin as e:
            message(self.message, str(e), True)
            return False
        _remplir(self.table, va.lire_emploi(self.f.conn, self.pid))
        self._controle()
        if afficher:
            message(self.message, "حُفظ استعمال الزمن.")
        return True

    def enregistrer_quotas(self) -> bool:
        try:
            va.enregistrer_quotas(self.f.conn, {l[0]: l[1] for l in _lire(self.t_quotas)})
        except va.ErreurVieAdmin as e:
            message(self.message, str(e), True)
            return False
        self._controle()
        message(self.message, "حُفظ الحصيص الأسبوعي.")
        return True

    def generer(self):
        if not self.enregistrer():
            return None
        try:
            return _ouvrir(self, va.generer_emploi(self.f.conn, self.f.dossier, self.pid), "وُلّد استعمال الزمن")
        except (va.ErreurVieAdmin, OSError) as e:
            message(self.message, str(e), True)
            return None
