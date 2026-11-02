"""صفحة جمعية دعم مدرسة النجاح: السنة المالية، العمليات، سجلا البنك والصندوق، الميزانية (نموذج المدير)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
                               QGridLayout, QHBoxLayout, QLabel, QMenu, QPlainTextEdit, QPushButton, QVBoxLayout,
                               QWidget)

from idara.services import associations as asso
from idara.services import bureautique
from idara.services import docs_association as da
from idara.services import textes as tx
from idara.ui.composants import carte, entete
from idara.ui.formulaires import champ, etiquette
from idara.ui.saisie import ChampDate, cellule, message, tableau

TYPE = "najah"


def dh(x: float) -> str:
    """فاصل الآلاف مسافة غير قابلة للكسر: يبقى الرقم كتلة واحدة داخل السطر العربي."""
    return f"{x:,.2f}".replace(",", "\u00a0")


def _date(w: ChampDate, lib: str) -> str:
    try:
        return w.iso()
    except ValueError:
        raise asso.ErreurAssociation(f"{lib} غير صحيح.") from None


class DialogueExercice(QDialog):
    """فتح سنة مالية. المنقول يُحتسب آلياً من السنة السابقة؛ يُدخل يدوياً لأول سنة في التطبيق فقط."""

    def __init__(self, parent, premiere: bool):
        super().__init__(parent)
        self.setWindowTitle("فتح سنة مالية")
        self.setLayoutDirection(Qt.RightToLeft)
        v = QVBoxLayout(self)
        f = QFormLayout()
        a = date.today().year if date.today().month >= 9 else date.today().year - 1
        self.libelle = champ()
        self.libelle.setText(f"{a}/{a + 1}")
        self.debut, self.fin = ChampDate(), ChampDate()
        self.debut.definir(f"{a}-09-01")
        self.fin.definir(f"{a + 1}-08-31")
        f.addRow("السنة المالية", self.libelle)
        f.addRow("تاريخ البداية", self.debut)
        f.addRow("تاريخ النهاية", self.fin)
        self.premiere = premiere
        self.banque, self.caisse = champ("0.00", ltr=True), champ("0.00", ltr=True)
        self.reference = champ("محضر تسليم المهام، كشف الحساب...")
        if premiere:
            f.addRow("المنقول — البنك", self.banque)
            f.addRow("المنقول — الصندوق", self.caisse)
            f.addRow("المرجع", self.reference)
        else:
            n = QLabel("المنقول من السنة السابقة يُسجل آلياً من رصيدي البنك والصندوق.")
            n.setWordWrap(True)
            f.addRow(n)
        v.addLayout(f)
        b = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        b.button(QDialogButtonBox.Ok).setText("فتح السنة المالية")
        b.button(QDialogButtonBox.Cancel).setText("إلغاء")
        b.accepted.connect(self.accept)
        b.rejected.connect(self.reject)
        v.addWidget(b)

    def valeurs(self) -> dict:
        d = dict(libelle=self.libelle.text(), debut=_date(self.debut, "تاريخ البداية"),
                 fin=_date(self.fin, "تاريخ النهاية"))
        if self.premiere:
            try:
                d.update(report_banque=float(self.banque.text().replace(",", ".").replace(" ", "") or 0),
                         report_caisse=float(self.caisse.text().replace(",", ".").replace(" ", "") or 0))
            except ValueError:
                raise asso.ErreurAssociation("مبلغ المنقول غير صحيح.") from None
            d["reference"] = self.reference.text().strip()
        return d


class DialoguePassation(QDialog):
    """محضر تسليم المهام المالية (الملحق 25 من الدليل المسطري)."""

    def __init__(self, parent, tresorier: str):
        super().__init__(parent)
        self.setWindowTitle("محضر تسليم المهام المالية")
        self.setLayoutDirection(Qt.RightToLeft)
        v = QVBoxLayout(self)
        f = QFormLayout()
        self.date = ChampDate()
        self.date.definir(date.today().isoformat())
        self.ancien, self.nouveau = champ(), champ()
        self.ancien.setText(tresorier or "")
        self.remarques = QPlainTextEdit()
        self.remarques.setPlaceholderText("ملاحظة في كل سطر (اختياري)")
        self.remarques.setFixedHeight(90)
        self.maj = QCheckBox("تسجيل أمين المال الجديد في معطيات الجمعية")
        self.maj.setChecked(True)
        f.addRow("تاريخ المحضر", self.date)
        f.addRow("أمين(ة) المال السابق(ة)", self.ancien)
        f.addRow("أمين(ة) المال الجديد(ة)", self.nouveau)
        f.addRow("الملاحظات", self.remarques)
        f.addRow(self.maj)
        v.addLayout(f)
        b = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        b.button(QDialogButtonBox.Ok).setText("توليد المحضر")
        b.button(QDialogButtonBox.Cancel).setText("إلغاء")
        b.accepted.connect(self.accept)
        b.rejected.connect(self.reject)
        v.addWidget(b)

    def valeurs(self) -> dict:
        return dict(date_pv=_date(self.date, "تاريخ المحضر"), ancien=self.ancien.text(), nouveau=self.nouveau.text(),
                    remarques=self.remarques.toPlainText().splitlines(), maj=self.maj.isChecked())


class PageAssociations(QWidget):
    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        self.eid: int | None = None
        self.op_id: int | None = None
        racine = QVBoxLayout(self)
        racine.setContentsMargins(40, 32, 40, 32)
        racine.setSpacing(16)
        a = asso.association(self.f.conn, TYPE)
        racine.addWidget(entete(a["nom"], "المداخيل والمصاريف حسب أبواب وبنود نموذجكم، بسجلين: البنك والصندوق. الوصولات والسجلات "
                                          "والمحاضر على نماذج الدليل المسطري للتدبير المالي (يوليوز 2023)."))
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.hide()
        racine.addWidget(self.message)

        # ---- السنة المالية والأرصدة ----
        c, cv = carte()
        h = QHBoxLayout()
        h.addWidget(QLabel("السنة المالية"))
        self.exercice = QComboBox()
        self.exercice.setMinimumWidth(160)
        self.exercice.currentIndexChanged.connect(lambda _: self._changer_exercice())
        h.addWidget(self.exercice)
        self.b_ouvrir = QPushButton("فتح سنة مالية جديدة")
        self.b_ouvrir.clicked.connect(self.ouvrir)
        self.b_export = QPushButton("تصدير السجلات (Excel)")
        self.b_export.clicked.connect(lambda: self.exporter())
        self.b_registres = QPushButton("السجلات (Word)")
        m = QMenu(self.b_registres)
        for k, (lib, n) in da.REGISTRES_DOC.items():
            m.addAction(f"{lib} (الملحق {n})", lambda k=k: self.generer_registre(k))
        self.b_registres.setMenu(m)
        self.b_budget = QPushButton("وثيقة الميزانية")
        self.b_budget.clicked.connect(lambda: self.generer_budget())
        self.b_passation = QPushButton("محضر تسليم المهام المالية")
        self.b_passation.clicked.connect(lambda: self.passation())
        for b in (self.b_ouvrir, self.b_registres, self.b_budget, self.b_passation, self.b_export):
            h.addWidget(b)
        h.addStretch()
        cv.addLayout(h)
        self.chiffres = {}
        g = QHBoxLayout()
        for k, lib in (("banque", "رصيد البنك (درهم)"), ("caisse", "رصيد الصندوق (درهم)"),
                       ("recettes", "مجموع المداخيل (درهم)"), ("depenses", "مجموع المصاريف (درهم)")):
            b = QVBoxLayout()
            t = QLabel(lib)
            t.setObjectName("etiquette")
            n = QLabel("—")
            n.setObjectName("titreCarte")
            n.setAlignment(Qt.AlignRight | Qt.AlignAbsolute | Qt.AlignVCenter)
            b.addWidget(t)
            b.addWidget(n)
            g.addLayout(b)
            self.chiffres[k] = n
        cv.addLayout(g)
        self.alertes = QLabel()
        self.alertes.setObjectName("erreur")
        self.alertes.setWordWrap(True)
        self.alertes.hide()
        cv.addWidget(self.alertes)
        racine.addWidget(c)


        # ---- العمليات / السجلات ----
        c, cv = carte()
        h = QHBoxLayout()
        t = QLabel("العمليات")
        t.setObjectName("titreCarte")
        h.addWidget(t)
        h.addStretch()
        self.vue = QComboBox()
        for k, lib in (("", "كل العمليات (اليومية)"), ("banque", "سجل البنك"), ("caisse", "سجل الصندوق")):
            self.vue.addItem(lib, k)
        self.vue.currentIndexChanged.connect(lambda _: self.afficher_operations())
        h.addWidget(self.vue)
        cv.addLayout(h)
        self.ops = tableau(["رقم", "التاريخ", "البيان", "مدخول", "مصروف", "السجل"], etirer=2)
        self.ops.setMinimumHeight(340)
        self.ops.itemSelectionChanged.connect(self._selection_op)
        cv.addWidget(self.ops, 1)
        h = QHBoxLayout()
        self.b_suppr = QPushButton("حذف العملية المحددة")
        self.b_suppr.setEnabled(False)
        self.b_suppr.clicked.connect(self.supprimer)
        self.b_pieces = QPushButton("وثائق العملية")
        self.b_pieces.setObjectName("principal")
        self.b_pieces.setEnabled(False)
        self.menu_pieces = QMenu(self.b_pieces)
        self.b_pieces.setMenu(self.menu_pieces)
        self.l_pieces = QLabel()
        self.l_pieces.setObjectName("sousTitre")
        h.addWidget(self.b_pieces)
        h.addWidget(self.b_suppr)
        h.addWidget(self.l_pieces, 1)
        cv.addLayout(h)
        racine.addWidget(c)
        corps = QHBoxLayout()
        corps.setSpacing(20)
        racine.addLayout(corps)

        # ---- عملية جديدة ----
        c, fv = carte("عملية جديدة")
        self.date = ChampDate()
        self.nature = QComboBox()
        for k, lib in asso.NATURES.items():
            self.nature.addItem(lib, k)
        self.registre = QComboBox()
        for k, lib in asso.REGISTRES.items():
            self.registre.addItem(lib, k)
        self.chapitre, self.ligne = QComboBox(), QComboBox()
        self.nature.currentIndexChanged.connect(lambda _: self._remplir_chapitres())
        self.chapitre.currentIndexChanged.connect(lambda _: self._remplir_lignes())
        self.ligne.currentIndexChanged.connect(lambda _: self._afficher_observation())
        self.indice = QLabel()
        self.indice.setObjectName("sousTitre")
        self.indice.setWordWrap(True)
        self.montant = champ("0.00", ltr=True)
        self.reference = champ("فاتورة، سند الطلب، رقم الشيك، كشف الحساب...")
        self.detail = champ("اختياري")
        self.tiers = champ("المؤدي (وصل مداخيل) أو المستفيد (سند تسلم)")
        self.tiers_qualite = champ("مثلا: ممون، حرفي، ولي أمر...")
        g = QGridLayout()
        g.setHorizontalSpacing(16)
        g.setVerticalSpacing(4)
        self.l_registre = etiquette("السجل *", self.registre)
        self.l_chapitre = etiquette("الباب *", self.chapitre)
        self.l_ligne = etiquette("البند *", self.ligne)
        champs = [(etiquette("التاريخ *", self.date), self.date, 0, 0), (etiquette("النوع *", self.nature), self.nature, 0, 1),
                  (self.l_registre, self.registre, 2, 0), (etiquette("المبلغ (درهم) *", self.montant), self.montant, 2, 1)]
        for lab, w, r, col in champs:
            g.addWidget(lab, r, col)
            g.addWidget(w, r + 1, col)
        for i, (lab, w) in enumerate(((self.l_chapitre, self.chapitre), (self.l_ligne, self.ligne),
                                      (None, self.indice), (etiquette("المرجع", self.reference), self.reference),
                                      (etiquette("البيان / التفاصيل", self.detail), self.detail)), start=2):
            if lab is not None:
                g.addWidget(lab, i * 2, 0, 1, 2)
            g.addWidget(w, i * 2 + 1, 0, 1, 2)
        g.addWidget(etiquette("الطرف المعني", self.tiers), 12, 0)
        g.addWidget(self.tiers, 13, 0)
        g.addWidget(etiquette("صفته", self.tiers_qualite), 12, 1)
        g.addWidget(self.tiers_qualite, 13, 1)
        g.setColumnStretch(1, 1)
        fv.addLayout(g)
        h = QHBoxLayout()
        self.b_save = QPushButton("تسجيل العملية")
        self.b_save.setObjectName("principal")
        self.b_save.clicked.connect(lambda: self.enregistrer())
        h.addWidget(self.b_save)
        h.addStretch()
        fv.addLayout(h)
        fv.addStretch()
        corps.addWidget(c, 5)

        # ---- الميزانية ----
        c, bv = carte()
        h = QHBoxLayout()
        t = QLabel("الميزانية: المتوقع والمنجز")
        t.setObjectName("titreCarte")
        h.addWidget(t)
        h.addStretch()
        self.sens = QComboBox()
        self.sens.addItem("المصاريف", "depense")
        self.sens.addItem("المداخيل", "recette")
        self.sens.currentIndexChanged.connect(lambda _: self.afficher_budget())
        h.addWidget(self.sens)
        bv.addLayout(h)
        self.budget = tableau(["البند", "المتوقع", "المنجز", "الباقي", "النسبة"], etirer=0)
        self.budget.setMinimumHeight(420)
        self.budget.itemSelectionChanged.connect(self._selection_budget)
        bv.addWidget(self.budget)
        h = QHBoxLayout()
        self.l_prev = QLabel("اختر بنداً لتحديد المبلغ المتوقع")
        self.l_prev.setWordWrap(True)
        self.prevu = champ("0.00", ltr=True)
        self.prevu.setMaximumWidth(160)
        self.b_prev = QPushButton("حفظ المتوقع")
        self.b_prev.clicked.connect(lambda: self.enregistrer_prevision())
        for w in (self.l_prev, self.prevu, self.b_prev):
            h.addWidget(w)
        h.addStretch()
        bv.addLayout(h)
        corps.addWidget(c, 6)

        # ---- معطيات الجمعية ----
        c, av = carte("معطيات الجمعية")
        self.rib, self.president, self.tresorier = champ("رقم الحساب البنكي", ltr=True), champ(), champ()
        self.renouvellement = ChampDate()
        g = QGridLayout()
        g.setHorizontalSpacing(16)
        for i, (lib, w) in enumerate((("رقم الحساب (RIB)", self.rib), ("الرئيس(ة)", self.president),
                                      ("أمين(ة) المال", self.tresorier), ("تاريخ آخر تجديد للمكتب", self.renouvellement))):
            g.addWidget(etiquette(lib, w), 0, i)
            g.addWidget(w, 1, i)
        av.addLayout(g)
        h = QHBoxLayout()
        b = QPushButton("حفظ معطيات الجمعية")
        b.clicked.connect(lambda: self.enregistrer_association())
        h.addWidget(b)
        h.addStretch()
        av.addLayout(h)
        racine.addWidget(c)
        racine.addStretch()

        self._remplir_chapitres()
        self._charger_association()
        self.rafraichir()

    # ---------- chargement ----------

    def rafraichir(self) -> None:
        courant = self.eid
        self.exercice.blockSignals(True)
        self.exercice.clear()
        for e in asso.exercices(self.f.conn, TYPE):
            self.exercice.addItem(e["libelle"], e["id"])
        i = self.exercice.findData(courant)
        self.exercice.setCurrentIndex(i if i >= 0 else 0)
        self.exercice.blockSignals(False)
        self._changer_exercice()

    def _changer_exercice(self) -> None:
        self.eid = self.exercice.currentData()
        actif = self.eid is not None
        for w in (self.b_export, self.b_registres, self.b_budget, self.b_passation, self.tiers, self.tiers_qualite,
                  self.b_save, self.date, self.nature, self.registre, self.chapitre, self.ligne,
                  self.montant, self.reference, self.detail, self.b_prev, self.prevu):
            w.setEnabled(actif)
        if actif:
            self.message.hide()
        else:
            message(self.message, "ابدأ بفتح السنة المالية الأولى، مع المنقول من السنة السابقة "
                                  "(من محضر تسليم المهام أو كشف الحساب).")
        e = asso.exercice(self.f.conn, self.eid) if actif else None
        if e:
            auj = date.today().isoformat()
            self.date.definir(min(max(auj, e["date_debut"]), e["date_fin"]))
        self.afficher_operations()
        self.afficher_budget()
        self.afficher_totaux()

    def afficher_totaux(self) -> None:
        if self.eid is None:
            for n in self.chiffres.values():
                n.setText("—")
            self.alertes.hide()
            return
        t = asso.totaux(self.f.conn, self.eid)
        for k, n in self.chiffres.items():
            n.setText(dh(t[k]))
        al = asso.depassements(self.f.conn, self.eid)
        self.alertes.setText("تنبيه — تجاوز المتوقع:\n" + "\n".join(al))
        self.alertes.setVisible(bool(al))

    def afficher_operations(self) -> None:
        self.op_id = None
        self.b_suppr.setEnabled(False)
        self.b_pieces.setEnabled(False)
        self.l_pieces.setText("")
        reg = self.vue.currentData()
        lignes = []
        if self.eid is not None:
            if reg:
                self.ops.setHorizontalHeaderItem(5, cellule("الرصيد"))
                ids = {o["numero"]: o["id"] for o in asso.operations(self.f.conn, self.eid)}
                for r in asso.registre(self.f.conn, self.eid, reg):
                    lignes.append((ids[r["numero"]], r["numero"], r["date"], r["libelle"], r["detail"], r["reference"],
                                   r["entree"], r["sortie"], dh(r["solde"])))
            else:
                self.ops.setHorizontalHeaderItem(5, cellule("السجل"))
                for o in asso.operations(self.f.conn, self.eid):
                    lib = o["ligne"] or "تحويل بين الصندوقين"
                    sens = o["nature"]
                    lignes.append((o["id"], o["numero"], o["date_op"], lib, o["detail"] or "", o["reference"] or "",
                                   o["montant"] if sens == "recette" else 0, o["montant"] if sens == "depense" else 0,
                                   asso.REGISTRES[o["registre"]] + (" ← " + asso.REGISTRES[
                                       "caisse" if o["registre"] == "banque" else "banque"] if sens == "transfert" else "")))
        self.ops.setRowCount(len(lignes))
        for i, (oid, num, d, lib, det, ref, ent, sor, der) in enumerate(lignes):
            self.ops.setItem(i, 0, cellule(num, oid))
            self.ops.setItem(i, 1, cellule(tx.date_chiffres(d)))
            it = cellule(lib + (f" — {det}" if det else ""))
            it.setToolTip(" · ".join(x for x in (det, f"المرجع: {ref}" if ref else "") if x))
            self.ops.setItem(i, 2, it)
            self.ops.setItem(i, 3, cellule(dh(ent) if ent else ""))
            self.ops.setItem(i, 4, cellule(dh(sor) if sor else ""))
            self.ops.setItem(i, 5, cellule(der))

    def afficher_budget(self) -> None:
        sens = self.sens.currentData()
        lignes = [r for r in asso.execution(self.f.conn, self.eid) if r["sens"] == sens] if self.eid else []
        self.budget.setRowCount(len(lignes))
        for i, r in enumerate(lignes):
            it = cellule(r["ligne"], r["id"])
            it.setToolTip("\n".join(x for x in (r["chapitre"], r["observation"]) if x))
            self.budget.setItem(i, 0, it)
            for j, k in enumerate(("prevu", "realise", "reste"), start=1):
                self.budget.setItem(i, j, cellule(dh(r[k]) if r[k] else "—"))
            self.budget.setItem(i, 4, cellule(r["taux"]))
            if sens == "depense" and r["realise"] > r["prevu"] + 1e-9:
                for j in range(5):
                    self.budget.item(i, j).setForeground(Qt.darkRed)

    def _charger_association(self) -> None:
        a = asso.association(self.f.conn, TYPE)
        self.rib.setText(a["rib"] or "")
        self.president.setText(a["president"] or "")
        self.tresorier.setText(a["tresorier"] or "")
        self.renouvellement.definir(a["date_renouvellement"] or "")

    # ---------- formulaire ----------

    def _remplir_chapitres(self) -> None:
        nat = self.nature.currentData()
        transfert = nat == "transfert"
        for w in (self.l_chapitre, self.chapitre, self.l_ligne, self.ligne):
            w.setVisible(not transfert)
        self.l_registre.setText("من *" if transfert else "السجل *")
        self.chapitre.blockSignals(True)
        self.chapitre.clear()
        if not transfert:
            vus = []
            for r in asso.rubriques(self.f.conn, TYPE, nat):
                if r["ligne"] != asso.REPORT and r["chapitre"] not in vus:
                    vus.append(r["chapitre"])
            self.chapitre.addItems(vus)
        self.chapitre.blockSignals(False)
        self._remplir_lignes()

    def _remplir_lignes(self) -> None:
        self.ligne.blockSignals(True)
        self.ligne.clear()
        nat, ch = self.nature.currentData(), self.chapitre.currentText()
        if nat != "transfert":
            for r in asso.rubriques(self.f.conn, TYPE, nat):
                if r["chapitre"] == ch and r["ligne"] != asso.REPORT:
                    self.ligne.addItem(r["ligne"], r["id"])
        self.ligne.blockSignals(False)
        self._afficher_observation()

    def _afficher_observation(self) -> None:
        if self.nature.currentData() == "transfert":
            self.indice.setText("تمويل الصندوق من البنك (سحب نقدي)، أو إيداع نقود الصندوق في الحساب البنكي.")
            self.indice.setVisible(True)
            return
        r = self.f.conn.execute("SELECT observation FROM rubrique WHERE id=?", (self.ligne.currentData(),)).fetchone()
        self.indice.setText(r[0] if r and r[0] else "")
        self.indice.setVisible(bool(self.indice.text()))

    def enregistrer(self) -> int | None:
        try:
            op = asso.Operation(self.eid, _date(self.date, "تاريخ العملية"), self.nature.currentData(),
                                self.registre.currentData(), self.montant.text(), self.ligne.currentData(),
                                self.reference.text(), self.detail.text(), tiers=self.tiers.text(),
                                tiers_qualite=self.tiers_qualite.text())
            oid = asso.enregistrer(self.f.conn, op)
        except asso.ErreurAssociation as e:
            message(self.message, str(e), True)
            return None
        for w in (self.montant, self.reference, self.detail, self.tiers, self.tiers_qualite):
            w.clear()
        self._changer_exercice()
        message(self.message, "سُجلت العملية.")
        return oid

    def _selection_op(self) -> None:
        rows = {i.row() for i in self.ops.selectedIndexes()}
        self.op_id = self.ops.item(rows.pop(), 0).data(Qt.UserRole) if len(rows) == 1 else None
        self.b_suppr.setEnabled(self.op_id is not None)
        self.menu_pieces.clear()
        types = []
        if self.op_id is not None:
            op = da._operation(self.f.conn, self.op_id)
            types = da.pieces_pour(op)
            emises = da.pieces_emises(self.f.conn, self.op_id)
            for t in types:
                lib, n = da.PIECES[t]
                suffixe = f" — رقم {emises[t]:02d}" if t in emises else ""
                self.menu_pieces.addAction(f"{lib} (الملحق {n}){suffixe}", lambda t=t: self.generer_piece(t))
            self.l_pieces.setText("صدرت: " + "، ".join(f"{da.PIECES[t][0]} {n:02d}" for t, n in emises.items())
                                  if emises else "")
        else:
            self.l_pieces.setText("")
        self.b_pieces.setEnabled(bool(types))

    def supprimer(self) -> bool:
        if self.op_id is None:
            return False
        try:
            asso.supprimer(self.f.conn, self.op_id)
        except asso.ErreurAssociation as e:
            message(self.message, str(e), True)
            return False
        self._changer_exercice()
        message(self.message, "حُذفت العملية.")
        return True

    def _selection_budget(self) -> None:
        rows = {i.row() for i in self.budget.selectedIndexes()}
        if len(rows) == 1:
            r = rows.pop()
            self.l_prev.setText(f"المتوقع لبند «{self.budget.item(r, 0).text()}»")
            v = self.budget.item(r, 1).text()
            self.prevu.setText("" if v == "—" else v.replace("\u00a0", ""))

    def enregistrer_prevision(self) -> bool:
        rows = {i.row() for i in self.budget.selectedIndexes()}
        if len(rows) != 1:
            message(self.message, "اختر بنداً من جدول الميزانية.", True)
            return False
        r = rows.pop()
        try:
            asso.definir_prevision(self.f.conn, self.eid, self.budget.item(r, 0).data(Qt.UserRole), self.prevu.text())
        except asso.ErreurAssociation as e:
            message(self.message, str(e), True)
            return False
        self.afficher_budget()
        self.afficher_totaux()
        message(self.message, "حُفظ المبلغ المتوقع.")
        return True

    def enregistrer_association(self) -> bool:
        try:
            d = self.renouvellement.iso() if self.renouvellement.text().strip("/_ ") else ""
        except ValueError:
            message(self.message, "تاريخ التجديد غير صحيح.", True)
            return False
        try:
            asso.modifier_association(self.f.conn, TYPE, self.rib.text(), self.president.text(),
                                      self.tresorier.text(), d)
        except asso.ErreurAssociation as e:
            message(self.message, str(e), True)
            return False
        message(self.message, "حُفظت معطيات الجمعية.")
        return True

    # ---------- وثائق الدليل المسطري ----------

    def _produire(self, fabrique, succes: str) -> Path | None:
        try:
            p = fabrique()
        except (da.ErreurDocAssociation, asso.ErreurAssociation) as e:
            message(self.message, str(e), True)
            return None
        message(self.message, f"{succes}: {p.name}")
        try:
            bureautique.ouvrir(p)
        except Exception:  # noqa: BLE001 — الفتح اختياري
            pass
        return p

    def generer_piece(self, type_: str) -> Path | None:
        oid = self.op_id
        p = self._produire(lambda: da.generer_piece(self.f.conn, self.f.dossier, oid, type_),
                           f"وُلّد {da.PIECES[type_][0]}")
        if p and oid is not None:
            self.op_id = oid
            self._selection_op()
        return p

    def generer_registre(self, kind: str) -> Path | None:
        return self._produire(lambda: da.generer_registre(self.f.conn, self.f.dossier, self.eid, kind),
                              f"وُلّد {da.REGISTRES_DOC[kind][0]}")

    def generer_budget(self) -> Path | None:
        return self._produire(lambda: da.generer_budget(self.f.conn, self.f.dossier, self.eid), "وُلّدت وثيقة الميزانية")

    def passation(self, valeurs: dict | None = None) -> Path | None:
        if valeurs is None:
            dlg = DialoguePassation(self, asso.association(self.f.conn, TYPE)["tresorier"])
            if dlg.exec() != QDialog.Accepted:
                return None
            try:
                valeurs = dlg.valeurs()
            except asso.ErreurAssociation as e:
                message(self.message, str(e), True)
                return None
        maj = valeurs.pop("maj", False)
        p = self._produire(lambda: da.generer_pv_passation(self.f.conn, self.f.dossier, self.eid, **valeurs),
                           "وُلّد محضر تسليم المهام المالية")
        if p and maj:
            a = asso.association(self.f.conn, TYPE)
            asso.modifier_association(self.f.conn, TYPE, a["rib"] or "", a["president"] or "", valeurs["nouveau"],
                                      a["date_renouvellement"] or "")
            self._charger_association()
        return p

    # ---------- السنة المالية والتصدير ----------

    def ouvrir(self, valeurs: dict | None = None) -> int | None:
        """يفتح سنة مالية (valeurs للاختبار، وإلا عبر النافذة)."""
        if valeurs is None:
            d = DialogueExercice(self, premiere=self.exercice.count() == 0)
            if d.exec() != QDialog.Accepted:
                return None
            try:
                valeurs = d.valeurs()
            except asso.ErreurAssociation as e:
                message(self.message, str(e), True)
                return None
        try:
            eid = asso.ouvrir_exercice(self.f.conn, TYPE, **valeurs)
        except asso.ErreurAssociation as e:
            message(self.message, str(e), True)
            return None
        self.eid = eid
        self.rafraichir()
        message(self.message, f"فُتحت السنة المالية {self.exercice.currentText()}.")
        return eid

    def exporter(self, chemin: Path | None = None) -> Path | None:
        if self.eid is None:
            return None
        if chemin is None:
            nom = f"جمعية النجاح {self.exercice.currentText().replace('/', '-')}.xlsx"
            f, _ = QFileDialog.getSaveFileName(self, "تصدير السجلات", str(Path.home() / nom), "Excel (*.xlsx)")
            if not f:
                return None
            chemin = Path(f)
        p = asso.exporter_excel(self.f.conn, self.eid, chemin)
        message(self.message, f"صُدّرت السجلات إلى {p}.")
        try:
            bureautique.ouvrir(p)
        except Exception:  # noqa: BLE001 — الفتح اختياري
            pass
        return p
