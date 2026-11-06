"""دليل «كيفية استخدام البرنامج»: مراحل العمل بالترتيب، مع زر «اذهب إلى» وحالة إنجاز كل مرحلة
(اقتراح المدير 2026-11-06، مستوحى من دليل المراحل في تطبيقات أخرى)."""

from __future__ import annotations

from PySide6.QtCore import Qt
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
        racine.addStretch()
        self.rafraichir()

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
