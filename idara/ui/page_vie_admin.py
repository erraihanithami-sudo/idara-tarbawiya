"""صفحات: الوثائق القانونية للجمعيات، جدول الحراسة، النقل المدرسي، استعمالات الزمن (2026-11-13)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QGridLayout, QHBoxLayout, QLabel,
                               QLineEdit, QPlainTextEdit, QPushButton, QSpinBox, QStyledItemDelegate,
                               QTableWidgetItem, QVBoxLayout, QWidget)

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
        self.carte_asso = c
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
        racine.addWidget(c)
        # توجيه المدير 2026-11-23: المعطيات والأعضاء في نوافذ منبثقة، والصفحة للجمعية ووثائقها
        from idara.ui.vitrine import bouton_couleur, en_fenetre
        lay = racine
        lay.removeWidget(self.carte_asso)
        cl = self.carte_asso.layout()
        cl.removeWidget(self.asso)
        self.fiche_asso = en_fenetre(self, self.carte_asso, "معطيات الجمعية والجمع العام", "", 980, ("enregistrer",))
        self.fiche_bureau = en_fenetre(self, c, "أعضاء المكتب", "", 1000, ("enregistrer",))
        b2 = QPushButton("حفظ")
        b2.setObjectName("principal")
        b2.clicked.connect(lambda: self.enregistrer(True))
        cl.addWidget(b2, 0, Qt.AlignLeft)
        c, v = carte("الجمعية ووثائقها")
        v.addWidget(self.asso)
        h = QHBoxLayout()
        for lib, fi, coul, pic in (("معطيات الجمعية والجمع العام", self.fiche_asso, "#1565C0", "modifier"),
                                   ("أعضاء المكتب", self.fiche_bureau, "#2E7D32", "personnes")):
            b = bouton_couleur(lib, coul, pic)
            b.clicked.connect(lambda _=False, fi=fi: fi.ouvrir())
            h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        self.l_bureau = QLabel()
        self.l_bureau.setObjectName("etiquette")
        self.l_bureau.setWordWrap(True)
        v.addWidget(self.l_bureau)
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
        if hasattr(self, "l_bureau"):
            ms = [m for m in d["membres"] if any(m)]
            self.l_bureau.setText("أعضاء المكتب: " + "، ".join(
                f"{m[0]} ({m[1]})" if len(m) > 1 and m[1] else str(m[0]) for m in ms) if ms else
                "لم يُسجَّل أعضاء المكتب بعد.")

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
        v.addWidget(self.l_jour)   # للاطلاع فقط: جدول الأسابيع الأربعة يكفي للطبع (طلب المدير 2026-11-19)
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
        # شرح المناطق في نافذة منبثقة، ويُدرج مفتاحاً أسفل كل جدول (طلب المدير 2026-11-20)
        from idara.ui.vitrine import FenetreFiche, bouton_couleur
        hz = QHBoxLayout()
        self.b_zones = bouton_couleur("شرح المناطق", "#00897B", "modifier",
                                      "منطقة 01: الباب الرئيسي، منطقة 02: الساحة الشمالية…")
        self.b_zones.clicked.connect(lambda: self.ouvrir_zones())
        hz.addWidget(self.b_zones)
        self.l_cle = QLabel()
        self.l_cle.setObjectName("etiquette")
        self.l_cle.setWordWrap(True)
        hz.addWidget(self.l_cle, 1)
        v.addLayout(hz)
        racine.addWidget(c)
        self.carte_config = c
        wz = QWidget()
        vz = QVBoxLayout(wz)
        az = QLabel("اكتب شرح كل منطقة (عدد المناطق تحدده أنت في «عدد المناطق»). الشرح يظهر مفتاحاً أسفل كل "
                    "جدول حراسة مطبوع، وفي مذكرة الحراسة.")
        az.setObjectName("etiquette")
        az.setWordWrap(True)
        vz.addWidget(az)
        self.t_zones = TableauRapide(0, 1)
        self.t_zones.setHorizontalHeaderLabels(["شرح المنطقة: الباب الرئيسي، الساحة الشمالية، المراحيض..."])
        self.t_zones.horizontalHeader().setStretchLastSection(True)
        self.t_zones.verticalHeader().setVisible(True)
        self.t_zones.setEditTriggers(QAbstractItemView.AllEditTriggers)
        self.t_zones.setMinimumHeight(260)
        vz.addWidget(self.t_zones)
        bz = bouton_couleur("حفظ شرح المناطق", "#00897B", "enregistrer")
        bz.clicked.connect(lambda: self.enregistrer_zones())
        vz.addWidget(bz, 0, Qt.AlignLeft)
        self.fiche_zones = FenetreFiche(self, "شرح مناطق الحراسة", "", wz, largeur=640)

        c, v = carte("الجدول: الأستاذ(ة) المكلف(ة) أمام كل منطقة")
        h = QHBoxLayout()
        self.pilules = QHBoxLayout()
        h.addLayout(self.pilules)
        h.addStretch()
        b = QPushButton("توزيع آلي عادل")
        b.setToolTip("يملأ كل أسابيع الدورة بأساتذة المؤسسة النشيطين، دوراً بعد دور")
        b.clicked.connect(lambda: self.repartir())
        h.addWidget(b)
        self.b_annuler_rep = bouton("إلغاء التوزيع")
        self.b_annuler_rep.setToolTip("يفرغ خانات الأساتذة في كل أسابيع الدورة (المناطق والأيام تبقى)")
        self.b_annuler_rep.clicked.connect(lambda: self.annuler_repartition())
        h.addWidget(self.b_annuler_rep)
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
        self.consignes.setFixedHeight(220)
        # توجيه المدير 2026-11-23: الإعداد والمقتضيات في نوافذ منبثقة
        from idara.ui.vitrine import en_fenetre
        wc = QWidget()
        vc = QVBoxLayout(wc)
        vc.addWidget(etiquette("مقتضيات المذكرة الداخلية (سطر لكل مقتضى)", self.consignes))
        vc.addWidget(self.consignes)
        bc = QPushButton("حفظ")
        bc.setObjectName("principal")
        bc.clicked.connect(lambda: self.enregistrer(True))
        vc.addWidget(bc, 0, Qt.AlignLeft)
        self.fiche_consignes = en_fenetre(self, wc, "مقتضيات المذكرة الداخلية", "", 760, ("enregistrer",))
        self.fiche_config = en_fenetre(self, self.carte_config, "المناطق والدورة",
                                       "عدد المناطق وأسابيع الدورة وبدايتها وأيام الحراسة؛ الجدول يتكيف مباشرة.", 900)
        bok = QPushButton("تم")
        bok.setObjectName("principal")
        bok.clicked.connect(lambda: self.fiche_config.hide())
        self.fiche_config.layout().addWidget(bok, 0, Qt.AlignLeft)
        h = QHBoxLayout()
        for lib, fn, coul, pic in (("المناطق والدورة", lambda: self.fiche_config.ouvrir(), "#1565C0", "modifier"),
                                   ("مقتضيات المذكرة الداخلية", lambda: self.fiche_consignes.ouvrir(), "#6A1B9A",
                                    "document")):
            bb = bouton_couleur(lib, coul, pic)
            bb.clicked.connect(fn)
            h.addWidget(bb)
        b = QPushButton("حفظ الجدول")
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
        self.t_zones.setVerticalHeaderLabels([gd.libelle_zone(self.g["zones"], k) for k in range(nz)])
        for k in range(nz):
            self.t_zones.setItem(k, 0, QTableWidgetItem(self.g["zones"][k]))
        cle = gd.cle_zones(self.g["zones"][:nz])
        self.l_cle.setText("مفتاح المناطق: " + " · ".join(f"{a}: {b}" for a, b in cle) if cle
                           else "لم تُشرح المناطق بعد: «شرح المناطق».")

    def ouvrir_zones(self):
        self._zones()
        self.fiche_zones.ouvrir()
        return self.fiche_zones

    def enregistrer_zones(self) -> bool:
        if not self.enregistrer(True):
            return False
        self.fiche_zones.hide()
        self._zones()
        self._remplir()
        return True

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
        for k in range(nz):
            if self.g["zones"][k] and self.table.horizontalHeaderItem(k):
                self.table.horizontalHeaderItem(k).setToolTip(self.g["zones"][k])
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

    def annuler_repartition(self) -> bool:
        """طلب المدير 2026-11-19: إلغاء التوزيع (آلياً كان أو يدوياً) وحفظ الجدول فارغاً."""
        self._lire_ecran()
        self.g["grille"] = gd._grille_vide(self.g["semaines"], self.g["jours"], self.g["nb_zones"])
        self._remplir()
        if not self.enregistrer():
            return False
        message(self.message, "أُلغي توزيع الأساتذة على المناطق.")
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
        bsv = QPushButton("حفظ")
        bsv.setObjectName("principal")
        bsv.clicked.connect(lambda: self.enregistrer(True))
        h.addWidget(bsv)
        _boutons_lignes(h, self.t_veh)
        h.addStretch()
        v.addLayout(h)
        racine.addWidget(c)
        self.carte_veh = c
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
        h.addStretch()
        v.addLayout(h)
        racine.addWidget(c)
        # توجيه المدير 2026-11-23: الإدخال في نوافذ منبثقة، والصفحة للحصيلة والوثائق
        from idara.ui.vitrine import bouton_couleur, en_fenetre
        self.fiche_veh = en_fenetre(self, self.carte_veh, "وسائل النقل", "رقم الوسيلة ونوعها وسائقها ومسارها.", 1000,
                                    ("enregistrer",))
        self.fiche_el = en_fenetre(self, c, "المستفيدون من النقل المدرسي", "", 1000, ("enregistrer",))
        c, v = carte("النقل المدرسي")
        h = QHBoxLayout()
        for lib, fi, coul, pic in (("وسائل النقل", self.fiche_veh, "#1565C0", "modifier"),
                                   ("المستفيدون", self.fiche_el, "#2E7D32", "personnes")):
            b = bouton_couleur(lib, coul, pic)
            b.clicked.connect(lambda _=False, fi=fi: fi.ouvrir())
            h.addWidget(b)
        b = QPushButton("لوائح المستفيدين وإحصاء الدواوير")
        b.setObjectName("principal")
        b.clicked.connect(lambda: self.generer())
        h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        self.stats = QLabel()
        self.stats.setObjectName("etiquette")
        self.stats.setWordWrap(True)
        v.addWidget(self.stats)
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

COUL_MATIERES = {"اللغة العربية": "#00897B", "اللغة الفرنسية": "#3949AB", "اللغة الأمازيغية": "#8D6E63",
                 "الرياضيات": "#E65100", "النشاط العلمي": "#2E7D32", "التربية الإسلامية": "#00695C",
                 "الاجتماعيات": "#6D4C41", "التربية الفنية": "#AD1457", "التربية البدنية": "#C62828",
                 "اللغة الإنجليزية": "#1565C0", "الدعم ومعالجة التعثرات": "#6A1B9A", "أنشطة الحياة المدرسية": "#F9A825"}


def couleur_matiere(m: str) -> str:
    if m in COUL_MATIERES:
        return COUL_MATIERES[m]
    palette = ("#5E35B1", "#00838F", "#7CB342", "#D81B60", "#FB8C00", "#546E7A")
    return palette[sum(map(ord, m)) % len(palette)]


class GrilleSemaine(QWidget):
    """استعمال زمن أستاذ مرسوماً: الأيام صفوفاً، والوقت من 08:00 إلى 18:00، وكل حصة كتلة بلون مادتها."""

    def __init__(self):
        super().__init__()
        self.seances: list[list[str]] = []
        self.setMinimumSize(760, 420)

    def definir(self, seances) -> None:
        self.seances = seances
        self.update()

    def paintEvent(self, ev):   # noqa: N802
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        W, H = self.width(), self.height()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#FFFFFF"))
        p.drawRoundedRect(QRectF(0, 0, W, H), 16, 16)
        gauche, droite_j, haut = 14, 92, 34
        debut, fin = 8 * 60, 18 * 60
        larg = W - gauche - droite_j - 10
        hl = (H - haut - 12) / len(va.JOURS)
        f = QFont()
        f.setPointSizeF(8.5)
        p.setFont(f)
        for h in range(8, 19):
            x = gauche + larg - (h * 60 - debut) / (fin - debut) * larg   # RTL: الصباح يمين
            p.setPen(QPen(QColor("#E3E8EE"), 1, Qt.DashLine if h % 2 else Qt.SolidLine))
            p.drawLine(int(x), haut, int(x), H - 10)
            p.setPen(QColor("#78909C"))
            p.drawText(QRectF(x - 24, 6, 48, 20), Qt.AlignCenter, f"{h:02d}:00")
        for k, j in enumerate(va.JOURS):
            y = haut + k * hl
            if k % 2 == 0:
                p.fillRect(QRectF(gauche, y, larg, hl), QColor("#F6F8FB"))
            fb = QFont(f)
            fb.setBold(True)
            fb.setPointSizeF(10)
            p.setFont(fb)
            p.setPen(QColor("#1F3B57"))
            p.drawText(QRectF(W - droite_j, y, droite_j - 8, hl), Qt.AlignRight | Qt.AlignVCenter, j)
        for s in self.seances:
            try:
                k = va.JOURS.index(s[0])
                a, b = va._minutes(s[1]), va._minutes(s[2])
            except (ValueError, va.ErreurVieAdmin):
                continue
            x1 = gauche + larg - (min(b, fin) - debut) / (fin - debut) * larg
            x2 = gauche + larg - (max(a, debut) - debut) / (fin - debut) * larg
            r = QRectF(x1 + 2, haut + k * hl + 5, max(8.0, x2 - x1 - 4), hl - 10)
            c = QColor(couleur_matiere(s[3]))
            g = QLinearGradient(r.topRight(), r.bottomLeft())
            g.setColorAt(0, c.lighter(115))
            g.setColorAt(1, c.darker(115))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 0, 0, 35))
            p.drawRoundedRect(r.translated(1.5, 2.5), 9, 9)
            p.setBrush(g)
            p.drawRoundedRect(r, 9, 9)
            p.setPen(QColor("#FFFFFF"))
            fs = QFont(f)
            fs.setBold(True)
            p.setFont(fs)
            p.drawText(r.adjusted(5, 3, -5, -3), Qt.AlignCenter | Qt.TextWordWrap,
                       f"{s[3]}\n{s[1]}–{s[2]}" + (f" · {s[4]}" if s[4] else ""))
        p.end()


class PageEmplois(QWidget):
    """استعمالات الزمن (طلب المدير 2026-11-19): الصفحة تعرض استعمال الزمن الجماعي أو لائحة الأساتذة (قائمة منسدلة
    لنمط العرض)، وأمام كل أستاذ زر لعرض استعماله وزر لمسكه؛ المسك والحصيص في نوافذ منبثقة."""

    def __init__(self, fenetre):
        super().__init__()
        from idara.ui.vitrine import CarteFiltre, FenetreFiche, bouton_couleur, grille_cartes
        self.f = fenetre
        self.pid: int | None = None
        racine, self.message = _page("استعمالات الزمن", "")
        self.setLayout(racine)
        # ---- البطاقات ----
        self.cartes = {
            "profs": CarteFiltre("profs", "الأساتذة", "#1565C0", "personnes", " "),
            "saisis": CarteFiltre("saisis", "استعمالات ممسوكة", "#2E7D32", "valider", " "),
            "sans": CarteFiltre("sans", "دون استعمال زمن", "#EF8A00", "rappel", " "),
            "seances": CarteFiltre("seances", "الحصص الأسبوعية", "#6A1B9A", "calendrier", " "),
        }
        for k, c_ in self.cartes.items():
            c_.clique.connect(self.filtrer)
        racine.addLayout(grille_cartes(list(self.cartes.values()), 4))
        h = QHBoxLayout()
        h.setSpacing(12)
        h.addWidget(QLabel("نمط العرض:"))
        self.mode = QComboBox()
        self.mode.addItem("لائحة الأساتذة", "liste")
        self.mode.addItem("استعمال الزمن الجماعي", "collectif")
        self.mode.setMinimumWidth(220)
        self.mode.currentIndexChanged.connect(lambda _: self._afficher())
        h.addWidget(self.mode)
        h.addStretch()
        self.b_quotas = bouton_couleur("الحصيص الأسبوعي للمواد", "#6A1B9A", "statistiques",
                                       "عدد الدقائق الأسبوعي لكل مادة، لمراقبة استعمالات الزمن")
        self.b_quotas.clicked.connect(lambda: self.ouvrir_quotas())
        h.addWidget(self.b_quotas)
        racine.addLayout(h)
        self.filtre: str | None = None
        # ---- لائحة الأساتذة ----
        self.c_liste, v = carte()
        self.titre_liste = QLabel()
        self.titre_liste.setObjectName("titreCarte")
        v.addWidget(self.titre_liste)
        self.liste = tableau(["الأستاذ(ة)", "التدريس", "الحصص", "المجموع الأسبوعي", "المراقبة", "الإجراءات"], etirer=4)
        self.liste.setMinimumHeight(320)
        self.liste.verticalHeader().setDefaultSectionSize(46)
        self.liste.itemDoubleClicked.connect(lambda it: self.voir(self.liste.item(it.row(), 0).data(Qt.UserRole)))
        v.addWidget(self.liste)
        racine.addWidget(self.c_liste)
        # ---- الجماعي ----
        self.c_coll, v = carte("استعمال الزمن الجماعي: فترتا الصباح والمساء لكل أستاذ")
        cols = ["الأستاذ(ة)"] + [f"{j} {x}" for j in va.JOURS for x in ("ص", "م")]
        self.collectif = tableau(cols, etirer=0)
        self.collectif.setMinimumHeight(340)
        v.addWidget(self.collectif)
        racine.addWidget(self.c_coll)
        racine.addStretch()

        # ---- نافذة المسك ----
        w = QWidget()
        wv = QVBoxLayout(w)
        wv.setSpacing(12)
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
        b = bouton_couleur("حفظ", "#1565C0", "enregistrer")
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
        b = bouton_couleur("توليد استعمال الزمن", "#2E7D32", "document")
        b.clicked.connect(lambda: self.generer())
        h.addWidget(b)
        v.addLayout(h)
        wv.addWidget(c)
        c, v = carte("مراقبة الحصيص الأسبوعي")
        self.total = QLabel()
        self.total.setObjectName("titreCarte")
        v.addWidget(self.total)
        self.t_ctrl = tableau(["المادة", "المنجز (دقيقة)", "الحصيص (دقيقة)", "الملاحظة"], etirer=3)
        self.t_ctrl.setMinimumHeight(180)
        v.addWidget(self.t_ctrl)
        wv.addWidget(c)
        self.message_fiche = QLabel()
        self.message_fiche.setWordWrap(True)
        self.message_fiche.hide()
        wv.addWidget(self.message_fiche)
        self.fiche = FenetreFiche(self, "مسك استعمال الزمن", "", w, largeur=1000)
        # ---- نافذة العرض ----
        w = QWidget()
        wv = QVBoxLayout(w)
        self.l_vue = QLabel()
        self.l_vue.setObjectName("titreCarte")
        wv.addWidget(self.l_vue)
        self.grille_vue = GrilleSemaine()
        wv.addWidget(self.grille_vue, 1)
        h = QHBoxLayout()
        b = bouton_couleur("تعديل الحصص", "#1565C0", "modifier")
        b.clicked.connect(lambda: self.saisir(self.pid))
        h.addWidget(b)
        b = bouton_couleur("توليد الوثيقة", "#2E7D32", "document")
        b.clicked.connect(lambda: self.generer())
        h.addWidget(b)
        h.addStretch()
        wv.addLayout(h)
        self.fiche_vue = FenetreFiche(self, "استعمال الزمن", "", w, largeur=1040)
        # ---- نافذة الحصيص ----
        w = QWidget()
        wv = QVBoxLayout(w)
        aide = QLabel("عدد الدقائق الأسبوعي لكل مادة حسب المستوى الدراسي والمنهاج المعتمد عندكم. المستوى الذي لا تُدخل "
                      "له حصيصاً يأخذ «الحصيص العام». البرنامج لا يفترض أي حصيص: المادة دون حصيص لا تُراقب.")
        aide.setObjectName("etiquette")
        aide.setWordWrap(True)
        wv.addWidget(aide)
        hq = QHBoxLayout()
        hq.addWidget(QLabel("المستوى:"))
        self.niveau_quota = QComboBox()
        self.niveau_quota.addItem("الحصيص العام (كل المستويات)", None)
        for n in va.NIVEAUX_QUOTAS:
            self.niveau_quota.addItem(f"المستوى {tx.niveau_ar(n)}", n)
        self.niveau_quota.currentIndexChanged.connect(lambda _: self._charger_quotas())
        hq.addWidget(self.niveau_quota)
        self.l_niveau_quota = QLabel()
        self.l_niveau_quota.setObjectName("etiquette")
        hq.addWidget(self.l_niveau_quota, 1)
        wv.addLayout(hq)
        self.t_quotas = _grille(("المادة", "الدقائق في الأسبوع"), 260)
        wv.addWidget(self.t_quotas)
        h = QHBoxLayout()
        b = bouton_couleur("حفظ الحصيص", "#6A1B9A", "enregistrer")
        b.clicked.connect(lambda: self.enregistrer_quotas())
        h.addWidget(b)
        _boutons_lignes(h, self.t_quotas)
        h.addStretch()
        wv.addLayout(h)
        self.fiche_quotas = FenetreFiche(self, "الحصيص الأسبوعي للمواد", "", w, largeur=640)
        self.rafraichir()

    def _profs(self):
        return [p for p in rh.lister(self.f.conn) if p.categorie in ("enseignant", "educatrice")]

    def filtrer(self, k: str) -> None:
        self.filtre = None if k == self.filtre or k in ("profs", "seances") else k
        self.mode.setCurrentIndex(0)
        self._afficher()

    def _afficher(self) -> None:
        from idara.ui import pictos
        from idara.ui.vitrine import icone_triangle, info_bulle
        profs = self._profs()
        donnees = []
        for p in profs:
            ss = va.lire_emploi(self.f.conn, p.id)
            try:
                c_ = va.controle_emploi(self.f.conn, p.id)
            except va.ErreurVieAdmin:
                c_ = {"heures": "—", "matieres": [], "seances": len(ss)}
            donnees.append((p, ss, c_))
        n_saisis = sum(1 for _, ss, _ in donnees if ss)
        self.cartes["profs"].definir(len(profs))
        self.cartes["saisis"].definir(n_saisis)
        self.cartes["sans"].definir(len(profs) - n_saisis)
        sans = [f"{p.prenom_ar} {p.nom_ar}" for p, ss, _ in donnees if not ss]
        self.cartes["sans"].definir_alerte("\n".join(["دون استعمال زمن:"] + sans) if sans else "")
        self.cartes["seances"].definir(sum(len(ss) for _, ss, _ in donnees))
        for k, c_ in self.cartes.items():
            c_.definir_actif(k == self.filtre)
        coll = self.mode.currentData() == "collectif"
        self.c_liste.setVisible(not coll)
        self.c_coll.setVisible(coll)
        lignes = [d for d in donnees if self.filtre is None or (self.filtre == "saisis") == bool(d[1])]
        self.titre_liste.setText(f"أساتذة المؤسسة ({len(lignes)})")
        from idara.ui.vitrine import vider_colonne_widgets
        vider_colonne_widgets(self.liste, 5)
        self.liste.setRowCount(len(lignes))
        for i, (p, ss, c_) in enumerate(lignes):
            it = _item(f"{p.prenom_ar} {p.nom_ar}", False, p.id)
            if not ss:
                it.setIcon(icone_triangle(18))
                it.setToolTip(info_bulle("لم يُمسك استعمال زمن هذا الأستاذ بعد"))
            self.liste.setItem(i, 0, it)
            ens = " · ".join(x for x in (p.matiere, p.niveau_enseigne) if x) or "—"
            depasse = [m for m in c_["matieres"] if m["etat"] and m["etat"] != "الحصيص مكتمل"]
            etat = "—" if not ss else ("؛ ".join(f"{m['matiere']}: {m['etat']}" for m in depasse) or "مطابق للحصيص")
            for j, x in enumerate((ens, str(len(ss)), c_["heures"] if ss else "—", etat), start=1):
                self.liste.setItem(i, j, _item(x, False))
            if depasse:
                self.liste.item(i, 4).setIcon(icone_triangle(16))
            from idara.ui.vitrine import boutons_ligne
            w = boutons_ligne([("عرض", "#3949AB", "apercu", lambda x=p.id: self.voir(x)),
                               ("مسك", "#2E7D32", "modifier", lambda x=p.id: self.saisir(x))])
            self.liste.setCellWidget(i, 5, w)
        from idara.ui.vitrine import ajuster_colonne_actions
        ajuster_colonne_actions(self.liste, 5)
        self.collectif.setRowCount(len(donnees))
        for i, (p, ss, _) in enumerate(donnees):
            self.collectif.setItem(i, 0, _item(f"{p.prenom_ar} {p.nom_ar}", False, p.id))
            dj = va.demi_journees(self.f.conn, p.id) if ss else {j: ["", ""] for j in va.JOURS}
            for k, x in enumerate(x for j in va.JOURS for x in dj[j]):
                it = _item(x, False)
                if x:
                    from PySide6.QtGui import QColor
                    it.setBackground(QColor("#E8F5E9" if k % 2 == 0 else "#E3F2FD"))
                self.collectif.setItem(i, k + 1, it)
        self.collectif.resizeColumnsToContents()

    def voir(self, pid: int):
        self.pid = pid
        p = next((x for x in self._profs() if x.id == pid), None)
        ss = va.lire_emploi(self.f.conn, pid)
        nom = f"{p.prenom_ar} {p.nom_ar}" if p else ""
        self.l_vue.setText(f"{nom} · {len(ss)} حصة" + (f" · {va.controle_emploi(self.f.conn, pid)['heures']}" if ss
                                                       else " · لم يُمسك بعد"))
        self.grille_vue.definir(ss)
        self.fiche_vue.definir_titre(f"استعمال الزمن: {nom}")
        self.fiche_vue.ouvrir()
        return self.fiche_vue

    def saisir(self, pid: int | None = None):
        self.fiche_vue.hide()
        if pid is not None:
            self.prof.setCurrentIndex(max(0, self.prof.findData(pid)))
        self.charger()
        self.message_fiche.hide()
        self.fiche.definir_titre(f"مسك استعمال الزمن: {self.prof.currentText()}")
        self.fiche.ouvrir()
        return self.fiche

    def ouvrir_quotas(self):
        self.fiche_quotas.ouvrir()
        return self.fiche_quotas

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
        self._charger_quotas()
        self.charger()
        self._afficher()

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
            message(self.message_fiche, str(e), True)
            return False
        _remplir(self.table, va.lire_emploi(self.f.conn, self.pid))
        self._controle()
        self._afficher()
        if afficher:
            message(self.message, "حُفظ استعمال الزمن.")
            message(self.message_fiche, "حُفظ استعمال الزمن.")
        return True

    def _charger_quotas(self) -> None:
        n = self.niveau_quota.currentData()
        propres = n in va.quotas_definis(self.f.conn) if n else True
        q = va.lire_quotas(self.f.conn, n) if propres else {}
        _remplir(self.t_quotas, [[m, str(q.get(m, ""))] for m in list(dict.fromkeys(list(va.MATIERES) + list(q)))])
        self.l_niveau_quota.setText("" if propres else "لا حصيص خاص بهذا المستوى: يأخذ الحصيص العام إلى أن تملأه.")

    def enregistrer_quotas(self) -> bool:
        try:
            va.enregistrer_quotas(self.f.conn, {l[0]: l[1] for l in _lire(self.t_quotas)},
                                  self.niveau_quota.currentData())
        except va.ErreurVieAdmin as e:
            message(self.message, str(e), True)
            return False
        self._controle()
        self._afficher()
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
