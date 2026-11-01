"""النافذة الرئيسية: القائمة الجانبية والصفحات."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt
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
from idara.ui import theme
from idara.ui.composants import carte, entete, page_defilante
from idara.ui.formulaires import FormDirecteur, FormEtablissement, FormIdentite
from idara.ui.page_documents import PageDocuments
from idara.ui.page_import import PageImport
from idara.ui.page_eleves import PageEleves
from idara.ui.page_anciens import PageAnciens
from idara.ui.page_personnel import PagePersonnel
from idara.ui.page_fa import PageFa
from idara.ui.page_mouvements import PageMouvements
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


# الأقسام (اقتراح المدير 2026-11-01): كل قسم في القائمة الجانبية، وصفحاته في ألسنة داخله.
SECTIONS = [
    ("لوحة القيادة", ["لوحة القيادة"]),
    ("التلاميذ", ["التلاميذ", "حركية التلاميذ", "التلاميذ القدامى", "الاستيراد من مسار"]),
    ("الموارد البشرية", ["الموارد البشرية", "الرخص", "تدبير الفائض"]),
    ("التدبير التربوي", []),
    ("التقييم", []),
    ("التدبير المالي والمادي", []),
    ("المراسلات", ["سجل الصادر"]),
    ("مشروع المؤسسة", []),
    ("الإعدادات", ["إعداد المؤسسة", "الوثائق"]),
]
ETIQUETTES = {"التلاميذ": "البحث والوثائق", "الموارد البشرية": "الموظفون", "الوثائق": "نماذج الوثائق",
              "إعداد المؤسسة": "المؤسسة"}
A_VENIR = {
    "التدبير التربوي": (
        ["تتبع أداء المؤسسة ونتائج التلاميذ حسب الأقسام والمستويات والمواد.",
         "مؤشرات تربوية تُستخرج آلياً من النتائج المسجلة في قسم التقييم.",
         "الحياة المدرسية والأنشطة: الأندية، الأنشطة الثقافية والرياضية، تقاريرها."],
        ["المؤشرات التي تعتمدونها في تتبع أداء المؤسسة.", "نماذج تقارير الأنشطة إن وُجدت."]),
    "التقييم": (
        ["تدبير الامتحان المحلي والإقليمي: الاستدعاءات، ترقيم الطاولات، الوثائق المرتبطة.",
         "محاضر مجالس الأقسام بنتائج التلاميذ، مذيلة بتوقيع أساتذة كل قسم على حدة."],
        ["نموذج محضر مجلس القسم.", "نماذج وثائق الامتحان المحلي والإقليمي.",
         "صيغة ملف النتائج الذي يُستخرج من مسار (إن أمكن)."]),
    "التدبير المالي والمادي": (
        ["الجمعيات الثلاث: المداخيل والمصاريف بحسابات منفصلة، التقارير المالية والأدبية، الحصيلة السنوية.",
         "جرد الممتلكات بالمجموعات وحالاتها، النقل والإعارة والمفقودات.",
         "محضر تسليم المهام: يُحيَّن آلياً من معطيات المؤسسة (المحاور اختيارية)."],
        ["وثائق الجمعيات الثلاث ونماذج التقارير المالية والأدبية.", "سجل الجرد الحالي."]),
    "مشروع المؤسسة": (
        ["إدراج المشروع: الأهداف، العمليات، المسؤوليات، المؤشرات.",
         "تتبع الإنجاز وتقييم النتائج، واقتراح أولويات المشروع اللاحق."],
        ["أنموذج من مشروع المؤسسة والمذكرات المؤطرة له (اتفقنا أن يكون هذا القسم آخر العمل)."]),
}


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
        self.page_rh = PagePersonnel(self)
        self.page_conges = PageConges(self)
        self.page_fa = PageFa(self)
        self.page_sortants = PageSortants(self)
        self.page_docs = PageDocuments(self)
        self.pages = {"لوحة القيادة": self.tableau, "التلاميذ": self.page_eleves,
                      "التلاميذ القدامى": self.page_anciens,
                      "حركية التلاميذ": self.page_mouvements, "الاستيراد من مسار": self.page_import,
                      "الموارد البشرية": self.page_rh, "الرخص": self.page_conges, "تدبير الفائض": self.page_fa,
                      "سجل الصادر": self.page_sortants, "إعداد المؤسسة": self.page_etab, "الوثائق": self.page_docs}
        self.emplacement = {}   # اسم الصفحة ← (رقم القسم، رقم اللسان)
        self.pile = QStackedWidget()
        self.onglets = {}
        for i, (titre, noms) in enumerate(SECTIONS):
            if not noms:
                self.pile.addWidget(page_defilante(PageAVenir(titre, *A_VENIR[titre])))
            elif len(noms) == 1:
                self.pile.addWidget(page_defilante(self.pages[noms[0]]))
                self.emplacement[noms[0]] = (i, None)
            else:
                t = QTabWidget()
                t.setObjectName("sections")
                t.setDocumentMode(True)
                for j, nom in enumerate(noms):
                    t.addTab(page_defilante(self.pages[nom]), ETIQUETTES.get(nom, nom))
                    self.emplacement[nom] = (i, j)
                t.currentChanged.connect(lambda j, noms=noms: self._rafraichir(noms[j]))
                self.onglets[i] = t
                self.pile.addWidget(t)
        h.addWidget(self._barre_laterale())
        h.addWidget(self.pile, 1)
        self.setCentralWidget(centre)
        self.aller(0)

    def _barre_laterale(self) -> QWidget:
        barre = QFrame()
        barre.setObjectName("barreLaterale")
        barre.setFixedWidth(270)
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

        nav = QVBoxLayout()
        nav.setContentsMargins(12, 8, 12, 8)
        nav.setSpacing(2)
        self.groupe = QButtonGroup(self)
        self.groupe.setExclusive(True)
        self.boutons = []
        for i, (nom, noms) in enumerate(SECTIONS):
            b = QPushButton(nom if noms else f"{nom}  ·  قريباً")
            b.setObjectName("nav")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, i=i: self.aller(i))
            self.groupe.addButton(b, i)
            nav.addWidget(b)
            self.boutons.append(b)
        v.addLayout(nav)
        v.addStretch()

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
        t = self.onglets.get(i)
        for nom, (si, j) in self.emplacement.items():
            if si == i and (t is None or j == t.currentIndex()):
                return nom
        return None

    def _rafraichir(self, nom: str) -> None:
        page = self.pages.get(nom)
        if page is not None and hasattr(page, "rafraichir"):
            page.rafraichir()

    def aller_a(self, nom: str) -> None:
        """يفتح صفحة باسمها (القسم واللسان)، أو قسماً باسمه."""
        if nom in self.emplacement:
            i, j = self.emplacement[nom]
            self.boutons[i].setChecked(True)
            self.pile.setCurrentIndex(i)
            if j is not None and self.onglets[i].currentIndex() != j:
                self.onglets[i].setCurrentIndex(j)  # يحدّث الصفحة عبر currentChanged
            else:
                self._rafraichir(nom)
            return
        self.aller([t for t, _ in SECTIONS].index(nom))

    def aller(self, i: int) -> None:
        """يفتح القسم رقم i على لسانه الحالي."""
        self.boutons[i].setChecked(True)
        self.pile.setCurrentIndex(i)
        nom = self.page_courante()
        if nom:
            self._rafraichir(nom)

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
