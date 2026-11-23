"""صفحة «بطاقة التلميذ» (توجيهات المدير 2026-11-15): مسار كل تلميذ من الرائز القبلي إلى البعدي ثم المراحل، مع
مبيانين، وإدخال مستويات التحكم، وطبع البطاقة لتلميذ أو لقسم كامل."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QTableWidget, QVBoxLayout, QWidget)

from idara.services import annee as annee_srv
from idara.services import bureautique
from idara.services import fiche_eleve as fe
from idara.ui.composants import carte
from idara.ui.graphe_parcours import Graphe, graphiques, peindre_etapes, peindre_tarl
from idara.ui.page_pedagogie import _page
from idara.ui.saisie import cellule, message, tableau


class PageFicheEleve(QWidget):
    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        self.eid: int | None = None
        self.p: dict | None = None
        racine, self.message = _page(
            "بطاقة التلميذ", "تتبع مسار كل تلميذ وتطور مستواه: رائزا الموضعة القبلي والبعدي (مستويات التعلم TaRL)، ثم "
                            "مستوى التحكم في كل مرحلة، مع مبيانين وملاحظات آلية.")
        self.setLayout(racine)

        c, v = carte("اختيار التلميذ")
        h = QHBoxLayout()
        self.classe = QComboBox()
        self.classe.currentIndexChanged.connect(lambda _: self.lister())
        self.recherche = QLineEdit()
        self.recherche.setPlaceholderText("بحث: الاسم أو رقم مسار")
        self.recherche.setClearButtonEnabled(True)
        self.recherche.textChanged.connect(lambda _: self.lister())
        self.annee = QComboBox()
        self.annee.currentIndexChanged.connect(lambda _: self.afficher())
        h.addWidget(self.classe)
        h.addWidget(self.recherche, 1)
        h.addWidget(QLabel("السنة:"))
        h.addWidget(self.annee)
        v.addLayout(h)
        self.liste = tableau(["التلميذ(ة)", "القسم", "رقم مسار"], etirer=0)
        self.liste.setMinimumHeight(170)
        self.liste.setMaximumHeight(230)
        self.liste.itemSelectionChanged.connect(self._selection)
        v.addWidget(self.liste)
        h = QHBoxLayout()
        b = QPushButton("طباعة بطاقة التلميذ")
        b.setObjectName("principal")
        b.clicked.connect(lambda: self.generer())
        h.addWidget(b)
        b = QPushButton("بطاقات القسم كله")
        b.setToolTip("بطاقة لكل تلميذ في القسم المختار، صفحة لكل واحد")
        b.clicked.connect(lambda: self.generer(tous=True))
        h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        racine.addWidget(c)

        self.c_fiche, v = carte("مسار التلميذ")
        self.titre = QLabel()
        self.titre.setObjectName("titreCarte")
        self.titre.setWordWrap(True)
        v.addWidget(self.titre)
        t = QLabel("رائزا الموضعة (TaRL)")
        t.setObjectName("titreCarte")
        v.addWidget(t)
        self.t_tarl = tableau(["المادة", "الرائز القبلي", "الرائز البعدي", "المستوى المتوقع", "التطور"], etirer=0)
        self.t_tarl.setMaximumHeight(140)
        v.addWidget(self.t_tarl)
        self.g_tarl = Graphe(peindre_tarl, 300)
        v.addWidget(self.g_tarl)
        t = QLabel("مستوى التحكم حسب الروائز والمراحل")
        t.setObjectName("titreCarte")
        t.setWordWrap(True)
        v.addWidget(t)
        self.t_etapes = QTableWidget(len(fe.MATIERES), len(fe.PHASES))
        self.t_etapes.setHorizontalHeaderLabels([fe.libelle_phase(ph) for ph in fe.PHASES])
        self.t_etapes.setVerticalHeaderLabels(list(fe.MATIERES.values()))
        self.t_etapes.setEditTriggers(QAbstractItemView.AllEditTriggers)
        self.t_etapes.setMinimumHeight(160)
        # توجيه المدير 2026-11-23: الإدخال في نافذة منبثقة
        from idara.ui.vitrine import bouton_couleur, en_fenetre
        w_e = QWidget()
        ve = QVBoxLayout(w_e)
        ve.setContentsMargins(0, 0, 0, 0)
        ve.addWidget(self.t_etapes)
        be = QPushButton("حفظ المستويات")
        be.setObjectName("principal")
        be.clicked.connect(lambda: self.enregistrer())
        ve.addWidget(be, 0, Qt.AlignLeft)
        self.fiche_etapes = en_fenetre(self, w_e, "مستوى التحكم حسب الروائز والمراحل", "اكتب A أو B أو C.", 900,
                                       ("enregistrer",))
        h = QHBoxLayout()
        b = bouton_couleur("إدخال مستويات التحكم", "#1565C0", "modifier")
        b.clicked.connect(lambda: self.fiche_etapes.ouvrir())
        h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        self.g_etapes = Graphe(peindre_etapes, 280)
        v.addWidget(self.g_etapes)
        self.obs = QLabel()
        self.obs.setObjectName("info")
        self.obs.setWordWrap(True)
        v.addWidget(self.obs)
        self.c_fiche.hide()
        racine.addWidget(self.c_fiche)

        # ---- الملف الشامل (طلب المدير 2026-11-20) ----
        self.c_dossier, v = carte("الملف الشامل للتلميذ(ة)")
        s = QLabel("كل ما سُجّل للتلميذ(ة) عبر السنوات: المسار الدراسي، المعدلات، الحركية، السلوك، الفحوصات الطبية، "
                   "والتنويهات والتشجيعات. يُطبع مع البطاقة.")
        s.setObjectName("sousTitre")
        s.setWordWrap(True)
        v.addWidget(s)
        h = QHBoxLayout()
        h.setSpacing(8)
        self.pilules_dossier: dict[str, QPushButton] = {}
        couleurs = {"parcours": "#1565C0", "moyennes": "#2E7D32", "mouvements": "#00838F", "comportement": "#C62828",
                    "medical": "#AD1457", "distinctions": "#EF6C00"}
        self.couleurs_dossier = couleurs
        for cle, titre, *_ in fe.SECTIONS_DOSSIER:
            b = QPushButton(titre)
            b.setObjectName("pilule")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=cle: self.choisir_section(k))
            self.pilules_dossier[cle] = b
            h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        self.t_dossier = tableau([""], etirer=0)
        self.t_dossier.setMinimumHeight(200)
        v.addWidget(self.t_dossier)
        self.l_dossier_vide = QLabel()
        self.l_dossier_vide.setObjectName("etiquette")
        self.l_dossier_vide.setWordWrap(True)
        v.addWidget(self.l_dossier_vide)
        self.c_dossier.hide()
        racine.addWidget(self.c_dossier)
        self.dossier: dict | None = None
        self.section = "parcours"
        racine.addStretch()
        self.lignes: list[dict] = []
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
        an = self.annee.currentText()
        self.annee.blockSignals(True)
        self.annee.clear()
        self.annee.addItems(fe.annees(self.f.conn))
        if an:
            self.annee.setCurrentIndex(max(0, self.annee.findText(an)))
        self.annee.blockSignals(False)
        self.lister()

    def lister(self) -> None:
        self.lignes = fe.eleves(self.f.conn, self.classe.currentData(), self.recherche.text())
        self.liste.blockSignals(True)
        self.liste.setRowCount(len(self.lignes))
        for i, e in enumerate(self.lignes):
            for j, x in enumerate((f"{e['prenom_ar']} {e['nom_ar']}", e["classe"] or "", e["code_massar"] or "")):
                self.liste.setItem(i, j, cellule(x, e["id"]))
        self.liste.blockSignals(False)

    def _selection(self) -> None:
        rows = {i.row() for i in self.liste.selectedIndexes()}
        if len(rows) == 1:
            self.charger(self.liste.item(rows.pop(), 0).data(Qt.UserRole))

    def charger(self, eid: int) -> None:
        self.eid = eid
        self.afficher()

    def afficher(self) -> None:
        if self.eid is None:
            return
        self.p = p = fe.parcours(self.f.conn, self.eid, self.annee.currentText() or None)
        e = p["eleve"]
        self.titre.setText(f"{e['nom']} · {e['classe']} · ⁦{e['code_massar']}⁩ · السنة {p['annee']}")
        self.t_tarl.setRowCount(len(p["tarl"]))
        for i, (m, t) in enumerate(p["tarl"].items()):
            d = (None if t["rang_pre"] is None or t["rang_post"] is None else t["rang_post"] - t["rang_pre"])
            for j, x in enumerate((fe.MATIERES[m], t["pre"] or "", t["post"] or "", t["attendu"] or "",
                                   "" if d is None else (f"+{d}" if d > 0 else str(d)))):
                self.t_tarl.setItem(i, j, cellule(x))
        for i, m in enumerate(fe.MATIERES):
            for j, ph in enumerate(fe.PHASES):
                it = cellule(p["etapes"].get(m, {}).get(ph, ""))
                it.setFlags(it.flags() | Qt.ItemIsEditable)
                it.setTextAlignment(Qt.AlignCenter)
                self.t_etapes.setItem(i, j, it)
        self.g_tarl.definir(p)
        self.g_tarl.setVisible(bool(p["tarl"]))
        self.g_etapes.definir(p)
        self.g_etapes.setVisible(bool(p["etapes"]))
        obs = fe.observations(p)
        if obs and fe.a_besoin_soutien(p):
            obs.append("يُقترح إدراجه(ا) في مجموعات الدعم.")
        self.obs.setText("\n".join(obs) if obs else "لا معطيات تقويم بعد: استورد مستويات التعلم (TaRL) أو نتائج "
                                                    "الروائز في «المدرسة الرائدة ← شارة الريادة»، أو أدخل المستويات أعلاه.")
        self.c_fiche.show()
        self.dossier = fe.dossier_complet(self.f.conn, self.eid)
        for cle, titre, *_ in fe.SECTIONS_DOSSIER:
            n = len(self.dossier[cle])
            self.pilules_dossier[cle].setText(f"{titre} ({n})" if n else titre)
        self.choisir_section(self.section)
        self.c_dossier.show()

    def choisir_section(self, cle: str) -> None:
        from PySide6.QtGui import QBrush, QColor
        self.section = cle
        for k, b in self.pilules_dossier.items():
            b.setChecked(k == cle)
        if self.dossier is None:
            return
        _, titre, entetes, champs = next(x for x in fe.SECTIONS_DOSSIER if x[0] == cle)
        lignes = self.dossier[cle]
        t = self.t_dossier
        t.clear()
        t.setColumnCount(len(entetes))
        t.setHorizontalHeaderLabels(list(entetes))
        t.setRowCount(len(lignes))
        couleur = QColor(self.couleurs_dossier[cle])
        for i, x in enumerate(lignes):
            for j, c in enumerate(champs):
                it = cellule(fe.valeur_dossier(c, x[c]))
                if c in ("mention", "type", "statut", "nature") and x[c]:
                    it.setForeground(QBrush(couleur))
                    f = it.font()
                    f.setBold(True)
                    it.setFont(f)
                t.setItem(i, j, it)
        t.horizontalHeader().setStretchLastSection(True)
        t.setVisible(bool(lignes))
        self.l_dossier_vide.setText("" if lignes else f"لا شيء مسجل في «{titre}» لهذا التلميذ(ة).")
        self.l_dossier_vide.setVisible(not lignes)

    def enregistrer(self) -> bool:
        if self.p is None:
            return False
        self.t_etapes.setCurrentItem(None)
        try:
            for i, m in enumerate(fe.MATIERES):
                for j, ph in enumerate(fe.PHASES):
                    it = self.t_etapes.item(i, j)
                    fe.enregistrer_etape(self.f.conn, self.eid, self.p["annee"], ph, m, it.text() if it else "")
        except fe.ErreurFiche as e:
            message(self.message, str(e), True)
            return False
        self.afficher()
        message(self.message, "حُفظت مستويات التحكم.")
        return True

    def generer(self, tous: bool = False):
        ids = [e["id"] for e in self.lignes] if tous else ([self.eid] if self.eid is not None else [])
        if tous and self.classe.currentData() is None:
            message(self.message, "اختر قسماً أولاً لطبع بطاقات تلاميذه.", True)
            return None
        try:
            p = fe.generer(self.f.conn, self.f.dossier, ids, self.annee.currentText() or None, graphiques)
        except (fe.ErreurFiche, OSError) as e:
            message(self.message, str(e), True)
            return None
        message(self.message, f"وُلّدت البطاقة: ⁦{p.name}⁩")
        try:
            bureautique.ouvrir(p)
        except OSError:
            pass
        return p
