"""مجالس المؤسسة (المرسوم 2.02.376): التركيبة، الاجتماعات والنصاب، المحاضر والاستدعاءات، وتتبع الحد الأدنى."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QHBoxLayout, QHeaderView, QLabel,
                               QListWidget, QListWidgetItem, QPlainTextEdit, QPushButton, QTableWidget, QWidget)

from idara.services import bureautique
from idara.services import conseils_etab as ce
from idara.ui.composants import bouton, carte
from idara.ui.formulaires import champ, etiquette
from idara.ui.page_pedagogie import _grille, _page
from idara.ui.saisie import ChampDate, cellule, message, tableau


def _texte(w: QPlainTextEdit) -> list[str]:
    return [l.strip() for l in w.toPlainText().splitlines() if l.strip()]


class PageConseilsEtab(QWidget):
    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        self.sid: int | None = None
        racine, self.message = _page("مجالس المؤسسة",
                                     "مجلس التدبير والمجلس التربوي والمجالس التعليمية حسب المرسوم 2.02.376 (المواد 17-31): "
                                     "التركيبة، الاجتماعات (مرتان على الأقل في السنة)، نصاب مجلس التدبير، المحاضر "
                                     "والاستدعاءات. مجالس الأقسام في قسم التقييم.")
        self.setLayout(racine)

        c, v = carte("تتبع اجتماعات السنة")
        self.suivi = tableau(["المجلس", "الاجتماعات", "الحد الأدنى", "آخر اجتماع", "تنبيهات"], etirer=4)
        self.suivi.setMinimumHeight(150)
        self.suivi.setWordWrap(True)
        v.addWidget(self.suivi)
        racine.addWidget(c)

        self.conseil = QComboBox()
        for k, lib in ce.CONSEILS.items():
            self.conseil.addItem(lib, k)
        self.conseil.currentIndexChanged.connect(lambda _: self.charger())
        c, v = carte()
        v.addLayout(_grille([("المجلس", self.conseil)]))
        racine.addWidget(c)

        # ---- التركيبة ----
        c, v = carte("التركيبة")
        self.l_ecarts = QLabel()
        self.l_ecarts.setObjectName("erreur")
        self.l_ecarts.setWordWrap(True)
        v.addWidget(self.l_ecarts)
        self.membres = QTableWidget(0, 3)
        self.membres.setHorizontalHeaderLabels(["الاسم", "الصفة", "المادة"])
        self.membres.verticalHeader().setVisible(False)
        self.membres.setEditTriggers(QAbstractItemView.AllEditTriggers)
        self.membres.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.membres.setMinimumHeight(330)
        self.c_optionnels = QCheckBox("إضافة الأعضاء الاختياريين: ممثل الأطر الإدارية والتقنية، رئيس جمعية آباء "
                                      "وأولياء التلاميذ، ممثل المجلس الجماعي")
        self.c_optionnels.toggled.connect(lambda c: self._basculer_optionnels(c))
        v.addWidget(self.c_optionnels)
        v.addWidget(self.membres)
        h = QHBoxLayout()
        for lib, fn in (("تركيبة مقترحة (المرسوم ومعطيات التطبيق)", lambda: self.proposer()),
                        ("سطر إضافي", lambda: self.membres.setRowCount(self.membres.rowCount() + 1)),
                        ("حفظ التركيبة", lambda: self.enregistrer_membres())):
            b = bouton(lib)
            b.clicked.connect(fn)
            h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        racine.addWidget(c)

        # ---- الاجتماعات ----
        c, v = carte("الاجتماعات والمحاضر")
        self.seances = tableau(["رقم", "التاريخ", "جدول الأعمال"], etirer=2)
        self.seances.setMinimumHeight(170)
        self.seances.itemSelectionChanged.connect(self._sel)
        v.addWidget(self.seances)
        self.date, self.heure = ChampDate(), champ("10:00", ltr=True)
        self.heure.setMaximumWidth(90)
        self.nature, self.convoc = QComboBox(), QComboBox()
        self.nature.addItem("اجتماع عادي", "ordinaire")
        self.nature.addItem("اجتماع استثنائي", "extraordinaire")
        self.convoc.addItem("الاستدعاء الأول", "premiere")
        self.convoc.addItem("الاستدعاء الثاني (النصاب بالحاضرين)", "seconde")
        v.addLayout(_grille([("التاريخ", self.date), ("الساعة", self.heure), ("نوع الاجتماع", self.nature),
                             ("الاستدعاء", self.convoc)]))
        self.suggestion = QComboBox()
        self.suggestion.setEditable(False)
        b = QPushButton("إضافة إلى جدول الأعمال")
        b.clicked.connect(lambda: self._ajouter_point())
        h = QHBoxLayout()
        h.addWidget(self.suggestion, 1)
        h.addWidget(b)
        v.addWidget(etiquette("نقط مقترحة (مهام المجلس في المرسوم ومحاضركم)", self.suggestion))
        v.addLayout(h)
        self.odj = QPlainTextEdit()
        self.odj.setPlaceholderText("جدول الأعمال: نقطة في كل سطر")
        self.odj.setFixedHeight(90)
        v.addWidget(self.odj)
        self.delib = QPlainTextEdit()
        self.delib.setPlaceholderText("المداولات (اختياري: تُترك أسطر فارغة في المحضر للكتابة باليد)")
        self.delib.setFixedHeight(120)
        v.addWidget(self.delib)
        self.decisions = QPlainTextEdit()
        self.decisions.setPlaceholderText("القرارات والتوصيات: واحدة في كل سطر (اختياري)")
        self.decisions.setFixedHeight(80)
        v.addWidget(self.decisions)
        t = QLabel("الحضور (أزل العلامة عن المتغيبين)")
        t.setObjectName("titreCarte")
        v.addWidget(t)
        self.presence = QListWidget()
        self.presence.setMinimumHeight(170)
        v.addWidget(self.presence)
        h = QHBoxLayout()
        self.c_res = QCheckBox("إدراج جدول نتائج المتعلمين (المحصلة النهائية)")
        self.c_isa = QCheckBox("إدراج تطور مؤشر ISA2")
        h.addWidget(self.c_res)
        h.addWidget(self.c_isa)
        h.addStretch()
        v.addLayout(h)
        h = QHBoxLayout()
        for lib, fn, p in (("تسجيل اجتماع جديد", lambda: self.enregistrer(True), False),
                           ("حفظ التعديل", lambda: self.enregistrer(False), False),
                           ("حذف الاجتماع", lambda: self.supprimer(), False),
                           ("المحضر (Word)", lambda: self.pv(), True),
                           ("استدعاء الأعضاء (Word)", lambda: self.convocation(), True)):
            b = bouton(lib)
            if p:
                b.setObjectName("principal")
            b.clicked.connect(fn)
            h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        racine.addWidget(c)
        racine.addStretch()
        self.rafraichir()

    # ---------- التحميل ----------

    def rafraichir(self) -> None:
        try:
            s = ce.suivi(self.f.conn)
        except ce.ErreurConseil as e:
            message(self.message, str(e), True)
            return
        self.suivi.setRowCount(len(s))
        for i, x in enumerate(s):
            from idara.services import textes as tx
            for j, v in enumerate((x["libelle"], str(x["nombre"]), str(x["minimum"]),
                                   tx.date_chiffres(x["derniere"]) if x["derniere"] else "—",
                                   "؛ ".join(x["alertes"]) or "—")):
                self.suivi.setItem(i, j, cellule(v))
        self.suivi.resizeRowsToContents()
        self.charger()

    def charger(self) -> None:
        cs = self.conseil.currentData()
        ms = ce.membres_actifs(self.f.conn, cs)
        self._remplir_membres([(m["nom"], m["qualite"], m["groupe"] or "") for m in ms])
        opt = ce.optionnels(cs)
        self.c_optionnels.setVisible(bool(opt))
        self.c_optionnels.blockSignals(True)
        self.c_optionnels.setChecked(any(m["qualite"] in opt for m in ms))
        self.c_optionnels.blockSignals(False)
        ec = ce.ecarts_decret(self.f.conn, cs) if ms else []
        self.l_ecarts.setText("مقاعد ينص عليها المرسوم وغير مسجلة: " + "، ".join(ec) if ec else "")
        self.l_ecarts.setVisible(bool(ec))
        self.suggestion.clear()
        self.suggestion.addItems(ce.SUGGESTIONS[cs])
        ss = ce.seances(self.f.conn, cs)
        self.seances.setRowCount(len(ss))
        from idara.services import textes as tx
        import json
        for i, s in enumerate(ss):
            for j, v in enumerate((str(s["numero"]), tx.date_chiffres(s["date_seance"]),
                                   "؛ ".join(json.loads(s["ordre_du_jour"])))):
                self.seances.setItem(i, j, cellule(v, s["id"] if j == 0 else None))
        self.sid = None
        self._formulaire(None)

    def _remplir_membres(self, lignes) -> None:
        self.membres.setColumnHidden(2, self.conseil.currentData() != "enseignement")
        self.membres.setRowCount(max(len(lignes) + 1, 4))
        self.membres.clearContents()
        for i, l in enumerate(lignes):
            for j, v in enumerate(l):
                self.membres.setItem(i, j, cellule(v))

    def _formulaire(self, s: ce.Seance | None) -> None:
        self.date.definir(s.date_seance if s else date.today().isoformat())
        self.heure.setText(s.heure if s and s.heure else "10:00")
        self.nature.setCurrentIndex(max(0, self.nature.findData(s.nature if s else "ordinaire")))
        self.convoc.setCurrentIndex(max(0, self.convoc.findData(s.convocation if s else "premiere")))
        self.odj.setPlainText("\n".join(s.ordre_du_jour) if s else "")
        self.delib.setPlainText(s.deliberations if s else "")
        self.decisions.setPlainText("\n".join(s.decisions) if s else "")
        self.c_res.setChecked(bool(s and s.inclure_resultats))
        self.c_isa.setChecked(bool(s and s.inclure_isa))
        self.presence.clear()
        presents = set(s.presents) if s and s.presents is not None else None
        for m in ce.membres_actifs(self.f.conn, self.conseil.currentData()):
            it = QListWidgetItem(f"{m['nom']} — {m['qualite']}" + (f" ({m['groupe']})" if m["groupe"] else ""))
            it.setData(Qt.UserRole, m["id"])
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if presents is None or m["id"] in presents else Qt.Unchecked)
            self.presence.addItem(it)

    def _sel(self) -> None:
        rows = {i.row() for i in self.seances.selectedIndexes()}
        if len(rows) == 1:
            self.sid = self.seances.item(rows.pop(), 0).data(Qt.UserRole)
            self._formulaire(ce.seance(self.f.conn, self.sid))

    # ---------- الأفعال ----------

    def _faire(self, fn, succes: str, recharger=True):
        try:
            r = fn()
        except (ce.ErreurConseil, ValueError) as e:
            message(self.message, str(e) or "قيمة غير صحيحة.", True)
            return None
        if recharger:
            self.rafraichir()
        if succes:
            message(self.message, succes)
        return True if r is None else r

    def _lignes(self) -> list[tuple[str, str, str]]:
        return [tuple((self.membres.item(i, j).text() if self.membres.item(i, j) else "") for j in range(3))
                for i in range(self.membres.rowCount())]

    def _basculer_optionnels(self, coche: bool) -> None:
        """يضيف أسطر الأعضاء الاختياريين إلى التركيبة المعروضة أو يحذفها (ثم «حفظ التركيبة»)."""
        opt = ce.optionnels(self.conseil.currentData())
        lignes = [l for l in self._lignes() if any(l) and l[1] not in opt]
        if coche:
            lignes += [("", q, "") for q in opt]
        self._remplir_membres(lignes)

    def proposer(self) -> None:
        self._remplir_membres(ce.proposition(self.f.conn, self.conseil.currentData(),
                                             self.c_optionnels.isChecked()))
        message(self.message, "تركيبة مقترحة: أكمل الأسماء الناقصة ثم احفظ.")

    def enregistrer_membres(self):
        lignes = self._lignes()
        return self._faire(lambda: ce.enregistrer_membres(self.f.conn, self.conseil.currentData(), lignes),
                           "حُفظت التركيبة.")

    def _ajouter_point(self) -> None:
        t = self.odj.toPlainText().rstrip()
        self.odj.setPlainText((t + "\n" if t else "") + self.suggestion.currentText())

    def _seance(self, nouveau: bool) -> ce.Seance:
        try:
            d = self.date.iso()
        except ValueError:
            raise ce.ErreurConseil("تاريخ الاجتماع غير صحيح.") from None
        presents = [self.presence.item(i).data(Qt.UserRole) for i in range(self.presence.count())
                    if self.presence.item(i).checkState() == Qt.Checked]
        return ce.Seance(self.conseil.currentData(), d, _texte(self.odj), self.heure.text(), self.nature.currentData(),
                         self.convoc.currentData(), self.delib.toPlainText(), _texte(self.decisions), presents,
                         self.c_res.isChecked(), self.c_isa.isChecked(), None if nouveau else self.sid)

    def enregistrer(self, nouveau: bool):
        if not nouveau and not self.sid:
            message(self.message, "حدد اجتماعاً في الجدول.", True)
            return None
        return self._faire(lambda: ce.enregistrer_seance(self.f.conn, self._seance(nouveau)), "سُجل الاجتماع.")

    def supprimer(self):
        if not self.sid:
            return None
        return self._faire(lambda: ce.supprimer_seance(self.f.conn, self.sid), "حُذف الاجتماع.")

    def _ouvrir(self, p: Path) -> Path:
        message(self.message, f"وُلّدت الوثيقة: {p.name}")
        try:
            bureautique.ouvrir(p)
        except Exception:  # noqa: BLE001 — الفتح اختياري
            pass
        return p

    def pv(self):
        if not self.sid:
            message(self.message, "حدد اجتماعاً مسجلاً في الجدول.", True)
            return None
        r = self._faire(lambda: ce.generer_pv(self.f.conn, self.f.dossier, self.sid), "", recharger=False)
        return self._ouvrir(r) if r else None

    def convocation(self):
        def fn():
            try:
                d = self.date.iso()
            except ValueError:
                raise ce.ErreurConseil("تاريخ الاجتماع غير صحيح.") from None
            return ce.generer_convocation(self.f.conn, self.f.dossier, self.conseil.currentData(), d,
                                          self.heure.text(), _texte(self.odj))
        r = self._faire(fn, "", recharger=False)
        return self._ouvrir(r) if r else None
