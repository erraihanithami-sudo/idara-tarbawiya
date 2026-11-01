"""صفحة الاستيراد من مسار وتأكيد المستوى في الأقسام المشتركة."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QFileDialog, QGridLayout, QHBoxLayout, QHeaderView,
                               QLabel, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
                               QWidget)

from idara.services import import_eleves as imp
from idara.services import massar as ms
from idara.services import textes as tx
from idara.services.massar import ErreurMassar
from idara.ui.composants import carte, entete

MAX_LIGNES = 40


def _libelle_niveau(code: str) -> str:
    return tx.niveau_ar(code) if code in tx.NIVEAUX else code


def _liste(lignes: list[str]) -> str:
    if len(lignes) > MAX_LIGNES:
        lignes = lignes[:MAX_LIGNES] + [f"... و{len(lignes) - MAX_LIGNES} أخرى"]
    return "\n".join("•  " + l for l in lignes)


class PageImport(QWidget):
    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        self.fichiers: list[Path] = []
        self.rapport: imp.RapportImport | None = None
        v = QVBoxLayout(self)
        v.setContentsMargins(40, 32, 40, 32)
        v.setSpacing(20)
        v.addWidget(entete("الاستيراد من مسار", "راجِع النتيجة قبل الاعتماد. لا شيء يُحذف آلياً."))

        c, cv = carte("لوائح التلاميذ")
        aide = QLabel("اختر لائحة التلاميذ كما صدّرتها من مسار، بالعربية أو بالفرنسية أو الاثنتين معاً "
                      "(الفرنسية لازمة لشهادة العطلة). لا تعدّل الملف قبل اختياره.")
        aide.setObjectName("etiquette")
        aide.setWordWrap(True)
        cv.addWidget(aide)
        h = QHBoxLayout()
        b = QPushButton("اختيار اللوائح...")
        b.clicked.connect(self.choisir)
        self.b_analyser = QPushButton("تحليل")
        self.b_analyser.setObjectName("principal")
        self.b_analyser.setEnabled(False)
        self.b_analyser.clicked.connect(self.analyser)
        h.addWidget(b)
        h.addWidget(self.b_analyser)
        h.addStretch()
        cv.addLayout(h)
        self.l_fichiers = QLabel()
        self.l_fichiers.setWordWrap(True)
        cv.addWidget(self.l_fichiers)
        v.addWidget(c)

        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.hide()
        v.addWidget(self.message)

        # التقرير
        self.c_rapport, rv = carte("نتيجة التحليل")
        self.grille_chiffres = QGridLayout()
        self.grille_chiffres.setSpacing(12)
        rv.addLayout(self.grille_chiffres)
        self.details = QLabel()
        self.details.setWordWrap(True)
        self.details.setTextInteractionFlags(Qt.TextSelectableByMouse)
        rv.addWidget(self.details)
        hb = QHBoxLayout()
        self.b_appliquer = QPushButton("اعتماد الاستيراد")
        self.b_appliquer.setObjectName("principal")
        self.b_appliquer.clicked.connect(self.appliquer)
        b_annuler = QPushButton("إلغاء")
        b_annuler.clicked.connect(self.annuler)
        hb.addWidget(self.b_appliquer)
        hb.addWidget(b_annuler)
        hb.addStretch()
        rv.addLayout(hb)
        self.c_rapport.hide()
        v.addWidget(self.c_rapport)

        # تأكيد المستوى
        self.c_niveaux, nv = carte("تأكيد المستوى في الأقسام المشتركة")
        a2 = QLabel("مرة واحدة فقط: المستوى مقترح حسب السن، صحّحه عند الحاجة ثم أكّد. "
                    "في السنوات الموالية يُقترح المستوى الموالي آلياً.")
        a2.setObjectName("etiquette")
        a2.setWordWrap(True)
        nv.addWidget(a2)
        hc = QHBoxLayout()
        hc.addWidget(QLabel("القسم:"))
        self.choix_classe = QComboBox()
        self.choix_classe.currentIndexChanged.connect(self._remplir_table)
        hc.addWidget(self.choix_classe, 1)
        nv.addLayout(hc)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["الرمز", "الاسم", "تاريخ الازدياد", "المستوى", "ملاحظة"])
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(48)
        entetes = self.table.horizontalHeader()
        entetes.setSectionResizeMode(QHeaderView.ResizeToContents)
        entetes.setSectionResizeMode(1, QHeaderView.Stretch)
        entetes.setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.setColumnWidth(3, 170)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        nv.addWidget(self.table)
        hn = QHBoxLayout()
        self.b_confirmer = QPushButton("تأكيد مستويات هذا القسم")
        self.b_confirmer.setObjectName("principal")
        self.b_confirmer.clicked.connect(self.confirmer)
        hn.addWidget(self.b_confirmer)
        hn.addStretch()
        nv.addLayout(hn)
        v.addWidget(self.c_niveaux)

        self.c_historique, self.hv = carte("آخر عمليات الاستيراد")
        self.l_historique = QLabel()
        self.l_historique.setObjectName("etiquette")
        self.l_historique.setWordWrap(True)
        self.hv.addWidget(self.l_historique)
        v.addWidget(self.c_historique)
        v.addStretch()
        self.rafraichir()

    # ---------- أدوات ----------

    def _message(self, texte: str, erreur: bool = False) -> None:
        self.message.setObjectName("erreur" if erreur else "info")
        self.message.setText(texte)
        self.message.style().unpolish(self.message)
        self.message.style().polish(self.message)
        self.message.show()

    def rafraichir(self) -> None:
        self._remplir_niveaux()
        lots = imp.historique(self.f.conn, 5)
        self.l_historique.setText("\n".join(
            f"{l['date_import'][:16]} · {l['fichier']} · {l['nb_ajoutes']} جديد، "
            f"{l['nb_mis_a_jour']} محدّث، {l['nb_absents']} غائب" for l in lots) or "لا شيء بعد.")

    # ---------- الاستيراد ----------

    def choisir(self) -> None:
        fs, _ = QFileDialog.getOpenFileNames(self, "اختيار لوائح مسار", "", "Excel (*.xlsx *.xlsm)")
        if fs:
            self.definir_fichiers([Path(f) for f in fs])

    def definir_fichiers(self, fichiers: list[Path]) -> None:
        self.fichiers = fichiers
        self.l_fichiers.setText("الملفات المختارة: " + "، ".join(f.name for f in fichiers))
        self.b_analyser.setEnabled(bool(fichiers))
        self.c_rapport.hide()

    def analyser(self) -> imp.RapportImport | None:
        self.message.hide()
        try:
            self.rapport = imp.analyser(self.f.conn, self.fichiers)
        except (ErreurMassar, imp.ErreurImport) as e:
            self._message(str(e), erreur=True)
            self.c_rapport.hide()
            return None
        self._afficher_rapport(self.rapport)
        return self.rapport

    def _afficher_rapport(self, r: imp.RapportImport) -> None:
        while self.grille_chiffres.count():
            w = self.grille_chiffres.takeAt(0).widget()
            if w:
                w.hide()
                w.setParent(None)
                w.deleteLater()
        for i, (lib, n) in enumerate([("تلاميذ جدد", len(r.nouveaux)), ("بيانات ستُحدَّث", len(r.mis_a_jour)),
                                      ("غائبون عن اللائحة", len(r.absents)), ("تنبيهات", len(r.alertes))]):
            boite = QWidget()
            bv = QVBoxLayout(boite)
            bv.setContentsMargins(0, 0, 0, 0)
            e = QLabel(lib)
            e.setObjectName("etiquette")
            ch = QLabel(str(n))
            ch.setObjectName("chiffre")
            bv.addWidget(e)
            bv.addWidget(ch)
            self.grille_chiffres.addWidget(boite, 0, i)

        parties = [f"السنة الدراسية: {r.annee} · الأقسام: {'، '.join(r.liste.classes)} · "
                   f"عدد التلاميذ في اللائحة: {r.nb_eleves} · اللغات: "
                   f"{'، '.join({'ar': 'العربية', 'fr': 'الفرنسية'}[l] for l in r.liste.langues)}"]
        if r.nouvelle_annee:
            parties.append(f"\nستُعتمد {r.annee} سنةً دراسية جارية جديدة عند الاعتماد.")
        if "fr" not in r.liste.langues:
            parties.append("\nبدون اللائحة الفرنسية لن تتوفر الأسماء بالفرنسية اللازمة لشهادة العطلة.")
        if r.mis_a_jour:
            parties.append("\nبيانات ستُحدَّث:\n" + _liste([
                f"{a.nom} ({a.massar.code}): " + "، ".join(
                    f"{imp.CHAMPS[c.champ]}: {c.ancien or '—'} ← {c.nouveau}"
                    for c in a.changements if not c.verrouille) for a in r.mis_a_jour]))
        if r.changements_classe:
            parties.append("\nتغيير القسم:\n" + _liste([
                f"{a.nom}: {a.ancienne_classe} ← {a.massar.classe}" for a in r.changements_classe]))
        if r.absents:
            parties.append("\nغائبون عن اللائحة (مغادرون محتملون، لن يُحذفوا؛ سجّل مغادرتهم من بطاقة التلميذ):\n"
                           + _liste([f"{x['prenom_ar']} {x['nom_ar']} ({x['code_massar']}) · {x['classe']}"
                                     for x in r.absents]))
        if r.alertes:
            parties.append("\nتنبيهات:\n" + _liste(r.alertes))
        self.details.setText("\n".join(parties))
        self.b_appliquer.setEnabled(bool(r.nouveaux or r.mis_a_jour or r.changements_classe or r.nouvelle_annee))
        self.c_rapport.show()

    def appliquer(self) -> imp.ResultatImport | None:
        if self.rapport is None:
            return None
        try:
            res = imp.appliquer(self.f.conn, self.f.dossier, self.rapport)
        except Exception as e:  # noqa: BLE001 — المعاملة أُلغيت كاملة
            self._message(f"لم يتم الاستيراد ولم يتغير شيء: {e}", erreur=True)
            return None
        self.rapport = None
        self.c_rapport.hide()
        self._message(f"تم الاستيراد: {res.ajoutes} تلميذ جديد، {res.mis_a_jour} تحديث. "
                      f"أُخذت نسخة احتياطية قبله ({res.sauvegarde.name}).")
        self.rafraichir()
        self.f.rafraichir_entete()
        return res

    def annuler(self) -> None:
        self.rapport = None
        self.c_rapport.hide()

    # ---------- تأكيد المستوى ----------

    def _remplir_niveaux(self) -> None:
        self.lignes_niveau = imp.niveaux_a_confirmer(self.f.conn)
        classes = list(dict.fromkeys(r["classe"] for r in self.lignes_niveau))
        actuelle = self.choix_classe.currentText()
        self.choix_classe.blockSignals(True)
        self.choix_classe.clear()
        for c in classes:
            n = sum(1 for r in self.lignes_niveau if r["classe"] == c)
            self.choix_classe.addItem(f"{c}  ({n})", c)
        if actuelle:
            i = self.choix_classe.findText(actuelle)
            if i >= 0:
                self.choix_classe.setCurrentIndex(i)
        self.choix_classe.blockSignals(False)
        self.c_niveaux.setVisible(bool(classes))
        self._remplir_table()

    def _remplir_table(self) -> None:
        classe = self.choix_classe.currentData()
        lignes = [r for r in self.lignes_niveau if r["classe"] == classe]
        candidats = ms.niveaux_du_code_classe(classe or "") or list(ms.ORDRE)
        self.table.setRowCount(len(lignes))
        hauteur = 48 * max(1, len(lignes)) + max(36, self.table.horizontalHeader().sizeHint().height()) + 8
        self.table.setMinimumHeight(hauteur)
        self.table.setMaximumHeight(hauteur)
        self.table.updateGeometry()
        self.c_niveaux.updateGeometry()
        self.combos = {}
        for i, r in enumerate(lignes):
            for j, t in enumerate([r["code_massar"], f"{r['prenom_ar']} {r['nom_ar']}",
                                   tx.date_chiffres(r["date_naissance"]) if r["date_naissance"] else "—"]):
                it = QTableWidgetItem(t)
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(i, j, it)
            cb = QComboBox()
            cb.addItem("— اختر —", None)
            for n in candidats:
                cb.addItem(_libelle_niveau(n), n)
            if r["niveau"]:
                cb.setCurrentIndex(max(0, cb.findData(r["niveau"])))
            cb.currentIndexChanged.connect(lambda _=0, i=i: self._note(i))
            cb.setMinimumWidth(150)
            self.table.setCellWidget(i, 3, cb)
            self.combos[r["inscription_id"]] = (cb, r)
            self._note(i)

    def _note(self, i: int) -> None:
        cb = self.table.cellWidget(i, 3)
        r = next(r for c, r in self.combos.values() if c is cb)
        note = ("اختر المستوى" if cb.currentData() is None else
                "السن خارج المعتاد لهذا المستوى: تأكد" if imp.age_hors_norme(cb.currentData(), r["date_naissance"], r["annee"])
                else "")
        it = QTableWidgetItem(note)
        it.setFlags(it.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(i, 4, it)

    def confirmer(self) -> int:
        choix = {ins: cb.currentData() for ins, (cb, _) in self.combos.items() if cb.currentData()}
        restants = len(self.combos) - len(choix)
        if not choix:
            self._message("اختر المستوى لتلميذ واحد على الأقل.", erreur=True)
            return 0
        n = imp.confirmer_niveaux(self.f.conn, choix)
        self._message(f"أُكِّد مستوى {n} تلميذاً." + (f" بقي {restants} دون مستوى." if restants else ""))
        self.rafraichir()
        return n
