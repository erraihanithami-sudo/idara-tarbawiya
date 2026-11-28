"""ترقية الأساتذة (طلب المدير 2026-11-28): صفحة لكل نوع: الترقية في الرتبة، والترقية في الدرجة بالاختيار،
والترقية بامتحان الكفاءة المهنية. تُعرض المعنيات حسب السنة (الترقيات تتم متأخرة: في 2026 تُعرض المعنيات برسم 2025)،
وتسجيل الترقية في بطاقة الأستاذ(ة) في نافذة منبثقة."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QComboBox, QFormLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from idara.services import bureautique
from idara.services import personnel as rh
from idara.services import tarqiya as tq
from idara.services import textes as tx
from idara.ui.composants import carte, entete
from idara.ui.saisie import ChampDate, cellule, message, tableau
from idara.ui.vitrine import FenetreFiche, bouton_couleur

SOUS = {
    "rang": "المعنيون بالانتقال إلى الرتبة الموالية خلال السنة المختارة، حسب أنساق المادة 49 من المرسوم 2.24.140، "
            "والترقيات المستحقة قبلها التي لم تُحيَّن بعد.",
    "choix": "المستوفون لشروط الترقي إلى الدرجة الأولى أو الممتازة بالاختيار برسم السنة المختارة (المادة 50)، مرتبين "
             "حسب الأقدمية في الدرجة ثم الأقدمية العامة.",
    "examen": "أساتذة الدرجة الثانية المستوفون لشرط امتحان الكفاءة المهنية لولوج الدرجة الأولى (6 سنوات في الدرجة "
              "إلى غاية 31 دجنبر)، مع بطاقة النقطة المهنية (نموذج رقم 1).",
}
COLONNES = {
    "rang": ["الاسم الكامل", "رقم التأجير", "الدرجة", "الرتبة الحالية", "تاريخها", "النسق", "الرتبة المرتقبة",
             "تاريخ الاستحقاق"],
    "choix": ["الاسم الكامل", "رقم التأجير", "الدرجة الحالية", "تاريخها", "الرتبة", "الأقدمية في الدرجة",
              "الدرجة المرتقبة", "التقييد", "ملاحظات"],
    "examen": ["الاسم الكامل", "رقم التأجير", "التخصص", "تاريخ الدرجة الثانية", "الرتبة", "الأقدمية في 31 دجنبر",
               "ملاحظات"],
}
COULEURS = {"rang": "#1565C0", "choix": "#6A1B9A", "examen": "#C62828"}


def liste_fixe(valeurs) -> QComboBox:
    c = QComboBox()
    c.addItems(list(valeurs))
    return c


class PageTarqiya(QWidget):
    def __init__(self, fenetre, type_: str = "rang"):
        super().__init__()
        self.f = fenetre
        self.type_ = type_
        self.lignes: list[tq.Concerne] = []
        racine = QVBoxLayout(self)
        racine.setContentsMargins(40, 32, 40, 32)
        racine.setSpacing(16)
        racine.addWidget(entete(tq.TYPES[type_], SOUS[type_]))
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.hide()
        racine.addWidget(self.message)

        # السنة والشروط
        c, v = carte("برسم سنة")
        h = QHBoxLayout()
        self.c_annee = QComboBox()
        for y in tq.annees_proposees():
            self.c_annee.addItem(str(y), y)
        self.c_annee.setCurrentIndex(max(0, self.c_annee.findData(tq.annee_defaut(type_))))
        self.c_annee.currentIndexChanged.connect(lambda _: self.rafraichir())
        h.addWidget(QLabel("السنة"))
        h.addWidget(self.c_annee)
        self.l_compte = QLabel()
        self.l_compte.setStyleSheet(f"font-size: 16px; font-weight: 800; color: {COULEURS[type_]};")
        h.addWidget(self.l_compte, 1)
        v.addLayout(h)
        self.l_examen = QLabel()
        self.l_examen.setWordWrap(True)
        self.l_examen.setStyleSheet("background: #FFF4E5; border: 1px solid #F0C27A; border-radius: 8px; "
                                    "padding: 10px; font-weight: 700; color: #7A4A00;")
        self.l_examen.hide()
        v.addWidget(self.l_examen)
        regles = QLabel("\n".join(f"• {r}" for r in tq.REGLES[type_]))
        regles.setWordWrap(True)
        regles.setObjectName("etiquette")
        v.addWidget(regles)
        racine.addWidget(c)

        # اللائحة
        c, v = carte("الأساتذة المعنيون")
        self.table = tableau(COLONNES[type_], etirer=len(COLONNES[type_]) - 1 if type_ != "rang" else 0)
        self.table.setMinimumHeight(320)
        self.table.setWordWrap(True)
        self.table.itemDoubleClicked.connect(lambda it: self.ouvrir_promotion(it.row()))
        if type_ == "examen":
            from PySide6.QtWidgets import QAbstractItemView
            self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        v.addWidget(self.table)
        h = QHBoxLayout()
        actions = [("تسجيل الترقية", "#2E7D32", "valider", lambda: self.ouvrir_promotion(self._ligne()),
                    "تحيين الدرجة والرتبة في بطاقة الأستاذ(ة) بعد صدور قرار الترقية")]
        if type_ == "rang":
            actions.append(("نسق الترقي", "#546E7A", "modifier", lambda: self.ouvrir_rythme(self._ligne()),
                            "سريع، متوسط أو بطيء حسب النقطة المحصل عليها"))
        actions.append(("لائحة المعنيين (Word)", COULEURS[type_], "document", lambda: self.generer(),
                        "لائحة مؤرخة موقعة من المدير(ة)"))
        if type_ == "examen":
            actions.append(("بطاقات النقطة المهنية (نموذج 1)", "#B8860B", "imprimer", lambda: self.generer_fiches(),
                            "للمحددين في اللائحة، أو للجميع إن لم يُحدَّد أحد"))
        for lib, coul, pic, fn, aide in actions:
            b = bouton_couleur(lib, coul, pic, aide)
            b.clicked.connect(fn)
            h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        racine.addWidget(c)

        # ما يحتاج تحييناً
        c, v = carte("معطيات تحتاج إلى تحيين")
        self.l_vide = QLabel()
        self.l_vide.setWordWrap(True)
        v.addWidget(self.l_vide)
        self.t_retard = None
        if type_ == "rang":
            self.t_retard = tableau(["الاسم الكامل", "الرتبة المسجلة", "تاريخها", "الرتبة المستحقة", "منذ"], etirer=0)
            self.t_retard.setMinimumHeight(160)
            v.addWidget(self.t_retard)
        self.t_manque = tableau(["الأستاذ(ة)", "المعطيات الناقصة في بطاقة الإطار"], etirer=1)
        self.t_manque.setMinimumHeight(140)
        v.addWidget(self.t_manque)
        racine.addWidget(c)
        racine.addStretch()

        self._fiche_promotion()
        self._fiche_rythme()
        self.rafraichir()

    # ---------- النوافذ ----------
    def _fiche_promotion(self) -> None:
        w = QWidget()
        vv = QVBoxLayout(w)
        self.l_qui = QLabel()
        self.l_qui.setWordWrap(True)
        self.l_qui.setStyleSheet("font-size: 15px; font-weight: 800;")
        vv.addWidget(self.l_qui)
        fl = QFormLayout()
        self.c_grade = liste_fixe(rh.GRADES)
        self.c_echelon = liste_fixe(rh.ECHELONS)
        self.c_date = ChampDate()
        fl.addRow("الدرجة بعد الترقية", self.c_grade)
        fl.addRow("الرتبة بعد الترقية", self.c_echelon)
        fl.addRow("تاريخ المفعول", self.c_date)
        vv.addLayout(fl)
        note = QLabel("في الترقية في الدرجة يُقترح الترتيب في الرتبة التي تقل مباشرة عن الرتبة الأصلية (المادة 52)، "
                      "وفي الرتبة 1 من الدرجة الممتازة. راجع ذلك وتاريخ المفعول مع قرار الترقية.")
        note.setWordWrap(True)
        note.setObjectName("etiquette")
        vv.addWidget(note)
        b = bouton_couleur("تسجيل في بطاقة الأستاذ(ة)", "#2E7D32", "enregistrer")
        b.clicked.connect(lambda: self.enregistrer_promotion())
        vv.addWidget(b, 0, Qt.AlignRight)
        self.msg_promo = QLabel()
        self.msg_promo.setWordWrap(True)
        self.msg_promo.hide()
        vv.addWidget(self.msg_promo)
        self.fiche_promo = FenetreFiche(self, "تسجيل الترقية", "تُحيَّن الدرجة والرتبة وتاريخهما، وتُحفظ في سجل "
                                        "الترقيات.", w, largeur=640)

    def _fiche_rythme(self) -> None:
        w = QWidget()
        vv = QVBoxLayout(w)
        self.l_qui_r = QLabel()
        self.l_qui_r.setStyleSheet("font-weight: 800;")
        vv.addWidget(self.l_qui_r)
        self.c_rythme = QComboBox()
        for k, lib in tq.RYTHMES.items():
            self.c_rythme.addItem(lib, k)
        fl = QFormLayout()
        fl.addRow("نسق الترقي في الرتبة", self.c_rythme)
        vv.addLayout(fl)
        b = bouton_couleur("حفظ", "#2E7D32", "enregistrer")
        b.clicked.connect(lambda: self.enregistrer_rythme())
        vv.addWidget(b, 0, Qt.AlignRight)
        self.fiche_rythme = FenetreFiche(self, "نسق الترقي", "يُعتمد السريع ما لم يُحدَّد غيره.", w, largeur=480)

    # ---------- العرض ----------
    def annee(self) -> int:
        return self.c_annee.currentData()

    def _ligne(self) -> int | None:
        r = self.table.currentRow()
        return r if 0 <= r < len(self.lignes) else None

    def rafraichir(self) -> None:
        y = self.annee()
        retard = []
        if self.type_ == "rang":
            self.lignes, retard = tq.concernes_rang(self.f.conn, y)
        else:
            self.lignes = tq.concernes(self.f.conn, self.type_, y)
        self.table.setRowCount(len(self.lignes))
        for i, c in enumerate(self.lignes):
            if self.type_ == "rang":
                vals = (c.nom, c.ppr, c.grade, tq._libelle_rang(tq._rang(c.echelon), c.grade),
                        tx.date_chiffres(c.date_echelon), c.rythme, c.vers, tx.date_chiffres(c.date_droit))
            elif self.type_ == "choix":
                vals = (c.nom, c.ppr, c.grade, tx.date_chiffres(c.date_grade), c.echelon, tq._ans(c.anciennete),
                        c.vers, f"المرة {c.inscription}" + (" (دون حصيص)" if c.sans_quota else ""), c.remarque)
            else:
                vals = (c.nom, c.ppr, c.extra.get("matiere", ""), tx.date_chiffres(c.date_grade), c.echelon,
                        tq._ans(c.anciennete), c.remarque)
            for j, x in enumerate(vals):
                it = cellule(x, c.pid if j == 0 else None)
                if self.type_ == "choix" and j == 7 and c.sans_quota:
                    it.setForeground(QColor("#2E7D32"))
                self.table.setItem(i, j, it)
        self.table.resizeRowsToContents()
        n = len(self.lignes)
        self.l_compte.setText(f"{n} معني(ة) برسم سنة {y}" if n else f"لا معنيين برسم سنة {y} حسب المعطيات المسجلة")
        ex = tq.EXAMENS.get(y)
        if self.type_ == "examen" and ex:
            self.l_examen.setText(
                f"دورة {y} ({ex['memo']}): الاختبارات يوم {tx.date_ar(ex['date'])}. الترشيح الإلكتروني عبر "
                f"{ex['portail']} من {tx.date_chiffres(ex['candidature'][0])} إلى {tx.date_chiffres(ex['candidature'][1])} "
                f"(الرابعة والنصف بعد الزوال)، وإيداع الملفات في أجل أقصاه {tx.date_chiffres(ex['depot'])}. "
                f"الاختباران: {'؛ '.join(ex['epreuves'])}. تقييم الأداء المهني قبل {tx.date_chiffres(ex['note_pro'])}.")
            self.l_examen.show()
        elif self.type_ == "examen":
            self.l_examen.setText(f"لم تُسجَّل في البرنامج مذكرة امتحانات الكفاءة المهنية برسم سنة {y}: تواريخ الدورة "
                                  "تُعلن بمذكرة وزارية.")
            self.l_examen.show()
        if self.t_retard is not None:
            self.t_retard.setRowCount(len(retard))
            for i, c in enumerate(retard):
                for j, x in enumerate((c.nom, tq._libelle_rang(tq._rang(c.echelon), c.grade),
                                       tx.date_chiffres(c.date_echelon), c.vers, tx.date_chiffres(c.date_droit))):
                    self.t_retard.setItem(i, j, cellule(x))
            self.t_retard.setVisible(bool(retard))
        manq = tq.manquants(self.f.conn, self.type_)
        self.t_manque.setRowCount(len(manq))
        for i, (nom, m) in enumerate(manq):
            self.t_manque.setItem(i, 0, cellule(nom))
            self.t_manque.setItem(i, 1, cellule(m))
        self.t_manque.setVisible(bool(manq))
        parts = []
        if retard:
            parts.append(f"{len(retard)} ترقية في الرتبة مستحقة قبل سنة {y} ولم تُحيَّن الرتبة بعدها.")
        if manq:
            parts.append(f"{len(manq)} أستاذ(ة) تنقص بطاقاتهم معطيات الحساب: أكملها في «الموارد البشرية».")
        self.l_vide.setText(" ".join(parts) if parts else "المعطيات اللازمة للحساب مكتملة لكل الأساتذة.")

    # ---------- الأفعال ----------
    def _erreur(self, lab: QLabel, t: str) -> None:
        lab.setText(t)
        lab.setObjectName("erreur")
        lab.setStyleSheet("color: #C62828; font-weight: 700;")
        lab.show()

    def ouvrir_promotion(self, i: int | None):
        if i is None:
            message(self.message, "حدد أستاذاً(ة) في اللائحة.", True)
            return None
        c = self.lignes[i]
        self.pid = c.pid
        self.l_qui.setText(f"{c.nom} · {c.grade} · {tq._libelle_rang(tq._rang(c.echelon), c.grade)} → {c.vers}")
        if self.type_ == "rang":
            g = c.grade
            e = tq.EXC if c.vers == "الرتبة الاستثنائية" else c.vers.removeprefix("الرتبة ")
            self.c_date.definir(c.date_droit)
        else:
            g, e = tq.reclassement(c)
            self.c_date.definir(None)
        self.c_grade.setCurrentIndex(max(0, self.c_grade.findText(g)))
        self.c_echelon.setCurrentIndex(max(0, self.c_echelon.findText(e)))
        self.msg_promo.hide()
        self.fiche_promo.ouvrir()
        return self.fiche_promo

    def enregistrer_promotion(self) -> bool:
        try:
            tq.enregistrer_promotion(self.f.conn, self.pid, self.type_, self.c_date.iso(), self.c_echelon.currentText(),
                                     self.c_grade.currentText(), self.annee())
        except (tq.ErreurTarqiya, rh.ErreurPersonnel) as e:
            self._erreur(self.msg_promo, str(e))
            return False
        except ValueError:
            self._erreur(self.msg_promo, "تاريخ المفعول غير صحيح.")
            return False
        self.fiche_promo.hide()
        message(self.message, "سُجّلت الترقية في بطاقة الأستاذ(ة).")
        self.rafraichir()
        return True

    def ouvrir_rythme(self, i: int | None):
        if i is None:
            message(self.message, "حدد أستاذاً(ة) في اللائحة.", True)
            return None
        c = self.lignes[i]
        self.pid = c.pid
        self.l_qui_r.setText(c.nom)
        self.c_rythme.setCurrentIndex(max(0, self.c_rythme.findData(tq.rythmes(self.f.conn).get(str(c.pid), "rapide"))))
        self.fiche_rythme.ouvrir()
        return self.fiche_rythme

    def enregistrer_rythme(self) -> bool:
        tq.definir_rythme(self.f.conn, self.pid, self.c_rythme.currentData())
        self.fiche_rythme.hide()
        self.rafraichir()
        return True

    def generer(self) -> Path | None:
        try:
            p = tq.generer_liste(self.f.conn, self.f.dossier, self.type_, self.annee())
        except tq.ErreurTarqiya as e:
            message(self.message, str(e), True)
            return None
        message(self.message, f"وُلّدت اللائحة: {p.name}")
        try:
            bureautique.ouvrir(p)
        except Exception:  # noqa: BLE001
            pass
        return p

    def generer_fiches(self) -> Path | None:
        rows = sorted({ix.row() for ix in self.table.selectedIndexes()})
        pids = [self.lignes[r].pid for r in rows if r < len(self.lignes)] or [c.pid for c in self.lignes]
        try:
            p = tq.generer_fiches_note(self.f.conn, self.f.dossier, pids, self.annee())
        except tq.ErreurTarqiya as e:
            message(self.message, str(e), True)
            return None
        message(self.message, f"وُلّدت {len(pids)} بطاقة للنقطة المهنية: {p.name}")
        try:
            bureautique.ouvrir(p)
        except Exception:  # noqa: BLE001
            pass
        return p
