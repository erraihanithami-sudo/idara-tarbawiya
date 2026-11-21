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


def _nombre(v) -> str:
    return "—" if v is None else (f"{v:.0f}" if isinstance(v, float) and v == int(v) else str(v))


def _pct(v) -> str:
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
    texte(p, QRectF(r.left() + 60 * u, r.top() + 120 * u, r.width() - 190 * u, 70 * u), d["titre"], 56 * u, BLANC,
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


def _anneau(p, c: QPointF, rayon: float, u, taux, accent: str, libelle: str, sous: str = "") -> None:
    p.setPen(QPen(QColor(255, 255, 255, 40), 26 * u, Qt.SolidLine, Qt.FlatCap))
    p.setBrush(Qt.NoBrush)
    rr = QRectF(c.x() - rayon, c.y() - rayon, 2 * rayon, 2 * rayon)
    p.drawEllipse(rr)
    if taux is not None:
        p.setPen(QPen(QColor(accent), 26 * u, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(rr, 90 * 16, -int(360 * 16 * max(0.0, min(100.0, taux)) / 100))
    texte(p, QRectF(c.x() - rayon, c.y() - 60 * u, 2 * rayon, 120 * u), _pct(taux), 84 * u, BLANC, True,
          Qt.AlignCenter)
    texte(p, QRectF(c.x() - rayon - 80 * u, c.y() + rayon + 30 * u, 2 * rayon + 160 * u, 54 * u), libelle, 36 * u,
          DORE_CLAIR, True, Qt.AlignCenter)
    if sous:
        texte(p, QRectF(c.x() - rayon - 80 * u, c.y() + rayon + 84 * u, 2 * rayon + 160 * u, 40 * u), sous, 24 * u,
              GRIS_CLAIR, False, Qt.AlignCenter)


def _barres(p, zone: QRectF, u, lignes, series) -> None:
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
                lw = max(hb, larg * v / maxi)
                b = QPainterPath()
                b.addRoundedRect(QRectF(x_droite - lw, yb, lw, hb * 0.82), hb * 0.4, hb * 0.4)
                g = QLinearGradient(QPointF(x_droite, 0), QPointF(x_droite - lw, 0))
                g.setColorAt(0, QColor(coul).darker(130))
                g.setColorAt(1, QColor(coul))
                p.fillPath(b, g)
            t = _pct(v) if series[0][0].startswith("%") else _nombre(v)
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


def peindre(p: QPainter, r: QRectF, d: dict, ident: dict, le: datetime | None = None) -> None:
    """يرسم شريحة كاملة في المستطيل r (أي حجم، بنسبة 16:9 مستحسنة)."""
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.TextAntialiasing)
    u = min(r.width() / LARGEUR, r.height() / HAUTEUR)
    _fond(p, r, u)
    cle = d["cle"]
    if cle == "couverture":
        dessiner_etoile(p, r.center().x(), r.top() + 170 * u, 60 * u, DORE, pleine=False)
        texte(p, QRectF(r.left() + 80 * u, r.top() + 240 * u, r.width() - 160 * u, 110 * u), ident.get("nom", ""),
              84 * u, DORE_CLAIR, True, Qt.AlignCenter)
        texte(p, QRectF(r.left() + 80 * u, r.top() + 350 * u, r.width() - 160 * u, 60 * u),
              f"الموسم الدراسي {ident.get('annee', '')}  ·  مؤسستنا بالأرقام", 36 * u, GRIS_CLAIR, False,
              Qt.AlignCenter)
        zone = QRectF(r.left() + 90 * u, r.top() + 430 * u, r.width() - 180 * u, 470 * u)
        _tuiles(p, zone, u, [(_nombre(d.get("eleves")), "تلميذة وتلميذاً", DORE_CLAIR, "مجموع المتمدرسين"),
                             (_nombre(d.get("garcons")), "ذكور", BLEU, ""),
                             (_nombre(d.get("filles")), "إناث", ROSE, ""),
                             (_nombre(d.get("classes")), "قسماً", VIOLET, ""),
                             (_nombre(d.get("personnel")), "إطاراً", VERT, "تربوياً وإدارياً")])
    else:
        zone = _entete(p, r, u, d, ident)
        if d.get("vide"):
            _vide(p, zone, u, "لا معطيات بعد لهذه الشريحة.")
        elif cle == "niveaux":
            lignes = [(n["libelle"], [n["garcons"], n["filles"]]) for n in d["niveaux"]]
            _barres(p, zone, u, lignes, [("ذكور", BLEU), ("إناث", ROSE)])
        elif cle == "mouvements":
            _tuiles(p, zone, u, [(_nombre(d["arrive"]), "وافدون", VERT, "التحقوا بمؤسستنا"),
                                 (_nombre(d["parti"]), "مغادرون", ORANGE, "انتقلوا إلى مؤسسات أخرى"),
                                 (_nombre(d["interrompu"]), "منقطعون", ROUGE, "نتابعهم لإرجاعهم"),
                                 (_nombre(d["exclu"]), "مفصولون", VIOLET, "")])
        elif cle == "resultats":
            items = ([(m["taux"], m["libelle"], m["epreuve"]) for m in d["matieres"]] if d.get("mode") == "maitrise"
                     else [(d.get("taux"), "نسبة النجاح", d.get("source", ""))])
            if d.get("activites") is not None:
                items.append((d["activites"], "المستفيدون من الأنشطة", "الأندية والأنشطة"))
            couleurs = [DORE_CLAIR, VERT, BLEU, ROSE]
            n = len(items)
            rayon = min(zone.height() * 0.3, zone.width() / (n * 2.8))
            for k, (taux, lib, sous) in enumerate(items):
                cx = zone.right() - (k + 0.5) * zone.width() / n
                _anneau(p, QPointF(cx, zone.top() + zone.height() * 0.4), rayon, u, taux, couleurs[k % 4], lib, sous)
        elif cle == "tarl":
            lignes = [(n["libelle"], [n["pre"], n["post"]]) for n in d["niveaux"]]
            _barres(p, zone, u, lignes, [("%الرائز القبلي", ORANGE), ("%الرائز البعدي", VERT)])
        elif cle == "actualites":
            h = min(110 * u, zone.height() / max(1, len(d["items"])) - 16 * u)
            for k, it in enumerate(d["items"]):
                rr = QRectF(zone.left(), zone.top() + k * (h + 16 * u), zone.width(), h)
                _carte(p, rr, u, VERT if it["en_cours"] else DORE)
                d1, d2 = tx.date_chiffres(it["debut"]), tx.date_chiffres(it["fin"])
                quand = d1 if d1 == d2 else f"من {d1} إلى {d2}"
                texte(p, QRectF(rr.left() + 320 * u, rr.top(), rr.width() - 370 * u, h), it["titre"], 38 * u, BLANC,
                      True)
                texte(p, QRectF(rr.left() + 30 * u, rr.top(), 300 * u, h),
                      "جارية الآن" if it["en_cours"] else quand, 28 * u, VERT if it["en_cours"] else DORE_CLAIR,
                      True, Qt.AlignLeft | Qt.AlignVCenter)
    # التذييل: الساعة والتاريخ
    le = le or datetime.now()
    texte(p, QRectF(r.left() + 60 * u, r.bottom() - 125 * u, 600 * u, 50 * u),
          f"{le:%H:%M}  ·  {tx.date_ar(le.date().isoformat())}", 28 * u, GRIS_CLAIR, False,
          Qt.AlignLeft | Qt.AlignVCenter)
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
          le: datetime | None = None) -> QImage:
    img = QImage(largeur, hauteur, QImage.Format_ARGB32)
    img.fill(QColor(NUIT))
    p = QPainter(img)
    r = QRectF(0, 0, largeur, hauteur)
    peindre(p, r, d, ident, le)
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


class FenetreAffichage(QWidget):
    """العرض بملء الشاشة: الشرائح تتوالى، شريط متحرك أسفلها، خط تقدم ذهبي، ونقاط الشرائح.
    الأسهم/المسافة/Esc وجهاز التحكم عن بعد (أسهم وصفحة تالية/سابقة) للتحكم؛ النقر للشريحة التالية."""

    def __init__(self, conn, diapos: list[dict], ident: dict, bandeau: str = "", ecran=None):
        super().__init__(None, Qt.Window | Qt.FramelessWindowHint)
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

