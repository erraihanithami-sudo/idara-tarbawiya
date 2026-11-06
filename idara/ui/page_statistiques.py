"""إحصائيات المؤسسة بالمبيانات (اقتراح المدير 2026-11-06): تحليل التلاميذ، البطاقة الإحصائية لكل مستوى،
وتطور التعلمات الأساس بين الرائزين."""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from idara.services import etablissement as etab_srv
from idara.services import statistiques as st
from idara.services import tarl as tarl_srv
from idara.ui import theme
from idara.ui.composants import carte
from idara.ui.graphiques import Anneau, BarresGroupees, Tuile
from idara.ui.page_pedagogie import _grille, _page
from idara.ui.saisie import cellule, tableau

COULEURS_ANALYSE = [theme.BLEU, theme.ROSE, theme.SARCELLE, theme.ORANGE, theme.GRIS, theme.VIOLET]
SECTIONS_ANALYSE = ["التلاميذ", "التلاميذ", "حركية التلاميذ", "حركية التلاميذ", "حركية التلاميذ", "حركية التلاميذ"]


class PageStatistiques(QWidget):
    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        racine, self.message = _page("إحصائيات المؤسسة",
                                     "تحليل التلاميذ، البطاقة الإحصائية لكل مستوى، وتطور التعلمات الأساس.")
        self.setLayout(racine)
        self.unite = QComboBox()
        self.unite.currentIndexChanged.connect(lambda _: self.rafraichir(garder=True))
        self.l_unite = QLabel("الوحدة المدرسية")
        h = QHBoxLayout()
        h.addWidget(self.l_unite)
        h.addWidget(self.unite)
        h.addStretch()
        racine.addLayout(h)
        self.zone = QVBoxLayout()
        self.zone.setSpacing(18)
        racine.addLayout(self.zone)
        racine.addStretch()
        self.matiere: str | None = None
        self.rafraichir()

    def _vider(self) -> None:
        while self.zone.count():
            it = self.zone.takeAt(0)
            w = it.widget()
            if w:   # يُخفى ويُفصل فوراً: الحذف المؤجل وحده يترك البطاقات القديمة ظاهرة تحت الجديدة
                w.hide()
                w.setParent(None)
                w.deleteLater()

    def rafraichir(self, garder: bool = False) -> None:
        unites = etab_srv.unites(self.f.conn)
        if not garder:
            actuel = self.unite.currentData()
            self.unite.blockSignals(True)
            self.unite.clear()
            self.unite.addItem("المؤسسة كاملة", None)
            for u in unites:
                self.unite.addItem(u, u)
            self.unite.setCurrentIndex(max(0, self.unite.findData(actuel)))
            self.unite.blockSignals(False)
        self.unite.setVisible(bool(unites))
        self.l_unite.setVisible(bool(unites))
        u = self.unite.currentData()
        self._vider()
        self.zone.addWidget(self._analyse(u))
        self.zone.addWidget(self._niveaux(u))
        self.zone.addWidget(self._tarl(u))
        # داخل منطقة التمرير: الارتفاع الأدنى يُحدَّث بعد إعادة البناء، وإلا تتراكب البطاقات
        self.layout().activate()
        self.setMinimumHeight(self.layout().totalMinimumSize().height())

    # ---------- تحليل التلاميذ ----------
    def _analyse(self, u) -> QWidget:
        a = st.analyse_eleves(self.f.conn, u)
        self.analyse = a
        c, v = carte("تحليل التلاميذ")
        n = QLabel(f"النسب محسوبة من مجموع المسجلين هذه السنة. العدد بعد الحركية (يتابعون دراستهم): "
                   f"{a['apres_mouvement']}")
        n.setObjectName("etiquette")
        n.setWordWrap(True)
        v.addWidget(n)
        v.addWidget(Tuile("مجموع التلاميذ المسجلين هذه السنة", str(a["total"]), theme.VERT, "التلاميذ"))
        g = QGridLayout()
        g.setSpacing(12)
        for i, ((lib, nb, pct), coul, sec) in enumerate(zip(a["details"], COULEURS_ANALYSE, SECTIONS_ANALYSE)):
            g.addWidget(Tuile(lib, str(nb), coul, sec, "" if pct is None else f"⁦{pct:g}%⁩"), i // 2, i % 2)
        v.addLayout(g)
        return c

    # ---------- البطاقة حسب المستوى ----------
    def _niveaux(self, u) -> QWidget:
        niv = st.par_niveau(self.f.conn, u)
        self.niveaux = niv
        c, v = carte("البطاقة الإحصائية حسب المستوى")
        n = QLabel("التوزيع حسب السن مقارنة بالسن النظامي للمستوى (السن في 31 دجنبر من بداية السنة). مؤشر تقديري "
                   "للتأخر الدراسي من تاريخ الازدياد؛ لوائح مسار المستوردة لا تتضمن التكرار.")
        n.setObjectName("etiquette")
        n.setWordWrap(True)
        v.addWidget(n)
        if not niv:
            v.addWidget(QLabel("لا تلاميذ بعد: استورد لوائح الأقسام من مسار."))
        for x in niv:
            b, bv = carte(f"المستوى {x['libelle']}")
            ch = QHBoxLayout()
            for t in (f"الأقسام: {x['classes']}", f"التلاميذ: {x['eleves']}", f"ذكور: {x['garcons']}", f"إناث: {x['filles']}",
                      f"متأخرون: {x['age'][1][1] + x['age'][2][1]}"):
                p = QLabel(t)
                p.setObjectName("pastille")
                ch.addWidget(p)
            ch.addStretch()
            bv.addLayout(ch)
            taux = x["taux_retard"]
            bv.addWidget(Anneau(x["age"], [theme.SARCELLE, theme.ORANGE, theme.ROSE],
                                "—" if taux is None else f"⁦{taux:g}%⁩", "نسبة التأخر"))
            if x["age_inconnu"]:
                l = QLabel(f"دون تاريخ ازدياد صالح: {x['age_inconnu']}")
                l.setObjectName("etiquette")
                bv.addWidget(l)
            v.addWidget(b)
        return c

    # ---------- تطور التعلمات الأساس ----------
    def _tarl(self, u) -> QWidget:
        c, v = carte("تطور مستوى التلاميذ في التعلمات الأساس")
        n = QLabel("نسبة من بلغوا المستوى المتوقع لمستواهم الدراسي في رائز الموضعة القبلي ثم البعدي.")
        n.setObjectName("etiquette")
        n.setWordWrap(True)
        v.addWidget(n)
        self.c_matiere = QComboBox()
        self.c_matiere.addItem("جميع المواد", None)
        for k, lib in tarl_srv.MATIERES.items():
            self.c_matiere.addItem(lib, k)
        self.c_matiere.setCurrentIndex(max(0, self.c_matiere.findData(self.matiere)))
        self.c_matiere.currentIndexChanged.connect(self._changer_matiere)
        v.addLayout(_grille([("المادة", self.c_matiere)]))
        evo = st.evolution_tarl(self.f.conn, self.matiere, u)
        self.evolution = evo
        if not evo:
            v.addWidget(QLabel("لا نتائج روائز مستوردة بعد (صفحة «تتبع التعلمات الأساس»)."))
            return c
        v.addWidget(BarresGroupees([e["libelle"] for e in evo],
                                   [("القبلي", [e["pre"] for e in evo], "#94A3B8"),
                                    ("البعدي", [e["post"] for e in evo], theme.BLEU)]))
        t = tableau(["المستوى", "القبلي", "البعدي", "التطور"], etirer=0)
        t.setRowCount(len(evo))
        for i, e in enumerate(evo):
            t.setItem(i, 0, cellule(e["libelle"]))
            t.setItem(i, 1, cellule("—" if e["pre"] is None else f"⁦{e['pre']:g}%⁩"))
            t.setItem(i, 2, cellule("—" if e["post"] is None else f"⁦{e['post']:g}%⁩"))
            ev = e["evolution"]
            it = cellule("—" if ev is None else ("▲ " if ev >= 0 else "▼ ") + f"⁦{ev:+g}⁩ نقطة")
            if ev is not None:
                from PySide6.QtGui import QColor
                it.setForeground(QColor("#047857" if ev >= 0 else theme.ROUGE_TEXTE))
            t.setItem(i, 3, it)
        t.setMinimumHeight(60 + 40 * len(evo))
        v.addWidget(t)
        return c

    def _changer_matiere(self, _=None) -> None:
        self.matiere = self.c_matiere.currentData()
        self.rafraichir(garder=True)
