"""تفريغ مكوّن واحد، وتقسيم التلاميذ حسب الوحدات المدرسية (طلب المدير 2026-11-07). بيانات وهمية."""

import pytest

from idara.services import eleves as el
from idara.services import etablissement as et
from idara.services import import_eleves as imp
from idara.services import projet_etab as pe
from idara.services import sauvegarde
from idara.services import soutien as sv
from idara.services import vidage as vd
from tests.test_eleves import AR, base, classeur  # noqa: F401


def _deux_unites(conn):
    et.definir_unites(conn, ["الوحدة المركزية", "فرعية الجبل"])
    rep = imp.repartition_classes(conn)
    assert len(rep) >= 2 and all(r["unite"] is None for r in rep)
    imp.affecter_unite(conn, rep[0]["id"], "الوحدة المركزية")
    for r in rep[1:]:
        imp.affecter_unite(conn, r["id"], "فرعية الجبل")
    return rep


def test_import_par_unite_et_recherche(base, dossier, tmp_path):  # noqa: F811
    rep = _deux_unites(base)
    tous = el.rechercher(base, "")
    centre = el.rechercher(base, "", unite="الوحدة المركزية")
    jbel = el.rechercher(base, "", unite="فرعية الجبل")
    assert centre and jbel and len(centre) + len(jbel) == len(tous)
    assert {r["classe"] for r in centre} == {rep[0]["code"]}
    # إعادة استيراد اللائحة مع اختيار وحدة: كل أقسامها تُسند إليها
    r = imp.analyser(base, [classeur(tmp_path / "a2.xlsx", AR)])
    imp.appliquer(base, dossier, r, unite="الوحدة المركزية")
    assert all(x["unite"] == "الوحدة المركزية" for x in imp.repartition_classes(base) if x["code"] in r.liste.classes)
    with pytest.raises(imp.ErreurImport, match="غير موجودة"):
        imp.appliquer(base, dossier, r, unite="وحدة مجهولة")


def test_vider_eleves_une_unite_puis_tout(base, dossier):  # noqa: F811
    rep = _deux_unites(base)
    n_total = vd.compter(base, "eleves")
    n_centre = len(el.rechercher(base, "", unite="الوحدة المركزية", limite=999))
    avant = len(sauvegarde.lister_sauvegardes(dossier))
    n, copie = vd.vider(base, dossier, "eleves", "الوحدة المركزية")
    assert n == n_centre and copie.exists() and len(sauvegarde.lister_sauvegardes(dossier)) == avant + 1
    assert vd.compter(base, "eleves") == n_total - n_centre
    assert [r["code"] for r in imp.repartition_classes(base)] == [r["code"] for r in rep[1:]]
    with pytest.raises(vd.ErreurVidage, match="خاص بلوائح التلاميذ"):
        vd.vider(base, dossier, "tarl", "الوحدة المركزية")
    vd.vider(base, dossier, "eleves")
    assert vd.compter(base, "eleves") == 0 and not imp.repartition_classes(base)
    assert base.execute("SELECT COUNT(*) FROM inscription").fetchone()[0] == 0


def test_vider_personnel_garde_directeur(base, dossier):  # noqa: F811
    with base:
        p = base.execute("INSERT INTO personnel(nom_ar, prenom_ar, sexe, categorie, ppr) VALUES "
                         "('التجريبي', 'علي', 'M', 'enseignant', '1112223')").lastrowid
    eid = sv.enregistrer_etape(base, "مرحلة")
    sv.creer_groupe(base, eid, sv.categories(base)[0]["id"], p)
    assert vd.compter(base, "personnel") == 1
    n, _ = vd.vider(base, dossier, "personnel")
    assert n == 1 and vd.compter(base, "personnel") == 0
    assert et.directeur_actuel(base) is not None
    assert vd.compter(base, "soutien") == 0


@pytest.mark.parametrize("cle", [c.cle for c in vd.COMPOSANTS])
def test_chaque_composant_se_vide(base, dossier, cle):  # noqa: F811
    pid = pe.enregistrer_projet(base, "م", "2026/2027", "2027/2028")
    pe.ajouter_operation(base, pid, "عملية وهمية")
    vd.vider(base, dossier, cle)
    assert vd.compter(base, cle) == 0
    if cle != "projet":
        assert pe.operations(base, pid)   # المكونات الأخرى لا تُمس
