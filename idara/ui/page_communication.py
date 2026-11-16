"""صفحة «الإعلام والتواصل» (طلب المدير 2026-11-15): إعلانات مزخرفة (10 قوالب، A4 أو A3)، استدعاءات أولياء
الأمور باسم كل تلميذ (عدة استدعاءات في الصفحة)، وسجل الإعلانات النصية."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QComboBox, QFileDialog, QGridLayout, QHBoxLayout,
                               QLabel, QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget)

from idara.services import affiches as af
from idara.services import annee as annee_srv
from idara.services import bureautique
from idara.services import convocations as cv
from idara.services import etablissement as etab_srv
from idara.services import textes as tx
from idara.ui import affiche_qt
from idara.ui.composants import carte
from idara.ui.formulaires import champ, etiquette
from idara.ui.page_pedagogie import _page
from idara.ui.page_registre import VueRegistre
from idara.ui.saisie import ChampDate, cellule, message, tableau

_EXEMPLE = af.Contenu(titre="عنوان الإعلان", texte="", surtitre="إعلان")


class VueAffiche(QWidget):
    """قالب ← مناسبة ← معطيات ← معاينة حية ← طبع أو حفظ."""

    def __init__(self, page):
        super().__init__()
        self.page, self.f = page, page.f
        self.theme = "zellige"
        v0 = QVBoxLayout(self)
        v0.setContentsMargins(0, 0, 0, 0)
        v0.setSpacing(16)

        c, v = carte("١ · اختر القالب")
        g = QGridLayout()
        g.setHorizontalSpacing(12)
        g.setVerticalSpacing(6)
        self.groupe = QButtonGroup(self)
        self.vignettes: dict[str, QPushButton] = {}
        for k, (cle, (th, _)) in enumerate(af.THEMES.items()):
            b = QPushButton()
            b.setObjectName("vignette")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setIcon(QIcon(affiche_qt.pixmap(af.composer(cle, _EXEMPLE), 220)))
            b.setIconSize(QSize(110, 156))
            b.setFixedSize(QSize(124, 170))
            b.setToolTip(th.description)
            b.clicked.connect(lambda _=False, cle=cle: self.choisir_theme(cle))
            self.groupe.addButton(b)
            self.vignettes[cle] = b
            nom = QLabel(th.nom + (" · يقتصد الحبر" if th.economique else ""))
            nom.setObjectName("etiquette")
            nom.setAlignment(Qt.AlignHCenter)
            g.addWidget(b, (k // 5) * 2, k % 5, Qt.AlignHCenter)
            g.addWidget(nom, (k // 5) * 2 + 1, k % 5)
        v.addLayout(g)
        v0.addWidget(c)

        h0 = QHBoxLayout()
        h0.setSpacing(16)
        c, v = carte("٢ · المناسبة والمعطيات")
        g = QGridLayout()
        g.setHorizontalSpacing(14)
        g.setVerticalSpacing(4)
        self.occasion = QComboBox()
        for o in af.OCCASIONS.values():
            self.occasion.addItem(o.libelle, o.cle)
        self.format = QComboBox()
        self.format.addItem("A4 (ورقة عادية)", "A4")
        self.format.addItem("A3 (ملصق كبير)", "A3")
        self.titre = champ()
        self.surtitre = champ()
        self.date = ChampDate()
        self.heure = champ()
        self.heure.setPlaceholderText("مثلاً 8:30 صباحاً")
        self.lieu = champ()
        self.public = champ()
        self.public.setPlaceholderText("مثلاً تلاميذ المستوى السادس")
        self.note = champ()
        self.texte = QPlainTextEdit()
        self.texte.setFixedHeight(110)
        self.texte.setTabChangesFocus(True)
        champs = [("المناسبة", self.occasion), ("حجم الورق", self.format), ("العنوان الكبير *", self.titre),
                  ("الكلمة فوق العنوان", self.surtitre), ("التاريخ", self.date), ("الساعة", self.heure),
                  ("المكان", self.lieu), ("الفئة المعنية", self.public)]
        for k, (lib, w) in enumerate(champs):
            g.addWidget(etiquette(lib, w), (k // 2) * 2, k % 2)
            g.addWidget(w, (k // 2) * 2 + 1, k % 2)
        g.addWidget(etiquette("نص الإعلان", self.texte), 8, 0, 1, 2)
        g.addWidget(self.texte, 9, 0, 1, 2)
        g.addWidget(etiquette("سطر صغير أسفل الإعلان", self.note), 10, 0, 1, 2)
        g.addWidget(self.note, 11, 0, 1, 2)
        v.addLayout(g)
        aide = QLabel("الحقل الفارغ لا يظهر في الإعلان. النص الطويل يُصغَّر تلقائياً حتى يدخل مكانه.")
        aide.setObjectName("etiquette")
        aide.setWordWrap(True)
        v.addWidget(aide)
        v.addStretch()
        h0.addWidget(c, 3)

        c, v = carte("٣ · المعاينة والطبع")
        self.apercu = QLabel()
        self.apercu.setFixedSize(QSize(340, 481))
        self.apercu.setStyleSheet("border: 1px solid #8E8E99; background: #FFFFFF;")
        v.addWidget(self.apercu, 0, Qt.AlignHCenter)
        h = QHBoxLayout()
        b = QPushButton("طباعة")
        b.setObjectName("principal")
        b.clicked.connect(lambda: self.imprimer())
        h.addWidget(b)
        b = QPushButton("حفظ ملف للطبع")
        b.setToolTip("ملف بالحجم المختار، يُطبع في أي مطبعة أو يُرسل")
        b.clicked.connect(lambda: self.enregistrer_pdf())
        h.addWidget(b)
        b = QPushButton("حفظ صورة")
        b.setToolTip("صورة للإرسال في واتساب أو النشر")
        b.clicked.connect(lambda: self.enregistrer_image())
        h.addWidget(b)
        v.addLayout(h)
        v.addStretch()
        h0.addWidget(c, 2)
        v0.addLayout(h0)

        self.minuteur = QTimer(self)
        self.minuteur.setSingleShot(True)
        self.minuteur.setInterval(250)
        self.minuteur.timeout.connect(self.actualiser)
        for w in (self.titre, self.surtitre, self.heure, self.lieu, self.public, self.note):
            w.textChanged.connect(lambda _: self.minuteur.start())
        self.texte.textChanged.connect(lambda: self.minuteur.start())
        for w in self.date.findChildren(QLineEdit):
            w.textChanged.connect(lambda _: self.minuteur.start())
        self.occasion.currentIndexChanged.connect(lambda _: self.choisir_occasion())
        self.vignettes[self.theme].setChecked(True)
        self.choisir_occasion()

    def rafraichir(self) -> None:
        self.actualiser()

    def choisir_theme(self, cle: str) -> None:
        self.theme = cle
        self.vignettes[cle].setChecked(True)
        self.actualiser()

    def choisir_occasion(self) -> None:
        o = af.OCCASIONS[self.occasion.currentData()]
        a = annee_srv.annee_courante(self.f.conn)
        self.titre.setText(o.titre + (f" {a['libelle']}" if o.cle == "rentree" and a else ""))
        self.surtitre.setText(o.surtitre)
        self.texte.setPlainText(o.texte)
        self.actualiser()

    def contenu(self) -> af.Contenu:
        e = etab_srv.lire_etablissement(self.f.conn)
        try:
            iso = self.date.iso()
        except ValueError:
            iso = ""
        return af.Contenu(
            titre=self.titre.text(), texte=self.texte.toPlainText().strip(), surtitre=self.surtitre.text().strip(),
            date=tx.date_longue_ar(iso) if iso else "", heure=self.heure.text(), lieu=self.lieu.text(),
            public=self.public.text(), note=self.note.text(), etablissement=e.nom_ar if e else "",
            direction=("المديرية الإقليمية: " + e.direction_ar) if e and e.direction_ar else "")

    def dessin(self) -> af.Dessin | None:
        try:
            return af.composer(self.theme, self.contenu())
        except af.ErreurAffiche as e:
            message(self.page.message, str(e), True)
            return None

    def actualiser(self) -> None:
        c = self.contenu()
        if not c.titre.strip():
            c.titre = " "
            d = af.apercu_vide(self.theme)
        else:
            d = af.composer(self.theme, c)
        self.apercu.setPixmap(affiche_qt.pixmap(d, 680).scaled(self.apercu.size(), Qt.KeepAspectRatio,
                                                               Qt.SmoothTransformation))

    def _chemin(self, ext: str) -> Path:
        rep = self.f.dossier.archives / "الإعلانات المزخرفة"
        rep.mkdir(parents=True, exist_ok=True)
        nom = "_".join(self.titre.text().split())[:40] or "إعلان"
        return rep / f"{datetime.now():%Y%m%d_%H%M%S}_{nom}_{self.format.currentData()}.{ext}"

    def enregistrer_pdf(self, cible: Path | None = None, ouvrir: bool = True) -> Path | None:
        d = self.dessin()
        if d is None:
            return None
        p = affiche_qt.exporter_pdf(d, self.format.currentData(), cible or self._chemin("pdf"))
        message(self.page.message, f"حُفظ الإعلان ({self.format.currentData()}): ⁦{p.name}⁩")
        if ouvrir:
            try:
                bureautique.ouvrir(p)
            except OSError:
                pass
        return p

    def enregistrer_image(self, cible: Path | None = None) -> Path | None:
        d = self.dessin()
        if d is None:
            return None
        if cible is None:
            nom, _ = QFileDialog.getSaveFileName(self, "حفظ صورة الإعلان", str(self._chemin("png")), "PNG (*.png)")
            if not nom:
                return None
            cible = Path(nom)
        p = affiche_qt.exporter_image(d, cible)
        message(self.page.message, f"حُفظت الصورة: ⁦{p.name}⁩")
        return p

    def imprimer(self) -> bool:
        d = self.dessin()
        if d is None:
            return False
        if affiche_qt.imprimer(d, self.format.currentData(), self):
            message(self.page.message, "أُرسل الإعلان إلى الطابعة.")
            return True
        return False


class VueConvocations(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page, self.f = page, page.f
        v0 = QVBoxLayout(self)
        v0.setContentsMargins(0, 0, 0, 0)
        v0.setSpacing(16)
        c, v = carte("المناسبة والموعد")
        g = QGridLayout()
        g.setHorizontalSpacing(14)
        g.setVerticalSpacing(4)
        self.occasion = QComboBox()
        for cle, (titre, _) in cv.OCCASIONS.items():
            self.occasion.addItem(titre, cle)
        self.numero = QComboBox()
        self.date = ChampDate()
        self.heure = champ()
        self.heure.setPlaceholderText("مثلاً 10:00")
        self.lieu = champ()
        self.lieu.setPlaceholderText("مثلاً قاعة الاجتماعات")
        self.par_page = QComboBox()
        for n in cv.PAR_PAGE:
            self.par_page.addItem(f"{n} في الصفحة" if n > 1 else "استدعاء واحد في الصفحة", n)
        self.par_page.setCurrentIndex(cv.PAR_PAGE.index(4))
        self.l_numero = etiquette("الرقم", self.numero)
        for k, (lib, w) in enumerate(((etiquette("المناسبة", self.occasion), self.occasion),
                                      (self.l_numero, self.numero),
                                      (etiquette("التاريخ *", self.date), self.date),
                                      (etiquette("الساعة *", self.heure), self.heure),
                                      (etiquette("المكان", self.lieu), self.lieu),
                                      (etiquette("اقتصاد الورق", self.par_page), self.par_page))):
            g.addWidget(lib, (k // 3) * 2, k % 3)
            g.addWidget(w, (k // 3) * 2 + 1, k % 3)
        self.ordre = QPlainTextEdit()
        self.ordre.setFixedHeight(64)
        self.ordre.setPlaceholderText("جدول الأعمال (اختياري): نقطة في كل سطر")
        g.addWidget(self.ordre, 4, 0, 1, 3)
        v.addLayout(g)
        v0.addWidget(c)

        c, v = carte("المدعوون")
        h = QHBoxLayout()
        self.classe = QComboBox()
        self.classe.currentIndexChanged.connect(lambda _: self.afficher())
        h.addWidget(self.classe)
        self.nb = QLabel()
        self.nb.setObjectName("etiquette")
        self.nb.setWordWrap(True)
        h.addWidget(self.nb, 1)
        b = QPushButton("توليد الاستدعاءات")
        b.setObjectName("principal")
        b.clicked.connect(lambda: self.generer())
        h.addWidget(b)
        v.addLayout(h)
        self.table = tableau(["التلميذ(ة)", "القسم", "تاريخ الازدياد", "رقم مسار"], etirer=0)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setMinimumHeight(300)
        self.table.itemSelectionChanged.connect(self._compte)
        v.addWidget(self.table)
        v0.addWidget(c)
        self.lignes: list[dict] = []
        self.occasion.currentIndexChanged.connect(lambda _: self._numeros())
        self.par_page.currentIndexChanged.connect(lambda _: self._compte())
        self._numeros()

    def _numeros(self) -> None:
        nums = cv.OCCASIONS[self.occasion.currentData()][1]
        self.numero.clear()
        self.numero.addItems(list(nums))
        self.numero.setVisible(bool(nums))
        self.l_numero.setVisible(bool(nums))

    def rafraichir(self) -> None:
        a = annee_srv.annee_courante(self.f.conn)
        actuel = self.classe.currentData()
        self.classe.blockSignals(True)
        self.classe.clear()
        self.classe.addItem("كل الأقسام", None)
        if a:
            for r in self.f.conn.execute("SELECT id, code FROM classe WHERE annee_id=? ORDER BY code", (a["id"],)):
                self.classe.addItem(r["code"], r["id"])
        self.classe.setCurrentIndex(max(0, self.classe.findData(actuel)))
        self.classe.blockSignals(False)
        self.afficher()

    def afficher(self) -> None:
        self.lignes = cv.eleves(self.f.conn, self.classe.currentData())
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.lignes))
        for i, e in enumerate(self.lignes):
            for j, x in enumerate((f"{e['prenom_ar']} {e['nom_ar']}", e["classe"] or "",
                                   tx.date_chiffres(e["date_naissance"]) if e["date_naissance"] else "",
                                   e["code_massar"] or "")):
                self.table.setItem(i, j, cellule(x, e["id"]))
        self.table.blockSignals(False)
        self._compte()

    def choisis(self) -> list[int] | None:
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        return [self.table.item(r, 0).data(Qt.UserRole) for r in rows] or None

    def _compte(self) -> None:
        ids = self.choisis()
        n = len(ids) if ids else len(self.lignes)
        pages = -(-n // self.par_page.currentData()) if n else 0
        self.nb.setText((f"المحدَّدون: {n} تلميذاً" if ids else f"كل المعروضين: {n} تلميذاً")
                        + f" · {pages} صفحة. حدّد أسطراً (Ctrl أو Shift) لاستدعاء تلاميذ بعينهم.")

    def generer(self):
        try:
            iso = self.date.iso()
        except ValueError:
            iso = ""
        try:
            p = cv.generer(self.f.conn, self.f.dossier, self.occasion.currentData(), self.numero.currentText(), iso,
                           self.heure.text(), self.lieu.text(), self.ordre.toPlainText(),
                           self.par_page.currentData(), self.classe.currentData(), self.choisis())
        except (cv.ErreurConvocation, OSError) as e:
            message(self.page.message, str(e), True)
            return None
        message(self.page.message, f"وُلّدت الاستدعاءات: ⁦{p.name}⁩")
        try:
            bureautique.ouvrir(p)
        except OSError:
            pass
        return p


class PageCommunication(QWidget):
    VUES = (("affiche", "إعلان مزخرف"), ("convocations", "استدعاءات أولياء الأمور"), ("annonces", "إعلانات نصية"))

    def __init__(self, fenetre, couleur: str | None = None):
        super().__init__()
        self.f = fenetre
        self.cles_registres = ["annonces"]
        racine, self.message = _page(
            "الإعلام والتواصل", "إعلانات مزخرفة بعشرة قوالب (A4 أو A3)، استدعاءات أولياء الأمور باسم كل تلميذ، "
                                "وسجل الإعلانات النصية.")
        self.setLayout(racine)
        h = QHBoxLayout()
        h.setSpacing(8)
        self.pilules: dict[str, QPushButton] = {}
        for cle, lib in self.VUES:
            b = QPushButton(lib)
            b.setObjectName("pilule")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, cle=cle: self.choisir(cle))
            self.pilules[cle] = b
            h.addWidget(b)
        h.addStretch()
        racine.addLayout(h)
        self.affiche = VueAffiche(self)
        self.convocations = VueConvocations(self)
        self.annonces = VueRegistre(self, "annonces", couleur or "#3B3FB6")
        self.vues = {"affiche": self.affiche, "convocations": self.convocations, "annonces": self.annonces}
        for w in self.vues.values():
            racine.addWidget(w)
        racine.addStretch()
        self.cle = "affiche"
        self.choisir("affiche")

    def vue(self, cle: str | None = None):
        return self.vues[cle or self.cle]

    def choisir(self, cle: str) -> None:
        self.cle = cle
        for k, w in self.vues.items():
            w.setVisible(k == cle)
        for k, b in self.pilules.items():
            b.setChecked(k == cle)
        self.vues[cle].rafraichir()

    def rafraichir(self) -> None:
        self.vues[self.cle].rafraichir()
