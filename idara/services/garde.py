"""الحراسة التربوية بالمناطق (توجيه المدير 2026-11-15، ونماذجه: «الحراسة»، «جدول الحراسة»، «تصميم المؤسسة»).

- تُقسَّم المؤسسة إلى مناطق (من 1 إلى 10)، لكل منطقة اسم اختياري (الساحة الشمالية، الباب الرئيسي...).
- دورة من 1 إلى 4 أسابيع تتكرر؛ في كل يوم دراسي أستاذ(ة) أمام كل منطقة، ولا يحرس الأستاذ منطقتين في اليوم نفسه.
- التوزيع الآلي يدير الأساتذة دوراً بعد دور، فتتساوى أيام الحراسة (بفارق يوم على الأكثر) وتتناوب المناطق.
- «حراسة اليوم»: الأسبوع من الدورة يُحسب من تاريخ بداية الدورة (أسابيع تقويمية متتالية)؛ الأحد والعطل والأعياد
  المسجلة في المقرر الوزاري أو محلياً لا حراسة فيها.
- الوثائق: جدول الحراسة (أسبوع في كل جدول)، المذكرة الداخلية بتوقيعات الأساتذة بعد الاطلاع، ورقة حراسة اليوم.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from idara.data.dossier import DossierDonnees
from idara.services import annee as annee_srv
from idara.services import etablissement as etab_srv
from idara.services import fiches
from idara.services import personnel as rh
from idara.services import textes as tx

JOURS = ("الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت")
ZONES_MAX, SEMAINES_MAX = 10, 4
REGLES = (
    "يعتبر الحفاظ على سلامة التلاميذ من مهام المؤسسة التربوية منذ ولوجهم إلى المؤسسة إلى لحظة خروجهم (حسب "
    "استعمال الزمن المصادق عليه) وبما في ذلك أثناء فترات الاستراحة.\n"
    "يحضر السيدات والسادة الأستاذات والأساتذة المكلفون بالحراسة عشر دقائق قبل بداية أول حصة دراسية.\n"
    "فور دخول التلاميذ إلى ساحة المؤسسة يقفون صفوفاً حسب أفواجهم، ويحرص الأساتذة المكلفون بالحراسة على تنظيم "
    "العملية، وبعد قرع الجرس يرافق كل أستاذ تلامذته إلى الحجرة الدراسية ويعتبرون منذ هذه اللحظة تحت مسؤوليته، كما "
    "يحرص على مرافقتهم بنظام عند خروجهم إلى الاستراحة ورجوعهم منها، وبعد نهاية الحصص الدراسية المقررة.\n"
    "يتم تنظيم عملية الخروج من المؤسسة بوقوف التلاميذ بشكل منتظم ثم يغادرون حسب المستويات الدراسية، مع تجنب "
    "الازدحام والجري.\n"
    "أثناء الاستراحة يجب الحرص على تجنب الألعاب العنيفة والجري والمشاجرات.")
REFERENCES = ("المادة 85 مكرر من قانون الالتزامات والعقود المغربي.", "المذكرة الوزارية 70/1 بتاريخ: 01/09/2011")


class ErreurGarde(ValueError):
    """رسالة موجهة للمدير بالعربية."""


def _cle(unite: str) -> str:
    return f"garde_zones:{unite}"


def _propre(v) -> str:
    return " ".join(str(v or "").split())


def libelle_zone(zones: list[str], k: int) -> str:
    return f"المنطقة {k + 1}" + (f": {zones[k]}" if k < len(zones) and zones[k] else "")


def _grille_vide(semaines: int, jours: list[str], nz: int, ancienne: dict | None = None) -> dict:
    ancienne = ancienne or {}
    g = {}
    for s in range(1, semaines + 1):
        a = ancienne.get(str(s)) or {}
        g[str(s)] = {j: [_propre(x) for x in (list(a.get(j) or []) + [""] * nz)[:nz]] for j in jours}
    return g


def lire(conn: sqlite3.Connection, unite: str = "") -> dict:
    d = fiches.lire(conn, _cle(unite)) or {}
    nz = min(ZONES_MAX, max(1, int(d.get("nb_zones") or 4)))
    zones = [_propre(z) for z in (list(d.get("zones") or []) + [""] * nz)[:nz]]
    semaines = min(SEMAINES_MAX, max(1, int(d.get("semaines") or 4)))
    jours = [j for j in JOURS if j in (d.get("jours") or JOURS)] or list(JOURS)
    return {"nb_zones": nz, "zones": zones, "semaines": semaines, "jours": jours, "debut": d.get("debut") or "",
            "grille": _grille_vide(semaines, jours, nz, d.get("grille")),
            "consignes": d.get("consignes", REGLES)}


def enregistrer(conn: sqlite3.Connection, donnees: dict, unite: str = "") -> None:
    try:
        nz, semaines = int(donnees.get("nb_zones") or 0), int(donnees.get("semaines") or 0)
    except (TypeError, ValueError):
        raise ErreurGarde("عدد المناطق والأسابيع أرقام.") from None
    if not 1 <= nz <= ZONES_MAX:
        raise ErreurGarde(f"عدد المناطق من 1 إلى {ZONES_MAX}.")
    if not 1 <= semaines <= SEMAINES_MAX:
        raise ErreurGarde(f"دورة الحراسة من أسبوع واحد إلى {SEMAINES_MAX} أسابيع.")
    jours = [j for j in JOURS if j in (donnees.get("jours") or [])]
    if not jours:
        raise ErreurGarde("اختر يوم حراسة واحداً على الأقل.")
    debut = str(donnees.get("debut") or "")
    if debut:
        try:
            date.fromisoformat(debut)
        except ValueError:
            raise ErreurGarde("تاريخ بداية الدورة غير صحيح.") from None
    grille = _grille_vide(semaines, jours, nz, donnees.get("grille"))
    for s, js in grille.items():
        for j, noms in js.items():
            vus = [n for n in noms if n]
            double = next((n for n in vus if vus.count(n) > 1), None)
            if double:
                raise ErreurGarde(f"«{double}» مكلف(ة) بمنطقتين يوم {j} من الأسبوع {s}.")
    zones = [_propre(z) for z in (list(donnees.get("zones") or []) + [""] * nz)[:nz]]
    fiches.ecrire(conn, _cle(unite), {"nb_zones": nz, "zones": zones, "semaines": semaines, "jours": jours,
                                      "debut": debut, "grille": grille,
                                      "consignes": str(donnees.get("consignes") or "").strip()})


def enseignants(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    """(الاسم الكامل، رقم التأجير) للأساتذة النشيطين، بترتيب لائحة الموارد البشرية."""
    return [(f"{p.nom_ar} {p.prenom_ar}".strip(), p.ppr or "") for p in rh.lister(conn, categorie="enseignant")]


def repartir(noms: list[str], nb_zones: int, semaines: int, jours: list[str]) -> dict:
    """توزيع عادل: الأساتذة يتعاقبون دوراً بعد دور على (الأسبوع، اليوم، المنطقة)."""
    noms = [n for n in dict.fromkeys(_propre(n) for n in noms) if n]
    if len(noms) < nb_zones:
        raise ErreurGarde(f"عدد الأساتذة ({len(noms)}) أقل من عدد المناطق ({nb_zones}): قلّص المناطق أو أضف أساتذة.")
    g, k = {}, 0
    for s in range(1, semaines + 1):
        g[str(s)] = {}
        for j in jours:
            g[str(s)][j] = [noms[(k + z) % len(noms)] for z in range(nb_zones)]
            k += nb_zones
    return g


def bilan(conn: sqlite3.Connection, unite: str = "") -> list[tuple[str, int]]:
    """أيام الحراسة لكل أستاذ خلال الدورة."""
    g = lire(conn, unite)
    n: dict[str, int] = {}
    for js in g["grille"].values():
        for noms in js.values():
            for nom in noms:
                if nom:
                    n[nom] = n.get(nom, 0) + 1
    return sorted(n.items(), key=lambda x: (-x[1], x[0]))


def semaine_de(g: dict, jour: date) -> int:
    if not g["debut"]:
        return 1
    lundi = date.fromisoformat(g["debut"])
    lundi -= timedelta(days=lundi.weekday())
    return ((jour - lundi).days // 7) % g["semaines"] + 1


def _ferie(conn, jour: date) -> str:
    from idara.services import calendrier as cal
    try:
        s = next((x for x in cal.stations(conn) if x.type in ("conge", "fete") and x.debut <= jour <= x.fin), None)
    except Exception:  # noqa: BLE001 (المقرر غير متوفر: لا يمنع عرض الحراسة)
        return ""
    return s.titre if s else ""


def du_jour(conn: sqlite3.Connection, jour: date | None = None, unite: str = "") -> dict:
    """{date، اليوم، الأسبوع، الأسطر [(المنطقة، الأستاذ)]، السبب إن لم تكن حراسة}."""
    jour = jour or date.today()
    g = lire(conn, unite)
    nom_jour = JOURS[jour.weekday()] if jour.weekday() < 6 else "الأحد"
    res = {"date": jour, "jour": nom_jour, "semaine": None, "lignes": [], "motif": ""}
    if jour.weekday() == 6:
        res["motif"] = "يوم الأحد: لا حراسة."
        return res
    ferie = _ferie(conn, jour)
    if ferie:
        res["motif"] = f"لا حراسة: {ferie}."
        return res
    if nom_jour not in g["jours"]:
        res["motif"] = f"لا حراسة مبرمجة يوم {nom_jour}."
        return res
    s = semaine_de(g, jour)
    noms = g["grille"][str(s)][nom_jour]
    res["semaine"] = s
    res["lignes"] = [(libelle_zone(g["zones"], k), n) for k, n in enumerate(noms)]
    if not any(noms):
        res["motif"] = "جدول الحراسة لم يُملأ بعد."
    return res


# ====================== الوثائق ======================

def _sauver(d, dossier: DossierDonnees, nom: str) -> Path:
    r = dossier.archives / "الحراسة"
    r.mkdir(parents=True, exist_ok=True)
    chemin = r / f"{datetime.now():%Y%m%d_%H%M%S}_{nom}.docx"
    n = 1
    while chemin.exists():
        n += 1
        chemin = chemin.with_name(f"{chemin.stem}_{n}.docx")
    d.save(chemin)
    return chemin


def _vide(g: dict) -> bool:
    return not any(n for js in g["grille"].values() for noms in js.values() for n in noms)


DOCS = {"tableau": "جدول الحراسة", "note": "المذكرة الداخلية في شأن الحراسة", "jour": "ورقة حراسة اليوم"}


def generer(conn: sqlite3.Connection, dossier: DossierDonnees, doc: str, unite: str = "",
            jour: date | None = None) -> Path:
    if doc not in DOCS:
        raise ErreurGarde("وثيقة غير معروفة.")
    g = lire(conn, unite)
    if doc != "note" and _vide(g):
        raise ErreurGarde("جدول الحراسة فارغ: وزّع الأساتذة آلياً أو اكتب أسماءهم في الجدول.")
    return {"tableau": _tableau, "note": _note, "jour": _jour}[doc](conn, dossier, g, unite, jour)


def _tableau(conn, dossier, g, unite, _jour) -> Path:
    from docx.shared import Cm

    from idara.services.docs_association import _nouveau, para, saut_page
    from idara.services.soutien import _entete, _signature, _table
    a = annee_srv.annee_courante(conn)
    nz = g["nb_zones"]
    paysage = nz > 4
    d = _nouveau(paysage)
    s = d.sections[0]
    s.top_margin = s.bottom_margin = Cm(1.0)
    s.left_margin = s.right_margin = Cm(1.2)
    largeur = 27.0 if paysage else 18.4
    sous = " · ".join(x for x in (unite, f"السنة الدراسية {a['libelle']}" if a else "",
                                  f"دورة من {g['semaines']} أسابيع" if g["semaines"] > 1 else "") if x)
    entetes = ["اليوم", *[libelle_zone(g["zones"], k) for k in range(nz)]]
    larg = [2.6] + [round((largeur - 2.6) / nz, 2)] * nz
    for i, (sem, js) in enumerate(g["grille"].items()):
        if i:
            saut_page(d)
        _entete(d, conn, dossier, "جدول الحراسة التربوية", sous)
        if g["semaines"] > 1:
            para(d, f"الأسبوع {sem}", gras=True, taille=13, centre=True, apres=4)
        _table(d, entetes, [[j, *js[j]] for j in g["jours"]], larg, taille=10 if nz <= 6 else 9)
    b = bilan(conn, unite)
    if b:
        para(d, "", apres=4)
        para(d, "أيام الحراسة لكل أستاذ(ة) خلال الدورة: " + "، ".join(f"{n} ({k})" for n, k in b), taille=9,
             apres=0)
    _signature(d, conn)
    return _sauver(d, dossier, "جدول_الحراسة" + (f"_{unite}" if unite else ""))


def _note(conn, dossier, g, unite, _jour) -> Path:
    from idara.services.docs_association import _nouveau, para, saut_page
    from idara.services.soutien import _entete, _table
    etab = etab_srv.lire_etablissement(conn)
    d = _nouveau()
    _entete(d, conn, dossier, "مذكرة داخلية", "")
    ville = (etab.ville_redaction_ar or etab.commune_ar) if etab else ""
    para(d, (f"{ville}، في: " if ville else "في: ") + tx.date_ar(date.today()), taille=11, apres=4)
    para(d, "من مدير(ة) " + (etab.nom_ar if etab else "المؤسسة"), gras=True, taille=12, apres=0)
    para(d, "إلى السيدات والسادة الأستاذات والأساتذة", gras=True, taille=12, apres=6)
    para(d, "الموضوع: في شأن تدبير الحراسة التربوية بالمؤسسة.", gras=True, taille=12, apres=2)
    para(d, "المرجع: " + REFERENCES[0], taille=11, apres=0)
    for r in REFERENCES[1:]:
        para(d, "             " + r, taille=11, apres=0)
    para(d, "", apres=2)
    para(d, "سلام تام بوجود مولانا الإمام، وبعد،", taille=12, apres=2)
    para(d, "وعلاقة بالموضوع المشار إليه أعلاه، يشرفني أن أوافيكم ببعض المقتضيات المتعلقة بتدبير الحراسة التربوية "
            "بالمؤسسة:", taille=12, apres=2)
    for l in (g["consignes"] or REGLES).splitlines():
        if l.strip():
            para(d, "- " + l.strip(), taille=12, apres=1)
    para(d, "ومن أجل نجاعة عملية الحراسة وضمان سلامة التلاميذ يرجى من السيدات والسادة الأستاذات والأساتذة جميعاً "
            "الحضور في الوقت وعدم ترك التلاميذ بمفردهم في قاعة الدرس.", taille=12, apres=4)
    para(d, "المرفقات:", gras=True, taille=11, apres=0)
    para(d, "- جدول الحراسة.", taille=11, apres=0)
    para(d, "- تصميم المؤسسة وتحديد مناطق الحراسة.", taille=11, apres=6)
    para(d, "مدير(ة) المؤسسة", gras=True, taille=12, apres=0)
    saut_page(d)
    para(d, "توقيعات السيدات الأستاذات والأساتذة بعد الاطلاع", gras=True, taille=13, centre=True, apres=6)
    profs = enseignants(conn) or [("", "")] * 10
    _table(d, ["ر.ت", "الاسم الكامل", "رقم التأجير", "التوقيع"],
           [[f"{i:02d}", n, f"⁦{p}⁩" if p else "", ""] for i, (n, p) in enumerate(profs, 1)],
           [1.3, 7.0, 3.6, 5.5], taille=11)
    if any(g["zones"]):
        para(d, "", apres=4)
        para(d, "مناطق الحراسة", gras=True, taille=12, apres=2)
        _table(d, ["المنطقة", "التحديد"], [[f"{k + 1}", z] for k, z in enumerate(g["zones"])], [3.0, 14.4], taille=11)
    return _sauver(d, dossier, "مذكرة_الحراسة")


def _jour(conn, dossier, g, unite, jour) -> Path:
    from idara.services.docs_association import _nouveau, para
    from idara.services.soutien import _entete, _signature, _table
    j = du_jour(conn, jour, unite)
    if not j["lignes"] or not any(n for _, n in j["lignes"]):
        raise ErreurGarde(j["motif"] or "لا حراسة في هذا اليوم.")
    d = _nouveau()
    _entete(d, conn, dossier, "الحراسة التربوية لهذا اليوم",
            f"{j['jour']} {tx.date_ar(j['date'])}" + (f" · الأسبوع {j['semaine']} من الدورة" if g["semaines"] > 1
                                                       else ""))
    _table(d, ["المنطقة", "الأستاذ(ة) المكلف(ة)", "ملاحظة"], [[z, n, ""] for z, n in j["lignes"]],
           [6.0, 6.4, 5.0], taille=13)
    para(d, "", apres=4)
    para(d, "الحضور عشر دقائق قبل بداية أول حصة، والتلاميذ تحت المسؤولية إلى لحظة خروجهم.", taille=11, apres=0)
    _signature(d, conn)
    return _sauver(d, dossier, f"حراسة_{j['date']:%Y%m%d}")
