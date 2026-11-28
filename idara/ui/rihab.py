"""واجهة «الرحاب» (طلب المدير 2026-11-14: تغيير المظهر الكلاسيكي بلمسة خاصة بنا).

- الرحبة: لكل قسم رئيسي صفحة استقبال، رأسها بلون القسم وزليجه، وتحتها بطاقة لكل صفحة فيه.
- شريط المسار: فوق كل صفحة، اسم القسم ثم صفحاته حبوباً يُنتقل بينها بنقرة.
- بطاقة الفعل: بطاقة تُنقر (صفحة تُفتح أو وثيقة تُولَّد) بدل زر في صف أزرار.

الأفكار فقط من المقارنة مع برامج أخرى؛ الرسم والتخطيط والألوان من هوية «رحاب».
"""

from __future__ import annotations

import sqlite3

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QButtonGroup, QFrame, QGridLayout, QHBoxLayout, QLabel, QLayout, QPushButton,
                               QScrollArea, QSizePolicy, QVBoxLayout, QWidget)

from idara.ui import icones, theme
from idara.ui.zellige import dessiner_etoile

# سطر تعريفي لكل صفحة (يظهر في بطاقتها داخل الرحبة)
DESCRIPTIONS = {
    "لوحة القيادة": "مؤشرات المؤسسة اليوم وما ينتظر التدخل.",
    "مفكرة المدير": "سبورة التذكيرات، ساعة ويومية تُبرز المواعيد والمحطات.",
    "شاشة العرض": "عرض عصري للمؤسسة بأرقامها ونتائجها على تلفاز أمام الزوار، أو تصديره PDF وصوراً.",
    "روابط مهمة": "منصات مسار ومسير وتبليغ وأوسايز، تُفتح في المتصفح بنقرة واحدة.",
    "التواصل": "واتساب (رسالة صوتية) أو البريد الإلكتروني لصاحب البرنامج.",
    "الإحصائيات": "أعداد التلاميذ والأطر حسب المستوى والجنس والوحدة.",
    "برنامج العمل": "محطات السنة والعطل والتذكيرات.",
    "أداء المؤسسة": "نتائج كل أسدوس ومقارنتها.",
    "تتبع الغياب": "نسب حضور التلاميذ شهراً بشهر وقسماً بقسم.",
    "مجالس المؤسسة": "تركيبة المجالس واجتماعاتها ومحاضرها.",
    "السبورة المرجعية": "لوحات المكتب: بطاقة المؤسسة، البنية، المجالس، استعمال الزمن.",
    "التلاميذ": "البحث عن تلميذ ووثائقه: الشهادات والبطاقات.",
    "حركية التلاميذ": "الوافدون والمغادرون وملفاتهم المدرسية.",
    "تتبع السلوك": "ملاحظات السلوك واستدعاء أولياء الأمور.",
    "أولياء الأمور": "معلومات الأولياء ورسائل واتساب الجاهزة.",
    "النقل المدرسي": "الحافلات والمسارات والمستفيدون.",
    "الصحة والسلامة": "الحوادث المدرسية ووضعية ملفاتها، والفحوصات الطبية للتلاميذ.",
    "التلاميذ القدامى": "تلاميذ ما قبل مسار وشواهدهم.",
    "الاستيراد من مسار": "استيراد لوائح الأقسام من منظومة مسار.",
    "الموارد البشرية": "بطاقات الأطر ومعطياتهم الإدارية.",
    "تدبير الفائض": "ترتيب الأساتذة وتحديد الفائض والخصاص.",
    "الرخص": "ملف الرخصة كاملاً: الطلب، الوصل، التعويض، الاستئناف.",
    "محاضر الموارد البشرية": "محاضر الالتحاق والدخول والخروج.",
    "طلبات الموظفين": "الإذن بالتغيب، رخصة الأبوة والزواج، الفحص المضاد، الورقة الشخصية.",
    "ملفات الأساتذة": "طلب الملف الإداري والتربوي لأستاذ أو إرساله، برقم الصادر.",
    "الأعوان": "أعوان الحراسة والنظافة والإطعام وتقييم خدمتهم.",
    "التنظيم التربوي": "البنية التربوية وإسناد الأقسام.",
    "التعلمات الأساس": "تتبع مستويات القراءة والحساب.",
    "بطاقة التلميذ": "مسار كل تلميذ من الرائز القبلي إلى البعدي والمراحل، بمبيانات.",
    "الدعم التربوي": "مجموعات الدعم وحصصها وسجلها.",
    "الريادة": "ISA2 حسب المراحل، مراسلة الأساتذة، ملف الشارة والتقرير التركيبي.",
    "نتائج الريادة": "النسب حسب الفترات والأقسام، والتقرير التركيبي حول النتائج.",
    "تواصل الريادة": "الأيام التواصلية والأبواب المفتوحة: الاستدعاءات والتقارير.",
    "مؤشرات الريادة": "التعلمات الأساس، تطور ISA2، الأنشطة الموازية، والهدر.",
    "استعمالات الزمن": "حصص كل أستاذ ومراقبة الحصيص الأسبوعي.",
    "جدول الحراسة": "المناطق والأساتذة المكلفون بها، وحراسة اليوم والمذكرة الداخلية.",
    "الأندية والأنشطة": "الأندية التربوية وبرنامج الأنشطة وحصيلته.",
    "خليتا اليقظة والإنصات": "التركيبة، الاجتماعات، والحالات المرصودة.",
    "التحفيز والتشجيع": "معرض الشواهد التقديرية المزخرفة وسجل التحفيز.",
    "الانفتاح والشراكة": "اتفاقيات الشراكة والتزامات كل طرف.",
    "الإعلام والتواصل": "إعلانات مزخرفة بعشرة قوالب، واستدعاءات أولياء الأمور.",
    "التسجيلات": "واجبات التسجيل والتأمين ووصولاتها.",
    "الجرد": "سجل الجرد حسب نوع التجهيز.",
    "جمعية دعم مدرسة النجاح": "المداخيل والمصاريف والميزانية والتقارير، والصرف: سند الطلب والاتفاقية.",
    "الجمعية الرياضية": "الانخراطات وتحويل الحصص، والمداخيل والمصاريف.",
    "الترقية في الرتبة": "المعنيون بالرتبة الموالية حسب السنة، وأنساق الترقي.",
    "الترقية بالاختيار": "المستوفون لشروط الدرجة الأولى والممتازة بالاختيار.",
    "الترقية بالامتحان المهني": "المعنيون بامتحان الكفاءة المهنية وبطاقات النقطة المهنية.",
    "جمعية تنمية التعاون المدرسي": "الاشتراكات وتحويل الحصص، ومجالات الصرف.",
    "البنية المادية": "الحجرات والمرافق لكل وحدة مدرسية.",
    "السكنيات": "السكنيات الإدارية والوظيفية: التباري ونقط المترشحين ومطبوعات المذكرة 40.",
    "الوثائق القانونية للجمعيات": "تجديد المكاتب ومحاضر الجموع العامة.",
    "المراقبة المستمرة": "تتبع فروض المراقبة المستمرة.",
    "الامتحان": "الامتحان الموحد: القاعات والحراسة والمحاضر.",
    "استثمار النتائج": "تحليل النتائج وتحديد حاجيات الدعم.",
    "مجالس الأقسام": "محاضر مجالس الأقسام وقراراتها.",
    "مشروع المؤسسة": "المؤشرات والعمليات وتتبع الإنجاز.",
    "فريق القيادة": "أعضاء فريق القيادة ومحضرا التشكيل والمصادقة.",
    "تسليم المهام": "محضر تسليم المهام بين المديرَين.",
    "سجل الصادر": "ترقيم المراسلات الصادرة.",
    "إعداد المؤسسة": "معطيات المؤسسة والمدير والمظهر.",
    "الوثائق": "نماذج الوثائق وتخصيصها.",
    "دليل الاستخدام": "جولة مصورة وخطوات البداية.",
}

# أيقونة معبرة لبعض الصفحات (طلب المدير 2026-11-19: تدبير السكنيات «مع الأيقونة المناسبة»)
ICONES_PAGES = {"السكنيات": "maison", "روابط مهمة": "ouvrir", "شاشة العرض": "apercu"}

SOUS_SECTIONS = {
    "القيادة والتدبير": "نظرة شاملة على المؤسسة: المؤشرات، البرنامج السنوي، المجالس، والسبورة المرجعية.",
    "التلاميذ": "كل ما يخص التلميذ: وثائقه، حركيته، سلوكه، وليّه، نقله، وسلامته.",
    "الموارد البشرية": "الأطر والأعوان: المعطيات، الرخص، الطلبات، والمحاضر.",
    "التدبير التربوي": "تنظيم الدراسة والدعم واستعمالات الزمن.",
    "المدرسة الرائدة": "تتبع النتائج والتعلمات الأساس، التواصل مع الأسر، المؤشرات العامة، وشارة الريادة.",
    "الحياة المدرسية": "الأندية، الخلايا، التحفيز، الشراكات، والتواصل.",
    "التدبير المالي والمادي": "مالية الجمعيات، الصرف، الجرد، والبنية المادية.",
    "التقييم": "المراقبة المستمرة، الامتحان، ومحاضر المجالس.",
    "مشروع المؤسسة": "مشروع المؤسسة المندمج: الفريق، العمليات، والتتبع.",
    "المراسلات": "سجل الصادر وترقيم المراسلات.",
    "الإعدادات": "إعداد المؤسسة والوثائق ودليل الاستخدام.",
}


def couleur_section(section: str) -> str:
    return icones.COULEURS.get(section, theme.VERT)


class Glyphe(QWidget):
    """مربع مستدير بلون خافت، داخله نجمة زليج (صفحة) أو ورقة (وثيقة)."""

    def __init__(self, couleur: str, forme: str = "etoile", taille: int = 44):
        super().__init__()
        self.couleur, self.forme = couleur, forme
        self.setFixedSize(QSize(taille, taille))
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        n = self.width()
        c = QColor(self.couleur)
        fond = QColor(c)
        fond.setAlpha(34)
        p.setPen(Qt.NoPen)
        p.setBrush(fond)
        p.drawRoundedRect(QRectF(0, 0, n, n), n * 0.28, n * 0.28)
        if self.forme == "etoile":
            dessiner_etoile(p, n / 2, n / 2, n * 0.27, self.couleur, pleine=True, trou=True)
        else:   # ورقة مطوية الزاوية بثلاثة أسطر
            x, y, w, h, k = n * 0.30, n * 0.22, n * 0.40, n * 0.56, n * 0.13
            ch = QPainterPath()
            ch.moveTo(x, y)
            ch.lineTo(x + w - k, y)
            ch.lineTo(x + w, y + k)
            ch.lineTo(x + w, y + h)
            ch.lineTo(x, y + h)
            ch.closeSubpath()
            p.setBrush(c)
            p.drawPath(ch)
            p.setPen(QPen(QColor("#FFFFFF"), max(1.4, n * 0.04)))
            for i in range(3):
                yy = y + h * (0.42 + 0.18 * i)
                p.drawLine(QPointF(x + w * 0.2, yy), QPointF(x + w * 0.8, yy))
        p.end()


class CarteAction(QFrame):
    """بطاقة تُنقر: عنوان، سطر تعريفي، وشارة اختيارية. تعمل أيضاً بلوحة المفاتيح (Entrée أو المسافة)."""

    clique = Signal()

    def __init__(self, titre: str, description: str = "", couleur: str | None = None, pastille: str = "",
                 forme: str = "etoile"):
        super().__init__()
        couleur = couleur or theme.VERT
        self.setObjectName("carteAction")
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAttribute(Qt.WA_Hover, True)
        self.setMinimumHeight(86)
        self.setStyleSheet(f"QFrame#carteAction {{ border-right: 5px solid {couleur}; }}")
        h = QHBoxLayout(self)
        h.setContentsMargins(16, 12, 14, 12)
        h.setSpacing(14)
        if forme.startswith("picto:"):   # أيقونة معبرة لصفحة بعينها (السكنيات: بيت)
            from idara.ui import pictos
            ic = QLabel()
            ic.setPixmap(pictos.pastille(forme[6:], couleur, 44))
            ic.setFixedSize(44, 44)
            ic.setAttribute(Qt.WA_TransparentForMouseEvents)
            h.addWidget(ic, 0, Qt.AlignTop)
        else:
            h.addWidget(Glyphe(couleur, forme), 0, Qt.AlignTop)
        v = QVBoxLayout()
        v.setSpacing(2)
        self.l_titre = QLabel(titre)
        self.l_titre.setObjectName("carteActionTitre")
        self.l_titre.setWordWrap(True)
        v.addWidget(self.l_titre)
        self.l_desc = QLabel(description, self)
        self.l_desc.setObjectName("etiquette")
        self.l_desc.setWordWrap(True)
        v.addWidget(self.l_desc)
        self.l_desc.setVisible(bool(description))
        self.l_pastille = QLabel()
        self.l_pastille.setObjectName("pastille")
        v.addWidget(self.l_pastille, 0, Qt.AlignRight | Qt.AlignAbsolute)
        v.addStretch()
        h.addLayout(v, 1)
        for w in (self.l_titre, self.l_desc, self.l_pastille):
            w.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.pastille(pastille)

    def titre(self) -> str:
        return self.l_titre.text()

    def pastille(self, texte: str) -> None:
        self.l_pastille.setText(texte)
        self.l_pastille.setVisible(bool(texte))

    def cliquer(self) -> None:
        self.clique.emit()

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.LeftButton and self.rect().contains(ev.position().toPoint()):
            self.clique.emit()
        super().mouseReleaseEvent(ev)

    def keyPressEvent(self, ev):
        if ev.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.clique.emit()
        else:
            super().keyPressEvent(ev)


class Galerie(QWidget):
    """شبكة بطاقات بعدد أعمدة ثابت."""

    def __init__(self, colonnes: int = 3):
        super().__init__()
        self.colonnes = colonnes
        self.cartes: list[CarteAction] = []
        self.g = QGridLayout(self)
        self.g.setContentsMargins(0, 0, 0, 0)
        self.g.setHorizontalSpacing(14)
        self.g.setVerticalSpacing(14)
        for j in range(colonnes):
            self.g.setColumnStretch(j, 1)

    def ajouter(self, c: CarteAction) -> CarteAction:
        i = len(self.cartes)
        self.g.addWidget(c, i // self.colonnes, i % self.colonnes)
        self.cartes.append(c)
        return c


class Hero(QFrame):
    """رأس الرحبة: تدرّج بلون القسم، زليج خافت، أيقونة القسم، عنوانه، وسطر تعريفي."""

    def __init__(self, section: str, sous: str, puce: str = ""):
        super().__init__()
        self.couleur = couleur_section(section)
        self.setMinimumHeight(128)
        h = QHBoxLayout(self)
        h.setContentsMargins(28, 20, 28, 20)
        h.setSpacing(18)
        ic = QLabel()
        ic.setPixmap(icones.tuile(section, 60, sombre=True))
        ic.setFixedSize(QSize(60, 60))
        ic.setStyleSheet("background: transparent;")
        h.addWidget(ic, 0, Qt.AlignVCenter)
        v = QVBoxLayout()
        v.setSpacing(2)
        t = QLabel(section)
        t.setObjectName("heroTitre")
        s = QLabel(sous)
        s.setObjectName("heroSous")
        s.setWordWrap(True)
        v.addStretch()
        v.addWidget(t)
        v.addWidget(s)
        v.addStretch()
        h.addLayout(v, 1)
        self.l_puce = QLabel(puce, self)
        self.l_puce.setObjectName("heroPuce")
        h.addWidget(self.l_puce, 0, Qt.AlignTop)
        self.l_puce.setVisible(bool(puce))

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if theme.LUXE:   # الليلي والذهبي (2026-11-20)
            from idara.ui.zellige import peindre_luxe
            peindre_luxe(p, QRectF(self.rect()).adjusted(1, 1, -1, -1), 22)
            p.end()
            return
        c = QColor(self.couleur)
        g = QLinearGradient(self.width(), 0, 0, self.height())
        g.setColorAt(0, c.darker(165))
        g.setColorAt(1, c.darker(118))
        ch = QPainterPath()
        ch.addRoundedRect(QRectF(self.rect()), 20, 20)
        p.fillPath(ch, g)
        p.setClipPath(ch)
        p.setOpacity(0.13)
        # الزليج في الجهة اليسرى فقط حتى يبقى النص مقروءاً
        for k, y in enumerate(range(-10, self.height() + 60, 46)):
            for x in range(18 + (23 if k % 2 else 0), int(self.width() * 0.42), 46):
                dessiner_etoile(p, x, y, 13, "#FFFFFF", pleine=False)
        p.setOpacity(1)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(theme.MENTHE))
        p.drawRect(QRectF(0, self.height() - 5, self.width(), 5))   # خط الليمون أسفل الرأس
        p.end()


def _compter(conn, sql: str, args=()) -> int | None:
    try:
        return conn.execute(sql, args).fetchone()[0]
    except sqlite3.Error:
        return None


def compteur(fenetre, page: str) -> str:
    """رقم حي صغير يظهر على بطاقة الصفحة (فارغ إن لم يكن لها عدّاد)."""
    from idara.services import annee as annee_srv
    from idara.services import registres as rg
    conn = fenetre.conn
    reg = getattr(fenetre, "cles_pages", {}).get(page)
    if reg:
        n = sum(rg.compter(conn, k) for k in reg)
        return f"{n} سجلاً" if n else ""
    a = annee_srv.annee_courante(conn)
    aid = a["id"] if a else -1
    n, unite = {
        "التلاميذ": (_compter(conn, "SELECT COUNT(*) FROM inscription WHERE annee_id=? AND statut IN "
                                    "('inscrit','arrive')", (aid,)), "تلميذاً"),
        "الموارد البشرية": (_compter(conn, "SELECT COUNT(*) FROM personnel WHERE statut='actif'"), "إطاراً"),
        "الجرد": (_compter(conn, "SELECT COUNT(*) FROM inventaire"), "سطراً"),
        "أولياء الأمور": (_compter(conn, "SELECT COUNT(DISTINCT eleve_id) FROM tuteur"), "تلميذاً بوليّه"),
        "الأندية والأنشطة": (_compter(conn, "SELECT COUNT(*) FROM club WHERE annee_id=?", (aid,)), "نادياً"),
    }.get(page, (None, ""))
    return f"{n} {unite}" if n else ""


class PageRahba(QWidget):
    """رحبة قسم: رأس ملوّن ثم بطاقة لكل صفحة من صفحاته."""

    def __init__(self, fenetre, indice: int, section: str, fils: list[tuple[str, str]], raccourci: str = ""):
        super().__init__()
        self.f, self.indice, self.section, self.fils = fenetre, indice, section, fils
        racine = QVBoxLayout(self)
        racine.setContentsMargins(40, 28, 40, 32)
        racine.setSpacing(20)
        puce = f"{len(fils)} صفحات" + (f"  ·  ⁦{raccourci}⁩" if raccourci else "")
        self.hero = Hero(section, SOUS_SECTIONS.get(section, ""), puce)
        racine.addWidget(self.hero)
        self.galerie = Galerie(3)
        c = couleur_section(section)
        self.cartes: dict[str, CarteAction] = {}
        for page, lib in fils:
            k = CarteAction(lib, DESCRIPTIONS.get(page, ""), c,
                            forme=f"picto:{ICONES_PAGES[page]}" if page in ICONES_PAGES else "etoile")
            k.clique.connect(lambda page=page: self.f.aller_a(page))
            self.cartes[page] = self.galerie.ajouter(k)
        racine.addWidget(self.galerie)
        racine.addStretch()

    def rafraichir(self) -> None:
        for page, k in self.cartes.items():
            k.pastille("قريباً" if page not in self.f.pages else compteur(self.f, page))


# أيقونة كل صفحة في حبوب المسار (طلب المدير 2026-11-20: مظهر جذاب ومبتكر بدل الحبوب البسيطة)
_MOTS_PICTOS = (("روابط", "ouvrir"), ("مفكرة", "calendrier"), ("برنامج العمل", "calendrier"), ("الزمن", "calendrier"),
                ("الحراسة", "calendrier"), ("الرخص", "calendrier"), ("لوحة القيادة", "statistiques"),
                ("إحصائيات", "statistiques"), ("الإحصائيات", "statistiques"), ("أداء", "statistiques"),
                ("نتائج", "statistiques"), ("مؤشرات", "statistiques"), ("استثمار", "statistiques"),
                ("الغياب", "absent"), ("حركية", "repartir"), ("الفائض", "repartir"), ("التنظيم", "repartir"),
                ("السلوك", "rappel"), ("الإعلام", "rappel"), ("التحفيز", "valider"), ("الامتحان", "valider"),
                ("المراقبة", "valider"), ("الاستيراد", "importer"), ("الصادر", "envoyer"), ("المراسلات", "envoyer"),
                ("الجرد", "maison"), ("البنية", "maison"), ("السكنيات", "maison"), ("جمعية", "personnes"),
                ("الجمعية", "personnes"), ("مجالس", "personnes"), ("أولياء", "personnes"), ("الأطر", "personnes"),
                ("الأعوان", "personnes"), ("فريق", "personnes"), ("التلاميذ", "personnes"), ("الأندية", "personnes"),
                ("خليتا", "personnes"), ("الشراكة", "personnes"), ("التسجيلات", "modifier"), ("بطاقة", "apercu"),
                ("الملفات", "ouvrir"), ("ملفات", "ouvrir"), ("الإعداد", "modifier"), ("دليل", "apercu"),
                ("التواصل", "envoyer"), ("السبورة", "apercu"))


def picto_page(page: str, lib: str = "") -> str:
    if page in ICONES_PAGES:
        return ICONES_PAGES[page]
    t = f"{page} {lib}"
    return next((n for mot, n in _MOTS_PICTOS if mot in t), "document")


class FluxLayout(QLayout):
    """تخطيط ينساب من اليمين إلى اليسار ويلتف إلى سطر جديد عند امتلاء العرض."""

    def __init__(self, parent=None, h_espace: int = 8, v_espace: int = 6):
        super().__init__(parent)
        self._items = []
        self.h, self.v = h_espace, v_espace
        self.setContentsMargins(0, 2, 0, 2)

    def addItem(self, item):   # noqa: N802
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, i):   # noqa: N802
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i):   # noqa: N802
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def expandingDirections(self):   # noqa: N802
        return Qt.Orientations(0)

    def hasHeightForWidth(self):   # noqa: N802
        return True

    def heightForWidth(self, w):   # noqa: N802
        return self._placer(QRect(0, 0, w, 0), True)

    def setGeometry(self, r):   # noqa: N802
        super().setGeometry(r)
        self._placer(r, False)

    def sizeHint(self):   # noqa: N802
        return self.minimumSize()

    def minimumSize(self):   # noqa: N802
        s = QSize()
        for it in self._items:
            s = s.expandedTo(it.minimumSize())
        m = self.contentsMargins()
        return s + QSize(m.left() + m.right(), m.top() + m.bottom())

    def _placer(self, r, essai: bool) -> int:
        m = self.contentsMargins()
        zone = r.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        rtl = (self.parentWidget() is None or self.parentWidget().layoutDirection() == Qt.RightToLeft)
        x, y, haut = 0, zone.y(), 0
        for it in self._items:
            w = it.widget()
            if w is not None and w.isHidden():   # البطاقات المصفّاة لا تأخذ مكاناً
                continue
            t = it.sizeHint()
            if x and x + t.width() > zone.width():
                x, y, haut = 0, y + haut + self.v, 0
            if not essai:
                gx = zone.right() - x - t.width() + 1 if rtl else zone.x() + x
                it.setGeometry(QRect(QPoint(gx, y), t))
            x += t.width() + self.h
            haut = max(haut, t.height())
        return y + haut - r.y() + m.bottom()


class PiluleOrnee(QPushButton):
    """حبة مسار مزخرفة: كبسولة عاجية بخيط ذهبي، يمينها وسام نجمة زليج فيه أيقونة الصفحة؛ والحبة المفتوحة ليلية
    بعنوان ذهبي وإطار ذهبي مزدوج وسهم صغير نحو الصفحة. ترتفع قليلاً عند المرور."""

    def __init__(self, texte: str, picto: str, accent: str):
        super().__init__(texte)
        self.setObjectName("piluleOrnee")
        self.picto, self.accent = picto, accent
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)
        self.setFixedHeight(40)
        f = self.font()
        f.setPointSizeF(10)
        f.setBold(True)
        self.setFont(f)
        self.setMinimumWidth(self.fontMetrics().horizontalAdvance(texte) + 64)

    def sizeHint(self):
        return QSize(self.fontMetrics().horizontalAdvance(self.text()) + 64, 40)

    def paintEvent(self, ev):   # noqa: N802
        from idara.ui import pictos
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        actif, survol = self.isChecked(), self.underMouse()
        dore = QColor("#C9A04A")
        r = QRectF(self.rect()).adjusted(2, 3 if not survol or actif else 1, -2, -5 if not survol or actif else -7)
        rayon = r.height() / 2
        # ظل خفيف (أعمق عند المرور)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(11, 28, 44, 60 if survol or actif else 28))
        p.drawRoundedRect(r.translated(0, 2.5), rayon, rayon)
        ch = QPainterPath()
        ch.addRoundedRect(r, rayon, rayon)
        g = QLinearGradient(r.topRight(), r.bottomLeft())
        if actif:
            g.setColorAt(0, QColor(theme.HERO_FOND))
            g.setColorAt(1, QColor(theme.HERO_FOND2))
        else:
            g.setColorAt(0, QColor("#FFFFFF"))
            g.setColorAt(1, QColor("#FFF6E2" if survol else "#F8F2E4"))
        p.fillPath(ch, g)
        p.setPen(QPen(dore if (actif or survol) else QColor("#E0D2AE"), 1.4))
        p.setBrush(Qt.NoBrush)
        p.drawPath(ch)
        if actif:   # إطار ذهبي داخلي رفيع
            p.setPen(QPen(QColor(201, 160, 74, 150), 0.9))
            p.drawRoundedRect(r.adjusted(3, 3, -3, -3), rayon - 3, rayon - 3)
        # وسام النجمة يمين الحبة (بداية النص في العربية)
        cx, cy = r.right() - rayon + 1, r.center().y()
        a = rayon * 0.78
        p.save()
        p.translate(cx, cy)
        etoile = QPainterPath()
        import math
        for k in range(16):
            ang = math.pi / 8 * k - math.pi / 2
            rr = a if k % 2 == 0 else a * 0.78
            pt = QPointF(rr * math.cos(ang), rr * math.sin(ang))
            etoile.moveTo(pt) if k == 0 else etoile.lineTo(pt)
        etoile.closeSubpath()
        if actif:
            p.fillPath(etoile, dore)
        else:
            p.fillPath(etoile, QColor(self.accent).lighter(185) if not survol else dore)
            p.setPen(QPen(QColor(self.accent) if not survol else dore, 1.1))
            p.drawPath(etoile)
        p.restore()
        coul_ic = theme.HERO_FOND if actif or survol else self.accent
        ic = pictos.pixmap(self.picto, coul_ic, 14)
        p.drawPixmap(QRectF(cx - 8, cy - 8, 16, 16), ic, QRectF(ic.rect()))
        # النص
        p.setFont(self.font())
        p.setPen(QColor(theme.HERO_TEXTE2 if (actif and theme.LUXE) else "#FFFFFF") if actif
                 else QColor(theme.ENCRE))
        zone = QRectF(r.left() + 14, r.top(), r.width() - 2 * rayon - 14, r.height())
        p.drawText(zone, Qt.AlignCenter, self.text())
        if actif:   # سهم ذهبي صغير نحو الصفحة
            fl = QPainterPath()
            m = r.center().x()
            fl.moveTo(m - 6, r.bottom() + 0.5)
            fl.lineTo(m + 6, r.bottom() + 0.5)
            fl.lineTo(m, r.bottom() + 5.5)
            fl.closeSubpath()
            p.fillPath(fl, dore)
        p.end()


class BandeauPage(QFrame):
    """شريط المسار فوق الصفحات: القسم (يفتح رحبته) ثم صفحاته حبوباً."""

    def __init__(self, fenetre, sections):
        super().__init__()
        self.f, self.sections = fenetre, sections
        self.setObjectName("bandeauPage")
        self.setMinimumHeight(62)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self.indice: int | None = None
        h = QHBoxLayout(self)
        h.setContentsMargins(24, 8, 24, 8)
        h.setSpacing(10)
        self.b_rahba = QPushButton()
        self.b_rahba.setObjectName("puceRahba")
        self.b_rahba.setCursor(Qt.PointingHandCursor)
        self.b_rahba.setToolTip("كل صفحات هذا القسم")
        self.b_rahba.setIconSize(QSize(30, 30))
        self.b_rahba.clicked.connect(lambda: self.f.ouvrir_rahba(self.indice) if self.indice is not None else None)
        h.addWidget(self.b_rahba)
        self.fleche = QLabel("‹")
        self.fleche.setObjectName("etiquette")
        h.addWidget(self.fleche)
        # طلب المدير 2026-11-21: الحبوب تظهر كاملة — تلتف على سطر ثانٍ عند ضيق الشاشة بدل التمرير الأفقي
        self.zone = QWidget()
        self.zone.setObjectName("fondPilules")
        self.flux = FluxLayout(self.zone, 8, 6)
        self.zone.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        h.addWidget(self.zone, 1)
        self.pilules: dict[str, QPushButton] = {}
        self.groupe = QButtonGroup(self)

    def _construire(self, i: int) -> None:
        titre, fils = self.sections[i]
        c = couleur_section(titre)
        self.setStyleSheet(f"QFrame#bandeauPage {{ border-bottom: 3px solid {c}; }}")
        self.b_rahba.setText("  " + titre)
        self.b_rahba.setIcon(QIcon(icones.tuile(titre, 30, sombre=False)))
        while self.flux.count():
            it = self.flux.takeAt(0)
            if it.widget():
                it.widget().hide()   # يختفي فوراً (الحذف المؤجل قد يتأخر فتتراكب الحبوب القديمة والجديدة)
                it.widget().deleteLater()
        self.groupe = QButtonGroup(self.zone)
        self.groupe.setExclusive(False)
        self.pilules = {}
        for page, lib in fils:
            b = PiluleOrnee(lib, picto_page(page, lib), c)
            b.clicked.connect(lambda _=False, page=page: self.f.aller_a(page))
            self.groupe.addButton(b)
            self.pilules[page] = b
            self.flux.addWidget(b)
        self.zone.updateGeometry()
        self.fleche.setVisible(len(fils) > 1)
        self.zone.setVisible(len(fils) > 1)
        self.indice = i

    def afficher(self, i: int, page: str | None) -> None:
        if i != self.indice:
            self._construire(i)
        for nom, b in self.pilules.items():
            b.setChecked(nom == page)
