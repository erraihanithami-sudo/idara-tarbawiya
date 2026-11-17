"""صفحات: الوثائق القانونية للجمعيات، جدول الحراسة، النقل المدرسي، استعمالات الزمن (2026-11-13)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QGridLayout, QHBoxLayout, QLabel,
                               QLineEdit, QPlainTextEdit, QPushButton, QSpinBox, QStyledItemDelegate,
                               QTableWidgetItem, QWidget)

from idara.services import bureautique
from idara.services import garde as gd
from idara.services import textes as tx
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
            b = QPushButton(f"{lib}")
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


# ====================== جدول الحراسة (بالمناطق، توجيه المدير 2026-11-15) ======================

class _DelegueProf(QStyledItemDelegate):
    """خانة الجدول: قائمة الأساتذة مع إمكان الكتابة الحرة."""

    def __init__(self, page):
        super().__init__(page)
        self.page = page

    def createEditor(self, parent, option, index):
        c = QComboBox(parent)
        c.setEditable(True)
        c.addItems([""] + [n for n, _ in self.page.profs])
        return c

    def setEditorData(self, editor, index):
        editor.setCurrentText(index.data() or "")

    def setModelData(self, editor, model, index):
        model.setData(index, " ".join(editor.currentText().split()))


class PageGarde(QWidget):
    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        self.g: dict = {}
        self.semaine = 1
        racine, self.message = _page(
            "جدول الحراسة", "قسّم المؤسسة إلى مناطق (من 1 إلى 10)، واختر دورة من 1 إلى 4 أسابيع: أمام كل منطقة "
                            "أستاذ(ة) في كل يوم. التوزيع الآلي يعدل بين الأساتذة ويناوب بينهم على المناطق.")
        self.setLayout(racine)

        self.c_jour, v = carte("حراسة اليوم")
        self.l_jour = QLabel()
        self.l_jour.setWordWrap(True)
        self.l_jour.setTextFormat(Qt.RichText)
        v.addWidget(self.l_jour)
        h = QHBoxLayout()
        b = QPushButton("طبع ورقة حراسة اليوم")
        b.clicked.connect(lambda: self.generer("jour"))
        h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        racine.addWidget(self.c_jour)

        c, v = carte("المناطق والدورة")
        self.nb_zones, self.semaines = QSpinBox(), QSpinBox()
        self.nb_zones.setRange(1, gd.ZONES_MAX)
        self.semaines.setRange(1, gd.SEMAINES_MAX)
        self.nb_zones.valueChanged.connect(lambda _: self._redimensionner())
        self.semaines.valueChanged.connect(lambda _: self._redimensionner())
        self.debut = ChampDate()
        self.debut.setToolTip("الاثنين الذي يبدأ فيه الأسبوع 1 من الدورة: منه يُحسب أسبوع اليوم")
        self.jours = {}
        hj = QHBoxLayout()
        for j in gd.JOURS:
            cb = QCheckBox(j)
            cb.toggled.connect(lambda _: self._redimensionner())
            self.jours[j] = cb
            hj.addWidget(cb)
        hj.addStretch()
        g = QGridLayout()
        g.setHorizontalSpacing(16)
        for k, (lib, w) in enumerate((("عدد المناطق", self.nb_zones), ("أسابيع الدورة", self.semaines),
                                      ("بداية الدورة (الأسبوع 1)", self.debut))):
            g.addWidget(etiquette(lib, w), 0, k)
            g.addWidget(w, 1, k)
        v.addLayout(g)
        v.addWidget(QLabel("أيام الحراسة:"))
        v.addLayout(hj)
        self.t_zones = TableauRapide(0, 1)
        self.t_zones.setHorizontalHeaderLabels(["تحديد المنطقة (اختياري): الباب الرئيسي، الساحة الشمالية..."])
        self.t_zones.horizontalHeader().setStretchLastSection(True)
        self.t_zones.verticalHeader().setVisible(True)
        self.t_zones.setEditTriggers(QAbstractItemView.AllEditTriggers)
        self.t_zones.setMaximumHeight(200)
        v.addWidget(self.t_zones)
        racine.addWidget(c)

        c, v = carte("الجدول: الأستاذ(ة) المكلف(ة) أمام كل منطقة")
        h = QHBoxLayout()
        self.pilules = QHBoxLayout()
        h.addLayout(self.pilules)
        h.addStretch()
        b = QPushButton("توزيع آلي عادل")
        b.setToolTip("يملأ كل أسابيع الدورة بأساتذة المؤسسة النشيطين، دوراً بعد دور")
        b.clicked.connect(lambda: self.repartir())
        h.addWidget(b)
        v.addLayout(h)
        self.table = TableauRapide(0, 0)
        self.table.verticalHeader().setVisible(True)
        self.table.setEditTriggers(QAbstractItemView.AllEditTriggers)
        self.table.setItemDelegate(_DelegueProf(self))
        self.table.setMinimumHeight(260)
        v.addWidget(self.table)
        self.bilan = QLabel()
        self.bilan.setObjectName("etiquette")
        self.bilan.setWordWrap(True)
        v.addWidget(self.bilan)
        self.consignes = QPlainTextEdit()
        self.consignes.setFixedHeight(120)
        v.addWidget(etiquette("مقتضيات المذكرة الداخلية (سطر لكل مقتضى)", self.consignes))
        v.addWidget(self.consignes)
        h = QHBoxLayout()
        b = QPushButton("حفظ")
        b.setObjectName("principal")
        b.clicked.connect(lambda: self.enregistrer(True))
        h.addWidget(b)
        for doc, lib in (("tableau", "جدول الحراسة"), ("note", "المذكرة الداخلية وتوقيعات الأساتذة")):
            b = QPushButton(lib)
            b.clicked.connect(lambda _=False, d=doc: self.generer(d))
            h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        racine.addWidget(c)
        racine.addStretch()
        self.rafraichir()

    # ---------- العرض ----------

    def rafraichir(self) -> None:
        self.profs = gd.enseignants(self.f.conn)
        self.g = gd.lire(self.f.conn)
        for w in (self.nb_zones, self.semaines, *self.jours.values()):
            w.blockSignals(True)
        self.nb_zones.setValue(self.g["nb_zones"])
        self.semaines.setValue(self.g["semaines"])
        for j, cb in self.jours.items():
            cb.setChecked(j in self.g["jours"])
        for w in (self.nb_zones, self.semaines, *self.jours.values()):
            w.blockSignals(False)
        self.debut.definir(self.g["debut"] or None)
        self.consignes.setPlainText(self.g["consignes"])
        self.semaine = min(self.semaine, self.g["semaines"])
        self._zones()
        self._pilules()
        self._remplir()
        self._bilan()
        self._jour()

    def _zones(self) -> None:
        nz = self.g["nb_zones"]
        self.t_zones.setRowCount(nz)
        self.t_zones.setVerticalHeaderLabels([f"المنطقة {k + 1}" for k in range(nz)])
        for k in range(nz):
            self.t_zones.setItem(k, 0, QTableWidgetItem(self.g["zones"][k]))

    def _pilules(self) -> None:
        while self.pilules.count():
            w = self.pilules.takeAt(0).widget()
            if w:
                w.deleteLater()
        self.b_semaines = {}
        for s in range(1, self.g["semaines"] + 1):
            b = QPushButton(f"الأسبوع {s}")
            b.setCheckable(True)
            b.setChecked(s == self.semaine)
            b.clicked.connect(lambda _=False, s=s: self.choisir_semaine(s))
            self.b_semaines[s] = b
            self.pilules.addWidget(b)

    def _remplir(self) -> None:
        nz, jours = self.g["nb_zones"], self.g["jours"]
        self.table.setColumnCount(nz)
        self.table.setHorizontalHeaderLabels([gd.libelle_zone(self.g["zones"], k) for k in range(nz)])
        self.table.setRowCount(len(jours))
        self.table.setVerticalHeaderLabels(jours)
        grille = self.g["grille"][str(self.semaine)]
        for i, j in enumerate(jours):
            for k in range(nz):
                self.table.setItem(i, k, _item(grille[j][k]))

    def _bilan(self) -> None:
        b = gd.bilan(self.f.conn)
        self.bilan.setText("أيام الحراسة لكل أستاذ(ة) خلال الدورة (المحفوظة): "
                           + " · ".join(f"{n} ({k})" for n, k in b) if b else "")

    def _jour(self) -> None:
        j = gd.du_jour(self.f.conn)
        titre = f"<b>{j['jour']} {tx.date_ar(j['date'])}</b>" + (
            f" · الأسبوع {j['semaine']} من الدورة" if j["semaine"] and self.g["semaines"] > 1 else "")
        if j["lignes"] and any(n for _, n in j["lignes"]):
            lignes = "".join(f"<br>&#8226; {z}: <b>{n or 'غير محدد'}</b>" for z, n in j["lignes"])
            self.l_jour.setText(titre + lignes)
        else:
            self.l_jour.setText(f"{titre}<br>{j['motif']}")
        self.jour = j

    # ---------- التعديل ----------

    def _lire_ecran(self) -> None:
        """ينقل ما على الشاشة إلى self.g (الأسبوع المعروض والمناطق والإعدادات)."""
        self.table.setCurrentItem(None)
        self.t_zones.setCurrentItem(None)
        if self.table.rowCount() and self.table.columnCount():
            grille = self.g["grille"].setdefault(str(self.semaine), {})
            for i in range(self.table.rowCount()):
                j = self.table.verticalHeaderItem(i).text()
                grille[j] = [self.table.item(i, k).text() if self.table.item(i, k) else ""
                             for k in range(self.table.columnCount())]
        self.g["zones"] = [self.t_zones.item(k, 0).text() if self.t_zones.item(k, 0) else ""
                           for k in range(self.t_zones.rowCount())]
        self.g["consignes"] = self.consignes.toPlainText()
        try:
            self.g["debut"] = self.debut.iso()
        except ValueError:
            self.g["debut"] = "؟"   # يرفضه الحفظ برسالة واضحة

    def _redimensionner(self) -> None:
        self._lire_ecran()
        jours = [j for j in gd.JOURS if self.jours[j].isChecked()] or [gd.JOURS[0]]
        self.g.update(nb_zones=self.nb_zones.value(), semaines=self.semaines.value(), jours=jours)
        self.g["zones"] = (self.g["zones"] + [""] * gd.ZONES_MAX)[:self.g["nb_zones"]]
        self.g["grille"] = gd._grille_vide(self.g["semaines"], jours, self.g["nb_zones"], self.g["grille"])
        self.semaine = min(self.semaine, self.g["semaines"])
        self._zones()
        self._pilules()
        self._remplir()

    def choisir_semaine(self, s: int) -> None:
        self._lire_ecran()
        self.semaine = s
        for k, b in self.b_semaines.items():
            b.setChecked(k == s)
        self._remplir()

    def repartir(self) -> bool:
        self._lire_ecran()
        try:
            self.g["grille"] = gd.repartir([n for n, _ in self.profs], self.g["nb_zones"], self.g["semaines"],
                                           self.g["jours"])
        except gd.ErreurGarde as e:
            message(self.message, str(e), True)
            return False
        self._remplir()
        message(self.message, "وُزّع الأساتذة على المناطق. راجع الجدول ثم احفظ.")
        return True

    def enregistrer(self, afficher: bool = False) -> bool:
        self._lire_ecran()
        try:
            gd.enregistrer(self.f.conn, self.g)
        except gd.ErreurGarde as e:
            message(self.message, str(e), True)
            return False
        self._bilan()
        self._jour()
        if afficher:
            message(self.message, "حُفظ جدول الحراسة.")
        return True

    def generer(self, doc: str = "tableau"):
        if not self.enregistrer():
            return None
        try:
            return _ouvrir(self, gd.generer(self.f.conn, self.f.dossier, doc), "وُلّدت " + gd.DOCS[doc])
        except (gd.ErreurGarde, OSError) as e:
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
        b = QPushButton("لوائح المستفيدين وإحصاء الدواوير")
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
        b = QPushButton("توليد استعمال الزمن")
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
