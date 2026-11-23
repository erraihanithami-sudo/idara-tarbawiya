"""حاجيات المؤسسة في إطار مشروع المؤسسة المندمج (طلب المدير 2026-11-23): جدول الحاجيات في الصفحة الثابتة،
والإضافة والتعديل في نافذة منبثقة، ووثيقة التحديد ممهورة بتوقيعات أعضاء مجلس التدبير."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QFormLayout, QHBoxLayout, QLabel, QPlainTextEdit, QVBoxLayout, QWidget)

from idara.services import besoins as bz
from idara.services import bureautique
from idara.ui.composants import carte
from idara.ui.formulaires import champ
from idara.ui.saisie import ChampDate, cellule, message, tableau

COULEURS_PRIORITE = {"عالية": "#C62828", "متوسطة": "#EF6C00", "عادية": "#2E7D32"}


class BlocBesoins(QWidget):
    def __init__(self, page):
        super().__init__()
        from idara.ui.vitrine import bouton_couleur
        self.page, self.f = page, page.f
        self.bid: int | None = None
        v0 = QVBoxLayout(self)
        v0.setContentsMargins(0, 0, 0, 0)
        c, v = carte("حاجيات المؤسسة (السنة الجارية)")
        n = QLabel("حدّد حاجيات المؤسسة في إطار مشروعها المندمج، ثم اطبع الوثيقة للمصادقة عليها في مجلس التدبير "
                   "(جدول توقيعات أعضائه من تركيبة المجلس المسجلة في «مجالس المؤسسة»).")
        n.setObjectName("etiquette")
        n.setWordWrap(True)
        v.addWidget(n)
        h = QHBoxLayout()
        self.b_ajouter = bouton_couleur("إضافة حاجة", "#1565C0", "ajouter")
        self.b_ajouter.clicked.connect(lambda: self.ouvrir())
        self.b_doc = bouton_couleur("وثيقة تحديد حاجيات المؤسسة", "#2E7D32", "document",
                                    "ممهورة بتوقيعات أعضاء مجلس التدبير وتوقيع المدير")
        self.b_doc.clicked.connect(lambda: self.ouvrir_document())
        h.addWidget(self.b_ajouter)
        h.addWidget(self.b_doc)
        h.addStretch()
        v.addLayout(h)
        self.l_synthese = QLabel()
        self.l_synthese.setWordWrap(True)
        self.l_synthese.setStyleSheet("font-weight: 700; color: #8C6A00;")
        v.addWidget(self.l_synthese)
        self.table = tableau(["المجال", "الحاجة", "الكمية", "الكلفة التقديرية", "الأولوية", "مصدر التمويل",
                              "الإجراءات"], etirer=1)
        self.table.setMinimumHeight(220)
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.itemDoubleClicked.connect(lambda it: self.ouvrir(self.table.item(it.row(), 0).data(Qt.UserRole)))
        v.addWidget(self.table)
        v0.addWidget(c)
        self._construire_fiche()
        self.rafraichir()

    # ---------- الجدول ----------
    def rafraichir(self) -> None:
        from idara.ui.vitrine import ajuster_colonne_actions, boutons_ligne, vider_colonne_widgets
        try:
            bs = bz.besoins(self.f.conn)
            s = bz.synthese(self.f.conn)
        except bz.ErreurBesoin:
            bs, s = [], {"nombre": 0, "cout": 0, "prioritaires": 0}
        vider_colonne_widgets(self.table, 6)
        self.table.setRowCount(len(bs))
        for i, b in enumerate(bs):
            vals = (b["domaine"], b["besoin"], "—" if b["quantite"] is None else str(b["quantite"]),
                    bz._dh(b["cout"]), b["priorite"], b["source"] or "—")
            for j, x in enumerate(vals):
                it = cellule(x, b["id"] if j == 0 else None)
                if j == 4:
                    from PySide6.QtGui import QColor
                    it.setForeground(QColor(COULEURS_PRIORITE.get(b["priorite"], "#333")))
                self.table.setItem(i, j, it)
            self.table.setCellWidget(i, 6, boutons_ligne([
                ("تعديل", "#1565C0", "modifier", lambda x=b["id"]: self.ouvrir(x)),
                ("حذف", "#C62828", "annuler", lambda x=b["id"]: self.supprimer(x))]))
        ajuster_colonne_actions(self.table, 6)
        self.l_synthese.setText(f"{s['nombre']} حاجة · {s['prioritaires']} ذات أولوية عالية · الكلفة التقديرية "
                                f"{bz._dh(s['cout'])} درهم" if s["nombre"] else "لا حاجيات مسجلة بعد.")

    # ---------- نافذة الإضافة والتعديل ----------
    def _construire_fiche(self) -> None:
        from idara.ui.vitrine import FenetreFiche, bouton_couleur
        w = QWidget()
        v = QVBoxLayout(w)
        fl = QFormLayout()
        self.c_domaine = QComboBox(w)
        self.c_domaine.addItems(bz.DOMAINES)
        self.c_besoin = champ("مثال: حواسيب محمولة لقاعة الموارد")
        self.c_justif = QPlainTextEdit(w)
        self.c_justif.setPlaceholderText("لماذا هذه الحاجة؟ (نتيجة التشخيص، عدد المستفيدين…)")
        self.c_justif.setFixedHeight(80)
        self.c_quantite = champ("العدد", ltr=True)
        self.c_cout = champ("بالدرهم", ltr=True)
        self.c_priorite = QComboBox(w)
        self.c_priorite.addItems(bz.PRIORITES)
        self.c_priorite.setCurrentIndex(1)
        self.c_source = QComboBox(w)
        self.c_source.setEditable(True)
        self.c_source.addItem("")
        self.c_source.addItems(bz.SOURCES)
        self.c_operation = QComboBox(w)
        self.c_operation.setEditable(True)
        for lib, x in (("المجال", self.c_domaine), ("الحاجة *", self.c_besoin), ("المبررات", self.c_justif),
                       ("الكمية", self.c_quantite), ("الكلفة التقديرية", self.c_cout), ("الأولوية", self.c_priorite),
                       ("مصدر التمويل المقترح", self.c_source), ("العملية المرتبطة في المشروع", self.c_operation)):
            fl.addRow(lib, x)
        v.addLayout(fl)
        h = QHBoxLayout()
        b = bouton_couleur("حفظ الحاجة", "#2E7D32", "enregistrer")
        b.clicked.connect(lambda: self.enregistrer())
        h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        self.message_fiche = QLabel()
        self.message_fiche.setWordWrap(True)
        self.message_fiche.hide()
        v.addWidget(self.message_fiche)
        self.fiche = FenetreFiche(self, "إضافة حاجة", "حاجيات المؤسسة في إطار مشروع المؤسسة المندمج.", w, largeur=760)

    def ouvrir(self, bid: int | None = None):
        self.bid = bid
        self.c_operation.clear()
        self.c_operation.addItem("")
        try:
            self.c_operation.addItems(bz.operations_projet(self.f.conn))
        except Exception:  # noqa: BLE001 — لا مشروع
            pass
        b = bz.besoin(self.f.conn, bid) if bid else {}
        self.c_domaine.setCurrentIndex(max(0, self.c_domaine.findText(b.get("domaine", ""))))
        self.c_besoin.setText(b.get("besoin", ""))
        self.c_justif.setPlainText(b.get("justification", ""))
        self.c_quantite.setText("" if b.get("quantite") is None else str(b["quantite"]))
        self.c_cout.setText("" if b.get("cout") is None else f"{b['cout']:g}")
        self.c_priorite.setCurrentIndex(max(0, self.c_priorite.findText(b.get("priorite", "متوسطة"))))
        self.c_source.setEditText(b.get("source", ""))
        self.c_operation.setEditText(b.get("operation", ""))
        self.fiche.definir_titre("تعديل حاجة" if bid else "إضافة حاجة")
        self.message_fiche.hide()
        self.fiche.ouvrir()
        return self.fiche

    def valeurs(self) -> dict:
        return {"domaine": self.c_domaine.currentText(), "besoin": self.c_besoin.text(),
                "justification": self.c_justif.toPlainText(), "quantite": self.c_quantite.text(),
                "cout": self.c_cout.text(), "priorite": self.c_priorite.currentText(),
                "source": self.c_source.currentText(), "operation": self.c_operation.currentText()}

    def enregistrer(self) -> int | None:
        try:
            bid = bz.enregistrer(self.f.conn, self.valeurs(), self.bid)
        except bz.ErreurBesoin as e:
            message(self.message_fiche, str(e), True)
            return None
        self.fiche.hide()
        self.rafraichir()
        message(self.page.message, "حُفظت الحاجة.")
        return bid

    def supprimer(self, bid: int) -> None:
        bz.supprimer(self.f.conn, bid)
        self.rafraichir()
        message(self.page.message, "حُذفت الحاجة.")

    # ---------- الوثيقة ----------
    def ouvrir_document(self):
        from idara.ui.vitrine import FenetreFiche, bouton_couleur
        if not hasattr(self, "fiche_doc"):
            w = QWidget()
            v = QVBoxLayout(w)
            fl = QFormLayout()
            self.c_seance = ChampDate(w)
            fl.addRow("تاريخ اجتماع مجلس التدبير (اختياري)", self.c_seance)
            v.addLayout(fl)
            b = bouton_couleur("توليد الوثيقة", "#2E7D32", "document")
            b.clicked.connect(lambda: self.generer())
            v.addWidget(b, 0, Qt.AlignLeft)
            self.message_doc = QLabel()
            self.message_doc.setWordWrap(True)
            self.message_doc.hide()
            v.addWidget(self.message_doc)
            self.fiche_doc = FenetreFiche(self, "وثيقة تحديد حاجيات المؤسسة",
                                          "تُطبع بجدول توقيعات أعضاء مجلس التدبير.", w, largeur=600)
        self.message_doc.hide()
        self.fiche_doc.ouvrir()
        return self.fiche_doc

    def generer(self, date_seance: str | None = None):
        try:
            ds = date_seance if date_seance is not None else (self.c_seance.iso() or "")
        except ValueError:
            message(self.message_doc, "تاريخ الاجتماع غير صحيح.", True)
            return None
        try:
            p = bz.generer(self.f.conn, self.f.dossier, date_seance=ds)
        except bz.ErreurBesoin as e:
            if hasattr(self, "message_doc"):
                message(self.message_doc, str(e), True)
            message(self.page.message, str(e), True)
            return None
        if hasattr(self, "fiche_doc"):
            self.fiche_doc.hide()
        message(self.page.message, f"وُلّدت الوثيقة: ⁦{p.name}⁩")
        try:
            bureautique.ouvrir(p)
        except OSError:
            pass
        return p
