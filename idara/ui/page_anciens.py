"""التلاميذ القدامى (ما قبل مسار): البحث برقم السجل العام أو الاسم، وملء كل حقول الشهادة المدرسية."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QDateEdit, QGridLayout,
                               QHBoxLayout, QLabel, QLineEdit, QPushButton, QRadioButton,
                               QVBoxLayout, QWidget)

from idara.services import anciens as an
from idara.services import bureautique
from idara.services import documents as dc
from idara.services import eleves as el
from idara.ui.composants import carte, entete
from idara.ui.formulaires import champ, etiquette
from idara.ui.saisie import ChampDate, cellule, message, tableau


class PageAnciens(QWidget):
    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        self.eleve_id: int | None = None
        racine = QVBoxLayout(self)
        racine.setContentsMargins(40, 32, 40, 32)
        racine.setSpacing(16)
        racine.addWidget(entete(
            "التلاميذ القدامى (ما قبل مسار)",
            "الشهادة المدرسية لمن درس قبل منظومة مسار. يُحفظ التلميذ برقمه في السجل العام لتيسير إعادة الطباعة. "
            "أما تلاميذ مسار فتُستخرج شهادتهم من المنصة."))
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.hide()
        racine.addWidget(self.message)
        # طلب المدير 2026-11-20: إضافة تلميذ أو شهادة مدرسية من نافذة منبثقة؛ الصفحة الثابتة للائحة
        from idara.ui.vitrine import FenetreFiche, bouton_couleur
        hb = QHBoxLayout()
        self.b_ajouter = bouton_couleur("تلميذ قديم جديد", "#1565C0", "ajouter",
                                        "إدخال تلميذ درس قبل مسار ثم توليد شهادته المدرسية")
        self.b_ajouter.clicked.connect(lambda: self.ouvrir_nouveau())
        self.b_certificat = bouton_couleur("شهادة مدرسية للتلميذ المحدد", "#2E7D32", "document",
                                           "اختر التلميذ من اللائحة ثم أدخل اسم متسلم الشهادة")
        self.b_certificat.clicked.connect(lambda: self.ouvrir_certificat(self.eleve_id))
        hb.addWidget(self.b_ajouter)
        hb.addWidget(self.b_certificat)
        hb.addStretch()
        racine.addLayout(hb)
        corps = QHBoxLayout()
        corps.setSpacing(20)
        racine.addLayout(corps, 1)

        # البحث
        c, cv = carte("التلاميذ القدامى المسجلون")
        self.recherche = QLineEdit()
        self.recherche.setPlaceholderText("رقم التسجيل في السجل العام أو الاسم")
        self.recherche.setClearButtonEnabled(True)
        self.recherche.textChanged.connect(self.chercher)
        cv.addWidget(etiquette("بحث", self.recherche))
        cv.addWidget(self.recherche)
        self.resultats = tableau(["رقم السجل", "الاسم", "آخر قسم", "الشهادات المسلمة", ""], etirer=1)
        self.resultats.setMinimumHeight(380)
        self.resultats.itemSelectionChanged.connect(self._selection)
        self.resultats.itemDoubleClicked.connect(
            lambda it: self.ouvrir_certificat(self.resultats.item(it.row(), 0).data(Qt.UserRole)))
        cv.addWidget(self.resultats, 1)
        corps.addWidget(c, 1)

        # الاستمارة
        c2, fv = carte()
        self.titre = QLabel("تلميذ جديد")
        self.titre.setObjectName("titreCarte")
        fv.addWidget(self.titre)
        self.m_fiche = QLabel()
        self.m_fiche.setWordWrap(True)
        self.m_fiche.hide()
        fv.addWidget(self.m_fiche)
        note = QLabel("كل الحقول المعلَّمة بـ * إجبارية: الشهادة لا تُولَّد بحقل فارغ.")
        note.setObjectName("etiquette")
        fv.addWidget(note)
        g = QGridLayout()
        g.setHorizontalSpacing(16)
        g.setVerticalSpacing(4)
        self.c_num = champ("مثال: 8173", ltr=True)
        self.c_cahier = champ(ltr=True)
        self.c_nom, self.c_prenom = champ(), champ()
        self.c_naissance = ChampDate()
        self.c_approx = QCheckBox("تاريخ تقريبي (سنة فقط)")
        self.c_lieu = champ()
        self.c_entree, self.c_sortie = ChampDate(), ChampDate()
        self.c_niveau = QComboBox()
        self.c_niveau.setEditable(True)
        self.c_niveau.addItems(an.NIVEAUX_ANCIENS)
        self.c_niveau.setCurrentIndex(-1)
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
        naiss = QWidget()
        nl = QHBoxLayout(naiss)
        nl.setContentsMargins(0, 0, 0, 0)
        nl.addWidget(self.c_naissance)
        nl.addWidget(self.c_approx)
        nl.addStretch()
        champs = [("رقم التسجيل في السجل العام *", self.c_num), ("رقم دفتر السجل (اختياري)", self.c_cahier),
                  ("النسب *", self.c_nom), ("الاسم *", self.c_prenom),
                  ("النوع *", sexe), ("مكان الازدياد *", self.c_lieu),
                  ("تاريخ الازدياد * (يوم/شهر/سنة)", naiss), ("آخر قسم درس به *", self.c_niveau),
                  ("تاريخ الالتحاق *", self.c_entree), ("تاريخ الانقطاع *", self.c_sortie)]
        for i, (lib, w) in enumerate(champs):
            g.addWidget(etiquette(lib, w), (i // 2) * 2, i % 2)
            g.addWidget(w, (i // 2) * 2 + 1, i % 2)
        fv.addLayout(g)

        t = QLabel("متسلّم الشهادة")
        t.setObjectName("titreCarte")
        fv.addWidget(t)
        g2 = QGridLayout()
        g2.setHorizontalSpacing(16)
        self.c_dest = champ("الاسم الكامل")
        self.c_cin = champ("مثال: A123456", ltr=True)
        self.c_le = QDateEdit()
        self.c_le.setCalendarPopup(True)
        self.c_le.setDisplayFormat("dd/MM/yyyy")
        self.c_le.setLayoutDirection(Qt.LeftToRight)
        self.c_le.setDate(QDate.currentDate())
        b_lui = QPushButton("التلميذ نفسه")
        b_lui.clicked.connect(lambda: self.c_dest.setText(f"{self.c_prenom.text()} {self.c_nom.text()}".strip()))
        for i, (lib, w) in enumerate([("اسم المتسلم *", self.c_dest), ("رقم البطاقة الوطنية *", self.c_cin),
                                      ("تاريخ التحرير", self.c_le)]):
            g2.addWidget(etiquette(lib, w), 0, i)
            g2.addWidget(w, 1, i)
        g2.addWidget(b_lui, 2, 0, Qt.AlignRight)
        fv.addLayout(g2)

        boutons = QHBoxLayout()
        b_gen = QPushButton("حفظ وتوليد الشهادة")
        b_gen.setObjectName("principal")
        b_gen.clicked.connect(self.generer)
        b_save = QPushButton("حفظ فقط")
        b_save.clicked.connect(self.enregistrer)
        boutons.addWidget(b_gen)
        boutons.addWidget(b_save)
        boutons.addStretch()
        fv.addLayout(boutons)

        t2 = QLabel("الشهادات المسلَّمة لهذا التلميذ")
        t2.setObjectName("titreCarte")
        fv.addWidget(t2)
        self.remises = tableau(["التاريخ", "المتسلم", "البطاقة", ""], etirer=1)
        self.remises.setMinimumHeight(130)
        self.remises.cellDoubleClicked.connect(self._reimprimer)
        fv.addWidget(self.remises)
        aide = QLabel("نقرة مزدوجة على سطر لإعادة طباعة الشهادة بنفس بياناتها.")
        aide.setObjectName("etiquette")
        fv.addWidget(aide)
        self.fiche = FenetreFiche(self, "تلميذ قديم جديد", "", c2, largeur=920)
        self.chercher("")

    # ---------- البحث ----------

    def rafraichir(self) -> None:
        self.chercher(self.recherche.text())

    def chercher(self, texte: str) -> None:
        from idara.ui.vitrine import ajuster_colonne_actions, boutons_ligne, vider_colonne_widgets
        lignes = el.rechercher(self.f.conn, texte, source="avant_massar")
        vider_colonne_widgets(self.resultats, 4)
        self.resultats.setRowCount(len(lignes))
        for i, r in enumerate(lignes):
            self.resultats.setItem(i, 0, cellule(r["num_registre"], r["id"]))
            self.resultats.setItem(i, 1, cellule(f"{r['prenom_ar']} {r['nom_ar']}"))
            try:
                niv = an.lire(self.f.conn, r["id"]).dernier_niveau
            except an.ErreurAncien:
                niv = ""
            self.resultats.setItem(i, 2, cellule(niv))
            n = len(an.remises(self.f.conn, r["id"]))
            self.resultats.setItem(i, 3, cellule(str(n) if n else "لا شيء"))
            self.resultats.setCellWidget(i, 4, boutons_ligne([
                ("شهادة مدرسية", "#2E7D32", "document", lambda _=False, k=r["id"]: self.ouvrir_certificat(k)),
                ("تعديل", "#1565C0", "modifier", lambda _=False, k=r["id"]: self.ouvrir_certificat(k, False))]))
        ajuster_colonne_actions(self.resultats, 4)

    def _msg(self, texte: str, erreur: bool = False) -> None:
        message(self.message, texte, erreur)
        message(self.m_fiche, texte, erreur)

    def ouvrir_nouveau(self):
        self.nouveau()
        self.fiche.definir_titre("تلميذ قديم جديد", "أدخل بياناته كما في السجل العام، ثم متسلم "
                                                                      "الشهادة إن أردت توليدها الآن.")
        self.fiche.ouvrir()
        return self.fiche

    def ouvrir_certificat(self, eleve_id: int | None, certificat: bool = True):
        if eleve_id is None:
            self._msg("اختر التلميذ من اللائحة أولاً، أو أضف تلميذاً قديماً جديداً.", True)
            return None
        self.afficher(eleve_id)
        a = an.lire(self.f.conn, eleve_id)
        self.fiche.definir_titre("شهادة مدرسية" if certificat else "تعديل بيانات التلميذ",
                                 f"{a.prenom_ar} {a.nom_ar} · رقم السجل {a.num_registre}")
        self.fiche.ouvrir()
        (self.c_dest if certificat else self.c_nom).setFocus()
        return self.fiche

    def _selection(self) -> None:
        lignes = {i.row() for i in self.resultats.selectedIndexes()}
        if len(lignes) == 1:
            self.afficher(self.resultats.item(lignes.pop(), 0).data(Qt.UserRole))

    # ---------- الاستمارة ----------

    def nouveau(self) -> None:
        self.eleve_id = None
        self.resultats.clearSelection()
        self.titre.setText("تلميذ جديد")
        for c in (self.c_num, self.c_cahier, self.c_nom, self.c_prenom, self.c_lieu, self.c_naissance,
                  self.c_entree, self.c_sortie, self.c_dest, self.c_cin):
            c.clear()
        self.c_approx.setChecked(False)
        self.c_niveau.setCurrentIndex(-1)
        self.c_niveau.setEditText("")
        for r in (self.r_m, self.r_f):
            r.setAutoExclusive(False)
            r.setChecked(False)
            r.setAutoExclusive(True)
        self.remises.setRowCount(0)
        self.message.hide()
        self.m_fiche.hide()
        self.c_num.setFocus()

    def afficher(self, eleve_id: int) -> None:
        a = an.lire(self.f.conn, eleve_id)
        self.eleve_id = eleve_id
        self.titre.setText(f"{a.prenom_ar} {a.nom_ar} · رقم {a.num_registre}")
        self.c_num.setText(a.num_registre)
        self.c_cahier.setText(a.num_cahier_registre)
        self.c_nom.setText(a.nom_ar)
        self.c_prenom.setText(a.prenom_ar)
        self.c_lieu.setText(a.lieu_ar)
        self.c_naissance.definir(a.date_naissance)
        self.c_approx.setChecked(a.date_naissance_approx)
        self.c_entree.definir(a.date_entree)
        self.c_sortie.definir(a.date_sortie)
        self.c_niveau.setEditText(a.dernier_niveau)
        (self.r_f if a.sexe == "F" else self.r_m).setChecked(True)
        self.c_dest.clear()
        self.c_cin.clear()
        rem = an.remises(self.f.conn, eleve_id)
        self.remises.setRowCount(len(rem))
        for i, r in enumerate(rem):
            self.remises.setItem(i, 0, cellule(r["date_generation"][:16], r["id"]))
            self.remises.setItem(i, 1, cellule(r["destinataire_nom"]))
            self.remises.setItem(i, 2, cellule(r["destinataire_cin"]))
            self.remises.setItem(i, 3, cellule("إعادة الطباعة ↵"))
        self.message.hide()
        self.m_fiche.hide()

    def _lire(self) -> an.Ancien:
        dates = {}
        for k, w, lib in (("date_naissance", self.c_naissance, "تاريخ الازدياد"),
                          ("date_entree", self.c_entree, "تاريخ الالتحاق"),
                          ("date_sortie", self.c_sortie, "تاريخ الانقطاع")):
            try:
                dates[k] = w.iso()
            except ValueError:
                raise an.ErreurAncien(f"{lib} غير صحيح.") from None
        sexe = "F" if self.r_f.isChecked() else "M" if self.r_m.isChecked() else ""
        return an.Ancien(num_registre=self.c_num.text().strip(), nom_ar=self.c_nom.text(),
                         prenom_ar=self.c_prenom.text(), sexe=sexe,
                         date_naissance_approx=self.c_approx.isChecked(), lieu_ar=self.c_lieu.text(),
                         dernier_niveau=self.c_niveau.currentText(),
                         num_cahier_registre=self.c_cahier.text().strip(), id=self.eleve_id, **dates)

    def enregistrer(self) -> int | None:
        try:
            eid = an.enregistrer(self.f.conn, self._lire())
        except an.ErreurAncien as e:
            self._msg(str(e), True)
            return None
        self.eleve_id = eid
        self.chercher(self.recherche.text())
        self.afficher(eid)
        self._msg("حُفظت بيانات التلميذ.")
        return eid

    def generer(self):
        dest, cin = self.c_dest.text().strip(), self.c_cin.text().strip()
        if not dest or not cin:
            self._msg("اسم متسلم الشهادة ورقم بطاقته الوطنية إجباريان.", True)
            return None
        if self.enregistrer() is None:
            return None
        q = self.c_le.date()
        try:
            doc = an.generer_certificat(self.f.conn, self.f.dossier, self.eleve_id, dest, cin,
                                        date(q.year(), q.month(), q.day()))
        except (an.ErreurAncien, dc.ErreurDocument) as e:
            self._msg(str(e), True)
            return None
        self.chercher(self.recherche.text())
        self.afficher(self.eleve_id)
        self._msg(f"وُلّدت الشهادة وسُجّل تسليمها: \u2066{doc.chemin.name}\u2069")
        self._ouvrir(doc.chemin)
        return doc

    def _reimprimer(self, ligne: int, _col: int):
        doc_id = self.remises.item(ligne, 0).data(Qt.UserRole)
        try:
            doc = dc.regenerer(self.f.conn, self.f.dossier, doc_id)
        except dc.ErreurDocument as e:
            self._msg(str(e), True)
            return None
        self._msg(f"أُعيد توليد الشهادة: \u2066{doc.chemin.name}\u2069")
        self._ouvrir(doc.chemin)
        return doc

    def _ouvrir(self, chemin) -> None:
        try:
            bureautique.ouvrir(chemin)
        except OSError as e:
            self._msg(f"تعذر فتح الملف تلقائياً: {e}", True)
