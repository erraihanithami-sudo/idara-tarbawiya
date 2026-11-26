"""مقترح برنامج العمل السنوي (نموذج المدير 2026-11-26).

يُقترح البرنامج افتراضياً في سبعة محاور على شكل نموذج المدير، ويعدّله المستعمل بالإضافة والحذف والتعديل:
1 عمليات الدخول المدرسي، 2 اجتماعات مجالس المؤسسة، 3 المراقبة المستمرة والامتحانات، 4 أنشطة الأندية التربوية،
5 الأنشطة المرتبطة بمشروع المؤسسة، 6 الإعداد للموسم الدراسي المقبل، 7 لائحة العطل المدرسية.

- التواريخ التي يحددها المقرر الوزاري لتنظيم السنة الدراسية تُؤخذ من ملف المقرر المرفق بالبرنامج
  (resources/mouqarrar)، وتُحسب من جديد كل سنة.
- الأيام العالمية والوطنية تُؤرَّخ بتواريخها الثابتة في السنة الدراسية الجارية، وينبَّه إلى ما يصادف منها عطلة.
- باقي التواريخ تُترك فارغة ليحددها المدير.
- لائحة العطل تُولَّد من المقرر ولا تُعدَّل يدوياً.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from idara.services import annee as annee_srv
from idara.services import calendrier as cal
from idara.services import fiches
from idara.services import textes as tx


class ErreurProgramme(ValueError):
    """رسالة موجهة للمدير بالعربية."""


# (المفتاح، العنوان، اللون)
SECTIONS = (
    ("rentree", "عمليات الدخول المدرسي", "1565C0"),
    ("conseils", "اجتماعات مجالس المؤسسة", "6A1B9A"),
    ("evaluation", "المراقبة المستمرة والامتحانات", "C62828"),
    ("clubs", "أنشطة الأندية التربوية", "2E7D32"),
    ("projet", "الأنشطة المرتبطة بمشروع المؤسسة", "EF6C00"),
    ("prochaine", "الإعداد للموسم الدراسي المقبل", "00838F"),
)
CONGES = ("conges", "لائحة العطل المدرسية", "AD1457")
TITRES = {k: t for k, t, _ in SECTIONS + (CONGES,)}
SELON_PROJET = "حسب الجدولة الزمنية المتضمنة في مشروع المؤسسة المصادق عليه من طرف مجلس التدبير"


# ---------- الأيام العالمية والوطنية (تواريخ ثابتة) ----------
# (المفتاح، الشهر، اليوم) أو قاعدة خاصة. السنة تُستنتج من السنة الدراسية: شتنبر-دجنبر للسنة الأولى، والباقي للثانية.
JOURNEES = {
    "nettoyage": ("rule", "samedi3_09"),    # اليوم العالمي للتنظيف: السبت الثالث من شتنبر
    "enseignant": (10, 5),
    "environnement_arabe": (10, 14),
    "alimentation": (10, 16),
    "enfant": (11, 20),
    "langue_arabe": (12, 18),
    "internet": ("rule", "mardi2_02"),      # اليوم العالمي للأنترنيت الآمن: الثلاثاء الثاني من فبراير
    "securite_routiere": (2, 18),
    "arbre": (3, 21),                       # اليوم العالمي للغابات واليوم الوطني للشجرة
    "eau": (3, 22),
    "terre": (4, 22),
    "livre": ((4, 23), (4, 26)),            # اليوم العالمي للكتاب وحقوق المؤلف (23) واليوم العالمي للملكية الفكرية (26)
    "biodiversite": (5, 22),
    "sans_tabac": (5, 31),
}


def _annee_de(mois: int, y1: int) -> int:
    return y1 if mois >= 9 else y1 + 1


def _nieme(y: int, m: int, jour_semaine: int, n: int) -> date:
    d = date(y, m, 1)
    d += timedelta(days=(jour_semaine - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def date_journee(cle: str, y1: int) -> tuple[date, date]:
    v = JOURNEES[cle]
    if v[0] == "rule":
        if v[1] == "samedi3_09":
            d = _nieme(y1, 9, 5, 3)
        else:   # mardi2_02
            d = _nieme(y1 + 1, 2, 1, 2)
        return d, d
    if isinstance(v[0], tuple):
        (m1, j1), (m2, j2) = v
        return date(_annee_de(m1, y1), m1, j1), date(_annee_de(m2, y1), m2, j2)
    m, j = v
    d = date(_annee_de(m, y1), m, j)
    return d, d


# ---------- المقترح الافتراضي ----------
# كل سطر: (المحطة، العمليات والأنشطة، المرجع) والمرجع: "" فارغ، "m:<مفتاح>" أو "m:<أ>..<ب>" أو "m:<أ>+<ب>" من المقرر،
# "j:<مفتاح>" يوم عالمي أو وطني، "mois:<شهر>" خلال شهر، "t:<نص>" نص ثابت، "p:..." بادئة «ابتداء من».
_R, _C, _E, _A, _P, _N = (k for k, _, _ in SECTIONS)
_TARL = "تمرير رائز طارل"
DEFAUT: dict[str, list[tuple[str, str, str]]] = {
    _R: [
        ("الالتحاق بالعمل", "توقيع محاضر الالتحاق بالعمل بالنسبة لهيئة الإدارة التربوية.", "m:debut_annee"),
        ("الالتحاق بالعمل", "توقيع محاضر الالتحاق بالعمل بالنسبة لهيئة التدريس.", "m:entree_ens"),
        ("بعض العمليات التقنية", "تزويد أطر هيئة التدريس بالملف التربوي: المقرر الوزاري، ولوائح التلاميذ، والمذكرة "
         "التنظيمية المحلية رقم 1 لتدبير الدخول المدرسي، والجدولة الزمنية لأهم المحطات التدبيرية خلال السنة الدراسية.\n"
         "إلقاء كلمة افتتاح السنة الدراسية من طرف رئيس المؤسسة.", "m:entree_ens"),
        ("استقبال التلميذات والتلاميذ", "التحاق أطفال التعليم الأولي وتلاميذ المستويات الستة حسب الجدولة الوزارية.\n"
         "إطلاع التلاميذ على النظام الداخلي للمؤسسة والقسم، وتقديم الأندية التربوية وأدوار خلايا اليقظة والإنصات "
         "والوساطة.", "m:eleves_ps_12..eleves_56"),
        ("الإعداد القبلي لإنجاح محطات الدخول المدرسي", "تنظيم ورشات تحضيرية تحاكي " + _TARL + ".\n"
         "استقبال التلاميذ وإطلاعهم على رزنامة " + _TARL + ".\n"
         "انطلاق عملية " + _TARL + " لجميع المستويات.\n"
         "انطلاق عملية الدعم المكثف.\n"
         "تمرير الروائز البعدية بعد الانتهاء من أنشطة الدعم (طارل).\n"
         "الانطلاق في التدريس الصريح والدعم التربوي.", ""),
        ("الانطلاق الفعلي للدراسة", "ضمان انطلاق الدراسة بشكل فعلي، مع تأمين الزمن الدراسي.\n"
         "الالتزام الفعلي بإجراءات " + _TARL + ".\n"
         "الشروع في مراقبة غياب التلميذات والتلاميذ.\n"
         "تعبئة المذكرة اليومية من طرف هيئة التدريس.", "m:debut_etudes"),
        ("استقبال أطر هيئة التأطير والمراقبة", "مناقشة التدابير الإجرائية المرتبطة بـ" + _TARL + " وخطط الدعم "
         "والمعالجة، ومناقشة جداول الحصص والأساتذة المعنيين بالتكوين المستمر.", ""),
        ("التسجيل وإعادة التسجيل", "إنهاء جميع العمليات المرتبطة بالتسجيل وإعادة التسجيل.\n"
         "جعل التعبئة المجتمعية المستدامة آلية إجرائية لتشجيع التمدرس.", ""),
        ("لقاءات تواصلية مع الشركاء", "لقاء تواصلي مع جمعية الآباء لمناقشة ترتيبات الدخول المدرسي وتقييم حصيلة "
         "الدخول المدرسي السابق.\n"
         "تشجيع الأسر على أداء واجبات التسجيل، بما في ذلك التأمين المدرسي لفائدة التلاميذ.", ""),
        ("اجتماعات عامة مع العاملين بالمؤسسة", "استكمال تحيين الهياكل التنظيمية للمؤسسة: مجالس المؤسسة، وخلية "
         "اليقظة، وخلية الإنصات والوساطة.", ""),
    ],
    _C: [
        ("تفعيل مجالس المؤسسة", "اتخاذ كافة الإجراءات والتدابير التي تمكن من تفعيل أدوار مجلس التدبير والمجلس "
         "التربوي والمجالس التعليمية ومجالس الأقسام.\n"
         "تأسيس الأندية التربوية والمحترفات الفنية في إطار المجلس التربوي.", ""),
        ("الاجتماع الأول لمجالس المؤسسة", "وضع الصيغة النهائية لبرنامج العمل السنوي والنظام الداخلي للمؤسسة قصد "
         "عرضهما على مجلس التدبير للمصادقة عليهما، وتوفير مستلزمات التنفيذ.\n"
         "تقييم حصيلة إنجاز مشروع المؤسسة وتنزيله.", ""),
        ("الاجتماع الثاني لمجالس المؤسسة", "وضع جدولة زمنية لتدبير العمليات المرتبطة بالأسدوس الثاني.", ""),
        ("الاجتماع الثالث لمجالس المؤسسة", "وضع جدولة زمنية لتدبير العمليات المرتبطة بنهاية السنة الدراسية.\n"
         "وضع التوجهات العامة لبرنامج عمل السنة الموالية.", ""),
        ("الاجتماع الرابع لمجالس المؤسسة", "تقويم حصيلة السنة الدراسية والمصادقة على مشروع التقرير السنوي المتعلق "
         "بسير عمل المؤسسة.\n"
         "تحيين النظام الداخلي للمؤسسة عند الاقتضاء.\n"
         "إعداد مشروع البرنامج السنوي لأنشطة المؤسسة للسنة الدراسية الموالية.", ""),
        ("تنظيم الندوات واللقاءات التربوية", "التنسيق مع هيئة التأطير والمراقبة التربوية لبرمجة الندوات واللقاءات "
         "التربوية لفائدة الأطر التربوية ومربيات التعليم الأولي، بشكل يراعي السير العادي للدراسة ويؤمّن الحصص "
         "الدراسية المبرمجة.", "t:طيلة السنة الدراسية"),
    ],
    _E: [
        ("الأسدوس الأول", "إجراء آخر فروض المراقبة المستمرة برسم الأسدوس الأول.", "m:s1_derniers_ctrl"),
        ("الأسدوس الأول", "انتهاء مسك نقط آخر فروض المراقبة المستمرة.", "m:s1_saisie"),
        ("الأسدوس الأول", "استصدار بيانات النقط عبر منظومة مسار.", "p:s1_bulletins_massar"),
        ("الأسدوس الأول", "عقد مجالس الأقسام.", "m:s1_conseils"),
        ("الأسدوس الأول", "توزيع بيانات النقط.", "m:s1_distribution"),
        ("الأسدوس الثاني", "إجراء آخر فروض المراقبة المستمرة برسم الأسدوس الثاني.", "m:s2_derniers_ctrl"),
        ("الأسدوس الثاني", "انتهاء مسك نقط آخر فروض المراقبة المستمرة.", "m:s2_saisie"),
        ("الأسدوس الثاني", "استصدار بيانات النقط عبر منظومة مسار.", "p:s2_bulletins_massar"),
        ("الأسدوس الثاني", "عقد مجالس الأقسام.", "m:s2_conseils"),
        ("الأسدوس الثاني", "توزيع بيانات النقط.", "m:s2_distribution"),
        ("الامتحان الموحد المحلي", "الامتحان الموحد المحلي لنيل شهادة الدروس الابتدائية.", "m:exam_local"),
        ("الامتحان الموحد المحلي", "انتهاء مسك نقط الامتحان الموحد المحلي.", "m:exam_local_saisie"),
        ("الامتحان الموحد الإقليمي", "الإعداد الجماعي للامتحان الموحد الإقليمي لنيل شهادة الدروس الابتدائية.",
         "m:prep_prov"),
        ("الامتحان الموحد الإقليمي", "الامتحان الموحد الإقليمي لنيل شهادة الدروس الابتدائية.", "m:exam_prov"),
    ],
    _A: [
        ("أنشطة التربية الصحية والبيئية", "تشكيل النادي الصحي والبيئي.", ""),
        ("أنشطة التربية الصحية والبيئية", "حملة نظافة بالمؤسسة بمناسبة اليوم العالمي للتنظيف.", "j:nettoyage"),
        ("أنشطة التربية الصحية والبيئية", "حملة نظافة بالمؤسسة بمناسبة اليوم العربي للبيئة.", "j:environnement_arabe"),
        ("أنشطة التربية الصحية والبيئية", "أنشطة خاصة باليوم العالمي للتغذية.", "j:alimentation"),
        ("أنشطة التربية الصحية والبيئية", "الزيارة الدورية لهيئة الصحة لمراقبة الوضعية الصحية لتلاميذ المستوى "
         "الأول.", ""),
        ("أنشطة التربية الصحية والبيئية", "حملة تحسيسية حول التلقيح لفائدة التلميذات المعنيات، بتنسيق مع المركز "
         "الصحي.", ""),
        ("أنشطة التربية الصحية والبيئية", "ملصقات حول الاهتمام بنظافة جسمي ومحيطي.", ""),
        ("أنشطة التربية الصحية والبيئية", "تنظيم مسابقة في التربية التشكيلية حول موضوع النظافة.", ""),
        ("أنشطة التربية الصحية والبيئية", "حملة تشجير بمناسبة اليوم الوطني للشجرة واليوم العالمي للغابات.",
         "j:arbre"),
        ("أنشطة التربية الصحية والبيئية", "أنشطة تحسيسية بمناسبة اليوم العالمي للماء.", "j:eau"),
        ("أنشطة التربية الصحية والبيئية", "استضافة ممرض(ة) المركز الصحي لتنشيط يوم دراسي حول فوائد الغذاء الصحي.",
         ""),
        ("أنشطة التربية الصحية والبيئية", "عملية البستنة بمناسبة اليوم العالمي للأرض.", "j:terre"),
        ("أنشطة التربية الصحية والبيئية", "التوعية بالتربية الطرقية من طرف رجال الأمن.", ""),
        ("أنشطة التربية الصحية والبيئية", "تهيئة حديقة المؤسسة بمناسبة اليوم الدولي للتنوع البيولوجي.",
         "j:biodiversite"),
        ("أنشطة التربية الصحية والبيئية", "محاضرات حول أضرار التدخين بمناسبة اليوم العالمي بدون تدخين.",
         "j:sans_tabac"),
        ("الأنشطة الثقافية والفنية والرياضية", "تشكيل النادي الرياضي والثقافي.", ""),
        ("الأنشطة الثقافية والفنية والرياضية", "الاحتفال باليوم العالمي للمدرس.", "j:enseignant"),
        ("الأنشطة الثقافية والفنية والرياضية", "الاحتفال بعيدي المسيرة الخضراء والاستقلال.", "m:massira+istiqlal"),
        ("الأنشطة الثقافية والفنية والرياضية", "الاحتفال باليوم العالمي لحقوق الطفل.", "j:enfant"),
        ("الأنشطة الثقافية والفنية والرياضية", "الاحتفال باليوم الوطني للتعاون المدرسي.",
         "mois:11:حسب المذكرة السنوية"),
        ("الأنشطة الثقافية والفنية والرياضية", "الانطلاق الفعلي للإذاعة المدرسية.", ""),
        ("الأنشطة الثقافية والفنية والرياضية", "الاحتفال باليوم العالمي للغة العربية.", "j:langue_arabe"),
        ("الأنشطة الثقافية والفنية والرياضية", "المشاركة في إقصائيات المسابقة الثقافية.", ""),
        ("الأنشطة الثقافية والفنية والرياضية", "التحسيس حول الاستعمال الآمن للأنترنيت بمناسبة اليوم العالمي "
         "للأنترنيت الآمن.", "j:internet"),
        ("الأنشطة الثقافية والفنية والرياضية", "المشاركة في مسابقات التشبيك الموضوعاتي.", ""),
        ("الأنشطة الثقافية والفنية والرياضية", "تخليد اليوم الوطني للسلامة الطرقية.", "j:securite_routiere"),
        ("الأنشطة الثقافية والفنية والرياضية", "القراءة في الهواء الطلق (حديقة المؤسسة) بمناسبة اليوم العالمي للكتاب "
         "وحقوق المؤلف واليوم العالمي للملكية الفكرية.", "j:livre"),
        ("الأنشطة الثقافية والفنية والرياضية", "المشاركة في التظاهرات المسرحية.", ""),
        ("الأنشطة الثقافية والفنية والرياضية", "حفل نهاية السنة الدراسية وتكريم وتحفيز المتميزين والمتميزات.", ""),
    ],
    _P: [
        ("إرساء وتنفيذ مشروع المؤسسة", "الدعم التربوي.", "t:" + SELON_PROJET),
        ("إرساء وتنفيذ مشروع المؤسسة", "إنتاج مجلة الحياة المدرسية.", "t:" + SELON_PROJET),
        ("إرساء وتنفيذ مشروع المؤسسة", "تتبع تنزيل مجالات مشروع المؤسسة.", "t:" + SELON_PROJET),
        ("إرساء وتنفيذ مشروع المؤسسة", "مسابقة في القراءة بالعربية والفرنسية.", "t:" + SELON_PROJET),
        ("إرساء وتنفيذ مشروع المؤسسة", "المجلة الحائطية من إنتاج التلاميذ.", "t:" + SELON_PROJET),
        ("إرساء وتنفيذ مشروع المؤسسة", "تجويد الإنتاج الكتابي والشفهي بتوظيف مكتبة القسم، ومسابقة ثقافية في الإبداع "
         "القصصي.", "t:" + SELON_PROJET),
        ("إرساء وتنفيذ مشروع المؤسسة", "تجويد المنتوج التعليمي لأقسام التعليم الأولي بتكثيف الأنشطة الموازية.",
         "t:" + SELON_PROJET),
    ],
    _N: [
        ("الإعداد القبلي للروائز", "الإعداد القبلي لتمرير رائز طارل.\n"
         "الإعداد القبلي لتمرير روائز تشخيص المكتسبات للمستوى الأول.", ""),
        ("برنامج العمل السنوي", "إعداد مشروع برنامج العمل السنوي للسنة الدراسية الموالية.", ""),
        ("استرجاع العدة المعلوماتية", "استرجاع العدة المعلوماتية من حواسب وأجهزة التحكم في العتاد المعلوماتي.", ""),
        ("التسجيل وإعادة التسجيل", "التسجيل الرقمي للتلاميذ الجدد عبر منظومة مسار.", "m:inscription_massar"),
        ("التسجيل وإعادة التسجيل", "إعادة تسجيل التلاميذ.", "m:reinscription"),
        ("توقيع محاضر الخروج", "توقيع أطر التدريس محاضر الخروج.", "m:sortie_ens"),
        ("توقيع محاضر الخروج", "توقيع أطر الإدارة التربوية محاضر الخروج بعد إتمام جميع المهام الإدارية "
         "والتدبيرية.", "m:sortie_admin"),
    ],
}


def _annee(conn) -> sqlite3.Row:
    a = annee_srv.annee_courante(conn)
    if a is None:
        raise ErreurProgramme("لا سنة دراسية جارية.")
    return a


def _y1(libelle: str) -> int:
    return int(libelle.split("/")[0])


def _stations_m(libelle: str) -> dict[str, cal.Station]:
    return {s.cle[2:]: s for s in cal.stations_ministerielles(libelle)}


def _vacances(libelle: str) -> list[cal.Station]:
    return [s for s in cal.stations_ministerielles(libelle) if s.type in ("conge", "fete")]


def _resoudre(ref: str, libelle: str, m: dict) -> dict:
    """يحوّل مرجع السطر إلى تواريخ: {debut, fin, periode, joint, prefixe, source}."""
    r = {"debut": "", "fin": "", "periode": "", "joint": False, "prefixe": "", "source": ""}
    if not ref:
        return r
    typ, _, v = ref.partition(":")
    if typ in ("m", "p"):
        if "+" in v:
            a, b = v.split("+")
            joint = True
        elif ".." in v:
            a, b = v.split("..")
            joint = False
        else:
            a = b = v
            joint = False
        if a in m and b in m:
            r.update(debut=m[a].debut.isoformat(), fin=m[b].fin.isoformat(), joint=joint, source="المقرر الوزاري",
                     prefixe="ابتداء من" if typ == "p" else "")
    elif typ == "j":
        d1, d2 = date_journee(v, _y1(libelle))
        r.update(debut=d1.isoformat(), fin=d2.isoformat(), source="يوم عالمي أو وطني")
    elif typ == "mois":
        mois, _, note = v.partition(":")
        mo = int(mois)
        y = _annee_de(mo, _y1(libelle))
        r.update(periode=f"خلال شهر {tx.MOIS_AR[mo - 1]} {y}" + (f" ({note})" if note else ""),
                 source="يوم عالمي أو وطني")
    elif typ == "t":
        r["periode"] = v
    return r


def defaut(conn: sqlite3.Connection) -> dict:
    """المقترح الافتراضي للسنة الجارية، بتواريخ المقرر والأيام العالمية والوطنية."""
    a = _annee(conn)
    m = _stations_m(a["libelle"])
    sections = {}
    for k, _, _ in SECTIONS:
        lignes = []
        for station, ops, ref in DEFAUT[k]:
            lignes.append({"station": station, "operations": ops, **_resoudre(ref, a["libelle"], m)})
        sections[k] = lignes
    # الأنشطة المرتبطة بمشروع المؤسسة: عمليات المشروع المسجل إن وُجدت
    ops = _operations_projet(conn)
    if ops:
        sections[_P] = ops
    return {"sections": sections, "validation": "", "personnalise": False}


def _operations_projet(conn) -> list[dict]:
    try:
        from idara.services import projet_etab as pe
        p = pe.projet_actif(conn)
        if p is None:
            return []
        res = []
        for o in pe.operations(conn, p["id"]):
            l = {"station": o["axe"] or "إرساء وتنفيذ مشروع المؤسسة", "operations": o["intitule"], "debut": "",
                 "fin": "", "periode": "", "joint": False, "prefixe": "", "source": "مشروع المؤسسة"}
            if o["date_debut"]:
                l.update(debut=o["date_debut"], fin=o["date_fin"] or o["date_debut"])
            else:
                l["periode"] = SELON_PROJET
            res.append(l)
        return res
    except sqlite3.Error:
        return []


def _cle(conn) -> str:
    return f"programme_annuel_{_annee(conn)['libelle'].replace('/', '-')}"


def programme(conn: sqlite3.Connection) -> dict:
    """برنامج السنة الجارية: ما عدّله المستعمل، وإلا المقترح الافتراضي."""
    d = fiches.lire(conn, _cle(conn))
    if not d:
        return defaut(conn)
    base = defaut(conn)
    for k, _, _ in SECTIONS:
        d.setdefault("sections", {}).setdefault(k, base["sections"][k])
    d.setdefault("validation", "")
    d["personnalise"] = True
    return d


def _sauver(conn, d: dict) -> None:
    fiches.ecrire(conn, _cle(conn), {"sections": d["sections"], "validation": d.get("validation", "")})


def _verifier_date(v: str, lib: str) -> str:
    v = (v or "").strip()
    if not v:
        return ""
    try:
        return date.fromisoformat(v).isoformat()
    except ValueError:
        raise ErreurProgramme(f"{lib} غير صحيح.") from None


def enregistrer_ligne(conn: sqlite3.Connection, section: str, station: str, operations: str, debut: str = "",
                      fin: str = "", periode: str = "", index: int | None = None, position: int | None = None) -> int:
    """يضيف سطراً (index=None) أو يعدّله. التاريخان اختياريان؛ «فترة الإنجاز» نص حر بديل (مثل: طيلة السنة).
    يرجع رقم السطر."""
    if section not in TITRES or section == CONGES[0]:
        raise ErreurProgramme("محور غير معروف (لائحة العطل تُولَّد من المقرر الوزاري).")
    station = " ".join((station or "").split())
    operations = "\n".join(" ".join(l.split()) for l in (operations or "").splitlines() if l.strip())
    if not station or not operations:
        raise ErreurProgramme("المحطة والعمليات إجباريتان.")
    debut, fin = _verifier_date(debut, "تاريخ البداية"), _verifier_date(fin, "تاريخ النهاية")
    if fin and not debut:
        debut, fin = fin, ""
    if debut and fin and fin < debut:
        raise ErreurProgramme("تاريخ النهاية قبل تاريخ البداية.")
    d = programme(conn)
    lignes = d["sections"][section]
    ligne = {"station": station, "operations": operations, "debut": debut, "fin": fin or debut,
             "periode": " ".join((periode or "").split()) if not debut else "", "joint": False, "prefixe": "",
             "source": "تعديل المؤسسة"}
    if index is None:
        if position is None or not 0 <= position <= len(lignes):
            # بعد آخر سطر من المحطة نفسها إن وُجدت، وإلا في الآخر
            pos = max((i for i, l in enumerate(lignes) if l["station"] == station), default=len(lignes) - 1) + 1
        else:
            pos = position
        lignes.insert(pos, ligne)
        index = pos
    else:
        if not 0 <= index < len(lignes):
            raise ErreurProgramme("السطر غير موجود.")
        ancien = lignes[index]
        if (ancien.get("debut"), ancien.get("fin")) == (debut, fin or debut) and not periode:
            ligne.update(joint=ancien.get("joint", False), prefixe=ancien.get("prefixe", ""))
        lignes[index] = ligne
    _sauver(conn, d)
    return index


def supprimer_ligne(conn: sqlite3.Connection, section: str, index: int) -> None:
    d = programme(conn)
    lignes = d["sections"].get(section, [])
    if not 0 <= index < len(lignes):
        raise ErreurProgramme("السطر غير موجود.")
    del lignes[index]
    _sauver(conn, d)


def deplacer_ligne(conn: sqlite3.Connection, section: str, index: int, sens: int) -> int:
    d = programme(conn)
    lignes = d["sections"][section]
    j = index + sens
    if not (0 <= index < len(lignes) and 0 <= j < len(lignes)):
        return index
    lignes[index], lignes[j] = lignes[j], lignes[index]
    _sauver(conn, d)
    return j


def definir_validation(conn: sqlite3.Connection, le: str) -> None:
    """تاريخ مصادقة مجلس التدبير على البرنامج (فارغ: يُكتب باليد)."""
    d = programme(conn)
    d["validation"] = _verifier_date(le, "تاريخ المصادقة")
    _sauver(conn, d)


def reinitialiser(conn: sqlite3.Connection, section: str | None = None) -> None:
    """يعيد المقترح الافتراضي لمحور واحد أو للبرنامج كله."""
    if section is None:
        fiches.supprimer(conn, _cle(conn))
        return
    d = programme(conn)
    d["sections"][section] = defaut(conn)["sections"][section]
    _sauver(conn, d)


# ---------- العرض ----------

def _jour(d: date) -> str:
    return f"{tx.JOURS_AR[d.weekday()]} {d.day:02d} {tx.MOIS_AR[d.month - 1]} {d.year}"


def periode(l: dict) -> str:
    """فترة الإنجاز كما تُطبع."""
    if not l.get("debut"):
        return l.get("periode", "")
    d1, d2 = date.fromisoformat(l["debut"]), date.fromisoformat(l.get("fin") or l["debut"])
    pre = (l.get("prefixe") + " ") if l.get("prefixe") else ""
    if d1 == d2:
        return pre + _jour(d1)
    if l.get("joint"):
        return f"{_jour(d1)} و{_jour(d2)}"
    if (d1.month, d1.year) == (d2.month, d2.year):
        if (d2 - d1).days == 1:
            return f"{d1.day:02d} و{d2.day:02d} {tx.MOIS_AR[d1.month - 1]} {d1.year}"
        return f"من {d1.day:02d} إلى {d2.day:02d} {tx.MOIS_AR[d1.month - 1]} {d1.year}"
    return f"من {tx.date_chiffres(d1)} إلى {tx.date_chiffres(d2)}"


def alerte(conn_or_libelle, l: dict) -> str:
    """ينبه إلى اليوم العالمي أو الوطني الذي يصادف عطلة أو يوم أحد."""
    if not l.get("debut") or l.get("source") == "المقرر الوزاري":
        return ""
    libelle = conn_or_libelle if isinstance(conn_or_libelle, str) else _annee(conn_or_libelle)["libelle"]
    d = date.fromisoformat(l["debut"])
    for v in _vacances(libelle):
        if v.debut <= d <= v.fin:
            return f"يصادف {v.titre}: يُنجز في آخر يوم دراسي قبلها أو أول يوم بعدها."
    if d.weekday() == 6:
        return "يصادف يوم أحد: يُنجز في اليوم الدراسي الموالي أو السابق."
    return ""


def conges(conn: sqlite3.Connection) -> list[dict]:
    """لائحة العطل المدرسية من المقرر الوزاري: العطلة، تواريخها، عدد الأيام."""
    a = _annee(conn)
    res = []
    for s in _vacances(a["libelle"]):
        n = (s.fin - s.debut).days + 1
        if s.debut == s.fin:
            dates = _jour(s.debut)
        else:
            dates = f"من {_jour(s.debut)}\nإلى {_jour(s.fin)}"
        nb = f"{n:02d}"
        if s.precision == "hijri":
            dates += "\n(تقريبي: حسب ثبوت رؤية الهلال)"
            if "عيد الفطر" in s.titre:
                nb = "3 أو 4"
        res.append({"titre": s.titre.split(" (")[0], "dates": dates, "jours": nb})
    return res


def resume(conn: sqlite3.Connection) -> dict:
    """أعداد الأسطر والتواريخ المحددة والفارغة في كل محور (للصفحة)."""
    d = programme(conn)
    res = {}
    for k, _, _ in SECTIONS:
        l = d["sections"][k]
        res[k] = {"lignes": len(l), "datees": sum(1 for x in l if x.get("debut") or x.get("periode"))}
    return res


# ---------- الوثيقة ----------

def _rgb(h: str) -> tuple[int, int, int]:
    return int(h[:2], 16), int(h[2:4], 16), int(h[4:], 16)


def _clair(h: str, k: float) -> str:
    """لون أفتح (k من 0 إلى 1 نحو الأبيض)."""
    r, g, b = _rgb(h)
    return "".join(f"{int(c + (255 - c) * k):02X}" for c in (r, g, b))


def _run(p, texte, gras=False, taille=11, couleur: str | None = None):
    from docx.shared import RGBColor
    from idara.services.docs_association import _rtl_run
    r = p.add_run(texte)
    _rtl_run(r, gras, taille)
    if couleur:
        r.font.color.rgb = RGBColor(*_rgb(couleur))
    return r


def _cel(c, texte, gras=False, taille=10.5, couleur=None, fond=None, centre=True, lignes_sep=False):
    from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt
    from idara.services.docs_association import _bidi, _ombre
    for p in list(c.paragraphs):
        p._element.getparent().remove(p._element)
    morceaux = (texte or "").split("\n") if lignes_sep else [(texte or "")]
    for k, t in enumerate(morceaux):
        p = c.add_paragraph()
        _bidi(p)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER if centre else WD_ALIGN_PARAGRAPH.RIGHT
        p.paragraph_format.space_after = Pt(1)
        p.paragraph_format.space_before = Pt(1)
        _run(p, ("• " + t) if lignes_sep and len(morceaux) > 1 else t, gras, taille, couleur)
    c.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    if fond:
        _ombre(c, fond)


def _bordures(t, couleur: str, sz=6) -> None:
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    tblpr = t._tbl.tblPr
    b = OxmlElement("w:tblBorders")
    for cote in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement(f"w:{cote}")
        e.set(qn("w:val"), "single")
        e.set(qn("w:sz"), str(sz))
        e.set(qn("w:color"), couleur)
        b.append(e)
    tblpr.append(b)


def _table(d, n, m, largeurs, couleur="BFBFBF"):
    from idara.services.docs_association import tableau
    t = tableau(d, n, m, bordures=False, largeurs=largeurs)
    _bordures(t, couleur)
    return t


def _entete_repete(row) -> None:
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    trpr = row._tr.get_or_add_trPr()
    e = OxmlElement("w:tblHeader")
    e.set(qn("w:val"), "true")
    trpr.append(e)


def _bandeau(d, numero: int | None, titre: str, couleur: str) -> None:
    """شريط المحور: رقم في دائرة ذهبية وعنوان أبيض على لون المحور."""
    from docx.shared import Pt
    t = _table(d, 1, 2, [1.3, 16.7], couleur)
    _cel(t.cell(0, 0), f"{numero}" if numero else "", True, 15, "1B2A4A", "F2D27A")
    _cel(t.cell(0, 1), titre, True, 14, "FFFFFF", couleur, centre=False)
    for c in t.rows[0].cells:
        c.paragraphs[0].paragraph_format.space_before = Pt(3)
        c.paragraphs[0].paragraph_format.space_after = Pt(3)
    _espace(d, 3)


def _espace(d, pts: float) -> None:
    """فاصل صغير بين الجداول (فقرة بخط صغير جداً)."""
    from docx.shared import Pt
    from idara.services.docs_association import para
    p = para(d, " ", apres=0)
    p.runs[0].font.size = Pt(pts)
    p.paragraph_format.line_spacing = Pt(pts)


def _pied(d, texte: str) -> None:
    """تذييل: اسم الوثيقة ورقم الصفحة."""
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from idara.services.docs_association import _bidi
    p = d.sections[0].footer.paragraphs[0]
    _bidi(p)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _run(p, texte, False, 9, "7A6A3A")
    r = _run(p, "", True, 9, "7A6A3A")
    for typ, txt in (("begin", None), (None, " PAGE "), ("end", None)):
        if typ:
            e = OxmlElement("w:fldChar")
            e.set(qn("w:fldCharType"), typ)
        else:
            e = OxmlElement("w:instrText")
            e.set(qn("xml:space"), "preserve")
            e.text = txt
        r._r.append(e)


def generer(conn: sqlite3.Connection, dossier) -> Path:
    """وثيقة برنامج العمل السنوي على قالب ملون: رأس رسمي، شريط عنوان ليلي ذهبي، محور لكل لون، ولائحة العطل،
    والمصادقة وتوقيعات أعضاء مجلس التدبير."""
    from docx.enum.section import WD_SECTION
    from docx.shared import Cm, Pt
    from idara.services import conseils_etab as ce
    from idara.services import etablissement as etab_srv
    from idara.services.docs_association import _nouveau, para
    _ = WD_SECTION
    a = _annee(conn)
    e = etab_srv.lire_etablissement(conn)
    if e is None or not e.nom_ar:
        raise ErreurProgramme("أكمل إعداد المؤسسة أولاً.")
    prog = programme(conn)
    d = _nouveau()
    s = d.sections[0]
    s.left_margin = s.right_margin = Cm(1.5)
    s.top_margin, s.bottom_margin = Cm(1.2), Cm(1.4)

    # الرأس الرسمي: الوزارة يميناً، الشعار في الوسط، السنة الدراسية يساراً
    t = _table(d, 1, 3, [6.0, 6.6, 5.4], "FFFFFF")
    _cel(t.cell(0, 0), "\n".join(x for x in ("المملكة المغربية", "وزارة التربية الوطنية والتعليم الأولي والرياضة",
                                             f"الأكاديمية الجهوية للتربية والتكوين {e.academie_ar or ''}".strip(),
                                             f"المديرية الإقليمية {e.direction_ar or ''}".strip(), e.nom_ar) if x),
         True, 10, "1B2A4A")
    c = t.cell(0, 1)
    logo = None
    if e.logo_path and dossier is not None and (dossier.racine / e.logo_path).exists():
        logo = dossier.racine / e.logo_path
    mini = Path(__file__).resolve().parent.parent / "resources" / "ministere.png"
    img = logo or (mini if mini.exists() else None)
    if img is not None:
        c.paragraphs[0].alignment = 1
        c.paragraphs[0].add_run().add_picture(str(img), width=Cm(6.2 if logo is None else 4.5))
    _cel(t.cell(0, 2), f"السنة الدراسية\n{a['libelle']}" + (f"\nرمز المؤسسة: {e.code_etab}" if e.code_etab else ""),
         True, 11, "1B2A4A")
    para(d, apres=4)

    # شريط العنوان
    t = _table(d, 1, 1, [18.0], "C9A227")
    c = t.cell(0, 0)
    _cel(c, "برنامج العمل السنوي", True, 24, "F2D27A", "1B2A4A")
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from idara.services.docs_association import _bidi
    p = c.add_paragraph()
    _bidi(p)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _run(p, f"برسم السنة الدراسية {a['libelle']}", True, 14, "FFFFFF")
    mq = cal.mouqarrar(a["libelle"])
    if mq:
        p = c.add_paragraph()
        _bidi(p)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _run(p, f"وفق مقرر تنظيم السنة الدراسية رقم {mq['mouqarrar']['numero']} بتاريخ "
                f"{tx.date_ar(mq['mouqarrar']['date'])}", False, 10.5, "F2D27A")
        if mq["mouqarrar"].get("shiaar"):
            p = c.add_paragraph()
            _bidi(p)
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            _run(p, f"«{mq['mouqarrar']['shiaar']}»", True, 11, "FFFFFF")
    for p in c.paragraphs:
        p.paragraph_format.space_after = Pt(2)
    para(d, apres=6)

    # المحاور
    for n, (k, titre, coul) in enumerate(SECTIONS, start=1):
        lignes = prog["sections"].get(k, [])
        if not lignes:
            continue
        _bandeau(d, n, titre, coul)
        t = _table(d, 1 + len(lignes), 3, [4.0, 9.5, 4.5], _clair(coul, 0.45))
        ent = ("المحطة", "العمليات والأنشطة المبرمجة", "فترة الإنجاز") if k != _E else \
            ("المحطات التربوية", "العمليات", "فترة الإنجاز")
        for j, h in enumerate(ent):
            _cel(t.cell(0, j), h, True, 11, coul, _clair(coul, 0.82))
        _entete_repete(t.rows[0])
        debut_groupe = 1
        for i, l in enumerate(lignes, start=1):
            fond = "FFFFFF" if i % 2 else _clair(coul, 0.95)
            per = periode(l)
            al = alerte(a["libelle"], l)
            _cel(t.cell(i, 1), l["operations"], False, 10.5, "222222", fond, centre=False,
                 lignes_sep="\n" in l["operations"])
            _cel(t.cell(i, 2), per + (f"\n{al}" if al else ""), True, 10, coul if per else None, fond,
                 lignes_sep=bool(al))
            if al:
                r = t.cell(i, 2).paragraphs[-1].runs[-1]
                r.font.size = Pt(8)
                r.bold = False
            # فترة إنجاز نصية مشتركة (مثل «حسب الجدولة الزمنية...»): دمج الأسطر المتتالية
            if not l.get("debut") and l.get("periode") and i > 1 and not lignes[i - 2].get("debut") \
                    and lignes[i - 2].get("periode") == l["periode"]:
                haut = t.cell(i - 1, 2)
                m_ = haut.merge(t.cell(i, 2))
                _cel(m_, l["periode"], True, 10, coul, "FFFFFF")
            # المحطة: دمج الأسطر المتتالية للمحطة نفسها
            fin_groupe = i == len(lignes) or lignes[i]["station"] != l["station"]
            if fin_groupe:
                c = t.cell(debut_groupe, 0)
                if i > debut_groupe:
                    c = c.merge(t.cell(i, 0))
                _cel(c, l["station"], True, 11, coul, _clair(coul, 0.9))
                debut_groupe = i + 1
        _espace(d, 10)

    # لائحة العطل
    cg = conges(conn)
    k, titre, coul = CONGES
    _bandeau(d, len(SECTIONS) + 1, titre, coul)
    if cg:
        t = _table(d, 1 + len(cg), 4, [1.2, 6.0, 8.3, 2.5], _clair(coul, 0.45))
        for j, h in enumerate(("ر.ت", "العطل المدرسية", "تواريخها", "عدد الأيام")):
            _cel(t.cell(0, j), h, True, 11, coul, _clair(coul, 0.82))
        _entete_repete(t.rows[0])
        for i, v in enumerate(cg, start=1):
            fond = "FFFFFF" if i % 2 else _clair(coul, 0.95)
            _cel(t.cell(i, 0), f"{i:02d}", True, 10.5, coul, fond)
            _cel(t.cell(i, 1), v["titre"], True, 10.5, "222222", fond)
            _cel(t.cell(i, 2), v["dates"], False, 10, "222222", fond, lignes_sep=False)
            _cel(t.cell(i, 3), v["jours"], True, 10.5, coul, fond)
    else:
        para(d, "لم يُرفق بالبرنامج بعد مقرر تنظيم هذه السنة الدراسية: تُضاف العطل عند صدوره.", taille=11)
    _espace(d, 10)

    # المصادقة والتوقيعات
    v = prog.get("validation")
    para(d, "صادق أعضاء مجلس تدبير المؤسسة على برنامج العمل السنوي بعد الاطلاع عليه بتاريخ: "
            + (tx.date_chiffres(v) if v else "......../......../............"), gras=True, taille=12, apres=4)
    try:
        membres = ce.membres_actifs(conn, "gestion")
    except sqlite3.Error:
        membres = []
    ppr = {}
    for r in conn.execute("SELECT id, ppr FROM personnel"):
        ppr[r["id"]] = r["ppr"] or ""
    n = max(len(membres), 8)
    t = _table(d, 1 + n, 5, [1.2, 6.0, 3.2, 4.4, 3.2], "8C8C8C")
    for j, h in enumerate(("ر.ت", "الاسم والنسب", "رقم التأجير", "بصفته", "التوقيع")):
        _cel(t.cell(0, j), h, True, 11, "1B2A4A", "F2E6C4")
    for i in range(1, n + 1):
        mbr = membres[i - 1] if i <= len(membres) else None
        vals = (f"{i:02d}", mbr["nom"] if mbr else "", ppr.get(mbr["personnel_id"], "") if mbr else "",
                mbr["qualite"] if mbr else "", "")
        for j, x in enumerate(vals):
            _cel(t.cell(i, j), x, j == 0, 10.5)
        t.rows[i].height = Cm(0.9)
    para(d, apres=6)
    para(d, f"حرر ب{e.ville_redaction_ar or ''} في: {tx.date_chiffres(date.today())}".replace("ب في", "في"),
         taille=11, apres=2)
    para(d, "خاتم وتوقيع رئيس مجلس تدبير المؤسسة (المدير):", gras=True, taille=12, apres=40)
    _pied(d, f"برنامج العمل السنوي {a['libelle']} · {e.nom_ar} · صفحة ")

    rep = dossier.archives / a["libelle"].replace("/", "-") / "برنامج العمل السنوي"
    rep.mkdir(parents=True, exist_ok=True)
    chemin = rep / f"{datetime.now():%Y%m%d_%H%M%S}_برنامج_العمل_السنوي.docx"
    d.save(chemin)
    return chemin


# ---------- للسبورة المرجعية ----------

def lignes_sabboura(conn: sqlite3.Connection) -> list[list[str]]:
    """المحطات المؤرخة فقط (المحور، المحطة والعملية، فترة الإنجاز)، مرتبة حسب التاريخ: لوحة تُعلَّق في المكتب."""
    prog = programme(conn)
    res = []
    for k, titre, _ in SECTIONS:
        for l in prog["sections"].get(k, []):
            if not l.get("debut"):
                continue
            op = l["operations"].split("\n")[0]
            res.append((l["debut"], [titre, f"{l['station']}: {op}" if l["station"] not in op else op, periode(l)]))
    res.sort(key=lambda x: x[0])
    return [x for _, x in res]
