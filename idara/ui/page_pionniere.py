"""المدرسة الرائدة (طلب المدير 2026-11-19): مكونات فرعية حول «شارة الريادة».

- «تتبع النتائج»: بطاقة لكل فترة (الرائز القبلي، المراحل، الرائز البعدي)، جدول الأقسام للفترة المختارة بألوان
  التحكم، مبيان التطور، وتقرير تركيبي حول النتائج.
- «التواصل»: الأيام التواصلية والأبواب المفتوحة: تسجيل كل لقاء في نافذة منبثقة، استدعاءات الأولياء، تقرير
  كل لقاء وتقرير تركيبي، ورابط إلى مكون التواصل مع الآباء.
- «المؤشرات العامة»: أربع بطاقات فاخرة (التعلمات الأساس، ISA2، الأنشطة الموازية، الهدر) بالقيمة والمرجع
  والاتجاه.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QComboBox, QFormLayout, QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton,
                               QSpinBox, QVBoxLayout, QWidget)

from idara.services import bureautique
from idara.services import pionniere as pn
from idara.services import riyada as ry
from idara.services import textes as tx
from idara.ui import pictos
from idara.ui.composants import carte, entete
from idara.ui.formulaires import champ
from idara.ui.graphiques import BarresGroupees
from idara.ui.saisie import ChampDate, cellule, message, tableau
from idara.ui.vitrine import CarteFiltre, FenetreFiche, bouton_couleur, grille_cartes

OR = "#B8860B"
COULEURS_MATIERES = {"ar": "#00897B", "fr": "#3949AB", "ma": "#E65100"}


def _racine(page: QWidget, titre: str, sous: str = "") -> tuple[QVBoxLayout, QLabel]:
    racine = QVBoxLayout(page)
    racine.setContentsMargins(40, 32, 40, 32)
    racine.setSpacing(16)
    racine.addWidget(entete(titre, sous))
    m = QLabel()
    m.setWordWrap(True)
    m.hide()
    racine.addWidget(m)
    return racine, m


def couleur_taux(x: float | None) -> str:
    if x is None:
        return "#90A4AE"
    return "#2E7D32" if x >= 75 else "#EF8A00" if x >= 50 else "#C62828"


def _ouvrir(page, p):
    if p is None:
        return None
    try:
        page.f.ouvrir_document(p)
    except Exception:  # noqa: BLE001 — الفتح اختياري
        try:
            bureautique.ouvrir(p)
        except Exception:  # noqa: BLE001
            pass
    return p


def _faire(page, fn):
    try:
        return fn()
    except (pn.ErreurPionniere, ValueError) as e:
        message(page.message, str(e) or "قيمة غير صحيحة.", True)
        return None


# ======================================================================
# تتبع النتائج
# ======================================================================

class PageResultatsPionniere(QWidget):
    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        self.phase: int | None = None
        racine, self.message = _racine(self, "تتبع النتائج")
        self.cartes: dict[int, CarteFiltre] = {}
        for p in ry.PHASES:
            coul = "#6A1B9A" if p == -1 else "#AD1457" if p == 0 else "#00897B"
            c = CarteFiltre(str(p), ry.libelle_phase(p), coul, "statistiques", " ", compacte=True)
            c.clique.connect(lambda k: self.choisir(int(k)))
            self.cartes[p] = c
        racine.addLayout(grille_cartes(list(self.cartes.values()), 4))
        h = QHBoxLayout()
        h.setSpacing(12)
        self.b_rapport = bouton_couleur("تقرير تركيبي حول النتائج", "#00695C", "document",
                                        "تطور النسب حسب الفترات، جدول الأقسام لكل فترة، وقراءة موجزة")
        self.b_rapport.clicked.connect(lambda: self.rapport())
        self.b_saisie = bouton_couleur("مسك النتائج واستيراد الروائز", "#6A1B9A", "importer",
                                       "يفتح «شارة الريادة» حيث تُحمَّل ملفات الروائز وتُدخل نسب الفترات")
        self.b_saisie.clicked.connect(lambda: self.f.aller_a("الريادة"))
        h.addWidget(self.b_rapport)
        h.addWidget(self.b_saisie)
        h.addStretch()
        racine.addLayout(h)

        c, v = carte()
        tete = QHBoxLayout()
        self.titre_table = QLabel()
        self.titre_table.setObjectName("titreCarte")
        tete.addWidget(self.titre_table, 1)
        legende = QLabel("<span style='color:#2E7D32'>■</span> 75% فما فوق  "
                         "<span style='color:#EF8A00'>■</span> 50% – 75%  "
                         "<span style='color:#C62828'>■</span> أقل من 50%")
        legende.setObjectName("etiquette")
        tete.addWidget(legende)
        v.addLayout(tete)
        self.table = tableau(["القسم", *ry.MATIERES.values(), "المعدل"], etirer=0)
        self.table.setMinimumHeight(280)
        v.addWidget(self.table)
        self.vide = QLabel("لا نتائج لهذه الفترة بعد.")
        self.vide.setObjectName("etiquette")
        self.vide.setAlignment(Qt.AlignCenter)
        v.addWidget(self.vide)
        racine.addWidget(c)
        self.c_graph, self.v_graph = carte("تطور النسب حسب الفترات (معدل الأقسام)")
        self._graphes: list[QWidget] = []
        racine.addWidget(self.c_graph)
        racine.addStretch()

    def _annee(self) -> str | None:
        from idara.services import annee as annee_srv
        a = annee_srv.annee_courante(self.f.conn)
        return a["libelle"] if a else None

    def rafraichir(self) -> None:
        a = self._annee()
        self.moy = pn.moyennes_par_phase(self.f.conn, a) if a else {}
        for p, c in self.cartes.items():
            v = self.moy.get(p, {}).get("all")
            c.definir("—" if v is None else f"{v:.1f}%")
            c.note.setText("معدل المواد" if v is not None else "لا نتائج")
        if self.phase is None or self.phase not in self.moy:
            self.phase = max(self.moy) if self.moy else ry.PHASES[2]
        self.choisir(self.phase)
        self._graphique()

    def choisir(self, phase: int) -> None:
        self.phase = phase
        for p, c in self.cartes.items():
            c.definir_actif(p == phase)
        a = self._annee()
        lignes = pn.resultats_periode(self.f.conn, a, phase) if a else []
        self.titre_table.setText(f"{ry.libelle_phase(phase)}: النسب حسب الأقسام ({len(lignes)})")
        self.table.setRowCount(len(lignes))
        for i, l in enumerate(lignes):
            self.table.setItem(i, 0, cellule(l["classe"]))
            for j, k in enumerate((*ry.MATIERES, "moyenne"), start=1):
                x = l[k]
                it = cellule("—" if x is None else f"{x:.2f}%")
                it.setTextAlignment(Qt.AlignCenter)
                coul = QColor(couleur_taux(x))
                it.setForeground(coul)
                fond = QColor(coul)
                fond.setAlpha(26 if x is not None else 0)
                it.setBackground(fond)
                if k == "moyenne":
                    f_ = it.font()
                    f_.setBold(True)
                    it.setFont(f_)
                self.table.setItem(i, j, it)
        self.table.setVisible(bool(lignes))
        self.vide.setVisible(not lignes)

    def _graphique(self) -> None:
        for w in self._graphes:
            w.hide()
            w.setParent(None)
            w.deleteLater()
        self._graphes = []
        self.c_graph.setVisible(bool(self.moy))
        if not self.moy:
            return
        g = BarresGroupees([ry.libelle_phase(p) for p in self.moy],
                           [(lib, [self.moy[p][m] for p in self.moy], COULEURS_MATIERES[m])
                            for m, lib in ry.MATIERES.items()], maximum=100, suffixe="%")
        g.setMinimumHeight(260)
        self.v_graph.addWidget(g)
        self._graphes = [g]

    def rapport(self):
        a = self._annee()
        if not a:
            message(self.message, "لا سنة دراسية جارية.", True)
            return None
        p = _faire(self, lambda: pn.generer_rapport_resultats(self.f.conn, self.f.dossier, a))
        if p:
            message(self.message, f"وُلّد التقرير التركيبي: ⁦{p.name}⁩")
        return _ouvrir(self, p)


# ======================================================================
# التواصل: الأيام التواصلية والأبواب المفتوحة
# ======================================================================

class PageCommunicationPionniere(QWidget):
    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        self.rid: int | None = None
        self.filtre: str | None = None
        racine, self.message = _racine(self, "التواصل مع الأسر")
        self.cartes = {
            "rencontre": CarteFiltre("rencontre", "الأيام التواصلية", "#EF6C00", "personnes", " "),
            "portes": CarteFiltre("portes", "الأبواب المفتوحة", "#00897B", "entree", " "),
        }
        for c in self.cartes.values():
            c.clique.connect(self.filtrer)
        self.c_taux = CarteFiltre("taux", "نسبة حضور الأولياء", "#6A1B9A", "statistiques", " ")
        racine.addLayout(grille_cartes([*self.cartes.values(), self.c_taux], 3))
        h = QHBoxLayout()
        h.setSpacing(12)
        actions = (
            ("تسجيل لقاء", "#1565C0", "ajouter", lambda: self.ouvrir_rencontre(), "يوم تواصلي أو أبواب مفتوحة"),
            ("استدعاءات اليوم التواصلي", "#EF6C00", "rappel", lambda: self.convocations("rencontre"), ""),
            ("استدعاءات الأبواب المفتوحة", "#00897B", "rappel", lambda: self.convocations("portes"), ""),
            ("تقرير تركيبي", "#6A1B9A", "document", lambda: self.rapport_synthese(),
             "تقرير حول الأيام التواصلية والأبواب المفتوحة المسجلة هذه السنة"),
            ("التواصل مع الآباء", "#455A64", "envoyer", lambda: self.f.aller_a("الإعلام والتواصل"),
             "يفتح مكون الإعلام والتواصل: الإعلانات المزخرفة واستدعاءات الأولياء"),
        )
        self.boutons = {}
        for t, coul, pic, fn, aide in actions:
            b = bouton_couleur(t, coul, pic, aide)
            b.clicked.connect(fn)
            self.boutons[t] = b
            h.addWidget(b)
        h.addStretch()
        racine.addLayout(h)
        c, v = carte()
        self.titre_liste = QLabel()
        self.titre_liste.setObjectName("titreCarte")
        v.addWidget(self.titre_liste)
        self.liste = tableau(["النوع", "التاريخ", "الموضوع", "المدعوون", "الحاضرون", "النسبة", "الإجراءات"], etirer=2)
        self.liste.setMinimumHeight(260)
        self.liste.verticalHeader().setDefaultSectionSize(46)
        self.liste.itemDoubleClicked.connect(lambda it: self.ouvrir_rencontre(
            self.liste.item(it.row(), 0).data(Qt.UserRole)))
        v.addWidget(self.liste)
        self.vide = QLabel("لا لقاء مسجلاً هذه السنة. «تسجيل لقاء» يضيف يوماً تواصلياً أو أبواباً مفتوحة.")
        self.vide.setObjectName("etiquette")
        self.vide.setAlignment(Qt.AlignCenter)
        self.vide.setWordWrap(True)
        v.addWidget(self.vide)
        racine.addWidget(c)
        racine.addStretch()
        self._construire_fiche()

    def _construire_fiche(self) -> None:
        w = QWidget()
        fl = QFormLayout(w)
        fl.setSpacing(10)
        self.c_type = QComboBox()
        for k, lib in pn.TYPES_RENCONTRE.items():
            self.c_type.addItem(lib, k)
        self.c_date = ChampDate()
        self.c_heure = champ("15:00", ltr=True)
        self.c_heure.setMaximumWidth(120)
        self.c_theme = champ("مثال: نتائج المرحلة الأولى وسبل الدعم")
        self.c_invites, self.c_presents = QSpinBox(), QSpinBox()
        for s in (self.c_invites, self.c_presents):
            s.setRange(0, 5000)
            s.setSpecialValueText("—")
            s.setMaximumWidth(140)
        self.c_deroulement = QPlainTextEdit()
        self.c_deroulement.setPlaceholderText("سطر لكل محطة: الاستقبال، عرض النتائج، اللقاءات الفردية…")
        self.c_recos = QPlainTextEdit()
        self.c_recos.setPlaceholderText("سطر لكل توصية أو التزام")
        for t in (self.c_deroulement, self.c_recos):
            t.setMinimumHeight(110)
        for lib, wdg in (("النوع", self.c_type), ("التاريخ", self.c_date), ("الساعة", self.c_heure),
                         ("الموضوع", self.c_theme), ("عدد المدعوين", self.c_invites),
                         ("عدد الحاضرين", self.c_presents), ("سير اللقاء", self.c_deroulement),
                         ("التوصيات والالتزامات", self.c_recos)):
            fl.addRow(lib, wdg)
        h = QHBoxLayout()
        self.b_save = bouton_couleur("حفظ", "#1565C0", "enregistrer")
        self.b_save.clicked.connect(lambda: self.enregistrer())
        self.b_save_rapport = bouton_couleur("حفظ وتوليد التقرير", "#2E7D32", "document")
        self.b_save_rapport.clicked.connect(lambda: self.enregistrer_et_rapport())
        h.addWidget(self.b_save)
        h.addWidget(self.b_save_rapport)
        h.addStretch()
        fl.addRow(h)
        self.message_fiche = QLabel()
        self.message_fiche.setWordWrap(True)
        self.message_fiche.hide()
        fl.addRow(self.message_fiche)
        self.fiche = FenetreFiche(self, "تسجيل لقاء", "", w, largeur=760)

    def rafraichir(self) -> None:
        tout = pn.rencontres(self.f.conn)
        for k, c in self.cartes.items():
            rs = [r for r in tout if r.type == k]
            c.definir(len(rs))
            prochain = sorted((r for r in rs if r.date_rencontre >= tx_today()), key=lambda r: r.date_rencontre)
            c.note.setText(f"القادم: {tx.date_chiffres(prochain[0].date_rencontre)}" if prochain
                           else "لا موعد قادم")
            c.definir_actif(k == self.filtre)
        inv = sum(r.invites or 0 for r in tout if r.presents is not None)
        pres = sum(r.presents or 0 for r in tout if r.invites)
        self.c_taux.definir(f"{100 * pres / inv:.1f}%" if inv else "—")
        self.c_taux.note.setText(f"{pres} من {inv} ولياً" if inv else "تُحسب بعد تسجيل الحضور")
        self.lignes = [r for r in tout if self.filtre is None or r.type == self.filtre]
        titre = pn.TYPES_RENCONTRE[self.filtre] if self.filtre else "كل اللقاءات"
        self.titre_liste.setText(f"{titre} ({len(self.lignes)})")
        self.liste.setRowCount(len(self.lignes))
        for i, r in enumerate(self.lignes):
            coul = self.cartes[r.type].couleur
            it = cellule(pn.TYPES_RENCONTRE[r.type], r.id)
            it.setForeground(QColor(coul))
            it.setIcon(pictos.icone("personnes" if r.type == "rencontre" else "entree", coul, 16))
            self.liste.setItem(i, 0, it)
            tp = pn.taux_presence(r)
            for j, x in enumerate((tx.date_chiffres(r.date_rencontre) + (f" · {r.heure}" if r.heure else ""),
                                   r.theme or "—", "—" if r.invites is None else str(r.invites),
                                   "—" if r.presents is None else str(r.presents),
                                   "—" if tp is None else f"{tp:.1f}%"), start=1):
                self.liste.setItem(i, j, cellule(x))
            self.liste.setCellWidget(i, 6, self._actions(r.id))
        from idara.ui.vitrine import ajuster_colonne_actions
        ajuster_colonne_actions(self.liste, 6)
        self.liste.setVisible(bool(self.lignes))
        self.vide.setVisible(not self.lignes)

    def _actions(self, rid: int) -> QWidget:
        from idara.ui.vitrine import boutons_ligne
        return boutons_ligne([("التقرير", "#2E7D32", "document", lambda: self.rapport(rid)),
                              ("تعديل", "#1565C0", "modifier", lambda: self.ouvrir_rencontre(rid)),
                              ("حذف", "#C62828", "annuler", lambda: self.supprimer(rid))])

    def filtrer(self, k: str) -> None:
        self.filtre = None if k == self.filtre else k
        self.rafraichir()

    def ouvrir_rencontre(self, rid: int | None = None, type_: str | None = None) -> FenetreFiche:
        self.rid = rid
        self.message_fiche.hide()
        if rid:
            r = pn.rencontre(self.f.conn, rid)
            self.c_type.setCurrentIndex(self.c_type.findData(r.type))
            self.c_date.definir(r.date_rencontre)
            self.c_heure.setText(r.heure)
            self.c_theme.setText(r.theme)
            self.c_invites.setValue(r.invites or 0)
            self.c_presents.setValue(r.presents or 0)
            self.c_deroulement.setPlainText(r.deroulement)
            self.c_recos.setPlainText(r.recommandations)
            self.fiche.definir_titre(f"تعديل: {pn.TYPES_RENCONTRE[r.type]} {tx.date_chiffres(r.date_rencontre)}")
        else:
            self.c_type.setCurrentIndex(max(0, self.c_type.findData(type_ or self.filtre or "rencontre")))
            from datetime import date
            self.c_date.definir(date.today().isoformat())
            for w in (self.c_heure, self.c_theme, self.c_deroulement, self.c_recos):
                w.clear()
            self.c_invites.setValue(0)
            self.c_presents.setValue(0)
            self.fiche.definir_titre("تسجيل لقاء مع الأسر")
        self.fiche.ouvrir()
        return self.fiche

    def enregistrer(self) -> int | None:
        def fn():
            d = self.c_date.iso()
            if not d:
                raise pn.ErreurPionniere("حدد تاريخ اللقاء.")
            r = pn.Rencontre(self.c_type.currentData(), d, self.c_theme.text(), self.c_heure.text().strip(),
                             self.c_invites.value() or None, self.c_presents.value() or None,
                             self.c_deroulement.toPlainText(), self.c_recos.toPlainText(), self.rid)
            return pn.enregistrer_rencontre(self.f.conn, r)
        try:
            rid = fn()
        except (pn.ErreurPionniere, ValueError) as e:
            message(self.message_fiche, str(e) or "تاريخ غير صحيح.", True)
            return None
        self.rid = rid
        message(self.message_fiche, "حُفظ اللقاء.")
        message(self.message, "حُفظ اللقاء.")
        self.rafraichir()
        return rid

    def enregistrer_et_rapport(self):
        rid = self.enregistrer()
        return self.rapport(rid) if rid else None

    def supprimer(self, rid: int) -> None:
        pn.supprimer_rencontre(self.f.conn, rid)
        message(self.message, "حُذف اللقاء.")
        self.rafraichir()

    def rapport(self, rid: int):
        p = _faire(self, lambda: pn.generer_rapport_rencontre(self.f.conn, self.f.dossier, rid))
        return _ouvrir(self, p)

    def rapport_synthese(self):
        p = _faire(self, lambda: pn.generer_rapport_rencontres(self.f.conn, self.f.dossier, self.filtre))
        if p:
            message(self.message, f"وُلّد التقرير التركيبي: ⁦{p.name}⁩")
        return _ouvrir(self, p)

    def convocations(self, occasion: str):
        from idara.ui.page_eleves import DialogueConvocationsOccasion
        d = DialogueConvocationsOccasion(self, occasion)
        d.ouvrir()
        self._dialogue = d
        return d


def tx_today() -> str:
    from datetime import date
    return date.today().isoformat()


# ======================================================================
# المؤشرات العامة
# ======================================================================

STYLES_IND = {"tarl": ("#00897B", "valider"), "isa2": ("#3949AB", "statistiques"),
              "activites": ("#8E24AA", "personnes"), "hadar": ("#C62828", "sortie")}


class CarteIndicateur(QFrame):
    """بطاقة مؤشر فاخرة: تدرج لوني، القيمة الكبيرة، المرجع، سهم الاتجاه، شارة الحالة، ومنحنى صغير."""

    def __init__(self, cle: str):
        super().__init__()
        self.cle = cle
        self.couleur, picto = STYLES_IND[cle]
        self.points: list[float] = []
        self.setMinimumHeight(210)
        self.setObjectName("carteIndicateur")
        v = QVBoxLayout(self)
        v.setContentsMargins(22, 18, 22, 18)
        v.setSpacing(4)
        h = QHBoxLayout()
        ic = QLabel()
        ic.setPixmap(pictos.pixmap(picto, "#FFFFFF", 30))
        ic.setStyleSheet("background: transparent;")
        h.addWidget(ic)
        self.titre = QLabel()
        self.titre.setStyleSheet("color: white; font-size: 13pt; font-weight: 700; background: transparent;")
        self.titre.setWordWrap(True)
        h.addWidget(self.titre, 1)
        self.etat = QLabel()
        self.etat.setStyleSheet("color: white; background: rgba(255,255,255,0.22); border-radius: 10px; "
                                "padding: 3px 10px; font-weight: 700;")
        h.addWidget(self.etat, 0, Qt.AlignTop)
        v.addLayout(h)
        self.valeur = QLabel()
        self.valeur.setStyleSheet("color: white; font-size: 30pt; font-weight: 800; background: transparent;")
        v.addWidget(self.valeur)
        self.ref = QLabel()
        self.ref.setStyleSheet("color: rgba(255,255,255,0.92); font-weight: 600; background: transparent;")
        v.addWidget(self.ref)
        self.detail = QLabel()
        self.detail.setWordWrap(True)
        self.detail.setStyleSheet("color: rgba(255,255,255,0.85); background: transparent;")
        v.addWidget(self.detail)
        v.addStretch()

    def definir(self, x: dict) -> None:
        self.donnees = x
        u = x["unite"]
        self.titre.setText(x["titre"])
        val = x["valeur"]
        self.valeur.setText("—" if val is None else (f"{val:.1f}%" if u == "%" else f"{val:g}"))
        ec = x["ecart"]
        fleche = "" if ec is None else ("+" if ec > 0 else "−" if ec < 0 else "±")
        refv = x["reference"]
        if refv is None:
            self.ref.setText("لا مرجع للمقارنة بعد")
        else:
            rtxt = f"{refv:.1f}%" if u == "%" else f"{refv:g}"
            etxt = "" if ec is None else f" · التطور: \u2066{fleche}{abs(ec):.1f}\u2069{' نقطة' if u == '%' else ''}"
            self.ref.setText(f"المرجع ({x['ref_lib']}): {rtxt}{etxt}")
        cible = x.get("cible")
        self.detail.setText(x["detail"] + (f" · الهدف: {cible:g} (ضعف المرجع)" if cible else ""))
        self.etat.setText(x["etat"])
        self.points = [v for _, v in sorted(x.get("points", {}).items())]
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        c = QColor(self.couleur)
        g = QLinearGradient(r.topRight(), r.bottomLeft())
        g.setColorAt(0, c.lighter(118))
        g.setColorAt(1, c.darker(135))
        chemin = QPainterPath()
        chemin.addRoundedRect(r, 20, 20)
        p.fillPath(chemin, g)
        # زخرفة: دائرتان شفافتان
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 22))
        p.drawEllipse(QPointF(r.left() + 30, r.bottom() - 10), 70, 70)
        p.drawEllipse(QPointF(r.left() + 110, r.top() + 10), 34, 34)
        # منحنى التطور
        if len(self.points) >= 2:
            w, h = 150, 54
            x0, y0 = r.left() + 22, r.bottom() - 18 - h
            mn, mx = min(self.points), max(self.points)
            et = (mx - mn) or 1
            pts = [QPointF(x0 + i * w / (len(self.points) - 1), y0 + h - (v - mn) / et * h)
                   for i, v in enumerate(self.points)]
            p.setPen(QPen(QColor(255, 255, 255, 230), 2.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            for a, b in zip(pts, pts[1:]):
                p.drawLine(a, b)
            p.setBrush(QColor("white"))
            for q in pts:
                p.drawEllipse(q, 3.4, 3.4)
        p.end()
        super().paintEvent(ev)


class PageIndicateursPionniere(QWidget):
    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        racine, self.message = _racine(self, "المؤشرات العامة")
        self.cartes = {k: CarteIndicateur(k) for k in STYLES_IND}
        from PySide6.QtWidgets import QGridLayout
        g = QGridLayout()
        g.setSpacing(16)
        for i, c in enumerate(self.cartes.values()):
            g.addWidget(c, i // 2, i % 2)
        racine.addLayout(g)
        note = QLabel("القيم من معطيات البرنامج: نتائج الروائز ونسب المراحل، الأندية والمنخرطون فيها، وحركية "
                      "التلاميذ (المنقطعون والمفصولون). المرجع هو السنة السابقة، ولمؤشر ISA2 أول مرحلة مسجلة.")
        note.setObjectName("etiquette")
        note.setWordWrap(True)
        racine.addWidget(note)
        h = QHBoxLayout()
        for t, coul, pic, page in (("التعلمات الأساس", "#00897B", "valider", "التعلمات الأساس"),
                                   ("تتبع النتائج", "#3949AB", "statistiques", "نتائج الريادة"),
                                   ("الأندية والأنشطة", "#8E24AA", "personnes", "الأندية والأنشطة"),
                                   ("حركية التلاميذ", "#C62828", "sortie", "حركية التلاميذ")):
            b = bouton_couleur(t, coul, pic)
            b.clicked.connect(lambda _=False, x=page: self.f.aller_a(x))
            h.addWidget(b)
        h.addStretch()
        racine.addLayout(h)
        racine.addStretch()

    def rafraichir(self) -> None:
        try:
            ind = pn.indicateurs(self.f.conn)
        except pn.ErreurPionniere as e:
            message(self.message, str(e), True)
            return
        self.ind = {x["cle"]: x for x in ind}
        for k, c in self.cartes.items():
            c.definir(self.ind[k])

