"""النافذة الرئيسية: القائمة الجانبية والصفحات."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QButtonGroup, QFileDialog, QFrame, QGridLayout, QHBoxLayout,
                               QLabel, QMainWindow, QMessageBox, QPushButton, QScrollArea,
                               QStackedWidget, QVBoxLayout, QWidget)

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
    def __init__(self, titre: str, etape: str):
        super().__init__()
        v = QVBoxLayout(self)
        v.setContentsMargins(40, 32, 40, 32)
        v.addWidget(entete(titre))
        c, cv = carte()
        l = QLabel(f"هذه الوحدة مخطط لها في {etape}، ولم تُبرمج بعد.")
        l.setWordWrap(True)
        cv.addWidget(l)
        v.addWidget(c)
        v.addStretch()


class FenetrePrincipale(QMainWindow):
    PAGES = [
        ("لوحة القيادة", None),
        ("التلاميذ", None),
        ("التلاميذ القدامى", None),
        ("الاستيراد من مسار", None),
        ("الوثائق", None),
        ("الموارد البشرية", "المرحلتين 6 و7"),
        ("إعداد المؤسسة", None),
    ]

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
        h.addWidget(self._barre_laterale())
        self.pile = QStackedWidget()
        self.tableau = PageTableauBord(self)
        self.page_etab = PageEtablissement(self)
        for nom, etape in self.PAGES:
            if nom == "لوحة القيادة":
                self.pile.addWidget(page_defilante(self.tableau))
            elif nom == "التلاميذ":
                self.page_eleves = PageEleves(self)
                self.pile.addWidget(page_defilante(self.page_eleves))
            elif nom == "التلاميذ القدامى":
                self.page_anciens = PageAnciens(self)
                self.pile.addWidget(page_defilante(self.page_anciens))
            elif nom == "الاستيراد من مسار":
                self.page_import = PageImport(self)
                self.pile.addWidget(page_defilante(self.page_import))
            elif nom == "الوثائق":
                self.page_docs = PageDocuments(self)
                self.pile.addWidget(page_defilante(self.page_docs))
            elif nom == "إعداد المؤسسة":
                self.pile.addWidget(page_defilante(self.page_etab))
            else:
                self.pile.addWidget(page_defilante(PageAVenir(nom, etape)))
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
        for i, (nom, _) in enumerate(self.PAGES):
            b = QPushButton(nom)
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

    def aller_a(self, nom: str) -> None:
        self.aller([n for n, _ in self.PAGES].index(nom))

    def aller(self, i: int) -> None:
        self.boutons[i].setChecked(True)
        if i == 0:
            self.tableau.rafraichir()
        elif self.PAGES[i][0] == "الوثائق":
            self.page_docs.rafraichir()
        elif self.PAGES[i][0] == "التلاميذ":
            self.page_eleves.rafraichir()
        elif self.PAGES[i][0] == "التلاميذ القدامى":
            self.page_anciens.rafraichir()
        elif self.PAGES[i][0] == "الاستيراد من مسار":
            self.page_import.rafraichir()
        self.pile.setCurrentIndex(i)

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
