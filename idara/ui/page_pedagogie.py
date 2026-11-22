"""قسم التدبير التربوي: أداء المؤسسة بالأسدوس، التعلمات الأساس (مؤسسات الريادة)، الأندية والأنشطة الموازية."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QComboBox, QFileDialog, QGridLayout, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton,
                               QVBoxLayout, QWidget)

from idara.services import bureautique
from idara.services import eleves as el
from idara.services import evaluation as ev
from idara.services import personnel as rh
from idara.services import tarl
from idara.services import vie_scolaire as vs
from idara.ui.composants import bouton, carte, entete
from idara.ui.formulaires import champ, etiquette
from idara.ui import theme
from idara.ui.saisie import ChampDate, TableauRapide, cellule, message, tableau

VERT, ROUGE = QColor(theme.VERT), QColor(theme.ROUGE_TEXTE)


def _n(x, suffixe="") -> str:
    return "—" if x is None else f"{x:.2f}{suffixe}"


def _ecart(x, suffixe="") -> str:
    if x is None:
        return "—"
    return "\u200e" + ("+" if x > 0 else "") + f"{x:.2f}{suffixe}"  # الإشارة على يسار الرقم


def _grille(paires, etirer=None) -> QGridLayout:
    g = QGridLayout()
    g.setHorizontalSpacing(16)
    g.setVerticalSpacing(4)
    for j, (lib, w) in enumerate(paires):
        g.addWidget(etiquette(lib, w), 0, j)
        g.addWidget(w, 1, j)
    g.setColumnStretch(len(paires) if etirer is None else etirer, 1)
    return g


def _page(titre: str, sous: str) -> tuple[QVBoxLayout, QLabel]:
    racine = QVBoxLayout()
    racine.setContentsMargins(40, 32, 40, 32)
    racine.setSpacing(16)
    racine.addWidget(entete(titre, sous))
    m = QLabel()
    m.setWordWrap(True)
    m.hide()
    racine.addWidget(m)
    return racine, m


# ======================================================================
class PagePerformance(QWidget):
    """أداء المؤسسة: كل أسدوس مقارنة بالذي قبله (المعدل ونسبة الحاصلين على المعدل)."""

    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        racine, self.message = _page("أداء المؤسسة حسب النتائج",
                                     "معدلا الدورتين من ملف «مجمل المعدلات» (مسار)، نفس الملف المستورد في مجالس "
                                     "الأقسام. كل أسدوس يقارن بالأسدوس الذي قبله: الأول بالثاني من السنة الفارطة، "
                                     "والثاني بالأول من نفس السنة.")
        self.setLayout(racine)
        c, v = carte()
        h = QHBoxLayout()
        b = QPushButton("استيراد ملفات «مجمل المعدلات»")
        b.setObjectName("principal")
        b.clicked.connect(lambda: self.choisir())
        h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        self.periode, self.vue = QComboBox(), QComboBox()
        self.vue.addItem("حسب المستويات", "niveau")
        self.vue.addItem("حسب الأقسام", "classe")
        self.periode.currentIndexChanged.connect(lambda _: self.afficher())
        self.vue.currentIndexChanged.connect(lambda _: self.afficher())
        v.addLayout(_grille([("الأسدوس", self.periode), ("العرض", self.vue)]))
        self.titre = QLabel()
        self.titre.setObjectName("titreCarte")
        v.addWidget(self.titre)
        self.table = tableau(["الفئة", "العدد", "المعدل", "نسبة النجاح", "المعدل قبله", "النسبة قبله",
                              "تطور المعدل", "تطور النسبة"], etirer=0)
        self.table.setMinimumHeight(360)
        v.addWidget(self.table)
        self.note = QLabel("نسبة النجاح: نسبة الحاصلين على معدل 5/10 فأكثر في الأسدوس.")
        self.note.setObjectName("sousTitre")
        self.note.setWordWrap(True)
        v.addWidget(self.note)
        racine.addWidget(c)
        racine.addStretch()
        self.rafraichir()

    def rafraichir(self) -> None:
        courant = self.periode.currentData()
        self.periode.blockSignals(True)
        self.periode.clear()
        for p in reversed(ev.periodes(self.f.conn)):
            self.periode.addItem(ev.libelle_periode(p), p)
        i = self.periode.findData(courant)
        self.periode.setCurrentIndex(i if i >= 0 else 0)
        self.periode.blockSignals(False)
        if not self.periode.count():
            message(self.message, "لا نتائج بعد. استورد ملفات «مجمل المعدلات» من مسار (بعد الأسدوس الأول أو الثاني).")
        self.afficher()

    def afficher(self) -> None:
        p = self.periode.currentData()
        lignes = ev.comparaison(self.f.conn, tuple(p), self.vue.currentData()) if p else []
        self.table.setRowCount(len(lignes))
        for i, l in enumerate(lignes):
            vals = (l["libelle"], str(l["effectif"]), _n(l["moyenne"]), _n(l["taux"], "%"), _n(l["moyenne_avant"]),
                    _n(l["taux_avant"], "%"), _ecart(l["ecart_moyenne"]), _ecart(l["ecart_taux"], "%"))
            for j, v in enumerate(vals):
                it = cellule(v)
                if j >= 6:
                    x = l["ecart_moyenne" if j == 6 else "ecart_taux"]
                    if x:
                        it.setForeground(VERT if x > 0 else ROUGE)
                if l["cle"] == "المؤسسة":
                    f = it.font()
                    f.setBold(True)
                    it.setFont(f)
                self.table.setItem(i, j, it)
        if lignes:
            l0 = lignes[0]
            self.titre.setText(f"{l0['periode']}" + (f" مقارنة ب{l0['avant']}" if l0["avant"] else
                                                     " (لا أسدوس قبله في البيانات)"))
            self.note.setText("نسبة النجاح: نسبة الحاصلين على معدل 5/10 فأكثر في الأسدوس. المقارنة بين أسدوسين من "
                              "سنتين مختلفتين تخص نفس المستوى الدراسي، لا نفس التلاميذ.")
        else:
            self.titre.setText("")
            self.note.setText("")

    def choisir(self) -> None:
        fs, _ = QFileDialog.getOpenFileNames(self, "ملفات «مجمل المعدلات» من مسار", "", "Excel (*.xlsx)")
        if fs:
            self.importer([Path(x) for x in fs])

    def importer(self, chemins: list[Path]):
        try:
            r = ev.importer(self.f.conn, chemins)
        except ev.ErreurEvaluation as e:
            message(self.message, str(e), True)
            return None
        self.rafraichir()
        message(self.message, f"استوردت نتائج {r.eleves} تلميذاً ({len(r.classes)} أقسام) للسنة {r.annee}.")
        return r


# ======================================================================
class PageTarl(QWidget):
    """التعلمات الأساس: مستويات TaRL في رائزي الموضعة القبلي والبعدي."""

    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        racine, self.message = _page("تتبع التعلمات الأساس",
                                     "من تصدير مسار «مستويات التعلم»: توزيع التلاميذ على مستويات اللغة العربية واللغة "
                                     "الفرنسية والرياضيات في رائزي الموضعة القبلي والبعدي، ونسبة بلوغ المستوى المتوقع.")
        self.setLayout(racine)
        c, v = carte()
        h = QHBoxLayout()
        b = QPushButton("استيراد «مستويات التعلم» من مسار")
        b.setObjectName("principal")
        b.clicked.connect(lambda: self.choisir())
        h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        self.annee, self.groupe, self.matiere = QComboBox(), QComboBox(), QComboBox()
        for k, lib in tarl.MATIERES.items():
            self.matiere.addItem(lib, k)
        self.annee.currentIndexChanged.connect(lambda _: self._groupes())
        self.groupe.currentIndexChanged.connect(lambda _: self.afficher())
        self.matiere.currentIndexChanged.connect(lambda _: self.afficher())
        v.addLayout(_grille([("السنة", self.annee), ("الفئة", self.groupe), ("المادة", self.matiere)]))
        self.resume = QLabel()
        self.resume.setObjectName("titreCarte")
        self.resume.setWordWrap(True)
        v.addWidget(self.resume)
        self.table = tableau(["المستوى", "القبلي (العدد)", "القبلي (%)", "البعدي (العدد)", "البعدي (%)"], etirer=0)
        self.table.setMinimumHeight(300)
        v.addWidget(self.table)
        racine.addWidget(c)
        c, v = carte("مسارات الدعم حسب الأقسام (تصدير «مجموعات الدعم»)")
        self.parcours = tableau(["القسم", "العربية", "الفرنسية", "الرياضيات"], etirer=0)
        self.parcours.setMinimumHeight(160)
        v.addWidget(self.parcours)
        racine.addWidget(c)
        c, v = carte("التلاميذ دون المستوى المتوقع في الرائز البعدي (للدعم)")
        self.difficulte = tableau(["القسم", "رمز مسار", "الاسم", "المستوى البعدي", "المتوقع"], etirer=2)
        self.difficulte.setMinimumHeight(260)
        v.addWidget(self.difficulte)
        racine.addWidget(c)
        racine.addStretch()
        self.rafraichir()

    def rafraichir(self) -> None:
        courant = self.annee.currentText()
        self.annee.blockSignals(True)
        self.annee.clear()
        self.annee.addItems(tarl.annees(self.f.conn))
        if courant:
            self.annee.setCurrentText(courant)
        self.annee.blockSignals(False)
        if not self.annee.count():
            message(self.message, "لا مستويات تعلم بعد. صدِّر «مستويات التعلم» من مسار (فضاء مؤسسات الريادة) ثم استوردها.")
        self._groupes()

    def _groupes(self) -> None:
        courant = self.groupe.currentData()
        self.groupe.blockSignals(True)
        self.groupe.clear()
        if self.annee.currentText():
            for k, lib in tarl.groupes(self.f.conn, self.annee.currentText()):
                self.groupe.addItem(lib, k)
        i = self.groupe.findData(courant)
        self.groupe.setCurrentIndex(i if i >= 0 else 0)
        self.groupe.blockSignals(False)
        self.afficher()

    def afficher(self) -> None:
        a, g, m = self.annee.currentText(), self.groupe.currentData(), self.matiere.currentData()
        pc = tarl.parcours(self.f.conn, a) if a else {}
        self.parcours.setRowCount(len(pc))
        for i, (cl, d) in enumerate(pc.items()):
            for j, v in enumerate((cl.replace("-", ""), d.get("ar", "—"), d.get("fr", "—"), d.get("ma", "—"))):
                self.parcours.setItem(i, j, cellule(v))
        if not (a and g):
            self.table.setRowCount(0)
            self.difficulte.setRowCount(0)
            self.resume.setText("")
            return
        tb = tarl.tableau_bord(self.f.conn, a, g, m)
        self.table.setRowCount(len(tb["echelle"]))
        for i, niv in enumerate(tb["echelle"]):
            vals = [niv]
            for ep in ("pre", "post"):
                n, t = tb["distribution"][ep][niv], tb["effectifs"][ep]
                vals += [str(n), f"{n / t * 100:.2f}%" if t else "—"]
            for j, v in enumerate(vals):
                self.table.setItem(i, j, cellule(v))
        ta, ev_ = tb["taux_attendu"], tb["evolution"]
        self.resume.setText(
            f"بلوغ المستوى المتوقع: القبلي {_n(ta['pre'], '%')} ← البعدي {_n(ta['post'], '%')} — "
            f"التطور بين الرائزين ({tb['compares']} تلميذاً): تحسن {ev_['progres']}، استقرار {ev_['stable']}، "
            f"تراجع {ev_['recul']}")
        diff = tarl.eleves_en_difficulte(self.f.conn, a, g, m)
        self.difficulte.setRowCount(len(diff))
        for i, r in enumerate(diff):
            for j, v in enumerate((r["classe"].replace("-", ""), r["code_massar"], r["nom"], r["valeur"],
                                   tarl.attendu(self.f.conn, a, r["niveau"], m) or "—")):
                self.difficulte.setItem(i, j, cellule(v))

    def choisir(self) -> None:
        fs, _ = QFileDialog.getOpenFileNames(self, "«مستويات التعلم» من مسار", "", "Excel (*.xlsx)")
        if fs:
            self.importer([Path(x) for x in fs])

    def importer(self, chemins: list[Path]):
        try:
            r = tarl.importer(self.f.conn, chemins)
        except tarl.ErreurTarl as e:
            message(self.message, str(e), True)
            return None
        self.rafraichir()
        self.annee.setCurrentText(r.annee)
        txt = f"استوردت مستويات {r.eleves} تلميذاً ({len(r.classes)} أقسام) للسنة {r.annee}."
        if r.parcours:
            txt += f" ومسارات الدعم ({r.parcours})."
        if r.alertes:
            txt += "\nتنبيهات: " + "؛ ".join(r.alertes[:5]) + (" ..." if len(r.alertes) > 5 else "")
        message(self.message, txt, bool(r.alertes))
        return r


# ======================================================================
class PageVieScolaire(QWidget):
    """الأندية التربوية والأنشطة الموازية: البرنامج السنوي، الإنجاز والحصيلة.
    طلب المدير 2026-11-19: الصفحة للعرض والإحصاء، وإضافة الأندية والأنشطة وتعديلها في نوافذ منبثقة."""

    def __init__(self, fenetre):
        super().__init__()
        from idara.ui.vitrine import CarteFiltre, FenetreFiche, bouton_couleur, grille_cartes
        self.f = fenetre
        self.club_id: int | None = None
        self.act_id: int | None = None
        racine, self.message = _page("الأندية التربوية والأنشطة الموازية", "")
        self.setLayout(racine)
        self.cartes = {
            "clubs": CarteFiltre("clubs", "الأندية", "#8E24AA", "personnes", " "),
            "membres": CarteFiltre("membres", "التلاميذ المنخرطون", "#00897B", "personnes", " "),
            "programmees": CarteFiltre("programmees", "أنشطة مبرمجة", "#1565C0", "calendrier", " "),
            "realisees": CarteFiltre("realisees", "أنشطة منجزة", "#2E7D32", "valider", " "),
        }
        racine.addLayout(grille_cartes(list(self.cartes.values()), 4))
        self.indic = QLabel()
        self.indic.setObjectName("etiquette")
        self.indic.setWordWrap(True)
        racine.addWidget(self.indic)
        h = QHBoxLayout()
        h.setSpacing(12)
        for lib, coul, pic, fn in (("نادٍ جديد", "#8E24AA", "ajouter", lambda: self.ouvrir_club()),
                                   ("نشاط جديد", "#1565C0", "ajouter", lambda: self.ouvrir_activite()),
                                   ("البرنامج السنوي", "#00897B", "document", lambda: self.document("programme")),
                                   ("حصيلة الأنشطة", "#2E7D32", "document", lambda: self.document("bilan"))):
            b = bouton_couleur(lib, coul, pic)
            b.clicked.connect(fn)
            h.addWidget(b)
        h.addStretch()
        racine.addLayout(h)

        # ---- الأندية (الصفحة) ----
        c, v = carte("الأندية التربوية")
        self.clubs = tableau(["النادي", "المنشط(ة)", "التوقيت", "الأعضاء", "أنشطة منجزة", "الإجراءات"], etirer=0)
        self.clubs.setMinimumHeight(200)
        self.clubs.verticalHeader().setDefaultSectionSize(46)
        self.clubs.itemSelectionChanged.connect(self._sel_club)
        self.clubs.itemDoubleClicked.connect(lambda it: self.ouvrir_club(self.clubs.item(it.row(), 0)
                                                                          .data(Qt.UserRole)))
        v.addWidget(self.clubs)
        racine.addWidget(c)
        # ---- الأنشطة (الصفحة) ----
        c, v = carte("البرنامج السنوي للأنشطة وإنجازها")
        self.acts = tableau(["فترة الإنجاز", "نوع النشاط", "النشاط", "الحالة", "المشاركون", "الصور", "الإجراءات"],
                            etirer=2)
        self.acts.setMinimumHeight(240)
        self.acts.verticalHeader().setDefaultSectionSize(46)
        self.acts.itemSelectionChanged.connect(self._sel_act)
        self.acts.itemDoubleClicked.connect(lambda it: self.ouvrir_activite(self.acts.item(it.row(), 0)
                                                                             .data(Qt.UserRole)))
        v.addWidget(self.acts)
        racine.addWidget(c)
        racine.addStretch()

        # ---- نافذة النادي: معطياته وأعضاؤه ----
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(10)
        self.nom_club, self.horaire = champ("مثلا: النادي البيئي"), champ("مثلا: الأربعاء 15:00-16:00")
        self.animateur = QComboBox()
        self.objectifs = champ("الأهداف (اختياري)")
        v.addLayout(_grille([("اسم النادي", self.nom_club), ("المنشط(ة)", self.animateur), ("التوقيت", self.horaire)],
                            etirer=0))
        v.addWidget(self.objectifs)
        h = QHBoxLayout()
        self.b_club_nouveau = bouton_couleur("تسجيل النادي", "#8E24AA", "enregistrer")
        self.b_club_nouveau.clicked.connect(lambda: self.enregistrer_club(True))
        self.b_club_maj = bouton_couleur("حفظ التعديل", "#1565C0", "enregistrer")
        self.b_club_maj.clicked.connect(lambda: self.enregistrer_club(False))
        h.addWidget(self.b_club_nouveau)
        h.addWidget(self.b_club_maj)
        for lib, fn in (("حذف النادي", lambda: self.supprimer_club()), ("لائحة الأعضاء", lambda: self.liste_club())):
            b = bouton(lib)
            b.clicked.connect(fn)
            h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        self.c_membres = QWidget()
        vm = QVBoxLayout(self.c_membres)
        vm.setContentsMargins(0, 0, 0, 0)
        t = QLabel("أعضاء النادي")
        t.setObjectName("titreCarte")
        vm.addWidget(t)
        self.recherche = champ("ابحث عن تلميذ بالاسم أو رمز مسار لإضافته")
        self.recherche.textChanged.connect(lambda _: self._chercher())
        self.candidats = QComboBox()
        self.role = champ("المهمة (اختياري): رئيس النادي، كاتب...")
        vm.addLayout(_grille([("البحث", self.recherche), ("التلميذ", self.candidats), ("المهمة", self.role)], etirer=0))
        h = QHBoxLayout()
        b = QPushButton("إضافة إلى النادي")
        b.clicked.connect(lambda: self.ajouter_membre())
        h.addWidget(b)
        b = QPushButton("سحب العضو المحدد")
        b.clicked.connect(lambda: self.retirer_membre())
        h.addWidget(b)
        h.addStretch()
        vm.addLayout(h)
        self.membres = tableau(["الاسم", "القسم", "المهمة"], etirer=0)
        self.membres.setMinimumHeight(200)
        vm.addWidget(self.membres)
        v.addWidget(self.c_membres)
        self.message_club = QLabel()
        self.message_club.setWordWrap(True)
        self.message_club.hide()
        v.addWidget(self.message_club)
        self.fiche_club = FenetreFiche(self, "نادٍ تربوي", "", w, largeur=900)

        # ---- نافذة النشاط ----
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(10)
        self.type_act, self.club_act, self.statut = QComboBox(), QComboBox(), QComboBox()
        self.type_act.addItems(vs.TYPES)
        for k, lib in vs.STATUTS.items():
            self.statut.addItem(lib, k)
        self.titre_act = champ("العمليات والأنشطة المبرمجة")
        self.intervenants, self.cibles = champ("المتدخلون فيه"), champ("المستهدفون منه")
        self.periode, self.mecanismes = champ("مثلا: شهر أكتوبر"), champ("آليات التنفيذ")
        self.debut, self.fin = ChampDate(), ChampDate()
        self.nb_g, self.nb_f = champ("0", ltr=True), champ("0", ltr=True)
        for x in (self.nb_g, self.nb_f):
            x.setMaximumWidth(80)
        self.bilan = QPlainTextEdit()
        self.bilan.setPlaceholderText("الحصيلة والملاحظات (للنشاط المنجز)")
        self.bilan.setFixedHeight(70)
        v.addLayout(_grille([("نوع النشاط", self.type_act), ("النادي (اختياري)", self.club_act),
                             ("الحالة", self.statut)], etirer=0))
        v.addWidget(etiquette("النشاط", self.titre_act))
        v.addWidget(self.titre_act)
        v.addLayout(_grille([("المتدخلون", self.intervenants), ("المستهدفون", self.cibles)], etirer=0))
        v.addLayout(_grille([("فترة الإنجاز", self.periode), ("من", self.debut), ("إلى", self.fin)], etirer=0))
        v.addLayout(_grille([("آليات التنفيذ", self.mecanismes), ("ذكور", self.nb_g), ("إناث", self.nb_f)], etirer=0))
        v.addWidget(self.bilan)
        h = QHBoxLayout()
        self.b_act_nouveau = bouton_couleur("تسجيل النشاط", "#1565C0", "enregistrer")
        self.b_act_nouveau.clicked.connect(lambda: self.enregistrer_activite(True))
        self.b_act_maj = bouton_couleur("حفظ التعديل", "#1565C0", "enregistrer")
        self.b_act_maj.clicked.connect(lambda: self.enregistrer_activite(False))
        h.addWidget(self.b_act_nouveau)
        h.addWidget(self.b_act_maj)
        self.b_act_rapport = bouton_couleur("تقرير النشاط", "#2E7D32", "document",
                                            "تقرير Word بمعطيات النشاط وحصيلته وصوره")
        self.b_act_rapport.clicked.connect(lambda: self.rapport_activite())
        h.addWidget(self.b_act_rapport)
        b = bouton("حذف النشاط")
        b.clicked.connect(lambda: self.supprimer_activite())
        h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        from idara.ui.photos_ui import BandePhotos
        self.photos_act = BandePhotos(self.f, "activite", w, "صور النشاط")
        v.addWidget(self.photos_act)
        self.message_act = QLabel()
        self.message_act.setWordWrap(True)
        self.message_act.hide()
        v.addWidget(self.message_act)
        self.fiche_act = FenetreFiche(self, "نشاط موازٍ", "", w, largeur=900)
        self.rafraichir()

    def ouvrir_club(self, cid: int | None = None):
        self.club_id = cid
        if cid:
            self._charger_club()
        else:
            for x in (self.nom_club, self.horaire, self.objectifs):
                x.clear()
            self.animateur.setCurrentIndex(0)
            self._membres()
        self.b_club_nouveau.setVisible(cid is None)
        self.b_club_maj.setVisible(cid is not None)
        self.c_membres.setVisible(cid is not None)
        self.message_club.hide()
        self.fiche_club.definir_titre(f"النادي: {self.nom_club.text()}" if cid else "نادٍ جديد")
        self.fiche_club.ouvrir()
        return self.fiche_club

    def ouvrir_activite(self, aid: int | None = None):
        self.act_id = aid
        if aid:
            self._charger_act()
        else:
            for x in (self.titre_act, self.intervenants, self.cibles, self.periode, self.mecanismes, self.nb_g,
                      self.nb_f):
                x.clear()
            self.debut.definir(None)
            self.fin.definir(None)
            self.bilan.clear()
            self.statut.setCurrentIndex(0)
        self.b_act_nouveau.setVisible(aid is None)
        self.b_act_maj.setVisible(aid is not None)
        self.b_act_rapport.setVisible(aid is not None)
        self.photos_act.definir(aid)
        self.message_act.hide()
        self.fiche_act.definir_titre("تعديل نشاط" if aid else "نشاط جديد")
        self.fiche_act.ouvrir()
        return self.fiche_act

    # ---------- التحميل ----------

    def rafraichir(self) -> None:
        self.animateur.clear()
        self.animateur.addItem("—", None)
        for p in rh.lister(self.f.conn):
            self.animateur.addItem(f"{p.prenom_ar} {p.nom_ar}", p.id)
        try:
            cs = vs.clubs(self.f.conn)
            b = vs.bilan(self.f.conn)
        except vs.ErreurVie as e:
            message(self.message, str(e), True)
            return
        from idara.ui.vitrine import vider_colonne_widgets
        vider_colonne_widgets(self.clubs, 5)
        self.clubs.setRowCount(len(cs))
        self.club_act.clear()
        self.club_act.addItem("—", None)
        for i, cl in enumerate(cs):
            for j, v in enumerate((cl["nom"], cl["animateur"] or "—", cl["horaire"] or "—", str(cl["membres"]),
                                   str(cl["activites"]))):
                self.clubs.setItem(i, j, cellule(v, cl["id"] if j == 0 else None))
            self.club_act.addItem(cl["nom"], cl["id"])
        self.cartes["clubs"].definir(b["clubs"])
        self.cartes["membres"].definir(b["membres"])
        self.cartes["programmees"].definir(b["programmees"])
        self.cartes["realisees"].definir(b["realisees"])
        self.cartes["realisees"].note.setText(f"{b['taux']:.0f}% من المبرمج" if b["taux"] is not None else " ")
        from idara.ui.vitrine import ajuster_colonne_actions, boutons_ligne
        for i, cl in enumerate(cs):
            w = boutons_ligne([("فتح", "#8E24AA", "ouvrir", lambda x=cl["id"]: self.ouvrir_club(x)),
                               ("نشاط للنادي", "#1565C0", "ajouter", lambda x=cl["id"]: self._activite_club(x))])
            self.clubs.setCellWidget(i, 5, w)
        ajuster_colonne_actions(self.clubs, 5)
        self.indic.setText(
            f"الأنشطة: مبرمجة {b['programmees']}، منجزة {b['realisees']}"
            + (f" ({b['taux']:.2f}%)" if b["taux"] is not None else "")
            + f" — المشاركون {b['garcons'] + b['filles']} (ذكور {b['garcons']}، إناث {b['filles']}) — "
              f"الأندية {b['clubs']} بـ{b['membres']} عضواً")
        self._acts()
        self._membres()

    def _acts(self) -> None:
        from idara.services import photos as ph
        from idara.ui.vitrine import ajuster_colonne_actions, boutons_ligne, vider_colonne_widgets
        ts = vs.activites(self.f.conn)
        vider_colonne_widgets(self.acts, 6)
        self.acts.setRowCount(len(ts))
        for i, a in enumerate(ts):
            per = a["periode"] or ""
            if a["date_debut"]:
                from idara.services import textes as tx
                per = (per + " " if per else "") + tx.date_chiffres(a["date_debut"])
            part = "—" if a["nb_garcons"] is None else f"{a['nb_garcons'] + (a['nb_filles'] or 0)}"
            nph = ph.nombre(self.f.conn, "activite", a["id"])
            for j, v in enumerate((per, a["type"] + (f": {a['club']}" if a["club"] else ""), a["titre"],
                                   vs.STATUTS[a["statut"]], part, str(nph) if nph else "—")):
                self.acts.setItem(i, j, cellule(v, a["id"] if j == 0 else None))
            self.acts.setCellWidget(i, 6, boutons_ligne([
                ("التقرير", "#2E7D32", "document", lambda x=a["id"]: self.rapport_activite(x)),
                ("الصور", "#00897B", "image", lambda x=a["id"]: self.ouvrir_activite(x))]))
        ajuster_colonne_actions(self.acts, 6)

    def _sel(self, t) -> int | None:
        rows = {i.row() for i in t.selectedIndexes()}
        return t.item(rows.pop(), 0).data(Qt.UserRole) if len(rows) == 1 else None

    def _activite_club(self, cid: int):
        d = self.ouvrir_activite()
        self.club_act.setCurrentIndex(max(0, self.club_act.findData(cid)))
        return d

    def _sel_club(self) -> None:
        self.club_id = self._sel(self.clubs)
        self._charger_club()

    def _charger_club(self) -> None:
        if self.club_id:
            c = vs.club(self.f.conn, self.club_id)
            self.nom_club.setText(c["nom"])
            self.horaire.setText(c["horaire"] or "")
            self.objectifs.setText(c["objectifs"] or "")
            self.animateur.setCurrentIndex(max(0, self.animateur.findData(c["animateur_id"])))
        self._membres()

    def _membres(self) -> None:
        ms = vs.membres(self.f.conn, self.club_id) if self.club_id else []
        self.membres.setRowCount(len(ms))
        for i, m in enumerate(ms):
            for j, v in enumerate((f"{m['prenom_ar']} {m['nom_ar']}", (m["classe"] or "").replace("-", ""),
                                   m["role"] or "عضو(ة)")):
                self.membres.setItem(i, j, cellule(v, m["id"] if j == 0 else None))

    def _chercher(self) -> None:
        self.candidats.clear()
        t = self.recherche.text().strip()
        if len(t) < 2:
            return
        for r in el.rechercher(self.f.conn, t)[:30]:
            self.candidats.addItem(f"{el.nom_complet(r)} ({r['code_massar']})", r["id"])

    def _sel_act(self) -> None:
        self.act_id = self._sel(self.acts)
        self._charger_act()

    def _charger_act(self) -> None:
        if not self.act_id:
            return
        a = vs.activite(self.f.conn, self.act_id)
        self.type_act.setCurrentText(a.type)
        self.club_act.setCurrentIndex(max(0, self.club_act.findData(a.club_id)))
        self.statut.setCurrentIndex(max(0, self.statut.findData(a.statut)))
        for w, val in ((self.titre_act, a.titre), (self.intervenants, a.intervenants), (self.cibles, a.cibles),
                       (self.periode, a.periode), (self.mecanismes, a.mecanismes)):
            w.setText(val or "")
        self.debut.definir(a.date_debut or "")
        self.fin.definir(a.date_fin or "")
        self.nb_g.setText("" if a.nb_garcons is None else str(a.nb_garcons))
        self.nb_f.setText("" if a.nb_filles is None else str(a.nb_filles))
        self.bilan.setPlainText(a.bilan or "")

    # ---------- الأفعال ----------

    def _faire(self, fn, succes: str):
        try:
            r = fn()
        except (vs.ErreurVie, ValueError) as e:
            for m in (self.message, self.message_club, self.message_act):
                message(m, str(e) or "قيمة غير صحيحة.", True)
            return None
        cid = self.club_id
        self.rafraichir()
        self.club_id = cid
        self._membres()
        for m in (self.message, self.message_club, self.message_act):
            message(m, succes)
        return True if r is None else r

    def enregistrer_club(self, nouveau: bool):
        if not nouveau and not self.club_id:
            message(self.message, "حدد نادياً في الجدول.", True)
            return None
        r = self._faire(lambda: vs.enregistrer_club(self.f.conn, self.nom_club.text(), self.animateur.currentData(),
                                                    self.objectifs.text(), self.horaire.text(),
                                                    None if nouveau else self.club_id), "حُفظ النادي.")
        if r and nouveau and isinstance(r, int) and self.fiche_club.isVisible():
            self.ouvrir_club(r)   # بعد التسجيل: إضافة الأعضاء في النافذة نفسها
            message(self.message_club, "حُفظ النادي. أضف أعضاءه الآن.")
        return r

    def supprimer_club(self):
        if not self.club_id:
            return None
        r = self._faire(lambda: vs.supprimer_club(self.f.conn, self.club_id), "حُذف النادي.")
        self.club_id = None
        return r

    def ajouter_membre(self):
        if not self.club_id or self.candidats.currentData() is None:
            message(self.message, "حدد نادياً ثم تلميذاً.", True)
            return None
        return self._faire(lambda: vs.ajouter_membre(self.f.conn, self.club_id, self.candidats.currentData(),
                                                     self.role.text()), "أضيف العضو.")

    def retirer_membre(self):
        eid = self._sel(self.membres)
        if not (self.club_id and eid):
            return None
        return self._faire(lambda: vs.retirer_membre(self.f.conn, self.club_id, eid), "سُحب العضو.")

    def _date(self, w: ChampDate) -> str:
        if not w.text().strip("/_ "):
            return ""
        try:
            return w.iso()
        except ValueError:
            raise vs.ErreurVie("تاريخ غير صحيح.") from None

    def enregistrer_activite(self, nouveau: bool):
        if not nouveau and not self.act_id:
            message(self.message, "حدد نشاطاً في الجدول.", True)
            return None

        def fn():
            a = vs.Activite(self.type_act.currentText(), self.titre_act.text(), self.club_act.currentData(),
                            self.intervenants.text(), self.cibles.text(), self.periode.text(),
                            self._date(self.debut), self._date(self.fin), self.mecanismes.text(),
                            self.statut.currentData(), self.nb_g.text(), self.nb_f.text(), self.bilan.toPlainText(),
                            None if nouveau else self.act_id)
            return vs.enregistrer_activite(self.f.conn, a)
        r = self._faire(fn, "حُفظ النشاط.")
        if r and nouveau and isinstance(r, int) and self.fiche_act.isVisible():
            self.ouvrir_activite(r)   # بعد التسجيل: إضافة الصور وتوليد التقرير في النافذة نفسها
            message(self.message_act, "حُفظ النشاط. يمكنك الآن إضافة صوره وتوليد تقريره.")
        return r

    def rapport_activite(self, aid: int | None = None) -> Path | None:
        aid = aid or self.act_id
        if not aid:
            message(self.message, "احفظ النشاط أولاً.", True)
            return None
        try:
            p = vs.generer_rapport_activite(self.f.conn, self.f.dossier, aid)
        except (vs.ErreurVie, Exception) as e:  # noqa: BLE001
            for m in (self.message, self.message_act):
                message(m, str(e), True)
            return None
        message(self.message_act, f"وُلّد تقرير النشاط: {p.name}")
        return self._ouvrir(p)

    def supprimer_activite(self):
        if not self.act_id:
            return None
        r = self._faire(lambda: vs.supprimer_activite(self.f.conn, self.act_id, self.f.dossier), "حُذف النشاط.")
        self.act_id = None
        return r

    def _ouvrir(self, p: Path) -> Path:
        message(self.message, f"وُلّدت الوثيقة: {p.name}")
        try:
            bureautique.ouvrir(p)
        except Exception:  # noqa: BLE001 — الفتح اختياري
            pass
        return p

    def document(self, code: str) -> Path | None:
        fn = {"programme": vs.generer_programme, "bilan": vs.generer_bilan}[code]
        try:
            return self._ouvrir(fn(self.f.conn, self.f.dossier))
        except vs.ErreurVie as e:
            message(self.message, str(e), True)
            return None

    def liste_club(self) -> Path | None:
        if not self.club_id:
            message(self.message, "حدد نادياً في الجدول.", True)
            return None
        try:
            return self._ouvrir(vs.generer_liste_club(self.f.conn, self.f.dossier, self.club_id))
        except vs.ErreurVie as e:
            message(self.message, str(e), True)
            return None


# ======================================================================
class PageRiyada(QWidget):
    """مؤسسات الريادة: ISA2 حسب المراحل، مراسلة الأساتذة، ملف شارة الريادة، التقرير التركيبي."""

    def __init__(self, fenetre):
        super().__init__()
        from PySide6.QtWidgets import QAbstractItemView, QCheckBox, QHeaderView, QTableWidget
        from idara.services import riyada as ry
        self.ry = ry
        self.f = fenetre
        racine, self.message = _page("شارة الريادة", "")   # طلب المدير 2026-11-19: دون جملة تحت العنوان
        self.setLayout(racine)
        from idara.services import isa as isa_srv
        self.isa_srv = isa_srv
        self.annee, self.phase = QComboBox(), QComboBox()
        # ---- حساب ISA2 من نتائج الروائز (صيغة المدير 2026-11-12) ----
        c, v = carte("حساب مؤشر التحكم في التعلمات ISA2 من نتائج الروائز")
        f = QLabel("طريقة الحساب: \u2066Ind = [(3*A + 2*B + 1*C) / 3] * 100\u2069 ثم "
                   f"\u2066ISA2 = {isa_srv.ALPHA:g} * Ind\u2069 — A: تحكم تام، B: تحكم مقنع، C: تحكم ضعيف "
                   "(نسب التلاميذ). المؤشر يُحتسب للمراحل فقط؛ للرائزين القبلي والبعدي يظهر توزيع المستويات "
                   "ويُحفظ مستوى كل تلميذ لبطاقته.")
        f.setObjectName("info")
        f.setWordWrap(True)
        v.addWidget(f)
        self.phase_r = QComboBox()
        for p in isa_srv.PHASES:
            self.phase_r.addItem(isa_srv.libelle_complet(p), p)
        self.phase_r.setCurrentIndex(1)
        self.phase_r.currentIndexChanged.connect(lambda _: self.charger_comptes())
        v.addLayout(_grille([("السنة", self.annee), ("المرحلة / الرائز", self.phase_r)]))
        h = QHBoxLayout()
        for lib, fn, prin in (("تحميل ملف النتائج (Excel)", lambda: self.choisir_resultats(), True),
                              ("حفظ الأعداد", lambda: self.enregistrer_comptes(), False),
                              ("تقرير المؤشر وتحديد الهدف", lambda: self.rapport_isa(), True)):
            b = QPushButton(lib)
            if prin:
                b.setObjectName("principal")
            b.clicked.connect(fn)
            h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        aide = QLabel("الملف: سطر لكل تلميذ برقمه في مسار، وعمود لكل مادة فيه مستوى التحكم (A/B/C أو «تحكم تام/مقنع/"
                      "ضعيف» أو النقطة). يمكن أيضاً كتابة أعداد التلاميذ في كل مستوى مباشرة في الجدول ثم «حفظ الأعداد».")
        aide.setObjectName("sousTitre")
        aide.setWordWrap(True)
        v.addWidget(aide)
        self.comptes = QTableWidget(0, 9)
        self.comptes.setHorizontalHeaderLabels(["القسم", "المادة", "A تام", "B مقنع", "C ضعيف", "المجموع", "Ind",
                                                "المؤشر", "الهدف المقترح"])
        self.comptes.verticalHeader().setVisible(False)
        self.comptes.setEditTriggers(QAbstractItemView.AllEditTriggers)
        hh = self.comptes.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(8, QHeaderView.Stretch)
        self.comptes.setMinimumHeight(320)
        v.addWidget(self.comptes)
        racine.addWidget(c)

        c, v = carte("نسبة التحكم حسب الروائز والمراحل (إدخال مباشر كما في مسار)")
        for p in ry.PHASES:
            self.phase.addItem(ry.libelle_phase(p) + (" (ISA2)" if p >= 1 else ""), p)
        # السنة: مشتركة بين الحساب والإدخال المباشر
        self.annee.currentIndexChanged.connect(lambda _: self.charger())
        self.phase.currentIndexChanged.connect(lambda _: self.charger_saisie())
        v.addLayout(_grille([("المرحلة", self.phase)]))
        self.saisie = QTableWidget(0, 4)
        self.saisie.setHorizontalHeaderLabels(["القسم", "العربية %", "الفرنسية %", "الرياضيات %"])
        self.saisie.verticalHeader().setVisible(False)
        self.saisie.setEditTriggers(QAbstractItemView.AllEditTriggers)
        self.saisie.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.saisie.setMinimumHeight(260)
        v.addWidget(self.saisie)
        h = QHBoxLayout()
        b = QPushButton("حفظ نسب المرحلة")
        b.setObjectName("principal")
        b.clicked.connect(lambda: self.enregistrer_isa())
        h.addWidget(b)
        b = QPushButton("ملء الرائزين من مستويات التعلم")
        b.setToolTip("نسبة بلوغ المستوى المتوقع في رائزي الموضعة القبلي والبعدي (TaRL)، للأقسام التي لم تُدخل نسبتها")
        b.clicked.connect(lambda: self.remplir_tarl())
        h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        t = QLabel("التطور حسب المراحل")
        t.setObjectName("titreCarte")
        v.addWidget(t)
        self.evol = tableau(["القسم", "المادة"], etirer=0)
        self.evol.setMinimumHeight(240)
        v.addWidget(self.evol)
        racine.addWidget(c)

        c, v = carte("مراسلة الأساتذة «بخصوص نتائج المرحلة» (نموذجكم)")
        self.phase_l, self.maths = QComboBox(), QComboBox()
        for p in range(1, 7):
            self.phase_l.addItem(ry.libelle_phase(p), p)   # المراسلة تخص نتائج مرحلة؛ جدولها يبدأ من الرائز القبلي
        for k, lib in (("fr", "أساتذة الفرنسية"), ("ar", "أساتذة العربية"), ("tous", "الجميع"), ("aucun", "لا أحد")):
            self.maths.addItem(lib, k)
        self.date_l = ChampDate()
        self.date_l.definir(date.today().isoformat())
        v.addLayout(_grille([("المرحلة", self.phase_l), ("تُدرج الرياضيات لـ", self.maths), ("التاريخ", self.date_l)]))
        self.felicit = QCheckBox("صيغة التهنئة («أتشرف بتهنئتكم بالنتائج الجيدة...»)")
        self.felicit.setChecked(True)
        v.addWidget(self.felicit)
        h = QHBoxLayout()
        b = QPushButton("توليد المراسلات")
        b.setObjectName("principal")
        b.clicked.connect(lambda: self.lettres())
        h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        racine.addWidget(c)

        c, v = carte("ملف شارة الريادة")
        self.infos_w = {}
        g = QGridLayout()
        g.setHorizontalSpacing(16)
        for i, (cle, lib) in enumerate(ry.INFOS_MANUELLES):
            w = champ()
            lab = etiquette(lib, w)
            lab.setWordWrap(True)
            g.addWidget(lab, (i // 2) * 2, i % 2)
            g.addWidget(w, (i // 2) * 2 + 1, i % 2)
            self.infos_w[cle] = w
        v.addLayout(g)
        self.infos_auto = QLabel()
        self.infos_auto.setWordWrap(True)
        self.infos_auto.setObjectName("sousTitre")
        v.addWidget(self.infos_auto)
        self.pieces = TableauRapide(0, 3)
        self.pieces.setHorizontalHeaderLabels(["الوثيقة", "متوفرة", "ملاحظات"])
        self.pieces.verticalHeader().setVisible(False)
        self.pieces.setWordWrap(True)
        hh = self.pieces.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.Fixed)
        hh.resizeSection(2, 220)
        self.pieces.setMinimumHeight(520)
        v.addWidget(self.pieces)
        h = QHBoxLayout()
        for lib, fn, prin in (("حفظ الملف", lambda: self.enregistrer_dossier(), False),
                              ("ملف الشارة", lambda: self.document("dossier"), True),
                              ("لائحة التلاميذ ذوي الصعوبات", lambda: self.document("difficultes"), True)):
            b = bouton(lib)
            if prin:
                b.setObjectName("principal")
            b.clicked.connect(fn)
            h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        racine.addWidget(c)

        c, v = carte("التقرير التركيبي لأداء المؤسسة والتعلمات الأساس")
        self.obs = QPlainTextEdit()
        self.obs.setPlaceholderText("ملاحظات وتوصيات (اختياري؛ تُترك أسطر فارغة للكتابة باليد)")
        self.obs.setFixedHeight(80)
        v.addWidget(self.obs)
        h = QHBoxLayout()
        b = QPushButton("توليد التقرير التركيبي")
        b.setObjectName("principal")
        b.clicked.connect(lambda: self.document("synthese"))
        h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        racine.addWidget(c)
        racine.addStretch()
        self.rafraichir()

    # ---------- التحميل ----------

    def rafraichir(self) -> None:
        from idara.services import annee as annee_srv
        courant = self.annee.currentText()
        annees = set(ev.annees_disponibles(self.f.conn)) | set(tarl.annees(self.f.conn))
        a = annee_srv.annee_courante(self.f.conn)
        if a:
            annees.add(a["libelle"])
        self.annee.blockSignals(True)
        self.annee.clear()
        self.annee.addItems(sorted(annees, reverse=True))
        if courant:
            self.annee.setCurrentText(courant)
        self.annee.blockSignals(False)
        self.charger()

    def charger(self) -> None:
        self.charger_comptes()
        self.charger_saisie()
        self._evolution()
        self._dossier()

    # ---------- ISA2 من نتائج الروائز ----------

    def remplir_tarl(self) -> int | None:
        a = self.annee.currentText()
        if not a:
            return None
        n = self.ry.remplir_depuis_tarl(self.f.conn, a)
        self.charger_saisie()
        self._evolution()
        message(self.message, f"مُلئت {n} خانة من مستويات التعلم." if n else
                "لا خانات فارغة للرائزين، أو لم تُستورد مستويات التعلم بعد.", not n)
        return n

    def charger_comptes(self) -> None:
        a, p = self.annee.currentText(), self.phase_r.currentData()
        if not a:
            self.comptes.setRowCount(0)
            return
        d = self.isa_srv.resultats(self.f.conn, a)
        cls = sorted(set(self.ry.classes(self.f.conn, a)) | set(d))
        lignes = [(cl, m) for cl in cls for m in self.isa_srv.MATIERES]
        self.comptes.setRowCount(len(lignes))
        for i, (cl, m) in enumerate(lignes):
            k = d.get(cl, {}).get(m, {}).get(p)
            fixe = [cellule(cl.replace("-", ""), (cl, m)), cellule(self.isa_srv.MATIERES[m])]
            vals = ["", "", ""] if k is None else [str(k.a), str(k.b), str(k.c)]
            calc = ["", "", "", ""]
            etape = self.isa_srv.est_etape(p)
            if k is not None and k.total and not etape:
                calc = [str(k.total), "لا يُحتسب", "لا يُحتسب", ""]
            elif k is not None and k.total:
                o = self.isa_srv.objectif(k.isa)
                calc = [str(k.total), f"{k.ind:.2f}%", f"{k.isa:.2f}%",
                        f"من {o['cible_min']:.2f}% إلى {o['cible_max']:.2f}%"]
            items = fixe + [cellule(x) for x in vals] + [cellule(x) for x in calc]
            if k is not None and k.total and etape:
                items[8].setToolTip(f"الفئة: {o['categorie']} — التطور المرتقب من {o['min']} إلى {o['max']} نقطة "
                                    f"— الهدف حسب الجدول: {o['objectif']}")
            for j, it in enumerate(items):
                if j not in (2, 3, 4):
                    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                self.comptes.setItem(i, j, it)

    def enregistrer_comptes(self):
        a, p = self.annee.currentText(), self.phase_r.currentData()

        def fn():
            for i in range(self.comptes.rowCount()):
                cl, m = self.comptes.item(i, 0).data(Qt.UserRole)
                v = [(self.comptes.item(i, j).text().strip() if self.comptes.item(i, j) else "") for j in (2, 3, 4)]
                self.isa_srv.enregistrer(self.f.conn, a, cl, m, p, *v)
        r = self._faire(fn, f"حُفظت أعداد {self.isa_srv.libelle_phase(p)} وحُسب المؤشر.")
        self.charger()
        return r

    def choisir_resultats(self) -> None:
        fs, _ = QFileDialog.getOpenFileNames(self, f"نتائج {self.phase_r.currentText()}", "", "Excel (*.xlsx)")
        if fs:
            self.importer_resultats([Path(x) for x in fs])

    def importer_resultats(self, chemins: list[Path]):
        a, p = self.annee.currentText(), self.phase_r.currentData()
        r = self._faire(lambda: self.isa_srv.importer(self.f.conn, a, p, chemins), "")
        if not r:
            return None
        self.charger()
        txt = (f"حُمّلت نتائج {r.eleves} تلميذاً ({self.isa_srv.libelle_phase(p)}): {r.lignes} سطراً (قسم × مادة)، "
               "وحُسب المؤشر.")
        if r.alertes:
            txt += "\nتنبيهات: " + "؛ ".join(r.alertes[:5]) + (" ..." if len(r.alertes) > 5 else "")
        message(self.message, txt, bool(r.alertes))
        return r

    def rapport_isa(self):
        r = self._faire(lambda: self.isa_srv.generer_rapport(self.f.conn, self.f.dossier, self.annee.currentText()), "")
        return self._ouvrir(r) if r else None

    def charger_saisie(self) -> None:
        a = self.annee.currentText()
        if not a:
            self.saisie.setRowCount(0)
            return
        cls = self.ry.classes(self.f.conn, a)
        d, p = self.ry.isa(self.f.conn, a), self.phase.currentData()
        self.saisie.setRowCount(len(cls))
        for i, cl in enumerate(cls):
            it = cellule(cl.replace("-", ""), cl)
            it.setFlags(it.flags() & ~Qt.ItemIsEditable)
            self.saisie.setItem(i, 0, it)
            for j, m in enumerate(self.ry.MATIERES, start=1):
                v = d.get(cl, {}).get(m, {}).get(p)
                self.saisie.setItem(i, j, cellule("" if v is None else f"{v:.2f}"))

    def _evolution(self) -> None:
        a = self.annee.currentText()
        d = self.ry.isa(self.f.conn, a) if a else {}
        phases = sorted({p for cl in d.values() for m in cl.values() for p in m})
        self.evol.setColumnCount(2 + len(phases))
        self.evol.setHorizontalHeaderLabels(["القسم", "المادة"] + [self.ry.libelle_phase(p) for p in phases])
        lignes = [(cl, m) for cl in sorted(d) for m in self.ry.MATIERES if m in d[cl]]
        self.evol.setRowCount(len(lignes))
        for i, (cl, m) in enumerate(lignes):
            self.evol.setItem(i, 0, cellule(cl.replace("-", "")))
            self.evol.setItem(i, 1, cellule(self.ry.MATIERES[m]))
            ev_ = {p: (v, dl) for p, v, dl in self.ry.evolution(d[cl][m])}
            for j, p in enumerate(phases, start=2):
                if p in ev_:
                    v, dl = ev_[p]
                    it = cellule(f"{v:.2f}%" + ("" if dl is None else f" ({_ecart(dl)})"))
                    if dl:
                        it.setForeground(VERT if dl > 0 else ROUGE)
                else:
                    it = cellule("—")
                self.evol.setItem(i, j, it)

    def _dossier(self) -> None:
        a = self.annee.currentText()
        for cle, w in self.infos_w.items():
            w.setText(self.ry._param(self.f.conn, cle))
        self.infos_auto.setText("من معطيات التطبيق: " + "، ".join(f"{l}: {v or '—'}" for l, v, auto in
                                                                 self.ry.infos(self.f.conn) if auto))
        ps = self.ry.pieces(self.f.conn, a) if a else []
        self.pieces.setRowCount(len(ps))
        for i, p in enumerate(ps):
            it = cellule(f"{p['numero']}- {p['libelle']}" + (f"\n← {p['indice']}" if p["indice"] else ""), p["numero"])
            it.setFlags(it.flags() & ~Qt.ItemIsEditable)
            self.pieces.setItem(i, 0, it)
            ck = cellule("")
            ck.setFlags((ck.flags() | Qt.ItemIsUserCheckable) & ~Qt.ItemIsEditable)
            ck.setCheckState(Qt.Checked if p["disponible"] else Qt.Unchecked)
            self.pieces.setItem(i, 1, ck)
            self.pieces.setItem(i, 2, cellule(p["observation"]))
        self.pieces.resizeRowsToContents()

    # ---------- الأفعال ----------

    def _faire(self, fn, succes: str):
        try:
            r = fn()
        except (self.ry.ErreurRiyada, self.isa_srv.ErreurIsa, ValueError) as e:
            message(self.message, str(e) or "قيمة غير صحيحة.", True)
            return None
        if succes:
            message(self.message, succes)
        return True if r is None else r

    def enregistrer_isa(self):
        a, p = self.annee.currentText(), self.phase.currentData()

        def fn():
            for i in range(self.saisie.rowCount()):
                cl = self.saisie.item(i, 0).data(Qt.UserRole)
                vals = {m: (self.saisie.item(i, j).text() if self.saisie.item(i, j) else "")
                        for j, m in enumerate(self.ry.MATIERES, start=1)}
                self.ry.enregistrer_isa(self.f.conn, a, cl, p, vals)
        r = self._faire(fn, f"حُفظت نسب {self.ry.libelle_phase(p)}.")
        self._evolution()
        return r

    def enregistrer_dossier(self):
        a = self.annee.currentText()

        def fn():
            self.ry.enregistrer_infos(self.f.conn, {k: w.text() for k, w in self.infos_w.items()})
            for i in range(self.pieces.rowCount()):
                self.ry.enregistrer_piece(self.f.conn, a, self.pieces.item(i, 0).data(Qt.UserRole),
                                          self.pieces.item(i, 1).checkState() == Qt.Checked,
                                          self.pieces.item(i, 2).text() if self.pieces.item(i, 2) else "")
        r = self._faire(fn, "حُفظ ملف شارة الريادة.")
        self._dossier()
        return r

    def _ouvrir(self, p: Path) -> Path:
        message(self.message, f"وُلّدت الوثيقة: {p.name}")
        try:
            bureautique.ouvrir(p)
        except Exception:  # noqa: BLE001 — الفتح اختياري
            pass
        return p

    def lettres(self):
        try:
            d = self.date_l.iso()
        except ValueError:
            message(self.message, "التاريخ غير صحيح.", True)
            return None
        r = self._faire(lambda: self.ry.generer_lettres(self.f.conn, self.f.dossier, self.annee.currentText(),
                                                        self.phase_l.currentData(), self.maths.currentData(),
                                                        self.felicit.isChecked(), d), "")
        return self._ouvrir(r) if r else None

    def document(self, code: str):
        a = self.annee.currentText()
        fn = {"dossier": lambda: self.ry.generer_dossier(self.f.conn, self.f.dossier, a),
              "difficultes": lambda: self.ry.generer_liste_difficultes(self.f.conn, self.f.dossier, a),
              "synthese": lambda: self.ry.generer_synthese(self.f.conn, self.f.dossier, a, self.obs.toPlainText())}[code]
        r = self._faire(fn, "")
        return self._ouvrir(r) if r else None
