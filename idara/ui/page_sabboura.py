"""صفحة «السبورة المرجعية» (القيادة والتدبير؛ نماذج المدير 2026-11-13): إحدى عشرة لوحة تُملأ من البرنامج وتُعدَّل،
وتُولَّد على شكل النموذج: ترويسة المؤسسة، شريط العنوان البرتقالي، وجدول برأس أزرق."""

from __future__ import annotations

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter, QPainterPath, QPolygonF
from PySide6.QtWidgets import (QAbstractItemView, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QPushButton, QTableWidgetItem, QVBoxLayout, QWidget)

from idara import marque
from idara.services import bureautique
from idara.services import sabboura as sb
from idara.ui import theme
from idara.ui.composants import bouton, carte
from idara.ui.formulaires import etiquette
from idara.ui.page_pedagogie import _page
from idara.ui.saisie import TableauRapide, message


def ruban_png(titre: str, largeur: int = 1300, hauteur: int = 230) -> bytes:
    """شريط العنوان كما في النموذج: شريط برتقالي مستدير، وعلى يمينه دائرة بيضاء فيها رمز البرنامج، والعنوان بخط عريض."""
    img = QImage(largeur, hauteur, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.TextAntialiasing)
    marge = 14
    bande = QRectF(marge, hauteur * 0.22, largeur - 2 * marge - hauteur * 0.35, hauteur * 0.62)
    ombre = QPainterPath()
    ombre.addRoundedRect(bande.translated(6, 8), bande.height() / 2, bande.height() / 2)
    p.fillPath(ombre, QColor(0, 0, 0, 45))
    g = QLinearGradient(bande.topLeft(), bande.bottomLeft())
    g.setColorAt(0, QColor("#FFC24D"))
    g.setColorAt(1, QColor("#F08A00"))
    chemin = QPainterPath()
    chemin.addRoundedRect(bande, bande.height() / 2, bande.height() / 2)
    p.fillPath(chemin, g)
    # الدائرة على اليمين (جهة البداية في العربية)
    r = hauteur * 0.46
    centre = QPointF(largeur - marge - r, hauteur / 2)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("white"))
    p.drawEllipse(centre, r, r)
    p.setBrush(QColor("#F08A00"))
    p.drawEllipse(centre, r * 0.86, r * 0.86)
    p.setBrush(QColor("white"))
    p.drawEllipse(centre, r * 0.78, r * 0.78)
    cote = r * 1.1
    k = cote / marque.COTE
    x0, y0 = centre.x() - cote / 2, centre.y() - cote / 2
    for nature, couleur, geo in marque.formes(False):
        p.setBrush(QColor(couleur))
        if nature in ("tuile", "rect"):
            a, b, c, d, rr = geo
            p.drawRoundedRect(QRectF(x0 + a * k, y0 + b * k, (c - a) * k, (d - b) * k), rr * k, rr * k)
        else:
            p.drawPolygon(QPolygonF([QPointF(x0 + x * k, y0 + y * k) for x, y in geo]))
    # العنوان
    f = QFont(theme.police_titres() or "Arial")
    f.setPixelSize(int(bande.height() * 0.48))
    f.setBold(True)
    p.setFont(f)
    p.setPen(QColor("#1B1B3A"))
    zone = QRectF(bande.left() + 30, bande.top(), centre.x() - r - bande.left() - 50, bande.height())
    p.drawText(zone, Qt.AlignCenter | Qt.TextSingleLine, titre)
    p.end()
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "PNG")
    buf.close()
    return bytes(ba)


def _item(v: str) -> QTableWidgetItem:
    it = QTableWidgetItem(v)
    it.setTextAlignment(Qt.AlignCenter)
    return it


class PageSabboura(QWidget):
    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        self.cle: str | None = None
        self.editeurs: dict[str, QLineEdit] = {}
        self._anciens: list[QWidget] = []
        self.table: TableauRapide | None = None
        self.note: QLineEdit | None = None
        racine, self.message = _page(
            "السبورة المرجعية", "لوحات تُعلَّق في مكتب الإدارة على شكل نموذجكم. تُملأ من معطيات البرنامج، وتُكمل "
                                "يدوياً، وتُطبع لوحة لوحة أو كاملة.")
        self.setLayout(racine)
        h = QHBoxLayout()
        b = QPushButton("توليد السبورة كاملة (Word)")
        b.setObjectName("principal")
        b.clicked.connect(lambda: self.generer(tout=True))
        h.addWidget(b)
        h.addStretch()
        racine.addLayout(h)
        corps = QHBoxLayout()
        corps.setSpacing(20)
        c, v = carte("اللوحات")
        self.liste = QListWidget()
        self.liste.setMinimumHeight(460)
        for l in sb.LAVHAT:
            it = QListWidgetItem(l.titre)
            it.setData(Qt.UserRole, l.cle)
            self.liste.addItem(it)
        self.liste.currentItemChanged.connect(lambda cur, _: self._choisir(cur))
        v.addWidget(self.liste, 1)
        corps.addWidget(c, 3)
        self.c_ed, self.v_ed = carte()
        self.titre = QLabel()
        self.titre.setObjectName("titreCarte")
        self.v_ed.addWidget(self.titre)
        self.source = QLabel()
        self.source.setObjectName("etiquette")
        self.source.setWordWrap(True)
        self.v_ed.addWidget(self.source)
        self.zone = QVBoxLayout()
        self.v_ed.addLayout(self.zone)
        h = QHBoxLayout()
        self.b_enr = QPushButton("حفظ")
        self.b_enr.setObjectName("principal")
        self.b_enr.clicked.connect(lambda: self.enregistrer(afficher=True))
        self.b_ajouter = QPushButton("إضافة سطر")
        self.b_ajouter.clicked.connect(self.ajouter_ligne)
        self.b_supprimer = bouton("حذف الأسطر المحددة")
        self.b_supprimer.clicked.connect(self.supprimer_lignes)
        self.b_actualiser = QPushButton("تحديث من البرنامج")
        self.b_actualiser.setToolTip("يعيد ما يأتي من البرنامج ويحتفظ بما أدخلتموه يدوياً")
        self.b_actualiser.clicked.connect(self.actualiser)
        b_gen = QPushButton("توليد هذه اللوحة (Word)")
        b_gen.clicked.connect(lambda: self.generer())
        for w in (self.b_enr, self.b_ajouter, self.b_supprimer, self.b_actualiser, b_gen):
            h.addWidget(w)
        h.addStretch()
        self.v_ed.addLayout(h)
        self.v_ed.addStretch()
        corps.addWidget(self.c_ed, 7)
        racine.addLayout(corps, 1)
        self.liste.setCurrentRow(0)

    def rafraichir(self) -> None:
        if self.cle:
            self.afficher(self.cle)

    def _choisir(self, it) -> None:
        if self.cle:
            self.enregistrer()
        if it is not None:
            self.afficher(it.data(Qt.UserRole))

    def afficher(self, cle: str, donnees: dict | None = None) -> None:
        l = sb.PAR_CLE[cle]
        d = donnees or sb.lire(self.f.conn, cle)
        self.cle = None
        for w in self._anciens:
            w.hide()
            w.setParent(None)
            w.deleteLater()
        self._anciens, self.editeurs, self.table, self.note = [], {}, None, None
        self.titre.setText(l.titre)
        self.source.setText("المصدر: " + l.source)
        contenu = QWidget()
        v = QVBoxLayout(contenu)
        v.setContentsMargins(0, 0, 0, 0)
        if l.nature == "fiche":
            g = QGridLayout()
            g.setHorizontalSpacing(14)
            g.setVerticalSpacing(4)
            for i, c in enumerate(l.champs):
                w = QLineEdit(d["champs"].get(c.cle, ""))
                self.editeurs[c.cle] = w
                g.addWidget(etiquette(c.libelle, w), (i // 3) * 2, i % 3)
                g.addWidget(w, (i // 3) * 2 + 1, i % 3)
            v.addLayout(g)
        else:
            t = TableauRapide(0, len(l.colonnes))
            t.setHorizontalHeaderLabels([c.replace(": ", "\n") for c in l.colonnes])
            t.setEditTriggers(QAbstractItemView.AllEditTriggers)
            t.setSelectionBehavior(QAbstractItemView.SelectRows)
            t.horizontalHeader().setStretchLastSection(True)
            t.setRowCount(len(d["lignes"]))
            for i, x in enumerate(d["lignes"]):
                for j, val in enumerate(x):
                    t.setItem(i, j, _item(val))
            t.setMinimumHeight(380)
            v.addWidget(t)
            self.table = t
            if l.note:
                self.note = QLineEdit(d.get("note", ""))
                v.addWidget(etiquette(l.note, self.note))
                v.addWidget(self.note)
        contenu.layout().activate()
        contenu.setMinimumHeight(contenu.layout().totalMinimumSize().height())
        self.zone.addWidget(contenu)
        self._anciens.append(contenu)
        for b in (self.b_ajouter, self.b_supprimer):
            b.setVisible(l.nature != "fiche")
        self.b_actualiser.setVisible(cle in sb.AUTO)
        self.cle = cle

    def donnees(self) -> dict:
        champs = {k: w.text() for k, w in self.editeurs.items()}
        lignes = []
        if self.table is not None:
            self.table.setCurrentItem(None)
            for i in range(self.table.rowCount()):
                lignes.append([(self.table.item(i, j).text() if self.table.item(i, j) else "")
                               for j in range(self.table.columnCount())])
        return {"champs": champs, "lignes": lignes, "note": self.note.text() if self.note else ""}

    def enregistrer(self, afficher: bool = False) -> bool:
        if self.cle is None:
            return False
        sb.enregistrer(self.f.conn, self.cle, self.donnees())
        if afficher:
            message(self.message, f"حُفظت لوحة «{sb.PAR_CLE[self.cle].titre}».")
        return True

    def ajouter_ligne(self) -> None:
        if self.table is not None:
            n = self.table.rowCount()
            self.table.insertRow(n)
            for j in range(self.table.columnCount()):
                self.table.setItem(n, j, _item(""))
            self.table.setCurrentCell(n, 0)

    def supprimer_lignes(self) -> None:
        if self.table is not None:
            for r in sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True):
                self.table.removeRow(r)

    def actualiser(self) -> None:
        if self.cle is None:
            return
        self.enregistrer()
        cle = self.cle
        self.afficher(cle, sb.actualiser(self.f.conn, cle))
        message(self.message, "حُدّثت اللوحة من معطيات البرنامج، وبقي ما أدخلتموه يدوياً.")

    def generer(self, tout: bool = False):
        self.enregistrer()
        cles = [l.cle for l in sb.LAVHAT] if tout else ([self.cle] if self.cle else [])
        if not cles:
            return None
        try:
            rubans = {c: ruban_png(sb.PAR_CLE[c].titre) for c in cles}
            chemin = sb.generer(self.f.conn, self.f.dossier, cles, rubans)
        except (sb.ErreurSabboura, OSError) as e:
            message(self.message, str(e), True)
            return None
        message(self.message, f"وُلّدت {'السبورة المرجعية كاملة' if tout else 'اللوحة'}: ⁦{chemin.name}⁩ "
                              "(في الأرشيف، مجلد «السبورة المرجعية»).")
        try:
            bureautique.ouvrir(chemin)
        except OSError:
            pass
        return chemin
