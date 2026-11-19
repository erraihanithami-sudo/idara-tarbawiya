"""مجالس المؤسسة (المرسوم 2.02.376): الصفحة لجدولة المجالس وأرشيفها، والاستدعاء والمحضر والتركيبة في نوافذ منبثقة
(طلب المدير 2026-11-18).

- بطاقات المجالس الثلاثة: الاجتماعات المنجزة والمبرمجة وآخر اجتماع، ومثلث برتقالي للتنبيهات. عدد الاجتماعات
  متروك للمدير، بلا حد أدنى (طلبه 2026-11-19).
- «لائحة المجالس»: المبرمجة ثم المنجزة، وأمام كل مجلس أزراره (الاستدعاء، تعديل الموعد، توليد المحضر،
  الاطلاع على المحضر).
- «أرشيف الوثائق»: المحاضر والاستدعاءات المولدة، تُفتح بنقرة مزدوجة.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QCheckBox, QComboBox, QFrame, QHBoxLayout,
                               QHeaderView, QLabel, QListWidget, QListWidgetItem, QPlainTextEdit, QPushButton,
                               QRadioButton, QTableWidget, QVBoxLayout, QWidget)

from idara.services import bureautique
from idara.services import conseils_etab as ce
from idara.services import textes as tx
from idara.ui import pictos
from idara.ui.composants import bouton, carte
from idara.ui.formulaires import champ, etiquette
from idara.ui.graphiques import BarresGroupees
from idara.ui.page_pedagogie import _grille, _page
from idara.ui.saisie import ChampDate, cellule, message, tableau
from idara.ui.vitrine import AlerteTriangle, CarteFiltre, FenetreFiche, bouton_couleur, grille_cartes

COULEURS = {"gestion": "#1565C0", "pedagogique": "#2E7D32", "enseignement": "#6A1B9A"}
PICTOS = {"gestion": "personnes", "pedagogique": "document", "enseignement": "statistiques"}


def _texte(w: QPlainTextEdit) -> list[str]:
    return [l.strip() for l in w.toPlainText().splitlines() if l.strip()]


def _choix_conseil(parent: QWidget, rappel) -> tuple[QWidget, dict[str, QRadioButton]]:
    """أزرار اختيار المجلس بألوانها (داخل النوافذ المنبثقة)."""
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    g = QButtonGroup(parent)
    boutons = {}
    for k, lib in ce.CONSEILS.items():
        r = QRadioButton(lib)
        r.setStyleSheet(f"QRadioButton {{ font-weight: 700; color: {COULEURS[k]}; padding: 4px 10px; }}")
        r.setIcon(pictos.icone(PICTOS[k], COULEURS[k], 20))
        g.addButton(r)
        r.toggled.connect(lambda on, k=k: on and rappel(k))
        boutons[k] = r
        h.addWidget(r)
    h.addStretch()
    return w, boutons


class PageConseilsEtab(QWidget):
    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        self.sid: int | None = None
        self.filtre: str | None = None
        racine, self.message = _page("مجالس المؤسسة",
                                     "جدولة مجلس التدبير والمجلس التربوي والمجالس التعليمية وأرشيفها (المرسوم 2.02.376، "
                                     "المواد 17-31). الاستدعاء والمحضر والتركيبة في نوافذ منبثقة. مجالس الأقسام في "
                                     "قسم التقييم.")
        self.setLayout(racine)

        # ---- بطاقات المجالس ----
        self.cartes: dict[str, CarteFiltre] = {}
        for k, lib in ce.CONSEILS.items():
            c_ = CarteFiltre(k, lib, COULEURS[k], PICTOS[k], " ")
            c_.clique.connect(self.filtrer)
            self.cartes[k] = c_
        racine.addLayout(grille_cartes(list(self.cartes.values()), 3))
        # جدول التتبع (للمراجعة السريعة وللوثائق): المجلس، العدد، الحد الأدنى، آخر اجتماع، التنبيهات
        self.suivi = tableau(["المجلس", "المنجزة", "المبرمجة", "آخر اجتماع", "تنبيهات"], etirer=4)
        self.suivi.setWordWrap(True)
        self.suivi.hide()

        # ---- الأزرار الرئيسية ----
        h = QHBoxLayout()
        h.setSpacing(12)
        self.b_programmer = bouton_couleur("برمجة اجتماع واستدعاء الأعضاء", "#1565C0", "rappel",
                                           "تحديد الموعد وجدول الأعمال ثم توليد الاستدعاء مع لائحة التوقيع بالتوصل")
        self.b_programmer.clicked.connect(lambda: self.ouvrir_programmation())
        self.b_nouveau_pv = bouton_couleur("تحرير محضر اجتماع", "#2E7D32", "document",
                                           "تسجيل اجتماع منعقد: الحضور والمداولات والقرارات، ثم توليد المحضر")
        self.b_nouveau_pv.clicked.connect(lambda: self.ouvrir_pv())
        self.b_compo = bouton_couleur("تركيبة المجالس", "#6A1B9A", "personnes",
                                      "الأعضاء حسب المرسوم، مقترحة من معطيات البرنامج")
        self.b_compo.clicked.connect(lambda: self.ouvrir_composition())
        for b in (self.b_programmer, self.b_nouveau_pv, self.b_compo):
            h.addWidget(b)
        h.addStretch()
        racine.addLayout(h)
        self.alertes = AlerteTriangle("تنبيهات")
        racine.addWidget(self.alertes)

        # ---- لائحة المجالس: المبرمجة والمنجزة، وأمام كل مجلس أزراره (طلب المدير 2026-11-19) ----
        c, v = carte()
        tete = QHBoxLayout()
        self.titre_liste = QLabel()
        self.titre_liste.setObjectName("titreCarte")
        tete.addWidget(self.titre_liste, 1)
        self.f_etat = QComboBox()
        for k, lib in (("tous", "المبرمجة والمنجزة"), ("prevu", "المبرمجة فقط"), ("fait", "المنجزة فقط")):
            self.f_etat.addItem(lib, k)
        self.f_etat.currentIndexChanged.connect(lambda _: self._remplir_liste())
        tete.addWidget(self.f_etat)
        v.addLayout(tete)
        self.liste = tableau(["المجلس", "رقم", "التاريخ", "الساعة", "الحالة", "جدول الأعمال", "الإجراءات"],
                             etirer=5)
        self.liste.setMinimumHeight(300)
        self.liste.verticalHeader().setDefaultSectionSize(46)
        self.liste.itemSelectionChanged.connect(self._sel)
        self.liste.itemDoubleClicked.connect(lambda _: self._ouvrir_ligne())
        v.addWidget(self.liste)
        self.vide_liste = QLabel("لا اجتماع مسجلاً بعد. «برمجة اجتماع واستدعاء الأعضاء» يضيف موعداً ويولد "
                                 "استدعاءه، و«تحرير محضر اجتماع» يسجل اجتماعاً منعقداً.")
        self.vide_liste.setObjectName("etiquette")
        self.vide_liste.setAlignment(Qt.AlignCenter)
        self.vide_liste.setWordWrap(True)
        v.addWidget(self.vide_liste)
        self.barre_sel = QFrame()
        self.barre_sel.setObjectName("barreSelection")
        self.barre_sel.setStyleSheet("QFrame#barreSelection { background: #F3F7F6; border: 1px solid #CFE3DE; "
                                     "border-radius: 12px; }")
        bs = QHBoxLayout(self.barre_sel)
        bs.setContentsMargins(12, 8, 12, 8)
        self.l_sel = QLabel()
        self.l_sel.setStyleSheet("font-weight: 700; background: transparent;")
        bs.addWidget(self.l_sel, 1)
        self.p_pv = bouton_couleur("المحضر", "#2E7D32", "document")
        self.p_pv.clicked.connect(lambda: self.pv())
        self.p_convoc = bouton_couleur("الاستدعاء", "#1565C0", "rappel")
        self.p_convoc.clicked.connect(lambda: self.convocation())
        self.p_ouvrir = QPushButton("فتح الاجتماع وتعديله")
        self.p_ouvrir.clicked.connect(lambda: self.ouvrir_pv(self.sid))
        self.p_suppr = QPushButton("حذف الاجتماع")
        self.p_suppr.setObjectName("danger")
        from idara.ui import icones
        self.p_suppr.setIcon(icones.corbeille())
        self.p_suppr.clicked.connect(lambda: self.supprimer())
        for b in (self.p_pv, self.p_convoc, self.p_ouvrir, self.p_suppr):
            bs.addWidget(b)
        v.addWidget(self.barre_sel)
        self.barre_sel.hide()
        racine.addWidget(c)

        # ---- أرشيف الوثائق والمبيان ----
        c, v = carte("أرشيف الوثائق: المحاضر والاستدعاءات المولدة هذه السنة")
        self.t_docs = tableau(["الوثيقة", "المجلس", "تاريخ التوليد"], etirer=0)
        self.t_docs.setMinimumHeight(160)
        self.t_docs.itemDoubleClicked.connect(lambda it: self._ouvrir(Path(self.t_docs.item(it.row(), 0)
                                                                           .data(Qt.UserRole))))
        v.addWidget(self.t_docs)
        self.vide_docs = QLabel("لم تُولد وثائق بعد.")
        self.vide_docs.setObjectName("etiquette")
        self.vide_docs.setAlignment(Qt.AlignCenter)
        v.addWidget(self.vide_docs)
        racine.addWidget(c)
        self.c_graph, self.v_graph = carte("الاجتماعات المنجزة والمبرمجة لكل مجلس")
        self._graphes: list[QWidget] = []
        racine.addWidget(self.c_graph)
        racine.addStretch()

        self._construire_seance()
        self._construire_composition()
        self._changer_conseil()
        self.rafraichir()

    # ======================================================================
    # النوافذ المنبثقة
    # ======================================================================

    def _construire_seance(self) -> None:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(4, 4, 4, 4)
        v.setSpacing(12)
        self.conseil = QComboBox()   # الحالة المشتركة (الأزرار الملونة واجهتها)
        for k, lib in ce.CONSEILS.items():
            self.conseil.addItem(lib, k)
        self.conseil.currentIndexChanged.connect(lambda _: self._changer_conseil())
        self.conseil.hide()
        c, cv = carte("المجلس والموعد")
        zone, self.r_conseils = _choix_conseil(self, lambda k: self.conseil.setCurrentIndex(self.conseil.findData(k)))
        cv.addWidget(zone)
        self.date, self.heure = ChampDate(), champ("10:00", ltr=True)
        self.heure.setMaximumWidth(110)
        self.nature, self.convoc = QComboBox(), QComboBox()
        self.nature.addItem("اجتماع عادي", "ordinaire")
        self.nature.addItem("اجتماع استثنائي", "extraordinaire")
        self.convoc.addItem("الاستدعاء الأول", "premiere")
        self.convoc.addItem("الاستدعاء الثاني (النصاب بالحاضرين)", "seconde")
        cv.addLayout(_grille([("التاريخ *", self.date), ("الساعة *", self.heure), ("نوع الاجتماع", self.nature),
                              ("الاستدعاء", self.convoc)]))
        v.addWidget(c)
        c, cv = carte("جدول الأعمال")
        self.suggestion = QComboBox()
        b = QPushButton("إضافة إلى جدول الأعمال")
        b.clicked.connect(lambda: self._ajouter_point())
        h = QHBoxLayout()
        h.addWidget(self.suggestion, 1)
        h.addWidget(b)
        cv.addWidget(etiquette("نقط مقترحة (مهام المجلس في المرسوم ومحاضركم)", self.suggestion))
        cv.addLayout(h)
        self.odj = QPlainTextEdit()
        self.odj.setPlaceholderText("جدول الأعمال: نقطة في كل سطر")
        self.odj.setFixedHeight(110)
        cv.addWidget(self.odj)
        v.addWidget(c)
        self.c_deroulement, cv = carte("سير الاجتماع (للمحضر)")
        self.delib = QPlainTextEdit()
        self.delib.setPlaceholderText("المداولات (اختياري: تُترك أسطر فارغة في المحضر للكتابة باليد)")
        self.delib.setFixedHeight(120)
        cv.addWidget(self.delib)
        self.decisions = QPlainTextEdit()
        self.decisions.setPlaceholderText("القرارات والتوصيات: واحدة في كل سطر (اختياري)")
        self.decisions.setFixedHeight(90)
        cv.addWidget(self.decisions)
        t = QLabel("الحضور (أزل العلامة عن المتغيبين)")
        t.setObjectName("titreCarte")
        cv.addWidget(t)
        self.presence = QListWidget()
        self.presence.setMinimumHeight(190)
        cv.addWidget(self.presence)
        h = QHBoxLayout()
        self.c_res = QCheckBox("إدراج جدول نتائج المتعلمين (المحصلة النهائية)")
        self.c_isa = QCheckBox("إدراج تطور مؤشر ISA2")
        h.addWidget(self.c_res)
        h.addWidget(self.c_isa)
        h.addStretch()
        cv.addLayout(h)
        v.addWidget(self.c_deroulement)
        self.message_seance = QLabel()
        self.message_seance.setWordWrap(True)
        self.message_seance.hide()
        v.addWidget(self.message_seance)
        h = QHBoxLayout()
        self.b_save_seance = QPushButton("حفظ الاجتماع")
        self.b_save_seance.setObjectName("principal")
        self.b_save_seance.clicked.connect(lambda: self.enregistrer(self.sid is None))
        h.addWidget(self.b_save_seance)
        self.b_gen_convoc = bouton_couleur("حفظ وتوليد الاستدعاء", "#1565C0", "rappel")
        self.b_gen_convoc.clicked.connect(lambda: self.programmer_et_convoquer())
        self.b_gen_pv = bouton_couleur("حفظ وتوليد المحضر", "#2E7D32", "document")
        self.b_gen_pv.clicked.connect(lambda: self.enregistrer_et_pv())
        h.addWidget(self.b_gen_convoc)
        h.addWidget(self.b_gen_pv)
        h.addStretch()
        v.addLayout(h)
        v.addStretch()
        self.fiche_seance = FenetreFiche(self, "اجتماع", "", w, 900)

    def _construire_composition(self) -> None:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(4, 4, 4, 4)
        v.setSpacing(12)
        c, cv = carte("المجلس")
        zone, self.r_conseils_c = _choix_conseil(self, lambda k: self.conseil.setCurrentIndex(
            self.conseil.findData(k)))
        cv.addWidget(zone)
        v.addWidget(c)
        c, cv = carte("الأعضاء")
        self.l_ecarts = QLabel()
        self.l_ecarts.setObjectName("erreur")
        self.l_ecarts.setWordWrap(True)
        cv.addWidget(self.l_ecarts)
        self.c_optionnels = QCheckBox("إضافة الأعضاء الاختياريين: ممثل الأطر الإدارية والتقنية، رئيس جمعية آباء "
                                      "وأولياء التلاميذ، ممثل المجلس الجماعي")
        self.c_optionnels.toggled.connect(lambda c: self._basculer_optionnels(c))
        cv.addWidget(self.c_optionnels)
        self.membres = QTableWidget(0, 3)
        self.membres.setHorizontalHeaderLabels(["الاسم", "الصفة", "المادة"])
        self.membres.verticalHeader().setVisible(False)
        self.membres.setEditTriggers(QAbstractItemView.AllEditTriggers)
        self.membres.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.membres.setMinimumHeight(360)
        cv.addWidget(self.membres)
        h = QHBoxLayout()
        b = bouton("تركيبة مقترحة (المرسوم ومعطيات التطبيق)")
        b.clicked.connect(lambda: self.proposer())
        h.addWidget(b)
        b = bouton("سطر إضافي")
        b.clicked.connect(lambda: self.membres.setRowCount(self.membres.rowCount() + 1))
        h.addWidget(b)
        h.addStretch()
        b = QPushButton("حفظ التركيبة")
        b.setObjectName("principal")
        b.clicked.connect(lambda: self.enregistrer_membres())
        h.addWidget(b)
        cv.addLayout(h)
        self.message_compo = QLabel()
        self.message_compo.setWordWrap(True)
        self.message_compo.hide()
        cv.addWidget(self.message_compo)
        v.addWidget(c)
        v.addStretch()
        self.fiche_compo = FenetreFiche(self, "تركيبة المجالس", "حسب المرسوم 2.02.376؛ تُقترح من معطيات البرنامج "
                                                               "وتُكمل يدوياً.", w, 860)

    def _msg(self, texte: str, erreur: bool = False) -> None:
        message(self.message, texte, erreur)
        for m in (self.message_seance, self.message_compo):
            message(m, texte, erreur)

    def ouvrir_programmation(self, conseil: str | None = None, sid: int | None = None) -> FenetreFiche:
        """نافذة الاستدعاء: موعد الاجتماع وجدول أعماله، ثم توليد الاستدعاء."""
        self._preparer(conseil, sid, prochain=True)
        self.c_deroulement.hide()
        self.b_gen_pv.hide()
        self.b_gen_convoc.show()
        self.fiche_seance.definir_titre("برمجة اجتماع واستدعاء الأعضاء",
                                        "الموعد وجدول الأعمال، ثم الاستدعاء مع لائحة التوقيع بالتوصل.")
        self.fiche_seance.ouvrir()
        return self.fiche_seance

    def ouvrir_pv(self, sid: int | None = None, conseil: str | None = None) -> FenetreFiche:
        """نافذة المحضر: الاجتماع المنعقد بحضوره ومداولاته وقراراته، ثم توليد المحضر."""
        self._preparer(conseil, sid, prochain=False)
        self.c_deroulement.show()
        self.b_gen_pv.show()
        self.b_gen_convoc.show()
        self.fiche_seance.definir_titre("محضر اجتماع " + self.conseil.currentText() +
                                        (" (تعديل)" if self.sid else ""),
                                        "الحضور والمداولات والقرارات، ثم توليد المحضر بتوقيعات الأعضاء.")
        self.fiche_seance.ouvrir()
        return self.fiche_seance

    def ouvrir_composition(self, conseil: str | None = None) -> FenetreFiche:
        if conseil:
            self.conseil.setCurrentIndex(self.conseil.findData(conseil))
        self.fiche_compo.ouvrir()
        return self.fiche_compo

    def _preparer(self, conseil: str | None, sid: int | None, prochain: bool) -> None:
        s = ce.seance(self.f.conn, sid) if sid else None
        cible = s.conseil if s else (conseil or self.filtre or self.conseil.currentData())
        self.conseil.blockSignals(True)
        self.conseil.setCurrentIndex(self.conseil.findData(cible))
        self.conseil.blockSignals(False)
        self._changer_conseil(charger_formulaire=False)
        self.sid = sid
        self._formulaire(s)
        if s is None and prochain:
            self.date.definir((date.today() + timedelta(days=7)).isoformat())
        self.message_seance.hide()

    def _changer_conseil(self, charger_formulaire: bool = True) -> None:
        k = self.conseil.currentData()
        for boutons in (self.r_conseils, self.r_conseils_c):
            boutons[k].blockSignals(True)
            boutons[k].setChecked(True)
            boutons[k].blockSignals(False)
        self.charger_composition()
        self.suggestion.clear()
        self.suggestion.addItems(ce.SUGGESTIONS[k])
        if charger_formulaire:
            self.sid = None
            self._formulaire(None)

    # ======================================================================
    # العرض
    # ======================================================================

    def rafraichir(self) -> None:
        try:
            s = ce.suivi(self.f.conn)
            tout = ce.seances(self.f.conn)
        except ce.ErreurConseil as e:
            message(self.message, str(e), True)
            return
        self.suivi.setRowCount(len(s))
        for i, x in enumerate(s):
            for j, v in enumerate((x["libelle"], str(x["nombre"]), str(x["programmes"]),
                                   tx.date_chiffres(x["derniere"]) if x["derniere"] else "—",
                                   "؛ ".join(x["alertes"]) or "—")):
                self.suivi.setItem(i, j, cellule(v))
            c_ = self.cartes[x["conseil"]]
            c_.definir(x["nombre"])   # المنجزة؛ العدد متروك للمدير، بلا حد أدنى (طلبه 2026-11-19)
            dern = f"آخر اجتماع: {tx.date_chiffres(x['derniere'])}" if x["derniere"] else "لا اجتماع منعقد بعد"
            prevus = f" · مبرمج: {x['programmes']}" if x["programmes"] else ""
            c_.note.setText(dern + prevus)
            c_.definir_alerte("\n".join(x["alertes"]))
        self.alertes.setText("")
        for k, c_ in self.cartes.items():
            c_.definir_actif(k == self.filtre)
        self.tout = tout
        self._remplir_liste()
        self._documents()
        self._graphique(s)
        self.charger_composition()

    def filtrer(self, conseil: str | None) -> None:
        self.filtre = None if conseil == self.filtre else conseil
        self.rafraichir()

    def _cellule_conseil(self, k: str, sid: int):
        it = cellule(ce.CONSEILS[k], sid)
        coul = QColor(COULEURS[k])
        it.setForeground(coul)
        fond = QColor(coul)
        fond.setAlpha(28)
        it.setBackground(fond)
        it.setIcon(pictos.icone(PICTOS[k], coul.name(), 16))
        f_ = it.font()
        f_.setBold(True)
        it.setFont(f_)
        return it

    @staticmethod
    def _prevu(r) -> bool:
        return r["date_seance"] > date.today().isoformat()

    def _remplir_liste(self) -> None:
        etat = self.f_etat.currentData()
        lignes = [r for r in getattr(self, "tout", []) if (self.filtre is None or r["conseil"] == self.filtre)
                  and (etat == "tous" or (etat == "prevu") == self._prevu(r))]
        prevus = [r for r in lignes if self._prevu(r)]
        faits = sorted((r for r in lignes if not self._prevu(r)), key=lambda r: r["date_seance"], reverse=True)
        self.lignes = prevus + faits
        titre = ce.CONSEILS[self.filtre] if self.filtre else "كل المجالس"
        self.titre_liste.setText(f"لائحة المجالس: {titre} · مبرمجة {len(prevus)} · منجزة {len(faits)}")
        self.liste.blockSignals(True)
        self.liste.clearSelection()
        self.liste.setRowCount(len(self.lignes))
        for i, r in enumerate(self.lignes):
            self.liste.setItem(i, 0, self._cellule_conseil(r["conseil"], r["id"]))
            prevu = self._prevu(r)
            if prevu:
                n = (date.fromisoformat(r["date_seance"]) - date.today()).days
                etat_t, coul = ("غداً" if n == 1 else f"مبرمج · بعد {n} يوماً"), ("#C62828" if n <= 2 else "#1565C0")
            else:
                etat_t, coul = "منجز", "#2E7D32"
            for j, v in enumerate((str(r["numero"]), tx.date_chiffres(r["date_seance"]), r["heure"] or "—", etat_t,
                                   "؛ ".join(json.loads(r["ordre_du_jour"]))), start=1):
                c_ = cellule(v)
                if j == 4:
                    c_.setForeground(QColor(coul))
                    f_ = c_.font()
                    f_.setBold(True)
                    c_.setFont(f_)
                    c_.setIcon(pictos.icone("calendrier" if prevu else "valider", coul, 16))
                self.liste.setItem(i, j, c_)
            self.liste.setCellWidget(i, 6, self._actions(r["id"], prevu))
        self.liste.resizeColumnToContents(6)
        self.liste.blockSignals(False)
        self.liste.setVisible(bool(self.lignes))
        self.vide_liste.setVisible(not self.lignes)
        self.sid = None
        self.barre_sel.hide()

    def _actions(self, sid: int, prevu: bool) -> QWidget:
        """أزرار أمام كل مجلس: المبرمج ← الاستدعاء وتحرير المحضر؛ المنجز ← توليد المحضر والاطلاع عليه."""
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(4, 2, 4, 2)
        h.setSpacing(6)

        def b(texte, couleur, picto, fn, aide=""):
            x = QPushButton(texte)
            x.setObjectName("boutonCouleur")
            x.setIcon(pictos.icone(picto, "#FFFFFF", 15))
            x.setToolTip(aide)
            x.setStyleSheet(f"QPushButton {{ background: {couleur}; color: white; border: none; border-radius: 9px; "
                            f"padding: 4px 10px; font-weight: 700; }} QPushButton:hover {{ background: {couleur}DD; }}"
                            f" QPushButton:disabled {{ background: #B0BEC5; }}")
            x.clicked.connect(fn)
            h.addWidget(x)
            return x
        b("الاستدعاء", "#1565C0", "rappel", lambda: self.convocation_ligne(sid), "توليد استدعاء الأعضاء لهذا الاجتماع")
        if prevu:
            b("تعديل الموعد", "#00838F", "modifier", lambda: self.ouvrir_programmation(sid=sid))
        else:
            b("توليد المحضر", "#2E7D32", "document", lambda: self.pv_ligne(sid), "توليد المحضر من المعطيات المسجلة")
            voir = b("الاطلاع على المحضر", "#6A1B9A", "apercu", lambda: self.voir_pv(sid),
                     "فتح آخر محضر مولد لهذا الاجتماع")
            voir.setEnabled(ce.pv_existant(self.f.conn, self.f.dossier, sid) is not None)
        return w

    def _maj_actions(self) -> None:
        """يعيد بناء أزرار الأسطر (تفعيل «الاطلاع على المحضر» بعد توليده) دون فقد التحديد."""
        for i, r in enumerate(getattr(self, "lignes", [])):
            self.liste.setCellWidget(i, 6, self._actions(r["id"], self._prevu(r)))

    def _ouvrir_ligne(self) -> None:
        r = next((x for x in self.lignes if x["id"] == self.sid), None)
        if r is not None:
            if self._prevu(r):
                self.ouvrir_programmation(sid=self.sid)
            else:
                self.ouvrir_pv(self.sid)

    def _documents(self) -> None:
        from idara.services import annee as annee_srv
        a = annee_srv.annee_courante(self.f.conn)
        rep = self.f.dossier.archives / a["libelle"].replace("/", "-") / "مجالس المؤسسة" if a else None
        fichiers = sorted(rep.glob("*.docx"), reverse=True) if rep and rep.exists() else []
        self.t_docs.setRowCount(len(fichiers))
        for i, p in enumerate(fichiers):
            nom = p.stem.split("_", 2)[-1]
            k = next((k for k, lib in ce.CONSEILS.items() if lib in nom), None)
            it = cellule(nom, str(p))
            it.setIcon(pictos.icone("document" if nom.startswith("محضر") else "rappel",
                                    COULEURS.get(k, "#455A64"), 16))
            self.t_docs.setItem(i, 0, it)
            self.t_docs.setItem(i, 1, cellule(ce.CONSEILS.get(k, "—") if k else "—"))
            d = p.stem[:8]
            self.t_docs.setItem(i, 2, cellule(f"{d[6:8]}/{d[4:6]}/{d[:4]}" if d.isdigit() else "—"))
        self.t_docs.setVisible(bool(fichiers))
        self.vide_docs.setVisible(not fichiers)

    def _graphique(self, s) -> None:
        for w in self._graphes:
            w.hide()
            w.setParent(None)
            w.deleteLater()
        g = BarresGroupees([x["libelle"] for x in s],
                           [("المنجزة", [float(x["nombre"]) for x in s], "#2E7D32"),
                            ("المبرمجة", [float(x["programmes"]) for x in s], "#1565C0")],
                           maximum=None, suffixe="")
        self.v_graph.addWidget(g)
        self._graphes = [g]

    def charger_composition(self) -> None:
        cs = self.conseil.currentData()
        ms = ce.membres_actifs(self.f.conn, cs)
        self._remplir_membres([(m["nom"], m["qualite"], m["groupe"] or "") for m in ms])
        opt = ce.optionnels(cs)
        self.c_optionnels.setVisible(bool(opt))
        self.c_optionnels.blockSignals(True)
        self.c_optionnels.setChecked(any(m["qualite"] in opt for m in ms))
        self.c_optionnels.blockSignals(False)
        ec = ce.ecarts_decret(self.f.conn, cs) if ms else []
        self.l_ecarts.setText("مقاعد ينص عليها المرسوم وغير مسجلة: " + "، ".join(ec) if ec else "")
        self.l_ecarts.setVisible(bool(ec))
        self.fiche_compo.definir_titre("تركيبة " + self.conseil.currentText())

    # الاسم القديم
    def charger(self) -> None:
        self._changer_conseil()

    def _remplir_membres(self, lignes) -> None:
        self.membres.setColumnHidden(2, self.conseil.currentData() != "enseignement")
        self.membres.setRowCount(max(len(lignes) + 1, 4))
        self.membres.clearContents()
        for i, l in enumerate(lignes):
            for j, v in enumerate(l):
                self.membres.setItem(i, j, cellule(v))

    def _formulaire(self, s: ce.Seance | None) -> None:
        self.date.definir(s.date_seance if s else date.today().isoformat())
        self.heure.setText(s.heure if s and s.heure else "10:00")
        self.nature.setCurrentIndex(max(0, self.nature.findData(s.nature if s else "ordinaire")))
        self.convoc.setCurrentIndex(max(0, self.convoc.findData(s.convocation if s else "premiere")))
        self.odj.setPlainText("\n".join(s.ordre_du_jour) if s else "")
        self.delib.setPlainText(s.deliberations if s else "")
        self.decisions.setPlainText("\n".join(s.decisions) if s else "")
        self.c_res.setChecked(bool(s and s.inclure_resultats))
        self.c_isa.setChecked(bool(s and s.inclure_isa))
        self.presence.clear()
        presents = set(s.presents) if s and s.presents is not None else None
        for m in ce.membres_actifs(self.f.conn, self.conseil.currentData()):
            it = QListWidgetItem(f"{m['nom']} — {m['qualite']}" + (f" ({m['groupe']})" if m["groupe"] else ""))
            it.setData(Qt.UserRole, m["id"])
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if presents is None or m["id"] in presents else Qt.Unchecked)
            self.presence.addItem(it)

    def _sel(self) -> None:
        rows = {i.row() for i in self.liste.selectedIndexes()}
        self.barre_sel.setVisible(len(rows) == 1)
        if len(rows) == 1:
            r = rows.pop()
            self.sid = self.liste.item(r, 0).data(Qt.UserRole)
            s = ce.seance(self.f.conn, self.sid)
            self.conseil.blockSignals(True)
            self.conseil.setCurrentIndex(self.conseil.findData(s.conseil))
            self.conseil.blockSignals(False)
            self._changer_conseil(charger_formulaire=False)
            self._formulaire(s)
            self.l_sel.setText(f"{ce.CONSEILS[s.conseil]} · الاجتماع رقم {self.liste.item(r, 1).text()} · "
                               f"{self.liste.item(r, 2).text()}")

    # ======================================================================
    # الأفعال
    # ======================================================================

    def _faire(self, fn, succes: str, recharger=True):
        try:
            r = fn()
        except (ce.ErreurConseil, ValueError) as e:
            self._msg(str(e) or "قيمة غير صحيحة.", True)
            return None
        if recharger:
            sid = self.sid
            self.rafraichir()
            self.sid = sid
        if succes:
            self._msg(succes)
        return True if r is None else r

    def _lignes(self) -> list[tuple[str, str, str]]:
        return [tuple((self.membres.item(i, j).text() if self.membres.item(i, j) else "") for j in range(3))
                for i in range(self.membres.rowCount())]

    def _basculer_optionnels(self, coche: bool) -> None:
        """يضيف أسطر الأعضاء الاختياريين إلى التركيبة المعروضة أو يحذفها (ثم «حفظ التركيبة»)."""
        opt = ce.optionnels(self.conseil.currentData())
        lignes = [l for l in self._lignes() if any(l) and l[1] not in opt]
        if coche:
            lignes += [("", q, "") for q in opt]
        self._remplir_membres(lignes)

    def proposer(self) -> None:
        self._remplir_membres(ce.proposition(self.f.conn, self.conseil.currentData(),
                                             self.c_optionnels.isChecked()))
        self._msg("تركيبة مقترحة: أكمل الأسماء الناقصة ثم احفظ.")

    def enregistrer_membres(self):
        lignes = self._lignes()
        r = self._faire(lambda: ce.enregistrer_membres(self.f.conn, self.conseil.currentData(), lignes),
                        "حُفظت التركيبة.")
        if r:
            self._formulaire(ce.seance(self.f.conn, self.sid) if self.sid else None)
        return r

    def _ajouter_point(self) -> None:
        t = self.odj.toPlainText().rstrip()
        self.odj.setPlainText((t + "\n" if t else "") + self.suggestion.currentText())

    def _seance(self, nouveau: bool) -> ce.Seance:
        try:
            d = self.date.iso()
        except ValueError:
            raise ce.ErreurConseil("تاريخ الاجتماع غير صحيح.") from None
        presents = [self.presence.item(i).data(Qt.UserRole) for i in range(self.presence.count())
                    if self.presence.item(i).checkState() == Qt.Checked]
        return ce.Seance(self.conseil.currentData(), d, _texte(self.odj), self.heure.text(), self.nature.currentData(),
                         self.convoc.currentData(), self.delib.toPlainText(), _texte(self.decisions), presents,
                         self.c_res.isChecked(), self.c_isa.isChecked(), None if nouveau else self.sid)

    def enregistrer(self, nouveau: bool):
        if not nouveau and not self.sid:
            self._msg("حدد اجتماعاً في الجدول.", True)
            return None
        sid = self._faire(lambda: ce.enregistrer_seance(self.f.conn, self._seance(nouveau)), "سُجل الاجتماع.")
        if sid and nouveau and isinstance(sid, int) and not isinstance(sid, bool):
            self.sid = sid
        return sid

    def programmer_et_convoquer(self):
        """يحفظ الاجتماع المبرمج ثم يولد استدعاء أعضائه."""
        if not self.enregistrer(self.sid is None):
            return None
        return self.convocation()

    def enregistrer_et_pv(self):
        if not self.enregistrer(self.sid is None):
            return None
        return self.pv()

    def supprimer(self):
        if not self.sid:
            return None
        sid = self.sid
        self.sid = None
        return self._faire(lambda: ce.supprimer_seance(self.f.conn, sid), "حُذف الاجتماع.")

    def _ouvrir(self, p: Path) -> Path:
        self._msg(f"وُلّدت الوثيقة: ⁦{p.name}⁩")
        self._documents()
        try:
            bureautique.ouvrir(p)
        except Exception:  # noqa: BLE001 — الفتح اختياري
            pass
        return p

    def pv(self):
        if not self.sid:
            self._msg("حدد اجتماعاً مسجلاً في الجدول.", True)
            return None
        r = self._faire(lambda: ce.generer_pv(self.f.conn, self.f.dossier, self.sid), "", recharger=False)
        if r:
            self._maj_actions()
        return self._ouvrir(r) if r else None

    def convocation_ligne(self, sid: int):
        r = self._faire(lambda: ce.convocation_seance(self.f.conn, self.f.dossier, sid), "", recharger=False)
        return self._ouvrir(r) if r else None

    def pv_ligne(self, sid: int):
        r = self._faire(lambda: ce.generer_pv(self.f.conn, self.f.dossier, sid), "", recharger=False)
        if r:
            self._maj_actions()
        return self._ouvrir(r) if r else None

    def voir_pv(self, sid: int):
        p = ce.pv_existant(self.f.conn, self.f.dossier, sid)
        if p is None:
            self._msg("لم يُولد محضر هذا الاجتماع بعد: «توليد المحضر».", True)
            return None
        self.f.ouvrir_document(p)
        return p

    def convocation(self):
        def fn():
            try:
                d = self.date.iso()
            except ValueError:
                raise ce.ErreurConseil("تاريخ الاجتماع غير صحيح.") from None
            return ce.generer_convocation(self.f.conn, self.f.dossier, self.conseil.currentData(), d,
                                          self.heure.text(), _texte(self.odj))
        r = self._faire(fn, "", recharger=False)
        return self._ouvrir(r) if r else None
