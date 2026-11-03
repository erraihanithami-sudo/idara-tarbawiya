"""الامتحان المحلي والإقليمي ووثائقه (تطبيق الامتحان الذي أرسله المدير). بيانات وهمية."""

import os
from pathlib import Path

import docx
import openpyxl
import pytest
from docx.oxml.ns import qn

from idara.services import docs_examen as de
from idara.services import examens as exs
from idara.services import personnel as rh
from tests.test_eleves import base  # noqa: F401


def _texte(p: Path) -> str:
    return "".join(x.text or "" for x in docx.Document(str(p)).element.body.iter(qn("w:t")))


def _profs(conn, n=5):
    return [rh.enregistrer(conn, rh.Personnel(nom_ar="التجريبي", prenom_ar=f"أستاذ{i}", sexe="M",
                                              categorie="enseignant", ppr=f"30000{i:02d}", matiere="عربية"))
            for i in range(1, n + 1)]


def _matieres(conn, eid):
    exs.definir_matieres(conn, eid, [
        {"matiere": "اللغة العربية", "jour": "2027-06-10", "debut": "08:30", "fin": "10:00"},
        {"matiere": "الرياضيات", "jour": "2027-06-10", "debut": "10:30", "fin": "12:00"},
        {"matiere": "اللغة الفرنسية", "jour": "2027-06-11", "debut": "8h30", "fin": "10:00"}])


def test_local_depuis_les_eleves_du_sixieme(base):  # noqa: F811
    ex = exs.examen(base, "local")
    assert ex["intitule"].startswith("الامتحان الموحد المحلي") and ex["session"] == "يونيو 2027"
    exs.modifier(base, ex["id"], ex["intitule"], ex["session"], ex["centre"], "", 101, 1)
    n = exs.preparer_local(base, ex["id"])
    cs = exs.candidats(base, ex["id"])
    assert n == len(cs) == 2 and [c["numero"] for c in cs] == [101, 102]   # تلميذا السادس في البيانات الوهمية
    assert [s["nom"] for s in exs.salles(base, ex["id"])] == ["القاعة 1", "القاعة 2"]
    with pytest.raises(exs.ErreurExamen, match="الإقليمي"):
        exs.importer_provincial(base, ex["id"], Path("x.xlsx"))
    _matieres(base, ex["id"])
    assert [m["debut"] for m in exs.matieres(base, ex["id"])] == ["08:30", "10:30", "08:30"]
    with pytest.raises(exs.ErreurExamen, match="قبل ساعة البداية"):
        exs.definir_matieres(base, ex["id"], [{"matiere": "س", "jour": "2027-06-10", "debut": "10:00", "fin": "09:00"}])


def _liste_direction(chemin: Path) -> Path:
    """نموذج قريب من ملف مسار «PVCollectifDesExamens» (أرقام تبدأ من 7903، القاعات «1-Salle 1»)."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["dligui", "PVCollectif"])
    ws.append([])
    ws.append([None, "رمز مركز الامتحان", "مركز الامتحان", "المستوى", " قاعة الإمتحان", "الرقم الوطني", "رقم الامتحان",
               "الاسم الكامل", "الجنس  ", "تاريخ الإزدياد", " رمز المؤسسة", "المؤسسة"])
    for k, (code, nom, sexe) in enumerate((("X000000004", "النموذج مريم", "أنثى"), ("Z900000001", "الغريب علي", "ذكر"),
                                           ("Z900000002", "الوهمية هند", "أنثى"))):
        ws.append([None, "1234X", "مركز", "السادس ابتدائي", f"{k // 2 + 1}-Salle {k // 2 + 1}", code, 7903 + k, nom,
                   sexe, "22-11-2014", "1234X", "مدرسة"])
    wb.save(chemin)
    return chemin


def test_provincial_garde_les_numeros_de_la_direction(tmp_path, base):  # noqa: F811
    ex = exs.examen(base, "provincial")
    r = exs.importer_provincial(base, ex["id"], _liste_direction(tmp_path / "d.xlsx"))
    cs = exs.candidats(base, ex["id"])
    assert r.n == 3 and r.salles == 2 and [c["numero"] for c in cs] == [7903, 7904, 7905]
    assert [c["salle_numero"] for c in cs] == [1, 1, 2] and cs[0]["sexe"] == "F" and cs[0]["date_naissance"] == "2014-11-22"
    assert len(r.hors_lister) == 2 and cs[0]["eleve_id"] is not None
    p = tmp_path / "dbl.xlsx"
    wb = openpyxl.load_workbook(_liste_direction(tmp_path / "d2.xlsx"))
    wb.active["G5"] = 7903
    wb.save(p)
    with pytest.raises(exs.ErreurExamen, match="مكررة"):
        exs.importer_provincial(base, ex["id"], p)


def test_affectations_et_tous_les_documents(tmp_path, base, dossier):  # noqa: F811
    ex = exs.examen(base, "provincial")
    eid = ex["id"]
    exs.importer_provincial(base, eid, _liste_direction(tmp_path / "d.xlsx"))
    _matieres(base, eid)
    profs = _profs(base, 6)
    ms = exs.matieres(base, eid)
    exs.definir_roles(base, eid, {exs.ROLES[0]: [profs[0]], exs.ROLES[1]: [profs[1]], exs.ROLES[2]: [profs[2]]},
                      {ms[0]["id"]: profs[3]})
    with pytest.raises(exs.ErreurExamen, match="يلزم 6"):
        exs.distribuer(base, eid, par_salle=3)
    cases = exs.distribuer(base, eid, par_salle=1)
    assert len(cases) == 6 and all(p not in profs[:3] for p, _ in cases)
    assert profs[3] not in [p for (p, m) in cases if m == ms[0]["id"]]   # المداوم لا يراقب في مادته
    assert exs.manquants(base, eid) == []
    textes = {}
    for code in de.DOCUMENTS:
        f = de.generer(base, dossier, eid, code)
        assert f.exists(), code
        textes[code] = _texte(f)
    assert "7903" in textes["listes"] and "عدد المترشحين بالقاعة: 2" in textes["listes"]
    assert "ورقة حضور المترشحين" in textes["presence"] and "الرياضيات" in textes["presence"]
    assert "رقم الامتحان: 7905" in textes["tables"]
    assert "استدعاء لاجتياز" in textes["convocations"] and "نصف ساعة" in textes["convocations"]
    assert "القاعة 1" in textes["repartition"] and "أستاذ5 التجريبي" in textes["repartition"]
    assert "سلام تام بوجود مولانا الإمام المؤيد بالله" in textes["convocations_profs"]
    assert "مراقبة القاعة" in textes["convocations_profs"] and "45 دقيقة" in textes["convocations_profs"]
    assert "لجنة المراقبة" in textes["badges"] and "رئيس(ة) مركز الامتحان" in textes["secretariat"]
    assert "إعـــلان" in textes["annonce"] and "الهاتف النقال" in textes["annonce"]
    assert "ورقة التنقيط" in textes["notation"]
    assert "قد تم فتحه أمامنا" in textes["ouverture"] and "أستاذ1 التجريبي" in textes["ouverture"]
    assert "قد تم إغلاقه أمامنا" in textes["fermeture"] and "المستوى: السادس ابتدائي" in textes["fermeture"]
    assert "بطاقة مركز الامتحان" in textes["centre"] and "3000001" in textes["centre"]
    assert "تقرير الملاحظ" in textes["rapport_observateur"] and "زيارة مركز الامتحان" in textes["rapport_president"]
    assert "المستوى: السادس ابتدائي" in textes["fraude"] and "الهاتف النقال" in textes["fraude"]
    if os.environ.get("EXAMEN_SORTIE"):
        out = Path(os.environ["EXAMEN_SORTIE"])
        out.mkdir(parents=True, exist_ok=True)
        for code in ("convocations_profs", "presence", "tables", "ouverture", "repartition"):
            (out / f"{code}.docx").write_bytes(de.generer(base, dossier, eid, code).read_bytes())


def test_documents_refuses_si_incomplet(base, dossier):  # noqa: F811
    ex = exs.examen(base, "local")
    with pytest.raises(exs.ErreurExamen, match="أكمل أولاً"):
        de.generer(base, dossier, ex["id"], "listes")
    assert "جدولة المواد" in exs.manquants(base, ex["id"])
