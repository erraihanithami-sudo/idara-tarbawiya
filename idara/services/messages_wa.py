"""رسائل واتساب جاهزة لأولياء الأمور (اقتراح مستلهم من مقارنة 2026-11-13، وافق عليه المدير).

البرنامج يهيئ نص الرسالة ورابط «wa.me» فقط؛ الرسالة تُفتح في واتساب (التطبيق أو المتصفح) ولا تُرسل إلا حين
يضغط المدير «إرسال» بنفسه. لا شيء يُرسل من البرنامج، والبرنامج يبقى يعمل دون إنترنت.
"""

from __future__ import annotations

import re
from urllib.parse import quote

MODELES = {
    "absence": ("إخبار بالغياب",
                "السلام عليكم. نخبركم أن {enfant} {nom_eleve} ({classe}) {verbe_absent} عن الدراسة يوم {date}. "
                "المرجو الاتصال بإدارة {etablissement} لتبرير الغياب. وشكراً."),
    "convocation": ("استدعاء",
                    "السلام عليكم. يتشرف مدير {etablissement} بدعوتكم للحضور إلى المؤسسة يوم {date} على الساعة "
                    "{heure}، في شأن يهم {enfant} {nom_eleve} ({classe}). وشكراً."),
    "rappel": ("تذكير بموعد",
               "السلام عليكم. نذكركم بالموعد المحدد بإدارة {etablissement} يوم {date} على الساعة {heure} "
               "بخصوص {enfant} {nom_eleve}. وشكراً."),
    "document": ("وثيقة جاهزة",
                 "السلام عليكم. الوثيقة التي طلبتموها بخصوص {enfant} {nom_eleve} جاهزة، ويمكنكم تسلمها من إدارة "
                 "{etablissement} خلال أوقات العمل. وشكراً."),
    "felicitation": ("تهنئة",
                     "السلام عليكم. يسر إدارة {etablissement} أن تهنئكم على النتائج المشرفة التي {verbe_obtenu} "
                     "{enfant} {nom_eleve} ({classe}). مع متمنياتنا بمزيد من التوفيق."),
}


class ErreurMessage(ValueError):
    """رسالة موجهة للمدير بالعربية."""


def numero_international(tel: str) -> str:
    """0612345678 ← 212612345678 (الصيغة التي يطلبها واتساب). يقبل +212 و00212."""
    c = re.sub(r"\D", "", tel or "")
    if c.startswith("00"):
        c = c[2:]
    if c.startswith("212") and len(c) == 12:
        return c
    if len(c) == 10 and c[0] == "0":
        return "212" + c[1:]
    if len(c) == 9 and c[0] in "5678":
        return "212" + c
    raise ErreurMessage("رقم هاتف الولي غير صالح لواتساب (المنتظر: 10 أرقام تبدأ بـ 06 أو 07).")


def texte(cle: str, nom_eleve: str, sexe: str = "M", classe: str = "", etablissement: str = "",
          date: str = "", heure: str = "") -> str:
    if cle not in MODELES:
        raise ErreurMessage("نوع رسالة غير معروف.")
    f = sexe == "F"
    t = MODELES[cle][1].format(
        nom_eleve=nom_eleve, classe=classe or "", etablissement=etablissement or "المؤسسة", date=date or "",
        heure=heure or "", enfant="ابنتكم" if f else "ابنكم",
        verbe_absent="تغيبت" if f else "تغيب", verbe_obtenu="حصلت عليها" if f else "حصل عليها")
    t = t.replace(" ()", "").replace("يوم  ", "").replace(" على الساعة ،", "،").replace(" على الساعة  ", " ")
    return " ".join(t.split())


def lien(tel: str, message: str) -> str:
    if not (message or "").strip():
        raise ErreurMessage("نص الرسالة فارغ.")
    return f"https://wa.me/{numero_international(tel)}?text={quote(message.strip())}"
