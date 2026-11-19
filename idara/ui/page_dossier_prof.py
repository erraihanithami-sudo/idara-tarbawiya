"""صفحة «ملفات الأساتذة»: طلب ملف أستاذ وإرسال ملف أستاذ (توجيه المدير 2026-11-15).

طلب المدير 2026-11-19: الطلب والإرسال في نافذة منبثقة، والصفحة الثابتة لتتبع الطلب والتوصل: «ملف الأستاذ موجود
بالمؤسسة» أمام من توصلنا بملفه (وهو ما يحيّن عدد الملفات المتوفرة في محضر تسليم المهام)، ومثلث تنبيه مع زري «طلب
الملف» و«تذكير بإرسال الملف» أمام من لم نتوصل بملفه."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QTableWidgetItem, QVBoxLayout, QWidget)

from idara.services import bureautique
from idara.services import dossier_enseignant as de
from idara.services import personnel as rh
from idara.ui.composants import bouton, carte
from idara.ui.formulaires import etiquette
from idara.ui.page_pedagogie import _page
from idara.ui import pictos
from idara.ui.saisie import ChampDate, TableauRapide, cellule, message, tableau
from idara.ui.vitrine import CarteFiltre, FenetreFiche, bouton_couleur, grille_cartes, icone_triangle, info_bulle

ETATS = {"recu": ("ملف الأستاذ موجود بالمؤسسة", "#2E7D32"), "demande": ("طُلب الملف ولم يُتوصل به", "#EF8A00"),
         "a_demander": ("لم يُطلب الملف بعد", "#EF8A00"), "envoye": ("أُرسل الملف", "#6A1B9A"),
         "a_envoyer": ("لم يُرسل الملف بعد", "#EF8A00")}


class PageDossierProf(QWidget):
    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        racine, self.message = _page("ملفات الأساتذة", "")
        self.setLayout(racine)
        self.filtre: str | None = None
        self.cartes = {
            "recu": CarteFiltre("recu", "ملفات موجودة بالمؤسسة", "#2E7D32", "valider", " "),
            "manquant": CarteFiltre("manquant", "ملفات لم يُتوصل بها", "#EF8A00", "rappel", " "),
            "demande": CarteFiltre("demande", "طلبات مرسلة", "#1565C0", "envoyer", " "),
            "partis": CarteFiltre("partis", "ملفات المغادرين", "#6A1B9A", "sortie", " "),
        }
        for c_ in self.cartes.values():
            c_.clique.connect(self.filtrer)
        racine.addLayout(grille_cartes(list(self.cartes.values()), 4))
        h = QHBoxLayout()
        h.setSpacing(12)
        self.b_nouveau = bouton_couleur("مراسلة: طلب ملف أو إرساله", "#1565C0", "envoyer",
                                        "تُرقَّم من سجل الصادر وتُسجَّل في تتبع كل أستاذ")
        self.b_nouveau.clicked.connect(lambda: self.ouvrir_correspondance())
        h.addWidget(self.b_nouveau)
        self.l_passation = QLabel()
        self.l_passation.setObjectName("etiquette")
        h.addWidget(self.l_passation, 1)
        racine.addLayout(h)
        c, v = carte()
        self.titre_suivi = QLabel()
        self.titre_suivi.setObjectName("titreCarte")
        v.addWidget(self.titre_suivi)
        self.suivi = tableau(["الأستاذ(ة)", "رقم التأجير", "الوضعية", "آخر مراسلة", "الإجراءات"], etirer=2)
        self.suivi.setMinimumHeight(320)
        self.suivi.verticalHeader().setDefaultSectionSize(46)
        v.addWidget(self.suivi)
        racine.addWidget(c)
        racine.addStretch()
        self.pids: list[int] = []

        # ---- نافذة المراسلة ----
        self.w_fiche = QWidget()
        racine_f = QVBoxLayout(self.w_fiche)
        racine_f.setSpacing(12)
        c, v = carte("المراسلة")
        self.sens = QComboBox()
        for k, lib in de.SENS.items():
            self.sens.addItem(lib, k)
        self.sens.currentIndexChanged.connect(lambda _: self._sens())
        self.rappel = QCheckBox("تذكير بطلب سابق")
        self.cible = QLineEdit()
        self.cible.setPlaceholderText("مثال: مدرسة ... بجماعة ...")
        self.couvert = QLineEdit()
        self.couvert.setPlaceholderText("فارغ إن كانت المؤسستان في المديرية نفسها، مثال: بإقليم ...")
        self.reference = QLineEdit()
        self.reference.setPlaceholderText("اختياري، مثال: مراسلتكم رقم ... بتاريخ ...")
        self.le = ChampDate()
        g = QGridLayout()
        g.setHorizontalSpacing(16)
        for k, (lib, w) in enumerate((("نوع المراسلة", self.sens), ("التاريخ", self.le),
                                      ("المؤسسة المرسل إليها", self.cible),
                                      ("تحت إشراف المدير الإقليمي", self.couvert), ("المرجع", self.reference))):
            g.addWidget(etiquette(lib, w), (k // 2) * 2, k % 2)
            g.addWidget(w, (k // 2) * 2 + 1, k % 2)
        g.addWidget(self.rappel, 5, 0)
        v.addLayout(g)
        racine_f.addWidget(c)

        c, v = carte("الأساتذة المعنيون")
        h = QHBoxLayout()
        self.choix = QComboBox()
        self.choix.setMinimumWidth(260)
        h.addWidget(self.choix, 1)
        b = QPushButton("إضافة من الأطر")
        b.clicked.connect(lambda: self.ajouter_personnel())
        h.addWidget(b)
        b = QPushButton("سطر فارغ")
        b.setToolTip("لأستاذ(ة) غير مسجل(ة) بعد في لائحة الأطر")
        b.clicked.connect(lambda: self.ajouter("", "", ""))
        h.addWidget(b)
        b = bouton("حذف السطر")
        b.clicked.connect(lambda: self.supprimer())
        h.addWidget(b)
        v.addLayout(h)
        self.table = TableauRapide(0, 3)
        self.table.setHorizontalHeaderLabels(["الاسم والنسب", "رقم التأجير", "ملاحظات"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QAbstractItemView.AllEditTriggers)
        self.table.setMinimumHeight(180)
        v.addWidget(self.table)
        h = QHBoxLayout()
        b = QPushButton("توليد المراسلة")
        b.setObjectName("principal")
        b.clicked.connect(lambda: self.generer())
        h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        racine_f.addWidget(c)
        self.message_fiche = QLabel()
        self.message_fiche.setWordWrap(True)
        self.message_fiche.hide()
        racine_f.addWidget(self.message_fiche)
        self.fiche = FenetreFiche(self, "مراسلة ملف أستاذ", "", self.w_fiche, largeur=920)
        self.rafraichir()
        self._sens()

    def rafraichir(self) -> None:
        self.choix.clear()
        for p in rh.lister(self.f.conn, actifs_seulement=False):
            if p.categorie in ("enseignant", "educatrice", "directeur"):
                self.choix.addItem(f"{p.nom_ar} {p.prenom_ar}".strip(), p.ppr or "")
        self.actualiser_suivi()

    # ---------------- التتبع ----------------

    def filtrer(self, k: str) -> None:
        self.filtre = None if k == self.filtre else k
        self.actualiser_suivi()

    def actualiser_suivi(self) -> None:
        tout = de.suivi(self.f.conn)
        actifs = [x for x in tout if x["actif"]]
        n = {"recu": sum(x["recu"] for x in actifs), "manquant": sum(not x["recu"] for x in actifs),
             "demande": sum(bool(x["demandes"]) and not x["recu"] for x in actifs),
             "partis": sum(1 for x in tout if not x["actif"])}
        for k, c_ in self.cartes.items():
            c_.definir(n[k])
            c_.definir_actif(k == self.filtre)
        manq = [x["nom"] for x in actifs if not x["recu"]]
        self.cartes["manquant"].definir_alerte("\n".join(["لم يُتوصل بملف:"] + manq) if manq else "")
        self.l_passation.setText(f"محضر تسليم المهام: {n['recu']} من {len(actifs)} ملفاً متوفراً بالمؤسسة "
                                 "(يتحين آلياً عند التوصل بملف).")
        f = self.filtre
        lignes = [x for x in tout if (f is None and x["actif"]) or (f == "recu" and x["actif"] and x["recu"])
                  or (f == "manquant" and x["actif"] and not x["recu"])
                  or (f == "demande" and x["actif"] and x["demandes"] and not x["recu"])
                  or (f == "partis" and not x["actif"])]
        titres = {None: "أساتذة المؤسسة", "recu": "ملفات موجودة بالمؤسسة", "manquant": "ملفات لم يُتوصل بها",
                  "demande": "طلبات مرسلة", "partis": "الأساتذة المغادرون"}
        self.titre_suivi.setText(f"{titres[f]} ({len(lignes)})")
        self.lignes = lignes
        self.suivi.setRowCount(len(lignes))
        for i, x in enumerate(lignes):
            it = cellule(x["nom"], x["pid"])
            lib, coul = ETATS[x["etat"]]
            if x["etat"] not in ("recu", "envoye"):
                it.setIcon(icone_triangle(18))
                it.setToolTip(info_bulle(lib))
            self.suivi.setItem(i, 0, it)
            self.suivi.setItem(i, 1, cellule(f"\u2066{x['ppr']}\u2069" if x["ppr"] else "—"))
            e = cellule(lib)
            e.setForeground(QColor(coul))
            fe = e.font()
            fe.setBold(True)
            e.setFont(fe)
            e.setIcon(pictos.icone("valider" if x["etat"] in ("recu", "envoye") else "rappel", coul, 16))
            self.suivi.setItem(i, 2, e)
            d = x["derniere"]
            from idara.services import textes as tx
            self.suivi.setItem(i, 3, cellule(
                f"{'تذكير' if d['rappel'] else de.SENS[d['sens']].split()[0]} · {tx.date_chiffres(d['date'])} · "
                f"عدد \u2066{d['numero']}\u2069" if d else "—"))
            self.suivi.setCellWidget(i, 4, self._actions(x))
        from idara.ui.vitrine import ajuster_colonne_actions
        ajuster_colonne_actions(self.suivi, 4)

    def _actions(self, x: dict) -> QWidget:
        from idara.ui.vitrine import boutons_ligne
        pid = x["pid"]
        if x["actif"] and not x["recu"]:
            specs = [("طلب الملف", "#1565C0", "envoyer", lambda: self.ouvrir_correspondance("demande", [pid]))]
            if x["demandes"]:
                specs.append(("تذكير بإرسال الملف", "#EF8A00", "rappel",
                              lambda: self.ouvrir_correspondance("demande", [pid], rappel=True)))
            specs.append(("تم التوصل بالملف", "#2E7D32", "valider", lambda: self.marquer_recu(pid)))
        elif x["actif"]:
            specs = [("إلغاء التوصل", "#78909C", "annuler", lambda: self.marquer_recu(pid, False))]
        else:
            specs = [("إرسال الملف", "#6A1B9A", "envoyer", lambda: self.ouvrir_correspondance("envoi", [pid]))]
        return boutons_ligne(specs)

    def marquer_recu(self, pid: int, recu: bool = True) -> None:
        de.marquer_recu(self.f.conn, pid, recu)
        message(self.message, "سُجل التوصل بملف الأستاذ، وتحين محضر تسليم المهام." if recu
                else "أُلغي التوصل بالملف.")
        self.actualiser_suivi()

    def ouvrir_correspondance(self, sens: str = "demande", pids: list[int] | None = None,
                              rappel: bool = False) -> FenetreFiche:
        self.sens.setCurrentIndex(self.sens.findData(sens))
        self.rappel.setChecked(rappel)
        self.table.setRowCount(0)
        self.pids = []
        if pids:
            for p in rh.lister(self.f.conn, actifs_seulement=False):
                if p.id in pids:
                    self.ajouter(f"{p.nom_ar} {p.prenom_ar}".strip(), p.ppr or "", "")
            h = de.historique(self.f.conn, pids[0])
            if h and not self.cible.text():
                self.cible.setText(h[-1].get("etab", ""))
        self.message_fiche.hide()
        titre = ("تذكير بطلب ملف" if rappel else de.SENS[sens])
        self.fiche.definir_titre(titre)
        self.fiche.ouvrir()
        return self.fiche

    def _pids_table(self) -> list[int]:
        """الأساتذة المسجلون في الجدول (برقم التأجير أو بالاسم) لتسجيل المراسلة في تتبعهم."""
        ps = rh.lister(self.f.conn, actifs_seulement=False)
        res = []
        for i in range(self.table.rowCount()):
            nom = self.table.item(i, 0).text().strip() if self.table.item(i, 0) else ""
            ppr = self.table.item(i, 1).text().strip() if self.table.item(i, 1) else ""
            p = next((p for p in ps if (ppr and p.ppr == ppr) or (nom and nom in (f"{p.nom_ar} {p.prenom_ar}",
                                                                                  f"{p.prenom_ar} {p.nom_ar}"))), None)
            if p is not None and p.id not in res:
                res.append(p.id)
        return res

    def _sens(self) -> None:
        self.rappel.setVisible(self.sens.currentData() == "demande")
        if self.sens.currentData() != "demande":
            self.rappel.setChecked(False)

    def ajouter(self, nom: str, ppr: str, obs: str) -> None:
        i = self.table.rowCount()
        self.table.insertRow(i)
        for j, x in enumerate((nom, ppr, obs)):
            self.table.setItem(i, j, QTableWidgetItem(x))

    def ajouter_personnel(self) -> None:
        if self.choix.currentIndex() >= 0:
            self.ajouter(self.choix.currentText(), self.choix.currentData() or "", "")

    def supprimer(self) -> None:
        r = self.table.currentRow()
        if r >= 0:
            self.table.removeRow(r)

    def generer(self):
        self.table.setCurrentItem(None)
        profs = [tuple((self.table.item(i, j).text() if self.table.item(i, j) else "") for j in range(3))
                 for i in range(self.table.rowCount())]
        try:
            le = self.le.iso() or None
            p, num = de.generer(self.f.conn, self.f.dossier, self.sens.currentData(), self.cible.text(), profs, le,
                                self.couvert.text(), self.reference.text(), self.rappel.isChecked(),
                                pids=self._pids_table())
        except ValueError as e:   # ErreurDossierProf أو تاريخ غير صحيح
            t = str(e) if isinstance(e, de.ErreurDossierProf) else "التاريخ غير صحيح."
            message(self.message, t, True)
            message(self.message_fiche, t, True)
            return None
        message(self.message, f"وُلّدت المراسلة وسُجلت في الصادر تحت عدد ⁦{num}⁩.")
        message(self.message_fiche, f"وُلّدت المراسلة وسُجلت في الصادر تحت عدد ⁦{num}⁩.")
        self.actualiser_suivi()
        try:
            bureautique.ouvrir(p)
        except OSError:
            pass
        return p
