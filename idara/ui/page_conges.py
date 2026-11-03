"""صفحتا الرخص وسجل الصادر: ملف رخصة واحد يولد سلسلة وثائقه."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDialog, QDialogButtonBox,
                               QFormLayout, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from idara.services import bureautique
from idara.services import conges as cg
from idara.services import documents as dc
from idara.services import personnel as rh
from idara.services import textes as tx
from idara.ui.composants import bouton, carte, entete
from idara.ui.formulaires import champ, etiquette
from idara.ui.saisie import ChampDate, cellule, message, tableau


def _ouvrir(label: QLabel, doc) -> None:
    message(label, f"وُلّدت الوثيقة وأُرشفت: ⁦{doc.chemin.name}⁩")
    try:
        bureautique.ouvrir(doc.chemin)
    except OSError as e:
        message(label, f"وُلّدت الوثيقة لكن تعذر فتحها: {e}", True)


def _grille(champs: list[tuple[str, QWidget]], colonnes: int = 2) -> QGridLayout:
    g = QGridLayout()
    g.setHorizontalSpacing(16)
    g.setVerticalSpacing(4)
    for i, (lib, w) in enumerate(champs):
        g.addWidget(etiquette(lib, w), (i // colonnes) * 2, i % colonnes)
        g.addWidget(w, (i // colonnes) * 2 + 1, i % colonnes)
    return g


def _boutons(dialogue: QDialog, ok: str) -> QDialogButtonBox:
    b = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    b.button(QDialogButtonBox.Ok).setText(ok)
    b.button(QDialogButtonBox.Cancel).setText("إلغاء")
    b.accepted.connect(dialogue.accept)
    b.rejected.connect(dialogue.reject)
    return b


class DialogueBordereau(QDialog):
    """ورقة إرسال: الوثائق وعدد نسخها، تُسجل في الصادر برقم جديد."""

    def __init__(self, parent, pieces: list[tuple[str, int]], objet: str, bureau: str = "bureau_conges"):
        super().__init__(parent)
        self.setWindowTitle("ورقة إرسال")
        self.setLayoutDirection(Qt.RightToLeft)
        self.resize(620, 460)
        v = QVBoxLayout(self)
        f = QFormLayout()
        self.objet = champ()
        self.objet.setText(objet)
        self.le = ChampDate()
        self.le.definir(date.today().isoformat())
        self.bureau = QComboBox()
        self.bureau.addItem("مكتب الرخص والتغيبات (إعداد المراسلات)", "bureau_conges")
        self.bureau.addItem("مكتب تسيير المؤسسات (إعداد المراسلات)", "bureau_etablissements")
        self.bureau.setCurrentIndex(max(0, self.bureau.findData(bureau)))
        f.addRow("الموضوع (لسجل الصادر)", self.objet)
        f.addRow("التاريخ", self.le)
        f.addRow("المكتب", self.bureau)
        v.addLayout(f)
        v.addWidget(QLabel("الوثائق المرسلة (8 على الأكثر):"))
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["نوع الإرسالية", "عدد النسخ"])
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(0, self.table.horizontalHeader().ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        v.addWidget(self.table, 1)
        for d, n in pieces:
            self.ajouter(d, n)
        h = QHBoxLayout()
        b1 = QPushButton("+ سطر")
        b1.clicked.connect(lambda: self.ajouter("", 1))
        b2 = bouton("حذف السطر المحدد")
        b2.clicked.connect(lambda: self.table.removeRow(self.table.currentRow()))
        h.addWidget(b1)
        h.addWidget(b2)
        h.addStretch()
        v.addLayout(h)
        v.addWidget(_boutons(self, "تسجيل في الصادر وتوليد الورقة"))

    def ajouter(self, designation: str, n: int) -> None:
        i = self.table.rowCount()
        self.table.insertRow(i)
        self.table.setItem(i, 0, QTableWidgetItem(designation))
        s = QSpinBox()
        s.setRange(1, 99)
        s.setValue(n)
        self.table.setCellWidget(i, 1, s)

    def pieces(self) -> list[tuple[str, int]]:
        return [((self.table.item(i, 0).text() if self.table.item(i, 0) else ""), self.table.cellWidget(i, 1).value())
                for i in range(self.table.rowCount())]


class DialogueReprise(QDialog):
    def __init__(self, parent, conn, r: cg.Reprise | None, personnels: list[rh.Personnel]):
        super().__init__(parent)
        self.setWindowTitle("محضر استئناف العمل")
        self.setLayoutDirection(Qt.RightToLeft)
        v = QVBoxLayout(self)
        f = QFormLayout()
        self.personnel = QComboBox()
        for p in personnels:
            self.personnel.addItem(f"{p.prenom_ar} {p.nom_ar}", p.id)
        self.cas = QComboBox()
        for c in cg.cas_reprise(conn):
            self.cas.addItem(c["libelle_ar"], c["id"])
        self.debut, self.fin, self.reprise = ChampDate(), ChampDate(), ChampDate()
        self.contacts = champ("اختياري")
        self.conge_id = r.conge_id if r else None
        if r:
            self.personnel.setCurrentIndex(max(0, self.personnel.findData(r.personnel_id)))
            self.personnel.setEnabled(False)
            self.cas.setCurrentIndex(max(0, self.cas.findData(r.cas_reprise_id)))
            self.debut.definir(r.date_debut_absence)
            self.fin.definir(r.date_fin_absence)
            self.reprise.definir(r.date_reprise)
        else:
            self.cas.setCurrentIndex(self.cas.count() - 1)  # تغيب أو انقطاع
        f.addRow("الموظف", self.personnel)
        f.addRow("الحالة", self.cas)
        f.addRow("بداية الغياب", self.debut)
        f.addRow("نهاية الغياب", self.fin)
        f.addRow("تاريخ استئناف العمل", self.reprise)
        f.addRow("وسائل أخرى للاتصال", self.contacts)
        v.addLayout(f)
        v.addWidget(_boutons(self, "تسجيل وتوليد المحضر"))

    def lire(self) -> cg.Reprise:
        try:
            dates = [w.iso() for w in (self.debut, self.fin, self.reprise)]
        except ValueError:
            raise cg.ErreurConge("أحد التواريخ غير صحيح.") from None
        return cg.Reprise(self.personnel.currentData(), self.cas.currentData(), *dates, conge_id=self.conge_id,
                          autres_contacts=self.contacts.text())


class PageConges(QWidget):
    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        self.cid: int | None = None
        racine = QVBoxLayout(self)
        racine.setContentsMargins(40, 32, 40, 32)
        racine.setSpacing(16)
        racine.addWidget(entete("الرخص", "ملف رخصة يُدخل مرة واحدة، ومنه يُولد الطلب وإيصال الشهادة الطبية "
                                         "وطلب التعويض وورقة الإرسال ومحضر الاستئناف."))
        self.alertes = QLabel()
        self.alertes.setObjectName("alerte")
        self.alertes.setWordWrap(True)
        racine.addWidget(self.alertes)
        self.l_radaa = QLabel()
        self.l_radaa.setObjectName("info")
        self.l_radaa.setWordWrap(True)
        self.l_radaa.hide()
        racine.addWidget(self.l_radaa)
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.hide()
        racine.addWidget(self.message)
        corps = QHBoxLayout()
        corps.setSpacing(20)
        racine.addLayout(corps, 1)

        # ---- اللائحة ----
        c, cv = carte()
        self.liste = tableau(["الرخصة", "الحالة"], etirer=0)
        h = self.liste.horizontalHeader()
        for i, l in ((1, 95),):
            h.setSectionResizeMode(i, h.ResizeMode.Fixed)
            h.resizeSection(i, l)
        self.liste.setMinimumHeight(420)
        self.liste.itemSelectionChanged.connect(self._selection)
        cv.addWidget(self.liste, 1)
        b = QPushButton("+ رخصة جديدة")
        b.clicked.connect(self.nouveau)
        cv.addWidget(b)
        b2 = QPushButton("محضر استئناف بعد تغيب (دون رخصة)")
        b2.clicked.connect(lambda: self.dialogue_reprise(None))
        cv.addWidget(b2)
        corps.addWidget(c, 5)

        # ---- الملف ----
        c2, fv = carte()
        self.titre = QLabel("رخصة جديدة")
        self.titre.setObjectName("titreCarte")
        fv.addWidget(self.titre)
        self.personnel = QComboBox()
        self.personnel.currentIndexChanged.connect(lambda _: self._maj_prolongations())
        self.type = QComboBox()
        self.type.currentIndexChanged.connect(lambda _: self._maj_type())
        self.prolongation = QComboBox()
        self.debut = ChampDate()
        self.duree = QSpinBox()
        self.duree.setRange(1, 1100)
        self.duree.setSuffix(" يوماً")
        self.duree.setLayoutDirection(Qt.LeftToRight)
        self.fin = QLabel()
        self.duree.valueChanged.connect(lambda _: self._maj_fin())
        self.debut.textChanged.connect(lambda _: self._maj_fin())
        self.motif, self.adresse = champ("مرض، الولادة..."), champ()
        self.date_demande = ChampDate()
        self.avis, self.mesures, self.pieces = champ(), champ("مثال: توزيع التلاميذ على الأقسام"), champ("اختياري")
        fv.addLayout(_grille([("الموظف *", self.personnel), ("نوع الرخصة *", self.type),
                              ("تمديد لرخصة سابقة", self.prolongation), ("تاريخ الطلب", self.date_demande),
                              ("تاريخ البداية *", self.debut), ("المدة *", self.duree)]))
        fv.addWidget(self.fin)
        # رخصة الرضاعة: ساعة يومياً إلى بلوغ الطفل 24 شهراً (الفصل 46، القانون 30.22)
        self.zone_radaa = QWidget()
        zr = QVBoxLayout(self.zone_radaa)
        zr.setContentsMargins(0, 0, 0, 0)
        self.naissance = ChampDate()
        self.naissance.textChanged.connect(lambda _: self._proposer_radaa())
        self.horaire = champ("مثال: 11:00 - 12:00", ltr=True)
        zr.addLayout(_grille([("تاريخ ازدياد الطفل (أو الكفالة) *", self.naissance),
                              ("الساعة المخصصة يومياً", self.horaire)]))
        n = QLabel("ساعة واحدة في اليوم، من انتهاء رخصة الولادة أو الكفالة إلى أن يبلغ الطفل 24 شهراً "
                   "(الفصل 46 من النظام الأساسي العام للوظيفة العمومية، كما غُيّر بالقانون 30.22). "
                   "تُقترح البداية والمدة آلياً من تاريخ الازدياد ومن رخصة الولادة المسجلة.")
        n.setObjectName("sousTitre")
        n.setWordWrap(True)
        zr.addWidget(n)
        self.zone_radaa.hide()
        fv.addWidget(self.zone_radaa)
        fv.addLayout(_grille([("السبب", self.motif), ("عنوان الإقامة خلال الرخصة", self.adresse),
                              ("رأي المدير", self.avis), ("الإجراءات المتخذة في سير الدراسة", self.mesures),
                              ("المرفقات", self.pieces)]))
        t = QLabel("الشهادة الطبية")
        t.setObjectName("titreCarte")
        fv.addWidget(t)
        self.medecin = champ("الدكتور(ة) ...")
        self.specialite, self.deposant = champ(), champ("قد يكون شخصاً آخر")
        self.deposant_cin = champ(ltr=True)
        self.recu_le = ChampDate()
        self.duree_cert = QSpinBox()
        self.duree_cert.setRange(0, 1100)
        self.duree_cert.setSpecialValueText("نفس مدة الرخصة")
        self.rem_cert = champ("اختياري")
        fv.addLayout(_grille([("الطبيب", self.medecin), ("التخصص", self.specialite),
                              ("تاريخ تسلم الشهادة", self.recu_le), ("مدة الشهادة", self.duree_cert),
                              ("المدلي بالشهادة", self.deposant), ("رقم بطاقته الوطنية", self.deposant_cin),
                              ("ملاحظات الإيصال", self.rem_cert)]))
        b_save = QPushButton("حفظ ملف الرخصة")
        b_save.setObjectName("principal")
        b_save.clicked.connect(self.enregistrer)
        fv.addWidget(b_save, 0, Qt.AlignRight)

        t = QLabel("الوثائق")
        t.setObjectName("titreCarte")
        fv.addWidget(t)
        self.zone_docs = QWidget()
        g = QGridLayout(self.zone_docs)
        g.setContentsMargins(0, 0, 0, 0)
        self.b_demande = QPushButton("طلب الرخصة (يُسجل في الصادر)")
        self.b_demande.clicked.connect(lambda: self._generer(cg.generer_demande))
        self.b_recu = QPushButton("إيصال الشهادة الطبية")
        self.b_recu.clicked.connect(lambda: self._generer(cg.generer_recu))
        self.b_remp = QPushButton("طلب تعويض")
        self.b_remp.clicked.connect(lambda: self._generer(cg.generer_remplacement))
        self.b_bord = QPushButton("ورقة الإرسال")
        self.b_bord.clicked.connect(self.dialogue_bordereau)
        self.b_reprise = QPushButton("محضر استئناف العمل")
        self.b_reprise.clicked.connect(lambda: self.dialogue_reprise(self.cid))
        for i, b in enumerate((self.b_demande, self.b_recu, self.b_remp, self.b_bord, self.b_reprise)):
            g.addWidget(b, i // 2, i % 2)
        fv.addWidget(self.zone_docs)
        self.docs = tableau(["الوثيقة", "التاريخ"], etirer=0)
        self.docs.setMinimumHeight(120)
        self.docs.cellDoubleClicked.connect(self._ouvrir_doc)
        fv.addWidget(self.docs)

        # ---- صيغ المراسلات ----
        t = QLabel("صيغ المراسلات (تُكتب في كل الوثائق)")
        t.setObjectName("titreCarte")
        fv.addWidget(t)
        self.params = {k: champ() for k in cg.PARAMETRES}
        fv.addLayout(_grille([(lib, self.params[k]) for k, (lib, _) in cg.PARAMETRES.items()], 1))
        b_p = QPushButton("حفظ الصيغ")
        b_p.clicked.connect(self.enregistrer_parametres)
        fv.addWidget(b_p, 0, Qt.AlignRight)
        fv.addStretch()
        corps.addWidget(c2, 7)
        self.rafraichir()
        self.nouveau()

    # ---------- اللائحة ----------

    def rafraichir(self) -> None:
        conn = self.f.conn
        actuel = self.personnel.currentData()
        self.personnels = rh.lister(conn)
        self.personnel.blockSignals(True)
        self.personnel.clear()
        for p in self.personnels:
            self.personnel.addItem(f"{p.prenom_ar} {p.nom_ar}", p.id)
        self.personnel.setCurrentIndex(max(0, self.personnel.findData(actuel)))
        self.personnel.blockSignals(False)
        if self.type.count() == 0:
            for t in cg.types_conge(conn):
                self.type.addItem(t["libelle_ar"], t["id"])
        for k, v in cg.parametres(conn).items():
            self.params[k].setText(v)
        attendues = cg.rentrees_attendues(conn)
        self.alertes.setText("رخص انتهت دون محضر استئناف: " + "، ".join(
            f"{r['prenom_ar']} {r['nom_ar']} (انتهت {tx.date_chiffres(r['date_fin'])})" for r in attendues)
            if attendues else "")
        self.alertes.setVisible(bool(attendues))
        radaa = cg.allaitements_en_cours(conn)
        self.l_radaa.setText("رخص رضاعة جارية: " + "، ".join(
            f"{r['prenom_ar']} {r['nom_ar']} ({r['horaire_allaitement'] or 'الساعة غير محددة'}، "
            f"إلى {tx.date_chiffres(r['date_fin'])})" for r in radaa) if radaa else "")
        self.l_radaa.setVisible(bool(radaa))
        lignes = cg.lister(conn)
        aujourdhui = date.today().isoformat()
        self.liste.setRowCount(len(lignes))
        for i, r in enumerate(lignes):
            etat = ("مستأنفة" if r["reprise_id"] else "جارية" if r["date_fin"] >= aujourdhui
                    else "دون استئناف" if any(a["id"] == r["id"] for a in attendues) else "ممدَّدة")
            it = cellule(f"{r['prenom_ar']} {r['nom_ar']} · {tx.date_chiffres(r['date_debut'])}", r["id"])
            it.setToolTip(f"{r['type']}: من {tx.date_chiffres(r['date_debut'])} إلى {tx.date_chiffres(r['date_fin'])}")
            self.liste.setItem(i, 0, it)
            self.liste.setItem(i, 1, cellule(etat))

    def _selection(self) -> None:
        lignes = {i.row() for i in self.liste.selectedIndexes()}
        if len(lignes) == 1:
            self.afficher(self.liste.item(lignes.pop(), 0).data(Qt.UserRole))

    # ---------- الملف ----------

    def _maj_type(self) -> None:
        if not self.motif.text() or self.motif.text() in ("مرض", "الولادة", "الرضاعة"):
            self.motif.setText(cg.motif_defaut(self.type.currentText()))
        self.zone_radaa.setVisible(self.type.currentText() == cg.RADAA)
        self._proposer_radaa()

    def _proposer_radaa(self) -> None:
        """البداية والمدة المقترحتان لرخصة الرضاعة (رخصة جديدة فقط)."""
        if self.type.currentText() != cg.RADAA or self.cid is not None:
            return
        try:
            n = self.naissance.iso()
        except ValueError:
            return
        if not n:
            return
        debut, fin = cg.periode_allaitement(self.f.conn, self.personnel.currentData(), n)
        self.debut.definir(debut)
        self.duree.setValue(max(1, (date.fromisoformat(fin) - date.fromisoformat(debut)).days + 1))

    def _maj_prolongations(self, choix: int | None = None) -> None:
        self.prolongation.clear()
        self.prolongation.addItem("— لا —", None)
        pid = self.personnel.currentData()
        if pid:
            for r in cg.lister(self.f.conn, pid):
                if r["id"] != self.cid:
                    self.prolongation.addItem(f"{r['type']} من {tx.date_chiffres(r['date_debut'])} "
                                              f"إلى {tx.date_chiffres(r['date_fin'])}", r["id"])
        self.prolongation.setCurrentIndex(max(0, self.prolongation.findData(choix)))

    def _maj_fin(self) -> None:
        try:
            d = self.debut.iso()
        except ValueError:
            d = ""
        if d:
            fin = cg.Conge(date_debut=d, duree_jours=self.duree.value()).date_fin
            self.fin.setText(f"تنتهي الرخصة يوم {tx.date_ar(fin)}، والاستئناف المتوقع في اليوم الموالي.")
        else:
            self.fin.setText("")

    def nouveau(self) -> None:
        self.cid = None
        self.liste.clearSelection()
        self.titre.setText("رخصة جديدة")
        self.personnel.setEnabled(True)
        for w in (self.motif, self.adresse, self.avis, self.mesures, self.pieces, self.medecin, self.specialite,
                  self.deposant, self.deposant_cin, self.rem_cert, self.debut, self.recu_le, self.naissance,
                  self.horaire):
            w.clear()
        self.date_demande.definir(date.today().isoformat())
        self.duree.setValue(1)
        self.duree_cert.setValue(0)
        self._maj_prolongations()
        self._maj_type()
        self.zone_docs.setEnabled(False)
        self.docs.setRowCount(0)
        self.message.hide()

    def afficher(self, cid: int) -> None:
        c = cg.lire(self.f.conn, cid)
        self.cid = cid
        self.personnel.setCurrentIndex(max(0, self.personnel.findData(c.personnel_id)))
        self.personnel.setEnabled(False)
        self.type.setCurrentIndex(max(0, self.type.findData(c.type_conge_id)))
        self._maj_prolongations(c.prolongation_de)
        self.debut.definir(c.date_debut)
        self.duree.setValue(int(c.duree_jours))
        self.date_demande.definir(c.date_demande or None)
        for w, v in ((self.motif, c.motif), (self.adresse, c.adresse_conge), (self.avis, c.avis_directeur),
                     (self.mesures, c.mesures_prises), (self.pieces, c.pieces), (self.medecin, c.medecin),
                     (self.specialite, c.specialite), (self.deposant, c.certificat_remis_par),
                     (self.deposant_cin, c.certificat_remis_par_cin), (self.rem_cert, c.remarques_certificat)):
            w.setText(v or "")
        self.recu_le.definir(c.certificat_recu_le or None)
        self.naissance.definir(c.date_naissance_enfant or None)
        self.horaire.setText(c.horaire_allaitement or "")
        self.duree_cert.setValue(int(c.certificat_duree_jours or 0))
        p = rh.lire(self.f.conn, c.personnel_id)
        self.titre.setText(f"{p.prenom_ar} {p.nom_ar} · {self.type.currentText()}")
        self.zone_docs.setEnabled(True)
        radaa = cg.est_allaitement(self.f.conn, c.type_conge_id)   # ساعة يومية: لا تعويض ولا استئناف
        self.b_remp.setEnabled(p.categorie in ("enseignant", "educatrice") and not radaa)
        self.b_recu.setEnabled(bool(c.medecin))
        deja = self.f.conn.execute("SELECT 1 FROM reprise_travail WHERE conge_id=?", (cid,)).fetchone()
        self.b_reprise.setEnabled(not deja and not c.prolongation_de and not radaa)
        docs = cg.documents(self.f.conn, cid)
        self.docs.setRowCount(len(docs))
        for i, d in enumerate(docs):
            self.docs.setItem(i, 0, cellule(d["titre"], d["fichier_archive"]))
            self.docs.setItem(i, 1, cellule(d["date_generation"][:16]))
        self.message.hide()

    def lire_formulaire(self) -> cg.Conge:
        try:
            debut, demande, recu = self.debut.iso(), self.date_demande.iso(), self.recu_le.iso()
            naissance = self.naissance.iso() if self.type.currentText() == cg.RADAA else ""
        except ValueError:
            raise cg.ErreurConge("أحد التواريخ غير صحيح.") from None
        return cg.Conge(personnel_id=self.personnel.currentData(), type_conge_id=self.type.currentData(),
                        date_debut=debut, duree_jours=self.duree.value(), motif=self.motif.text(),
                        adresse_conge=self.adresse.text(), date_demande=demande,
                        prolongation_de=self.prolongation.currentData(), avis_directeur=self.avis.text(),
                        mesures_prises=self.mesures.text(), pieces=self.pieces.text(), medecin=self.medecin.text(),
                        specialite=self.specialite.text(), certificat_recu_le=recu,
                        certificat_remis_par=self.deposant.text(), certificat_remis_par_cin=self.deposant_cin.text(),
                        certificat_duree_jours=self.duree_cert.value() or None,
                        remarques_certificat=self.rem_cert.text(), date_naissance_enfant=naissance,
                        horaire_allaitement=self.horaire.text(), id=self.cid)

    def enregistrer(self) -> int | None:
        try:
            c = self.lire_formulaire()
            if c.id:
                c.demande_remplacement = cg.lire(self.f.conn, c.id).demande_remplacement
            cid = cg.enregistrer(self.f.conn, c)
        except (cg.ErreurConge, rh.ErreurPersonnel) as e:
            message(self.message, str(e), True)
            return None
        self.rafraichir()
        self.afficher(cid)
        message(self.message, "حُفظ ملف الرخصة. يمكنك الآن توليد وثائقه.")
        return cid

    def _generer(self, fonction):
        try:
            doc = fonction(self.f.conn, self.f.dossier, self.cid)
        except (cg.ErreurConge, dc.ErreurDocument) as e:
            message(self.message, str(e), True)
            return None
        self.rafraichir()
        self.afficher(self.cid)
        _ouvrir(self.message, doc)
        return doc

    def dialogue_bordereau(self) -> None:
        c = cg.lire(self.f.conn, self.cid)
        p = rh.lire(self.f.conn, c.personnel_id)
        d = DialogueBordereau(self, cg.pieces_proposees(self.f.conn, c), f"ملف رخصة {p.prenom_ar} {p.nom_ar}")
        if d.exec() == QDialog.Accepted:
            try:
                le = d.le.iso() or None
            except ValueError:
                message(self.message, "التاريخ غير صحيح.", True)
                return
            self.bordereau(d.pieces(), d.objet.text(), le, d.bureau.currentData())

    def bordereau(self, pieces, objet: str, le: str | None = None, bureau: str = "bureau_conges"):
        try:
            doc = cg.generer_bordereau(self.f.conn, self.f.dossier, pieces, objet, le, self.cid, bureau)
        except (cg.ErreurConge, dc.ErreurDocument) as e:
            message(self.message, str(e), True)
            return None
        self.afficher(self.cid)
        _ouvrir(self.message, doc)
        return doc

    def dialogue_reprise(self, cid: int | None) -> None:
        r = cg.proposition_reprise(self.f.conn, cid) if cid else None
        d = DialogueReprise(self, self.f.conn, r, self.personnels)
        if d.exec() == QDialog.Accepted:
            try:
                self.reprise(d.lire())
            except cg.ErreurConge as e:
                message(self.message, str(e), True)

    def reprise(self, r: cg.Reprise):
        try:
            rid = cg.enregistrer_reprise(self.f.conn, r)
            doc = cg.generer_reprise(self.f.conn, self.f.dossier, rid)
        except (cg.ErreurConge, dc.ErreurDocument) as e:
            message(self.message, str(e), True)
            return None
        self.rafraichir()
        if self.cid:
            self.afficher(self.cid)
        _ouvrir(self.message, doc)
        return doc

    def enregistrer_parametres(self) -> None:
        try:
            cg.definir_parametres(self.f.conn, {k: w.text() for k, w in self.params.items()})
        except cg.ErreurConge as e:
            message(self.message, str(e), True)
            return
        message(self.message, "حُفظت صيغ المراسلات.")

    def _ouvrir_doc(self, ligne: int, _col: int) -> None:
        try:
            bureautique.ouvrir(self.f.dossier.racine / self.docs.item(ligne, 0).data(Qt.UserRole))
        except OSError as e:
            message(self.message, f"تعذر فتح الملف: {e}", True)


class PageSortants(QWidget):
    """سجل الصادر: ترقيم آلي «رقم/سنة دراسية» يبدأ من 1 كل سنة."""

    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        racine = QVBoxLayout(self)
        racine.setContentsMargins(40, 32, 40, 32)
        racine.setSpacing(16)
        racine.addWidget(entete("سجل الصادر", "كل وثيقة صادرة تأخذ رقمها من هذا السجل: طلبات الرخص وأوراق الإرسال "
                                               "تُسجَّل آلياً، ويمكن تسجيل أي مراسلة أخرى يدوياً."))
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.hide()
        racine.addWidget(self.message)
        c, v = carte()
        h = QHBoxLayout()
        self.objet = champ("موضوع المراسلة")
        self.le = ChampDate()
        self.le.definir(date.today().isoformat())
        b = QPushButton("تسجيل")
        b.setObjectName("principal")
        b.clicked.connect(self.ajouter)
        self.prochain = QLabel()
        h.addWidget(self.prochain)
        h.addWidget(self.objet, 1)
        h.addWidget(self.le)
        h.addWidget(b)
        v.addLayout(h)
        b2 = QPushButton("ورقة إرسال حرة...")
        b2.clicked.connect(self.dialogue_bordereau)
        v.addWidget(b2, 0, Qt.AlignRight)
        self.table = tableau(["الرقم", "التاريخ", "الموضوع"], etirer=2)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setMinimumHeight(420)
        v.addWidget(self.table)
        racine.addWidget(c)
        racine.addStretch()
        self.rafraichir()

    def rafraichir(self) -> None:
        try:
            lignes = cg.sortants(self.f.conn)
            self.prochain.setText(f"الرقم الموالي: {cg.prochain_numero(self.f.conn)}")
        except cg.ErreurConge as e:
            message(self.message, str(e), True)
            return
        self.table.setRowCount(len(lignes))
        for i, r in enumerate(lignes):
            self.table.setItem(i, 0, cellule(f"\u2066{cg.numero_affiche(r['numero'], r['code_court'])}\u2069"))
            self.table.setItem(i, 1, cellule(tx.date_chiffres(r["date_courrier"])))
            self.table.setItem(i, 2, cellule(r["objet"]))

    def ajouter(self) -> str | None:
        try:
            _, num = cg.enregistrer_sortant(self.f.conn, self.objet.text(), self.le.iso())
        except (cg.ErreurConge, ValueError) as e:
            message(self.message, str(e) or "التاريخ غير صحيح.", True)
            return None
        self.objet.clear()
        self.rafraichir()
        message(self.message, f"سُجلت المراسلة تحت عدد ⁦{num}⁩.")
        return num

    def dialogue_bordereau(self) -> None:
        d = DialogueBordereau(self, [("", 1)], "", "bureau_etablissements")
        if d.exec() == QDialog.Accepted:
            try:
                doc = cg.generer_bordereau(self.f.conn, self.f.dossier, d.pieces(), d.objet.text(),
                                           d.le.iso() or None, bureau=d.bureau.currentData())
            except (cg.ErreurConge, dc.ErreurDocument, ValueError) as e:
                message(self.message, str(e), True)
                return
            self.rafraichir()
            _ouvrir(self.message, doc)
