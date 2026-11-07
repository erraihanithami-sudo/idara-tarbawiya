"""التنظيم التربوي (تحت «التدبير التربوي»): معطيات الأطر في صفحة واحدة، وزر توليد الوثيقة على نموذج المدير."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QLabel, QPushButton, QWidget

from idara.services import bureautique
from idara.services import personnel as rh
from idara.services import etablissement as et_srv
from idara.services import tanzim as tz
from idara.services import textes as tx
from idara.ui.composants import carte
from idara.ui.formulaires import champ
from idara.ui.page_pedagogie import _grille, _page
from idara.ui.saisie import cellule, message, tableau


def _d(v) -> str:
    return tx.date_chiffres(v) if v else "—"


def _note(p: rh.Personnel) -> str:
    if p.sans_inspection:
        return "لم يُفتَّش بعد"
    if p.note_inspection in (None, ""):
        return "—"
    return f"{float(p.note_inspection):g} ({_d(p.date_inspection)}) · {p.inspecteur or '—'}"


class PageTanzim(QWidget):
    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        racine, self.message = _page("التنظيم التربوي",
                                     "معطيات الأطر للموسم الدراسي كما في نموذج «التنظيم التربوي». تُدخل وتُصحح في "
                                     "«الموارد البشرية ← معلومات الأطر»؛ والبنية التربوية تُحسب من لوائح مسار.")
        self.setLayout(racine)

        c, v = carte("المفتشون التربويون")
        self.insp = {k: champ("اسم المفتش(ة)") for k in tz.INSPECTEURS}
        v.addLayout(_grille([(lib, self.insp[k]) for k, lib in tz.INSPECTEURS.items()]))
        b = QPushButton("حفظ المفتشين")
        b.clicked.connect(lambda: self.enregistrer_inspecteurs())
        v.addWidget(b)
        racine.addWidget(c)

        self.tables = {}
        for cle, titre, cols in (
                ("administration", "هيئة الإدارة التربوية",
                 ["الاسم الكامل", "رقم التأجير", "تاريخ التوظيف", "تاريخ المهمة الحالية", "تاريخ الالتحاق"]),
                ("assistants", "المساعدون التربويون", ["الاسم الكامل", "رقم البطاقة الوطنية", "تاريخ الالتحاق"]),
                ("structure", "البنية التربوية", ["المستوى", "عدد الأفواج", "التلاميذ بكل فوج", "المجموع", "المعدل"]),
                ("enseignants", "هيئة التدريس",
                 ["الوحدة", "الاسم", "رقم التأجير", "التوظيف", "الالتحاق", "الدرجة", "الرتبة", "آخر تفتيش",
                  "المادة (TaRL / إرساء)", "الأقسام", "عدد"]),
                ("charges_in", "الأساتذة المكلفون بالمؤسسة",
                 ["الوحدة", "الاسم", "رقم التأجير", "المؤسسة الأصلية", "تاريخ التكليف", "الدرجة", "الرتبة",
                  "آخر تفتيش", "الأقسام"]),
                ("charges_out", "الأساتذة المكلفون خارج المؤسسة",
                 ["الوحدة", "الاسم", "رقم التأجير", "مؤسسة التكليف", "تاريخ التكليف", "الدرجة", "الرتبة",
                  "آخر تفتيش"])):
            c, v = carte(titre)
            t = tableau(cols, etirer=1 if cle != "structure" else 2)
            t.setWordWrap(True)
            v.addWidget(t)
            self.tables[cle] = t
            racine.addWidget(c)

        c, v = carte("الوثيقة")
        self.l_manquants = QLabel()
        self.l_manquants.setObjectName("erreur")
        self.l_manquants.setWordWrap(True)
        v.addWidget(self.l_manquants)
        self.b_generer = QPushButton("توليد وثيقة التنظيم التربوي (Word)")
        self.b_generer.setObjectName("principal")
        self.b_generer.clicked.connect(lambda: self.generer())
        v.addWidget(self.b_generer)
        racine.addWidget(c)
        racine.addStretch()

    def _remplir(self, cle: str, lignes: list[list[str]]) -> None:
        t = self.tables[cle]
        t.setRowCount(len(lignes))
        for i, l in enumerate(lignes):
            for j, x in enumerate(l):
                t.setItem(i, j, cellule(x or "—"))
        t.setMinimumHeight(min(420, 60 + 34 * max(1, len(lignes))))
        t.resizeRowsToContents()

    def rafraichir(self) -> None:
        conn = self.f.conn
        groupe = et_srv.est_groupe(conn)   # مؤسسة مستقلة: لا عمود للوحدة (قرار المدير 2026-11-07)
        for cle in ("enseignants", "charges_in", "charges_out"):
            self.tables[cle].setColumnHidden(0, not groupe)
        for k, v in tz.inspecteurs(conn).items():
            self.insp[k].setText(v)
        d = tz.donnees(conn)
        nom = lambda p: f"{p.prenom_ar} {p.nom_ar}"  # noqa: E731
        self._remplir("administration", [[nom(p), p.ppr, _d(p.date_recrutement), _d(p.date_fonction),
                                          _d(p.date_affectation)]
                                         for p in d["administration"]])
        self._remplir("assistants", [[nom(p), p.cin, _d(p.date_affectation)] for p in d["assistants"]])
        self._remplir("structure", [[s["libelle"], str(len(s["groupes"])),
                                     " · ".join(f"{c}: {n}" for c, n in s["groupes"]), str(s["total"]),
                                     f"{s['moyenne']:g}" if s["moyenne"] is not None else ""]
                                    for s in d["structure"]])

        def classes(p):
            e = rh.enseignement(conn, p)
            return " / ".join(e["classes"]) or p.niveau_enseigne, e["nb_eleves"]

        lignes = []
        for p in d["enseignants"]:
            cl, nb = classes(p)
            lignes.append([p.unite, nom(p), p.ppr, _d(p.date_recrutement), _d(p.date_affectation),
                           f"{rh.grade_court(p.grade) or '—'} ({_d(p.date_grade)})",
                           f"{p.echelon or '—'} ({_d(p.date_echelon)})", _note(p),
                           f"{p.matiere_tarl or p.matiere or '—'} / {p.matiere or '—'}",
                           f"{p.classes_tarl or cl or '—'} / {cl or '—'}", str(nb if nb is not None else "")])
        self._remplir("enseignants", lignes)
        self._remplir("charges_in", [[p.unite, nom(p), p.ppr, p.etab_charge, _d(p.date_charge),
                                      f"{rh.grade_court(p.grade) or '—'} ({_d(p.date_grade)})",
                                      f"{p.echelon or '—'} ({_d(p.date_echelon)})", _note(p), classes(p)[0]]
                                     for p in d["charges_in"]])
        self._remplir("charges_out", [[p.unite, nom(p), p.ppr, p.etab_charge, _d(p.date_charge),
                                       f"{rh.grade_court(p.grade) or '—'} ({_d(p.date_grade)})",
                                       f"{p.echelon or '—'} ({_d(p.date_echelon)})", _note(p)]
                                      for p in d["charges_out"]])
        m = tz.manquants(conn)
        self.l_manquants.setText("لا تُولَّد الوثيقة قبل إكمال المعطيات التالية:\n• " + "\n• ".join(m) if m else "")
        self.l_manquants.setVisible(bool(m))
        self.b_generer.setEnabled(not m)

    def enregistrer_inspecteurs(self) -> bool:
        try:
            tz.definir_inspecteurs(self.f.conn, {k: w.text() for k, w in self.insp.items()})
        except tz.ErreurTanzim as e:
            message(self.message, str(e), True)
            return False
        message(self.message, "حُفظ المفتشون.")
        return True

    def generer(self) -> Path | None:
        try:
            p = tz.generer(self.f.conn, self.f.dossier)
        except tz.ErreurTanzim as e:
            message(self.message, str(e), True)
            return None
        message(self.message, f"وُلّدت الوثيقة: {p.name}")
        try:
            bureautique.ouvrir(p)
        except Exception:  # noqa: BLE001 — الفتح اختياري
            pass
        return p
