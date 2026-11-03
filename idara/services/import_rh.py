"""استيراد معلومات الموظفين من ملف XML لتصدير الموارد البشرية (DsAgentExport)، كخيار ثانٍ بجانب الملء اليدوي
(طلب المدير 2026-11-03).

بنية الملف (كما في النموذج الذي زوّد به المدير؛ لا بيانات حقيقية في المستودع):
- DATAIDENTIFPERSONNEL: سطر لكل موظف (PPR، CINA+CINN، NOMA، NOML، GENRE، تواريخ الازدياد والتوظيف والدرجة
  والرتبة، CD_GRADE، CD_CADRE، CD_DISCIP، CD_LAST_FONC...).
- ACTIVITE: المهمة الحالية (CD_FONC) وتواريخ التعيين بالمؤسسة والمديرية والأكاديمية.
- R_TABSERV: جدول الخدمة (المادة والمستوى والساعات لكل نشاط).
- جداول مرجعية R_*: تسميات الرموز (الدرجات، الأطر، المهام، المواد...).

القواعد:
- المطابقة برقم التأجير ثم برقم البطاقة الوطنية؛ إعادة الاستيراد تحدّث ولا تكرر، ولا حذف آلي.
- القيمة الفارغة في الملف لا تمحو قيمة مدخلة؛ الاسمان العربي والفرنسي لا يُستبدلان عند موظف موجود
  (قد يكون المدير صحّح تقسيم النسب والاسم).
- المعطيات التي لا يتضمنها الملف (التفتيش، أنصاف أيام العطلة، الأقسام...) تبقى كما هي.
- المدير يُسجَّل من «إعداد المؤسسة»: سطره يُحدَّث إن وُجد، ولا يُنشأ من الاستيراد.
- كل اقتراح يُراجَع قبل الاعتماد.
"""

from __future__ import annotations

import sqlite3
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, replace

from idara.services import personnel as rh
from idara.services import textes as tx


class ErreurImportRH(ValueError):
    """رسالة موجهة للمدير بالعربية."""


# الأطر حسب رمز الهيئة (CD_CORPS = أول 4 أرقام من CD_CADRE)
_CORPS = {"1109": "أستاذ(ة) التعليم الابتدائي", "1112": "متصرف(ة) تربوي(ة)"}
# المواد (CD_DISCIP)
_MATIERES = {"0011": "عربية", "0012": "فرنسية", "0017": "أمازيغية"}
# المستويات (CD_NIVENS)
_NIVEAUX = {"101": "1AP", "102": "2AP", "103": "3AP", "104": "4AP", "105": "5AP", "106": "6AP"}
_CYCLES = {"10": "الابتدائي", "00": "الأولي"}
# أسماء الحقول للمراجعة
LIBELLES = {"nom_ar": "النسب", "prenom_ar": "الاسم", "nom_fr": "النسب (فرنسية)", "prenom_fr": "الاسم (فرنسية)",
            "sexe": "النوع", "categorie": "الفئة", "ppr": "رقم التأجير", "cin": "البطاقة الوطنية",
            "cadre": "الإطار", "grade": "الدرجة", "date_grade": "تاريخ الدرجة", "echelon": "الرتبة",
            "date_echelon": "تاريخ الرتبة", "fonction": "المهمة", "cycle": "السلك", "matiere": "مادة التدريس",
            "niveau_enseigne": "المستوى المدرّس", "heures_hebdo": "ساعات العمل", "adresse": "العنوان",
            "telephone": "الهاتف", "date_naissance": "تاريخ الازدياد", "date_recrutement": "تاريخ التوظيف",
            "date_affectation": "تاريخ التعيين بالمؤسسة",
            "date_affectation_direction": "تاريخ التعيين بالمديرية الإقليمية",
            "date_affectation_academie": "تاريخ التعيين بالأكاديمية"}
_NOMS = ("nom_ar", "prenom_ar", "nom_fr", "prenom_fr")
# معطيات يدبّرها المدير محلياً: يملؤها الملف إن كانت فارغة فقط، ولا يغيّرها عند إعادة الاستيراد
# (ملاحظة المدير 2026-11-03: ساعات العمل المدخلة يدوياً كانت تُستبدل بقيمة جدول الخدمة)
LOCAUX = ("heures_hebdo", "niveau_enseigne", "matiere", "cycle", "fonction", "adresse", "telephone")


@dataclass
class Agent:
    """موظف كما قُرئ من الملف (الحقول المعروفة فقط) مع ملاحظات القراءة."""
    valeurs: dict
    notes: list[str] = field(default_factory=list)

    @property
    def nom(self) -> str:
        v = self.valeurs
        return " ".join(x for x in (v.get("prenom_ar"), v.get("nom_ar")) if x) or \
            " ".join(x for x in (v.get("prenom_fr"), v.get("nom_fr")) if x) or v.get("ppr", "")


@dataclass
class Proposition:
    agent: Agent
    etat: str                       # nouveau | maj | identique | ignore | erreur
    pid: int | None = None
    changements: list[tuple[str, str, str]] = field(default_factory=list)   # (الحقل، القديم، الجديد)
    raison: str = ""
    personnel: rh.Personnel | None = None


def _txt(e: ET.Element, tag: str) -> str:
    c = e.find(tag)
    return " ".join((c.text or "").split()) if c is not None else ""


def _date(v: str) -> str:
    """«2019-09-01T00:00:00+01:00» ← «2019-09-01» (التاريخ المحلي كما في الملف)."""
    return v[:10] if len(v) >= 10 and v[4] == "-" and v[7] == "-" else ""


def _separer(nom: str) -> tuple[str, str]:
    """NOML (بالفرنسية): النسب ثم الاسم؛ الكلمة الأخيرة اسم وما قبلها نسب (EL MOUSTAID ...)."""
    mots = nom.split()
    if len(mots) < 2:
        return nom, ""
    return " ".join(mots[:-1]), mots[-1]


def _separer_ar(nom: str) -> tuple[str, str]:
    """NOMA (بالعربية): الاسم ثم النسب (عكس الخانة الفرنسية، تصحيح المدير 2026-11-03)؛ الكلمة الأولى اسم
    وما بعدها نسب. يرجع (النسب، الاسم)."""
    mots = nom.split()
    if len(mots) < 2:
        return nom, ""
    return " ".join(mots[1:]), mots[0]


def _grade(ll: str) -> str:
    s = ll.upper()
    if "HORS" in s or "EXCEP" in s:
        return "الدرجة الممتازة"
    if "1ER" in s or "1ERE" in s:
        return "الدرجة الأولى"
    if "2EME" in s or "2ÈME" in s:
        return "الدرجة الثانية"
    return ""


def lire_xml(source) -> list[Agent]:
    """source: مسار الملف أو محتواه (bytes)."""
    try:
        brut = source if isinstance(source, bytes) else open(source, "rb").read()
    except OSError as e:
        raise ErreurImportRH(f"تعذر فتح الملف: {e}") from None
    if b"<!DOCTYPE" in brut[:4096] or b"<!ENTITY" in brut:
        raise ErreurImportRH("الملف يتضمن تعريفات غير مقبولة (DOCTYPE).")
    try:
        racine = ET.fromstring(brut)
    except ET.ParseError:
        raise ErreurImportRH("الملف ليس ملف XML صالحاً.") from None
    lignes = racine.findall("DATAIDENTIFPERSONNEL")
    if not lignes:
        raise ErreurImportRH("لم يُعثر على معطيات الموظفين في الملف (DATAIDENTIFPERSONNEL). "
                             "تأكد أنه ملف تصدير الموارد البشرية.")

    def ref(tag: str, cle: str) -> dict[str, ET.Element]:
        return {_txt(e, cle): e for e in racine.findall(tag)}

    grades, fonctions = ref("R_GRADE", "CD_GRADE"), ref("R_FONCT", "CD_Fonc")
    activites = {_txt(e, "CD_ACTIVITES"): e for e in racine.findall("ACTIVITE")}
    service: dict[str, list[ET.Element]] = {}
    for e in racine.findall("R_TABSERV"):
        service.setdefault(_txt(e, "CD_ACTIVITES"), []).append(e)

    agents = []
    for e in lignes:
        v: dict = {}
        notes: list[str] = []
        v["ppr"] = _txt(e, "PPR")
        v["cin"] = (_txt(e, "CINA") + _txt(e, "CINN")).replace(" ", "").upper()
        if _txt(e, "PRENOMA"):
            v["nom_ar"], v["prenom_ar"] = _txt(e, "NOMA"), _txt(e, "PRENOMA")
        else:
            v["nom_ar"], v["prenom_ar"] = _separer_ar(_txt(e, "NOMA"))
        if _txt(e, "PRENOML"):
            v["nom_fr"], v["prenom_fr"] = _txt(e, "NOML"), _txt(e, "PRENOML")
        else:
            v["nom_fr"], v["prenom_fr"] = _separer(_txt(e, "NOML"))
        g = _txt(e, "GENRE").upper()
        v["sexe"] = g if g in ("M", "F") else ""
        j, m, a = _txt(e, "JOUR_NAIS"), _txt(e, "MOIS_NAIS"), _txt(e, "AN_NAIS")
        if j.isdigit() and m.isdigit() and a.isdigit():
            v["date_naissance"] = f"{int(a):04d}-{int(m):02d}-{int(j):02d}"
        v["date_recrutement"] = _date(_txt(e, "DATE_REC"))
        adresse = _txt(e, "ADRESSE")
        ville = _txt(e, "VILLE")
        if adresse:
            v["adresse"] = adresse if not ville or ville.lower() in adresse.lower() else f"{adresse} {ville}"
        tel = _txt(e, "TEL_PORTABLE") or _txt(e, "TEL_FIXE")
        v["telephone"] = tel.replace(" ", "").replace(".", "").replace("-", "")

        cadre = _txt(e, "CD_CADRE")
        v["cadre"] = _CORPS.get(cadre[:4], "")
        if cadre and not v["cadre"]:
            notes.append("الإطار غير معروف في قائمة التطبيق؛ يُحدَّد يدوياً.")
        ll_grade = _txt(grades[_txt(e, "CD_GRADE")], "LL_GRADE") if _txt(e, "CD_GRADE") in grades else ""
        v["grade"] = _grade(ll_grade)
        if ll_grade and not v["grade"]:
            notes.append(f"الدرجة «{ll_grade}» غير موجودة في قائمة التطبيق؛ تُحدَّد يدوياً.")
        if v["grade"]:
            v["date_grade"] = _date(_txt(e, "DT_GRADE")) or _date(_txt(e, "ANC_GRADE"))
        ech = _txt(e, "ECHELON")
        if ech.isdigit():
            v["echelon"] = ech if 1 <= int(ech) <= 10 else "الاستثنائية" if int(ech) > 10 else ""
            v["date_echelon"] = _date(_txt(e, "DT_ECHELON"))

        act = activites.get(_txt(e, "CD_LAST_ACTIVITES"))
        cd_fonc = (_txt(act, "CD_FONC") if act is not None else "") or _txt(e, "CD_LAST_FONC")
        drapeau = _txt(fonctions[cd_fonc], "Flag") if cd_fonc in fonctions else ""
        if cd_fonc.startswith("D"):
            v["categorie"] = "directeur"
        elif drapeau == "EN" or cd_fonc.startswith("E"):
            v["categorie"] = "enseignant"
        elif cadre[:4] == "1109":
            v["categorie"] = "enseignant"
        else:
            v["categorie"] = "autre"
            notes.append("المهمة غير معروفة؛ الفئة «آخرون» تُصحَّح يدوياً عند الحاجة.")
        v["fonction"] = rh.fonction_par_defaut(v["categorie"])
        if act is not None:
            v["date_affectation"] = _date(_txt(act, "DT_AFF_ETAB"))
            v["date_affectation_direction"] = _date(_txt(act, "DT_AFF_PROV"))
            v["date_affectation_academie"] = _date(_txt(act, "DT_AFF_REG"))
            if v["date_affectation_direction"] and v["date_affectation_direction"] < rh.DATE_REFERENCE_ACADEMIES:
                v["date_affectation_academie"] = rh.DATE_REFERENCE_ACADEMIES
            if v["categorie"] != "directeur":
                v["cycle"] = _CYCLES.get(_txt(act, "CD_CYCLE"), "")

        if v["categorie"] == "enseignant":
            lignes_srv = service.get(_txt(e, "CD_LAST_ACTIVITES"), [])
            mats = {_MATIERES.get(_txt(s, "CD_DISCIP")) for s in lignes_srv} - {None}
            if not mats and _txt(e, "CD_DISCIP") in _MATIERES:
                mats = {_MATIERES[_txt(e, "CD_DISCIP")]}
            if {"عربية", "فرنسية"} <= mats:
                v["matiere"] = "مزدوجة"
            elif len(mats) == 1:
                v["matiere"] = mats.pop()
            niveaux = sorted({_NIVEAUX[_txt(s, "CD_NIVENS")] for s in lignes_srv
                              if _txt(s, "CD_NIVENS") in _NIVEAUX})
            if niveaux:
                v["niveau_enseigne"] = "، ".join(tx.niveau_ar(n) for n in niveaux)
            heures = 0.0
            for s in lignes_srv:
                try:
                    heures += float(_txt(s, "NBR_HEURE_ENS") or 0) + float(_txt(s, "NBR_HEURE_SUP") or 0)
                except ValueError:
                    pass
            if heures:
                v["heures_hebdo"] = int(round(heures))
        agents.append(Agent({k: x for k, x in v.items() if x not in ("", None)}, notes))
    return agents


def _existant(conn: sqlite3.Connection, v: dict) -> int | None:
    for k in ("ppr", "cin"):
        if v.get(k):
            r = conn.execute(f"SELECT id FROM personnel WHERE {k}=?", (v[k],)).fetchone()
            if r:
                return r[0]
    return None


def _affiche(k: str, x) -> str:
    if x in (None, ""):
        return ""
    if k == "sexe":
        return {"M": "ذكر", "F": "أنثى"}.get(x, x)
    if k == "categorie":
        return rh.CATEGORIES.get(x, ("",))[0]
    return str(x)


def comparer(conn: sqlite3.Connection, agents: list[Agent]) -> list[Proposition]:
    res = []
    for a in agents:
        v = a.valeurs
        pid = _existant(conn, v)
        if pid is None:
            if v.get("categorie") == "directeur":
                res.append(Proposition(a, "ignore", raison="المدير يُسجَّل من «إعداد المؤسسة»؛ أضف رقم تأجيره "
                                                            "هناك ثم أعد الاستيراد لإتمام ملفه."))
                continue
            p = rh.Personnel(**{k: x for k, x in v.items()})
            changements = [(LIBELLES.get(k, k), "", _affiche(k, x)) for k, x in v.items()]
            etat = "nouveau"
        else:
            ancien = rh.lire(conn, pid)
            p = replace(ancien, classes=list(ancien.classes))
            changements = []
            inverse = {k for a, b in (("nom_ar", "prenom_ar"), ("nom_fr", "prenom_fr"))
                       if v.get(a) and v.get(b) and getattr(ancien, a) == v[b] and getattr(ancien, b) == v[a]
                       for k in (a, b)}   # استيراد سابق قلب النسب والاسم: يُصحَّح
            for k, x in v.items():
                if k in _NOMS and getattr(ancien, k) and k not in inverse:
                    continue
                if k == "categorie" and (ancien.categorie == "directeur" or x == "directeur"
                                         or x == "autre"):
                    continue
                if k in LOCAUX and getattr(ancien, k) not in ("", None):
                    continue
                avant = getattr(ancien, k)
                if str(avant if avant is not None else "") != str(x):
                    setattr(p, k, x)
                    changements.append((LIBELLES.get(k, k), _affiche(k, avant), _affiche(k, x)))
            etat = "maj" if changements else "identique"
        try:
            rh.Personnel.valider(replace(p, classes=list(p.classes)))
        except rh.ErreurPersonnel as e:
            res.append(Proposition(a, "erreur", pid, changements, str(e), p))
            continue
        res.append(Proposition(a, etat, pid, changements, "", p))
    return res


def appliquer(conn: sqlite3.Connection, propositions: list[Proposition]) -> dict[str, int]:
    """يعتمد الاقتراحات المختارة (nouveau / maj). يرجع عدد المضافين والمحدَّثين."""
    n = {"ajoutes": 0, "maj": 0}
    for pr in propositions:
        if pr.etat not in ("nouveau", "maj") or pr.personnel is None:
            continue
        rh.enregistrer(conn, pr.personnel)
        n["ajoutes" if pr.etat == "nouveau" else "maj"] += 1
    return n
