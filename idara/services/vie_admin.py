"""أربع صفحات إدارية أُضيفت بعد مقارنة 2026-11-13 (وافق المدير عليها كلها):

1. الوثائق القانونية للجمعيات (جمعية النجاح، الجمعية الرياضية، جمعية الآباء، التعاونية المدرسية): أعضاء المكتب،
   تصريح بتجديد المكتب، لائحة الأعضاء، محضر الجمع العام. الموقّع هو رئيس الجمعية لا المدير.
2. جدول الحراسة: الأيام × فترات الحراسة، في كل خانة الأساتذة المكلفون.
3. النقل المدرسي: وسائل النقل (الرقم، السائق، الهاتف، المسار، الدواوير) والمستفيدون، لائحة لكل وسيلة.
4. استعمالات الزمن: حصص كل أستاذ (اليوم، من، إلى، المادة، المستوى)، مراقبة الحصيص الأسبوعي والتعارض،
   وثيقة استعمال الزمن، وتغذية لوحة «استعمال الزمن الجماعي» في السبورة المرجعية.

صياغات الوثائق القانونية عامة (لا نموذج رسمي بين يدي): تُراجع وتُعدَّل في Word قبل الإيداع.
الحصيص الأسبوعي للمواد لا يُفترض: يدخله المدير مرة واحدة حسب المنهاج المعتمد عنده.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from idara.data.dossier import DossierDonnees
from idara.services import annee as annee_srv
from idara.services import etablissement as etab_srv
from idara.services import fiches
from idara.services import personnel as rh
from idara.services import textes as tx


class ErreurVieAdmin(ValueError):
    """رسالة موجهة للمدير بالعربية."""


def _sauver(d, dossier: DossierDonnees, rep: str, nom: str) -> Path:
    r = dossier.archives / rep
    r.mkdir(parents=True, exist_ok=True)
    chemin = r / f"{datetime.now():%Y%m%d_%H%M%S}_{nom}.docx"
    n = 1
    while chemin.exists():
        n += 1
        chemin = chemin.with_name(f"{chemin.stem}_{n}.docx")
    d.save(chemin)
    return chemin


def _propre(lignes, n: int) -> list[list[str]]:
    res = []
    for l in lignes or []:
        l = [" ".join(str(v if v is not None else "").split()) for v in l][:n]
        l += [""] * (n - len(l))
        if any(l):
            res.append(l)
    return res


def _date(v: str) -> str:
    try:
        return tx.date_ar(v) if v else ""
    except (ValueError, TypeError):
        return v or ""


# ====================== 1. الوثائق القانونية للجمعيات ======================

ASSOCIATIONS = {"najah": "جمعية دعم مدرسة النجاح", "sportive": "الجمعية الرياضية المدرسية",
                "parents": "جمعية آباء وأمهات وأولياء التلاميذ", "cooperative": "جمعية تنمية التعاون المدرسي"}
COLS_BUREAU = ("الاسم الكامل", "المهمة", "رقم البطاقة الوطنية", "المهنة", "العنوان")
ROLES_BUREAU = ("الرئيس", "نائب الرئيس", "الكاتب العام", "نائب الكاتب العام", "أمين المال", "نائب أمين المال",
                "مستشار")
CHAMPS_ASSO = (("date_ag", "تاريخ الجمع العام"), ("heure", "ساعة الانعقاد"), ("lieu", "مكان الانعقاد"),
               ("presents", "عدد الحاضرين"), ("siege", "مقر الجمعية"), ("autorite", "السلطة المحلية المودع لديها"),
               ("ordre", "جدول الأعمال (نقطة في كل سطر)"), ("deroulement", "مجريات الجمع العام"))


def lire_asso(conn: sqlite3.Connection, cle: str) -> dict:
    if cle not in ASSOCIATIONS:
        raise ErreurVieAdmin("جمعية غير معروفة.")
    d = fiches.lire(conn, f"asso:{cle}")
    if d is None:
        e = etab_srv.lire_etablissement(conn)
        d = {"champs": {"siege": e.nom_ar if e else "", "lieu": e.nom_ar if e else "",
                        "ordre": "قراءة التقريرين الأدبي والمالي والمصادقة عليهما\nتجديد مكتب الجمعية"},
             "membres": [["", r, "", "", ""] for r in ROLES_BUREAU]}
        a = conn.execute("SELECT president, tresorier FROM association WHERE type=?", (cle,)).fetchone() \
            if cle in ("najah", "sportive", "cooperative") else None
        if a:
            d["membres"][0][0] = a["president"] or ""
            d["membres"][4][0] = a["tresorier"] or ""
    d["membres"] = _propre(d.get("membres"), len(COLS_BUREAU))
    d.setdefault("champs", {})
    return d


def enregistrer_asso(conn: sqlite3.Connection, cle: str, donnees: dict) -> None:
    if cle not in ASSOCIATIONS:
        raise ErreurVieAdmin("جمعية غير معروفة.")
    ch = {k: str(v or "").strip() for k, v in donnees.get("champs", {}).items()}
    fiches.ecrire(conn, f"asso:{cle}", {"champs": ch, "membres": _propre(donnees.get("membres"), len(COLS_BUREAU))})


def personnel_pour_bureau(conn: sqlite3.Connection) -> list[list[str]]:
    """لائحة العاملين بالمؤسسة لاختيار أعضاء المكتب منها."""
    return [[f"{p.prenom_ar} {p.nom_ar}", "", p.cin or "", rh.libelle_categorie(p.categorie, p.sexe), p.adresse or ""]
            for p in rh.lister(conn)]


DOCS_ASSO = {"declaration": "تصريح بتجديد المكتب", "liste": "لائحة أعضاء المكتب", "pv": "محضر الجمع العام"}


def generer_asso(conn: sqlite3.Connection, dossier: DossierDonnees, cle: str, doc: str) -> Path:
    from idara.services.docs_association import _nouveau, para
    from idara.services.soutien import _entete, _table
    if doc not in DOCS_ASSO:
        raise ErreurVieAdmin("وثيقة غير معروفة.")
    d0 = lire_asso(conn, cle)
    ch, membres = d0["champs"], [m for m in d0["membres"] if m[0]]
    if not membres:
        raise ErreurVieAdmin("أدخل أعضاء المكتب أولاً (الاسم والمهمة).")
    nom = ASSOCIATIONS[cle]
    e = etab_srv.lire_etablissement(conn)
    etab = e.nom_ar if e else ""
    president = next((m[0] for m in membres if m[1].startswith("الرئيس") or m[1].startswith("رئيس")), membres[0][0])
    d = _nouveau()
    _entete(d, conn, dossier, DOCS_ASSO[doc], f"{nom} · {etab}")
    le = _date(ch.get("date_ag", ""))
    if doc == "declaration":
        para(d, f"إلى السيد: {ch.get('autorite') or ''}", gras=True, taille=12, apres=6)
        para(d, f"الموضوع: تصريح بتجديد مكتب {nom}.", gras=True, taille=12, apres=6)
        para(d, f"سلام تام بوجود مولانا الإمام، وبعد؛ فطبقاً لمقتضيات الظهير الشريف رقم 1.58.376 الصادر في 15 "
                f"نونبر 1958 بتنظيم حق تأسيس الجمعيات كما وقع تغييره وتتميمه، يشرفني أن أصرح لديكم بأن {nom} "
                f"بمؤسسة {etab}، الكائن مقرها بـ{ch.get('siege') or etab}، قد عقدت جمعها العام"
                + (f" بتاريخ {le}" if le else "") + "، وأسفر عن تجديد مكتبها المتكون من السادة والسيدات:",
             taille=12, apres=6)
    elif doc == "pv":
        para(d, f"انعقد الجمع العام لـ{nom} بمؤسسة {etab}" + (f" يوم {le}" if le else "")
             + (f" على الساعة {ch['heure']}" if ch.get("heure") else "")
             + (f" بـ{ch['lieu']}" if ch.get("lieu") else "")
             + (f"، بحضور {ch['presents']} عضواً" if ch.get("presents") else "") + "، وتضمن جدول أعماله:",
             taille=12, apres=2)
        for k, l in enumerate([x.strip() for x in (ch.get("ordre") or "").splitlines() if x.strip()], start=1):
            para(d, f"{k}. {l}", taille=12, apres=0)
        para(d, "", apres=4)
        for l in (ch.get("deroulement") or "").splitlines():
            if l.strip():
                para(d, l.strip(), taille=12, apres=2)
        para(d, "وبعد المناقشة والمصادقة، أسفر الجمع العام عن تشكيل مكتب الجمعية على الشكل التالي:", taille=12,
             apres=6)
    _table(d, ["ر.ت", *COLS_BUREAU] + (["التوقيع"] if doc != "declaration" else []),
           [[f"{i:02d}", *m] + ([""] if doc != "declaration" else []) for i, m in enumerate(membres, start=1)],
           [1.0, 4.4, 3.0, 2.6, 2.6, 3.4] if doc == "declaration" else [1.0, 3.8, 2.6, 2.4, 2.2, 2.6, 2.4], taille=9)
    para(d, "", apres=8)
    ville = (e.ville_redaction_ar or e.commune_ar) if e else ""
    para(d, f"حرر ب{ville}، بتاريخ: {tx.date_ar(datetime.now().date())}", taille=11, apres=4)
    para(d, "رئيس(ة) الجمعية:", gras=True, taille=12, apres=0)
    para(d, president, gras=True, taille=12)
    return _sauver(d, dossier, "الوثائق القانونية للجمعيات", f"{DOCS_ASSO[doc]}_{nom}".replace(" ", "_"))


# ====================== 2. جدول الحراسة ======================

JOURS = ("الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت")
PERIODES_GARDE = ("الدخول الصباحي", "استراحة الصباح", "الخروج الصباحي", "الدخول المسائي", "استراحة المساء",
                  "الخروج المسائي")


def lire_garde(conn: sqlite3.Connection, unite: str = "") -> dict:
    d = fiches.lire(conn, f"garde:{unite}") or {}
    periodes = [p for p in d.get("periodes", PERIODES_GARDE) if p]
    grille = d.get("grille") or {}
    return {"periodes": periodes, "consignes": d.get("consignes", ""),
            "grille": {j: [(grille.get(j) or [""] * len(periodes) + [""] * 9)[k] for k in range(len(periodes))]
                       for j in JOURS}}


def enregistrer_garde(conn: sqlite3.Connection, donnees: dict, unite: str = "") -> None:
    periodes = [" ".join(str(p).split()) for p in donnees.get("periodes", PERIODES_GARDE) if str(p).strip()]
    if not periodes:
        raise ErreurVieAdmin("فترة حراسة واحدة على الأقل.")
    grille = {j: [" ".join(str(v or "").split()) for v in (donnees.get("grille", {}).get(j) or [])][:len(periodes)]
              for j in JOURS}
    for j in JOURS:
        grille[j] += [""] * (len(periodes) - len(grille[j]))
    fiches.ecrire(conn, f"garde:{unite}", {"periodes": periodes, "grille": grille,
                                           "consignes": str(donnees.get("consignes") or "").strip()})


def bilan_garde(conn: sqlite3.Connection, unite: str = "") -> list[tuple[str, int]]:
    """عدد فترات الحراسة لكل أستاذ (للتوزيع العادل)."""
    g = lire_garde(conn, unite)
    n: dict[str, int] = {}
    for j in JOURS:
        for c in g["grille"][j]:
            for nom in c.replace("،", ",").split(","):
                nom = nom.strip()
                if nom:
                    n[nom] = n.get(nom, 0) + 1
    return sorted(n.items(), key=lambda x: (-x[1], x[0]))


def generer_garde(conn: sqlite3.Connection, dossier: DossierDonnees, unite: str = "") -> Path:
    from docx.enum.section import WD_ORIENT
    from docx.shared import Cm

    from idara.services.docs_association import _nouveau, para
    from idara.services.soutien import _entete, _signature, _table
    g = lire_garde(conn, unite)
    if not any(c for j in JOURS for c in g["grille"][j]):
        raise ErreurVieAdmin("جدول الحراسة فارغ: أدخل أستاذاً واحداً على الأقل.")
    a = annee_srv.annee_courante(conn)
    d = _nouveau()
    s = d.sections[0]
    s.orientation = WD_ORIENT.LANDSCAPE
    s.page_width, s.page_height = s.page_height, s.page_width
    s.left_margin = s.right_margin = Cm(1.2)
    s.top_margin = s.bottom_margin = Cm(1.0)
    _entete(d, conn, dossier, "جدول الحراسة", (f"{unite} · " if unite else "") + f"السنة الدراسية {a['libelle']}"
            if a else unite)
    n = len(g["periodes"])
    _table(d, ["اليوم", *g["periodes"]], [[j, *g["grille"][j]] for j in JOURS if any(g["grille"][j])],
           [2.6] + [round(24.2 / n, 2)] * n, taille=10)
    if g["consignes"]:
        para(d, "", apres=4)
        para(d, "توجيهات:", gras=True, taille=11, apres=0)
        for l in g["consignes"].splitlines():
            if l.strip():
                para(d, l.strip(), taille=10, apres=0)
    _signature(d, conn)
    return _sauver(d, dossier, "جدول الحراسة", "جدول_الحراسة" + (f"_{unite}" if unite else ""))


# ====================== 3. النقل المدرسي ======================

COLS_VEHICULE = ("رقم الحافلة أو السيارة", "السائق", "الهاتف", "المسار", "الدواوير")


def lire_transport(conn: sqlite3.Connection) -> dict:
    d = fiches.lire(conn, "transport") or {}
    return {"vehicules": _propre(d.get("vehicules"), len(COLS_VEHICULE)),
            "beneficiaires": {str(k): v for k, v in (d.get("beneficiaires") or {}).items()}}


def enregistrer_transport(conn: sqlite3.Connection, donnees: dict) -> None:
    vs = _propre(donnees.get("vehicules"), len(COLS_VEHICULE))
    nums = [v[0] for v in vs]
    if any(not n for n in nums):
        raise ErreurVieAdmin("رقم الحافلة أو السيارة إجباري في كل سطر.")
    if len(set(nums)) != len(nums):
        raise ErreurVieAdmin("رقم وسيلة النقل مكرر.")
    ben = {}
    for eid, b in (donnees.get("beneficiaires") or {}).items():
        v = " ".join(str(b.get("vehicule") or "").split())
        if not v:
            continue
        if v not in nums:
            raise ErreurVieAdmin(f"وسيلة النقل «{v}» غير موجودة في اللائحة.")
        ben[str(int(eid))] = {"vehicule": v, "douar": " ".join(str(b.get("douar") or "").split())}
    fiches.ecrire(conn, "transport", {"vehicules": vs, "beneficiaires": ben})


def eleves_transport(conn: sqlite3.Connection) -> list[dict]:
    """تلاميذ السنة الجارية مع وسيلة نقلهم ودوارهم (إن سُجلا)."""
    a = annee_srv.annee_courante(conn)
    if a is None:
        return []
    ben = lire_transport(conn)["beneficiaires"]
    res = []
    for r in conn.execute("SELECT e.id, e.prenom_ar, e.nom_ar, e.code_massar, c.code AS classe FROM inscription i "
                          "JOIN eleve e ON e.id=i.eleve_id LEFT JOIN classe c ON c.id=i.classe_id WHERE i.annee_id=? "
                          "AND i.statut IN ('inscrit','arrive') ORDER BY c.code, e.nom_ar, e.prenom_ar", (a["id"],)):
        b = ben.get(str(r["id"]), {})
        res.append({"eleve_id": r["id"], "eleve": f"{r['prenom_ar']} {r['nom_ar']}", "code": r["code_massar"],
                    "classe": r["classe"] or "", "vehicule": b.get("vehicule", ""), "douar": b.get("douar", "")})
    return res


def stats_transport(conn: sqlite3.Connection) -> dict:
    ls = [x for x in eleves_transport(conn) if x["vehicule"]]
    par_v, par_d = {}, {}
    for x in ls:
        par_v[x["vehicule"]] = par_v.get(x["vehicule"], 0) + 1
        par_d[x["douar"] or "غير محدد"] = par_d.get(x["douar"] or "غير محدد", 0) + 1
    return {"total": len(ls), "vehicules": par_v, "douars": dict(sorted(par_d.items(), key=lambda x: -x[1]))}


def generer_transport(conn: sqlite3.Connection, dossier: DossierDonnees, vehicule: str | None = None) -> Path:
    """لائحة المستفيدين لكل وسيلة نقل (صفحة لكل وسيلة)، ثم إحصاء الدواوير. دون توقيع المدير: النقل تسيّره جمعيته."""
    from idara.services.docs_association import _nouveau, para, saut_page
    from idara.services.soutien import _entete, _table
    t = lire_transport(conn)
    ls = eleves_transport(conn)
    vs = [v for v in t["vehicules"] if (vehicule is None or v[0] == vehicule) and any(x["vehicule"] == v[0] for x in ls)]
    if not vs:
        raise ErreurVieAdmin("لا مستفيدين مسجلين" + (f" في «{vehicule}»" if vehicule else "") + ".")
    a = annee_srv.annee_courante(conn)
    d = _nouveau()
    for k, v in enumerate(vs):
        if k:
            saut_page(d)
        ben = [x for x in ls if x["vehicule"] == v[0]]
        _entete(d, conn, dossier, "لائحة المستفيدين من النقل المدرسي", f"السنة الدراسية {a['libelle']}")
        para(d, f"وسيلة النقل: {v[0]}" + (f" · السائق: {v[1]}" if v[1] else "") + (f" · الهاتف: {v[2]}" if v[2] else ""),
             gras=True, taille=11, apres=0)
        if v[3] or v[4]:
            para(d, " · ".join(x for x in ((f"المسار: {v[3]}" if v[3] else ""), (f"الدواوير: {v[4]}" if v[4] else ""))
                               if x), taille=10, apres=4)
        _table(d, ["ر.ت", "التلميذ(ة)", "رمز مسار", "القسم", "الدوار"],
               [[f"{i:02d}", x["eleve"], x["code"], x["classe"], x["douar"]] for i, x in enumerate(ben, start=1)],
               [1.0, 5.6, 3.0, 3.0, 4.4])
        para(d, f"عدد المستفيدين: {len(ben):02d}", gras=True, taille=11)
    if vehicule is None:
        st = stats_transport(conn)
        saut_page(d)
        _entete(d, conn, dossier, "إحصاء المستفيدين من النقل المدرسي حسب الدواوير",
                f"السنة الدراسية {a['libelle']} · المجموع: {st['total']}")
        _table(d, ["الدوار", "عدد المستفيدين"], [[k, f"{n:02d}"] for k, n in st["douars"].items()], [9.0, 5.0])
    return _sauver(d, dossier, "النقل المدرسي", "لائحة_النقل_المدرسي" + (f"_{vehicule}" if vehicule else ""))


# ====================== 4. استعمالات الزمن ======================

MATIERES = ("اللغة العربية", "اللغة الفرنسية", "اللغة الأمازيغية", "الرياضيات", "النشاط العلمي", "التربية الإسلامية",
            "الاجتماعيات", "التربية الفنية", "التربية البدنية", "اللغة الإنجليزية", "الدعم ومعالجة التعثرات",
            "أنشطة الحياة المدرسية")
COLS_SEANCE = ("اليوم", "من", "إلى", "المادة", "المستوى أو القسم", "القاعة")


def _minutes(h: str) -> int:
    try:
        hh, mm = str(h).replace(".", ":").replace("h", ":").split(":")
        v = int(hh) * 60 + int(mm or 0)
    except (ValueError, AttributeError):
        raise ErreurVieAdmin(f"توقيت غير صحيح: «{h}» (المنتظر مثل 08:30).") from None
    if not 0 <= v < 24 * 60:
        raise ErreurVieAdmin(f"توقيت غير صحيح: «{h}».")
    return v


def _hhmm(m: int) -> str:
    return f"{m // 60:02d}:{m % 60:02d}"


def lire_emploi(conn: sqlite3.Connection, pid: int) -> list[list[str]]:
    return _propre((fiches.lire(conn, f"emploi:{int(pid)}") or {}).get("seances"), len(COLS_SEANCE))


def enregistrer_emploi(conn: sqlite3.Connection, pid: int, seances: list[list[str]]) -> None:
    propres = []
    for s in _propre(seances, len(COLS_SEANCE)):
        if s[0] not in JOURS:
            raise ErreurVieAdmin(f"يوم غير معروف: «{s[0]}».")
        a, b = _minutes(s[1]), _minutes(s[2])
        if b <= a:
            raise ErreurVieAdmin(f"{s[0]}: نهاية الحصة ({s[2]}) قبل بدايتها ({s[1]}).")
        if not s[3]:
            raise ErreurVieAdmin(f"{s[0]} {s[1]}: المادة إجبارية.")
        propres.append([s[0], _hhmm(a), _hhmm(b), s[3], s[4], s[5]])
    propres.sort(key=lambda s: (JOURS.index(s[0]), s[1]))
    for x, y in zip(propres, propres[1:]):
        if x[0] == y[0] and y[1] < x[2]:
            raise ErreurVieAdmin(f"{x[0]}: حصتان متداخلتان ({x[1]}–{x[2]} و{y[1]}–{y[2]}).")
    fiches.ecrire(conn, f"emploi:{int(pid)}", {"seances": propres})


def lire_quotas(conn: sqlite3.Connection) -> dict[str, int]:
    """الحصيص الأسبوعي بالدقائق لكل مادة، كما أدخله المدير (لا قيم مفترضة)."""
    return {k: int(v) for k, v in (fiches.lire(conn, "emploi_quotas") or {}).items() if v}


def enregistrer_quotas(conn: sqlite3.Connection, quotas: dict[str, object]) -> None:
    propres = {}
    for k, v in quotas.items():
        k = " ".join(str(k).split())
        if not k or str(v).strip() == "":
            continue
        try:
            n = int(str(v).strip())
        except ValueError:
            raise ErreurVieAdmin(f"حصيص «{k}»: عدد الدقائق في الأسبوع (رقم).") from None
        if n < 0:
            raise ErreurVieAdmin(f"حصيص «{k}» لا يكون سالباً.")
        propres[k] = n
    fiches.ecrire(conn, "emploi_quotas", propres)


def controle_emploi(conn: sqlite3.Connection, pid: int) -> dict:
    """مجموع الدقائق الأسبوعي، ولكل مادة: المنجز، الحصيص (إن أُدخل)، والفرق."""
    ss = lire_emploi(conn, pid)
    par: dict[str, int] = {}
    for s in ss:
        par[s[3]] = par.get(s[3], 0) + _minutes(s[2]) - _minutes(s[1])
    q = lire_quotas(conn)
    matieres = []
    for m in list(dict.fromkeys(list(par) + [k for k in q if k in par])):
        fait, quota = par.get(m, 0), q.get(m)
        if quota is None:
            etat = ""
        elif fait > quota:
            etat = f"تجاوز الحصيص: زيادة {fait - quota} دقيقة"
        elif fait < quota:
            etat = f"الحصيص غير مستكمل: ينقص {quota - fait} دقيقة"
        else:
            etat = "الحصيص مكتمل"
        matieres.append({"matiere": m, "minutes": fait, "quota": quota, "etat": etat})
    total = sum(par.values())
    return {"total": total, "heures": f"{total // 60} س {total % 60:02d} د", "matieres": matieres, "seances": len(ss)}


def demi_journees(conn: sqlite3.Connection, pid: int) -> dict[str, list[str]]:
    """لكل يوم: [فترة الصباح، فترة المساء] على شكل «08:30–12:30» (للوحة استعمال الزمن الجماعي)."""
    res = {}
    for j in JOURS:
        ss = [s for s in lire_emploi(conn, pid) if s[0] == j]
        matin = [s for s in ss if _minutes(s[1]) < 13 * 60]
        soir = [s for s in ss if _minutes(s[1]) >= 13 * 60]
        res[j] = [f"{min(s[1] for s in g)}–{max(s[2] for s in g)}" if g else "" for g in (matin, soir)]
    return res


def generer_emploi(conn: sqlite3.Connection, dossier: DossierDonnees, pid: int) -> Path:
    from idara.services.docs_association import _nouveau, para, tableau
    from idara.services.soutien import _entete, _table
    ss = lire_emploi(conn, pid)
    if not ss:
        raise ErreurVieAdmin("لا حصص مسجلة لهذا الأستاذ بعد.")
    p = rh.lire(conn, pid)
    a = annee_srv.annee_courante(conn)
    c = controle_emploi(conn, pid)
    d = _nouveau()
    _entete(d, conn, dossier, "استعمال الزمن الأسبوعي", f"السنة الدراسية {a['libelle']}" if a else "")
    para(d, f"الأستاذ(ة): {p.prenom_ar} {p.nom_ar}" + (f" · رقم التأجير: {p.ppr}" if p.ppr else "")
         + f" · المجموع الأسبوعي: {c['heures']}", gras=True, taille=11, apres=4)
    lignes = []
    for j in JOURS:
        for k, s in enumerate([x for x in ss if x[0] == j]):
            lignes.append([j if k == 0 else "", f"{s[1]} – {s[2]}", f"{_minutes(s[2]) - _minutes(s[1])} د", s[3], s[4],
                           s[5]])
    _table(d, ["اليوم", "التوقيت", "المدة", "المادة", "المستوى أو القسم", "القاعة"], lignes,
           [2.2, 3.0, 1.6, 4.6, 3.4, 2.2])
    para(d, "", apres=4)
    para(d, "الحصيص الأسبوعي حسب المادة", gras=True, taille=11, apres=2)
    _table(d, ["المادة", "المنجز (دقيقة)", "الحصيص (دقيقة)", "الملاحظة"],
           [[m["matiere"], str(m["minutes"]), "" if m["quota"] is None else str(m["quota"]), m["etat"]]
            for m in c["matieres"]], [5.0, 3.0, 3.0, 6.0], taille=9)
    para(d, "", apres=8)
    t = tableau(d, 1, 3, bordures=False, largeurs=[5.6, 5.6, 5.6])
    from idara.services.docs_association import _cellule
    for j, lib in enumerate(("توقيع الأستاذ(ة)", "السيد(ة) المفتش(ة)", "مدير(ة) المؤسسة")):
        _cellule(t.cell(0, j), lib, gras=True, taille=11)
    return _sauver(d, dossier, "استعمالات الزمن", f"استعمال_الزمن_{p.prenom_ar}_{p.nom_ar}".replace(" ", "_"))
