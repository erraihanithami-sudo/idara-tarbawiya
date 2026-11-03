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
        for code in ("parti", "interrompu", "exclu", "arrive", "inscrit"):
            self.statut.addItem({"parti": "مغادر (انتقال إلى مؤسسة أخرى)", "interrompu": "منقطع",
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


class PageEleves(QWidget):
    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        self.eleve_id: int | None = None
        racine = QVBoxLayout(self)
        racine.setContentsMargins(40, 32, 40, 32)
        racine.setSpacing(16)
        racine.addWidget(entete("التلاميذ", "ابحث بالاسم أو برمز مسار، ثم ولّد الوثيقة من بطاقة التلميذ."))
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.hide()
        racine.addWidget(self.message)

        corps = QHBoxLayout()
        corps.setSpacing(20)
        racine.addLayout(corps, 1)

        # البحث والنتائج
        c, cv = carte()
        self.recherche = QLineEdit()
        self.recherche.setPlaceholderText("الاسم أو النسب (بالعربية أو الفرنسية) أو رمز مسار")
        self.recherche.setClearButtonEnabled(True)
        self.recherche.textChanged.connect(self.chercher)
        cv.addWidget(etiquette("بحث", self.recherche))
        cv.addWidget(self.recherche)
        self.resultats = tableau(["الرمز", "الاسم", "القسم", "الوضعية"])
        self.resultats.setSelectionMode(self.resultats.SelectionMode.ExtendedSelection)
        self.resultats.itemSelectionChanged.connect(self._selection)
        self.resultats.setMinimumHeight(420)
        cv.addWidget(self.resultats, 1)
        self.nb = QLabel()
        self.nb.setObjectName("etiquette")
        cv.addWidget(self.nb)
        self.b_convocations = QPushButton("استدعاء أولياء أمور المحددين")
        self.b_convocations.setToolTip("حدد عدة تلاميذ بالضغط على Ctrl، ثم ولّد استدعاءاتهم في ملف واحد")
        self.b_convocations.clicked.connect(self.convocations)
        cv.addWidget(self.b_convocations)
        corps.addWidget(c, 6)

        # البطاقة
        self.c_fiche, fv = carte()
        self.titre = QLabel()
        self.titre.setObjectName("titrePage")
        self.sous_titre = QLabel()
        self.sous_titre.setObjectName("sousTitre")
        self.sous_titre.setWordWrap(True)
        fv.addWidget(self.titre)
        fv.addWidget(self.sous_titre)

        actions = QGridLayout()
        actions.setSpacing(8)
        self.b_vacances = QPushButton("شهادة العطلة")
        self.b_vacances.setObjectName("principal")
        self.b_vacances.clicked.connect(self.dialogue_vacances)
        self.b_visite = QPushButton("ورقة الزيارة الطبية")
        self.b_visite.clicked.connect(self.visite)
        self.b_convoc = QPushButton("استدعاء ولي الأمر")
        self.b_convoc.clicked.connect(lambda: self.convocations([self.eleve_id]))
        self.b_statut = QPushButton("الوضعية (مغادرة، انقطاع...)")
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
        corps.addWidget(self.c_fiche, 5)
        self.c_fiche.hide()
        self.vide = QLabel("اختر تلميذاً من اللائحة لعرض بطاقته.")
        self.vide.setObjectName("etiquette")
        self.vide.setAlignment(Qt.AlignCenter)
        corps.addWidget(self.vide, 5)
        self.chercher("")

    # ---------- البحث ----------

    def rafraichir(self) -> None:
        self.chercher(self.recherche.text())
        if self.eleve_id:
            self.afficher(self.eleve_id)

    def chercher(self, texte: str) -> None:
        lignes = el.rechercher(self.f.conn, texte)
        self.resultats.setRowCount(len(lignes))
        for i, r in enumerate(lignes):
            for j, v in enumerate([r["code_massar"], el.nom_complet(r), r["classe"] or "—",
                                   el.STATUTS.get(r["statut"], "غير مسجل")]):
                self.resultats.setItem(i, j, cellule(v, r["id"]))
        self.nb.setText(f"{len(lignes)} نتيجة" if texte.strip() else f"تلاميذ السنة الجارية: {len(lignes)}")

    def _selection(self) -> None:
        ids = self.ids_selectionnes()
        if len(ids) == 1:
            self.afficher(ids[0])

    def ids_selectionnes(self) -> list[int]:
        lignes = sorted({i.row() for i in self.resultats.selectedIndexes()})
        return [self.resultats.item(r, 0).data(Qt.UserRole) for r in lignes]

    # ---------- البطاقة ----------

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
        self.vide.hide()
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
