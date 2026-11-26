"""مقترح برنامج العمل السنوي في صفحة «برنامج العمل السنوي» (نموذج المدير 2026-11-26): محور في كل مرة، والإضافة
والتعديل في نافذة منبثقة، والترتيب، واستعادة المقترح، وتاريخ المصادقة، وتوليد الوثيقة."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QComboBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QVBoxLayout,
                               QWidget)

from idara.services import bureautique
from idara.services import programme_annuel as pa
from idara.ui.composants import carte
from idara.ui.saisie import ChampDate, cellule, tableau
from idara.ui.vitrine import FenetreFiche, bouton_couleur


class BlocProgramme(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.f = page.f
        self.index: int | None = None
        v0 = QVBoxLayout(self)
        v0.setContentsMargins(0, 0, 0, 0)
        c, v = carte("مقترح برنامج العمل السنوي")
        intro = QLabel("مقترح جاهز في سبعة محاور على نموذج المدير. تواريخ المقرر الوزاري والأيام العالمية والوطنية "
                       "محددة؛ والباقي فارغ تحدده المؤسسة. عدّل بالإضافة والحذف، ثم ولّد الوثيقة.")
        intro.setWordWrap(True)
        intro.setObjectName("etiquette")
        v.addWidget(intro)
        h = QHBoxLayout()
        self.c_section = QComboBox()
        for n, (k, t, coul) in enumerate(pa.SECTIONS, start=1):
            self.c_section.addItem(f"{n}. {t}", k)
        self.c_section.currentIndexChanged.connect(lambda _: self.afficher())
        h.addWidget(QLabel("المحور"))
        h.addWidget(self.c_section, 1)
        self.l_resume = QLabel()
        self.l_resume.setStyleSheet("font-weight: 700;")
        h.addWidget(self.l_resume)
        v.addLayout(h)
        self.table = tableau(["المحطة", "العمليات والأنشطة المبرمجة", "فترة الإنجاز", "تنبيه"], etirer=1)
        self.table.setMinimumHeight(380)
        self.table.setWordWrap(True)
        self.table.itemDoubleClicked.connect(lambda it: self.ouvrir(it.row()))
        v.addWidget(self.table)
        h = QHBoxLayout()
        for lib, coul, pic, fn, aide in (
                ("سطر جديد", "#2E7D32", "ajouter", lambda: self.ouvrir(None), "محطة أو عملية جديدة في هذا المحور"),
                ("تعديل", "#1565C0", "modifier", lambda: self.ouvrir(self._ligne()), "أو نقرتان على السطر"),
                ("حذف", "#C62828", "supprimer", lambda: self.supprimer(), ""),
                ("أعلى", "#546E7A", None, lambda: self.deplacer(-1), ""),
                ("أسفل", "#546E7A", None, lambda: self.deplacer(1), ""),
                ("استعادة مقترح المحور", "#8D6E63", None, lambda: self.reinitialiser(), "يمحو تعديلات هذا المحور"),
                ("تاريخ المصادقة", "#6A1B9A", "modifier", lambda: self.ouvrir_validation(),
                 "مصادقة مجلس التدبير على البرنامج"),
                ("توليد برنامج العمل السنوي", "#B8860B", "document", lambda: self.generer(),
                 "وثيقة Word على قالب ملون بالمحاور السبعة")):
            b = bouton_couleur(lib, coul, pic, aide)
            b.clicked.connect(fn)
            h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        v0.addWidget(c)

        # نافذة السطر
        w = QWidget()
        vv = QVBoxLayout(w)
        fl = QFormLayout()
        self.c_station = QComboBox()
        self.c_station.setEditable(True)
        self.c_operations = QPlainTextEdit()
        self.c_operations.setPlaceholderText("عملية في كل سطر")
        self.c_operations.setFixedHeight(150)
        self.c_debut, self.c_fin = ChampDate(), ChampDate()
        self.c_periode = QLineEdit()
        self.c_periode.setPlaceholderText("بديل التاريخين: طيلة السنة الدراسية، خلال شهر أكتوبر... (اختياري)")
        fl.addRow("المحطة", self.c_station)
        fl.addRow("العمليات والأنشطة", self.c_operations)
        hd = QHBoxLayout()
        hd.addWidget(QLabel("من"))
        hd.addWidget(self.c_debut)
        hd.addWidget(QLabel("إلى (اختياري)"))
        hd.addWidget(self.c_fin)
        hd.addStretch()
        fl.addRow("فترة الإنجاز", hd)
        fl.addRow("أو نصاً", self.c_periode)
        vv.addLayout(fl)
        h = QHBoxLayout()
        b = bouton_couleur("حفظ", "#2E7D32", "enregistrer")
        b.clicked.connect(lambda: self.enregistrer())
        h.addWidget(b)
        h.addStretch()
        vv.addLayout(h)
        self.msg = QLabel()
        self.msg.setWordWrap(True)
        self.msg.hide()
        vv.addWidget(self.msg)
        self.fiche = FenetreFiche(self, "سطر في برنامج العمل السنوي", "اترك فترة الإنجاز فارغة إن لم تُحدَّد بعد.",
                                  w, largeur=820)
        # نافذة تاريخ المصادقة
        w2 = QWidget()
        v2 = QVBoxLayout(w2)
        f2 = QFormLayout()
        self.c_validation = ChampDate()
        f2.addRow("تاريخ مصادقة مجلس التدبير", self.c_validation)
        v2.addLayout(f2)
        b = bouton_couleur("حفظ", "#2E7D32", "enregistrer")
        b.clicked.connect(lambda: self.enregistrer_validation())
        v2.addWidget(b, 0, Qt.AlignRight)
        self.msg_validation = QLabel()
        self.msg_validation.hide()
        v2.addWidget(self.msg_validation)
        self.fiche_validation = FenetreFiche(self, "مصادقة مجلس التدبير", "يُطبع في الوثيقة فوق توقيعات الأعضاء؛ "
                                             "اتركه فارغاً ليُكتب باليد.", w2, largeur=560)
        self.afficher()

    # ---------- العرض ----------
    def section(self) -> str:
        return self.c_section.currentData()

    def _ligne(self) -> int | None:
        r = self.table.currentRow()
        return r if r >= 0 else None

    def afficher(self) -> None:
        try:
            prog = pa.programme(self.f.conn)
        except pa.ErreurProgramme as e:
            self.l_resume.setText(str(e))
            self.table.setRowCount(0)
            return
        k = self.section()
        lignes = prog["sections"].get(k, [])
        coul = dict((x, c) for x, _, c in pa.SECTIONS)[k]
        self.table.setRowCount(len(lignes))
        for i, l in enumerate(lignes):
            per = pa.periode(l)
            al = pa.alerte(self.f.conn, l)
            for j, x in enumerate((l["station"], l["operations"], per or "تحدده المؤسسة", al)):
                it = cellule(x)
                if j == 2:
                    it.setForeground(QColor(f"#{coul}" if per else "#8A8A8A"))
                if j == 3 and al:
                    it.setForeground(QColor("#C62828"))
                self.table.setItem(i, j, it)
        self.table.resizeRowsToContents()
        n = sum(1 for l in lignes if l.get("debut") or l.get("periode"))
        etat = "معدَّل من المؤسسة" if prog["personnalise"] else "المقترح الافتراضي"
        val = f" · المصادقة: {prog['validation']}" if prog.get("validation") else ""
        self.l_resume.setText(f"{len(lignes)} سطراً، {n} بفترة إنجاز محددة · {etat}{val}")

    def _erreur(self, fi_msg: QLabel, e) -> None:
        fi_msg.setText(str(e))
        fi_msg.setObjectName("erreur")
        fi_msg.setStyleSheet("color: #C62828; font-weight: 700;")
        fi_msg.show()

    # ---------- الأسطر ----------
    def ouvrir(self, index: int | None):
        prog = pa.programme(self.f.conn)
        lignes = prog["sections"][self.section()]
        self.index = index if index is not None and 0 <= index < len(lignes) else None
        self.c_station.clear()
        for s in dict.fromkeys(l["station"] for l in lignes):
            self.c_station.addItem(s)
        l = lignes[self.index] if self.index is not None else None
        self.c_station.setCurrentText(l["station"] if l else "")
        self.c_operations.setPlainText(l["operations"] if l else "")
        self.c_debut.definir(l.get("debut") if l else None)
        self.c_fin.definir(l.get("fin") if l and l.get("fin") != l.get("debut") else None)
        self.c_periode.setText(l.get("periode", "") if l else "")
        self.msg.hide()
        self.fiche.definir_titre("تعديل السطر" if l else "سطر جديد في: " + self.c_section.currentText())
        self.fiche.ouvrir()
        return self.fiche

    def enregistrer(self) -> bool:
        try:
            i = pa.enregistrer_ligne(self.f.conn, self.section(), self.c_station.currentText(),
                                     self.c_operations.toPlainText(), self.c_debut.iso(), self.c_fin.iso(),
                                     self.c_periode.text(), index=self.index)
        except pa.ErreurProgramme as e:
            self._erreur(self.msg, e)
            return False
        except ValueError:
            self._erreur(self.msg, "تاريخ غير صحيح.")
            return False
        self.fiche.hide()
        self.afficher()
        self.table.selectRow(i)
        return True

    def supprimer(self) -> bool:
        i = self._ligne()
        if i is None:
            return False
        pa.supprimer_ligne(self.f.conn, self.section(), i)
        self.afficher()
        return True

    def deplacer(self, sens: int) -> None:
        i = self._ligne()
        if i is None:
            return
        j = pa.deplacer_ligne(self.f.conn, self.section(), i, sens)
        self.afficher()
        self.table.selectRow(j)

    def reinitialiser(self) -> None:
        pa.reinitialiser(self.f.conn, self.section())
        self.afficher()

    def ouvrir_validation(self):
        self.c_validation.definir(pa.programme(self.f.conn).get("validation") or None)
        self.msg_validation.hide()
        self.fiche_validation.ouvrir()
        return self.fiche_validation

    def enregistrer_validation(self) -> bool:
        try:
            pa.definir_validation(self.f.conn, self.c_validation.iso())
        except pa.ErreurProgramme as e:
            self._erreur(self.msg_validation, e)
            return False
        except ValueError:
            self._erreur(self.msg_validation, "تاريخ غير صحيح.")
            return False
        self.fiche_validation.hide()
        self.afficher()
        return True

    def generer(self) -> Path | None:
        from idara.ui.saisie import message
        try:
            p = pa.generer(self.f.conn, self.f.dossier)
        except pa.ErreurProgramme as e:
            message(self.page.message, str(e), True)
            return None
        message(self.page.message, f"وُلّد برنامج العمل السنوي: {p.name}")
        try:
            bureautique.ouvrir(p)
        except Exception:  # noqa: BLE001 — الفتح اختياري
            pass
        return p
