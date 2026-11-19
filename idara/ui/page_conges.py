"""صفحتا الرخص وسجل الصادر: ملف رخصة واحد يولد سلسلة وثائقه."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDialog, QDialogButtonBox, QHeaderView,
                               QFormLayout, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from idara.services import bureautique
from idara.services import conges as cg
from idara.services import documents as dc
from idara.services import personnel as rh
from idara.services import textes as tx
from idara.ui.composants import bouton, carte, entete
from idara.ui.formulaires import champ, etiquette
from idara.ui import pictos
from idara.ui.graphiques import Anneau, BarresGroupees
from idara.ui.saisie import ChampDate, cellule, message, tableau
from idara.ui.vitrine import AlerteTriangle, CarteFiltre, FenetreFiche, bouton_couleur, grille_cartes

DOCS_COULEURS = {"demande": "#2E7D32", "recu": "#1565C0", "remp": "#6A1B9A", "bord": "#00838F",
                 "reprise": "#EF6C00"}

# بطاقات الأرقام (طلب المدير 2026-11-18): الحالة معيار للجدول عند الضغط
ETATS = [
    ("toutes", "كل الرخص", "#455A64", "document", "المسجلة في البرنامج"),
    ("en_cours", "رخص جارية", "#1565C0", "calendrier", "لم تنته مدتها بعد"),
    ("sans_reprise", "دون محضر استئناف", "#C62828", "rappel", "انتهت ولم يُحرر محضر الاستئناف"),
    ("reprise", "مستأنفة", "#2E7D32", "valider", "حُرر محضر استئنافها"),
    ("radaa", "رخص رضاعة جارية", "#AD1457", "personnes", "ساعة يومياً"),
    ("jours", "أيام الرخص", "#EF6C00", "statistiques", "مجموع المدد (دون الرضاعة)"),
]
LIB_ETAT = {"reprise": "مستأنفة", "en_cours": "جارية", "sans_reprise": "دون استئناف", "prolongee": "ممدَّدة"}
COUL_ETAT = {"reprise": "#2E7D32", "en_cours": "#1565C0", "sans_reprise": "#C62828", "prolongee": "#6A1B9A"}
PICTO_ETAT = {"reprise": "valider", "en_cours": "calendrier", "sans_reprise": "rappel", "prolongee": "actualiser"}


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
        # مكاتب هيكلة المديرية (طلب المدير 2026-11-19)؛ المكتبان المعيَّنان يحملان مفتاح إعدادهما
        conn = parent.f.conn
        par = cg.parametres(conn)
        cles = {par["bureau_conges"]: "bureau_conges", par["bureau_etablissements"]: "bureau_etablissements"}
        for sv, bu in cg.bureaux_direction(conn):
            self.bureau.addItem(f"{bu} ({sv})", cles.get(bu, bu))
        for k in ("bureau_conges", "bureau_etablissements"):
            if self.bureau.findData(k) < 0:
                self.bureau.addItem(par[k], k)
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
        racine.addWidget(entete("الرخص", "رخص الأطر وإحصائياتها. ملف الرخصة يُدخل مرة واحدة (في نافذة منبثقة)، ومنه "
                                         "يُولد الطلب وإيصال الشهادة الطبية وطلب التعويض وورقة الإرسال ومحضر الاستئناف."))
        # ---- بطاقات الأرقام (طلب المدير 2026-11-18) ----
        self.etat_filtre: str | None = None
        self.cartes: dict[str, CarteFiltre] = {}
        for k, lib, coul, picto, note in ETATS:
            c_ = CarteFiltre(k, lib, coul, picto, note)
            c_.clique.connect(self.filtrer)
            self.cartes[k] = c_
        racine.addLayout(grille_cartes(list(self.cartes.values()), 3))
        h = QHBoxLayout()
        b = QPushButton("إضافة رخصة جديدة")
        b.setObjectName("principal")
        b.clicked.connect(lambda: self.ouvrir_nouveau())
        h.addWidget(b)
        b2 = QPushButton("محضر استئناف بعد تغيب (دون رخصة)")
        b2.clicked.connect(lambda: self.dialogue_reprise(None))
        h.addWidget(b2)
        self.b_ouvrir = QPushButton("فتح ملف الرخصة المحددة")
        self.b_ouvrir.setEnabled(False)
        self.b_ouvrir.clicked.connect(lambda: self.ouvrir_fiche())
        h.addWidget(self.b_ouvrir)
        h.addStretch()
        b3 = QPushButton("تخصيص صيغ المراسلات")
        b3.clicked.connect(lambda: self.fiche_params.ouvrir())
        h.addWidget(b3)
        racine.addLayout(h)
        self.alertes = AlerteTriangle("رخص تحتاج إجراء")   # مثلث التنبيه (طلب المدير 2026-11-19)
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

        # ---- اللائحة ----
        c, cv = carte()
        self.titre_liste = QLabel()
        self.titre_liste.setObjectName("titreCarte")
        cv.addWidget(self.titre_liste)
        hf = QHBoxLayout()
        self.recherche = QLineEdit()
        self.recherche.setPlaceholderText("بحث: اسم الموظف أو نوع الرخصة")
        self.recherche.setClearButtonEnabled(True)
        self.recherche.textChanged.connect(lambda _: self.chercher())
        hf.addWidget(self.recherche, 2)
        self.f_type = QComboBox()
        self.f_type.addItem("كل الأنواع", None)
        self.f_type.currentIndexChanged.connect(lambda _: self.chercher())
        hf.addWidget(self.f_type, 1)
        cv.addLayout(hf)
        self.liste = tableau(["الموظف", "الحالة", "نوع الرخصة", "من", "إلى", "المدة", "رقم الطلب",
                              "الوثائق المولدة"], etirer=0)
        h = self.liste.horizontalHeader()
        h.setSectionResizeMode(h.ResizeMode.ResizeToContents)
        h.setStretchLastSection(True)
        self.liste.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.liste.setMinimumHeight(340)
        self.liste.itemSelectionChanged.connect(self._selection)
        self.liste.itemDoubleClicked.connect(lambda _: self.ouvrir_fiche())
        cv.addWidget(self.liste, 1)
        self.vide = QLabel("لا رخص مسجلة بعد. أضف رخصة جديدة من الزر أعلاه.")
        self.vide.setObjectName("etiquette")
        self.vide.setAlignment(Qt.AlignCenter)
        cv.addWidget(self.vide)
        # وثائق الرخصة المحددة مباشرة من الصفحة (طلب المدير 2026-11-18)
        self.barre_docs = QFrame()
        self.barre_docs.setObjectName("barreSelection")
        self.barre_docs.setStyleSheet("QFrame#barreSelection { background: #F3F7F6; border: 1px solid #CFE3DE; "
                                      "border-radius: 12px; }")
        bd = QGridLayout(self.barre_docs)
        bd.setContentsMargins(12, 10, 12, 10)
        bd.setSpacing(8)
        self.l_doc_sel = QLabel()
        self.l_doc_sel.setStyleSheet("font-weight: 700; background: transparent;")
        bd.addWidget(self.l_doc_sel, 0, 0, 1, 3)
        self.p_demande = bouton_couleur("طلب الرخصة", DOCS_COULEURS["demande"], "document")
        self.p_demande.clicked.connect(lambda: self._generer(cg.generer_demande))
        self.p_recu = bouton_couleur("إيصال الشهادة الطبية", DOCS_COULEURS["recu"], "valider")
        self.p_recu.clicked.connect(lambda: self._generer(cg.generer_recu))
        self.p_remp = bouton_couleur("طلب تعويض", DOCS_COULEURS["remp"], "personnes")
        self.p_remp.clicked.connect(lambda: self._generer(cg.generer_remplacement))
        self.p_bord = bouton_couleur("ورقة الإرسال", DOCS_COULEURS["bord"], "envoyer")
        self.p_bord.clicked.connect(self.dialogue_bordereau)
        self.p_reprise = bouton_couleur("محضر الاستئناف", DOCS_COULEURS["reprise"], "retour")
        self.p_reprise.clicked.connect(lambda: self.dialogue_reprise(self.cid))
        self.p_ouvrir = QPushButton("فتح الملف")
        self.p_ouvrir.clicked.connect(lambda: self.ouvrir_fiche())
        for i, b in enumerate((self.p_demande, self.p_recu, self.p_remp, self.p_bord, self.p_reprise,
                               self.p_ouvrir)):
            bd.addWidget(b, 1 + i // 3, i % 3)
        cv.addWidget(self.barre_docs)
        self.barre_docs.hide()
        racine.addWidget(c)
        self.c_graph, self.v_graph = carte("المبيانات")
        self._graphes: list[QWidget] = []
        racine.addWidget(self.c_graph)
        racine.addStretch()

        # ---- الملف ----
        c2, fv = carte()
        self.titre = QLabel("رخصة جديدة")
        self.titre.setObjectName("titreCarte")
        fv.addWidget(self.titre)
        self.personnel = QComboBox()
        self.personnel.currentIndexChanged.connect(lambda _: self._maj_prolongations())
        self.personnel.currentIndexChanged.connect(lambda _: self._maj_adresse())
        self.personnel.currentIndexChanged.connect(lambda _: self._maj_deposant() if hasattr(self, "qui_depose") else None)
        self._adresse_auto = ""
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
        # من أدلى بالشهادة (طلب المدير 2026-11-13): «الموظف نفسه» يملأ اسمه ورقم بطاقته ويُكتب اسمه أسفل الوصل
        self.qui_depose = QComboBox()
        self.qui_depose.addItem("شخص آخر", "autre")
        self.qui_depose.addItem("الموظف نفسه", "lui")
        self.qui_depose.currentIndexChanged.connect(lambda _: self._maj_deposant())
        self.recu_le = ChampDate()
        self.duree_cert = QSpinBox()
        self.duree_cert.setRange(0, 1100)
        self.duree_cert.setSpecialValueText("نفس مدة الرخصة")
        self.rem_cert = champ("اختياري")
        fv.addLayout(_grille([("الطبيب", self.medecin), ("التخصص", self.specialite),
                              ("تاريخ تسلم الشهادة", self.recu_le), ("مدة الشهادة", self.duree_cert),
                              ("من أدلى بالشهادة", self.qui_depose),
                              ("المدلي بالشهادة", self.deposant), ("رقم بطاقته الوطنية", self.deposant_cin),
                              ("ملاحظات الإيصال", self.rem_cert)]))
        hs = QHBoxLayout()
        b_save = QPushButton("حفظ ملف الرخصة")
        b_save.setObjectName("principal")
        b_save.clicked.connect(self.enregistrer)
        hs.addWidget(b_save)
        # طلب المدير 2026-11-18: طلب الرخصة يُولد مباشرة من ملفها
        self.b_save_demande = bouton_couleur("حفظ وتوليد طلب الرخصة", "#2E7D32", "document",
                                             "يحفظ الملف ثم يولد طلب الرخصة ويسجله في الصادر")
        self.b_save_demande.clicked.connect(lambda: self.enregistrer_et_demande())
        hs.addWidget(self.b_save_demande)
        hs.addStretch()
        fv.addLayout(hs)
        self.message_fiche = QLabel()   # نتيجة الحفظ والتوليد داخل النافذة المنبثقة
        self.message_fiche.setWordWrap(True)
        self.message_fiche.hide()
        fv.addWidget(self.message_fiche)

        t = QLabel("وثائق الرخصة")
        t.setObjectName("titreCarte")
        fv.addWidget(t)
        self.aide_docs = QLabel("احفظ ملف الرخصة أولاً، ثم ولّد وثائقه من هنا أو من الصفحة الرئيسية للرخص.")
        self.aide_docs.setObjectName("etiquette")
        self.aide_docs.setWordWrap(True)
        fv.addWidget(self.aide_docs)
        self.zone_docs = QWidget()
        g = QGridLayout(self.zone_docs)
        g.setContentsMargins(0, 0, 0, 0)
        g.setSpacing(10)
        self.b_demande = bouton_couleur("طلب الرخصة (يُسجل في الصادر)", DOCS_COULEURS["demande"], "document")
        self.b_demande.clicked.connect(lambda: self._generer(cg.generer_demande))
        self.b_recu = bouton_couleur("إيصال الشهادة الطبية", DOCS_COULEURS["recu"], "valider")
        self.b_recu.clicked.connect(lambda: self._generer(cg.generer_recu))
        self.b_remp = bouton_couleur("طلب تعويض", DOCS_COULEURS["remp"], "personnes")
        self.b_remp.clicked.connect(lambda: self._generer(cg.generer_remplacement))
        self.b_bord = bouton_couleur("ورقة الإرسال", DOCS_COULEURS["bord"], "envoyer")
        self.b_bord.clicked.connect(self.dialogue_bordereau)
        self.b_reprise = bouton_couleur("محضر استئناف العمل", DOCS_COULEURS["reprise"], "retour")
        self.b_reprise.clicked.connect(lambda: self.dialogue_reprise(self.cid))
        for i, b in enumerate((self.b_demande, self.b_recu, self.b_remp, self.b_bord, self.b_reprise)):
            g.addWidget(b, i // 2, i % 2)
        fv.addWidget(self.zone_docs)
        self.docs = tableau(["الوثيقة", "التاريخ"], etirer=0)
        self.docs.setMinimumHeight(120)
        self.docs.cellDoubleClicked.connect(self._ouvrir_doc)
        fv.addWidget(self.docs)

        self.fiche = FenetreFiche(self, "ملف الرخصة", "يُدخل مرة واحدة، ومنه تُولد كل وثائق الرخصة.", c2)

        # ---- صيغ المراسلات (نافذة مستقلة) ----
        cp, pv = carte("صيغ المراسلات (تُكتب في كل الوثائق)")
        self.params = {k: champ() for k in cg.PARAMETRES}
        pv.addLayout(_grille([(lib, self.params[k]) for k, (lib, _) in cg.PARAMETRES.items()], 1))
        b_p = QPushButton("حفظ الصيغ")
        b_p.setObjectName("principal")
        b_p.clicked.connect(self.enregistrer_parametres)
        pv.addWidget(b_p, 0, Qt.AlignRight)
        self.message_params = QLabel()
        self.message_params.setWordWrap(True)
        self.message_params.hide()
        pv.addWidget(self.message_params)
        pv.addStretch()
        self.fiche_params = FenetreFiche(self, "صيغ المراسلات", "الجهات والصيغ التي تُكتب في وثائق الرخص.", cp, 760)
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
        types = [self.f_type.itemText(i) for i in range(1, self.f_type.count())]
        for t in cg.types_conge(conn):
            if t["libelle_ar"] not in types:
                self.f_type.addItem(t["libelle_ar"], t["libelle_ar"])
        aujourdhui = date.today().isoformat()
        ids_attendus = {a["id"] for a in attendues}
        self.toutes = []
        for r in cg.lister(conn):
            etat = ("reprise" if r["reprise_id"] else "en_cours" if r["date_fin"] >= aujourdhui
                    else "sans_reprise" if r["id"] in ids_attendus else "prolongee")
            self.toutes.append({"r": r, "etat": etat, "docs": len(cg.documents(conn, r["id"])),
                                "radaa": cg.est_allaitement(conn, r["type_conge_id"])})
        n = {"toutes": len(self.toutes), "en_cours": sum(1 for x in self.toutes if x["etat"] == "en_cours"),
             "sans_reprise": len(attendues), "reprise": sum(1 for x in self.toutes if x["etat"] == "reprise"),
             "radaa": len(radaa),
             "jours": sum(int(x["r"]["duree_jours"] or 0) for x in self.toutes if not x["radaa"])}
        for k, c_ in self.cartes.items():
            c_.definir(n[k])
        self._graphiques()
        self.chercher()

    def filtrer(self, etat: str | None) -> None:
        self.etat_filtre = None if etat in (self.etat_filtre, "toutes", "jours") else etat
        self.chercher()

    def chercher(self) -> None:
        from idara.services.massar import normaliser
        for k, c_ in self.cartes.items():
            c_.definir_actif(k == (self.etat_filtre or "toutes"))
        t = normaliser(self.recherche.text())
        typ = self.f_type.currentData()
        self.lignes = [x for x in getattr(self, "toutes", [])
                       if (self.etat_filtre is None or (x["radaa"] and x["etat"] == "en_cours"
                                                        if self.etat_filtre == "radaa" else
                                                        x["etat"] == self.etat_filtre))
                       and (not typ or x["r"]["type"] == typ)
                       and (not t or any(t in normaliser(v) for v in (
                           f"{x['r']['prenom_ar']}{x['r']['nom_ar']}", f"{x['r']['nom_ar']}{x['r']['prenom_ar']}",
                           x["r"]["type"])))]
        titre = next((lib for k, lib, *_ in ETATS if k == (self.etat_filtre or "toutes")), "")
        self.titre_liste.setText(f"{titre} ({len(self.lignes)})")
        self.liste.blockSignals(True)
        self.liste.clearSelection()
        self.liste.setRowCount(len(self.lignes))
        for i, x in enumerate(self.lignes):
            r = x["r"]
            it = cellule(f"{r['prenom_ar']} {r['nom_ar']}", r["id"])
            f_ = it.font()
            f_.setBold(True)
            it.setFont(f_)
            it.setToolTip(f"{r['type']}: من {tx.date_chiffres(r['date_debut'])} إلى {tx.date_chiffres(r['date_fin'])}")
            self.liste.setItem(i, 0, it)
            e = cellule(LIB_ETAT[x["etat"]])
            e.setForeground(QColor(COUL_ETAT[x["etat"]]))
            e.setIcon(pictos.icone(PICTO_ETAT[x["etat"]], COUL_ETAT[x["etat"]], 16))
            self.liste.setItem(i, 1, e)
            for j, v in enumerate((r["type"], tx.date_chiffres(r["date_debut"]), tx.date_chiffres(r["date_fin"]),
                                   f"{int(r['duree_jours'])} يوماً",
                                   f"\u2066{cg.numero_affiche(r['numero'], r['code_court'])}\u2069" if r["numero"]
                                   else "—", str(x["docs"]) if x["docs"] else "—"), start=2):
                self.liste.setItem(i, j, cellule(v))
        self.liste.blockSignals(False)
        self.liste.setVisible(bool(self.toutes))
        self.vide.setVisible(not self.toutes)
        self._selection()

    def _graphiques(self) -> None:
        for w in self._graphes:
            w.hide()
            w.setParent(None)
            w.deleteLater()
        self._graphes = []
        self.c_graph.setVisible(bool(self.toutes))
        if not self.toutes:
            return
        par_type: dict[str, int] = {}
        for x in self.toutes:
            par_type[x["r"]["type"]] = par_type.get(x["r"]["type"], 0) + 1
        total = len(self.toutes)
        palette = ["#1565C0", "#AD1457", "#2E7D32", "#EF6C00", "#6A1B9A", "#00838F", "#C62828", "#5D4037"]
        cont = QWidget()
        ligne = QHBoxLayout(cont)
        ligne.setContentsMargins(0, 0, 0, 0)
        an = Anneau([(k, v, round(100 * v / total, 1)) for k, v in par_type.items()],
                    palette[:len(par_type)] + ["#757575"] * max(0, len(par_type) - len(palette)), str(total), "رخصة")
        an.setMinimumHeight(230)
        ligne.addWidget(an, 2)
        mois: dict[str, list[int]] = {}
        for x in self.toutes:
            if x["radaa"]:
                continue
            m = x["r"]["date_debut"][:7]
            mois.setdefault(m, [0, 0])
            mois[m][0] += 1
            mois[m][1] += int(x["r"]["duree_jours"] or 0)
        if mois:
            from idara.services.mouvements import libelle_mois
            cles = sorted(mois)[-10:]
            self.g_mois = BarresGroupees([libelle_mois(m) for m in cles],
                                         [("عدد الرخص", [float(mois[m][0]) for m in cles], "#1565C0"),
                                          ("أيام الرخص", [float(mois[m][1]) for m in cles], "#EF6C00")],
                                         maximum=None, suffixe="")
            ligne.addWidget(self.g_mois, 3)
        self.v_graph.addWidget(cont)
        self._graphes.append(cont)

    def _selection(self) -> None:
        lignes = {i.row() for i in self.liste.selectedIndexes()}
        self.b_ouvrir.setEnabled(len(lignes) == 1)
        self.barre_docs.setVisible(len(lignes) == 1)
        if len(lignes) == 1:
            self.afficher(self.liste.item(lignes.pop(), 0).data(Qt.UserRole))
            self.l_doc_sel.setText("وثائق الرخصة المحددة: " + self.titre.text())

    def enregistrer_et_demande(self):
        """يحفظ ملف الرخصة ثم يولد طلبها مباشرة (طلب المدير 2026-11-18)."""
        if self.enregistrer() is None:
            return None
        return self._generer(cg.generer_demande)

    def _msg(self, texte: str, erreur: bool = False) -> None:
        message(self.message, texte, erreur)
        message(self.message_fiche, texte, erreur)

    def _ouvrir(self, doc) -> None:
        _ouvrir(self.message, doc)
        message(self.message_fiche, self.message.text(), self.message.objectName() == "erreur")

    def ouvrir_nouveau(self) -> FenetreFiche:
        self.nouveau()
        self.fiche.definir_titre("إضافة رخصة جديدة")
        self.fiche.ouvrir()
        return self.fiche

    def ouvrir_fiche(self, cid: int | None = None) -> FenetreFiche | None:
        if cid is not None:
            self.afficher(cid)
        if self.cid is None:
            return None
        self.fiche.definir_titre("ملف الرخصة: " + self.titre.text())
        self.fiche.ouvrir()
        return self.fiche

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

    def _maj_adresse(self) -> None:
        """عنوان الإقامة خلال الرخصة: عنوان الموظف في ملفه افتراضياً، ويُعدَّل يدوياً عند الاقتضاء."""
        if self.cid is not None or not hasattr(self, "adresse"):
            return
        pid = self.personnel.currentData()
        r = self.f.conn.execute("SELECT adresse FROM personnel WHERE id=?", (pid,)).fetchone() if pid else None
        if self.adresse.text().strip() in ("", self._adresse_auto):
            self._adresse_auto = (r["adresse"] if r else "") or ""
            self.adresse.setText(self._adresse_auto)

    def _maj_deposant(self) -> None:
        lui = self.qui_depose.currentData() == "lui"
        for w in (self.deposant, self.deposant_cin):
            w.setReadOnly(lui)
        pid = self.personnel.currentData()
        r = self.f.conn.execute("SELECT prenom_ar, nom_ar, cin FROM personnel WHERE id=?", (pid,)).fetchone() \
            if pid else None
        if lui and r:
            self.deposant.setText(f"{r['prenom_ar']} {r['nom_ar']}")
            self.deposant_cin.setText(r["cin"] or "")
        elif not lui and r and self.deposant.text() == f"{r['prenom_ar']} {r['nom_ar']}":
            self.deposant.clear()
            self.deposant_cin.clear()

    def nouveau(self) -> None:
        self.cid = None
        self.liste.clearSelection()
        self.titre.setText("رخصة جديدة")
        self.personnel.setEnabled(True)
        for w in (self.motif, self.adresse, self.avis, self.mesures, self.pieces, self.medecin, self.specialite,
                  self.deposant, self.deposant_cin, self.rem_cert, self.debut, self.recu_le, self.naissance,
                  self.horaire):
            w.clear()
        self._adresse_auto = ""
        self._maj_adresse()
        self.qui_depose.setCurrentIndex(0)
        self.date_demande.definir(date.today().isoformat())
        self.duree.setValue(1)
        self.duree_cert.setValue(0)
        self._maj_prolongations()
        self._maj_type()
        self.zone_docs.setEnabled(False)
        self.aide_docs.show()
        self.docs.setRowCount(0)
        self.message.hide()
        self.message_fiche.hide()

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
        p = rh.lire(self.f.conn, c.personnel_id)
        self.qui_depose.blockSignals(True)
        self.qui_depose.setCurrentIndex(1 if cg.depose_par_lui_meme(c, p) else 0)
        self.qui_depose.blockSignals(False)
        for w in (self.deposant, self.deposant_cin):
            w.setReadOnly(self.qui_depose.currentData() == "lui")
        self.recu_le.definir(c.certificat_recu_le or None)
        self.naissance.definir(c.date_naissance_enfant or None)
        self.horaire.setText(c.horaire_allaitement or "")
        self.duree_cert.setValue(int(c.certificat_duree_jours or 0))
        p = rh.lire(self.f.conn, c.personnel_id)
        self.titre.setText(f"{p.prenom_ar} {p.nom_ar} · {self.type.currentText()}")
        self.zone_docs.setEnabled(True)
        self.aide_docs.hide()
        radaa = cg.est_allaitement(self.f.conn, c.type_conge_id)   # ساعة يومية: لا تعويض ولا استئناف
        self.b_remp.setEnabled(p.categorie in ("enseignant", "educatrice") and not radaa)
        self.b_recu.setEnabled(bool(c.medecin))
        deja = self.f.conn.execute("SELECT 1 FROM reprise_travail WHERE conge_id=?", (cid,)).fetchone()
        self.b_reprise.setEnabled(not deja and not c.prolongation_de and not radaa)
        for pb, b in ((self.p_remp, self.b_remp), (self.p_recu, self.b_recu), (self.p_reprise, self.b_reprise)):
            pb.setEnabled(b.isEnabled())
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
            self._msg(str(e), True)
            return None
        self.rafraichir()
        self.afficher(cid)
        self._msg("حُفظ ملف الرخصة. يمكنك الآن توليد وثائقه.")
        self.fiche.definir_titre("ملف الرخصة: " + self.titre.text())
        return cid

    def _generer(self, fonction):
        try:
            doc = fonction(self.f.conn, self.f.dossier, self.cid)
        except (cg.ErreurConge, dc.ErreurDocument) as e:
            self._msg(str(e), True)
            return None
        self.rafraichir()
        self.afficher(self.cid)
        self._ouvrir(doc)
        return doc

    def dialogue_bordereau(self) -> None:
        c = cg.lire(self.f.conn, self.cid)
        p = rh.lire(self.f.conn, c.personnel_id)
        d = DialogueBordereau(self, cg.pieces_proposees(self.f.conn, c), f"ملف رخصة {p.prenom_ar} {p.nom_ar}")
        if d.exec() == QDialog.Accepted:
            try:
                le = d.le.iso() or None
            except ValueError:
                self._msg("التاريخ غير صحيح.", True)
                return
            self.bordereau(d.pieces(), d.objet.text(), le, d.bureau.currentData())

    def bordereau(self, pieces, objet: str, le: str | None = None, bureau: str = "bureau_conges"):
        try:
            doc = cg.generer_bordereau(self.f.conn, self.f.dossier, pieces, objet, le, self.cid, bureau)
        except (cg.ErreurConge, dc.ErreurDocument) as e:
            self._msg(str(e), True)
            return None
        self.afficher(self.cid)
        self._ouvrir(doc)
        return doc

    def dialogue_reprise(self, cid: int | None) -> None:
        r = cg.proposition_reprise(self.f.conn, cid) if cid else None
        d = DialogueReprise(self, self.f.conn, r, self.personnels)
        if d.exec() == QDialog.Accepted:
            try:
                self.reprise(d.lire())
            except cg.ErreurConge as e:
                self._msg(str(e), True)

    def reprise(self, r: cg.Reprise):
        try:
            rid = cg.enregistrer_reprise(self.f.conn, r)
            doc = cg.generer_reprise(self.f.conn, self.f.dossier, rid)
        except (cg.ErreurConge, dc.ErreurDocument) as e:
            self._msg(str(e), True)
            return None
        self.rafraichir()
        if self.cid:
            self.afficher(self.cid)
        self._ouvrir(doc)
        return doc

    def enregistrer_parametres(self) -> None:
        try:
            cg.definir_parametres(self.f.conn, {k: w.text() for k, w in self.params.items()})
        except cg.ErreurConge as e:
            message(self.message_params, str(e), True)
            return
        message(self.message_params, "حُفظت صيغ المراسلات.")

    def _ouvrir_doc(self, ligne: int, _col: int) -> None:
        try:
            bureautique.ouvrir(self.f.dossier.racine / self.docs.item(ligne, 0).data(Qt.UserRole))
        except OSError as e:
            self._msg(f"تعذر فتح الملف: {e}", True)


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
        h2 = QHBoxLayout()
        b2 = QPushButton("ورقة إرسال حرة...")
        b2.clicked.connect(self.dialogue_bordereau)
        h2.addWidget(b2)
        h2.addStretch()
        from idara.ui.vitrine import bouton_couleur
        self.b_structure = bouton_couleur("هيكلة المديرية: المصالح والمكاتب", "#1565C0", "personnes",
                                          "تختلف من مديرية إلى أخرى: أضف مصالح مديريتك ومكاتبها")
        self.b_structure.clicked.connect(lambda: self.ouvrir_structure())
        h2.addWidget(self.b_structure)
        v.addLayout(h2)
        self.l_structure = QLabel()
        self.l_structure.setWordWrap(True)
        self.l_structure.setTextFormat(Qt.RichText)
        self.l_structure.setStyleSheet("background: #F3F7FC; border: 1px solid #D5E3F3; border-radius: 12px; "
                                       "padding: 10px 14px;")
        v.addWidget(self.l_structure)
        self.table = tableau(["الرقم", "التاريخ", "الموضوع"], etirer=2)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setMinimumHeight(420)
        v.addWidget(self.table)
        racine.addWidget(c)
        racine.addStretch()
        self._construire_structure()
        self.rafraichir()

    # ---- هيكلة المديرية في نافذة منبثقة (طلب المدير 2026-11-19) ----
    def _construire_structure(self) -> None:
        from idara.ui.vitrine import FenetreFiche, bouton_couleur
        w = QWidget()
        v = QVBoxLayout(w)
        aide = QLabel("سطر لكل مكتب: المصلحة ثم المكتب التابع لها. مصلحة دون مكاتب: اترك خانة المكتب فارغة. "
                      "ثم حدد المصلحة والمكتبين اللذين تُوجَّه إليهما الرخص وأوراق الإرسال.")
        aide.setObjectName("etiquette")
        aide.setWordWrap(True)
        v.addWidget(aide)
        self.t_structure = QTableWidget(0, 2)
        self.t_structure.setHorizontalHeaderLabels(["المصلحة", "المكتب"])
        self.t_structure.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.t_structure.verticalHeader().setVisible(False)
        self.t_structure.setMinimumHeight(280)
        v.addWidget(self.t_structure)
        h = QHBoxLayout()
        b = QPushButton("+ مكتب أو مصلحة")
        b.clicked.connect(lambda: self._ligne_structure("", ""))
        h.addWidget(b)
        b = bouton("حذف السطر المحدد")
        b.clicked.connect(lambda: self.t_structure.removeRow(self.t_structure.currentRow()))
        h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        f = QFormLayout()
        self.aff = {k: QComboBox() for k in ("service_rh", "bureau_conges", "bureau_etablissements")}
        for k, cb in self.aff.items():
            cb.setEditable(True)
            f.addRow({"service_rh": "المصلحة المختصة بالرخص", "bureau_conges": "مكتب الرخص (طلبات الرخص)",
                      "bureau_etablissements": "مكتب تسيير المؤسسات (أوراق الإرسال)"}[k], cb)
        v.addLayout(f)
        h = QHBoxLayout()
        b = bouton_couleur("حفظ الهيكلة", "#1565C0", "enregistrer")
        b.clicked.connect(lambda: self.enregistrer_structure())
        h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        self.message_structure = QLabel()
        self.message_structure.setWordWrap(True)
        self.message_structure.hide()
        v.addWidget(self.message_structure)
        self.fiche_structure = FenetreFiche(self, "هيكلة المديرية الإقليمية", "", w, largeur=760)

    def _ligne_structure(self, sv: str, bu: str) -> None:
        i = self.t_structure.rowCount()
        self.t_structure.insertRow(i)
        self.t_structure.setItem(i, 0, QTableWidgetItem(sv))
        self.t_structure.setItem(i, 1, QTableWidgetItem(bu))

    def ouvrir_structure(self):
        st = cg.structure_direction(self.f.conn)
        self.t_structure.setRowCount(0)
        for x in st:
            for b in x["bureaux"] or [""]:
                self._ligne_structure(x["service"], b)
        par = cg.parametres(self.f.conn)
        for k, cb in self.aff.items():
            cb.clear()
            cb.addItems([x["service"] for x in st] if k == "service_rh" else [b for x in st for b in x["bureaux"]])
            cb.setCurrentText(par[k])
        self.message_structure.hide()
        self.fiche_structure.ouvrir()
        return self.fiche_structure

    def enregistrer_structure(self) -> bool:
        self.t_structure.setCurrentItem(None)
        lignes = [tuple((self.t_structure.item(i, j).text() if self.t_structure.item(i, j) else "") for j in range(2))
                  for i in range(self.t_structure.rowCount())]
        try:
            cg.enregistrer_structure_direction(self.f.conn, lignes, {k: cb.currentText() for k, cb in self.aff.items()})
        except cg.ErreurConge as e:
            message(self.message_structure, str(e), True)
            return False
        message(self.message_structure, "حُفظت هيكلة المديرية.")
        self._afficher_structure()
        # إعادة ملء قوائم الاختيار بالمصالح والمكاتب الجديدة
        self.ouvrir_structure()
        message(self.message_structure, "حُفظت هيكلة المديرية.")
        return True

    def _afficher_structure(self) -> None:
        st = cg.structure_direction(self.f.conn)
        par = cg.parametres(self.f.conn)
        puce = ("<span style='background:{c};color:white;border-radius:8px;padding:2px 8px;'>&nbsp;{t}&nbsp;</span>")
        lignes = []
        for x in st:
            bs = " ".join(puce.format(c="#2E7D32" if b in (par["bureau_conges"], par["bureau_etablissements"])
                                      else "#78909C", t=b) for b in x["bureaux"]) or "—"
            lignes.append(f"<b style='color:#1565C0'>{x['service']}</b>: {bs}")
        self.l_structure.setText("<div dir='rtl'><b>هيكلة المديرية</b><br>" + "<br>".join(lignes) + "</div>")

    def rafraichir(self) -> None:
        self._afficher_structure()
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
