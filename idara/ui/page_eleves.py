"""صفحة التلاميذ: البحث بالرمز أو الاسم، البطاقة، ثم توليد الوثيقة المطلوبة."""

from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QDateEdit, QDialog, QDialogButtonBox,
                               QFormLayout, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QRadioButton, QVBoxLayout, QWidget)

from idara.services import bureautique
from idara.services import calendrier as cal
from idara.services import documents as dc
from idara.services import eleves as el
from idara.services import textes as tx
from idara.ui.composants import carte, entete
from idara.ui.formulaires import champ, etiquette
from idara.ui.saisie import ChampDate, cellule, message, tableau
from idara.ui.vitrine import CarteDocument, FenetreFiche, bouton_couleur

# معرض الوثائق (طلب المدير 2026-11-18): (المفتاح، العنوان، الوصف، اللون، الأيقونة)
DOCUMENTS = [
    ("vacances", "شهادة العطلة", "للسفر خلال العطل، بالفرنسية، والعطل تُقترح من المقرر الوزاري.", "#1565C0",
     "calendrier"),
    ("visite", "ورقة الزيارة الطبية", "لتوجيه التلميذ إلى الطبيب أو المركز الصحي.", "#00838F", "valider"),
    ("convocation", "استدعاء ولي الأمر", "استدعاء فردي، أو لعدة تلاميذ في ملف واحد.", "#6A1B9A", "rappel"),
    ("portes", "استدعاءات الأبواب المفتوحة", "الأبواب المفتوحة رقم 1 إلى 4، بعدد يختاره المدير في الصفحة.",
     "#2E7D32", "ouvrir"),
    ("rencontre", "استدعاءات اللقاء التواصلي", "اللقاء التواصلي رقم 01 إلى 05 مع أولياء الأمور.", "#EF6C00",
     "personnes"),
    ("ag_parents", "استدعاءات الجمع العام", "الجمع العام لجمعية أمهات وآباء وأولياء التلاميذ.", "#AD1457",
     "personnes"),
    ("fiche", "بطاقة التلميذ: تتبع المسار", "الرائزان والمراحل بمبيانات، لتلميذ أو لقسم كامل.", "#3949AB",
     "statistiques"),
    ("ancien", "الشهادة المدرسية (ما قبل مسار)", "للتلاميذ القدامى غير المسجلين في منظومة مسار.", "#5D4037",
     "document"),
    ("dossier", "طلب ملف التلميذ أو إرساله", "مراسلات الوافدين والمغادرين وتتبع ملفاتهم.", "#455A64",
     "envoyer"),
]
PAGES_DOCS = {"fiche": "بطاقة التلميذ", "ancien": "التلاميذ القدامى", "dossier": "حركية التلاميذ"}


def _qdate(d: date) -> QDate:
    return QDate(d.year, d.month, d.day)


def _pydate(q: QDate) -> date:
    return date(q.year(), q.month(), q.day())


class DialogueVacances(QDialog):
    """فترة العطلة التي تشملها الشهادة، وتاريخ التحرير."""

    def __init__(self, nom: str, parent=None, vacances: list | None = None):
        super().__init__(parent)
        self.setWindowTitle("شهادة العطلة")
        self.setLayoutDirection(Qt.RightToLeft)
        v = QVBoxLayout(self)
        v.addWidget(QLabel(f"شهادة العطلة لـ: {nom}"))
        f = QFormLayout()
        aujourdhui = date.today()
        self.du, self.au, self.le = QDateEdit(), QDateEdit(), QDateEdit()
        for w, d in ((self.du, aujourdhui), (self.au, aujourdhui + timedelta(days=14)), (self.le, aujourdhui)):
            w.setCalendarPopup(True)
            w.setLayoutDirection(Qt.LeftToRight)
            w.setDisplayFormat("dd/MM/yyyy")
            w.setDate(_qdate(d))
        # اقتراح العطل من المقرر الوزاري المرفق بالبرنامج (قرار مؤجل منذ 2026-11-01، أُنجز 2026-11-03)
        self.choix = QComboBox()
        self.choix.addItem("— إدخال يدوي —", None)
        for s in vacances or []:
            self.choix.addItem(f"{s.titre} ({s.periode})", (s.debut, s.fin))
        self.choix.currentIndexChanged.connect(self._choisir)
        if vacances:
            f.addRow("عطلة من المقرر", self.choix)
            prochaine = next((i for i, s in enumerate(vacances, start=1) if s.fin >= aujourdhui), None)
            if prochaine:
                self.choix.setCurrentIndex(prochaine)
        f.addRow("بداية العطلة *", self.du)
        f.addRow("نهاية العطلة *", self.au)
        f.addRow("تاريخ التحرير", self.le)
        v.addLayout(f)
        self.erreur = QLabel()
        self.erreur.setObjectName("erreur")
        self.erreur.hide()
        v.addWidget(self.erreur)
        b = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        b.button(QDialogButtonBox.Ok).setText("توليد الشهادة")
        b.button(QDialogButtonBox.Cancel).setText("إلغاء")
        b.accepted.connect(self._ok)
        b.rejected.connect(self.reject)
        v.addWidget(b)

    def _choisir(self, _=None) -> None:
        d = self.choix.currentData()
        if d:
            self.du.setDate(_qdate(d[0]))
            self.au.setDate(_qdate(d[1]))

    def valeurs(self) -> tuple[date, date, date]:
        return _pydate(self.du.date()), _pydate(self.au.date()), _pydate(self.le.date())

    def _ok(self) -> None:
        du, au, _ = self.valeurs()
        if au < du:
            message(self.erreur, "نهاية العطلة قبل بدايتها.", True)
            return
        self.accept()


class DialogueStatut(QDialog):
    def __init__(self, nom: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("وضعية التلميذ")
        self.setLayoutDirection(Qt.RightToLeft)
        v = QVBoxLayout(self)
        v.addWidget(QLabel(nom))
        f = QFormLayout()
        self.statut = QComboBox()
        for code in ("parti", "interrompu", "exclu", "non_rejoint", "arrive", "inscrit"):
            self.statut.addItem({"parti": "مغادر (انتقال إلى مؤسسة أخرى)", "interrompu": "منقطع",
                                 "non_rejoint": "غير ملتحق (مسجل في مسار ولم يلتحق)",
                                 "exclu": "مفصول (السبب ومرجع القرار في خانة السبب)",
                                 "arrive": "وافد من مؤسسة أخرى", "inscrit": "يتابع دراسته (إلغاء مغادرة أو انقطاع)"}[code], code)
        self.le = ChampDate()
        self.le.definir(date.today().isoformat())
        self.etab = champ("اسم المؤسسة")
        self.motif = champ()
        f.addRow("الوضعية", self.statut)
        f.addRow("التاريخ", self.le)
        f.addRow("المؤسسة المستقبلة أو الأصلية", self.etab)
        f.addRow("السبب (اختياري)", self.motif)
        v.addLayout(f)
        b = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        b.button(QDialogButtonBox.Ok).setText("تسجيل")
        b.button(QDialogButtonBox.Cancel).setText("إلغاء")
        b.accepted.connect(self.accept)
        b.rejected.connect(self.reject)
        v.addWidget(b)


class DialogueDocEleve(QDialog):
    """نافذة توليد وثيقة تلميذ (طلب المدير 2026-11-18): اختيار التلميذ أو التلاميذ، ثم معطيات الوثيقة، ثم التوليد."""

    def __init__(self, page, cle: str):
        super().__init__(page)
        self.page, self.f, self.cle = page, page.f, cle
        _, titre, desc, coul, picto = next(d for d in DOCUMENTS if d[0] == cle)
        self.setWindowTitle(titre)
        self.setLayoutDirection(Qt.RightToLeft)
        self.setModal(True)
        v = QVBoxLayout(self)
        v.setContentsMargins(18, 16, 18, 16)
        v.setSpacing(10)
        e = entete(titre, desc)
        v.addWidget(e)
        self.multiple = cle == "convocation"
        c, cv = carte("التلاميذ المعنيون" if self.multiple else "التلميذ(ة)")
        self.recherche = QLineEdit()
        self.recherche.setPlaceholderText("بحث: الاسم أو رمز مسار")
        self.recherche.setClearButtonEnabled(True)
        self.recherche.textChanged.connect(lambda _: self.chercher())
        cv.addWidget(self.recherche)
        self.table = tableau(["الرمز", "الاسم", "القسم"])
        self.table.setSelectionMode(self.table.SelectionMode.ExtendedSelection if self.multiple
                                    else self.table.SelectionMode.SingleSelection)
        self.table.setMinimumHeight(240)
        self.table.itemSelectionChanged.connect(self._compte)
        cv.addWidget(self.table)
        self.l_choix = QLabel()
        self.l_choix.setObjectName("etiquette")
        cv.addWidget(self.l_choix)
        v.addWidget(c)
        self.zone_vac = None
        if cle == "vacances":
            c2, v2 = carte("فترة العطلة")
            try:
                vac = cal.vacances(self.f.conn)
            except cal.ErreurCalendrier:
                vac = []
            self.choix = QComboBox()
            self.choix.addItem("— إدخال يدوي —", None)
            for st in vac:
                self.choix.addItem(f"{st.titre} ({st.periode})", (st.debut.isoformat(), st.fin.isoformat()))
            self.du, self.au, self.le = ChampDate(), ChampDate(), ChampDate()
            self.le.definir(date.today().isoformat())
            self.choix.currentIndexChanged.connect(lambda _: self._choisir())
            g = QGridLayout()
            g.setHorizontalSpacing(14)
            for k, (lib, w) in enumerate((("عطلة من المقرر", self.choix), ("تاريخ التحرير", self.le),
                                          ("بداية العطلة *", self.du), ("نهاية العطلة *", self.au))):
                g.addWidget(etiquette(lib, w), (k // 2) * 2, k % 2)
                g.addWidget(w, (k // 2) * 2 + 1, k % 2)
            v2.addLayout(g)
            prochaine = next((i for i, st in enumerate(vac, start=1) if st.fin >= date.today()), None)
            if prochaine:
                self.choix.setCurrentIndex(prochaine)
            v.addWidget(c2)
            self.zone_vac = c2
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.hide()
        v.addWidget(self.message)
        h = QHBoxLayout()
        h.addStretch()
        b = QPushButton("إغلاق")
        b.clicked.connect(self.reject)
        h.addWidget(b)
        self.b_generer = bouton_couleur("توليد " + titre, coul, picto)
        self.b_generer.clicked.connect(lambda: self.generer())
        h.addWidget(self.b_generer)
        v.addLayout(h)
        self.lignes: list = []
        self.chercher()
        self.resize(820, 720)

    def ouvrir(self) -> None:
        self.show()
        self.raise_()

    def _choisir(self) -> None:
        d = self.choix.currentData()
        if d:
            self.du.definir(d[0])
            self.au.definir(d[1])

    def chercher(self) -> None:
        u = self.page.barre_unites.unite
        t = self.recherche.text()
        self.lignes = el.rechercher(self.f.conn, t, unite=u, limite=60 if t.strip() else 2000)
        self.table.setRowCount(len(self.lignes))
        for i, r in enumerate(self.lignes):
            for j, x in enumerate((r["code_massar"], el.nom_complet(r), r["classe"] or "—")):
                self.table.setItem(i, j, cellule(x, r["id"]))
        self._compte()

    def ids(self) -> list[int]:
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        return [self.table.item(r, 0).data(Qt.UserRole) for r in rows]

    def _compte(self) -> None:
        n = len(self.ids())
        self.l_choix.setText(f"المحدَّدون: {n}" + (" (حدد عدة تلاميذ بالضغط على Ctrl أو Shift)" if self.multiple
                                                  else "") if n else "حدد التلميذ من اللائحة.")

    def generer(self):
        ids = self.ids()
        if not ids:
            message(self.message, "حدد تلميذاً واحداً على الأقل.", True)
            return None
        try:
            if self.cle == "vacances":
                du, au, le = self.du.iso(), self.au.iso(), self.le.iso()
                if not du or not au:
                    raise el.ErreurEleve("بداية العطلة ونهايتها إجباريتان.")
                if au < du:
                    raise el.ErreurEleve("نهاية العطلة قبل بدايتها.")
                doc = el.generer_attestation_vacances(self.f.conn, self.f.dossier, ids[0], date.fromisoformat(du),
                                                      date.fromisoformat(au), date.fromisoformat(le) if le else None)
            elif self.cle == "visite":
                doc = el.generer_visite_medicale(self.f.conn, self.f.dossier, ids[0])
            else:
                doc = el.generer_convocations(self.f.conn, self.f.dossier, ids)[0]
        except ValueError as e:   # ErreurEleve أو تاريخ غير صحيح
            message(self.message, str(e) or "تاريخ غير صحيح.", True)
            return None
        except dc.ErreurDocument as e:
            message(self.message, str(e), True)
            return None
        message(self.message, f"وُلّدت الوثيقة وحُفظت في الأرشيف: \u2066{doc.chemin.name}\u2069")
        self.page.compter_documents()
        if self.page.eleve_id in ids:
            self.page.afficher(self.page.eleve_id)
        try:
            bureautique.ouvrir(doc.chemin)
        except OSError as e:
            message(self.message, f"وُلّدت الوثيقة لكن تعذر فتحها: {e}", True)
        return doc


class DialogueConvocationsOccasion(QDialog):
    """استدعاءات المناسبات (الأبواب المفتوحة، اللقاء التواصلي، الجمع العام) في نافذة منبثقة، بنفس واجهة
    «الإعلام والتواصل» والمناسبة مختارة مسبقاً."""

    def __init__(self, page, occasion: str):
        super().__init__(page)
        from idara.services import convocations as cvs
        from idara.ui.page_communication import VueConvocations
        self.page, self.f = page, page.f
        _, titre, desc, coul, picto = next(d for d in DOCUMENTS if d[0] == occasion)
        self.setWindowTitle(titre)
        self.setLayoutDirection(Qt.RightToLeft)
        self.setModal(True)
        v = QVBoxLayout(self)
        v.setContentsMargins(18, 16, 18, 16)
        v.setSpacing(10)
        v.addWidget(entete(titre, desc + " اقتصاد الورق: 1 إلى 8 استدعاءات في الصفحة، بخطوط قص."))
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.hide()
        v.addWidget(self.message)
        self.vue = VueConvocations(self)
        self.vue.occasion.setCurrentIndex(self.vue.occasion.findData(occasion))
        self.vue.rafraichir()
        from PySide6.QtWidgets import QScrollArea
        zone = QScrollArea()
        zone.setWidgetResizable(True)
        zone.setFrameShape(QFrame.NoFrame)
        zone.setWidget(self.vue)
        v.addWidget(zone, 1)
        self.occasion = occasion
        assert occasion in cvs.OCCASIONS
        self.resize(900, 820)

    def ouvrir(self) -> None:
        self.show()
        self.raise_()

    def generer(self):
        return self.vue.generer()


class PageEleves(QWidget):
    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        self.eleve_id: int | None = None
        racine = QVBoxLayout(self)
        racine.setContentsMargins(40, 32, 40, 32)
        racine.setSpacing(16)
        racine.addWidget(entete("وثائق التلاميذ", "اختر الوثيقة فتنبثق نافذتها: اختيار التلميذ أو التلاميذ، ثم "
                                                  "المعطيات، ثم التوليد. وتحتها لائحة التلاميذ وبطاقة كل واحد."))
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.hide()
        racine.addWidget(self.message)

        # ---- معرض الوثائق (طلب المدير 2026-11-18) ----
        c, cv = carte("الوثائق التي يمكن توليدها")
        self.cartes_docs: dict[str, CarteDocument] = {}
        g = QGridLayout()
        g.setSpacing(14)
        for i, (k, titre, desc, coul, picto) in enumerate(DOCUMENTS):
            cd = CarteDocument(k, titre, desc, coul, picto)
            cd.clique.connect(self.ouvrir_document)
            self.cartes_docs[k] = cd
            g.addWidget(cd, i // 3, i % 3)
        cv.addLayout(g)
        racine.addWidget(c)

        # البحث والنتائج
        c, cv = carte("لائحة التلاميذ")
        self.recherche = QLineEdit()
        self.recherche.setPlaceholderText("بحث: الاسم أو النسب (بالعربية أو الفرنسية) أو رمز مسار")
        self.recherche.setClearButtonEnabled(True)
        self.recherche.textChanged.connect(self.chercher)
        # المجموعة المدرسية: تلاميذ كل وحدة على حدة، و«المؤسسة كاملة» للجميع (طلب المدير 2026-11-07)
        from idara.ui.unites import BarreUnites
        self.barre_unites = BarreUnites(lambda: self.f.conn, lambda _u: self.chercher(self.recherche.text()))
        cv.addWidget(self.barre_unites)
        cv.addWidget(self.recherche)
        self.resultats = tableau(["الرمز", "الاسم", "القسم", "الوضعية"])
        self.resultats.setSelectionMode(self.resultats.SelectionMode.ExtendedSelection)
        self.resultats.itemSelectionChanged.connect(self._selection)
        self.resultats.itemDoubleClicked.connect(lambda _: self.ouvrir_fiche())
        self.resultats.setMinimumHeight(380)
        # نسخ الرمز من اللائحة أيضاً: النقر بالزر الأيمن أو Ctrl+C
        from PySide6.QtGui import QAction, QKeySequence
        a = QAction("نسخ رمز مسار", self.resultats)
        a.setShortcut(QKeySequence.Copy)
        a.setShortcutContext(Qt.WidgetShortcut)
        a.triggered.connect(lambda: self.copier_code(depuis_liste=True))
        self.resultats.addAction(a)
        self.resultats.setContextMenuPolicy(Qt.ActionsContextMenu)
        cv.addWidget(self.resultats, 1)
        h = QHBoxLayout()
        self.nb = QLabel()
        self.nb.setObjectName("etiquette")
        h.addWidget(self.nb, 1)
        self.b_ouvrir = QPushButton("فتح بطاقة التلميذ المحدد")
        self.b_ouvrir.setEnabled(False)
        self.b_ouvrir.clicked.connect(lambda: self.ouvrir_fiche())
        h.addWidget(self.b_ouvrir)
        self.b_convocations = QPushButton("استدعاء أولياء أمور المحددين")
        self.b_convocations.setToolTip("حدد عدة تلاميذ بالضغط على Ctrl، ثم ولّد استدعاءاتهم في ملف واحد")
        self.b_convocations.clicked.connect(self.convocations)
        h.addWidget(self.b_convocations)
        cv.addLayout(h)
        racine.addWidget(c, 1)

        # البطاقة
        self.c_fiche, fv = carte()
        self.titre = QLabel()
        self.titre.setObjectName("titrePage")
        self.sous_titre = QLabel()
        self.sous_titre.setObjectName("sousTitre")
        self.sous_titre.setWordWrap(True)
        self.sous_titre.setTextInteractionFlags(Qt.TextSelectableByMouse)
        fv.addWidget(self.titre)
        ligne_code = QHBoxLayout()
        ligne_code.addWidget(self.sous_titre, 1)
        # نسخ رمز مسار (طلب المدير 2026-11-13) للصقه في منظومة مسار أو في مراسلة
        self.b_copier = QPushButton("نسخ رمز مسار")
        self.b_copier.setToolTip("ينسخ رمز مسار التلميذ للصقه حيث تشاء (Ctrl+V)")
        self.b_copier.clicked.connect(lambda: self.copier_code())
        ligne_code.addWidget(self.b_copier, 0, Qt.AlignTop)
        fv.addLayout(ligne_code)

        actions = QGridLayout()
        actions.setSpacing(8)
        self.b_vacances = bouton_couleur("شهادة العطلة", "#1565C0", "calendrier")
        self.b_vacances.clicked.connect(self.dialogue_vacances)
        self.b_visite = bouton_couleur("ورقة الزيارة الطبية", "#00838F", "valider")
        self.b_visite.clicked.connect(self.visite)
        self.b_convoc = bouton_couleur("استدعاء ولي الأمر", "#6A1B9A", "rappel")
        self.b_convoc.clicked.connect(lambda: self.convocations([self.eleve_id]))
        self.b_statut = bouton_couleur("الوضعية (مغادرة، انقطاع...)", "#455A64", "modifier")
        self.b_statut.clicked.connect(self.dialogue_statut)
        for i, b in enumerate((self.b_vacances, self.b_visite, self.b_convoc, self.b_statut)):
            actions.addWidget(b, i // 2, i % 2)
        fv.addLayout(actions)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color:#E4E2DD;")
        fv.addWidget(sep)
        t = QLabel("الهوية")
        t.setObjectName("titreCarte")
        fv.addWidget(t)
        g = QGridLayout()
        g.setHorizontalSpacing(16)
        self.c_nom_ar, self.c_prenom_ar = champ(), champ()
        self.c_nom_fr, self.c_prenom_fr = champ(ltr=True), champ(ltr=True)
        self.c_lieu_ar, self.c_lieu_fr = champ(), champ(ltr=True)
        self.c_date = ChampDate()
        self.r_m, self.r_f = QRadioButton("ذكر"), QRadioButton("أنثى")
        grp = QButtonGroup(self)
        grp.addButton(self.r_m)
        grp.addButton(self.r_f)
        sexe = QHBoxLayout()
        sexe.addWidget(self.r_m)
        sexe.addWidget(self.r_f)
        sexe.addStretch()
        champs = [("النسب", self.c_nom_ar), ("الاسم", self.c_prenom_ar), ("Nom", self.c_nom_fr),
                  ("Prénom", self.c_prenom_fr), ("مكان الازدياد", self.c_lieu_ar),
                  ("Lieu de naissance", self.c_lieu_fr), ("تاريخ الازدياد", self.c_date)]
        for i, (lib, w) in enumerate(champs):
            g.addWidget(etiquette(lib, w), (i // 2) * 2, i % 2)
            g.addWidget(w, (i // 2) * 2 + 1, i % 2)
        g.addWidget(etiquette("النوع"), 6, 1)
        g.addLayout(sexe, 7, 1)
        fv.addLayout(g)
        self.verrous = QLabel()
        self.verrous.setObjectName("etiquette")
        self.verrous.setWordWrap(True)
        fv.addWidget(self.verrous)
        b = QPushButton("حفظ التعديلات")
        b.clicked.connect(self.enregistrer)
        fv.addWidget(b, 0, Qt.AlignRight)

        t2 = QLabel("المسار الدراسي والوثائق")
        t2.setObjectName("titreCarte")
        fv.addWidget(t2)
        self.l_parcours = QLabel()
        self.l_parcours.setWordWrap(True)
        fv.addWidget(self.l_parcours)
        self.docs = tableau(["الوثيقة", "التاريخ", ""], etirer=0)
        self.docs.setMinimumHeight(140)
        self.docs.cellDoubleClicked.connect(self._ouvrir_doc)
        fv.addWidget(self.docs)
        fv.addStretch()
        self.c_fiche.hide()
        self.fiche = FenetreFiche(self, "بطاقة التلميذ", "الهوية والمسار الدراسي والوثائق المولدة.", self.c_fiche, 820)
        self.chercher("")
        self.compter_documents()

    # ---------- البحث ----------

    def rafraichir(self) -> None:
        self.barre_unites.actualiser()
        self.chercher(self.recherche.text())
        if self.eleve_id:
            self.afficher(self.eleve_id)

    def chercher(self, texte: str) -> None:
        u = self.barre_unites.unite if hasattr(self, "barre_unites") else None
        lignes = el.rechercher(self.f.conn, texte, unite=u, limite=60 if texte.strip() else 2000)
        self.resultats.setRowCount(len(lignes))
        for i, r in enumerate(lignes):
            for j, v in enumerate([r["code_massar"], el.nom_complet(r), r["classe"] or "—",
                                   el.STATUTS.get(r["statut"], "غير مسجل")]):
                self.resultats.setItem(i, j, cellule(v, r["id"]))
        portee = f" · {u}" if u else ""
        self.nb.setText(f"{len(lignes)} نتيجة{portee}" if texte.strip() else
                        f"تلاميذ السنة الجارية{portee}: {len(lignes)}")

    def _selection(self) -> None:
        ids = self.ids_selectionnes()
        self.b_ouvrir.setEnabled(len(ids) == 1)
        if len(ids) == 1:
            self.afficher(ids[0])

    def ouvrir_fiche(self, eleve_id: int | None = None) -> FenetreFiche | None:
        if eleve_id is not None:
            self.afficher(eleve_id)
        if not self.eleve_id:
            return None
        self.fiche.definir_titre("بطاقة التلميذ: " + self.titre.text())
        self.fiche.ouvrir()
        return self.fiche

    # ---------- معرض الوثائق ----------

    def compter_documents(self) -> None:
        for k, code in (("vacances", "attestation_vacances"), ("visite", "visite_medicale"),
                        ("convocation", "convocation_parent")):
            r = self.f.conn.execute("SELECT COUNT(*) FROM document_genere d JOIN modele_document m ON "
                                    "m.id=d.modele_id WHERE m.code=?", (code,)).fetchone()
            self.cartes_docs[k].definir_compte(r[0] if r else 0)

    def ouvrir_document(self, cle: str, ouvrir: bool = True):
        """الضغط على وثيقة في المعرض: نافذتها المنبثقة، أو صفحتها إن كانت لها صفحة خاصة."""
        if cle in PAGES_DOCS:
            self.f.aller_a(PAGES_DOCS[cle])
            return None
        if cle in ("portes", "rencontre", "ag_parents"):
            d = DialogueConvocationsOccasion(self, cle)
        else:
            d = DialogueDocEleve(self, cle)
        self.dialogue = d
        if ouvrir:
            d.ouvrir()
        return d

    def ids_selectionnes(self) -> list[int]:
        lignes = sorted({i.row() for i in self.resultats.selectedIndexes()})
        return [self.resultats.item(r, 0).data(Qt.UserRole) for r in lignes]

    # ---------- البطاقة ----------

    def copier_code(self, depuis_liste: bool = False) -> str | None:
        """ينسخ رمز مسار التلميذ المعروض (أو المحدد في اللائحة) إلى الحافظة."""
        from PySide6.QtWidgets import QApplication
        ids = self.ids_selectionnes()
        eid = (ids[0] if ids else None) if depuis_liste else (self.eleve_id or (ids[0] if ids else None))
        if not eid:
            return None
        code = el.fiche(self.f.conn, eid)["code_massar"]
        QApplication.clipboard().setText(code)
        message(self.message, f"نُسخ رمز مسار \u2066{code}\u2069: الصقه حيث تشاء (Ctrl+V).")
        return code

    def afficher(self, eleve_id: int) -> None:
        self.eleve_id = eleve_id
        r = el.fiche(self.f.conn, eleve_id)
        self.titre.setText(el.nom_complet(r))
        niveau = tx.niveau_ar(r["niveau"]) if r["niveau"] in tx.NIVEAUX else "غير محدد"
        if r["niveau"] and not r["niveau_confirme"]:
            niveau += " (مقترح، لم يُؤكَّد)"
        self.sous_titre.setText(
            f"رمز مسار: \u2066{r['code_massar']}\u2069    القسم: \u2066{r['classe'] or '—'}\u2069\n"
            f"المستوى: {niveau}    الوضعية: {el.STATUTS.get(r['statut'], 'غير مسجل في السنة الجارية')}")
        self.c_nom_ar.setText(r["nom_ar"] or "")
        self.c_prenom_ar.setText(r["prenom_ar"] or "")
        self.c_nom_fr.setText(r["nom_fr"] or "")
        self.c_prenom_fr.setText(r["prenom_fr"] or "")
        self.c_lieu_ar.setText(r["lieu_ar"] or "")
        self.c_lieu_fr.setText(r["lieu_fr"] or "")
        self.c_date.definir(r["date_naissance"])
        (self.r_f if r["sexe"] == "F" else self.r_m).setChecked(True)
        verrous = el.champs_verrouilles(self.f.conn, eleve_id)
        self.verrous.setText("معدّل يدوياً (لا يمحوه الاستيراد من مسار): " + "، ".join(sorted(verrous))
                             if verrous else "")
        lignes = []
        for p in el.parcours(self.f.conn, eleve_id):
            t = f"{p['annee']} · {p['classe'] or '—'} · {tx.niveau_ar(p['niveau']) if p['niveau'] in tx.NIVEAUX else '—'} · {el.STATUTS.get(p['statut'], '')}"
            if p["date_sortie"]:
                t += f" بتاريخ {tx.date_chiffres(p['date_sortie'])}"
            if p["etab_destination"]:
                t += f" نحو {p['etab_destination']}"
            if p["etab_origine"]:
                t += f" من {p['etab_origine']}"
            lignes.append("•  " + t)
        self.l_parcours.setText("\n".join(lignes))
        docs = el.documents(self.f.conn, eleve_id)
        self.docs.setRowCount(len(docs))
        for i, d in enumerate(docs):
            self.docs.setItem(i, 0, cellule(d["titre"], d["fichier_archive"]))
            self.docs.setItem(i, 1, cellule(d["date_generation"][:16]))
            self.docs.setItem(i, 2, cellule("فتح ↵"))
        self.c_fiche.show()

    def enregistrer(self) -> list[str] | None:
        try:
            valeurs = {"nom_ar": self.c_nom_ar.text(), "prenom_ar": self.c_prenom_ar.text(),
                       "nom_fr": self.c_nom_fr.text(), "prenom_fr": self.c_prenom_fr.text(),
                       "sexe": "F" if self.r_f.isChecked() else "M", "date_naissance": self.c_date.iso(),
                       "lieu_ar": self.c_lieu_ar.text(), "lieu_fr": self.c_lieu_fr.text()}
            changes = el.modifier(self.f.conn, self.eleve_id, valeurs)
        except ValueError as e:
            message(self.message, str(e) or "تاريخ غير صحيح.", True)
            return None
        message(self.message, "حُفظت التعديلات." if changes else "لا تغيير.")
        self.rafraichir()
        return changes

    # ---------- الوثائق ----------

    def _resultat(self, doc) -> None:
        message(self.message, f"وُلّدت الوثيقة وحُفظت في الأرشيف: \u2066{doc.chemin.name}\u2069")
        try:
            bureautique.ouvrir(doc.chemin)
        except OSError as e:
            message(self.message, f"وُلّدت الوثيقة لكن تعذر فتحها: {e}", True)
        self.afficher(self.eleve_id) if self.eleve_id else None

    def dialogue_vacances(self) -> None:
        try:
            vac = cal.vacances(self.f.conn)
        except cal.ErreurCalendrier:
            vac = []
        d = DialogueVacances(self.titre.text(), self, vac)
        if d.exec() == QDialog.Accepted:
            self.vacances(*d.valeurs())

    def vacances(self, du: date, au: date, le: date | None = None):
        try:
            doc = el.generer_attestation_vacances(self.f.conn, self.f.dossier, self.eleve_id, du, au, le)
        except (el.ErreurEleve, dc.ErreurDocument) as e:
            message(self.message, str(e), True)
            return None
        self._resultat(doc)
        return doc

    def visite(self):
        try:
            doc = el.generer_visite_medicale(self.f.conn, self.f.dossier, self.eleve_id)
        except (el.ErreurEleve, dc.ErreurDocument) as e:
            message(self.message, str(e), True)
            return None
        self._resultat(doc)
        return doc

    def convocations(self, ids: list[int] | None = None):
        ids = ids if ids else self.ids_selectionnes()
        try:
            docs = el.generer_convocations(self.f.conn, self.f.dossier, ids)
        except (el.ErreurEleve, dc.ErreurDocument) as e:
            message(self.message, str(e), True)
            return None
        self._resultat(docs[0])
        return docs

    def dialogue_statut(self) -> None:
        d = DialogueStatut(self.titre.text(), self)
        if d.exec() == QDialog.Accepted:
            try:
                le = d.le.iso()
            except ValueError:
                message(self.message, "التاريخ غير صحيح.", True)
                return
            self.statut(d.statut.currentData(), le, d.etab.text(), d.motif.text())

    def statut(self, code: str, le: str, etab: str = "", motif: str = "") -> bool:
        try:
            el.changer_statut(self.f.conn, self.eleve_id, code, le, etab, motif)
        except el.ErreurEleve as e:
            message(self.message, str(e), True)
            return False
        message(self.message, f"سُجّلت الوضعية: {el.STATUTS[code]}.")
        self.rafraichir()
        return True

    def _ouvrir_doc(self, ligne: int, _col: int) -> None:
        rel = self.docs.item(ligne, 0).data(Qt.UserRole)
        try:
            bureautique.ouvrir(self.f.dossier.racine / rel)
        except OSError as e:
            message(self.message, f"تعذر فتح الملف: {e}", True)
