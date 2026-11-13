"""أزرار تفريغ المكونات (طلب المدير 2026-11-07): في كل صفحة تُحمَّل فيها لوائح، وفي الإعدادات لكل المكونات."""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QMessageBox, QPushButton, QWidget

from idara.services import etablissement as etab_srv
from idara.services import vidage as vd
from idara.ui import icones
from idara.ui.composants import carte
from idara.ui.saisie import message

# الصفحة ← المكونات التي تُفرَّغ منها
PAGES_VIDAGE = {
    "الاستيراد من مسار": ["eleves"], "التلاميذ القدامى": ["anciens"], "مجالس الأقسام": ["resultats"],
    "التعلمات الأساس": ["tarl"], "الموارد البشرية": ["personnel"], "الأندية والأنشطة": ["activites"],
    "تتبع الغياب": ["absences"], "التسجيلات": ["frais"], "الدعم التربوي": ["soutien"], "الامتحان": ["examen"],
    "مشروع المؤسسة": ["projet"], "جمعية دعم مدرسة النجاح": ["finances"], "الجرد": ["inventaire"], "أولياء الأمور": ["parents"], "البنية المادية": ["structure"],
}


class LigneVidage(QWidget):
    """سطر: اسم المكوّن وعدد عناصره، نطاق التفريغ (الوحدة) للتلاميذ، وزر التفريغ."""

    def __init__(self, fenetre, cle: str, zone_message: QLabel, avec_titre: bool = True):
        super().__init__()
        self.f, self.cle, self.zone_message = fenetre, cle, zone_message
        c = vd.PAR_CLE[cle]
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        self.l = QLabel()
        self.l.setWordWrap(True)
        self.l.setToolTip(c.description)
        h.addWidget(self.l, 1)
        self.portee = QComboBox()
        self.portee.setVisible(False)
        h.addWidget(self.portee)
        self.bouton = QPushButton(f"تفريغ «{c.libelle}»…")
        self.bouton.setObjectName("danger")
        self.bouton.setIcon(icones.corbeille())
        self.bouton.clicked.connect(lambda: self.vider())
        h.addWidget(self.bouton)
        self.avec_titre = avec_titre
        self.actualiser()

    def actualiser(self) -> None:
        c = vd.PAR_CLE[self.cle]
        n = vd.compter(self.f.conn, self.cle)
        self.l.setText((f"{c.libelle}: " if self.avec_titre else "") + f"{n} عنصر حالياً. {c.description}")
        unites = etab_srv.unites(self.f.conn) if self.cle == "eleves" else []
        actuel = self.portee.currentData()
        self.portee.clear()
        self.portee.addItem("المؤسسة كاملة", None)
        for u in unites:
            self.portee.addItem(f"الوحدة: {u}", u)
        self.portee.setCurrentIndex(max(0, self.portee.findData(actuel)))
        self.portee.setVisible(bool(unites))
        self.bouton.setEnabled(n > 0)

    def vider(self, confirmer: bool | None = None):
        c = vd.PAR_CLE[self.cle]
        unite = self.portee.currentData() if not self.portee.isHidden() else None
        cible = c.libelle + (f" (الوحدة: {unite})" if unite else "")
        if confirmer is None:
            confirmer = getattr(self.f, "confirmer_vidage", None)
        if confirmer is None:
            rep = QMessageBox.question(
                self, "تفريغ مكوّن",
                f"سيُحذف كل ما أُضيف إلى «{cible}».\n{c.description}\n\nتُحفظ قبل ذلك نسخة احتياطية كاملة "
                f"يمكن استرجاعها. هل تتابع؟", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            confirmer = rep == QMessageBox.Yes
        if not confirmer:
            return None
        try:
            n, copie = vd.vider(self.f.conn, self.f.dossier, self.cle, unite)
        except (vd.ErreurVidage, OSError) as e:
            message(self.zone_message, f"تعذر التفريغ، ولم يُحذف شيء: {e}", True)
            return None
        message(self.zone_message, f"فُرّغ «{cible}» ({n} عنصر). نسخة ما قبل التفريغ: {copie.name}")
        actualiser_tout(self.f)
        return n


def carte_page(fenetre, cles: list[str], zone_message: QLabel) -> QWidget:
    c, v = carte("تفريغ هذا المكوّن")
    for k in cles:
        v.addWidget(LigneVidage(fenetre, k, zone_message, avec_titre=False))
    return c


def carte_parametres(fenetre, zone_message: QLabel) -> QWidget:
    c, v = carte("تفريغ مكوّن واحد")
    l = QLabel("لإفراغ مكوّن بعينه دون باقي البرنامج (مثلاً لإعادة استيراد لوائحه). تسبق كل تفريغ نسخة احتياطية.")
    l.setObjectName("etiquette")
    l.setWordWrap(True)
    v.addWidget(l)
    for comp in vd.COMPOSANTS:
        v.addWidget(LigneVidage(fenetre, comp.cle, zone_message))
    return c


def actualiser_tout(fenetre) -> None:
    """بعد التفريغ: تُحدَّث أسطر التفريغ والصفحة الحالية."""
    for w in fenetre.findChildren(LigneVidage):
        w.actualiser()
    nom = fenetre.page_courante()
    if nom:
        fenetre._rafraichir(nom)


def installer(fenetre) -> None:
    """يضيف بطاقة التفريغ في أسفل كل صفحة معنية (قبل الفراغ الأخير)."""
    for nom, cles in PAGES_VIDAGE.items():
        page = fenetre.pages.get(nom)
        lay = page.layout() if page is not None else None
        if lay is None:
            continue
        zone = getattr(page, "message", None)
        if not isinstance(zone, QLabel):
            zone = fenetre.page_etab.message
        w = carte_page(fenetre, cles, zone)
        n = lay.count()
        if n and lay.itemAt(n - 1).spacerItem() is not None:
            lay.insertWidget(n - 1, w)
        else:
            lay.addWidget(w)
