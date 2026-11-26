"""الشواهد التقديرية المزخرفة (طلب المدير 2026-11-22): مكوّن «التحفيز والتشجيع».

التصاميم مأخوذة من نماذج المدير (PowerPoint) بعد تجريدها من كل المعطيات الخاصة (أسماء المؤسسات والأشخاص
ورؤوس المراسلات وشعارات المؤسسات): لم تبق إلا الزخرفة، مسطّحةً في صورة خلفية لكل نموذج (resources/chawahid).
النصوص تُرسم فوقها من معطيات البرنامج: رأس رسمي (شعار الوزارة + الأكاديمية والمديرية والمؤسسة)، والعنوان،
واسم التلميذ(ة) من اللائحة، والسبب، والتاريخ، والتوقيع. الرسم (المعاينة وPDF) في ui/chawahid_rendu.py،
وهذه الوحدة تجمع المعطيات وتسجل التحفيز في سجل «التحفيز والتشجيع» وتصدر PowerPoint قابلاً للتعديل.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from idara.services import annee as annee_srv
from idara.services import etablissement as etab_srv
from idara.services import textes as tx

DOSSIER = Path(__file__).resolve().parent.parent / "resources" / "chawahid"
MINISTERE = Path(__file__).resolve().parent.parent / "resources" / "ministere.png"


class ErreurChahada(ValueError):
    """رسالة موجهة للمدير بالعربية."""


Zone = tuple[float, float, float, float]   # x، y، العرض، الارتفاع بالنسبة المئوية من الخلفية


@dataclass(frozen=True)
class Modele:
    cle: str
    nom: str
    description: str
    ratio: float                      # العرض/الارتفاع
    zones: dict                       # entete, titre?, corps, date, signature, logo?, medaille?
    nom_couleur: str = "#9A6A0F"
    texte_couleur: str = "#1B2A4A"
    titre_couleur: str = "#1B2A4A"
    titre_fixe: str = ""              # عنوان مخطوط ضمن الزخرفة (لا يُكتب فوقه عنوان)
    pour: tuple = field(default=("eleve",))
    famille: str = "رسمية ومزخرفة"

    @property
    def langues(self) -> tuple:
        """العنوان المخطوط بالعربية لا يصلح لشهادة بالفرنسية أو الأمازيغية."""
        return ("ar",) if self.titre_fixe else tuple(LANGUES)

    @property
    def fond(self) -> Path:
        return DOSSIER / f"{self.cle}.jpg"


MODELES: tuple[Modele, ...] = (
    Modele("almasi", "الماسي بالوسام", "إطار داكن بحواف ذهبية ووسام يحمل شعار المؤسسة، وعنوان «شهادة شكر وتقدير».",
           2167 / 1500, {"entete": (60, 6, 34, 22), "logo": (24, 11, 12.5, 18), "corps": (9, 35, 82, 45),
                         "date": (9, 80, 82, 5), "signature": (9, 85, 82, 8)},
           nom_couleur="#B07A16", titre_fixe="شهادة شكر وتقدير"),
    Modele("banafsaji", "البنفسجي بالوسام", "شريط بنفسجي وذهبي ووسام بشريطين، وعنوان «شهادة تفوق».",
           2167 / 1500, {"entete": (2, 3, 30, 20), "corps": (10, 38, 74, 31), "date": (10, 70, 74, 6),
                         "signature": (60, 84, 37, 11)},
           nom_couleur="#6A1B9A", titre_fixe="شهادة تفوق"),
    Modele("dhahabi_taqdir", "الذهبي المزخرف: شهادة تقدير",
           "إطار بزخارف ذهبية على أرضية زليج خفيفة، وعنوان مخطوط «شهادة تقدير».",
           2167 / 1500, {"entete": (18, 4.5, 64, 15), "corps": (10, 36, 80, 41), "date": (10, 77, 80, 5),
                         "signature": (14, 82, 72, 9)},
           nom_couleur="#A0522D", titre_fixe="شهادة تقدير"),
    Modele("dhahabi_chukr", "الذهبي المزخرف: شكر وتقدير",
           "الإطار الذهبي نفسه بعنوان مخطوط «شهادة شكر وتقدير» (للتلاميذ وللأطر والشركاء).",
           2167 / 1500, {"entete": (18, 4.5, 64, 12), "corps": (10, 36, 80, 41), "date": (10, 77, 80, 5),
                         "signature": (14, 82, 72, 9)},
           nom_couleur="#A0522D", titre_fixe="شهادة شكر وتقدير", pour=("eleve", "adulte")),
    Modele("satair", "الستائر الذهبية", "ستائر ذهبية ووسام يحمل تاريخ التتويج، وعنوان «شهادة شكر وتقدير».",
           2000 / 1500, {"entete": (17, 9, 62, 20), "medaille": (82.5, 9.5, 14.5, 18), "corps": (9, 45, 78, 35),
                         "date": (9, 80, 78, 5), "signature": (9, 85, 78, 8)},
           nom_couleur="#8C6A00", titre_fixe="شهادة شكر وتقدير", pour=("eleve", "adulte")),
    Modele("rasmi", "الرسمي بالأحمر والأخضر", "ألوان العلم الوطني ووسام بشعار المملكة، والعنوان حسب نوع التحفيز.",
           2000 / 1500, {"entete": (24, 3, 46, 17), "titre": (24, 20, 52, 12), "corps": (22, 33, 68, 42),
                         "date": (28, 76, 66, 5), "signature": (34, 81, 60, 10)},
           nom_couleur="#C1272D", titre_couleur="#1E6B2F", pour=("eleve", "adulte")),
    Modele("nuhasi", "الإطار النحاسي", "إطار نحاسي بزخارف أندلسية على أرضية بيضاء، والعنوان حسب نوع التحفيز.",
           2000 / 1500, {"entete": (12, 12, 76, 13), "titre": (12, 25, 76, 11), "corps": (12, 37, 76, 37),
                         "date": (12, 74, 76, 5), "signature": (12, 79, 76, 8)},
           nom_couleur="#8B4513", titre_couleur="#8B4513", pour=("eleve", "adulte")),
)

# الدفعة الثانية (نماذج المدير 2026-11-24/26): تسعة تصاميم «شهادة شكر وتقدير» بعنوان مخطوط
# (جُرّدت من النصوص ومن شعار الموقع الذي صممها، وصار مكانه قرصاً فارغاً يحمل شعار المؤسسة إن وُجد)،
# وستة إطارات للصغار بشريط عنوان، تصلح للعربية والفرنسية والأمازيغية.
_R2 = 2000 / 1384
_R3 = 2000 / 1385
_CHUKR = "شهادة شكر وتقدير"
_F2, _F3 = "شكر وتقدير", "للصغار بثلاث لغات"
MODELES = MODELES + (
    Modele("dhahabi_fanous", "الذهبي بالفوانيس", "أمواج ذهبية وفانوسان وكأس، وعنوان مخطوط «شهادة شكر وتقدير».", _R2,
           {"entete": (64, 12, 31, 19), "corps": (8, 38, 84, 30), "date": (6, 71, 34, 5),
            "signature": (60, 69, 34, 8)}, nom_couleur="#A66F00", titre_fixe=_CHUKR, famille=_F2),
    Modele("ahmar_wisam", "الأحمر بالوسام", "شريطان أحمران متقاطعان ووسام في الأعلى يحمل شعار المؤسسة.", _R2,
           {"entete": (69, 12, 27, 19), "logo": (44.6, 0.3, 10.8, 13), "corps": (8, 42, 84, 28),
            "date": (6, 72, 34, 5), "signature": (60, 70, 34, 8)}, nom_couleur="#B71C1C", titre_fixe=_CHUKR,
           famille=_F2),
    Modele("itar_tilmidh", "الإطار الذهبي بالتلميذ", "إطار ذهبي مزخرف وتلميذ مجتهد، ووسام أسفل الشهادة.", _R2,
           {"entete": (63, 11, 30, 19), "logo": (44, 72, 12, 17), "corps": (9, 38, 82, 29),
            "date": (13, 67, 29, 5), "signature": (63, 64, 28, 8)}, nom_couleur="#8B5A00", titre_fixe=_CHUKR,
           famille=_F2),
    Modele("burtuqali_ittar", "البرتقالي المؤطر", "إطار برتقالي بنقوش وأرضية عاجية، وكأس في الأسفل.", _R2,
           {"entete": (67, 11, 23, 20), "corps": (11, 37, 78, 31), "date": (11, 74, 33, 5),
            "signature": (56, 71, 33, 9)}, nom_couleur="#C25400", titre_fixe=_CHUKR, famille=_F2),
    Modele("khatm_ahmar", "الختم الأحمر", "موجات حمراء ورمادية وختم شمعي، ورمز المعرفة في الأسفل.", _R2,
           {"entete": (66, 19, 30, 16), "corps": (8, 40, 84, 26), "date": (6, 72, 34, 5),
            "signature": (60, 70, 34, 8)}, nom_couleur="#B71C1C", titre_fixe=_CHUKR, famille=_F2),
    Modele("midaliya", "الميدالية الذهبية", "شريط ذهبي وميدالية تحمل شعار المؤسسة، وموجة ذهبية في الأسفل.", _R2,
           {"entete": (72, 8, 25, 22), "logo": (4.6, 13.6, 9.6, 15), "corps": (8, 38, 84, 29),
            "date": (10, 69, 27, 5), "signature": (64, 66, 30, 8)}, nom_couleur="#8C6A00", titre_fixe=_CHUKR,
           famille=_F2),
    Modele("abbad_shams", "عباد الشمس", "إطار ذهبي على أرضية زهرة عباد الشمس، ووسام يحمل شعار المؤسسة.", _R2,
           {"entete": (67, 9, 26, 20), "logo": (44, 71, 12, 18), "corps": (9, 38, 82, 28),
            "date": (10, 70, 27, 5), "signature": (63, 68, 28, 8)}, nom_couleur="#9A5B00", titre_fixe=_CHUKR,
           famille=_F2),
    Modele("urjuwani", "الأرجواني", "منحنيات أرجوانية وذهبية وختم شمعي يحمل شعار المؤسسة.", _R2,
           {"entete": (70, 4, 27, 20), "logo": (42, 70, 9.5, 14), "corps": (16, 33, 66, 32),
            "date": (14, 72, 26, 5), "signature": (50, 68, 32, 8)}, nom_couleur="#7B1F3A", titre_fixe=_CHUKR,
           famille=_F2),
    Modele("turquazi", "الفيروزي", "إطار فيروزي بارز على أرضية بيضاء، ومكتب التلميذ في الأسفل.", _R2,
           {"entete": (60, 13, 29, 20), "corps": (12, 39, 76, 28), "date": (12, 77, 28, 5),
            "signature": (61, 75, 26, 8)}, nom_couleur="#00796B", titre_fixe=_CHUKR, famille=_F2),
    Modele("nujum_aswad", "النجوم بالإطار الأسود", "نجوم وتلاميذ ومدرسة، وشريط عنوان أصفر؛ بالعربية أو الفرنسية "
           "أو الأمازيغية.", _R3,
           {"entete": (30, 2, 40, 19), "titre": (33.5, 23, 33, 8), "corps": (9, 37, 82, 24),
            "date": (18, 63, 40, 5), "signature": (18, 68, 40, 8)}, nom_couleur="#C62828", famille=_F3),
    Modele("nujum_burtuqali", "النجوم بالإطار البرتقالي", "الرسم نفسه بإطار برتقالي؛ بالعربية أو الفرنسية "
           "أو الأمازيغية.", _R3,
           {"entete": (30, 2, 40, 19), "titre": (33.5, 23, 33, 8), "corps": (9, 37, 82, 23),
            "date": (18, 62, 40, 5), "signature": (18, 67, 40, 8)}, nom_couleur="#D35400", famille=_F3),
    Modele("zahra_wardiya", "الزهرة الوردية", "إطار وردي بزهرة ووسام وشريط عنوان؛ بالعربية أو الفرنسية "
           "أو الأمازيغية.", _R3,
           {"entete": (19, 28, 54, 14), "titre": (71, 12, 27, 7), "corps": (19, 42, 54, 29),
            "date": (16, 74, 26, 5), "signature": (44, 73, 28, 8)}, nom_couleur="#AD1457", famille=_F3),
    Modele("zahra_khadra", "الزهرة الخضراء", "الإطار نفسه بالأخضر؛ بالعربية أو الفرنسية أو الأمازيغية.", _R3,
           {"entete": (19, 28, 54, 14), "titre": (71, 12, 27, 7), "corps": (19, 42, 54, 29),
            "date": (16, 74, 26, 5), "signature": (44, 73, 28, 8)}, nom_couleur="#2E7D32", famille=_F3),
    Modele("wisam_burtuqali", "الوسامان البرتقاليان", "موجتان برتقاليتان ووسامان حول شريط العنوان؛ بالعربية "
           "أو الفرنسية أو الأمازيغية.", _R3,
           {"entete": (30, 8, 40, 13), "titre": (33.5, 29, 33, 7), "corps": (10, 38, 80, 32),
            "date": (10, 71, 38, 5), "signature": (54, 70, 36, 8)}, nom_couleur="#BF360C", famille=_F3),
    Modele("wisam_azraq", "الوسامان الأزرقان", "موجتان زرقاوان ووسامان حول شريط العنوان؛ بالعربية أو الفرنسية "
           "أو الأمازيغية.", _R3,
           {"entete": (30, 8, 40, 13), "titre": (33.5, 29, 33, 7), "corps": (10, 38, 80, 32),
            "date": (10, 71, 38, 5), "signature": (54, 70, 36, 8)}, nom_couleur="#1A4E9A", famille=_F3),
)
PAR_CLE = {m.cle: m for m in MODELES}
FAMILLES = tuple(dict.fromkeys(m.famille for m in MODELES))

TYPES = ("شهادة تقديرية", "شهادة تفوق", "تهنئة", "تشجيع", "لوحة الشرف")
TITRES = {"شهادة تقديرية": "شهادة تقديرية", "شهادة تفوق": "شهادة تفوق", "تهنئة": "شهادة تهنئة",
          "تشجيع": "شهادة تشجيع", "لوحة الشرف": "شهادة استحقاق"}
NATURES = {"شهادة تقديرية": "الشهادة التقديرية", "شهادة تفوق": "شهادة التفوق", "تهنئة": "شهادة التهنئة",
           "تشجيع": "شهادة التشجيع", "لوحة الشرف": "شهادة الاستحقاق"}
PERIODES = ("الأسدوس الأول", "الأسدوس الثاني", "نهاية السنة")
# أسباب مقترحة: {ه} ← ه/ها، {له} ← له/لها، {الفترة} ← الفترة والموسم
MOTIFS = (
    "تقديراً لتفوق{ه} الدراسي ونتائج{ه} المتميزة خلال {الفترة}.",
    "تقديراً لحصول{ه} على الرتبة الأولى في قسم{ه} خلال {الفترة}.",
    "تقديراً لحصول{ه} على الرتبة الثانية في قسم{ه} خلال {الفترة}.",
    "تقديراً لحصول{ه} على الرتبة الثالثة في قسم{ه} خلال {الفترة}.",
    "تقديراً لانضباط{ه} وحسن سلوك{ه} ومواظبت{ه} على الحضور.",
    "تشجيعاً ل{ه} على التحسن الملحوظ في نتائج{ه} خلال {الفترة}.",
    "تقديراً لمشاركت{ه} المتميزة في أنشطة المؤسسة.",
    "تهنئةً ل{ه} على تتويج{ه} في المسابقة.",
)
VOEU = "متمنين {له} مزيداً من التألق والنجاح."

# ---------- اللغات (نماذج المدير 2026-11-26: شواهد بالعربية والفرنسية والأمازيغية) ----------
# النصوص الفرنسية والأمازيغية مأخوذة من نموذج «ATT_AR_FR_AMZ_2022» (حروف تيفيناغ كما وردت فيه).
LANGUES = {"ar": "العربية", "fr": "الفرنسية", "amz": "الأمازيغية (تيفيناغ)"}
TITRES_FR = {"شهادة تقديرية": "ATTESTATION D'HONNEUR", "شهادة تفوق": "ATTESTATION D'EXCELLENCE",
             "تهنئة": "ATTESTATION DE FÉLICITATIONS", "تشجيع": "ATTESTATION D'ENCOURAGEMENT",
             "لوحة الشرف": "TABLEAU D'HONNEUR"}
TITRE_AMZ = "ⴰⵙⵍⴽⵉⵏ ⵏ ⵓⵙⵎⵖⵔ"
PERIODES_FR = {"الأسدوس الأول": "la première session", "الأسدوس الثاني": "la deuxième session",
               "نهاية السنة": "l'année scolaire"}
PERIODES_AMZ = {"الأسدوس الأول": " ⴳ ⵜⵙⵓⵜⵍⵜ: 01", "الأسدوس الثاني": " ⴳ ⵜⵙⵓⵜⵍⵜ: 02", "نهاية السنة": ""}
MOTIFS_FR = (
    "En reconnaissance de ses efforts remarquables lors de {الفترة}.",
    "Pour ses excellents résultats scolaires lors de {الفترة}.",
    "Pour avoir obtenu la première place de sa classe lors de {الفترة}.",
    "Pour avoir obtenu la deuxième place de sa classe lors de {الفترة}.",
    "Pour avoir obtenu la troisième place de sa classe lors de {الفترة}.",
    "Pour sa discipline, sa bonne conduite et son assiduité.",
    "Pour ses progrès remarquables lors de {الفترة}.",
    "Pour sa participation distinguée aux activités de l'établissement.",
)
MOTIFS_AMZ = ("ⵙ ⵜⵢⴰⴼⵓⵜⵉⵏ ⵉⵥⵉⵍⵏ ⵏⵏⴰ ⴷ {ⵜ}ⵢⵉⵡⵉ{الفترة}.",)
MOTIFS_LANGUE = {"ar": MOTIFS, "fr": MOTIFS_FR, "amz": MOTIFS_AMZ}
VOEUX = {"ar": VOEU, "fr": "Avec nos vœux de réussite et d'excellence continue.",
         "amz": "ⵔⵏⵓ ⴳ ⵓⵎⵓⵔⵙ {ⵏⵏⴽ}. ⴰⵏⵏⴰⵣ ⵉⵖⵓⴷⴰⵏ."}
SIGNATAIRES = {"fr": {"مدير المؤسسة": "La Direction", "رئيس جمعية الآباء": "Le Président de l'Association des Parents"},
               "amz": {"مدير المؤسسة": "ⵜⴰⵎⵀⵍⴰ ⵜⴰⵙⴳⵎⴰⵏⵜ"}}


def intro_defaut(conn: sqlite3.Connection, type_: str, langue: str = "ar") -> str:
    e = etab_srv.lire_etablissement(conn)
    if langue == "fr":
        etab = (e.nom_fr or e.nom_ar) if e else "l'établissement"
        return (f"La direction et le corps enseignant de l'établissement {etab} ont le plaisir de décerner "
                "cette attestation à l'apprenant(e) :")
    if langue == "amz":
        etab = (e.nom_fr or e.nom_ar) if e else ""
        return (f"ⵉⵙⵙⵓⵙⵎ ⵛⵉⴳⴰⵏ ⵜⴰⵎⵀⵍⴰ ⵏ ⵜⵎⵔⵙⵍⵜ ⵜⴰⵙⵍⵎⴷⴰⵏⵜ: {etab} ⴷ ⵉⵎⵙⵙⵓⴳⴰⵔ ⵉⵙⴳⵎⴰⵏⵏ ⴷⵉⴽⵙ, "
                "ⴰⴷ ⴼⴽⵉⵏ ⴰⵙⵍⴽⵏ ⵏ ⵓⵙⵎⵖⵔ ⵉ {ⵜ}ⵓⵏⵍⵎⴰⴷ{ⵜ}:")
    etab = e.nom_ar if e else "المؤسسة"
    return f"يتشرف مدير وأطر {etab} بتقديم هذه {NATURES[type_]} إلى التلميذ(ة):"


def accorder(texte: str, feminin: bool) -> str:
    """صيغ التذكير والتأنيث: {ه} {له} {ة} و«(ة)»."""
    t = texte or ""
    for a, m, f in (("{ه}", "ه", "ها"), ("{له}", "له", "لها"), ("{ة}", "", "ة"), ("(ة)", "", "ة"),
                    ("{e}", "", "e"), ("(e)", "", "e"), ("{ⵜ}", "", "ⵜ"), ("{ⵏⵏⴽ}", "ⵏⵏⴽ", "ⵏⵏⵎ")):
        t = t.replace(a, f if feminin else m)
    return t


def entete(conn: sqlite3.Connection, langue: str = "ar") -> list[str]:
    """أسطر الرأس تحت شعار الوزارة: الأكاديمية، المديرية الإقليمية، المؤسسة."""
    from idara.services.mouvements import formule_academie, formule_direction
    e = etab_srv.lire_etablissement(conn)
    if e is None:
        return []
    if langue == "fr" and (e.academie_fr or e.direction_fr or e.nom_fr):
        def pref(v, debut, lib):
            v = " ".join((v or "").split())
            return v if not v or v.lower().startswith(debut) else f"{lib} : {v}"
        return [x for x in (pref(e.academie_fr, ("acad", "aref"), "Académie Régionale d'Éducation et de Formation"),
                            pref(e.direction_fr, ("dir",), "Direction Provinciale"),
                            " ".join((e.nom_fr or "").split())) if x]
    return [x for x in (formule_academie(e.academie_ar), formule_direction(e.direction_ar), e.nom_ar) if x]


def logo_etablissement(conn: sqlite3.Connection, dossier) -> str:
    """شعار المؤسسة إن وُجد (شعار شاشة العرض أولاً، ثم شعار الإعداد)."""
    try:
        from idara.services import ecran as ec
        p = ec.chemin_logo(conn, dossier)
        if p:
            return p
    except Exception:  # noqa: BLE001
        pass
    e = etab_srv.lire_etablissement(conn)
    if e and e.logo_path and dossier is not None:
        p = Path(dossier.racine) / e.logo_path
        if p.exists():
            return str(p)
    return ""


def eleves(conn: sqlite3.Connection, classe: str | None = None) -> list[dict]:
    """تلاميذ السنة الجارية: {id، nom، classe، sexe}، مرتبين حسب القسم ثم الاسم."""
    a = annee_srv.annee_courante(conn)
    if a is None:
        return []
    sql = ("SELECT e.id, e.nom_ar, e.prenom_ar, e.nom_fr, e.prenom_fr, e.sexe, c.code AS classe FROM inscription i "
           "JOIN eleve e "
           "ON e.id=i.eleve_id LEFT JOIN classe c ON c.id=i.classe_id WHERE i.annee_id=? AND "
           "i.statut IN ('inscrit','arrive')")
    args: list = [a["id"]]
    if classe:
        sql += " AND c.code=?"
        args.append(classe)
    rs = conn.execute(sql + " ORDER BY c.code, e.prenom_ar, e.nom_ar", args).fetchall()
    return [{"id": r["id"], "nom": f"{r['prenom_ar']} {r['nom_ar']}".strip(), "classe": r["classe"] or "",
             "sexe": r["sexe"] or "M",
             "nom_lat": " ".join(f"{r['prenom_fr'] or ''} {(r['nom_fr'] or '').upper()}".split())} for r in rs]


def classes(conn: sqlite3.Connection) -> list[str]:
    return sorted({e["classe"] for e in eleves(conn) if e["classe"]})


def _periode_complete(conn, periode: str) -> str:
    a = annee_srv.annee_courante(conn)
    an = f"الموسم الدراسي {a['libelle']}" if a else ""
    if not periode:
        return an
    if periode == "نهاية السنة":
        return f"{an}" if an else "السنة الدراسية"
    return f"{periode} من {an}" if an else periode


def _periode_langue(conn, periode: str, langue: str) -> str:
    if langue == "amz":
        return PERIODES_AMZ.get(periode, "")
    a = annee_srv.annee_courante(conn)
    lib = a["libelle"] if a else ""
    p = PERIODES_FR.get(periode, "l'année scolaire")
    if p == "l'année scolaire":
        return f"{p} {lib}".strip()
    return f"{p} de l'année scolaire {lib}".strip()


def droite_a_gauche(texte: str) -> bool:
    """اتجاه السطر من أول حرف قوي فيه: العربي من اليمين، واللاتيني وتيفيناغ من اليسار."""
    import unicodedata
    for ch_ in texte or "":
        b = unicodedata.bidirectional(ch_)
        if b in ("R", "AL"):
            return True
        if b == "L":
            return False
    return True


def _annee_amazighe(conn) -> str:
    """السنة الأمازيغية = الميلادية + 950 (كما في النموذج: 2971/2972 · 2021/2022)."""
    a = annee_srv.annee_courante(conn)
    if not a:
        return ""
    try:
        y1, y2 = (int(x) for x in a["libelle"].split("/"))
    except ValueError:
        return a["libelle"]
    return f"ⴰⵙⴳⴳⵯⴰⵙ ⴰⵏⵎⵍⴰⵏ {y1 + 950}/{y2 + 950} · {y1}/{y2}"


def contenu(conn: sqlite3.Connection, eleve: dict, type_: str = "شهادة تقديرية", motif: str = "",
            periode: str = "", le: str | None = None, intro: str | None = None, voeu: str | None = None,
            signataires: tuple = ("مدير المؤسسة",), afficher_classe: bool = True, langue: str = "ar") -> dict:
    """كل نصوص الشهادة لتلميذ(ة) واحد(ة). eleve: {nom، classe، sexe، nom_lat}."""
    if type_ not in TYPES:
        raise ErreurChahada("نوع التحفيز غير معروف.")
    if langue not in LANGUES:
        raise ErreurChahada("لغة الشهادة غير معروفة.")
    if langue != "ar":
        return _contenu_langue(conn, eleve, type_, motif, periode, le, intro, voeu, signataires, afficher_classe,
                               langue)
    nom = " ".join((eleve.get("nom") or "").split())
    if not nom:
        raise ErreurChahada("اختر التلميذ(ة) من اللائحة.")
    fem = (eleve.get("sexe") or "M") == "F"
    e = etab_srv.lire_etablissement(conn)
    motif = " ".join((motif or "").split())
    if not motif:
        raise ErreurChahada("اكتب سبب التحفيز أو اختر واحداً من المقترحات.")
    motif = motif.replace("{الفترة}", _periode_complete(conn, periode))
    reste = re.findall(r"\{([^}]*)\}", motif.replace("{ه}", "").replace("{له}", "").replace("{ة}", ""))
    if reste:
        raise ErreurChahada(f"أكمل في السبب: «{reste[0]}».")
    le = le or date.today().isoformat()
    if intro is None:
        intro = intro_defaut(conn, type_, "ar")
    ville = e.ville_redaction_ar if e and e.ville_redaction_ar else ""
    y, m, j = le.split("-")
    return {
        "entete": entete(conn),
        "titre": TITRES[type_],
        "intro": accorder(" ".join(intro.split()), fem),
        "nom": nom,
        "classe": f"القسم: {eleve.get('classe')}" if afficher_classe and eleve.get("classe") else "",
        "motif": accorder(motif, fem),
        "voeu": accorder(VOEU if voeu is None else voeu, fem),
        "date": (f"حرر في {ville} بتاريخ {tx.date_chiffres(le)}" if ville else f"حرر بتاريخ {tx.date_chiffres(le)}"),
        "signataires": [s for s in signataires if s],
        "jour": str(int(j)), "mois": tx.MOIS_AR[int(m) - 1], "annee": y,
        "_eleve": eleve, "_type": type_, "_motif": accorder(motif, fem), "_periode": periode, "_date": le,
        "langue": "ar", "ltr": False,
    }


def _contenu_langue(conn, eleve, type_, motif, periode, le, intro, voeu, signataires, afficher_classe,
                    langue) -> dict:
    """الشهادة بالفرنسية أو بالأمازيغية: الاسم بالحروف اللاتينية إن سُجّل في مسار، وإلا بالعربية."""
    nom = " ".join((eleve.get("nom_lat") or eleve.get("nom") or "").split())
    if not nom:
        raise ErreurChahada("اختر التلميذ(ة) من اللائحة.")
    fem = (eleve.get("sexe") or "M") == "F"
    e = etab_srv.lire_etablissement(conn)
    motif = " ".join((motif or "").split()) or MOTIFS_LANGUE[langue][0]
    motif = motif.replace("{الفترة}", _periode_langue(conn, periode, langue))
    le = le or date.today().isoformat()
    y, m, j = le.split("-")
    intro = intro_defaut(conn, type_, langue) if intro is None else intro
    cl = eleve.get("classe") if afficher_classe else ""
    if langue == "fr":
        titre = TITRES_FR[type_]
        classe = f"Niveau : {cl}" if cl else ""
        ville = (e.ville_redaction_fr or "") if e else ""
        ladate = f"Fait à {ville}, le {j}/{m}/{y}" if ville else f"Fait le {j}/{m}/{y}"
    else:
        titre = TITRE_AMZ
        an = _annee_amazighe(conn)
        classe = " · ".join(x for x in ((f"ⴳ ⵓⵙⵡⵉⵔ: {cl}" if cl else ""), an) if x)
        ville = (e.ville_redaction_fr or e.ville_redaction_ar or "") if e else ""
        ladate = f"{ville}, {j}/{m}/{y}" if ville else f"{j}/{m}/{y}"
    noms = SIGNATAIRES.get(langue, {})
    return {
        "entete": entete(conn, langue),
        "titre": titre,
        "intro": accorder(" ".join(intro.split()), fem),
        "nom": nom,
        "classe": classe,
        "motif": accorder(motif, fem),
        "voeu": accorder(VOEUX[langue] if voeu is None else voeu, fem),
        "date": ladate,
        "signataires": [noms.get(x, x) for x in signataires if x],
        "jour": str(int(j)), "mois": m, "annee": y,
        "_eleve": eleve, "_type": type_, "_motif": accorder(motif, fem), "_periode": periode, "_date": le,
        "langue": langue, "ltr": True,
    }


def enregistrer(conn: sqlite3.Connection, contenus: list[dict], modele: str) -> list[int]:
    """يسجل كل شهادة في سجل «التحفيز والتشجيع» (يظهر أيضاً في الملف الشامل للتلميذ)."""
    from idara.services import registres as rg
    ids = []
    for c in contenus:
        el = c["_eleve"]
        ids.append(rg.enregistrer(conn, "tahfiz", {
            "date": c["_date"], "eleve": el["nom"], "classe": el.get("classe", ""), "type": c["_type"],
            "motif": c["_motif"], "periode": c["_periode"] if c["_periode"] in PERIODES else "",
            "modele": (PAR_CLE[modele].nom if modele in PAR_CLE else "")
            + (f" ({LANGUES[c['langue']]})" if c.get("langue", "ar") != "ar" else "")}))
    return ids


def exemple(conn: sqlite3.Connection, type_: str = "شهادة تقديرية", langue: str = "ar") -> dict:
    """محتوى توضيحي لمعرض الشواهد."""
    return contenu(conn, {"nom": "اسم التلميذة أو التلميذ", "nom_lat": "Prénom NOM", "classe": "", "sexe": "M"},
                   type_, MOTIFS_LANGUE[langue][0], "الأسدوس الأول", langue=langue)


def chemin_sortie(dossier, nom: str, ext: str) -> Path:
    from datetime import datetime
    rep = Path(dossier.archives) / "الشواهد التقديرية"
    rep.mkdir(parents=True, exist_ok=True)
    propre = re.sub(r'[\\/:*?"<>|]', "_", nom).replace(" ", "_")
    chemin = rep / f"{datetime.now():%Y%m%d_%H%M%S}_{propre}.{ext}"
    n = 1
    while chemin.exists():
        n += 1
        chemin = chemin.with_name(f"{chemin.stem}_{n}.{ext}")
    return chemin


def nom_fichier(contenus: list[dict], modele: str) -> str:
    n = len(contenus)
    qui = contenus[0]["nom"] if n == 1 else f"{n} تلاميذ"
    return f"{contenus[0]['titre']} - {qui}"


# ---------- PowerPoint قابل للتعديل ----------

def _rgb(h: str):
    from pptx.dml.color import RGBColor
    return RGBColor.from_string(h.lstrip("#"))


POLICES_PPT = {"ar": "Sakkal Majalla", "fr": "Calibri", "amz": "Ebrima"}


def _boite(sl, prs, zone: Zone, lignes: list[tuple[str, float, str, bool]], langue: str = "ar") -> None:
    """مربع نص (من اليمين للعربية، ومن اليسار للفرنسية والأمازيغية)، في الوسط، بأسطر (النص، الحجم، اللون، عريض)."""
    from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
    from pptx.oxml.ns import qn
    from pptx.util import Pt
    x, y, w, h = zone
    W, H = prs.slide_width, prs.slide_height
    tb = sl.shapes.add_textbox(int(W * x / 100), int(H * y / 100), int(W * w / 100), int(H * h / 100))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    for k, (t, taille, coul, gras) in enumerate(lignes):
        p = tf.paragraphs[0] if k == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.CENTER
        p._p.get_or_add_pPr().set("rtl", "1" if langue == "ar" else "0")
        r = p.add_run()
        r.text = t
        f = r.font
        f.size = Pt(taille)
        f.bold = gras
        f.color.rgb = _rgb(coul)
        police = POLICES_PPT.get(langue, "Sakkal Majalla")
        f.name = police
        rpr = r._r.get_or_add_rPr()
        cs = rpr.find(qn("a:cs"))
        if cs is None:
            cs = rpr.makeelement(qn("a:cs"), {})
            rpr.append(cs)
        cs.set("typeface", police)
        rpr.set("lang", {"ar": "ar-MA", "fr": "fr-FR", "amz": "zgh-MA"}.get(langue, "ar-MA"))


def generer_pptx(contenus: list[dict], modele: str, chemin: Path, logo: str = "") -> Path:
    """شريحة لكل تلميذ(ة): الزخرفة صورة خلفية، والنصوص مربعات قابلة للتعديل في PowerPoint."""
    from pptx import Presentation
    from pptx.util import Emu
    m = PAR_CLE[modele]
    prs = Presentation()
    prs.slide_height = Emu(6858000)
    prs.slide_width = Emu(int(6858000 * m.ratio))
    W, H = prs.slide_width, prs.slide_height
    for c in contenus:
        lg = c.get("langue", "ar")
        sl = prs.slides.add_slide(prs.slide_layouts[6])
        sl.shapes.add_picture(str(m.fond), 0, 0, W, H)
        x, y, w, h = m.zones["entete"]
        if MINISTERE.exists():
            hi = h * 0.42
            wi = min(w, hi * H / W * 694 / 82)
            sl.shapes.add_picture(str(MINISTERE), int(W * (x + (w - wi) / 2) / 100), int(H * y / 100),
                                  int(W * wi / 100), int(H * hi / 100))
            _boite(sl, prs, (x, y + hi, w, h - hi), [(l, 10, m.texte_couleur, k == 2)
                                                      for k, l in enumerate(c["entete"])],
                  "ar" if droite_a_gauche(" ".join(c["entete"])) else "fr")
        if logo and "logo" in m.zones:
            lx, ly, lw, lh = m.zones["logo"]
            s = min(lw * W / 100, lh * H / 100) * 0.8
            sl.shapes.add_picture(logo, int(W * (lx + lw / 2) / 100 - s / 2), int(H * (ly + lh / 2) / 100 - s / 2),
                                  int(s), int(s))
        if "titre" in m.zones:
            _boite(sl, prs, m.zones["titre"], [(c["titre"], min(44.0, m.zones["titre"][3] * 3.2), m.titre_couleur, True)], lg)
        lignes = [(c["intro"], 18, m.texte_couleur, False), (c["nom"], 36, m.nom_couleur, True)]
        if c["classe"]:
            lignes.append((c["classe"], 15, m.texte_couleur, True))
        lignes += [(c["motif"], 18, m.texte_couleur, False), (c["voeu"], 15, m.texte_couleur, False)]
        _boite(sl, prs, m.zones["corps"], lignes, lg)
        _boite(sl, prs, m.zones["date"], [(c["date"], 13, m.texte_couleur, False)], lg)
        _boite(sl, prs, m.zones["signature"], [("        ".join(c["signataires"]), 15, m.texte_couleur, True)], lg)
        if "medaille" in m.zones:
            _boite(sl, prs, m.zones["medaille"], [(c["jour"], 22, "#5A4300", True), (c["mois"], 13, "#5A4300", True),
                                                  (c["annee"], 13, "#5A4300", True)])
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(chemin))
    return chemin
