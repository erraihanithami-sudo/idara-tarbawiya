"""صفحة «أولياء الأمور» (طلب المدير 2026-11-13): استيراد ملف معلومات أولياء الأمور من مسار، البحث، تعديل
معلومات الولي والأب والأم، ولائحة أولياء الأمور حسب القسم."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QFileDialog, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QWidget)

from idara.services import annee as annee_srv
from idara.services import bureautique
from idara.services import parents as pa
from idara.ui.composants import carte
from idara.ui.formulaires import etiquette
from idara.ui.page_pedagogie import _page
from idara.ui.saisie import cellule, message, tableau


class PageParents(QWidget):
    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        self.eid: int | None = None
        racine, self.message = _page(
            "أولياء الأمور", "استورد ملف «معلومات أولياء الأمور» المصدَّر من مسار (ورقة لكل قسم أو ورقة واحدة)، "
                             "ثم ابحث وعدّل، واستخرج لائحة أولياء الأمور لكل قسم.")
        self.setLayout(racine)
        c, v = carte("الاستيراد من مسار")
        h = QHBoxLayout()
        b = QPushButton("اختيار ملف أولياء الأمور (Excel)…")
        b.setObjectName("principal")
        b.clicked.connect(lambda: self.importer())
        h.addWidget(b)
        self.rapport = QLabel()
        self.rapport.setObjectName("etiquette")
        self.rapport.setWordWrap(True)
        h.addWidget(self.rapport, 1)
        v.addLayout(h)
        racine.addWidget(c)

        c, v = carte("أولياء أمور التلاميذ")
        h = QHBoxLayout()
        self.classe = QComboBox()
        self.classe.currentIndexChanged.connect(lambda _: self.afficher())
        self.recherche = QLineEdit()
        self.recherche.setPlaceholderText("بحث: اسم التلميذ أو الولي، رمز مسار، الهاتف")
        self.recherche.textChanged.connect(lambda _: self.afficher())
        h.addWidget(self.classe)
        h.addWidget(self.recherche, 1)
        b = QPushButton("لائحة أولياء الأمور (Word)")
        b.setToolTip("للقسم المختار، أو لكل الأقسام (صفحة لكل قسم)")
        b.clicked.connect(lambda: self.generer())
        h.addWidget(b)
        v.addLayout(h)
        self.table = tableau(["التلميذ(ة)", "القسم", "ولي الأمر", "الصفة", "الهاتف", "العنوان"], etirer=5)
        self.table.setMinimumHeight(360)
        self.table.itemSelectionChanged.connect(self._selection)
        v.addWidget(self.table)
        self.nb = QLabel()
        self.nb.setObjectName("etiquette")
        v.addWidget(self.nb)
        racine.addWidget(c)

        self.c_fiche, v = carte("معلومات أولياء الأمور")
        self.titre = QLabel()
        self.titre.setObjectName("titreCarte")
        v.addWidget(self.titre)
        g = QGridLayout()
        g.setHorizontalSpacing(16)
        g.setVerticalSpacing(4)
        self.champs: dict[str, dict[str, QLineEdit]] = {}
        for k, (role, lib) in enumerate(pa.ROLES.items()):
            t = QLabel(lib)
            t.setObjectName("titreCarte")
            g.addWidget(t, 0, k)
            self.champs[role] = {}
            r = 1
            if role == "tuteur":
                self.tutelle = QComboBox()
                self.tutelle.setEditable(True)
                self.tutelle.addItems([""] + list(pa.TUTELLES))
                g.addWidget(etiquette("نوع الوصاية", self.tutelle), r, k)
                g.addWidget(self.tutelle, r + 1, k)
            r = 3
            for ch in pa.CHAMPS:
                w = QLineEdit()
                self.champs[role][ch] = w
                g.addWidget(etiquette(pa.LIBELLES[ch], w), r, k)
                g.addWidget(w, r + 1, k)
                r += 2
        v.addLayout(g)
        b = QPushButton("حفظ معلومات أولياء الأمور")
        b.setObjectName("principal")
        b.clicked.connect(lambda: self.enregistrer())
        v.addWidget(b, 0, Qt.AlignRight)
        self.c_fiche.hide()
        racine.addWidget(self.c_fiche)
        racine.addStretch()
        self.rafraichir()

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
        self.lignes = pa.lister(self.f.conn, self.classe.currentData(), self.recherche.text())
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.lignes))
        for i, l in enumerate(self.lignes):
            for j, x in enumerate((l["eleve"], l["classe"], l["tuteur"], l["lien"], l["telephone"], l["adresse"])):
                self.table.setItem(i, j, cellule(x, l["eleve_id"]))
        self.table.blockSignals(False)
        n = sum(1 for l in self.lignes if l["renseigne"])
        self.nb.setText(f"{len(self.lignes)} تلميذاً · معلومات الأولياء مسجلة لـ {n}")

    def _selection(self) -> None:
        rows = {i.row() for i in self.table.selectedIndexes()}
        if len(rows) == 1:
            self.charger(self.table.item(rows.pop(), 0).data(Qt.UserRole))

    def charger(self, eid: int) -> None:
        self.eid = eid
        l = next((x for x in self.lignes if x["eleve_id"] == eid), None)
        self.titre.setText(f"{l['eleve']} · {l['classe']} · ⁦{l['code']}⁩" if l else "")
        f = pa.fiche(self.f.conn, eid)
        for role, ws in self.champs.items():
            for ch, w in ws.items():
                w.setText((f.get(role) or {}).get(ch) or "")
        self.tutelle.setCurrentText((f.get("tuteur") or {}).get("tutelle") or "")
        self.c_fiche.show()

    def enregistrer(self) -> bool:
        if self.eid is None:
            return False
        try:
            for role, ws in self.champs.items():
                vals = {ch: w.text() for ch, w in ws.items()}
                if role == "tuteur":
                    vals["tutelle"] = self.tutelle.currentText()
                pa.enregistrer(self.f.conn, self.eid, role, vals)
        except pa.ErreurParents as e:
            message(self.message, str(e), True)
            return False
        eid = self.eid
        self.afficher()
        self.charger(eid)
        message(self.message, "حُفظت معلومات أولياء الأمور.")
        return True

    def importer(self, chemins: list[str | Path] | None = None):
        if chemins is None:
            chemins, _ = QFileDialog.getOpenFileNames(self, "ملف معلومات أولياء الأمور من مسار", "", "Excel (*.xlsx)")
            if not chemins:
                return None
        try:
            r = pa.importer(self.f.conn, chemins)
        except (pa.ErreurParents, OSError) as e:
            message(self.message, str(e), True)
            return None
        txt = (f"{r.eleves} تلميذاً في {r.feuilles} ورقة · {r.ajoutes} سجلاً جديداً · {r.mis_a_jour} محيَّناً")
        if r.inconnus:
            txt += f" · {len(r.inconnus)} رمزاً غير موجود في لوائح التلاميذ المستوردة"
        self.rapport.setText(txt)
        self.afficher()
        message(self.message, "استُورد ملف أولياء الأمور. " + txt)
        return r

    def generer(self):
        try:
            p = pa.generer_liste(self.f.conn, self.f.dossier, self.classe.currentData())
        except (pa.ErreurParents, OSError) as e:
            message(self.message, str(e), True)
            return None
        message(self.message, f"وُلّدت لائحة أولياء الأمور: ⁦{p.name}⁩")
        try:
            bureautique.ouvrir(p)
        except OSError:
            pass
        return p
