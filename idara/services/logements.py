"""تدبير السكنيات (طلب المدير 2026-11-19) حسب المذكرة رقم 40 الصادرة في 10 ماي 2004 حول تدبير المساكن الإدارية
والوظيفية المخصصة لوزارة التربية الوطنية.

- السكنيات: الرقم المخزني والعنوان والوحدة، وسجل شاغليها (بطاقة مراقبة السكن، المطبوع 9).
- إجراء التباري على سكن شاغر: الإعلان، آخر أجل للطلبات، تاريخ انعقاد لجنة الإسناد، والوسط (القروي له معايير
  إضافية).
- المترشحون: تُحسب نقطهم حسب جدول المذكرة (2.2.2-ب)، ويُرتَّبون؛ عند التساوي يُفصل بالأقدمية في العمل ثم بالقرعة.
- المطبوعات: كل مطبوع في وثيقة مستقلة وفي صفحة خاصة به: طلب المشاركة (1)، محضر أشغال لجنة الإسناد (2)،
  الالتزام والتصريح بالشرف (3 و4)، بطاقة معاينة السكن (5)، بطاقة مراقبة السكن (9). البطاقتان 1 و4 الخاصتان
  بالسكن (6 و7) وبطاقة الإشعار (8) تُعبأ لدى دائرة الأملاك المخزنية، ونماذجها غير مرفقة بالمذكرة.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from idara.data.dossier import DossierDonnees
from idara.services import etablissement as etab_srv
from idara.services import personnel as rh
from idara.services import textes as tx
from idara.services.docs_association import _cellule, _nouveau, _ombre, para, tableau

POINTILLES = "........................................"

# المطبوعات: الرمز ← (الرقم في المذكرة، العنوان، الوصف، متوفر)
MODELES = {
    "demande": (1, "طلب المشاركة في التباري للحصول على سكن إداري",
                "يملؤه المترشح، وجدول «خاص بالإدارة» بنقطه.", True),
    "pv": (2, "محضر أشغال لجنة إسناد المساكن الإدارية",
           "لائحة المتبارين ونقطهم والمرشح المقترح، وتوقيعات اللجنة.", True),
    "engagement_droit": (3, "التزام وتصريح بالشرف (المسكنون وجوباً أو بالمجان أو بحكم القانون)",
                         "يُدلي به المستفيد قبل تسلم المفاتيح، مصادقاً عليه.", True),
    "engagement_fait": (4, "التزام وتصريح بالشرف (المسكنون بالفعل)",
                        "يُدلي به المستفيد قبل تسلم المفاتيح، مصادقاً عليه.", True),
    "constat": (5, "بطاقة معاينة السكن", "محتويات السكن وحالته وتجهيزاته عند التسلم أو الإفراغ.", True),
    "carte1": (6, "البطاقة رقم 1 (خاصة بالمسكن المحدث)",
               "تُعبأ وتُرسل إلى رئيس دائرة الأملاك المخزنية. النموذج غير مرفق بالمذكرة.", False),
    "carte4": (7, "البطاقة رقم 4 (تغيير شاغل المسكن أو تعديلات عليه)",
               "تُوافى بها دائرة الأملاك المخزنية. النموذج غير مرفق بالمذكرة.", False),
    "notification": (8, "بطاقة إشعار (احتلال بدون سند)",
                     "تُبلَّغ إلى رئيس دائرة الأملاك المخزنية. النموذج غير مرفق بالمذكرة.", False),
    "controle": (9, "بطاقة مراقبة السكن", "الشاغلون المتعاقبون، والإحداث والتغييرات والإصلاحات.", True),
}

SITUATIONS = {"celibataire": "أعزب (عازبة)", "marie": "متزوج(ة)", "divorce": "مطلق(ة)", "veuf": "أرمل(ة)"}
RESPONSABILITES = {"": "لا شيء", "chef_division": "رئيس قسم", "chef_service": "رئيس مصلحة"}
RENDEMENTS = {"tres_bien": "جيد جداً", "bien": "جيد", "assez_bien": "مستحسن", "inferieur": "دون المستحسن"}


class ErreurLogement(ValueError):
    """رسالة موجهة للمدير بالعربية."""


# ---------- حساب النقط (جدول المذكرة) ----------

def annees(debut: str | None, fin: date) -> int:
    if not debut:
        return 0
    try:
        d = date.fromisoformat(debut)
    except ValueError:
        return 0
    n = fin.year - d.year - ((fin.month, fin.day) < (d.month, d.day))
    return max(0, n)


def points(d: dict, rural: bool = False) -> dict:
    """d: echelle (رقم أو "hors")، anciennete_generale، anciennete_locale (بالسنوات)، situation، enfants،
    conjoint_sans_travail، responsabilite، rendement، et (للوسط القروي) femme_non_mariee، satellite.
    يرجع {"details": [(العنصر، القيمة، النقط)], "total": n}."""
    det = []
    e = str(d.get("echelle") or "").strip()
    if e == "hors":
        pe, le = 3, "خارج السلم"
    else:
        try:
            n = int(e)
        except ValueError:
            n = 0
        pe = 1 if 1 <= n <= 6 else 2 if 7 <= n <= 9 else 3 if n >= 10 else 0
        le = f"السلم {n}" if n else "غير محدد"
    det.append(("الإطار (السلم)", le, pe))
    ag = int(d.get("anciennete_generale") or 0)
    pag = 0 if ag < 1 else 1 if ag <= 5 else 2 if ag <= 10 else 3 if ag <= 15 else 4 if ag <= 20 else 5
    det.append(("الأقدمية العامة", f"{ag} سنة", pag))
    al = int(d.get("anciennete_locale") or 0)
    pal = 0 if al < 2 else 1 if al <= 5 else 2
    det.append(("الأقدمية بنفس المدينة أو البلدة", f"{al} سنة", pal))
    sit = d.get("situation") or "celibataire"
    enf = max(0, int(d.get("enfants") or 0))
    pen = 0 if sit == "celibataire" and not enf else min(enf, 3)
    det.append(("التحملات العائلية: الأطفال", f"{enf} (في حدود ثلاثة)", pen))
    pcj = 2 if sit == "marie" and d.get("conjoint_sans_travail") else 0
    det.append(("الراتب الوحيد (الزوج أو الزوجة بدون عمل)", "نعم" if pcj else "لا", pcj))
    r = d.get("responsabilite") or ""
    pr = {"chef_division": 3, "chef_service": 2}.get(r, 0)
    det.append(("المسؤولية", RESPONSABILITES.get(r, "لا شيء"), pr))
    rd = d.get("rendement") or "inferieur"
    prd = {"tres_bien": 4, "bien": 2, "assez_bien": 1}.get(rd, 0)
    det.append(("المردودية", RENDEMENTS.get(rd, "—"), prd))
    if rural:
        pf = 3 if d.get("femme_non_mariee") else 0
        det.append(("الوسط القروي: معلمة أو أستاذة غير متزوجة", "نعم" if pf else "لا", pf))
        ps = 2 if d.get("satellite") else 0
        det.append(("الوسط القروي: يعمل بالفرعية", "نعم" if ps else "لا", ps))
    return {"details": det, "total": sum(x[2] for x in det)}


def _echelle(grade: str) -> str:
    """الدرجة ← السلم: الثانية = 10، الأولى = 11، الممتازة = خارج السلم (أطر التدريس)."""
    g = grade or ""
    corresp = {"الدرجة الثانية": "10", "الدرجة الأولى": "11", "الدرجة الممتازة": "hors"}
    if g in corresp:
        return corresp[g]
    if "خارج" in g:
        return "hors"
    m = re.search(r"(\d+)", g)
    return m.group(1) if m else ""


def proposition(conn: sqlite3.Connection, pid: int, rural: bool = False, le: date | None = None) -> dict:
    """عناصر التنقيط المقترحة من ملف الموظف (تُراجع وتُكمل في نافذة الحساب)."""
    p = rh.lire(conn, pid)
    j = le or date.today()
    return {"echelle": _echelle(p.grade), "anciennete_generale": annees(p.date_recrutement, j),
            "anciennete_locale": annees(p.date_affectation, j), "situation": "celibataire", "enfants": 0,
            "conjoint_sans_travail": False, "responsabilite": "", "rendement": "bien",
            "femme_non_mariee": bool(rural and p.sexe == "F"), "satellite": False}


# ---------- السكنيات ----------

@dataclass
class Logement:
    adresse: str
    numero: str = ""
    unite: str = ""
    nature: str = ""
    categorie: str = "administratif"
    remarques: str = ""
    id: int | None = None


def enregistrer_logement(conn, l: Logement) -> int:
    adr = " ".join((l.adresse or "").split())
    if not adr:
        raise ErreurLogement("عنوان السكن إجباري.")
    vals = (" ".join(l.numero.split()), adr, l.unite.strip(), l.nature.strip(), l.categorie, l.remarques.strip())
    with conn:
        if l.id:
            conn.execute("UPDATE logement SET numero=?, adresse=?, unite=?, nature=?, categorie=?, remarques=? "
                         "WHERE id=?", (*vals, l.id))
            return l.id
        return conn.execute("INSERT INTO logement(numero, adresse, unite, nature, categorie, remarques) "
                            "VALUES (?,?,?,?,?,?)", vals).lastrowid


def logements(conn) -> list[Logement]:
    return [Logement(r["adresse"], r["numero"], r["unite"], r["nature"], r["categorie"], r["remarques"], r["id"])
            for r in conn.execute("SELECT * FROM logement ORDER BY id")]


def logement(conn, lid: int) -> Logement:
    l = next((x for x in logements(conn) if x.id == lid), None)
    if l is None:
        raise ErreurLogement("السكن غير موجود.")
    return l


def supprimer_logement(conn, lid: int) -> None:
    with conn:
        conn.execute("DELETE FROM logement WHERE id=?", (lid,))


def occupant_actuel(conn, lid: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM logement_occupation WHERE logement_id=? AND date_sortie='' "
                        "ORDER BY id DESC LIMIT 1", (lid,)).fetchone()


def occupations(conn, lid: int) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM logement_occupation WHERE logement_id=? ORDER BY id", (lid,)).fetchall()


def ajouter_occupation(conn, lid: int, occupant: str, personnel_id: int | None = None, acte_numero: str = "",
                       acte_date: str = "") -> int:
    occupant = " ".join((occupant or "").split())
    if not occupant:
        raise ErreurLogement("اسم الشاغل إجباري.")
    p = rh.lire(conn, personnel_id) if personnel_id else None
    with conn:
        return conn.execute(
            "INSERT INTO logement_occupation(logement_id, occupant, personnel_id, ppr, cadre, fonction, "
            "date_naissance, acte_numero, acte_date) VALUES (?,?,?,?,?,?,?,?,?)",
            (lid, occupant, personnel_id, p.ppr if p else "", p.cadre if p else "", p.fonction if p else "",
             p.date_naissance if p else "", acte_numero, acte_date)).lastrowid


def liberer(conn, oid: int, le: str, motif: str, reference: str = "") -> None:
    try:
        date.fromisoformat(le)
    except ValueError:
        raise ErreurLogement("تاريخ الإفراغ غير صحيح.") from None
    if not motif.strip():
        raise ErreurLogement("سبب الإفراغ إجباري.")
    with conn:
        conn.execute("UPDATE logement_occupation SET date_sortie=?, motif_sortie=?, sortie_ref=? WHERE id=?",
                     (le, motif.strip(), reference.strip(), oid))


# ---------- إجراءات التباري ----------

@dataclass
class Concours:
    logement_id: int
    date_annonce: str
    date_limite: str = ""
    date_commission: str = ""
    rural: bool = False
    statut: str = "ouvert"
    beneficiaire_id: int | None = None
    remarques: str = ""
    id: int | None = None


def _iso(v: str, lib: str, requis: bool = False) -> str:
    v = (v or "").strip()
    if not v:
        if requis:
            raise ErreurLogement(f"{lib} إجباري.")
        return ""
    try:
        date.fromisoformat(v)
    except ValueError:
        raise ErreurLogement(f"{lib} غير صحيح.") from None
    return v


def enregistrer_concours(conn, c: Concours) -> int:
    logement(conn, c.logement_id)
    a = _iso(c.date_annonce, "تاريخ الإعلان", True)
    lim = _iso(c.date_limite, "آخر أجل لتقديم الطلبات")
    com = _iso(c.date_commission, "تاريخ انعقاد لجنة الإسناد")
    if lim and lim < a:
        raise ErreurLogement("آخر أجل للطلبات قبل تاريخ الإعلان.")
    if com and lim and com < lim:
        raise ErreurLogement("لجنة الإسناد تنعقد بعد انصرام أجل الطلبات.")
    vals = (c.logement_id, a, lim or None, com or None, int(c.rural), c.statut, c.beneficiaire_id, c.remarques)
    with conn:
        if c.id:
            conn.execute("UPDATE logement_concours SET logement_id=?, date_annonce=?, date_limite=?, date_commission=?, "
                         "rural=?, statut=?, beneficiaire_id=?, remarques=? WHERE id=?", (*vals, c.id))
            return c.id
        return conn.execute("INSERT INTO logement_concours(logement_id, date_annonce, date_limite, date_commission, "
                            "rural, statut, beneficiaire_id, remarques) VALUES (?,?,?,?,?,?,?,?)", vals).lastrowid


def _concours(r) -> Concours:
    return Concours(r["logement_id"], r["date_annonce"], r["date_limite"] or "", r["date_commission"] or "",
                    bool(r["rural"]), r["statut"], r["beneficiaire_id"], r["remarques"], r["id"])


def concours_liste(conn) -> list[Concours]:
    return [_concours(r) for r in conn.execute("SELECT * FROM logement_concours ORDER BY date_annonce DESC, id DESC")]


def concours(conn, cid: int) -> Concours:
    r = conn.execute("SELECT * FROM logement_concours WHERE id=?", (cid,)).fetchone()
    if r is None:
        raise ErreurLogement("إجراء التباري غير موجود.")
    return _concours(r)


def supprimer_concours(conn, cid: int) -> None:
    with conn:
        conn.execute("DELETE FROM logement_concours WHERE id=?", (cid,))


@dataclass
class Candidat:
    personnel_id: int
    donnees: dict = field(default_factory=dict)
    points: float = 0
    id: int | None = None


def enregistrer_candidat(conn, cid: int, pid: int, donnees: dict) -> Candidat:
    c = concours(conn, cid)
    rh.lire(conn, pid)
    total = points(donnees, c.rural)["total"]
    with conn:
        conn.execute("INSERT INTO logement_candidat(concours_id, personnel_id, donnees, points) VALUES (?,?,?,?) "
                     "ON CONFLICT(concours_id, personnel_id) DO UPDATE SET donnees=excluded.donnees, "
                     "points=excluded.points", (cid, pid, json.dumps(donnees, ensure_ascii=False), total))
    return next(x for x in candidats(conn, cid) if x.personnel_id == pid)


def supprimer_candidat(conn, cid: int, pid: int) -> None:
    with conn:
        conn.execute("DELETE FROM logement_candidat WHERE concours_id=? AND personnel_id=?", (cid, pid))


def candidats(conn, cid: int) -> list[Candidat]:
    """مرتبون: النقط تنازلياً، ثم الأقدمية العامة (معيار الفصل في المذكرة)؛ التساوي التام يُفصل بالقرعة."""
    res = [Candidat(r["personnel_id"], json.loads(r["donnees"] or "{}"), r["points"], r["id"])
           for r in conn.execute("SELECT * FROM logement_candidat WHERE concours_id=?", (cid,))]
    res.sort(key=lambda x: (-x.points, -int(x.donnees.get("anciennete_generale") or 0)))
    return res


def ex_aequo(cands: list[Candidat]) -> bool:
    """تساوٍ تام في الرتبة الأولى (النقط والأقدمية): يُفصل بالقرعة."""
    if len(cands) < 2:
        return False
    a, b = cands[0], cands[1]
    return a.points == b.points and int(a.donnees.get("anciennete_generale") or 0) == \
        int(b.donnees.get("anciennete_generale") or 0)


def attribuer(conn, cid: int, pid: int) -> None:
    c = concours(conn, cid)
    if pid not in [x.personnel_id for x in candidats(conn, cid)]:
        raise ErreurLogement("المستفيد ليس من المترشحين لهذا السكن.")
    p = rh.lire(conn, pid)
    with conn:
        conn.execute("UPDATE logement_concours SET statut='attribue', beneficiaire_id=? WHERE id=?", (pid, cid))
    if not any(o["personnel_id"] == pid and not o["date_sortie"] for o in occupations(conn, c.logement_id)):
        ajouter_occupation(conn, c.logement_id, f"{p.prenom_ar} {p.nom_ar}", pid, "",
                           c.date_commission or date.today().isoformat())


def synthese(conn) -> dict:
    ls = logements(conn)
    occ = sum(1 for l in ls if occupant_actuel(conn, l.id))
    cs = concours_liste(conn)
    return {"logements": len(ls), "occupes": occ, "vacants": len(ls) - occ,
            "ouverts": sum(1 for c in cs if c.statut == "ouvert"),
            "candidats": conn.execute("SELECT COUNT(*) FROM logement_candidat").fetchone()[0]}


# ---------- المطبوعات: كل مطبوع وثيقة مستقلة في صفحة خاصة به ----------

def _entete(conn, d) -> None:
    e = etab_srv.lire_etablissement(conn)
    for l in ("المملكة المغربية", "وزارة التربية الوطنية والتعليم الأولي والرياضة",
              f"الأكاديمية الجهوية للتربية والتكوين: {e.academie_ar}" if e and e.academie_ar else "",
              f"المديرية الإقليمية: {e.direction_ar}" if e and e.direction_ar else "",
              f"المؤسسة: {e.nom_ar}" if e else ""):
        if l:
            para(d, l, gras=True, taille=10, apres=0)
    para(d, "", apres=2)


def _titre(d, t: str, num: int) -> None:
    para(d, t, gras=True, taille=16, centre=True, apres=0)
    para(d, f"(المطبوع رقم {num} · المذكرة 40 بتاريخ 10 ماي 2004)", taille=9, centre=True, apres=8)


def _v(x) -> str:
    return x if x not in (None, "") else POINTILLES


def _ltr(t: str) -> str:
    return f"⁦{t}⁩" if t else ""


def _ligne(d, lib: str, val: str = "", apres=3) -> None:
    para(d, f"{lib}: {_v(val)}", taille=12, apres=apres)


def _compacter(t, taille: float = 10) -> None:
    """أسطر جدول مضغوطة (الخانات الفارغة لا ترفع ارتفاع السطر) ليبقى المطبوع في صفحة واحدة."""
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Pt
    for r in t.rows:
        for c in r.cells:
            for p in c.paragraphs:
                p.paragraph_format.space_after = Pt(0)
                p.paragraph_format.space_before = Pt(0)
                p.paragraph_format.line_spacing = 1.0
                ppr = p._p.get_or_add_pPr()
                rpr = ppr.find(qn("w:rPr"))
                if rpr is None:
                    rpr = OxmlElement("w:rPr")
                    ppr.append(rpr)
                for tag in ("w:sz", "w:szCs"):
                    e = OxmlElement(tag)
                    e.set(qn("w:val"), str(int(taille * 2)))
                    rpr.append(e)


def _personne(conn, pid: int | None):
    return rh.lire(conn, pid) if pid else None


def _doc_demande(conn, d, ctx) -> str:
    l, p, cand, rural = ctx["logement"], ctx["personne"], ctx["candidat"], ctx["rural"]
    _titre(d, "طلب المشاركة في التباري للحصول على سكن إداري", 1)
    t = tableau(d, 2, 2, largeurs=[9, 8])
    _cellule(t.cell(0, 0), "الرقم المخزني للمسكن (يعبأ من طرف الإدارة)", taille=11)
    _cellule(t.cell(0, 1), _ltr(l.numero) if l else "", taille=11)
    _cellule(t.cell(1, 0), "عنوانه", taille=11)
    _cellule(t.cell(1, 1), l.adresse if l else "", taille=11)
    para(d, "", apres=2)
    para(d, "أنا الموقع(ة) أسفله", taille=12, apres=3)
    don = cand.donnees if cand else {}
    _ligne(d, "الاسم والنسب", f"{p.prenom_ar} {p.nom_ar}" if p else "")
    _ligne(d, "تاريخ التوظيف", tx.date_chiffres(p.date_recrutement) if p and p.date_recrutement else "")
    e = etab_srv.lire_etablissement(conn)
    _ligne(d, "مقر العمل", (e.nom_ar if e else "") if p else "")
    _ligne(d, "الإطار", (p.cadre or "") if p else "")
    _ligne(d, "السلم", don.get("echelle", "") if don else "")
    _ligne(d, "رقم التأجير", _ltr(p.ppr) if p and p.ppr else "")
    _ligne(d, "عنوان الإقامة", (p.adresse or "") if p else "")
    sit = SITUATIONS.get(don.get("situation", ""), "") if don else ""
    _ligne(d, "الحالة العائلية", sit or "أعزب – متزوج(ة) – مطلق(ة) – أرمل(ة) (أحط ما يناسب)")
    _ligne(d, "مهنة الزوج(ة)", "بدون عمل" if don.get("conjoint_sans_travail") else "")
    _ligne(d, "عدد الأطفال", str(don.get("enfants")) if don and don.get("enfants") is not None else "")
    _ligne(d, "المهمة الحالية", (p.fonction or "") if p else "")
    _ligne(d, "تاريخ الالتحاق بمقر العمل الحالي",
           tx.date_chiffres(p.date_affectation) if p and p.date_affectation else "")
    para(d, "- أصرح أنني لا أملك أي سكن شخصي في البلدة التي أزاول العمل بها، وأنني لم أتعرض لعقوبة تأديبية لم يتم "
            "سحبها، وأن المعلومات التي أدليت بها صحيحة.", taille=12, apres=2)
    para(d, "- أطلب تسجيلي في مباراة الحصول على السكن الإداري المبين أعلاه.", taille=12, apres=4)
    para(d, "إمضاء المعني بالأمر", gras=True, taille=12, apres=8)
    para(d, "خاص بالإدارة", gras=True, taille=13, centre=True, apres=2)
    det = points(don, rural)["details"] if don else []
    lignes = det or [(x, "", "") for x in ("الإطار (السلم)", "الأقدمية العامة", "الأقدمية بنفس المدينة أو البلدة",
                                           "التحملات العائلية: الأطفال", "الراتب الوحيد", "المسؤولية", "المردودية")]
    t = tableau(d, len(lignes) + 2, 3, largeurs=[7.5, 5, 2.5])
    for j, x in enumerate(("عناصر التقويم", "القيمة", "النقطة")):
        _cellule(t.cell(0, j), x, gras=True, taille=10)
        _ombre(t.cell(0, j))
    for i, (a, b, c) in enumerate(lignes, start=1):
        _cellule(t.cell(i, 0), a, taille=10, centre=False)
        _cellule(t.cell(i, 1), str(b), taille=10)
        _cellule(t.cell(i, 2), str(c), taille=10)
    k = len(lignes) + 1
    _cellule(t.cell(k, 0), "مجموع النقط", gras=True, taille=10)
    _cellule(t.cell(k, 2), str(points(don, rural)["total"]) if don else "", gras=True, taille=10)
    para(d, "إمضاء الرئيس المباشر", taille=11, apres=0)
    return f"طلب المشاركة {p.prenom_ar} {p.nom_ar}" if p else "طلب المشاركة (فارغ)"


def _doc_pv(conn, d, ctx) -> str:
    l, c = ctx["logement"], ctx["concours"]
    _titre(d, "محضر أشغال لجنة إسناد المساكن الإدارية", 2)
    _ligne(d, "السكن موضوع التباري", (f"{l.adresse}" + (f" (الرقم المخزني {_ltr(l.numero)})" if l.numero else ""))
           if l else "")
    _ligne(d, "تاريخ الإعلان عن السكن الشاغر", tx.date_chiffres(c.date_annonce) if c else "")
    _ligne(d, "تاريخ انعقاد اللجنة", tx.date_chiffres(c.date_commission) if c and c.date_commission else "")
    para(d, "درست اللجنة ملفات الترشيح على ضوء المعايير المحددة في المذكرة رقم 40 بتاريخ 10 ماي 2004، وتضع هذا "
            "المحضر الذي يتضمن لائحة المتبارين والنقط التي حصل عليها كل واحد منهم، واسم المرشح الذي تقترح اللجنة "
            "أن يسند إليه السكن.", taille=12, apres=4)
    cands = candidats(conn, c.id) if c else []
    n = max(len(cands), 5)
    t = tableau(d, n + 1, 5, largeurs=[1.2, 6, 3, 3.5, 2.5])
    for j, x in enumerate(("ر.ت", "الاسم والنسب", "رقم التأجير", "الأقدمية العامة", "مجموع النقط")):
        _cellule(t.cell(0, j), x, gras=True, taille=11)
        _ombre(t.cell(0, j))
    for i, x in enumerate(cands, start=1):
        p = rh.lire(conn, x.personnel_id)
        for j, v in enumerate((str(i), f"{p.prenom_ar} {p.nom_ar}", _ltr(p.ppr),
                               f"{x.donnees.get('anciennete_generale', '')} سنة", f"{x.points:g}")):
            _cellule(t.cell(i, j), v, taille=11)
    para(d, "", apres=2)
    prop = cands[0] if cands else None
    if c and c.beneficiaire_id:
        prop = next((x for x in cands if x.personnel_id == c.beneficiaire_id), prop)
    pp = rh.lire(conn, prop.personnel_id) if prop else None
    _ligne(d, "المرشح(ة) الذي تقترح اللجنة إسناد السكن إليه", f"{pp.prenom_ar} {pp.nom_ar}" if pp else "")
    if cands and ex_aequo(cands):
        para(d, "ملاحظة: تساوى مرشحان أو أكثر في مجموع النقط وفي الأقدمية في العمل، فتم الفصل بينهم بالقرعة.",
             taille=11, apres=3)
    if c and c.rural:
        para(d, "السكن بالوسط القروي: يُسند بعد مصادقة المدير الإقليمي على محضر اللجنة المكونة من مدير المجموعة "
                "المدرسية ومفتش المقاطعة.", taille=11, apres=3)
    para(d, "توقيعات أعضاء اللجنة", gras=True, taille=12, apres=2)
    t = tableau(d, 5, 3, largeurs=[5.5, 6, 4.5])
    for j, x in enumerate(("الصفة", "الاسم", "التوقيع")):
        _cellule(t.cell(0, j), x, gras=True, taille=11)
        _ombre(t.cell(0, j))
    quals = (("مدير المجموعة المدرسية", "مفتش(ة) المقاطعة", "ممثل المديرية الإقليمية", "عضو")
             if c and c.rural else ("ممثل(ة) المديرية الإقليمية", "مدير(ة) المؤسسة", "رئيس(ة) مصلحة الموارد البشرية",
                                     "المكلف(ة) بتدبير المساكن (مقرراً)"))
    e = etab_srv.directeur_actuel(conn)
    for i, q in enumerate(quals, start=1):
        _cellule(t.cell(i, 0), q, taille=11)
        if "مدير" in q and e and ("المؤسسة" in q or "المجموعة" in q):
            _cellule(t.cell(i, 1), f"{e['prenom_ar']} {e['nom_ar']}", taille=11)
    return "محضر لجنة الإسناد"


def _engagement(conn, d, ctx, droit: bool) -> str:
    p, l = ctx["personne"], ctx["logement"]
    _titre(d, "التزام وتصريح بالشرف", 3 if droit else 4)
    para(d, "(خاص بالموظفين المسكنين وجوباً أو بالمجان أو بحكم القانون)" if droit
         else "(خاص بالموظفين المسكنين بالفعل)", taille=11, centre=True, apres=6)
    para(d, "أصرح بالشرف أنا الموقع(ة) أسفله:", taille=12, apres=3)
    _ligne(d, "الاسم الشخصي", p.prenom_ar if p else "")
    _ligne(d, "الاسم العائلي", p.nom_ar if p else "")
    _ligne(d, "رقم بطاقة التعريف الوطنية", _ltr(p.cin) if p and p.cin else "")
    _ligne(d, "رقم التأجير", _ltr(p.ppr) if p and p.ppr else "")
    e = etab_srv.lire_etablissement(conn)
    _ligne(d, "إدارة العمل", (e.nom_ar if e else "") if p else "")
    ville = (e.commune_ar or e.ville_redaction_ar) if e else ""
    para(d, "بأني على علم بكافة المقتضيات التنظيمية المتعلقة بالموظفين المسكنين ولاسيما تلك النصوص المنصوص عليها "
            "في القرار الوزيري الصادر في 19 شتنبر 1951 حسبما وقع تغييره وتتميمه، والتي منح لي "
            + ("بمقتضاها" if droit else "في إطارها") + f" السكن الإداري الواقع ب: {l.adresse if l else POINTILLES} "
            f"بمدينة {ville or POINTILLES} حيث أزاول مهامي" + ("." if droit else "، وبأني لا أملك مسكناً شخصياً "
                                                              "بالمدينة المذكورة."), taille=12, apres=4)
    para(d, "وألتزم:", gras=True, taille=12, apres=2)
    para(d, "أولاً: بإفراغ المسكن الممنوح لي من طرف الإدارة في أجل شهرين عند الكف عن مزاولتي لمهامي المترتب عن: "
            "الاستقالة المقبولة بصفة قانونية؛ الإعفاء؛ العزل؛ التوقف المؤقت عن العمل (الاستيداع)؛ الانتقال إلى "
            "مدينة أخرى؛ الإلحاق؛ الإحالة على التقاعد"
            + ("؛ إنهاء المهمة التي من أجلها أسند إلي السكن الذي أشغله سواء كان هذا الإنهاء من أجل المصلحة أو "
               "بطلب مني." if droit else "."), taille=12, apres=3)
    if droit:
        para(d, "ثانياً: في مرحلة عدم الامتثال لأمر الإدارة فإني أصبح معرضاً لإفراغ المسكن بالطرق القانونية التي "
                "تراها الإدارة مناسبة:", taille=12, apres=2)
    else:
        para(d, "ثانياً: الإدلاء داخل أجل شهر واحد بجميع التغيرات التي تطرأ على أي من العناصر المصرح بها أعلاه، "
                "وإلا أصبحت معرضاً لإفراغ المسكن بالطرق القانونية التي تراها الإدارة مناسبة:", taille=12, apres=2)
    for x in ("أ- تحمل سومة كرائية حقيقية للمسكن الذي أشغله تقوم بتحديدها اللجنة الإدارية للتقويم؛",
              "ب- المتابعة القضائية؛", "ج- التعرض للعقوبات التأديبية التي تراها الإدارة مناسبة."):
        para(d, x, taille=12, apres=1)
    para(d, "", apres=8)
    para(d, f"حرر ب{ville or POINTILLES} في: {POINTILLES}", taille=12, apres=2)
    para(d, "الإمضاء (مصادق عليه من طرف السلطات المحلية)", gras=True, taille=12, apres=0)
    nom = f" {p.prenom_ar} {p.nom_ar}" if p else ""
    return ("التزام المسكنين وجوبا" if droit else "التزام المسكنين بالفعل") + nom


def _doc_constat(conn, d, ctx) -> str:
    l, p = ctx["logement"], ctx["personne"]
    _titre(d, "بطاقة معاينة السكن" + (f" رقم {l.numero}" if l and l.numero else ""), 5)
    _ligne(d, "عنوان السكن", l.adresse if l else "", apres=4)
    para(d, "1- محتويات السكن", gras=True, taille=12, apres=1)
    pieces = ("غرفة", "صالون", "مطبخ", "حمام", "دوش", "مراحيض", "مستودع", "مرأب")
    t = tableau(d, len(pieces) + 1, 6, largeurs=[3, 2.6, 2.6, 2.6, 2.6, 2.6])
    for j, x in enumerate(("المحتويات", "المطبق", "الطابق الأرضي", "الطابق الأول", "الطابق الثاني", "المجموع")):
        _cellule(t.cell(0, j), x, gras=True, taille=9)
        _ombre(t.cell(0, j))
    for i, x in enumerate(pieces, start=1):
        _cellule(t.cell(i, 0), x, gras=True, taille=9)
    _compacter(t)
    para(d, "2- حالة السكن", gras=True, taille=12, apres=1)
    elems = ("البناء", "تلبيس الجدران", "الصباغة", "تبليط الأرضية", "المساكة", "النجارة الخشبية", "النجارة الصناعية",
             "التجهيزات النحاسية والحديدية", "الحدادة", "الزجاج", "الترصيص", "الكهرباء", "الربط بشبكة الماء الشروب",
             "الربط بشبكة الكهرباء", "الربط بشبكة التطهير", "قنوات الماء الحار", "قنوات الماء الشروب",
             "التدفئة المركزية", "التدفئة الخشبية")
    t = tableau(d, len(elems) + 1, 3, largeurs=[1.2, 6.5, 8.3])
    for j, x in enumerate(("ر.ت", "العناصر", "وصف الحالة")):
        _cellule(t.cell(0, j), x, gras=True, taille=9)
        _ombre(t.cell(0, j))
    for i, x in enumerate(elems, start=1):
        _cellule(t.cell(i, 0), str(i), taille=9)
        _cellule(t.cell(i, 1), x, taille=9, centre=False)
    _compacter(t)
    para(d, "3- التجهيزات المتوفرة", gras=True, taille=12, apres=1)
    t = tableau(d, 5, 4, largeurs=[4, 5, 3, 4])
    for j, x in enumerate(("المكان", "نوع التجهيز", "العدد", "الحالة")):
        _cellule(t.cell(0, j), x, gras=True, taille=9)
        _ombre(t.cell(0, j))
    _compacter(t, 10)
    para(d, f"أشهد أنا الموقع(ة) أسفله: {f'{p.prenom_ar} {p.nom_ar}' if p else POINTILLES} · رقم التأجير: "
            f"{_ltr(p.ppr) if p and p.ppr else POINTILLES} · رقم بطاقة التعريف الوطنية: "
            f"{_ltr(p.cin) if p and p.cin else POINTILLES}، بأنني عاينت حالة المسكن ومحتوياته المبينة أعلاه بحضور "
            "ممثل الإدارة وأشهد بصحتها، وذلك عند استلام (أو إفراغ) المسكن.", taille=10, apres=3)
    para(d, f"وحرر في {POINTILLES} بتاريخ {POINTILLES}", taille=10, apres=3)
    t = tableau(d, 1, 2, bordures=False, largeurs=[8, 8])
    _cellule(t.cell(0, 0), "اسم وصفة وتوقيع ممثل الإدارة", gras=True, taille=10)
    _cellule(t.cell(0, 1), "إمضاء المستفيد", gras=True, taille=10)
    return "بطاقة معاينة السكن"


def _doc_controle(conn, d, ctx) -> str:
    l = ctx["logement"]
    e = etab_srv.lire_etablissement(conn)
    _titre(d, "بطاقة مراقبة السكن", 9)
    _ligne(d, "الأكاديمية", e.academie_ar if e else "")
    _ligne(d, "الرمز", _ltr(l.numero) if l and l.numero else "")
    _ligne(d, "المديرية الإقليمية", e.direction_ar if e else "")
    _ligne(d, "عنوان السكن (رقم السكن والشارع أو الزنقة والحي والبلدة)", l.adresse if l else "", apres=4)
    occ = occupations(conn, l.id) if l and l.id else []
    n = max(len(occ), 6)
    t = tableau(d, n + 2, 10, largeurs=[2.6, 1.7, 1.5, 1.5, 1.6, 1.3, 1.6, 1.6, 1.6, 1.4])
    tetes = ("الاسم والنسب", "رقم التأجير", "الإطار", "المهمة", "تاريخ الميلاد", "وثيقة الإسناد", "", "الإفراغ", "", "")
    for j, x in enumerate(tetes):
        _cellule(t.cell(0, j), x, gras=True, taille=8)
        _ombre(t.cell(0, j))
    for j, x in enumerate(("", "", "", "", "", "الرقم", "التاريخ", "التاريخ", "السبب", "السند")):
        _cellule(t.cell(1, j), x, gras=True, taille=8)
        _ombre(t.cell(1, j))
    for i, o in enumerate(occ, start=2):
        for j, x in enumerate((o["occupant"], _ltr(o["ppr"]), o["cadre"], o["fonction"],
                               tx.date_chiffres(o["date_naissance"]) if o["date_naissance"] else "",
                               o["acte_numero"], tx.date_chiffres(o["acte_date"]) if o["acte_date"] else "",
                               tx.date_chiffres(o["date_sortie"]) if o["date_sortie"] else "", o["motif_sortie"],
                               o["sortie_ref"])):
            _cellule(t.cell(i, j), x, taille=8)
    _ligne(d, "ملاحظات", l.remarques if l else "", apres=4)
    para(d, "1- الإحداث", gras=True, taille=11, apres=1)
    for x in ("برنامج سنة", "تاريخ التسلم المؤقت", "تاريخ التسلم النهائي"):
        _ligne(d, x, "", apres=1)
    para(d, "2- التغييرات الطارئة على السكن (إعادة التصميم، التقسيم، الفصل، الإدماج، إضافات...)", gras=True,
         taille=11, apres=1)
    for x in ("التاريخ", "الطبيعة والنوع", "السند"):
        _ligne(d, x, "", apres=1)
    para(d, "3- الإصلاحات المنجزة", gras=True, taille=11, apres=1)
    t = tableau(d, 4, 6, largeurs=[3, 2.2, 2.4, 3.2, 2.6, 2.6])
    for j, x in enumerate(("نوعية الإصلاح", "المقاولة", "مبلغ المصاريف", "رقم وتاريخ الصفقة أو سند الطلب",
                           "رقم وتاريخ التأشير", "رقم وتاريخ الأمر بالأداء")):
        _cellule(t.cell(0, j), x, gras=True, taille=8)
        _ombre(t.cell(0, j))
    return "بطاقة مراقبة السكن"


GENERATEURS = {"demande": _doc_demande, "pv": _doc_pv, "constat": _doc_constat, "controle": _doc_controle,
               "engagement_droit": lambda c, d, x: _engagement(c, d, x, True),
               "engagement_fait": lambda c, d, x: _engagement(c, d, x, False)}


def generer(conn: sqlite3.Connection, dossier: DossierDonnees, code: str, concours_id: int | None = None,
            personnel_id: int | None = None, logement_id: int | None = None) -> Path:
    """مطبوع واحد في وثيقة مستقلة. يُملأ من إجراء التباري (السكن، المترشحون، المستفيد) ومن ملف الموظف، وإلا فارغاً."""
    if code not in MODELES:
        raise ErreurLogement("مطبوع غير معروف.")
    if not MODELES[code][3]:
        raise ErreurLogement("نموذج هذا المطبوع غير مرفق بالمذكرة: أرسله لبرمجته.")
    c = concours(conn, concours_id) if concours_id else None
    lid = logement_id or (c.logement_id if c else None)
    l = logement(conn, lid) if lid else None
    pid = personnel_id or (c.beneficiaire_id if c else None)
    cand = next((x for x in candidats(conn, c.id) if x.personnel_id == pid), None) if c and pid else None
    ctx = {"concours": c, "logement": l, "personne": _personne(conn, pid), "candidat": cand,
           "rural": bool(c and c.rural)}
    d = _nouveau()
    _entete(conn, d)
    nom = GENERATEURS[code](conn, d, ctx)
    rep = dossier.archives / "تدبير السكنيات"
    rep.mkdir(parents=True, exist_ok=True)
    chemin = rep / f"{datetime.now():%Y%m%d_%H%M%S_%f}_{MODELES[code][0]:02d}_{nom}.docx".replace("/", "-")
    d.save(chemin)
    return chemin
