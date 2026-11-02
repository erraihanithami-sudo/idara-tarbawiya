"""صفحة الصرف لجمعية دعم مدرسة النجاح: سند الطلب أو الاتفاقية، من التعبير عن الحاجة إلى الأداء،
بمراحل الدليل المسطري (يوليوز 2023) ووثائقه."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGridLayout,
                               QHBoxLayout, QHeaderView, QLabel, QPushButton, QTableWidget, QVBoxLayout, QWidget)

from idara.services import achats as ac
from idara.services import associations as asso
from idara.services import bureautique
from idara.services import textes as tx
from idara.ui.composants import carte, entete
from idara.ui.formulaires import champ, etiquette
from idara.ui.saisie import ChampDate, cellule, message, tableau

TYPE = "najah"


def _iso(w: ChampDate, lib: str) -> str:
    try:
        return w.iso()
    except ValueError:
        raise ac.ErreurAchat(f"{lib} غير صحيح.") from None


def _boutons(dlg: QDialog, ok: str) -> QDialogButtonBox:
    b = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    b.button(QDialogButtonBox.Ok).setText(ok)
    b.button(QDialogButtonBox.Cancel).setText("إلغاء")
    b.accepted.connect(dlg.accept)
    b.rejected.connect(dlg.reject)
    return b


def _combo_rubriques(conn) -> QComboBox:
    c = QComboBox()
    for r in asso.rubriques(conn, TYPE, "depense", actifs=True):
        c.addItem(f"{r['chapitre']} ← {r['ligne']}", r["id"])
    return c


def _combo_services() -> QComboBox:
    c = QComboBox()
    for s in ac.SERVICES_CONVENTION:
        c.addItem(s, s)
    return c


def _table_edit(colonnes: list[str], lignes: int, etirer: int = 0) -> QTableWidget:
    t = QTableWidget(lignes, len(colonnes))
    t.setHorizontalHeaderLabels(colonnes)
    t.verticalHeader().setVisible(False)
    t.setEditTriggers(QAbstractItemView.AllEditTriggers)
    h = t.horizontalHeader()
    h.setSectionResizeMode(QHeaderView.ResizeToContents)
    h.setSectionResizeMode(etirer, QHeaderView.Stretch)
    t.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    return t


def _grille(paires: list[tuple[str, QWidget]], etirer: int | None = None) -> QGridLayout:
    """حقول متجاورة، العنوان فوق كل حقل (لا تتجاوز الصفحة عرضها)."""
    g = QGridLayout()
    g.setHorizontalSpacing(16)
    g.setVerticalSpacing(4)
    for j, (lib, w) in enumerate(paires):
        g.addWidget(etiquette(lib, w), 0, j)
        g.addWidget(w, 1, j)
    g.setColumnStretch(len(paires) if etirer is None else etirer, 1)
    return g


def _val(t: QTableWidget, i: int, j: int) -> str:
    it = t.item(i, j)
    return it.text().strip() if it else ""


class DialogueNouveau(QDialog):
    def __init__(self, parent, conn):
        super().__init__(parent)
        self.setWindowTitle("ملف صرف جديد")
        self.setLayoutDirection(Qt.RightToLeft)
        v = QVBoxLayout(self)
        f = QFormLayout()
        self.mode = QComboBox()
        for k, lib in ac.MODES.items():
            self.mode.addItem(lib, k)
        self.objet = champ("مثلا: اقتناء معدات معلوماتية")
        self.rubrique = _combo_rubriques(conn)
        self.service = _combo_services()
        self.l_service = QLabel("نوع الخدمة (الملحق 27)")
        self.mode.currentIndexChanged.connect(self._mode)
        f.addRow("آلية الصرف", self.mode)
        f.addRow("الموضوع", self.objet)
        f.addRow("بند الميزانية", self.rubrique)
        f.addRow(self.l_service, self.service)
        v.addLayout(f)
        v.addWidget(_boutons(self, "إنشاء الملف"))
        self._mode()

    def _mode(self) -> None:
        conv = self.mode.currentData() == "convention"
        self.service.setVisible(conv)
        self.l_service.setVisible(conv)


class DialogueFournisseur(QDialog):
    CHAMPS = (("nom", "اسم الممون أو الشركة أو المقاولة"), ("represente_par", "المتصرف باسمه أو نيابة عن"),
              ("cin", "رقم البطاقة الوطنية"), ("adresse", "العنوان الاجتماعي / محل الإقامة"),
              ("telephone", "الهاتف والفاكس"), ("rc", "رقم القيد في السجل التجاري"),
              ("patente", "رقم الضريبة المهنية"), ("cnss", "رقم ص.و.ض.ج"), ("ice", "التعريف الضريبي"),
              ("compte_bancaire", "الحساب البنكي"))

    def __init__(self, parent, f: ac.Fournisseur):
        super().__init__(parent)
        self.setWindowTitle("بيانات الممون أو المكلف بالأعمال")
        self.setLayoutDirection(Qt.RightToLeft)
        self.f = f
        v = QVBoxLayout(self)
        form = QFormLayout()
        self.w = {}
        for k, lib in self.CHAMPS:
            self.w[k] = champ(ltr=k not in ("nom", "represente_par", "adresse"))
            self.w[k].setText(getattr(f, k) or "")
            form.addRow(lib, self.w[k])
        v.addLayout(form)
        v.addWidget(_boutons(self, "حفظ"))

    def fournisseur(self) -> ac.Fournisseur:
        return ac.Fournisseur(**{k: self.w[k].text() for k, _ in self.CHAMPS}, id=self.f.id)


class PageAchats(QWidget):
    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        self.eid: int | None = None
        self.aid: int | None = None
        racine = QVBoxLayout(self)
        racine.setContentsMargins(40, 32, 40, 32)
        racine.setSpacing(16)
        racine.addWidget(entete("الصرف: سند الطلب والاتفاقية",
                                "مراحل الدليل المسطري: الحاجة، طلب عروض الأثمان (3 على الأقل)، لجنة الدراسة واختيار "
                                "العرض، سند الطلب أو الاتفاقية، التسليم، الفاتورة، ثم الأداء بالشيك أو التحويل."))
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.hide()
        racine.addWidget(self.message)

        # ---- الملفات ----
        c, cv = carte()
        h = QHBoxLayout()
        h.addWidget(QLabel("السنة المالية"))
        self.exercice = QComboBox()
        self.exercice.setMinimumWidth(150)
        self.exercice.currentIndexChanged.connect(lambda _: self._changer_exercice())
        h.addWidget(self.exercice)
        self.b_nouveau = QPushButton("ملف صرف جديد")
        self.b_nouveau.setObjectName("principal")
        self.b_nouveau.clicked.connect(lambda: self.nouveau())
        h.addWidget(self.b_nouveau)
        self.b_suppr = QPushButton("حذف الملف المحدد")
        self.b_suppr.clicked.connect(lambda: self.supprimer())
        h.addWidget(self.b_suppr)
        h.addStretch()
        cv.addLayout(h)
        self.liste = tableau(["رقم", "الموضوع", "الآلية", "الممون", "المبلغ", "المرحلة"], etirer=1)
        self.liste.setMinimumHeight(200)
        self.liste.itemSelectionChanged.connect(self._selection)
        cv.addWidget(self.liste)
        racine.addWidget(c)

        self.zone = QWidget()
        z = QVBoxLayout(self.zone)
        z.setContentsMargins(0, 0, 0, 0)
        z.setSpacing(16)
        racine.addWidget(self.zone)
        racine.addStretch()

        # 1. الحاجة
        c, v = carte("1. التعبير عن الحاجة")
        self.titre = QLabel()
        self.titre.setObjectName("sousTitre")
        v.addWidget(self.titre)
        g = QGridLayout()
        self.objet = champ()
        self.rubrique = _combo_rubriques(self.f.conn)
        self.service = _combo_services()
        self.l_service = etiquette("نوع الخدمة (الملحق 27)", self.service)
        self.tva = champ("20", ltr=True)
        self.tva.setMaximumWidth(90)
        g.addWidget(etiquette("الموضوع", self.objet), 0, 0)
        g.addWidget(self.objet, 1, 0)
        g.addWidget(etiquette("نسبة الضريبة على القيمة المضافة (%)", self.tva), 0, 1)
        g.addWidget(self.tva, 1, 1)
        g.addWidget(etiquette("بند الميزانية", self.rubrique), 2, 0, 1, 2)
        g.addWidget(self.rubrique, 3, 0, 1, 2)
        g.addWidget(self.l_service, 4, 0, 1, 2)
        g.addWidget(self.service, 5, 0, 1, 2)
        g.setColumnStretch(0, 1)
        v.addLayout(g)
        self.articles = _table_edit(["التعيين", "الكمية", "الوحدة", "الثمن الفردي (دون الضريبة)"], 6)
        self.articles.setMinimumHeight(250)
        v.addWidget(self.articles)
        h = QHBoxLayout()
        b = QPushButton("سطر إضافي")
        b.clicked.connect(lambda: self.articles.setRowCount(self.articles.rowCount() + 1))
        self.b_besoin = QPushButton("حفظ الحاجة")
        self.b_besoin.clicked.connect(lambda: self.enregistrer_besoin())
        self.l_totaux = QLabel()
        h.addWidget(self.b_besoin)
        h.addWidget(b)
        h.addWidget(self.l_totaux, 1)
        v.addLayout(h)
        z.addWidget(c)

        # 2. طلب عروض الأثمان
        c, v = carte("2. طلب عروض الأثمان")
        self.date_demande = ChampDate()
        self.delai, self.nb = champ("15", ltr=True), champ("3", ltr=True)
        for w in (self.delai, self.nb):
            w.setMaximumWidth(80)
        v.addLayout(_grille([("التاريخ", self.date_demande), ("أجل الرد (15 يوماً على الأكثر)", self.delai),
                             ("عدد الطلبات (3 على الأقل)", self.nb)]))
        v.addLayout(self._ligne_boutons([("حفظ", self.enregistrer_demande)], ["demande_devis", "modele_devis"]))
        z.addWidget(c)

        # 3. اللجنة
        c, v = carte("3. لجنة دراسة عروض الأثمان")
        self.date_comm, self.heure = ChampDate(), champ("10:00", ltr=True)
        self.heure.setMaximumWidth(90)
        self.absents = champ("اختياري")
        v.addLayout(_grille([("التاريخ", self.date_comm), ("الساعة", self.heure), ("المتغيبون", self.absents)],
                            etirer=2))
        self.membres = _table_edit(["الاسم", "الصفة"], 5)
        self.membres.setMinimumHeight(210)
        v.addWidget(self.membres)
        v.addLayout(self._ligne_boutons([("حفظ", self.enregistrer_commission)], ["invitations"]))
        z.addWidget(c)

        # 4. العروض والاختيار
        c, v = carte("4. العروض المتوصل بها واختيار اللجنة")
        self.offres = tableau(["الممون", "المبلغ باحتساب الضريبة", "بالحروف"], etirer=2)
        self.offres.setMinimumHeight(170)
        v.addWidget(self.offres)
        self.nom_offre = QComboBox()
        self.nom_offre.setEditable(True)
        self.montant_offre = champ("0.00", ltr=True)
        self.montant_offre.setMaximumWidth(140)
        v.addLayout(_grille([("الممون", self.nom_offre), ("المبلغ باحتساب الضريبة", self.montant_offre)], etirer=0))
        h = QHBoxLayout()
        b = QPushButton("تسجيل العرض")
        b.clicked.connect(lambda: self.ajouter_offre())
        h.addWidget(b)
        b = QPushButton("حذف العرض المحدد")
        b.clicked.connect(lambda: self.supprimer_offre())
        h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        h = QHBoxLayout()
        self.justification = champ("تبرير اختيار العرض الأكثر نفعاً إن لم يكن الأقل ثمناً (الجودة/الثمن)")
        h.addWidget(self.justification, 1)
        v.addLayout(h)
        v.addLayout(self._ligne_boutons([("اختيار العرض المحدد", self.choisir),
                                         ("بيانات الممون المختار", self.editer_fournisseur)], ["pv_commission"]))
        z.addWidget(c)

        # 5. التنفيذ
        c, v = carte("5. سند الطلب أو الاتفاقية، ثم التسليم")
        self.date_conv, self.date_bc, self.date_liv = ChampDate(), ChampDate(), ChampDate()
        g = _grille([("تاريخ الاتفاقية", self.date_conv), ("تاريخ سند الطلب / الطلب", self.date_bc)])
        self.l_conv = g.itemAtPosition(0, 0).widget()
        v.addLayout(g)
        v.addLayout(self._ligne_boutons([("إصدار", self.engager)], ["convention", "bon_commande"]))
        v.addLayout(_grille([("تاريخ التسليم / إنجاز الخدمة", self.date_liv)]))
        self.l_reception = QLabel("لجنة التسليم الجزئي أو الكلي للخدمة (شخصان على الأقل):")
        v.addWidget(self.l_reception)
        self.reception_t = _table_edit(["الاسم الكامل", "الصفة"], 3)
        self.reception_t.setMinimumHeight(150)
        v.addWidget(self.reception_t)
        v.addLayout(self._ligne_boutons([("تسجيل التسليم", self.enregistrer_reception)],
                                        ["bon_livraison", "pv_service"]))
        z.addWidget(c)

        # 6. الفاتورة والأداء
        c, v = carte("6. الفاتورة والأداء")
        self.num_facture, self.date_facture = champ(ltr=True), ChampDate()
        self.num_facture.setMaximumWidth(160)
        v.addLayout(_grille([("رقم الفاتورة", self.num_facture), ("تاريخها", self.date_facture)]))
        v.addLayout(self._ligne_boutons([("تسجيل الفاتورة", self.enregistrer_facture)], []))
        self.date_paie, self.mode_paie, self.ref_paie = ChampDate(), QComboBox(), champ(ltr=True)
        self.mode_paie.addItem("شيك", "cheque")
        self.mode_paie.addItem("تحويل بنكي", "virement")
        self.ref_paie.setMaximumWidth(160)
        v.addLayout(_grille([("تاريخ الأداء", self.date_paie), ("الطريقة", self.mode_paie),
                             ("رقم الشيك / المرجع", self.ref_paie)]))
        v.addLayout(self._ligne_boutons([("تسجيل الأداء بسجل البنك", self.payer)], []))
        t = QLabel("ملف الأداء:")
        t.setObjectName("titreCarte")
        v.addWidget(t)
        self.etapes = QLabel()
        self.etapes.setWordWrap(True)
        v.addWidget(self.etapes)
        z.addWidget(c)

        self.rafraichir()

    def _ligne_boutons(self, actions, docs) -> QHBoxLayout:
        h = QHBoxLayout()
        for lib, f in actions:
            b = QPushButton(lib)
            b.clicked.connect(lambda _=False, f=f: f())
            h.addWidget(b)
        self.boutons_docs = getattr(self, "boutons_docs", {})
        for code in docs:
            titre, n, _ = ac.DOCUMENTS[code]
            b = QPushButton(f"{titre.split(' (')[0]} (الملحق {n})")
            b.setObjectName("principal")
            b.clicked.connect(lambda _=False, code=code: self.document(code))
            h.addWidget(b)
            self.boutons_docs[code] = b
        h.addStretch()
        return h

    # ---------- التحميل ----------

    def rafraichir(self) -> None:
        courant = self.eid
        self.exercice.blockSignals(True)
        self.exercice.clear()
        for e in asso.exercices(self.f.conn, TYPE):
            self.exercice.addItem(e["libelle"], e["id"])
        i = self.exercice.findData(courant)
        self.exercice.setCurrentIndex(i if i >= 0 else 0)
        self.exercice.blockSignals(False)
        self._changer_exercice()

    def _changer_exercice(self) -> None:
        self.eid = self.exercice.currentData()
        self.b_nouveau.setEnabled(self.eid is not None)
        if self.eid is None:
            message(self.message, "افتح السنة المالية أولاً في صفحة «جمعية دعم مدرسة النجاح».")
        else:
            self.message.hide()
        self.afficher_liste()

    def afficher_liste(self, selection: int | None = None) -> None:
        lignes = ac.dossiers(self.f.conn, self.eid) if self.eid else []
        self.liste.blockSignals(True)
        self.liste.setRowCount(len(lignes))
        cible = None
        for i, a in enumerate(lignes):
            et = ac.etapes(self.f.conn, a["id"])
            faite = [lib for lib, ok in et if ok]
            t = ac.totaux(self.f.conn, a["id"])
            for j, v in enumerate((a["id"], a["objet"], ac.MODES[a["mode"]], a["fournisseur"] or "—",
                                   f"{t['ttc']:,.2f}".replace(",", " ") if t["ttc"] else "—",
                                   faite[-1] if faite else "—")):
                self.liste.setItem(i, j, cellule(v, a["id"] if j == 0 else None))
            if a["id"] == selection:
                cible = i
        self.liste.blockSignals(False)
        if cible is not None:
            from idara.ui.saisie import selectionner
            selectionner(self.liste, cible)
            self.afficher(selection)
        else:
            self.aid = None
            self.zone.setVisible(False)
            self.b_suppr.setEnabled(False)

    def _selection(self) -> None:
        rows = {i.row() for i in self.liste.selectedIndexes()}
        if len(rows) == 1:
            self.afficher(self.liste.item(rows.pop(), 0).data(Qt.UserRole))

    def afficher(self, aid: int) -> None:
        self.aid = aid
        a = ac.achat(self.f.conn, aid)
        conv = a["mode"] == "convention"
        self.zone.setVisible(True)
        self.b_suppr.setEnabled(not a["date_bc"])
        self.titre.setText(f"الملف رقم {aid} — {ac.MODES[a['mode']]}")
        self.objet.setText(a["objet"])
        self.rubrique.setCurrentIndex(max(0, self.rubrique.findData(a["rubrique_id"])))
        for w in (self.service, self.l_service, self.l_conv, self.date_conv, self.l_reception, self.reception_t):
            w.setVisible(conv)
        if conv:
            self.service.setCurrentIndex(max(0, self.service.findData(a["service_type"])))
        self.tva.setText(f"{a['taux_tva']:g}")
        arts = ac.articles(self.f.conn, aid)
        self.articles.setRowCount(max(6, len(arts) + 1))
        self.articles.clearContents()
        for i, r in enumerate(arts):
            for j, v in enumerate((r["designation"], f"{r['quantite']:g}", r["unite"] or "",
                                   "" if r["prix_unitaire"] is None else f"{r['prix_unitaire']:.2f}")):
                self.articles.setItem(i, j, cellule(v))
        t = ac.totaux(self.f.conn, aid)
        self.l_totaux.setText(f"دون الضريبة: {t['ht']:,.2f} — الضريبة: {t['tva']:,.2f} — المجموع: {t['ttc']:,.2f} درهم"
                              .replace(",", " ") if t["ht"] else "")
        self.date_demande.definir(a["date_demande"] or date.today().isoformat())
        self.delai.setText(str(a["delai_jours"] or 15))
        self.nb.setText(str(a["nb_demandes"] or 3))
        self.date_comm.definir(a["date_commission"] or "")
        self.heure.setText(a["heure_commission"] or "10:00")
        self.absents.setText(a["absents"] or "")
        m = ac.membres(a)
        if not m:
            asso_r = asso.association(self.f.conn, TYPE)
            m = [(asso_r["president"] or "", "رئيسا"), (asso_r["tresorier"] or "", "أمين المال"),
                 ("", "عضو بمكتب الجمعية")]
        self.membres.clearContents()
        for i, (nom, q) in enumerate(m[:self.membres.rowCount()]):
            self.membres.setItem(i, 0, cellule(nom))
            self.membres.setItem(i, 1, cellule(q))
        self.offres.setRowCount(0)
        os_ = ac.offres(self.f.conn, aid)
        self.offres.setRowCount(len(os_))
        for i, o in enumerate(os_):
            nom = o["nom"] + (" ✓" if o["fournisseur_id"] == a["fournisseur_id"] else "")
            self.offres.setItem(i, 0, cellule(nom, o["fournisseur_id"]))
            self.offres.setItem(i, 1, cellule(f"{o['montant']:,.2f}".replace(",", " ")))
            self.offres.setItem(i, 2, cellule(tx.montant_lettres_ar(o["montant"])))
        self.nom_offre.clear()
        self.nom_offre.addItems([r["nom"] for r in ac.fournisseurs(self.f.conn)])
        self.nom_offre.setEditText("")
        self.justification.setText(a["justification"] or "")
        self.date_conv.definir(a["date_convention"] or "")
        self.date_bc.definir(a["date_bc"] or "")
        self.date_liv.definir(a["date_livraison"] or "")
        self.reception_t.clearContents()
        import json
        for i, (nom, q) in enumerate(json.loads(a["commission_reception"] or "[]")[:3]):
            self.reception_t.setItem(i, 0, cellule(nom))
            self.reception_t.setItem(i, 1, cellule(q))
        self.num_facture.setText(a["facture_numero"] or "")
        self.date_facture.definir(a["facture_date"] or "")
        self.date_paie.definir(date.today().isoformat())
        self.etapes.setText("\n".join(("✓ " if ok else "○ ") + lib for lib, ok in ac.etapes(self.f.conn, aid)))
        for code, b in self.boutons_docs.items():
            b.setVisible(a["mode"] in ac.DOCUMENTS[code][2])

    # ---------- الأفعال ----------

    def _faire(self, f, succes: str, recharger=True):
        try:
            r = f()
        except (ac.ErreurAchat, asso.ErreurAssociation) as e:
            message(self.message, str(e), True)
            return None
        if recharger:
            self.afficher_liste(self.aid)
        if succes:
            message(self.message, succes if not isinstance(r, list) or not r else succes + "\n" + "\n".join(r),
                    bool(isinstance(r, list) and r))
        return True if r is None or r == [] else r

    def nouveau(self, valeurs: dict | None = None) -> int | None:
        if valeurs is None:
            d = DialogueNouveau(self, self.f.conn)
            if d.exec() != QDialog.Accepted:
                return None
            valeurs = dict(mode=d.mode.currentData(), objet=d.objet.text(), rubrique_id=d.rubrique.currentData(),
                           service_type=d.service.currentData() if d.mode.currentData() == "convention" else "")
        try:
            aid = ac.creer(self.f.conn, self.eid, **valeurs)
        except ac.ErreurAchat as e:
            message(self.message, str(e), True)
            return None
        self.aid = aid
        self.afficher_liste(aid)
        message(self.message, "أُنشئ الملف. حدد الحاجة (التعيين والكمية) ثم احفظها.")
        return aid

    def supprimer(self):
        return self._faire(lambda: ac.supprimer(self.f.conn, self.aid), "حُذف الملف.")

    def _articles(self) -> list[tuple]:
        return [tuple(_val(self.articles, i, j) for j in range(4)) for i in range(self.articles.rowCount())]

    def enregistrer_besoin(self):
        a = ac.achat(self.f.conn, self.aid)
        return self._faire(lambda: ac.definir_besoin(
            self.f.conn, self.aid, self.objet.text(), self.rubrique.currentData(), self._articles(), self.tva.text(),
            self.service.currentData() if a["mode"] == "convention" else ""), "حُفظت الحاجة.")

    def enregistrer_demande(self):
        return self._faire(lambda: ac.definir_demande(self.f.conn, self.aid, _iso(self.date_demande, "التاريخ"),
                                                      self.delai.text(), self.nb.text()), "سُجل طلب عروض الأثمان.")

    def enregistrer_commission(self):
        m = [(_val(self.membres, i, 0), _val(self.membres, i, 1)) for i in range(self.membres.rowCount())]
        return self._faire(lambda: ac.definir_commission(self.f.conn, self.aid, _iso(self.date_comm, "تاريخ الاجتماع"),
                                                         self.heure.text(), m, self.absents.text()), "سُجلت اللجنة.")

    def ajouter_offre(self):
        r = self._faire(lambda: ac.ajouter_offre(self.f.conn, self.aid, self.nom_offre.currentText(),
                                                 self.montant_offre.text()), "سُجل العرض.")
        if r:
            self.montant_offre.clear()
        return r

    def _offre_selectionnee(self) -> int:
        rows = {i.row() for i in self.offres.selectedIndexes()}
        if len(rows) != 1:
            raise ac.ErreurAchat("حدد عرضاً في الجدول.")
        return self.offres.item(rows.pop(), 0).data(Qt.UserRole)

    def supprimer_offre(self):
        return self._faire(lambda: ac.supprimer_offre(self.f.conn, self.aid, self._offre_selectionnee()), "حُذف العرض.")

    def choisir(self):
        return self._faire(lambda: ac.choisir(self.f.conn, self.aid, self._offre_selectionnee(),
                                              self.justification.text()), "سُجل اختيار اللجنة.")

    def editer_fournisseur(self, valeurs: ac.Fournisseur | None = None):
        a = ac.achat(self.f.conn, self.aid)
        if not a["fournisseur_id"]:
            message(self.message, "لم يقع الاختيار على عرض بعد.", True)
            return None
        if valeurs is None:
            d = DialogueFournisseur(self, ac.fournisseur(self.f.conn, a["fournisseur_id"]))
            if d.exec() != QDialog.Accepted:
                return None
            valeurs = d.fournisseur()
        return self._faire(lambda: ac.enregistrer_fournisseur(self.f.conn, valeurs), "حُفظت بيانات الممون.")

    def engager(self):
        a = ac.achat(self.f.conn, self.aid)
        conv = a["mode"] == "convention"
        return self._faire(lambda: ac.engager(self.f.conn, self.aid, _iso(self.date_bc, "تاريخ سند الطلب"),
                                              _iso(self.date_conv, "تاريخ الاتفاقية") if conv else None),
                           "سُجل سند الطلب.")

    def enregistrer_reception(self):
        c = [(_val(self.reception_t, i, 0), _val(self.reception_t, i, 1)) for i in range(self.reception_t.rowCount())]
        return self._faire(lambda: ac.reception(self.f.conn, self.aid, _iso(self.date_liv, "تاريخ التسليم"), c),
                           "سُجل التسليم.")

    def enregistrer_facture(self):
        return self._faire(lambda: ac.facture(self.f.conn, self.aid, self.num_facture.text(),
                                              _iso(self.date_facture, "تاريخ الفاتورة")), "سُجلت الفاتورة.")

    def payer(self):
        return self._faire(lambda: ac.payer(self.f.conn, self.aid, _iso(self.date_paie, "تاريخ الأداء"),
                                            self.mode_paie.currentData(), self.ref_paie.text()),
                           "سُجل الأداء مصروفاً بسجل البنك والسجل اليومي.")

    def document(self, code: str) -> Path | None:
        p = self._faire(lambda: ac.generer(self.f.conn, self.f.dossier, self.aid, code), "", recharger=False)
        if not p:
            return None
        message(self.message, f"وُلّدت الوثيقة: {p.name}")
        try:
            bureautique.ouvrir(p)
        except Exception:  # noqa: BLE001 — الفتح اختياري
            pass
        return p
