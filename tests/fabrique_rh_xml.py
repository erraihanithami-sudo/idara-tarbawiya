"""ملف XML اصطناعي (NOMA: الاسم ثم النسب؛ NOML: النسب ثم الاسم) على بنية تصدير الموارد البشرية (DsAgentExport). كل المعطيات وهمية."""

from __future__ import annotations

from xml.sax.saxutils import escape


def _el(tag: str, champs: dict) -> str:
    return f"  <{tag}>\n" + "".join(f"    <{k}>{escape(str(v))}</{k}>\n" for k, v in champs.items()) + f"  </{tag}>\n"


AGENTS = [
    # (ppr, cina, cinn, noma, noml, genre, j, m, a, grade, cadre, ech, discip, fonc, activite)
    ("9000001", "ZZ", "100001", "سعيد الوهمي", "ELWAHMI SAID", "M", 5, 3, 1985, "11090101", "110901", 7,
     "0012", "E001", "1"),
    ("9000002", "ZZ", "100002", "فاطمة المثال", "EL MITHAL FATIMA", "F", 12, 1, 1990, "11090102", "110901", 6,
     "0011", "E001", "2"),
    ("9000003", "ZY", "100003", "كريم النموذج", "NAMOUDAJ KARIM", "M", 1, 10, 1980, "11120402", "111204", 10,
     "0322", "D017", "3"),
]


def xml_rh(agents=AGENTS) -> bytes:
    corps = ""
    for (ppr, cina, cinn, noma, noml, genre, j, m, a, grade, cadre, ech, discip, fonc, act) in agents:
        corps += _el("DATAIDENTIFPERSONNEL", {
            "PPR": ppr, "CINA": cina, "CINN": cinn, "CD_DISCIP": discip, "CD_GRADE": grade, "NOML": noml,
            "NOMA": noma, "JOUR_NAIS": j, "MOIS_NAIS": m, "AN_NAIS": a, "GENRE": genre,
            "ADRESSE": "حي وهمي رقم 1", "VILLE": "مدينة", "TEL_PORTABLE": "0600000000",
            "DATE_REC": "2010-09-02T00:00:00+00:00", "ANC_GRADE": "2019-12-31T00:00:00+01:00", "ECHELON": ech,
            "DT_ECHELON": "2023-11-29T00:00:00+01:00", "CD_CADRE": cadre,
            "DT_GRADE": "2019-12-31T00:00:00+01:00", "CD_LAST_ACTIVITES": act, "CD_LAST_FONC": fonc})
        corps += _el("ACTIVITE", {"CD_ACTIVITES": act, "CD_FONC": fonc, "PPR": ppr, "CD_CYCLE": "10",
                                  "ACTIV_PRINC": "true", "DT_AFF_ETAB": "2018-09-04T00:00:00+01:00",
                                  "DT_AFF_PROV": "2018-09-04T00:00:00+01:00",
                                  "DT_AFF_REG": "2018-09-04T00:00:00+01:00"})
        if fonc.startswith("E"):
            for niv in ("103", "104", "105", "106"):
                corps += _el("R_TABSERV", {"CD_DISCIP": discip, "CD_NIVENS": niv, "CD_ACTIVITES": act,
                                           "NBR_HEURE_ENS": 7, "NBR_HEURE_SUP": 0})
    for cd, ll in (("11090101", "PROF. DE L'ENS. PRIMAIRE 1ER GR."), ("11090102", "PROF. DE L'ENS. PRIMAIRE 2EME GR."),
                   ("11090103", "PROF. DE L'ENS. PRIMAIRE 3EME GR."),
                   ("11120402", "ADMINISTRATEUR PEDAGOGIQUE 1ER GRADE")):
        corps += _el("R_GRADE", {"CD_GRADE": cd, "LL_GRADE": ll})
    for cd, ll, fl in (("E001", "ENSEIGNANT EN CLASSE", "EN"), ("D017", "Directeur de Secteur Scolaire", "AP")):
        corps += _el("R_FONCT", {"CD_Fonc": cd, "LL_FONC": ll, "Flag": fl})
    return ("<DsAgentExport>\n" + corps + "</DsAgentExport>\n").encode("utf-8")
