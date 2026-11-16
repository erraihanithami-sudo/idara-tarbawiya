"""محرر الوثائق داخل البرنامج (طلب المدير 2026-11-15): كل وثيقة مولَّدة تُفتح هنا، تُعدَّل وتُطبع مباشرة.

منذ توجيهات 2026-11-16 (نموذج «الورقة الشخصية»): المحرر مدمج في نافذة البرنامج نفسها لا في نافذة مستقلة. تُفتح
الوثيقة معاينةً للقراءة، وفوقها: رجوع، تعديل الوثيقة، حفظ PDF، حفظ كصورة، طباعة. «تعديل الوثيقة» يُظهر أدوات
التنسيق ويجعل الورقة قابلة للكتابة.

الوثيقة تُحوَّل من Word إلى صفحة يحررها QTextEdit (idara.services.finition.en_html). التعديلات تُحفظ بجانب
الملف الأصلي («‎.تعديل.html‎») فيُعاد فتحها كما تُركت؛ الملف الأصلي لا يُمَس، وزر «فتح في Word» يفتحه هو.
ما لا يظهر هنا: إطار الصفحة المزخرف، مربعات النص، والصور العائمة؛ لتلك يبقى Word.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QMarginsF, QRectF, QSizeF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPageLayout, QPageSize, QPainter, QTextCharFormat, QTextCursor
from PySide6.QtPrintSupport import QPrintDialog, QPrinter, QPrintPreviewDialog
from PySide6.QtWidgets import (QDialog, QFileDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QTextEdit,
                               QVBoxLayout, QWidget)

from idara.services import bureautique, finition
from idara.ui.saisie import message

PX_PAR_MM = 96 / 25.4
MARGE_ECRAN = 44   # هامش الورقة على الشاشة (بكسل)


def fichier_modifie(chemin: Path) -> Path:
    return chemin.with_name(chemin.stem + ".تعديل.html")


class EditeurDocument(QWidget):
    """معاينة الوثيقة وتحريرها داخل النافذة. retour: ما يُنفَّذ عند «رجوع» (العودة إلى الصفحة السابقة)."""

    def __init__(self, chemin: Path, parent=None, retour=None):
        super().__init__(parent)
        self.chemin = Path(chemin)
        self.retour = retour
        self.page = finition.en_html(self.chemin)
        self.setWindowTitle(f"محرر الوثائق · ⁦{self.chemin.name}⁩")
        self.setLayoutDirection(Qt.RightToLeft)
        g, _, d, _ = self.page.marges_mm
        self.largeur_contenu = round((self.page.largeur_mm - g - d) * PX_PAR_MM)
        v = QVBoxLayout(self)
        v.setContentsMargins(24, 16, 24, 16)
        v.setSpacing(8)

        def bouton(texte, action, aide="", principal=False, largeur=None):
            b = QPushButton(texte)
            if principal:
                b.setObjectName("principal")
            if aide:
                b.setToolTip(aide)
            if largeur:
                b.setFixedWidth(largeur)
            b.clicked.connect(lambda: action())
            return b

        h = QHBoxLayout()
        h.setSpacing(6)
        self.b_retour = bouton("رجوع", self.revenir_page, "العودة إلى الصفحة التي فُتحت منها الوثيقة")
        h.addWidget(self.b_retour)
        titre = QLabel(self.chemin.stem.split("_", 2)[-1].replace("_", " "))
        titre.setObjectName("titreCarte")
        h.addWidget(titre, 1)
        self.b_modifier = bouton("تعديل الوثيقة", self.basculer_edition, "الكتابة على الورقة وأدوات التنسيق")
        self.b_modifier.setCheckable(True)
        self.b_pdf = bouton("حفظ PDF", self.exporter_pdf, "ملف للقراءة فقط يُرسل بالبريد أو واتساب")
        self.b_image = bouton("حفظ كصورة", self.exporter_image, "صورة لكل صفحة (للنشر أو الإرسال)")
        self.b_imprimer = bouton("طباعة", self.imprimer, "اختيار الطابعة وعدد النسخ ثم الطبع", True)
        for b in (self.b_modifier, self.b_pdf, self.b_image, self.b_imprimer):
            h.addWidget(b)
        v.addLayout(h)

        self.outils = QWidget()
        h = QHBoxLayout(self.outils)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)
        for texte, action, aide in (
                ("تراجع", lambda: self.edit.undo(), "Ctrl+Z"), ("إعادة", lambda: self.edit.redo(), "Ctrl+Y"),
                ("غامق", self.gras, "Ctrl+B"), ("تسطير", self.souligner, "Ctrl+U"),
                ("تكبير الخط", lambda: self.taille(+1), ""), ("تصغير الخط", lambda: self.taille(-1), ""),
                ("يمين", lambda: self.aligner(Qt.AlignRight | Qt.AlignAbsolute), ""),
                ("وسط", lambda: self.aligner(Qt.AlignHCenter), ""),
                ("يسار", lambda: self.aligner(Qt.AlignLeft | Qt.AlignAbsolute), "")):
            h.addWidget(bouton(texte, action, aide))
        h.addStretch()
        self.b_enregistrer = bouton("حفظ التعديلات", self.enregistrer, "تُحفظ بجانب الوثيقة وتُفتح بها في المرة المقبلة",
                                    True)
        h.addWidget(self.b_enregistrer)
        self.b_original = bouton("العودة إلى الأصل", self.revenir, "حذف التعديلات المحفوظة وعرض الوثيقة كما وُلّدت")
        h.addWidget(self.b_original)
        h.addWidget(bouton("معاينة الطبع", self.apercu))
        h.addWidget(bouton("فتح في برنامج الحاسوب", self.ouvrir_externe,
                           "يفتح الملف الأصلي (دون تعديلات هذا المحرر) ببرنامج تحرير النصوص المثبت"))
        v.addWidget(self.outils)
        h = QHBoxLayout()
        h.addStretch()
        self.etat = QLabel()
        self.etat.setObjectName("pastille")
        h.addWidget(self.etat)
        v.addLayout(h)

        self.message = QLabel()
        self.message.setObjectName("message")
        self.message.setWordWrap(True)
        self.message.hide()
        v.addWidget(self.message)

        fond = QFrame()
        fond.setObjectName("fondPapier")
        fond.setStyleSheet("QFrame#fondPapier { background: #8E8E99; border-radius: 8px; }")
        hf = QHBoxLayout(fond)
        hf.setContentsMargins(0, 14, 0, 14)
        self.edit = QTextEdit()
        self.edit.setObjectName("papier")
        self.edit.setStyleSheet("QTextEdit#papier { background: #FFFFFF; color: #000000; border: 1px solid #5C5C66; "
                                "border-radius: 0; selection-background-color: #2E3192; selection-color: #FFFFFF; }")
        self.edit.setLayoutDirection(Qt.RightToLeft)
        self.edit.setAcceptRichText(True)
        self.edit.document().setDocumentMargin(MARGE_ECRAN)
        self.edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.edit.setFixedWidth(self.largeur_contenu + 2 * MARGE_ECRAN + 24)
        hf.addStretch()
        hf.addWidget(self.edit)
        hf.addStretch()
        v.addWidget(fond, 1)

        self.edit.document().modificationChanged.connect(lambda _: self._etat())
        self.charger()
        self.basculer_edition(False)

    # ---------- المعاينة والتحرير ----------
    def basculer_edition(self, actif: bool | None = None) -> None:
        actif = self.b_modifier.isChecked() if actif is None else actif
        self.b_modifier.setChecked(actif)
        self.edit.setReadOnly(not actif)
        self.outils.setVisible(actif)
        self.edit.setTextInteractionFlags(Qt.TextEditorInteraction if actif else
                                          Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        if actif:
            self.edit.setFocus()

    def revenir_page(self) -> None:
        if self.edit.document().isModified():
            self.enregistrer()   # لا تضيع تعديلات المدير بالرجوع
        if self.retour is not None:
            self.retour(self)
        else:
            self.close()

    # ---------- التحميل والحفظ ----------
    def charger(self) -> None:
        f = fichier_modifie(self.chemin)
        self.modifie_sur_disque = f.exists()
        self.edit.setHtml(f.read_text(encoding="utf-8") if self.modifie_sur_disque else self.page.html)
        self.edit.document().setModified(False)
        self.b_original.setEnabled(self.modifie_sur_disque)
        self._etat()

    def _etat(self) -> None:
        if self.edit.document().isModified():
            self.etat.setText("تعديلات غير محفوظة")
        else:
            self.etat.setText("نسخة معدَّلة محفوظة" if self.modifie_sur_disque else "الوثيقة كما وُلّدت")

    def enregistrer(self) -> Path:
        f = fichier_modifie(self.chemin)
        f.write_text(self.edit.toHtml(), encoding="utf-8")
        self.modifie_sur_disque = True
        self.edit.document().setModified(False)
        self.b_original.setEnabled(True)
        self._etat()
        message(self.message, "حُفظت التعديلات. الملف الأصلي لم يتغير.")
        return f

    def revenir(self) -> None:
        fichier_modifie(self.chemin).unlink(missing_ok=True)
        self.charger()
        message(self.message, "عادت الوثيقة كما وُلّدت.")

    def ouvrir_externe(self) -> None:
        try:
            bureautique.ouvrir_externe(self.chemin)
        except OSError as e:
            message(self.message, f"تعذر فتح الملف: {e}", True)

    # ---------- التنسيق ----------
    def _appliquer(self, fmt: QTextCharFormat) -> None:
        c = self.edit.textCursor()
        if not c.hasSelection():
            c.select(QTextCursor.WordUnderCursor)
        c.mergeCharFormat(fmt)
        self.edit.mergeCurrentCharFormat(fmt)

    def gras(self) -> None:
        fmt = QTextCharFormat()
        fmt.setFontWeight(QFont.Weight.Normal if int(self.edit.fontWeight()) > 400 else QFont.Weight.Bold)
        self._appliquer(fmt)

    def souligner(self) -> None:
        fmt = QTextCharFormat()
        fmt.setFontUnderline(not self.edit.fontUnderline())
        self._appliquer(fmt)

    def taille(self, delta: int) -> None:
        actuelle = self.edit.fontPointSize() or self.edit.document().defaultFont().pointSizeF() or 15
        fmt = QTextCharFormat()
        fmt.setFontPointSize(max(6.0, actuelle + delta))
        self._appliquer(fmt)

    def aligner(self, alignement) -> None:
        self.edit.setAlignment(alignement)

    # ---------- الطبع ----------
    def imprimante(self, pdf: Path | None = None) -> QPrinter:
        pr = QPrinter(QPrinter.HighResolution)
        if pdf is not None:   # قبل ضبط الصفحة: تغيير الصيغة يعيد تهيئة إعداداتها
            pr.setOutputFormat(QPrinter.PdfFormat)
            pr.setOutputFileName(str(pdf))
        pr.setPageSize(QPageSize(QPageSize.A4))
        pr.setPageOrientation(QPageLayout.Landscape if self.page.paysage else QPageLayout.Portrait)
        pr.setPageMargins(QMarginsF(*self.page.marges_mm), QPageLayout.Millimeter)
        pr.setDocName(self.chemin.stem)
        return pr

    def rendre(self, pr: QPrinter) -> None:
        """يرسم الوثيقة على الطابعة بنفس عرض السطر الظاهر في المحرر (ما تراه هو ما يُطبع)."""
        doc = self.edit.document().clone(self)
        doc.setDocumentMargin(0)
        rect = pr.pageLayout().paintRect(QPageLayout.Millimeter)
        doc.setPageSize(QSizeF(self.largeur_contenu, self.largeur_contenu * rect.height() / rect.width()))
        doc.print_(pr)
        doc.deleteLater()

    def imprimer(self) -> bool:
        pr = self.imprimante()
        if QPrintDialog(pr, self).exec() != QDialog.Accepted:
            return False
        self.rendre(pr)
        message(self.message, "أُرسلت الوثيقة إلى الطابعة.")
        return True

    def apercu(self) -> None:
        d = QPrintPreviewDialog(self.imprimante(), self)
        d.setLayoutDirection(Qt.RightToLeft)
        d.paintRequested.connect(self.rendre)
        d.exec()

    def pages_images(self, echelle: float = 2.0) -> list[QImage]:
        """كل صفحة صورةً بحجم الورقة (هوامشها بيضاء)، بنفس تقطيع الطبع."""
        doc = self.edit.document().clone(self)
        doc.setDocumentMargin(0)
        g, h_, d, b = (m * PX_PAR_MM for m in self.page.marges_mm)
        larg = self.largeur_contenu
        haut = max(100.0, self.page.hauteur_mm * PX_PAR_MM - h_ - b)
        doc.setPageSize(QSizeF(larg, haut))
        images = []
        for i in range(max(1, doc.pageCount())):
            img = QImage(int((larg + g + d) * echelle), int((haut + h_ + b) * echelle), QImage.Format_RGB32)
            img.fill(QColor("white"))
            p = QPainter(img)
            p.setRenderHint(QPainter.Antialiasing)
            p.setRenderHint(QPainter.TextAntialiasing)
            p.scale(echelle, echelle)
            p.translate(g, h_ - i * haut)
            doc.drawContents(p, QRectF(0, i * haut, larg, haut))
            p.end()
            images.append(img)
        doc.deleteLater()
        return images

    def exporter_image(self, cible: Path | None = None) -> list[Path] | None:
        if cible is None:
            nom, _ = QFileDialog.getSaveFileName(self, "حفظ كصورة", str(self.chemin.with_suffix(".png")),
                                                 "صورة (*.png *.jpg)")
            if not nom:
                return None
            cible = Path(nom)
        cible = Path(cible)
        if cible.suffix.lower() not in (".png", ".jpg", ".jpeg"):
            cible = cible.with_suffix(".png")
        chemins = []
        for i, img in enumerate(self.pages_images()):
            c = cible if i == 0 else cible.with_name(f"{cible.stem}_{i + 1}{cible.suffix}")
            img.save(str(c))
            chemins.append(c)
        message(self.message, f"حُفظت {len(chemins)} صورة: ⁦{chemins[0].name}⁩" if len(chemins) > 1
                else f"حُفظت الصورة: ⁦{chemins[0].name}⁩")
        return chemins

    def exporter_pdf(self, cible: Path | None = None) -> Path | None:
        if cible is None:
            nom, _ = QFileDialog.getSaveFileName(self, "حفظ الوثيقة", str(self.chemin.with_suffix(".pdf")), "PDF (*.pdf)")
            if not nom:
                return None
            cible = Path(nom)
        self.rendre(self.imprimante(cible))
        message(self.message, f"حُفظ الملف: ⁦{Path(cible).name}⁩")
        return Path(cible)
