"""سجلات إدارية تُعرَّف بالوصف لا بالكود (طلب المدير 2026-11-14): أعوان الحراسة والنظافة، طلبات الموظفين والورقة
الشخصية، الحوادث المدرسية، خليتا اليقظة والإنصات، التحفيز والتشجيع، الشراكات، الإعلانات، فريق قيادة المشروع.

كل سجل = حقول + وثائق. الأسطر تُحفظ في fiche_json (مفتاح «reg:<السجل>:<السنة>»)، فلا جدول جديد لكل سجل.
الوثائق تُبنى بالبرنامج. صياغاتها عامة (لا نماذج رسمية بين يدي): تُراجع قبل التوقيع.
لا نقط مكان المعطيات الناقصة: الحقل الفارغ لا يُطبع.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from idara.data.dossier import DossierDonnees
from idara.services import annee as annee_srv
from idara.services import etablissement as etab_srv
from idara.services import fiches
from idara.services import personnel as rh
from idara.services import textes as tx


class ErreurRegistre(ValueError):
    """رسالة موجهة للمدير بالعربية."""


MOIS = ("شتنبر", "أكتوبر", "نونبر", "دجنبر", "يناير", "فبراير", "مارس", "أبريل", "ماي", "يونيو", "يوليوز")
CELLULES = ("خلية اليقظة", "خلية الإنصات والمصالحة")


@dataclass(frozen=True)
class Champ:
    cle: str
    libelle: str
    type: str = "texte"        # texte | long | date | nombre | choix | personnel | eleve | ref
    choix: tuple = ()
    requis: bool = False
    colonne: bool = True       # يظهر في جدول الصفحة وفي اللوائح
    source: str = ""           # ref: السجل الذي تؤخذ منه الأسماء (حقله الأول)


@dataclass(frozen=True)
class Doc:
    cle: str
    titre: str
    description: str
    portee: str = "tout"       # tout: كل الأسطر المعروضة | ligne: السطر المحدد | personnel: موظف يُختار
    colonnes: tuple = ()       # للوائح: حقول معينة بدل كل الأعمدة


@dataclass(frozen=True)
class Registre:
    cle: str
    titre: str
    sous: str
    champs: tuple
    docs: tuple
    filtre: str | None = None  # حقل تُصفّى به الأسطر (والوثائق)
    par_annee: bool = True
    etat: str | None = None    # حقل الوضعية: يُلوَّن في الجدول (أخضر إن تمّ، برتقالي إن لم يتمّ)
    defaut_etat: str = ""      # ما يُعرض حين يكون حقل الوضعية فارغاً
    dossier: bool = False      # زر «الاطلاع على الملف كاملاً» أمام كل سطر
    internes: tuple = ()       # حقول تتبع داخلية لا تُطبع في بطاقة السطر (مثل وضعية الإرسال)
    filtre_defaut: str = ""    # التصفية عند فتح الصفحة (مثلاً الشراكات «السارية» فقط)
    titre_liste: str = ""      # عنوان جدول الأسطر في الصفحة الثابتة
    ajout: str = ""            # نص زر الإضافة في النافذة المنبثقة

    def champ(self, cle: str) -> Champ:
        return next(c for c in self.champs if c.cle == cle)


_OUI_NON = ("نعم", "لا")
ENVOIS_ACCIDENT = ("لم يُرسل بعد", "أُرسل إلى المديرية الإقليمية", "أُرسل إلى التأمين المدرسي",
                   "أُرسل إلى المديرية والتأمين")

REGISTRES: dict[str, Registre] = {r.cle: r for r in (
    Registre("agents", "بطاقات الأعوان",
             "أعوان الحراسة والنظافة والإطعام والشركة المشغلة لكل واحد.",
             (Champ("nom", "الاسم الكامل", requis=True),
              Champ("fonction", "المهمة", "choix", ("الحراسة", "النظافة", "الطبخ والإطعام"), requis=True),
              Champ("societe", "الشركة المشغلة"), Champ("cin", "رقم البطاقة الوطنية", colonne=False),
              Champ("telephone", "الهاتف"), Champ("unite", "الوحدة المدرسية"),
              Champ("horaire", "توقيت العمل"), Champ("debut", "تاريخ الالتحاق", "date", colonne=False)),
             (Doc("liste", "لائحة الأعوان والشركات المشغلة", "كل الأعوان بمهامهم وشركاتهم وهواتفهم."),
              Doc("service", "جدول الخدمة", "توقيت عمل كل عون حسب الوحدة المدرسية.",
                  colonnes=("nom", "fonction", "unite", "horaire"))),
             filtre="fonction", par_annee=False),
    # توجيهات المدير 2026-11-15: لا تتبع لحضور الأعوان؛ يبقى تقييم الخدمة الشهري
    Registre("suivi_agents", "تقييم الخدمة الشهري",
             "لكل شهر: تقييم خدمة كل عون وملاحظاته. منه تُولَّد الحصيلة الشهرية.",
             (Champ("mois", "الشهر", "choix", MOIS, requis=True),
              Champ("agent", "العون", "ref", source="agents", requis=True),
              Champ("appreciation", "تقييم الخدمة", "choix", ("جيد", "مقبول", "دون المطلوب")),
              Champ("observations", "ملاحظات", "long")),
             (Doc("bilan", "الحصيلة الشهرية لتقييم الخدمة", "للشهر المختار في المصفاة، أو لكل الأشهر."),),
             filtre="mois"),
    Registre("demandes", "طلبات الموظفين",
             "طلبات لا يغطيها ملف «الرخص»: الإذن بالتغيب، رخصة الأبوة، رخصة الزواج، وطلب الفحص الطبي المضاد.",
             (Champ("date", "تاريخ الطلب", "date", requis=True),
              Champ("personnel", "الموظف(ة)", "personnel", requis=True),
              Champ("type", "نوع الطلب", "choix", ("إذن بالتغيب", "رخصة الأبوة", "رخصة الزواج", "رخصة استثنائية",
                                                   "إجراء فحص طبي مضاد"), requis=True),
              Champ("du", "من", "date"), Champ("au", "إلى", "date"),
              Champ("motif", "السبب أو التوضيح", "long")),
             (Doc("demande", "الطلب", "طلب السطر المحدد، باسم الموظف(ة) ومعطياته.", "ligne"),
              Doc("suivi", "لائحة تتبع الطلبات", "كل الطلبات المسجلة هذه السنة."),
              Doc("fiche_personnelle", "الورقة الشخصية", "بطاقة المعطيات الإدارية للموظف(ة) المختار(ة).",
                  "personnel")),
             filtre="type"),
    Registre("accidents", "الحوادث المدرسية",
             "سجل الحوادث التي تقع للتلاميذ داخل المؤسسة أو في محيطها، والتصريح بكل حادثة.",
             (Champ("date", "تاريخ الحادثة", "date", requis=True), Champ("heure", "الساعة", colonne=False),
              Champ("eleve", "التلميذ(ة)", "eleve", requis=True), Champ("classe", "القسم"),
              Champ("lieu", "المكان", "choix", ("الساحة", "القسم", "الملعب", "المرافق الصحية", "الدرج",
                                               "الطريق إلى المدرسة", "مكان آخر")),
              Champ("description", "وصف الحادثة", "long", requis=True, colonne=False),
              Champ("blessure", "طبيعة الإصابة"),
              Champ("temoin", "الشاهد أو المكلف بالحراسة", "personnel", colonne=False),
              Champ("mesures", "الإجراءات المتخذة", "long", colonne=False),
              Champ("declare", "صُرّح بها للتأمين", "choix", _OUI_NON, colonne=False),
              # طلب المدير 2026-11-20: وضعية ملف الحادثة (هل أُرسل؟)
              Champ("envoi", "وضعية ملف الحادثة", "choix", ENVOIS_ACCIDENT),
              Champ("date_envoi", "تاريخ الإرسال", "date", colonne=False),
              Champ("reference", "مرجع الإرسال", colonne=False)),
             (Doc("declaration", "تصريح بحادثة مدرسية", "تصريح الحادثة المحددة، للتأمين المدرسي والمديرية.", "ligne"),
              Doc("registre", "سجل الحوادث المدرسية", "كل حوادث السنة في جدول واحد.",
                  colonnes=("date", "eleve", "classe", "lieu", "blessure", "envoi"))),
             filtre="lieu", etat="envoi", defaut_etat=ENVOIS_ACCIDENT[0], dossier=True,
             internes=("envoi", "date_envoi", "reference")),
    Registre("examens_medicaux", "الفحوصات الطبية",
             "الفحوصات الطبية والتلقيحات التي استفاد منها التلاميذ ونتائجها، وما تقرر بعدها. معطيات صحية: لا تُنشر.",
             (Champ("date", "تاريخ الفحص", "date", requis=True),
              Champ("eleve", "التلميذ(ة)", "eleve", requis=True), Champ("classe", "القسم"),
              Champ("type", "نوع الفحص", "choix", ("الفحص الطبي المنتظم", "فحص البصر", "فحص السمع", "فحص الأسنان",
                                                   "التلقيح", "فحص آخر"), requis=True),
              Champ("intervenant", "الطبيب(ة) أو الجهة"),
              Champ("resultat", "النتيجة أو الملاحظة", "long", colonne=False),
              Champ("suite", "الإجراء بعد الفحص", "choix", ("لا شيء", "إخبار ولي الأمر", "توجيه نحو طبيب مختص",
                                                           "متابعة داخل المؤسسة"))),
             (Doc("fiche", "بطاقة الفحص", "بطاقة الفحص المحدد.", "ligne"),
              Doc("liste", "لائحة الفحوصات الطبية", "كل فحوصات السنة، أو لنوع واحد.")),
             filtre="type"),
    Registre("cellule_membres", "التركيبة والأدوار",
             "أعضاء خلية اليقظة وخلية الإنصات والمصالحة، وصفة كل عضو ودوره.",
             (Champ("cellule", "الخلية", "choix", CELLULES, requis=True),
              Champ("membre", "العضو", "personnel", requis=True),
              Champ("qualite", "الصفة"), Champ("role", "الدور داخل الخلية", "long")),
             (Doc("composition", "تركيبة الخلية وأدوار أعضائها", "للخلية المختارة في المصفاة، أو للخليتين."),),
             filtre="cellule"),
    Registre("cellule_reunions", "الاجتماعات",
             "برمجة اجتماعات الخليتين ومحاضرها.",
             (Champ("date", "التاريخ", "date", requis=True),
              Champ("cellule", "الخلية", "choix", CELLULES, requis=True),
              Champ("ordre", "جدول الأعمال", "long", requis=True),
              Champ("presents", "الحاضرون", "long", colonne=False),
              Champ("conclusions", "الخلاصات والقرارات", "long", colonne=False)),
             (Doc("pv", "محضر الاجتماع", "محضر الاجتماع المحدد.", "ligne"),
              Doc("programme", "برمجة اشتغال الخلية", "تواريخ الاجتماعات وجداول أعمالها.",
                  colonnes=("date", "cellule", "ordre"))),
             filtre="cellule"),
    Registre("cellule_cas", "الرصد والمواكبة",
             "الحالات التي رصدتها الخليتان وما اتُّخذ فيها. معطيات داخلية: لا تُنشر.",
             (Champ("date", "تاريخ الرصد", "date", requis=True),
              Champ("cellule", "الخلية", "choix", CELLULES, requis=True),
              Champ("eleve", "التلميذ(ة)", "eleve", requis=True), Champ("classe", "القسم"),
              Champ("type", "نوع الحالة", "choix", ("غياب متكرر", "تعثر دراسي", "مهدد بالانقطاع", "عنف أو نزاع",
                                                    "وضعية اجتماعية", "وضعية صحية", "حالة أخرى"), requis=True),
              Champ("description", "وصف الحالة", "long", colonne=False),
              Champ("intervention", "التدخل المنجز", "long", colonne=False),
              Champ("suivi", "المآل", "choix", ("قيد المواكبة", "عولجت", "أحيلت على جهة مختصة"))),
             (Doc("bilan", "حصيلة الرصد والمواكبة", "عدد الحالات حسب النوع والمآل، ثم لائحتها."),),
             filtre="cellule"),
    Registre("tahfiz", "التحفيز والتشجيع",
             "الشهادات التقديرية والتهاني والتشجيعات الممنوحة للتلاميذ.",
             (Champ("date", "التاريخ", "date", requis=True),
              Champ("eleve", "التلميذ(ة)", "eleve", requis=True), Champ("classe", "القسم"),
              Champ("type", "نوع التحفيز", "choix", ("شهادة تقديرية", "شهادة تفوق", "تهنئة", "تشجيع", "لوحة الشرف"),
                    requis=True),
              Champ("motif", "المناسبة أو السبب", requis=True),
              Champ("periode", "الفترة", "choix", ("الأسدوس الأول", "الأسدوس الثاني", "نهاية السنة")),
              Champ("modele", "تصميم الشهادة", colonne=False)),
             (Doc("certificat", "الشهادة (صفحة مزخرفة)", "شهادة السطر المحدد، جاهزة للطبع والتوقيع.", "ligne"),
              Doc("liste", "لائحة المتوَّجين", "كل المحفَّزين هذه السنة، أو لنوع واحد.")),
             filtre="type"),
    Registre("partenariats", "الانفتاح والشراكة",
             "اتفاقيات الشراكة مع الجمعيات والجماعات والمؤسسات، والتزامات كل طرف.",
             (Champ("partenaire", "الشريك", requis=True), Champ("objet", "موضوع الشراكة", requis=True),
              Champ("date", "تاريخ التوقيع", "date"), Champ("duree", "المدة"),
              Champ("engagements", "التزامات الطرفين", "long", colonne=False),
              Champ("etat", "الحالة", "choix", ("سارية", "قيد الإعداد", "منتهية"))),
             (Doc("registre", "سجل الشراكات", "كل الشراكات بحالتها."),
              Doc("fiche", "بطاقة شراكة", "بطاقة الشراكة المحددة بالتزامات الطرفين.", "ligne")),
             filtre="etat", par_annee=False, filtre_defaut="سارية", dossier=True,
             titre_liste="اتفاقيات الشراكة القائمة", ajout="إضافة اتفاقية شراكة"),
    Registre("annonces", "الإعلام والتواصل",
             "الإعلانات والبلاغات الموجهة للأساتذة أو أولياء الأمور أو التلاميذ.",
             (Champ("date", "التاريخ", "date", requis=True), Champ("titre", "الموضوع", requis=True),
              Champ("destinataires", "الموجه إليهم", "choix", ("الأساتذة", "أولياء الأمور", "التلاميذ", "العموم"),
                    requis=True),
              Champ("texte", "نص الإعلان", "long", requis=True, colonne=False)),
             (Doc("annonce", "الإعلان", "الإعلان المحدد، جاهز للتعليق أو التوزيع.", "ligne"),
              Doc("registre", "سجل الإعلانات", "كل إعلانات السنة.")),
             filtre="destinataires"),
    Registre("equipe", "فريق قيادة المشروع",
             "أعضاء فريق قيادة مشروع المؤسسة المندمج وصفة كل واحد، ومحضرا التشكيل والمصادقة.",
             (Champ("membre", "الاسم والنسب", "personnel", requis=True),
              Champ("ppr", "رقم التأجير"), Champ("qualite", "الصفة داخل الفريق", requis=True)),
             (Doc("liste", "لائحة فريق القيادة", "أعضاء الفريق وصفاتهم."),
              Doc("pv_formation", "محضر تشكيل فريق القيادة", "محضر الاجتماع الذي شُكّل فيه الفريق."),
              Doc("pv_validation", "محضر مصادقة مجلس التدبير", "محضر مصادقة مجلس التدبير على المشروع."))),
)}


def _ltr(texte) -> str:
    """نص لاتيني أو أرقام معزولة الاتجاه داخل السطر العربي."""
    return f"\u2066{texte}\u2069"


def registre(cle: str) -> Registre:
    if cle not in REGISTRES:
        raise ErreurRegistre("سجل غير معروف.")
    return REGISTRES[cle]


# ====================== التخزين ======================

def _annee(conn) -> str:
    a = annee_srv.annee_courante(conn)
    return a["libelle"] if a else ""


def _cle(conn, r: Registre) -> str:
    return f"reg:{r.cle}:{_annee(conn) if r.par_annee else ''}"


def _charger(conn, r: Registre) -> dict:
    d = fiches.lire(conn, _cle(conn, r)) or {}
    return {"suivant": int(d.get("suivant") or 1), "lignes": list(d.get("lignes") or [])}


def _texte(v) -> str:
    return " ".join(str(v if v is not None else "").split())


def _valider(r: Registre, valeurs: dict) -> dict:
    res = {}
    for c in r.champs:
        v = valeurs.get(c.cle)
        if c.type == "long":
            v = "\n".join(l.strip() for l in str(v or "").splitlines() if l.strip())
        elif c.type == "date":
            v = _texte(v)
            if v:
                try:
                    v = date.fromisoformat(v).isoformat()
                except ValueError:
                    raise ErreurRegistre(f"«{c.libelle}»: تاريخ غير صحيح.") from None
        elif c.type == "nombre":
            v = _texte(v)
            if v:
                if not v.isdigit():
                    raise ErreurRegistre(f"«{c.libelle}»: يُكتب عدداً صحيحاً.")
                v = int(v)
        else:
            v = _texte(v)
        if c.requis and v in ("", None):
            raise ErreurRegistre(f"«{c.libelle}» مطلوب.")
        res[c.cle] = v
    if res.get("du") and res.get("au") and res["au"] < res["du"]:
        raise ErreurRegistre("تاريخ النهاية قبل تاريخ البداية.")
    return res


def enregistrer(conn: sqlite3.Connection, cle: str, valeurs: dict, lid: int | None = None) -> int:
    r = registre(cle)
    v = _valider(r, valeurs)
    if r.filtre and r.filtre_defaut and not v.get(r.filtre):
        v[r.filtre] = r.filtre_defaut   # اتفاقية بلا حالة: تُعدّ سارية فتظهر في الصفحة الثابتة
    d = _charger(conn, r)
    if lid is None:
        lid = d["suivant"]
        d["suivant"] += 1
        d["lignes"].append({"id": lid, **v})
    else:
        for i, l in enumerate(d["lignes"]):
            if l.get("id") == lid:
                d["lignes"][i] = {"id": lid, **v}
                break
        else:
            raise ErreurRegistre("السطر غير موجود.")
    fiches.ecrire(conn, _cle(conn, r), d)
    return lid


def supprimer(conn: sqlite3.Connection, cle: str, lid: int) -> None:
    r = registre(cle)
    d = _charger(conn, r)
    d["lignes"] = [l for l in d["lignes"] if l.get("id") != lid]
    fiches.ecrire(conn, _cle(conn, r), d)


def lister(conn: sqlite3.Connection, cle: str, filtre: str | None = None, texte: str = "") -> list[dict]:
    """الأسطر: الأحدث أولاً إن كان للسجل تاريخ، وإلا بترتيب الإدخال."""
    r = registre(cle)
    ls = [{c.cle: l.get(c.cle, "") for c in r.champs} | {"id": l["id"]} for l in _charger(conn, r)["lignes"]]
    if filtre and r.filtre:
        ls = [l for l in ls if l.get(r.filtre) == filtre]
    mots = _texte(texte).split()
    if mots:
        ls = [l for l in ls if all(m in " ".join(str(x) for x in l.values()) for m in mots)]
    if any(c.cle == "date" for c in r.champs):
        ls.sort(key=lambda l: (l.get("date") or "", l["id"]), reverse=True)
    return ls


def lignes_eleve(conn: sqlite3.Connection, cle: str, nom: str) -> list[dict]:
    """أسطر تلميذ في سجل عبر كل السنوات (للبطاقة الشاملة)، مع السنة، الأحدث أولاً."""
    import json
    r = registre(cle)
    nom = _texte(nom)
    res = []
    for k, donnees in conn.execute("SELECT cle, donnees FROM fiche_json WHERE cle LIKE ?", (f"reg:{cle}:%",)):
        an = k.split(":", 2)[2]
        for l in (json.loads(donnees) or {}).get("lignes") or []:
            if _texte(l.get("eleve")) == nom:
                res.append({c.cle: l.get(c.cle, "") for c in r.champs} | {"id": l["id"], "annee": an})
    res.sort(key=lambda l: (l.get("date") or "", l["id"]), reverse=True)
    return res


def etat(r: Registre, l: dict) -> tuple[str, bool]:
    """(نص الوضعية، هل تمّ؟) لسطر في سجل له حقل وضعية."""
    if not r.etat:
        return "", True
    v = str(l.get(r.etat) or "") or r.defaut_etat
    return v, bool(v) and v != r.defaut_etat


def lire(conn: sqlite3.Connection, cle: str, lid: int) -> dict:
    l = next((x for x in lister(conn, cle) if x["id"] == lid), None)
    if l is None:
        raise ErreurRegistre("السطر غير موجود.")
    return l


def compter(conn: sqlite3.Connection, cle: str) -> int:
    return len(_charger(conn, registre(cle))["lignes"])


def total(conn: sqlite3.Connection) -> int:
    """كل أسطر كل السجلات (لبطاقة التفريغ)."""
    import json
    return sum(len((json.loads(x[0]) or {}).get("lignes") or [])
               for x in conn.execute("SELECT donnees FROM fiche_json WHERE cle LIKE 'reg:%'"))


def repartition(conn: sqlite3.Connection, cle: str, champ: str) -> list[tuple[str, int]]:
    """عدد الأسطر لكل قيمة من حقل (بترتيب الاختيارات إن وُجدت)."""
    r = registre(cle)
    n: dict[str, int] = {}
    for l in lister(conn, cle):
        k = str(l.get(champ) or "")
        if k:
            n[k] = n.get(k, 0) + 1
    ordre = list(r.champ(champ).choix)
    return sorted(n.items(), key=lambda kv: (ordre.index(kv[0]) if kv[0] in ordre else len(ordre), kv[0]))


def noms_personnel(conn: sqlite3.Connection) -> list[str]:
    return [f"{p.prenom_ar} {p.nom_ar}".strip() for p in rh.lister(conn)]


def eleves(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    """(الاسم، القسم) لتلاميذ السنة الجارية."""
    a = annee_srv.annee_courante(conn)
    if a is None:
        return []
    return [(f"{x['prenom_ar']} {x['nom_ar']}", x["classe"] or "") for x in conn.execute(
        "SELECT e.nom_ar, e.prenom_ar, c.code AS classe FROM inscription i JOIN eleve e ON e.id=i.eleve_id "
        "LEFT JOIN classe c ON c.id=i.classe_id WHERE i.annee_id=? AND i.statut IN ('inscrit','arrive') "
        "ORDER BY e.prenom_ar, e.nom_ar", (a["id"],))]


def propositions(conn: sqlite3.Connection, c: Champ) -> list[str]:
    if c.type == "personnel":
        return noms_personnel(conn)
    if c.type == "eleve":
        return [n for n, _ in eleves(conn)]
    if c.type == "ref":
        premier = registre(c.source).champs[0].cle
        return [l[premier] for l in sorted(lister(conn, c.source), key=lambda l: l["id"])]
    return list(c.choix)


def afficher(c: Champ, v) -> str:
    """قيمة حقل كما تُعرض في الجدول والوثائق."""
    if v in ("", None):
        return ""
    if c.type == "date":
        return _ltr(tx.date_chiffres(v))
    return str(v).replace("\n", " · ") if c.type == "long" else str(v)


# ====================== الوثائق ======================

_POIDS = {"long": 3.2, "texte": 2.0, "personnel": 2.2, "eleve": 2.2, "ref": 2.2, "choix": 1.6, "date": 1.3,
          "nombre": 1.0}


def _sauver(d, dossier: DossierDonnees, r: Registre, nom: str) -> Path:
    rep = dossier.archives / "السجلات" / r.titre
    rep.mkdir(parents=True, exist_ok=True)
    chemin = rep / f"{datetime.now():%Y%m%d_%H%M%S}_{nom.replace(' ', '_')}.docx"
    n = 1
    while chemin.exists():
        n += 1
        chemin = chemin.with_name(f"{chemin.stem}_{n}.docx")
    d.save(chemin)
    return chemin


def _document(conn, dossier, titre: str, sous: str = "", paysage: bool = False):
    from idara.services.docs_association import _nouveau
    from idara.services.soutien import _entete
    d = _nouveau(paysage)
    a = _annee(conn)
    _entete(d, conn, dossier, titre, " · ".join(x for x in (sous, f"السنة الدراسية {a}" if a else "") if x))
    return d


def _tableau_liste(d, r: Registre, lignes: list[dict], cles: tuple = (), largeur: float = 17.4, taille=10) -> None:
    from idara.services.soutien import _table
    champs = [r.champ(k) for k in cles] if cles else [c for c in r.champs if c.colonne]
    poids = [_POIDS.get(c.type, 2.0) for c in champs]
    dispo = largeur - 1.3
    _table(d, ["ر.ت", *[c.libelle for c in champs]],
           [[str(i), *[afficher(c, l.get(c.cle)) for c in champs]] for i, l in enumerate(lignes, 1)],
           [1.3] + [round(dispo * p / sum(poids), 2) for p in poids], taille=taille)


def _tableau_fiche(d, r: Registre, l: dict, sauf: tuple = ()) -> None:
    """بطاقة سطر واحد: العنوان والقيمة، للحقول غير الفارغة فقط."""
    from idara.services.docs_association import _cellule, _ombre, tableau
    paires = [(c.libelle, afficher(c, l.get(c.cle)) if c.type != "long" else str(l.get(c.cle) or ""))
              for c in r.champs if c.cle not in sauf and l.get(c.cle) not in ("", None)]
    t = tableau(d, len(paires), 2, largeurs=[5.0, 12.4])
    for i, (lib, v) in enumerate(paires):
        _cellule(t.cell(i, 0), lib, gras=True, taille=11)
        _ombre(t.cell(i, 0))
        _cellule(t.cell(i, 1), v, taille=11, centre=False)


def _exiger_lignes(lignes: list) -> None:
    if not lignes:
        raise ErreurRegistre("لا أسطر في هذا السجل بعد.")


def _gen_liste(conn, dossier, r: Registre, doc: Doc, lignes, ligne, filtre, cible) -> Path:
    from idara.services.soutien import _signature
    _exiger_lignes(lignes)
    champs = doc.colonnes or tuple(c.cle for c in r.champs if c.colonne)
    paysage = len(champs) > 5
    d = _document(conn, dossier, doc.titre, filtre or "", paysage)
    _tableau_liste(d, r, lignes, doc.colonnes, 26.0 if paysage else 17.4)
    _signature(d, conn)
    return _sauver(d, dossier, r, doc.titre + (f"_{filtre}" if filtre else ""))


def _gen_fiche(conn, dossier, r: Registre, doc: Doc, lignes, ligne, filtre, cible) -> Path:
    from idara.services.soutien import _signature
    d = _document(conn, dossier, doc.titre)
    _tableau_fiche(d, r, ligne, r.internes)
    _signature(d, conn)
    return _sauver(d, dossier, r, doc.titre)


def _gen_bilan_cas(conn, dossier, r, doc, lignes, ligne, filtre, cible) -> Path:
    from idara.services.docs_association import para
    from idara.services.soutien import _signature, _table
    _exiger_lignes(lignes)
    d = _document(conn, dossier, doc.titre, filtre or "الخليتان", True)
    para(d, f"عدد الحالات المرصودة: {len(lignes)}", gras=True, taille=11, apres=4)
    for titre, champ in (("حسب نوع الحالة", "type"), ("حسب المآل", "suivi")):
        n: dict[str, int] = {}
        for l in lignes:
            if l.get(champ):
                n[l[champ]] = n.get(l[champ], 0) + 1
        if n:
            para(d, titre, gras=True, taille=11, apres=2)
            _table(d, list(n), [[str(v) for v in n.values()]], [round(24.0 / len(n), 2)] * len(n))
            para(d, "", apres=4)
    para(d, "لائحة الحالات", gras=True, taille=11, apres=2)
    _tableau_liste(d, r, lignes, ("date", "eleve", "classe", "type", "intervention", "suivi"), 26.0, taille=9)
    _signature(d, conn)
    return _sauver(d, dossier, r, doc.titre)


def _gen_pv_reunion(conn, dossier, r, doc, lignes, ligne, filtre, cible) -> Path:
    from idara.services.docs_association import para
    from idara.services.soutien import _signature
    d = _document(conn, dossier, f"محضر اجتماع {ligne['cellule']}", f"المنعقد يوم {tx.date_longue_ar(ligne['date'])}")
    for titre, k in (("جدول الأعمال", "ordre"), ("الحاضرون", "presents"), ("الخلاصات والقرارات", "conclusions")):
        if ligne.get(k):
            para(d, titre + ":", gras=True, taille=12, apres=2)
            for x in ligne[k].splitlines():
                para(d, "- " + x, taille=11, apres=0)
            para(d, "", apres=4)
    _signature(d, conn, "توقيع رئيس(ة) الخلية:")
    return _sauver(d, dossier, r, "محضر اجتماع")


def _bordure_page(d, couleur: str = "2E3192") -> None:
    """إطار مزدوج حول الصفحة (للشهادات)."""
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    sect = d.sections[0]._sectPr
    b = OxmlElement("w:pgBorders")
    b.set(qn("w:offsetFrom"), "page")
    for cote in ("top", "left", "bottom", "right"):
        e = OxmlElement(f"w:{cote}")
        e.set(qn("w:val"), "thinThickSmallGap")
        e.set(qn("w:sz"), "24")
        e.set(qn("w:space"), "24")
        e.set(qn("w:color"), couleur)
        b.append(e)
    # ترتيب عناصر sectPr مفروض: pgBorders بعد pgMar
    ref = sect.find(qn("w:pgMar"))
    if ref is not None:
        ref.addnext(b)
    else:
        sect.append(b)


def _gen_certificat(conn, dossier, r, doc, lignes, ligne, filtre, cible) -> Path:
    from docx.shared import RGBColor

    from idara.services.docs_association import _nouveau, para
    d = _nouveau(paysage=True)
    _bordure_page(d)
    etab = etab_srv.lire_etablissement(conn)
    dr = etab_srv.directeur_actuel(conn)
    if etab:
        para(d, "المملكة المغربية", gras=True, taille=11, centre=True, apres=0)
        para(d, f"المديرية الإقليمية: {etab.direction_ar}", taille=11, centre=True, apres=0)
        para(d, etab.nom_ar, gras=True, taille=13, centre=True, apres=14)
    titre = {"تهنئة": "تهنئة", "تشجيع": "شهادة تشجيع", "لوحة الشرف": "لوحة الشرف"}.get(ligne["type"], "شهادة تقديرية")
    p = para(d, "✦  " + titre + "  ✦", gras=True, taille=40, centre=True, apres=14)
    for run in p.runs:
        run.font.color.rgb = RGBColor(0x2E, 0x31, 0x92)
    para(d, "تتشرف إدارة المؤسسة وأطرها التربوية بمنح هذه الشهادة إلى التلميذ(ة):", taille=16, centre=True, apres=8)
    p = para(d, ligne["eleve"], gras=True, taille=30, centre=True, apres=8)
    for run in p.runs:
        run.font.color.rgb = RGBColor(0x9A, 0x6A, 0x0F)
    if ligne.get("classe"):
        para(d, f"القسم: {ligne['classe']}", taille=15, centre=True, apres=6)
    para(d, f"وذلك: {ligne['motif']}" + (f" ({ligne['periode']})" if ligne.get("periode") else ""),
         taille=16, centre=True, apres=6)
    para(d, "مع متمنياتنا بدوام التفوق والنجاح.", taille=14, centre=True, apres=16)
    a = _annee(conn)
    ville = etab.ville_redaction_ar if etab and etab.ville_redaction_ar else ""
    para(d, (f"{ville}، في " if ville else "في ") + tx.date_ar(ligne["date"])
         + (f"  ·  السنة الدراسية {a}" if a else ""), taille=12, centre=True, apres=6)
    nom = f"{dr['prenom_ar']} {dr['nom_ar']}".strip() if dr is not None else ""
    para(d, "مدير(ة) المؤسسة" + (f": {nom}" if nom else ""), gras=True, taille=13, centre=True)
    return _sauver(d, dossier, r, f"{titre}_{ligne['eleve']}")


def _gen_annonce(conn, dossier, r, doc, lignes, ligne, filtre, cible) -> Path:
    from idara.services.docs_association import para
    from idara.services.soutien import _signature
    d = _document(conn, dossier, "إعـــلان", f"إلى: {ligne['destinataires']}")
    para(d, ligne["titre"], gras=True, taille=15, centre=True, apres=10)
    for x in ligne["texte"].splitlines():
        para(d, x, taille=13, apres=4)
    _signature(d, conn)
    return _sauver(d, dossier, r, "إعلان")


def _trouver_personnel(conn, nom: str):
    return next((p for p in rh.lister(conn, actifs_seulement=False)
                 if f"{p.prenom_ar} {p.nom_ar}".strip() == nom), None)


_MINISTERE = "السيد المدير الإقليمي لوزارة التربية الوطنية والتعليم الأولي والرياضة"


def _gen_demande(conn, dossier, r, doc, lignes, ligne, filtre, cible) -> Path:
    from idara.services.docs_association import para
    from idara.services.soutien import _signature
    etab = etab_srv.lire_etablissement(conn)
    p = _trouver_personnel(conn, ligne["personnel"])
    typ = ligne["type"]
    contre_visite = typ == "إجراء فحص طبي مضاد"
    interne = typ == "إذن بالتغيب"
    d = _document(conn, dossier, "طلب " + typ if not typ.startswith("إجراء") else "طلب إجراء فحص طبي مضاد",
                  f"بتاريخ {tx.date_ar(ligne['date'])}")
    ident = [ligne["personnel"]]
    if p is not None:
        ident += [x for x in (rh.cadre_accorde(p.cadre, p.sexe) if p.cadre else "",
                              f"رقم التأجير: {_ltr(p.ppr)}" if p.ppr else "") if x]
    periode = ""
    if ligne.get("du"):
        periode = f" ابتداء من {tx.date_ar(ligne['du'])}"
        if ligne.get("au"):
            n = (date.fromisoformat(ligne["au"]) - date.fromisoformat(ligne["du"])).days + 1
            periode += f" إلى غاية {tx.date_ar(ligne['au'])} ({tx.duree_jours_ar(n)})"
    if contre_visite:
        para(d, "من مدير(ة) المؤسسة", gras=True, taille=12, apres=0)
        para(d, f"إلى {_MINISTERE}" + (f" بـ{etab.direction_ar}" if etab and etab.direction_ar else ""),
             gras=True, taille=12, apres=8)
        para(d, "الموضوع: طلب إجراء فحص طبي مضاد.", gras=True, taille=12, apres=8)
        para(d, "سلام تام بوجود مولانا الإمام، وبعد،", taille=12, apres=4)
        para(d, "يشرفني أن أطلب منكم العمل على إجراء فحص طبي مضاد للمعني(ة) بالأمر: " + "، ".join(ident)
             + ("، بعد إدلائه(ا) بشهادة طبية" + periode if periode else "") + ".", taille=12, apres=4)
    else:
        para(d, "من: " + "، ".join(ident), gras=True, taille=12, apres=0)
        if interne:
            para(d, "إلى السيد(ة) مدير(ة) المؤسسة", gras=True, taille=12, apres=8)
        else:
            para(d, f"إلى {_MINISTERE}" + (f" بـ{etab.direction_ar}" if etab and etab.direction_ar else ""),
                 gras=True, taille=12, apres=0)
            para(d, "على يد السيد(ة) مدير(ة) المؤسسة (تحت إشراف السلم الإداري)", taille=11, apres=8)
        para(d, f"الموضوع: طلب {typ}.", gras=True, taille=12, apres=8)
        para(d, "سلام تام بوجود مولانا الإمام، وبعد،", taille=12, apres=4)
        para(d, f"يشرفني أن ألتمس منكم الترخيص لي بـ{typ}{periode}.", taille=12, apres=4)
    if ligne.get("motif"):
        para(d, ("التوضيح: " if contre_visite else "السبب: ") + ligne["motif"].replace("\n", "، "), taille=12, apres=4)
    para(d, "وتقبلوا فائق التقدير والاحترام.", taille=12, apres=10)
    if contre_visite:
        _signature(d, conn)
    else:
        _signature(d, conn, "توقيع المعني(ة) بالأمر:")
        para(d, "", apres=10)
        para(d, "رأي مدير(ة) المؤسسة:", gras=True, taille=11)
    return _sauver(d, dossier, r, f"طلب_{typ}_{ligne['personnel']}")


def _gen_fiche_personnelle(conn, dossier, r, doc, lignes, ligne, filtre, cible) -> Path:
    from idara.services.docs_association import _cellule, _ombre, para, tableau
    p = _trouver_personnel(conn, cible or "")
    if p is None:
        raise ErreurRegistre("اختر الموظف(ة) الذي تريد ورقته الشخصية.")
    etab = etab_srv.lire_etablissement(conn)
    d = _document(conn, dossier, "الورقة الشخصية")

    def dt(v):
        return _ltr(tx.date_chiffres(v)) if v else ""
    paires = [
        ("المؤسسة", etab.nom_ar if etab else ""), ("رمز المؤسسة", _ltr(etab.code_etab) if etab and etab.code_etab else ""),
        ("الاسم العائلي والشخصي", f"{p.nom_ar} {p.prenom_ar}".strip()),
        ("الاسم بالحروف اللاتينية", _ltr(f"{p.nom_fr} {p.prenom_fr}".strip().upper()) if p.nom_fr or p.prenom_fr else ""),
        ("رقم التأجير", _ltr(p.ppr) if p.ppr else ""), ("رقم البطاقة الوطنية", _ltr(p.cin) if p.cin else ""),
        ("تاريخ الازدياد", dt(p.date_naissance)), ("الجنس", {"M": "ذكر", "F": "أنثى"}.get(p.sexe, "")),
        ("تاريخ التوظيف", dt(p.date_recrutement)), ("الإطار الحالي", rh.cadre_accorde(p.cadre, p.sexe) if p.cadre else ""),
        ("الدرجة", p.grade), ("الرتبة", str(p.echelon or "")),
        ("تاريخ الدرجة", dt(p.date_grade)), ("تاريخ الرتبة", dt(p.date_echelon)),
        ("المهمة الحالية", p.fonction), ("تاريخ التعيين بالمؤسسة", dt(p.date_affectation)),
        ("المادة المدرَّسة", p.matiere), ("سلك التدريس", p.cycle),
        ("آخر نقطة للتفتيش", "" if p.note_inspection in ("", None) else _ltr(str(p.note_inspection))),
        ("تاريخ آخر تفتيش", dt(p.date_inspection)),
        ("الهاتف", _ltr(p.telephone) if p.telephone else ""), ("العنوان", p.adresse),
    ]
    t = tableau(d, (len(paires) + 1) // 2, 4, largeurs=[4.0, 4.7, 4.0, 4.7])
    for i, (lib, v) in enumerate(paires):
        li, co = divmod(i, 2)
        _cellule(t.cell(li, co * 2), lib, gras=True, taille=10)
        _ombre(t.cell(li, co * 2))
        _cellule(t.cell(li, co * 2 + 1), str(v or ""), taille=10)
    para(d, "", apres=8)
    t = tableau(d, 2, 2, largeurs=[8.7, 8.7])
    _cellule(t.cell(0, 0), "توقيع المعني(ة) بالأمر", gras=True, taille=11)
    _cellule(t.cell(0, 1), "توقيع وخاتم مدير(ة) المؤسسة", gras=True, taille=11)
    for j in (0, 1):
        _ombre(t.cell(0, j))
        _cellule(t.cell(1, j), "\n\n\n", taille=11)
    return _sauver(d, dossier, r, f"الورقة_الشخصية_{cible}")


def _gen_pv_equipe(conn, dossier, r, doc, lignes, ligne, filtre, cible) -> Path:
    from idara.services.docs_association import para
    from idara.services.soutien import _signature, _table
    _exiger_lignes(lignes)
    intitule = ""
    try:
        from idara.services import projet_etab
        pr = projet_etab.projet_actif(conn)
        intitule = pr["intitule"] if pr else ""
    except Exception:  # noqa: BLE001 — المشروع غير مسجل: المحضر دون عنوانه
        pass
    lignes = sorted(lignes, key=lambda l: l["id"])
    d = _document(conn, dossier, doc.titre, f"مشروع المؤسسة المندمج: {intitule}" if intitule else "")
    etab = etab_srv.lire_etablissement(conn)
    nom = etab.nom_ar if etab else "المؤسسة"
    if doc.cle == "pv_formation":
        para(d, f"انعقد بمقر {nom} اجتماع خُصص لتشكيل فريق قيادة مشروع المؤسسة المندمج. وبعد التداول، تم الاتفاق "
                "على أن يتكون الفريق من السيدات والسادة الآتية أسماؤهم:", taille=12, apres=6)
    else:
        para(d, f"اجتمع مجلس تدبير {nom} لدراسة مشروع المؤسسة المندمج الذي أعده فريق القيادة. وبعد عرض مكونات "
                "المشروع (التشخيص، الأولويات، خطة العمل، الميزانية) ومناقشتها، صادق المجلس على المشروع. "
                "وقد حضر عن فريق القيادة:", taille=12, apres=6)
    _table(d, ["ر.ت", "الاسم والنسب", "رقم التأجير", "الصفة داخل الفريق", "التوقيع"],
           [[str(i), l["membre"], _ltr(l["ppr"]) if l.get("ppr") else "", l["qualite"], ""]
            for i, l in enumerate(lignes, 1)], [1.0, 5.0, 2.8, 5.2, 3.4])
    _signature(d, conn)
    return _sauver(d, dossier, r, doc.titre)


GENERATEURS = {("cellule_cas", "bilan"): _gen_bilan_cas, ("cellule_reunions", "pv"): _gen_pv_reunion,
               ("tahfiz", "certificat"): _gen_certificat, ("annonces", "annonce"): _gen_annonce,
               ("demandes", "demande"): _gen_demande, ("demandes", "fiche_personnelle"): _gen_fiche_personnelle,
               ("equipe", "pv_formation"): _gen_pv_equipe, ("equipe", "pv_validation"): _gen_pv_equipe}


def generer(conn: sqlite3.Connection, dossier: DossierDonnees, cle: str, doc: str, lid: int | None = None,
            filtre: str | None = None, cible: str | None = None) -> Path:
    r = registre(cle)
    dc = next((x for x in r.docs if x.cle == doc), None)
    if dc is None:
        raise ErreurRegistre("وثيقة غير معروفة.")
    ligne = None
    if dc.portee == "ligne":
        if lid is None:
            raise ErreurRegistre("اختر سطراً من الجدول أولاً.")
        ligne = lire(conn, cle, lid)
    lignes = lister(conn, cle, filtre)
    fn = GENERATEURS.get((cle, doc)) or (_gen_fiche if dc.portee == "ligne" else _gen_liste)
    return fn(conn, dossier, r, dc, lignes, ligne, filtre, cible)
