"""يلتقط صوراً للواجهة ببيانات وهمية لمراجعتها دون حاسوب Windows.

الاستعمال: python outils/captures.py <مجلد_الصور>
"""

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication  # noqa: E402

from idara.app import creer_application  # noqa: E402


def main(sortie: Path) -> None:
    sortie.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp())
    os.environ["IDARA_CONFIG_DIR"] = str(tmp / "config")
    app = creer_application(["captures"])
    from idara.ui.assistant import AssistantPremierLancement
    from idara.ui.fenetre import FenetrePrincipale

    a = AssistantPremierLancement()
    a.resize(1280, 800)
    a.show()

    def photo(w, nom):
        QApplication.processEvents()
        w.grab().save(str(sortie / f"{nom}.png"))

    photo(a, "01_assistant_etape1_vide")
    a.suivant()
    photo(a, "02_assistant_erreur")
    a.f_etab.nom_ar.setText("مجموعة مدارس تجريبية")
    a.f_etab.nom_fr.setText("GS TEST")
    a.f_etab.commune_ar.setText("الجماعة التجريبية")
    a.f_etab.direction_ar.setText("المديرية التجريبية")
    a.f_etab.academie_ar.setText("الأكاديمية التجريبية")
    a.f_etab.unites.setText("الوحدة المركزية، وحدة فرعية")
    photo(a, "03_assistant_etape1_rempli")
    a.suivant()
    a.f_dir.nom_ar.setText("التجريبي")
    a.f_dir.prenom_ar.setText("أحمد")
    photo(a, "04_assistant_etape2")
    a.suivant()
    photo(a, "05_assistant_etape3")
    a.suivant()
    a.f_donnees.dossier.setText(str(tmp / "الإدارة التربوية"))
    photo(a, "06_assistant_etape4")
    dossier = a.terminer()
    a.close()

    f = FenetrePrincipale(dossier)
    f.resize(1280, 800)
    f.show()
    for i, nom in [(0, "07_tableau_de_bord"), (4, "08_etablissement"), (1, "09_page_a_venir"),
                   (2, "10_documents")]:
        f.aller(i)
        photo(f, nom)
    f.close()
    app.quit()
    print("captures:", sorted(p.name for p in sortie.glob("*.png")))


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "captures"))
