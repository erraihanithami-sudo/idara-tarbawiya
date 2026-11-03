"""النافذة الرئيسية: القائمة الجانبية والصفحات."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (QButtonGroup, QFileDialog, QFrame, QGridLayout, QHBoxLayout,
                               QLabel, QMainWindow, QMessageBox, QPushButton, QScrollArea,
                               QStackedWidget, QTabWidget, QVBoxLayout, QWidget)

from idara import NOM_APPLICATION, __version__
from idara.data.db import ouvrir_base
from idara.data.dossier import DossierDonnees
from idara.services import annee as annee_srv
from idara.services import etablissement as etab_srv
from idara.services import import_eleves as imp
from idara.services import sauvegarde
from idara.services.etablissement import ErreurValidation
from idara.services.textes import date_longue_ar
from idara.ui import icones, theme
from idara.ui.composants import carte, entete, page_defilante
from idara.ui.formulaires import FormDirecteur, FormEtablissement, FormIdentite
from idara.ui.page_documents import PageDocuments
from idara.ui.page_import import PageImport
from idara.ui.page_eleves import PageEleves
from idara.ui.page_anciens import PageAnciens
from idara.ui.page_personnel import PagePersonnel
from idara.ui.page_fa import PageFa
from idara.ui.page_mouvements import PageMouvements
from idara.ui.page_comportement import PageComportement
from idara.ui.page_conseils import PageConseils
from idara.ui.page_associations import PageAssociations
from idara.ui.page_achats import PageAchats
from idara.ui.page_conseils_etab import PageConseilsEtab
from idara.ui.page_pedagogie import PagePerformance, PageRiyada, PageTarl, PageVieScolaire
from idara.ui.page_conges import PageConges, PageSortants
from idara.ui.zellige import BandeZellige, FondZellige, LogoEtoile


class PageTableauBord(QWidget):
    def __init__(self, fenetre: "FenetrePrincipale"):
        super().__init__()
        self.f = fenetre
        self.externe = QVBoxLayout(self)
        self.externe.setContentsMargins(0, 0, 0, 0)
        self.contenu = None
        self.rafraichir()

    def rafraichir(self) -> None:
        if self.contenu is not None:
            self.externe.removeWidget(self.contenu)
            self.contenu.hide()
            self.contenu.setParent(None)
            self.contenu.deleteLater()
        self.contenu = QWidget()
        self.v = QVBoxLayout(self.contenu)
        self.v.setContentsMargins(40, 32, 40, 32)
        self.v.setSpacing(20)
        self.externe.addWidget(self.contenu)
        conn = self.f.conn
        a = annee_srv.annee_courante(conn)
        self.v.addWidget(entete("لوحة القيادة",
                                f"السنة الدراسية {a['libelle'] if a else '—'} · {date_longue_ar(date.today())}"))
        n_eleves = conn.execute(
            "SELECT COUNT(*) FROM inscription WHERE annee_id=? AND statut IN ('inscrit','arrive')",
            (a["id"] if a else -1,)).fetchone()[0]
        n_classes = conn.execute("SELECT COUNT(*) FROM classe WHERE annee_id=?",
                                 (a["id"] if a else -1,)).fetchone()[0]
        n_pers = conn.execute(
            "SELECT COUNT(*) FROM personnel WHERE statut='actif' AND categorie<>'directeur'").fetchone()[0]
        sv = sauvegarde.lister_sauvegardes(self.f.dossier)
        derniere = sv[-1].name[len(sauvegarde.PREFIXE):len(sauvegarde.PREFIXE) + 8] if sv else ""
        derniere = f"{derniere[6:8]}/{derniere[4:6]}/{derniere[:4]}" if derniere else "لا توجد بعد"

        grille = QGridLayout()
        grille.setSpacing(16)
        for i, (lib, val, note) in enumerate([
                ("عدد التلاميذ", str(n_eleves), "المسجلون هذه السنة"),
                ("الأقسام", str(n_classes), ""),
                ("الموظفون", str(n_pers), "دون المدير"),
                ("آخر نسخة احتياطية", derniere, f"{len(sv)} نسخة محفوظة")]):
            c, cv = carte()
            e = QLabel(lib)
            e.setObjectName("etiquette")
            ch = QLabel(val)
            ch.setObjectName("chiffre")
            cv.addWidget(e)
            cv.addWidget(ch)
            if note:
                nl = QLabel(note)
                nl.setObjectName("etiquette")
                cv.addWidget(nl)
            grille.addWidget(c, 0, i)
        self.v.addLayout(grille)

        # التوزيع حسب القسم
        repartition = conn.execute(
            "SELECT c.code, COUNT(i.id) AS n FROM classe c LEFT JOIN inscription i ON i.classe_id=c.id "
            "AND i.statut IN ('inscrit','arrive') WHERE c.annee_id=? GROUP BY c.id ORDER BY c.code",
            (a["id"] if a else -1,)).fetchall()
        if repartition:
            c, cv = carte("التوزيع حسب القسم")
            maxi = max(r["n"] for r in repartition) or 1
            for r in repartition:
                ligne = QHBoxLayout()
                nom = QLabel(r["code"])
                nom.setMinimumWidth(160)
                barre = QFrame()
                barre.setFixedHeight(10)
                barre.setFixedWidth(max(4, int(420 * r["n"] / maxi)))
                barre.setStyleSheet(f"background:{theme.VERT}; border-radius:5px;")
                ligne.addWidget(nom)
                ligne.addWidget(barre)
                ligne.addWidget(QLabel(str(r["n"])))
                ligne.addStretch()
                cv.addLayout(ligne)
            self.v.addWidget(c)

        # التنبيهات المفيدة فقط
        alertes = []
        n_niv = len(imp.niveaux_a_confirmer(conn))
        if n_niv:
            alertes.append((f"مستوى {n_niv} تلميذاً بانتظار تأكيدك (أقسام مشتركة)",
                            "الاستيراد من مسار"))
        n_lieu = conn.execute(
            "SELECT COUNT(*) FROM inscription i JOIN eleve e ON e.id=i.eleve_id WHERE i.annee_id=? "
            "AND i.statut IN ('inscrit','arrive') AND e.lieu_naissance_id IS NULL",
            (a["id"] if a else -1,)).fetchone()[0]
        if n_lieu:
            alertes.append((f"مكان الازدياد غير مسجل لـ {n_lieu} تلميذ (يلزم قبل توليد وثائقهم)", None))
        if n_eleves == 0:
            alertes.append(("لا يوجد تلاميذ بعد: ابدأ باستيراد لوائح مسار", "الاستيراد من مسار"))
        if alertes:
            c, cv = carte("تنبيهات")
            for texte, cible in alertes:
                ligne = QHBoxLayout()
                l = QLabel(texte)
                l.setWordWrap(True)
                ligne.addWidget(l, 1)
                if cible:
                    b = QPushButton("فتح")
                    b.clicked.connect(lambda _=False, c=cible: self.f.aller_a(c))
                    ligne.addWidget(b)
                cv.addLayout(ligne)
            self.v.addWidget(c)
        self.v.addStretch()


class PageEtablissement(QWidget):
    def __init__(self, fenetre: "FenetrePrincipale"):
        super().__init__()
        self.f = fenetre
        v = QVBoxLayout(self)
        v.setContentsMargins(40, 32, 40, 32)
        v.setSpacing(20)
        v.addWidget(entete("إعداد المؤسسة", "أي تعديل هنا يظهر في كل الوثائق الجديدة."))
        self.f_etab, self.f_dir, self.f_id = FormEtablissement(), FormDirecteur(), FormIdentite()
        for titre, form in (("المؤسسة", self.f_etab), ("المدير", self.f_dir),
                            ("الهوية البصرية للوثائق", self.f_id)):
            c, cv = carte(titre)
            cv.addWidget(form)
            v.addWidget(c)
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.hide()
        v.addWidget(self.message)
        h = QHBoxLayout()
        b = QPushButton("حفظ التعديلات")
        b.setObjectName("principal")
        b.clicked.connect(self.enregistrer)
        h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        v.addStretch()
        self.charger()

    def charger(self) -> None:
        conn = self.f.conn
        e = etab_srv.lire_etablissement(conn)
        if e:
            self.f_etab.remplir(e, etab_srv.unites(conn))
            self.f_id.remplir(e)
        d = etab_srv.directeur_actuel(conn)
        if d:
            self.f_dir.remplir(d)

    def enregistrer(self) -> None:
        conn = self.f.conn
        try:
            e = self.f_etab.lire(etab_srv.lire_etablissement(conn))
            logo, filigrane = self.f_id.appliquer(e)
            if logo:
                e.logo_path = etab_srv.importer_image(self.f.dossier, logo, "logo")
            if filigrane:
                e.filigrane_path = etab_srv.importer_image(self.f.dossier, filigrane, "filigrane")
            e.valider()
            d = self.f_dir.lire()
            d.valider()
            etab_srv.enregistrer_etablissement(conn, e)
            etab_srv.enregistrer_directeur(conn, d)
            if e.type_etab == "groupe":
                etab_srv.definir_unites(conn, self.f_etab.liste_unites())
        except ErreurValidation as ex:
            self.message.setObjectName("erreur")
            self.message.setText(str(ex))
        else:
            self.message.setObjectName("info")
            self.message.setText("حُفظت التعديلات.")
            self.f.rafraichir_entete()
        self.message.setStyleSheet("")
        self.message.style().unpolish(self.message)
        self.message.style().polish(self.message)
        self.message.show()


class PageAVenir(QWidget):
    """قسم مخطط له: ما سيضمه، وما يلزم من المدير لإنجازه."""

    def __init__(self, titre: str, contenu: list[str], besoins: list[str]):
        super().__init__()
        v = QVBoxLayout(self)
        v.setContentsMargins(40, 32, 40, 32)
        v.setSpacing(16)
        v.addWidget(entete(titre, "قسم مخطط له، لم يُبرمج بعد."))
        for t, lignes in (("ما سيضمه", contenu), ("ما أحتاجه منك لإنجازه", besoins)):
            if not lignes:
                continue
            c, cv = carte(t)
            for x in lignes:
                l = QLabel("•  " + x)
                l.setWordWrap(True)
                cv.addWidget(l)
            v.addWidget(c)
        v.addStretch()


# الأقسام الرئيسية وفروعها (ترتيب المدير 2026-11-03). كل فرع: (اسم الصفحة الداخلي، العنوان في القائمة).
# الفروع غير المبرمجة بعد تفتح صفحة «قريباً» (A_VENIR). تظهر الفروع تحت القسم عند الضغط عليه وتختفي بالضغطة الثانية.
# الموارد البشرية والمراسلات والإعدادات لم ترد في ترتيب المدير، فأُبقيت أقساماً رئيسية بعده حتى لا تضيع وظائفها.
SECTIONS = [
    ("القيادة والتدبير", [("لوحة القيادة", "معلومات عامة"), ("أداء المؤسسة", "الأداء العام للمؤسسة"),
                          ("تتبع الغياب", "تتبع الغياب"), ("مجالس المؤسسة", "مجالس المؤسسة")]),
    ("التلاميذ", [("التلاميذ", "وثائق التلاميذ"), ("حركية التلاميذ", "حركية التلاميذ"),
                  ("تتبع السلوك", "تتبع سلوكات التلاميذ"), ("أولياء الأمور", "معلومات أولياء الأمور"),
                  ("التلاميذ القدامى", "التلاميذ القدامى"), ("الاستيراد من مسار", "الاستيراد من مسار")]),
    ("التدبير التربوي", [("الأندية والأنشطة", "الحياة المدرسية"), ("التعلمات الأساس", "تتبع التعلمات الأساس"),
                         ("الريادة", "المدرسة الرائدة")]),
    ("التدبير المالي والمادي", [("الجرد", "الجرد"), ("جمعية دعم مدرسة النجاح", "جمعية دعم مدرسة النجاح"),
                                ("الصرف", "الصرف: سند الطلب والاتفاقية"), ("الجمعية الرياضية", "الجمعية الرياضية"),
                                ("جمعية تنمية التعاون المدرسي", "جمعية تنمية التعاون المدرسي")]),
    ("التقييم", [("المراقبة المستمرة", "المراقبة المستمرة"), ("الامتحان", "الامتحان"),
                 ("استثمار النتائج", "استثمار النتائج"), ("مجالس الأقسام", "المحاضر: مجالس الأقسام")]),
    ("مشروع المؤسسة", [("مشروع المؤسسة", "مشروع المؤسسة")]),
    ("تسليم المهام", [("تسليم المهام", "تسليم المهام")]),
    ("الموارد البشرية", [("الموارد البشرية", "الموظفون"), ("الرخص", "الرخص"), ("تدبير الفائض", "تدبير الفائض")]),
    ("المراسلات", [("سجل الصادر", "سجل الصادر")]),
    ("الإعدادات", [("إعداد المؤسسة", "المؤسسة"), ("الوثائق", "نماذج الوثائق")]),
]
A_VENIR = {
    "تتبع الغياب": (
        ["غياب التلاميذ: التسجيل اليومي، الإحصاء الشهري حسب الأقسام، تنبيه الغياب المتكرر، إشعار الأولياء.",
         "غياب الموظفين وتأخرهم، مرتبطاً بالرخص المسجلة."],
        ["الوثائق التي تعتمدونها حالياً في تتبع الغياب (السجل، الإحصاء الشهري، الإشعار)."]),
    "أولياء الأمور": (
        ["معلومات الأولياء: الاسم، صلة القرابة، الهاتف، العنوان، لكل تلميذ.",
         "استعمالها في الاستدعاءات والإشعارات، ولوائح الاتصال حسب القسم."],
        ["مصدر هذه المعلومات عندكم (بطاقة التسجيل، مسار...) والخانات التي تحتاجونها."]),
    "الجرد": (
        ["سجل الجرد (الدليل المسطري، الملحقان 20 و24): الممتلكات، مصدرها، حالتها، النقل والإعارة والإتلاف.",
         "ربط التجهيزات المقتناة من جمعية النجاح بالجرد آلياً."],
        ["سجل الجرد الحالي أو نموذجه."]),
    "الجمعية الرياضية": (
        ["المداخيل والمصاريف بحساب مستقل، السجلات، التقرير المالي والأدبي."],
        ["وثائق الجمعية الرياضية: القانون الأساسي، نماذج السجلات والتقارير المعتمدة."]),
    "جمعية تنمية التعاون المدرسي": (
        ["المداخيل والمصاريف بحساب مستقل، السجلات، التقرير المالي والأدبي، الحصيلة السنوية."],
        ["وثائق الجمعية: القانون الأساسي، نماذج السجلات والتقارير المعتمدة."]),
    "المراقبة المستمرة": (
        ["تتبع إنجاز فروض المراقبة المستمرة حسب الأقسام والمواد، ومسك النقط في مسار."],
        ["تصدير النقط من مسار أو نموذج جدولة الفروض الذي تعتمدونه."]),
    "الامتحان": (
        ["تدبير الامتحان الموحد المحلي: الاستدعاءات، ترقيم الطاولات، لوائح الحراسة، المحاضر."],
        ["نماذج وثائق الامتحان المعتمدة في مديريتكم."]),
    "استثمار النتائج": (
        ["تحليل نتائج المراقبة المستمرة والامتحان حسب المستويات والمواد، وتحديد حاجيات الدعم."],
        ["نموذج تقرير استثمار النتائج الذي تعتمدونه إن وُجد."]),
    "مشروع المؤسسة": (
        ["إدراج المشروع: الأهداف، العمليات، المسؤوليات، المؤشرات.",
         "تتبع الإنجاز وتقييم النتائج، واقتراح أولويات المشروع اللاحق."],
        ["أنموذج من مشروع المؤسسة والمذكرات المؤطرة له (اتفقنا أن نفصل فيه لاحقاً)."]),
    "تسليم المهام": (
        ["محضر تسليم المهام الإدارية: يُحيَّن آلياً من معطيات المؤسسة (التلاميذ، الموظفون، الجرد، الجمعيات)، "
         "والمحاور اختيارية.",
         "محضر تسليم المهام المالية لجمعية النجاح موجود في صفحتها (الملحق 25)."],
        ["نموذج محضر تسليم المهام المعتمد عندكم."]),
}


def _programmes(fils, pages) -> list[str]:
    return [n for n, _ in fils if n in pages]


class BoutonNav(QPushButton):
    """زر قسم رئيسي: الأيقونة ثم العنوان محاذيين لليمين بتخطيط صريح (محاذاة النص في Qt تنعكس مع RTL)،
    وعلامة الفتح للأقسام ذات الفروع."""

    def __init__(self, section: str, libelle: str, deroulant: bool = False):
        super().__init__()
        self.setObjectName("nav")
        self.setCheckable(not deroulant)
        self.deroulant = deroulant
        self.actif = False
        self._icone = icones.icone(section)
        h = QHBoxLayout(self)
        h.setContentsMargins(12, 0, 12, 0)
        h.setSpacing(12)
        self.l_icone = QLabel()
        self.l_icone.setPixmap(icones.pixmap(section))
        self.l_icone.setFixedSize(QSize(24, 24))
        self.l_texte = QLabel(libelle)
        self.l_texte.setAlignment(Qt.AlignRight | Qt.AlignAbsolute | Qt.AlignVCenter)
        self.l_texte.setWordWrap(True)
        self.l_fleche = QLabel("‹" if deroulant else "")
        self.l_fleche.setVisible(deroulant)
        for w in (self.l_icone, self.l_texte, self.l_fleche):
            w.setAttribute(Qt.WA_TransparentForMouseEvents)
        h.addWidget(self.l_icone)   # في RTL أول عنصر يكون في أقصى اليمين
        h.addWidget(self.l_texte, 1)
        h.addWidget(self.l_fleche)
        self.toggled.connect(lambda c: self.marquer(c))
        self.marquer(False)

    def marquer(self, actif: bool) -> None:
        """القسم الذي فيه الصفحة المفتوحة: عنوانه بخط عريض."""
        self.actif = actif
        couleur = theme.VERT if actif and self.deroulant else theme.MARINE
        self.l_texte.setStyleSheet(f"color:{couleur}; font-weight:{600 if actif else 400};")
        self.l_fleche.setStyleSheet(f"color:{theme.GRIS}; font-size:14pt; font-weight:600;")

    def ouvrir(self, ouvert: bool) -> None:
        self.l_fleche.setText("⌄" if ouvert else "‹")

    def text(self) -> str:  # noqa: D401
        return self.l_texte.text()

    def icon(self):
        return self._icone


class BoutonSous(QPushButton):
    """فرع تحت قسم رئيسي، بإزاحة تحت عنوانه."""

    def __init__(self, libelle: str):
        super().__init__()
        self.setObjectName("sousnav")
        self.setCheckable(True)
        h = QHBoxLayout(self)
        h.setContentsMargins(12, 0, 48, 0)
        self.l_texte = QLabel(libelle)
        self.l_texte.setAlignment(Qt.AlignRight | Qt.AlignAbsolute | Qt.AlignVCenter)
        self.l_texte.setWordWrap(True)
        self.l_texte.setAttribute(Qt.WA_TransparentForMouseEvents)
        h.addWidget(self.l_texte, 1)
        self.toggled.connect(self._etat)
        self._etat(False)

    def _etat(self, coche: bool) -> None:
        self.l_texte.setStyleSheet(f"color:{theme.MARINE if coche else theme.GRIS}; "
                                   f"font-weight:{600 if coche else 400};")

    def text(self) -> str:  # noqa: D401
        return self.l_texte.text()


class FenetrePrincipale(QMainWindow):
    def __init__(self, dossier: DossierDonnees):
        super().__init__()
        self.dossier = dossier
        self.conn = ouvrir_base(dossier.base)
        self.setWindowTitle(f"{NOM_APPLICATION} {__version__}")
        self.resize(1280, 800)

        centre = QWidget()
        centre.setObjectName("fond")
        h = QHBoxLayout(centre)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        self.tableau = PageTableauBord(self)
        self.page_etab = PageEtablissement(self)
        self.page_eleves = PageEleves(self)
        self.page_anciens = PageAnciens(self)
        self.page_import = PageImport(self)
        self.page_mouvements = PageMouvements(self)
        self.page_comportement = PageComportement(self)
        self.page_conseils = PageConseils(self)
        self.page_asso = PageAssociations(self)
        self.page_achats = PageAchats(self)
        self.page_conseils_etab = PageConseilsEtab(self)
        self.page_perf = PagePerformance(self)
        self.page_tarl = PageTarl(self)
        self.page_vie = PageVieScolaire(self)
        self.page_riyada = PageRiyada(self)
        self.page_rh = PagePersonnel(self)
        self.page_conges = PageConges(self)
        self.page_fa = PageFa(self)
        self.page_sortants = PageSortants(self)
        self.page_docs = PageDocuments(self)
        self.pages = {"لوحة القيادة": self.tableau, "التلاميذ": self.page_eleves,
                      "التلاميذ القدامى": self.page_anciens,
                      "حركية التلاميذ": self.page_mouvements, "تتبع السلوك": self.page_comportement,
                      "مجالس الأقسام": self.page_conseils, "جمعية دعم مدرسة النجاح": self.page_asso, "الصرف": self.page_achats, "مجالس المؤسسة": self.page_conseils_etab, "أداء المؤسسة": self.page_perf, "التعلمات الأساس": self.page_tarl, "الأندية والأنشطة": self.page_vie, "الريادة": self.page_riyada, "الاستيراد من مسار": self.page_import,
                      "الموارد البشرية": self.page_rh, "الرخص": self.page_conges, "تدبير الفائض": self.page_fa,
                      "سجل الصادر": self.page_sortants, "إعداد المؤسسة": self.page_etab, "الوثائق": self.page_docs}
        self.emplacement = {}   # اسم الصفحة ← رقمها في الكومة
        self.section_de = {}    # اسم الصفحة ← رقم القسم الرئيسي
        self.pile = QStackedWidget()
        for i, (titre, fils) in enumerate(SECTIONS):
            for nom, lib in fils:
                if nom in self.pages:
                    w = page_defilante(self.pages[nom])
                else:
                    w = page_defilante(PageAVenir(lib, *A_VENIR[nom]))
                self.emplacement[nom] = self.pile.addWidget(w)
                self.section_de[nom] = i
        h.addWidget(self._barre_laterale())
        h.addWidget(self.pile, 1)
        self.setCentralWidget(centre)
        self.aller(0)

    def _barre_laterale(self) -> QWidget:
        barre = QFrame()
        barre.setObjectName("barreLaterale")
        barre.setFixedWidth(290)
        v = QVBoxLayout(barre)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        v.addWidget(BandeZellige())
        tete = QHBoxLayout()
        tete.setContentsMargins(20, 20, 20, 16)
        tete.setSpacing(12)
        tete.addWidget(LogoEtoile(36))
        noms = QVBoxLayout()
        noms.setSpacing(0)
        a = QLabel(NOM_APPLICATION)
        a.setStyleSheet("font-weight:600; font-size:12pt;")
        self.nom_etab = QLabel()
        self.nom_etab.setObjectName("etiquette")
        noms.addWidget(a)
        noms.addWidget(self.nom_etab)
        tete.addLayout(noms, 1)
        v.addLayout(tete)

        contenu = QWidget()
        contenu.setObjectName("navigation")
        nav = QVBoxLayout(contenu)
        nav.setContentsMargins(12, 8, 12, 8)
        nav.setSpacing(2)
        self.groupe = QButtonGroup(self)   # الصفحة المفتوحة: فرع أو قسم دون فروع
        self.groupe.setExclusive(True)
        self.boutons, self.sous, self.blocs, self.boutons_pages = [], [], [], {}
        for i, (nom, fils) in enumerate(SECTIONS):
            deroulant = len(fils) > 1
            prog = _programmes(fils, self.pages)
            b = BoutonNav(nom, nom if prog else f"{nom}  ·  قريباً", deroulant)
            b.setCursor(Qt.PointingHandCursor)
            nav.addWidget(b)
            self.boutons.append(b)
            bloc = QWidget()
            bv = QVBoxLayout(bloc)
            bv.setContentsMargins(0, 0, 0, 4)
            bv.setSpacing(1)
            sous = []
            if deroulant:
                b.clicked.connect(lambda _=False, i=i: self.basculer(i))
                for page, lib in fils:
                    sb = BoutonSous(lib if page in self.pages else f"{lib}  ·  قريباً")
                    sb.setCursor(Qt.PointingHandCursor)
                    sb.clicked.connect(lambda _=False, page=page: self.aller_a(page))
                    self.groupe.addButton(sb)
                    self.boutons_pages[page] = sb
                    bv.addWidget(sb)
                    sous.append(sb)
            else:
                b.clicked.connect(lambda _=False, page=fils[0][0]: self.aller_a(page))
                self.groupe.addButton(b)
                self.boutons_pages[fils[0][0]] = b
            bloc.setVisible(False)
            nav.addWidget(bloc)
            self.blocs.append(bloc)
            self.sous.append(sous)
        nav.addStretch()
        defil = QScrollArea()
        defil.setObjectName("defilNav")
        defil.setWidgetResizable(True)
        defil.setFrameShape(QFrame.NoFrame)
        defil.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        defil.setWidget(contenu)
        v.addWidget(defil, 1)

        bas = FondZellige()
        bas.setMinimumHeight(110)
        bv = QVBoxLayout(bas)
        bv.setContentsMargins(24, 16, 24, 16)
        self.etat_sauvegarde = QLabel()
        self.etat_sauvegarde.setObjectName("etiquette")
        bv.addWidget(self.etat_sauvegarde)
        b = QPushButton("نسخ إلى قرص خارجي")
        b.clicked.connect(self.exporter)
        bv.addWidget(b)
        v.addWidget(bas)
        self.rafraichir_entete()
        return barre

    def rafraichir_entete(self) -> None:
        e = etab_srv.lire_etablissement(self.conn)
        self.nom_etab.setText(e.nom_ar if e else "")
        n = len(sauvegarde.lister_sauvegardes(self.dossier))
        self.etat_sauvegarde.setText(f"النسخ الاحتياطية المحفوظة: {n}")

    def noms_pages(self) -> list[str]:
        return list(self.emplacement)

    def page_courante(self) -> str | None:
        i = self.pile.currentIndex()
        return next((nom for nom, k in self.emplacement.items() if k == i), None)

    def _rafraichir(self, nom: str) -> None:
        page = self.pages.get(nom)
        if page is not None and hasattr(page, "rafraichir"):
            page.rafraichir()

    def est_ouvert(self, i: int) -> bool:
        return not self.blocs[i].isHidden()

    def basculer(self, i: int, ouvert: bool | None = None) -> None:
        """يُظهر فروع القسم i أو يخفيها (الضغطة الثانية). فتح قسم يطوي الأقسام الأخرى."""
        ouvert = not self.est_ouvert(i) if ouvert is None else ouvert
        for k, bloc in enumerate(self.blocs):
            o = ouvert and k == i
            bloc.setVisible(o and bool(self.sous[k]))
            self.boutons[k].ouvrir(o)

    def aller_a(self, nom: str) -> None:
        """يفتح صفحة باسمها، أو قسماً رئيسياً باسمه (أول فرع مبرمج فيه)."""
        if nom not in self.emplacement:
            titres = [t for t, _ in SECTIONS]
            if nom not in titres:
                raise KeyError(nom)
            self.aller(titres.index(nom))
            return
        i = self.section_de[nom]
        if not self.est_ouvert(i):   # يفتح فروع القسم (إن وُجدت) ويطوي الأقسام الأخرى
            self.basculer(i, True)
        self.boutons_pages[nom].setChecked(True)
        for k, b in enumerate(self.boutons):
            b.marquer(k == i)
        self.pile.setCurrentIndex(self.emplacement[nom])
        self._rafraichir(nom)

    def aller(self, i: int) -> None:
        """يفتح القسم الرئيسي رقم i على أول فرع مبرمج فيه."""
        fils = SECTIONS[i][1]
        prog = _programmes(fils, self.pages)
        self.aller_a(prog[0] if prog else fils[0][0])

    def exporter(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "اختيار القرص الخارجي أو المجلد")
        if not d:
            return
        try:
            f = sauvegarde.exporter(self.dossier, __import__("pathlib").Path(d))
        except (sauvegarde.ErreurSauvegarde, OSError) as e:
            QMessageBox.warning(self, "تعذر النسخ", str(e))
            return
        QMessageBox.information(self, "تم النسخ", f"حُفظت النسخة في:\n{f}")

    def closeEvent(self, ev) -> None:
        try:
            sauvegarde.sauvegarde_quotidienne(self.dossier)
        except Exception:  # noqa: BLE001 — لا نمنع الإغلاق بسبب النسخ
            pass
        self.conn.close()
        super().closeEvent(ev)
