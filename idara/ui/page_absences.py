"""تتبع الحضور الشهري (طلب المدير 2026-11-07، ثم 2026-11-13): نسبة الحضور الشهرية لكل قسم تُدخل يدوياً، ويحسب
البرنامج نسبة كل وحدة والمؤسسة كاملة، مع تقرير شهري بمبيان المؤسسة."""

from __future__ import annotations

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDoubleSpinBox, QGridLayout, QHBoxLayout, QPushButton,
                               QTableWidgetItem,
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
    """مبيان نسبة حضور المؤسسة عبر الأشهر المُدرجة، صورة PNG للتقرير."""
    if not evolution:
        return None
    w = BarresGroupees([e["libelle"].split()[0] for e in evolution],
                       [("المؤسسة كاملة", [e["etablissement"]["taux"] for e in evolution], theme.SARCELLE)], 100)
    w.setLayoutDirection(Qt.RightToLeft)
    w.resize(largeur, hauteur)
    img = QImage(largeur, hauteur, QImage.Format_ARGB32)
    img.fill(QColor("white"))
    w.render(img)
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "PNG")
    buf.close()
    donnees = bytes(ba)
    w.deleteLater()
    return donnees


class PageAbsences(QWidget):
    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        racine, self.message = _page("تتبع الغياب",
                                     "أدخل كل شهر نسبة الحضور الشهرية لكل قسم، ويحسب البرنامج نسبة حضور كل وحدة "
                                     "والمؤسسة كاملة (متوسط مرجح بعدد تلاميذ الأقسام).")
        self.setLayout(racine)
        c, v = carte("نسب حضور الشهر")
        self.mois = QComboBox()
        self.mois.currentIndexChanged.connect(lambda _: self.afficher())
        self.jours = QDoubleSpinBox()
        self.jours.setRange(0, 31)
        self.jours.setDecimals(1)
        self.jours.setSingleStep(0.5)
        self.jours.setSpecialValueText("غير محدد")
        self.jours.setSuffix(" يوماً")
        v.addLayout(_grille([("الشهر", self.mois), ("أيام الدراسة الفعلية (اختياري)", self.jours)]))
        self.table = tableau(["الوحدة", "القسم", "عدد التلاميذ", "نسبة الحضور %"], etirer=1)
        self.table.setEditTriggers(QAbstractItemView.AllEditTriggers)
        self.table.setMinimumHeight(360)
        v.addWidget(self.table)
        h = QHBoxLayout()
        b = QPushButton("حفظ نسب الشهر")
        b.setObjectName("principal")
        b.clicked.connect(lambda: self.enregistrer())
        self.b_rapport = QPushButton("توليد التقرير الشهري (Word)")
        self.b_rapport.clicked.connect(lambda: self.generer())
        h.addWidget(b)
        h.addWidget(self.b_rapport)
        h.addStretch()
        v.addLayout(h)
        racine.addWidget(c)
        c, v = carte("نسبة الحضور: الوحدات والمؤسسة")
        self.grille = QGridLayout()
        self.grille.setSpacing(12)
        v.addLayout(self.grille)
        racine.addWidget(c)
        c, self.v_evo = carte("تطور نسبة الحضور حسب الأشهر")
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
            for j, v in ((2, f"{x['effectif']:g}"), (3, "" if x["taux"] is None else f"{x['taux']:g}")):
                it = QTableWidgetItem(v)
                it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)
                it.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(i, j, it)
        for col in (0, 1):
            for i in range(self.table.rowCount()):
                it = self.table.item(i, col)
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
        self.synthese()

    def valeurs(self) -> list[tuple[int, int, str]]:
        res = []
        for i in range(self.table.rowCount()):
            cid = self.table.item(i, 1).data(Qt.UserRole)
            try:
                eff = int(float(self.table.item(i, 2).text().replace(",", ".") or 0))
            except ValueError:
                raise ab.ErreurAbsence(f"{self.table.item(i, 1).text()}: عدد التلاميذ رقم.") from None
            res.append((cid, eff, self.table.item(i, 3).text()))
        return res

    def enregistrer(self) -> bool:
        try:
            ab.enregistrer(self.f.conn, self.mois.currentData(), self.valeurs(), self.jours.value() or None)
        except ab.ErreurAbsence as e:
            message(self.message, str(e), True)
            return False
        self.rafraichir()
        message(self.message, f"حُفظت نسب حضور {ab.libelle_mois(self.mois.currentData())}.")
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
            self.grille.addWidget(Tuile("لم تُدرج نسب هذا الشهر بعد", "—", theme.GRIS, "القيادة والتدبير"), 0, 0)
        else:
            e = s["etablissement"]
            self.grille.addWidget(Tuile("نسبة الحضور بالمؤسسة كاملة", ab._fmt(e["taux"]), theme.SARCELLE,
                                        "القيادة والتدبير",
                                        f"{e['classes']} قسماً · {e['effectif']} تلميذاً"), 0, 0, 1, 2)
            for k, u in enumerate(s["unites"]):
                self.grille.addWidget(Tuile(u["unite"], ab._fmt(u["taux"]), COULEURS_UNITES[k % 4], "القيادة والتدبير",
                                            f"{u['classes']} قسماً · {u['effectif']} تلميذاً"), 1 + k // 2, k % 2)
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
            series = [("المؤسسة كاملة", [e["etablissement"]["taux"] for e in ev], theme.SARCELLE)]
            noms_u = list(dict.fromkeys(u["unite"] for e in ev for u in e["unites"]))
            for k, nu in enumerate(noms_u[:4]):
                series.append((nu, [next((u["taux"] for u in e["unites"] if u["unite"] == nu), None) for e in ev],
                               COULEURS_UNITES[k]))
            self.l_evo.addWidget(BarresGroupees([e["libelle"].split()[0] for e in ev], series, 100))

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
