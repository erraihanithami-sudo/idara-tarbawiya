"""مبيانا بطاقة التلميذ: سلم TaRL (الرائز القبلي والبعدي والمستوى المتوقع لكل مادة)، وتطور مستوى التحكم A/B/C
عبر الروائز والمراحل. يُرسمان على الشاشة، ويُصدَّران صوراً لوثيقة البطاقة."""

from __future__ import annotations

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QApplication, QSizePolicy, QWidget

from idara.services import fiche_eleve as fe

COULEURS = {"ar": "#3B3FB6", "fr": "#C0392B", "ma": "#1F7A5C"}
GRIS, GRILLE, ENCRE = "#5C5C66", "#D9D9E0", "#1B1B3A"


def _police(px: float, gras: bool = False) -> QFont:
    f = QFont(QApplication.font().family())
    f.setPixelSize(max(8, int(px)))
    f.setBold(gras)
    return f


def _texte(p: QPainter, r: QRectF, t: str, px: float, couleur=ENCRE, gras=False, align=Qt.AlignCenter) -> None:
    p.setFont(_police(px, gras))
    p.setPen(QColor(couleur))
    p.drawText(r, int(align) | int(Qt.TextWordWrap), t)


def peindre_tarl(p: QPainter, r: QRectF, parcours: dict) -> None:
    """لكل مادة عمودان (القبلي فاتح، البعدي داكن) بارتفاع درجة التلميذ على سلم المادة، وخط المستوى المتوقع."""
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    p.setLayoutDirection(Qt.RightToLeft)
    p.fillRect(r, QColor("white"))
    t = parcours["tarl"]
    u = r.height() / 100
    _texte(p, QRectF(r.left(), r.top(), r.width(), 8 * u), "رائزا الموضعة: موقع التلميذ على سلم كل مادة",
           5 * u, gras=True)
    zone = QRectF(r.left() + 4 * u, r.top() + 12 * u, r.width() - 8 * u, r.height() - 30 * u)
    p.setPen(QPen(QColor(GRILLE), max(1, u * 0.25)))
    for k in range(5):
        y = zone.bottom() - zone.height() * k / 4
        p.drawLine(QPointF(zone.left(), y), QPointF(zone.right(), y))
    mats = [m for m in fe.MATIERES if m in t] or list(fe.MATIERES)
    largeur = zone.width() / len(mats)
    for i, m in enumerate(reversed(mats)):          # من اليمين: العربية أولاً
        x0 = zone.left() + i * largeur
        d = t.get(m)
        _texte(p, QRectF(x0, zone.bottom() + 2 * u, largeur, 6 * u), fe.MATIERES[m], 4.2 * u, gras=True)
        if not d:
            _texte(p, QRectF(x0, zone.top(), largeur, zone.height()), "لا معطيات", 3.6 * u, GRIS)
            continue
        n = len(d["echelle"]) - 1
        bw = largeur * 0.26
        c = QColor(COULEURS[m])
        for k, (cle, alpha, lib) in enumerate((("pre", 110, "القبلي"), ("post", 255, "البعدي"))):
            rg = d[f"rang_{cle}"]
            bx = x0 + largeur / 2 + (0.06 * largeur if k == 0 else -0.06 * largeur - bw)
            _texte(p, QRectF(bx - bw * 0.3, zone.bottom() + 8 * u, bw * 1.6, 5 * u), lib, 3.2 * u, GRIS)
            if rg is None:
                continue
            h = zone.height() * (rg + 0.35) / (n + 0.35)
            cc = QColor(c)
            cc.setAlpha(alpha)
            ch = QPainterPath()
            ch.addRoundedRect(QRectF(bx, zone.bottom() - h, bw, h), bw * 0.18, bw * 0.18)
            p.fillPath(ch, cc)
            _texte(p, QRectF(bx - bw * 0.5, zone.bottom() - h - 6.5 * u, bw * 2, 6 * u), d[cle], 3.4 * u,
                   ENCRE, gras=cle == "post")
        if d["rang_attendu"] is not None:   # المستوى المتوقع: خط متقطع
            ya = zone.bottom() - zone.height() * (d["rang_attendu"] + 0.35) / (n + 0.35)
            stylo = QPen(QColor("#F08A00"), max(1.5, 0.6 * u), Qt.DashLine)
            p.setPen(stylo)
            p.drawLine(QPointF(x0 + largeur * 0.12, ya), QPointF(x0 + largeur * 0.88, ya))
            _texte(p, QRectF(x0 + largeur * 0.62, ya - 5.5 * u, largeur * 0.38, 5 * u),
                   f"المتوقع: {d['attendu']}", 3 * u, "#B35F00")
    p.restore()


def peindre_etapes(p: QPainter, r: QRectF, parcours: dict) -> None:
    """خط لكل مادة: مستوى التحكم (C ضعيف، B مقنع، A تام) من الرائز القبلي إلى آخر مرحلة."""
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    p.setLayoutDirection(Qt.RightToLeft)
    p.fillRect(r, QColor("white"))
    e = parcours["etapes"]
    u = r.height() / 100
    _texte(p, QRectF(r.left(), r.top(), r.width(), 8 * u), "تطور مستوى التحكم عبر الروائز والمراحل", 5 * u, gras=True)
    phases = sorted({ph for v in e.values() for ph in v}) or [-1, 0, 1]
    gauche = r.left() + 16 * u
    zone = QRectF(gauche, r.top() + 14 * u, r.right() - 4 * u - gauche, r.height() - 32 * u)
    for k, (lettre, lib) in enumerate((("C", "ضعيف"), ("B", "مقنع"), ("A", "تام"))):
        y = zone.bottom() - zone.height() * k / 2
        p.setPen(QPen(QColor(GRILLE), max(1, u * 0.25)))
        p.drawLine(QPointF(zone.left(), y), QPointF(zone.right(), y))
        _texte(p, QRectF(r.left(), y - 3.5 * u, 15 * u, 7 * u), f"{lettre} {lib}", 3.4 * u, GRIS)
    pas = zone.width() / max(1, len(phases) - 1) if len(phases) > 1 else 0

    def x_de(i: int) -> float:   # من اليمين إلى اليسار: الرائز القبلي على اليمين
        return zone.right() - i * pas if len(phases) > 1 else zone.center().x()

    for i, ph in enumerate(phases):
        _texte(p, QRectF(x_de(i) - 12 * u, zone.bottom() + 3 * u, 24 * u, 9 * u), fe.libelle_phase(ph), 3.2 * u, GRIS)
    for k, m in enumerate(fe.MATIERES):
        pts = [(i, e[m][ph]) for i, ph in enumerate(phases) if ph in e.get(m, {})]
        if not pts:
            continue
        c = QColor(COULEURS[m])
        decal = (k - 1) * 0.8 * u                   # تفادي تطابق الخطوط
        xy = [QPointF(x_de(i), zone.bottom() - zone.height() * (fe.VALEUR[n] - 1) / 2 + decal) for i, n in pts]
        p.setPen(QPen(c, max(2, 0.8 * u)))
        for a, b in zip(xy, xy[1:]):
            p.drawLine(a, b)
        p.setBrush(c)
        for q in xy:
            p.drawEllipse(q, 1.6 * u, 1.6 * u)
    # المفتاح
    x = r.right() - 4 * u
    for m in fe.MATIERES:
        if m not in e:
            continue
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(COULEURS[m]))
        p.drawRoundedRect(QRectF(x - 4 * u, r.bottom() - 7 * u, 4 * u, 3 * u), u, u)
        _texte(p, QRectF(x - 32 * u, r.bottom() - 8.5 * u, 27 * u, 6 * u), fe.MATIERES[m], 3.2 * u, ENCRE,
               align=Qt.AlignRight | Qt.AlignVCenter)
        x -= 36 * u
    p.restore()


def png(peintre, parcours: dict, taille=QSize(1600, 620)) -> bytes:
    img = QImage(taille, QImage.Format_ARGB32)
    img.fill(Qt.white)
    p = QPainter(img)
    peintre(p, QRectF(0, 0, taille.width(), taille.height()), parcours)
    p.end()
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "PNG")
    return bytes(ba)


def graphiques(parcours: dict) -> tuple[bytes | None, bytes | None]:
    """الصورتان للوثيقة (لا صورة لما لا معطيات له)."""
    return (png(peindre_tarl, parcours) if parcours["tarl"] else None,
            png(peindre_etapes, parcours) if parcours["etapes"] else None)


class Graphe(QWidget):
    def __init__(self, peintre, hauteur: int = 280):
        super().__init__()
        self.peintre, self.parcours = peintre, None
        self.setMinimumHeight(hauteur)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def definir(self, parcours: dict | None) -> None:
        self.parcours = parcours
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        if self.parcours is not None:
            self.peintre(p, QRectF(self.rect()), self.parcours)
        p.end()
