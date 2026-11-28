"""ترقية الأساتذة (المرسوم 2.24.140 والمذكرة 115x26): الرتبة، والدرجة بالاختيار، والامتحان المهني. أساتذة وهميون."""

from datetime import date

import pytest
from docx import Document

from idara.services import personnel as rh
from idara.services import tarqiya as tq
from tests.test_personnel import base  # noqa: F401


def _prof(conn, n, **k):
    d = dict(nom_ar=f"وهمي{n}", prenom_ar="أستاذ", sexe="M", categorie="enseignant", ppr=f"90000{n:02d}",
             cin=f"zz{n:04d}", cadre="أستاذ(ة) التعليم الابتدائي", fonction="التدريس", matiere="عربية",
             date_affectation="2024-09-01")
    d.update(k)
    return rh.enregistrer(conn, rh.Personnel(**d))


def _id(lst, pid):
    return next(c for c in lst if c.pid == pid)


def test_regles_de_base():
    assert tq.duree(tq.G2, 1) == 12 and tq.duree(tq.G2, 2, "lent") == 24 and tq.duree(tq.G2, 5, "lent") == 42
    assert tq.duree(tq.G2, 9, "moyen") == 36 and tq.duree(tq.G2, 10) is None      # الاستثنائية بالاختيار
    assert tq.duree(tq.G1, 10) == 24 and tq.duree(tq.G1, 12) == 24 and tq.duree(tq.G1, 13) is None
    assert tq.duree(tq.GX, 1, "lent") == 36 and tq.duree(tq.GX, 8) is None
    assert tq.rang_au(tq.G1, 5, date(2020, 1, 1), date(2025, 12, 31)) == (7, date(2024, 1, 1))
    assert tq.annee_defaut("rang", date(2026, 11, 28)) == 2025 and tq.annee_defaut("examen", date(2026, 11, 28)) == 2026
    assert "13" in rh.ECHELONS and tq._indice(tq.G1, 13) == 704 and tq._indice(tq.G2, 11) == 564


def test_rang(base):  # noqa: F811
    a = _prof(base, 1, grade=tq.G2, date_grade="2018-09-01", echelon="5", date_echelon="2023-06-15")
    b = _prof(base, 2, grade=tq.G1, date_grade="2015-01-01", echelon="11", date_echelon="2023-03-01")
    c = _prof(base, 3, grade=tq.G2, date_grade="2010-01-01", echelon="10", date_echelon="2022-01-01")
    e = _prof(base, 4, grade=tq.G1, date_grade="2016-01-01", echelon="4", date_echelon="2020-01-01")
    _prof(base, 5, grade=tq.G2, date_grade="2020-01-01")                     # بلا رتبة: ناقص
    res, retard = tq.concernes_rang(base, 2025)
    assert _id(res, a).date_droit == "2025-06-15" and _id(res, a).vers == "الرتبة 6"   # سريع: سنتان
    assert _id(res, b).date_droit == "2025-03-01" and _id(res, b).vers == "الرتبة 12" and _id(res, b).rythme == "مباشرة"
    assert _id(res, c).vers == "الرتبة الاستثنائية" and "10%" in _id(res, c).remarque
    assert _id(retard, e).date_droit == "2022-01-01" and "حيّن" in _id(retard, e).remarque
    tq.definir_rythme(base, a, "lent")                                      # 3 سنوات ونصف: 2026-12-15
    assert all(x.pid != a for x in tq.concernes_rang(base, 2025)[0])
    assert _id(tq.concernes_rang(base, 2026)[0], a).date_droit == "2026-12-15"
    assert any("الرتبة" in m for _, m in tq.manquants(base, "rang"))
    with pytest.raises(tq.ErreurTarqiya):
        tq.definir_rythme(base, a, "x")


def test_choix_et_examen(base, dossier):  # noqa: F811
    # الثانية منذ 2014 (توظيف مباشر فيها): 10 سنوات في 31/12/2024 ← معني برسم 2025 (التقييد الثاني)
    p1 = _prof(base, 11, grade=tq.G2, date_grade="2014-09-01", date_recrutement="2014-09-01", echelon="6",
               date_echelon="2022-09-01")
    # الثانية منذ 2020 بعد توظيف في الثالثة (2010): 5 سنوات اعتبارية (المادة 81) ← 10 في 31/12/2025
    p2 = _prof(base, 12, grade=tq.G2, date_grade="2020-12-31", date_recrutement="2010-09-01", echelon="4",
               date_echelon="2023-01-01")
    # الثانية منذ 2019: امتحان فقط (6 سنوات في 31/12/2025)
    p3 = _prof(base, 13, grade=tq.G2, date_grade="2019-09-01", date_recrutement="2019-09-01", echelon="3",
               date_echelon="2023-09-01")
    # الأولى منذ 2019، الرتبة 7: الممتازة بالاختيار
    p4 = _prof(base, 14, grade=tq.G1, date_grade="2019-01-01", date_recrutement="2005-09-01", echelon="7",
               date_echelon="2024-02-01")
    # الأولى منذ 2022 (سنة اعتبارية)، الرتبة 6 اليوم وتبلغ 7 قبل نهاية 2026
    p5 = _prof(base, 15, grade=tq.G1, date_grade="2022-06-01", date_recrutement="2008-09-01", echelon="6",
               date_echelon="2024-06-01")
    ch = tq.concernes_choix(base, 2025)
    assert _id(ch, p1).anciennete >= 11 and _id(ch, p1).inscription == 2 and not _id(ch, p1).sans_quota
    assert _id(ch, p2).bonus == 5 and "المادة 81" in _id(ch, p2).remarque and _id(ch, p2).inscription == 1
    assert all(c.pid != p3 for c in ch)
    assert _id(ch, p4).vers == tq.GX and _id(ch, p4).inscription == 2        # مستوفٍ منذ 2024 (الرتبة 7 في فبراير 2024)
    assert all(c.pid != p5 for c in ch)
    c5 = _id(tq.concernes_choix(base, 2026), p5)
    assert c5.bonus == 1 and c5.extra["rang_31"] == 7 and c5.inscription == 1     # الرتبة 7 في يونيو 2026
    assert _id(tq.concernes_choix(base, 2027), p1).inscription == 4
    assert _id(tq.concernes_choix(base, 2028), p1).sans_quota                # التقييد الخامس: دون حصيص
    assert ch[0].grade == tq.G1                                             # الممتازة أولاً ثم الأقدمية
    ex = tq.concernes_examen(base, 2025)
    assert {c.pid for c in ex} >= {p1, p3} and all(c.pid != p4 for c in ex)
    assert "بالاختيار" in _id(ex, p1).remarque and _id(ex, p3).remarque == ""
    assert all(c.pid != p3 for c in tq.concernes_examen(base, 2024))        # 5 سنوات و4 أشهر فقط
    # الوثائق
    t = "\n".join(c.text for tb in Document(tq.generer_liste(base, dossier, "choix", 2025)).tables
                  for r in tb.rows for c in r.cells)
    assert "وهمي11" in t and "المادة 81" in t
    d = Document(tq.generer_fiches_note(base, dossier, [p1, p3], 2026))
    txt = "\n".join(p.text for p in d.paragraphs)
    assert "دورة 2026" in txt and "9000011" in txt and "9000013" in txt and txt.count("نموذج رقم 1") == 2
    with pytest.raises(tq.ErreurTarqiya, match="لا معنيين"):
        tq.generer_liste(base, dossier, "examen", 2010)
    # تسجيل الترقية
    g, r = tq.reclassement(_id(ch, p1))
    assert (g, r) == (tq.G1, "5")
    tq.enregistrer_promotion(base, p1, "choix", "2025-12-31", r, g, 2025)
    p = rh.lire(base, p1)
    assert (p.grade, p.echelon, p.date_grade, p.date_echelon) == (tq.G1, "5", "2025-12-31", "2025-12-31")
    assert tq.historique(base, p1)[0]["avant"]["grade"] == tq.G2
    with pytest.raises(tq.ErreurTarqiya, match="إجباري"):
        tq.enregistrer_promotion(base, p1, "rang", "", "6")
