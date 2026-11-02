"""نقطة تشغيل التطبيق."""

from __future__ import annotations

import sys
import traceback
from datetime import datetime

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
    app.setFont(theme.charger_police())
    app.setStyleSheet(theme.FEUILLE_STYLE)
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
        AssistantPremierLancement()
        BandeZellige()
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
    from idara.ui.assistant import AssistantPremierLancement
    from idara.ui.fenetre import FenetrePrincipale

    fenetres = {}

    def ouvrir_principale(dossier: DossierDonnees) -> None:
        f = FenetrePrincipale(dossier)
        fenetres["principale"] = f
        f.showMaximized()
        if "assistant" in fenetres:
            fenetres.pop("assistant").close()

    dossier = dossier_pret()
    if dossier:
        ouvrir_principale(dossier)
    else:
        a = AssistantPremierLancement()
        a.resize(1200, 780)
        a.termine.connect(ouvrir_principale)
        fenetres["assistant"] = a
        a.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
