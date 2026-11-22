"""شريط الصور في نوافذ التقارير (طلب المدير 2026-11-22): زر «إضافة الصور» ومصغرات الصور مع حذفها وتعليقها.
يُستعمل في نوافذ الأنشطة والأيام التواصلية والأبواب المفتوحة، وفي صور المرافق ونجم الأسبوع لشاشة العرض."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QImage, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QListView, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from idara.services import photos as ph

TAILLE = 132


def vignette(chemin: Path, taille: int = TAILLE) -> QPixmap:
    img = QImage(str(chemin))
    if img.isNull():
        return QPixmap()
    return QPixmap.fromImage(img.scaled(taille, taille, Qt.KeepAspectRatio, Qt.SmoothTransformation))


class BandePhotos(QWidget):
    """صور عنصر واحد (objet، ref). ref=None: العنصر لم يُحفظ بعد، فالزر معطل مع تنبيه."""

    def __init__(self, fenetre, objet: str, parent=None, titre: str = "صور التقرير",
                 note: str = "صور الأطفال لا تُعرض على شاشة المؤسسة إلا بموافقة أوليائهم."):
        super().__init__(parent)
        from idara.ui.vitrine import bouton_couleur
        self.f, self.objet, self.ref = fenetre, objet, None
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 4, 0, 4)
        v.setSpacing(6)
        h = QHBoxLayout()
        self.titre = QLabel(titre, self)
        self.titre.setObjectName("titreCarte")
        self._titre = titre
        h.addWidget(self.titre)
        h.addStretch()
        self.b_ajouter = bouton_couleur("إضافة الصور", "#00897B", "image",
                                        "صور PNG أو JPG تُضاف إلى التقرير المطبوع (تُصغَّر تلقائياً)")
        self.b_ajouter.setParent(self)
        self.b_ajouter.clicked.connect(lambda: self.ajouter())
        self.b_supprimer = bouton_couleur("حذف الصورة", "#C62828", "annuler")
        self.b_supprimer.setParent(self)
        self.b_supprimer.clicked.connect(lambda: self.supprimer_selection())
        h.addWidget(self.b_ajouter)
        h.addWidget(self.b_supprimer)
        v.addLayout(h)
        self.liste = QListWidget(self)
        self.liste.setViewMode(QListView.IconMode)
        self.liste.setFlow(QListView.LeftToRight)
        self.liste.setWrapping(False)
        self.liste.setIconSize(QSize(TAILLE, TAILLE))
        self.liste.setGridSize(QSize(TAILLE + 16, TAILLE + 34))
        self.liste.setFixedHeight(TAILLE + 56)
        self.liste.setMovement(QListView.Static)
        self.liste.setEditTriggers(QListWidget.DoubleClicked | QListWidget.EditKeyPressed)
        self.liste.itemChanged.connect(self._legende)
        v.addWidget(self.liste)
        self.note = QLabel(self)
        self.note.setObjectName("etiquette")
        self.note.setWordWrap(True)
        self._note = note
        v.addWidget(self.note)
        self.message = QLabel(self)
        self.message.setWordWrap(True)
        self.message.hide()
        v.addWidget(self.message)
        self.definir(None)

    def definir(self, ref) -> None:
        self.ref = None if ref in (None, "") else ref
        self.b_ajouter.setEnabled(self.ref is not None)
        self.message.hide()
        self.rafraichir()

    def rafraichir(self) -> None:
        self.liste.blockSignals(True)
        self.liste.clear()
        ps = ph.lister(self.f.conn, self.objet, self.ref) if self.ref is not None else []
        for p in ps:
            it = QListWidgetItem(QIcon(vignette(ph.chemin(self.f.dossier, p))), p["legende"] or "")
            it.setData(Qt.UserRole, p["id"])
            it.setFlags(it.flags() | Qt.ItemIsEditable)
            it.setToolTip("انقر مرتين لكتابة تعليق تحت الصورة")
            self.liste.addItem(it)
        self.liste.blockSignals(False)
        self.titre.setText(f"{self._titre} ({len(ps)})" if ps else self._titre)
        self.liste.setVisible(bool(ps))
        self.b_supprimer.setVisible(bool(ps))
        if self.ref is None:
            self.note.setText("احفظ أولاً، ثم أضف الصور بزر «إضافة الصور».")
        else:
            self.note.setText(("انقر مرتين على صورة لكتابة تعليقها. " if ps else "لا صور بعد. ") + self._note)

    def ajouter(self, chemins: list[str] | None = None) -> int:
        from idara.ui.saisie import message
        if chemins is None:
            from PySide6.QtWidgets import QFileDialog
            chemins, _ = QFileDialog.getOpenFileNames(self, "إضافة الصور", str(Path.home()),
                                                      "Images (*.png *.jpg *.jpeg *.bmp *.webp)")
            if not chemins:
                return 0
        if self.ref is None:
            message(self.message, "احفظ أولاً ثم أضف الصور.", True)
            return 0
        n, erreurs = ph.ajouter_plusieurs(self.f.conn, self.f.dossier, self.objet, self.ref, chemins)
        self.rafraichir()
        if erreurs:
            message(self.message, (f"أضيفت {n} صورة. " if n else "") + " ".join(erreurs[:3]), True)
        else:
            message(self.message, f"أضيفت {n} صورة إلى التقرير." if n != 1 else "أضيفت الصورة إلى التقرير.")
        return n

    def supprimer_selection(self) -> bool:
        it = self.liste.currentItem()
        if it is None:
            from idara.ui.saisie import message
            message(self.message, "حدد صورة أولاً.", True)
            return False
        ph.supprimer(self.f.conn, self.f.dossier, it.data(Qt.UserRole))
        self.rafraichir()
        return True

    def _legende(self, it: QListWidgetItem) -> None:
        ph.definir_legende(self.f.conn, it.data(Qt.UserRole), it.text())
