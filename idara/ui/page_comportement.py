"""صفحة تتبع سلوك التلاميذ: ملاحظات مؤرخة، والإجراء المتخذ، واستدعاء ولي الأمر منها."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from idara.services import bureautique
from idara.services import comportement as cp
from idara.services import documents as dc
from idara.services import eleves as el
from idara.services import textes as tx
from idara.ui.composants import carte, entete
from idara.ui.formulaires import champ, etiquette
from idara.ui.saisie import ChampDate, cellule, message, tableau


def _combo() -> QComboBox:
    c = QComboBox()
    c.setEditable(True)
    c.setInsertPolicy(QComboBox.NoInsert)
    return c


class PageComportement(QWidget):
    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        self.eleve_id: int | None = None
        self.obs_id: int | None = None
        racine = QVBoxLayout(self)
        racine.setContentsMargins(40, 32, 40, 32)
        racine.setSpacing(16)
        racine.addWidget(entete("تتبع السلوك", "ملاحظات مؤرخة لكل تلميذ والإجراء المتخذ، ومنها يُولد استدعاء ولي الأمر."))
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.hide()
        racine.addWidget(self.message)
        corps = QHBoxLayout()
        corps.setSpacing(20)
        racine.addLayout(corps, 1)

        # ---- البحث والملخص ----
        c, cv = carte()
        self.recherche = QLineEdit()
        self.recherche.setPlaceholderText("ابحث عن التلميذ بالاسم أو رمز مسار")
        self.recherche.setClearButtonEnabled(True)
        self.recherche.textChanged.connect(lambda _: self.chercher())
        cv.addWidget(self.recherche)
        self.titre_liste = QLabel()
        self.titre_liste.setObjectName("etiquette")
        cv.addWidget(self.titre_liste)
        self.liste = tableau(["التلميذ", "الملاحظات"], etirer=0)
        hh = self.liste.horizontalHeader()
        hh.setSectionResizeMode(1, hh.ResizeMode.Fixed)
        hh.resizeSection(1, 110)
        self.liste.setMinimumHeight(420)
        self.liste.itemSelectionChanged.connect(self._selection)
        cv.addWidget(self.liste, 1)
        corps.addWidget(c, 5)

        # ---- ملف التلميذ ----
        c2, fv = carte()
        self.titre = QLabel("اختر تلميذاً")
        self.titre.setObjectName("titreCarte")
        fv.addWidget(self.titre)
        self.obs = tableau(["التاريخ", "الملاحظة", "الإجراء"], etirer=1)
        self.obs.setMinimumHeight(180)
        self.obs.itemSelectionChanged.connect(self._selection_obs)
        fv.addWidget(self.obs)
        t = QLabel("ملاحظة جديدة")
        t.setObjectName("titreCarte")
        fv.addWidget(t)
        self.date = ChampDate()
        self.nature, self.mesure, self.signale = _combo(), _combo(), _combo()
        self.description = champ("تفاصيل (اختياري)")
        g = QGridLayout()
        g.setHorizontalSpacing(16)
        g.setVerticalSpacing(4)
        for i, (lib, w) in enumerate((("التاريخ *", self.date), ("طبيعة الملاحظة *", self.nature),
                                      ("الإجراء المتخذ", self.mesure), ("صاحب الملاحظة", self.signale),
                                      ("التفاصيل", self.description))):
            g.addWidget(etiquette(lib, w), (i // 2) * 2, i % 2)
            g.addWidget(w, (i // 2) * 2 + 1, i % 2)
        fv.addLayout(g)
        h = QHBoxLayout()
        self.b_save = QPushButton("تسجيل الملاحظة")
        self.b_save.clicked.connect(lambda: self.enregistrer(False))
        self.b_conv = QPushButton("تسجيل واستدعاء ولي الأمر")
        self.b_conv.setObjectName("principal")
        self.b_conv.clicked.connect(lambda: self.enregistrer(True))
        self.b_suppr = QPushButton("حذف الملاحظة المحددة")
        self.b_suppr.clicked.connect(self.supprimer)
        for b in (self.b_conv, self.b_save, self.b_suppr):
            h.addWidget(b)
        h.addStretch()
        fv.addLayout(h)
        fv.addStretch()
        self.zone = c2
        corps.addWidget(c2, 6)
        self.rafraichir()
        self._activer(False)

    def _activer(self, oui: bool) -> None:
        for w in (self.date, self.nature, self.mesure, self.signale, self.description, self.b_save, self.b_conv):
            w.setEnabled(oui)
        self.b_suppr.setEnabled(False)

    def rafraichir(self) -> None:
        for k, w in (("nature", self.nature), ("mesure", self.mesure), ("signale_par", self.signale)):
            t = w.currentText()
            w.clear()
            w.addItems(cp.suggestions(self.f.conn, k))
            w.setEditText(t)
        self.chercher()
        if self.eleve_id:
            self.afficher(self.eleve_id)

    def chercher(self) -> None:
        texte = self.recherche.text().strip()
        try:
            if texte:
                lignes = [(r["id"], el.nom_complet(r), r["code_massar"]) for r in el.rechercher(self.f.conn, texte)]
                comptes = {r["id"]: r["n"] for r in cp.recapitulatif(self.f.conn)}
                lignes = [(i, n, c, comptes.get(i, 0)) for i, n, c in lignes]
                self.titre_liste.setText(f"{len(lignes)} نتيجة")
            else:
                lignes = [(r["id"], f"{r['prenom_ar']} {r['nom_ar']}", r["code_massar"], r["n"])
                          for r in cp.recapitulatif(self.f.conn)]
                self.titre_liste.setText("التلاميذ الذين لهم ملاحظات هذه السنة (الأكثر أولاً):" if lignes
                                         else "لا ملاحظات هذه السنة. ابحث عن تلميذ لتسجيل ملاحظة.")
        except cp.ErreurComportement as e:
            message(self.message, str(e), True)
            return
        self.liste.setRowCount(len(lignes))
        for i, (eid, nom, code, n) in enumerate(lignes):
            it = cellule(nom, eid)
            it.setToolTip(code)
            self.liste.setItem(i, 0, it)
            self.liste.setItem(i, 1, cellule(n or "—"))

    def _selection(self) -> None:
        rows = {i.row() for i in self.liste.selectedIndexes()}
        if len(rows) == 1:
            self.afficher(self.liste.item(rows.pop(), 0).data(Qt.UserRole))

    def afficher(self, eleve_id: int) -> None:
        self.eleve_id = eleve_id
        r = el.fiche(self.f.conn, eleve_id)
        self.titre.setText(f"{el.nom_complet(r)} · {r['classe'] or '—'}")
        lignes = cp.observations(self.f.conn, eleve_id)
        self.obs.setRowCount(len(lignes))
        for i, o in enumerate(lignes):
            self.obs.setItem(i, 0, cellule(tx.date_chiffres(o["date_obs"]), o["id"]))
            it = cellule(o["nature"])
            it.setToolTip(" · ".join(x for x in (o["description"], o["signale_par"]) if x))
            self.obs.setItem(i, 1, it)
            mesure = o["mesure"] or "—"
            if o["date_convocation"]:
                mesure += f" (استدعاء {tx.date_chiffres(o['date_convocation'])})"
            self.obs.setItem(i, 2, cellule(mesure))
        self.date.definir(date.today().isoformat())
        for w in (self.nature, self.mesure, self.signale):
            w.setEditText("")
        self.description.clear()
        self._activer(True)
        self.message.hide()

    def _selection_obs(self) -> None:
        rows = {i.row() for i in self.obs.selectedIndexes()}
        self.obs_id = self.obs.item(rows.pop(), 0).data(Qt.UserRole) if len(rows) == 1 else None
        self.b_suppr.setEnabled(self.obs_id is not None)

    def enregistrer(self, convoquer: bool):
        try:
            d = self.date.iso()
        except ValueError:
            message(self.message, "التاريخ غير صحيح.", True)
            return None
        o = cp.Observation(self.eleve_id, d, self.nature.currentText(), self.description.text(),
                           self.signale.currentText(), self.mesure.currentText())
        try:
            oid = cp.enregistrer(self.f.conn, o)
            doc = cp.convoquer(self.f.conn, self.f.dossier, oid) if convoquer else None
        except (cp.ErreurComportement, dc.ErreurDocument) as e:
            message(self.message, str(e), True)
            return None
        eid = self.eleve_id
        self.rafraichir()
        self.afficher(eid)
        if doc:
            message(self.message, "سُجلت الملاحظة ووُلّد الاستدعاء.")
            try:
                bureautique.ouvrir(doc.chemin)
            except OSError as e:
                message(self.message, f"وُلّد الاستدعاء لكن تعذر فتحه: {e}", True)
            return doc
        message(self.message, "سُجلت الملاحظة.")
        return oid

    def supprimer(self) -> bool:
        try:
            cp.supprimer(self.f.conn, self.obs_id)
        except cp.ErreurComportement as e:
            message(self.message, str(e), True)
            return False
        self.rafraichir()
        message(self.message, "حُذفت الملاحظة.")
        return True
