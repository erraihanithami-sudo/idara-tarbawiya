"""استخلاص واجبات الجمعية الرياضية المدرسية وجمعية تنمية التعاون المدرسي وتحويل حصصها (وثائق المدير 2026-11-24).

المراجع (كما في وثائق المدير):
- الجمعية الرياضية: المذكرة الوزارية 66 بتاريخ 22 يونيو 2004، والدوريات 1 و2 و3 و16 للجامعة الملكية المغربية للرياضة
  المدرسية، والمذكرة 92 بتاريخ 23 يوليوز 2003. يستخلص مسير(ة) المصالح الاقتصادية الواجبات ويودعها في الحساب الجاري
  للمؤسسة، ثم تُحوَّل الحصص القانونية تحت مسؤولية رئيس الجمعية وبتعاون مع أمين المال: قبل 15 أكتوبر، مرفقة بنسخ من
  محضر الاستخلاص، والمبالغ المستخلصة بعد 15 أكتوبر في أجل أقصاه 31 دجنبر.
  التوزيع: الجمعية 65%، الجامعة 15% (CCP 5094-70X الرباط)، صندوق دعم الرياضة المدرسية 5%، فرع الجامعة بالمديرية 10%،
  فرع الجامعة بالأكاديمية 5%.
- جمعية تنمية التعاون المدرسي: المذكرة الوزارية 24 بتاريخ 20 فبراير 2007. التعاونية بالمؤسسة 40%، والفرع الإقليمي 60%
  (المطاعم المدرسية 20%، الجمعية الأم بالرباط 10%، الفرع الإقليمي بالمديرية 10%، الأعمال الاجتماعية الإقليمية 10%،
  المخيمات الصيفية 10%). وتُصرف حصة التعاونية (40%): النشاط الاجتماعي 30%، الثقافي 20%، الإصلاح والصيانة والتجهيز 20%،
  الورشات الفنية والتربوية 20%، البستنة والتربية البيئية 10%.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from idara.services import annee as annee_srv
from idara.services import fiches


class ErreurTransfert(ValueError):
    """رسالة موجهة للمدير بالعربية."""


@dataclass(frozen=True)
class Part:
    cle: str
    libelle: str
    pct: float
    compte: str = ""                      # رقم الحساب المعروف (يمكن للمدير تغييره)
    sous: tuple = ()                      # تفصيل الحصة (التعاونية: حصة الفرع الإقليمي)
    association: bool = False             # حصة الجمعية نفسها (تُسجَّل مدخولاً في حسابها)


@dataclass(frozen=True)
class Regime:
    type: str
    nom: str
    element: str                          # عنصر واجبات التسجيل المقابل (frais_inscription)
    reference: str
    parts: tuple
    echeances: tuple = ()
    programme: tuple = field(default=())  # مجالات صرف حصة الجمعية (النسبة من حصتها)


REGIMES = {
    "sportive": Regime(
        "sportive", "الجمعية الرياضية المدرسية", "sport",
        "المذكرة الوزارية 66 (22 يونيو 2004) والدوريتان 1 و2 للجامعة الملكية المغربية للرياضة المدرسية",
        (Part("association", "الجمعية الرياضية المدرسية", 65, association=True),
         Part("frmss", "الجامعة الملكية المغربية للرياضة المدرسية", 15, "CCP 5094-70X الرباط"),
         Part("fonds", "صندوق دعم الرياضة المدرسية", 5),
         Part("direction", "فرع الجامعة الملكية المغربية للرياضة المدرسية بالمديرية الإقليمية", 10),
         Part("academie", "فرع الجامعة الملكية المغربية للرياضة المدرسية بالأكاديمية", 5)),
        (("10-15", "تحويل الحصص المستخلصة قبل 15 أكتوبر، مرفقة بنسخ من محضر الاستخلاص"),
         ("12-31", "تحويل المبالغ المستخلصة بعد 15 أكتوبر في أجل أقصاه 31 دجنبر"))),
    "cooperative": Regime(
        "cooperative", "جمعية تنمية التعاون المدرسي", "cooperative",
        "المذكرة الوزارية رقم 24 بتاريخ 20 فبراير 2007 في شأن حسابات التعاونية المدرسية",
        (Part("association", "التعاونية المدرسية بالمؤسسة", 40, association=True),
         Part("branche", "الفرع الإقليمي لجمعية تنمية التعاون المدرسي", 60,
              sous=(("المطاعم المدرسية", 20), ("الجمعية الأم بالرباط", 10), ("الفرع الإقليمي بالمديرية", 10),
                    ("الأعمال الاجتماعية الإقليمية", 10), ("المخيمات الصيفية", 10)))),
        (),
        (("النشاط الاجتماعي", 30), ("النشاط الثقافي", 20), ("الإصلاح والصيانة والتجهيز", 20),
         ("الورشات الفنية والتربوية", 20), ("البستنة والتربية البيئية", 10))),
}


def regime(type_: str) -> Regime:
    if type_ not in REGIMES:
        raise ErreurTransfert("جمعية غير معروفة.")
    return REGIMES[type_]


def _r(x: float) -> float:
    return round(x + 1e-9, 2)


def _annee(conn) -> str:
    a = annee_srv.annee_courante(conn)
    if a is None:
        raise ErreurTransfert("لا سنة دراسية جارية.")
    return a["libelle"]


def _cle(conn, type_: str) -> str:
    return f"transferts_{type_}_{_annee(conn)}"


def _charger(conn, type_: str) -> dict:
    d = fiches.lire(conn, _cle(conn, type_)) or {}
    return {"collecte": d.get("collecte"), "eleves": d.get("eleves"), "operations": list(d.get("operations", [])),
            "suivant": int(d.get("suivant", 1))}


def _ecrire(conn, type_: str, d: dict) -> None:
    fiches.ecrire(conn, _cle(conn, type_), d)


# ---------- المبلغ المستخلص ----------

def collecte_programme(conn: sqlite3.Connection, type_: str) -> dict:
    """ما سُجّل في «التسجيلات» (عدد المؤدين والمبلغ)، إن وُجد."""
    from idara.services import frais_inscription as fr
    try:
        t = fr.totaux(conn)["elements"][regime(type_).element]
    except fr.ErreurFrais:
        return {"payes": 0, "montant": None, "unitaire": None}
    return {"payes": t["payes"], "montant": t["montant"], "unitaire": t["montant_unitaire"]}


def collecte(conn: sqlite3.Connection, type_: str) -> dict:
    """المبلغ المستخلص المعتمد: ما كتبه المدير (المسك اليدوي في المطبوع)، وإلا ما سُجّل في البرنامج."""
    d = _charger(conn, type_)
    p = collecte_programme(conn, type_)
    if d["collecte"] is not None:
        return {"montant": float(d["collecte"]), "eleves": d["eleves"], "source": "manuel", "programme": p}
    return {"montant": float(p["montant"] or 0), "eleves": p["payes"], "source": "programme", "programme": p}


def definir_collecte(conn: sqlite3.Connection, type_: str, montant, eleves=None) -> None:
    """المبلغ المستخلص فعلياً (من محاضر الأساتذة). montant=None: الرجوع إلى ما سُجّل في البرنامج."""
    regime(type_)
    d = _charger(conn, type_)
    if montant in (None, ""):
        d["collecte"], d["eleves"] = None, None
    else:
        try:
            m = float(str(montant).replace(",", ".").replace(" ", ""))
        except ValueError:
            raise ErreurTransfert("المبلغ المستخلص رقم.") from None
        if m < 0:
            raise ErreurTransfert("المبلغ المستخلص لا يكون سالباً.")
        d["collecte"] = m
        try:
            d["eleves"] = int(eleves) if eleves not in (None, "") else None
        except ValueError:
            raise ErreurTransfert("عدد المنخرطين رقم صحيح.") from None
    _ecrire(conn, type_, d)


# ---------- التوزيع والتحويلات ----------

def comptes(conn: sqlite3.Connection, type_: str) -> dict:
    """أرقام الحسابات الجارية لكل جهة (تبقى من سنة لأخرى)."""
    base = {p.cle: p.compte for p in regime(type_).parts}
    base.update((fiches.lire(conn, "comptes_transferts") or {}).get(type_, {}))
    return base


def definir_compte(conn: sqlite3.Connection, type_: str, part: str, compte: str) -> None:
    if part not in {p.cle for p in regime(type_).parts}:
        raise ErreurTransfert("جهة غير معروفة.")
    d = fiches.lire(conn, "comptes_transferts") or {}
    d.setdefault(type_, {})[part] = " ".join((compte or "").split())
    fiches.ecrire(conn, "comptes_transferts", d)


def repartition(conn: sqlite3.Connection, type_: str) -> dict:
    """لكل جهة: النسبة، المستحق، المحوَّل، الباقي، رقم الحساب، وتفصيل الحصة إن وُجد."""
    rg = regime(type_)
    c = collecte(conn, type_)
    d = _charger(conn, type_)
    cpt = comptes(conn, type_)
    lignes = []
    for p in rg.parts:
        du = _r(c["montant"] * p.pct / 100)
        vire = _r(sum(o["montant"] for o in d["operations"] if o["part"] == p.cle))
        ops = [o for o in d["operations"] if o["part"] == p.cle]
        lignes.append({"cle": p.cle, "libelle": p.libelle, "pct": p.pct, "du": du, "vire": vire,
                       "reste": _r(du - vire), "compte": cpt.get(p.cle, ""), "association": p.association,
                       "dates": [o["date"] for o in ops], "sous": [(l, pc, _r(c["montant"] * pc / 100))
                                                                   for l, pc in p.sous]})
    prog = []
    if rg.programme:
        part_asso = next(l for l in lignes if l["association"])["du"]
        prog = [(l, pc, _r(part_asso * pc / 100)) for l, pc in rg.programme]
    return {"regime": rg, "collecte": c, "lignes": lignes, "programme": prog,
            "total_du": _r(sum(l["du"] for l in lignes)), "total_vire": _r(sum(l["vire"] for l in lignes)),
            "operations": sorted(d["operations"], key=lambda o: (o["date"], o["id"]))}


def _date(v: str) -> str:
    try:
        return date.fromisoformat(v).isoformat()
    except (TypeError, ValueError):
        raise ErreurTransfert("تاريخ التحويل غير صحيح.") from None


def enregistrer_virement(conn: sqlite3.Connection, type_: str, part: str, le: str, montant=None,
                         reference: str = "") -> int:
    """تحويل حصة جهة (أو جزء منها). montant=None: الباقي المستحق كاملاً."""
    r = repartition(conn, type_)
    ligne = next((l for l in r["lignes"] if l["cle"] == part), None)
    if ligne is None:
        raise ErreurTransfert("اختر الجهة المحوَّل إليها.")
    if montant in (None, ""):
        m = ligne["reste"]
    else:
        try:
            m = float(str(montant).replace(",", ".").replace(" ", ""))
        except ValueError:
            raise ErreurTransfert("مبلغ التحويل رقم.") from None
    if m <= 0:
        raise ErreurTransfert("لا باقي للتحويل لهذه الجهة." if montant in (None, "") else "مبلغ التحويل موجب.")
    if m > ligne["reste"] + 0.005:
        raise ErreurTransfert(f"المبلغ يتجاوز الباقي المستحق لهذه الجهة ({ligne['reste']:.2f} درهم).")
    d = _charger(conn, type_)
    vid = d["suivant"]
    d["suivant"] += 1
    d["operations"].append({"id": vid, "part": part, "date": _date(le), "montant": _r(m),
                            "reference": " ".join((reference or "").split())})
    _ecrire(conn, type_, d)
    return vid


def supprimer_virement(conn: sqlite3.Connection, type_: str, vid: int) -> None:
    d = _charger(conn, type_)
    d["operations"] = [o for o in d["operations"] if o["id"] != vid]
    _ecrire(conn, type_, d)


def echeances(conn: sqlite3.Connection, type_: str, le: date | None = None) -> list[str]:
    """تنبيهات الآجال (الجمعية الرياضية: 15 أكتوبر و31 دجنبر)."""
    rg = regime(type_)
    le = le or date.today()
    r = repartition(conn, type_)
    reste = _r(sum(l["reste"] for l in r["lignes"] if not l["association"]))
    if not rg.echeances or reste <= 0:
        return []
    an = _annee(conn)
    y = int(an[:4])
    res = []
    for md, lib in rg.echeances:
        m, j = map(int, md.split("-"))
        lim = date(y, m, j)
        jours = (lim - le).days
        if 0 <= jours <= 30:
            res.append(f"{lib}: بقي {jours} يوماً (الباقي للتحويل {reste:.2f} درهم).")
        elif jours < 0 and md == rg.echeances[-1][0]:
            res.append(f"تجاوز أجل {lim:%d/%m/%Y}: الباقي للتحويل {reste:.2f} درهم.")
    return res


def inscrire_part_association(conn: sqlite3.Connection, type_: str, le: str | None = None,
                              registre: str = "banque") -> int:
    """يسجل حصة الجمعية (65% أو 40%) مدخولاً في سنتها المالية التي يقع فيها التاريخ."""
    from idara.services import associations as asso
    r = repartition(conn, type_)
    part = next(l for l in r["lignes"] if l["association"])
    if part["du"] <= 0:
        raise ErreurTransfert("لا مبلغ مستخلص بعد.")
    le = _date(le or date.today().isoformat())
    ex = [e for e in asso.exercices(conn, type_) if e["date_debut"] <= le <= e["date_fin"]]
    if not ex:
        raise ErreurTransfert("افتح السنة المالية للجمعية التي يقع فيها هذا التاريخ أولاً.")
    rub = next(x for x in asso.rubriques(conn, type_, "recette", actifs=True)
               if x["ligne"].startswith("حصة"))
    deja = conn.execute("SELECT 1 FROM operation_financiere WHERE exercice_id=? AND rubrique_id=? AND detail LIKE ?",
                        (ex[0]["id"], rub["id"], f"%{_annee(conn)}%")).fetchone()
    if deja:
        raise ErreurTransfert("سُجّلت حصة الجمعية لهذا الموسم في سجلاتها من قبل.")
    return asso.enregistrer(conn, asso.Operation(
        ex[0]["id"], le, "recette", registre, part["du"], rub["id"], "محضر الاستخلاص",
        f"حصة الجمعية ({part['pct']:g}%) من الواجبات المستخلصة، الموسم الدراسي {_annee(conn)}"))


# ---------- الوثائق ----------

def _dh(v) -> str:
    return f"{v:,.2f}".replace(",", " ")


def _doc(conn, dossier, titre: str):
    from docx.shared import Cm
    from idara.services import documents as dc
    from idara.services import etablissement as etab_srv
    from idara.services.docs_association import _nouveau, para
    try:
        c = dc.champs_communs(conn)
    except dc.ErreurDocument as e:
        raise ErreurTransfert(str(e)) from None
    d = _nouveau()
    e = etab_srv.lire_etablissement(conn)
    if e and e.logo_path and (dossier.racine / e.logo_path).exists():
        d.add_picture(str(dossier.racine / e.logo_path), width=Cm(17.4))
    para(d, titre, gras=True, taille=19, centre=True, apres=0)
    return d, c


def _sauver(d, dossier, conn, type_: str, nom: str) -> Path:
    rep = dossier.archives / _annee(conn).replace("/", "-") / regime(type_).nom
    rep.mkdir(parents=True, exist_ok=True)
    chemin = rep / f"{datetime.now():%Y%m%d_%H%M%S}_{nom}.docx"
    d.save(chemin)
    return chemin


def _table_parts(d, r: dict, avec_vire: bool) -> None:
    from idara.services import textes as tx
    from idara.services.docs_association import _cellule, _ombre, tableau
    entetes = ["الجهة المعنية", "الحصة", "المبلغ (درهم)"] + (["تاريخ التحويل"] if avec_vire else []) + \
        ["رقم الحساب الجاري"]
    lignes = []
    for l in r["lignes"]:
        lignes.append((l["libelle"], f"{l['pct']:g}%", _dh(l["vire"] if avec_vire and l["vire"] else l["du"]),
                       "، ".join(tx.date_chiffres(x) for x in l["dates"]) if avec_vire else None, l["compte"]))
        for lib, pc, m in l["sous"]:
            lignes.append((f"   منها: {lib}", f"{pc:g}%", _dh(m), "" if avec_vire else None, ""))
    t = tableau(d, 2 + len(lignes), len(entetes), largeurs=[6.4, 1.6, 2.8] + ([2.8] if avec_vire else []) + [3.8])
    for j, h in enumerate(entetes):
        _cellule(t.cell(0, j), h, gras=True, taille=11)
        _ombre(t.cell(0, j))
    for i, l in enumerate(lignes, start=1):
        vals = [l[0], l[1], l[2]] + ([l[3]] if avec_vire else []) + [l[4]]
        for j, v in enumerate(vals):
            _cellule(t.cell(i, j), v, taille=11, centre=j != 0, gras=not l[0].startswith("   "))
    i = len(lignes) + 1
    tot = r["total_vire"] if avec_vire else r["total_du"]
    for j, v in enumerate(["المجموع", "100%", _dh(tot)] + ([""] if avec_vire else []) + [""]):
        _cellule(t.cell(i, j), v, gras=True, taille=11)
        _ombre(t.cell(i, j))


def generer_pv_collecte(conn: sqlite3.Connection, dossier, type_: str) -> Path:
    """محضر الاستخلاص وتوزيع الحصص (يُرفق بالتحويلات)، وبرمجة صرف حصة التعاونية."""
    from idara.services import textes as tx
    from idara.services.docs_association import _cellule, _ombre, para, tableau
    r = repartition(conn, type_)
    rg = r["regime"]
    if r["collecte"]["montant"] <= 0:
        raise ErreurTransfert("لا مبلغ مستخلص بعد: سجّل الأداءات في «التسجيلات» أو اكتب المبلغ المستخلص.")
    quoi = "واجبات الانخراط في" if type_ == "sportive" else "واجب الاشتراك السنوي في"
    d, c = _doc(conn, dossier, f"محضر استخلاص {quoi} {rg.nom}")
    para(d, f"الموسم الدراسي {_annee(conn)}", centre=True, taille=13, apres=6)
    n = r["collecte"]["eleves"]
    para(d, f"بلغ مجموع {quoi.replace(' في', '')} المستخلصة بـ{c['etablissement']}: {_dh(r['collecte']['montant'])} درهم"
            + (f"، من {n} تلميذة وتلميذاً." if n else "."), taille=13, apres=2)
    para(d, f"وتوزع طبقاً لـ{rg.reference} على النحو التالي:", taille=13, apres=4)
    _table_parts(d, r, False)
    if r["programme"]:
        para(d, apres=6)
        para(d, "مجالات صرف حصة التعاونية المدرسية بالمؤسسة", gras=True, taille=14, apres=2)
        t = tableau(d, 2 + len(r["programme"]), 3, largeurs=[9.5, 2.5, 4.5])
        for j, h in enumerate(("المجال", "النسبة", "المبلغ المبرمج (درهم)")):
            _cellule(t.cell(0, j), h, gras=True, taille=11)
            _ombre(t.cell(0, j))
        for i, (lib, pc, m) in enumerate(r["programme"], start=1):
            for j, v in enumerate((lib, f"{pc:g}%", _dh(m))):
                _cellule(t.cell(i, j), v, taille=11, centre=j != 0)
        i = len(r["programme"]) + 1
        for j, v in enumerate(("المجموع", "100%", _dh(sum(m for *_, m in r["programme"])))):
            _cellule(t.cell(i, j), v, gras=True, taille=11)
            _ombre(t.cell(i, j))
    if rg.echeances:
        para(d, apres=4)
        for _, lib in rg.echeances:
            para(d, "• " + lib + ".", taille=11, apres=0)
    para(d, apres=8)
    para(d, f"حرر ب{c['ville']} في: {tx.date_chiffres(date.today().isoformat())}", taille=12, apres=6)
    t = tableau(d, 2, 3, bordures=False, largeurs=[5.8, 5.8, 5.8])
    for j, v in enumerate(("مدير المؤسسة", "رئيس الجمعية", "أمين المال")):
        _cellule(t.cell(0, j), v, gras=True, taille=12)
    from docx.shared import Cm
    t.rows[1].height = Cm(2.2)
    return _sauver(d, dossier, conn, type_, f"محضر الاستخلاص - {rg.nom}")


def generer_certificat(conn: sqlite3.Connection, dossier, type_: str, qualite: str = "") -> Path:
    """شهادة نفقة: المبلغ المستخلص وتوزيعه وإيداعه في حسابات الجهات (تاريخ التحويل ورقم الحساب)."""
    from idara.services import textes as tx
    from idara.services.docs_association import para
    r = repartition(conn, type_)
    if r["total_vire"] <= 0:
        raise ErreurTransfert("لا تحويلات مسجلة بعد: سجّل تحويل الحصص أولاً.")
    d, c = _doc(conn, dossier, "شـهـادة نـفـقـة")
    para(d, f"{r['regime'].nom} · الموسم الدراسي {_annee(conn)}", centre=True, taille=13, apres=8)
    para(d, "أنا الموقع أسفله بصفتي: " + (qualite or "." * 90), taille=13, apres=4)
    para(d, f"أشهد أنني أنفقت مبلغاً مالياً قدره: {_dh(r['total_vire'])} درهم، والتي تم توزيعها وإيداعها في الحسابات "
            "الخاصة على الشكل التالي:", taille=13, apres=6)
    _table_parts(d, r, True)
    para(d, apres=10)
    para(d, f"حرر ب{c['ville']} في: {tx.date_chiffres(date.today().isoformat())}", taille=12, apres=4)
    para(d, "الإمضاء", gras=True, taille=13)
    return _sauver(d, dossier, conn, type_, f"شهادة نفقة - {r['regime'].nom}")


# ---------- بطاقة مشروع صرف مداخيل التعاونية والتقرير المالي (نماذج المديرية، المدير 2026-11-26) ----------
# البطاقة تُبعث في نسختين إلى المديرية الإقليمية قبل 20 نونبر، والتقرير المالي قبل 30 ماي.
# أساس التوزيع = المنقول (الفائض عن السنة الماضية) + مجموع المداخيل المرتقبة، على المجالات الخمسة للمذكرة 24.
ECHEANCE_PROJET = "20/11"
ECHEANCE_RAPPORT = "30/05"
BUREAU_COOP = "مصلحة الشؤون التربوية · مكتب تنمية الأنشطة التربوية والاجتماعية والثقافية والفنية"


def _cle_coop(conn) -> str:
    return f"cooperative_projet_{_annee(conn)}"


def exercice_cooperative(conn: sqlite3.Connection, le: date | None = None):
    """السنة المالية للتعاونية التي تضم التاريخ، وإلا آخر سنة مفتوحة."""
    from idara.services import associations as asso
    le = (le or date.today()).isoformat()
    exs = asso.exercices(conn, "cooperative")
    for e in exs:
        if e["date_debut"] <= le <= e["date_fin"]:
            return e
    return exs[0] if exs else None


def donnees_cooperative(conn: sqlite3.Connection) -> dict:
    """المنقول والمداخيل المرتقبة ورقم التعاونية والمنسق: المسجل يدوياً، وإلا المحسوب من البرنامج."""
    from idara.services import associations as asso
    d = fiches.lire(conn, _cle_coop(conn)) or {}
    ex = exercice_cooperative(conn)
    surplus_calc, prevu_calc = None, None
    if ex is not None:
        rep = asso.report(conn, ex["id"])
        surplus_calc = _r(rep["banque"] + rep["caisse"])
        prev = [r for r in asso.execution(conn, ex["id"]) if r["sens"] == "recette" and r["ligne"] != asso.REPORT]
        if sum(r["prevu"] for r in prev) > 0:
            prevu_calc = _r(sum(r["prevu"] for r in prev))
    if prevu_calc is None:
        part = next(l for l in repartition(conn, "cooperative")["lignes"] if l["cle"] == "association")
        prevu_calc = part["du"] if part["du"] > 0 else None
    a = asso.association(conn, "cooperative")
    return {
        "surplus": d["surplus"] if d.get("surplus") is not None else surplus_calc,
        "prevu": d["prevu"] if d.get("prevu") is not None else prevu_calc,
        "source_surplus": "manuel" if d.get("surplus") is not None else ("programme" if surplus_calc is not None else ""),
        "source_prevu": "manuel" if d.get("prevu") is not None else ("programme" if prevu_calc is not None else ""),
        "numero": d.get("numero", ""), "coordinateur": d.get("coordinateur", ""),
        "compte": (a["rib"] or "") if a else "", "exercice": ex["libelle"] if ex is not None else "",
    }


def definir_donnees_cooperative(conn: sqlite3.Connection, surplus=None, prevu=None, numero: str = "",
                                coordinateur: str = "") -> None:
    """None: يُحسب من البرنامج (منقول السنة المالية، وتوقعات المداخيل أو حصة التعاونية من الاستخلاص)."""
    def montant(v, lib):
        if v is None or str(v).strip() == "":
            return None
        try:
            m = round(float(str(v).replace(",", ".").replace(" ", "").replace(" ", "")), 2)
        except ValueError:
            raise ErreurTransfert(f"{lib} غير صحيح.") from None
        if m < 0:
            raise ErreurTransfert(f"{lib} لا يكون سالباً.")
        return m
    fiches.ecrire(conn, _cle_coop(conn), {"surplus": montant(surplus, "المنقول"), "prevu": montant(prevu, "مبلغ المداخيل المرتقبة"),
                                          "numero": " ".join((numero or "").split()),
                                          "coordinateur": " ".join((coordinateur or "").split())})


def bilan_cooperative(conn: sqlite3.Connection) -> dict:
    """لكل مجال: النسبة، المبلغ المخصص (من المنقول + المداخيل المرتقبة)، المصاريف المنجزة، والباقي."""
    from idara.services import associations as asso
    d = donnees_cooperative(conn)
    base = _r((d["surplus"] or 0) + (d["prevu"] or 0))
    ex = exercice_cooperative(conn)
    depenses: dict[str, float] = {}
    if ex is not None:
        for r in asso.execution(conn, ex["id"]):
            if r["sens"] == "depense":
                depenses[r["chapitre"]] = _r(depenses.get(r["chapitre"], 0) + r["realise"])
    lignes = []
    for lib, pc in REGIMES["cooperative"].programme:
        alloue = _r(base * pc / 100)
        dep = depenses.get(lib, 0.0)
        lignes.append({"libelle": lib, "pct": pc, "alloue": alloue, "depense": dep, "reste": _r(alloue - dep)})
    autres = _r(sum(v for k, v in depenses.items() if k not in dict(REGIMES["cooperative"].programme)))
    solde = None
    if ex is not None:
        s = asso.soldes(conn, ex["id"])
        solde = _r(s["banque"] + s["caisse"])
    return {**d, "base": base, "lignes": lignes, "autres_depenses": autres,
            "total_alloue": _r(sum(l["alloue"] for l in lignes)), "total_depense": _r(sum(l["depense"] for l in lignes)),
            "total_reste": _r(sum(l["reste"] for l in lignes)), "solde": solde}


def _entete_coop(conn, dossier, titre: str, b: dict):
    from idara.services import etablissement as etab_srv
    from idara.services.docs_association import para
    if b["surplus"] is None and b["prevu"] is None:
        raise ErreurTransfert("سجّل المنقول (الفائض عن السنة الماضية) والمداخيل المرتقبة أولاً، أو افتح السنة "
                              "المالية للتعاونية في تبويب «المداخيل والمصاريف والسجلات».")
    d, c = _doc(conn, dossier, titre)
    para(d, f"للموسم الدراسي {_annee(conn)}", centre=True, taille=13, apres=0)
    para(d, BUREAU_COOP, centre=True, taille=11, apres=6)
    e = etab_srv.lire_etablissement(conn)
    trait = "." * 30
    para(d, f"المؤسسة: {c['etablissement']}      رمزها: {(e.code_etab if e else '') or trait}", taille=13, apres=0)
    para(d, f"الجماعة: {(e.commune_ar if e else '') or trait}      رقم التعاونية المدرسية: {b['numero'] or trait}",
         taille=13, apres=0)
    para(d, f"رقم الحساب: {b['compte'] or trait}", taille=13, apres=0)
    para(d, f"المنقول الفائض عن السنة الماضية: {_dh(b['surplus'] or 0)} درهم      "
            f"مجموع المداخيل المرتقبة خلال السنة الحالية: {_dh(b['prevu'] or 0)} درهم", taille=13, apres=6)
    return d, c


def _pied_coop(d, c, echeance: str, rapport: bool, coordinateur: str = "") -> None:
    from docx.shared import Cm
    from idara.services import textes as tx
    from idara.services.docs_association import _cellule, para, tableau
    para(d, apres=4)
    para(d, f"حرر ب{c['ville']} في: {tx.date_chiffres(date.today().isoformat())}", taille=12, apres=6)
    t = tableau(d, 2, 2, bordures=False, largeurs=[8.7, 8.7])
    _cellule(t.cell(0, 0), "إمضاء منسق(ة) التعاونية المدرسية", gras=True, taille=12)
    _cellule(t.cell(0, 1), "إمضاء المدير(ة) وطابع المؤسسة", gras=True, taille=12)
    if coordinateur:
        _cellule(t.cell(1, 0), coordinateur, taille=12)
    t.rows[1].height = Cm(2.0)
    t = tableau(d, 2, 2, largeurs=[8.7, 8.7])
    _cellule(t.cell(0, 0), "خاص بالمديرية الإقليمية: تأشيرة المكتب المختص", gras=True, taille=11)
    _cellule(t.cell(0, 1), "إمضاء السيد المدير الإقليمي", gras=True, taille=11)
    t.rows[1].height = Cm(2.0)
    quoi = "بدقة، " if rapport else ""
    para(d, f"* يعبأ هذا المطبوع {quoi}ويبعث في نسختين إلى المديرية الإقليمية قبل {echeance} من الموسم الدراسي "
            "الجاري.", taille=10, apres=0)


def generer_projet_cooperative(conn: sqlite3.Connection, dossier) -> Path:
    """بطاقة مشروع صرف مداخيل التعاونية المدرسية (قبل 20 نونبر)."""
    from idara.services.docs_association import _cellule, _ombre, tableau
    b = bilan_cooperative(conn)
    d, c = _entete_coop(conn, dossier, "بطاقة مشروع صرف مداخيل التعاونية المدرسية", b)
    t = tableau(d, 2 + len(b["lignes"]), 5, largeurs=[1.0, 6.0, 2.4, 3.6, 4.4])
    for j, h in enumerate(("ر.ت", "المجالات", "النسبة المخصصة", "المبلغ المخصص للمجال (بالدرهم)", "ملاحظات")):
        _cellule(t.cell(0, j), h, gras=True, taille=11)
        _ombre(t.cell(0, j))
    for i, l in enumerate(b["lignes"], start=1):
        for j, v in enumerate((f"{i:02d}", l["libelle"], f"{l['pct']:g} %", _dh(l["alloue"]), "")):
            _cellule(t.cell(i, j), v, taille=11, centre=j != 1)
    i = len(b["lignes"]) + 1
    for j, v in enumerate(("", "المجموع", "100 %", _dh(b["total_alloue"]), "")):
        _cellule(t.cell(i, j), v, gras=True, taille=11)
        _ombre(t.cell(i, j))
    _pied_coop(d, c, ECHEANCE_PROJET, False, b["coordinateur"])
    return _sauver(d, dossier, conn, "cooperative", "بطاقة مشروع صرف مداخيل التعاونية")


def generer_rapport_cooperative(conn: sqlite3.Connection, dossier) -> Path:
    """التقرير المالي للتعاونية المدرسية (قبل 30 ماي): المخصص والمصاريف والباقي لكل مجال."""
    from idara.services.docs_association import _cellule, _ombre, para, tableau
    b = bilan_cooperative(conn)
    d, c = _entete_coop(conn, dossier, "التقرير المالي للتعاونية المدرسية", b)
    ent = ("ر.ت", "المجالات", "النسبة المخصصة", "المبلغ المخصص للمجال (بالدرهم)", "المصاريف (بالدرهم)",
           "الباقي (بالدرهم)", "ملاحظات")
    t = tableau(d, 2 + len(b["lignes"]), len(ent), largeurs=[0.9, 4.0, 1.8, 2.9, 2.6, 2.6, 2.6])
    for j, h in enumerate(ent):
        _cellule(t.cell(0, j), h, gras=True, taille=10)
        _ombre(t.cell(0, j))
    for i, l in enumerate(b["lignes"], start=1):
        obs = "تجاوز المخصص" if l["reste"] < 0 else ""
        for j, v in enumerate((f"{i:02d}", l["libelle"], f"{l['pct']:g}%", _dh(l["alloue"]), _dh(l["depense"]),
                               _dh(l["reste"]), obs)):
            _cellule(t.cell(i, j), v, taille=10, centre=j != 1)
    i = len(b["lignes"]) + 1
    for j, v in enumerate(("", "المجموع", "100%", _dh(b["total_alloue"]), _dh(b["total_depense"]),
                           _dh(b["total_reste"]), "")):
        _cellule(t.cell(i, j), v, gras=True, taille=10)
        _ombre(t.cell(i, j))
    if b["autres_depenses"]:
        para(d, f"مصاريف خارج المجالات الخمسة (مصاريف بنكية وبريدية ومختلفات): {_dh(b['autres_depenses'])} درهم.",
             taille=11, apres=0)
    if b["solde"] is not None:
        para(d, f"الباقي في الحساب (البنك والصندوق) حسب سجلات السنة المالية {b['exercice']}: {_dh(b['solde'])} درهم.",
             gras=True, taille=12, apres=0)
    _pied_coop(d, c, ECHEANCE_RAPPORT, True, b["coordinateur"])
    return _sauver(d, dossier, conn, "cooperative", "التقرير المالي للتعاونية المدرسية")
