"""السجلات الإدارية المعرَّفة بالوصف (2026-11-14). بيانات وهمية."""

import pytest
from docx import Document

from idara.services import personnel as rh
from idara.services import registres as rg
from tests.test_eleves import AR, base, classeur  # noqa: F401


def _lire(chemin):
    d = Document(chemin)
    return [c.text for t in d.tables for r in t.rows for c in r.cells], "\n".join(p.text for p in d.paragraphs)


def test_definitions_coherentes():
    for r in rg.REGISTRES.values():
        cles = [c.cle for c in r.champs]
        assert len(set(cles)) == len(cles) and r.docs and (r.filtre is None or r.filtre in cles), r.cle
        assert all(c.source in rg.REGISTRES for c in r.champs if c.type == "ref")
        assert all(set(d.colonnes) <= set(cles) and d.portee in ("tout", "ligne", "personnel") for d in r.docs)
        assert all("..." not in d.titre + d.description for d in r.docs)
    assert all(k[0] in rg.REGISTRES and k[1] in [d.cle for d in rg.REGISTRES[k[0]].docs] for k in rg.GENERATEURS)


def test_saisie_validation_et_filtre(base):  # noqa: F811
    with pytest.raises(rg.ErreurRegistre, match="مطلوب"):
        rg.enregistrer(base, "agents", {"nom": "", "fonction": "الحراسة"})
    a = rg.enregistrer(base, "agents", {"nom": "  عون   تجريبي ", "fonction": "الحراسة", "societe": "شركة وهمية"})
    b = rg.enregistrer(base, "agents", {"nom": "عونة تجريبية", "fonction": "النظافة"})
    assert rg.lire(base, "agents", a)["nom"] == "عون تجريبي" and rg.compter(base, "agents") == 2
    assert [l["id"] for l in rg.lister(base, "agents", "النظافة")] == [b]
    assert [l["id"] for l in rg.lister(base, "agents", texte="وهمية")] == [a]
    assert rg.repartition(base, "agents", "fonction") == [("الحراسة", 1), ("النظافة", 1)]
    rg.enregistrer(base, "agents", {"nom": "عون معدَّل", "fonction": "الحراسة"}, a)
    assert rg.lire(base, "agents", a)["nom"] == "عون معدَّل" and rg.lire(base, "agents", a)["societe"] == ""
    assert rg.propositions(base, rg.registre("suivi_agents").champ("agent")) == ["عون معدَّل", "عونة تجريبية"]
    assert "absences" not in [c.cle for c in rg.registre("suivi_agents").champs]   # لا تتبع لحضور الأعوان
    with pytest.raises(rg.ErreurRegistre, match="تاريخ غير صحيح"):
        rg.enregistrer(base, "annonces", {"date": "2026-13-40", "titre": "ع", "destinataires": "العموم", "texte": "ن"})
    with pytest.raises(rg.ErreurRegistre, match="قبل تاريخ البداية"):
        rg.enregistrer(base, "demandes", {"date": "2026-11-01", "personnel": "س", "type": "إذن بالتغيب",
                                          "du": "2026-11-05", "au": "2026-11-03"})
    rg.supprimer(base, "agents", b)
    assert rg.compter(base, "agents") == 1 and rg.total(base) == 1
    with pytest.raises(rg.ErreurRegistre):
        rg.lire(base, "agents", b)
    assert rg.eleves(base) and all(len(x) == 2 for x in rg.eleves(base))


def test_documents(base, dossier):  # noqa: F811
    with pytest.raises(rg.ErreurRegistre, match="لا أسطر"):
        rg.generer(base, dossier, "agents", "liste")
    rg.enregistrer(base, "agents", {"nom": "عون تجريبي", "fonction": "الحراسة", "horaire": "8:00 - 16:00"})
    c, t = _lire(rg.generer(base, dossier, "agents", "service"))
    assert "عون تجريبي" in c and "توقيت العمل" in c and "الشركة المشغلة" not in c and "جدول الخدمة" in t
    rg.enregistrer(base, "suivi_agents", {"mois": "نونبر", "agent": "عون تجريبي", "appreciation": "جيد"})
    c, t = _lire(rg.generer(base, dossier, "suivi_agents", "bilan", filtre="نونبر"))
    assert "جيد" in c and "نونبر" in t and "أيام الغياب" not in c
    with pytest.raises(rg.ErreurRegistre, match="لا أسطر"):
        rg.generer(base, dossier, "suivi_agents", "bilan", filtre="ماي")
    # حادثة مدرسية: التصريح لا يطبع الحقول الفارغة
    nom, classe = rg.eleves(base)[0]
    lid = rg.enregistrer(base, "accidents", {"date": "2026-11-10", "eleve": nom, "classe": classe, "lieu": "الساحة",
                                             "description": "سقوط أثناء الاستراحة", "declare": "نعم"})
    with pytest.raises(rg.ErreurRegistre, match="اختر سطراً"):
        rg.generer(base, dossier, "accidents", "declaration")
    c, t = _lire(rg.generer(base, dossier, "accidents", "declaration", lid))
    assert nom in c and "سقوط أثناء الاستراحة" in c and "طبيعة الإصابة" not in c and "تصريح بحادثة مدرسية" in t
    assert not any("..." in x for x in c)
    rg.generer(base, dossier, "accidents", "registre")
    # الخليتان
    rg.enregistrer(base, "cellule_membres", {"cellule": rg.CELLULES[0], "membre": "عضو تجريبي", "qualite": "أستاذ"})
    c, _ = _lire(rg.generer(base, dossier, "cellule_membres", "composition", filtre=rg.CELLULES[0]))
    assert "عضو تجريبي" in c
    lid = rg.enregistrer(base, "cellule_reunions", {"date": "2026-11-12", "cellule": rg.CELLULES[0],
                                                    "ordre": "تتبع الغياب\nحالات التعثر", "conclusions": "زيارة الأسر"})
    _, t = _lire(rg.generer(base, dossier, "cellule_reunions", "pv", lid))
    assert "محضر اجتماع خلية اليقظة" in t and "- حالات التعثر" in t and "الحاضرون" not in t
    for typ, suivi in (("غياب متكرر", "عولجت"), ("غياب متكرر", "قيد المواكبة"), ("تعثر دراسي", "قيد المواكبة")):
        rg.enregistrer(base, "cellule_cas", {"date": "2026-11-13", "cellule": rg.CELLULES[0], "eleve": nom,
                                             "type": typ, "suivi": suivi})
    c, t = _lire(rg.generer(base, dossier, "cellule_cas", "bilan"))
    assert "عدد الحالات المرصودة: 3" in t and c[c.index("غياب متكرر") + 2] == "2"
    # الشهادة
    lid = rg.enregistrer(base, "tahfiz", {"date": "2026-11-14", "eleve": nom, "classe": classe,
                                          "type": "شهادة تقديرية", "motif": "التفوق في القراءة"})
    p = rg.generer(base, dossier, "tahfiz", "certificat", lid)
    _, t = _lire(p)
    d = Document(p)
    assert nom in t and "التفوق في القراءة" in t and "شهادة تقديرية" in t and "أحمد المدير" in t
    assert d.sections[0].page_width > d.sections[0].page_height and "pgBorders" in d.sections[0]._sectPr.xml
    # إعلان وشراكة
    lid = rg.enregistrer(base, "annonces", {"date": "2026-11-14", "titre": "اجتماع الآباء", "destinataires": "أولياء الأمور",
                                            "texte": "يُعقد الاجتماع يوم السبت.\nالحضور ضروري."})
    _, t = _lire(rg.generer(base, dossier, "annonces", "annonce", lid))
    assert "اجتماع الآباء" in t and "الحضور ضروري." in t and "إلى: أولياء الأمور" in t
    lid = rg.enregistrer(base, "partenariats", {"partenaire": "جمعية وهمية", "objet": "دعم القراءة", "etat": "سارية"})
    c, _ = _lire(rg.generer(base, dossier, "partenariats", "fiche", lid))
    assert "جمعية وهمية" in c and "المدة" not in c


def test_demandes_et_fiche_personnelle(base, dossier):  # noqa: F811
    rh.enregistrer(base, rh.Personnel(nom_ar="التجريبي", prenom_ar="سعيد", sexe="M", categorie="enseignant",
                                      ppr="1234567", cadre=rh.CADRES[0], grade=rh.GRADES[0],
                                      date_naissance="1985-01-02", nom_fr="TAJRIBI", prenom_fr="Said"))
    assert "سعيد التجريبي" in rg.noms_personnel(base)
    lid = rg.enregistrer(base, "demandes", {"date": "2026-11-14", "personnel": "سعيد التجريبي", "type": "رخصة الأبوة",
                                            "du": "2026-11-16", "au": "2026-11-18", "motif": "ازدياد مولود"})
    _, t = _lire(rg.generer(base, dossier, "demandes", "demande", lid))
    assert "طلب رخصة الأبوة" in t and "1234567" in t and "ثلاثة أيام" in t and "على يد" in t and "رأي مدير" in t
    lid = rg.enregistrer(base, "demandes", {"date": "2026-11-14", "personnel": "سعيد التجريبي", "type": "إذن بالتغيب"})
    _, t = _lire(rg.generer(base, dossier, "demandes", "demande", lid))
    assert "إلى السيد(ة) مدير(ة) المؤسسة" in t and "على يد" not in t and "ابتداء" not in t
    lid = rg.enregistrer(base, "demandes", {"date": "2026-11-14", "personnel": "سعيد التجريبي",
                                            "type": "إجراء فحص طبي مضاد", "du": "2026-11-10", "au": "2026-11-12"})
    _, t = _lire(rg.generer(base, dossier, "demandes", "demande", lid))
    assert "من مدير(ة) المؤسسة" in t and "فحص طبي مضاد للمعني(ة)" in t and "رأي مدير" not in t
    with pytest.raises(rg.ErreurRegistre, match="اختر الموظف"):
        rg.generer(base, dossier, "demandes", "fiche_personnelle")
    c, t = _lire(rg.generer(base, dossier, "demandes", "fiche_personnelle", cible="سعيد التجريبي"))
    assert "الورقة الشخصية" in t and "التجريبي سعيد" in c and any("TAJRIBI SAID" in x for x in c)
    assert any("02/01/1985" in x for x in c) and "مدرسة تجريبية" in c
    # فريق القيادة
    rg.enregistrer(base, "equipe", {"membre": "سعيد التجريبي", "ppr": "1234567", "qualite": "منسق الفريق"})
    c, t = _lire(rg.generer(base, dossier, "equipe", "pv_formation"))
    assert "منسق الفريق" in c and "تشكيل فريق قيادة" in t
    _, t = _lire(rg.generer(base, dossier, "equipe", "pv_validation"))
    assert "صادق المجلس" in t


def test_accidents_vaziyat_al_irsal(base, dossier):  # noqa: F811
    """طلب المدير 2026-11-20: وضعية ملف الحادثة (أُرسل أم لا) ولا تُطبع في التصريح."""
    r = rg.registre("accidents")
    assert r.dossier and r.etat == "envoi"
    nom, classe = rg.eleves(base)[0]
    lid = rg.enregistrer(base, "accidents", {"date": "2026-11-12", "eleve": nom, "classe": classe,
                                             "description": "التواء في الكاحل"})
    l = rg.lire(base, "accidents", lid)
    assert rg.etat(r, l) == ("لم يُرسل بعد", False)
    l |= {"envoi": "أُرسل إلى المديرية الإقليمية", "date_envoi": "2026-11-13", "reference": "ر/77"}
    rg.enregistrer(base, "accidents", l, lid)
    assert rg.etat(r, rg.lire(base, "accidents", lid)) == ("أُرسل إلى المديرية الإقليمية", True)
    c, _ = _lire(rg.generer(base, dossier, "accidents", "declaration", lid))
    assert "التواء في الكاحل" in c and "ر/77" not in c and "وضعية ملف الحادثة" not in c
    c, _ = _lire(rg.generer(base, dossier, "accidents", "registre"))
    assert "أُرسل إلى المديرية الإقليمية" in c
