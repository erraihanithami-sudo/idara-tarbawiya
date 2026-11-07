"""الدعم التربوي (طلب المدير 2026-11-07): المراحل وفئات التعثر، مجموعات يؤطرها أساتذة متدخلون، التلاميذ المستفيدون
ونتائجهم قبل الدعم وبعده، استعمال زمن الدعم، والوثائق: سجل كل أستاذ، برنامج المرحلة، وتقرير المرحلة."""

from __future__ import annotations

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QGridLayout, QHBoxLayout, QLabel, QPushButton,
                               QTableWidgetItem, QWidget)

from idara.services import annee as annee_srv
from idara.services import bureautique
from idara.services import soutien as sv
from idara.ui import theme
from idara.ui.composants import bouton, carte
from idara.ui.formulaires import champ
from idara.ui.graphiques import BarresGroupees, Tuile
from idara.ui.page_pedagogie import _grille, _page
from idara.ui.saisie import ChampDate, cellule, message, selectionner, tableau


def png_barres(categories: list[str], series, largeur: int = 1000, hauteur: int = 380) -> bytes | None:
    if not categories:
        return None
    w = BarresGroupees(categories, series)
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


def _vider(layout) -> None:
    while layout.count():
        it = layout.takeAt(0)
        w = it.widget()
        if w:
            w.hide()
            w.setParent(None)
            w.deleteLater()


class PageSoutien(QWidget):
    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        racine, self.message = _page("الدعم التربوي",
                                     "حدد المرحلة وفئات التعثر، ثم كوّن مجموعات الدعم بأساتذتها وتلاميذها وحصصها، وأدرج "
                                     "نتائج التلاميذ قبل الدعم وبعده (على 10).")
        self.setLayout(racine)

        # 1. المرحلة والفئات
        c, v = carte("مرحلة الدعم وفئات التعثر")
        self.etape = QComboBox()
        self.etape.currentIndexChanged.connect(lambda _: self.afficher_etape())
        self.nom_etape = champ("مثلاً: الدعم المرحلي الأول")
        self.debut, self.fin = ChampDate(), ChampDate()
        v.addLayout(_grille([("المرحلة", self.etape), ("مرحلة جديدة", self.nom_etape), ("من", self.debut),
                             ("إلى", self.fin)]))
        h = QHBoxLayout()
        b = QPushButton("إضافة المرحلة")
        b.clicked.connect(lambda: self.ajouter_etape())
        h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        self.l_categories = QLabel()
        self.l_categories.setWordWrap(True)
        self.l_categories.setObjectName("etiquette")
        self.nom_categorie = champ("فئة جديدة، مثلاً: صعوبات في التركيز")
        b2 = QPushButton("إضافة الفئة")
        b2.clicked.connect(lambda: self.ajouter_categorie())
        h2 = QHBoxLayout()
        h2.addWidget(self.nom_categorie, 1)
        h2.addWidget(b2)
        v.addWidget(self.l_categories)
        v.addLayout(h2)
        racine.addWidget(c)

        # 2. المجموعات
        c, v = carte("مجموعات الدعم")
        self.categorie = QComboBox()
        self.intervenant = QComboBox()
        self.matiere = champ("العربية، الرياضيات...")
        v.addLayout(_grille([("فئة التعثر", self.categorie), ("الأستاذ(ة) المتدخل(ة)", self.intervenant),
                             ("المادة", self.matiere)]))
        h = QHBoxLayout()
        b = QPushButton("إنشاء مجموعة")
        b.setObjectName("principal")
        b.clicked.connect(lambda: self.creer_groupe())
        bs = bouton("حذف المجموعة المحددة")
        bs.clicked.connect(lambda: self.supprimer_groupe())
        h.addWidget(b)
        h.addWidget(bs)
        h.addStretch()
        v.addLayout(h)
        self.t_groupes = tableau(["المجموعة", "الفئة", "الأستاذ(ة)", "المادة", "الأقسام", "التلاميذ", "الحصص"], etirer=0)
        self.t_groupes.setMinimumHeight(220)
        self.t_groupes.itemSelectionChanged.connect(self.afficher_groupe)
        v.addWidget(self.t_groupes)
        racine.addWidget(c)

        # 3. تلاميذ المجموعة
        c, v = carte("تلاميذ المجموعة المحددة ونتائجهم")
        self.l_groupe = QLabel("حدد مجموعة في الجدول أعلاه.")
        self.l_groupe.setObjectName("etiquette")
        v.addWidget(self.l_groupe)
        self.classe = QComboBox()
        self.classe.currentIndexChanged.connect(lambda _: self.afficher_classe())
        v.addLayout(_grille([("القسم", self.classe)]))
        self.t_classe = tableau(["", "الاسم الكامل", "رقم مسار"], etirer=1)
        self.t_classe.setMinimumHeight(220)
        v.addWidget(self.t_classe)
        h = QHBoxLayout()
        b = QPushButton("إضافة التلاميذ المؤشر عليهم إلى المجموعة")
        b.clicked.connect(lambda: self.affecter())
        h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        self.t_membres = tableau(["الاسم الكامل", "القسم", "قبل الدعم", "بعد الدعم", "التطور", "ملاحظات"], etirer=5)
        self.t_membres.setEditTriggers(QAbstractItemView.AllEditTriggers)
        self.t_membres.setMinimumHeight(260)
        v.addWidget(self.t_membres)
        h = QHBoxLayout()
        b = QPushButton("حفظ النتائج")
        b.setObjectName("principal")
        b.clicked.connect(lambda: self.enregistrer_notes())
        br = QPushButton("سحب التلميذ المحدد")
        br.clicked.connect(lambda: self.retirer())
        h.addWidget(b)
        h.addWidget(br)
        h.addStretch()
        v.addLayout(h)
        racine.addWidget(c)

        # 4. استعمال الزمن
        c, v = carte("استعمال زمن الدعم")
        self.jour = QComboBox()
        for i, j in enumerate(sv.JOURS):
            self.jour.addItem(j, i)
        self.h_debut, self.h_fin = champ("14:30", ltr=True), champ("15:30", ltr=True)
        self.lieu = champ("القاعة")
        v.addLayout(_grille([("اليوم", self.jour), ("من الساعة", self.h_debut), ("إلى", self.h_fin),
                             ("المكان", self.lieu)]))
        h = QHBoxLayout()
        b = QPushButton("إضافة حصة للمجموعة المحددة")
        b.clicked.connect(lambda: self.ajouter_seance())
        bs = bouton("حذف الحصة المحددة")
        bs.clicked.connect(lambda: self.supprimer_seance())
        h.addWidget(b)
        h.addWidget(bs)
        h.addStretch()
        v.addLayout(h)
        self.t_edt = tableau(["اليوم", "التوقيت", "المجموعة", "الأستاذ(ة)", "المكان"], etirer=2)
        self.t_edt.setMinimumHeight(200)
        v.addWidget(self.t_edt)
        racine.addWidget(c)

        # 5. الحصيلة والوثائق
        c, v = carte("حصيلة المرحلة والوثائق")
        self.grille = QGridLayout()
        self.grille.setSpacing(12)
        v.addLayout(self.grille)
        self.zone_graph = QWidget()
        self.l_graph = QHBoxLayout(self.zone_graph)
        self.l_graph.setContentsMargins(0, 0, 0, 0)
        v.addWidget(self.zone_graph)
        self.prof_registre = QComboBox()
        v.addLayout(_grille([("سجل الدعم للأستاذ(ة)", self.prof_registre)]))
        h = QHBoxLayout()
        for lib, fn in (("سجل الدعم (Word)", self.generer_registre), ("برنامج الدعم (Word)", self.generer_programme),
                        ("تقرير المرحلة (Word)", self.generer_rapport)):
            b = QPushButton(lib)
            b.clicked.connect(lambda _=False, fn=fn: fn())
            h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        racine.addWidget(c)
        racine.addStretch()
        self.groupes: list[dict] = []
        self.membres: list[dict] = []
        self.edt: list[dict] = []
        self.b: dict | None = None
        self.series: list = []
        self.rafraichir()

    # ---------- التحميل ----------
    def _erreur(self, e: Exception) -> None:
        message(self.message, str(e), True)

    def rafraichir(self) -> None:
        if annee_srv.annee_courante(self.f.conn) is None:
            return
        conn = self.f.conn
        actuel = self.etape.currentData()
        self.etape.blockSignals(True)
        self.etape.clear()
        for e in sv.etapes(conn):
            self.etape.addItem(e["nom"], e["id"])
        self.etape.setCurrentIndex(max(0, self.etape.findData(actuel)))
        self.etape.blockSignals(False)
        cats = sv.categories(conn)
        self.l_categories.setText("فئات التعثر: " + "، ".join(c["nom"] for c in cats))
        cat = self.categorie.currentData()
        self.categorie.clear()
        for c in cats:
            self.categorie.addItem(c["nom"], c["id"])
        self.categorie.setCurrentIndex(max(0, self.categorie.findData(cat)))
        prof = self.intervenant.currentData()
        self.intervenant.clear()
        self.prof_registre.clear()
        for p in sv.intervenants(conn):
            self.intervenant.addItem(p["nom"], p["id"])
            self.prof_registre.addItem(p["nom"], p["id"])
        self.intervenant.setCurrentIndex(max(0, self.intervenant.findData(prof)))
        cl = self.classe.currentData()
        self.classe.blockSignals(True)
        self.classe.clear()
        a = annee_srv.annee_courante(conn)
        for r in conn.execute("SELECT id, code FROM classe WHERE annee_id=? ORDER BY code", (a["id"],)):
            self.classe.addItem(r["code"], r["id"])
        self.classe.setCurrentIndex(max(0, self.classe.findData(cl)))
        self.classe.blockSignals(False)
        self.afficher_classe()
        self.afficher_etape()

    def afficher_etape(self) -> None:
        eid = self.etape.currentData()
        garder = self.gid()
        self.groupes = sv.groupes(self.f.conn, eid) if eid else []
        self.t_groupes.blockSignals(True)
        self.t_groupes.setRowCount(len(self.groupes))
        for i, g in enumerate(self.groupes):
            for j, val in enumerate((g["nom"], g["categorie"], g["intervenant"], g["matiere"] or "—",
                                     "، ".join(g["classes"]) or "—", str(g["effectif"]),
                                     sv._libelle_seances(g["seances"]))):
                self.t_groupes.setItem(i, j, cellule(val, g["id"] if j == 0 else None))
        self.t_groupes.blockSignals(False)
        ligne = next((i for i, g in enumerate(self.groupes) if g["id"] == garder), None)
        if ligne is not None:
            selectionner(self.t_groupes, ligne)
        self.afficher_groupe()
        self.edt = sv.emploi_du_temps(self.f.conn, eid) if eid else []
        self.t_edt.setRowCount(len(self.edt))
        for i, s in enumerate(self.edt):
            for j, val in enumerate((s["jour"], f"⁦{s['debut']} - {s['fin']}⁩", s["groupe"], s["intervenant"],
                                     s["lieu"] or "—")):
                self.t_edt.setItem(i, j, cellule(val, s["id"] if j == 0 else None))
        self.bilan()

    def gid(self) -> int | None:
        rows = self.t_groupes.selectionModel().selectedRows() if self.t_groupes.selectionModel() else []
        if not rows:
            return None
        it = self.t_groupes.item(rows[0].row(), 0)
        return it.data(Qt.UserRole) if it else None

    def afficher_groupe(self) -> None:
        gid = self.gid()
        self.membres = sv.membres(self.f.conn, gid) if gid else []
        g = next((x for x in self.groupes if x["id"] == gid), None)
        self.l_groupe.setText(f"المجموعة: {g['nom']} · {g['intervenant']}" if g else "حدد مجموعة في الجدول أعلاه.")
        self.t_membres.setRowCount(len(self.membres))
        for i, m in enumerate(self.membres):
            self.t_membres.setItem(i, 0, cellule(m["nom"], m["inscription_id"]))
            self.t_membres.setItem(i, 1, cellule(m["classe"] or ""))
            for j, k in ((2, "note_avant"), (3, "note_apres")):
                it = QTableWidgetItem("" if m[k] is None else f"{m[k]:g}")
                it.setTextAlignment(Qt.AlignCenter)
                self.t_membres.setItem(i, j, it)
            ev = cellule(m["evolution"])
            if m["evolution"] in ("تحسن", "تراجع"):
                ev.setForeground(QColor("#047857" if m["evolution"] == "تحسن" else theme.ROUGE_TEXTE))
            self.t_membres.setItem(i, 4, ev)
            self.t_membres.setItem(i, 5, QTableWidgetItem(m["observation"] or ""))
            for col in (0, 1, 4):
                it = self.t_membres.item(i, col)
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)

    def afficher_classe(self) -> None:
        cid = self.classe.currentData()
        els = sv.eleves_classe(self.f.conn, cid) if cid else []
        self.t_classe.setRowCount(len(els))
        for i, e in enumerate(els):
            it = QTableWidgetItem()
            it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Unchecked)
            it.setData(Qt.UserRole, e["inscription_id"])
            self.t_classe.setItem(i, 0, it)
            self.t_classe.setItem(i, 1, cellule(f"{e['nom_ar']} {e['prenom_ar']}"))
            self.t_classe.setItem(i, 2, cellule(e["code_massar"] or ""))

    # ---------- الأفعال ----------
    def ajouter_etape(self) -> int | None:
        try:
            eid = sv.enregistrer_etape(self.f.conn, self.nom_etape.text(), self.debut.iso(), self.fin.iso())
        except ValueError as e:   # ErreurSoutien أو تاريخ غير صحيح
            self._erreur(e if isinstance(e, sv.ErreurSoutien) else ValueError("تاريخ غير صحيح."))
            return None
        self.nom_etape.clear()
        self.debut.clear()
        self.fin.clear()
        self.rafraichir()
        self.etape.setCurrentIndex(self.etape.findData(eid))
        message(self.message, "أضيفت المرحلة.")
        return eid

    def ajouter_categorie(self) -> None:
        try:
            sv.ajouter_categorie(self.f.conn, self.nom_categorie.text())
        except sv.ErreurSoutien as e:
            self._erreur(e)
            return
        self.nom_categorie.clear()
        self.rafraichir()
        message(self.message, "أضيفت الفئة.")

    def creer_groupe(self) -> int | None:
        if self.etape.currentData() is None:
            self._erreur(sv.ErreurSoutien("أضف مرحلة الدعم أولاً."))
            return None
        if self.intervenant.currentData() is None:
            self._erreur(sv.ErreurSoutien("لا أساتذة مسجلين: أضفهم من «الموارد البشرية»."))
            return None
        try:
            gid = sv.creer_groupe(self.f.conn, self.etape.currentData(), self.categorie.currentData(),
                                  self.intervenant.currentData(), self.matiere.text())
        except sv.ErreurSoutien as e:
            self._erreur(e)
            return None
        self.matiere.clear()
        self.afficher_etape()
        ligne = next(i for i, g in enumerate(self.groupes) if g["id"] == gid)
        selectionner(self.t_groupes, ligne)
        self.afficher_groupe()
        message(self.message, "أنشئت المجموعة: أضف تلاميذها وحصصها.")
        return gid

    def supprimer_groupe(self) -> None:
        gid = self.gid()
        if gid is None:
            self._erreur(sv.ErreurSoutien("حدد مجموعة."))
            return
        sv.supprimer_groupe(self.f.conn, gid)
        self.afficher_etape()
        message(self.message, "حُذفت المجموعة.")

    def cocher(self, lignes: list[int]) -> None:
        for i in lignes:
            self.t_classe.item(i, 0).setCheckState(Qt.Checked)

    def affecter(self) -> int:
        gid = self.gid()
        if gid is None:
            self._erreur(sv.ErreurSoutien("حدد المجموعة أولاً."))
            return 0
        ids = [self.t_classe.item(i, 0).data(Qt.UserRole) for i in range(self.t_classe.rowCount())
               if self.t_classe.item(i, 0).checkState() == Qt.Checked]
        try:
            n = sv.affecter(self.f.conn, gid, ids)
        except sv.ErreurSoutien as e:
            self._erreur(e)
            return 0
        self.afficher_classe()
        self.afficher_etape()
        message(self.message, f"أضيف {n} تلميذ(ة) إلى المجموعة.")
        return n

    def enregistrer_notes(self) -> bool:
        gid = self.gid()
        if gid is None:
            return False
        vals = [(self.t_membres.item(i, 0).data(Qt.UserRole), self.t_membres.item(i, 2).text(),
                 self.t_membres.item(i, 3).text(), self.t_membres.item(i, 5).text())
                for i in range(self.t_membres.rowCount())]
        try:
            sv.noter(self.f.conn, gid, vals)
        except sv.ErreurSoutien as e:
            self._erreur(e)
            return False
        self.afficher_etape()
        message(self.message, "حُفظت النتائج.")
        return True

    def retirer(self) -> None:
        gid = self.gid()
        rows = self.t_membres.selectionModel().selectedRows()
        if gid is None or not rows:
            self._erreur(sv.ErreurSoutien("حدد التلميذ في جدول المجموعة."))
            return
        sv.retirer(self.f.conn, gid, self.t_membres.item(rows[0].row(), 0).data(Qt.UserRole))
        self.afficher_etape()

    def ajouter_seance(self) -> int | None:
        gid = self.gid()
        if gid is None:
            self._erreur(sv.ErreurSoutien("حدد المجموعة أولاً."))
            return None
        try:
            sid = sv.ajouter_seance(self.f.conn, gid, self.jour.currentData(), self.h_debut.text().strip(),
                                    self.h_fin.text().strip(), self.lieu.text())
        except sv.ErreurSoutien as e:
            self._erreur(e)
            return None
        self.afficher_etape()
        message(self.message, "أضيفت الحصة.")
        return sid

    def supprimer_seance(self) -> None:
        rows = self.t_edt.selectionModel().selectedRows()
        if not rows:
            self._erreur(sv.ErreurSoutien("حدد الحصة."))
            return
        sv.supprimer_seance(self.f.conn, self.t_edt.item(rows[0].row(), 0).data(Qt.UserRole))
        self.afficher_etape()

    # ---------- الحصيلة ----------
    def bilan(self) -> None:
        _vider(self.grille)
        _vider(self.l_graph)
        eid = self.etape.currentData()
        self.b = sv.bilan_etape(self.f.conn, eid) if eid else None
        if not self.b or not self.b["groupes"]:
            self.grille.addWidget(Tuile("لا مجموعات دعم في هذه المرحلة بعد", "—", theme.GRIS, "التدبير التربوي"), 0, 0)
            return
        gl = self.b["global"]
        fmt = sv._n
        for k, (lib, val, coul, note) in enumerate((
                ("التلاميذ المستفيدون", str(self.b["beneficiaires"]), theme.VERT,
                 f"{len(self.b['groupes'])} مجموعة · {self.b['intervenants']} أستاذ(ة)"),
                ("نسبة من تحسنت نتائجهم", fmt(gl["pct_ameliores"], "%"), theme.BLEU,
                 f"{gl['ameliores']} من {gl['evalues']} تلميذاً قُوّموا قبل الدعم وبعده"),
                ("المعدل قبل الدعم ← بعده", f"⁦{fmt(gl['moy_avant'])} ← {fmt(gl['moy_apres'])}⁩", theme.ORANGE,
                 "على 10"),
                ("نسبة التحكم قبل ← بعد", f"⁦{fmt(gl['maitrise_avant'], '%')} ← {fmt(gl['maitrise_apres'], '%')}⁩",
                 theme.SARCELLE, f"نقطة {sv.SEUIL:g}/10 فما فوق"))):
            self.grille.addWidget(Tuile(lib, val, coul, "التدبير التربوي", note), k // 2, k % 2)
        cats = self.b["categories"]
        self.series = [("قبل الدعم", [c["bilan"]["maitrise_avant"] for c in cats], "#94A3B8"),
                       ("بعد الدعم", [c["bilan"]["maitrise_apres"] for c in cats], theme.BLEU)]
        self.l_graph.addWidget(BarresGroupees([c["categorie"] for c in cats], self.series))

    # ---------- الوثائق ----------
    def _ouvrir(self, p):
        message(self.message, f"وُلّدت الوثيقة: {p.name}")
        try:
            bureautique.ouvrir(p)
        except Exception:  # noqa: BLE001
            pass
        return p

    def generer_registre(self):
        if self.etape.currentData() is None or self.prof_registre.currentData() is None:
            self._erreur(sv.ErreurSoutien("اختر المرحلة والأستاذ(ة)."))
            return None
        try:
            return self._ouvrir(sv.generer_registre(self.f.conn, self.f.dossier, self.etape.currentData(),
                                                    self.prof_registre.currentData()))
        except sv.ErreurSoutien as e:
            self._erreur(e)
            return None

    def generer_programme(self):
        if self.etape.currentData() is None:
            self._erreur(sv.ErreurSoutien("أضف مرحلة الدعم أولاً."))
            return None
        try:
            return self._ouvrir(sv.generer_programme(self.f.conn, self.f.dossier, self.etape.currentData()))
        except sv.ErreurSoutien as e:
            self._erreur(e)
            return None

    def generer_rapport(self):
        if self.etape.currentData() is None:
            self._erreur(sv.ErreurSoutien("أضف مرحلة الدعم أولاً."))
            return None
        b = self.b
        png = None
        if b and b["categories"]:
            png = png_barres([c["categorie"] for c in b["categories"]], self.series)
        try:
            return self._ouvrir(sv.generer_rapport(self.f.conn, self.f.dossier, self.etape.currentData(), png))
        except sv.ErreurSoutien as e:
            self._erreur(e)
            return None
