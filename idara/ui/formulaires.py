"""نماذج الإدخال المشتركة بين معالج أول تشغيل وصفحة تعديل الإعداد."""

from __future__ import annotations

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (QButtonGroup, QDateEdit, QFileDialog, QGridLayout,
                               QHBoxLayout, QLabel, QLineEdit, QPushButton, QRadioButton,
                               QVBoxLayout, QWidget)

from idara.services.etablissement import Directeur, Etablissement


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
        self.nom_fr = g.ajouter("اسم المؤسسة بالفرنسية", champ(ltr=True))
        self.code = g.ajouter("رمز المؤسسة", champ(ltr=True))
        self.commune_ar = g.ajouter("الجماعة", champ())
        self.direction_ar = g.ajouter("المديرية الإقليمية *", champ("مثال: بركان"))
        self.academie_ar = g.ajouter("الأكاديمية الجهوية *", champ("مثال: جهة الشرق"))
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
        self.nom_fr = g.ajouter("النسب بالفرنسية", champ(ltr=True))
        self.prenom_fr = g.ajouter("الاسم بالفرنسية", champ(ltr=True))
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
        self.ville_fr = g.ajouter("مدينة التحرير بالفرنسية", champ("Fait à ...", ltr=True))
        self.telephone = g.ajouter("الهاتف المهني", champ(ltr=True))
        self.adresse = g.ajouter("العنوان", champ())
        self.logo = g.ajouter("الترويسة (صورة تُوضع أعلى الوثائق)", SelecteurFichier("اختيار صورة الترويسة"), pleine_largeur=True)
        self.filigrane = g.ajouter("العلامة المائية (اختياري)", SelecteurFichier("اختيار العلامة المائية"),
                                   pleine_largeur=True)
        self.pied = g.ajouter("نص التذييل", champ("العنوان والهاتف كما في أسفل الوثائق"),
                              pleine_largeur=True)
        v.addWidget(g)
        note = QLabel("تعوّض الترويسةُ والعلامةُ المائية ونصُّ التذييل ما في قوالبك آلياً في كل الوثائق المولدة. "
                      "أفضل ترويسة: صورة عريضة (العرض 5 أضعاف الارتفاع تقريباً). اترك الحقل فارغاً لإبقاء الحالي.")
        note.setObjectName("etiquette")
        note.setWordWrap(True)
        v.addWidget(note)

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
