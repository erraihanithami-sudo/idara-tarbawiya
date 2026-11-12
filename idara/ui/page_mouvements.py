"""صفحة حركية التلاميذ: الوافدون (طلب الملف، التذكير، التوصل) والمغادرون (إرسال الملف)."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QGridLayout, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QRadioButton, QVBoxLayout, QWidget)

from idara.services import bureautique
from idara.services import documents as dc
from idara.services import eleves as el
from idara.services import mouvements as mv
from idara.services import textes as tx
from idara.ui.composants import carte, entete
from idara.ui.formulaires import champ, etiquette
from idara.ui.saisie import ChampDate, cellule, message, tableau


def _combo(valeurs=()) -> QComboBox:
    c = QComboBox()
    c.setEditable(True)
    c.setInsertPolicy(QComboBox.NoInsert)
    c.addItems(list(valeurs))
    c.setCurrentIndex(-1)
    return c


class PageMouvements(QWidget):
    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        self.mid: int | None = None
        racine = QVBoxLayout(self)
        racine.setContentsMargins(40, 32, 40, 32)
        racine.setSpacing(16)
        racine.addWidget(entete("حركية التلاميذ", "الوافدون وطلب ملفاتهم، والمغادرون وإرسال ملفاتهم. "
                                                  "كل مراسلة تُسجل في الصادر وتُولد من نماذجكم."))
        # المجموعة المدرسية: زر لكل وحدة يعرض كل مكونات الصفحة لتلاميذها (طلب المدير 2026-11-09)
        from idara.ui.unites import BarreUnites
        self.barre_unites = BarreUnites(lambda: self.f.conn, self._changer_unite)
        racine.addWidget(self.barre_unites)
        self.alertes = QLabel()
        self.alertes.setObjectName("alerte")
        self.alertes.setWordWrap(True)
        racine.addWidget(self.alertes)
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.hide()
        racine.addWidget(self.message)
        corps = QHBoxLayout()
        corps.setSpacing(20)
        racine.addLayout(corps, 1)

        # ---- اللائحة ----
        c, cv = carte()
        h = QHBoxLayout()
        self.r_arrive, self.r_parti = QRadioButton("الوافدون"), QRadioButton("المغادرون")
        self.r_autres = QRadioButton("المنقطعون والمفصولون")
        self.r_arrive.setChecked(True)
        g = QButtonGroup(self)
        for r in (self.r_arrive, self.r_parti, self.r_autres):
            g.addButton(r)
            r.toggled.connect(lambda on: on and self.chercher())
            h.addWidget(r)
        h.addStretch()
        self.b_stats = QPushButton("الإحصائيات ووثيقة الحركية")
        self.b_stats.setObjectName("principal")
        self.b_stats.clicked.connect(self.statistiques)
        h.addWidget(self.b_stats)
        cv.addLayout(h)
        self.recherche = QLineEdit()
        self.recherche.setPlaceholderText("الاسم، رمز مسار أو المؤسسة")
        self.recherche.setClearButtonEnabled(True)
        self.recherche.textChanged.connect(lambda _: self.chercher())
        cv.addWidget(self.recherche)
        self.liste = tableau(["التلميذ", "حالة الملف"], etirer=0)
        hh = self.liste.horizontalHeader()
        hh.setSectionResizeMode(1, hh.ResizeMode.Fixed)
        hh.resizeSection(1, 140)
        self.liste.setSelectionMode(self.liste.SelectionMode.ExtendedSelection)
        self.liste.itemSelectionChanged.connect(self._selection)
        self.liste.setMinimumHeight(360)
        cv.addWidget(self.liste, 1)
        aide = QLabel("لمراسلة واحدة لعدة تلاميذ من نفس المؤسسة (إخوة مثلاً): حددهم بالضغط على Ctrl.")
        aide.setObjectName("etiquette")
        aide.setWordWrap(True)
        cv.addWidget(aide)
        ga = QGridLayout()
        self.date_action = ChampDate()
        self.date_action.definir(date.today().isoformat())
        ga.addWidget(etiquette("تاريخ المراسلة أو التأشير", self.date_action), 0, 0, 1, 2)
        ga.addWidget(self.date_action, 1, 0, 1, 2)
        self.b_demande = QPushButton("طلب الملف")
        self.b_demande.setObjectName("principal")
        self.b_demande.clicked.connect(lambda: self.demande(False))
        self.b_rappel = QPushButton("تذكير (الطلب الثاني)")
        self.b_rappel.clicked.connect(lambda: self.demande(True))
        self.b_recu = QPushButton("تأشير: توصلنا بالملف")
        self.b_recu.clicked.connect(lambda: self.marquer("dossier_recu_le"))
        self.b_envoi = QPushButton("إرسال الملف (مراسلة)")
        self.b_envoi.setObjectName("principal")
        self.b_envoi.clicked.connect(self.envoi)
        self.b_envoye = QPushButton("تأشير: أُرسل الملف")
        self.b_envoye.clicked.connect(lambda: self.marquer("dossier_envoye_le"))
        self.b_annuler = QPushButton("إلغاء التأشير")
        self.b_annuler.clicked.connect(self.annuler)
        for i, b in enumerate((self.b_demande, self.b_rappel, self.b_recu, self.b_envoi, self.b_envoye, self.b_annuler)):
            ga.addWidget(b, 2 + i // 2, i % 2)
        cv.addLayout(ga)
        corps.addWidget(c, 6)

        # ---- التسجيل ----
        c2, fv = carte()
        self.titre = QLabel("حركة جديدة")
        self.titre.setObjectName("titreCarte")
        fv.addWidget(self.titre)
        h2 = QHBoxLayout()
        self.f_arrive, self.f_parti = QRadioButton("وافد"), QRadioButton("مغادر")
        self.f_arrive.setChecked(True)
        g2 = QButtonGroup(self)
        g2.addButton(self.f_arrive)
        g2.addButton(self.f_parti)
        self.f_arrive.toggled.connect(lambda _: self._maj_sens())
        h2.addWidget(self.f_arrive)
        h2.addWidget(self.f_parti)
        h2.addStretch()
        fv.addLayout(h2)
        self.code = champ("مثال: B219054491", ltr=True)
        self.code.editingFinished.connect(self._chercher_code)
        self.nom, self.prenom = champ(), champ()
        self.s_m, self.s_f = QRadioButton("ذكر"), QRadioButton("أنثى")
        g3 = QButtonGroup(self)
        g3.addButton(self.s_m)
        g3.addButton(self.s_f)
        sexe = QWidget()
        sl = QHBoxLayout(sexe)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.addWidget(self.s_m)
        sl.addWidget(self.s_f)
        sl.addStretch()
        self.date_mv = ChampDate()
        self.niveau = _combo(v[0] for v in tx.NIVEAUX.values())
        self.etab, self.direction, self.academie = _combo(), _combo(), _combo()
        self.hors = QCheckBox("خارج الإقليم")
        self.hors.toggled.connect(lambda _: self._maj_hors())
        self.ref_num = champ(ltr=True)
        self.ref_date = ChampDate()
        self.remarques = champ("اختياري")
        self.classe = QComboBox()   # مغادر سابق غير وارد في اللائحة: قسمه (اختياري)
        self.l_classe = etiquette("القسم (تلميذ غير وارد في اللائحة)", self.classe)
        self.l_etab = etiquette("المؤسسة الأصلية *", self.etab)
        self.l_ref = etiquette("رقم شهادة المغادرة", self.ref_num)
        g4 = QGridLayout()
        g4.setHorizontalSpacing(16)
        g4.setVerticalSpacing(4)
        items = [(etiquette("رمز مسار *", self.code), self.code), (etiquette("تاريخ التحويل *", self.date_mv), self.date_mv),
                 (etiquette("النسب", self.nom), self.nom), (etiquette("الاسم", self.prenom), self.prenom),
                 (etiquette("النوع"), sexe), (etiquette("المستوى", self.niveau), self.niveau),
                 (self.l_etab, self.etab), (QLabel(""), self.hors),
                 (etiquette("المديرية الإقليمية", self.direction), self.direction),
                 (etiquette("الأكاديمية الجهوية", self.academie), self.academie),
                 (self.l_ref, self.ref_num), (etiquette("بتاريخ", self.ref_date), self.ref_date),
                 (etiquette("ملاحظات", self.remarques), self.remarques), (self.l_classe, self.classe)]
        for i, (lab, w) in enumerate(items):
            g4.addWidget(lab, (i // 2) * 2, i % 2)
            g4.addWidget(w, (i // 2) * 2 + 1, i % 2)
        fv.addLayout(g4)
        self.info_eleve = QLabel()
        self.info_eleve.setObjectName("etiquette")
        self.info_eleve.setWordWrap(True)
        fv.addWidget(self.info_eleve)
        hb = QHBoxLayout()
        b = QPushButton("حفظ الحركة")
        b.setObjectName("principal")
        b.clicked.connect(self.enregistrer)
        b2 = QPushButton("حركة جديدة")
        b2.clicked.connect(self.nouveau)
        hb.addWidget(b)
        hb.addWidget(b2)
        hb.addStretch()
        fv.addLayout(hb)
        fv.addStretch()
        corps.addWidget(c2, 5)
        self.rafraichir()
        self.nouveau()

    # ---------- اللائحة ----------

    def sens(self) -> str:
        return "arrive" if self.r_arrive.isChecked() else "parti" if self.r_parti.isChecked() else "autres"

    def rafraichir(self) -> None:
        self.barre_unites.actualiser()
        try:
            a = mv.alertes(self.f.conn, unite=self.unite())
        except mv.ErreurMouvement as e:
            message(self.message, str(e), True)
            return
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
        for k, w in (("etablissement", self.etab), ("direction", self.direction), ("academie", self.academie)):
            t = w.currentText()
            w.clear()
            w.addItems(mv.suggestions(self.f.conn, k))
            w.setEditText(t)
        self.chercher()

    def chercher(self) -> None:
        if self.sens() == "autres":
            lignes = mv.sorties_sans_transfert(self.f.conn, self.recherche.text(), self.unite())
            self.liste.setRowCount(len(lignes))
            for i, r in enumerate(lignes):
                it = cellule(f"{r['prenom_ar']} {r['nom_ar']} · {r['motif_sortie'] or '—'}", None)
                it.setToolTip(r["code_massar"])
                self.liste.setItem(i, 0, it)
                self.liste.setItem(i, 1, cellule(f"{el.STATUTS[r['statut']]} {tx.date_chiffres(r['date_sortie'])}"))
            for b in (self.b_demande, self.b_rappel, self.b_recu, self.b_envoi, self.b_envoye, self.b_annuler):
                b.setVisible(False)
            return
        self.b_annuler.setVisible(True)
        try:
            lignes = mv.lister(self.f.conn, self.sens(), self.recherche.text(), self.unite())
        except mv.ErreurMouvement:
            lignes = []
        self.liste.setRowCount(len(lignes))
        for i, r in enumerate(lignes):
            it = cellule(f"{r['prenom_ar']} {r['nom_ar']} · {r['etablissement']}", r["id"])
            it.setToolTip(f"{r['code_massar']} · {tx.date_chiffres(r['date_mouvement'])}")
            self.liste.setItem(i, 0, it)
            self.liste.setItem(i, 1, cellule(mv.etat(r)))
        arrive = self.sens() == "arrive"
        for b in (self.b_demande, self.b_rappel, self.b_recu):
            b.setVisible(arrive)
        for b in (self.b_envoi, self.b_envoye):
            b.setVisible(not arrive)

    def ids(self) -> list[int]:
        lignes = sorted({i.row() for i in self.liste.selectedIndexes()})
        return [self.liste.item(r, 0).data(Qt.UserRole) for r in lignes]

    def _selection(self) -> None:
        if self.sens() == "autres":
            return
        ids = self.ids()
        if len(ids) == 1:
            self.afficher(ids[0])

    # ---------- الاستمارة ----------

    def _maj_sens(self) -> None:
        arrive = self.f_arrive.isChecked()
        self._remplir_classes()
        self.l_etab.setText("المؤسسة الأصلية *" if arrive else "المؤسسة المستقبلة *")
        self.l_ref.setText("رقم شهادة المغادرة" if arrive else "رقم مراسلتهم (المرجع)")

    def _maj_hors(self) -> None:
        for w in (self.direction, self.academie):
            w.setEnabled(self.hors.isChecked())

    def _chercher_code(self) -> None:
        code = self.code.text().strip().upper()
        r = self.f.conn.execute("SELECT id FROM eleve WHERE code_massar=?", (code,)).fetchone()
        if not r:
            if not code:
                self.info_eleve.setText("")
            elif self.f_arrive.isChecked():
                self.info_eleve.setText("تلميذ غير موجود في اللوائح: يُنشأ وافداً جديداً (النسب والاسم والنوع إجبارية).")
            else:
                self.info_eleve.setText("تلميذ غير وارد في اللائحة الحالية (غادر قبل استيرادها): يُدرج مغادراً. النسب "
                                        "والاسم والنوع والمستوى إجبارية، والقسم اختياري.")
            return
        f = el.fiche(self.f.conn, r["id"])
        self.nom.setText(f["nom_ar"] or "")
        self.prenom.setText(f["prenom_ar"] or "")
        (self.s_f if f["sexe"] == "F" else self.s_m).setChecked(True)
        if f["niveau"] in tx.NIVEAUX and not self.niveau.currentText():
            self.niveau.setEditText(tx.niveau_ar(f["niveau"]))
        self.info_eleve.setText(f"في اللوائح: {f['prenom_ar']} {f['nom_ar']} · القسم {f['classe'] or '—'} · "
                                f"{el.STATUTS.get(f['statut'], 'غير مسجل')}")

    def nouveau(self) -> None:
        self.mid = None
        self.liste.clearSelection()
        self.titre.setText("حركة جديدة")
        (self.f_parti if self.sens() == "parti" else self.f_arrive).setChecked(True)
        for w in (self.code, self.nom, self.prenom, self.ref_num, self.remarques, self.date_mv, self.ref_date):
            w.clear()
        for w in (self.etab, self.direction, self.academie, self.niveau):
            w.setEditText("")
        self.hors.setChecked(False)
        self._maj_hors()
        self._maj_sens()
        self.info_eleve.setText("")
        for r in (self.s_m, self.s_f):
            r.setAutoExclusive(False)
            r.setChecked(False)
            r.setAutoExclusive(True)
        self.code.setEnabled(True)

    def afficher(self, mid: int) -> None:
        r = mv.lire(self.f.conn, mid)
        self.mid = mid
        (self.f_arrive if r["sens"] == "arrive" else self.f_parti).setChecked(True)
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
        self.titre.setText(f"{r['prenom_ar']} {r['nom_ar']} · {mv.SENS[r['sens']]} · {mv.etat(r)}")
        self.info_eleve.setText("")

    def enregistrer(self) -> int | None:
        try:
            d, rd = self.date_mv.iso(), self.ref_date.iso()
        except ValueError:
            message(self.message, "أحد التواريخ غير صحيح.", True)
            return None
        code = self.code.text().strip().upper()
        if self.unite() and not self.classe.currentData() and not self.f.conn.execute(
                "SELECT 1 FROM eleve WHERE code_massar=?", (code,)).fetchone():
            message(self.message, f"تلميذ غير وارد في اللوائح: اختر قسمه من أقسام «{self.unite()}».", True)
            return None
        m = mv.Mouvement("arrive" if self.f_arrive.isChecked() else "parti", self.code.text(), self.nom.text(),
                         self.prenom.text(), "F" if self.s_f.isChecked() else "M" if self.s_m.isChecked() else "",
                         d, self.etab.currentText(), self.direction.currentText(), self.academie.currentText(),
                         self.hors.isChecked(), self.niveau.currentText(), self.ref_num.text(), rd,
                         self.remarques.text(), classe_id=self.classe.currentData(), id=self.mid)
        try:
            mid = mv.enregistrer(self.f.conn, m)
        except mv.ErreurMouvement as e:
            message(self.message, str(e), True)
            return None
        (self.r_arrive if m.sens == "arrive" else self.r_parti).setChecked(True)
        self.rafraichir()
        self.afficher(mid)
        message(self.message, "حُفظت الحركة، وحُدّثت وضعية التلميذ.")
        return mid

    # ---------- الإجراءات ----------

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
        return self.marquer("dossier_recu_le" if self.sens() == "arrive" else "dossier_envoye_le", annuler=True)

    def statistiques(self):
        """عدد الوافدين والمغادرين وتوليد وثيقة الحركية (طلب المدير 2026-11-12)، للوحدة المختارة أو للمؤسسة."""
        from idara.ui.stats_mouvements import DialogueStatistiques
        d = DialogueStatistiques(self)
        d.open()
        return d

    def _remplir_classes(self) -> None:
        from idara.services import annee as annee_srv
        a = annee_srv.annee_courante(self.f.conn)
        actuel = self.classe.currentData()
        self.classe.clear()
        self.classe.addItem("غير محدد", None)
        u = self.unite()
        for r in self.f.conn.execute(
                "SELECT c.id, c.code, u.nom_ar AS unite FROM classe c LEFT JOIN unite_scolaire u ON u.id=c.unite_id "
                "WHERE c.annee_id=? AND (? IS NULL OR u.nom_ar=?) ORDER BY c.code, u.id", (a["id"] if a else -1, u, u)):
            self.classe.addItem(r["code"] + (f" ({r['unite']})" if r["unite"] and not u else ""), r["id"])
        self.classe.setCurrentIndex(max(0, self.classe.findData(actuel)))

    def unite(self) -> str | None:
        return self.barre_unites.unite if hasattr(self, "barre_unites") else None

    def _changer_unite(self, _u) -> None:
        self._remplir_classes()
        self.rafraichir()
