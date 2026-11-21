"""صفحة «شاشة العرض» (طلب المدير 2026-11-21): اختيار الشرائح وترتيبها ومدتها، معاينتها، ثم عرضها بملء الشاشة
على التلفاز أو تصديرها PDF وصوراً لمفتاح USB."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QGridLayout, QHBoxLayout, QLabel,
                               QLineEdit, QSizePolicy, QToolButton, QVBoxLayout, QWidget)

from idara.services import ecran as ec
from idara.ui import ecran_affichage as ea
from idara.ui.composants import carte, entete
from idara.ui.saisie import message
from idara.ui.vitrine import bouton_couleur


class Apercu(QWidget):
    """معاينة مصغرة لشريحة بنسبة 16:9."""

    def __init__(self):
        super().__init__()
        self.d: dict | None = None
        self.ident: dict = {}
        self.bandeau = ""
        self.setMinimumSize(480, 270)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def hasHeightForWidth(self):   # noqa: N802
        return True

    def heightForWidth(self, w):   # noqa: N802
        return int(w * 9 / 16)

    def sizeHint(self):   # noqa: N802
        return QSize(800, 450)

    def paintEvent(self, e):   # noqa: N802
        p = QPainter(self)
        w = self.width()
        h = min(self.height(), int(w * 9 / 16))
        r = QRectF(0, (self.height() - h) / 2, h * 16 / 9, h)
        if self.d is not None:
            ea.peindre(p, r, self.d, self.ident)
            if self.bandeau:
                u = r.height() / ea.HAUTEUR
                ea.peindre_bandeau(p, QRectF(r.left(), r.bottom() - 70 * u, r.width(), 70 * u), u, self.bandeau, 0)
        p.end()


class PageEcran(QWidget):
    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        self.fenetre_affichage = None
        racine = QVBoxLayout(self)
        racine.setContentsMargins(40, 32, 40, 32)
        racine.setSpacing(18)
        racine.addWidget(entete("شاشة العرض",
                                "عرض عصري يعرّف بالمؤسسة وأرقامها ونتائجها على تلفاز أو شاشة، أمام الزوار والآباء "
                                "والمرتفقين واللجان. الشرائح تُبنى من معطيات البرنامج مباشرة، وتُحدَّث وحدها. "
                                "أرقام مجمَّعة فقط: لا أسماء تلاميذ ولا نقط فردية."))
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.hide()
        racine.addWidget(self.message)

        # أزرار العرض والتصدير
        h = QHBoxLayout()
        h.setSpacing(10)
        self.b_lancer = bouton_couleur("بدء العرض بملء الشاشة", "#0B1C2C", "apercu",
                                       "Esc للخروج · الأسهم للتنقل · المسافة للإيقاف المؤقت")
        self.b_lancer.setMinimumHeight(52)
        self.b_lancer.clicked.connect(lambda: self.lancer())
        h.addWidget(self.b_lancer)
        h.addWidget(QLabel("على الشاشة:"))
        self.c_ecran = QComboBox()
        h.addWidget(self.c_ecran)
        self.b_pdf = bouton_couleur("تصدير PDF", "#B5462F", "exporter", "شريحة في كل صفحة")
        self.b_pdf.clicked.connect(lambda: self.exporter_pdf())
        self.b_images = bouton_couleur("صور للتلفاز (مفتاح USB)", "#1E6B66", "image",
                                       "صور 1920×1080 مرقمة بالترتيب، يعرضها التلفاز دون حاسوب")
        self.b_images.clicked.connect(lambda: self.exporter_images())
        h.addStretch()
        self.b_logo = bouton_couleur("شعار المؤسسة", "#6A1B9A", "image", "صورة PNG أو JPG تظهر في الغلاف وأسفل الشرائح")
        self.b_logo.clicked.connect(lambda: self.choisir_logo())
        h.addWidget(self.b_logo)
        h.addWidget(self.b_pdf)
        h.addWidget(self.b_images)
        racine.addLayout(h)

        corps = QHBoxLayout()
        corps.setSpacing(20)
        # المعاينة
        c, v = carte("المعاينة")
        self.apercu = Apercu()
        v.addWidget(self.apercu, 1)
        hn = QHBoxLayout()
        self.b_prec = bouton_couleur("السابقة", "#1F3B57", "retour")
        self.b_prec.clicked.connect(lambda: self.voir(self.indice - 1))
        self.l_position = QLabel()
        self.l_position.setAlignment(Qt.AlignCenter)
        self.l_position.setObjectName("etiquette")
        self.b_suiv = bouton_couleur("التالية", "#1F3B57", "envoyer")
        self.b_suiv.clicked.connect(lambda: self.voir(self.indice + 1))
        hn.addWidget(self.b_prec)
        hn.addWidget(self.l_position, 1)
        hn.addWidget(self.b_suiv)
        v.addLayout(hn)
        corps.addWidget(c, 3)
        # الشرائح
        c2, v2 = carte("الشرائح وترتيبها ومدتها")
        aide = QLabel("علّم الشرائح التي تظهر، ورتّبها بالسهمين، واختر مدة كل واحدة. الشريحة التي لا معطيات لها "
                      "بعد لا تُعرض.")
        aide.setObjectName("etiquette")
        aide.setWordWrap(True)
        v2.addWidget(aide)
        self.grille = QGridLayout()
        self.grille.setVerticalSpacing(8)
        v2.addLayout(self.grille)
        v2.addWidget(QLabel("الشريط المتحرك أسفل الشاشة:"))
        self.c_bandeau = QLineEdit()
        self.c_bandeau.editingFinished.connect(lambda: self.enregistrer())
        v2.addWidget(self.c_bandeau)
        v2.addStretch()
        corps.addWidget(c2, 2)
        racine.addLayout(corps)
        racine.addStretch()
        self.lignes: dict[str, dict] = {}
        self.indice = 0
        self.diapos: list[dict] = []

    # ---- الإعدادات ----
    def _construire_lignes(self) -> None:
        while self.grille.count():
            it = self.grille.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        r = ec.reglages(self.f.conn)
        desc = {c: d for c, _, d in ec.CATALOGUE}
        self.lignes = {}
        for i, cle in enumerate(r["ordre"]):
            cb = QCheckBox(ec.TITRES[cle], self)
            cb.setChecked(cle in r["actives"])
            cb.setToolTip(desc[cle])
            cb.setStyleSheet("font-weight: 700;")
            cb.toggled.connect(lambda _: self.enregistrer())
            du = QComboBox(self)
            for s in ec.DUREES:
                du.addItem(f"{s} ثانية", s)
            k = du.findData(r["durees"][cle])
            if k < 0:
                du.addItem(f"{r['durees'][cle]} ثانية", r["durees"][cle])
                k = du.count() - 1
            du.setCurrentIndex(k)
            du.currentIndexChanged.connect(lambda _: self.enregistrer())
            haut = QToolButton(self)
            bas = QToolButton(self)
            haut.setArrowType(Qt.UpArrow)
            bas.setArrowType(Qt.DownArrow)
            haut.setToolTip("تقديم الشريحة")
            bas.setToolTip("تأخير الشريحة")
            for b in (haut, bas):
                b.setFixedSize(36, 32)
                b.setCursor(Qt.PointingHandCursor)
            haut.clicked.connect(lambda _=False, c=cle: self.deplacer(c, -1))
            bas.clicked.connect(lambda _=False, c=cle: self.deplacer(c, 1))
            haut.setEnabled(i > 0)
            bas.setEnabled(i < len(r["ordre"]) - 1)
            bp = bouton_couleur("النقاط", "#B07A16", "valider", "اختر ما يُعرض من نقاط هذه الشريحة")
            bp.setMinimumHeight(32)
            bp.clicked.connect(lambda _=False, c=cle: self.ouvrir_points(c))
            self.grille.addWidget(cb, i, 0)
            self.grille.addWidget(bp, i, 1)
            self.grille.addWidget(du, i, 2)
            self.grille.addWidget(haut, i, 3)
            self.grille.addWidget(bas, i, 4)
            self.lignes[cle] = {"case": cb, "duree": du, "points": bp}
        self.grille.setColumnStretch(0, 1)
        self.c_bandeau.blockSignals(True)
        self.c_bandeau.setText(r["bandeau"])
        self.c_bandeau.setPlaceholderText(ec.bandeau_defaut(self.f.conn))
        self.c_bandeau.blockSignals(False)

    def ordre(self) -> list[str]:
        return list(self.lignes)

    def enregistrer(self) -> bool:
        try:
            ec.enregistrer_reglages(self.f.conn, self.ordre(),
                                    [c for c, l in self.lignes.items() if l["case"].isChecked()],
                                    {c: l["duree"].currentData() for c, l in self.lignes.items()},
                                    self.c_bandeau.text())
        except ec.ErreurEcran as e:
            message(self.message, str(e), True)
            return False
        self.message.hide()
        self._charger_diapos()
        return True

    def deplacer(self, cle: str, sens: int) -> None:
        o = self.ordre()
        i = o.index(cle)
        j = i + sens
        if not 0 <= j < len(o):
            return
        o[i], o[j] = o[j], o[i]
        r = ec.reglages(self.f.conn)
        ec.enregistrer_reglages(self.f.conn, o, [c for c in o if self.lignes[c]["case"].isChecked()] or r["actives"],
                                {c: self.lignes[c]["duree"].currentData() for c in o}, self.c_bandeau.text())
        self._construire_lignes()
        self._charger_diapos()

    # ---- النقاط والمنجزات والشعار (الدفعة الثانية 2026-11-21) ----
    def ouvrir_points(self, cle: str):
        """نافذة منبثقة: كل نقاط الشريحة بعلامات؛ إزالة العلامة تُخفي النقطة من العرض."""
        from idara.ui.vitrine import FenetreFiche
        w = QWidget()
        v = QVBoxLayout(w)
        self.cases_points: dict[str, QCheckBox] = {}
        if cle == "realisations":
            v.addWidget(self._formulaire_realisation())
        pts = ec.points(self.f.conn, cle)
        if not pts:
            l = QLabel("لا نقاط في هذه الشريحة بعد." + (" أضف منجزاً أعلاه." if cle == "realisations" else ""))
            l.setObjectName("etiquette")
            l.setWordWrap(True)
            v.addWidget(l)
        for pt in pts:
            hl = QHBoxLayout()
            c = QCheckBox(pt["libelle"], w)
            c.setChecked(pt["affiche"])
            self.cases_points[pt["id"]] = c
            hl.addWidget(c, 1)
            if cle == "realisations":
                b = bouton_couleur("حذف", "#C62828", "annuler")
                b.setObjectName("danger")
                b.clicked.connect(lambda _=False, i=pt["id"]: self.supprimer_realisation(int(i)))
                hl.addWidget(b)
            v.addLayout(hl)
        hb = QHBoxLayout()
        b = bouton_couleur("حفظ الاختيار", "#2E7D32", "enregistrer")
        b.clicked.connect(lambda: self.enregistrer_points(cle))
        tous = bouton_couleur("تعليم الكل", "#1F3B57", "valider")
        tous.clicked.connect(lambda: [c.setChecked(True) for c in self.cases_points.values()])
        hb.addWidget(b)
        hb.addWidget(tous)
        hb.addStretch()
        v.addLayout(hb)
        v.addStretch()
        if getattr(self, "fiche_points", None) is not None:
            self.fiche_points.hide()
            self.fiche_points.deleteLater()
        self.fiche_points = FenetreFiche(self, f"نقاط الشريحة: {ec.TITRES[cle]}",
                                         "علّم ما تريد عرضه وأزل العلامة عما لا تريد عرضه.", w, largeur=720)
        self.cle_points = cle
        self.fiche_points.ouvrir()
        return self.fiche_points

    def _formulaire_realisation(self) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 8)
        self.c_axe = QComboBox(w)
        for k, lib in ec.AXES:
            self.c_axe.addItem(lib, k)
        self.c_realisation = QLineEdit(w)
        self.c_realisation.setPlaceholderText("مثال: تجهيز قاعة متعددة الوسائط")
        self.c_realisation.setMaxLength(140)
        b = bouton_couleur("إضافة المنجز", "#1565C0", "ajouter")
        b.clicked.connect(lambda: self.ajouter_realisation())
        h.addWidget(self.c_axe)
        h.addWidget(self.c_realisation, 1)
        h.addWidget(b)
        return w

    def ajouter_realisation(self, axe: str | None = None, texte: str | None = None):
        axe = axe or self.c_axe.currentData()
        texte = self.c_realisation.text() if texte is None else texte
        try:
            l = ec.ajouter_realisation(self.f.conn, axe, texte)
        except ec.ErreurEcran as e:
            message(self.message, str(e), True)
            return None
        self.ouvrir_points("realisations")
        self._charger_diapos()
        return l

    def supprimer_realisation(self, rid: int) -> None:
        ec.supprimer_realisation(self.f.conn, rid)
        self.ouvrir_points("realisations")
        self._charger_diapos()

    def enregistrer_points(self, cle: str | None = None) -> None:
        cle = cle or self.cle_points
        ec.definir_masques(self.f.conn, cle, [i for i, c in self.cases_points.items() if not c.isChecked()])
        self.fiche_points.hide()
        self._charger_diapos()
        message(self.message, f"حُفظت نقاط «{ec.TITRES[cle]}».")

    def choisir_logo(self, chemin=None, retirer: bool = False):
        if not retirer and chemin is None:
            from PySide6.QtWidgets import QFileDialog
            chemin, _ = QFileDialog.getOpenFileName(self, "شعار المؤسسة لشاشة العرض", str(Path.home()),
                                                    "Images (*.png *.jpg *.jpeg)")
            if not chemin:
                return None
        try:
            rel = ec.definir_logo(self.f.conn, self.f.dossier, None if retirer else chemin)
        except ec.ErreurEcran as e:
            message(self.message, str(e), True)
            return None
        self._charger_diapos()
        message(self.message, "أُضيف شعار المؤسسة إلى العرض." if rel else "أزيل الشعار من العرض.")
        return rel

    # ---- المعاينة والعرض ----
    def bandeau(self) -> str:
        return self.c_bandeau.text().strip() or ec.bandeau_defaut(self.f.conn)

    def _charger_diapos(self) -> None:
        self.diapos = ec.diaporama(self.f.conn)
        self.voir(min(self.indice, max(0, len(self.diapos) - 1)))

    def voir(self, i: int) -> None:
        n = len(self.diapos)
        self.indice = i % n if n else 0
        self.apercu.ident = ec.identite(self.f.conn, self.f.dossier)
        self.apercu.bandeau = self.bandeau()
        self.apercu.d = self.diapos[self.indice] if n else None
        self.l_position.setText(f"الشريحة {self.indice + 1} من {n} · {self.diapos[self.indice]['titre']}" if n
                                else "لا شرائح مختارة")
        self.apercu.update()

    def rafraichir(self) -> None:
        self._construire_lignes()
        self.c_ecran.clear()
        for k, s in enumerate(ea.ecrans()):
            g = s.geometry()
            self.c_ecran.addItem(f"الشاشة {k + 1} ({g.width()}×{g.height()})", k)
        if self.c_ecran.count() > 1:
            self.c_ecran.setCurrentIndex(1)   # التلفاز الموصول غالباً هو الشاشة الثانية
        self._charger_diapos()

    def lancer(self):
        if not self.diapos:
            message(self.message, "لا شرائح للعرض: علّم شريحة واحدة على الأقل.", True)
            return None
        e = ea.ecrans()
        k = self.c_ecran.currentData()
        ecran = e[k] if k is not None and 0 <= k < len(e) else None
        self.fenetre_affichage = ea.FenetreAffichage(self.f.conn, ec.diaporama(self.f.conn),
                                                     ec.identite(self.f.conn, self.f.dossier), self.bandeau(), ecran)
        return self.fenetre_affichage.ouvrir()

    def exporter_pdf(self, chemin=None):
        if chemin is None:
            nom = f"شاشة العرض {datetime.now():%Y-%m-%d}.pdf"
            f, _ = QFileDialog.getSaveFileName(self, "تصدير شاشة العرض PDF", str(Path.home() / nom), "PDF (*.pdf)")
            if not f:
                return None
            chemin = Path(f)
        if not self.diapos:
            message(self.message, "لا شرائح للتصدير.", True)
            return None
        p = ea.exporter_pdf(self.diapos, ec.identite(self.f.conn, self.f.dossier), chemin, self.bandeau())
        message(self.message, f"صُدّر العرض PDF ({len(self.diapos)} شرائح): ⁦{p.name}⁩")
        try:
            from idara.services import bureautique
            bureautique.ouvrir_externe(p)
        except Exception:  # noqa: BLE001
            pass
        return p

    def exporter_images(self, dossier=None):
        if dossier is None:
            d = QFileDialog.getExistingDirectory(self, "اختر مفتاح USB أو مجلداً لصور العرض", str(Path.home()))
            if not d:
                return None
            dossier = Path(d) / "شاشة العرض"
        if not self.diapos:
            message(self.message, "لا شرائح للتصدير.", True)
            return None
        fichiers = ea.exporter_images(self.diapos, ec.identite(self.f.conn, self.f.dossier), Path(dossier), self.bandeau())
        message(self.message, f"حُفظت {len(fichiers)} صور في المجلد «{Path(dossier).name}». ضع المفتاح في التلفاز "
                              "واختر عرض الصور التلقائي.")
        return fichiers

