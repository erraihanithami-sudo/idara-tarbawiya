"""صفحة الوثائق: القوالب وحالتها، والمعاينة بمثال، وآخر الوثائق المولدة."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QMenu,
                               QMessageBox, QPushButton, QToolButton, QVBoxLayout, QWidget)

from idara.services import bureautique
from idara.services import documents as dc
from idara.ui.composants import carte, entete


class LigneModele(QFrame):
    def __init__(self, page: "PageDocuments", code: str):
        super().__init__()
        self.page, self.code = page, code
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 8, 0, 8)
        h.setSpacing(10)
        textes = QVBoxLayout()
        textes.setSpacing(2)
        self.titre = QLabel(dc.MODELES[code].titre)
        self.titre.setStyleSheet("font-weight:600;")
        self.etat = QLabel()
        self.etat.setWordWrap(True)
        textes.addWidget(self.titre)
        textes.addWidget(self.etat)
        h.addLayout(textes, 1)

        self.b_apercu = QPushButton("معاينة بمثال")
        self.b_apercu.setToolTip("يولد الوثيقة ببيانات وهمية ويفتحها في Word للطباعة والمقارنة")
        self.b_apercu.clicked.connect(lambda: self.page.apercu(code, pdf=False))
        self.b_pdf = QPushButton("PDF")
        self.b_pdf.setToolTip("نفس المعاينة، محوّلة إلى PDF عبر Word")
        self.b_pdf.clicked.connect(lambda: self.page.apercu(code, pdf=True))
        plus = QToolButton()
        plus.setText("القالب ▾")
        plus.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(plus)
        menu.addAction("تعديل القالب في Word", lambda: self.page.modifier(code))
        menu.addAction("تعويضه بملف Word آخر...", lambda: self.page.importer(code))
        menu.addSeparator()
        menu.addAction("استعادة القالب الأصلي", lambda: self.page.restaurer(code))
        plus.setMenu(menu)
        for b in (self.b_apercu, self.b_pdf, plus):
            h.addWidget(b)

    def actualiser(self, etat: dc.EtatModele) -> None:
        if not etat.utilisable:
            self.etat.setObjectName("alerte")
            self.etat.setText("يحتاج تصحيحاً: " + "، ".join(etat.inconnus))
        else:
            txt = "جاهز · " + ("قالب معدّل" if etat.personnalise else "القالب المأخوذ من نموذجك")
            if etat.absents:
                txt += " · حقول غير مستعملة: " + "، ".join(etat.absents)
            self.etat.setObjectName("ok")
            self.etat.setText(txt)
        self.etat.style().unpolish(self.etat)
        self.etat.style().polish(self.etat)
        self.b_apercu.setEnabled(etat.utilisable)
        self.b_pdf.setEnabled(etat.utilisable)


class PageDocuments(QWidget):
    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        v = QVBoxLayout(self)
        v.setContentsMargins(40, 32, 40, 32)
        v.setSpacing(20)
        v.addWidget(entete("الوثائق", "القوالب مأخوذة من نماذجك الحقيقية، والحقول تُملأ آلياً من البيانات."))

        c, cv = carte("القوالب")
        self.lignes = {}
        for i, code in enumerate(dc.MODELES):
            if i:
                sep = QFrame()
                sep.setFrameShape(QFrame.HLine)
                sep.setStyleSheet("color:#EFEBE2;")
                cv.addWidget(sep)
            ligne = LigneModele(self, code)
            self.lignes[code] = ligne
            cv.addWidget(ligne)
        note = QLabel("الترويسة والتذييل والعلامة المائية صور مأخوذة من نماذجك. لتغييرها: "
                      "«القالب ▾» ثم «تعديل القالب في Word»، ثم احفظ الملف وأغلقه. "
                      "التلاميذ ما قبل مسار لهم الشهادة المدرسية من هنا؛ تلاميذ مسار تُستخرج شهادتهم من المنصة.")
        note.setObjectName("etiquette")
        note.setWordWrap(True)
        cv.addWidget(note)
        v.addWidget(c)

        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.hide()
        v.addWidget(self.message)

        c2, self.cv_recents = carte("آخر الوثائق المولدة")
        self.grille = QGridLayout()
        self.grille.setHorizontalSpacing(16)
        self.cv_recents.addLayout(self.grille)
        v.addWidget(c2)
        v.addStretch()
        self.rafraichir()

    # ---------- العرض ----------

    def rafraichir(self) -> None:
        for code, ligne in self.lignes.items():
            ligne.actualiser(dc.etat_modele(self.f.dossier, code))
        while self.grille.count():
            w = self.grille.takeAt(0).widget()
            if w:
                w.deleteLater()
        recents = dc.documents_recents(self.f.conn, 10)
        if not recents:
            vide = QLabel("لم تُولَّد أي وثيقة بعد. ستظهر هنا الوثائق الفعلية ابتداء من المرحلة 4.")
            vide.setObjectName("etiquette")
            self.grille.addWidget(vide, 0, 0)
            return
        for i, d in enumerate(recents):
            self.grille.addWidget(QLabel(d["titre"]), i, 0)
            self.grille.addWidget(QLabel(d["libelle"] or ""), i, 1)
            self.grille.addWidget(QLabel(d["date_generation"][:16]), i, 2)
            b = QPushButton("فتح")
            chemin = self.f.dossier.racine / d["fichier_archive"]
            b.clicked.connect(lambda _=False, p=chemin: self._ouvrir(p))
            self.grille.addWidget(b, i, 3)

    def _message(self, texte: str, erreur: bool = False) -> None:
        self.message.setObjectName("erreur" if erreur else "info")
        self.message.setText(texte)
        self.message.style().unpolish(self.message)
        self.message.style().polish(self.message)
        self.message.show()

    def _ouvrir(self, chemin: Path) -> None:
        try:
            bureautique.ouvrir(chemin)
        except OSError as e:
            self._message(f"تعذر فتح الملف: {e}", erreur=True)

    # ---------- الأفعال ----------

    def apercu(self, code: str, pdf: bool = False) -> Path | None:
        try:
            valeurs, pages = dc.exemple(self.f.conn, code)
            doc = dc.generer(self.f.conn, self.f.dossier, code, valeurs, pages,
                             libelle="معاينة", essai=True)
            chemin = doc.chemin
            if pdf:
                self.setCursor(Qt.WaitCursor)
                try:
                    chemin = bureautique.convertir_pdf(chemin)
                finally:
                    self.unsetCursor()
        except (dc.ErreurDocument, bureautique.ErreurBureautique) as e:
            self._message(str(e), erreur=True)
            return None
        self._message(f"وثيقة تجريبية ببيانات وهمية: {chemin.name}")
        self._ouvrir(chemin)
        return chemin

    def modifier(self, code: str) -> None:
        self._ouvrir(dc.chemin_modele(self.f.dossier, code))
        self._message("بعد الحفظ في Word وإغلاق الملف، عُد إلى هذه الصفحة لتحديث حالة القالب.")

    def importer(self, code: str) -> None:
        f, _ = QFileDialog.getOpenFileName(self, "اختيار قالب Word", "", "Word (*.docx)")
        if not f:
            return
        try:
            dc.importer_modele(self.f.dossier, code, Path(f))
        except dc.ErreurDocument as e:
            self._message(str(e), erreur=True)
            return
        self._message("عُوّض القالب. القالب السابق محفوظ باسم ‎.precedent في مجلد القوالب.")
        self.rafraichir()

    def restaurer(self, code: str) -> None:
        r = QMessageBox.question(self, "استعادة القالب الأصلي",
                                 "سيُعوَّض القالب الحالي بالأصلي (ويُحفظ الحالي كنسخة سابقة). متابعة؟")
        if r != QMessageBox.Yes:
            return
        dc.restaurer_modele(self.f.dossier, code)
        self._message("استُعيد القالب الأصلي.")
        self.rafraichir()
