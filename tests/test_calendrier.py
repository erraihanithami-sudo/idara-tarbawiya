"""محطات السنة الدراسية والتذكيرات (الملف المرفق بالبرنامج: مقرر 2026/2027)."""

import json
from datetime import date

import pytest
from docx import Document

from idara.services import calendrier as cal
from tests.test_personnel import base  # noqa: F401


def test_fichier_mouqarrar_coherent():
    m = cal.mouqarrar("2026/2027")
    assert m["mouqarrar"]["numero"] == "047.26" and m["mouqarrar"]["date"] == "2026-07-03"
    st = cal.stations_ministerielles("2026/2027")
    cles = [s.cle for s in st]
    assert len(cles) == len(set(cles)) and len(st) >= 40
    for s in st:
        assert s.fin >= s.debut and s.type in cal.TYPES and s.titre
        assert date(2026, 9, 1) <= s.debut <= date(2027, 7, 31)
        assert all(p in cal.PUBLICS for p in s.public)
    d = {s.cle: s for s in st}
    assert d["m:debut_etudes"].debut == date(2026, 9, 7)
    assert (d["m:exam_local"].debut, d["m:exam_local"].fin) == (date(2027, 1, 18), date(2027, 1, 19))
    assert d["m:exam_prov"].debut == date(2027, 6, 25) and d["m:fin_etudes"].debut == date(2027, 6, 26)
    assert d["m:mi_annee"].fin == date(2027, 1, 31) and d["m:aid_fitr"].precision == "hijri"
    assert "تقريبي" in d["m:aid_fitr"].periode and "خلال شهر أبريل 2027" == d["m:kangourou"].periode
    assert cal.mouqarrar("2030/2031") is None and cal.stations_ministerielles("2030/2031") == []
    # كل الملفات المرفقة صالحة
    for f in cal.DOSSIER.glob("*.json"):
        assert json.loads(f.read_text(encoding="utf-8"))["format"] == 1


def test_rappels_locales_et_suivi(base):  # noqa: F811
    conn = base   # السنة الجارية 2026/2027
    r = cal.rappels(conn, date(2027, 1, 8))
    assert "m:exam_local" in [s.cle for s in r["a_venir"]]
    assert "m:s1_derniers_ctrl" in [s.cle for s in r["en_cours"]]
    r = cal.rappels(conn, date(2027, 1, 25))
    assert "m:s1_conseils" in [s.cle for s in r["en_retard"]]
    assert "m:mi_annee" in [s.cle for s in r["en_cours"]] and "m:pause2" not in [s.cle for s in r["en_retard"]]
    cal.marquer(conn, "m:s1_conseils")
    assert "m:s1_conseils" not in [s.cle for s in cal.rappels(conn, date(2027, 1, 25))["en_retard"]]
    cal.marquer(conn, "m:s1_conseils", False)
    assert "m:s1_conseils" in [s.cle for s in cal.rappels(conn, date(2027, 1, 25))["en_retard"]]
    sid = cal.enregistrer_locale(conn, "اجتماع مجلس التدبير", "2026-10-07", rappel_jours=5)
    s = next(x for x in cal.stations(conn) if x.cle == f"l:{sid}")
    assert s.locale and s.fin == date(2026, 10, 7)
    assert f"l:{sid}" in [x.cle for x in cal.rappels(conn, date(2026, 10, 3))["a_venir"]]
    assert f"l:{sid}" not in [x.cle for x in cal.rappels(conn, date(2026, 10, 1))["a_venir"]]
    cal.enregistrer_locale(conn, "اجتماع مجلس التدبير (معدل)", "2026-10-08", sid=sid)
    assert any(x.titre.endswith("(معدل)") for x in cal.stations(conn))
    with pytest.raises(cal.ErreurCalendrier):
        cal.enregistrer_locale(conn, "", "2026-10-08")
    with pytest.raises(cal.ErreurCalendrier):
        cal.enregistrer_locale(conn, "س", "2026-10-08", "2026-10-01")
    cal.marquer(conn, f"l:{sid}")
    cal.supprimer_locale(conn, sid)
    assert not conn.execute("SELECT 1 FROM station_suivi WHERE cle=?", (f"l:{sid}",)).fetchone()
    assert [v.cle for v in cal.vacances(conn)][:2] == ["m:pause1", "m:pause2"]


def test_programme_annuel(base, dossier):  # noqa: F811
    cal.enregistrer_locale(base, "حفل نهاية السنة", "2027-06-24", type_="local")
    f = cal.generer_programme(base, dossier)
    texte = "\n".join(c.text for t in Document(f).tables for r in t.rows for c in r.cells)
    entete = "\n".join(p.text for p in Document(f).paragraphs)
    assert "برنامج العمل السنوي برسم السنة الدراسية 2026/2027" in entete and "047.26" in entete
    assert "الامتحان الموحد الإقليمي لنيل شهادة الدروس الابتدائية" in texte and "حفل نهاية السنة" in texte
    assert "شتنبر 2026" in entete and "يوليوز 2027" in entete
