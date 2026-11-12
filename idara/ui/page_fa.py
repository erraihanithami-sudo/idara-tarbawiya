"""صفحة تدبير الفائض: ترتيب الأساتذة حسب المادة وفق المذكرة الإطار."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSpinBox, QVBoxLayout, QWidget

from idara.services import annee as annee_srv
from idara.services import fa
from idara.services import textes as tx
from idara.ui.composants import carte, entete
from idara.ui.formulaires import etiquette
from idara.ui import theme
from idara.ui.saisie import cellule, message, tableau

RESULTATS = {"maintenu": "يبقى", "fa": "فائض", "exempte": "مستثنى", "incomplet": "غير مرتب", "": "—"}


class CarteMatiere(QWidget):
    def __init__(self, page, matiere: str):
        super().__init__()
        self.page, self.matiere = page, matiere
        c, v = carte()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(c)
        haut = QHBoxLayout()
        haut.setSpacing(8)
        t = QLabel("جميع الأساتذة (بغض النظر عن مادة التدريس)" if matiere == fa.TOUS else f"مادة التدريس: {matiere}")
        t.setObjectName("titreCarte")
        haut.addWidget(t)
        haut.addStretch()
        self.postes = QSpinBox()
        self.postes.setRange(-1, 99)
        self.postes.setSpecialValueText("غير محدد")
        self.postes.setLayoutDirection(Qt.LeftToRight)
        self.postes.valueChanged.connect(self._postes)
        haut.addWidget(etiquette("عدد الأساتذة اللازم حسب البنية التربوية:", self.postes))
        haut.addWidget(self.postes)
        v.addLayout(haut)
        self.etat = QLabel()
        self.etat.setWordWrap(True)
        v.addWidget(self.etat)
        self.table = tableau(["الرتبة", "الاسم", "المادة", "العامة", "المديرية", "المؤسسة ×2",
                              "المجموع", "الازدياد", "النتيجة"], etirer=1)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        v.addWidget(self.table)

    def _postes(self, n: int) -> None:
        if self.page.chargement:
            return
        fa.definir_postes(self.page.f.conn, self.matiere, None if n < 0 else n)
        self.page.rafraichir()

    def afficher(self, g: fa.Groupe | None) -> None:
        self.postes.blockSignals(True)
        self.postes.setValue(-1 if g is None or g.requis is None else g.requis)
        self.postes.blockSignals(False)
        lignes = g.lignes if g else []
        self.table.setRowCount(len(lignes))
        for i, l in enumerate(lignes):
            complet = l.resultat != "incomplet"
            vals = [l.rang or "—", f"{l.p.prenom_ar} {l.p.nom_ar}", l.p.matiere or "—",
                    l.generale if complet else "—", l.direction if complet else "—",
                    f"{l.etablissement} × 2 = {2 * l.etablissement}" if complet else "—",
                    l.total if complet else "—",
                    tx.date_chiffres(l.p.date_naissance) if l.p.date_naissance else "—",
                    RESULTATS[l.resultat] + (f" ({l.motif})" if l.motif else "")]
            for j, val in enumerate(vals):
                it = cellule(val, l.p.id if j == 0 else None)
                if l.resultat == "fa":
                    it.setForeground(QColor(theme.ROUGE_TEXTE))
                self.table.setItem(i, j, it)
        self.table.setMinimumHeight(self.table.horizontalHeader().sizeHint().height() + 30
                                    + 40 * max(1, len(lignes)))
        if g is None or not g.lignes:
            texte, nom = "لا أساتذة عاملون.", "etiquette"
        elif g.requis is None:
            texte, nom = "حدد عدد الأساتذة اللازم لتحديد الفائض. الترتيب أسفله محسوب.", "alerte"
        elif g.incomplets:
            texte, nom = (f"الترتيب غير نهائي: {len(g.incomplets)} أستاذ(ة) بتواريخ ناقصة. "
                          "أكمل ملفاتهم في «الموارد البشرية»."), "alerte"
        elif g.fa:
            texte, nom = "الفائض: " + "، ".join(f"{l.p.prenom_ar} {l.p.nom_ar}" for l in g.fa), "alerte"
        else:
            texte, nom = "لا فائض.", "ok"
        self.etat.setObjectName(nom)
        self.etat.setText(texte)
        self.etat.style().unpolish(self.etat)
        self.etat.style().polish(self.etat)


class PageFa(QWidget):
    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        self.chargement = False
        racine = QVBoxLayout(self)
        racine.setContentsMargins(40, 32, 40, 32)
        racine.setSpacing(16)
        racine.addWidget(entete(
            "تدبير الفائض",
            "حسب المذكرة الإطار: نقطة عن كل سنة من تاريخ التوظيف، ونقطة عن كل سنة بالمديرية الإقليمية، "
            "ونقطتان عن كل سنة بالمؤسسة الحالية. كل موسم دراسي بسنة، بما فيه الموسم الجاري. "
            "عند التساوي: الأقدمية العامة، ثم بالمديرية، ثم بالمؤسسة، ثم السن (الأصغر سناً هو الفائض). "
            "يُستثنى المبرزون وحاملو الدكتوراه منذ 5 سنوات على الأقل."))
        self.saison = QLabel()
        self.saison.setObjectName("etiquette")
        racine.addWidget(self.saison)
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.hide()
        racine.addWidget(self.message)
        self.cartes = {fa.TOUS: CarteMatiere(self, fa.TOUS)}   # ترتيب واحد (قرار المدير 2026-11-10)
        for c in self.cartes.values():
            racine.addWidget(c)
        h = QHBoxLayout()
        b = QPushButton("توليد محضر الفائض + توقيعات الأساتذة (Word)")
        b.setObjectName("principal")
        b.setToolTip("الصفحة الأولى: المحضر والترتيب والنتيجة؛ الصفحة الثانية: توقيعات الأساتذة العاملين بعد الاطلاع.")
        b.clicked.connect(lambda: self.generer_pv())
        h.addWidget(b)
        b = QPushButton("فتح ملفات الأساتذة")
        b.clicked.connect(lambda: self.f.aller_a("الموارد البشرية"))
        h.addWidget(b)
        h.addStretch()
        racine.addLayout(h)
        racine.addStretch()
        self.rafraichir()

    def rafraichir(self) -> None:
        self.chargement = True
        try:
            a = annee_srv.annee_courante(self.f.conn)
            self.saison.setText(f"الموسم الجاري: {a['libelle']} · عدد الأقسام هذه السنة: {fa.nombre_classes(self.f.conn)}"
                                if a else "")
            try:
                groupes, sans = fa.calculer(self.f.conn)
            except fa.ErreurFa as e:
                message(self.message, str(e), True)
                return
            par_matiere = {g.matiere: g for g in groupes}
            for m, c in self.cartes.items():
                c.afficher(par_matiere.get(m))
            if sans:
                message(self.message, "أساتذة بدون مادة تدريس (لا يدخلون في الترتيب): "
                        + "، ".join(f"{p.prenom_ar} {p.nom_ar}" for p in sans), True)
            else:
                self.message.hide()
        finally:
            self.chargement = False

    def generer_pv(self):
        """محضر الفائض مع صفحة التوقيعات (طلب المدير 2026-11-12)."""
        from idara.services import bureautique
        try:
            p = fa.generer_pv(self.f.conn, self.f.dossier)
        except fa.ErreurFa as e:
            message(self.message, str(e), True)
            return None
        message(self.message, f"وُلّد المحضر: {p.name}")
        try:
            bureautique.ouvrir(p)
        except Exception:  # noqa: BLE001 — الفتح اختياري
            pass
        return p
