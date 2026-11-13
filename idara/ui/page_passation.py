"""صفحة «تسليم المهام» (نموذج المدير 2026-11-12): محاور المحضر، معطياتها المقترحة من البرنامج والمدخلة يدوياً،
وزر توليد المحضر على شكل النموذج."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QFileDialog, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget)

from idara.services import bureautique
from idara.services import passation as ps
from idara.ui.composants import bouton, carte, entete
from idara.ui.formulaires import etiquette
from idara.ui.saisie import ChampDate, TableauRapide, message


class PagePassation(QWidget):
    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        self.cle: str | None = None
        self.editeurs: dict[str, QLineEdit | QPlainTextEdit] = {}
        self._anciens: list[QWidget] = []
        racine = QVBoxLayout(self)
        racine.setContentsMargins(40, 32, 40, 32)
        racine.setSpacing(16)
        racine.addWidget(entete(
            "تسليم المهام",
            "محضر تسليم مهام الإدارة التربوية على شكل نموذجكم. ما يوجد في البرنامج يُقترح آلياً (المؤسسة، الموظفون، "
            "التلاميذ، السجلات، الجمعيات، المشروع)، والباقي يُدخل يدوياً مرة واحدة ويُحفظ."))
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.hide()
        racine.addWidget(self.message)

        # ---- المحضر ----
        c, v = carte("المحضر")
        self.date_pv = ChampDate()
        self.g_champs = {k.cle: QLineEdit() for k in ps.GENERAL if k.cle != "date_pv"}
        g = QGridLayout()
        g.setHorizontalSpacing(16)
        g.setVerticalSpacing(4)
        widgets = [("date_pv", self.date_pv)] + list(self.g_champs.items())
        lib = {k.cle: k.libelle for k in ps.GENERAL}
        for j, (k, w) in enumerate(widgets):
            g.addWidget(etiquette(lib[k], w), 0, j)
            g.addWidget(w, 1, j)
        v.addLayout(g)
        h = QHBoxLayout()
        self.b_generer = QPushButton("توليد المحضر (Word)")
        self.b_generer.setObjectName("principal")
        self.b_generer.clicked.connect(lambda: self.generer())
        h.addWidget(self.b_generer)
        h.addStretch()
        v.addLayout(h)
        racine.addWidget(c)

        corps = QHBoxLayout()
        corps.setSpacing(20)
        # ---- المحاور ----
        c, v = carte("محاور المحضر")
        aide = QLabel("أزل العلامة لإخفاء محور من المحضر، وغيّر موضعه بالسهمين.")
        aide.setObjectName("etiquette")
        aide.setWordWrap(True)
        v.addWidget(aide)
        self.liste = QListWidget()
        self.liste.setMinimumHeight(520)
        self.liste.currentItemChanged.connect(lambda cur, _: self._choisir(cur))
        self.liste.itemChanged.connect(self._coche)
        v.addWidget(self.liste, 1)
        h = QHBoxLayout()
        for txt, pas in (("▲ أعلى", -1), ("▼ أسفل", 1)):
            b = QPushButton(txt)
            b.clicked.connect(lambda _=False, p=pas: self.deplacer(p))
            h.addWidget(b)
        b = QPushButton("ترتيب النموذج")
        b.setToolTip("كل المحاور مدرجة، بترتيب نموذج المحضر")
        b.clicked.connect(self.retablir)
        h.addWidget(b)
        v.addLayout(h)
        # محور خاص يضيفه المدير (طلب 2026-11-13)
        h = QHBoxLayout()
        b = QPushButton("إضافة محور خاص…")
        b.clicked.connect(lambda: self.ajouter_section())
        h.addWidget(b)
        self.b_suppr_section = bouton("حذف المحور الخاص")
        self.b_suppr_section.clicked.connect(lambda: self.supprimer_section())
        h.addWidget(self.b_suppr_section)
        v.addLayout(h)
        corps.addWidget(c, 3)

        # ---- المحور المختار ----
        self.carte_ed, self.v_ed = carte()
        self.titre = QLabel()
        self.titre.setObjectName("titreCarte")
        self.v_ed.addWidget(self.titre)
        self.source = QLabel()
        self.source.setObjectName("etiquette")
        self.source.setWordWrap(True)
        self.v_ed.addWidget(self.source)
        self.zone = QVBoxLayout()
        self.v_ed.addLayout(self.zone)
        h = QHBoxLayout()
        self.b_ajouter = QPushButton("إضافة سطر")
        self.b_ajouter.clicked.connect(self.ajouter_ligne)
        self.b_supprimer = bouton("حذف الأسطر المحددة")
        self.b_supprimer.clicked.connect(self.supprimer_lignes)
        self.b_importer = QPushButton("استيراد لائحة من Excel")
        self.b_importer.clicked.connect(lambda: self.importer())
        self.b_actualiser = QPushButton("تحديث من البرنامج")
        self.b_actualiser.setToolTip("يعيد ما يأتي من البرنامج ويحتفظ بما أدخلتموه يدوياً")
        self.b_actualiser.clicked.connect(self.actualiser)
        self.b_enregistrer = QPushButton("حفظ")
        self.b_enregistrer.setObjectName("principal")
        self.b_enregistrer.clicked.connect(lambda: self.enregistrer(afficher=True))
        for b in (self.b_enregistrer, self.b_ajouter, self.b_supprimer, self.b_importer, self.b_actualiser):
            h.addWidget(b)
        h.addStretch()
        self.v_ed.addLayout(h)
        self.v_ed.addStretch()
        corps.addWidget(self.carte_ed, 7)
        racine.addLayout(corps, 1)
        self.table: TableauRapide | None = None
        self.rafraichir()

    # ---------- التحميل ----------

    def rafraichir(self) -> None:
        g = ps.lire(self.f.conn, "_general")["champs"]
        self.date_pv.definir(g.get("date_pv") or None)
        for k, w in self.g_champs.items():
            w.setText(g.get(k, ""))
        actuel = self.cle
        self.cle = None      # لا حفظ أثناء إعادة البناء
        self.liste.blockSignals(True)
        self.liste.clear()
        for s, actif in ps.sections(self.f.conn):
            it = QListWidgetItem(s.titre)
            it.setData(Qt.UserRole, s.cle)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if actif else Qt.Unchecked)
            self.liste.addItem(it)
        self.liste.blockSignals(False)
        cles = [self.liste.item(i).data(Qt.UserRole) for i in range(self.liste.count())]
        self.liste.setCurrentRow(cles.index(actuel) if actuel in cles else 0)

    def _choisir(self, it) -> None:
        if self.cle:
            self.enregistrer()
        if it is None:
            return
        self.afficher(it.data(Qt.UserRole))

    def afficher(self, cle: str, donnees: dict | None = None) -> None:
        s = ps.section(self.f.conn, cle)
        d = donnees or ps.lire(self.f.conn, cle)
        self.cle = None
        for w in self._anciens:
            w.hide()
            w.setParent(None)
            w.deleteLater()
        self._anciens = []
        self.editeurs = {}
        self.table = None
        self.titre.setText(s.titre)
        self.source.setText("المصدر: " + s.source)
        contenu = QWidget()
        v = QVBoxLayout(contenu)
        v.setContentsMargins(0, 0, 0, 0)
        if s.champs:
            g = QGridLayout()
            g.setHorizontalSpacing(16)
            g.setVerticalSpacing(4)
            r = 0
            courts = [c for c in s.champs if not c.long]
            for i, c in enumerate(courts):
                w = QLineEdit(d["champs"].get(c.cle, ""))
                self.editeurs[c.cle] = w
                g.addWidget(etiquette(c.libelle, w), (i // 2) * 2, i % 2)
                g.addWidget(w, (i // 2) * 2 + 1, i % 2)
                r = (i // 2) * 2 + 2
            for c in s.champs:
                if c.long:
                    w = QPlainTextEdit(d["champs"].get(c.cle, ""))
                    w.setFixedHeight(90)
                    self.editeurs[c.cle] = w
                    g.addWidget(etiquette(c.libelle, w), r, 0, 1, 2)
                    g.addWidget(w, r + 1, 0, 1, 2)
                    r += 2
            v.addLayout(g)
        if s.colonnes:
            t = TableauRapide(0, len(s.colonnes))
            t.setHorizontalHeaderLabels(list(s.colonnes))
            t.setEditTriggers(QAbstractItemView.AllEditTriggers)
            t.setSelectionBehavior(QAbstractItemView.SelectRows)
            t.horizontalHeader().setStretchLastSection(True)
            t.horizontalHeader().setSectionResizeMode(0, t.horizontalHeader().ResizeMode.Stretch)
            t.setRowCount(len(d["lignes"]))
            for i, l in enumerate(d["lignes"]):
                for j, val in enumerate(l):
                    t.setItem(i, j, self._item(val))
            t.setMinimumHeight(360)
            v.addWidget(t)
            self.table = t
        contenu.layout().activate()
        contenu.setMinimumHeight(contenu.layout().totalMinimumSize().height())
        self.zone.addWidget(contenu)
        self._anciens.append(contenu)
        tableau_ = bool(s.colonnes)
        for b in (self.b_ajouter, self.b_supprimer):
            b.setVisible(tableau_)
        self.b_importer.setVisible(s.deux_colonnes)
        self.b_actualiser.setVisible(cle in ps.AUTO)
        self.b_suppr_section.setEnabled(cle not in ps.PAR_CLE)
        self.cle = cle

    @staticmethod
    def _item(val: str):
        from PySide6.QtWidgets import QTableWidgetItem
        it = QTableWidgetItem(val)
        it.setTextAlignment(Qt.AlignCenter)
        return it

    def donnees(self) -> dict:
        champs = {k: (w.toPlainText() if isinstance(w, QPlainTextEdit) else w.text()) for k, w in self.editeurs.items()}
        lignes = []
        if self.table is not None:
            for i in range(self.table.rowCount()):
                lignes.append([(self.table.item(i, j).text() if self.table.item(i, j) else "")
                               for j in range(self.table.columnCount())])
        return {"champs": champs, "lignes": lignes}

    # ---------- الحفظ ----------

    def _general(self) -> bool:
        try:
            dp = self.date_pv.iso()
        except ValueError:
            message(self.message, "تاريخ المحضر غير صحيح.", True)
            return False
        ps.enregistrer(self.f.conn, "_general",
                       {"champs": {"date_pv": dp, **{k: w.text() for k, w in self.g_champs.items()}}})
        return True

    def enregistrer(self, afficher: bool = False) -> bool:
        if self.cle is None:
            return False
        if self.table is not None:
            self.table.setCurrentItem(None)     # إنهاء التحرير الجاري في الخانة
        try:
            ps.enregistrer(self.f.conn, self.cle, self.donnees())
        except ps.ErreurPassation as e:
            message(self.message, str(e), True)
            return False
        if afficher:
            message(self.message, f"حُفظ محور «{ps.section(self.f.conn, self.cle).titre}».")
        return True

    def ajouter_ligne(self) -> None:
        if self.table is not None:
            n = self.table.rowCount()
            self.table.insertRow(n)
            for j in range(self.table.columnCount()):
                self.table.setItem(n, j, self._item(""))
            self.table.setCurrentCell(n, 0)

    def supprimer_lignes(self) -> None:
        if self.table is None:
            return
        for r in sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True):
            self.table.removeRow(r)

    def actualiser(self) -> None:
        if self.cle is None:
            return
        self.enregistrer()
        cle = self.cle
        self.afficher(cle, ps.actualiser(self.f.conn, cle))
        message(self.message, "حُدّث المحور من معطيات البرنامج، وبقي ما أدخلتموه يدوياً.")

    def importer(self, chemin: str | None = None) -> int | None:
        if self.cle is None:
            return None
        if chemin is None:
            chemin, _ = QFileDialog.getOpenFileName(self, "لائحة الكتب (العمود الأول العنوان والثاني العدد)", "",
                                                    "Excel أو CSV (*.xlsx *.csv)")
            if not chemin:
                return None
        try:
            lignes = ps.importer_liste(chemin)
        except (ps.ErreurPassation, OSError) as e:
            message(self.message, str(e), True)
            return None
        d = self.donnees()
        d["lignes"] += lignes
        cle = self.cle
        ps.enregistrer(self.f.conn, cle, d)
        self.afficher(cle)
        message(self.message, f"أُضيف {len(lignes)} عنوان إلى «{ps.section(self.f.conn, cle).titre}».")
        return len(lignes)

    # ---------- المحاور ----------

    def _coche(self, it) -> None:
        ps.activer(self.f.conn, it.data(Qt.UserRole), it.checkState() == Qt.Checked)

    def deplacer(self, pas: int) -> None:
        if self.cle is None:
            return
        self.enregistrer()
        ps.deplacer(self.f.conn, self.cle, pas)
        self.rafraichir()

    def ajouter_section(self, titre: str | None = None, colonnes: str | None = None,
                        texte: bool | None = None) -> str | None:
        """عنوان المحور، وأعمدة جدوله مفصولة بفاصلة (أو لا شيء لنص حر)."""
        if titre is None:
            from PySide6.QtWidgets import QInputDialog
            titre, ok = QInputDialog.getText(self, "محور خاص", "عنوان المحور:")
            if not ok:
                return None
            colonnes, ok = QInputDialog.getText(
                self, "محور خاص", "أعمدة الجدول مفصولة بفاصلة (مثلاً: النوع، العدد، ملاحظات).\n"
                                  "اتركها فارغة لمحور نصي:")
            if not ok:
                return None
            texte = not colonnes.strip()
        self.enregistrer()
        try:
            cle = ps.ajouter_section(self.f.conn, titre, colonnes or "", bool(texte))
        except ps.ErreurPassation as e:
            message(self.message, str(e), True)
            return None
        self.cle = None
        self.rafraichir()
        cles = [self.liste.item(i).data(Qt.UserRole) for i in range(self.liste.count())]
        self.liste.setCurrentRow(cles.index(cle))
        message(self.message, f"أُضيف المحور «{titre.strip()}» في آخر المحضر؛ غيّر موضعه بالسهمين.")
        return cle

    def supprimer_section(self) -> bool:
        if self.cle is None:
            return False
        try:
            ps.supprimer_section(self.f.conn, self.cle)
        except ps.ErreurPassation as e:
            message(self.message, str(e), True)
            return False
        self.cle = None
        self.rafraichir()
        message(self.message, "حُذف المحور الخاص.")
        return True

    def retablir(self) -> None:
        self.enregistrer()
        ps.retablir_ordre(self.f.conn)
        self.rafraichir()

    # ---------- التوليد ----------

    def generer(self):
        if not self._general():
            return None
        self.enregistrer()
        try:
            chemin = ps.generer(self.f.conn, self.f.dossier)
        except (ps.ErreurPassation, OSError) as e:
            message(self.message, str(e), True)
            return None
        message(self.message, f"وُلّد المحضر: ⁦{chemin.name}⁩ (في الأرشيف، مجلد «تسليم المهام»).")
        try:
            bureautique.ouvrir(chemin)
        except OSError as e:
            message(self.message, f"وُلّد المحضر لكن تعذر فتحه: {e}", True)
        return chemin
