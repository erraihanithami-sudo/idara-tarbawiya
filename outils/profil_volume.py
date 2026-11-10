"""قياس زمن خدمات الصفحات على مؤسسة وهمية كبيرة (350 تلميذاً، وحدتان). يُستعمل لكشف البطء.
الاستعمال: python outils/profil_volume.py [مجلد]"""

from __future__ import annotations

import cProfile
import pstats
import random
import sys
import tempfile
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from idara.data.db import ouvrir_base  # noqa: E402
from idara.data.dossier import DossierDonnees  # noqa: E402
from idara.services import etablissement as et  # noqa: E402
from idara.services import import_eleves as imp  # noqa: E402
from tests.fabrique_massar import classeur  # noqa: E402

NIVEAUX = ["1APG", "2APG", "3APG", "4APG", "5APG", "6APG"]


def base_volumineuse(dossier_tmp: Path, n_par_classe: int = 29):
    d = DossierDonnees(dossier_tmp / "data").preparer()
    conn = ouvrir_base(d.base)
    et.appliquer_configuration_initiale(conn, d, et.ConfigurationInitiale(
        etablissement=et.Etablissement(nom_ar="مدرسة تجريبية", direction_ar="م", academie_ar="أ"),
        directeur=et.Directeur(nom_ar="المدير", prenom_ar="أحمد", sexe="M"), annee="2026/2027",
        unites=["المركز", "الفرعية"]))
    rnd = random.Random(1)
    k = 0
    for u, nb in (("المركز", 2), ("الفرعية", 1)):
        classes = {}
        for niv in NIVEAUX:
            for j in range(1, nb + 1):
                el = []
                for _ in range(n_par_classe):
                    k += 1
                    el.append((f"X{k:09d}", f"النسب{k}", f"الاسم{k}", rnd.choice("MF"),
                               f"{2013 + NIVEAUX.index(niv) * 0}-0{rnd.randint(1, 9)}-1{rnd.randint(0, 9)}", "المدينة"))
                classes[f"{niv}-{j}"] = el
        f = classeur(dossier_tmp / f"{u}.xlsx", classes)
        r = imp.analyser(conn, [f], u)
        imp.appliquer(conn, d, r, u)
    return conn, d, k


def mesurer(conn, d) -> list[tuple[str, float]]:
    from idara.services import (absences, eleves, frais_inscription, mouvements, statistiques, tableau_bord,
                                vidage)
    from idara.services import soutien as sv
    taches = [
        ("eleves.rechercher (tout)", lambda: eleves.rechercher(conn, "", limite=2000)),
        ("eleves.rechercher (unite)", lambda: eleves.rechercher(conn, "", limite=2000, unite="المركز")),
        ("eleves.rechercher (texte)", lambda: eleves.rechercher(conn, "الاسم1")),
        ("tableau_bord.indicateurs", lambda: tableau_bord.indicateurs(conn)),
        ("statistiques.analyse", lambda: statistiques.analyse_eleves(conn)),
        ("statistiques.par_niveau", lambda: statistiques.par_niveau(conn)),
        ("statistiques.evolution_tarl", lambda: statistiques.evolution_tarl(conn)),
        ("frais.lister", lambda: frais_inscription.lister(conn, None, None)),
        ("mouvements.alertes", lambda: mouvements.alertes(conn)),
        ("mouvements.sorties", lambda: mouvements.sorties_sans_transfert(conn)),
        ("imp.repartition", lambda: imp.repartition_classes(conn)),
        ("vidage.compter*", lambda: [vidage.compter(conn, c.cle) for c in vidage.COMPOSANTS]),
        ("soutien.eleves_classe", lambda: sv.eleves_classe(conn, conn.execute("SELECT id FROM classe").fetchone()[0])),
    ]
    res = []
    for nom, fn in taches:
        t = time.perf_counter()
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            nom += f" !{type(e).__name__}: {e}"
        res.append((nom, time.perf_counter() - t))
    return res


if __name__ == "__main__":
    tmp = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp())
    t = time.perf_counter()
    conn, d, n = base_volumineuse(tmp)
    print(f"base: {n} تلميذ في {time.perf_counter() - t:.2f}s")
    for nom, s in sorted(mesurer(conn, d), key=lambda x: -x[1]):
        print(f"{s * 1000:9.1f} ms  {nom}")
    if "--profil" in sys.argv:
        pr = cProfile.Profile()
        pr.enable()
        mesurer(conn, d)
        pr.disable()
        pstats.Stats(pr).sort_stats("cumulative").print_stats(15)
