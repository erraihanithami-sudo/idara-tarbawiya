"""قياس زمن فتح كل صفحة وأهم الأفعال على مؤسسة وهمية كبيرة (حوالي 350 تلميذاً في وحدتين)، بالواجهة الحقيقية.
بلاغ المدير 2026-11-10: البرنامج يتوقف كثيراً بعد استيراد لائحة من 347 تلميذاً.
الاستعمال: python outils/profil_ui.py rapports/profil_ui.txt"""

from __future__ import annotations

import cProfile
import io
import os
import pstats
import random
import sys
import tempfile
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

NIVEAUX = ["1APG", "2APG", "3APG", "4APG", "5APG", "6APG"]


def main(sortie: Path) -> None:
    tmp = Path(tempfile.mkdtemp())
    os.environ["IDARA_CONFIG_DIR"] = str(tmp / "config")
    from PySide6.QtWidgets import QApplication

    from idara.app import creer_application
    from idara.services import import_eleves as imp
    from idara.services import personnel as rh
    from idara.ui.assistant import AssistantPremierLancement
    from idara.ui.fenetre import SECTIONS, FenetrePrincipale
    from tests.fabrique_massar import classeur
    from tests.test_interface import remplir_assistant

    lignes: list[str] = []

    def log(t: str) -> None:
        lignes.append(t)
        print(t, flush=True)

    app = creer_application(["profil"])
    a = AssistantPremierLancement()
    remplir_assistant(a, tmp / "الإدارة التربوية")
    a.f_donnees.annee.setCurrentText("2026/2027")
    t = time.perf_counter()
    f = FenetrePrincipale(a.terminer())
    f.resize(1280, 800)
    f.show()
    log(f"فتح النافذة (قاعدة فارغة): {time.perf_counter() - t:.2f}s")
    rnd = random.Random(1)
    k = 0
    for u, nb in (("الوحدة المركزية", 2), ("وحدة فرعية", 1)):
        classes = {}
        for niv in NIVEAUX:
            for j in range(1, nb + 1):
                el = []
                for _ in range(20):
                    k += 1
                    el.append((f"X{k:09d}", f"النسب{k}", f"الاسم{k}", rnd.choice("MF"),
                               f"{2020 - NIVEAUX.index(niv)}-0{rnd.randint(1, 9)}-1{rnd.randint(0, 9)}", "المدينة"))
                classes[f"{niv}-{j}"] = el
        fich = classeur(tmp / f"{k}.xlsx", classes)
        t = time.perf_counter()
        r = imp.analyser(f.conn, [fich], u)
        imp.appliquer(f.conn, f.dossier, r, u)
        log(f"استيراد {u}: {time.perf_counter() - t:.2f}s")
    for i in range(25):
        rh.enregistrer(f.conn, rh.Personnel(nom_ar="التجريبي", prenom_ar=f"أستاذ{i}", sexe="M", categorie="enseignant",
                                            ppr=f"70000{i:02d}", cadre=rh.CADRES[0], matiere="عربية"))
    log(f"عدد التلاميذ: {k}")

    pages = [p for _, fils in SECTIONS for p, _ in fils]
    mesures = []
    prof = cProfile.Profile()
    for passage in (1, 2):
        for p in pages:
            t = time.perf_counter()
            prof.enable()
            try:
                f.aller_a(p)
                QApplication.processEvents()
            except Exception as e:  # noqa: BLE001
                log(f"!! {p}: {type(e).__name__}: {e}")
            prof.disable()
            d = time.perf_counter() - t
            if passage == 2:
                mesures.append((d, p))
    log("\nزمن فتح كل صفحة (المرة الثانية):")
    for d, p in sorted(mesures, reverse=True):
        log(f"{d * 1000:9.0f} ms  {p}")
    # البحث في صفحة التلاميذ حرفاً بحرف
    f.aller_a("التلاميذ")
    t = time.perf_counter()
    for txt in ("ا", "ال", "الا", "الاس", "الاسم", "الاسم1"):
        f.page_eleves.recherche.setText(txt)
        QApplication.processEvents()
    log(f"\nالكتابة في بحث التلاميذ (6 أحرف): {(time.perf_counter() - t) * 1000:.0f} ms")
    s = io.StringIO()
    pstats.Stats(prof, stream=s).sort_stats("cumulative").print_stats(40)
    lignes.append("\n" + s.getvalue())
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text("\n".join(lignes), encoding="utf-8")
    f.close()


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "profil_ui.txt"))
