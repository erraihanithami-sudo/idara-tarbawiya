"""شاشة العرض: رسم الشرائح (للتلفاز وللتصدير) ونافذة العرض بملء الشاشة (طلب المدير 2026-11-21).
تصميم خاص بالبرنامج: ليلي وذهبي بنجوم الزليج، مثل صفحة التواصل والمظهر العام."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QMarginsF, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (QColor, QFont, QFontMetricsF, QGuiApplication, QImage, QLinearGradient, QPainter,
                           QPainterPath, QPageLayout, QPageSize, QPdfWriter, QPen, QTextOption)
from PySide6.QtWidgets import QApplication, QWidget

from idara.services import textes as tx
from idara.services.ecran import DYNAMIQUES
from idara.ui.zellige import dessiner_etoile

NUIT, NUIT2, DORE, DORE_CLAIR, BLANC = "#0B1C2C", "#1F3B57", "#C9A04A", "#F3D27A", "#FFFFFF"
GRIS_CLAIR = "#C9D3DF"
VERT, ORANGE, ROUGE, BLEU, ROSE, VIOLET = "#3FB68B", "#F0A23B", "#E5624F", "#4C9BE8", "#E87AA8", "#9C7FE0"
LARGEUR, HAUTEUR = 1920, 1080


def _police(taille: float, gras: bool = False) -> QFont:
    app = QApplication.instance()
    f = QFont(app.font()) if app else QFont()
    f.setPixelSize(max(6, int(taille)))
    f.setBold(gras)
    return f


def texte(p: QPainter, r: QRectF, t: str, taille: float, couleur: str = BLANC, gras: bool = False,
          align=Qt.AlignRight | Qt.AlignVCenter, ajuster: bool = True) -> None:
    """نص عربي من اليمين؛ يُصغَّر الخط إن لم يتسع في سطر واحد."""
    f = _police(taille, gras)
    if ajuster:
        fm = QFontMetricsF(f)
        while fm.horizontalAdvance(t) > r.width() and f.pixelSize() > 10:
            f.setPixelSize(int(f.pixelSize() * 0.92))
            fm = QFontMetricsF(f)
    p.setFont(f)
    p.setPen(QColor(couleur))
    o = QTextOption(align | Qt.AlignAbsolute)   # المواضع بصرية (يمين = يمين الشاشة)
    o.setTextDirection(Qt.RightToLeft)
    o.setWrapMode(QTextOption.NoWrap if ajuster else QTextOption.WordWrap)
    p.drawText(r, t, o)


# تقدم حركة العدادات (0 ← 1) أثناء ظهور الشريحة: الأرقام تعدّ تصاعدياً والحلقات والأعمدة تمتلئ
_P = 1.0


def _anim(v):
    if _P >= 1 or not isinstance(v, (int, float)) or isinstance(v, bool):
        return v
    return round(v * _P) if isinstance(v, int) else round(v * _P, 1)


def _nombre(v) -> str:
    v = _anim(v)
    return "—" if v is None else (f"{v:.0f}" if isinstance(v, float) and v == int(v) else str(v))


def _pct(v) -> str:
    v = _anim(v)
    return "—" if v is None else f"{v:.0f}%" if v == int(v) else f"{v:.1f}%"


def _fond(p: QPainter, r: QRectF, u: float) -> None:
    g = QLinearGradient(r.topRight(), r.bottomLeft())
    g.setColorAt(0, QColor(NUIT))
    g.setColorAt(1, QColor(NUIT2))
    p.fillRect(r, g)
    for x, y, s in ((r.left() + 150 * u, r.bottom() - 170 * u, 120 * u), (r.left() + 330 * u, r.bottom() - 70 * u,
                                                                         34 * u),
                    (r.right() - 120 * u, r.top() + 250 * u, 26 * u), (r.left() + 60 * u, r.top() + 300 * u, 18 * u)):
        p.setOpacity(0.35)
        dessiner_etoile(p, x, y, s, DORE, pleine=False)
    p.setOpacity(1)
    p.setPen(QPen(QColor(DORE), 3 * u))
    p.setBrush(Qt.NoBrush)
    p.drawRect(r.adjusted(18 * u, 18 * u, -18 * u, -18 * u))
    p.setPen(QPen(QColor(201, 160, 74, 110), 1.2 * u))
    p.drawRect(r.adjusted(28 * u, 28 * u, -28 * u, -28 * u))


def _carte(p: QPainter, r: QRectF, u: float, accent: str = DORE) -> None:
    ch = QPainterPath()
    ch.addRoundedRect(r, 26 * u, 26 * u)
    p.fillPath(ch, QColor(255, 255, 255, 22))
    p.setPen(QPen(QColor(255, 255, 255, 50), 1.5 * u))
    p.setBrush(Qt.NoBrush)
    p.drawPath(ch)
    bar = QPainterPath()
    bar.addRoundedRect(QRectF(r.left() + 30 * u, r.top(), r.width() - 60 * u, 6 * u), 3 * u, 3 * u)
    p.fillPath(bar, QColor(accent))


def _entete(p: QPainter, r: QRectF, u: float, d: dict, ident: dict) -> QRectF:
    """رأس الشريحة: اسم المؤسسة والموسم، ثم عنوان الشريحة بنجمة ذهبية. يعيد مساحة المحتوى."""
    texte(p, QRectF(r.left() + 60 * u, r.top() + 50 * u, r.width() - 120 * u, 50 * u),
          ident.get("nom", ""), 34 * u, DORE_CLAIR, True)
    texte(p, QRectF(r.left() + 60 * u, r.top() + 50 * u, r.width() - 120 * u, 50 * u),
          f"الموسم الدراسي {ident.get('annee', '')}", 26 * u, GRIS_CLAIR, align=Qt.AlignLeft | Qt.AlignVCenter)
    dessiner_etoile(p, r.right() - 90 * u, r.top() + 155 * u, 22 * u, DORE, pleine=True)
    texte(p, QRectF(r.left() + 60 * u, r.top() + 120 * u, r.width() - 215 * u, 70 * u), d["titre"], 56 * u, BLANC,
          True)
    p.setPen(QPen(QColor(DORE), 2 * u))
    p.drawLine(QPointF(r.right() - 60 * u, r.top() + 205 * u), QPointF(r.right() - 560 * u, r.top() + 205 * u))
    return QRectF(r.left() + 70 * u, r.top() + 240 * u, r.width() - 140 * u, r.height() - 240 * u - 140 * u)


def _tuile(p: QPainter, r: QRectF, u: float, valeur: str, libelle: str, accent: str, sous: str = "") -> None:
    _carte(p, r, u, accent)
    texte(p, QRectF(r.left(), r.top() + r.height() * 0.16, r.width(), r.height() * 0.42), valeur, 120 * u, accent,
          True, Qt.AlignCenter)
    texte(p, QRectF(r.left() + 20 * u, r.top() + r.height() * 0.6, r.width() - 40 * u, 60 * u), libelle, 38 * u,
          BLANC, True, Qt.AlignCenter)
    if sous:
        texte(p, QRectF(r.left() + 20 * u, r.top() + r.height() * 0.6 + 60 * u, r.width() - 40 * u, 46 * u), sous,
              26 * u, GRIS_CLAIR, False, Qt.AlignCenter)


def _tuiles(p, zone: QRectF, u, items) -> None:
    n = len(items)
    esp = 36 * u
    w = (zone.width() - esp * (n - 1)) / n
    h = min(zone.height() * 0.8, 440 * u)
    y = zone.top() + (zone.height() - h) / 2
    for k, it in enumerate(items):   # من اليمين إلى اليسار
        x = zone.right() - (k + 1) * w - k * esp
        _tuile(p, QRectF(x, y, w, h), u, *it)


def _anneau(p, c: QPointF, rayon: float, u, taux, accent: str, libelle: str, sous: str = "",
            centre: str | None = None) -> None:
    p.setPen(QPen(QColor(255, 255, 255, 40), 26 * u, Qt.SolidLine, Qt.FlatCap))
    p.setBrush(Qt.NoBrush)
    rr = QRectF(c.x() - rayon, c.y() - rayon, 2 * rayon, 2 * rayon)
    p.drawEllipse(rr)
    if taux is not None:
        p.setPen(QPen(QColor(accent), 26 * u, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(rr, 90 * 16, -int(360 * 16 * max(0.0, min(100.0, taux)) * _P / 100))
    texte(p, QRectF(c.x() - rayon * 0.8, c.y() - 60 * u, 1.6 * rayon, 120 * u), _pct(taux) if centre is None
          else centre, 84 * u, BLANC, True, Qt.AlignCenter)
    texte(p, QRectF(c.x() - rayon - 80 * u, c.y() + rayon + 30 * u, 2 * rayon + 160 * u, 54 * u), libelle, 36 * u,
          DORE_CLAIR, True, Qt.AlignCenter)
    if sous:
        texte(p, QRectF(c.x() - rayon - 80 * u, c.y() + rayon + 84 * u, 2 * rayon + 160 * u, 40 * u), sous, 24 * u,
              GRIS_CLAIR, False, Qt.AlignCenter)


def _barres(p, zone: QRectF, u, lignes, series, pct: bool | None = None) -> None:
    """أعمدة أفقية: لكل سطر (libelle، [قيم]) وسلسلة (اسم، لون)؛ القيم نسب أو أعداد (المقياس الأكبر)."""
    if not lignes:
        return
    maxi = max([v for _, vals in lignes for v in vals if v is not None] + [1])
    n = len(lignes)
    pas = min(zone.height() / n, 120 * u)
    larg_lib = 300 * u
    x_droite = zone.right() - larg_lib - 20 * u
    larg = x_droite - zone.left() - 150 * u
    hb = pas * 0.62 / len(series)
    for i, (lib, vals) in enumerate(lignes):
        y = zone.top() + i * pas + (zone.height() - n * pas) / 2
        texte(p, QRectF(zone.right() - larg_lib, y, larg_lib, pas * 0.7), lib, 36 * u, BLANC, True)
        for k, ((_, coul), v) in enumerate(zip(series, vals)):
            yb = y + k * hb + pas * 0.04
            fond = QPainterPath()
            fond.addRoundedRect(QRectF(x_droite - larg, yb, larg, hb * 0.82), hb * 0.4, hb * 0.4)
            p.fillPath(fond, QColor(255, 255, 255, 25))
            if v:
                lw = max(hb, larg * v * _P / maxi)
                b = QPainterPath()
                b.addRoundedRect(QRectF(x_droite - lw, yb, lw, hb * 0.82), hb * 0.4, hb * 0.4)
                g = QLinearGradient(QPointF(x_droite, 0), QPointF(x_droite - lw, 0))
                g.setColorAt(0, QColor(coul).darker(130))
                g.setColorAt(1, QColor(coul))
                p.fillPath(b, g)
            t = _pct(v) if (pct if pct is not None else series[0][0].startswith("%")) else _nombre(v)
            texte(p, QRectF(zone.left(), yb - 4 * u, 140 * u, hb), t, min(34 * u, hb * 0.8), BLANC, True,
                  Qt.AlignLeft | Qt.AlignVCenter)
    # مفتاح السلاسل
    if len(series) > 1:
        x = zone.right()
        for nom, coul in series:
            nom = nom.lstrip("%")
            w = QFontMetricsF(_police(28 * u)).horizontalAdvance(nom) + 60 * u
            p.setBrush(QColor(coul))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(QRectF(x - 30 * u, zone.bottom() + 20 * u, 24 * u, 24 * u), 6 * u, 6 * u)
            texte(p, QRectF(x - w, zone.bottom() + 12 * u, w - 40 * u, 40 * u), nom, 28 * u, GRIS_CLAIR)
            x -= w + 30 * u


def _vide(p, zone, u, message: str) -> None:
    texte(p, zone, message, 40 * u, GRIS_CLAIR, False, Qt.AlignCenter)


COULEURS = {"or": DORE_CLAIR, "bleu": BLEU, "rose": ROSE, "violet": VIOLET, "vert": VERT, "orange": ORANGE,
            "rouge": ROUGE}
COUL_AXES = {"eleve": BLEU, "ecole": VERT, "professeur": ORANGE}


def _logo(p: QPainter, chemin: str, r: QRectF) -> bool:
    """شعار المؤسسة داخل المستطيل مع حفظ نسبته."""
    if not chemin:
        return False
    img = QImage(chemin)
    if img.isNull():
        return False
    s = img.size().scaled(int(r.width()), int(r.height()), Qt.KeepAspectRatio)
    cible = QRectF(r.center().x() - s.width() / 2, r.center().y() - s.height() / 2, s.width(), s.height())
    p.drawImage(cible, img)
    return True


def _anneaux(p, zone: QRectF, u, items) -> None:
    couleurs = [DORE_CLAIR, VERT, BLEU, ROSE, ORANGE]
    n = max(1, len(items))
    rayon = min(zone.height() * 0.3, zone.width() / (n * 2.8))
    for k, it in enumerate(items):
        cx = zone.right() - (k + 0.5) * zone.width() / n
        _anneau(p, QPointF(cx, zone.top() + zone.height() * 0.4), rayon, u, it.get("taux"), couleurs[k % 5],
                it["libelle"], it.get("sous", ""))


def _liste(p, zone: QRectF, u, lignes, maxi: int = 6) -> None:
    """بطاقات أسطر: (نص رئيسي، نص ثانوي يساراً، لون الشريط)."""
    lignes = lignes[:maxi]
    if not lignes:
        return
    h = min(115 * u, zone.height() / len(lignes) - 16 * u)
    for k, (t, sous, coul) in enumerate(lignes):
        rr = QRectF(zone.left(), zone.top() + k * (h + 16 * u), zone.width(), h)
        _carte(p, rr, u, coul)
        dessiner_etoile(p, rr.right() - 42 * u, rr.center().y(), 13 * u, coul, pleine=True)
        larg_sous = 420 * u if sous else 0
        texte(p, QRectF(rr.left() + 30 * u + larg_sous, rr.top(), rr.width() - 110 * u - larg_sous, h), t, 36 * u,
              BLANC, True)
        if sous:
            texte(p, QRectF(rr.left() + 30 * u, rr.top(), larg_sous - 20 * u, h), sous, 26 * u, DORE_CLAIR, False,
                  Qt.AlignLeft | Qt.AlignVCenter)


def _colonnes_axes(p, zone: QRectF, u, items) -> None:
    """ثلاثة أعمدة: محور التلميذ، محور المدرسة، محور الأستاذ (من اليمين)."""
    from idara.services.ecran import AXES
    esp = 30 * u
    w = (zone.width() - 2 * esp) / 3
    for k, (axe, lib) in enumerate(AXES):
        x = zone.right() - (k + 1) * w - k * esp
        col = QRectF(x, zone.top(), w, zone.height())
        coul = COUL_AXES[axe]
        _carte(p, col, u, coul)
        texte(p, QRectF(col.left() + 20 * u, col.top() + 24 * u, col.width() - 40 * u, 60 * u), lib, 40 * u, coul,
              True, Qt.AlignCenter)
        y = col.top() + 110 * u
        for it in [i for i in items if i.get("axe") == axe][:5]:
            dessiner_etoile(p, col.right() - 38 * u, y + 26 * u, 10 * u, DORE_CLAIR, pleine=True)
            rr = QRectF(col.left() + 24 * u, y, col.width() - 82 * u, 104 * u)
            texte(p, rr, it["libelle"], 28 * u, BLANC, False, Qt.AlignRight | Qt.AlignTop, ajuster=False)
            y += 112 * u
            if y > col.bottom() - 60 * u:
                break


# ---------- شرائح الدفعة الثالثة (2026-11-22) ----------

SERIES = [BLEU, VERT, ORANGE, VIOLET, ROSE, DORE_CLAIR]
OR, ARGENT, BRONZE = "#F3C64B", "#C9D3DF", "#D08A4E"


def _image_couverte(p: QPainter, chemin: str, r: QRectF, rayon: float) -> bool:
    """صورة تملأ المستطيل (قص من الوسط) بحواف مستديرة."""
    img = QImage(chemin) if chemin else QImage()
    if img.isNull():
        return False
    s = img.size().scaled(int(r.width()) + 1, int(r.height()) + 1, Qt.KeepAspectRatioByExpanding)
    cible = QRectF(r.center().x() - s.width() / 2, r.center().y() - s.height() / 2, s.width(), s.height())
    p.save()
    ch = QPainterPath()
    ch.addRoundedRect(r, rayon, rayon)
    p.setClipPath(ch)
    p.drawImage(cible, img)
    p.restore()
    return True


def _plaque(p: QPainter, chemin: str, r: QRectF, u) -> bool:
    """شعار الوزارة على لوحة بيضاء مستديرة (يُقرأ على الخلفية الليلية)."""
    img = QImage(chemin) if chemin else QImage()
    if img.isNull():
        return False
    s = img.size().scaled(int(r.width() - 40 * u), int(r.height() - 20 * u), Qt.KeepAspectRatio)
    fond = QRectF(r.center().x() - s.width() / 2 - 20 * u, r.top(), s.width() + 40 * u, s.height() + 20 * u)
    ch = QPainterPath()
    ch.addRoundedRect(fond, 16 * u, 16 * u)
    p.fillPath(ch, QColor(255, 255, 255, 240))
    p.setPen(QPen(QColor(DORE), 2 * u))
    p.setBrush(Qt.NoBrush)
    p.drawPath(ch)
    p.drawImage(QRectF(fond.left() + 20 * u, fond.top() + 10 * u, s.width(), s.height()), img)
    return True


def _grille_tuiles(p, zone: QRectF, u, items) -> None:
    """حتى 4 بطاقات في السطر، وسطران على الأكثر."""
    n = len(items)
    if n <= 4:
        _tuiles(p, zone, u, items)
        return
    h = (zone.height() - 30 * u) / 2
    k = (n + 1) // 2
    _tuiles(p, QRectF(zone.left(), zone.top(), zone.width(), h), u, items[:k])
    _tuiles(p, QRectF(zone.left(), zone.top() + h + 30 * u, zone.width(), h), u, items[k:])


def _cartes_niveaux(p, zone: QRectF, u, items) -> None:
    items = items[:8]
    n = len(items)
    cols = 4 if n > 6 else 3 if n > 4 else max(1, n) if n <= 3 else 2 if n == 4 else 3
    lignes = (n + cols - 1) // cols
    esp = 28 * u
    w = (zone.width() - esp * (cols - 1)) / cols
    h = (zone.height() - esp * (lignes - 1)) / lignes
    for k, it in enumerate(items):
        x = zone.right() - (k % cols + 1) * w - (k % cols) * esp
        y = zone.top() + (k // cols) * (h + esp)
        r = QRectF(x, y, w, h)
        _carte(p, r, u, SERIES[k % len(SERIES)])
        texte(p, QRectF(r.left() + 24 * u, r.top() + 18 * u, r.width() - 48 * u, 56 * u), it["libelle"], 40 * u,
              DORE_CLAIR, True)
        texte(p, QRectF(r.left() + 24 * u, r.top() + 18 * u, r.width() - 48 * u, 56 * u),
              f"{_nombre(it['classes'])} أقسام" if it["classes"] != 1 else "قسم واحد", 28 * u, GRIS_CLAIR,
              align=Qt.AlignLeft | Qt.AlignVCenter)
        hv = min(h * 0.38, 150 * u)
        texte(p, QRectF(r.left(), r.top() + 76 * u, r.width(), hv), _nombre(it["eleves"]), hv * 0.8, BLANC, True,
              Qt.AlignCenter)
        # شريط الذكور والإناث
        yb = r.top() + 76 * u + hv + 14 * u
        hb = 30 * u
        larg = r.width() - 60 * u
        tot = (it["garcons"] or 0) + (it["filles"] or 0)
        fg = (it["garcons"] / tot if tot else 0.5) * _P + 0.5 * (1 - _P)
        g = QPainterPath()
        g.addRoundedRect(QRectF(r.left() + 30 * u, yb, larg, hb), hb / 2, hb / 2)
        p.fillPath(g, QColor(ROSE))
        b = QPainterPath()
        b.addRoundedRect(QRectF(r.right() - 30 * u - larg * fg, yb, larg * fg, hb), hb / 2, hb / 2)
        p.fillPath(b, QColor(BLEU))
        y2 = yb + hb + 10 * u
        if y2 + 44 * u <= r.bottom():
            texte(p, QRectF(r.left() + 30 * u, y2, larg, 44 * u),
                  f"ذكور {_nombre(it['garcons'])} · {_pct(it['pct_garcons'])}", 26 * u, BLEU, True)
            texte(p, QRectF(r.left() + 30 * u, y2, larg, 44 * u),
                  f"إناث {_nombre(it['filles'])} · {_pct(it['pct_filles'])}", 26 * u, ROSE, True,
                  Qt.AlignLeft | Qt.AlignVCenter)


def _pyramide(p, zone: QRectF, u, items) -> None:
    """هرم الأعمار: الذكور يميناً والإناث يساراً، والسن في الوسط (الأكبر في الأعلى)."""
    if not items:
        return
    maxi = max([max(i["valeurs"]) for i in items] + [1])
    n = len(items)
    haut_leg = 50 * u
    pas = min((zone.height() - haut_leg) / n, 80 * u)
    cx = zone.center().x()
    col = 170 * u
    larg = zone.width() / 2 - col / 2 - 120 * u
    y0 = zone.top() + haut_leg + (zone.height() - haut_leg - n * pas) / 2
    texte(p, QRectF(cx + col / 2, zone.top(), larg + 100 * u, haut_leg), "ذكور", 34 * u, BLEU, True, Qt.AlignCenter)
    texte(p, QRectF(cx - col / 2 - larg - 100 * u, zone.top(), larg + 100 * u, haut_leg), "إناث", 34 * u, ROSE, True,
          Qt.AlignCenter)
    for k, it in enumerate(items):
        y = y0 + k * pas
        hb = pas * 0.74
        texte(p, QRectF(cx - col / 2, y, col, hb), it["libelle"], min(30 * u, hb * 0.7), DORE_CLAIR, True,
              Qt.AlignCenter)
        g, f = it["valeurs"]
        for v, coul, droite in ((g, BLEU, True), (f, ROSE, False)):
            lw = max(6 * u, larg * (v or 0) * _P / maxi)
            x = cx + col / 2 if droite else cx - col / 2 - lw
            ch = QPainterPath()
            ch.addRoundedRect(QRectF(x, y, lw, hb), hb * 0.3, hb * 0.3)
            p.fillPath(ch, QColor(coul))
            tr = QRectF(x + lw + 10 * u, y, 110 * u, hb) if droite else QRectF(x - 120 * u, y, 110 * u, hb)
            texte(p, tr, _nombre(v), min(30 * u, hb * 0.7), BLANC, True,
                  (Qt.AlignLeft if droite else Qt.AlignRight) | Qt.AlignVCenter)


def _matrice(p, zone: QRectF, u, items, ages) -> None:
    """جدول المستويات (أسطر) والأعمار (أعمدة) بخلايا ملونة حسب العدد."""
    if not items or not ages:
        return
    maxi = max([v for i in items for v in i["par_age"].values()] + [1])
    larg_lib = 260 * u
    nc = len(ages) + 1     # + المجموع
    w = (zone.width() - larg_lib) / nc
    h = min((zone.height() - 20 * u) / (len(items) + 1), 90 * u)
    y = zone.top()
    for j, a in enumerate(list(ages) + ["المجموع"]):
        x = zone.right() - larg_lib - (j + 1) * w
        texte(p, QRectF(x, y, w, h), f"{a} س" if j < len(ages) else a, min(30 * u, h * 0.5), DORE_CLAIR, True,
              Qt.AlignCenter)
    for i, it in enumerate(items):
        y = zone.top() + (i + 1) * h
        texte(p, QRectF(zone.right() - larg_lib, y, larg_lib - 16 * u, h), it["libelle"], min(32 * u, h * 0.5), BLANC,
              True)
        tot = 0
        for j, a in enumerate(ages):
            v = it["par_age"].get(str(a), 0)
            tot += v
            x = zone.right() - larg_lib - (j + 1) * w
            c = QRectF(x + 4 * u, y + 4 * u, w - 8 * u, h - 8 * u)
            ch = QPainterPath()
            ch.addRoundedRect(c, 10 * u, 10 * u)
            coul = QColor(DORE)
            coul.setAlpha(int(25 + 200 * v / maxi) if v else 12)
            p.fillPath(ch, coul)
            if v:
                texte(p, c, _nombre(v), min(30 * u, h * 0.45), BLANC, True, Qt.AlignCenter)
        x = zone.right() - larg_lib - (len(ages) + 1) * w
        texte(p, QRectF(x, y, w, h), _nombre(tot), min(32 * u, h * 0.5), DORE_CLAIR, True, Qt.AlignCenter)


def _podiums(p, zone: QRectF, u, items) -> None:
    """لوحة الشرف: عمود لكل مستوى، والثلاثة الأوائل بميداليات ذهبية وفضية وبرونزية."""
    items = items[:6]
    n = max(1, len(items))
    esp = 24 * u
    w = (zone.width() - esp * (n - 1)) / n
    for k, it in enumerate(items):
        x = zone.right() - (k + 1) * w - k * esp
        col = QRectF(x, zone.top(), w, zone.height())
        _carte(p, col, u, OR)
        texte(p, QRectF(col.left() + 16 * u, col.top() + 20 * u, col.width() - 32 * u, 56 * u), it["libelle"],
              36 * u, DORE_CLAIR, True, Qt.AlignCenter)
        hl = (col.height() - 110 * u) / 3
        for j, (e, coul) in enumerate(zip(it["podium"], (OR, ARGENT, BRONZE))):
            y = col.top() + 90 * u + j * hl
            c = QPointF(col.center().x(), y + 40 * u)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(coul))
            p.drawEllipse(c, 34 * u, 34 * u)
            texte(p, QRectF(c.x() - 34 * u, c.y() - 34 * u, 68 * u, 68 * u), str(j + 1), 40 * u, NUIT, True,
                  Qt.AlignCenter)
            texte(p, QRectF(col.left() + 12 * u, y + 82 * u, col.width() - 24 * u, 48 * u), e["nom"], 32 * u, BLANC,
                  True, Qt.AlignCenter)
            if e.get("classe"):
                texte(p, QRectF(col.left() + 12 * u, y + 128 * u, col.width() - 24 * u, 36 * u), e["classe"], 24 * u,
                      GRIS_CLAIR, False, Qt.AlignCenter)


def _salles(p, zone: QRectF, u, items, heure: str) -> None:
    lignes = []
    for it in items:
        quoi = " · ".join(v for v in (it["classe"], it["matiere"]) if v)
        if it["etat"] == "en_cours":
            sous, coul = (f"القاعة {it['salle']}" if it["salle"] else "في القسم") + f" · حتى {it['fin']}", VERT
        elif it["etat"] == "prochaine":
            sous, coul = f"تبدأ {it['debut']}" + (f" · القاعة {it['salle']}" if it["salle"] else ""), ORANGE
        else:
            sous, coul = "أنهى(ت) حصص اليوم", GRIS_CLAIR
        lignes.append((f"{it['libelle']}" + (f"  —  {quoi}" if quoi else ""), sous, coul))
    texte(p, QRectF(zone.left(), zone.top() - 70 * u, 500 * u, 50 * u), f"الساعة {heure}", 34 * u, DORE_CLAIR, True,
          Qt.AlignLeft | Qt.AlignVCenter)
    _liste(p, zone, u, lignes, 7)


def _equipements(p, zone: QRectF, u, items) -> None:
    items = items[:8]
    n = len(items)
    cols = 4 if n > 6 else 3 if n > 4 else max(1, min(n, 4))
    lignes = (n + cols - 1) // cols
    esp = 26 * u
    w = (zone.width() - esp * (cols - 1)) / cols
    h = (zone.height() - esp * (lignes - 1)) / lignes
    for k, it in enumerate(items):
        x = zone.right() - (k % cols + 1) * w - (k % cols) * esp
        r = QRectF(x, zone.top() + (k // cols) * (h + esp), w, h)
        coul = SERIES[k % len(SERIES)]
        if it.get("photo") and _image_couverte(p, it["photo"], r, 26 * u):
            bas = QRectF(r.left(), r.bottom() - 110 * u, r.width(), 110 * u)
            g = QLinearGradient(bas.topLeft(), bas.bottomLeft())
            g.setColorAt(0, QColor(11, 28, 44, 0))
            g.setColorAt(1, QColor(11, 28, 44, 235))
            ch = QPainterPath()
            ch.addRoundedRect(bas, 26 * u, 26 * u)
            p.fillPath(ch, g)
            texte(p, QRectF(r.left() + 20 * u, r.bottom() - 70 * u, r.width() - 140 * u, 56 * u), it["libelle"],
                  30 * u, BLANC, True)
            texte(p, QRectF(r.left() + 20 * u, r.bottom() - 80 * u, 110 * u, 70 * u), _nombre(it["valeur"]), 56 * u,
                  coul, True, Qt.AlignLeft | Qt.AlignVCenter)
            p.setPen(QPen(QColor(coul), 3 * u))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(r, 26 * u, 26 * u)
        else:
            _tuile(p, r, u, _nombre(it["valeur"]), it["libelle"], coul)


def _galerie(p, zone: QRectF, u, items) -> None:
    """فسيفساء حتى ست صور مع اسم النشاط تحت كل صورة."""
    photos = [(ph, it["libelle"]) for it in items for ph in it["photos"]][:6]
    n = len(photos)
    if not n:
        return
    cols = 3 if n > 4 else 2 if n > 1 else 1
    lignes = (n + cols - 1) // cols
    esp = 22 * u
    w = (zone.width() - esp * (cols - 1)) / cols
    h = (zone.height() - esp * (lignes - 1)) / lignes
    for k, (ch, lib) in enumerate(photos):
        r = QRectF(zone.right() - (k % cols + 1) * w - (k % cols) * esp, zone.top() + (k // cols) * (h + esp), w, h)
        if not _image_couverte(p, ch, r, 22 * u):
            _carte(p, r, u)
        bande = QRectF(r.left(), r.bottom() - 58 * u, r.width(), 58 * u)
        cc = QPainterPath()
        cc.addRoundedRect(bande, 18 * u, 18 * u)
        p.fillPath(cc, QColor(11, 28, 44, 200))
        texte(p, bande.adjusted(18 * u, 0, -18 * u, 0), lib, 28 * u, DORE_CLAIR, True)
        p.setPen(QPen(QColor(DORE), 2.5 * u))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r, 22 * u, 22 * u)


def _etoile(p, r: QRectF, u, it: dict) -> None:
    """شهادة نجم الأسبوع بإطار ذهبي مزدوج وصورة كبيرة."""
    cad = r.adjusted(150 * u, 250 * u, -150 * u, -150 * u)
    fond = QPainterPath()
    fond.addRoundedRect(cad, 30 * u, 30 * u)
    g = QLinearGradient(cad.topLeft(), cad.bottomRight())
    g.setColorAt(0, QColor("#FFF8E1"))
    g.setColorAt(1, QColor("#F6E2A8"))
    p.fillPath(fond, g)
    for marge, ep in ((0, 10), (22, 3)):
        p.setPen(QPen(QColor("#B8862B"), ep * u))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(cad.adjusted(marge * u, marge * u, -marge * u, -marge * u), 26 * u, 26 * u)
    for x, y in ((cad.left() + 60 * u, cad.top() + 60 * u), (cad.right() - 60 * u, cad.top() + 60 * u),
                 (cad.left() + 60 * u, cad.bottom() - 60 * u), (cad.right() - 60 * u, cad.bottom() - 60 * u)):
        dessiner_etoile(p, x, y, 22 * u, "#B8862B", pleine=True)
    # الصورة يميناً
    ph = QRectF(cad.right() - 470 * u, cad.top() + 70 * u, 380 * u, cad.height() - 140 * u)
    if not (it.get("photo") and _image_couverte(p, it["photo"], ph, 24 * u)):
        ch = QPainterPath()
        ch.addRoundedRect(ph, 24 * u, 24 * u)
        p.fillPath(ch, QColor(NUIT))
        dessiner_etoile(p, ph.center().x(), ph.center().y(), 110 * u, DORE_CLAIR, pleine=True)
    p.setPen(QPen(QColor("#B8862B"), 6 * u))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(ph, 24 * u, 24 * u)
    t = QRectF(cad.left() + 90 * u, cad.top() + 70 * u, ph.left() - cad.left() - 130 * u, cad.height() - 140 * u)
    texte(p, QRectF(t.left(), t.top(), t.width(), 90 * u), "شهادة تقدير", 76 * u, "#8A5A00", True, Qt.AlignCenter)
    texte(p, QRectF(t.left(), t.top() + 110 * u, t.width(), 50 * u), "تُهنّئ أسرة المؤسسة", 32 * u, "#5D4A1F", False,
          Qt.AlignCenter)
    texte(p, QRectF(t.left(), t.top() + 170 * u, t.width(), 110 * u), it["libelle"], 84 * u, NUIT, True,
          Qt.AlignCenter)
    if it.get("classe"):
        texte(p, QRectF(t.left(), t.top() + 285 * u, t.width(), 50 * u), f"القسم: {it['classe']}", 34 * u, "#5D4A1F",
              True, Qt.AlignCenter)
    if it.get("motif"):
        texte(p, QRectF(t.left() + 20 * u, t.top() + 350 * u, t.width() - 40 * u, t.height() - 370 * u), it["motif"],
              36 * u, "#3E2F10", False, Qt.AlignHCenter | Qt.AlignTop, ajuster=False)


def _mouvements(p, zone: QRectF, u, items) -> None:
    n = max(1, len(items))
    rayon = min(zone.height() * 0.3, zone.width() / (n * 2.8))
    for k, it in enumerate(items):
        cx = zone.right() - (k + 0.5) * zone.width() / n
        _anneau(p, QPointF(cx, zone.top() + zone.height() * 0.4), rayon, u, it.get("taux"),
                COULEURS.get(it.get("couleur"), DORE_CLAIR), it["libelle"],
                (_pct(it.get("taux")) + " من المتمدرسين · " if it.get("taux") is not None else "") + it.get("sous", ""),
                centre=_nombre(it["valeur"]))


def peindre(p: QPainter, r: QRectF, d: dict, ident: dict, le: datetime | None = None, progres: float = 1.0) -> None:
    """يرسم شريحة كاملة في المستطيل r (أي حجم، بنسبة 16:9 مستحسنة). progres<1: حركة العدادات."""
    global _P
    _P = max(0.0, min(1.0, progres))
    try:
        _peindre(p, r, d, ident, le)
    finally:
        _P = 1.0


def _peindre(p: QPainter, r: QRectF, d: dict, ident: dict, le: datetime | None = None) -> None:
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.TextAntialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    u = min(r.width() / LARGEUR, r.height() / HAUTEUR)
    _fond(p, r, u)
    cle = d["cle"]
    items = d.get("items", [])
    if cle == "couverture":
        haut = r.top() + 50 * u
        if _plaque(p, ident.get("ministere", ""), QRectF(r.center().x() - 330 * u, haut, 660 * u, 100 * u), u):
            haut += 105 * u
        if not _logo(p, ident.get("logo", ""), QRectF(r.center().x() - 90 * u, haut, 180 * u, 130 * u)):
            dessiner_etoile(p, r.center().x(), haut + 65 * u, 50 * u, DORE, pleine=False)
        haut += 135 * u
        texte(p, QRectF(r.left() + 80 * u, haut, r.width() - 160 * u, 100 * u), ident.get("nom", ""),
              78 * u, DORE_CLAIR, True, Qt.AlignCenter)
        texte(p, QRectF(r.left() + 80 * u, haut + 95 * u, r.width() - 160 * u, 54 * u),
              f"الموسم الدراسي {ident.get('annee', '')}  ·  مؤسستنا بالأرقام", 34 * u, GRIS_CLAIR, False,
              Qt.AlignCenter)
        zone = QRectF(r.left() + 90 * u, haut + 170 * u, r.width() - 180 * u, r.bottom() - 170 * u - haut - 170 * u)
        if items:
            _tuiles(p, zone, u, [(_nombre(i["valeur"]), i["libelle"], COULEURS.get(i.get("couleur"), DORE_CLAIR),
                                  i.get("sous", "")) for i in items])
    else:
        zone = _entete(p, r, u, d, ident)
        if d.get("vide"):
            _vide(p, zone, u, "لا معطيات بعد لهذه الشريحة.")
        elif cle == "niveaux":
            _barres(p, zone, u, [(i["libelle"], i["valeurs"]) for i in items], [("ذكور", BLEU), ("إناث", ROSE)])
        elif cle == "tarl":
            _barres(p, zone, u, [(i["libelle"], i["valeurs"]) for i in items],
                    [("%الرائز القبلي", ORANGE), ("%الرائز البعدي", VERT)])
        elif cle in ("maitrise", "resultats"):
            _anneaux(p, zone, u, items)
        elif cle == "mouvements":
            _mouvements(p, zone, u, items)
        elif cle == "indicateurs":
            _grille_tuiles(p, zone, u, [(str(i["valeur"]), i["libelle"], SERIES[k % len(SERIES)], i.get("sous", ""))
                                        for k, i in enumerate(items)])
        elif cle == "cartes_niveaux":
            _cartes_niveaux(p, zone, u, items)
        elif cle == "pyramide":
            _pyramide(p, zone, u, items)
        elif cle == "ages":
            _matrice(p, zone, u, items, d.get("ages", []))
        elif cle == "acquis":
            _barres(p, zone, u, [(i["libelle"], i["valeurs"]) for i in items],
                    [("%تحكم تام", VERT), ("%تحكم مقنع", ORANGE), ("%تحكم ضعيف", ROUGE)])
            if d.get("phase"):
                texte(p, QRectF(zone.left(), zone.top() - 70 * u, 700 * u, 50 * u), d["phase"], 30 * u, DORE_CLAIR,
                      True, Qt.AlignLeft | Qt.AlignVCenter)
        elif cle == "isa":
            _barres(p, zone, u, [(i["libelle"], i["valeurs"]) for i in items],
                    [("%" + ph, SERIES[k % len(SERIES)]) for k, ph in enumerate(d.get("phases", []))])
        elif cle == "examens":
            _barres(p, zone, u, [(f"{i['libelle']} · المعدل {i['moyenne']:.2f}", i["valeurs"]) for i in items],
                    [("%نسبة النجاح", VERT)])
        elif cle == "honneur":
            _podiums(p, zone, u, items)
        elif cle == "salles":
            _salles(p, zone, u, items, d.get("heure", ""))
        elif cle == "equipements":
            _equipements(p, zone, u, items)
        elif cle == "galerie":
            _galerie(p, zone, u, items)
        elif cle == "etoile":
            _etoile(p, r, u, items[0])
        elif cle == "annonces":
            _liste(p, zone, u, [(i["libelle"] + (f": {i['texte']}" if i.get("texte") else ""), i.get("date", ""),
                                 SERIES[k % len(SERIES)]) for k, i in enumerate(items)])
        elif cle == "projet":
            bande = QRectF(zone.left(), zone.top(), zone.width(), 120 * u)
            _carte(p, bande, u, DORE)
            texte(p, QRectF(bande.left() + 420 * u, bande.top(), bande.width() - 460 * u, bande.height()),
                  d.get("intitule", ""), 34 * u, DORE_CLAIR, True)
            texte(p, QRectF(bande.left() + 30 * u, bande.top(), 400 * u, bande.height()),
                  f"أُنجز {d.get('realisees', 0)} من {d.get('actives', 0)} عملية · {_pct(d.get('pct_realisees'))}",
                  30 * u, BLANC, True, Qt.AlignLeft | Qt.AlignVCenter)
            reste = QRectF(zone.left(), zone.top() + 145 * u, zone.width(), zone.height() - 145 * u)
            _liste(p, reste, u, [(i["libelle"], i.get("axe", ""), VERT) for i in items], 5)
        elif cle == "realisations":
            _colonnes_axes(p, zone, u, items)
        elif cle == "partenariats":
            _liste(p, zone, u, [(f"{i['libelle']}: {i['objet']}", i.get("etat", ""), BLEU) for i in items])
    # التذييل: الساعة والتاريخ، والشعار صغيراً في الشرائح الداخلية
    le = le or datetime.now()
    texte(p, QRectF(r.left() + 60 * u, r.bottom() - 125 * u, 600 * u, 50 * u),
          f"{le:%H:%M}  ·  {tx.date_ar(le.date().isoformat())}", 28 * u, GRIS_CLAIR, False,
          Qt.AlignLeft | Qt.AlignVCenter)
    if cle != "couverture":
        _logo(p, ident.get("logo", ""), QRectF(r.right() - 190 * u, r.bottom() - 190 * u, 130 * u, 100 * u))
    p.restore()


def peindre_bandeau(p: QPainter, r: QRectF, u: float, t: str, decalage: float) -> None:
    """الشريط المتحرك أسفل الشاشة (ينساب من اليسار إلى اليمين كقراءة العربية)."""
    p.save()
    ch = QPainterPath()
    ch.addRect(r)
    p.fillPath(ch, QColor(201, 160, 74, 235))
    p.setClipRect(r)
    f = _police(34 * u, True)
    p.setFont(f)
    p.setPen(QColor(NUIT))
    fm = QFontMetricsF(f)
    motif = t + "   ·   "
    w = max(1.0, fm.horizontalAdvance(motif))
    x = r.left() - w + (decalage % w)
    o = QTextOption(Qt.AlignVCenter | Qt.AlignLeft)
    o.setTextDirection(Qt.RightToLeft)
    while x < r.right():
        p.drawText(QRectF(x, r.top(), w, r.height()), motif, o)
        x += w
    p.restore()


def image(d: dict, ident: dict, largeur: int = LARGEUR, hauteur: int = HAUTEUR, bandeau: str = "",
          le: datetime | None = None, progres: float = 1.0) -> QImage:
    img = QImage(largeur, hauteur, QImage.Format_ARGB32)
    img.fill(QColor(NUIT))
    p = QPainter(img)
    r = QRectF(0, 0, largeur, hauteur)
    peindre(p, r, d, ident, le, progres)
    if bandeau:
        u = min(largeur / LARGEUR, hauteur / HAUTEUR)
        peindre_bandeau(p, QRectF(0, hauteur - 70 * u, largeur, 70 * u), u, bandeau, 0)
    p.end()
    return img


def exporter_images(diapos: list[dict], ident: dict, dossier: Path, bandeau: str = "") -> list[Path]:
    """صور PNG بدقة 1920×1080 مرقمة بالترتيب (للعرض من مفتاح USB على التلفاز)."""
    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    res = []
    for k, d in enumerate(diapos, start=1):
        ch = dossier / f"{k:02d} - {d['titre']}.png"
        image(d, ident, bandeau=bandeau).save(str(ch))
        res.append(ch)
    return res


def exporter_pdf(diapos: list[dict], ident: dict, chemin: Path, bandeau: str = "") -> Path:
    """ملف PDF: شريحة في كل صفحة أفقية."""
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    w = QPdfWriter(str(chemin))
    w.setPageSize(QPageSize(QPageSize.A4))
    w.setPageOrientation(QPageLayout.Landscape)
    w.setPageMargins(QMarginsF(0, 0, 0, 0))
    w.setResolution(150)
    w.setTitle(f"شاشة العرض · {ident.get('nom', '')}")
    p = QPainter(w)
    for k, d in enumerate(diapos):
        if k:
            w.newPage()
        pr = QRectF(p.viewport())
        h = pr.width() * 9 / 16
        r = QRectF(pr.left(), pr.top() + (pr.height() - h) / 2, pr.width(), h) if h <= pr.height() else pr
        p.fillRect(pr, QColor(NUIT))
        p.drawImage(r, image(d, ident, bandeau=bandeau))
    p.end()
    return chemin


def exporter_ppt(diapos: list[dict], ident: dict, chemin: Path, bandeau: str = "") -> Path:
    """عرض PowerPoint (16:9): كل شريحة صورة بملء الصفحة، تُعرض في أي حاسوب أو تلفاز ذكي."""
    import io
    try:
        from pptx import Presentation
        from pptx.util import Emu
    except ImportError as e:
        raise RuntimeError("مكتبة PowerPoint غير مثبتة في هذه النسخة.") from e
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    prs = Presentation()
    prs.slide_width, prs.slide_height = Emu(12192000), Emu(6858000)
    vide = prs.slide_layouts[6]
    for d in diapos:
        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QIODevice.WriteOnly)
        image(d, ident, bandeau=bandeau).save(buf, "PNG")
        buf.close()
        sl = prs.slides.add_slide(vide)
        sl.shapes.add_picture(io.BytesIO(bytes(ba)), 0, 0, prs.slide_width, prs.slide_height)
        if d.get("duree"):
            sl.notes_slide.notes_text_frame.text = f"{d['titre']} · {d['duree']} ثانية"
    prs.core_properties.title = f"شاشة العرض · {ident.get('nom', '')}"
    prs.save(str(chemin))
    return chemin


ANIMATION = 1.4   # ثوانٍ: مدة عدّ الأرقام وامتلاء الحلقات عند ظهور الشريحة
# شرائح بلا أرقام تُعدّ (أو بصور ثقيلة): تظهر مباشرة
SANS_ANIMATION = {"galerie", "etoile", "annonces", "salles", "equipements", "realisations", "partenariats", "honneur"}


class FenetreAffichage(QWidget):
    """العرض بملء الشاشة: الشرائح تتوالى، شريط متحرك أسفلها، خط تقدم ذهبي، ونقاط الشرائح.
    الأسهم/المسافة/Esc وجهاز التحكم عن بعد (أسهم وصفحة تالية/سابقة) للتحكم؛ النقر للشريحة التالية."""

    def __init__(self, conn, diapos: list[dict], ident: dict, bandeau: str = "", ecran=None, dossier=None):
        super().__init__(None, Qt.Window | Qt.FramelessWindowHint)
        self.dossier = dossier
        self.conn, self.diapos, self.ident, self.bandeau = conn, diapos, ident, bandeau
        self.setWindowTitle("شاشة العرض")
        self.setCursor(Qt.BlankCursor)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.indice, self.ecoule, self.pause = 0, 0.0, False
        self.decalage = 0.0
        self.fondu = 1.0
        self.precedente = None
        self._images: dict[int, QImage] = {}
        self.minuterie = QTimer(self)
        self.minuterie.timeout.connect(self._tic)
        self.minuterie.start(33)
        self.ecran = ecran

    def ouvrir(self):
        if self.ecran is not None:
            self.setGeometry(self.ecran.geometry())
        self.showFullScreen()
        return self

    def _image(self, i: int) -> QImage:
        if i not in self._images:
            self._images[i] = image(self.diapos[i], self.ident, max(640, self.width()), max(360, self.height()))
        return self._images[i]

    def aller(self, i: int) -> None:
        if not self.diapos:
            return
        self.precedente = self._image(self.indice) if self.isVisible() else None
        self.indice = i % len(self.diapos)
        d = self.diapos[self.indice]
        if self.conn is not None and d.get("cle") in DYNAMIQUES:   # «أين الأساتذة الآن»: حساب جديد
            try:
                from idara.services import ecran as ec
                nd = ec.diapositive(self.conn, d["cle"], datetime.now(), dossier=self.dossier)
                nd["duree"] = d.get("duree", 12)
                self.diapos[self.indice] = nd
            except Exception:  # noqa: BLE001 — يبقى المحتوى السابق
                pass
        self.ecoule = 0.0
        self.fondu = 0.0 if self.precedente is not None else 1.0
        self._images.pop(self.indice, None)   # معطيات حية: إعادة الرسم عند كل ظهور
        self.update()

    def suivante(self) -> None:
        self.aller(self.indice + 1)

    def _tic(self) -> None:
        dt = 0.033
        self.decalage += 90 * dt * max(0.5, self.height() / HAUTEUR)
        if self.fondu < 1:
            self.fondu = min(1.0, self.fondu + dt / 0.6)
        if not self.pause and self.diapos:
            self.ecoule += dt
            if self.ecoule >= self.diapos[self.indice].get("duree", 12):
                self.suivante()
        self.update()

    def resizeEvent(self, e):   # noqa: N802
        self._images.clear()
        super().resizeEvent(e)

    def paintEvent(self, e):   # noqa: N802
        p = QPainter(self)
        r = QRectF(self.rect())
        p.fillRect(r, QColor(NUIT))
        if not self.diapos:
            p.end()
            return
        if self.precedente is not None and self.fondu < 1:
            p.drawImage(r, self.precedente)
            p.setOpacity(self.fondu)
        if self.ecoule < ANIMATION and self.diapos[self.indice].get("cle") not in SANS_ANIMATION:   # العدادات المتحركة: رسم مباشر أثناء الحركة
            t = self.ecoule / ANIMATION
            p.drawImage(r, image(self.diapos[self.indice], self.ident, max(640, self.width()),
                                 max(360, self.height()), progres=1 - (1 - t) ** 3))
        else:
            p.drawImage(r, self._image(self.indice))
        p.setOpacity(1)
        u = min(r.width() / LARGEUR, r.height() / HAUTEUR)
        hb = 70 * u
        if self.bandeau:
            peindre_bandeau(p, QRectF(0, r.height() - hb, r.width(), hb), u, self.bandeau, self.decalage)
        # خط التقدم الذهبي ونقاط الشرائح
        d = self.diapos[self.indice].get("duree", 12)
        y = r.height() - hb - 8 * u
        p.fillRect(QRectF(0, y, r.width(), 6 * u), QColor(255, 255, 255, 30))
        p.fillRect(QRectF(r.width() * (1 - min(1.0, self.ecoule / d)), y, r.width(), 6 * u), QColor(DORE))
        n = len(self.diapos)
        for k in range(n):
            cx = r.width() / 2 + (n / 2 - k - 0.5) * 28 * u
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(DORE_CLAIR) if k == self.indice else QColor(255, 255, 255, 70))
            p.drawEllipse(QPointF(cx, y - 24 * u), 7 * u, 7 * u)
        if self.pause:
            texte(p, QRectF(40 * u, 40 * u, 400 * u, 50 * u), "متوقف مؤقتاً", 30 * u, DORE_CLAIR, True,
                  Qt.AlignLeft | Qt.AlignVCenter)
        p.end()

    def keyPressEvent(self, e):   # noqa: N802
        k = e.key()
        if k == Qt.Key_Escape:
            self.close()
        elif k in (Qt.Key_Left, Qt.Key_PageDown, Qt.Key_Down, Qt.Key_Return, Qt.Key_Enter):
            self.suivante()   # في العربية: اليسار هو التالي
        elif k in (Qt.Key_Right, Qt.Key_PageUp, Qt.Key_Up, Qt.Key_Backspace):
            self.aller(self.indice - 1)
        elif k in (Qt.Key_Space, Qt.Key_P, Qt.Key_MediaPlay, Qt.Key_MediaPause, Qt.Key_MediaTogglePlayPause):
            self.pause = not self.pause
        elif k == Qt.Key_Home:
            self.aller(0)
        else:
            super().keyPressEvent(e)

    def mouseReleaseEvent(self, e):   # noqa: N802
        if e.button() == Qt.LeftButton:
            self.suivante()
        elif e.button() == Qt.RightButton:
            self.aller(self.indice - 1)


def ecrans() -> list:
    return list(QGuiApplication.screens())

