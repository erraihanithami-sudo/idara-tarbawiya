"""تتبع الغياب الشهري (طلب المدير 2026-11-07): إدراج الغياب حسب الأقسام والوحدات بالأشهر، نسب حسب الأشهر والوحدات
والمؤسسة كاملة، وتقرير شهري بمبيان المؤسسة."""

from __future__ import annotations

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QGridLayout, QHBoxLayout, QPushButton, QTableWidgetItem,
                               QWidget)

from idara.services import absences as ab
from idara.services import bureautique
from idara.services import etablissement as etab_srv
from idara.ui import theme
from idara.ui.composants import carte
from idara.ui.graphiques import BarresGroupees, Tuile
from idara.ui.page_pedagogie import _grille, _page
from idara.ui.saisie import cellule, message, tableau

COULEURS_UNITES = [theme.SARCELLE, theme.VIOLET, theme.ROSE, theme.ORANGE]


def png_evolution(evolution: list[dict], largeur: int = 1000, hauteur: int = 380) -> bytes | None:
    """مبيان نسبة غياب المؤسسة عبر الأشهر المُدرجة، صورة PNG للتقرير."""
    if not evolution:
        return None
    w = BarresGroupees([e["libelle"].split()[0] for e in evolution],
                       [("المؤسسة كاملة", [e["etablissement"]["taux"] for e in evolution], theme.ORANGE)], None)
    w.setLayoutDirection(Qt.RightToLeft)
    w.resize(largeur, hauteur)
    img = QImage(largeur, hauteur, QImage.Format_ARGB32)
    img.fill(QColor("white"))
    p = QPainter(img)
    w.render(p)
    p.end()
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "PNG")
    return bytes(ba)


class PageAbsences(QWidget):
    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        racine, self.message = _page("تتبع الغياب",
                                     "أدرج كل شهر مجموع أيام غياب تلاميذ كل قسم (نصف يوم = 0.5)؛ تُحسب النسب للأقسام "
                                     "والوحدات والمؤسسة كاملة.")
        self.setLayout(racine)
        c, v = carte("إدراج غياب الشهر")
        self.mois = QComboBox()
        self.mois.currentIndexChanged.connect(lambda _: self.afficher())
        self.jours = QDoubleSpinBox()
        self.jours.setRange(0, 31)
        self.jours.setDecimals(1)
        self.jours.setSingleStep(0.5)
        self.jours.setSuffix(" يوماً")
        v.addLayout(_grille([("الشهر", self.mois), ("أيام الدراسة الفعلية في الشهر", self.jours)]))
        self.table = tableau(["الوحدة", "القسم", "عدد التلاميذ", "المتغيبون", "أيام الغياب", "النسبة"], etirer=1)
        self.table.setEditTriggers(self.table.AllEditTriggers)
        self.table.setMinimumHeight(360)
        v.addWidget(self.table)
        h = QHBoxLayout()
        b = QPushButton("حفظ غياب الشهر")
        b.setObjectName("principal")
        b.clicked.connect(lambda: self.enregistrer())
        self.b_rapport = QPushButton("توليد التقرير الشهري (Word)")
        self.b_rapport.clicked.connect(lambda: self.generer())
        h.addWidget(b)
        h.addWidget(self.b_rapport)
        h.addStretch()
        v.addLayout(h)
        racine.addWidget(c)
        c, v = carte("نسب الشهر")
        self.grille = QGridLayout()
        self.grille.setSpacing(12)
        v.addLayout(self.grille)
        racine.addWidget(c)
        c, self.v_evo = carte("تطور نسبة الغياب حسب الأشهر")
        self.zone_evo = QWidget()
        self.l_evo = QHBoxLayout(self.zone_evo)
        self.l_evo.setContentsMargins(0, 0, 0, 0)
        self.v_evo.addWidget(self.zone_evo)
        racine.addWidget(c)
        racine.addStretch()
        self.rafraichir()

    def rafraichir(self) -> None:
        try:
            mois = ab.mois_de_l_annee(self.f.conn)
        except ab.ErreurAbsence as e:
            message(self.message, str(e), True)
            return
        actuel = self.mois.currentData()
        self.mois.blockSignals(True)
        self.mois.clear()
        saisis = {e["mois"] for e in ab.evolution(self.f.conn)}
        for m, lib in mois:
            self.mois.addItem(lib + ("  ✓" if m in saisis else ""), m)
        from datetime import date
        defaut = f"{date.today():%Y-%m}"
        self.mois.setCurrentIndex(max(0, self.mois.findData(actuel or defaut)))
        self.mois.blockSignals(False)
        self.afficher()

    def afficher(self) -> None:
        m = self.mois.currentData()
        if not m:
            return
        self.groupe = etab_srv.est_groupe(self.f.conn)
        self.table.setColumnHidden(0, not self.groupe)
        self.jours.setValue(ab.jours_etude(self.f.conn, m) or 0)
        self.lignes = ab.lignes(self.f.conn, m)
        self.table.setRowCount(len(self.lignes))
        for i, x in enumerate(self.lignes):
            self.table.setItem(i, 0, cellule(x["unite"] or "—"))
            self.table.setItem(i, 1, cellule(x["classe"], x["classe_id"]))
            for j, k in ((2, "effectif"), (3, "absents"), (4, "jours_absence")):
                it = QTableWidgetItem(f"{x[k]:g}")
                it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)
                it.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(i, j, it)
            self.table.setItem(i, 5, cellule(ab._fmt(x["taux"])))
        for col in (0, 1, 5):
            for i in range(self.table.rowCount()):
                it = self.table.item(i, col)
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
        self.synthese()

    def valeurs(self) -> list[tuple[int, int, float, int]]:
        res = []
        for i in range(self.table.rowCount()):
            cid = self.table.item(i, 1).data(Qt.UserRole)
            try:
                eff = int(float(self.table.item(i, 2).text().replace(",", ".") or 0))
                abs_ = int(float(self.table.item(i, 3).text().replace(",", ".") or 0))
                ja = float(self.table.item(i, 4).text().replace(",", ".") or 0)
            except ValueError:
                raise ab.ErreurAbsence(f"{self.table.item(i, 1).text()}: أرقام فقط.") from None
            res.append((cid, eff, ja, abs_))
        return res

    def enregistrer(self) -> bool:
        try:
            ab.enregistrer(self.f.conn, self.mois.currentData(), self.jours.value(), self.valeurs())
        except ab.ErreurAbsence as e:
            message(self.message, str(e), True)
            return False
        self.rafraichir()
        message(self.message, f"حُفظ غياب {ab.libelle_mois(self.mois.currentData())}.")
        return True

    def synthese(self) -> None:
        while self.grille.count():
            w = self.grille.takeAt(0).widget()
            if w:
                w.hide()
                w.setParent(None)
                w.deleteLater()
        s = ab.synthese_mois(self.f.conn, self.mois.currentData())
        self.s = s
        if s is None:
            self.grille.addWidget(Tuile("لم يُدرج غياب هذا الشهر بعد", "—", theme.GRIS, "القيادة والتدبير"), 0, 0)
        else:
            e = s["etablissement"]
            self.grille.addWidget(Tuile("نسبة الغياب بالمؤسسة كاملة", ab._fmt(e["taux"]), theme.ORANGE,
                                        "القيادة والتدبير",
                                        f"المتغيبون {e['absents']} من {e['effectif']} · {e['jours_absence']:g} يوم غياب"),
                                  0, 0, 1, 2)
            for k, u in enumerate(s["unites"]):
                self.grille.addWidget(Tuile(u["unite"], ab._fmt(u["taux"]), COULEURS_UNITES[k % 4], "القيادة والتدبير",
                                            f"المتغيبون {u['absents']} من {u['effectif']}"), 1 + k // 2, k % 2)
        # التطور عبر الأشهر
        while self.l_evo.count():
            w = self.l_evo.takeAt(0).widget()
            if w:
                w.hide()
                w.setParent(None)
                w.deleteLater()
        ev = ab.evolution(self.f.conn)
        self.evolution = ev
        if not ev:
            from PySide6.QtWidgets import QLabel
            self.l_evo.addWidget(QLabel("يظهر المبيان بعد إدراج شهر واحد على الأقل."))
        else:
            series = [("المؤسسة كاملة", [e["etablissement"]["taux"] for e in ev], theme.ORANGE)]
            noms_u = list(dict.fromkeys(u["unite"] for e in ev for u in e["unites"]))
            for k, nu in enumerate(noms_u[:4]):
                series.append((nu, [next((u["taux"] for u in e["unites"] if u["unite"] == nu), None) for e in ev],
                               COULEURS_UNITES[k]))
            self.l_evo.addWidget(BarresGroupees([e["libelle"].split()[0] for e in ev], series, None))

    def generer(self):
        try:
            p = ab.generer_rapport(self.f.conn, self.f.dossier, self.mois.currentData(),
                                   png_evolution(ab.evolution(self.f.conn)))
        except ab.ErreurAbsence as e:
            message(self.message, str(e), True)
            return None
        message(self.message, f"وُلّد التقرير: {p.name}")
        try:
            bureautique.ouvrir(p)
        except Exception:  # noqa: BLE001
            pass
        return p
