"""محضر تسليم مهام الإدارة التربوية (نموذج المدير 2026-11-12). بيانات وهمية."""

import pytest
from docx import Document

from idara.services import passation as ps
from idara.services import personnel as rh
from tests.test_eleves import AR, base, classeur  # noqa: F401
from tests.test_vidage import _deux_unites


def _texte(chemin) -> tuple[str, list[str]]:
    d = Document(chemin)
    cellules = [c.text for t in d.tables for r in t.rows for c in r.cells]
    pied = [c.text for t in d.sections[0].footer.tables for r in t.rows for c in r.cells]
    return "\n".join(p.text for p in d.paragraphs), cellules + pied


def _personnel(conn):
    for i, (cat, dossier) in enumerate((("enseignant", True), ("enseignant", False), ("gardien", True))):
        rh.enregistrer(conn, rh.Personnel(nom_ar="التجريبي", prenom_ar=f"موظف{i}", sexe="M", categorie=cat,
                                          ppr=f"90000{i}", cadre=rh.CADRES[0] if cat == "enseignant" else "",
                                          dossier_disponible=dossier))


def test_donnees_proposees_par_le_programme(base):  # noqa: F811
    _deux_unites(base)
    _personnel(base)
    e = ps.lire(base, "etablissement")["champs"]
    assert e["nb_unites"] == "01" and e["nom"]
    r = ps.lire(base, "ressources")["champs"]
    assert (r["nb_enseignants"], r["nb_agents"], r["dossiers_enseignants"], r["dossiers_agents"]) == \
        ("02", "01", "01", "01")
    el = ps.lire(base, "eleves")["lignes"]
    assert [l[0] for l in el] == ["الوحدة المركزية", "فرعية الجبل"]
    assert sum(int(l[1]) for l in el) == int(r["nb_eleves"])
    pe = ps.lire(base, "personnel")["lignes"]
    assert len(pe) == 3 and {l[3] for l in pe} == {"متوفر", "غير متوفر"}
    assert all("المدير" not in l[2] for l in pe)
    assert ps.lire(base, "parties")["champs"]["ancien_nom"]
    assert len(ps.lire(base, "batiments")["lignes"]) == 6
    assert [l[0] for l in ps.lire(base, "cles")["lignes"]][0] == "مفاتيح الحجرات الدراسية"
    assert ps.lire(base, "registres")["lignes"][0][0] == "سجل الصادرات"


def test_actualiser_garde_la_saisie_manuelle(base):  # noqa: F811
    _deux_unites(base)
    d = ps.lire(base, "eleves")
    d["lignes"][0][2] = "20"          # الملفات المدرسية المتوفرة (يدوي)
    d["lignes"][0][1] = "999"         # عدد التلاميذ (من البرنامج)
    ps.enregistrer(base, "eleves", d)
    assert ps.lire(base, "eleves")["lignes"][0][1] == "999"
    n = ps.actualiser(base, "eleves")["lignes"][0]
    assert n[2] == "20" and n[1] != "999"
    e = ps.lire(base, "etablissement")
    e["champs"]["cercle"] = "الدائرة التجريبية"
    ps.enregistrer(base, "etablissement", e)
    assert ps.actualiser(base, "etablissement")["champs"]["cercle"] == "الدائرة التجريبية"
    assert ps.reinitialiser(base, "etablissement")["champs"].get("cercle", "") == ""
    with pytest.raises(ps.ErreurPassation, match="غير معروف"):
        ps.lire(base, "inexistant")
    with pytest.raises(ps.ErreurPassation, match="تاريخ"):
        ps.enregistrer(base, "_general", {"champs": {"date_pv": "25/07/2026"}})


def test_ordre_et_sections_optionnelles(base):  # noqa: F811
    cles = [s.cle for s, _ in ps.sections(base)]
    assert cles == [s.cle for s in ps.SECTIONS]
    ps.deplacer(base, "commission", -100)
    ps.activer(base, "livres", False)
    l = ps.sections(base)
    assert l[0][0].cle == "commission" and dict((s.cle, a) for s, a in l)["livres"] is False
    ps.retablir_ordre(base)
    assert [s.cle for s, a in ps.sections(base) if a] == [s.cle for s in ps.SECTIONS]


def test_importer_liste(tmp_path):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["الكتاب", "العدد", "الكتاب", "العدد"])
    ws.append(["القاموس التجريبي", 4, "كتاب ثان", 1])
    ws.append(["كتاب ثالث", 102, None, None])
    wb.save(tmp_path / "l.xlsx")
    assert ps.importer_liste(tmp_path / "l.xlsx") == [["القاموس التجريبي", "04"], ["كتاب ثان", "01"],
                                                      ["كتاب ثالث", "102"]]
    (tmp_path / "l.csv").write_text("العنوان;العدد\nقصة تجريبية;2\n", encoding="utf-8")
    assert ps.importer_liste(tmp_path / "l.csv") == [["قصة تجريبية", "02"]]
    (tmp_path / "v.csv").write_text("العنوان;العدد\n", encoding="utf-8")
    with pytest.raises(ps.ErreurPassation, match="لم يُعثر"):
        ps.importer_liste(tmp_path / "v.csv")


def test_generer_le_proces_verbal(base, dossier):  # noqa: F811
    _deux_unites(base)
    _personnel(base)
    ps.enregistrer(base, "_general", {"champs": {**ps.lire(base, "_general")["champs"], "date_pv": "2026-07-25"}})
    ps.enregistrer(base, "livres", {"lignes": [[f"كتاب {i}", "01"] for i in range(5)]})
    p = ps.lire(base, "parties")
    p["champs"]["nouveau_nom"] = "المدير الجديد التجريبي"
    ps.enregistrer(base, "parties", p)
    ps.activer(base, "cachets", False)
    chemin = ps.generer(base, dossier)
    texte, cellules = _texte(chemin)
    assert "محضر تسليم مهام الإدارة التربوية" in texte and "بتاريخ: 25/07/2026" in texte
    for titre in ("تعريف المؤسسة", "وثائق المتعلمين", "ملفات الموظفين", "الكتب والمراجع", "أعضاء لجنة التسليم"):
        assert titre in cellules, titre
    assert "الأختام الخاصة بإدارة المؤسسة" not in cellules
    assert "المجموع" in cellules and "كتاب 4" in cellules and "المدير الجديد التجريبي" in cellules
    assert "الملفات المدرسية" in cellules and "المتوفر" in cellules
    assert "25/07/2026" in cellules and "المدير السابق" in cellules      # أسفل الصفحة
    assert "يصرح السيد المدير الجديد" in texte and "توقيع وخاتم المدير الإقليمي" in texte
    assert "..." not in texte and not any("..." in c for c in cellules)
    for s in ps.SECTIONS:
        ps.activer(base, s.cle, False)
    with pytest.raises(ps.ErreurPassation, match="لا محور"):
        ps.generer(base, dossier)


def test_eleves_sans_unite_comptes(base):  # noqa: F811
    """أقسام لم تُسند إلى وحداتها بعد (حالة رصدها اختبار الواجهة): لا يضيع أي تلميذ من العدد."""
    from idara.services import etablissement as et
    et.definir_unites(base, ["الوحدة المركزية", "فرعية الجبل"])
    l = ps.lire(base, "eleves")["lignes"]
    assert len(l) == 1 and int(l[0][1]) == int(ps.lire(base, "ressources")["champs"]["nb_eleves"]) > 0
