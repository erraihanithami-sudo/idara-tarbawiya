"""التقييم: محاضر نهاية الأسدوس، والامتحان الموحد المحلي والإقليمي (ملفا المدير، 2026-11-03)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QFileDialog, QGridLayout, QHBoxLayout, QLabel, QPushButton,
                               QSpinBox, QTableWidgetItem, QWidget)

from idara.services import bureautique
from idara.services import deliberations as dl
from idara.services import docs_examen as de
from idara.services import evaluation as ev
from idara.services import examens as exs
from idara.services import textes as tx
from idara.ui.composants import bouton, carte
from idara.ui.formulaires import champ
from idara.ui.page_pedagogie import _grille, _page
from idara.ui.saisie import cellule, message, tableau


def _ouvrir(page, p: Path) -> Path:
    message(page.message, f"وُلّدت الوثيقة: {p.name}")
    try:
        bureautique.ouvrir(p)
    except Exception:  # noqa: BLE001 — الفتح اختياري
        pass
    return p


def _f(x) -> str:
    return "" if x is None else f"{x:.2f}"


# ======================================================================
class PageDeliberations(QWidget):
    """قرار ومحضر مجلس القسم لكل قسم، ومحضر نتائج المستوى، للأسدوس الأول والثاني."""

    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        racine, self.message = _page("محاضر نهاية الأسدوس",
                                     "من نتائج مسار المستوردة في «المحاضر: مجالس الأقسام»: قرار ومحضر مجلس القسم لكل "
                                     "قسم، ومحضر نتائج المستوى. الميزة على 10: تنويه 8 فما فوق، تشجيع 7، لوحة الشرف 6. "
                                     "السادس في الدورة الثانية: 50% المراقبة المستمرة + 25% المحلي + 25% الإقليمي.")
        self.setLayout(racine)
        c, v = carte()
        self.annee, self.periode, self.classe, self.niveau = QComboBox(), QComboBox(), QComboBox(), QComboBox()
        for k, lib in dl.PERIODES.items():
            self.periode.addItem(lib, k)
        self.annee.currentIndexChanged.connect(lambda _: self._classes())
        self.periode.currentIndexChanged.connect(lambda _: self.charger())
        self.classe.currentIndexChanged.connect(lambda _: self.charger())
        v.addLayout(_grille([("السنة الدراسية", self.annee), ("الدورة", self.periode), ("القسم", self.classe)]))
        racine.addWidget(c)

        c, v = carte("قرار مجلس القسم")
        aide = QLabel("الإنذار والتوبيخ والتوجيه يقررها المجلس: اختر أو اكتب ثم «حفظ قرارات المجلس».")
        aide.setObjectName("sousTitre")
        aide.setWordWrap(True)
        v.addWidget(aide)
        self.table = tableau(["الاسم", "الرمز", "المعدل", "الميزة", "الرتبة", "القرار", "إنذار/توبيخ", "التوجيه"],
                             etirer=7)
        self.table.setMinimumHeight(360)
        v.addWidget(self.table)
        h = QHBoxLayout()
        for lib, fn, principal in (("حفظ قرارات المجلس", lambda: self.enregistrer(), False),
                                   ("قرار ومحضر مجلس القسم (Word)", lambda: self.generer_classe(), True)):
            b = QPushButton(lib)
            if principal:
                b.setObjectName("principal")
            b.clicked.connect(fn)
            h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        racine.addWidget(c)

        c, v = carte("محضر نتائج المستوى")
        for k, o in ev.ORDINAUX.items():
            self.niveau.addItem(o, k)
        b = QPushButton("محضر نتائج المستوى (Word)")
        b.clicked.connect(lambda: self.generer_niveau())
        v.addLayout(_grille([("المستوى", self.niveau)]))
        v.addWidget(b)
        racine.addWidget(c)
        racine.addStretch()

    def rafraichir(self) -> None:
        a = self.annee.currentText()
        self.annee.blockSignals(True)
        self.annee.clear()
        self.annee.addItems(ev.annees_disponibles(self.f.conn))
        i = self.annee.findText(a)
        self.annee.setCurrentIndex(i if i >= 0 else 0)
        self.annee.blockSignals(False)
        self._classes()

    def _classes(self) -> None:
        c = self.classe.currentText()
        self.classe.blockSignals(True)
        self.classe.clear()
        if self.annee.currentText():
            for cl, _ in dl.classes(self.f.conn, self.annee.currentText()):
                self.classe.addItem(cl)
        i = self.classe.findText(c)
        self.classe.setCurrentIndex(i if i >= 0 else 0)
        self.classe.blockSignals(False)
        self.charger()

    def charger(self) -> None:
        self.table.setRowCount(0)
        if not self.annee.currentText() or not self.classe.currentText():
            message(self.message, "استورد أولاً نتائج مسار في «المحاضر: مجالس الأقسام».", True)
            return
        self.message.hide()
        ls = dl.lignes(self.f.conn, self.annee.currentText(), self.periode.currentData(), classe=self.classe.currentText())
        self.table.setRowCount(len(ls))
        self.table.setEditTriggers(QAbstractItemView.AllEditTriggers)
        for i, l in enumerate(ls):
            for j, v in enumerate((l["nom"], l["code"], _f(l["note"]), l["mention"], str(l["rang"] or ""), l["decision"])):
                it = cellule(v, l["code"] if j == 0 else None)
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(i, j, it)
            cb = QComboBox()
            cb.addItem("—", "")
            for s in dl.SANCTIONS:
                cb.addItem(s, s)
            cb.setCurrentIndex(max(0, cb.findData(l["sanction"])))
            self.table.setCellWidget(i, 6, cb)
            self.table.setItem(i, 7, QTableWidgetItem(l["orientation"]))

    def enregistrer(self) -> bool:
        try:
            for i in range(self.table.rowCount()):
                code = self.table.item(i, 0).data(Qt.UserRole)
                orient = self.table.item(i, 7).text() if self.table.item(i, 7) else ""
                dl.enregistrer_deliberation(self.f.conn, self.annee.currentText(), self.periode.currentData(), code,
                                            self.table.cellWidget(i, 6).currentData(), orient)
        except ev.ErreurEvaluation as e:
            message(self.message, str(e), True)
            return False
        message(self.message, "حُفظت قرارات المجلس.")
        return True

    def generer_classe(self) -> Path | None:
        if not self.enregistrer():
            return None
        try:
            p = dl.generer_classe(self.f.conn, self.f.dossier, self.annee.currentText(), self.classe.currentText(),
                                  self.periode.currentData())
        except ev.ErreurEvaluation as e:
            message(self.message, str(e), True)
            return None
        return _ouvrir(self, p)

    def generer_niveau(self) -> Path | None:
        try:
            p = dl.generer_niveau(self.f.conn, self.f.dossier, self.annee.currentText(), self.niveau.currentData(),
                                  self.periode.currentData())
        except ev.ErreurEvaluation as e:
            message(self.message, str(e), True)
            return None
        return _ouvrir(self, p)


# ======================================================================
class PageExamen(QWidget):
    """الامتحان الموحد المحلي (تلاميذ السادس) والإقليمي (لائحة المديرية بأرقامها)."""

    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        self.eid: int | None = None
        racine, self.message = _page("الامتحان الموحد",
                                     "المحلي: المترشحون تلاميذ السادس من لوائح مسار، يُرقَّمون من الرقم الأول المختار. "
                                     "الإقليمي: لائحة المديرية بأرقامها وقاعاتها كما هي. ثم الجدولة، والمكلفون، "
                                     "وتوزيع المراقبين، والوثائق.")
        self.setLayout(racine)

        # ---- الامتحان ----
        c, v = carte("الامتحان")
        self.type = QComboBox()
        for k, lib in exs.TYPES.items():
            self.type.addItem(lib, k)
        self.type.currentIndexChanged.connect(lambda _: self.charger())
        self.intitule, self.session, self.centre, self.code_centre = champ(), champ("يونيو 2027"), champ(), champ(ltr=True)
        self.premier, self.capacite = QSpinBox(), QSpinBox()
        self.premier.setRange(1, 999999)
        self.capacite.setRange(1, 60)
        v.addLayout(_grille([("النوع", self.type), ("الدورة", self.session), ("مركز الامتحان", self.centre),
                             ("رمز المركز", self.code_centre)]))
        v.addLayout(_grille([("اسم الامتحان", self.intitule)], etirer=0))
        v.addLayout(_grille([("الرقم الأول (المحلي)", self.premier), ("عدد المترشحين في القاعة", self.capacite)]))
        b = QPushButton("حفظ معطيات الامتحان")
        b.clicked.connect(lambda: self.enregistrer())
        v.addWidget(b)
        racine.addWidget(c)

        # ---- المترشحون ----
        c, v = carte("المترشحون والقاعات")
        h = QHBoxLayout()
        self.b_local = QPushButton("تحضير اللائحة من تلاميذ السادس")
        self.b_local.clicked.connect(lambda: self.preparer_local())
        self.b_prov = QPushButton("استيراد لائحة المديرية الإقليمية...")
        self.b_prov.clicked.connect(lambda: self.importer_provincial())
        for b in (self.b_local, self.b_prov):
            b.setObjectName("principal")
            h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        self.l_cands = QLabel()
        self.l_cands.setObjectName("sousTitre")
        self.l_cands.setWordWrap(True)
        v.addWidget(self.l_cands)
        aide_c = QLabel("المنقطعون والمفصولون والمغادرون مستبعدون آلياً. قبل توليد الوثائق احذف كل تلميذ انقطع "
                        "ولم يُسجَّل انقطاعه في البرنامج (زر الحذف أمامه): يُعاد ترقيم الباقين وتوزيعهم على القاعات.")
        aide_c.setObjectName("etiquette")
        aide_c.setWordWrap(True)
        v.addWidget(aide_c)
        self.cands = tableau(["رقم الامتحان", "الاسم الكامل", "الرمز", "القاعة", "القسم", ""], etirer=1)
        self.cands.setMinimumHeight(240)
        v.addWidget(self.cands)
        racine.addWidget(c)

        # ---- الجدولة ----
        c, v = carte("جدولة المواد")
        aide = QLabel("سطر لكل مادة: التاريخ بصيغة 10/06/2027 والساعة بصيغة 08:30.")
        aide.setObjectName("sousTitre")
        v.addWidget(aide)
        self.mats = tableau(["المادة", "التاريخ", "من", "إلى"], etirer=0)
        self.mats.setEditTriggers(QAbstractItemView.AllEditTriggers)
        self.mats.setMinimumHeight(220)
        v.addWidget(self.mats)
        h = QHBoxLayout()
        for lib, fn in (("سطر إضافي", lambda: self._ligne_matiere()), ("حفظ الجدولة", lambda: self.enregistrer_matieres())):
            b = QPushButton(lib)
            b.clicked.connect(fn)
            h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        racine.addWidget(c)

        # ---- المكلفون ----
        c, v = carte("المكلفون بالمهام")
        self.c_roles = {r: [QComboBox() for _ in range(3 if r == exs.ROLES[2] else 1)] for r in exs.ROLES[:3]}
        v.addLayout(_grille([(exs.ROLES[0], self.c_roles[exs.ROLES[0]][0]),
                             (exs.ROLES[1], self.c_roles[exs.ROLES[1]][0])]))
        v.addLayout(_grille([(f"{exs.ROLES[2]} {k + 1}", w) for k, w in enumerate(self.c_roles[exs.ROLES[2]])]))
        self.mudawim = tableau(["المادة", "الأستاذ(ة) المداوم(ة)"], etirer=1)
        self.mudawim.setMinimumHeight(160)
        v.addWidget(self.mudawim)
        b = QPushButton("حفظ المكلفين")
        b.clicked.connect(lambda: self.enregistrer_roles())
        v.addWidget(b)
        racine.addWidget(c)

        # ---- المراقبة ----
        c, v = carte("توزيع المراقبين على القاعات")
        self.par_salle = QSpinBox()
        self.par_salle.setRange(1, 4)
        self.par_salle.setValue(2)
        v.addLayout(_grille([("عدد المراقبين في كل قاعة", self.par_salle)]))
        aide = QLabel("رقم القاعة لكل أستاذ في كل مادة (فارغ: لا مراقبة). «توزيع آلي» يوزع بالتناوب دون المكلفين بالمهام "
                      "العامة، ثم يمكن التعديل والحفظ.")
        aide.setObjectName("sousTitre")
        aide.setWordWrap(True)
        v.addWidget(aide)
        self.surv = tableau(["الأستاذ(ة)"], etirer=0)
        self.surv.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)   # مواد كثيرة: تمرير داخل الجدول لا الصفحة
        self.surv.setEditTriggers(QAbstractItemView.AllEditTriggers)
        self.surv.setMinimumHeight(240)
        v.addWidget(self.surv)
        h = QHBoxLayout()
        for lib, fn in (("توزيع آلي", lambda: self.distribuer()), ("حفظ التوزيع", lambda: self.enregistrer_surveillance())):
            b = QPushButton(lib)
            b.clicked.connect(fn)
            h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        racine.addWidget(c)

        # ---- الوثائق ----
        c, v = carte("الوثائق")
        self.l_manquants = QLabel()
        self.l_manquants.setObjectName("alerte")
        self.l_manquants.setWordWrap(True)
        v.addWidget(self.l_manquants)
        groupes = {1: "المترشحون", 2: "المكلفون", 3: "الإعلان والتنقيط", 4: "المحاضر والتقارير"}
        self.boutons_docs = {}
        for g, lib in groupes.items():
            t = QLabel(lib)
            t.setObjectName("etiquette")
            v.addWidget(t)
            grille = QGridLayout()   # ثلاثة أزرار في كل سطر حتى لا تتجاوز الصفحة عرضها
            grille.setHorizontalSpacing(8)
            k = 0
            for code, (nom, gg) in de.DOCUMENTS.items():
                if gg != g:
                    continue
                b = QPushButton(nom)
                b.clicked.connect(lambda _=False, code=code: self.generer(code))
                self.boutons_docs[code] = b
                grille.addWidget(b, k // 3, k % 3)
                k += 1
            v.addLayout(grille)
        racine.addWidget(c)
        racine.addStretch()

    # ---------- التحميل ----------

    def rafraichir(self) -> None:
        self.charger()

    def charger(self) -> None:
        try:
            ex = exs.examen(self.f.conn, self.type.currentData())
        except exs.ErreurExamen as e:
            message(self.message, str(e), True)
            return
        self.eid = ex["id"]
        local = ex["type"] == "local"
        self.intitule.setText(ex["intitule"])
        self.session.setText(ex["session"] or "")
        self.centre.setText(ex["centre"] or "")
        self.code_centre.setText(ex["code_centre"] or "")
        self.premier.setValue(ex["premier_numero"])
        self.capacite.setValue(ex["capacite"])
        self.premier.setEnabled(local)
        self.b_local.setVisible(local)
        self.b_prov.setVisible(not local)
        cs = exs.candidats(self.f.conn, self.eid)
        self.cands.setRowCount(len(cs))
        for i, c in enumerate(cs):
            for j, v in enumerate((str(c["numero"]), c["nom"], c["code_massar"] or "", c["salle_nom"] or "",
                                   c["classe"] or "")):
                self.cands.setItem(i, j, cellule(v, c["id"] if j == 0 else None))
            b = bouton("حذف")
            b.setToolTip(f"حذف {c['nom']} من لائحة المترشحين")
            b.clicked.connect(lambda _=False, cid=c["id"], nom=c["nom"]: self.supprimer_candidat(cid, nom))
            self.cands.setCellWidget(i, 5, b)
        ss = exs.salles(self.f.conn, self.eid)
        self.l_cands.setText(f"{len(cs)} مترشحاً" + (f"، الأرقام {cs[0]['numero']}–{cs[-1]['numero']}" if cs else "")
                             + (" · " + "، ".join(f"{s['nom']}: {s['n']}" for s in ss) if ss else ""))
        self._charger_matieres()
        self._charger_roles()
        self._charger_surveillance()
        m = exs.manquants(self.f.conn, self.eid)
        self.l_manquants.setText("قبل الوثائق: " + "، ".join(m) if m else "")
        self.l_manquants.setVisible(bool(m))

    def _ligne_matiere(self, valeurs=("", "", "", ""), mid=None) -> None:
        i = self.mats.rowCount()
        self.mats.setRowCount(i + 1)
        for j, v in enumerate(valeurs):
            self.mats.setItem(i, j, cellule(v, mid if j == 0 else None))
        cb = QComboBox()
        cb.setEditable(True)
        cb.addItems(exs.MATIERES_SUGGEREES)
        cb.setEditText(valeurs[0])
        self.mats.setCellWidget(i, 0, cb)

    def _charger_matieres(self) -> None:
        self.mats.setRowCount(0)
        for m in exs.matieres(self.f.conn, self.eid):
            self._ligne_matiere((m["matiere"], tx.date_chiffres(m["jour"]), m["debut"], m["fin"]), m["id"])
        if not self.mats.rowCount():
            for _ in range(3):
                self._ligne_matiere()

    def _personnes(self, cb: QComboBox, choix) -> None:
        cb.clear()
        cb.addItem("—", None)
        for p in exs.enseignants(self.f.conn):
            cb.addItem(f"{p['prenom_ar']} {p['nom_ar']}", p["id"])
        cb.setCurrentIndex(max(0, cb.findData(choix)))

    def _charger_roles(self) -> None:
        aff = exs.affectations(self.f.conn, self.eid)
        for role, cbs in self.c_roles.items():
            ids = [a["personnel_id"] for a in aff if a["role"] == role]
            for k, cb in enumerate(cbs):
                self._personnes(cb, ids[k] if k < len(ids) else None)
        ms = exs.matieres(self.f.conn, self.eid)
        self.mudawim.setRowCount(len(ms))
        for i, m in enumerate(ms):
            self.mudawim.setItem(i, 0, cellule(f"{m['matiere']} · {tx.date_chiffres(m['jour'])}", m["id"]))
            cb = QComboBox()
            self._personnes(cb, next((a["personnel_id"] for a in aff if a["role"] == exs.ROLES[3]
                                      and a["matiere_id"] == m["id"]), None))
            self.mudawim.setCellWidget(i, 1, cb)

    def _charger_surveillance(self) -> None:
        ms = exs.matieres(self.f.conn, self.eid)
        profs = [p for p in exs.enseignants(self.f.conn) if p["categorie"] != "directeur"]
        cases = exs.surveillance(self.f.conn, self.eid)
        self.surv.setColumnCount(1 + len(ms))
        self.surv.setHorizontalHeaderLabels(["الأستاذ(ة)"] + [f"{m['matiere']}\n{tx.date_chiffres(m['jour'])}" for m in ms])
        self.surv.setRowCount(len(profs))
        self._ms = [m["id"] for m in ms]
        for i, p in enumerate(profs):
            it = cellule(f"{p['prenom_ar']} {p['nom_ar']}", p["id"])
            it.setFlags(it.flags() & ~Qt.ItemIsEditable)
            self.surv.setItem(i, 0, it)
            for j, mid in enumerate(self._ms, start=1):
                n = cases.get((p["id"], mid))
                self.surv.setItem(i, j, QTableWidgetItem("" if n is None else str(n)))

    # ---------- الأفعال ----------

    def _faire(self, fn, succes: str):
        try:
            r = fn()
        except (exs.ErreurExamen, ValueError) as e:
            message(self.message, str(e) or "قيمة غير صحيحة.", True)
            return None
        self.charger()
        if succes:
            message(self.message, succes if isinstance(succes, str) else succes(r))
        return True if r is None else r

    def enregistrer(self):
        return self._faire(lambda: exs.modifier(self.f.conn, self.eid, self.intitule.text(), self.session.text(),
                                                self.centre.text(), self.code_centre.text(), self.premier.value(),
                                                self.capacite.value()), "حُفظت معطيات الامتحان.")

    def preparer_local(self):
        if not self.enregistrer():
            return None
        return self._faire(lambda: exs.preparer_local(self.f.conn, self.eid),
                           "حُضّرت لائحة المترشحين من تلاميذ السادس.")

    def supprimer_candidat(self, cid: int, nom: str = ""):
        return self._faire(lambda: exs.supprimer_candidat(self.f.conn, self.eid, cid),
                           f"حُذف {nom} من لائحة المترشحين." if nom else "حُذف المترشح.")

    def importer_provincial(self, chemin: Path | None = None):
        if not self.enregistrer():
            return None
        if chemin is None:
            f, _ = QFileDialog.getOpenFileName(self, "لائحة المديرية الإقليمية", str(Path.home()), "Excel (*.xlsx *.xlsm)")
            if not f:
                return None
            chemin = Path(f)

        def apres(r: exs.RapportListe) -> str:
            t = f"استوردت {r.n} مترشحاً في {r.salles} قاعة بأرقام المديرية."
            if r.hors_lister:
                t += f" {len(r.hors_lister)} منهم غير موجودين في لوائح المؤسسة (يبقون في اللائحة)."
            return t + (" " + " ".join(r.alertes) if r.alertes else "")
        return self._faire(lambda: exs.importer_provincial(self.f.conn, self.eid, chemin), apres)

    def enregistrer_matieres(self):
        def lire():
            lignes = []
            for i in range(self.mats.rowCount()):
                cb = self.mats.cellWidget(i, 0)
                v = [self.mats.item(i, j).text().strip() if self.mats.item(i, j) else "" for j in range(1, 4)]
                jour = ""
                if v[0]:
                    try:
                        j_, m_, a_ = (int(x) for x in v[0].split("/"))
                        jour = date(a_, m_, j_).isoformat()
                    except ValueError:
                        raise exs.ErreurExamen(f"تاريخ غير صحيح: {v[0]} (الصيغة 10/06/2027).") from None
                lignes.append({"matiere": cb.currentText(), "jour": jour, "debut": v[1], "fin": v[2],
                               "id": self.mats.item(i, 0).data(Qt.UserRole) if self.mats.item(i, 0) else None})
            exs.definir_matieres(self.f.conn, self.eid, lignes)
        return self._faire(lire, "حُفظت الجدولة.")

    def enregistrer_roles(self):
        roles = {r: [cb.currentData() for cb in cbs if cb.currentData()] for r, cbs in self.c_roles.items()}
        mud = {self.mudawim.item(i, 0).data(Qt.UserRole): self.mudawim.cellWidget(i, 1).currentData()
               for i in range(self.mudawim.rowCount())}
        return self._faire(lambda: exs.definir_roles(self.f.conn, self.eid, roles, mud), "حُفظ المكلفون.")

    def distribuer(self):
        return self._faire(lambda: exs.distribuer(self.f.conn, self.eid, self.par_salle.value()),
                           "وُزّع المراقبون على القاعات. راجع التوزيع ثم ولّد الوثائق.")

    def enregistrer_surveillance(self):
        def lire():
            cases = {}
            for i in range(self.surv.rowCount()):
                pid = self.surv.item(i, 0).data(Qt.UserRole)
                for j, mid in enumerate(self._ms, start=1):
                    t = self.surv.item(i, j).text().strip() if self.surv.item(i, j) else ""
                    if t:
                        if not t.isdigit():
                            raise exs.ErreurExamen(f"رقم القاعة غير صحيح: «{t}».")
                        cases[(pid, mid)] = int(t)
            exs.definir_surveillance(self.f.conn, self.eid, cases)
        return self._faire(lire, "حُفظ توزيع المراقبين.")

    def generer(self, code: str) -> Path | None:
        try:
            p = de.generer(self.f.conn, self.f.dossier, self.eid, code)
        except exs.ErreurExamen as e:
            message(self.message, str(e), True)
            return None
        return _ouvrir(self, p)
