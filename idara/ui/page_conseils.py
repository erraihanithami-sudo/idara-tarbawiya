"""صفحة مجالس الأقسام: نتائج مسار، إحصاء الحاصلين على المعدل، المحاضر."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QFileDialog, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPlainTextEdit, QPushButton, QVBoxLayout, QWidget)

from idara.services import bureautique
from idara.services import documents as dc
from idara.services import evaluation as ev
from idara.ui.composants import carte, entete
from idara.ui.formulaires import etiquette
from idara.ui.saisie import ChampDate, cellule, message, tableau


class PageConseils(QWidget):
    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        self.chargement = False
        racine = QVBoxLayout(self)
        racine.setContentsMargins(40, 32, 40, 32)
        racine.setSpacing(16)
        racine.addWidget(entete(
            "مجالس الأقسام",
            "استورد «مجمل المعدلات السنوية» من مسار: يُحسب المعدل السنوي (متوسط المواد) وعدد الحاصلين على المعدل "
            "(5/10 فما فوق) لكل قسم، وتُولد المحاضر من نماذجكم بتوقيعات أساتذة كل مستوى."))
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.hide()
        racine.addWidget(self.message)

        c, v = carte()
        h = QHBoxLayout()
        b = QPushButton("استيراد نتائج مسار...")
        b.setObjectName("principal")
        b.clicked.connect(self.choisir_fichiers)
        h.addWidget(b)
        h.addWidget(etiquette("السنة الدراسية"))
        self.annee = QComboBox()
        self.annee.currentIndexChanged.connect(lambda _: self.charger())
        h.addWidget(self.annee)
        h.addWidget(etiquette("المستوى"))
        self.niveau = QComboBox()
        self.niveau.currentIndexChanged.connect(lambda _: self.charger_niveau())
        h.addWidget(self.niveau)
        h.addStretch()
        v.addLayout(h)
        self.verif = QLabel()
        self.verif.setObjectName("alerte")
        self.verif.setWordWrap(True)
        v.addWidget(self.verif)
        self.niveaux_manquants = tableau(["التلميذ (قسم مشترك)", "المستوى"], etirer=0)
        self.niveaux_manquants.setMaximumHeight(200)
        v.addWidget(self.niveaux_manquants)
        self.b_niveaux = QPushButton("حفظ المستويات")
        self.b_niveaux.clicked.connect(self.enregistrer_niveaux)
        v.addWidget(self.b_niveaux, 0, Qt.AlignRight)
        racine.addWidget(c)

        c2, v2 = carte("نتائج المستوى")
        self.stats = tableau(["القسم", "ذكور", "إناث", "المجموع", "الحاصلون", "غير الحاصلين", "النسبة"], etirer=0)
        self.stats.setMinimumHeight(200)
        v2.addWidget(self.stats)
        t = QLabel("مؤشر ISA2 لكل قسم (بالمائة، من نتائج المدرسة الرائدة؛ اختياري):")
        t.setObjectName("etiquette")
        v2.addWidget(t)
        self.grille_isa = QGridLayout()
        self.grille_isa.setHorizontalSpacing(10)
        v2.addLayout(self.grille_isa)
        self.isa = {}
        g = QGridLayout()
        g.setHorizontalSpacing(16)
        self.date = ChampDate()
        self.phase = QLineEdit()
        self.phase.setPlaceholderText("الخامسة")
        self.difficultes, self.solutions = QPlainTextEdit(), QPlainTextEdit()
        for w in (self.difficultes, self.solutions):
            w.setMaximumHeight(90)
            w.setPlaceholderText("فارغ: تُترك أسطر للكتابة باليد في المحضر")
        for i, (lib, w) in enumerate((("تاريخ المجلس", self.date), ("مرحلة ISA2", self.phase),
                                      ("الصعوبات والعراقيل", self.difficultes),
                                      ("الحلول المقترحة", self.solutions))):
            g.addWidget(etiquette(lib, w), (i // 2) * 2, i % 2)
            g.addWidget(w, (i // 2) * 2 + 1, i % 2)
        v2.addLayout(g)
        self.membres = QLabel()
        self.membres.setObjectName("etiquette")
        self.membres.setWordWrap(True)
        v2.addWidget(self.membres)
        hb = QHBoxLayout()
        self.b_pv = QPushButton("حفظ وتوليد محضر مجلس القسم")
        self.b_pv.setObjectName("principal")
        self.b_pv.clicked.connect(self.generer_pv)
        hb.addWidget(self.b_pv)
        hb.addStretch()
        self.periode = QComboBox()
        self.periode.addItems(["للأسدوس الثاني", "للأسدوس الأول"])
        hb.addWidget(self.periode)
        self.b_synthese = QPushButton("التقرير التركيبي للمؤسسة")
        self.b_synthese.clicked.connect(self.generer_synthese)
        hb.addWidget(self.b_synthese)
        v2.addLayout(hb)
        racine.addWidget(c2)
        racine.addStretch()
        self.rafraichir()

    # ---------- التحميل ----------

    def rafraichir(self) -> None:
        actuelle = self.annee.currentText()
        self.chargement = True
        self.annee.clear()
        self.annee.addItems(ev.annees_disponibles(self.f.conn))
        if actuelle:
            self.annee.setCurrentText(actuelle)
        self.chargement = False
        self.charger()

    def charger(self) -> None:
        if self.chargement:
            return
        annee = self.annee.currentText()
        vide = not annee
        for w in (self.b_pv, self.b_synthese):
            w.setEnabled(not vide)
        if vide:
            self.verif.setText("لا نتائج مستوردة بعد.")
            self.niveaux_manquants.hide()
            self.b_niveaux.hide()
            self.stats.setRowCount(0)
            return
        av = ev.a_verifier(self.f.conn, annee)
        lignes = []
        if av["moyenne"]:
            lignes.append(f"دون معدل سنوي ({len(av['moyenne'])}): " + "، ".join(av["moyenne"][:8])
                          + (" ..." if len(av["moyenne"]) > 8 else "")
                          + " — السادس يحتاج «المعدل السنوي» من مسار بعد الامتحانات.")
        if av["sexe"]:
            lignes.append(f"غير موجودين في لوائح التلاميذ، فالنوع غير معروف ({len(av['sexe'])}): يُحسبون في المجموع فقط.")
        if av["niveau"]:
            lignes.append(f"تلاميذ أقسام مشتركة بلا مستوى ({len(av['niveau'])}): حدده أسفله.")
        self.verif.setText("\n".join(lignes))
        self.verif.setVisible(bool(lignes))
        self._niveaux_manquants(annee)
        self.chargement = True
        n = self.niveau.currentData()
        self.niveau.clear()
        for code in ev.niveaux(self.f.conn, annee):
            self.niveau.addItem(f"القسم {ev.ORDINAUX[code]}", code)
        if n:
            self.niveau.setCurrentIndex(max(0, self.niveau.findData(n)))
        self.chargement = False
        self.charger_niveau()

    def _niveaux_manquants(self, annee: str) -> None:
        lignes = [r for r in ev._lignes(self.f.conn, annee) if not r["niveau"]]
        self.niveaux_manquants.setVisible(bool(lignes))
        self.b_niveaux.setVisible(bool(lignes))
        self.niveaux_manquants.setRowCount(len(lignes))
        for i, r in enumerate(lignes):
            self.niveaux_manquants.setItem(i, 0, cellule(f"{r['nom']} · {r['classe']}", r["code_massar"]))
            cb = QComboBox()
            cb.addItem("—", None)
            for code in ev.niveaux_du_code_classe(r["classe"]) or list(ev.ORDINAUX):
                if code in ev.ORDINAUX:
                    cb.addItem(ev.ORDINAUX[code], code)
            self.niveaux_manquants.setCellWidget(i, 1, cb)

    def charger_niveau(self) -> None:
        if self.chargement:
            return
        annee, niveau = self.annee.currentText(), self.niveau.currentData()
        while self.grille_isa.count():
            w = self.grille_isa.takeAt(0).widget()
            if w:
                w.setParent(None)
        self.isa = {}
        if not annee or not niveau:
            self.stats.setRowCount(0)
            return
        stats = ev.stats_par_classe(self.f.conn, annee, niveau)
        self.stats.setRowCount(len(stats))
        for i, s in enumerate(stats):
            for j, val in enumerate((s.libelle, s.g, s.f, s.t, s.rt, s.et, s.pourcentage)):
                self.stats.setItem(i, j, cellule(val))
        for j, lib in enumerate(("القسم", "العربية", "الفرنسية", "الرياضيات", "الإجمالية")):
            self.grille_isa.addWidget(etiquette(lib), 0, j)
        classes = sorted({r["classe"] for r in ev._lignes(self.f.conn, annee) if r["niveau"] == niveau})
        for i, classe in enumerate(classes, 1):
            self.grille_isa.addWidget(QLabel(ev.libelle_classe(classe)), i, 0)
            val = ev.lire_isa(self.f.conn, annee, classe)
            self.isa[classe] = {}
            for j, k in enumerate(("ar", "fr", "ma", "gl"), 1):
                e = QLineEdit("" if val[k] is None else f"{val[k]:g}")
                e.setLayoutDirection(Qt.LeftToRight)
                e.setMaximumWidth(110)
                self.grille_isa.addWidget(e, i, j)
                self.isa[classe][k] = e
        c = ev.lire_conseil(self.f.conn, annee, niveau)
        self.date.definir(c.get("date_conseil") or None)
        self.phase.setText(c.get("phase_isa") or "الخامسة")
        self.difficultes.setPlainText(c.get("difficultes") or "")
        self.solutions.setPlainText(c.get("solutions") or "")
        m = ev.membres(self.f.conn, annee, niveau)
        self.membres.setText("أعضاء المجلس (توقيعات المحضر): " + "، ".join(m) if m else
                             "لا أساتذة مسندون لأقسام هذا المستوى في «الموارد البشرية»: تُترك خانات التوقيع فارغة.")

    # ---------- الإجراءات ----------

    def choisir_fichiers(self) -> None:
        f, _ = QFileDialog.getOpenFileNames(self, "ملفات «مجمل المعدلات السنوية» من مسار", "", "Excel (*.xlsx)")
        if f:
            self.importer([Path(x) for x in f])

    def importer(self, chemins: list[Path]):
        try:
            r = ev.importer(self.f.conn, chemins)
        except ev.ErreurEvaluation as e:
            message(self.message, str(e), True)
            return None
        self.rafraichir()
        self.annee.setCurrentText(r.annee)
        message(self.message, f"استوردت نتائج {r.eleves} تلميذاً ({len(r.classes)} أقسام) للسنة {r.annee}.")
        return r

    def enregistrer_niveaux(self) -> int:
        annee, n = self.annee.currentText(), 0
        for i in range(self.niveaux_manquants.rowCount()):
            code = self.niveaux_manquants.cellWidget(i, 1).currentData()
            if code:
                ev.definir_niveau(self.f.conn, annee, self.niveaux_manquants.item(i, 0).data(Qt.UserRole), code)
                n += 1
        self.charger()
        message(self.message, f"حُفظ مستوى {n} تلميذاً.")
        return n

    def _enregistrer(self) -> bool:
        annee, niveau = self.annee.currentText(), self.niveau.currentData()
        try:
            d = self.date.iso()
            ev.enregistrer_conseil(self.f.conn, annee, niveau, d, self.phase.text(),
                                   self.difficultes.toPlainText(), self.solutions.toPlainText())
            for classe, champs in self.isa.items():
                ev.enregistrer_isa(self.f.conn, annee, classe, {k: e.text() for k, e in champs.items()})
        except (ev.ErreurEvaluation, ValueError) as e:
            message(self.message, str(e) or "التاريخ غير صحيح.", True)
            return False
        return True

    def _ouvrir(self, doc) -> None:
        message(self.message, f"وُلّدت الوثيقة: ⁦{doc.chemin.name}⁩")
        try:
            bureautique.ouvrir(doc.chemin)
        except OSError as e:
            message(self.message, f"وُلّدت الوثيقة لكن تعذر فتحها: {e}", True)

    def generer_pv(self):
        if not self._enregistrer():
            return None
        try:
            doc = ev.generer_conseil(self.f.conn, self.f.dossier, self.annee.currentText(), self.niveau.currentData())
        except (ev.ErreurEvaluation, dc.ErreurDocument) as e:
            message(self.message, str(e), True)
            return None
        self._ouvrir(doc)
        return doc

    def generer_synthese(self):
        try:
            le = self.date.iso() or date.today().isoformat()
            doc = ev.generer_synthese(self.f.conn, self.f.dossier, self.annee.currentText(),
                                      self.periode.currentText(), le)
        except (ev.ErreurEvaluation, dc.ErreurDocument, ValueError) as e:
            message(self.message, str(e), True)
            return None
        self._ouvrir(doc)
        return doc
