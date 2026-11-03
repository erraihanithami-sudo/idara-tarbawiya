"""برنامج العمل السنوي: محطات المقرر الوزاري (تصل مع تحديث البرنامج) ومحطات المؤسسة، والتذكيرات
(اقتراح المدير 2026-11-03)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox, QVBoxLayout,
                               QWidget)

from idara.services import annee as annee_srv
from idara.services import bureautique
from idara.services import calendrier as cal
from idara.services import textes as tx
from idara.ui.composants import bouton, carte
from idara.ui.page_pedagogie import _grille, _page
from idara.ui.saisie import ChampDate, cellule, message, tableau

ETATS = {"en_cours": "جارية", "a_venir": "قادمة", "en_retard": "فاتت دون تعليمها منجزة"}


class PageCalendrier(QWidget):
    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        self.sid: int | None = None
        racine, self.message = _page("برنامج العمل السنوي",
                                     "محطات المقرر الوزاري لتنظيم السنة الدراسية ومحطات المؤسسة، مع التذكير بها.")
        self.setLayout(racine)
        self.l_mouqarrar = QLabel()
        self.l_mouqarrar.setWordWrap(True)
        self.l_mouqarrar.setObjectName("etiquette")
        racine.addWidget(self.l_mouqarrar)

        # ---- التذكيرات ----
        c, v = carte("التذكيرات")
        self.t_rappels = tableau(["الحالة", "التاريخ", "المحطة", "المرجع"], etirer=2)
        v.addWidget(self.t_rappels)
        h = QHBoxLayout()
        self.b_fait = QPushButton("تعليم المحددة كمنجزة")
        self.b_fait.clicked.connect(lambda: self.marquer_selection(self.t_rappels, True))
        self.b_aller = QPushButton("فتح الصفحة المعنية")
        self.b_aller.clicked.connect(self.aller_lien)
        h.addWidget(self.b_fait)
        h.addWidget(self.b_aller)
        h.addStretch()
        v.addLayout(h)
        racine.addWidget(c)

        # ---- كل المحطات ----
        c, v = carte("محطات السنة")
        self.f_mois = QComboBox()
        self.f_mois.currentIndexChanged.connect(lambda _: self.afficher_stations())
        self.f_source = QComboBox()
        for lib, d in (("الوزارية والمحلية", None), ("الوزارية فقط", "m"), ("المحلية فقط", "l")):
            self.f_source.addItem(lib, d)
        self.f_source.currentIndexChanged.connect(lambda _: self.afficher_stations())
        v.addLayout(_grille([("الشهر", self.f_mois), ("المصدر", self.f_source)]))
        self.t_stations = tableau(["التاريخ", "المحطة", "النوع", "المعنيون", "المرجع", "منجزة"], etirer=1)
        self.t_stations.setMinimumHeight(360)
        self.t_stations.itemSelectionChanged.connect(self._selection)
        v.addWidget(self.t_stations)
        h = QHBoxLayout()
        b = QPushButton("تعليم المحددة كمنجزة")
        b.clicked.connect(lambda: self.marquer_selection(self.t_stations, True))
        b2 = QPushButton("إلغاء التعليم")
        b2.clicked.connect(lambda: self.marquer_selection(self.t_stations, False))
        self.b_programme = QPushButton("توليد برنامج العمل السنوي (Word)")
        self.b_programme.setObjectName("principal")
        self.b_programme.clicked.connect(lambda: self.generer())
        for x in (b, b2, self.b_programme):
            h.addWidget(x)
        h.addStretch()
        v.addLayout(h)
        racine.addWidget(c)

        # ---- محطة محلية ----
        c, v = carte("محطة خاصة بالمؤسسة")
        self.titre = QLineEdit()
        self.titre.setPlaceholderText("مثال: اجتماع مجلس التدبير، حفل نهاية السنة، زيارة...")
        self.type = QComboBox()
        for k in cal.TYPES_LOCAUX:
            self.type.addItem(cal.TYPES[k], k)
        self.debut, self.fin = ChampDate(), ChampDate()
        self.rappel = QSpinBox()
        self.rappel.setRange(0, 120)
        self.rappel.setValue(7)
        self.rappel.setSuffix(" يوماً")
        self.remarque = QLineEdit()
        v.addLayout(_grille([("العنوان", self.titre), ("النوع", self.type)], etirer=0))
        v.addLayout(_grille([("من", self.debut), ("إلى (اختياري)", self.fin), ("التذكير قبل", self.rappel),
                             ("ملاحظة", self.remarque)], etirer=3))
        h = QHBoxLayout()
        b = QPushButton("إضافة محطة")
        b.clicked.connect(lambda: self.enregistrer(True))
        self.b_modifier = QPushButton("حفظ التعديل")
        self.b_modifier.clicked.connect(lambda: self.enregistrer(False))
        self.b_suppr = bouton("حذف المحطة")
        self.b_suppr.clicked.connect(lambda: self.supprimer())
        for x in (b, self.b_modifier, self.b_suppr):
            h.addWidget(x)
        h.addStretch()
        v.addLayout(h)
        racine.addWidget(c)
        racine.addStretch()
        self.rafraichir()

    # ---------- العرض ----------
    def rafraichir(self) -> None:
        a = annee_srv.annee_courante(self.f.conn)
        m = cal.mouqarrar(a["libelle"]) if a else None
        if m:
            mq = m["mouqarrar"]
            self.l_mouqarrar.setText(f"المرجع: {mq['titre']}، رقم {mq['numero']} بتاريخ {tx.date_ar(mq['date'])}. "
                                     f"{m['perimetre']} تواريخ الأعياد الدينية تقديرية حسب ثبوت رؤية الهلال.")
        else:
            self.l_mouqarrar.setText("لم يُرفق بالبرنامج بعد مقرر تنظيم السنة الدراسية "
                                     f"{a['libelle'] if a else ''}. يصل مع تحديث البرنامج عند صدوره؛ "
                                     "يمكنك إضافة محطات المؤسسة في انتظار ذلك.")
        self.stations = cal.stations(self.f.conn) if a else []
        mois = sorted({(s.debut.year, s.debut.month) for s in self.stations})
        actuel = self.f_mois.currentData()
        self.f_mois.blockSignals(True)
        self.f_mois.clear()
        self.f_mois.addItem("كل الأشهر", None)
        for y, mo in mois:
            self.f_mois.addItem(f"{tx.MOIS_AR[mo - 1]} {y}", (y, mo))
        i = self.f_mois.findData(actuel)
        self.f_mois.setCurrentIndex(max(0, i))
        self.f_mois.blockSignals(False)
        self.afficher_rappels()
        self.afficher_stations()
        self._remplir(None)

    def afficher_rappels(self, le: date | None = None) -> None:
        r = cal.rappels(self.f.conn, le) if self.stations else {k: [] for k in ETATS}
        lignes = [(k, s) for k in ("en_retard", "en_cours", "a_venir") for s in r[k]]
        self.t_rappels.setRowCount(len(lignes))
        for i, (k, s) in enumerate(lignes):
            self.t_rappels.setItem(i, 0, cellule(ETATS[k], s.cle))
            self.t_rappels.setItem(i, 1, cellule(s.periode))
            self.t_rappels.setItem(i, 2, cellule(s.titre))
            self.t_rappels.setItem(i, 3, cellule(s.reference))
        if not lignes:
            self.t_rappels.setRowCount(1)
            self.t_rappels.setItem(0, 0, cellule("—"))
            self.t_rappels.setItem(0, 2, cellule("لا تذكيرات حالياً."))
        self.t_rappels.setMinimumHeight(min(320, 60 + 40 * max(1, len(lignes))))
        self.rappels = r

    def afficher_stations(self) -> None:
        mois, src = self.f_mois.currentData(), self.f_source.currentData()
        liste = [s for s in getattr(self, "stations", [])
                 if (mois is None or (s.debut.year, s.debut.month) == tuple(mois))
                 and (src is None or s.cle.startswith(src + ":"))]
        self.t_stations.setRowCount(len(liste))
        for i, s in enumerate(liste):
            pub = "، ".join(cal.PUBLICS.get(p, p) for p in s.public)
            if s.niveaux:
                pub += " (" + "، ".join(tx.niveau_ar(n) for n in s.niveaux if n in tx.NIVEAUX) + ")"
            self.t_stations.setItem(i, 0, cellule(s.periode, s.cle))
            it = cellule(s.titre)
            if s.note:
                it.setToolTip(s.note)
            self.t_stations.setItem(i, 1, it)
            self.t_stations.setItem(i, 2, cellule(s.libelle_type))
            self.t_stations.setItem(i, 3, cellule(pub or "المؤسسة"))
            self.t_stations.setItem(i, 4, cellule(s.reference))
            self.t_stations.setItem(i, 5, cellule(tx.date_ar(s.fait_le) if s.fait_le else ""))
        self.t_stations.resizeRowsToContents()

    def _cles(self, t) -> list[str]:
        rows = sorted({i.row() for i in t.selectedIndexes()})
        return [t.item(r, 0).data(Qt.UserRole) for r in rows if t.item(r, 0) and t.item(r, 0).data(Qt.UserRole)]

    def _selection(self) -> None:
        cles = self._cles(self.t_stations)
        s = next((x for x in self.stations if cles and x.cle == cles[0] and x.locale), None) if len(cles) == 1 else None
        self._remplir(s)

    def _remplir(self, s: cal.Station | None) -> None:
        self.sid = s.id if s else None
        self.titre.setText(s.titre if s else "")
        self.type.setCurrentIndex(max(0, self.type.findData(s.type if s else "local")))
        self.debut.definir(s.debut.isoformat() if s else None)
        self.fin.definir(s.fin.isoformat() if s and s.fin != s.debut else None)
        self.rappel.setValue(s.rappel_jours if s else 7)
        self.remarque.setText(s.note if s else "")
        self.b_modifier.setEnabled(s is not None)
        self.b_suppr.setEnabled(s is not None)

    # ---------- الإجراءات ----------
    def marquer_selection(self, t, fait: bool) -> int:
        cles = self._cles(t)
        for k in cles:
            cal.marquer(self.f.conn, k, fait)
        if cles:
            self.rafraichir()
            message(self.message, ("عُلّمت منجزة: " if fait else "أُلغي التعليم: ") + str(len(cles)))
        return len(cles)

    def aller_lien(self) -> None:
        cles = self._cles(self.t_rappels)
        s = next((x for x in self.stations if cles and x.cle == cles[0]), None)
        if s and s.lien and s.lien in self.f.emplacement:
            self.f.aller_a(s.lien)
        elif s:
            message(self.message, "لا صفحة مرتبطة بهذه المحطة في البرنامج.")

    def enregistrer(self, nouvelle: bool) -> int | None:
        try:
            sid = cal.enregistrer_locale(self.f.conn, self.titre.text(), self.debut.iso(), self.fin.iso(),
                                         self.type.currentData(), self.rappel.value(), self.remarque.text().strip(),
                                         None if nouvelle else self.sid)
        except (cal.ErreurCalendrier, ValueError) as e:
            message(self.message, str(e) or "تاريخ غير صحيح.", True)
            return None
        self.rafraichir()
        message(self.message, "أُضيفت المحطة." if nouvelle else "حُفظ التعديل.")
        return sid

    def supprimer(self) -> bool:
        if self.sid is None:
            return False
        cal.supprimer_locale(self.f.conn, self.sid)
        self.rafraichir()
        message(self.message, "حُذفت المحطة.")
        return True

    def generer(self) -> Path | None:
        try:
            p = cal.generer_programme(self.f.conn, self.f.dossier)
        except cal.ErreurCalendrier as e:
            message(self.message, str(e), True)
            return None
        message(self.message, f"وُلّد برنامج العمل السنوي: {p.name}")
        try:
            bureautique.ouvrir(p)
        except Exception:  # noqa: BLE001 — الفتح اختياري
            pass
        return p
