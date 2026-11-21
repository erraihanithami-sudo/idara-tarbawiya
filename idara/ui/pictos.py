"""أيقونات العمليات (طلب المدير 2026-11-17: «أيقونات معبرة عن كل عملية»): تُرسم بالخطوط (لا ملفات صور، ولا رموز
قد لا يتضمنها الخط)، وتوضع آلياً على كل زر حسب نصه: إضافة، حفظ، طباعة، توليد وثيقة، استيراد، إرسال، تذكير...

`Decorateur` مرشح أحداث على مستوى التطبيق: كل زر يظهر لأول مرة (في الصفحات أو النوافذ المنبثقة) يأخذ أيقونته إن
لم تكن له أيقونة، فلا حاجة لتعديل كل صفحة على حدة.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import QPushButton

from idara.ui import theme


def _plus(p):
    p.drawLine(QPointF(12, 5), QPointF(12, 19))
    p.drawLine(QPointF(5, 12), QPointF(19, 12))


def _disque(p):
    ch = QPainterPath()
    ch.moveTo(5, 4)
    ch.lineTo(16.5, 4)
    ch.lineTo(20, 7.5)
    ch.lineTo(20, 20)
    ch.lineTo(4, 20)
    ch.lineTo(4, 4)
    ch.closeSubpath()
    p.drawPath(ch)
    p.drawRect(QRectF(8, 4, 7, 4.5))
    p.drawRect(QRectF(7.5, 13, 9, 7))


def _imprimante(p):
    p.drawRect(QRectF(7, 3.5, 10, 5))
    p.drawRoundedRect(QRectF(3.5, 8.5, 17, 8), 2, 2)
    p.drawRect(QRectF(7, 13.5, 10, 7))
    p.drawLine(QPointF(9, 16.5), QPointF(15, 16.5))


def _document(p):
    ch = QPainterPath()
    ch.moveTo(6, 3.5)
    ch.lineTo(14, 3.5)
    ch.lineTo(18.5, 8)
    ch.lineTo(18.5, 20.5)
    ch.lineTo(6, 20.5)
    ch.closeSubpath()
    p.drawPath(ch)
    p.drawPolyline(QPolygonF([QPointF(14, 3.5), QPointF(14, 8), QPointF(18.5, 8)]))
    for y in (11.5, 14.5, 17.5):
        p.drawLine(QPointF(9, y), QPointF(15.5, y))


def _pdf(p):
    _document(p)


def _image(p):
    p.drawRoundedRect(QRectF(3.5, 5, 17, 14), 2, 2)
    p.drawEllipse(QPointF(9, 10), 1.6, 1.6)
    p.drawPolyline(QPolygonF([QPointF(4, 17.5), QPointF(10, 12.5), QPointF(13.5, 15.5), QPointF(16, 13.5),
                              QPointF(20, 17)]))


def _importer(p):
    p.drawLine(QPointF(12, 3.5), QPointF(12, 14))
    p.drawPolyline(QPolygonF([QPointF(8, 10.5), QPointF(12, 14.5), QPointF(16, 10.5)]))
    p.drawPolyline(QPolygonF([QPointF(4, 14), QPointF(4, 20), QPointF(20, 20), QPointF(20, 14)]))


def _exporter(p):
    p.drawLine(QPointF(12, 15), QPointF(12, 4))
    p.drawPolyline(QPolygonF([QPointF(8, 8), QPointF(12, 4), QPointF(16, 8)]))
    p.drawPolyline(QPolygonF([QPointF(4, 14), QPointF(4, 20), QPointF(20, 20), QPointF(20, 14)]))


def _loupe(p):
    p.drawEllipse(QPointF(10.5, 10.5), 6, 6)
    p.drawLine(QPointF(15, 15), QPointF(20, 20))


def _crayon(p):
    ch = QPainterPath()
    ch.moveTo(15.5, 4.5)
    ch.lineTo(19.5, 8.5)
    ch.lineTo(8.5, 19.5)
    ch.lineTo(4, 20)
    ch.lineTo(4.5, 15.5)
    ch.closeSubpath()
    p.drawPath(ch)
    p.drawLine(QPointF(13, 7), QPointF(17, 11))


def _retour(p):   # سهم نحو اليمين (الرجوع في الاتجاه العربي)
    p.drawLine(QPointF(5, 12), QPointF(19, 12))
    p.drawPolyline(QPolygonF([QPointF(13.5, 6.5), QPointF(19, 12), QPointF(13.5, 17.5)]))


def _avion(p):
    p.drawPolygon(QPolygonF([QPointF(20.5, 3.5), QPointF(3.5, 11), QPointF(10, 13.5), QPointF(12.5, 20.5)]))
    p.drawLine(QPointF(10, 13.5), QPointF(20.5, 3.5))


def _cloche(p):
    ch = QPainterPath()
    ch.moveTo(5, 17)
    ch.cubicTo(7, 15, 6.5, 12, 7, 9.5)
    ch.cubicTo(7.5, 6, 9.5, 4.5, 12, 4.5)
    ch.cubicTo(14.5, 4.5, 16.5, 6, 17, 9.5)
    ch.cubicTo(17.5, 12, 17, 15, 19, 17)
    ch.closeSubpath()
    p.drawPath(ch)
    p.drawArc(QRectF(10, 17, 4, 4), 180 * 16, 180 * 16)


def _coche(p):
    p.drawEllipse(QPointF(12, 12), 8.5, 8.5)
    p.drawPolyline(QPolygonF([QPointF(8, 12.5), QPointF(11, 15.5), QPointF(16.5, 9)]))


def _croix(p):
    p.drawLine(QPointF(6.5, 6.5), QPointF(17.5, 17.5))
    p.drawLine(QPointF(17.5, 6.5), QPointF(6.5, 17.5))


def _barres(p):
    p.drawLine(QPointF(4, 20), QPointF(20, 20))
    for x, h in ((6, 7), (11, 12), (16, 9)):
        p.drawRoundedRect(QRectF(x, 19 - h, 3, h), 1, 1)


def _actualiser(p):
    p.drawArc(QRectF(5, 5, 14, 14), 40 * 16, 270 * 16)
    p.drawPolyline(QPolygonF([QPointF(17.5, 3.5), QPointF(17.6, 7.6), QPointF(13.5, 7.4)]))


def _dossier(p):
    ch = QPainterPath()
    ch.moveTo(3.5, 7)
    ch.lineTo(3.5, 19)
    ch.lineTo(20.5, 19)
    ch.lineTo(20.5, 8.5)
    ch.lineTo(11.5, 8.5)
    ch.lineTo(9.5, 5.5)
    ch.lineTo(3.5, 5.5)
    ch.closeSubpath()
    p.drawPath(ch)


def _oeil(p):
    ch = QPainterPath()
    ch.moveTo(3, 12)
    ch.quadTo(12, 3, 21, 12)
    ch.quadTo(12, 21, 3, 12)
    p.drawPath(ch)
    p.drawEllipse(QPointF(12, 12), 3, 3)


def _calendrier(p):
    p.drawRoundedRect(QRectF(4, 5.5, 16, 15), 2, 2)
    p.drawLine(QPointF(4, 10), QPointF(20, 10))
    p.drawLine(QPointF(8.5, 3.5), QPointF(8.5, 7))
    p.drawLine(QPointF(15.5, 3.5), QPointF(15.5, 7))


def _personnes(p):
    p.drawEllipse(QPointF(9, 8.5), 3.2, 3.2)
    p.drawArc(QRectF(3.5, 13, 11, 10), 0, 180 * 16)
    p.drawEllipse(QPointF(16.5, 9.5), 2.6, 2.6)
    p.drawArc(QRectF(13, 14, 8, 8), 0, 180 * 16)


def _melanger(p):
    p.drawPolyline(QPolygonF([QPointF(4, 7), QPointF(9, 7), QPointF(15, 17), QPointF(20, 17)]))
    p.drawPolyline(QPolygonF([QPointF(4, 17), QPointF(9, 17), QPointF(15, 7), QPointF(20, 7)]))
    p.drawPolyline(QPolygonF([QPointF(17.5, 4.5), QPointF(20, 7), QPointF(17.5, 9.5)]))
    p.drawPolyline(QPolygonF([QPointF(17.5, 14.5), QPointF(20, 17), QPointF(17.5, 19.5)]))


def _pause(p):
    p.drawEllipse(QPointF(12, 12), 8.5, 8.5)
    p.drawLine(QPointF(10, 8.5), QPointF(10, 15.5))
    p.drawLine(QPointF(14, 8.5), QPointF(14, 15.5))


def _interdit(p):
    p.drawEllipse(QPointF(12, 12), 8.5, 8.5)
    p.drawLine(QPointF(6, 18), QPointF(18, 6))


def _absent(p):
    p.drawEllipse(QPointF(10, 8), 3.4, 3.4)
    p.drawArc(QRectF(3.5, 13, 13, 11), 0, 180 * 16)
    p.drawLine(QPointF(16, 11), QPointF(21, 16))
    p.drawLine(QPointF(21, 11), QPointF(16, 16))


def _entree(p):   # وافد: سهم يدخل الباب
    p.drawPolyline(QPolygonF([QPointF(13, 4), QPointF(20, 4), QPointF(20, 20), QPointF(13, 20)]))
    p.drawLine(QPointF(3.5, 12), QPointF(14, 12))
    p.drawPolyline(QPolygonF([QPointF(10, 8), QPointF(14, 12), QPointF(10, 16)]))


def _sortie(p):   # مغادر: سهم يخرج من الباب
    p.drawPolyline(QPolygonF([QPointF(11, 4), QPointF(4, 4), QPointF(4, 20), QPointF(11, 20)]))
    p.drawLine(QPointF(9, 12), QPointF(20.5, 12))
    p.drawPolyline(QPolygonF([QPointF(16.5, 8), QPointF(20.5, 12), QPointF(16.5, 16)]))


def _maison(p):   # السكن: بيت بسقف وباب ونافذة
    p.drawPolyline(QPolygonF([QPointF(3, 11.5), QPointF(12, 4), QPointF(21, 11.5)]))
    p.drawPolyline(QPolygonF([QPointF(5.5, 9.8), QPointF(5.5, 20), QPointF(18.5, 20), QPointF(18.5, 9.8)]))
    p.drawPolyline(QPolygonF([QPointF(10, 20), QPointF(10, 14.5), QPointF(14, 14.5), QPointF(14, 20)]))
    p.drawLine(QPointF(16.5, 4.8), QPointF(16.5, 7.6))


DESSINS = {
    "maison": _maison,
    "pause": _pause, "interdit": _interdit, "absent": _absent, "entree": _entree, "sortie": _sortie,
    "ajouter": _plus, "enregistrer": _disque, "imprimer": _imprimante, "document": _document, "pdf": _pdf,
    "image": _image, "importer": _importer, "exporter": _exporter, "chercher": _loupe, "modifier": _crayon,
    "retour": _retour, "envoyer": _avion, "rappel": _cloche, "valider": _coche, "annuler": _croix,
    "statistiques": _barres, "actualiser": _actualiser, "ouvrir": _dossier, "apercu": _oeil,
    "calendrier": _calendrier, "personnes": _personnes, "repartir": _melanger,
}

# الأولوية بالترتيب: أول كلمة مفتاحية موجودة في نص الزر تحدد أيقونته.
MOTS = [
    ("حفظ PDF", "pdf"), ("PDF", "pdf"), ("كصورة", "image"), ("صورة", "image"),
    ("معاينة", "apercu"), ("الاطلاع", "apercu"), ("رجوع", "retour"), ("العودة", "retour"),
    ("إلغاء", "annuler"), ("إغلاق", "annuler"),
    ("استيراد", "importer"), ("تصدير", "exporter"), ("نسخ إلى", "exporter"), ("نسخة احتياطية", "exporter"),
    ("إضافة", "ajouter"), ("جديد", "ajouter"), ("سطر فارغ", "ajouter"),
    ("طباعة", "imprimer"), ("طبع", "imprimer"),
    ("حفظ", "enregistrer"), ("تسجيل", "enregistrer"),
    ("تذكير", "rappel"), ("إرسال", "envoyer"),
    ("تأشير", "valider"), ("تأكيد", "valider"), ("اعتماد", "valider"), ("قبول", "valider"),
    ("إحصائيات", "statistiques"), ("المبيان", "statistiques"),
    ("توزيع", "repartir"), ("تحديث", "actualiser"), ("احتساب", "actualiser"), ("ملء", "actualiser"),
    ("بحث", "chercher"), ("تعديل", "modifier"), ("تخصيص", "modifier"),
    ("فتح", "ouvrir"), ("المجلد", "ouvrir"),
    ("توليد", "document"), ("وثيقة", "document"), ("وثائق", "document"), ("محضر", "document"), ("مذكرة", "document"),
    ("مراسلة", "document"), ("شهادة", "document"), ("بطاقة", "document"), ("بطاقات", "document"),
    ("لائحة", "document"), ("جدول", "document"), ("تقرير", "document"), ("طلب", "document"),
    ("أسبوع", "calendrier"), ("التاريخ", "calendrier"),
]

# أزرار لها مظهرها الخاص (حبوب التنقل، الشريط الجانبي، أدوات التنسيق...) لا تُمس.
EXCLUS = {"boutonCouleur", "piluleOrnee", "onglet", "puceRahba", "pilule", "navSection", "navPage", "danger", "puce", "carteAction", "lien", "navSous", "nav",
          "navQuitter", "boutonAnnee", "sousnav", "navigation", "rechercheNav"}
ZONES_EXCLUES = {"barreLaterale", "bandeauPage", "bandeauArchive"}
FORMATAGE = {"غامق", "تسطير", "يمين", "وسط", "يسار", "تكبير الخط", "تصغير الخط", "تراجع", "إعادة"}

_cache: dict[tuple[str, str, int], QIcon] = {}


def pixmap(nom: str, couleur: str, taille: int = 18, epaisseur: float = 1.9) -> QPixmap:
    n = taille * 3
    pm = QPixmap(n, n)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(n / 24, n / 24)
    p.setPen(QPen(QColor(couleur), epaisseur, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    DESSINS[nom](p)
    p.end()
    pm.setDevicePixelRatio(3)
    return pm


def pastille(nom: str, couleur: str, taille: int = 46) -> QPixmap:
    """الأيقونة داخل دائرة بلون خافت (بطاقات الأرقام والمعايير)."""
    n = taille * 3
    pm = QPixmap(n, n)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    c = QColor(couleur)
    fond = QColor(c)
    fond.setAlpha(36)
    p.setPen(Qt.NoPen)
    p.setBrush(fond)
    p.drawEllipse(QRectF(0, 0, n, n))
    p.translate(n * 0.22, n * 0.22)
    p.scale(n * 0.56 / 24, n * 0.56 / 24)
    p.setPen(QPen(c, 2.1, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    DESSINS[nom](p)
    p.end()
    pm.setDevicePixelRatio(3)
    return pm


def icone(nom: str, couleur: str | None = None, taille: int = 18) -> QIcon:
    couleur = couleur or theme.VERT
    cle = (nom, couleur, taille)
    if cle not in _cache:
        _cache[cle] = QIcon(pixmap(nom, couleur, taille))
    return _cache[cle]


def nom_pour(texte: str) -> str | None:
    t = " ".join((texte or "").replace("&", "").split())
    if not t or t in FORMATAGE or t.startswith("حذف") or t.startswith("تفريغ"):
        return None
    return next((n for mot, n in MOTS if mot in t), None)


def decorer(b: QPushButton) -> bool:
    """يضع الأيقونة المناسبة على الزر إن لم تكن له أيقونة. يرجع True إن وُضعت."""
    if b.objectName() in EXCLUS or b.isCheckable() or not b.icon().isNull():
        return False
    nom = nom_pour(b.text())
    if nom is None:
        return False
    w = b.parentWidget()
    while w is not None:
        if w.objectName() in ZONES_EXCLUES:
            return False
        w = w.parentWidget()
    blanc = b.objectName() == "principal"
    b.setIcon(icone(nom, "#FFFFFF" if blanc else theme.VERT))
    b.setIconSize(QSize(18, 18))
    b.setProperty("picto", nom)
    return True


class Decorateur(QObject):
    """مرشح أحداث: كل زر يُعرض لأول مرة يأخذ أيقونته (الصفحات والنوافذ المنبثقة على السواء)."""

    def eventFilter(self, obj, ev):   # noqa: N802
        if ev.type() == QEvent.Show and isinstance(obj, QPushButton) and obj.property("picto") is None:
            obj.setProperty("picto", "")
            decorer(obj)
        return False
