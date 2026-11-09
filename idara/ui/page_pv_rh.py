"""محاضر الموارد البشرية (طلب المدير 2026-11-09): محضر الالتحاق بالعمل، ومحضرا الدخول والخروج مع لائحة من لم
يوقعوا."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QTableWidgetItem, QVBoxLayout, QWidget

from idara.services import bureautique
from idara.services import documents as dc
from idara.services import etablissement as etab_srv
from idara.services import pv_rh as pv
from idara.ui.composants import bouton, carte, entete
from idara.ui.formulaires import champ
from idara.ui.page_pedagogie import _grille
from idara.ui.saisie import ChampDate, cellule, message, tableau


class PagePvRh(QWidget):
    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        racine = QVBoxLayout(self)
        racine.setContentsMargins(40, 32, 40, 32)
        racine.setSpacing(18)
        racine.addWidget(entete("محاضر الموارد البشرية",
                                "محضر الالتحاق بالعمل لكل موظف يلتحق بالمؤسسة، ومحضرا الدخول والخروج مع لائحة من "
                                "لم يوقعوا."))
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.hide()
        racine.addWidget(self.message)

        # ---- محضر الالتحاق ----
        c, v = carte("محضر الالتحاق بالعمل")
        self.personnel = QComboBox()
        self.cas = QComboBox()
        for i, lib in enumerate(pv.CAS, start=1):
            self.cas.addItem(lib, i)
        self.date_prise = ChampDate()
        self.date_redaction = ChampDate()
        self.reference = champ("رقم الرسالة الوزارية أو المقرر وتاريخه")
        self.ancien_lieu = champ("المؤسسة أو المديرية السابقة")
        self.lieu_naissance = champ("مكان الازدياد")
        self.mission = champ("التدريس (افتراضياً حسب ملف الموظف)")
        v.addLayout(_grille([("الموظف(ة)", self.personnel), ("الحالة", self.cas),
                             ("تاريخ الالتحاق", self.date_prise), ("تاريخ التحرير (اختياري)", self.date_redaction),
                             ("مراجع الرسالة الوزارية", self.reference), ("مقر العمل السابق", self.ancien_lieu),
                             ("مكان الازدياد", self.lieu_naissance), ("المهمة", self.mission)]))
        n = QLabel("تؤخذ باقي البيانات (رقم التأجير، البطاقة الوطنية، الإطار، تاريخ الازدياد، العنوان) من ملف "
                   "الموظف في «معلومات الأطر».")
        n.setObjectName("etiquette")
        n.setWordWrap(True)
        v.addWidget(n)
        h = QHBoxLayout()
        b = QPushButton("حفظ وتوليد المحضر (Word)")
        b.setObjectName("principal")
        b.clicked.connect(lambda: self.enregistrer_prise())
        bg = QPushButton("إعادة توليد المحدد")
        bg.clicked.connect(lambda: self.regenerer_prise())
        bs = bouton("حذف المحضر المحدد")
        bs.clicked.connect(lambda: self.supprimer_prise())
        for x in (b, bg, bs):
            h.addWidget(x)
        h.addStretch()
        v.addLayout(h)
        self.t_prises = tableau(["الموظف(ة)", "الحالة", "تاريخ الالتحاق"], etirer=0)
        self.t_prises.setMinimumHeight(200)
        v.addWidget(self.t_prises)
        racine.addWidget(c)

        # ---- محضر الدخول / الخروج ----
        c, v = carte("محضر الدخول / محضر الخروج")
        self.sens = QComboBox()
        for k, lib in pv.SENS.items():
            self.sens.addItem(lib, k)
        self.concerne = QComboBox()
        for k, lib in pv.CONCERNE.items():
            self.concerne.addItem(lib, k)
        self.unite = QComboBox()
        self.l_unite = QLabel("الوحدة المدرسية")
        self.date_pv = ChampDate()
        v.addLayout(_grille([("المحضر", self.sens), ("يهم", self.concerne), ("التاريخ", self.date_pv)]))
        hu = QHBoxLayout()
        hu.addWidget(self.l_unite)
        hu.addWidget(self.unite)
        hu.addStretch()
        v.addLayout(hu)
        for cb in (self.concerne, self.unite):
            cb.currentIndexChanged.connect(lambda _: self.remplir_signataires())
        n = QLabel("أشّر على من لم يوقع واكتب السبب؛ إن وقّع الجميع تحمل اللائحة «لا أحد».")
        n.setObjectName("etiquette")
        n.setWordWrap(True)
        v.addWidget(n)
        self.t_sign = tableau(["لم يوقع", "الاسم الكامل", "رقم التأجير", "سبب عدم التوقيع"], etirer=3)
        self.t_sign.setMinimumHeight(280)
        self.t_sign.setEditTriggers(self.t_sign.EditTrigger.AllEditTriggers)
        v.addWidget(self.t_sign)
        h = QHBoxLayout()
        b = QPushButton("حفظ وتوليد المحضر ولائحة من لم يوقعوا (Word)")
        b.setObjectName("principal")
        b.clicked.connect(lambda: self.generer_collectif())
        h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        self.l_collectifs = QLabel()
        self.l_collectifs.setObjectName("etiquette")
        self.l_collectifs.setWordWrap(True)
        v.addWidget(self.l_collectifs)
        racine.addWidget(c)
        racine.addStretch()
        self.rafraichir()

    # ---------- التحميل ----------
    def rafraichir(self) -> None:
        actuel = self.personnel.currentData()
        self.personnel.clear()
        self.personnel.addItem("— اختر —", None)
        for r in self.f.conn.execute("SELECT id, prenom_ar || ' ' || nom_ar AS nom FROM personnel WHERE "
                                     "statut='actif' AND categorie<>'directeur' ORDER BY nom_ar, prenom_ar"):
            self.personnel.addItem(r["nom"], r["id"])
        self.personnel.setCurrentIndex(max(0, self.personnel.findData(actuel)))
        if not _rempli(self.date_prise):
            self.date_prise.definir(date.today().isoformat())
        if not _rempli(self.date_pv):
            self.date_pv.definir(date.today().isoformat())
        unites = etab_srv.unites(self.f.conn)
        u = self.unite.currentData()
        self.unite.blockSignals(True)
        self.unite.clear()
        self.unite.addItem("المؤسسة كاملة", None)
        for x in unites:
            self.unite.addItem(x, x)
        self.unite.setCurrentIndex(max(0, self.unite.findData(u)))
        self.unite.blockSignals(False)
        self.unite.setVisible(bool(unites))
        self.l_unite.setVisible(bool(unites))
        self._prises()
        self.remplir_signataires()
        cs = pv.lister_collectifs(self.f.conn)[:5]
        self.l_collectifs.setText("آخر المحاضر: " + "، ".join(
            f"{pv.SENS[r['sens']]} {pv.CONCERNE[r['concerne']]} ({r['date_pv']})" for r in cs) if cs else "")

    def _prises(self) -> None:
        self.prises = pv.lister_prises(self.f.conn)
        self.t_prises.setRowCount(len(self.prises))
        for i, r in enumerate(self.prises):
            self.t_prises.setItem(i, 0, cellule(r["nom"], r["id"]))
            self.t_prises.setItem(i, 1, cellule(pv.CAS[r["cas"] - 1]))
            self.t_prises.setItem(i, 2, cellule(r["date_prise"]))

    def remplir_signataires(self) -> None:
        self.signataires = pv.personnels(self.f.conn, self.concerne.currentData() or "enseignants",
                                         self.unite.currentData())
        t = self.t_sign
        t.setRowCount(len(self.signataires))
        for i, p in enumerate(self.signataires):
            it = QTableWidgetItem()
            it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Unchecked)
            it.setData(Qt.UserRole, p["id"])
            t.setItem(i, 0, it)
            t.setItem(i, 1, cellule(f"{p['prenom_ar']} {p['nom_ar']}"))
            t.setItem(i, 2, cellule(p["ppr"] or ""))
            t.setItem(i, 3, QTableWidgetItem(""))

    # ---------- الأفعال ----------
    def _ouvrir(self, chemin) -> None:
        try:
            bureautique.ouvrir(chemin)
        except Exception:  # noqa: BLE001
            pass

    def enregistrer_prise(self):
        if self.personnel.currentData() is None:
            message(self.message, "اختر الموظف(ة).", True)
            return None
        try:
            d, dr = self.date_prise.iso(), self.date_redaction.iso()
        except ValueError:
            message(self.message, "أحد التواريخ غير صحيح.", True)
            return None
        try:
            vid = pv.enregistrer_prise(self.f.conn, pv.PriseService(
                self.personnel.currentData(), d or "", self.cas.currentData(), self.reference.text(),
                self.ancien_lieu.text(), self.lieu_naissance.text(), self.mission.text(), dr or ""))
            doc = pv.generer_prise(self.f.conn, self.f.dossier, vid)
        except (pv.ErreurPV, dc.ErreurDocument) as e:
            message(self.message, str(e), True)
            self._prises()
            return None
        self._prises()
        message(self.message, f"وُلّد محضر الالتحاق: {doc.chemin.name}")
        self._ouvrir(doc.chemin)
        return doc

    def _pv_selectionne(self) -> int | None:
        rows = self.t_prises.selectionModel().selectedRows()
        return self.t_prises.item(rows[0].row(), 0).data(Qt.UserRole) if rows else None

    def regenerer_prise(self):
        vid = self._pv_selectionne()
        if vid is None:
            message(self.message, "حدد المحضر في الجدول.", True)
            return None
        try:
            doc = pv.generer_prise(self.f.conn, self.f.dossier, vid)
        except (pv.ErreurPV, dc.ErreurDocument) as e:
            message(self.message, str(e), True)
            return None
        self._ouvrir(doc.chemin)
        return doc

    def supprimer_prise(self) -> None:
        vid = self._pv_selectionne()
        if vid is None:
            message(self.message, "حدد المحضر في الجدول.", True)
            return
        pv.supprimer_prise(self.f.conn, vid)
        self._prises()

    def cocher(self, ligne: int, motif: str) -> None:
        self.t_sign.item(ligne, 0).setCheckState(Qt.Checked)
        self.t_sign.item(ligne, 3).setText(motif)

    def generer_collectif(self):
        try:
            d = self.date_pv.iso()
        except ValueError:
            message(self.message, "تاريخ المحضر غير صحيح.", True)
            return None
        non = [(self.t_sign.item(i, 0).data(Qt.UserRole), self.t_sign.item(i, 3).text())
               for i in range(self.t_sign.rowCount()) if self.t_sign.item(i, 0).checkState() == Qt.Checked]
        try:
            vid = pv.enregistrer_collectif(self.f.conn, self.sens.currentData(), self.concerne.currentData(),
                                           d or "", non, self.unite.currentData())
            doc, doc2 = pv.generer_collectif(self.f.conn, self.f.dossier, vid)
        except (pv.ErreurPV, dc.ErreurDocument) as e:
            message(self.message, str(e), True)
            return None
        message(self.message, f"وُلّد {self.sens.currentText()} ولائحة من لم يوقعوا.")
        self._ouvrir(doc.chemin)
        self._ouvrir(doc2.chemin)
        self.rafraichir()
        return doc, doc2



def _rempli(c: ChampDate) -> bool:
    return bool(c.text().replace("_", "").replace("/", "").strip())
