"""دليل «كيفية استخدام البرنامج»: مراحل العمل بالترتيب، مع زر «اذهب إلى» وحالة إنجاز كل مرحلة
(اقتراح المدير 2026-11-06، مستوحى من دليل المراحل في تطبيقات أخرى)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from idara.ui.composants import carte
from idara.ui.page_pedagogie import _page

# (العنوان، الوصف، الخطوات، الصفحة، نص الزر، استعلام الإنجاز → عدد، صيغة الإنجاز)
ETAPES = [
    ("الإعدادات ومعلومات المؤسسة",
     "ابدأ هنا قبل أي استيراد أو طباعة: كل ما تكتبه يظهر في ترويسة الوثائق المولَّدة.",
     ["أكمل معلومات المؤسسة والمدير والوحدات المدرسية، وحدد إن كانت المؤسسة رائدة.",
      "أضف الشعار أو الترويسة والعلامة المائية في «الهوية البصرية للوثائق».",
      "اختر مظهر البرنامج الذي يريح عينك."],
     "إعداد المؤسسة", "اذهب إلى الإعدادات",
     "SELECT COUNT(*) FROM etablissement WHERE nom_ar IS NOT NULL AND nom_ar<>''", "معلومات المؤسسة مسجلة"),
    ("استيراد لوائح التلاميذ من مسار",
     "لوائح الأقسام (العربية والفرنسية) تُستورد مرة في بداية السنة، وتُعاد كلما تغيرت.",
     ["صدّر لوائح التلاميذ من منظومة مسار (ListEleve) بالعربية ثم بالفرنسية.",
      "استوردها: البرنامج يطابق التلاميذ بالرمز ولا يكرر أحداً.",
      "راجع الوافدين والمغادرين المحتملين قبل تأكيدهم."],
     "الاستيراد من مسار", "اذهب إلى الاستيراد",
     "SELECT COUNT(*) FROM inscription WHERE statut IN ('inscrit','arrive')", "{n} تلميذاً يتابعون دراستهم"),
    ("الموارد البشرية",
     "ملف كل موظف: يدوياً أو من ملف XML للموارد البشرية، ثم إسناد الأقسام.",
     ["استورد ملف XML (أو أدخل المعلومات يدوياً)، ثم راجع النتيجة قبل اعتمادها.",
      "أكمل لكل أستاذ: الوحدة، الأقسام المسندة، الساعات، وآخر تفتيش.",
      "الرخص ومحاضر الاستئناف وتدبير الفائض في نفس القسم."],
     "الموارد البشرية", "اذهب إلى الموارد البشرية",
     "SELECT COUNT(*) FROM personnel WHERE statut='actif' AND categorie<>'directeur'", "{n} موظفاً مسجلاً"),
    ("برنامج العمل السنوي والتذكيرات",
     "محطات المقرر الوزاري تصل مع تحديث البرنامج؛ أضف إليها محطات مؤسستك.",
     ["راجع التذكيرات في لوحة القيادة كل صباح.",
      "علّم المحطة «منجزة» بعد إنجازها حتى لا تبقى في التذكيرات.",
      "ولّد برنامج العمل السنوي بصيغة Word."],
     "برنامج العمل", "اذهب إلى برنامج العمل",
     "SELECT COUNT(*) FROM station_locale", "{n} محطة خاصة بالمؤسسة"),
    ("الحياة المدرسية والتعلمات الأساس",
     "الأندية والأنشطة الموازية، ونتائج الروائز (القبلي والبعدي).",
     ["سجّل الأندية ومنخرطيها: نسبة المشاركين تظهر في لوحة القيادة.",
      "استورد نتائج الروائز لتتبع تطور التحكم في التعلمات الأساس."],
     "الأندية والأنشطة", "اذهب إلى الحياة المدرسية",
     "SELECT COUNT(*) FROM club", "{n} نادياً"),
    ("التقييم والمحاضر والامتحان",
     "النتائج من مسار، ومجالس الأقسام، ومحاضر نهاية الأسدوس، والامتحان الموحد المحلي.",
     ["استورد «مجمل المعدلات» من مسار بعد مسك النقط.",
      "حرّر محاضر مجالس الأقسام ونهاية الأسدوس وولّدها.",
      "نظّم الامتحان: القاعات والمترشحون والمراقبون والوثائق."],
     "محاضر نهاية الأسدوس", "اذهب إلى المحاضر",
     "SELECT COUNT(*) FROM resultat", "{n} نتيجة مستوردة"),
    ("الوثائق والمراسلات",
     "وثائق التلاميذ (الشهادة المدرسية، شهادة العطلة...) وسجل الصادر.",
     ["ابحث عن التلميذ بالرمز أو الاسم، ثم اختر الوثيقة من بطاقته.",
      "كل وثيقة مولَّدة تُحفظ في الأرشيف مع رقمها."],
     "التلاميذ", "اذهب إلى وثائق التلاميذ",
     "SELECT COUNT(*) FROM document_genere", "{n} وثيقة مولَّدة"),
    ("التدبير المالي",
     "جمعية دعم مدرسة النجاح: المداخيل والمصاريف والرصيد، وسندات الطلب والاتفاقيات.",
     ["افتح السنة المالية بالمبلغ المنقول.",
      "سجّل العمليات؛ الرصيد البنكي يُحسب آلياً."],
     "جمعية دعم مدرسة النجاح", "اذهب إلى جمعية النجاح",
     "SELECT COUNT(*) FROM operation_financiere", "{n} عملية مالية"),
    ("حماية المعطيات",
     "معطيات المؤسسة لا تغادر حاسوبك. البرنامج يأخذ نسخة احتياطية يومية عند الإغلاق.",
     ["انسخ المعطيات إلى قرص خارجي من أسفل الشريط الجانبي بانتظام.",
      "التصفير (في الإعدادات) يحذف كل شيء بعد أخذ نسخة كاملة."],
     "إعداد المؤسسة", "اذهب إلى الإعدادات", None, ""),
]


# الجولة المصورة (طلب المدير 2026-11-07): لقطات من البرنامج نفسه ببيانات وهمية (لقطات الاختبار الآلي)،
# محفوظة في resources/guide. (العنوان، الصورة، الشرح، النقط، الصفحة)
DOSSIER_IMAGES = Path(__file__).resolve().parent.parent / "resources" / "guide"
TOUR = [
    ("الإعداد الأول", "assistant",
     "عند أول تشغيل يفتح معالج من أربع خطوات: المؤسسة، المدير، الهوية البصرية، ومجلد البيانات والسنة الدراسية.",
     ["الخانات المعلَّمة بنجمة إجبارية؛ الباقي يُكمل لاحقاً من الإعدادات.",
      "نوع المؤسسة (مستقلة أو مجموعة مدرسية) يحدد ظهور كل ما يخص الوحدات المدرسية.",
      "مجلد البيانات يحفظ القاعدة والوثائق المولَّدة والنسخ الاحتياطية على حاسوبك."], "إعداد المؤسسة"),
    ("الشريط الجانبي والبحث", "recherche",
     "الأقسام الرئيسية في الشريط الجانبي؛ الضغط على قسم يُظهر فروعه، والبحث يجد الصفحة بكلمة واحدة.",
     ["اكتب كلمة مثل «محضر» أو «رخصة» ثم Entrée لفتح أول نتيجة.",
      "الرقم بجانب القسم عدد صفحاته."], None),
    ("لوحة القيادة", "tableau",
     "أول ما يظهر عند فتح البرنامج: الأعداد الأساسية والتذكيرات والمؤشرات.",
     ["التذكيرات تأتي من برنامج العمل السنوي (محطات المقرر الوزاري ومحطاتك).",
      "مؤشرات الأنشطة والتعلمات الأساس والغياب تُحسب مما تدخله في الصفحات الأخرى."], "لوحة القيادة"),
    ("الاستيراد من مسار", "import",
     "لوائح الأقسام المصدَّرة من مسار (العربية والفرنسية) تُستورد في بداية السنة وكلما تغيرت.",
     ["البرنامج يطابق التلاميذ برمز مسار ولا يكرر أحداً.",
      "تقرير الاستيراد يبين الجدد والوافدين والمغادرين المحتملين قبل التأكيد."], "الاستيراد من مسار"),
    ("وثائق التلاميذ", "eleve",
     "ابحث عن التلميذ بالرمز أو الاسم، ثم ولّد وثائقه من بطاقته.",
     ["الشهادة المدرسية وشهادة العطلة وغيرها بترويسة المؤسسة.",
      "كل وثيقة تُحفظ في الأرشيف برقمها."], "التلاميذ"),
    ("الموارد البشرية والرخص", "personnel",
     "ملف كل موظف يدوياً أو من ملف XML، ثم الأقسام المسندة والساعات؛ والرخص بوثائقها.",
     ["المعلومات المدخلة يدوياً (الوحدة، الساعات) لا تُمحى عند إعادة استيراد XML.",
      "الرخصة تولّد الطلب والإشعار ومحضر الاستئناف."], "الموارد البشرية"),
    ("التنظيم التربوي", "tanzim",
     "البنية التربوية وتوزيع الأقسام على الأساتذة، والوثيقة جاهزة للطباعة.",
     ["الخانات الناقصة تظهر تنبيهاً بجانب زر الحفظ دون أن تمنعه."], "التنظيم التربوي"),
    ("الدعم التربوي", "soutien",
     "مراحل الدعم وفئات التعثر، مجموعات يؤطرها أساتذة متدخلون، ونتائج التلاميذ قبل الدعم وبعده.",
     ["أنشئ المرحلة، ثم المجموعة (الفئة، الأستاذ، المادة)، ثم أشّر على تلاميذها من كل قسم.",
      "أضف الحصص: البرنامج يمنع تداخل حصتين لنفس الأستاذ.",
      "سجل الدعم لكل أستاذ، برنامج المرحلة، وتقريرها بمقارنة قبل/بعد."], "الدعم التربوي"),
    ("التعلمات الأساس", "tarl",
     "نتائج رائز الموضعة القبلي والبعدي، وتطور نسبة من بلغوا المستوى المتوقع.", [], "التعلمات الأساس"),
    ("تتبع الغياب", "absences",
     "كل شهر: أيام الدراسة الفعلية، وأيام غياب كل قسم؛ تُحسب النسب للأقسام والوحدات والمؤسسة.",
     ["نصف يوم = 0.5.", "التقرير الشهري (Word) يتضمن مبيان التطور عبر الأشهر."], "تتبع الغياب"),
    ("الإحصائيات", "statistiques",
     "تحليل التلاميذ (الحركية والجنس)، البطاقة الإحصائية لكل مستوى، وتطور التعلمات الأساس.", [],
     "الإحصائيات"),
    ("التسجيلات", "inscriptions",
     "لائحة التلاميذ حسب المستوى بخانات التأمين والجمعية الرياضية والتعاون المدرسي، مع عدّاد تراكمي.",
     ["مبلغ التأمين حسب وسط المؤسسة (حضري أو قروي) المحدد في الإعدادات."], "التسجيلات"),
    ("جمعية دعم مدرسة النجاح", "association",
     "المداخيل والمصاريف والرصيد، ووثائق كل عملية، والصرف بسند الطلب أو الاتفاقية.", [],
     "جمعية دعم مدرسة النجاح"),
    ("التقييم والمحاضر", "deliberations",
     "مجالس الأقسام ومحاضر نهاية الأسدوس من نتائج مسار، والامتحان الموحد المحلي.", [], "محاضر نهاية الأسدوس"),
]


def image_guide(nom: str) -> Path | None:
    for ext in (".jpg", ".png"):
        p = DOSSIER_IMAGES / f"{nom}{ext}"
        if p.is_file():
            return p
    return None


class PageGuide(QWidget):
    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        racine, self.message = _page("كيفية استخدام البرنامج",
                                     "مراحل العمل بالترتيب. اضغط «اذهب إلى» داخل كل مرحلة للانتقال إلى صفحتها.")
        self.setLayout(racine)
        # البطاقة الرئيسية بلون الشريط الجانبي
        haut = QFrame()
        haut.setObjectName("etape")
        hv = QVBoxLayout(haut)
        hv.setContentsMargins(28, 24, 28, 24)
        hv.setSpacing(14)
        t = QLabel("دليل المراحل الكامل")
        t.setObjectName("etapeTitre")
        hv.addWidget(t)
        d = QLabel("من ضبط الإعدادات، إلى استيراد اللوائح والموارد البشرية، فبرنامج العمل السنوي، فالتقييم "
                   "والمحاضر، فالوثائق والتدبير المالي.")
        d.setObjectName("etapeTexte")
        d.setWordWrap(True)
        hv.addWidget(d)
        g = QGridLayout()
        g.setSpacing(12)
        for i, (titre, texte) in enumerate((("اضبط الإعدادات", "معلومات المؤسسة والشعار لتظهر في كل الوثائق."),
                                            ("استورد اللوائح", "التلاميذ من مسار، والأطر من ملف XML."),
                                            ("تابع السنة", "برنامج العمل والتذكيرات والحياة المدرسية."),
                                            ("قيّم وولّد", "المحاضر والامتحان والوثائق بضغطة زر.")), start=1):
            g.addWidget(self._mini(i, titre, texte), (i - 1) // 2, (i - 1) % 2)
        hv.addLayout(g)
        racine.addWidget(haut)

        self.etats: list[QLabel] = []
        self.boutons: list[QPushButton] = []
        for n, (titre, desc, pas, page, lib_b, _, _) in enumerate(ETAPES, start=1):
            c, v = carte()
            h = QHBoxLayout()
            tt = QLabel(titre)
            tt.setObjectName("titreCarte")
            p = QLabel(f"المرحلة {n}")
            p.setObjectName("pastille")
            h.addWidget(tt)
            h.addStretch()
            h.addWidget(p)
            v.addLayout(h)
            l = QLabel(desc)
            l.setWordWrap(True)
            v.addWidget(l)
            for x in pas:
                b = QLabel(f"•  {x}")
                b.setWordWrap(True)
                b.setObjectName("etiquette")
                v.addWidget(b)
            hb = QHBoxLayout()
            etat = QLabel()
            self.etats.append(etat)
            bouton = QPushButton(lib_b)
            bouton.setCursor(Qt.PointingHandCursor)
            bouton.clicked.connect(lambda _=False, pg=page: self.f.aller_a(pg))
            self.boutons.append(bouton)
            hb.addWidget(etat, 1)
            hb.addWidget(bouton)
            v.addLayout(hb)
            racine.addWidget(c)
        self._tour(racine)
        racine.addStretch()
        self.rafraichir()

    def _tour(self, racine) -> None:
        """الجولة المصورة: لكل قسم لقطة من البرنامج وشرح مختصر."""
        t = QLabel("جولة مصورة في أقسام البرنامج")
        t.setObjectName("titreCarte")
        racine.addWidget(t)
        n = QLabel("اللقطات مأخوذة من البرنامج نفسه ببيانات وهمية.")
        n.setObjectName("etiquette")
        racine.addWidget(n)
        self.images: list[QLabel] = []
        for titre, img, texte, points, page in TOUR:
            c, v = carte(titre)
            l = QLabel(texte)
            l.setWordWrap(True)
            v.addWidget(l)
            for x in points:
                b = QLabel(f"•  {x}")
                b.setWordWrap(True)
                b.setObjectName("etiquette")
                v.addWidget(b)
            chemin = image_guide(img)
            if chemin:
                im = QLabel()
                pm = QPixmap(str(chemin))
                if not pm.isNull():
                    im.setPixmap(pm.scaledToWidth(min(760, pm.width()), Qt.SmoothTransformation))
                    im.setAlignment(Qt.AlignCenter)
                    im.setStyleSheet("border: 1px solid rgba(0,0,0,0.12); border-radius: 8px;")
                    v.addWidget(im)
                    self.images.append(im)
            if page:
                hb = QHBoxLayout()
                hb.addStretch()
                b = QPushButton(f"افتح «{page}»")
                b.setCursor(Qt.PointingHandCursor)
                b.clicked.connect(lambda _=False, pg=page: self.f.aller_a(pg))
                hb.addWidget(b)
                v.addLayout(hb)
            racine.addWidget(c)

    def _mini(self, n: int, titre: str, texte: str) -> QFrame:
        f = QFrame()
        f.setStyleSheet("QFrame { background: rgba(255,255,255,0.10); border: 1px solid rgba(255,255,255,0.30);"
                        " border-radius: 12px; }")
        v = QVBoxLayout(f)
        v.setContentsMargins(16, 12, 16, 12)
        h = QHBoxLayout()
        num = QLabel(str(n))
        num.setObjectName("numero")
        num.setFixedSize(26, 26)
        num.setAlignment(Qt.AlignCenter)
        t = QLabel(titre)
        t.setObjectName("etapeTitre")
        t.setStyleSheet("font-size: 11.5pt; border: 0; background: transparent;")
        h.addWidget(num)
        h.addWidget(t, 1)
        v.addLayout(h)
        x = QLabel(texte)
        x.setObjectName("etapeTexte")
        x.setStyleSheet("border: 0; background: transparent;")
        x.setWordWrap(True)
        v.addWidget(x)
        return f

    def avancement(self) -> list[tuple[bool, str]]:
        res = []
        for (_, _, _, _, _, sql, modele) in ETAPES:
            if not sql:
                res.append((True, ""))
                continue
            try:
                n = self.f.conn.execute(sql).fetchone()[0]
            except Exception:  # noqa: BLE001 — جدول غير موجود في قاعدة قديمة
                n = 0
            res.append((bool(n), modele.format(n=n) if n else "لم تُبدأ بعد"))
        return res

    def rafraichir(self) -> None:
        for l, (fait, txt) in zip(self.etats, self.avancement()):
            l.setText(("✓ " if fait else "○ ") + txt if txt else "")
            l.setObjectName("ok" if fait else "etiquette")
            l.style().unpolish(l)
            l.style().polish(l)
