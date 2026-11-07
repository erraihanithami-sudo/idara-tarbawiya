"""تتبع مشروع المؤسسة المندمج (قرار المدير 2026-11-07): لوحة قيادة بمبيان لكل هدف من الأهداف الثلاثة، المستهدفات،
تتبع تنزيل العمليات المستوردة من مسار، والتقارير التركيبية. الصياغة تبقى في مسار."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QFileDialog, QGridLayout, QHBoxLayout, QLabel,
                               QPushButton, QTableWidgetItem, QWidget)

from idara.services import annee as annee_srv
from idara.services import bureautique
from idara.services import projet_etab as pe
from idara.ui import theme
from idara.ui.composants import bouton, carte
from idara.ui.formulaires import champ
from idara.ui.graphiques import BarresGroupees, Tuile
from idara.ui.page_pedagogie import _grille, _page
from idara.ui.page_soutien import _vider, png_barres
from idara.ui.saisie import cellule, message

COULEURS = {"tarl": theme.SARCELLE, "hadar": theme.ROSE, "activites": theme.VIOLET}
SECTION_TUILE = {"tarl": "التدبير التربوي", "hadar": "حركية التلاميذ", "activites": "التدبير التربوي"}


def _f(v, s="%") -> str:
    return "—" if v is None else f"⁦{v:g}{s}⁩"


def series_indicateur(x: dict) -> tuple[list[str], list]:
    cats = ["المرجعية"] + [l["annee"] for l in x["annees"]]
    return cats, [("المستهدف", [x["reference"]] + [l["cible"] for l in x["annees"]], "#94A3B8"),
                  ("المحقق", [None] + [l["realise"] for l in x["annees"]], COULEURS_SERIE[x["sens"]])]


COULEURS_SERIE = {1: theme.BLEU, -1: theme.ROSE}


class PageProjet(QWidget):
    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        racine, self.message = _page("مشروع المؤسسة",
                                     "تتبع مؤشرات الأهداف الثلاثة وتنزيل العمليات. صياغة المشروع تتم في منظومة مسار؛ "
                                     "تُستورد منه خطة العمل ثم تُتابع هنا.")
        self.setLayout(racine)
        # 1. المشروع
        c, v = carte("المشروع")
        self.c_projet = QComboBox()
        self.c_projet.currentIndexChanged.connect(lambda _: self.changer_projet())
        self.intitule = champ("مشروع المؤسسة المندمج")
        self.debut, self.fin = QComboBox(), QComboBox()
        a0 = int(annee_srv.libelle_pour_date()[:4])
        for y in range(a0 - 4, a0 + 5):
            for cb in (self.debut, self.fin):
                cb.addItem(f"{y}/{y + 1}", f"{y}/{y + 1}")
        self.debut.setCurrentIndex(self.debut.findData(f"{a0}/{a0 + 1}"))
        self.fin.setCurrentIndex(self.fin.findData(f"{a0 + 2}/{a0 + 3}"))
        v.addLayout(_grille([("المشروع المتتبَّع", self.c_projet), ("العنوان", self.intitule),
                             ("سنة البداية", self.debut), ("سنة النهاية", self.fin)]))
        h = QHBoxLayout()
        b = QPushButton("حفظ المشروع")
        b.setObjectName("principal")
        b.clicked.connect(lambda: self.enregistrer_projet())
        bn = QPushButton("مشروع جديد")
        bn.clicked.connect(lambda: self.enregistrer_projet(nouveau=True))
        h.addWidget(b)
        h.addWidget(bn)
        h.addStretch()
        v.addLayout(h)
        racine.addWidget(c)
        # 2. لوحة القيادة (يعاد بناؤها)
        self.c_tableau, tv = carte("لوحة قيادة المشروع")
        self.grille = QGridLayout()
        self.grille.setSpacing(12)
        tv.addLayout(self.grille)
        self.zone_graphs = QWidget()
        self.l_graphs = QGridLayout(self.zone_graphs)
        self.l_graphs.setContentsMargins(0, 0, 0, 0)
        self.l_graphs.setSpacing(14)
        tv.addWidget(self.zone_graphs)
        racine.addWidget(self.c_tableau)
        # 3. المستهدفات
        c, v = carte("القيمة المرجعية والمستهدفات (من وثيقة المشروع في مسار)")
        n = QLabel("النسب بالمائة. «محقق يدوياً» لسنة لا معطيات لها في البرنامج (سنة سابقة مثلاً)؛ "
                   "ما يحسبه البرنامج يُقدَّم عليه.")
        n.setObjectName("etiquette")
        n.setWordWrap(True)
        v.addWidget(n)
        self.t_cibles = tableau_editable(["المؤشر", "السنة", "المستهدف", "المحقق (البرنامج)", "محقق يدوياً"])
        self.t_cibles.setMinimumHeight(330)
        v.addWidget(self.t_cibles)
        h = QHBoxLayout()
        b = QPushButton("حفظ المستهدفات")
        b.setObjectName("principal")
        b.clicked.connect(lambda: self.enregistrer_cibles())
        h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        racine.addWidget(c)
        # 4. العمليات
        c, v = carte("تتبع تنزيل العمليات")
        n = QLabel("استورد تقرير «خطة العمل» أو ملف تصدير العمليات من مسار. إعادة الاستيراد تحدّث المبالغ والتواريخ "
                   "ولا تمس الحالة والإنجاز والمصروف.")
        n.setObjectName("etiquette")
        n.setWordWrap(True)
        v.addWidget(n)
        h = QHBoxLayout()
        b = QPushButton("استيراد خطة العمل من مسار")
        b.clicked.connect(self.choisir_fichier)
        h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        self.l_ops = QLabel()
        self.l_ops.setObjectName("etiquette")
        self.l_ops.setWordWrap(True)
        v.addWidget(self.l_ops)
        self.t_ops = tableau_editable(["العملية", "المحور", "المعيار", "الفترة", "المبلغ", "الحالة", "الإنجاز %",
                                       "المصروف", "ملاحظات"])
        self.t_ops.setMinimumHeight(380)
        v.addWidget(self.t_ops)
        h = QHBoxLayout()
        b = QPushButton("حفظ التتبع")
        b.setObjectName("principal")
        b.clicked.connect(lambda: self.enregistrer_suivi())
        bs = bouton("حذف العملية المحددة")
        bs.clicked.connect(lambda: self.supprimer_operation())
        h.addWidget(b)
        h.addWidget(bs)
        h.addStretch()
        v.addLayout(h)
        racine.addWidget(c)
        # 5. التقارير
        c, v = carte("التقارير")
        h = QHBoxLayout()
        for lib, final in (("التقرير التركيبي للإنجاز (Word)", False), ("حصيلة نهاية المشروع (Word)", True)):
            b = QPushButton(lib)
            b.clicked.connect(lambda _=False, fi=final: self.generer(fi))
            h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        racine.addWidget(c)
        racine.addStretch()
        self.ind: dict = {}
        self.ops: list = []
        self.rafraichir()

    # ---------- التحميل ----------
    def pid(self) -> int | None:
        return self.c_projet.currentData()

    def rafraichir(self) -> None:
        actif = pe.projet_actif(self.f.conn)
        garder = self.pid() or (actif["id"] if actif else None)
        self.c_projet.blockSignals(True)
        self.c_projet.clear()
        for p in pe.projets(self.f.conn):
            self.c_projet.addItem(f"{p['intitule']} ({p['annee_debut']} - {p['annee_fin']})", p["id"])
        self.c_projet.setCurrentIndex(max(0, self.c_projet.findData(garder)))
        self.c_projet.blockSignals(False)
        self.changer_projet()

    def changer_projet(self) -> None:
        pid = self.pid()
        if pid:
            p = pe.projet(self.f.conn, pid)
            self.intitule.setText(p["intitule"])
            for cb, k in ((self.debut, "annee_debut"), (self.fin, "annee_fin")):
                if cb.findData(p[k]) < 0:
                    cb.addItem(p[k], p[k])
                cb.setCurrentIndex(cb.findData(p[k]))
            if not p["actif"]:
                pe.activer(self.f.conn, pid)
        self.ind = pe.tableau_indicateurs(self.f.conn, pid) if pid else {}
        self.ops = pe.operations(self.f.conn, pid) if pid else []
        self._tableau_bord()
        self._cibles()
        self._operations()

    def _tableau_bord(self) -> None:
        _vider(self.grille)
        _vider(self.l_graphs)
        self.graphs: dict[str, BarresGroupees] = {}
        if not self.ind:
            self.grille.addWidget(Tuile("سجّل المشروع (العنوان والسنوات) لبدء التتبع", "—", theme.GRIS,
                                        "القيادة والتدبير"), 0, 0)
            return
        for k, (cle, x) in enumerate(self.ind.items()):
            d = x["derniere"]
            note = (f"{d['annee']} · المستهدف {_f(d['cible'])}" if d else "لا معطيات بعد") + \
                ("" if x["evolution"] is None else f" · {x['evolution']:+g} نقطة عن المرجعية")
            self.grille.addWidget(Tuile(x["libelle"], _f(d["realise"]) if d else "—", COULEURS[cle],
                                        SECTION_TUILE[cle], note), k // 2, k % 2)
        so = pe.synthese_operations(self.f.conn, self.pid())
        self.synthese = so
        self.grille.addWidget(Tuile("نسبة إنجاز العمليات", _f(so["taux_global"]), theme.VERT, "القيادة والتدبير",
                                    f"{so['par_statut']['realisee']} منجزة من {so['actives']} · المصروف "
                                    f"{_f(so['pct_depense'])} من المبرمج"), 1, 1)
        for i, (cle, x) in enumerate(self.ind.items()):
            c, v = carte(x["objectif"])
            cats, series = series_indicateur(x)
            g = BarresGroupees(cats, series, maximum=None if cle == "hadar" else 100)
            g.setMinimumHeight(260)
            self.graphs[cle] = g
            v.addWidget(g)
            if cle == "tarl" and x["derniere"]:
                l = QLabel("حسب المادة: " + "، ".join(f"{m['libelle']} {_f(m['valeur'])}"
                                                    for m in x["derniere"]["detail"]["matieres"].values()))
                l.setObjectName("etiquette")
                v.addWidget(l)
            if cle == "hadar":
                l = QLabel("كلما انخفضت النسبة كان أفضل.")
                l.setObjectName("etiquette")
                v.addWidget(l)
            v.activate()
            c.setMinimumHeight(max(330, v.totalMinimumSize().height() + 40))
            self.l_graphs.addWidget(c, i, 0)
        # داخل منطقة التمرير: الارتفاع الأدنى يُحدَّث بعد إعادة البناء، وإلا تنضغط المبيانات
        self.l_graphs.activate()
        self.zone_graphs.setMinimumHeight(self.l_graphs.totalMinimumSize().height())

    def _cibles(self) -> None:
        t = self.t_cibles
        lignes = []
        for cle, x in self.ind.items():
            lignes.append((cle, "ref", x["reference"], None, None))
            for l in x["annees"]:
                calc = l["detail"]["valeur"]
                lignes.append((cle, l["annee"], l["cible"], calc, l["manuel"]))
        self.lignes_cibles = lignes
        t.setRowCount(len(lignes))
        for i, (cle, an, cible, calc, manuel) in enumerate(lignes):
            t.setItem(i, 0, _fixe(pe.INDICATEURS[cle]))
            t.setItem(i, 1, _fixe("المرجعية" if an == "ref" else an))
            t.setItem(i, 2, _editable("" if cible is None else f"{cible:g}"))
            t.setItem(i, 3, _fixe("—" if calc is None else f"{calc:g}%"))
            t.setItem(i, 4, _editable("" if manuel is None else f"{manuel:g}") if an != "ref" else _fixe(""))

    def _operations(self) -> None:
        t = self.t_ops
        t.setRowCount(len(self.ops))
        for i, o in enumerate(self.ops):
            periode = " → ".join(x for x in (o["date_debut"], o["date_fin"]) if x) or "—"
            for j, val in enumerate((o["intitule"], o["axe"] or "—", o["critere"] or "—", periode,
                                     "—" if o["montant"] is None else f"{o['montant']:g}")):
                it = _fixe(val)
                if j == 0:
                    it.setData(Qt.UserRole, o["id"])
                t.setItem(i, j, it)
            cb = QComboBox()
            for k, lib in pe.STATUTS.items():
                cb.addItem(lib, k)
            cb.setCurrentIndex(cb.findData(o["statut"]))
            t.setCellWidget(i, 5, cb)
            t.setItem(i, 5, _fixe(""))
            t.setItem(i, 6, _editable(f"{o['taux']:g}"))
            t.setItem(i, 7, _editable("" if o["montant_depense"] is None else f"{o['montant_depense']:g}"))
            it = _editable(o["observation"] or "")
            it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            t.setItem(i, 8, it)
            if o["statut"] == "realisee":
                t.item(i, 0).setForeground(QColor("#047857"))
        if self.pid():
            so = pe.synthese_operations(self.f.conn, self.pid())
            self.l_ops.setText(f"{so['total']} عملية · المبرمج {so['montant_programme']:g} درهم (منها جمعية النجاح "
                               f"{so['budget_najah']:g}) · المصروف {so['montant_depense']:g} درهم")
        else:
            self.l_ops.setText("")

    # ---------- الأفعال ----------
    def enregistrer_projet(self, nouveau: bool = False) -> int | None:
        try:
            pid = pe.enregistrer_projet(self.f.conn, self.intitule.text(), self.debut.currentData(),
                                        self.fin.currentData(), None if nouveau else self.pid())
        except pe.ErreurProjet as e:
            message(self.message, str(e), True)
            return None
        self.c_projet.blockSignals(True)
        self.c_projet.clear()
        self.c_projet.blockSignals(False)
        pe.activer(self.f.conn, pid)
        self.rafraichir()
        self.c_projet.setCurrentIndex(self.c_projet.findData(pid))
        message(self.message, "حُفظ المشروع.")
        return pid

    def enregistrer_cibles(self) -> bool:
        pid = self.pid()
        if not pid:
            message(self.message, "سجّل المشروع أولاً.", True)
            return False
        vals = [(cle, an, self.t_cibles.item(i, 2).text(), self.t_cibles.item(i, 4).text() if an != "ref" else None)
                for i, (cle, an, *_r) in enumerate(self.lignes_cibles)]
        try:
            pe.enregistrer_cibles(self.f.conn, pid, vals)
        except pe.ErreurProjet as e:
            message(self.message, str(e), True)
            return False
        self.changer_projet()
        message(self.message, "حُفظت المستهدفات.")
        return True

    def choisir_fichier(self) -> None:
        f, _ = QFileDialog.getOpenFileName(self, "خطة العمل من مسار", "", "Excel (*.xlsx *.xls)")
        if f:
            self.importer(Path(f))

    def importer(self, chemin: Path):
        if not self.pid():
            message(self.message, "سجّل المشروع (العنوان والسنوات) قبل الاستيراد.", True)
            return None
        try:
            r = pe.importer_operations(self.f.conn, self.pid(), chemin)
        except pe.ErreurProjet as e:
            message(self.message, str(e), True)
            return None
        self.changer_projet()
        message(self.message, f"استُوردت خطة العمل: {r.ajoutees} عملية جديدة، {r.mises_a_jour} حُدّثت."
                + (" " + " ".join(r.avertissements) if r.avertissements else ""))
        return r

    def enregistrer_suivi(self) -> bool:
        try:
            for i in range(self.t_ops.rowCount()):
                oid = self.t_ops.item(i, 0).data(Qt.UserRole)
                pe.suivre(self.f.conn, oid, self.t_ops.cellWidget(i, 5).currentData(), self.t_ops.item(i, 6).text(),
                          self.t_ops.item(i, 7).text(), self.t_ops.item(i, 8).text())
        except pe.ErreurProjet as e:
            message(self.message, f"السطر {i + 1}: {e}", True)
            return False
        self.changer_projet()
        message(self.message, "حُفظ تتبع العمليات.")
        return True

    def supprimer_operation(self) -> None:
        rows = self.t_ops.selectionModel().selectedRows()
        if not rows:
            message(self.message, "حدد العملية في الجدول.", True)
            return
        pe.supprimer_operation(self.f.conn, self.t_ops.item(rows[0].row(), 0).data(Qt.UserRole))
        self.changer_projet()

    def generer(self, final: bool = False):
        if not self.pid():
            message(self.message, "سجّل المشروع أولاً.", True)
            return None
        pngs = {}
        for cle, x in self.ind.items():
            cats, series = series_indicateur(x)
            pngs[cle] = png_barres(cats, series, maximum=None if cle == "hadar" else 100)
        p = pe.generer_rapport(self.f.conn, self.f.dossier, self.pid(), final, pngs)
        message(self.message, f"وُلّد التقرير: {p.name}")
        try:
            bureautique.ouvrir(p)
        except Exception:  # noqa: BLE001
            pass
        return p


def tableau_editable(entetes: list[str]):
    from idara.ui.saisie import tableau
    t = tableau(entetes, etirer=0)
    t.setEditTriggers(QAbstractItemView.AllEditTriggers)
    return t


def _fixe(texte: str) -> QTableWidgetItem:
    it = cellule(texte)
    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
    return it


def _editable(texte: str) -> QTableWidgetItem:
    it = QTableWidgetItem(texte)
    it.setTextAlignment(Qt.AlignCenter)
    return it
