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
    rd = ps.lire(base, "ressources")
    r = rd["champs"]
    assert rd["lignes"] == [["الأساتذة", "02", "01", "01", ""], ["الحراس", "01", "01", "00", ""]]
    assert [l[0] for l in ps.lire(base, "associations")["lignes"]] == [
        "التعاونية المدرسية", "الجمعية الرياضية", "جمعية آباء وأولياء التلاميذ"]
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
    e["champs"]["date_creation"] = "1985"
    ps.enregistrer(base, "etablissement", e)
    assert ps.actualiser(base, "etablissement")["champs"]["date_creation"] == "1985"
    assert ps.reinitialiser(base, "etablissement")["champs"].get("date_creation", "") == ""
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


def test_ameliorations_des_tableaux(base, dossier):  # noqa: F811
    """التحسينات الست التي وافق عليها المدير (2026-11-13)."""
    import json
    _deux_unites(base)
    _personnel(base)
    # الجرد: الحالة بالأعداد، والحواسيب المسندة غير المسترجعة
    base.execute("INSERT INTO article_inventaire(id, designation, quantite, num_inv_debut, num_inv_fin, qte_bon, "
                 "qte_maintenance, qte_hs) VALUES (1, 'حاسوب محمول', 3, 10, 12, 1, 1, 1)")
    base.execute("INSERT INTO equipement(id, article_id, num_serie) VALUES (1, 1, 'SN-TEST-1')")
    pid = base.execute("SELECT id FROM personnel WHERE prenom_ar='موظف0'").fetchone()[0]
    base.execute("INSERT INTO affectation_equipement(equipement_id, personnel_id, date_remise) "
                 "VALUES (1, ?, '2025-10-01')", (pid,))
    assert ps.lire(base, "equip_admin")["lignes"] == [["حاسوب محمول", "03", "10 - 12", "01", "01", "01", ""]]
    o = ps.lire(base, "ordinateurs")["lignes"]
    assert o == [["موظف0 التجريبي", "900000", "حاسوب محمول", "SN-TEST-1", "01/10/2025", ""]]
    # معطيات محفوظة بأعمدة الإصدار الأول: تُكيَّف
    base.execute("INSERT INTO passation_section(cle, donnees) VALUES ('equip_admin', ?)",
                 (json.dumps({"champs": {}, "lignes": [["مكتب", "02", "", "صالحة", ""]]}, ensure_ascii=False),))
    assert ps.lire(base, "equip_admin")["lignes"][0][0] == "حاسوب محمول"     # أعيد من الجرد
    ps.enregistrer(base, "sportive", {"lignes": [["كرة", "05", "", "جيدة", ""]]})
    d = json.loads(base.execute("SELECT donnees FROM passation_section WHERE cle='sportive'").fetchone()[0])
    d["colonnes"] = ["العدد", "النوع"]
    base.execute("UPDATE passation_section SET donnees=? WHERE cle='sportive'", (json.dumps(d, ensure_ascii=False),))
    assert ps.lire(base, "sportive")["lignes"] == [["05", "كرة", "", "", ""]]
    # اللوائح الطويلة في ملحق، والمتن يكتفي بالعدد
    ps.enregistrer(base, "livres", {"lignes": [["كتاب أ", "02"], ["كتاب ب", "03"], ["كتاب ج", "بدون"]]})
    assert ps.resume_liste(ps.lire(base, "livres")["lignes"]) == "عدد العناوين: 03، عدد النسخ: 05"
    ps.enregistrer(base, "najah_cheques", {"lignes": [["الدفتر 1", "1001", "1025", "مستعمل", ""]]})
    texte, cellules = _texte(ps.generer(base, dossier))
    assert "عدد العناوين: 03، عدد النسخ: 05 (اللائحة المفصلة في الملحق رقم 1)." in texte
    assert "الملحق رقم 1: الكتب والمراجع" in texte and "كتاب ب" in cellules
    assert texte.index("توقيع وخاتم المدير الإقليمي") < texte.index("الملحق رقم 1: الكتب")
    for c in ("الحالة", "يحتاج صيانة", "معطل", "SN-TEST-1", "الجمعيات المدرسية", "آخر وضعية بسجل", "1025",
              "الحواسيب المسلمة للأساتذة", "الأساتذة", "الملفات غير المتوفرة"):
        assert c in cellules, c


def test_sections_ajoutees_par_le_directeur(base, dossier):  # noqa: F811
    """طلب المدير 2026-11-13: إضافة محور خاص إلى المحاور المقترحة."""
    with pytest.raises(ps.ErreurPassation, match="إجباري"):
        ps.ajouter_section(base, " ")
    with pytest.raises(ps.ErreurPassation, match="يوجد محور"):
        ps.ajouter_section(base, "تعريف المؤسسة")
    with pytest.raises(ps.ErreurPassation, match="مكررة"):
        ps.ajouter_section(base, "محور", "أ، أ")
    cle = ps.ajouter_section(base, "الحديقة المدرسية", "النوع، العدد، ملاحظات")
    cle2 = ps.ajouter_section(base, "ملاحظات عامة", texte=True)
    l = ps.sections(base)
    assert [s.cle for s, _ in l][-2:] == [cle, cle2] and all(a for _, a in l)
    assert ps.section(base, cle).colonnes == ("النوع", "العدد", "ملاحظات") and not ps.section(base, cle).champs
    ps.enregistrer(base, cle, {"lignes": [["أشجار الزيتون", "12", ""]]})
    ps.enregistrer(base, cle2, {"champs": {"texte": "سطر أول\nسطر ثان"}})
    ps.deplacer(base, cle2, -100)
    assert ps.sections(base)[0][0].cle == cle2
    texte, cellules = _texte(ps.generer(base, dossier))
    assert "الحديقة المدرسية" in cellules and "أشجار الزيتون" in cellules and "ملاحظات عامة" in cellules
    assert "سطر ثان" in texte and "النص:" not in texte
    with pytest.raises(ps.ErreurPassation, match="لا تُحذف"):
        ps.supprimer_section(base, "etablissement")
    ps.supprimer_section(base, cle)
    assert cle not in [s.cle for s, _ in ps.sections(base)]
    with pytest.raises(ps.ErreurPassation, match="غير معروف"):
        ps.lire(base, cle)
    ps.retablir_ordre(base)
    assert [s.cle for s, _ in ps.sections(base)][-1] == cle2
