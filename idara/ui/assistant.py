"""معالج أول تشغيل: أربع خطوات، ولا يُكتب شيء قبل الضغط على "إنهاء"."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel,
                               QMessageBox, QPushButton, QScrollArea, QStackedWidget,
                               QVBoxLayout, QWidget)

from idara.data.db import ouvrir_base
from idara.data.dossier import DossierDonnees
from idara.services import annee as annee_srv
from idara.services import config as config_srv
from idara.services import sauvegarde
from idara.services.etablissement import (ConfigurationInitiale, ErreurValidation,
                                          appliquer_configuration_initiale,
                                          configuration_complete)
from idara.ui import theme
from idara.ui.formulaires import (FormDirecteur, FormEtablissement, FormIdentite, champ,
                                  etiquette)
from idara import marque
from idara.ui.zellige import FondZellige, LogoMarque

ETAPES = ["المؤسسة", "المدير", "الهوية البصرية للوثائق", "مجلد البيانات والسنة الدراسية"]
TITRES = ["تعريف المؤسسة", "المدير", "الهوية البصرية للوثائق", "مجلد البيانات والسنة الدراسية"]


class FormDonnees(QWidget):
    """الخطوة 4: مكان البيانات والسنة الدراسية."""

    def __init__(self, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(etiquette("مجلد بيانات المؤسسة"))
        h = QHBoxLayout()
        self.dossier = champ(ltr=True)
        self.dossier.setText(str(config_srv.dossier_donnees_par_defaut()))
        b = QPushButton("تغيير...")
        b.clicked.connect(self._choisir)
        h.addWidget(self.dossier, 1)
        h.addWidget(b)
        v.addLayout(h)
        aide = QLabel("كل شيء يُحفظ في هذا المجلد: القاعدة والقوالب والأرشيف والنسخ الاحتياطية. "
                      "نقله إلى حاسوب آخر ينقل كل شيء.")
        aide.setObjectName("etiquette")
        aide.setWordWrap(True)
        v.addWidget(aide)
        v.addSpacing(16)
        v.addWidget(etiquette("السنة الدراسية الجارية"))
        self.annee = QComboBox()
        courante = annee_srv.libelle_pour_date()
        debut = int(courante[:4])
        for a in (debut - 1, debut, debut + 1):
            self.annee.addItem(f"{a}/{a + 1}")
        self.annee.setCurrentText(courante)
        v.addWidget(self.annee)
        v.addSpacing(16)
        self.bouton_import = QPushButton("لدي نسخة مصدّرة من حاسوب آخر...")
        v.addWidget(self.bouton_import, 0, Qt.AlignRight)

    def _choisir(self):
        d = QFileDialog.getExistingDirectory(self, "اختيار مجلد البيانات", self.dossier.text())
        if d:
            p = Path(d)
            if p.name != config_srv.NOM_DOSSIER_DONNEES and not (p / "data.db").exists():
                p = p / config_srv.NOM_DOSSIER_DONNEES
            self.dossier.setText(str(p))


class AssistantPremierLancement(QWidget):
    termine = Signal(object)  # DossierDonnees

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("fond")
        self.setWindowTitle("الإدارة التربوية — الإعداد الأول")
        racine = QHBoxLayout(self)
        racine.setContentsMargins(0, 0, 0, 0)
        racine.setSpacing(0)

        # اللوحة الجانبية: الترحيب والخطوات، بخلفية زليج خافتة
        cote = FondZellige(couleur_fond=theme.BLANC)
        cote.setFixedWidth(360)
        cv = QVBoxLayout(cote)
        cv.setContentsMargins(36, 44, 36, 36)
        cv.setSpacing(14)
        cv.addWidget(LogoMarque(64, inverse=False))
        t = QLabel(f"مرحباً بكم في «{marque.NOM_COURT}»")
        t.setObjectName("titrePage")
        t.setWordWrap(True)
        cv.addWidget(t)
        p = QLabel("تُدخل هذه المعلومات مرة واحدة، وتُستعمل آلياً في كل الوثائق. "
                   "يمكن تعديلها لاحقاً من إعداد المؤسسة.")
        p.setWordWrap(True)
        cv.addWidget(p)
        cv.addSpacing(16)
        self.puces = []
        for i, nom in enumerate(ETAPES):
            l = QLabel(f"  {i + 1}.  {nom}")
            l.setMinimumHeight(44)
            cv.addWidget(l)
            self.puces.append(l)
        cv.addStretch()
        racine.addWidget(cote)

        # المحتوى
        droite = QWidget()
        dv = QVBoxLayout(droite)
        dv.setContentsMargins(48, 40, 48, 32)
        dv.setSpacing(14)
        self.numero = QLabel()
        self.numero.setObjectName("sousTitre")
        self.titre = QLabel()
        self.titre.setObjectName("titrePage")
        dv.addWidget(self.numero)
        dv.addWidget(self.titre)

        self.f_etab, self.f_dir = FormEtablissement(), FormDirecteur()
        self.f_id, self.f_donnees = FormIdentite(), FormDonnees()
        self.f_donnees.bouton_import.clicked.connect(self._importer_export)
        self.pile = QStackedWidget()
        for f in (self.f_etab, self.f_dir, self.f_id, self.f_donnees):
            carte = QFrame()
            carte.setObjectName("carte")
            cl = QVBoxLayout(carte)
            cl.setContentsMargins(28, 24, 28, 24)
            cl.addWidget(f)
            cl.addStretch()
            zone = QScrollArea()
            zone.setWidgetResizable(True)
            zone.setFrameShape(QFrame.NoFrame)
            zone.setWidget(carte)
            self.pile.addWidget(zone)
        dv.addWidget(self.pile, 1)

        self.erreur = QLabel()
        self.erreur.setObjectName("erreur")
        self.erreur.setWordWrap(True)
        self.erreur.hide()
        dv.addWidget(self.erreur)

        boutons = QHBoxLayout()
        self.b_suivant = QPushButton()
        self.b_suivant.setObjectName("principal")
        self.b_suivant.clicked.connect(self.suivant)
        self.b_precedent = QPushButton("السابق")
        self.b_precedent.clicked.connect(self.precedent)
        boutons.addWidget(self.b_suivant)
        boutons.addWidget(self.b_precedent)
        boutons.addStretch()
        dv.addLayout(boutons)
        racine.addWidget(droite, 1)
        # الرسالة تختفي بمجرد أن يبدأ المدير التصحيح
        from PySide6.QtWidgets import QLineEdit
        for c in self.findChildren(QLineEdit):
            c.textEdited.connect(lambda _t: self.erreur.hide())
        self._aller(0)

    # ---------- التنقل ----------

    def _aller(self, i: int) -> None:
        self.pile.setCurrentIndex(i)
        self.numero.setText(f"الخطوة {i + 1} من {len(ETAPES)}")
        self.titre.setText(TITRES[i])
        self.b_precedent.setEnabled(i > 0)
        self.b_suivant.setText("إنهاء الإعداد" if i == len(ETAPES) - 1 else
                               f"التالي: {ETAPES[i + 1]}")
        for j, l in enumerate(self.puces):
            actif = j == i
            l.setStyleSheet(
                f"background:{theme.VERT_CLAIR}; color:{theme.VERT_FONCE}; font-weight:600;"
                " border-radius:8px;" if actif else
                (f"color:{theme.VERT_FONCE};" if j < i else f"color:{theme.GRIS};"))
        self.erreur.hide()

    def etape(self) -> int:
        return self.pile.currentIndex()

    def precedent(self) -> None:
        if self.etape() > 0:
            self._aller(self.etape() - 1)

    def _montrer_erreur(self, msg: str) -> None:
        self.erreur.setText(msg)
        self.erreur.show()

    def _valider_etape(self, i: int) -> None:
        if i == 0:
            self.f_etab.lire().valider()
        elif i == 1:
            self.f_dir.lire().valider()
        elif i == 3:
            if not self.f_donnees.dossier.text().strip():
                raise ErreurValidation("اختر مجلد البيانات.")

    def suivant(self) -> None:
        try:
            self._valider_etape(self.etape())
        except ErreurValidation as e:
            self._montrer_erreur(str(e))
            return
        if self.etape() < len(ETAPES) - 1:
            self._aller(self.etape() + 1)
        else:
            self.terminer()

    # ---------- الإنهاء ----------

    def configuration(self) -> ConfigurationInitiale:
        etab = self.f_etab.lire()
        logo, filigrane = self.f_id.appliquer(etab)
        return ConfigurationInitiale(etablissement=etab, directeur=self.f_dir.lire(),
                                     annee=self.f_donnees.annee.currentText(),
                                     unites=self.f_etab.liste_unites(),
                                     logo_source=logo, filigrane_source=filigrane)

    def terminer(self) -> DossierDonnees | None:
        dossier = DossierDonnees(Path(self.f_donnees.dossier.text().strip()))
        try:
            dossier.preparer()
            conn = ouvrir_base(dossier.base)
            try:
                if configuration_complete(conn):
                    # مجلد مُعدّ سابقاً: لا نكتب فوق بياناته
                    pass
                else:
                    appliquer_configuration_initiale(conn, dossier, self.configuration())
            finally:
                conn.close()
        except ErreurValidation as e:
            self._montrer_erreur(str(e))
            return None
        except OSError as e:
            self._montrer_erreur(f"تعذر الكتابة في المجلد المختار: {e}")
            return None
        config_srv.ecrire_config(dossier_donnees=str(dossier.racine))
        self.termine.emit(dossier)
        return dossier

    def _importer_export(self) -> None:
        f, _ = QFileDialog.getOpenFileName(self, "اختيار النسخة المصدّرة", "", "نسخة مصدّرة (*.zip)")
        if not f:
            return
        dossier = DossierDonnees(Path(self.f_donnees.dossier.text().strip()))
        try:
            sauvegarde.importer_export(dossier, Path(f))
        except (sauvegarde.ErreurSauvegarde, OSError) as e:
            QMessageBox.warning(self, "تعذر الاستيراد", str(e))
            return
        config_srv.ecrire_config(dossier_donnees=str(dossier.racine))
        self.termine.emit(dossier)
