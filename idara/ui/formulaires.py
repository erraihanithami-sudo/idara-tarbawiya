"""نماذج الإدخال المشتركة بين معالج أول تشغيل وصفحة تعديل الإعداد."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QDateEdit, QFileDialog, QGridLayout,
                               QHBoxLayout, QLabel, QLineEdit, QPushButton, QRadioButton,
                               QVBoxLayout, QWidget)

from idara.services.etablissement import MILIEUX, Directeur, Etablissement


def champ(texte_aide: str = "", ltr: bool = False) -> QLineEdit:
    c = QLineEdit()
    if texte_aide:
        c.setPlaceholderText(texte_aide)
    if ltr:
        c.setLayoutDirection(Qt.LeftToRight)
        c.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    return c


def etiquette(texte: str, pour: QWidget | None = None) -> QLabel:
    l = QLabel(texte)
    l.setStyleSheet("font-weight: 500;")
    if pour is not None:
        l.setBuddy(pour)
    return l


class Grille(QWidget):
    """شبكة من عمودين: تسمية فوق كل حقل."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.g = QGridLayout(self)
        self.g.setContentsMargins(0, 0, 0, 0)
        self.g.setHorizontalSpacing(24)
        self.g.setVerticalSpacing(6)
        self._ligne = 0
        self._col = 0

    def ajouter(self, texte: str, widget: QWidget, pleine_largeur: bool = False) -> QWidget:
        if pleine_largeur and self._col == 1:
            self._ligne += 2
            self._col = 0
        span = 2 if pleine_largeur else 1
        self.g.addWidget(etiquette(texte, widget), self._ligne, self._col, 1, span)
        self.g.addWidget(widget, self._ligne + 1, self._col, 1, span)
        if pleine_largeur or self._col == 1:
            self._ligne += 2
            self._col = 0
        else:
            self._col = 1
        self.g.setRowMinimumHeight(self._ligne, 14)
        return widget


class FormEtablissement(QWidget):
    """الخطوة 1: تعريف المؤسسة."""

    def __init__(self, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        g = Grille()
        self.nom_ar = g.ajouter("اسم المؤسسة بالعربية *", champ())
        self.nom_fr = g.ajouter("اسم المؤسسة بالفرنسية (لشهادة العطلة)", champ(ltr=True))
        self.code = g.ajouter("رمز المؤسسة", champ(ltr=True))
        self.commune_ar = g.ajouter("الجماعة", champ())
        self.direction_ar = g.ajouter("المديرية الإقليمية *", champ("مثال: بركان"))
        self.academie_ar = g.ajouter("الأكاديمية الجهوية *", champ("مثال: جهة الشرق"))
        # وسط المؤسسة: يحدد واجب التأمين المدرسي في تدبير التسجيلات (طلب المدير 2026-11-07)
        self.milieu = QComboBox()
        self.milieu.addItem("— غير محدد —", "")
        for k, lib in MILIEUX.items():
            self.milieu.addItem(lib, k)
        g.ajouter("وسط المؤسسة (لواجب التأمين)", self.milieu)
        v.addWidget(g)

        v.addSpacing(10)
        v.addWidget(etiquette("نوع المؤسسة"))
        ligne = QHBoxLayout()
        self.r_independant = QRadioButton("مؤسسة مستقلة")
        self.r_groupe = QRadioButton("مجموعة مدرسية")
        self.r_groupe.setChecked(True)
        self._type = QButtonGroup(self)
        self._type.addButton(self.r_independant)
        self._type.addButton(self.r_groupe)
        ligne.addWidget(self.r_independant)
        ligne.addWidget(self.r_groupe)
        ligne.addStretch()
        v.addLayout(ligne)
        self.pionniere = QCheckBox("مؤسسة رائدة (لوحة القيادة: نسبة المتحكمين في التعلمات الأساس)")
        v.addWidget(self.pionniere)

        self.bloc_unites = QWidget()
        bu = QVBoxLayout(self.bloc_unites)
        bu.setContentsMargins(0, 6, 0, 0)
        self.unites = champ("أسماء الوحدات مفصولة بفاصلة")
        bu.addWidget(etiquette("الوحدات المدرسية التابعة (اختياري)", self.unites))
        bu.addWidget(self.unites)
        aide = QLabel("تُستعمل فقط لربط كل قسم بوحدته.")
        aide.setObjectName("etiquette")
        bu.addWidget(aide)
        v.addWidget(self.bloc_unites)
        self.r_groupe.toggled.connect(self.bloc_unites.setVisible)

    def lire(self, base: Etablissement | None = None) -> Etablissement:
        e = base or Etablissement()
        e.nom_ar, e.nom_fr, e.code_etab = self.nom_ar.text(), self.nom_fr.text(), self.code.text()
        e.commune_ar = self.commune_ar.text()
        e.direction_ar, e.academie_ar = self.direction_ar.text(), self.academie_ar.text()
        e.type_etab = "groupe" if self.r_groupe.isChecked() else "independant"
        e.est_pionniere = "1" if self.pionniere.isChecked() else ""
        e.milieu = self.milieu.currentData() or ""
        return e

    def liste_unites(self) -> list[str]:
        if not self.r_groupe.isChecked():
            return []
        return [u for u in self.unites.text().replace("،", ",").split(",")]

    def remplir(self, e: Etablissement, unites: list[str] | None = None) -> None:
        self.nom_ar.setText(e.nom_ar)
        self.nom_fr.setText(e.nom_fr)
        self.code.setText(e.code_etab)
        self.commune_ar.setText(e.commune_ar)
        self.direction_ar.setText(e.direction_ar)
        self.academie_ar.setText(e.academie_ar)
        (self.r_groupe if e.type_etab == "groupe" else self.r_independant).setChecked(True)
        self.bloc_unites.setVisible(e.type_etab == "groupe")
        self.pionniere.setChecked(bool(e.est_pionniere))
        self.milieu.setCurrentIndex(max(0, self.milieu.findData(e.milieu)))
        self.unites.setText("، ".join(unites or []))


class FormDirecteur(QWidget):
    """الخطوة 2: المدير."""

    def __init__(self, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        g = Grille()
        self.nom_ar = g.ajouter("النسب بالعربية *", champ())
        self.prenom_ar = g.ajouter("الاسم بالعربية *", champ())
        self.nom_fr = g.ajouter("النسب بالفرنسية (لشهادة العطلة)", champ(ltr=True))
        self.prenom_fr = g.ajouter("الاسم بالفرنسية (لشهادة العطلة)", champ(ltr=True))
        self.ppr = g.ajouter("رقم التأجير", champ(ltr=True))
        self.date_aff = QDateEdit()
        self.date_aff.setCalendarPopup(True)
        self.date_aff.setDisplayFormat("dd/MM/yyyy")
        self.date_aff.setDate(QDate.currentDate())
        g.ajouter("تاريخ التعيين بالمؤسسة", self.date_aff)
        v.addWidget(g)
        v.addSpacing(10)
        v.addWidget(etiquette("النوع (لصيغ التذكير والتأنيث في الوثائق)"))
        ligne = QHBoxLayout()
        self.r_m = QRadioButton("ذكر")
        self.r_f = QRadioButton("أنثى")
        self.r_m.setChecked(True)
        grp = QButtonGroup(self)
        grp.addButton(self.r_m)
        grp.addButton(self.r_f)
        ligne.addWidget(self.r_m)
        ligne.addWidget(self.r_f)
        ligne.addStretch()
        v.addLayout(ligne)

    def lire(self) -> Directeur:
        return Directeur(nom_ar=self.nom_ar.text(), prenom_ar=self.prenom_ar.text(),
                         nom_fr=self.nom_fr.text(), prenom_fr=self.prenom_fr.text(),
                         sexe="F" if self.r_f.isChecked() else "M", ppr=self.ppr.text(),
                         date_affectation=self.date_aff.date().toString("yyyy-MM-dd"))

    def remplir(self, d) -> None:
        self.nom_ar.setText(d["nom_ar"] or "")
        self.prenom_ar.setText(d["prenom_ar"] or "")
        self.nom_fr.setText(d["nom_fr"] or "")
        self.prenom_fr.setText(d["prenom_fr"] or "")
        self.ppr.setText(d["ppr"] or "")
        (self.r_f if d["sexe"] == "F" else self.r_m).setChecked(True)
        if d["mandat_debut"]:
            self.date_aff.setDate(QDate.fromString(d["mandat_debut"], "yyyy-MM-dd"))


class SelecteurFichier(QWidget):
    def __init__(self, titre: str, filtre: str = "صور (*.png *.jpg *.jpeg *.bmp)", parent=None):
        super().__init__(parent)
        self.titre, self.filtre = titre, filtre
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        self.chemin = champ("لم يُختر أي ملف", ltr=True)
        self.chemin.setReadOnly(True)
        b = QPushButton("اختيار...")
        b.clicked.connect(self._choisir)
        h.addWidget(self.chemin, 1)
        h.addWidget(b)

    def _choisir(self):
        f, _ = QFileDialog.getOpenFileName(self, self.titre, "", self.filtre)
        if f:
            self.chemin.setText(f)

    def valeur(self) -> str:
        return self.chemin.text().strip()


class FormIdentite(QWidget):
    """الخطوة 3: الهوية البصرية للوثائق."""

    def __init__(self, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        g = Grille()
        self.ville_ar = g.ajouter("مدينة التحرير بالعربية", champ("كما في: بركان في ..."))
        self.ville_fr = g.ajouter("مدينة التحرير بالفرنسية (لشهادة العطلة)", champ("Fait à ...", ltr=True))
        self.telephone = g.ajouter("الهاتف المهني", champ(ltr=True))
        self.adresse = g.ajouter("العنوان", champ())
        self.logo = g.ajouter("الترويسة (صورة تُوضع أعلى الوثائق)", SelecteurFichier("اختيار صورة الترويسة"), pleine_largeur=True)
        self.filigrane = g.ajouter("العلامة المائية (اختياري)", SelecteurFichier("اختيار العلامة المائية"),
                                   pleine_largeur=True)
        # التذييل: نص أو صورة من الحاسوب (طلب المدير 2026-11-07)
        ligne = QWidget()
        hl = QHBoxLayout(ligne)
        hl.setContentsMargins(0, 0, 0, 0)
        self.r_pied_texte = QRadioButton("نص")
        self.r_pied_image = QRadioButton("صورة")
        self.r_pied_texte.setChecked(True)
        self._mode_pied = QButtonGroup(self)
        self._mode_pied.addButton(self.r_pied_texte)
        self._mode_pied.addButton(self.r_pied_image)
        hl.addWidget(self.r_pied_texte)
        hl.addWidget(self.r_pied_image)
        hl.addStretch()
        g.ajouter("التذييل", ligne, pleine_largeur=True)
        self.pied = g.ajouter("نص التذييل", champ("العنوان والهاتف كما في أسفل الوثائق"),
                              pleine_largeur=True)
        self.pied_image = g.ajouter("صورة التذييل (تُوضع في الوسط أسفل الوثائق)",
                                    SelecteurFichier("اختيار صورة التذييل"), pleine_largeur=True)
        self.l_pied_actuel = QLabel()
        self.l_pied_actuel.setObjectName("etiquette")
        g.ajouter("", self.l_pied_actuel, pleine_largeur=True)
        self.r_pied_image.toggled.connect(self._maj_pied)
        v.addWidget(g)
        self._maj_pied()
        note = QLabel("تعوّض الترويسةُ والعلامةُ المائية ونصُّ التذييل ما في قوالبك آلياً في كل الوثائق المولدة. "
                      "أفضل ترويسة: صورة عريضة (العرض 5 أضعاف الارتفاع تقريباً). اترك الحقل فارغاً لإبقاء الحالي.")
        note.setObjectName("etiquette")
        note.setWordWrap(True)
        v.addWidget(note)

    def _maj_pied(self, _=None) -> None:
        image = self.r_pied_image.isChecked()
        for l in self.findChildren(QLabel):   # عناوين الحقول (buddy) تتبع حقولها
            if l.buddy() in (self.pied_image, self.l_pied_actuel):
                l.setVisible(image)
            elif l.buddy() is self.pied:
                l.setVisible(not image)
        for w in (self.pied_image, self.l_pied_actuel):
            w.setVisible(image)
        self.pied.setVisible(not image)

    def mode_pied(self) -> str:
        return "image" if self.r_pied_image.isChecked() else "texte"

    def appliquer(self, e: Etablissement) -> tuple[str, str]:
        e.ville_redaction_ar, e.ville_redaction_fr = self.ville_ar.text(), self.ville_fr.text()
        e.telephone, e.adresse, e.pied_page = self.telephone.text(), self.adresse.text(), self.pied.text()
        return self.logo.valeur(), self.filigrane.valeur()

    def remplir(self, e: Etablissement) -> None:
        self.ville_ar.setText(e.ville_redaction_ar)
        self.ville_fr.setText(e.ville_redaction_fr)
        self.telephone.setText(e.telephone)
        self.adresse.setText(e.adresse)
        self.pied.setText(e.pied_page)
        (self.r_pied_image if e.pied_image_path else self.r_pied_texte).setChecked(True)
        self.l_pied_actuel.setText("الصورة الحالية: " + Path(e.pied_image_path).name if e.pied_image_path else
                                   "لم تُختر صورة بعد.")
        self._maj_pied()
