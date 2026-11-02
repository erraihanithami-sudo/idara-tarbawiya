"""قسم التدبير التربوي: أداء المؤسسة بالأسدوس، التعلمات الأساس (مؤسسات الريادة)، الأندية والأنشطة الموازية."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QComboBox, QFileDialog, QGridLayout, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton,
                               QVBoxLayout, QWidget)

from idara.services import bureautique
from idara.services import eleves as el
from idara.services import evaluation as ev
from idara.services import personnel as rh
from idara.services import tarl
from idara.services import vie_scolaire as vs
from idara.ui.composants import carte, entete
from idara.ui.formulaires import champ, etiquette
from idara.ui.saisie import ChampDate, cellule, message, tableau

VERT, ROUGE = QColor("#006233"), QColor("#B3261E")


def _n(x, suffixe="") -> str:
    return "—" if x is None else f"{x:.2f}{suffixe}"


def _ecart(x, suffixe="") -> str:
    if x is None:
        return "—"
    return ("▲ +" if x > 0 else "▼ " if x < 0 else "= ") + f"{x:.2f}{suffixe}"


def _grille(paires, etirer=None) -> QGridLayout:
    g = QGridLayout()
    g.setHorizontalSpacing(16)
    g.setVerticalSpacing(4)
    for j, (lib, w) in enumerate(paires):
        g.addWidget(etiquette(lib, w), 0, j)
        g.addWidget(w, 1, j)
    g.setColumnStretch(len(paires) if etirer is None else etirer, 1)
    return g


def _page(titre: str, sous: str) -> tuple[QVBoxLayout, QLabel]:
    racine = QVBoxLayout()
    racine.setContentsMargins(40, 32, 40, 32)
    racine.setSpacing(16)
    racine.addWidget(entete(titre, sous))
    m = QLabel()
    m.setWordWrap(True)
    m.hide()
    racine.addWidget(m)
    return racine, m


# ======================================================================
class PagePerformance(QWidget):
    """أداء المؤسسة: كل أسدوس مقارنة بالذي قبله (المعدل ونسبة الحاصلين على المعدل)."""

    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        racine, self.message = _page("أداء المؤسسة حسب النتائج",
                                     "معدلا الدورتين من ملف «مجمل المعدلات» (مسار)، نفس الملف المستورد في مجالس "
                                     "الأقسام. كل أسدوس يقارن بالأسدوس الذي قبله: الأول بالثاني من السنة الفارطة، "
                                     "والثاني بالأول من نفس السنة.")
        self.setLayout(racine)
        c, v = carte()
        h = QHBoxLayout()
        b = QPushButton("استيراد ملفات «مجمل المعدلات»")
        b.setObjectName("principal")
        b.clicked.connect(lambda: self.choisir())
        h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        self.periode, self.vue = QComboBox(), QComboBox()
        self.vue.addItem("حسب المستويات", "niveau")
        self.vue.addItem("حسب الأقسام", "classe")
        self.periode.currentIndexChanged.connect(lambda _: self.afficher())
        self.vue.currentIndexChanged.connect(lambda _: self.afficher())
        v.addLayout(_grille([("الأسدوس", self.periode), ("العرض", self.vue)]))
        self.titre = QLabel()
        self.titre.setObjectName("titreCarte")
        v.addWidget(self.titre)
        self.table = tableau(["الفئة", "العدد", "المعدل", "نسبة الحاصلين على المعدل", "المعدل (السابق)",
                              "النسبة (السابق)", "تطور المعدل", "تطور النسبة"], etirer=0)
        self.table.setMinimumHeight(360)
        v.addWidget(self.table)
        self.note = QLabel()
        self.note.setObjectName("sousTitre")
        self.note.setWordWrap(True)
        v.addWidget(self.note)
        racine.addWidget(c)
        racine.addStretch()
        self.rafraichir()

    def rafraichir(self) -> None:
        courant = self.periode.currentData()
        self.periode.blockSignals(True)
        self.periode.clear()
        for p in reversed(ev.periodes(self.f.conn)):
            self.periode.addItem(ev.libelle_periode(p), p)
        i = self.periode.findData(courant)
        self.periode.setCurrentIndex(i if i >= 0 else 0)
        self.periode.blockSignals(False)
        if not self.periode.count():
            message(self.message, "لا نتائج بعد. استورد ملفات «مجمل المعدلات» من مسار (بعد الأسدوس الأول أو الثاني).")
        self.afficher()

    def afficher(self) -> None:
        p = self.periode.currentData()
        lignes = ev.comparaison(self.f.conn, tuple(p), self.vue.currentData()) if p else []
        self.table.setRowCount(len(lignes))
        for i, l in enumerate(lignes):
            vals = (l["libelle"], str(l["effectif"]), _n(l["moyenne"]), _n(l["taux"], "%"), _n(l["moyenne_avant"]),
                    _n(l["taux_avant"], "%"), _ecart(l["ecart_moyenne"]), _ecart(l["ecart_taux"], "%"))
            for j, v in enumerate(vals):
                it = cellule(v)
                if j >= 6:
                    x = l["ecart_moyenne" if j == 6 else "ecart_taux"]
                    if x:
                        it.setForeground(VERT if x > 0 else ROUGE)
                if l["cle"] == "المؤسسة":
                    f = it.font()
                    f.setBold(True)
                    it.setFont(f)
                self.table.setItem(i, j, it)
        if lignes:
            l0 = lignes[0]
            self.titre.setText(f"{l0['periode']}" + (f" مقارنة ب{l0['avant']}" if l0["avant"] else
                                                     " (لا أسدوس قبله في البيانات)"))
            self.note.setText("المقارنة بين أسدوسين من سنتين مختلفتين تخص نفس المستوى الدراسي، لا نفس التلاميذ "
                              "(انتقلوا إلى المستوى الموالي).")
        else:
            self.titre.setText("")
            self.note.setText("")

    def choisir(self) -> None:
        fs, _ = QFileDialog.getOpenFileNames(self, "ملفات «مجمل المعدلات» من مسار", "", "Excel (*.xlsx)")
        if fs:
            self.importer([Path(x) for x in fs])

    def importer(self, chemins: list[Path]):
        try:
            r = ev.importer(self.f.conn, chemins)
        except ev.ErreurEvaluation as e:
            message(self.message, str(e), True)
            return None
        self.rafraichir()
        message(self.message, f"استوردت نتائج {r.eleves} تلميذاً ({len(r.classes)} أقسام) للسنة {r.annee}.")
        return r


# ======================================================================
class PageTarl(QWidget):
    """التعلمات الأساس: مستويات TaRL في رائزي الموضعة القبلي والبعدي."""

    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        racine, self.message = _page("تتبع التعلمات الأساس (مؤسسات الريادة)",
                                     "من تصدير مسار «مستويات التعلم»: توزيع التلاميذ على مستويات اللغة العربية واللغة "
                                     "الفرنسية والرياضيات في رائزي الموضعة القبلي والبعدي، ونسبة بلوغ المستوى المتوقع.")
        self.setLayout(racine)
        c, v = carte()
        h = QHBoxLayout()
        b = QPushButton("استيراد «مستويات التعلم» من مسار")
        b.setObjectName("principal")
        b.clicked.connect(lambda: self.choisir())
        h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        self.annee, self.groupe, self.matiere = QComboBox(), QComboBox(), QComboBox()
        for k, lib in tarl.MATIERES.items():
            self.matiere.addItem(lib, k)
        self.annee.currentIndexChanged.connect(lambda _: self._groupes())
        self.groupe.currentIndexChanged.connect(lambda _: self.afficher())
        self.matiere.currentIndexChanged.connect(lambda _: self.afficher())
        v.addLayout(_grille([("السنة", self.annee), ("الفئة", self.groupe), ("المادة", self.matiere)]))
        self.resume = QLabel()
        self.resume.setObjectName("titreCarte")
        self.resume.setWordWrap(True)
        v.addWidget(self.resume)
        self.table = tableau(["المستوى", "القبلي (العدد)", "القبلي (%)", "البعدي (العدد)", "البعدي (%)"], etirer=0)
        self.table.setMinimumHeight(300)
        v.addWidget(self.table)
        racine.addWidget(c)
        c, v = carte("التلاميذ دون المستوى المتوقع في الرائز البعدي (للدعم)")
        self.difficulte = tableau(["القسم", "رمز مسار", "الاسم", "المستوى البعدي", "المتوقع"], etirer=2)
        self.difficulte.setMinimumHeight(260)
        v.addWidget(self.difficulte)
        racine.addWidget(c)
        racine.addStretch()
        self.rafraichir()

    def rafraichir(self) -> None:
        courant = self.annee.currentText()
        self.annee.blockSignals(True)
        self.annee.clear()
        self.annee.addItems(tarl.annees(self.f.conn))
        if courant:
            self.annee.setCurrentText(courant)
        self.annee.blockSignals(False)
        if not self.annee.count():
            message(self.message, "لا مستويات تعلم بعد. صدِّر «مستويات التعلم» من مسار (فضاء مؤسسات الريادة) ثم استوردها.")
        self._groupes()

    def _groupes(self) -> None:
        courant = self.groupe.currentData()
        self.groupe.blockSignals(True)
        self.groupe.clear()
        if self.annee.currentText():
            for k, lib in tarl.groupes(self.f.conn, self.annee.currentText()):
                self.groupe.addItem(lib, k)
        i = self.groupe.findData(courant)
        self.groupe.setCurrentIndex(i if i >= 0 else 0)
        self.groupe.blockSignals(False)
        self.afficher()

    def afficher(self) -> None:
        a, g, m = self.annee.currentText(), self.groupe.currentData(), self.matiere.currentData()
        if not (a and g):
            self.table.setRowCount(0)
            self.difficulte.setRowCount(0)
            self.resume.setText("")
            return
        tb = tarl.tableau_bord(self.f.conn, a, g, m)
        self.table.setRowCount(len(tb["echelle"]))
        for i, niv in enumerate(tb["echelle"]):
            vals = [niv]
            for ep in ("pre", "post"):
                n, t = tb["distribution"][ep][niv], tb["effectifs"][ep]
                vals += [str(n), f"{n / t * 100:.2f}%" if t else "—"]
            for j, v in enumerate(vals):
                self.table.setItem(i, j, cellule(v))
        ta, ev_ = tb["taux_attendu"], tb["evolution"]
        self.resume.setText(
            f"بلوغ المستوى المتوقع: القبلي {_n(ta['pre'], '%')} ← البعدي {_n(ta['post'], '%')} — "
            f"التطور بين الرائزين ({tb['compares']} تلميذاً): تحسن {ev_['progres']}، استقرار {ev_['stable']}، "
            f"تراجع {ev_['recul']}")
        diff = tarl.eleves_en_difficulte(self.f.conn, a, g, m)
        self.difficulte.setRowCount(len(diff))
        for i, r in enumerate(diff):
            for j, v in enumerate((r["classe"].replace("-", ""), r["code_massar"], r["nom"], r["valeur"],
                                   tarl.attendu(self.f.conn, a, r["niveau"], m) or "—")):
                self.difficulte.setItem(i, j, cellule(v))

    def choisir(self) -> None:
        fs, _ = QFileDialog.getOpenFileNames(self, "«مستويات التعلم» من مسار", "", "Excel (*.xlsx)")
        if fs:
            self.importer([Path(x) for x in fs])

    def importer(self, chemins: list[Path]):
        try:
            r = tarl.importer(self.f.conn, chemins)
        except tarl.ErreurTarl as e:
            message(self.message, str(e), True)
            return None
        self.rafraichir()
        self.annee.setCurrentText(r.annee)
        txt = f"استوردت مستويات {r.eleves} تلميذاً ({len(r.classes)} أقسام) للسنة {r.annee}."
        if r.alertes:
            txt += "\nتنبيهات: " + "؛ ".join(r.alertes[:5]) + (" ..." if len(r.alertes) > 5 else "")
        message(self.message, txt, bool(r.alertes))
        return r


# ======================================================================
class PageVieScolaire(QWidget):
    """الأندية التربوية والأنشطة الموازية: البرنامج السنوي، الإنجاز والحصيلة."""

    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        self.club_id: int | None = None
        self.act_id: int | None = None
        racine, self.message = _page("الأندية التربوية والأنشطة الموازية",
                                     "البرنامج السنوي بأعمدة نموذجكم (نوع النشاط، الأنشطة، المتدخلون، المستهدفون، "
                                     "فترة الإنجاز، آليات التنفيذ)، ثم تسجيل الإنجاز وعدد المشاركين والحصيلة.")
        self.setLayout(racine)
        self.indic = QLabel()
        self.indic.setObjectName("titreCarte")
        self.indic.setWordWrap(True)
        racine.addWidget(self.indic)

        # ---- الأندية ----
        c, v = carte("الأندية التربوية")
        self.clubs = tableau(["النادي", "المنشط(ة)", "التوقيت", "الأعضاء", "أنشطة منجزة"], etirer=0)
        self.clubs.setMinimumHeight(180)
        self.clubs.itemSelectionChanged.connect(self._sel_club)
        v.addWidget(self.clubs)
        self.nom_club, self.horaire = champ("مثلا: النادي البيئي"), champ("مثلا: الأربعاء 15:00-16:00")
        self.animateur = QComboBox()
        self.objectifs = champ("الأهداف (اختياري)")
        v.addLayout(_grille([("اسم النادي", self.nom_club), ("المنشط(ة)", self.animateur), ("التوقيت", self.horaire)],
                            etirer=0))
        v.addWidget(self.objectifs)
        h = QHBoxLayout()
        for lib, fn in (("تسجيل نادٍ جديد", lambda: self.enregistrer_club(True)),
                        ("حفظ التعديل", lambda: self.enregistrer_club(False)),
                        ("حذف النادي", lambda: self.supprimer_club()),
                        ("لائحة الأعضاء (Word)", lambda: self.liste_club())):
            b = QPushButton(lib)
            b.clicked.connect(fn)
            h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        t = QLabel("أعضاء النادي المحدد")
        t.setObjectName("titreCarte")
        v.addWidget(t)
        self.recherche = champ("ابحث عن تلميذ بالاسم أو رمز مسار لإضافته")
        self.recherche.textChanged.connect(lambda _: self._chercher())
        self.candidats = QComboBox()
        self.role = champ("المهمة (اختياري): رئيس النادي، كاتب...")
        v.addLayout(_grille([("البحث", self.recherche), ("التلميذ", self.candidats), ("المهمة", self.role)], etirer=0))
        h = QHBoxLayout()
        b = QPushButton("إضافة إلى النادي")
        b.clicked.connect(lambda: self.ajouter_membre())
        h.addWidget(b)
        b = QPushButton("سحب العضو المحدد")
        b.clicked.connect(lambda: self.retirer_membre())
        h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        self.membres = tableau(["الاسم", "القسم", "المهمة"], etirer=0)
        self.membres.setMinimumHeight(180)
        v.addWidget(self.membres)
        racine.addWidget(c)

        # ---- الأنشطة ----
        c, v = carte("البرنامج السنوي للأنشطة وإنجازها")
        h = QHBoxLayout()
        for lib, fn in (("البرنامج السنوي (Word)", lambda: self.document("programme")),
                        ("حصيلة الأنشطة (Word)", lambda: self.document("bilan"))):
            b = QPushButton(lib)
            b.setObjectName("principal")
            b.clicked.connect(fn)
            h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        self.acts = tableau(["فترة الإنجاز", "نوع النشاط", "النشاط", "الحالة", "المشاركون"], etirer=2)
        self.acts.setMinimumHeight(240)
        self.acts.itemSelectionChanged.connect(self._sel_act)
        v.addWidget(self.acts)
        self.type_act, self.club_act, self.statut = QComboBox(), QComboBox(), QComboBox()
        self.type_act.addItems(vs.TYPES)
        for k, lib in vs.STATUTS.items():
            self.statut.addItem(lib, k)
        self.titre_act = champ("العمليات والأنشطة المبرمجة")
        self.intervenants, self.cibles = champ("المتدخلون فيه"), champ("المستهدفون منه")
        self.periode, self.mecanismes = champ("مثلا: شهر أكتوبر"), champ("آليات التنفيذ")
        self.debut, self.fin = ChampDate(), ChampDate()
        self.nb_g, self.nb_f = champ("0", ltr=True), champ("0", ltr=True)
        for w in (self.nb_g, self.nb_f):
            w.setMaximumWidth(80)
        self.bilan = QPlainTextEdit()
        self.bilan.setPlaceholderText("الحصيلة والملاحظات (للنشاط المنجز)")
        self.bilan.setFixedHeight(70)
        v.addLayout(_grille([("نوع النشاط", self.type_act), ("النادي (اختياري)", self.club_act),
                             ("الحالة", self.statut)], etirer=0))
        v.addWidget(etiquette("النشاط", self.titre_act))
        v.addWidget(self.titre_act)
        v.addLayout(_grille([("المتدخلون", self.intervenants), ("المستهدفون", self.cibles)], etirer=0))
        v.addLayout(_grille([("فترة الإنجاز", self.periode), ("من", self.debut), ("إلى", self.fin)], etirer=0))
        v.addLayout(_grille([("آليات التنفيذ", self.mecanismes), ("ذكور", self.nb_g), ("إناث", self.nb_f)], etirer=0))
        v.addWidget(self.bilan)
        h = QHBoxLayout()
        for lib, fn in (("تسجيل نشاط جديد", lambda: self.enregistrer_activite(True)),
                        ("حفظ التعديل", lambda: self.enregistrer_activite(False)),
                        ("حذف النشاط", lambda: self.supprimer_activite())):
            b = QPushButton(lib)
            b.clicked.connect(fn)
            h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        racine.addWidget(c)
        racine.addStretch()
        self.rafraichir()

    # ---------- التحميل ----------

    def rafraichir(self) -> None:
        self.animateur.clear()
        self.animateur.addItem("—", None)
        for p in rh.lister(self.f.conn):
            self.animateur.addItem(f"{p.prenom_ar} {p.nom_ar}", p.id)
        try:
            cs = vs.clubs(self.f.conn)
            b = vs.bilan(self.f.conn)
        except vs.ErreurVie as e:
            message(self.message, str(e), True)
            return
        self.clubs.setRowCount(len(cs))
        self.club_act.clear()
        self.club_act.addItem("—", None)
        for i, cl in enumerate(cs):
            for j, v in enumerate((cl["nom"], cl["animateur"] or "—", cl["horaire"] or "—", str(cl["membres"]),
                                   str(cl["activites"]))):
                self.clubs.setItem(i, j, cellule(v, cl["id"] if j == 0 else None))
            self.club_act.addItem(cl["nom"], cl["id"])
        self.indic.setText(
            f"الأنشطة: مبرمجة {b['programmees']}، منجزة {b['realisees']}"
            + (f" ({b['taux']:.2f}%)" if b["taux"] is not None else "")
            + f" — المشاركون {b['garcons'] + b['filles']} (ذكور {b['garcons']}، إناث {b['filles']}) — "
              f"الأندية {b['clubs']} بـ{b['membres']} عضواً")
        self._acts()
        self._membres()

    def _acts(self) -> None:
        ts = vs.activites(self.f.conn)
        self.acts.setRowCount(len(ts))
        for i, a in enumerate(ts):
            per = a["periode"] or ""
            if a["date_debut"]:
                from idara.services import textes as tx
                per = (per + " " if per else "") + tx.date_chiffres(a["date_debut"])
            part = "—" if a["nb_garcons"] is None else f"{a['nb_garcons'] + (a['nb_filles'] or 0)}"
            for j, v in enumerate((per, a["type"] + (f": {a['club']}" if a["club"] else ""), a["titre"],
                                   vs.STATUTS[a["statut"]], part)):
                self.acts.setItem(i, j, cellule(v, a["id"] if j == 0 else None))

    def _sel(self, t) -> int | None:
        rows = {i.row() for i in t.selectedIndexes()}
        return t.item(rows.pop(), 0).data(Qt.UserRole) if len(rows) == 1 else None

    def _sel_club(self) -> None:
        self.club_id = self._sel(self.clubs)
        if self.club_id:
            c = vs.club(self.f.conn, self.club_id)
            self.nom_club.setText(c["nom"])
            self.horaire.setText(c["horaire"] or "")
            self.objectifs.setText(c["objectifs"] or "")
            self.animateur.setCurrentIndex(max(0, self.animateur.findData(c["animateur_id"])))
        self._membres()

    def _membres(self) -> None:
        ms = vs.membres(self.f.conn, self.club_id) if self.club_id else []
        self.membres.setRowCount(len(ms))
        for i, m in enumerate(ms):
            for j, v in enumerate((f"{m['prenom_ar']} {m['nom_ar']}", (m["classe"] or "").replace("-", ""),
                                   m["role"] or "عضو(ة)")):
                self.membres.setItem(i, j, cellule(v, m["id"] if j == 0 else None))

    def _chercher(self) -> None:
        self.candidats.clear()
        t = self.recherche.text().strip()
        if len(t) < 2:
            return
        for r in el.rechercher(self.f.conn, t)[:30]:
            self.candidats.addItem(f"{el.nom_complet(r)} ({r['code_massar']})", r["id"])

    def _sel_act(self) -> None:
        self.act_id = self._sel(self.acts)
        if not self.act_id:
            return
        a = vs.activite(self.f.conn, self.act_id)
        self.type_act.setCurrentText(a.type)
        self.club_act.setCurrentIndex(max(0, self.club_act.findData(a.club_id)))
        self.statut.setCurrentIndex(max(0, self.statut.findData(a.statut)))
        for w, val in ((self.titre_act, a.titre), (self.intervenants, a.intervenants), (self.cibles, a.cibles),
                       (self.periode, a.periode), (self.mecanismes, a.mecanismes)):
            w.setText(val or "")
        self.debut.definir(a.date_debut or "")
        self.fin.definir(a.date_fin or "")
        self.nb_g.setText("" if a.nb_garcons is None else str(a.nb_garcons))
        self.nb_f.setText("" if a.nb_filles is None else str(a.nb_filles))
        self.bilan.setPlainText(a.bilan or "")

    # ---------- الأفعال ----------

    def _faire(self, fn, succes: str):
        try:
            r = fn()
        except (vs.ErreurVie, ValueError) as e:
            message(self.message, str(e) or "قيمة غير صحيحة.", True)
            return None
        self.rafraichir()
        message(self.message, succes)
        return True if r is None else r

    def enregistrer_club(self, nouveau: bool):
        if not nouveau and not self.club_id:
            message(self.message, "حدد نادياً في الجدول.", True)
            return None
        return self._faire(lambda: vs.enregistrer_club(self.f.conn, self.nom_club.text(), self.animateur.currentData(),
                                                       self.objectifs.text(), self.horaire.text(),
                                                       None if nouveau else self.club_id), "حُفظ النادي.")

    def supprimer_club(self):
        if not self.club_id:
            return None
        r = self._faire(lambda: vs.supprimer_club(self.f.conn, self.club_id), "حُذف النادي.")
        self.club_id = None
        return r

    def ajouter_membre(self):
        if not self.club_id or self.candidats.currentData() is None:
            message(self.message, "حدد نادياً ثم تلميذاً.", True)
            return None
        return self._faire(lambda: vs.ajouter_membre(self.f.conn, self.club_id, self.candidats.currentData(),
                                                     self.role.text()), "أضيف العضو.")

    def retirer_membre(self):
        eid = self._sel(self.membres)
        if not (self.club_id and eid):
            return None
        return self._faire(lambda: vs.retirer_membre(self.f.conn, self.club_id, eid), "سُحب العضو.")

    def _date(self, w: ChampDate) -> str:
        if not w.text().strip("/_ "):
            return ""
        try:
            return w.iso()
        except ValueError:
            raise vs.ErreurVie("تاريخ غير صحيح.") from None

    def enregistrer_activite(self, nouveau: bool):
        if not nouveau and not self.act_id:
            message(self.message, "حدد نشاطاً في الجدول.", True)
            return None

        def fn():
            a = vs.Activite(self.type_act.currentText(), self.titre_act.text(), self.club_act.currentData(),
                            self.intervenants.text(), self.cibles.text(), self.periode.text(),
                            self._date(self.debut), self._date(self.fin), self.mecanismes.text(),
                            self.statut.currentData(), self.nb_g.text(), self.nb_f.text(), self.bilan.toPlainText(),
                            None if nouveau else self.act_id)
            return vs.enregistrer_activite(self.f.conn, a)
        return self._faire(fn, "حُفظ النشاط.")

    def supprimer_activite(self):
        if not self.act_id:
            return None
        r = self._faire(lambda: vs.supprimer_activite(self.f.conn, self.act_id), "حُذف النشاط.")
        self.act_id = None
        return r

    def _ouvrir(self, p: Path) -> Path:
        message(self.message, f"وُلّدت الوثيقة: {p.name}")
        try:
            bureautique.ouvrir(p)
        except Exception:  # noqa: BLE001 — الفتح اختياري
            pass
        return p

    def document(self, code: str) -> Path | None:
        fn = {"programme": vs.generer_programme, "bilan": vs.generer_bilan}[code]
        try:
            return self._ouvrir(fn(self.f.conn, self.f.dossier))
        except vs.ErreurVie as e:
            message(self.message, str(e), True)
            return None

    def liste_club(self) -> Path | None:
        if not self.club_id:
            message(self.message, "حدد نادياً في الجدول.", True)
            return None
        try:
            return self._ouvrir(vs.generer_liste_club(self.f.conn, self.f.dossier, self.club_id))
        except vs.ErreurVie as e:
            message(self.message, str(e), True)
            return None
