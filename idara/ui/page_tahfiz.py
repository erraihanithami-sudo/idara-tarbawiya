"""مكوّن «التحفيز والتشجيع» (طلب المدير 2026-11-22): معرض الشواهد التقديرية في الصفحة الثابتة؛ يُختار تصميم،
ثم تُملأ معطياته في نافذة منبثقة (التلاميذ من اللائحة، نوع التحفيز، السبب، التاريخ، الموقعون) مع معاينة حية،
وتُطبع الشهادات PDF (صفحة لكل تلميذ) أو تُصدَّر PowerPoint قابلاً للتعديل. كل شهادة تُسجل في سجل التحفيز."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget)

from idara.services import bureautique
from idara.services import chawahid as ch
from idara.ui.composants import carte
from idara.ui.page_pedagogie import _page
from idara.ui.page_registre import VueRegistre
from idara.ui.rihab import FluxLayout
from idara.ui.saisie import ChampDate, message

LARGEUR_VIGNETTE = 340


class CarteModele(QFrame):
    """بطاقة تصميم في المعرض: صورة مصغرة، الاسم، الوصف، وزر الاختيار."""

    def __init__(self, page, m: ch.Modele, image, parent=None):
        super().__init__(parent)
        from idara.ui.vitrine import bouton_couleur
        self.page, self.m = page, m
        self.setObjectName("carteChahada")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedWidth(LARGEUR_VIGNETTE + 28)
        self.setStyleSheet("#carteChahada { background: #FFFDF7; border: 1px solid #E2C77A; border-radius: 16px; }"
                           "#carteChahada:hover { border: 2px solid #C9A227; }")
        v = QVBoxLayout(self)
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(6)
        self.vignette = QLabel(self)
        self.vignette.setPixmap(QPixmap.fromImage(image))
        self.vignette.setAlignment(Qt.AlignCenter)
        v.addWidget(self.vignette)
        t = QLabel(m.nom, self)
        t.setStyleSheet("font-size: 16px; font-weight: 800; color: #1B2A4A;")
        v.addWidget(t)
        d = QLabel(m.description, self)
        d.setWordWrap(True)
        d.setObjectName("etiquette")
        v.addWidget(d)
        self.bouton = bouton_couleur("اختيار هذا التصميم", "#B07A16", "valider")
        self.bouton.setParent(self)
        self.bouton.clicked.connect(lambda: self.page.ouvrir(self.m.cle))
        v.addWidget(self.bouton)

    def mouseReleaseEvent(self, e) -> None:   # noqa: N802
        if e.button() == Qt.LeftButton:
            self.page.ouvrir(self.m.cle)
        super().mouseReleaseEvent(e)


class PageTahfiz(QWidget):
    def __init__(self, fenetre, couleur: str | None = None):
        super().__init__()
        from idara.ui import theme
        self.f = fenetre
        self.cle_modele = ch.MODELES[0].cle
        self.fiche = None
        racine, self.message = _page(
            "التحفيز والتشجيع", "معرض الشواهد التقديرية: اختر تصميماً، ثم املأ معطياته في النافذة واطبع الشواهد. "
            "كل شهادة تُسجَّل في سجل التحفيز وفي الملف الشامل للتلميذ(ة).")
        self.setLayout(racine)
        c, v = carte("معرض الشواهد")
        self.zone_galerie = QWidget()
        self.flux = FluxLayout(self.zone_galerie, 18, 18)
        self.cartes: dict[str, CarteModele] = {}
        ex = self._exemple()
        for m in ch.MODELES:
            img = _apercu(m.cle, ex, LARGEUR_VIGNETTE, self._logo())
            carte_m = CarteModele(self, m, img, self.zone_galerie)
            self.cartes[m.cle] = carte_m
            self.flux.addWidget(carte_m)
        v.addWidget(self.zone_galerie)
        racine.addWidget(c)
        self.vue = VueRegistre(self, "tahfiz", couleur or theme.VERT)
        racine.addWidget(self.vue)
        racine.addStretch()

    # توافق مع PageRegistres (العدادات والتنقل)
    def vue_registre(self):
        return self.vue

    def rafraichir(self) -> None:
        self.vue.rafraichir()

    def _logo(self) -> str:
        try:
            return ch.logo_etablissement(self.f.conn, self.f.dossier)
        except Exception:  # noqa: BLE001
            return ""

    def _exemple(self, type_: str = "شهادة تقديرية") -> dict:
        try:
            return ch.exemple(self.f.conn, type_)
        except Exception:  # noqa: BLE001 — لا مؤسسة بعد
            return {"nom": "اسم التلميذة أو التلميذ", "titre": ch.TITRES[type_], "entete": [],
                    "intro": "", "motif": "", "voeu": "", "date": "", "signataires": ["مدير المؤسسة"]}

    # ---------------- النافذة المنبثقة ----------------
    def ouvrir(self, cle: str):
        from idara.ui.vitrine import FenetreFiche, bouton_couleur
        self.cle_modele = cle
        if self.fiche is not None:
            self.fiche.hide()
            self.fiche.deleteLater()
        w = QWidget()
        h = QVBoxLayout(w)
        h.setSpacing(12)
        # المعاينة في الأعلى ثم الاستمارة (تتسع لكل عرض للشاشة)
        form = QWidget(w)
        fl = QFormLayout(form)
        fl.setLabelAlignment(Qt.AlignRight)
        self.c_modele = QComboBox(form)
        for m in ch.MODELES:
            self.c_modele.addItem(m.nom, m.cle)
        self.c_modele.setCurrentIndex([m.cle for m in ch.MODELES].index(cle))
        self.c_modele.currentIndexChanged.connect(lambda _: self._changer_modele())
        fl.addRow("التصميم", self.c_modele)
        self.c_classe = QComboBox(form)
        self.c_classe.addItem("كل الأقسام", "")
        for k in ch.classes(self.f.conn):
            self.c_classe.addItem(k, k)
        self.c_classe.currentIndexChanged.connect(lambda _: self._charger_eleves())
        fl.addRow("القسم", self.c_classe)
        self.c_cherche = QLineEdit(form)
        self.c_cherche.setPlaceholderText("بحث بالاسم…")
        self.c_cherche.textChanged.connect(lambda _: self._filtrer())
        hb = QHBoxLayout()
        hb.addWidget(self.c_cherche, 1)
        b_tous = QPushButton("تحديد الكل", form)
        b_tous.clicked.connect(lambda: self.cocher_tout(True))
        b_aucun = QPushButton("إلغاء التحديد", form)
        b_aucun.clicked.connect(lambda: self.cocher_tout(False))
        hb.addWidget(b_tous)
        hb.addWidget(b_aucun)
        fl.addRow("التلاميذ", hb)
        self.l_eleves = QListWidget(form)
        self.l_eleves.setMinimumHeight(170)
        self.l_eleves.itemChanged.connect(lambda _: self._maj())
        self.l_eleves.currentRowChanged.connect(lambda _: self._maj())
        fl.addRow(self.l_eleves)
        self.c_type = QComboBox(form)
        self.c_type.addItems(ch.TYPES)
        self.c_type.currentIndexChanged.connect(lambda _: self._changer_type())
        fl.addRow("نوع التحفيز", self.c_type)
        self.c_periode = QComboBox(form)
        self.c_periode.addItem("—", "")
        for p in ch.PERIODES:
            self.c_periode.addItem(p, p)
        self.c_periode.setCurrentIndex(1)
        self.c_periode.currentIndexChanged.connect(lambda _: self._maj())
        fl.addRow("الفترة", self.c_periode)
        self.c_motif = QComboBox(form)
        self.c_motif.setEditable(True)
        for t in ch.MOTIFS:
            self.c_motif.addItem(ch.accorder(t, False).replace("{الفترة}", "…"), t)
        self.motif_modele: str | None = ch.MOTIFS[0]
        self.c_motif.activated.connect(lambda i: self._choisir_motif(i))
        self.c_motif.lineEdit().textEdited.connect(lambda _: self._motif_libre())
        fl.addRow("السبب", self.c_motif)
        self.c_intro = QLineEdit(form)
        self.intro_modifiee = False
        self.c_intro.textEdited.connect(lambda _: self._intro_libre())
        fl.addRow("العبارة الافتتاحية", self.c_intro)
        self.c_date = ChampDate(form)
        self.c_date.definir(date.today().isoformat())
        self.c_date.textChanged.connect(lambda _: self._maj())
        fl.addRow("التاريخ", self.c_date)
        self.c_asso = QCheckBox("توقيع رئيس جمعية الآباء أيضاً", form)
        self.c_asso.toggled.connect(lambda _: self._maj())
        self.c_classe_aff = QCheckBox("إظهار القسم في الشهادة", form)
        self.c_classe_aff.setChecked(True)
        self.c_classe_aff.toggled.connect(lambda _: self._maj())
        fl.addRow(self.c_asso)
        fl.addRow(self.c_classe_aff)
        bh = QHBoxLayout()
        self.b_pdf = bouton_couleur("طباعة الشواهد (PDF)", "#2E7D32", "document",
                                    "صفحة A4 أفقية لكل تلميذ(ة) محدد(ة)، وتُسجَّل في سجل التحفيز")
        self.b_pdf.clicked.connect(lambda: self.generer_pdf())
        self.b_ppt = bouton_couleur("PowerPoint قابل للتعديل", "#C55A11", "exporter")
        self.b_ppt.clicked.connect(lambda: self.generer_ppt())
        b_fermer = bouton_couleur("إغلاق", "#546E7A", "annuler")
        b_fermer.clicked.connect(lambda: self.fiche.hide())
        for b in (self.b_pdf, self.b_ppt, b_fermer):
            bh.addWidget(b)
        bh.addStretch()
        fl.addRow(bh)
        self.message_fiche = QLabel(form)
        self.message_fiche.setWordWrap(True)
        self.message_fiche.hide()
        fl.addRow(self.message_fiche)
        self.l_apercu = QLabel(w)
        self.l_apercu.setAlignment(Qt.AlignCenter)
        h.addWidget(self.l_apercu)
        self.l_nombre = QLabel(w)
        self.l_nombre.setAlignment(Qt.AlignCenter)
        self.l_nombre.setStyleSheet("font-weight: 800; color: #8C6A00;")
        h.addWidget(self.l_nombre)
        h.addWidget(form)
        self._charger_eleves()
        self._changer_type()
        self.fiche = FenetreFiche(self, "شهادة تقديرية", "اختر التلاميذ واملأ المعطيات؛ المعاينة تتحدث مباشرة.", w,
                                  largeur=900)
        self.fiche.ouvrir()
        return self.fiche

    def _charger_eleves(self) -> None:
        self.l_eleves.blockSignals(True)
        self.l_eleves.clear()
        for e in ch.eleves(self.f.conn, self.c_classe.currentData() or None):
            it = QListWidgetItem(f"{e['nom']}  ·  {e['classe']}" if e["classe"] else e["nom"])
            it.setData(Qt.UserRole, e)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Unchecked)
            self.l_eleves.addItem(it)
        self.l_eleves.blockSignals(False)
        self._filtrer()
        self._maj()

    def _filtrer(self) -> None:
        t = " ".join(self.c_cherche.text().split())
        for i in range(self.l_eleves.count()):
            it = self.l_eleves.item(i)
            it.setHidden(bool(t) and t not in it.text())

    def cocher(self, noms: list[str]) -> int:
        """للاختبارات والاختيار السريع: يحدد التلاميذ بأسمائهم."""
        n = 0
        self.l_eleves.blockSignals(True)
        for i in range(self.l_eleves.count()):
            it = self.l_eleves.item(i)
            if it.data(Qt.UserRole)["nom"] in noms:
                it.setCheckState(Qt.Checked)
                n += 1
        self.l_eleves.blockSignals(False)
        self._maj()
        return n

    def cocher_tout(self, oui: bool) -> None:
        self.l_eleves.blockSignals(True)
        for i in range(self.l_eleves.count()):
            it = self.l_eleves.item(i)
            if not it.isHidden():
                it.setCheckState(Qt.Checked if oui else Qt.Unchecked)
        self.l_eleves.blockSignals(False)
        self._maj()

    def selection(self) -> list[dict]:
        return [self.l_eleves.item(i).data(Qt.UserRole) for i in range(self.l_eleves.count())
                if self.l_eleves.item(i).checkState() == Qt.Checked]

    def _changer_modele(self) -> None:
        self.cle_modele = self.c_modele.currentData()
        self._maj()

    def _changer_type(self) -> None:
        t = self.c_type.currentText()
        if not self.intro_modifiee:
            try:
                e = ch.etab_srv.lire_etablissement(self.f.conn)
            except Exception:  # noqa: BLE001
                e = None
            etab = e.nom_ar if e else "المؤسسة"
            self.c_intro.setText(f"يتشرف مدير وأطر {etab} بتقديم هذه {ch.NATURES[t]} إلى التلميذ(ة):")
        self._maj()

    def _choisir_motif(self, i: int) -> None:
        self.motif_modele = self.c_motif.itemData(i)
        self._maj()

    def _motif_libre(self) -> None:
        self.motif_modele = None
        self._maj()

    def _intro_libre(self) -> None:
        self.intro_modifiee = True
        self._maj()

    def _motif(self) -> str:
        return self.motif_modele if self.motif_modele else self.c_motif.currentText()

    def contenus(self, eleves: list[dict] | None = None) -> list[dict]:
        eleves = self.selection() if eleves is None else eleves
        try:
            le = self.c_date.iso() or None
        except ValueError as e:
            raise ch.ErreurChahada("التاريخ غير صحيح.") from e
        sig = ("مدير المؤسسة", "رئيس جمعية الآباء") if self.c_asso.isChecked() else ("مدير المؤسسة",)
        return [ch.contenu(self.f.conn, e, self.c_type.currentText(), self._motif(), self.c_periode.currentData(),
                           le, self.c_intro.text(), signataires=sig, afficher_classe=self.c_classe_aff.isChecked())
                for e in eleves]

    def _maj(self) -> None:
        if not hasattr(self, "l_apercu"):
            return
        sel = self.selection()
        cur = self.l_eleves.currentItem()
        el = sel[0] if sel else (cur.data(Qt.UserRole) if cur else {"nom": "اسم التلميذة أو التلميذ", "sexe": "M"})
        self.l_nombre.setText(f"{len(sel)} شهادة محددة للطبع" if sel else "حدد تلميذاً أو أكثر من اللائحة.")
        try:
            c = self.contenus([el])[0]
            self.message_fiche.hide()
        except ch.ErreurChahada as e:
            c = self._exemple(self.c_type.currentText())
            c["nom"] = el.get("nom", c["nom"])
            message(self.message_fiche, str(e), True)
        img = _apercu(self.cle_modele, c, 600, self._logo())
        self.l_apercu.setPixmap(QPixmap.fromImage(img))

    def _preparer(self) -> list[dict] | None:
        if not self.selection():
            message(self.message_fiche, "حدد تلميذاً أو أكثر من اللائحة.", True)
            return None
        try:
            return self.contenus()
        except ch.ErreurChahada as e:
            message(self.message_fiche, str(e), True)
            return None

    def generer_pdf(self, chemin: Path | None = None) -> Path | None:
        from idara.ui import chawahid_rendu as cr
        cs = self._preparer()
        if cs is None:
            return None
        chemin = chemin or ch.chemin_sortie(self.f.dossier, ch.nom_fichier(cs, self.cle_modele), "pdf")
        p = cr.exporter_pdf(cs, self.cle_modele, chemin, self._logo())
        return self._apres(cs, p)

    def generer_ppt(self, chemin: Path | None = None) -> Path | None:
        cs = self._preparer()
        if cs is None:
            return None
        chemin = chemin or ch.chemin_sortie(self.f.dossier, ch.nom_fichier(cs, self.cle_modele), "pptx")
        try:
            p = ch.generer_pptx(cs, self.cle_modele, chemin, self._logo())
        except ImportError:
            message(self.message_fiche, "مكتبة PowerPoint غير مثبتة في هذه النسخة.", True)
            return None
        return self._apres(cs, p)

    def _apres(self, cs: list[dict], p: Path) -> Path:
        ch.enregistrer(self.f.conn, cs, self.cle_modele)
        self.vue.rafraichir()
        t = f"وُلّدت {len(cs)} شهادة وسُجّلت في سجل التحفيز: ⁦{p.name}⁩"
        message(self.message_fiche, t)
        message(self.message, t)
        try:
            bureautique.ouvrir(p)
        except Exception:  # noqa: BLE001 — الفتح اختياري
            pass
        return p


def _apercu(cle: str, c: dict, largeur: int, logo: str = ""):
    from idara.ui import chawahid_rendu as cr
    return cr.apercu(cle, c, largeur, logo)
