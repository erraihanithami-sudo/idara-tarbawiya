"""نقطة تشغيل التطبيق."""

from __future__ import annotations

import sys
import traceback
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from idara import NOM_APPLICATION
from idara.data.db import ouvrir_base
from idara.data.dossier import DossierDonnees
from idara.services import config as config_srv
from idara.services.etablissement import configuration_complete
from idara.ui import theme


def _journal_erreurs(exc_type, exc, tb) -> None:
    """أي خطأ غير متوقع يُسجل في ملف ويُعرض برسالة، بدل إغلاق صامت."""
    try:
        f = config_srv.dossier_config() / "erreurs.log"
        f.parent.mkdir(parents=True, exist_ok=True)
        with f.open("a", encoding="utf-8") as h:
            h.write(f"\n[{datetime.now():%Y-%m-%d %H:%M:%S}]\n")
            h.write("".join(traceback.format_exception(exc_type, exc, tb)))
    except OSError:
        pass
    QMessageBox.critical(None, NOM_APPLICATION,
                         "حدث خطأ غير متوقع وسُجّل في ملف الأخطاء.\n" + str(exc))


def dossier_pret() -> DossierDonnees | None:
    """المجلد المسجل، إن كان موجوداً ومُعدّاً بالكامل."""
    chemin = config_srv.dossier_donnees_enregistre()
    if not chemin or not (chemin / "data.db").exists():
        return None
    dossier = DossierDonnees(chemin)
    conn = ouvrir_base(dossier.base)
    try:
        return dossier if configuration_complete(conn) else None
    finally:
        conn.close()


def creer_application(argv=None) -> QApplication:
    app = QApplication.instance() or QApplication(argv or sys.argv)
    app.setApplicationName(NOM_APPLICATION)
    app.setLayoutDirection(Qt.RightToLeft)
    cfg = config_srv.lire_config()
    if not cfg.get("theme_layali_applique"):
        # «الليلي والذهبي» يُفعَّل مرة واحدة عند التحديث (طلب المدير 2026-11-20)، ثم يبقى اختيار المظهر حراً
        config_srv.ecrire_config(theme=theme.THEME_DEFAUT, theme_maghribi_applique=True, theme_rihab_applique=True,
                                 theme_layali_applique=True)
        cfg = config_srv.lire_config()
    if not cfg.get("theme_rihab_applique"):
        # هوية «رحاب» تُفعَّل مرة واحدة عند التحديث (اختيار المدير 2026-11-13)، ثم يبقى اختيار المظهر حراً
        config_srv.ecrire_config(theme=theme.THEME_DEFAUT, theme_maghribi_applique=True, theme_rihab_applique=True)
        cfg = config_srv.lire_config()
    ico = Path(__file__).resolve().parent / "resources" / "icone.ico"
    if ico.exists():
        from PySide6.QtGui import QIcon
        app.setWindowIcon(QIcon(str(ico)))
    theme.appliquer(cfg.get("theme", theme.THEME_DEFAUT))   # المظهر المختار
    app.setFont(theme.charger_police())   # بعد المظهر: لكل مظهر خطه
    app.setStyleSheet(theme.appliquer(theme.THEME_ACTUEL))   # بعد تحميل الخطوط (خط العناوين)
    return app


def verification_installation() -> int:
    """فحص ذاتي للنسخة المثبتة (يُشغَّل في البناء الآلي): الملفات المرفقة والقاعدة والواجهة."""
    import tempfile
    from pathlib import Path

    from idara.data.db import lister_migrations
    from idara.ui.assistant import AssistantPremierLancement
    from idara.ui.zellige import BandeZellige

    # النسخة المبنية بلا نافذة أوامر: النتيجة تُكتب في ملف
    i = sys.argv.index("--verification")
    rapport = Path(sys.argv[i + 1]) if len(sys.argv) > i + 1 else Path("verification.txt")
    try:
        creer_application()
        assert len(lister_migrations()) >= 2, "ملفات ترحيل القاعدة غير مرفقة"
        with tempfile.TemporaryDirectory() as tmp:
            dossier = DossierDonnees(Path(tmp) / "الإدارة التربوية").preparer()
            conn = ouvrir_base(dossier.base)
            n = conn.execute("SELECT COUNT(*) FROM niveau").fetchone()[0]
            conn.close()
            assert n == 8, "البيانات المرجعية غير مكتملة"
        from idara.services import documents as dc
        from idara.services.moteur_docx import champs_du_modele
        for code in dc.MODELES:
            assert champs_du_modele(dc.chemin_defaut(code)), f"القالب {code} غير مرفق"
        from docx import Document  # وثائق الجمعية: القالب الافتراضي لـ python-docx مرفق
        Document()
        from pptx import Presentation  # تصدير شاشة العرض PowerPoint: القالب الافتراضي مرفق
        Presentation()
        from idara.services import ecran as _ec
        assert _ec.MINISTERE.exists(), "شعار الوزارة غير مرفق"
        AssistantPremierLancement()
        BandeZellige()
        e = ecran_demarrage()
        assert e is not None, "شاشة التحميل"
        e.close()
        # كل وحدات الواجهة مرفقة في النسخة المبنية (بلاغ 2026-11-21: «No module named idara.ui.page_memo»)
        import pkgutil

        import idara.ui as _ui
        noms = [m.name for m in pkgutil.iter_modules(_ui.__path__)]
        assert "page_memo" in noms and "page_liens" in noms, "وحدات الواجهة غير مرفقة"
        import importlib
        for n in noms:
            importlib.import_module(f"idara.ui.{n}")
        police = QApplication.instance().font().family()
        rapport.write_text(f"VERIFICATION_OK police={police}\n", encoding="utf-8")
        return 0
    except Exception:  # noqa: BLE001
        rapport.write_text("VERIFICATION_ECHEC\n" + traceback.format_exc(), encoding="utf-8")
        return 1


def main() -> int:
    if "--verification" in sys.argv:
        return verification_installation()
    app = creer_application()
    sys.excepthook = _journal_erreurs
    ecran = ecran_demarrage()   # يظهر فوراً أثناء التحميل (طلب المدير 2026-11-21)
    from idara.ui.assistant import AssistantPremierLancement
    if ecran is not None:
        ecran.progression(0.35, "تحميل المكونات…")
    from idara.ui.fenetre import FenetrePrincipale
    if ecran is not None:
        ecran.progression(0.55, "فتح قاعدة المعطيات…")
        FenetrePrincipale.progression = staticmethod(ecran.progression)

    fenetres = {}

    def ouvrir_assistant(_=None) -> None:
        a = AssistantPremierLancement()
        a.resize(1200, 780)
        a.termine.connect(ouvrir_principale)
        fenetres["assistant"] = a
        a.show()

    def ouvrir_principale(dossier: DossierDonnees) -> None:
        nonlocal ecran
        f = FenetrePrincipale(dossier)
        FenetrePrincipale.progression = None
        from idara.services import bureautique
        bureautique.ouvreur = f.ouvrir_document   # كل وثيقة مولَّدة تُفتح في محرر البرنامج
        f.reinitialisation.connect(ouvrir_assistant)   # بعد التصفير: مساعد الإعداد الأول
        fenetres["principale"] = f
        if ecran is not None:
            ecran.progression(1.0, "مرحباً بك", pas=8)
        f.showMaximized()
        if ecran is not None:
            ecran.finish(f)
            ecran = None
        if "assistant" in fenetres:
            fenetres.pop("assistant").close()

    dossier = dossier_pret()
    if dossier:
        ouvrir_principale(dossier)
    else:
        if ecran is not None:
            ecran.close()
            ecran = None
        FenetrePrincipale.progression = None
        ouvrir_assistant()
    return app.exec()


class _Ecran:
    """شاشة الترحيب: لوحة ليلية ذهبية، وشريط أنيق يمتلئ تدريجياً إلى أن تجهز النافذة الرئيسية
    (طلب المدير 2026-11-21)."""

    def __init__(self):
        from PySide6.QtWidgets import QSplashScreen
        self.valeur, self.texte = 0.0, "جارٍ التحميل…"
        self.e = QSplashScreen(self._dessiner())
        self.e.show()
        QApplication.processEvents()

    def _dessiner(self):
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap

        from idara import __version__, marque
        from idara.ui.zellige import dessiner_etoile
        w, h = 600, 330
        pm = QPixmap(w, h)
        pm.fill(QColor("#0B1C2C"))
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(0, 0, w, h)
        g = QLinearGradient(r.topRight(), r.bottomLeft())
        g.setColorAt(0, QColor("#0B1C2C"))
        g.setColorAt(1, QColor("#1F3B57"))
        p.fillRect(r, g)
        p.setPen(QPen(QColor("#C9A04A"), 2))
        p.setBrush(Qt.NoBrush)
        p.drawRect(r.adjusted(10, 10, -10, -10))
        for x, y, t in ((95, 140, 70), (175, 55, 22), (205, 225, 14), (w - 60, 55, 18)):
            dessiner_etoile(p, x, y, t, "#C9A04A", pleine=False)
        f = QFont(QApplication.instance().font())
        f.setPointSize(34)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor("#F3D27A"))
        p.drawText(QRectF(40, 50, w - 80, 90), Qt.AlignRight | Qt.AlignVCenter, marque.NOM_COURT)
        f.setPointSize(13)
        f.setBold(False)
        p.setFont(f)
        p.setPen(QColor("#E8EEF5"))
        p.drawText(QRectF(40, 135, w - 80, 40), Qt.AlignRight | Qt.AlignVCenter, "في الإدارة التربوية بالمغرب")
        # الشريط: مجرى ليلي بخيط ذهبي، يمتلئ بتدرج ذهبي ولمعة، ونجمة صغيرة على رأسه
        bar = QRectF(48, 238, w - 96, 14)
        ch = QPainterPath()
        ch.addRoundedRect(bar, 7, 7)
        p.fillPath(ch, QColor(255, 255, 255, 28))
        p.setPen(QPen(QColor(201, 160, 74, 170), 1))
        p.drawPath(ch)
        v = max(0.0, min(1.0, self.valeur))
        if v > 0:
            lw = max(14.0, bar.width() * v)
            plein = QRectF(bar.right() - lw, bar.top(), lw, bar.height())   # يمتلئ من اليمين (العربية)
            gg = QLinearGradient(plein.topRight(), plein.topLeft())
            gg.setColorAt(0, QColor("#B8862E"))
            gg.setColorAt(1, QColor("#F3D27A"))
            cp = QPainterPath()
            cp.addRoundedRect(plein, 7, 7)
            p.fillPath(cp, gg)
            lu = QPainterPath()
            lu.addRoundedRect(QRectF(plein.left() + 3, plein.top() + 2, plein.width() - 6, 4), 2, 2)
            p.fillPath(lu, QColor(255, 255, 255, 90))
            dessiner_etoile(p, plein.left(), bar.center().y(), 9, "#FFF3C4", pleine=True)
        f.setPointSize(10)
        p.setFont(f)
        p.setPen(QColor("#C9D3DF"))
        p.drawText(QRectF(48, 258, w - 96, 30), Qt.AlignRight | Qt.AlignVCenter, self.texte)
        p.drawText(QRectF(48, 258, w - 96, 30), Qt.AlignLeft | Qt.AlignVCenter, f"{int(v * 100)}%   {__version__}")
        p.end()
        return pm

    def progression(self, valeur: float, texte: str | None = None, pas: int = 6) -> None:
        """يتقدم الشريط بلطف نحو القيمة (بضع خطوات مرسومة) دون أن يرجع إلى الخلف."""
        import time
        depart = self.valeur
        cible = max(depart, valeur)
        if texte:
            self.texte = texte
        for k in range(1, pas + 1):
            self.valeur = depart + (cible - depart) * k / pas
            self.e.setPixmap(self._dessiner())
            QApplication.processEvents()
            if pas > 1:
                time.sleep(0.012)

    def finish(self, w) -> None:
        self.e.finish(w)

    def close(self) -> None:
        self.e.close()


def ecran_demarrage():
    """شاشة ترحيب ليلية ذهبية بشريط تقدم، تظهر لحظة الضغط على البرنامج إلى أن تجهز النافذة الرئيسية."""
    try:
        e = _Ecran()
        e.progression(0.08, "تحميل الواجهة…", pas=2)
        return e
    except Exception:  # noqa: BLE001 — الشاشة اختيارية
        return None
