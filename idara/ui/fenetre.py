"""النافذة الرئيسية: القائمة الجانبية والصفحات."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (QApplication, QButtonGroup, QComboBox, QFileDialog, QFrame, QInputDialog, QGridLayout,
                               QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton, QScrollArea,
                               QStackedWidget, QTabWidget, QVBoxLayout, QWidget)

from idara import NOM_APPLICATION, __version__, marque
from idara.data.db import ouvrir_base
from idara.data.dossier import DossierDonnees
from idara.services import annee as annee_srv
from idara.services import calendrier as cal_srv
from idara.services import config as config_srv
from idara.services import eleves as el
from idara.services import etablissement as etab_srv
from idara.services import import_eleves as imp
from idara.services import personnel as rh
from idara.services import sauvegarde
from idara.services import tableau_bord as tb_srv
from idara.services.etablissement import ErreurValidation
from idara.services.textes import date_longue_ar
from idara.ui import icones, theme
from idara.ui.composants import carte, entete, page_defilante
from idara.ui.formulaires import FormDirecteur, FormEtablissement, FormIdentite
from idara.ui.saisie import message
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
from idara.ui.page_tanzim import PageTanzim
from idara.ui.page_calendrier import PageCalendrier
from idara.ui.page_guide import PageGuide
from idara.ui.page_statistiques import PageStatistiques
from idara.ui.page_inscriptions import PageInscriptions
from idara.ui.page_absences import PageAbsences
from idara.ui.page_soutien import PageSoutien
from idara.ui.page_inventaire import PageInventaire
from idara.ui.page_structure import PageStructure
from idara.ui.page_parents import PageParents
from idara.ui.page_passation import PagePassation
from idara.ui.page_sabboura import PageSabboura
from idara.ui.page_projet import PageProjet
from idara.ui.page_pv_rh import PagePvRh
from idara.ui.page_examen import PageDeliberations, PageExamen
from idara.ui.page_conges import PageConges, PageSortants
from idara.ui.zellige import BandeZellige, FondZellige, LogoMarque


class Jauge(QWidget):
    """مؤشر دائري: النسبة في الوسط، والعنوان والملاحظة تحته (رسم بالكود)."""

    def __init__(self, titre: str, taux: float | None, note: str = "", couleur: str = theme.SARCELLE):
        super().__init__()
        self.titre, self.taux, self.note, self.couleur = titre, taux, note, couleur
        self.setMinimumSize(150, 215)
        from PySide6.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def sizeHint(self):
        from PySide6.QtCore import QSize
        return QSize(180, 215)

    def paintEvent(self, _ev) -> None:
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QColor, QFont, QPainter, QPen
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        d = min(self.width() - 20, 130)
        r = QRectF((self.width() - d) / 2, 8, d, d)
        p.setPen(QPen(QColor(theme.LIGNE), 14, Qt.SolidLine, Qt.FlatCap))
        p.drawArc(r, 0, 360 * 16)
        if self.taux is not None:
            p.setPen(QPen(QColor(self.couleur), 14, Qt.SolidLine, Qt.RoundCap))
            p.drawArc(r, 90 * 16, -int(min(self.taux, 100) / 100 * 360 * 16))
        p.setPen(QColor(theme.MARINE))
        f = QFont(self.font())
        f.setPointSize(16)
        f.setBold(True)
        p.setFont(f)
        p.drawText(r, Qt.AlignCenter, "—" if self.taux is None else f"\u2066{self.taux:g}%\u2069")
        f.setPointSize(10)
        p.setFont(f)
        y = int(r.bottom()) + 8
        p.drawText(QRectF(0, y, self.width(), 22), Qt.AlignHCenter | Qt.AlignTop, self.titre)
        f.setBold(False)
        f.setPointSize(9)
        p.setFont(f)
        p.setPen(QColor(theme.GRIS))
        p.drawText(QRectF(4, y + 22, self.width() - 8, 44), Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap, self.note)
        p.end()


class PageTableauBord(QWidget):
    def __init__(self, fenetre: "FenetrePrincipale"):
        super().__init__()
        self.f = fenetre
        self.unite: str | None = None   # المجموعة المدرسية: وحدة واحدة أو المؤسسة كاملة
        self.externe = QVBoxLayout(self)
        self.externe.setContentsMargins(0, 0, 0, 0)
        self.contenu = None
        self.rafraichir()

    def _carte_groupe(self, etab, unites: list[str]) -> None:
        """المجموعة المدرسية: معطيات المؤسسة كاملة وزر لكل وحدة مدرسية."""
        c, cv = carte("المؤسسة")
        infos = [("المؤسسة", etab.nom_ar), ("الرمز", etab.code_etab or "—"), ("النوع", "مجموعة مدرسية"),
                 ("الجماعة", etab.commune_ar or "—"), ("المديرية الإقليمية", etab.direction_ar or "—"),
                 ("الأكاديمية", etab.academie_ar or "—"), ("الريادة", "مؤسسة رائدة" if etab.est_pionniere else "—"),
                 ("الوحدات المدرسية", str(len(unites)))]
        g = QGridLayout()
        g.setHorizontalSpacing(24)
        for k, (lib, val) in enumerate(infos):
            e = QLabel(lib)
            e.setObjectName("etiquette")
            v = QLabel(val)
            v.setStyleSheet("font-weight:600;")
            g.addWidget(e, (k // 4) * 2, k % 4)
            g.addWidget(v, (k // 4) * 2 + 1, k % 4)
        cv.addLayout(g)
        if unites:
            h = QHBoxLayout()
            self.boutons_unites = {}
            for nom in [None, *unites]:
                b = QPushButton("المؤسسة كاملة" if nom is None else nom)
                b.setCheckable(True)
                b.setChecked(nom == self.unite)
                if nom == self.unite:
                    b.setObjectName("principal")
                b.clicked.connect(lambda _=False, nom=nom: self.choisir_unite(nom))
                self.boutons_unites[nom] = b
                h.addWidget(b)
            h.addStretch()
            cv.addLayout(h)
        self.v.addWidget(c)

    def choisir_unite(self, unite: str | None) -> None:
        self.unite = unite
        self.rafraichir()

    def _jauges(self, ind: dict) -> None:
        """ملخص مبياني: الغياب، الهدر المدرسي، الأنشطة الموازية، والتعلمات الأساس (رائدة) أو المعدل (غيرها)."""
        c, cv = carte("ملخص المؤشرات" + (f" · {self.unite}" if self.unite else ""))
        h = QHBoxLayout()
        h.setSpacing(8)
        hd = ind["hadar"]
        from idara.services import absences as abs_srv
        dt = abs_srv.dernier_taux(self.f.conn)
        jauges = [Jauge("الحضور", dt[1] if dt else None, f"آخر شهر مُدرج: {dt[0]}" if dt else "لم يُدرج أي شهر بعد",
                        theme.SARCELLE),
                  Jauge("الهدر المدرسي", hd["taux"], f"منقطعون {hd['interrompus']} · مفصولون {hd['exclus']}", theme.ROSE),
                  Jauge("الأنشطة الموازية", ind["activites"]["taux"],
                        f"{ind['activites']['participants']} تلميذاً في الأندية", theme.VIOLET)]
        if ind["pionniere"]:
            for m in ind["maitrise"].values():
                jauges.append(Jauge(f"التعلمات الأساس: {m['matiere']}", m["taux"],
                                    f"{m['maitrise']}/{m['total']} · {m['epreuve']}" if m["total"]
                                    else "لا نتائج رائز بعد", theme.SARCELLE))
        else:
            r = ind["reussite"]
            jauges.append(Jauge("الحاصلون على المعدل", r["taux"],
                                f"{r['admis']}/{r['total']} · {r['source']}" if r["total"] else "لا نتائج مستوردة بعد",
                                theme.SARCELLE))
        self.jauges = jauges
        for j in jauges:
            h.addWidget(j, 1)
        cv.addLayout(h)
        self.v.addWidget(c)

    def _aujourdhui(self) -> None:
        """«ماذا أفعل اليوم؟» (2026-11-13): أعمال ينتظرها البرنامج من المدير، محسوبة من المعطيات."""
        from idara.services import aujourdhui as auj
        try:
            self.taches = auj.taches(self.f.conn, self.f.dossier)
        except Exception:  # noqa: BLE001 (لا يُعطَّل فتح لوحة القيادة)
            self.taches = []
        c, cv = carte("ماذا أفعل اليوم؟")
        if not self.taches:
            l = QLabel("لا شيء مستعجل اليوم.")
            l.setObjectName("etiquette")
            cv.addWidget(l)
        for t in self.taches:
            ligne = QHBoxLayout()
            l = QLabel(("● " if t["urgence"] >= 2 else "○ ") + t["texte"])
            l.setWordWrap(True)
            if t["urgence"] >= 2:
                l.setStyleSheet(f"color:{theme.ROUGE_TEXTE}; font-weight:600;")
            ligne.addWidget(l, 1)
            if t["page"]:
                b = QPushButton("فتح")
                b.clicked.connect(lambda _=False, p=t["page"]: self.f.aller_a(p))
                ligne.addWidget(b)
            cv.addLayout(ligne)
        self.v.addWidget(c)

    def _rappels(self) -> None:
        """التذكيرات بمحطات المقرر الوزاري والمؤسسة (اقتراح المدير 2026-11-03)."""
        try:
            r = cal_srv.rappels(self.f.conn)
        except cal_srv.ErreurCalendrier:
            r = {"en_cours": [], "a_venir": [], "en_retard": []}
        lignes = ([("فاتت", s) for s in r["en_retard"]] + [("جارية", s) for s in r["en_cours"]] +
                  [("قادمة", s) for s in r["a_venir"]])
        self.lignes_rappels = lignes
        c, cv = carte("التذكيرات")
        if not lignes:
            l = QLabel("لا محطات قريبة. كل محطات السنة في «برنامج العمل السنوي».")
            l.setObjectName("etiquette")
            cv.addWidget(l)
        for etat, s in lignes[:6]:
            ligne = QHBoxLayout()
            e = QLabel(etat)
            e.setObjectName("alerte" if etat == "فاتت" else "etiquette")
            e.setMinimumWidth(60)
            l = QLabel(f"{s.titre} · {s.periode}")
            l.setWordWrap(True)
            ligne.addWidget(e)
            ligne.addWidget(l, 1)
            if s.lien and s.lien in getattr(self.f, "emplacement", {}):
                b = QPushButton("فتح")
                b.clicked.connect(lambda _=False, c=s.lien: self.f.aller_a(c))
                ligne.addWidget(b)
            cv.addLayout(ligne)
        h = QHBoxLayout()
        b = QPushButton("برنامج العمل السنوي" + (f" (+{len(lignes) - 6})" if len(lignes) > 6 else ""))
        b.clicked.connect(lambda: self.f.aller_a("برنامج العمل"))
        h.addWidget(b)
        h.addStretch()
        cv.addLayout(h)
        self.v.addWidget(c)

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
        etab = etab_srv.lire_etablissement(conn)
        unites = etab_srv.unites(conn) if etab and etab.type_etab == "groupe" else []
        if self.unite not in unites:
            self.unite = None
        if etab and etab.type_etab == "groupe":
            self._carte_groupe(etab, unites)
        ind = tb_srv.indicateurs(conn, self.unite)
        n_eleves, n_classes, n_pers = ind["eleves"], len(ind["classes"]), ind["personnel"]
        sv = sauvegarde.lister_sauvegardes(self.f.dossier)
        derniere = sv[-1].name[len(sauvegarde.PREFIXE):len(sauvegarde.PREFIXE) + 8] if sv else ""
        derniere = f"{derniere[6:8]}/{derniere[4:6]}/{derniere[:4]}" if derniere else "لا توجد بعد"

        # بطاقات الأرقام: أيقونة وخط جانبي بلون المؤشر (اقتراح المدير 2026-11-06)
        from idara.ui.graphiques import Tuile
        grille = QGridLayout()
        grille.setSpacing(16)
        self.tuiles = []
        for i, (lib, val, note, coul, sec) in enumerate([
                ("التلاميذ يتابعون دراستهم", str(n_eleves), f"ذكور {ind['garcons']} · إناث {ind['filles']}",
                 theme.BLEU, "التلاميذ"),
                ("الأقسام", str(n_classes), "", theme.VIOLET, "التدبير التربوي"),
                ("الموظفون", str(n_pers), "دون المدير", theme.SARCELLE, "الموارد البشرية"),
                ("آخر نسخة احتياطية", derniere, f"{len(sv)} نسخة محفوظة", theme.ORANGE, "الإعدادات")]):
            t = Tuile(lib, val, coul, sec, note)
            self.tuiles.append(t)
            grille.addWidget(t, i // 2, i % 2)
        self.v.addLayout(grille)

        self._aujourdhui()
        self._rappels()
        self._jauges(ind)
        # التوزيع حسب القسم
        repartition = ind["classes"]
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
        # المحتوى أطول من النافذة: حد أدنى للارتفاع حتى لا تُضغط البطاقات (المؤشرات ومعطيات المؤسسة) داخل التمرير
        self.v.activate()
        self.contenu.setMinimumHeight(self.v.totalMinimumSize().height())


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
        # مظهر البرنامج (اقتراح المدير 2026-11-06)
        c, cv = carte("مظهر البرنامج")
        hb = QHBoxLayout()
        self.choix_theme = QComboBox()
        for k, lib in theme.NOMS_THEMES.items():
            self.choix_theme.addItem(lib, k)
        self.choix_theme.setCurrentIndex(max(0, self.choix_theme.findData(theme.THEME_ACTUEL)))
        self.choix_theme.currentIndexChanged.connect(lambda _: self.f.appliquer_theme(self.choix_theme.currentData()))
        l = QLabel("يُطبَّق فوراً ويُحفظ لهذا الحاسوب.")
        l.setObjectName("etiquette")
        hb.addWidget(self.choix_theme)
        hb.addWidget(l)
        hb.addStretch()
        cv.addLayout(hb)
        v.addWidget(c)
        from idara.ui.vidage_ui import carte_parametres
        v.addWidget(carte_parametres(self.f, self.message))
        # تصفير البرنامج (طلب المدير 2026-11-04)
        c, cv = carte("تصفير البرنامج")
        l = QLabel("يحذف كل ما أُدخل في البرنامج: معطيات المؤسسة والمدير، التلاميذ، الموظفون، الرخص، الجمعيات، "
                   "المجالس، النتائج، المحطات المحلية، القوالب المعدّلة والهوية البصرية، والوثائق المولَّدة. "
                   "يعود البرنامج بعدها إلى مساعد الإعداد الأول.\n"
                   "قبل الحذف تُحفظ نسخة كاملة في مجلد النسخ الاحتياطية، ويمكن استرجاعها من مساعد الإعداد "
                   "(«استيراد نسخة»).")
        l.setWordWrap(True)
        cv.addWidget(l)
        hb = QHBoxLayout()
        self.b_reinit = QPushButton("تصفير البرنامج…")
        self.b_reinit.setObjectName("danger")
        self.b_reinit.setIcon(icones.corbeille())
        self.b_reinit.clicked.connect(lambda: self.f.reinitialiser())
        hb.addWidget(self.b_reinit)
        hb.addStretch()
        cv.addLayout(hb)
        v.addWidget(c)
        v.addStretch()
        self.charger()

    def rafraichir(self) -> None:
        """عند فتح الصفحة: تُقرأ القيم المحفوظة (قد تكون صفحة أخرى غيّرتها، مثل وسط المؤسسة)."""
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
            if self.f_id.mode_pied() == "image":
                if self.f_id.pied_image.valeur():
                    e.pied_image_path = etab_srv.importer_image(self.f.dossier, self.f_id.pied_image.valeur(), "pied")
                elif not e.pied_image_path:
                    raise ErreurValidation("اختر صورة التذييل، أو اختر «نص».")
            else:
                e.pied_image_path = ""
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
            self.f_id.remplir(e)
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
# الموارد البشرية أضافها المدير بعد ذلك (2026-11-03). المراسلات والإعدادات لم تردا في ترتيبه، فأُبقيتا بعده
# حتى لا تضيع وظائفهما.
SECTIONS = [
    ("القيادة والتدبير", [("لوحة القيادة", "لوحة القيادة"), ("الإحصائيات", "إحصائيات المؤسسة"),
                          ("برنامج العمل", "برنامج العمل السنوي والتذكيرات"),
                          ("أداء المؤسسة", "الأداء العام للمؤسسة"),
                          ("تتبع الغياب", "تتبع الغياب"), ("مجالس المؤسسة", "مجالس المؤسسة"),
                          ("السبورة المرجعية", "السبورة المرجعية")]),
    ("التلاميذ", [("التلاميذ", "وثائق التلاميذ"), ("حركية التلاميذ", "حركية التلاميذ"),
                  ("تتبع السلوك", "تتبع سلوكات التلاميذ"), ("أولياء الأمور", "معلومات أولياء الأمور"),
                  ("التلاميذ القدامى", "التلاميذ القدامى (ما قبل مسار)"), ("الاستيراد من مسار", "الاستيراد من مسار")]),
    ("الموارد البشرية", [("الموارد البشرية", "معلومات الأطر"), ("تدبير الفائض", "تدبير الفائض"),
                         ("الرخص", "الرخص"), ("محاضر الموارد البشرية", "المحاضر")]),
    ("التدبير التربوي", [("التنظيم التربوي", "التنظيم التربوي"), ("الأندية والأنشطة", "الحياة المدرسية"), ("التعلمات الأساس", "تتبع التعلمات الأساس"),
                         ("الدعم التربوي", "الدعم التربوي"), ("الريادة", "المدرسة الرائدة")]),
    ("التدبير المالي والمادي", [("التسجيلات", "تدبير التسجيلات"), ("الجرد", "الجرد"),
                                ("جمعية دعم مدرسة النجاح", "جمعية دعم مدرسة النجاح"),
                                ("الصرف", "الصرف: سند الطلب والاتفاقية"), ("الجمعية الرياضية", "الجمعية الرياضية"),
                                ("جمعية تنمية التعاون المدرسي", "جمعية تنمية التعاون المدرسي"),
                                ("البنية المادية", "البنية المادية")]),
    ("التقييم", [("المراقبة المستمرة", "المراقبة المستمرة"), ("الامتحان", "الامتحان"),
                 ("استثمار النتائج", "استثمار النتائج"), ("مجالس الأقسام", "المحاضر: مجالس الأقسام"),
                 ("محاضر نهاية الأسدوس", "المحاضر: نهاية الأسدوس")]),
    ("مشروع المؤسسة", [("مشروع المؤسسة", "تتبع مشروع المؤسسة المندمج")]),
    ("تسليم المهام", [("تسليم المهام", "تسليم المهام")]),
    ("المراسلات", [("سجل الصادر", "سجل الصادر")]),
    ("الإعدادات", [("إعداد المؤسسة", "المؤسسة"), ("الوثائق", "نماذج الوثائق"),
                   ("دليل الاستخدام", "كيفية استخدام البرنامج")]),
]
A_VENIR = {
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
}


def _programmes(fils, pages) -> list[str]:
    return [n for n, _ in fils if n in pages]


class BoutonNav(QPushButton):
    """زر قسم رئيسي: الأيقونة ثم العنوان محاذيين لليمين بتخطيط صريح (محاذاة النص في Qt تنعكس مع RTL)،
    وعلامة الفتح للأقسام ذات الفروع."""

    def __init__(self, section: str, libelle: str, deroulant: bool = False, nb: int = 0):
        super().__init__()
        self.setObjectName("nav")
        self.setCheckable(not deroulant)
        self.deroulant = deroulant
        self.actif = False
        self._icone = icones.icone(section)
        self.setMinimumHeight(54)
        h = QHBoxLayout(self)
        h.setContentsMargins(10, 4, 10, 4)
        h.setSpacing(12)
        self.l_icone = QLabel()
        self.l_icone.setPixmap(icones.tuile(section))   # الأيقونة داخل مربع بلون القسم (2026-11-06)
        self.l_icone.setFixedSize(QSize(38, 38))
        self.l_texte = QLabel(libelle)
        self.l_texte.setAlignment(Qt.AlignRight | Qt.AlignAbsolute | Qt.AlignVCenter)
        self.l_texte.setWordWrap(True)
        self.l_badge = QLabel(str(nb) if nb > 1 else "")   # عدد الصفحات الفرعية
        self.l_badge.setObjectName("badge")
        self.l_badge.setVisible(nb > 1)
        self.l_fleche = QLabel()
        self.l_fleche.setFixedSize(QSize(14, 14))
        if deroulant:
            self.l_fleche.setPixmap(icones.chevron(False, theme.NAV_TEXTE2))
        self.l_fleche.setVisible(deroulant)
        for w in (self.l_icone, self.l_texte, self.l_badge, self.l_fleche):
            w.setAttribute(Qt.WA_TransparentForMouseEvents)
        h.addWidget(self.l_icone)   # في RTL أول عنصر يكون في أقصى اليمين
        h.addWidget(self.l_texte, 1)
        h.addWidget(self.l_badge)
        h.addWidget(self.l_fleche)
        self.toggled.connect(lambda c: self.marquer(c))
        self.marquer(False)

    def marquer(self, actif: bool) -> None:
        """القسم الذي فيه الصفحة المفتوحة: عنوانه بخط عريض."""
        self.actif = actif
        couleur = (theme.NAV_ACCENT if self.deroulant else theme.NAV_TEXTE_ACTIF) if actif else theme.NAV_TEXTE
        self.l_texte.setStyleSheet(f"color:{couleur}; font-weight:{700 if actif else 600}; background:transparent;")

    def ouvrir(self, ouvert: bool) -> None:
        if self.deroulant:
            self.l_fleche.setPixmap(icones.chevron(ouvert, theme.NAV_TEXTE2))

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
        self.l_texte.setStyleSheet(f"color:{theme.NAV_TEXTE_ACTIF if coche else theme.NAV_TEXTE2}; "
                                   f"font-weight:{600 if coche else 400}; background:transparent;")

    def text(self) -> str:  # noqa: D401
        return self.l_texte.text()


def normaliser_recherche(t: str) -> str:
    """للبحث في أسماء الصفحات: دون تشكيل، الهمزات ألف، التاء المربوطة هاء، ودون «ال» التعريف."""
    import re
    t = re.sub(r"[\u064B-\u0652\u0640]", "", t or "")
    for a, b in (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ة", "ه"), ("ى", "ي"), ("ؤ", "و"), ("ئ", "ي")):
        t = t.replace(a, b)
    mots = []
    for m in t.split():
        if m.startswith("وال") and len(m) > 4:
            m = m[3:]
        elif m.startswith("ال") and len(m) > 3:
            m = m[2:]
        mots.append(m)
    return " ".join(mots)


# كلمات إضافية للبحث (ما يكتبه المدير قد لا يكون في اسم الصفحة)
MOTS_CLES = {"الرخص": "إجازة رخصة مرض ولادة رضاعة", "الموارد البشرية": "أساتذة أستاذ موظفين أطر xml",
             "محاضر نهاية الأسدوس": "محضر مداولات نتائج نقط", "الامتحان": "امتحان موحد إشهادي سادس",
             "التلاميذ": "تلميذ بحث شهادة مدرسية وثائق", "الاستيراد من مسار": "مسار لوائح استيراد",
             "برنامج العمل": "مقرر عطل عطلة تذكير محطات", "تتبع الغياب": "غياب متغيبون نسبة", "إعداد المؤسسة": "إعدادات شعار مظهر تصفير ترويسة",
             "جمعية دعم مدرسة النجاح": "مالية مداخيل مصاريف بنك", "التسجيلات": "تأمين واجبات تسجيل رياضية تعاون", "مجالس الأقسام": "مجلس قسم محضر",
             "التنظيم التربوي": "بنية تربوية توزيع", "تدبير الفائض": "فائض خصاص",
             "الدعم التربوي": "دعم متعثرين تعثر معالجة سجل",
             "مشروع المؤسسة": "مشروع مؤشرات عمليات خطة العمل مسار حصيلة",
             "محاضر الموارد البشرية": "محضر التحاق دخول خروج توقيع",
             "تسليم المهام": "محضر تسليم المهام المدير الجديد السابق مفاتيح أختام بنايات",
             "الجرد": "جرد ممتلكات تجهيزات سجل الجرد فاتورة محو",
             "البنية المادية": "حجرات مباني ملاعب مراحيض مرافق صحية بنايات إعاقة",
             "أولياء الأمور": "ولي الأب الأم هاتف وصاية آباء",
             "السبورة المرجعية": "سبورة لوحات بطاقة معلومات المؤسسة خلايا يقظة إنصات استعمال الزمن الجماعي"}


class BarreLaterale(QFrame):
    """الشريط الجانبي: تدرّج لون المظهر مع زليج خافت (اقتراح المدير 2026-11-06)."""

    def paintEvent(self, ev):
        from PySide6.QtGui import QColor, QLinearGradient, QPainter
        from idara.ui.zellige import dessiner_etoile
        p = QPainter(self)
        g = QLinearGradient(0, 0, 0, self.height())
        g.setColorAt(0, QColor(theme.NAV_FOND))
        g.setColorAt(1, QColor(theme.NAV_FOND2))
        p.fillRect(self.rect(), g)
        if theme.NAV_SOMBRE:
            p.setRenderHint(QPainter.Antialiasing)
            p.setOpacity(0.07)
            for y in range(0, self.height() + 64, 64):
                for x in range(0, self.width() + 64, 64):
                    dessiner_etoile(p, x + 32, y + 32, 14, theme.NAV_MOTIF, pleine=False)
        p.end()
        super().paintEvent(ev)


class FenetrePrincipale(QMainWindow):
    reinitialisation = Signal(object)   # مسار النسخة المأخوذة قبل التصفير

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
        self.page_tanzim = PageTanzim(self)
        self.page_deliberations = PageDeliberations(self)
        self.page_examen = PageExamen(self)
        self.page_rh = PagePersonnel(self)
        self.page_conges = PageConges(self)
        self.page_fa = PageFa(self)
        self.page_sortants = PageSortants(self)
        self.page_docs = PageDocuments(self)
        self.page_calendrier = PageCalendrier(self)
        self.page_guide = PageGuide(self)
        self.page_stats = PageStatistiques(self)
        self.page_inscriptions = PageInscriptions(self)
        self.page_absences = PageAbsences(self)
        self.page_soutien = PageSoutien(self)
        self.page_projet = PageProjet(self)
        self.page_pv_rh = PagePvRh(self)
        self.page_passation = PagePassation(self)
        self.page_inventaire = PageInventaire(self)
        self.page_structure = PageStructure(self)
        self.page_parents = PageParents(self)
        self.page_sabboura = PageSabboura(self)
        self.pages = {"لوحة القيادة": self.tableau, "برنامج العمل": self.page_calendrier, "التلاميذ": self.page_eleves,
                      "التلاميذ القدامى": self.page_anciens,
                      "حركية التلاميذ": self.page_mouvements, "تتبع السلوك": self.page_comportement,
                      "مجالس الأقسام": self.page_conseils, "جمعية دعم مدرسة النجاح": self.page_asso, "الصرف": self.page_achats, "مجالس المؤسسة": self.page_conseils_etab, "أداء المؤسسة": self.page_perf, "التعلمات الأساس": self.page_tarl, "الأندية والأنشطة": self.page_vie, "الريادة": self.page_riyada, "التنظيم التربوي": self.page_tanzim, "محاضر نهاية الأسدوس": self.page_deliberations,
                      "الامتحان": self.page_examen, "الاستيراد من مسار": self.page_import,
                      "الموارد البشرية": self.page_rh, "الرخص": self.page_conges, "تدبير الفائض": self.page_fa,
                      "سجل الصادر": self.page_sortants, "إعداد المؤسسة": self.page_etab, "الوثائق": self.page_docs,
                      "دليل الاستخدام": self.page_guide, "الإحصائيات": self.page_stats,
                      "التسجيلات": self.page_inscriptions, "تتبع الغياب": self.page_absences,
                      "الدعم التربوي": self.page_soutien,
                      "مشروع المؤسسة": self.page_projet, "محاضر الموارد البشرية": self.page_pv_rh,
                      "تسليم المهام": self.page_passation, "الجرد": self.page_inventaire,
                      "البنية المادية": self.page_structure, "أولياء الأمور": self.page_parents,
                      "السبورة المرجعية": self.page_sabboura}
        from idara.ui import vidage_ui
        vidage_ui.installer(self)   # تفريغ كل مكوّن من صفحته (طلب المدير 2026-11-07)
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
        self._boutons_suppression()
        self._disposition = h
        self.barre = self._barre_laterale()
        h.addWidget(self.barre)
        from idara.ui.annees_ui import BandeauArchive
        droite = QWidget()
        dv = QVBoxLayout(droite)
        dv.setContentsMargins(0, 0, 0, 0)
        dv.setSpacing(0)
        self.bandeau_archive = BandeauArchive(self)   # الاطلاع على سنة ماضية (طلب المدير 2026-11-12)
        dv.addWidget(self.bandeau_archive)
        dv.addWidget(self.pile, 1)
        h.addWidget(droite, 1)
        self.setCentralWidget(centre)
        self.aller(0)

    def _boutons_suppression(self) -> None:
        """أزرار الحذف بالأحمر مع علامة الحذف (اقتراح المدير 2026-11-03)."""
        for b in self.findChildren(QPushButton):
            if b.text().strip().startswith("حذف"):
                b.setObjectName("danger")
                b.setIcon(icones.corbeille())
                b.style().unpolish(b)
                b.style().polish(b)

    def _barre_laterale(self) -> QWidget:
        barre = BarreLaterale()
        barre.setObjectName("barreLaterale")
        barre.setFixedWidth(300)
        v = QVBoxLayout(barre)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        v.addWidget(BandeZellige())
        tete = QHBoxLayout()
        tete.setContentsMargins(20, 20, 20, 16)
        tete.setSpacing(12)
        tete.addWidget(LogoMarque(44), 0, Qt.AlignTop)
        noms = QVBoxLayout()
        noms.setSpacing(0)
        a = QLabel(marque.NOM_COURT)   # «الشامل» بخط العناوين، وتحته «في الإدارة التربوية بالمغرب»
        a.setObjectName("navTitre")
        a.setToolTip(NOM_APPLICATION)
        s = QLabel(marque.SOUS_TITRE)
        s.setObjectName("navSous")
        self.nom_etab = QLabel()
        self.nom_etab.setObjectName("navSous")
        self.nom_etab.setWordWrap(True)
        noms.addWidget(a)
        noms.addWidget(s)
        noms.addWidget(self.nom_etab)
        tete.addLayout(noms, 1)
        v.addLayout(tete)
        # السنة الدراسية المفتوحة: فتح سنة جديدة أو الاطلاع على السنوات الماضية (طلب المدير 2026-11-12)
        self.b_annee = QPushButton()
        self.b_annee.setObjectName("boutonAnnee")
        self.b_annee.setCursor(Qt.PointingHandCursor)
        self.b_annee.setToolTip("السنوات الدراسية: فتح سنة جديدة، أو الاطلاع على معطيات سنة ماضية")
        self.b_annee.clicked.connect(lambda: self.gerer_annees())
        ra = QHBoxLayout()
        ra.setContentsMargins(14, 0, 14, 10)
        ra.addWidget(self.b_annee)
        v.addLayout(ra)
        # البحث في الصفحات (اقتراح المدير 2026-11-06)
        self.recherche = QLineEdit()
        self.recherche.setObjectName("rechercheNav")
        self.recherche.setPlaceholderText("ابحث: صفحة، تلميذ، موظف… (Ctrl+K)")
        self.recherche.setClearButtonEnabled(True)
        self.recherche.textChanged.connect(self.filtrer_nav)
        self.recherche.returnPressed.connect(self.ouvrir_premier_resultat)
        rv = QHBoxLayout()
        rv.setContentsMargins(14, 0, 14, 10)
        rv.addWidget(self.recherche)
        v.addLayout(rv)
        # البحث الشامل (2026-11-13): التلاميذ والموظفون أيضاً، والنقر يفتح البطاقة. Ctrl+K يضع المؤشر في البحث
        from PySide6.QtGui import QKeySequence, QShortcut
        from PySide6.QtWidgets import QListWidget
        self.liste_personnes = QListWidget()
        self.liste_personnes.setObjectName("rechercheListe")
        self.liste_personnes.setMaximumHeight(190)
        self.liste_personnes.hide()
        self.liste_personnes.itemClicked.connect(self.ouvrir_personne)
        lp = QHBoxLayout()
        lp.setContentsMargins(14, 0, 14, 6)
        lp.addWidget(self.liste_personnes)
        v.addLayout(lp)
        QShortcut(QKeySequence("Ctrl+K"), self, activated=lambda: (self.recherche.setFocus(), self.recherche.selectAll()))
        self.aucun_resultat = QLabel("لا صفحة بهذا الاسم.")
        self.aucun_resultat.setObjectName("navSous")
        self.aucun_resultat.setContentsMargins(20, 0, 20, 6)
        self.aucun_resultat.hide()
        v.addWidget(self.aucun_resultat)

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
            b = BoutonNav(nom, nom if prog else f"{nom}  ·  قريباً", deroulant, len(fils))
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
        # إقفال البرنامج تحت الإعدادات (طلب المدير 2026-11-09): يُغلق بعد النسخة الاحتياطية المعتادة عند الإغلاق
        self.b_quitter = QPushButton("⏻  إقفال البرنامج")
        self.b_quitter.setObjectName("navQuitter")
        self.b_quitter.setCursor(Qt.PointingHandCursor)
        self.b_quitter.setToolTip("يُغلق البرنامج بعد حفظ نسخة احتياطية.")
        self.b_quitter.clicked.connect(self.close)
        nav.addSpacing(6)
        nav.addWidget(self.b_quitter)
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
        self.etat_sauvegarde.setObjectName("navSous")
        bv.addWidget(self.etat_sauvegarde)
        b = QPushButton("نسخ إلى قرص خارجي")
        b.clicked.connect(self.exporter)
        bv.addWidget(b)
        v.addWidget(bas)
        self.rafraichir_entete()
        return barre

    def rafraichir_entete(self) -> None:
        from idara.ui.annees_ui import libelle_bouton
        e = etab_srv.lire_etablissement(self.conn)
        self.nom_etab.setText(e.nom_ar if e else "")
        self.b_annee.setText(libelle_bouton(self.conn))
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

    # ---------- البحث في الصفحات ----------
    def resultats_recherche(self, texte: str) -> list[str]:
        """الصفحات المطابقة لنص البحث (كل كلماته في اسم الصفحة أو قسمها أو كلماتها المفتاحية)."""
        mots = normaliser_recherche(texte).split()
        res = []
        for titre, fils in SECTIONS:
            for page, lib in fils:
                cible = normaliser_recherche(f"{lib} {titre} {page} {MOTS_CLES.get(page, '')}")
                if mots and all(m in cible for m in mots):
                    res.append(page)
        return res

    def resultats_personnes(self, texte: str, limite: int = 8) -> list[tuple[str, int, str]]:
        """تلاميذ وموظفون يطابقون النص (حرفان على الأقل): (النوع، المعرف، ما يُعرض)."""
        t = " ".join((texte or "").split())
        if len(t) < 2:
            return []
        res = []
        try:
            for r in el.rechercher(self.conn, t, limite=limite):
                res.append(("eleve", r["id"], f"تلميذ · {r['prenom_ar']} {r['nom_ar']} · {r['classe'] or ''}"))
        except Exception:  # noqa: BLE001
            pass
        mots = normaliser_recherche(t).split()
        for p in rh.lister(self.conn, actifs_seulement=False):
            cible = normaliser_recherche(f"{p.prenom_ar} {p.nom_ar} {p.ppr or ''} {p.nom_fr or ''} {p.prenom_fr or ''}")
            if all(m in cible for m in mots) or t.lower() in cible.lower():
                res.append(("personnel", p.id, f"موظف · {p.prenom_ar} {p.nom_ar}"))
        return res[:limite + 4]

    def _maj_personnes(self, texte: str) -> None:
        from PySide6.QtWidgets import QListWidgetItem
        ps = self.resultats_personnes(texte)
        self.liste_personnes.clear()
        for typ, ident, lib in ps:
            it = QListWidgetItem(lib)
            it.setData(Qt.UserRole, (typ, ident))
            self.liste_personnes.addItem(it)
        self.liste_personnes.setVisible(bool(ps))

    def ouvrir_personne(self, it) -> None:
        typ, ident = it.data(Qt.UserRole)
        self.recherche.clear()
        if typ == "eleve":
            self.aller_a("التلاميذ")
            self.page_eleves.afficher(ident)
        else:
            self.aller_a("الموارد البشرية")
            self.page_rh.afficher(ident)

    def filtrer_nav(self, texte: str) -> list[str]:
        res = self.resultats_recherche(texte)
        self._maj_personnes(texte)
        if not texte.strip():
            for k, (_, fils) in enumerate(SECTIONS):
                self.boutons[k].show()
                for sb in self.sous[k]:
                    sb.show()
            courante = self.page_courante()
            self.basculer(self.section_de[courante] if courante else 0, True)
            self.aucun_resultat.hide()
            return []
        for k, (_, fils) in enumerate(SECTIONS):
            pages = [pg for pg, _ in fils]
            vis = [pg in res for pg in pages]
            self.boutons[k].setVisible(any(vis))
            for sb, v in zip(self.sous[k], vis):
                sb.setVisible(v)
            self.blocs[k].setVisible(any(vis) and bool(self.sous[k]))
            self.boutons[k].ouvrir(any(vis))
        self.aucun_resultat.setVisible(not res and self.liste_personnes.isHidden())
        return res

    def ouvrir_premier_resultat(self) -> None:
        res = self.resultats_recherche(self.recherche.text())
        if res:
            self.recherche.clear()
            self.aller_a(res[0])
        elif self.liste_personnes.count():
            self.ouvrir_personne(self.liste_personnes.item(0))

    # ---------- السنوات الدراسية ----------
    def gerer_annees(self):
        from idara.ui.annees_ui import DialogueAnnees
        d = DialogueAnnees(self)
        d.open()
        return d

    def changer_annee(self, libelle: str) -> None:
        annee_srv.consulter(self.conn, libelle)
        self.annee_changee()

    def annee_changee(self) -> None:
        """بعد تغيير السنة المفتوحة: الشريط، والتنبيه، وإعادة تحميل الصفحة الحالية."""
        self.rafraichir_entete()
        self.bandeau_archive.actualiser()
        courante = self.page_courante()
        if courante:
            self._rafraichir(courante)
        self.tableau.rafraichir()

    # ---------- المظهر ----------
    def appliquer_theme(self, nom: str) -> None:
        """يغيّر مظهر البرنامج فوراً ويحفظه في إعدادات الجهاز (اقتراح المدير 2026-11-06)."""
        # على النافذة الرئيسية فقط (نوافذها الفرعية ترثه): إعادة تنسيق التطبيق كله تمر على كل نافذة في الذاكرة
        feuille = theme.appliquer(nom)
        QApplication.instance().setFont(theme.charger_police())   # لكل مظهر خطه
        self.setStyleSheet(feuille)
        config_srv.ecrire_config(theme=theme.THEME_ACTUEL)
        courante = self.page_courante()
        ancienne = self.barre
        self.barre = self._barre_laterale()
        self._disposition.replaceWidget(ancienne, self.barre)
        ancienne.deleteLater()
        if courante:
            self.aller_a(courante)
        self.tableau.rafraichir()

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

    def reinitialiser(self, mot: str | None = None) -> Path | None:
        """تصفير البرنامج بعد تأكيد مكتوب. mot (للاختبار) يعوّض نافذة التأكيد."""
        if mot is None:
            mot, ok = QInputDialog.getText(
                self, "تصفير البرنامج",
                "سيُحذف كل ما أُدخل في البرنامج، وتُحفظ قبل ذلك نسخة كاملة في مجلد النسخ الاحتياطية.\n"
                f"للتأكيد اكتب كلمة: {sauvegarde.MOT_CONFIRMATION}")
            if not ok:
                return None
        if mot.strip() != sauvegarde.MOT_CONFIRMATION:
            message(self.page_etab.message, "لم يُكتب التأكيد كما هو مطلوب؛ لم يُحذف شيء.", True)
            return None
        self.conn.close()
        try:
            securite = sauvegarde.reinitialiser(self.dossier)
        except Exception as e:  # noqa: BLE001
            self.conn = ouvrir_base(self.dossier.base)
            QMessageBox.critical(self, "تصفير البرنامج", f"تعذر التصفير، ولم يُحذف شيء: {e}")
            return None
        self.reinitialise = True
        self.reinitialisation.emit(securite)
        self.close()
        return securite

    def closeEvent(self, ev) -> None:
        if getattr(self, "reinitialise", False):   # القاعدة حُذفت: لا نسخ ولا اتصال
            super().closeEvent(ev)
            return
        try:
            sauvegarde.sauvegarde_quotidienne(self.dossier)
        except Exception:  # noqa: BLE001 — لا نمنع الإغلاق بسبب النسخ
            pass
        self.conn.close()
        super().closeEvent(ev)
