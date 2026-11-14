"""واجهة «الرحاب» (طلب المدير 2026-11-14: تغيير المظهر الكلاسيكي بلمسة خاصة بنا).

- الرحبة: لكل قسم رئيسي صفحة استقبال، رأسها بلون القسم وزليجه، وتحتها بطاقة لكل صفحة فيه.
- شريط المسار: فوق كل صفحة، اسم القسم ثم صفحاته حبوباً يُنتقل بينها بنقرة.
- بطاقة الفعل: بطاقة تُنقر (صفحة تُفتح أو وثيقة تُولَّد) بدل زر في صف أزرار.

الأفكار فقط من المقارنة مع برامج أخرى؛ الرسم والتخطيط والألوان من هوية «رحاب».
"""

from __future__ import annotations

import sqlite3

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QButtonGroup, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
                               QVBoxLayout, QWidget)

from idara.ui import icones, theme
from idara.ui.zellige import dessiner_etoile

# سطر تعريفي لكل صفحة (يظهر في بطاقتها داخل الرحبة)
DESCRIPTIONS = {
    "لوحة القيادة": "مؤشرات المؤسسة اليوم وما ينتظر التدخل.",
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
    "الصحة والسلامة": "سجل الحوادث المدرسية والتصريح بها.",
    "التلاميذ القدامى": "تلاميذ ما قبل مسار وشواهدهم.",
    "الاستيراد من مسار": "استيراد لوائح الأقسام من منظومة مسار.",
    "الموارد البشرية": "بطاقات الأطر ومعطياتهم الإدارية.",
    "تدبير الفائض": "ترتيب الأساتذة وتحديد الفائض والخصاص.",
    "الرخص": "ملف الرخصة كاملاً: الطلب، الوصل، التعويض، الاستئناف.",
    "محاضر الموارد البشرية": "محاضر الالتحاق والدخول والخروج.",
    "طلبات الموظفين": "الإذن بالتغيب، رخصة الأبوة والزواج، الفحص المضاد، الورقة الشخصية.",
    "الأعوان": "أعوان الحراسة والنظافة والإطعام وحصيلتهم الشهرية.",
    "التنظيم التربوي": "البنية التربوية وإسناد الأقسام.",
    "التعلمات الأساس": "تتبع مستويات القراءة والحساب.",
    "الدعم التربوي": "مجموعات الدعم وحصصها وسجلها.",
    "الريادة": "مؤشرات المدرسة الرائدة ووثائقها.",
    "استعمالات الزمن": "حصص كل أستاذ ومراقبة الحصيص الأسبوعي.",
    "جدول الحراسة": "توزيع حراسة الدخول والاستراحة والخروج.",
    "الأندية والأنشطة": "الأندية التربوية وبرنامج الأنشطة وحصيلته.",
    "خليتا اليقظة والإنصات": "التركيبة، الاجتماعات، والحالات المرصودة.",
    "التحفيز والتهاني": "الشهادات التقديرية ولوحة الشرف.",
    "الانفتاح والشراكة": "اتفاقيات الشراكة والتزامات كل طرف.",
    "الإعلام والتواصل": "الإعلانات والبلاغات الجاهزة للتعليق.",
    "التسجيلات": "واجبات التسجيل والتأمين ووصولاتها.",
    "الجرد": "سجل الجرد حسب نوع التجهيز.",
    "جمعية دعم مدرسة النجاح": "المداخيل والمصاريف والميزانية والتقارير.",
    "الصرف": "سند الطلب والاتفاقية وملف الصرف.",
    "الجمعية الرياضية": "مالية الجمعية الرياضية وسجلاتها.",
    "جمعية تنمية التعاون المدرسي": "مالية التعاونية وسجلاتها.",
    "البنية المادية": "الحجرات والمرافق لكل وحدة مدرسية.",
    "الوثائق القانونية للجمعيات": "تجديد المكاتب ومحاضر الجموع العامة.",
    "المراقبة المستمرة": "تتبع فروض المراقبة المستمرة.",
    "الامتحان": "الامتحان الموحد: القاعات والحراسة والمحاضر.",
    "استثمار النتائج": "تحليل النتائج وتحديد حاجيات الدعم.",
    "مجالس الأقسام": "محاضر مجالس الأقسام وقراراتها.",
    "محاضر نهاية الأسدوس": "المداولات ومحاضر نهاية الأسدوس.",
    "مشروع المؤسسة": "المؤشرات والعمليات وتتبع الإنجاز.",
    "فريق القيادة": "أعضاء فريق القيادة ومحضرا التشكيل والمصادقة.",
    "تسليم المهام": "محضر تسليم المهام بين المديرَين.",
    "سجل الصادر": "ترقيم المراسلات الصادرة.",
    "إعداد المؤسسة": "معطيات المؤسسة والمدير والمظهر.",
    "الوثائق": "نماذج الوثائق وتخصيصها.",
    "دليل الاستخدام": "جولة مصورة وخطوات البداية.",
}

SOUS_SECTIONS = {
    "القيادة والتدبير": "نظرة شاملة على المؤسسة: المؤشرات، البرنامج السنوي، المجالس، والسبورة المرجعية.",
    "التلاميذ": "كل ما يخص التلميذ: وثائقه، حركيته، سلوكه، وليّه، نقله، وسلامته.",
    "الموارد البشرية": "الأطر والأعوان: المعطيات، الرخص، الطلبات، والمحاضر.",
    "التدبير التربوي": "تنظيم الدراسة والدعم واستعمالات الزمن.",
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
        h.addWidget(Glyphe(couleur, forme), 0, Qt.AlignTop)
        v = QVBoxLayout()
        v.setSpacing(2)
        self.l_titre = QLabel(titre)
        self.l_titre.setObjectName("carteActionTitre")
        self.l_titre.setWordWrap(True)
        v.addWidget(self.l_titre)
        self.l_desc = QLabel(description)
        self.l_desc.setObjectName("etiquette")
        self.l_desc.setWordWrap(True)
        self.l_desc.setVisible(bool(description))
        v.addWidget(self.l_desc)
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
        self.l_puce = QLabel(puce)
        self.l_puce.setObjectName("heroPuce")
        self.l_puce.setVisible(bool(puce))
        h.addWidget(self.l_puce, 0, Qt.AlignTop)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
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
    reg = getattr(fenetre.pages.get(page), "cles_registres", None)
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
            k = CarteAction(lib, DESCRIPTIONS.get(page, ""), c)
            k.clique.connect(lambda page=page: self.f.aller_a(page))
            self.cartes[page] = self.galerie.ajouter(k)
        racine.addWidget(self.galerie)
        racine.addStretch()

    def rafraichir(self) -> None:
        for page, k in self.cartes.items():
            k.pastille("قريباً" if page not in self.f.pages else compteur(self.f, page))


class BandeauPage(QFrame):
    """شريط المسار فوق الصفحات: القسم (يفتح رحبته) ثم صفحاته حبوباً."""

    def __init__(self, fenetre, sections):
        super().__init__()
        self.f, self.sections = fenetre, sections
        self.setObjectName("bandeauPage")
        self.setFixedHeight(60)
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
        self.zone = QScrollArea()
        self.zone.setObjectName("defilPilules")
        self.zone.setWidgetResizable(True)
        self.zone.setFrameShape(QFrame.NoFrame)
        self.zone.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.zone.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.zone.setFixedHeight(42)
        h.addWidget(self.zone, 1)
        self.pilules: dict[str, QPushButton] = {}
        self.groupe = QButtonGroup(self)

    def _construire(self, i: int) -> None:
        titre, fils = self.sections[i]
        c = couleur_section(titre)
        self.setStyleSheet(f"QFrame#bandeauPage {{ border-bottom: 3px solid {c}; }}")
        self.b_rahba.setText("  " + titre)
        self.b_rahba.setIcon(QIcon(icones.tuile(titre, 30, sombre=False)))
        contenu = QWidget()   # محتوى جديد في كل مرة (لا نعيد استعمال تخطيط قديم)
        contenu.setObjectName("fondPilules")
        hh = QHBoxLayout(contenu)
        hh.setContentsMargins(0, 2, 0, 2)
        hh.setSpacing(8)
        self.groupe = QButtonGroup(contenu)
        self.groupe.setExclusive(False)
        self.pilules = {}
        for page, lib in fils:
            b = QPushButton(lib)
            b.setObjectName("pilule")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, page=page: self.f.aller_a(page))
            self.groupe.addButton(b)
            self.pilules[page] = b
            hh.addWidget(b)
        hh.addStretch()
        self.zone.setWidget(contenu)
        self.fleche.setVisible(len(fils) > 1)
        self.zone.setVisible(len(fils) > 1)
        self.indice = i

    def afficher(self, i: int, page: str | None) -> None:
        if i != self.indice:
            self._construire(i)
        for nom, b in self.pilules.items():
            b.setChecked(nom == page)
        if page in self.pilules:
            self.zone.ensureWidgetVisible(self.pilules[page])
