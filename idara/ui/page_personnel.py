"""صفحة الموظفين: لائحة، بحث، ملف كامل يُدخل مرة واحدة لوثائق الرخص ومحضر التسليم."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
                               QFormLayout,
                               QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QPlainTextEdit, QPushButton, QRadioButton, QVBoxLayout, QWidget)

from idara.services import etablissement as et
from idara.services import import_rh as irh
from idara.services import personnel as rh
from idara.ui.composants import carte, entete
from idara.ui.formulaires import champ, etiquette
from idara.ui.saisie import ChampDate, cellule, message, selectionner, tableau


def _combo_libre(valeurs: list[str]) -> QComboBox:
    c = QComboBox()
    c.setEditable(True)
    c.addItems(valeurs)
    c.setCurrentIndex(-1)
    c.setInsertPolicy(QComboBox.NoInsert)
    return c


class DialogueDepart(QDialog):
    def __init__(self, nom: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("مغادرة الموظف")
        self.setLayoutDirection(Qt.RightToLeft)
        v = QVBoxLayout(self)
        v.addWidget(QLabel(f"{nom}: الملف يبقى محفوظاً، ويُرفع من لائحة العاملين."))
        f = QFormLayout()
        self.statut = QComboBox()
        for k in ("mute", "retraite", "autre"):
            self.statut.addItem(rh.STATUTS[k], k)
        self.le = ChampDate()
        self.le.definir(date.today().isoformat())
        self.remarque = champ("مثال: انتقال إلى مدرسة ...")
        f.addRow("الوضعية", self.statut)
        f.addRow("تاريخ المغادرة", self.le)
        f.addRow("ملاحظة (اختيارية)", self.remarque)
        v.addLayout(f)
        b = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        b.button(QDialogButtonBox.Ok).setText("تسجيل المغادرة")
        b.button(QDialogButtonBox.Cancel).setText("إلغاء")
        b.accepted.connect(self.accept)
        b.rejected.connect(self.reject)
        v.addWidget(b)


class PagePersonnel(QWidget):
    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        self.pid: int | None = None
        self.categorie_dir = False
        racine = QVBoxLayout(self)
        racine.setContentsMargins(40, 32, 40, 32)
        racine.setSpacing(16)
        racine.addWidget(entete("الموارد البشرية",
                                "ملف كل موظف يُدخل مرة واحدة، ومنه تُملأ وثائق الرخص ومحضر الاستئناف ومحضر التسليم."))
        self.effectifs = QLabel()
        self.effectifs.setObjectName("etiquette")
        racine.addWidget(self.effectifs)
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.hide()
        racine.addWidget(self.message)
        corps = QHBoxLayout()
        corps.setSpacing(20)
        racine.addLayout(corps, 1)

        # ---- اللائحة ----
        c, cv = carte()
        self.recherche = QLineEdit()
        self.recherche.setPlaceholderText("الاسم، رقم التأجير أو البطاقة الوطنية")
        self.recherche.setClearButtonEnabled(True)
        self.recherche.textChanged.connect(self.chercher)
        cv.addWidget(etiquette("بحث", self.recherche))
        cv.addWidget(self.recherche)
        filtres = QHBoxLayout()
        self.filtre_cat = QComboBox()
        self.filtre_cat.addItem("كل الفئات", None)
        for k, (_, _, pl) in rh.CATEGORIES.items():
            self.filtre_cat.addItem(pl, k)
        self.filtre_cat.currentIndexChanged.connect(lambda _: self.chercher())
        self.voir_partis = QCheckBox("إظهار المغادرين")
        self.voir_partis.toggled.connect(lambda _: self.chercher())
        filtres.addWidget(self.filtre_cat)
        filtres.addWidget(self.voir_partis)
        filtres.addStretch()
        cv.addLayout(filtres)
        self.liste = tableau(["الاسم", "المهمة"], etirer=0)   # قرار المدير 2026-11-03: المهمة بدل الفئة، دون عمود الملف
        h = self.liste.horizontalHeader()
        for i, largeur in ((1, 110),):
            h.setSectionResizeMode(i, h.ResizeMode.Fixed)
            h.resizeSection(i, largeur)
        self.liste.setMinimumHeight(420)
        self.liste.itemSelectionChanged.connect(self._selection)
        cv.addWidget(self.liste, 1)
        h_ajout = QHBoxLayout()
        b = QPushButton("+ موظف جديد")
        b.clicked.connect(self.nouveau)
        h_ajout.addWidget(b)
        # خيار ثانٍ: الاستيراد من ملف XML للموارد البشرية (طلب المدير 2026-11-03)
        b_xml = QPushButton("استيراد من ملف XML")
        b_xml.setToolTip("ملف تصدير الموارد البشرية (DsAgentExport). تُراجَع النتيجة قبل الاعتماد.")
        b_xml.clicked.connect(self.choisir_xml)
        h_ajout.addWidget(b_xml)
        cv.addLayout(h_ajout)
        corps.addWidget(c, 5)

        # ---- الملف ----
        c2, fv = carte()
        self.titre = QLabel("موظف جديد")
        self.titre.setObjectName("titreCarte")
        fv.addWidget(self.titre)
        note = QLabel("الحقول المعلَّمة بـ * إجبارية للحفظ. الباقي يُطلب عند توليد وثيقة تحتاجه.")
        note.setObjectName("etiquette")
        note.setWordWrap(True)
        fv.addWidget(note)

        self.c = {}
        for k, aide, ltr in (("nom_ar", "", False), ("prenom_ar", "", False), ("nom_fr", "", True),
                             ("prenom_fr", "", True), ("ppr", "أرقام فقط", True), ("cin", "AB123456", True),
                             ("adresse", "", False), ("telephone", "06XXXXXXXX", True),
                             ("niveau_enseigne", "إن لم يُسند قسم", False),
                             ("nb_eleves", "إن لم يُسند قسم", True), ("heures_hebdo", "", True)):
            self.c[k] = champ(aide, ltr)
        for k in rh.CHAMPS_SUGGERES:
            self.c[k] = _combo_libre([])
        self.matiere = QComboBox()
        self.matiere.addItem("— اختر —", "")
        for m in rh.MATIERES:
            self.matiere.addItem(m, m)
        self.r_m, self.r_f = QRadioButton("ذكر"), QRadioButton("أنثى")
        grp = QButtonGroup(self)
        grp.addButton(self.r_m)
        grp.addButton(self.r_f)
        sexe = QWidget()
        sl = QHBoxLayout(sexe)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.addWidget(self.r_m)
        sl.addWidget(self.r_f)
        sl.addStretch()
        self.categorie = QComboBox()
        self.unite = QComboBox()
        self.date_aff = ChampDate()

        self.etiquettes = {}

        def section(titre: str, champs: list[tuple[str, QWidget]], cible=None) -> None:
            cible = cible or fv
            t = QLabel(titre)
            t.setObjectName("titreCarte")
            cible.addWidget(t)
            g = QGridLayout()
            g.setHorizontalSpacing(16)
            g.setVerticalSpacing(4)
            for i, (lib, w) in enumerate(champs):
                e = etiquette(lib, w)
                self.etiquettes[lib] = e
                g.addWidget(e, (i // 2) * 2, i % 2)
                g.addWidget(w, (i // 2) * 2 + 1, i % 2)
            cible.addLayout(g)

        def liste_fixe(valeurs) -> QComboBox:
            c = QComboBox()
            c.addItem("— اختر —", "")
            for v in valeurs:
                c.addItem(v, v)
            return c
        self.cadre, self.grade = liste_fixe(rh.CADRES), liste_fixe(rh.GRADES)
        self.fonction = liste_fixe(rh.FONCTIONS)   # قرار المدير 2026-11-03: التدريس أو الإدارة

        section("الهوية", [("النسب *", self.c["nom_ar"]), ("الاسم *", self.c["prenom_ar"]),
                           ("Nom", self.c["nom_fr"]), ("Prénom", self.c["prenom_fr"]),
                           ("النوع *", sexe), ("الفئة *", self.categorie)])
        section("الوضعية الإدارية", [("رقم التأجير", self.c["ppr"]), ("رقم البطاقة الوطنية", self.c["cin"]),
                                     ("الإطار", self.cadre), ("الدرجة", self.grade),
                                     ("المهمة", self.fonction), ("السلك", self.c["cycle"]),
                                     ("الوحدة المدرسية", self.unite)])
        # ---- التنظيم التربوي (نموذج المدير 2026-11-03) ----
        self.d_tanzim = {k: ChampDate() for k, _ in rh.DATES_TANZIM}
        self.echelon = liste_fixe(rh.ECHELONS)
        self.note_insp = champ("مثال: 16.5", ltr=True)
        self.inspecteur = champ("اسم المفتش(ة)")
        self.sans_insp = QCheckBox("لم يخضع(تخضع) للتفتيش بعد")
        self.sans_insp.toggled.connect(lambda c: [w.setEnabled(not c) for w in
                                                  (self.note_insp, self.d_tanzim["date_inspection"], self.inspecteur)])
        self.repos_matin, self.repos_soir = liste_fixe(rh.JOURS), liste_fixe(rh.JOURS)
        self.situation = QComboBox()
        for k, lib in rh.SITUATIONS.items():
            self.situation.addItem(lib, k)
        self.etab_charge = champ()
        self.situation.currentIndexChanged.connect(lambda _: self._maj_situation())
        self.bloc_tanzim = QWidget()
        bt = QVBoxLayout(self.bloc_tanzim)
        bt.setContentsMargins(0, 0, 0, 0)
        fv.addWidget(self.bloc_tanzim)
        section("التنظيم التربوي (مطلوب للأساتذة)", [
            ("تاريخ الدرجة", self.d_tanzim["date_grade"]), ("الرتبة", self.echelon),
            ("تاريخ الرتبة", self.d_tanzim["date_echelon"]), ("تاريخ المهمة الحالية", self.d_tanzim["date_fonction"]),
            ("آخر نقطة تفتيش", self.note_insp), ("تاريخ آخر تفتيش", self.d_tanzim["date_inspection"]),
            ("المفتش(ة) الذي منحها", self.inspecteur), ("", self.sans_insp)], bt)
        self.bloc_charge = QWidget()
        bch = QVBoxLayout(self.bloc_charge)
        bch.setContentsMargins(0, 0, 0, 0)
        g_ch = QGridLayout()
        g_ch.setHorizontalSpacing(16)
        self.l_etab_charge = etiquette("المؤسسة", self.etab_charge)
        for i, (lab, w) in enumerate(((etiquette("التكليف", self.situation), self.situation),
                                      (self.l_etab_charge, self.etab_charge),
                                      (etiquette("تاريخ التكليف", self.d_tanzim["date_charge"]),
                                       self.d_tanzim["date_charge"]))):
            g_ch.addWidget(lab, (i // 2) * 2, i % 2)
            g_ch.addWidget(w, (i // 2) * 2 + 1, i % 2)
        bch.addLayout(g_ch)
        bt.addWidget(self.bloc_charge)
        self.bloc_repos = QWidget()
        br = QVBoxLayout(self.bloc_repos)
        br.setContentsMargins(0, 0, 0, 0)
        section("أنصاف أيام العطلة الأسبوعية", [("صباحاً", self.repos_matin), ("مساءً", self.repos_soir)], br)
        bt.addWidget(self.bloc_repos)
        self.dates = {k: (self.date_aff if k == "date_affectation" else ChampDate()) for k, _ in rh.DATES_CARRIERE}
        # قرار المدير: المسار المهني (الفائض) لا يظهر لفئة المدير
        self.bloc_carriere = QWidget()
        bc = QVBoxLayout(self.bloc_carriere)
        bc.setContentsMargins(0, 0, 0, 0)
        fv.addWidget(self.bloc_carriere)
        section("المسار المهني (لتحديد الفائض)", [(lib, self.dates[k]) for k, lib in rh.DATES_CARRIERE], bc)
        self.exemption = QComboBox()
        for lib, k in (("لا استثناء", ""), ("أستاذ(ة) مبرز(ة)", "agrege"), ("حامل(ة) الدكتوراه", "doctorat")):
            self.exemption.addItem(lib, k)
        self.date_doctorat = ChampDate()
        self.exemption.currentIndexChanged.connect(
            lambda _: self.date_doctorat.setEnabled(self.exemption.currentData() == "doctorat"))
        g_ex = QGridLayout()
        g_ex.setHorizontalSpacing(16)
        g_ex.addWidget(etiquette("الاستثناء من الفائض", self.exemption), 0, 0)
        g_ex.addWidget(self.exemption, 1, 0)
        g_ex.addWidget(etiquette("تاريخ الحصول على الدكتوراه", self.date_doctorat), 0, 1)
        g_ex.addWidget(self.date_doctorat, 1, 1)
        bc.addLayout(g_ex)
        regle = QLabel("من عُيّن بالمديرية قبل إحداث الأكاديميات: يُعتمد 01/09/2002 تاريخاً للتعيين بالأكاديمية "
                       "(يُملأ آلياً عند الحفظ).")
        regle.setObjectName("etiquette")
        regle.setWordWrap(True)
        bc.addWidget(regle)
        self.anciennete = QLabel()
        self.anciennete.setObjectName("etiquette")
        self.anciennete.setWordWrap(True)
        bc.addWidget(self.anciennete)
        self.bloc_ens = QWidget()
        be = QVBoxLayout(self.bloc_ens)
        be.setContentsMargins(0, 0, 0, 0)
        t = QLabel("التدريس")
        t.setObjectName("titreCarte")
        be.addWidget(t)
        aide = QLabel("أسند أقسام السنة الجارية: يُحسب مستوى التدريس وعدد التلاميذ آلياً من لوائح مسار.")
        aide.setObjectName("etiquette")
        aide.setWordWrap(True)
        be.addWidget(aide)
        self.classes = QListWidget()
        self.classes.setMaximumHeight(120)
        self.classes.itemChanged.connect(lambda _: self._maj_enseignement())
        be.addWidget(self.classes)
        self.calcul = QLabel()
        self.calcul.setWordWrap(True)
        be.addWidget(self.calcul)
        g = QGridLayout()
        g.setHorizontalSpacing(16)
        self.matiere_tarl = QComboBox()
        self.matiere_tarl.addItem("نفس مادة التدريس", "")
        for m in rh.MATIERES:
            self.matiere_tarl.addItem(m, m)
        self.classes_tarl = champ("إن اختلفت عن الأقسام المسندة")
        for i, (lib, w) in enumerate((("مادة التدريس (فترة إرساء الموارد)", self.matiere),
                                      ("المادة خلال فترة الدعم TaRL", self.matiere_tarl),
                                      ("الأقسام أو المجموعات خلال فترة الدعم TaRL", self.classes_tarl),
                                      ("ساعات العمل الأسبوعية", self.c["heures_hebdo"]),
                                      ("مستوى التدريس (يدوي)", self.c["niveau_enseigne"]),
                                      ("عدد التلاميذ (يدوي)", self.c["nb_eleves"]))):
            g.addWidget(etiquette(lib, w), (i // 2) * 2, i % 2)
            g.addWidget(w, (i // 2) * 2 + 1, i % 2)
        be.addLayout(g)
        fv.addWidget(self.bloc_ens)
        self.categorie.currentIndexChanged.connect(lambda _: self._maj_categorie())

        section("التواصل", [("العنوان الشخصي", self.c["adresse"]), ("الهاتف", self.c["telephone"])])
        self.dossier = QCheckBox("الملف الإداري للموظف متوفر بالمؤسسة")
        fv.addWidget(self.dossier)
        self.remarques = QPlainTextEdit()
        self.remarques.setPlaceholderText("ملاحظات (تظهر في محضر التسليم)")
        self.remarques.setMaximumHeight(70)
        fv.addWidget(self.remarques)
        self.manquants = QLabel()
        self.manquants.setWordWrap(True)
        fv.addWidget(self.manquants)
        boutons = QHBoxLayout()
        b_save = QPushButton("حفظ")
        b_save.setObjectName("principal")
        b_save.clicked.connect(self.enregistrer)
        self.b_depart = QPushButton("مغادرة (انتقال، تقاعد...)")
        self.b_depart.clicked.connect(self.dialogue_depart)
        self.b_retour = QPushButton("إرجاع إلى العمل")
        self.b_retour.clicked.connect(self.reintegrer)
        for b in (b_save, self.b_depart, self.b_retour):
            boutons.addWidget(b)
        boutons.addStretch()
        fv.addLayout(boutons)
        fv.addStretch()
        corps.addWidget(c2, 7)
        self.rafraichir()
        self.nouveau()

    # ---------- اللائحة ----------

    def rafraichir(self) -> None:
        eff = rh.effectifs(self.f.conn)
        self.effectifs.setText("العاملون حالياً:  " + "   ·   ".join(
            f"{rh.CATEGORIES[k][2]}: {n}" for k, n in eff.items() if n))
        self.unite.clear()
        self.unite.addItem("—", "")
        for u in et.unites(self.f.conn):
            self.unite.addItem(u, u)
        for k in rh.CHAMPS_SUGGERES:
            w, t = self.c[k], self.c[k].currentText()
            w.clear()
            w.addItems(rh.suggestions(self.f.conn, k))
            w.setEditText(t)
        self.chercher()

    def chercher(self, _=None) -> None:
        lignes = rh.lister(self.f.conn, self.recherche.text(), self.filtre_cat.currentData(),
                           not self.voir_partis.isChecked())
        self.liste.setRowCount(len(lignes))
        for i, p in enumerate(lignes):
            nom = f"{p.prenom_ar} {p.nom_ar}"
            if p.statut != "actif":
                nom += f" ({rh.STATUTS[p.statut]})"
            self.liste.setItem(i, 0, cellule(nom, p.id))
            self.liste.setItem(i, 1, cellule(p.fonction or "—"))
            self.liste.item(i, 0).setToolTip(f"{rh.libelle_categorie(p.categorie, p.sexe)} · رقم التأجير: {p.ppr or '—'}")

    def choisir_xml(self) -> None:
        f, _ = QFileDialog.getOpenFileName(self, "ملف XML للموارد البشرية", "", "XML (*.xml)")
        if f:
            self.importer_xml(f)

    def importer_xml(self, source, valider: bool | None = None) -> dict | None:
        """يقرأ الملف ويعرض المراجعة؛ valider (للاختبار) يعتمد دون نافذة."""
        try:
            props = irh.comparer(self.f.conn, irh.lire_xml(source))
        except irh.ErreurImportRH as e:
            message(self.message, str(e), erreur=True)
            return None
        d = DialogueImportRH(props, self)
        if valider is None:
            if d.exec() != QDialog.Accepted:
                return None
        elif not valider:
            return None
        choisis = d.choisies()
        try:
            n = irh.appliquer(self.f.conn, choisis)
        except rh.ErreurPersonnel as e:
            message(self.message, str(e), erreur=True)
            self.rafraichir()
            return None
        message(self.message, f"الاستيراد من ملف XML: أُضيف {n['ajoutes']} وحُدِّث {n['maj']}. "
                              "أكمل ما لا يتضمنه الملف (التفتيش، الأقسام، أنصاف أيام العطلة...) من ملف كل موظف.")
        self.rafraichir()
        return n

    def _selection(self) -> None:
        lignes = {i.row() for i in self.liste.selectedIndexes()}
        if len(lignes) == 1:
            self.afficher(self.liste.item(lignes.pop(), 0).data(Qt.UserRole))

    # ---------- الملف ----------

    def _categories(self, directeur: bool) -> None:
        self.categorie.blockSignals(True)
        self.categorie.clear()
        for k, (m, f, _) in rh.CATEGORIES.items():
            if (k == "directeur") == directeur:
                self.categorie.addItem(m if k == "directeur" else f"{m} / {f}", k)
        self.categorie.setEnabled(not directeur)
        self.categorie.blockSignals(False)

    def _remplir_classes(self, coches: list[int]) -> None:
        self.classes.blockSignals(True)
        self.classes.clear()
        for r in rh.classes_annee(self.f.conn):
            texte = f"{r['code']}  ·  {r['effectif']} تلميذاً"
            if r["enseignants"] and r["id"] not in coches:
                texte += f"  ·  مسند إلى: {r['enseignants']}"
            it = QListWidgetItem(texte)
            it.setData(Qt.UserRole, r["id"])
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if r["id"] in coches else Qt.Unchecked)
            self.classes.addItem(it)
        if not self.classes.count():
            self.classes.addItem("لا أقسام في السنة الجارية بعد (استورد لوائح مسار).")
        self.classes.blockSignals(False)

    def classes_cochees(self) -> list[int]:
        return [self.classes.item(i).data(Qt.UserRole) for i in range(self.classes.count())
                if self.classes.item(i).data(Qt.UserRole) is not None
                and self.classes.item(i).checkState() == Qt.Checked]

    def _maj_situation(self) -> None:
        s = self.situation.currentData()
        for w in (self.etab_charge, self.d_tanzim["date_charge"], self.l_etab_charge,
                  self.etiquettes.get("تاريخ التكليف")):
            if w is not None:
                w.setEnabled(s != "normal")
        self.l_etab_charge.setText("المؤسسة الأصلية" if s == "charge_in" else "مؤسسة التكليف")

    def _maj_categorie(self) -> None:
        cat = self.categorie.currentData()
        self.bloc_tanzim.setVisible(cat in ("enseignant", "directeur", "assistant"))
        self.bloc_charge.setVisible(cat == "enseignant")
        self.bloc_repos.setVisible(cat == "directeur")
        if not self.fonction.currentData() and rh.fonction_par_defaut(cat or ""):
            self.fonction.setCurrentIndex(self.fonction.findData(rh.fonction_par_defaut(cat)))
        self.bloc_ens.setVisible(cat in ("enseignant", "educatrice"))
        directeur = cat == "directeur"
        self.bloc_carriere.setVisible(not directeur)
        self.c["cycle"].setVisible(not directeur)
        self.etiquettes["السلك"].setVisible(not directeur)

    def _maj_enseignement(self) -> None:
        ids = self.classes_cochees()
        manuel = not ids
        for k in ("niveau_enseigne", "nb_eleves"):
            self.c[k].setEnabled(manuel)
        if ids:
            e = rh.enseignement(self.f.conn, rh.Personnel(classes=ids))
            self.calcul.setText(f"محسوب من الأقسام: {e['niveau']} · {e['nb_eleves']} تلميذاً")
            self.calcul.show()
        else:
            self.calcul.hide()

    def nouveau(self) -> None:
        self.pid = None
        self.liste.clearSelection()
        self.afficher_personnel(rh.Personnel())
        self.titre.setText("موظف جديد")
        self.c["nom_ar"].setFocus()

    def afficher(self, pid: int) -> None:
        self.afficher_personnel(rh.lire(self.f.conn, pid))

    def afficher_personnel(self, p: rh.Personnel) -> None:
        self.pid = p.id
        self._categories(p.categorie == "directeur")
        self.categorie.setCurrentIndex(max(0, self.categorie.findData(p.categorie)))
        for k, w in self.c.items():
            v = getattr(p, k)
            v = "" if v is None else str(v)
            w.setEditText(v) if isinstance(w, QComboBox) else w.setText(v)
        for r in (self.r_m, self.r_f):
            r.setAutoExclusive(False)
            r.setChecked(False)
            r.setAutoExclusive(True)
        if p.sexe:
            (self.r_f if p.sexe == "F" else self.r_m).setChecked(True)
        self.unite.setCurrentIndex(max(0, self.unite.findData(p.unite)))
        self.exemption.setCurrentIndex(max(0, self.exemption.findData(p.exemption_fa or "")))
        self.date_doctorat.definir(p.date_exemption_fa or None)
        self.date_doctorat.setEnabled(p.exemption_fa == "doctorat")
        for k, w in self.d_tanzim.items():
            w.definir(getattr(p, k) or None)
        self.note_insp.setText("" if p.note_inspection in (None, "") else f"{float(p.note_inspection):g}")
        self.inspecteur.setText(p.inspecteur or "")
        self.sans_insp.setChecked(bool(p.sans_inspection))
        self.situation.setCurrentIndex(max(0, self.situation.findData(p.situation or "normal")))
        self.etab_charge.setText(p.etab_charge or "")
        self.matiere_tarl.setCurrentIndex(max(0, self.matiere_tarl.findData(p.matiere_tarl or "")))
        self.classes_tarl.setText(p.classes_tarl or "")
        self._maj_situation()
        for w, val, n in ((self.cadre, p.cadre, len(rh.CADRES)), (self.grade, p.grade, len(rh.GRADES)),
                          (self.fonction, p.fonction, len(rh.FONCTIONS)),
                          (self.echelon, p.echelon, len(rh.ECHELONS)), (self.repos_matin, p.repos_matin, len(rh.JOURS)),
                          (self.repos_soir, p.repos_soir, len(rh.JOURS)),
                          (self.matiere, None, len(rh.MATIERES))):
            while w.count() > n + 1:  # حذف القيم القديمة المضافة لعرض سابق
                w.removeItem(w.count() - 1)
            if val is None:
                continue
            j = w.findData(val or "")
            if j < 0:  # قيمة مكتوبة يدوياً قبل اعتماد القائمة
                w.addItem(f"{val} (اختر من القائمة)", val)
                j = w.count() - 1
            w.setCurrentIndex(j)
        i = self.matiere.findData(p.matiere)
        if i < 0:  # قيمة قديمة مكتوبة يدوياً قبل اعتماد القائمة: تظهر وتُطلب إعادة الاختيار
            self.matiere.addItem(f"{p.matiere} (اختر من القائمة)", p.matiere)
            i = self.matiere.count() - 1
        self.matiere.setCurrentIndex(i)
        for k, w in self.dates.items():
            w.definir(getattr(p, k) or None)
        a = rh.anciennetes(p)
        morceaux = [f"{lib}: {a[k]} سنة" for k, lib in (("age", "السن"), ("fonction", "الأقدمية في الوظيفة"),
                    ("academie", "بالأكاديمية"), ("direction", "بالمديرية"), ("etablissement", "بالمؤسسة"))
                    if a[k] is not None]
        self.anciennete.setText(" · ".join(morceaux))
        self.anciennete.setVisible(bool(morceaux))
        self.dossier.setChecked(p.dossier_disponible)
        self.remarques.setPlainText(p.remarques)
        self._remplir_classes(p.classes)
        self._maj_categorie()
        self._maj_enseignement()
        self.statut, self.date_depart = p.statut, p.date_depart
        if p.id:
            etat = "" if p.statut == "actif" else f" · {rh.STATUTS[p.statut]} منذ {p.date_depart}"
            self.titre.setText(f"{p.prenom_ar} {p.nom_ar} · {rh.libelle_categorie(p.categorie, p.sexe)}{etat}")
            m = rh.manquants_documents(self.f.conn, p)
            mc = rh.manquants_carriere(p)
            lignes = ["ينقص لوثائق الرخص ومحضر الاستئناف: " + "، ".join(m) if m
                      else "الملف مكتمل لوثائق الرخص ومحضر الاستئناف."]
            if mc:
                lignes.append("ينقص لتحديد الفائض: " + "، ".join(mc))
            self.manquants.setObjectName("alerte" if (m or mc) else "ok")
            self.manquants.setText("\n".join(lignes))
            self.manquants.style().unpolish(self.manquants)
            self.manquants.style().polish(self.manquants)
            self.manquants.show()
        else:
            self.manquants.hide()
        self.b_depart.setVisible(bool(p.id) and p.statut == "actif" and p.categorie != "directeur")
        self.b_retour.setVisible(bool(p.id) and p.statut != "actif")
        self.message.hide()

    def lire_formulaire(self) -> rh.Personnel:
        v = {k: (w.currentText() if isinstance(w, QComboBox) else w.text()) for k, w in self.c.items()}
        v["matiere"] = self.matiere.currentData() or ""
        v["cadre"] = self.cadre.currentData() or ""
        v["fonction"] = self.fonction.currentData() or ""
        v["echelon"] = self.echelon.currentData() or ""
        v["repos_matin"], v["repos_soir"] = self.repos_matin.currentData() or "", self.repos_soir.currentData() or ""
        v["note_inspection"], v["inspecteur"] = self.note_insp.text(), self.inspecteur.text()
        v["sans_inspection"] = self.sans_insp.isChecked()
        v["situation"], v["etab_charge"] = self.situation.currentData(), self.etab_charge.text()
        v["matiere_tarl"], v["classes_tarl"] = self.matiere_tarl.currentData() or "", self.classes_tarl.text()
        v["grade"] = self.grade.currentData() or ""
        v["exemption_fa"] = self.exemption.currentData() or ""
        try:
            v["date_exemption_fa"] = self.date_doctorat.iso() if v["exemption_fa"] == "doctorat" else ""
        except ValueError:
            raise rh.ErreurPersonnel("تاريخ الحصول على الدكتوراه غير صحيح.") from None
        dates = {}
        for k, lib in rh.DATES_CARRIERE + rh.DATES_TANZIM:
            try:
                dates[k] = (self.dates.get(k) or self.d_tanzim[k]).iso()
            except ValueError:
                raise rh.ErreurPersonnel(f"{lib} غير صحيح.") from None
        ids = self.classes_cochees()
        if ids:
            v["niveau_enseigne"], v["nb_eleves"] = "", ""
        sexe = "F" if self.r_f.isChecked() else "M" if self.r_m.isChecked() else ""
        return rh.Personnel(**v, sexe=sexe, categorie=self.categorie.currentData(),
                            unite=self.unite.currentData() or "", **dates,
                            dossier_disponible=self.dossier.isChecked(),
                            remarques=self.remarques.toPlainText().strip(), id=self.pid,
                            classes=ids if self.categorie.currentData() in ("enseignant", "educatrice") else [],
                            statut=getattr(self, "statut", "actif"), date_depart=getattr(self, "date_depart", ""))

    def enregistrer(self) -> int | None:
        try:
            p = self.lire_formulaire()
            p.valider()   # الحقول الأساسية أولاً (النسب، الاسم، النوع...)
            m = rh.obligatoires_manquants(p)
            if m:   # قرار المدير 2026-11-03: معطيات التنظيم التربوي مطلوبة عند ملء ملف الأستاذ(ة)
                raise rh.ErreurPersonnel("معطيات مطلوبة لملف الأستاذ(ة) (التنظيم التربوي): " + "، ".join(m)
                                         + ". إن لم يخضع(تخضع) للتفتيش بعد، أشّر على الخانة الخاصة بذلك.")
            pid = rh.enregistrer(self.f.conn, p)
        except rh.ErreurPersonnel as e:
            message(self.message, str(e), True)
            return None
        self.rafraichir()
        self.afficher(pid)
        ligne = next((i for i in range(self.liste.rowCount())
                      if self.liste.item(i, 0).data(Qt.UserRole) == pid), None)
        if ligne is not None:
            self.liste.blockSignals(True)
            selectionner(self.liste, ligne)
            self.liste.blockSignals(False)
        message(self.message, "حُفظ ملف الموظف.")
        return pid

    def dialogue_depart(self) -> None:
        d = DialogueDepart(self.titre.text(), self)
        if d.exec() == QDialog.Accepted:
            try:
                le = d.le.iso()
            except ValueError:
                message(self.message, "التاريخ غير صحيح.", True)
                return
            self.depart(d.statut.currentData(), le, d.remarque.text())

    def depart(self, statut: str, le: str, remarque: str = "") -> bool:
        try:
            rh.depart(self.f.conn, self.pid, statut, le, remarque)
        except rh.ErreurPersonnel as e:
            message(self.message, str(e), True)
            return False
        pid = self.pid
        self.rafraichir()
        self.afficher(pid)
        message(self.message, f"سُجّلت المغادرة ({rh.STATUTS[statut]}). الملف محفوظ ويظهر بتفعيل «إظهار المغادرين».")
        return True

    def reintegrer(self) -> None:
        try:
            rh.reintegrer(self.f.conn, self.pid)
        except rh.ErreurPersonnel as e:
            message(self.message, str(e), True)
            return
        pid = self.pid
        self.rafraichir()
        self.afficher(pid)
        message(self.message, "أُرجع الموظف إلى لائحة العاملين.")


class DialogueImportRH(QDialog):
    """مراجعة نتيجة الاستيراد من ملف XML قبل الاعتماد: سطر لكل موظف مع ما سيُضاف أو يُغيَّر."""

    ETATS = {"nouveau": "جديد", "maj": "تحديث", "identique": "دون تغيير", "ignore": "لا يُستورد",
             "erreur": "يحتاج تصحيحاً"}

    def __init__(self, props: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("مراجعة الاستيراد من ملف XML")
        self.setLayoutDirection(Qt.RightToLeft)
        self.resize(900, 520)
        self.props = props
        v = QVBoxLayout(self)
        n = {k: sum(p.etat == k for p in props) for k in self.ETATS}
        resume = QLabel("   ·   ".join(f"{lib}: {n[k]}" for k, lib in self.ETATS.items() if n[k]) +
                        "\nلا شيء يُحذف. القيم المدخلة سابقاً لا تُمحى بخانة فارغة، والاسمان لا يُغيَّران عند "
                        "موظف مسجل.")
        resume.setWordWrap(True)
        v.addWidget(resume)
        self.table = tableau(["اعتماد", "الموظف", "الحالة", "التفاصيل"], etirer=3)
        self.table.setRowCount(len(props))
        self.cases: list[QCheckBox | None] = []
        for i, p in enumerate(props):
            if p.etat in ("nouveau", "maj"):
                c = QCheckBox()
                c.setChecked(True)
                self.table.setCellWidget(i, 0, c)
                self.cases.append(c)
            else:
                self.cases.append(None)
            self.table.setItem(i, 1, cellule(p.agent.nom))
            self.table.setItem(i, 2, cellule(self.ETATS[p.etat]))
            if p.etat == "nouveau":
                det = "يُضاف بـ " + str(len(p.changements)) + " معلومة."
            elif p.etat == "maj":
                det = "؛ ".join(f"{lib}: {a or '—'} ← {b}" for lib, a, b in p.changements)
            else:
                det = p.raison
            if p.agent.notes:
                det = (det + " " if det else "") + " ".join(p.agent.notes)
            it = cellule(det)
            it.setToolTip("\n".join(f"{lib}: {a or '—'} ← {b}" for lib, a, b in p.changements) or det)
            self.table.setItem(i, 3, it)
        v.addWidget(self.table, 1)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("اعتماد المحدد")
        bb.button(QDialogButtonBox.Cancel).setText("إلغاء")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)

    def choisies(self) -> list:
        return [p for p, c in zip(self.props, self.cases) if c is not None and c.isChecked()]
