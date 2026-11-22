"""رسم الشواهد التقديرية (المعاينة الحية، ومعرض الشواهد، وملف PDF للطبع) فوق زخرفة كل نموذج."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QMarginsF, QRectF, QSizeF, Qt
from PySide6.QtGui import (QColor, QFont, QFontDatabase, QFontMetricsF, QImage, QPageLayout, QPageSize,
                           QPainter, QPainterPath, QPdfWriter, QTextOption)
from PySide6.QtWidgets import QApplication

from idara.services import chawahid as ch

_CACHE: dict[str, QImage] = {}
POLICES = ("Sakkal Majalla", "Traditional Arabic", "Simplified Arabic", "Arial")


def _image(chemin: str) -> QImage:
    if chemin not in _CACHE:
        _CACHE[chemin] = QImage(chemin)
    return _CACHE[chemin]


def famille() -> str:
    fams = set(QFontDatabase.families())
    for f in POLICES:
        if f in fams:
            return f
    app = QApplication.instance()
    return app.font().family() if app else ""


def _police(px: float, gras: bool) -> QFont:
    f = QFont(famille())
    f.setPixelSize(max(6, int(px)))
    f.setBold(gras)
    return f


def _option(enrouler: bool = True) -> QTextOption:
    o = QTextOption(Qt.AlignHCenter | Qt.AlignVCenter | Qt.AlignAbsolute)
    o.setTextDirection(Qt.RightToLeft)
    o.setWrapMode(QTextOption.WordWrap if enrouler else QTextOption.NoWrap)
    return o


def _ligne(p: QPainter, r: QRectF, t: str, px: float, couleur: str, gras: bool = False) -> None:
    """سطر واحد في الوسط، يُصغَّر حتى يتسع."""
    f = _police(px, gras)
    fm = QFontMetricsF(f)
    while fm.horizontalAdvance(t) > r.width() * 0.98 and f.pixelSize() > 6:
        f.setPixelSize(int(f.pixelSize() * 0.93))
        fm = QFontMetricsF(f)
    p.setFont(f)
    p.setPen(QColor(couleur))
    p.drawText(r, t, _option(False))


def _bloc(p: QPainter, r: QRectF, lignes: list[tuple[str, float, str, bool]]) -> None:
    """فقرات متتالية في الوسط (تلتف)، تُصغَّر معاً حتى تسع المنطقة، وتتوسط عمودياً."""
    lignes = [l for l in lignes if l[0]]
    k = 1.0
    while True:
        hs = []
        for t, px, _, gras in lignes:
            fm = QFontMetricsF(_police(px * k, gras))
            br = fm.boundingRect(QRectF(0, 0, r.width(), 10000), int(Qt.TextWordWrap | Qt.AlignHCenter), t)
            hs.append(br.height() + px * k * 0.28)
        if sum(hs) <= r.height() or k < 0.35:
            break
        k *= 0.93
    y = r.top() + (r.height() - sum(hs)) / 2
    for (t, px, coul, gras), h in zip(lignes, hs):
        p.setFont(_police(px * k, gras))
        p.setPen(QColor(coul))
        p.drawText(QRectF(r.left(), y, r.width(), h), t, _option(True))
        y += h


def _zone(r: QRectF, z) -> QRectF:
    x, y, w, h = z
    return QRectF(r.left() + r.width() * x / 100, r.top() + r.height() * y / 100, r.width() * w / 100,
                  r.height() * h / 100)


def _dessiner_image(p: QPainter, img: QImage, zone: QRectF) -> QRectF:
    s = img.size().scaled(int(zone.width()) or 1, int(zone.height()) or 1, Qt.KeepAspectRatio)
    cible = QRectF(zone.center().x() - s.width() / 2, zone.top(), s.width(), s.height())
    p.drawImage(cible, img)
    return cible


def peindre(p: QPainter, r: QRectF, cle: str, c: dict, logo: str = "") -> None:
    """يرسم شهادة كاملة في المستطيل r (بنسبة النموذج)."""
    m = ch.PAR_CLE[cle]
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.setRenderHint(QPainter.TextAntialiasing)
    fond = _image(str(m.fond))
    if fond.isNull():
        p.fillRect(r, QColor("#FFFDF6"))
    else:
        p.drawImage(r, fond)
    H = r.height()
    # الرأس: شعار الوزارة ثم الأكاديمية والمديرية والمؤسسة
    ze = _zone(r, m.zones["entete"])
    y = ze.top()
    if ch.MINISTERE.exists():
        mi = _image(str(ch.MINISTERE))
        cible = _dessiner_image(p, mi, QRectF(ze.left(), ze.top(), ze.width(), ze.height() * 0.42))
        y = cible.bottom() + H * 0.004
    lignes = c.get("entete", [])
    if lignes:
        hl = (ze.bottom() - y) / len(lignes)
        for k, l in enumerate(lignes):
            _ligne(p, QRectF(ze.left(), y + k * hl, ze.width(), hl), l, min(hl * 0.82, H * 0.024),
                   m.texte_couleur, k == len(lignes) - 1)
    if logo and "logo" in m.zones:
        img = _image(logo)
        if not img.isNull():
            zl = _zone(r, m.zones["logo"])
            d = min(zl.width(), zl.height())
            cercle = QRectF(zl.center().x() - d / 2, zl.center().y() - d / 2, d, d)
            ch_ = QPainterPath()
            ch_.addEllipse(cercle.adjusted(d * 0.06, d * 0.06, -d * 0.06, -d * 0.06))
            p.save()
            p.setClipPath(ch_)
            p.fillPath(ch_, QColor("white"))
            s = img.size().scaled(int(d * 0.8), int(d * 0.8), Qt.KeepAspectRatio)
            p.drawImage(QRectF(cercle.center().x() - s.width() / 2, cercle.center().y() - s.height() / 2,
                               s.width(), s.height()), img)
            p.restore()
    if "titre" in m.zones:
        zt = _zone(r, m.zones["titre"])
        _ligne(p, zt, c.get("titre", ""), zt.height() * 0.8, m.titre_couleur, True)
    _bloc(p, _zone(r, m.zones["corps"]), [
        (c.get("intro", ""), H * 0.034, m.texte_couleur, False),
        (c.get("nom", ""), H * 0.07, m.nom_couleur, True),
        (c.get("classe", ""), H * 0.028, m.texte_couleur, True),
        (c.get("motif", ""), H * 0.034, m.texte_couleur, False),
        (c.get("voeu", ""), H * 0.029, m.texte_couleur, False)])
    zd = _zone(r, m.zones["date"])
    _ligne(p, zd, c.get("date", ""), zd.height() * 0.62, m.texte_couleur)
    zs = _zone(r, m.zones["signature"])
    sig = c.get("signataires", [])
    if len(sig) >= 2:   # من اليمين: الأول ثم الثاني
        w = zs.width() / len(sig)
        for k, s in enumerate(sig):
            _ligne(p, QRectF(zs.right() - (k + 1) * w, zs.top(), w, zs.height() * 0.5), s, zs.height() * 0.36,
                   m.texte_couleur, True)
    elif sig:
        _ligne(p, QRectF(zs.left(), zs.top(), zs.width(), zs.height() * 0.5), sig[0], zs.height() * 0.36,
               m.texte_couleur, True)
    if "medaille" in m.zones:
        zm = _zone(r, m.zones["medaille"])
        h3 = zm.height() / 3.2
        _ligne(p, QRectF(zm.left(), zm.top() + h3 * 0.3, zm.width(), h3 * 1.2), c.get("jour", ""), h3, "#5A4300", True)
        _ligne(p, QRectF(zm.left(), zm.top() + h3 * 1.45, zm.width(), h3 * 0.8), c.get("mois", ""), h3 * 0.62,
               "#5A4300", True)
        _ligne(p, QRectF(zm.left(), zm.top() + h3 * 2.2, zm.width(), h3 * 0.8), c.get("annee", ""), h3 * 0.62,
               "#5A4300", True)
    p.restore()


def apercu(cle: str, c: dict, largeur: int = 900, logo: str = "") -> QImage:
    m = ch.PAR_CLE[cle]
    h = int(largeur / m.ratio)
    img = QImage(largeur, h, QImage.Format_ARGB32_Premultiplied)
    img.fill(QColor("white"))
    p = QPainter(img)
    peindre(p, QRectF(0, 0, largeur, h), cle, c, logo)
    p.end()
    return img


def exporter_pdf(contenus: list[dict], cle: str, chemin: Path, logo: str = "") -> Path:
    """صفحة A4 أفقية لكل شهادة، جاهزة للطبع (الزخرفة بنسبتها في وسط الصفحة)."""
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    w = QPdfWriter(str(chemin))
    w.setResolution(200)
    w.setPageLayout(QPageLayout(QPageSize(QPageSize.A4), QPageLayout.Landscape, QMarginsF(0, 0, 0, 0)))
    w.setTitle(contenus[0].get("titre", "شهادة") if contenus else "شهادة")
    m = ch.PAR_CLE[cle]
    p = QPainter(w)
    for k, c in enumerate(contenus):
        if k:
            w.newPage()
        page = QRectF(0, 0, w.width(), w.height())
        s = QSizeF(m.ratio, 1).scaled(page.size(), Qt.KeepAspectRatio)
        r = QRectF(page.center().x() - s.width() / 2, page.center().y() - s.height() / 2, s.width(), s.height())
        peindre(p, r, cle, c, logo)
    p.end()
    return chemin
