"""الإعلانات المزخرفة (طلب المدير 2026-11-15): عشرة قوالب زخرفية، مناسبات جاهزة، A4 أو A3.

الهندسة هنا دون Qt (كما في idara/marque.py): كل قالب يُنتج قائمة أشكال بسيطة (مضلعات، خطوط، دوائر، مستطيلات)
وقائمة نصوص بمواضعها، على ورقة 210×297 مم. A3 هو نفس الرسم مكبَّراً (النسبة واحدة).
الواجهة ترسمها بـ QPainter (idara/ui/affiche_qt.py)؛ و`en_svg` يكتبها SVG للمعاينة والاختبار.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from html import escape

L, H = 210.0, 297.0          # ورقة A4 بالمليمتر
FORMATS = {"A4": (210.0, 297.0), "A3": (297.0, 420.0)}


class ErreurAffiche(ValueError):
    """رسالة موجهة للمدير بالعربية."""


# ====================== المناسبات ======================

@dataclass(frozen=True)
class Occasion:
    cle: str
    libelle: str
    surtitre: str
    titre: str
    texte: str


OCCASIONS: dict[str, Occasion] = {o.cle: o for o in (
    Occasion("rentree", "الدخول المدرسي", "إعلان", "الدخول المدرسي",
             "تنهي إدارة المؤسسة إلى علم أمهات وآباء وأولياء أمور التلميذات والتلاميذ أن الدراسة ستنطلق في "
             "التاريخ المبين أسفله. المرجو الحرص على حضور الجميع في الموعد."),
    Occasion("activite", "نشاط أو حفل", "دعوة", "حفل مدرسي",
             "يسعد أسرة المؤسسة دعوتكم لحضور هذا النشاط التربوي الذي يحييه تلميذاتنا وتلاميذنا. حضوركم دعم وتشجيع لهم."),
    Occasion("examen", "امتحان أو فروض", "إعلان", "الامتحان الموحد",
             "ليكن في علم التلميذات والتلاميذ وأولياء أمورهم أن الامتحان سيجرى وفق البرمجة المبينة أسفله. "
             "المرجو الحضور قبل الموعد بنصف ساعة مع إحضار الأدوات اللازمة."),
    Occasion("reunion", "اجتماع أولياء الأمور", "دعوة", "لقاء تواصلي مع الأسر",
             "تدعو إدارة المؤسسة أمهات وآباء وأولياء أمور التلميذات والتلاميذ لحضور لقاء تواصلي حول تتبع "
             "تمدرس أبنائهم ونتائجهم."),
    Occasion("vacances", "عطلة مدرسية", "إعلان", "عطلة مدرسية",
             "تنهي إدارة المؤسسة إلى علم الجميع أن الدراسة ستتوقف خلال العطلة المبينة أسفله، وستستأنف مباشرة بعدها."),
    Occasion("concours", "مسابقة أو تتويج", "إعلان", "مسابقة ثقافية",
             "تنظم المؤسسة مسابقة مفتوحة في وجه تلميذاتها وتلاميذها. باب المشاركة مفتوح لدى الأستاذات والأساتذة."),
    Occasion("campagne", "حملة تحسيسية", "نداء", "حملة تحسيسية",
             "تنظم المؤسسة بتعاون مع شركائها حملة تحسيسية لفائدة التلميذات والتلاميذ. مشاركة الجميع تُنجح الحملة."),
    Occasion("portes", "أبواب مفتوحة", "دعوة", "أبواب مفتوحة",
             "تفتح المؤسسة أبوابها لاستقبال الأسر والاطلاع على أعمال التلميذات والتلاميذ ولقاء أطرها التربوية."),
    Occasion("sortie", "رحلة أو خرجة", "إعلان", "رحلة مدرسية",
             "تنظم المؤسسة رحلة تربوية لفائدة تلميذاتها وتلاميذها. المرجو من الراغبين في المشاركة تسليم "
             "ترخيص ولي الأمر إلى الإدارة."),
    Occasion("libre", "إعلان عام", "إعلان", "إعلان", ""),
)}


@dataclass
class Contenu:
    """ما يكتبه المدير. الحقل الفارغ لا يُرسم (لا نقط مكان المعطيات الناقصة)."""
    titre: str = ""
    texte: str = ""
    surtitre: str = "إعلان"
    date: str = ""           # نص جاهز للعرض («السبت 14 نونبر 2026»)
    heure: str = ""
    lieu: str = ""
    public: str = ""
    note: str = ""
    etablissement: str = ""
    direction: str = ""
    signature: str = "الإدارة"

    def infos(self) -> list[tuple[str, str]]:
        return [(lib, v.strip()) for lib, v in (("التاريخ", self.date), ("الساعة", self.heure),
                                                ("المكان", self.lieu), ("الفئة المعنية", self.public)) if v.strip()]


# ====================== الرسم ======================

@dataclass
class Texte:
    boite: tuple[float, float, float, float]    # x, y, عرض، ارتفاع (مم)
    texte: str
    taille: float                               # أقصى حجم بالنقطة على A4؛ يُصغَّر حتى يدخل الصندوق
    couleur: str
    gras: bool = False
    titre: bool = False                         # خط العناوين
    aligne: str = "centre"                      # centre | droite


@dataclass
class Dessin:
    formes: list[dict] = field(default_factory=list)
    textes: list[Texte] = field(default_factory=list)

    def poly(self, pts, f=None, s=None, e=0.4, o=1.0):
        self.formes.append({"t": "poly", "p": [(round(x, 2), round(y, 2)) for x, y in pts], "f": f, "s": s, "e": e,
                            "o": o})

    def ligne(self, pts, s, e=0.4, o=1.0):
        self.formes.append({"t": "ligne", "p": [(round(x, 2), round(y, 2)) for x, y in pts], "f": None, "s": s,
                            "e": e, "o": o})

    def cercle(self, cx, cy, r, f=None, s=None, e=0.4, o=1.0):
        self.formes.append({"t": "cercle", "c": (round(cx, 2), round(cy, 2)), "r": round(r, 2), "f": f, "s": s,
                            "e": e, "o": o})

    def rect(self, x, y, w, h, f=None, s=None, e=0.4, o=1.0, r=0.0):
        self.formes.append({"t": "rect", "b": (round(x, 2), round(y, 2), round(w, 2), round(h, 2)), "r": r, "f": f,
                            "s": s, "e": e, "o": o})


def grad(x1, y1, x2, y2, c1, c2):
    return ("grad", (x1, y1, x2, y2), c1, c2)


def _etoile(cx, cy, R, r=None, n=8, rot=0.0):
    r = R * 0.765 if r is None else r     # 0.765: نجمة المربعين المتراكبين (الخاتم)
    return [(cx + (R if k % 2 == 0 else r) * math.cos(rot + k * math.pi / n),
             cy + (R if k % 2 == 0 else r) * math.sin(rot + k * math.pi / n)) for k in range(2 * n)]


def _arc(cx, cy, r, a0, a1, n=40):
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * k / n)),
             cy + r * math.sin(math.radians(a0 + (a1 - a0) * k / n))) for k in range(n + 1)]


def _arche(x0, x1, y_haut, y_bas, depasse=0.08):
    """قوس حدوة مغربي بين x0 و x1: قمته عند y_haut وقاعدته y_bas."""
    demi = (x1 - x0) / 2
    cx = (x0 + x1) / 2
    r = demi * (1 + depasse)
    cy = y_haut + r
    a = math.degrees(math.acos(demi / r))            # زاوية نقطة التقاء القوس بالعمود
    return [(x1, y_bas)] + _arc(cx, cy, r, a, -180 - a) + [(x0, y_bas)]


def _losange(cx, cy, a, b):
    return [(cx, cy - b), (cx + a, cy), (cx, cy + b), (cx - a, cy)]


def _vague(y, amp, periode, phase, bas, n=80):
    pts = [(L * k / n, y + amp * math.sin(2 * math.pi * (L * k / n) / periode + phase)) for k in range(n + 1)]
    return pts + [(L, bas), (0, bas)]


def _frise_etoiles(d: Dessin, y, x0, x1, R, couleur, contour=None, pas=None, e=0.35):
    pas = pas or R * 2.6
    n = max(1, int((x1 - x0) // pas))
    depart = (x0 + x1) / 2 - pas * (n - 1) / 2
    for k in range(n):
        cx = depart + k * pas
        d.poly(_etoile(cx, y, R, rot=math.pi / 8), f=couleur, s=contour, e=e)
        if k < n - 1 and couleur:
            d.poly(_losange(cx + pas / 2, y, R * 0.28, R * 0.28), f=couleur)


def _coins(d: Dessin, m, taille, couleur, e=0.6):
    """زاوية هندسية في الأركان الأربعة: خطان متعامدان وخاتم صغير."""
    for sx, sy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
        x = m if sx > 0 else L - m
        y = m if sy > 0 else H - m
        d.ligne([(x + sx * taille, y), (x, y), (x, y + sy * taille)], couleur, e)
        d.ligne([(x + sx * taille, y + sy * 2.2), (x + sx * 2.2, y + sy * 2.2), (x + sx * 2.2, y + sy * taille)],
                couleur, e * 0.5)
        d.poly(_etoile(x + sx * 6.5, y + sy * 6.5, 2.4, rot=math.pi / 8), f=couleur)


# ---------- القوالب ----------

@dataclass(frozen=True)
class Theme:
    cle: str
    nom: str
    description: str
    encre: str          # لون النص
    titre: str          # لون العنوان
    accent: str         # لون الشارات والفواصل
    doux: str           # لون خلفية الشارات
    sur_accent: str     # لون النص فوق الشارات
    zone: tuple[float, float, float, float]   # منطقة المحتوى: x0, y0, x1, y1
    encre_entete: str = ""                    # لون ترويسة المؤسسة إن اختلف (فوق شريط ملوّن)
    economique: bool = False                  # قليل الحبر


def _t_zellige(d: Dessin):
    bleu, or_ = "#2E3192", "#B8892B"
    d.rect(0, 0, L, H, f="#FBF7EC")
    for y in (12, H - 40):
        d.rect(12, y, L - 24, 28, f=bleu)
        d.ligne([(12, y + 3), (L - 12, y + 3)], or_, 0.5)
        d.ligne([(12, y + 25), (L - 12, y + 25)], or_, 0.5)
        _frise_etoiles(d, y + 14, 18, L - 18, 6.2, None, contour=or_, pas=17.2, e=0.55)
        _frise_etoiles(d, y + 14, 18, L - 18, 2.6, or_, pas=17.2)
    d.rect(8, 8, L - 16, H - 16, s=bleu, e=1.6)
    d.rect(10.4, 10.4, L - 20.8, H - 20.8, s=or_, e=0.45)
    for x in (22, L - 22):
        d.ligne([(x, 46), (x, H - 46)], or_, 0.35)
        for k in range(9):
            d.poly(_losange(x, 58 + k * 22.6, 1.6, 2.6), f=bleu)


def _t_arche(d: Dessin):
    vert, or_, creme = "#0F5B4A", "#C39A3B", "#F7F4EA"
    d.rect(0, 0, L, H, f=creme)
    d.rect(0, 0, L, 122, f=grad(0, 0, 0, 122, "#0A4638", vert))
    for k, y in enumerate(range(10, 120, 14)):          # زليج خافت على الأخضر
        for x in range(8 + (7 if k % 2 else 0), int(L), 14):
            d.poly(_etoile(x, y, 3.4, rot=math.pi / 8), s="#FFFFFF", e=0.25, o=0.14)
    arche = _arche(36, L - 36, 18, 122)
    d.poly(arche, f=creme)
    d.ligne(arche, or_, 1.3)
    d.ligne(_arche(40, L - 40, 22.5, 122), or_, 0.4)
    d.rect(0, 122, L, 2.2, f=or_)
    d.rect(8, 8, L - 16, H - 16, s=vert, e=1.2)
    _frise_etoiles(d, H - 20, 30, L - 30, 3.4, vert, pas=12)
    d.ligne([(20, H - 27), (L - 20, H - 27)], or_, 0.5)
    d.ligne([(20, H - 13), (L - 20, H - 13)], or_, 0.5)


def _t_rihab(d: Dessin):
    bleu, jaune, nuit = "#3B3FB6", "#F2C14E", "#1B1B3A"
    d.rect(0, 0, L, H, f="#FFFFFF")
    d.poly([(L, 0), (L, 58), (L - 84, 0)], f=bleu)
    d.poly([(L, 0), (L, 36), (L - 52, 0)], f=nuit)
    d.poly([(L - 84, 0), (L - 94, 0), (L, 65), (L, 58)], f=jaune)
    d.poly([(0, H), (0, H - 62), (88, H)], f=bleu)
    d.poly([(0, H), (0, H - 38), (54, H)], f=nuit)
    d.poly([(88, H), (98, H), (0, H - 69), (0, H - 62)], f=jaune)
    for k in range(4):                                   # خواتم صغيرة على الزاويتين
        d.poly(_etoile(L - 9 - k * 9, 7 + k * 0.6, 3.0 - k * 0.45, rot=math.pi / 8), s="#FFFFFF", e=0.4, o=0.8)
        d.poly(_etoile(12 + k * 11, H - 8 - k * 1.8, 2.8 - k * 0.35, rot=math.pi / 8), s="#FFFFFF", e=0.4, o=0.8)
    d.rect(16, 34, 3, 46, f=jaune)
    d.rect(16, 34, 3, 18, f=bleu)


def _t_nuit(d: Dessin):
    or_, clair = "#D9B25F", "#F1DFA9"
    d.rect(0, 0, L, H, f=grad(0, 0, L, H, "#0E1230", "#23285F"))
    rnd = random.Random(11)
    for _ in range(70):                                  # نجوم خافتة
        x, y = rnd.uniform(14, L - 14), rnd.uniform(14, H - 14)
        d.poly(_etoile(x, y, rnd.uniform(0.5, 1.5), n=4, r=0.25), f=clair, o=rnd.uniform(0.15, 0.5))
    d.rect(9, 9, L - 18, H - 18, s=or_, e=1.1)
    d.rect(12.5, 12.5, L - 25, H - 25, s=or_, e=0.35)
    for sx, sy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):  # خاتم في كل ركن
        x = 12.5 if sx > 0 else L - 12.5
        y = 12.5 if sy > 0 else H - 12.5
        d.poly(_etoile(x, y, 9.5, rot=math.pi / 8), f="#141838", s=or_, e=0.7)
        d.poly(_etoile(x, y, 5.2, rot=math.pi / 8), s=or_, e=0.4)
        d.cercle(x, y, 1.3, f=or_)
    for y in (33, H - 33):
        d.ligne([(40, y), (L / 2 - 12, y)], or_, 0.45)
        d.ligne([(L / 2 + 12, y), (L - 40, y)], or_, 0.45)
        d.poly(_etoile(L / 2, y, 6.5, rot=math.pi / 8), s=or_, e=0.6)
        d.poly(_etoile(L / 2, y, 3, rot=math.pi / 8), f=or_)


def _t_terre(d: Dessin):
    terre, sable, sarcelle = "#B4532A", "#F6EBDD", "#1F6F6B"
    d.rect(0, 0, L, H, f=sable)
    for x in (0, L - 20):
        d.rect(x, 0, 20, H, f=terre)
        cx = x + 10
        for k in range(15):
            cy = 10 + k * 20
            d.poly(_losange(cx, cy, 7, 9), s=sable, e=0.6)
            d.poly(_losange(cx, cy, 3.2, 4.2), f=sable)
            d.cercle(cx, cy + 10, 1.1, f=sable)
    for x in (20, L - 21.2):
        d.rect(x, 0, 1.2, H, f=sarcelle)
    for k in range(9):                                   # أقواس صغيرة أعلى الصفحة وأسفلها
        cx = 32 + k * 18.25
        d.poly(_arc(cx, 10, 8, 0, 180) + [(cx - 8, 0), (cx + 8, 0)], f=terre)
        d.cercle(cx, 10, 2.2, f=sable)
        d.poly(_arc(cx, H - 10, 8, 180, 360) + [(cx + 8, H), (cx - 8, H)], f=terre)
        d.cercle(cx, H - 10, 2.2, f=sable)


def _t_chaouen(d: Dessin):
    d.rect(0, 0, L, H, f=grad(0, 0, 0, H, "#FFFFFF", "#E4F0FB"))
    hauts = [(_vague(46, 5, 120, 0.4, 0), "#BBD9F2"), (_vague(36, 6, 150, 1.6, 0), "#5E9FD6"),
             (_vague(24, 5, 110, 3.0, 0), "#1E4E8C")]
    for pts, c in hauts:
        d.poly(pts, f=c)
    for amp, per, ph, y, c in ((5, 120, 2.0, H - 40, "#BBD9F2"), (6, 150, 0.2, H - 30, "#5E9FD6"),
                               (5, 110, 4.0, H - 19, "#1E4E8C")):
        d.poly(_vague(y, amp, per, ph, H), f=c)
    for x, y, r in ((30, 13, 4.2), (L - 34, 11, 3.4), (L / 2 + 22, 9, 2.6)):
        d.poly(_etoile(x, y, r, rot=math.pi / 8), f="#F2A541")
    for x, y, r in ((36, H - 9, 3.2), (L - 40, H - 8, 4)):
        d.poly(_etoile(x, y, r, rot=math.pi / 8), f="#F2A541")


def _t_fete(d: Dessin):
    couleurs = ["#E4572E", "#F2A541", "#2E86AB", "#7B2D8E", "#3BB273"]
    d.rect(0, 0, L, H, f="#FFFDF8")
    rnd = random.Random(5)
    for zone in ((0, 62), (H - 50, H)):
        for _ in range(85):
            x, y = rnd.uniform(4, L - 4), rnd.uniform(*zone)
            bord = 1 - min(abs(y - zone[0]), abs(y - zone[1])) / 60
            c, t = rnd.choice(couleurs), rnd.uniform(1, 2.6)
            forme = rnd.randrange(3)
            if forme == 0:
                d.cercle(x, y, t * 0.8, f=c, o=0.55 + 0.4 * bord)
            elif forme == 1:
                a = rnd.uniform(0, math.pi)
                d.poly([(x + t * 1.6 * math.cos(a + k * math.pi / 2) * (1 if k % 2 == 0 else 0.35),
                         y + t * 1.6 * math.sin(a + k * math.pi / 2) * (1 if k % 2 == 0 else 0.35)) for k in range(4)],
                       f=c, o=0.55 + 0.4 * bord)
            else:
                d.poly(_etoile(x, y, t * 1.2, n=5, r=t * 0.5, rot=rnd.uniform(0, 3)), f=c, o=0.6 + 0.4 * bord)
    corde = [(L * k / 40, 16 + 15 * math.sin(math.pi * k / 40)) for k in range(41)]
    d.ligne(corde, "#6B5B4B", 0.5)
    for k in range(1, 40, 3):                            # رايات مثلثة على الحبل
        (xa, ya), (xb, yb) = corde[k], corde[k + 2]
        d.poly([(xa, ya), (xb, yb), ((xa + xb) / 2, (ya + yb) / 2 + 15)], f=couleurs[(k // 3) % 5])


def _t_rentree(d: Dessin):
    vert, bois, jaune = "#1F5D4C", "#8A5A2B", "#F5C518"
    d.rect(0, 0, L, H, f="#FFFBEF")
    for y in range(132, 262, 9):                         # سطور دفتر خافتة
        d.ligne([(14, y), (L - 14, y)], "#9CC3E6", 0.25, o=0.55)
    d.ligne([(L - 26, 126), (L - 26, 262)], "#E57373", 0.4, o=0.7)
    d.rect(0, 0, L, 14, f=jaune)
    d.rect(18, 22, L - 36, 92, f=bois, r=4)              # سبورة بإطار خشبي
    d.rect(22, 26, L - 44, 84, f=grad(0, 26, 0, 110, "#256B58", vert), r=2)
    d.rect(60, 112, 44, 3.2, f="#F4F1E8", r=1.2)         # طباشيرة وممسحة
    d.rect(112, 111.4, 24, 4.4, f="#5C6B73", r=1)
    crayons = ["#E4572E", "#F5C518", "#2E86AB", "#3BB273", "#7B2D8E", "#F2A541", "#D1495B", "#2E86AB", "#F5C518",
               "#3BB273"]
    for k, c in enumerate(crayons):                      # صف أقلام ملونة أسفل الصفحة
        x = 21 + k * 17.2
        haut = H - 34 - (k % 3) * 4
        d.rect(x, haut, 11, H - haut, f=c)
        d.rect(x + 3.6, haut, 3.8, H - haut, f="#FFFFFF", o=0.22)
        d.poly([(x, haut), (x + 11, haut), (x + 5.5, haut - 11)], f="#F2D7A6")
        d.poly([(x + 3.7, haut - 7.4), (x + 7.3, haut - 7.4), (x + 5.5, haut - 11)], f=c)


def _t_officiel(d: Dessin):
    noir = "#1A1A1A"
    d.rect(0, 0, L, H, f="#FFFFFF")
    d.rect(9, 9, L - 18, H - 18, s=noir, e=0.9)
    d.rect(11.5, 11.5, L - 23, H - 23, s=noir, e=0.3)
    _coins(d, 15, 16, noir, 0.5)
    for y in (40, H - 30):
        d.ligne([(34, y), (L / 2 - 10, y)], noir, 0.4)
        d.ligne([(L / 2 + 10, y), (L - 34, y)], noir, 0.4)
        d.poly(_etoile(L / 2, y, 5, rot=math.pi / 8), s=noir, e=0.5)
        d.poly(_etoile(L / 2, y, 2.2, rot=math.pi / 8), f=noir)


def _t_andalou(d: Dessin):
    grenat, or_, creme = "#7A1F2B", "#B8892B", "#FBF3E7"
    d.rect(0, 0, L, H, f=creme)
    d.poly(_etoile(L / 2, 150, 78, rot=math.pi / 8), s=or_, e=0.5, o=0.28)     # ميدالية خافتة خلف النص
    d.poly(_etoile(L / 2, 150, 62, rot=0), s=or_, e=0.4, o=0.22)
    d.cercle(L / 2, 150, 47, s=or_, e=0.4, o=0.22)
    for y in (22, H - 22):
        d.rect(10, y - 10, L - 20, 20, f=grenat)
        for k in range(14):                              # حلقات متشابكة
            cx = 21.6 + k * 12.83
            d.cercle(cx, y, 7.2, s=or_, e=0.55)
            d.poly(_losange(cx, y, 2, 2), f=or_)
    d.rect(8, 8, L - 16, H - 16, s=grenat, e=1.4)
    d.rect(10, 10, L - 20, H - 20, s=or_, e=0.4)
    for x in (16, L - 16):
        d.ligne([(x, 36), (x, H - 36)], or_, 0.4)
        d.ligne([(x + (1.6 if x < 100 else -1.6), 36), (x + (1.6 if x < 100 else -1.6), H - 36)], grenat, 0.4)


THEMES: dict[str, tuple[Theme, callable]] = {t.cle: (t, fn) for t, fn in (
    (Theme("zellige", "زليج فاس", "أزرق نيلي وذهبي، بإفريزَي خواتم.", "#23233F", "#2E3192", "#B8892B", "#F1E6CC",
           "#23233F", (30, 46, L - 30, H - 46)), _t_zellige),
    (Theme("arche", "القوس الأخضر", "قوس مغربي أخضر وذهبي يحتضن العنوان.", "#1F2B27", "#0F5B4A", "#C39A3B",
           "#E6EFE6", "#143D33", (22, 26, L - 22, H - 32)), _t_arche),
    (Theme("rihab", "رحاب", "هوية البرنامج: أزرق ماجوريل وأصفر، بزوايا مائلة.", "#1B1B3A", "#3B3FB6", "#3B3FB6",
           "#EEF0FF", "#1B1B3A", (28, 30, L - 24, H - 24)), _t_rihab),
    (Theme("nuit", "ليل وذهب", "خلفية كحلية بإطار ذهبي: للمناسبات الكبرى. يستهلك حبراً كثيراً.", "#F3EBD3",
           "#E6C46E", "#D9B25F", "#2C3270", "#F6EBC8", (26, 40, L - 26, H - 40)), _t_nuit),
    (Theme("terre", "تيراكوتا", "لون الطين وزخرفة المعيّنات على الجانبين.", "#3A2418", "#7A3216", "#1F6F6B",
           "#EAD9C2", "#3A2418", (30, 24, L - 30, H - 24)), _t_terre),
    (Theme("chaouen", "أزرق شفشاون", "أمواج زرقاء هادئة أعلى الصفحة وأسفلها.", "#1D2B3A", "#1E4E8C", "#1E4E8C",
           "#E1EEFA", "#16324F", (22, 54, L - 22, H - 46)), _t_chaouen),
    (Theme("fete", "احتفال", "رايات وقصاصات ملونة: للحفلات وأعياد المدرسة.", "#2B2233", "#7B2D8E", "#E4572E",
           "#FBE9E2", "#4A1E12", (22, 58, L - 22, H - 54)), _t_fete),
    (Theme("rentree", "دفتر وسبورة", "سبورة خضراء وأقلام ملونة: للدخول المدرسي.", "#23302C", "#FFFFFF", "#1F5D4C",
           "#FFF1B8", "#23302C", (20, 20, L - 20, H - 52)), _t_rentree),
    (Theme("officiel", "رسمي هادئ", "أبيض وأسود بإطار رفيع: للامتحانات، ويقتصد الحبر.", "#1A1A1A", "#000000",
           "#1A1A1A", "#EFEFEF", "#1A1A1A", (26, 18, L - 26, H - 36), economique=True), _t_officiel),
    (Theme("andalou", "أندلسي", "عنابي وذهبي بحلقات متشابكة وميدالية خافتة.", "#2F1A1D", "#7A1F2B", "#B8892B",
           "#F3E3CF", "#3A1A1F", (26, 38, L - 26, H - 38)), _t_andalou),
)}


def _mise_en_page(d: Dessin, th: Theme, c: Contenu) -> None:
    x0, y0, x1, y1 = th.zone
    w = x1 - x0
    y = y0
    # ترويسة المؤسسة
    entete = " · ".join(x for x in (c.direction.strip(), c.etablissement.strip()) if x)
    sur_fond = th.cle in ("arche", "rentree")            # العنوان داخل شكل خاص (القوس، السبورة)
    if th.cle == "arche":
        bx, bw = 52, L - 104
        if entete:
            d.textes.append(Texte((44, 47, L - 88, 8), entete, 11, th.encre, gras=True))
        d.textes.append(Texte((bx, 57, bw, 10), c.surtitre, 15, th.accent, gras=True, titre=True))
        d.textes.append(Texte((bx - 8, 68, bw + 16, 46), c.titre, 40, th.titre, gras=True, titre=True))
        y = 132
    elif th.cle == "rentree":
        if entete:
            d.textes.append(Texte((28, 30, L - 56, 9), entete, 12, "#DCEFE6", gras=True))
        d.textes.append(Texte((28, 41, L - 56, 10), c.surtitre, 15, "#F5C518", gras=True, titre=True))
        d.textes.append(Texte((30, 52, L - 60, 52), c.titre, 42, "#FFFFFF", gras=True, titre=True))
        y = 126
    if not sur_fond:
        if entete:
            d.textes.append(Texte((x0, y, w, 10), entete, 13, th.encre_entete or th.encre, gras=True))
            y += 13
        if c.surtitre.strip():
            larg = 46
            d.rect(L / 2 - larg / 2, y, larg, 11, f=th.accent, r=5.5)
            d.textes.append(Texte((L / 2 - larg / 2, y, larg, 11), c.surtitre, 14, _contraste(th.accent), gras=True,
                                  titre=True))
            y += 15
        d.textes.append(Texte((x0, y, w, 46), c.titre, 44, th.titre, gras=True, titre=True))
        y += 49
        d.ligne([(L / 2 - 30, y), (L / 2 - 5, y)], th.accent, 0.7)
        d.ligne([(L / 2 + 5, y), (L / 2 + 30, y)], th.accent, 0.7)
        d.poly(_etoile(L / 2, y, 2.6, rot=math.pi / 8), f=th.accent)
        y += 7
    # أسفل الصفحة أولاً، ثم النص يأخذ ما بقي
    bas = y1
    d.textes.append(Texte((x0, bas - 11, w * 0.42, 11), c.signature, 15, th.titre if not sur_fond else th.accent,
                          gras=True, titre=True))
    if c.note.strip():
        d.textes.append(Texte((x0 + w * 0.44, bas - 11, w * 0.56, 11), c.note, 11, th.encre, aligne="droite"))
    bas -= 15
    infos = c.infos()
    if infos:
        n = len(infos)
        par_ligne = 2 if n == 4 else min(n, 3)
        lignes = math.ceil(n / par_ligne)
        haut, esp = 23.0, 5.0
        bas -= lignes * haut + (lignes - 1) * esp
        for k, (lib, v) in enumerate(infos):
            li, co = divmod(k, par_ligne)
            dans = min(par_ligne, n - li * par_ligne)
            lw = (w - (dans - 1) * esp) / dans
            bx = x1 - (co + 1) * lw - co * esp           # من اليمين: التاريخ أولاً
            by = bas + li * (haut + esp)
            d.rect(bx, by, lw, haut, f=th.doux, r=4)
            d.rect(bx + lw - 2.2, by + 4, 2.2, haut - 8, f=th.accent, r=1.1)
            d.textes.append(Texte((bx + 3, by + 2.2, lw - 8, 7), lib, 10.5, th.sur_accent))
            d.textes.append(Texte((bx + 3, by + 9, lw - 8, haut - 11), v, 17, th.sur_accent, gras=True))
        bas -= 6
    if c.texte.strip():
        d.textes.append(Texte((x0 + 2, y, w - 4, max(20.0, bas - y)), c.texte, 22, th.encre))


def _contraste(couleur: str) -> str:
    r, g, b = (int(couleur[i:i + 2], 16) for i in (1, 3, 5))
    return "#FFFFFF" if 0.299 * r + 0.587 * g + 0.114 * b < 150 else "#1A1A1A"


def composer(theme: str, contenu: Contenu) -> Dessin:
    """الإعلان كاملاً: الزخرفة ثم النصوص. يرفض إعلاناً بلا عنوان."""
    if theme not in THEMES:
        raise ErreurAffiche("قالب غير معروف.")
    if not contenu.titre.strip():
        raise ErreurAffiche("اكتب عنوان الإعلان.")
    th, decor = THEMES[theme]
    d = Dessin()
    decor(d)
    _mise_en_page(d, th, contenu)
    return d


def apercu_vide(theme: str) -> Dessin:
    """الزخرفة وحدها (لمصغّرات اختيار القالب)."""
    th, decor = THEMES[theme]
    d = Dessin()
    decor(d)
    return d


# ---------- SVG (معاينة واختبار؛ البرنامج يرسم بـ QPainter) ----------

def en_svg(d: Dessin, format_: str = "A4", police: str = "sans-serif") -> str:
    lw, lh = FORMATS[format_]
    defs, corps = [], []
    prefixe = f"g{id(d):x}"

    def remplissage(f):
        if f is None:
            return "none"
        if isinstance(f, tuple):
            _, (x1, y1, x2, y2), c1, c2 = f
            gid = f"{prefixe}_{len(defs)}"
            defs.append(f'<linearGradient id="{gid}" gradientUnits="userSpaceOnUse" x1="{x1}" y1="{y1}" x2="{x2}" '
                        f'y2="{y2}"><stop offset="0" stop-color="{c1}"/><stop offset="1" stop-color="{c2}"/>'
                        "</linearGradient>")
            return f"url(#{gid})"
        return f

    for f in d.formes:
        style = (f'fill="{remplissage(f["f"])}" stroke="{f["s"] or "none"}" stroke-width="{f["e"]}" '
                 f'opacity="{f["o"]}" stroke-linejoin="round"')
        if f["t"] in ("poly", "ligne"):
            pts = " ".join(f"{x},{y}" for x, y in f["p"])
            corps.append(f'<{"polygon" if f["t"] == "poly" else "polyline"} points="{pts}" {style}/>')
        elif f["t"] == "cercle":
            corps.append(f'<circle cx="{f["c"][0]}" cy="{f["c"][1]}" r="{f["r"]}" {style}/>')
        else:
            x, y, w, h = f["b"]
            corps.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{f["r"]}" {style}/>')
    for t in d.textes:
        x, y, w, h = t.boite
        taille = t.taille * 0.3528                        # نقطة → مم
        just = "center" if t.aligne == "centre" else "flex-start"
        corps.append(
            f'<foreignObject x="{x}" y="{y}" width="{w}" height="{h}"><div xmlns="http://www.w3.org/1999/xhtml" '
            f'dir="rtl" style="width:100%;height:100%;display:flex;align-items:center;justify-content:{just};'
            f'text-align:{"center" if t.aligne == "centre" else "right"};font-family:{police};'
            f'font-size:{taille:.2f}px;line-height:1.35;color:{t.couleur};font-weight:{700 if t.gras else 400};'
            f'overflow:hidden">{escape(t.texte)}</div></foreignObject>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{lw}mm" height="{lh}mm" viewBox="0 0 {L} {H}">'
            f'<defs>{"".join(defs)}</defs>{"".join(corps)}</svg>')
