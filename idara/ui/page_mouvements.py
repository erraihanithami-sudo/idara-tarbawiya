"""صفحة حركية التلاميذ (طلب المدير 2026-11-17: الصفحة تعرض الحركية أولاً بدل استمارة الإدخال).

- بطاقات الأرقام في الأعلى (الوافدون، المغادرون، المنقطعون، المفصولون، غير الملتحقين) وهي نفسها معايير الجدول:
  الضغط على بطاقة يعرض فئتها فقط.
- شريط المعايير: بحث، مستوى، فترة.
- الجدول الكامل للحركية، ومبيانات التوزيع حسب الفئة والمستوى والشهر.
- «إضافة حركية جديدة» تفتح نافذة الإدخال، و«وثيقة الحركية» تولد الحصيلة مباشرة.
- إجراءات الملف (طلب، تذكير، تأشير التوصل، إرسال، تأشير الإرسال) تظهر عند تحديد تلاميذ في الجدول.
"""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QRadioButton, QVBoxLayout, QWidget)

from idara.services import bureautique
from idara.services import documents as dc
from idara.services import eleves as el
from idara.services import mouvements as mv
from idara.services import textes as tx
from idara.ui import pictos
from idara.ui.composants import carte, entete
from idara.ui.formulaires import champ, etiquette
from idara.ui.graphiques import Anneau, BarresGroupees
from idara.ui.saisie import ChampDate, cellule, message, tableau

COULEURS = {"arrive": "#2E7D32", "parti": "#1565C0", "interrompu": "#EF6C00", "exclu": "#C62828",
            "non_rejoint": "#6A1B9A"}
PICTOS = {"arrive": "entree", "parti": "sortie", "interrompu": "pause", "exclu": "interdit", "non_rejoint": "absent"}
NOTES = {"arrive": "قدموا من مؤسسات أخرى", "parti": "انتقلوا إلى مؤسسات أخرى", "interrompu": "توقفوا عن الدراسة",
         "exclu": "بقرار من المجلس", "non_rejoint": "مسجلون في مسار ولم يلتحقوا"}


def _combo(valeurs=()) -> QComboBox:
    c = QComboBox()
    c.setEditable(True)
    c.setInsertPolicy(QComboBox.NoInsert)
    c.addItems(list(valeurs))
    c.setCurrentIndex(-1)
    return c


class CarteFiltre(QFrame):
    """بطاقة رقم تعمل معياراً: أيقونة في دائرة، العدد، الفئة، وسطر تعريفي. الضغط عليها يعرض فئتها."""

    clique = Signal(str)

    def __init__(self, cle: str, libelle: str, couleur: str, picto: str, note: str = ""):
        super().__init__()
        self.cle, self.couleur = cle, couleur
        self.setObjectName("carteFiltre")
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(96)
        h = QHBoxLayout(self)
        h.setContentsMargins(16, 12, 14, 12)
        h.setSpacing(12)
        ic = QLabel()
        ic.setPixmap(pictos.pastille(picto, couleur, 48))
        ic.setFixedSize(48, 48)
        ic.setStyleSheet("background: transparent;")
        h.addWidget(ic, 0, Qt.AlignVCenter)
        v = QVBoxLayout()
        v.setSpacing(0)
        self.chiffre = QLabel("0")
        self.chiffre.setStyleSheet(f"font-size: 22pt; font-weight: 700; color: {couleur}; background: transparent;")
        self.libelle = QLabel(libelle)
        self.libelle.setStyleSheet("font-weight: 700; background: transparent;")
        v.addWidget(self.chiffre)
        v.addWidget(self.libelle)
        if note:
            n = QLabel(note)
            n.setObjectName("etiquette")
            n.setStyleSheet("background: transparent;")
            n.setWordWrap(True)
            v.addWidget(n)
        h.addLayout(v, 1)
        self.definir_actif(False)

    def definir_actif(self, actif: bool) -> None:
        self.actif = actif
        c = QColor(self.couleur)
        teinte = f"rgba({c.red()}, {c.green()}, {c.blue()}, {28 if actif else 0})"
        bord = f"2px solid {self.couleur}" if actif else "1px solid #D8D4CC"
        self.setStyleSheet(f"QFrame#carteFiltre {{ background: qlineargradient(x1:1, y1:0, x2:0, y2:1, "
                           f"stop:0 {teinte}, stop:1 white); border: {bord}; border-radius: 16px; "
                           f"border-right: 6px solid {self.couleur}; }}")

    def mouseReleaseEvent(self, ev):   # noqa: N802
        if ev.button() == Qt.LeftButton:
            self.clique.emit(self.cle)
        super().mouseReleaseEvent(ev)


# ======================================================================
# نافذة إضافة حركية أو تعديلها
# ======================================================================

class DialogueMouvement(QDialog):
    def __init__(self, page, mid: int | None = None, categorie: str = "arrive"):
        super().__init__(page)
        self.page, self.f, self.mid = page, page.f, mid
        self.setWindowTitle("تعديل حركية" if mid else "إضافة حركية جديدة")
        self.setLayoutDirection(Qt.RightToLeft)
        self.setMinimumWidth(760)
        v = QVBoxLayout(self)
        v.setContentsMargins(22, 18, 22, 18)
        v.setSpacing(12)
        v.addWidget(entete(self.windowTitle(), "اختر نوع الحركية ثم أدخل معطياتها. رمز مسار يملأ معطيات التلميذ "
                                                "إن كان في اللوائح."))
        h = QHBoxLayout()
        self.types: dict[str, QRadioButton] = {}
        g = QButtonGroup(self)
        for k, lib in mv.CATEGORIES.items():
            r = QRadioButton(lib)
            r.setStyleSheet(f"QRadioButton {{ font-weight: 600; color: {COULEURS[k]}; }}")
            r.setIcon(pictos.icone(PICTOS[k], COULEURS[k], 20))
            g.addButton(r)
            r.toggled.connect(lambda on: on and self._maj_type())
            self.types[k] = r
            h.addWidget(r)
        h.addStretch()
        v.addLayout(h)
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.hide()
        v.addWidget(self.message)

        self.code = champ("مثال: B219054491", ltr=True)
        self.code.editingFinished.connect(self._chercher_code)
        self.nom, self.prenom = champ(), champ()
        self.s_m, self.s_f = QRadioButton("ذكر"), QRadioButton("أنثى")
        g3 = QButtonGroup(self)
        g3.addButton(self.s_m)
        g3.addButton(self.s_f)
        self.sexe = QWidget()
        sl = QHBoxLayout(self.sexe)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.addWidget(self.s_m)
        sl.addWidget(self.s_f)
        sl.addStretch()
        self.date_mv = ChampDate()
        self.niveau = _combo(v_[0] for v_ in tx.NIVEAUX.values())
        self.etab, self.direction, self.academie = _combo(), _combo(), _combo()
        for k, w in (("etablissement", self.etab), ("direction", self.direction), ("academie", self.academie)):
            w.addItems(mv.suggestions(self.f.conn, k))
            w.setCurrentIndex(-1)
        self.hors = QCheckBox("خارج الإقليم")
        self.hors.toggled.connect(lambda _: self._maj_hors())
        self.ref_num = champ(ltr=True)
        self.ref_date = ChampDate()
        self.remarques = champ("اختياري")
        self.classe = QComboBox()
        self.l_classe = etiquette("القسم (تلميذ غير وارد في اللائحة)", self.classe)
        self.l_etab = etiquette("المؤسسة الأصلية *", self.etab)
        self.l_ref = etiquette("رقم شهادة المغادرة", self.ref_num)
        self.l_date = etiquette("تاريخ التحويل *", self.date_mv)
        self.l_rem = etiquette("ملاحظات", self.remarques)
        g4 = QGridLayout()
        g4.setHorizontalSpacing(16)
        g4.setVerticalSpacing(4)
        self.lignes_transfert: list[QWidget] = []
        items = [(etiquette("رمز مسار *", self.code), self.code, False), (self.l_date, self.date_mv, False),
                 (etiquette("النسب", self.nom), self.nom, True), (etiquette("الاسم", self.prenom), self.prenom, True),
                 (etiquette("النوع"), self.sexe, True), (etiquette("المستوى", self.niveau), self.niveau, True),
                 (self.l_etab, self.etab, True), (QLabel(""), self.hors, True),
                 (etiquette("المديرية الإقليمية", self.direction), self.direction, True),
                 (etiquette("الأكاديمية الجهوية", self.academie), self.academie, True),
                 (self.l_ref, self.ref_num, True), (etiquette("بتاريخ", self.ref_date), self.ref_date, True),
                 (self.l_rem, self.remarques, False), (self.l_classe, self.classe, True)]
        for i, (lab, w, transfert) in enumerate(items):
            g4.addWidget(lab, (i // 2) * 2, i % 2)
            g4.addWidget(w, (i // 2) * 2 + 1, i % 2)
            if transfert:
                self.lignes_transfert += [lab, w]
        v.addLayout(g4)
        self.info_eleve = QLabel()
        self.info_eleve.setObjectName("etiquette")
        self.info_eleve.setWordWrap(True)
        v.addWidget(self.info_eleve)
        hb = QHBoxLayout()
        hb.addStretch()
        b = QPushButton("إلغاء")
        b.clicked.connect(self.reject)
        hb.addWidget(b)
        self.b_save = QPushButton("حفظ الحركية")
        self.b_save.setObjectName("principal")
        self.b_save.setDefault(True)
        self.b_save.clicked.connect(self.enregistrer)
        hb.addWidget(self.b_save)
        v.addLayout(hb)
        self._remplir_classes()
        self.types[categorie if categorie in self.types else "arrive"].setChecked(True)
        self._maj_type()
        self._maj_hors()
        if mid is not None:
            self._charger(mid)

    def categorie(self) -> str:
        return next(k for k, r in self.types.items() if r.isChecked())

    def _maj_type(self) -> None:
        cat = self.categorie()
        transfert = cat in ("arrive", "parti")
        for w in self.lignes_transfert:
            w.setVisible(transfert)
        self.l_etab.setText("المؤسسة الأصلية *" if cat == "arrive" else "المؤسسة المستقبلة *")
        self.l_ref.setText("رقم شهادة المغادرة" if cat == "arrive" else "رقم مراسلتهم (المرجع)")
        self.l_date.setText({"arrive": "تاريخ التحويل *", "parti": "تاريخ التحويل *", "interrompu": "تاريخ الانقطاع *",
                             "exclu": "تاريخ الفصل *", "non_rejoint": "تاريخ المعاينة *"}[cat])
        self.l_rem.setText("السبب ومرجع القرار *" if cat == "exclu" else
                           "السبب (اختياري)" if cat in ("interrompu", "non_rejoint") else "ملاحظات")
        if transfert:
            self.l_classe.setVisible(cat == "parti" or bool(self.page.unite()))
            self.classe.setVisible(self.l_classe.isVisible())

    def _maj_hors(self) -> None:
        for w in (self.direction, self.academie):
            w.setEnabled(self.hors.isChecked())

    def _remplir_classes(self) -> None:
        from idara.services import annee as annee_srv
        a = annee_srv.annee_courante(self.f.conn)
        self.classe.clear()
        self.classe.addItem("غير محدد", None)
        u = self.page.unite()
        for r in self.f.conn.execute(
                "SELECT c.id, c.code, u.nom_ar AS unite FROM classe c LEFT JOIN unite_scolaire u ON u.id=c.unite_id "
                "WHERE c.annee_id=? AND (? IS NULL OR u.nom_ar=?) ORDER BY c.code, u.id", (a["id"] if a else -1, u, u)):
            self.classe.addItem(r["code"] + (f" ({r['unite']})" if r["unite"] and not u else ""), r["id"])

    def _chercher_code(self) -> None:
        code = self.code.text().strip().upper()
        r = self.f.conn.execute("SELECT id FROM eleve WHERE code_massar=?", (code,)).fetchone()
        cat = self.categorie()
        if not r:
            if not code:
                self.info_eleve.setText("")
            elif cat == "arrive":
                self.info_eleve.setText("تلميذ غير موجود في اللوائح: يُنشأ وافداً جديداً (النسب والاسم والنوع إجبارية).")
            elif cat == "parti":
                self.info_eleve.setText("تلميذ غير وارد في اللائحة الحالية (غادر قبل استيرادها): يُدرج مغادراً. النسب "
                                        "والاسم والنوع والمستوى إجبارية، والقسم اختياري.")
            else:
                self.info_eleve.setText("تلميذ غير موجود في لوائح السنة الجارية.")
            return
        fi = el.fiche(self.f.conn, r["id"])
        self.nom.setText(fi["nom_ar"] or "")
        self.prenom.setText(fi["prenom_ar"] or "")
        (self.s_f if fi["sexe"] == "F" else self.s_m).setChecked(True)
        if fi["niveau"] in tx.NIVEAUX and not self.niveau.currentText():
            self.niveau.setEditText(tx.niveau_ar(fi["niveau"]))
        self.info_eleve.setText(f"في اللوائح: {fi['prenom_ar']} {fi['nom_ar']} · القسم {fi['classe'] or 'غير محدد'} · "
                                f"{el.STATUTS.get(fi['statut'], 'غير مسجل')}")

    def _charger(self, mid: int) -> None:
        r = mv.lire(self.f.conn, mid)
        self.types[r["sens"]].setChecked(True)
        for k, rb in self.types.items():
            rb.setEnabled(k == r["sens"])
        self.code.setText(r["code_massar"])
        self.code.setEnabled(False)
        self.nom.setText(r["nom_ar"])
        self.prenom.setText(r["prenom_ar"])
        (self.s_f if r["sexe"] == "F" else self.s_m).setChecked(True)
        self.date_mv.definir(r["date_mouvement"])
        self.etab.setEditText(r["etablissement"])
        self.hors.setChecked(bool(r["hors_province"]))
        self.direction.setEditText(r["direction"] or "")
        self.academie.setEditText(r["academie"] or "")
        self.niveau.setEditText(r["niveau"] or "")
        self.ref_num.setText(r["ref_numero"] or "")
        self.ref_date.definir(r["ref_date"] or None)
        self.remarques.setText(r["remarques"] or "")
        self.info_eleve.setText(f"{r['prenom_ar']} {r['nom_ar']} · {mv.SENS[r['sens']]} · {mv.etat(r)}")

    def enregistrer(self) -> int | None:
        try:
            d, rd = self.date_mv.iso(), self.ref_date.iso()
        except ValueError:
            message(self.message, "أحد التواريخ غير صحيح.", True)
            return None
        cat = self.categorie()
        try:
            if cat not in ("arrive", "parti"):
                res = mv.changer_statut_sortie(self.f.conn, self.code.text(), cat, d, self.remarques.text())
            else:
                code = self.code.text().strip().upper()
                if self.page.unite() and not self.classe.currentData() and not self.f.conn.execute(
                        "SELECT 1 FROM eleve WHERE code_massar=?", (code,)).fetchone():
                    message(self.message, f"تلميذ غير وارد في اللوائح: اختر قسمه من أقسام «{self.page.unite()}».",
                            True)
                    return None
                m = mv.Mouvement(cat, self.code.text(), self.nom.text(), self.prenom.text(),
                                 "F" if self.s_f.isChecked() else "M" if self.s_m.isChecked() else "", d,
                                 self.etab.currentText(), self.direction.currentText(), self.academie.currentText(),
                                 self.hors.isChecked(), self.niveau.currentText(), self.ref_num.text(), rd,
                                 self.remarques.text(), classe_id=self.classe.currentData(), id=self.mid)
                res = mv.enregistrer(self.f.conn, m)
        except mv.ErreurMouvement as e:
            message(self.message, str(e), True)
            return None
        self.resultat = res
        self.accept()
        self.page.apres_enregistrement(cat)
        return res


# ======================================================================
# الصفحة
# ======================================================================

class PageMouvements(QWidget):
    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        self.categorie: str | None = None
        self.lignes: list[dict] = []
        racine = QVBoxLayout(self)
        racine.setContentsMargins(40, 32, 40, 32)
        racine.setSpacing(16)
        racine.addWidget(entete("حركية التلاميذ", "الوافدون والمغادرون والمنقطعون والمفصولون وغير الملتحقين في جدول "
                                                  "واحد، بمعايير ومبيانات. كل مراسلة تُسجل في الصادر."))
        from idara.ui.unites import BarreUnites
        self.barre_unites = BarreUnites(lambda: self.f.conn, self._changer_unite)
        racine.addWidget(self.barre_unites)

        # ---- بطاقات الأرقام (معايير) ----
        g = QGridLayout()
        g.setSpacing(14)
        self.cartes: dict[str, CarteFiltre] = {}
        for i, (k, lib) in enumerate(mv.CATEGORIES_PLURIEL.items()):
            c = CarteFiltre(k, lib, COULEURS[k], PICTOS[k], NOTES[k])
            c.clique.connect(self.filtrer)
            self.cartes[k] = c
            g.addWidget(c, i // 3, i % 3)
        self.c_solde = CarteFiltre("", "الكل", "#455A64", "personnes", "")
        self.c_solde.clique.connect(lambda _: self.filtrer(None))
        g.addWidget(self.c_solde, 1, 2)
        racine.addLayout(g)

        # ---- الإجراءات العامة ----
        h = QHBoxLayout()
        self.b_ajouter = QPushButton("إضافة حركية جديدة")
        self.b_ajouter.setObjectName("principal")
        self.b_ajouter.clicked.connect(lambda: self.ajouter())
        h.addWidget(self.b_ajouter)
        self.b_bilan = QPushButton("توليد وثيقة الحركية")
        self.b_bilan.clicked.connect(lambda: self.generer_bilan())
        h.addWidget(self.b_bilan)
        self.listes = QCheckBox("مع لائحتي الوافدين والمغادرين")
        self.listes.setChecked(True)
        h.addWidget(self.listes)
        h.addStretch()
        self.b_stats = QPushButton("الإحصائيات التفصيلية")
        self.b_stats.clicked.connect(self.statistiques)
        h.addWidget(self.b_stats)
        racine.addLayout(h)
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.hide()
        racine.addWidget(self.message)
        self.alertes = QLabel()
        self.alertes.setObjectName("alerte")
        self.alertes.setWordWrap(True)
        self.alertes.setStyleSheet("QLabel#alerte { background: #FFF4E5; border: 1px solid #F0B46A; "
                                   "border-right: 5px solid #EF6C00; border-radius: 12px; padding: 10px 14px; }")
        racine.addWidget(self.alertes)

        # ---- الجدول والمعايير ----
        c, cv = carte()
        self.titre_table = QLabel()
        self.titre_table.setObjectName("titreCarte")
        cv.addWidget(self.titre_table)
        hf = QHBoxLayout()
        self.recherche = QLineEdit()
        self.recherche.setPlaceholderText("بحث: الاسم، رمز مسار، القسم أو المؤسسة")
        self.recherche.setClearButtonEnabled(True)
        self.recherche.textChanged.connect(lambda _: self.chercher())
        hf.addWidget(self.recherche, 2)
        self.niveau = QComboBox()
        self.niveau.addItem("كل المستويات", None)
        for v_ in tx.NIVEAUX.values():
            self.niveau.addItem(v_[0], v_[0])
        self.niveau.currentIndexChanged.connect(lambda _: self.chercher())
        hf.addWidget(self.niveau)
        self.debut, self.fin = ChampDate(), ChampDate()
        for lib, w in (("من", self.debut), ("إلى", self.fin)):
            hf.addWidget(QLabel(lib))
            w.setMaximumWidth(150)
            w.editingFinished.connect(self.rafraichir)
            hf.addWidget(w)
        b = QPushButton("تحديث")
        b.clicked.connect(self.rafraichir)
        hf.addWidget(b)
        cv.addLayout(hf)
        self.table = tableau(["الحركية", "التلميذ(ة)", "رمز مسار", "القسم", "المستوى", "النوع", "التاريخ",
                              "المؤسسة", "حالة الملف أو السبب"], etirer=1)
        self.liste = self.table   # الاسم القديم (الاختبارات والصفحات الأخرى)
        self.table.setSelectionMode(self.table.SelectionMode.ExtendedSelection)
        self.table.setMinimumHeight(380)
        self.table.itemSelectionChanged.connect(self._selection)
        self.table.itemDoubleClicked.connect(lambda it: self.modifier())
        cv.addWidget(self.table, 1)
        self.vide = QLabel("لا حركية مسجلة بهذه المعايير. أضف حركية جديدة من الزر أعلاه.")
        self.vide.setObjectName("etiquette")
        self.vide.setAlignment(Qt.AlignCenter)
        cv.addWidget(self.vide)
        # إجراءات الملف للتلاميذ المحددين
        self.barre_sel = QFrame()
        self.barre_sel.setObjectName("barreSelection")
        self.barre_sel.setStyleSheet("QFrame#barreSelection { background: #F3F7F6; border: 1px solid #CFE3DE; "
                                     "border-radius: 12px; }")
        bs = QHBoxLayout(self.barre_sel)
        bs.setContentsMargins(12, 8, 12, 8)
        self.l_sel = QLabel()
        self.l_sel.setStyleSheet("font-weight: 700; background: transparent;")
        bs.addWidget(self.l_sel)
        self.date_action = ChampDate()
        self.date_action.definir(date.today().isoformat())
        self.date_action.setMaximumWidth(150)
        self.date_action.setToolTip("تاريخ المراسلة أو التأشير")
        bs.addWidget(self.date_action)
        self.b_demande = QPushButton("طلب الملف")
        self.b_demande.clicked.connect(lambda: self.demande(False))
        self.b_rappel = QPushButton("تذكير")
        self.b_rappel.clicked.connect(lambda: self.demande(True))
        self.b_recu = QPushButton("تأشير التوصل بالملف")
        self.b_recu.clicked.connect(lambda: self.marquer("dossier_recu_le"))
        self.b_envoi = QPushButton("إرسال الملف")
        self.b_envoi.clicked.connect(self.envoi)
        self.b_envoye = QPushButton("تأشير إرسال الملف")
        self.b_envoye.clicked.connect(lambda: self.marquer("dossier_envoye_le"))
        self.b_annuler = QPushButton("إلغاء التأشير")
        self.b_annuler.clicked.connect(self.annuler)
        self.b_modifier = QPushButton("تعديل")
        self.b_modifier.clicked.connect(lambda: self.modifier())
        for b in (self.b_demande, self.b_rappel, self.b_recu, self.b_envoi, self.b_envoye, self.b_annuler,
                  self.b_modifier):
            bs.addWidget(b)
        bs.addStretch()
        cv.addWidget(self.barre_sel)
        racine.addWidget(c)

        # ---- المبيانات ----
        self.c_graph, self.v_graph = carte("المبيانات")
        racine.addWidget(self.c_graph)
        self._graphes: list[QWidget] = []
        racine.addStretch()
        self.rafraichir()

    # ---------- العرض ----------

    def unite(self) -> str | None:
        return self.barre_unites.unite if hasattr(self, "barre_unites") else None

    def _changer_unite(self, _u) -> None:
        self.rafraichir()

    def _periode(self) -> tuple[str | None, str | None] | None:
        try:
            return self.debut.iso() or None, self.fin.iso() or None
        except ValueError:
            message(self.message, "أحد تاريخي الفترة غير صحيح.", True)
            return None

    def rafraichir(self) -> None:
        self.barre_unites.actualiser()
        p = self._periode()
        if p is None:
            return
        try:
            a = mv.alertes(self.f.conn, unite=self.unite())
            self.tous = mv.registre(self.f.conn, None, "", self.unite(), *p)
        except mv.ErreurMouvement as e:
            message(self.message, str(e), True)
            self.tous = []
            a = {"envoi": [], "demande": [], "relance": []}
        noms = lambda ls: "، ".join(f"{r['prenom_ar']} {r['nom_ar']}" for r in ls)  # noqa: E731
        lignes = []
        if a["envoi"]:
            lignes.append(f"مغادرون لم يُرسل ملفهم ({len(a['envoi'])}): {noms(a['envoi'])}")
        if a["demande"]:
            lignes.append(f"وافدون لم يُطلب ملفهم ({len(a['demande'])}): {noms(a['demande'])}")
        if a["relance"]:
            lignes.append(f"طلبات دون توصل منذ أكثر من {mv.DELAI_RELANCE} يوماً ({len(a['relance'])}): "
                          f"{noms(a['relance'])}")
        self.alertes.setText("\n".join(lignes))
        self.alertes.setVisible(bool(lignes))
        n = mv.compter(self.tous)
        for k, c in self.cartes.items():
            c.chiffre.setText(str(n[k]))
        solde = n["arrive"] - n["parti"] - n["interrompu"] - n["exclu"] - n["non_rejoint"]
        self.c_solde.chiffre.setText(str(len(self.tous)))
        self.c_solde.libelle.setText("كل الحركات · الفرق " + (f"⁦{solde:+d}⁩" if solde else "0"))
        self._graphiques(n)
        self.chercher()

    def filtrer(self, categorie: str | None) -> None:
        self.categorie = None if categorie == self.categorie else categorie
        self.chercher()

    # الاسم القديم للتبويبات (الوافدون / المغادرون / المنقطعون والمفصولون)
    def sens(self) -> str:
        return self.categorie or "tous"

    def chercher(self) -> None:
        for k, c in self.cartes.items():
            c.definir_actif(k == self.categorie)
        self.c_solde.definir_actif(self.categorie is None)
        cible = self.recherche.text()
        niv = self.niveau.currentData()
        from idara.services.massar import normaliser
        t = normaliser(cible)
        self.lignes = [x for x in getattr(self, "tous", [])
                       if (self.categorie is None or x["categorie"] == self.categorie)
                       and (not niv or x["niveau"] == niv)
                       and (not t or any(t in normaliser(v) for v in (x["code_massar"], x["nom"], x["etablissement"],
                                                                      x["classe"])))]
        self.titre_table.setText((mv.CATEGORIES_PLURIEL[self.categorie] if self.categorie else "كل الحركات")
                                 + f" ({len(self.lignes)})")
        self.table.blockSignals(True)
        self.table.clearSelection()
        self.table.setRowCount(len(self.lignes))
        for i, x in enumerate(self.lignes):
            coul = QColor(COULEURS[x["categorie"]])
            it = cellule(mv.CATEGORIES[x["categorie"]], x["mouvement_id"])
            it.setForeground(coul)
            fond = QColor(coul)
            fond.setAlpha(30)
            it.setBackground(fond)
            f = it.font()
            f.setBold(True)
            it.setFont(f)
            it.setIcon(pictos.icone(PICTOS[x["categorie"]], coul.name(), 16))
            self.table.setItem(i, 0, it)
            for j, val in enumerate((x["nom"], f"⁦{x['code_massar']}⁩", x["classe"], x["niveau"],
                                     {"M": "ذكر", "F": "أنثى"}.get(x["sexe"], ""), tx.date_chiffres(x["date"]),
                                     x["etablissement"], x["etat"]), start=1):
                c = cellule(val, x["eleve_id"] if j == 1 else None)
                if j == 8 and x["a_traiter"]:
                    c.setForeground(QColor("#B23B00"))
                self.table.setItem(i, j, c)
        self.table.blockSignals(False)
        self.vide.setVisible(not self.lignes)
        self.table.setVisible(bool(self.lignes))
        self._selection()

    def _graphiques(self, n: dict[str, int]) -> None:
        for w in self._graphes:
            w.hide()
            w.setParent(None)
            w.deleteLater()
        self._graphes = []
        total = sum(n.values())
        self.c_graph.setVisible(bool(total))
        if not total:
            return
        ligne = QHBoxLayout()
        cont = QWidget()
        cont.setLayout(ligne)
        parts = [(mv.CATEGORIES_PLURIEL[k], n[k], round(100 * n[k] / total, 1)) for k in mv.CATEGORIES]
        an = Anneau(parts, [COULEURS[k] for k in mv.CATEGORIES], str(total), "حركة")
        an.setMinimumHeight(230)
        ligne.addWidget(an, 2)
        par_niv: dict[str, dict[str, int]] = {}
        for x in self.tous:
            par_niv.setdefault(x["niveau"] or mv.NON_DEFINI, {k: 0 for k in mv.CATEGORIES})[x["categorie"]] += 1
        ordre = [v_[0] for v_ in tx.NIVEAUX.values()]
        nivs = sorted(par_niv, key=lambda s: ordre.index(s) if s in ordre else 99)
        series = [("الوافدون", [float(par_niv[s]["arrive"]) for s in nivs], COULEURS["arrive"]),
                  ("المغادرون", [float(par_niv[s]["parti"]) for s in nivs], COULEURS["parti"]),
                  ("المنقطعون والمفصولون وغير الملتحقين",
                   [float(par_niv[s]["interrompu"] + par_niv[s]["exclu"] + par_niv[s]["non_rejoint"]) for s in nivs],
                   COULEURS["interrompu"])]
        self.g_niveaux = BarresGroupees(nivs, series, maximum=None, suffixe="")
        ligne.addWidget(self.g_niveaux, 3)
        self.v_graph.addWidget(cont)
        self._graphes.append(cont)
        mois: dict[str, dict[str, int]] = {}
        for x in self.tous:
            if x["date"]:
                mois.setdefault(x["date"][:7], {"entrees": 0, "sorties": 0})[
                    "entrees" if x["categorie"] == "arrive" else "sorties"] += 1
        if mois:
            cles = sorted(mois)
            self.g_mois = BarresGroupees(
                [mv.libelle_mois(m) for m in cles],
                [("الدخول (الوافدون)", [float(mois[m]["entrees"]) for m in cles], COULEURS["arrive"]),
                 ("الخروج (باقي الحركات)", [float(mois[m]["sorties"]) for m in cles], COULEURS["exclu"])],
                maximum=None, suffixe="")
            t = QLabel("الحركية حسب الشهر")
            t.setObjectName("titreCarte")
            self.v_graph.addWidget(t)
            self.v_graph.addWidget(self.g_mois)
            self._graphes += [t, self.g_mois]

    # ---------- التحديد والإجراءات ----------

    def _selection_lignes(self) -> list[dict]:
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        return [self.lignes[r] for r in rows if r < len(self.lignes)]

    def ids(self) -> list[int]:
        return [x["mouvement_id"] for x in self._selection_lignes() if x["mouvement_id"]]

    def _selection(self) -> None:
        sel = self._selection_lignes()
        cats = {x["categorie"] for x in sel}
        self.barre_sel.setVisible(bool(sel))
        self.l_sel.setText(f"المحدد: {len(sel)}")
        arrive, parti = cats == {"arrive"}, cats == {"parti"}
        for b in (self.b_demande, self.b_rappel, self.b_recu):
            b.setVisible(arrive)
        for b in (self.b_envoi, self.b_envoye):
            b.setVisible(parti)
        self.b_annuler.setVisible(arrive or parti)
        self.date_action.setVisible(arrive or parti)
        self.b_modifier.setVisible(len(sel) == 1 and bool(sel[0]["mouvement_id"]))

    def ajouter(self, categorie: str | None = None, ouvrir: bool = True) -> DialogueMouvement:
        d = DialogueMouvement(self, None, categorie or self.categorie or "arrive")
        self.dialogue = d
        if ouvrir:
            d.open()
        return d

    def modifier(self, ouvrir: bool = True) -> DialogueMouvement | None:
        sel = self._selection_lignes()
        if len(sel) != 1 or not sel[0]["mouvement_id"]:
            return None
        d = DialogueMouvement(self, sel[0]["mouvement_id"])
        self.dialogue = d
        if ouvrir:
            d.open()
        return d

    def apres_enregistrement(self, categorie: str) -> None:
        self.categorie = categorie
        self.rafraichir()
        message(self.message, "حُفظت الحركية، وحُدّثت وضعية التلميذ.")

    def _date(self) -> str | None:
        try:
            return self.date_action.iso() or date.today().isoformat()
        except ValueError:
            message(self.message, "تاريخ المراسلة غير صحيح.", True)
            return None

    def _apres(self, doc) -> None:
        self.rafraichir()
        message(self.message, f"وُلّدت المراسلة وسُجلت في الصادر: ⁦{doc.chemin.name}⁩")
        try:
            bureautique.ouvrir(doc.chemin)
        except OSError as e:
            message(self.message, f"وُلّدت المراسلة لكن تعذر فتحها: {e}", True)

    def demande(self, rappel: bool):
        le = self._date()
        if le is None:
            return None
        try:
            doc = mv.generer_demande(self.f.conn, self.f.dossier, self.ids(), le, rappel)
        except (mv.ErreurMouvement, dc.ErreurDocument) as e:
            message(self.message, str(e), True)
            return None
        self._apres(doc)
        return doc

    def envoi(self):
        le = self._date()
        if le is None:
            return None
        try:
            doc = mv.generer_envoi(self.f.conn, self.f.dossier, self.ids(), le)
        except (mv.ErreurMouvement, dc.ErreurDocument) as e:
            message(self.message, str(e), True)
            return None
        self._apres(doc)
        return doc

    def marquer(self, champ_: str, annuler: bool = False) -> bool:
        le = None if annuler else self._date()
        if not annuler and le is None:
            return False
        ids = self.ids()
        if not ids:
            message(self.message, "حدد تلميذاً واحداً على الأقل.", True)
            return False
        try:
            for i in ids:
                mv.marquer(self.f.conn, i, champ_, le)
        except mv.ErreurMouvement as e:
            message(self.message, str(e), True)
            return False
        self.rafraichir()
        message(self.message, "أُلغي التأشير." if annuler else "سُجل التأشير.")
        return True

    def annuler(self) -> bool:
        cats = {x["categorie"] for x in self._selection_lignes()}
        return self.marquer("dossier_recu_le" if cats == {"arrive"} else "dossier_envoye_le", annuler=True)

    def generer_bilan(self):
        """وثيقة الحركية مباشرة من الصفحة: للوحدة المختارة وللفترة المختارة."""
        p = self._periode()
        if p is None:
            return None
        from idara.ui.stats_mouvements import png_graphique
        try:
            s = mv.statistiques(self.f.conn, self.unite(), *p)
            chemin = mv.generer_bilan(self.f.conn, self.f.dossier, self.unite(), *p, listes=self.listes.isChecked(),
                                      graphique_png=png_graphique(s))
        except (mv.ErreurMouvement, OSError) as e:
            message(self.message, str(e), True)
            return None
        message(self.message, f"وُلّدت وثيقة الحركية: ⁦{chemin.name}⁩")
        try:
            bureautique.ouvrir(chemin)
        except OSError as e:
            message(self.message, f"وُلّدت الوثيقة لكن تعذر فتحها: {e}", True)
        return chemin

    def statistiques(self):
        from idara.ui.stats_mouvements import DialogueStatistiques
        d = DialogueStatistiques(self)
        d.open()
        return d
