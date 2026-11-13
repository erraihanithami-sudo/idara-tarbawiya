"""صفحة «الجرد» (طلب المدير 2026-11-13): سجل الجرد على نموذج السجل الورقي، مع فرز معطياته حسب نوع التجهيز."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
                               QPushButton, QSpinBox, QWidget)

from idara.services import bureautique
from idara.services import inventaire as inv
from idara.services import textes as tx
from idara.ui.composants import bouton, carte
from idara.ui.formulaires import etiquette
from idara.ui.page_pedagogie import _page
from idara.ui.saisie import ChampDate, cellule, message, tableau


def _mt(v) -> str:
    return "" if v is None else f"{v:,.2f}".replace(",", " ")


class PageInventaire(QWidget):
    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        self.aid: int | None = None
        racine, self.message = _page(
            "الجرد", "سجل الجرد على نموذج السجل الورقي: كل تجهيز برقمه الترتيبي ومصدره وثمنه وتخصيصه وحالة صيانته. "
                     "يُفرز السجل حسب نوع التجهيز، ويُولَّد كاملاً أو لنوع واحد، ويغذي محضر تسليم المهام.")
        self.setLayout(racine)

        # ---- البطاقة ----
        c, v = carte("تجهيز في السجل")
        self.titre = QLabel("تجهيز جديد")
        self.titre.setObjectName("titreCarte")
        v.addWidget(self.titre)
        self.numero = QLineEdit()
        self.date_ins = ChampDate()
        self.designation = QLineEdit()
        self.type = QComboBox()
        self.type.setEditable(True)
        self.quantite = QSpinBox()
        self.quantite.setRange(1, 100000)
        self.prix = QLineEdit()
        self.prix.setPlaceholderText("بالدرهم")
        self.facture = QLineEdit()
        self.date_facture = ChampDate()
        self.fournisseur = QLineEdit()
        self.affectation = QLineEdit()
        self.affectation.setPlaceholderText("مثلاً: الإدارة، القسم 3، قاعة الموارد")
        self.entretien = QComboBox()
        self.entretien.setEditable(True)
        self.entretien.addItems([""] + list(inv.ETATS))
        self.remarques = QLineEdit()
        g = QGridLayout()
        g.setHorizontalSpacing(16)
        g.setVerticalSpacing(4)
        champs = [("الرقم الترتيبي", self.numero), ("تاريخ التسجيل", self.date_ins), ("وصف التجهيزات", self.designation),
                  ("نوع التجهيز", self.type), ("عدد الأشياء", self.quantite), ("ثمن الوحدة", self.prix),
                  ("رقم الفاتورة", self.facture), ("تاريخ الفاتورة", self.date_facture),
                  ("اسم التاجر", self.fournisseur), ("تخصيص التجهيزات", self.affectation),
                  ("حالة صيانتها", self.entretien), ("ملاحظات", self.remarques)]
        for k, (lib, w) in enumerate(champs):
            g.addWidget(etiquette(lib, w), (k // 4) * 2, k % 4)
            g.addWidget(w, (k // 4) * 2 + 1, k % 4)
        v.addLayout(g)
        t = QLabel("محو التجهيزات من السجل")
        t.setObjectName("titreCarte")
        v.addWidget(t)
        self.radie_le = ChampDate()
        self.motif = QLineEdit()
        self.decision = QLineEdit()
        g2 = QGridLayout()
        g2.setHorizontalSpacing(16)
        for k, (lib, w) in enumerate((("التاريخ", self.radie_le), ("السبب", self.motif), ("رقم القرار", self.decision))):
            g2.addWidget(etiquette(lib, w), 0, k)
            g2.addWidget(w, 1, k)
        v.addLayout(g2)
        aide = QLabel("المحو لا يحذف السطر: يبقى في السجل مع تاريخ المحو وسببه ورقم القرار، كما في السجل الورقي.")
        aide.setObjectName("etiquette")
        aide.setWordWrap(True)
        v.addWidget(aide)
        h = QHBoxLayout()
        b = QPushButton("حفظ")
        b.setObjectName("principal")
        b.clicked.connect(lambda: self.enregistrer())
        h.addWidget(b)
        b = QPushButton("تجهيز جديد")
        b.clicked.connect(self.nouveau)
        h.addWidget(b)
        self.b_supprimer = bouton("حذف السطر (إدخال خاطئ)")
        self.b_supprimer.clicked.connect(lambda: self.supprimer())
        h.addWidget(self.b_supprimer)
        h.addStretch()
        v.addLayout(h)
        racine.addWidget(c)

        # ---- السجل ----
        c, v = carte("سجل الجرد")
        h = QHBoxLayout()
        self.filtre = QComboBox()
        self.filtre.currentIndexChanged.connect(lambda _: self.afficher())
        self.recherche = QLineEdit()
        self.recherche.setPlaceholderText("بحث: الوصف، التاجر، التخصيص، رقم الفاتورة أو الرقم الترتيبي")
        self.recherche.textChanged.connect(lambda _: self.afficher())
        self.ordre = QComboBox()
        self.ordre.addItem("مرتب حسب نوع التجهيز", "type")
        self.ordre.addItem("مرتب حسب الرقم الترتيبي", "numero")
        self.ordre.currentIndexChanged.connect(lambda _: self.afficher())
        self.radies = QCheckBox("إظهار التجهيزات الممحوة")
        self.radies.setChecked(True)
        self.radies.toggled.connect(lambda _: self.afficher())
        for w in (self.filtre, self.recherche, self.ordre, self.radies):
            h.addWidget(w)
        h.setStretch(1, 1)
        v.addLayout(h)
        self.table = tableau(["الرقم", "تاريخ التسجيل", "وصف التجهيزات", "نوع التجهيز", "العدد", "ثمن الوحدة",
                              "المجموع", "التخصيص", "حالة الصيانة", "المحو"], etirer=2)
        self.table.setMinimumHeight(380)
        self.table.itemSelectionChanged.connect(self._selection)
        v.addWidget(self.table)
        h = QHBoxLayout()
        self.total = QLabel()
        self.total.setObjectName("etiquette")
        h.addWidget(self.total, 1)
        b = QPushButton("توليد سجل الجرد (Word)")
        b.setObjectName("principal")
        b.setToolTip("للنوع المختار في الفرز، أو لكل الأنواع")
        b.clicked.connect(lambda: self.generer())
        h.addWidget(b)
        v.addLayout(h)
        racine.addWidget(c)

        # ---- حسب النوع ----
        c, v = carte("حسب نوع التجهيز")
        self.t_types = tableau(["نوع التجهيز", "الأسطر", "عدد الأشياء", "صالح", "يحتاج صيانة", "معطل", "الممحوة",
                                "القيمة (درهم)"], etirer=0)
        self.t_types.setMinimumHeight(220)
        v.addWidget(self.t_types)
        racine.addWidget(c)
        racine.addStretch()
        self.articles: list[inv.Article] = []
        self.rafraichir()

    # ---------- التحميل ----------

    def rafraichir(self) -> None:
        types = inv.types_utilises(self.f.conn)
        actuel = self.filtre.currentData()
        self.filtre.blockSignals(True)
        self.filtre.clear()
        self.filtre.addItem("كل أنواع التجهيزات", None)
        for t in types:
            self.filtre.addItem(t, t)
        self.filtre.setCurrentIndex(max(0, self.filtre.findData(actuel)))
        self.filtre.blockSignals(False)
        texte = self.type.currentText()
        self.type.clear()
        self.type.addItems(types)
        self.type.setCurrentText(texte or types[0])
        if self.aid is None:
            self.nouveau()
        self.afficher()

    def afficher(self) -> None:
        self.articles = inv.lister(self.f.conn, self.filtre.currentData(), self.recherche.text(),
                                   self.radies.isChecked(), self.ordre.currentData() or "type")
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.articles))
        for i, a in enumerate(self.articles):
            vals = [str(a.numero), tx.date_chiffres(a.date_inscription), a.designation, a.type, str(a.quantite),
                    _mt(a.prix_unitaire),
                    _mt(a.total), a.affectation, a.entretien,
                    (f"ممحو ({a.radiation_motif})" if a.radie else "")]
            for j, x in enumerate(vals):
                self.table.setItem(i, j, cellule(x or "", a.id))
        self.table.blockSignals(False)
        actifs = [a for a in self.articles if not a.radie]
        self.total.setText(f"{len(self.articles)} سطراً · {sum(a.quantite for a in actifs)} شيئاً قائماً · القيمة: "
                           f"{_mt(round(sum(a.total or 0 for a in actifs), 2))} درهم")
        syn = inv.synthese(self.f.conn)
        self.t_types.setRowCount(len(syn))
        for i, s in enumerate(syn):
            for j, x in enumerate([s["type"], s["lignes"], s["quantite"], s["etats"]["صالح"],
                                   s["etats"]["يحتاج صيانة"], s["etats"]["معطل"], s["radies"], _mt(s["valeur"])]):
                self.t_types.setItem(i, j, cellule(str(x)))

    def _selection(self) -> None:
        rows = {i.row() for i in self.table.selectedIndexes()}
        if len(rows) == 1:
            self.charger(self.table.item(rows.pop(), 0).data(Qt.UserRole))

    def charger(self, aid: int) -> None:
        a = inv.lire(self.f.conn, aid)
        self.aid = aid
        self.titre.setText(f"السطر {a.numero}: {a.designation}" + (" (ممحو من السجل)" if a.radie else ""))
        self.numero.setText(str(a.numero))
        self.date_ins.definir(a.date_inscription or None)
        self.designation.setText(a.designation)
        self.type.setCurrentText(a.type)
        self.quantite.setValue(a.quantite)
        self.prix.setText("" if a.prix_unitaire is None else f"{a.prix_unitaire:g}")
        self.facture.setText(a.facture_numero)
        self.date_facture.definir(a.facture_date or None)
        self.fournisseur.setText(a.fournisseur)
        self.affectation.setText(a.affectation)
        self.entretien.setCurrentText(a.entretien)
        self.remarques.setText(a.remarques)
        self.radie_le.definir(a.radie_le or None)
        self.motif.setText(a.radiation_motif)
        self.decision.setText(a.radiation_decision)
        self.b_supprimer.setEnabled(True)

    def nouveau(self) -> None:
        self.aid = None
        self.titre.setText("تجهيز جديد")
        self.numero.setText(str(inv.prochain_numero(self.f.conn)))
        self.date_ins.definir(date.today().isoformat())
        for w in (self.designation, self.prix, self.facture, self.fournisseur, self.affectation, self.remarques,
                  self.motif, self.decision):
            w.clear()
        self.date_facture.definir(None)
        self.radie_le.definir(None)
        self.quantite.setValue(1)
        self.entretien.setCurrentText("")
        self.b_supprimer.setEnabled(False)
        self.table.clearSelection()

    # ---------- الحفظ ----------

    def enregistrer(self) -> int | None:
        try:
            a = inv.Article(
                id=self.aid, numero=self.numero.text().strip() or None, date_inscription=self.date_ins.iso() or "",
                designation=self.designation.text(), type=self.type.currentText(), quantite=self.quantite.value(),
                prix_unitaire=self.prix.text().strip() or None, facture_numero=self.facture.text(),
                facture_date=self.date_facture.iso() or "", fournisseur=self.fournisseur.text(),
                affectation=self.affectation.text(), entretien=self.entretien.currentText(),
                remarques=self.remarques.text(), radie_le=self.radie_le.iso() or "",
                radiation_motif=self.motif.text(), radiation_decision=self.decision.text())
            aid = inv.enregistrer(self.f.conn, a)
        except ValueError as e:     # ErreurInventaire، أو تاريخ غير صحيح في خانة
            message(self.message, str(e) if isinstance(e, inv.ErreurInventaire) else "أحد التواريخ غير صحيح.", True)
            return None
        self.aid = aid
        self.rafraichir()
        self.charger(aid)
        message(self.message, f"حُفظ السطر {a.numero} في سجل الجرد.")
        return aid

    def supprimer(self, confirmer: bool | None = None) -> bool:
        if self.aid is None:
            return False
        if confirmer is None:
            confirmer = QMessageBox.question(
                self, "حذف سطر", "حذف هذا السطر نهائياً؟ (لإخراج تجهيز من السجل استعمل «محو التجهيزات من السجل»)",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes
        if not confirmer:
            return False
        inv.supprimer(self.f.conn, self.aid)
        self.aid = None
        self.rafraichir()
        message(self.message, "حُذف السطر.")
        return True

    def generer(self):
        try:
            p = inv.generer_registre(self.f.conn, self.f.dossier, self.filtre.currentData(), self.radies.isChecked())
        except (inv.ErreurInventaire, OSError) as e:
            message(self.message, str(e), True)
            return None
        message(self.message, f"وُلّد سجل الجرد: ⁦{p.name}⁩")
        try:
            bureautique.ouvrir(p)
        except OSError:
            pass
        return p
