"""رسم الإعلانات المزخرفة بـ QPainter: معاينة على الشاشة، ملف PDF، صورة، وطبع مباشر (A4 أو A3).

الهندسة كلها في idara.services.affiches؛ هنا التحويل إلى أشكال Qt وضبط حجم النص حتى يدخل صندوقه.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QMarginsF, QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QFont, QLinearGradient, QPageLayout, QPageSize, QPainter, QPdfWriter, QPen,
                           QPixmap, QPolygonF)
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import QApplication, QDialog

from idara.services import affiches as af
from idara.ui import theme

PT_EN_MM = 0.3528


def _familles() -> tuple[str, str]:
    """(خط العناوين، خط النص) من الخطوط المرفقة إن وُجدت، وإلا خط التطبيق."""
    base = QApplication.font().family()
    return theme.police_titres() or base, base


def _pinceau(f, k: float):
    if f is None:
        return Qt.NoBrush
    if isinstance(f, tuple):
        _, (x1, y1, x2, y2), c1, c2 = f
        g = QLinearGradient(x1 * k, y1 * k, x2 * k, y2 * k)
        g.setColorAt(0, QColor(c1))
        g.setColorAt(1, QColor(c2))
        return QBrush(g)
    return QBrush(QColor(f))


def peindre(p: QPainter, d: af.Dessin, cible: QRectF) -> list[int]:
    """يرسم الإعلان داخل cible (بنسبة A4). يرجع أحجام الخط المستعملة بالبكسل (للاختبار)."""
    k = cible.width() / af.L
    p.save()
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.TextAntialiasing, True)
    p.translate(cible.topLeft())
    p.setClipRect(QRectF(0, 0, af.L * k, af.H * k))
    for f in d.formes:
        p.setOpacity(f["o"])
        if f["s"]:
            stylo = QPen(QColor(f["s"]), f["e"] * k)
            stylo.setJoinStyle(Qt.RoundJoin)
            stylo.setCapStyle(Qt.RoundCap)
            p.setPen(stylo)
        else:
            p.setPen(Qt.NoPen)
        p.setBrush(_pinceau(f["f"], k))
        if f["t"] == "poly":
            p.drawPolygon(QPolygonF([QPointF(x * k, y * k) for x, y in f["p"]]))
        elif f["t"] == "ligne":
            p.setBrush(Qt.NoBrush)
            p.drawPolyline(QPolygonF([QPointF(x * k, y * k) for x, y in f["p"]]))
        elif f["t"] == "cercle":
            p.drawEllipse(QPointF(f["c"][0] * k, f["c"][1] * k), f["r"] * k, f["r"] * k)
        else:
            x, y, w, h = f["b"]
            p.drawRoundedRect(QRectF(x * k, y * k, w * k, h * k), f["r"] * k, f["r"] * k)
    p.setOpacity(1)
    p.setLayoutDirection(Qt.RightToLeft)
    f_titre, f_corps = _familles()
    tailles = []
    for t in d.textes:
        x, y, w, h = t.boite
        boite = QRectF(x * k, y * k, w * k, h * k)
        drapeaux = Qt.AlignVCenter.value | Qt.TextWordWrap.value | (
            Qt.AlignHCenter.value if t.aligne == "centre" else Qt.AlignRight.value | Qt.AlignAbsolute.value)
        police = QFont(f_titre if t.titre else f_corps)
        police.setBold(t.gras)
        px = max(1.0, t.taille * PT_EN_MM * k)
        mini = max(1.0, px * 0.3)
        while True:   # نصغّر حتى يدخل النص صندوقه
            police.setPixelSize(max(1, int(px)))
            p.setFont(police)
            r = p.boundingRect(boite, drapeaux, t.texte)
            if (r.height() <= boite.height() + 0.5 and r.width() <= boite.width() + 0.5) or px <= mini:
                break
            px *= 0.94
        tailles.append(int(px))
        p.setPen(QColor(t.couleur))
        p.drawText(boite, drapeaux, t.texte)
    p.restore()
    return tailles


def pixmap(d: af.Dessin, largeur: int) -> QPixmap:
    pm = QPixmap(largeur, round(largeur * af.H / af.L))
    pm.fill(Qt.white)
    p = QPainter(pm)
    peindre(p, d, QRectF(0, 0, pm.width(), pm.height()))
    p.end()
    return pm


def _taille_page(format_: str) -> QPageSize:
    return QPageSize(QPageSize.A3 if format_ == "A3" else QPageSize.A4)


def exporter_pdf(d: af.Dessin, format_: str, chemin: Path) -> Path:
    w = QPdfWriter(str(chemin))
    w.setResolution(300)
    w.setPageSize(_taille_page(format_))
    w.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Millimeter)
    w.setTitle(Path(chemin).stem)
    p = QPainter(w)
    peindre(p, d, QRectF(0, 0, w.width(), w.height()))
    p.end()
    return Path(chemin)


def exporter_image(d: af.Dessin, chemin: Path, largeur: int = 2480) -> Path:
    """صورة PNG (عرض A4 بدقة 300 نقطة) للإرسال في واتساب أو النشر."""
    pixmap(d, largeur).save(str(chemin), "PNG")
    return Path(chemin)


def imprimer(d: af.Dessin, format_: str, parent=None) -> bool:
    pr = QPrinter(QPrinter.HighResolution)
    pr.setPageSize(_taille_page(format_))
    pr.setPageOrientation(QPageLayout.Portrait)
    pr.setFullPage(True)
    if QPrintDialog(pr, parent).exec() != QDialog.Accepted:
        return False
    p = QPainter(pr)
    papier = pr.paperRect(QPrinter.DevicePixel)
    larg = min(papier.width(), papier.height() * af.L / af.H)   # نحافظ على النسبة إن اختلف ورق الطابعة
    peindre(p, d, QRectF((papier.width() - larg) / 2, 0, larg, larg * af.H / af.L))
    p.end()
    return True
