"""صفحة عامة للسجلات المعرَّفة بالوصف (idara.services.registres): استمارة، جدول، وبطاقات الوثائق.

صفحة واحدة قد تجمع عدة سجلات (حبوب أعلاها): مثلاً «خليتا اليقظة والإنصات» = التركيبة + الاجتماعات + الرصد.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QCompleter, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
                               QPushButton, QVBoxLayout, QWidget)

from idara.services import bureautique
from idara.services import registres as rg
from idara.ui import theme
from idara.ui.composants import bouton, carte
from idara.ui.formulaires import champ, etiquette
from idara.ui.page_pedagogie import _page
from idara.ui.rihab import CarteAction, Galerie
from idara.ui.saisie import ChampDate, cellule, message, tableau

_PORTEES = {"ligne": "للسطر المحدد في الجدول", "tout": "لكل الأسطر المعروضة", "personnel": "للموظف(ة) المختار(ة)"}


class VueRegistre(QWidget):
    def __init__(self, page, cle: str, couleur: str, fenetre: bool = False):
        super().__init__()
        self.en_fenetre = fenetre   # طلب المدير 2026-11-19: الإضافة والتعديل في نافذة منبثقة
        self.page, self.f, self.r = page, page.f, rg.registre(cle)
        self.lid: int | None = None
        self.classes: dict[str, str] = {}
        v0 = QVBoxLayout(self)
        v0.setContentsMargins(0, 0, 0, 0)
        v0.setSpacing(16)

        # ---- الاستمارة
        c, v = carte(self.r.titre)
        s = QLabel(self.r.sous)
        s.setObjectName("sousTitre")
        s.setWordWrap(True)
        v.addWidget(s)
        g = QGridLayout()
        g.setHorizontalSpacing(16)
        g.setVerticalSpacing(4)
        self.w: dict[str, QWidget] = {}
        ligne = col = 0
        for ch in self.r.champs:
            w = self._widget(ch)
            self.w[ch.cle] = w
            lib = etiquette(ch.libelle + (" *" if ch.requis else ""), w)
            if ch.type == "long":
                if col:
                    ligne, col = ligne + 2, 0
                g.addWidget(lib, ligne, 0, 1, 3)
                g.addWidget(w, ligne + 1, 0, 1, 3)
                ligne += 2
            else:
                g.addWidget(lib, ligne, col)
                g.addWidget(w, ligne + 1, col)
                col += 1
                if col == 3:
                    ligne, col = ligne + 2, 0
        for j in range(3):
            g.setColumnStretch(j, 1)
        v.addLayout(g)
        h = QHBoxLayout()
        self.b_enregistrer = QPushButton("حفظ")
        self.b_enregistrer.setObjectName("principal")
        self.b_enregistrer.clicked.connect(lambda: self.enregistrer())
        h.addWidget(self.b_enregistrer)
        b = QPushButton("سطر جديد")
        b.clicked.connect(lambda: self.nouveau())
        h.addWidget(b)
        self.b_suppr = bouton("حذف السطر")
        self.b_suppr.clicked.connect(lambda: self.supprimer())
        h.addWidget(self.b_suppr)
        h.addStretch()
        self.etat = QLabel()
        self.etat.setObjectName("pastille")
        h.addWidget(self.etat)
        v.addLayout(h)
        if fenetre:
            from idara.ui.vitrine import FenetreFiche, bouton_couleur
            self.fiche = FenetreFiche(self, self.r.titre, "", c, largeur=900)
            self.message_fiche = QLabel()
            self.message_fiche.setWordWrap(True)
            self.message_fiche.hide()
            v.addWidget(self.message_fiche)
            hb = QHBoxLayout()
            self.b_ajouter = bouton_couleur(f"إضافة: {self.r.titre}", couleur, "ajouter")
            self.b_ajouter.clicked.connect(lambda: self.ouvrir_nouveau())
            hb.addWidget(self.b_ajouter)
            hb.addStretch()
            v0.addLayout(hb)
        else:
            self.fiche = None
            v0.addWidget(c)

        # ---- الجدول
        c, v = carte("الأسطر المسجلة")
        h = QHBoxLayout()
        self.filtre = QComboBox(self)
        self.filtre.addItem("الكل", None)
        if self.r.filtre:
            for x in self.r.champ(self.r.filtre).choix:
                self.filtre.addItem(x, x)
        self.filtre.currentIndexChanged.connect(lambda _: self.afficher())
        h.addWidget(self.filtre)
        self.filtre.setVisible(bool(self.r.filtre))
        self.recherche = QLineEdit()
        self.recherche.setPlaceholderText("بحث في الأسطر")
        self.recherche.setClearButtonEnabled(True)
        self.recherche.textChanged.connect(lambda _: self.afficher())
        h.addWidget(self.recherche, 1)
        v.addLayout(h)
        self.colonnes = [ch for ch in self.r.champs if ch.colonne]
        self.couleur = couleur
        self.table = tableau([ch.libelle for ch in self.colonnes] + ([""] if self.r.dossier else []),
                             etirer=min(1, len(self.colonnes) - 1))
        self.table.setMinimumHeight(240)
        self.table.itemSelectionChanged.connect(self._selection)
        if fenetre:
            self.table.itemDoubleClicked.connect(lambda it: self.ouvrir(self.table.item(it.row(), 0).data(Qt.UserRole)))
        v.addWidget(self.table)
        self.nb = QLabel()
        self.nb.setObjectName("etiquette")
        v.addWidget(self.nb)
        v0.addWidget(c)

        # ---- الوثائق
        c, v = carte("الوثائق")
        self.cible: QComboBox | None = None
        if any(d.portee == "personnel" for d in self.r.docs):
            h = QHBoxLayout()
            self.cible = QComboBox()
            self.cible.setMinimumWidth(280)
            h.addWidget(etiquette("الموظف(ة):", self.cible))
            h.addWidget(self.cible)
            h.addStretch()
            v.addLayout(h)
        self.galerie = Galerie(3)
        self.cartes: dict[str, CarteAction] = {}
        for d in self.r.docs:
            k = CarteAction(d.titre, d.description, couleur, _PORTEES[d.portee], forme="doc")
            k.clique.connect(lambda cle=d.cle: self.generer(cle))
            self.cartes[d.cle] = self.galerie.ajouter(k)
        v.addWidget(self.galerie)
        v0.addWidget(c)
        self.nouveau()

    # ---------- الحقول ----------
    def _widget(self, ch: rg.Champ) -> QWidget:
        if ch.type == "date":
            return ChampDate()
        if ch.type == "long":
            w = QPlainTextEdit()
            w.setFixedHeight(76)
            w.setTabChangesFocus(True)
            return w
        if ch.type == "choix":
            w = QComboBox()
            w.addItems(["", *ch.choix])
            return w
        if ch.type in ("personnel", "eleve", "ref"):
            w = QComboBox()
            w.setEditable(True)
            w.setInsertPolicy(QComboBox.NoInsert)
            w.completer().setFilterMode(Qt.MatchContains)
            w.completer().setCompletionMode(QCompleter.PopupCompletion)
            if ch.type == "eleve":
                w.currentTextChanged.connect(self._eleve_choisi)
                w.editTextChanged.connect(self._eleve_choisi)
            return w
        return champ(ltr=ch.type == "nombre")

    def _eleve_choisi(self, nom: str) -> None:
        if "classe" in self.w and nom in self.classes and self.classes[nom]:
            self.w["classe"].setText(self.classes[nom])

    def _lire(self, ch: rg.Champ):
        w = self.w[ch.cle]
        if ch.type == "date":
            try:
                return w.iso()
            except ValueError:
                raise rg.ErreurRegistre(f"«{ch.libelle}»: تاريخ غير صحيح.") from None
        if ch.type == "long":
            return w.toPlainText()
        return w.currentText() if isinstance(w, QComboBox) else w.text()

    def _ecrire(self, ch: rg.Champ, v) -> None:
        w = self.w[ch.cle]
        if ch.type == "date":
            w.definir(v or None)
        elif ch.type == "long":
            w.setPlainText(str(v or ""))
        elif isinstance(w, QComboBox):
            t = str(v or "")
            if w.isEditable():
                w.setEditText(t)
            else:
                if t and w.findText(t) < 0:
                    w.addItem(t)
                w.setCurrentIndex(max(0, w.findText(t)))
        else:
            w.setText("" if v in ("", None) else str(v))

    def remplir(self, valeurs: dict) -> None:
        """يملأ الاستمارة (للاختبار وللتحميل). التواريخ بصيغة ISO."""
        for ch in self.r.champs:
            if ch.cle in valeurs:
                self._ecrire(ch, valeurs[ch.cle])

    def valeurs(self) -> dict:
        return {ch.cle: self._lire(ch) for ch in self.r.champs}

    # ---------- الأفعال ----------
    def rafraichir(self) -> None:
        conn = self.f.conn
        self.classes = dict(rg.eleves(conn)) if any(ch.type == "eleve" for ch in self.r.champs) else {}
        for ch in self.r.champs:
            if ch.type in ("personnel", "eleve", "ref"):
                w = self.w[ch.cle]
                actuel = w.currentText()
                w.blockSignals(True)
                w.clear()
                w.addItems(["", *rg.propositions(conn, ch)])
                w.setEditText(actuel)
                w.blockSignals(False)
        if self.cible is not None:
            actuel = self.cible.currentText()
            self.cible.clear()
            self.cible.addItems(rg.noms_personnel(conn))
            if actuel:
                self.cible.setCurrentIndex(max(0, self.cible.findText(actuel)))
        self.afficher()

    def afficher(self) -> None:
        from PySide6.QtGui import QBrush, QColor
        from idara.ui.vitrine import ajuster_colonne_actions, boutons_ligne, vider_colonne_widgets
        self.lignes = rg.lister(self.f.conn, self.r.cle, self.filtre.currentData(), self.recherche.text())
        self.table.blockSignals(True)
        n_col = len(self.colonnes)
        if self.r.dossier:
            vider_colonne_widgets(self.table, n_col)
        self.table.setRowCount(len(self.lignes))
        for i, l in enumerate(self.lignes):
            for j, ch in enumerate(self.colonnes):
                it = cellule(rg.afficher(ch, l.get(ch.cle)), l["id"])
                if ch.cle == self.r.etat:   # الوضعية ملونة (طلب المدير 2026-11-20)
                    texte, fait = rg.etat(self.r, l)
                    it.setText(texte)
                    it.setForeground(QBrush(QColor("#2E7D32" if fait else "#E65100")))
                    f = it.font()
                    f.setBold(True)
                    it.setFont(f)
                self.table.setItem(i, j, it)
            if self.r.dossier:
                self.table.setCellWidget(i, n_col, boutons_ligne(
                    [("الاطلاع على الملف", "#1565C0", "apercu", lambda _=False, k=l["id"]: self.ouvrir_dossier(k))]))
        if self.r.dossier:
            ajuster_colonne_actions(self.table, n_col)
        self.table.blockSignals(False)
        total = rg.compter(self.f.conn, self.r.cle)
        self.nb.setText(f"المعروض: {len(self.lignes)} من {total}")

    def _selection(self) -> None:
        rows = {i.row() for i in self.table.selectedIndexes()}
        if len(rows) == 1:
            self.charger(self.table.item(rows.pop(), 0).data(Qt.UserRole))

    def charger(self, lid: int) -> None:
        l = rg.lire(self.f.conn, self.r.cle, lid)
        self.lid = lid
        self.remplir(l)
        self.etat.setText("تعديل سطر مسجل")
        self.b_suppr.setEnabled(True)

    def ouvrir_nouveau(self):
        self.nouveau()
        if self.fiche is not None:
            self.message_fiche.hide()
            self.fiche.definir_titre(f"إضافة: {self.r.titre}")
            self.fiche.ouvrir()
        return self.fiche

    def ouvrir(self, lid: int):
        self.charger(lid)
        if self.fiche is not None:
            self.message_fiche.hide()
            self.fiche.definir_titre(f"تعديل: {self.r.titre}")
            self.fiche.ouvrir()
        return self.fiche

    def ouvrir_dossier(self, lid: int):
        """الملف الكامل لسطر (كل حقوله، ووضعيته، ووثائقه) في نافذة منبثقة للاطلاع (طلب المدير 2026-11-20)."""
        from idara.ui.vitrine import FenetreFiche, bouton_couleur
        self.charger(lid)
        l = rg.lire(self.f.conn, self.r.cle, lid)
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(6, 6, 6, 6)
        v.setSpacing(10)
        texte, fait = rg.etat(self.r, l)
        if self.r.etat:
            e = QLabel(texte)
            e.setStyleSheet(f"background: {'#2E7D32' if fait else '#E65100'}; color: white; border-radius: 12px; "
                            "padding: 6px 16px; font-weight: 700; font-size: 12pt;")
            he = QHBoxLayout()
            he.addWidget(e)
            he.addStretch()
            v.addLayout(he)
        g = QGridLayout()
        g.setHorizontalSpacing(14)
        g.setVerticalSpacing(6)
        k = 0
        self.dossier_valeurs: dict[str, str] = {}
        for ch in self.r.champs:
            val = rg.afficher(ch, l.get(ch.cle)) if ch.type != "long" else str(l.get(ch.cle) or "")
            if ch.cle == self.r.etat:
                continue
            a = QLabel(ch.libelle)
            a.setStyleSheet(f"font-weight: 700; color: {self.couleur};")
            b = QLabel(val or "غير مُدخل")
            b.setWordWrap(True)
            b.setTextInteractionFlags(Qt.TextSelectableByMouse)
            b.setAlignment(Qt.AlignAbsolute | Qt.AlignRight | Qt.AlignVCenter)   # التواريخ والرموز في صف النص
            if not val:
                b.setStyleSheet("color: #9E9E9E; font-style: italic;")
            self.dossier_valeurs[ch.cle] = val
            g.addWidget(a, k, 0, Qt.AlignTop)
            g.addWidget(b, k, 1)
            k += 1
        g.setColumnStretch(1, 1)
        v.addLayout(g)
        h = QHBoxLayout()
        b = bouton_couleur("تعديل / تحيين الوضعية", self.couleur, "modifier")
        b.clicked.connect(lambda: (self.fiche_dossier.hide(), self.ouvrir(lid)))
        h.addWidget(b)
        for d in self.r.docs:
            if d.portee == "ligne":
                bd = bouton_couleur(d.titre, "#6A1B9A", "document")
                bd.clicked.connect(lambda _=False, c=d.cle: self.generer(c))
                h.addWidget(bd)
        h.addStretch()
        v.addLayout(h)
        v.addStretch()
        titre = f"ملف: {self.r.titre}"
        sous = " · ".join(x for x in (str(l.get("eleve") or ""), rg.afficher(self.r.champs[0], l.get(self.r.champs[0].cle)))
                          if x)
        if getattr(self, "fiche_dossier", None) is not None:
            self.fiche_dossier.hide()
            self.fiche_dossier.deleteLater()
        self.fiche_dossier = FenetreFiche(self, titre, sous, w, largeur=760)
        self.fiche_dossier.ouvrir()
        return self.fiche_dossier

    def nouveau(self) -> None:
        self.lid = None
        for ch in self.r.champs:
            self._ecrire(ch, "")
        self.etat.setText("سطر جديد")
        self.b_suppr.setEnabled(False)
        if hasattr(self, "table"):
            self.table.clearSelection()

    def enregistrer(self) -> int | None:
        try:
            lid = rg.enregistrer(self.f.conn, self.r.cle, self.valeurs(), self.lid)
        except rg.ErreurRegistre as e:
            message(self.page.message, str(e), True)
            if self.fiche is not None:
                message(self.message_fiche, str(e), True)
            return None
        self.afficher()
        self.charger(lid)
        message(self.page.message, "حُفظ السطر.")
        if self.fiche is not None:
            message(self.message_fiche, "حُفظ السطر.")
        return lid

    def supprimer(self) -> bool:
        if self.lid is None:
            return False
        rg.supprimer(self.f.conn, self.r.cle, self.lid)
        self.nouveau()
        self.afficher()
        message(self.page.message, "حُذف السطر.")
        return True

    def generer(self, doc: str):
        try:
            p = rg.generer(self.f.conn, self.f.dossier, self.r.cle, doc, self.lid, self.filtre.currentData(),
                           self.cible.currentText() if self.cible is not None else None)
        except (rg.ErreurRegistre, OSError) as e:
            message(self.page.message, str(e), True)
            return None
        message(self.page.message, f"وُلّدت الوثيقة: ⁦{p.name}⁩")
        try:
            bureautique.ouvrir(p)
        except OSError:
            pass
        return p


class PageRegistres(QWidget):
    def __init__(self, fenetre, titre: str, sous: str, cles: list[str], couleur: str | None = None,
                 fenetres: bool = False):
        super().__init__()
        self.f = fenetre
        self.cles_registres = list(cles)
        couleur = couleur or theme.VERT
        racine, self.message = _page(titre, sous)
        self.setLayout(racine)
        self.vues: dict[str, VueRegistre] = {}
        self.pilules: dict[str, QPushButton] = {}
        if len(cles) > 1:
            h = QHBoxLayout()
            h.setSpacing(8)
            for k in cles:
                b = QPushButton(rg.registre(k).titre)
                b.setObjectName("pilule")
                b.setCheckable(True)
                b.setCursor(Qt.PointingHandCursor)
                b.clicked.connect(lambda _=False, k=k: self.choisir(k))
                self.pilules[k] = b
                h.addWidget(b)
            h.addStretch()
            racine.addLayout(h)
        for k in cles:
            self.vues[k] = VueRegistre(self, k, couleur, fenetres)
            racine.addWidget(self.vues[k])
        racine.addStretch()
        self.cle = cles[0]
        self.choisir(cles[0])

    def vue(self, cle: str | None = None) -> VueRegistre:
        return self.vues[cle or self.cle]

    def choisir(self, cle: str) -> None:
        self.cle = cle
        for k, v in self.vues.items():
            v.setVisible(k == cle)
        for k, b in self.pilules.items():
            b.setChecked(k == cle)
        self.vues[cle].rafraichir()

    def rafraichir(self) -> None:
        self.vues[self.cle].rafraichir()
