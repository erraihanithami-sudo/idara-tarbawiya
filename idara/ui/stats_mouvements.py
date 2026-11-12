"""نافذة إحصائيات حركية التلاميذ ووثيقة الحركية (طلب المدير 2026-11-12): عدد الوافدين والمغادرين إجمالاً وحسب
المستوى والنوع والشهر، للوحدة المختارة أو للمؤسسة كاملة، مع فترة اختيارية."""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import (QCheckBox, QDialog, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
                               QVBoxLayout, QWidget)

from idara.services import bureautique
from idara.services import mouvements as mv
from idara.ui.composants import carte
from idara.ui.graphiques import BarresGroupees, Tuile
from idara.ui.saisie import ChampDate, cellule, message, tableau

VERT, ROUGE, ORANGE, BLEU = "#2E7D32", "#C62828", "#EF6C00", "#1565C0"


def png_graphique(s: dict, largeur: int = 1000, hauteur: int = 360) -> bytes | None:
    niv = [(n, v) for n, v in s["niveaux"] if sum(v["arrive"].values()) or sum(v["parti"].values())]
    if not niv:
        return None
    w = BarresGroupees([n for n, _ in niv], _series(niv), maximum=None)
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
    w.deleteLater()
    return bytes(ba)


def _series(niv) -> list:
    return [("الوافدون", [float(sum(v["arrive"].values())) for _, v in niv], VERT),
            ("المغادرون", [float(sum(v["parti"].values())) for _, v in niv], ROUGE)]


class DialogueStatistiques(QDialog):
    def __init__(self, page):
        super().__init__(page)
        self.page, self.f = page, page.f
        self.setWindowTitle("إحصائيات حركية التلاميذ")
        self.setLayoutDirection(Qt.RightToLeft)
        self.resize(980, 760)
        racine = QVBoxLayout(self)
        t = QLabel("إحصائيات حركية التلاميذ")
        t.setObjectName("titrePage")
        racine.addWidget(t)
        self.portee = QLabel()
        self.portee.setObjectName("sousTitre")
        racine.addWidget(self.portee)
        h = QHBoxLayout()
        self.debut, self.fin = ChampDate(), ChampDate()
        for lib, w in (("من (اختياري)", self.debut), ("إلى (اختياري)", self.fin)):
            h.addWidget(QLabel(lib))
            h.addWidget(w)
        b = QPushButton("تحديث")
        b.clicked.connect(self.actualiser)
        h.addWidget(b)
        h.addStretch()
        self.listes = QCheckBox("إرفاق لائحتي الوافدين والمغادرين")
        self.listes.setChecked(True)
        h.addWidget(self.listes)
        self.b_doc = QPushButton("توليد وثيقة الحركية")
        self.b_doc.setObjectName("principal")
        self.b_doc.clicked.connect(self.generer)
        h.addWidget(self.b_doc)
        racine.addLayout(h)
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.hide()
        racine.addWidget(self.message)
        zone = QScrollArea()
        zone.setWidgetResizable(True)
        self.corps = QWidget()
        self.v = QVBoxLayout(self.corps)
        zone.setWidget(self.corps)
        racine.addWidget(zone, 1)
        self.stats: dict | None = None
        self._anciens: list[QWidget] = []
        self.actualiser()

    def _periode(self) -> tuple[str | None, str | None] | None:
        try:
            return self.debut.iso() or None, self.fin.iso() or None
        except ValueError:
            message(self.message, "أحد تاريخي الفترة غير صحيح.", True)
            return None

    def actualiser(self) -> dict | None:
        p = self._periode()
        if p is None:
            return None
        unite = self.page.unite()
        try:
            s = mv.statistiques(self.f.conn, unite, *p)
        except mv.ErreurMouvement as e:
            message(self.message, str(e), True)
            return None
        self.message.hide()
        self.stats = s
        self.portee.setText(f"السنة الدراسية {s['annee']} · " + (f"الوحدة: {unite}" if unite else "المؤسسة كاملة"))
        for w in self._anciens:
            w.hide()
            w.setParent(None)
            w.deleteLater()
        self._anciens = []
        contenu = QWidget()
        v = QVBoxLayout(contenu)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(14)
        t = s["totaux"]
        g = QGridLayout()
        tuiles = [("الوافدون", t["arrive"], VERT, f"منهم {t['arrive_F']} إناث"),
                  ("المغادرون", t["parti"], ROUGE, f"منهم {t['parti_F']} إناث"),
                  ("المنقطعون والمفصولون", t["interrompu"] + t["exclu"], ORANGE,
                   f"منقطعون {t['interrompu']} · مفصولون {t['exclu']}"),
                  ("الفرق", t["solde"], BLEU, "الوافدون − المغادرون − المنقطعون − المفصولون")]
        self.tuiles = {}
        for i, (lib, n, coul, note) in enumerate(tuiles):
            w = Tuile(lib, f"\u2066{n:+d}\u2069" if lib == "الفرق" and n else str(n), coul, "حركية التلاميذ", note)
            self.tuiles[lib] = w
            g.addWidget(w, 0, i)
        v.addLayout(g)
        c, cv = carte("حسب المستوى والنوع")
        self.t_niveaux = tableau(["المستوى", "وافدون ذكور", "وافدات إناث", "مجموع الوافدين", "مغادرون ذكور",
                                  "مغادرات إناث", "مجموع المغادرين", "المنقطعون والمفصولون"], etirer=0)
        lignes = s["niveaux"] + [("المجموع", {
            "arrive": {"M": t["arrive"] - t["arrive_F"], "F": t["arrive_F"]},
            "parti": {"M": t["parti"] - t["parti_F"], "F": t["parti_F"]},
            "interrompu": t["interrompu"], "exclu": t["exclu"]})]
        self.t_niveaux.setRowCount(len(lignes))
        for i, (n, x) in enumerate(lignes):
            a, p_ = x["arrive"], x["parti"]
            for j, val in enumerate([n, a["M"], a["F"], a["M"] + a["F"], p_["M"], p_["F"], p_["M"] + p_["F"],
                                     x["interrompu"] + x["exclu"]]):
                self.t_niveaux.setItem(i, j, cellule(str(val)))
        self.t_niveaux.setMinimumHeight(min(60 + 32 * len(lignes), 360))
        cv.addWidget(self.t_niveaux)
        v.addWidget(c)
        niv = [(n, x) for n, x in s["niveaux"] if sum(x["arrive"].values()) or sum(x["parti"].values())]
        if niv:
            c, cv = carte("الوافدون والمغادرون حسب المستوى")
            cv.addWidget(BarresGroupees([n for n, _ in niv], _series(niv), maximum=None))
            v.addWidget(c)
        bas = QHBoxLayout()
        c, cv = carte("حسب الشهر")
        self.t_mois = tableau(["الشهر", "الوافدون", "المغادرون"], etirer=0)
        self.t_mois.setRowCount(len(s["mois"]))
        for i, (m, x) in enumerate(s["mois"]):
            for j, val in enumerate([mv.libelle_mois(m), x["arrive"], x["parti"]]):
                self.t_mois.setItem(i, j, cellule(str(val)))
        self.t_mois.setMinimumHeight(220)
        cv.addWidget(self.t_mois)
        bas.addWidget(c, 1)
        c, cv = carte("المؤسسات الأخرى")
        self.t_etabs = tableau(["المؤسسة", "الحركة", "العدد"], etirer=0)
        self.t_etabs.setRowCount(len(s["etablissements"]))
        for i, e in enumerate(s["etablissements"]):
            nom = e["etablissement"] + (" (خارج الإقليم)" if e["hors_province"] else "")
            for j, val in enumerate([nom, "قدموا منها" if e["sens"] == "arrive" else "انتقلوا إليها", e["effectif"]]):
                self.t_etabs.setItem(i, j, cellule(str(val)))
        self.t_etabs.setMinimumHeight(220)
        cv.addWidget(self.t_etabs)
        bas.addWidget(c, 1)
        v.addLayout(bas)
        info = QLabel(f"ملفات المغادرين المرسلة: {t['envoyes']} من {t['parti']}. ملفات الوافدين المتوصل بها: "
                      f"{t['recus']} من {t['arrive']}. من خارج الإقليم: {t['hors_province_arrive']} وافداً و"
                      f"{t['hors_province_parti']} مغادراً.")
        info.setObjectName("etiquette")
        info.setWordWrap(True)
        v.addWidget(info)
        v.addStretch()
        contenu.layout().activate()
        contenu.setMinimumHeight(contenu.layout().totalMinimumSize().height())
        self.v.addWidget(contenu)
        self._anciens.append(contenu)
        self.b_doc.setEnabled(bool(t["arrive"] or t["parti"] or t["interrompu"] or t["exclu"]))
        return s

    def generer(self):
        p = self._periode()
        if p is None or self.stats is None:
            return None
        try:
            chemin = mv.generer_bilan(self.f.conn, self.f.dossier, self.page.unite(), *p,
                                      listes=self.listes.isChecked(), graphique_png=png_graphique(self.stats))
        except (mv.ErreurMouvement, OSError) as e:
            message(self.message, str(e), True)
            return None
        message(self.message, f"وُلّدت وثيقة الحركية: ⁦{chemin.name}⁩")
        try:
            bureautique.ouvrir(chemin)
        except OSError as e:
            message(self.message, f"وُلّدت الوثيقة لكن تعذر فتحها: {e}", True)
        return chemin
