"""ملف الرخصة وسلسلة وثائقه وسجل الصادر. أسماء وأرقام وهمية."""

from datetime import date

import pytest

from idara.services import conges as cg
from idara.services import etablissement as et
from idara.services import moteur_docx as m
from idara.services import personnel as rh


@pytest.fixture
def base(dossier, conn):
    et.appliquer_configuration_initiale(conn, dossier, et.ConfigurationInitiale(
        etablissement=et.Etablissement(nom_ar="مدرسة تجريبية", direction_ar="م", academie_ar="أ",
                                       ville_redaction_ar="المدينة"),
        directeur=et.Directeur(nom_ar="المدير", prenom_ar="أحمد", sexe="F"), annee="2026/2027"))
    return conn


def _prof(conn, **k):
    d = dict(nom_ar="التجريبية", prenom_ar="سلمى", sexe="F", categorie="enseignant", ppr="1234567",
             cin="AB123456", cadre="أستاذ(ة) التعليم الابتدائي", grade="الدرجة الأولى", fonction="التدريس",
             cycle="ابتدائي", matiere="فرنسية", niveau_enseigne="الرابع", nb_eleves=28, heures_hebdo=30,
             adresse="حي تجريبي", telephone="0600000000")
    d.update(k)
    return rh.enregistrer(conn, rh.Personnel(**d))


def _type(conn, mot="قصيرة"):
    return conn.execute("SELECT id FROM type_conge WHERE libelle_ar LIKE ?", (f"%{mot}%",)).fetchone()[0]


def _conge(conn, pid, **k):
    d = dict(personnel_id=pid, type_conge_id=_type(conn), date_debut="2026-11-10", duree_jours=10,
             motif="مرض", adresse_conge="حي تجريبي", date_demande="2026-11-10",
             avis_directeur="أستاذة منضبطة", mesures_prises="توزيع التلاميذ على الأقسام",
             medecin="الدكتور الطبيب", specialite="الطب العام", certificat_recu_le="2026-11-10",
             certificat_remis_par="المدلي", certificat_remis_par_cin="cd 1")
    d.update(k)
    return cg.enregistrer(conn, cg.Conge(**d))


# ---------- الصادر ----------

def test_registre_sortant_numerotation(base):
    assert cg.prochain_numero(base) == 1
    _, n1 = cg.enregistrer_sortant(base, "مراسلة أولى", "2026-11-01")
    _, n2 = cg.enregistrer_sortant(base, "مراسلة ثانية", "2026-11-02")
    assert (n1, n2) == ("1/26-27", "2/26-27")
    with pytest.raises(cg.ErreurConge, match="مستعمل"):
        cg.enregistrer_sortant(base, "مكرر", "2026-11-02", numero=2)
    cg.enregistrer_sortant(base, "رقم يدوي", "2026-11-03", numero=98)
    assert cg.prochain_numero(base) == 99
    assert [r["numero"] for r in cg.sortants(base)] == [98, 2, 1]
    with pytest.raises(cg.ErreurConge, match="موضوع"):
        cg.enregistrer_sortant(base, " ", "2026-11-02")


def test_numerotation_reprend_a_un_chaque_annee(base):
    cg.enregistrer_sortant(base, "أ", "2026-11-01")
    from idara.services import annee
    annee.activer_annee(base, "2027/2028")
    assert cg.prochain_numero(base) == 1
    assert cg.enregistrer_sortant(base, "ب", "2027-09-20")[1] == "1/27-28"


# ---------- ملف الرخصة ----------

def test_conge_fin_calculee_et_chevauchement(base):
    pid = _prof(base)
    cid = _conge(base, pid)
    assert cg.lire(base, cid).date_fin == "2026-11-19"
    with pytest.raises(cg.ErreurConge, match="تتداخل"):
        _conge(base, pid, date_debut="2026-11-19", duree_jours=3)
    _conge(base, pid, date_debut="2026-11-20", duree_jours=3, prolongation_de=cid)


@pytest.mark.parametrize("modif, message", [
    (dict(duree_jours=""), "إجبارية"), (dict(duree_jours="x"), "صحيح"), (dict(duree_jours=0), "معقولة"),
    (dict(date_debut=""), "إجباري"), (dict(date_debut="2026-02-30"), "غير صحيح"),
    (dict(type_conge_id=None), "نوع الرخصة"),
])
def test_conge_refus(base, modif, message):
    pid = _prof(base)
    with pytest.raises(cg.ErreurConge, match=message):
        _conge(base, pid, **modif)


def test_prolongation_meme_personne(base):
    a, b = _prof(base), _prof(base, ppr="7654321", cin="CD7")
    cid = _conge(base, a)
    with pytest.raises(cg.ErreurConge, match="نفس الموظف"):
        _conge(base, b, date_debut="2026-11-20", prolongation_de=cid)
    with pytest.raises(cg.ErreurConge, match="بعد بداية"):
        _conge(base, a, date_debut="2026-11-05", duree_jours=2, prolongation_de=cid)


# ---------- الوثائق ----------

def test_demande_complete_et_numero_unique(base, dossier):
    pid = _prof(base)
    cid = _conge(base, pid)
    doc = cg.generer_demande(base, dossier, cid)
    t = m.texte_complet(doc.chemin.read_bytes())
    for attendu in ["السيـــــــــــدة  : سلمى التجريبية", "رقم التأجيـــــر   : 1234567",
                    "مستوى التدريس: الرابع؛ عدد التلاميذ: 28", "الموضـــــــــــوع: طلب رخصة",
                    "مدتهـا: عشرة أيام", "10 نونبر 2026", "19 نونبر 2026", "1/26-27",
                    "السيدة مديرة: مدرسة تجريبية", "رأي السيدة المديرة: أستاذة منضبطة",
                    "مصلحة تدبير الموارد البشرية", "مكتب الرخص والتغيبات", "لا شيء",
                    "لوزارة التربية الوطنية والتعليم الأولي والرياضة بالمدينة"]:
        assert attendu in t, attendu
    assert "{{" not in t and "......" not in t
    # إعادة التوليد لا تحجز رقماً جديداً
    cg.generer_demande(base, dossier, cid)
    assert len(cg.sortants(base)) == 1
    assert cg.lister(base)[0]["numero"] == 1


def test_demande_refusee_si_dossier_incomplet_sans_reserver_numero(base, dossier):
    pid = _prof(base, cin="", heures_hebdo=None)
    cid = _conge(base, pid)
    with pytest.raises(cg.ErreurConge, match="رقم البطاقة الوطنية، ساعات العمل"):
        cg.generer_demande(base, dossier, cid)
    assert cg.sortants(base) == []
    cid2 = _conge(base, _prof(base, ppr="7654321", cin="CD7"), avis_directeur="")
    with pytest.raises(cg.ErreurConge, match="رأي المدير"):
        cg.generer_demande(base, dossier, cid2)


def test_prolongation_et_historique_12_mois(base, dossier):
    pid = _prof(base)
    ancien = _conge(base, pid, date_debut="2026-01-05", duree_jours=3, date_demande="2026-01-05")
    _conge(base, pid, date_debut="2025-06-01", duree_jours=2, date_demande="2025-06-01")  # أقدم من 12 شهراً
    cid = _conge(base, pid)
    prol = _conge(base, pid, date_debut="2026-11-20", duree_jours=5, prolongation_de=cid, date_demande="2026-11-19")
    h = cg.historique_12_mois(base, cg.lire(base, prol))
    assert [r["date_debut"] for r in h] == ["2026-01-05", "2026-11-10"]
    t = m.texte_complet(cg.generer_demande(base, dossier, prol).chemin.read_bytes())
    assert "طلب تمديد رخصة مرضية" in t and "مرض (تمديد)" in t
    assert "05/01/2026" in t and "10/11/2026" in t and ancien


def test_recu_remplacement_bordereau(base, dossier):
    pid = _prof(base)
    cid = _conge(base, pid)
    t = m.texte_complet(cg.generer_recu(base, dossier, cid).chemin.read_bytes())
    for a in ["أنا الموقعة أسفله السيدة: أحمد المدير", "بصفتي مديرة لمدرسة تجريبية", "الدكتور الطبيب",
              "تتعلق بالسيدة: سلمى التجريبية", "CD1", "دتها: عشرة أيام"]:
        assert a in t, a
    assert "الاسم الكامل:" not in t
    # الموظفة نفسها أدلت بالشهادة (طلب المدير 2026-11-13): اسمها أسفل الوصل
    c = cg.lire(base, cid)
    base.execute("UPDATE conge SET certificat_remis_par='سلمى  التجريبية' WHERE id=?", (cid,))
    assert cg.depose_par_lui_meme(cg.lire(base, cid), rh.lire(base, pid)) and c.certificat_remis_par
    t = m.texte_complet(cg.generer_recu(base, dossier, cid).chemin.read_bytes())
    assert "الاسم الكامل: سلمى  التجريبية" in t or "الاسم الكامل: سلمى التجريبية" in t
    t = m.texte_complet(cg.generer_remplacement(base, dossier, cid).chemin.read_bytes())
    assert "طلب تعويض أستاذة في رخصة" in t and "الأستاذة سلمى التجريبية التي تعمل بمدرسة تجريبية" in t
    assert "لتعويضها" in t and "مكتب تسيير مؤسسات التعليم الابتدائي" in t
    assert cg.lire(base, cid).demande_remplacement
    pieces = cg.pieces_proposees(base, cg.lire(base, cid))
    assert pieces[0][0] == "طلب رخصة يخص الأستاذة سلمى التجريبية" and len(pieces) == 4
    doc = cg.generer_bordereau(base, dossier, pieces, "ملف رخصة سلمى التجريبية", "2026-11-11", conge_id=cid)
    t = m.texte_complet(doc.chemin.read_bytes())
    assert "وصل تسلم الشهادة الطبية" in t and t.count("*01") == 4
    assert "{{" not in t
    assert len(cg.documents(base, cid)) == 4       # وصلان (الثاني أدلت فيه الموظفة بنفسها)
    with pytest.raises(cg.ErreurConge, match="واحدة على الأقل"):
        cg.generer_bordereau(base, dossier, [("  ", 1)], "فارغ")
    with pytest.raises(cg.ErreurConge, match="ثماني"):
        cg.generer_bordereau(base, dossier, [(f"و{i}", 1) for i in range(9)], "كثير")


def test_bordereau_lignes_supprimees(base, dossier):
    doc = cg.generer_bordereau(base, dossier, [("محضر الخروج", 4)], "محضر الخروج", "2026-11-01",
                               bureau="bureau_etablissements")
    t = m.texte_complet(doc.chemin.read_bytes())
    assert "محضر الخروج" in t and "*04" in t and "supprimer" not in t
    assert "مكتب تسيير مؤسسات التعليم الابتدائي" in t


def test_remplacement_refuse_pour_non_enseignant(base, dossier):
    g = rh.enregistrer(base, rh.Personnel(nom_ar="الحارس", prenom_ar="علي", sexe="M", categorie="gardien"))
    cid = _conge(base, g)
    with pytest.raises(cg.ErreurConge, match="الأساتذة"):
        cg.generer_remplacement(base, dossier, cid)


def test_reprise(base, dossier):
    pid = _prof(base)
    cid = _conge(base, pid)
    prol = _conge(base, pid, date_debut="2026-11-20", duree_jours=5, prolongation_de=cid)
    assert [r["id"] for r in cg.rentrees_attendues(base, date(2026, 12, 1))] == [prol]
    r = cg.proposition_reprise(base, cid)
    assert (r.date_debut_absence, r.date_fin_absence, r.date_reprise) == ("2026-11-10", "2026-11-24", "2026-11-25")
    assert r.cas_reprise_id == base.execute("SELECT id FROM cas_reprise WHERE libelle_ar LIKE '%قصيرة%'").fetchone()[0]
    rid = cg.enregistrer_reprise(base, r)
    with pytest.raises(cg.ErreurConge, match="من قبل"):
        cg.enregistrer_reprise(base, r)
    t = m.texte_complet(cg.generer_reprise(base, dossier, rid).chemin.read_bytes())
    assert "قد استأنفت عملها بتاريخ: 25 نونبر 2026" in t and "دام: خمسة عشر يوماً" in t
    assert "☑ استئناف العمل بعد رخصة مرض قصيرة الأمد" in t and t.count("☐") == 9
    assert "الدرجــــة: الأولى" in t
    assert cg.rentrees_attendues(base, date(2026, 12, 1)) == []


def test_reprise_apres_absence_sans_conge(base, dossier):
    pid = _prof(base)
    cas = base.execute("SELECT id FROM cas_reprise WHERE libelle_ar LIKE '%تغيب%'").fetchone()[0]
    with pytest.raises(cg.ErreurConge, match="بعد نهاية الغياب"):
        cg.enregistrer_reprise(base, cg.Reprise(pid, cas, "2026-04-06", "2026-04-08", "2026-04-08"))
    rid = cg.enregistrer_reprise(base, cg.Reprise(pid, cas, "2026-04-06", "2026-04-08", "2026-04-09"))
    t = m.texte_complet(cg.generer_reprise(base, dossier, rid).chemin.read_bytes())
    assert "ثلاثة أيام" in t and "06/04/2026" in t and "☑ استئناف العمل بعد تغيب أو انقطاع العمل" in t


def test_parametres_destinataire(base, dossier):
    p = cg.parametres(base)
    assert p["destinataire"].endswith("بالمدينة") and p["bureau_conges"] == "مكتب الرخص والتغيبات"
    cg.definir_parametres(base, {"bureau_conges": "مكتب آخر"})
    assert cg.parametres(base)["bureau_conges"] == "مكتب آخر"
    with pytest.raises(cg.ErreurConge):
        cg.definir_parametres(base, {"bureau_conges": " "})
    with pytest.raises(cg.ErreurConge):
        cg.definir_parametres(base, {"inconnu": "x"})


def test_rukhsat_radaa(base):
    """رخصة الرضاعة (طلب المدير 2026-11-03؛ الفصل 46 كما غُيّر بالقانون 30.22): ساعة يومياً من انتهاء
    رخصة الولادة إلى بلوغ الطفل 24 شهراً، لا تتداخل مع الرخص الأخرى ولا تنتظر محضر استئناف."""
    pid = _prof(base)
    wid = _conge(base, pid, type_conge_id=_type(base, "الولادة"), date_debut="2025-03-01", duree_jours=98,
                 motif="الولادة")
    assert cg.lire(base, wid).date_naissance_enfant == ""
    debut, fin = cg.periode_allaitement(base, pid, "2025-03-01")
    assert (debut, fin) == ("2025-06-07", "2027-02-28")
    rid = _type(base, "الرضاعة")
    nb = (date.fromisoformat(fin) - date.fromisoformat(debut)).days + 1
    with pytest.raises(cg.ErreurConge, match="ازدياد الطفل"):
        _conge(base, pid, type_conge_id=rid, date_debut=debut, duree_jours=nb)
    with pytest.raises(cg.ErreurConge, match="24 شهراً"):
        _conge(base, pid, type_conge_id=rid, date_debut=debut, duree_jours=nb + 1, date_naissance_enfant="2025-03-01")
    cid = _conge(base, pid, type_conge_id=rid, date_debut=debut, duree_jours=nb, date_naissance_enfant="2025-03-01",
                 horaire_allaitement="11:00 - 12:00", medecin="", motif="")
    c = cg.lire(base, cid)
    assert c.date_fin == fin and c.horaire_allaitement == "11:00 - 12:00"
    assert cg.motif_defaut(cg.RADAA) == "الرضاعة"
    # رخصة مرض أثناء فترة الرضاعة مقبولة؛ ولا رضاعتان متداخلتان
    _conge(base, pid, date_debut="2026-01-05", duree_jours=3)
    with pytest.raises(cg.ErreurConge, match="تتداخل"):
        _conge(base, pid, type_conge_id=rid, date_debut="2026-02-01", duree_jours=5, date_naissance_enfant="2025-03-01")
    assert [r["id"] for r in cg.allaitements_en_cours(base, date(2026, 11, 3))] == [cid]
    assert cid not in [r["id"] for r in cg.rentrees_attendues(base, date(2027, 6, 1))]
    # خاصة بالموظفات
    m_id = rh.enregistrer(base, rh.Personnel(nom_ar="الحارس", prenom_ar="علي", sexe="M", categorie="gardien"))
    with pytest.raises(cg.ErreurConge, match="الموظفات"):
        _conge(base, m_id, type_conge_id=rid, date_debut=debut, duree_jours=5, date_naissance_enfant="2025-03-01")
