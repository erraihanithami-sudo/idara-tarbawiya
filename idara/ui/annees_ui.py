"""السنوات الدراسية في الواجهة (طلب المدير 2026-11-12): زر السنة في الشريط الجانبي، نافذة السنوات (فتح سنة
جديدة مع الأرشفة، والاطلاع على سنة ماضية)، وشريط التنبيه عند الاطلاع على الأرشيف."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QHBoxLayout, QHeaderView, QInputDialog, QLabel,
                               QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from idara.services import annee as annee_srv
from idara.ui import theme


def libelle_bouton(conn) -> str:
    a = annee_srv.annee_courante(conn)
    if not a:
        return "السنة الدراسية: —"
    return f"السنة الدراسية {a['libelle']}" + ("  ·  أرشيف" if annee_srv.en_consultation(conn) else "")


class BandeauArchive(QWidget):
    """شريط فوق الصفحات يظهر عند الاطلاع على سنة ماضية."""

    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        self.setObjectName("bandeauArchive")
        h = QHBoxLayout(self)
        h.setContentsMargins(16, 8, 16, 8)
        self.texte = QLabel()
        self.texte.setObjectName("erreur")
        self.texte.setWordWrap(True)
        h.addWidget(self.texte, 1)
        self.retour = QPushButton("العودة إلى السنة الجارية")
        self.retour.setObjectName("principal")
        self.retour.clicked.connect(self.revenir)
        h.addWidget(self.retour)
        self.actualiser()

    def actualiser(self) -> None:
        conn = self.f.conn
        a = annee_srv.annee_courante(conn)
        visible = bool(a) and annee_srv.en_consultation(conn)
        if visible:
            self.texte.setText(f"أنت تطّلع على معطيات السنة الدراسية {a['libelle']} (أرشيف). كل ما يُدخل الآن يُسجل "
                               f"في هذه السنة. السنة الجارية: {annee_srv.la_plus_recente(conn)}.")
        self.setVisible(visible)

    def revenir(self) -> None:
        self.f.changer_annee(annee_srv.la_plus_recente(self.f.conn))


class DialogueAnnees(QDialog):
    """السنوات الدراسية: اللائحة، الاطلاع على سنة، فتح سنة جديدة."""

    def __init__(self, fenetre):
        super().__init__(fenetre)
        self.f = fenetre
        self.setWindowTitle("السنوات الدراسية")
        self.resize(640, 460)
        v = QVBoxLayout(self)
        t = QLabel("السنوات الدراسية")
        t.setObjectName("titrePage")
        v.addWidget(t)
        aide = QLabel("يعمل البرنامج بالسنة الدراسية المفتوحة. عند نهاية السنة افتح سنة جديدة: تُحفظ قبل ذلك نسخة كاملة "
                      "(أرشيف) وتبقى معطيات السنوات الماضية متاحة للاطلاع من هذه اللائحة.")
        aide.setObjectName("sousTitre")
        aide.setWordWrap(True)
        v.addWidget(aide)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["السنة الدراسية", "الأقسام", "التلاميذ", "الحالة"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.doubleClicked.connect(lambda _: self.consulter())
        v.addWidget(self.table, 1)
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.hide()
        v.addWidget(self.message)
        h = QHBoxLayout()
        self.b_consulter = QPushButton("فتح السنة المختارة")
        self.b_consulter.clicked.connect(lambda: self.consulter())
        self.b_nouvelle = QPushButton("فتح سنة دراسية جديدة")
        self.b_nouvelle.setObjectName("principal")
        self.b_nouvelle.clicked.connect(lambda: self.nouvelle())
        fermer = QPushButton("إغلاق")
        fermer.clicked.connect(self.accept)
        h.addWidget(self.b_nouvelle)
        h.addWidget(self.b_consulter)
        h.addStretch()
        h.addWidget(fermer)
        v.addLayout(h)
        self.charger()

    def charger(self) -> None:
        recente = annee_srv.la_plus_recente(self.f.conn)
        ls = annee_srv.lister(self.f.conn)
        self.table.setRowCount(len(ls))
        for i, a in enumerate(ls):
            etat = ("مفتوحة الآن" if a["courante"] else "") + (" · السنة الجارية" if a["libelle"] == recente
                                                               else " · أرشيف")
            for j, val in enumerate((a["libelle"], str(a["classes"]), str(a["eleves"]), etat.strip(" ·"))):
                it = QTableWidgetItem(val)
                it.setTextAlignment(Qt.AlignCenter)
                it.setData(Qt.UserRole, a["libelle"])
                if a["courante"]:
                    f = it.font()
                    f.setBold(True)
                    it.setFont(f)
                self.table.setItem(i, j, it)

    def _info(self, texte: str, erreur=False) -> None:
        self.message.setObjectName("erreur" if erreur else "info")
        self.message.style().unpolish(self.message)
        self.message.style().polish(self.message)
        self.message.setText(texte)
        self.message.show()

    def consulter(self, libelle: str | None = None) -> bool:
        if libelle is None:
            it = self.table.currentItem()
            if not it:
                self._info("اختر سنة من اللائحة.", True)
                return False
            libelle = it.data(Qt.UserRole)
        self.f.changer_annee(libelle)
        self.charger()
        self._info(f"فُتحت السنة الدراسية {libelle}.")
        return True

    def nouvelle(self, libelle: str | None = None, confirmer: bool = True) -> bool:
        recente = annee_srv.la_plus_recente(self.f.conn)
        defaut = annee_srv.suivante(recente) if recente else annee_srv.libelle_pour_date()
        if libelle is None:
            libelle, ok = QInputDialog.getText(self, "فتح سنة دراسية جديدة",
                                               "السنة الدراسية (مثال 2027/2028، أو سنة سابقة للتجريب مثل 2025/2026):",
                                               text=defaut)
            if not ok:
                return False
        if confirmer and QMessageBox.question(
                self, "تأكيد", f"ستُحفظ نسخة كاملة (أرشيف) ثم تُفتح السنة {libelle}.\n"
                               "تبقى معطيات السنوات السابقة محفوظة ويمكن الاطلاع عليها. متابعة؟") != QMessageBox.Yes:
            return False
        try:
            archive = annee_srv.ouvrir_annee(self.f.conn, self.f.dossier, libelle)
        except annee_srv.ErreurAnnee as e:
            self._info(str(e), True)
            return False
        self.f.annee_changee()
        self.charger()
        self._info(f"فُتحت السنة الدراسية {libelle}. نسخة الأرشيف: {archive.name}")
        return True
