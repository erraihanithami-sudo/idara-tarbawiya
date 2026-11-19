"""تدبير السكنيات (طلب المدير 2026-11-19) حسب المذكرة 40 بتاريخ 10 ماي 2004.

الصفحة الثابتة: بطاقات الإحصاء، السكنيات وشاغلوها، إجراءات التباري، و«الوثائق المطلوبة لتدبير السكنيات» وأمام كل
مطبوع: معاينة، تعديل، طبع. النوافذ المنبثقة: إضافة سكن، إضافة إجراء تباري على السكن، وحساب نقط المترشح حسب جدول
المذكرة مع الترتيب والإسناد.
"""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QHBoxLayout, QLabel, QPushButton, QSpinBox,
                               QVBoxLayout, QWidget)

from idara.services import logements as lg
from idara.services import personnel as rh
from idara.services import textes as tx
from idara.ui import pictos
from idara.ui.composants import carte
from idara.ui.formulaires import champ
from idara.ui.page_pedagogie import _page
from idara.ui.saisie import ChampDate, cellule, message, tableau
from idara.ui.vitrine import (CarteFiltre, FenetreFiche, ajuster_colonne_actions, bouton_couleur, boutons_ligne,
                              grille_cartes, vider_colonne_widgets)

OR = "#B8860B"
STATUTS = {"ouvert": ("مفتوح", "#1565C0"), "attribue": ("أُسند", "#2E7D32"), "annule": ("ملغى", "#78909C")}


def _ligne_titre(texte: str) -> QLabel:
    l = QLabel(texte)
    l.setObjectName("titreCarte")
    return l


class PageLogements(QWidget):
    def __init__(self, fenetre):
        super().__init__()
        self.f = fenetre
        racine, self.message = _page("تدبير السكنيات", "")
        self.setLayout(racine)
        self.cartes = {
            "logements": CarteFiltre("logements", "السكنيات", "#6D4C41", "maison", " "),
            "occupes": CarteFiltre("occupes", "مشغولة", "#2E7D32", "personnes", " "),
            "vacants": CarteFiltre("vacants", "شاغرة", "#EF8A00", "maison", " "),
            "ouverts": CarteFiltre("ouverts", "إجراءات تباري مفتوحة", "#1565C0", "calendrier", " "),
            "candidats": CarteFiltre("candidats", "المترشحون", "#6A1B9A", "statistiques", " "),
        }
        racine.addLayout(grille_cartes(list(self.cartes.values()), 5))
        h = QHBoxLayout()
        h.setSpacing(12)
        for t, coul, pic, fn, aide in (
                ("إضافة سكن", "#6D4C41", "maison", lambda: self.ouvrir_logement(), "سكن إداري أو وظيفي بالمؤسسة"),
                ("إضافة إجراء تباري على السكن", "#1565C0", "ajouter", lambda: self.ouvrir_concours(),
                 "الإعلان عن سكن شاغر قابل للتباري (شهر على الأقل قبل انعقاد لجنة الإسناد)"),
                ("حساب نقط مترشح", OR, "statistiques", lambda: self.ouvrir_points(),
                 "حسب معايير المذكرة 40: الإطار، الأقدمية، التحملات العائلية، المسؤولية، المردودية، الوسط القروي")):
            b = bouton_couleur(t, coul, pic, aide)
            b.clicked.connect(fn)
            h.addWidget(b)
        h.addStretch()
        racine.addLayout(h)

        # ---- الوثائق المطلوبة ----
        c, v = carte()
        v.addWidget(_ligne_titre("الوثائق المطلوبة لتدبير السكنيات (مطبوعات المذكرة 40)"))
        hc = QHBoxLayout()
        hc.addWidget(QLabel("تُملأ من:"))
        self.ctx_concours = QComboBox()
        self.ctx_concours.setMinimumWidth(300)
        self.ctx_concours.currentIndexChanged.connect(lambda _: self._ctx_personnes())
        hc.addWidget(self.ctx_concours)
        hc.addWidget(QLabel("الموظف(ة):"))
        self.ctx_personne = QComboBox()
        self.ctx_personne.setMinimumWidth(220)
        hc.addWidget(self.ctx_personne)
        hc.addStretch()
        v.addLayout(hc)
        aide = QLabel("كل مطبوع وثيقة مستقلة في صفحة خاصة به. دون إجراء تباري يُولَّد المطبوع فارغاً للملء باليد.")
        aide.setObjectName("etiquette")
        aide.setWordWrap(True)
        v.addWidget(aide)
        self.t_docs = tableau(["ر.ت", "المطبوع", "الوصف", "الإجراءات"], etirer=2)
        self.t_docs.setMinimumHeight(420)
        v.addWidget(self.t_docs)
        racine.addWidget(c)

        # ---- إجراءات التباري ----
        c, v = carte()
        v.addWidget(_ligne_titre("إجراءات التباري على السكن"))
        self.t_concours = tableau(["السكن", "الإعلان", "آخر أجل", "لجنة الإسناد", "الوسط", "المترشحون", "الحالة",
                                   "الإجراءات"], etirer=0)
        self.t_concours.setMinimumHeight(180)
        v.addWidget(self.t_concours)
        self.vide_concours = QLabel("لا إجراء تباري بعد. «إضافة إجراء تباري على السكن» يعلن عن سكن شاغر.")
        self.vide_concours.setObjectName("etiquette")
        self.vide_concours.setAlignment(Qt.AlignCenter)
        v.addWidget(self.vide_concours)
        racine.addWidget(c)

        # ---- السكنيات ----
        c, v = carte()
        v.addWidget(_ligne_titre("السكنيات وشاغلوها"))
        self.t_logements = tableau(["العنوان", "الرقم المخزني", "الوحدة", "الصنف", "الشاغل الحالي", "الإجراءات"],
                                   etirer=0)
        self.t_logements.setMinimumHeight(160)
        v.addWidget(self.t_logements)
        self.vide_logements = QLabel("لا سكن مسجلاً. «إضافة سكن» يسجل سكناً إدارياً أو وظيفياً.")
        self.vide_logements.setObjectName("etiquette")
        self.vide_logements.setAlignment(Qt.AlignCenter)
        v.addWidget(self.vide_logements)
        racine.addWidget(c)
        racine.addStretch()
        self._construire_logement()
        self._construire_concours()
        self._construire_points()

    # ================= النوافذ =================

    def _msg_fiche(self, label: QLabel, texte: str, erreur: bool = False) -> None:
        message(label, texte, erreur)
        message(self.message, texte, erreur)

    def _construire_logement(self) -> None:
        w = QWidget()
        fl = QFormLayout(w)
        self.l_adresse = champ("رقم السكن والشارع أو الزنقة والحي والبلدة")
        self.l_numero = champ("الرقم المخزني", ltr=True)
        self.l_unite = QComboBox()
        self.l_unite.setEditable(True)
        self.l_nature = champ("صلب، مفكك…")
        self.l_categorie = QComboBox()
        self.l_categorie.addItem("سكن إداري", "administratif")
        self.l_categorie.addItem("سكن وظيفي", "fonction")
        self.l_occupant = QComboBox()
        self.l_occupant.setEditable(True)
        self.l_remarques = champ()
        for lib, x in (("العنوان *", self.l_adresse), ("الرقم المخزني", self.l_numero), ("الوحدة المدرسية", self.l_unite),
                       ("النوع", self.l_nature), ("الصنف", self.l_categorie),
                       ("الشاغل الحالي (اختياري)", self.l_occupant), ("ملاحظات", self.l_remarques)):
            fl.addRow(lib, x)
        b = bouton_couleur("حفظ السكن", "#6D4C41", "enregistrer")
        b.clicked.connect(lambda: self.enregistrer_logement())
        fl.addRow(b)
        self.m_logement = QLabel()
        self.m_logement.setWordWrap(True)
        self.m_logement.hide()
        fl.addRow(self.m_logement)
        self.fiche_logement = FenetreFiche(self, "سكن", "", w, largeur=700)
        self.lid = None

    def _construire_concours(self) -> None:
        w = QWidget()
        v = QVBoxLayout(w)
        aide = QLabel("حسب المذكرة: يُعلن عن السكن الشاغر شهراً على الأقل قبل انعقاد لجنة الإسناد. يُشترط في المترشح "
                      "مزاولة العمل بالبلدة التي يوجد بها السكن، وعدم ملكيته سكناً شخصياً بها (شهادة من مصلحة "
                      "الضرائب لا يفوق أجل تسليمها شهرين)، وعدم تعرضه لعقوبة تأديبية لم يتم سحبها.")
        aide.setObjectName("etiquette")
        aide.setWordWrap(True)
        v.addWidget(aide)
        fl = QFormLayout()
        self.c_logement = QComboBox()
        self.c_annonce, self.c_limite, self.c_commission = ChampDate(), ChampDate(), ChampDate()
        self.c_rural = QCheckBox("السكن بالوسط القروي (معايير إضافية، ومصادقة المدير الإقليمي على المحضر)")
        self.c_remarques = champ()
        for lib, x in (("السكن *", self.c_logement), ("تاريخ الإعلان *", self.c_annonce),
                       ("آخر أجل لتقديم الطلبات", self.c_limite), ("تاريخ انعقاد لجنة الإسناد", self.c_commission),
                       ("", self.c_rural), ("ملاحظات", self.c_remarques)):
            fl.addRow(lib, x)
        v.addLayout(fl)
        b = bouton_couleur("حفظ إجراء التباري", "#1565C0", "enregistrer")
        b.clicked.connect(lambda: self.enregistrer_concours())
        v.addWidget(b, 0, Qt.AlignLeft)
        self.m_concours = QLabel()
        self.m_concours.setWordWrap(True)
        self.m_concours.hide()
        v.addWidget(self.m_concours)
        self.fiche_concours = FenetreFiche(self, "إجراء تباري على السكن", "", w, largeur=760)
        self.cid = None

    def _construire_points(self) -> None:
        w = QWidget()
        v = QVBoxLayout(w)
        fl = QFormLayout()
        self.p_concours = QComboBox()
        self.p_concours.currentIndexChanged.connect(lambda _: self._maj_rural())
        self.p_personne = QComboBox()
        self.p_personne.currentIndexChanged.connect(lambda _: self.proposer())
        fl.addRow("إجراء التباري", self.p_concours)
        fl.addRow("الموظف(ة) المترشح(ة)", self.p_personne)
        self.p_echelle = QComboBox()
        self.p_echelle.addItem("—", "")
        for n in range(1, 12):
            self.p_echelle.addItem(f"السلم {n}", str(n))
        self.p_echelle.addItem("خارج السلم", "hors")
        self.p_ag, self.p_al, self.p_enfants = QSpinBox(), QSpinBox(), QSpinBox()
        for s, m, suf in ((self.p_ag, 45, " سنة"), (self.p_al, 45, " سنة"), (self.p_enfants, 15, "")):
            s.setRange(0, m)
            s.setSuffix(suf)
            s.setMaximumWidth(120)
        self.p_situation = QComboBox()
        for k, lib in lg.SITUATIONS.items():
            self.p_situation.addItem(lib, k)
        self.p_conjoint = QCheckBox("الزوج(ة) بدون عمل (الراتب الوحيد)")
        self.p_resp = QComboBox()
        for k, lib in lg.RESPONSABILITES.items():
            self.p_resp.addItem(lib, k)
        self.p_rend = QComboBox()
        for k, lib in lg.RENDEMENTS.items():
            self.p_rend.addItem(lib, k)
        self.p_femme = QCheckBox("معلمة أو أستاذة غير متزوجة")
        self.p_satellite = QCheckBox("يعمل(تعمل) بالفرعية")
        for lib, x in (("الإطار (السلم)", self.p_echelle), ("الأقدمية العامة (منذ التوظيف)", self.p_ag),
                       ("الأقدمية بنفس المدينة أو البلدة", self.p_al), ("الحالة العائلية", self.p_situation),
                       ("عدد الأطفال", self.p_enfants), ("", self.p_conjoint), ("المسؤولية", self.p_resp),
                       ("المردودية (يقدرها الرئيس المباشر)", self.p_rend)):
            fl.addRow(lib, x)
        self.l_rural = QLabel("معايير إضافية للعاملين بالوسط القروي")
        self.l_rural.setObjectName("titreCarte")
        fl.addRow(self.l_rural)
        fl.addRow("", self.p_femme)
        fl.addRow("", self.p_satellite)
        v.addLayout(fl)
        for x in (self.p_ag, self.p_al, self.p_enfants):
            x.valueChanged.connect(lambda _: self.calculer())
        for x in (self.p_echelle, self.p_situation, self.p_resp, self.p_rend):
            x.currentIndexChanged.connect(lambda _: self.calculer())
        for x in (self.p_conjoint, self.p_femme, self.p_satellite):
            x.toggled.connect(lambda _: self.calculer())
        self.t_points = tableau(["العنصر", "القيمة", "النقط"], etirer=0)
        self.t_points.setMinimumHeight(260)
        v.addWidget(self.t_points)
        self.l_total = QLabel()
        self.l_total.setAlignment(Qt.AlignCenter)
        self.l_total.setStyleSheet(f"font-size: 18pt; font-weight: 800; color: white; background: qlineargradient("
                                   f"x1:1, y1:0, x2:0, y2:1, stop:0 {OR}, stop:1 #7A5A0B); border-radius: 14px; "
                                   f"padding: 10px;")
        v.addWidget(self.l_total)
        h = QHBoxLayout()
        b = bouton_couleur("حفظ ترشيحه بهذه النقط", OR, "enregistrer")
        b.clicked.connect(lambda: self.enregistrer_candidat())
        h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        v.addWidget(_ligne_titre("ترتيب المترشحين"))
        aide = QLabel("عند تساوي مرشحين أو أكثر في مجموع النقط يُفصل بينهم بالأقدمية في العمل ثم بالقرعة.")
        aide.setObjectName("etiquette")
        aide.setWordWrap(True)
        v.addWidget(aide)
        self.t_classement = tableau(["الرتبة", "المترشح(ة)", "الأقدمية العامة", "النقط", "الإجراءات"], etirer=1)
        self.t_classement.setMinimumHeight(180)
        v.addWidget(self.t_classement)
        self.m_points = QLabel()
        self.m_points.setWordWrap(True)
        self.m_points.hide()
        v.addWidget(self.m_points)
        self.fiche_points = FenetreFiche(self, "حساب نقط المترشح للسكن", "", w, largeur=820)

    # ================= العرض =================

    def _libelle_concours(self, c: lg.Concours) -> str:
        l = lg.logement(self.f.conn, c.logement_id)
        return f"{l.adresse} · إعلان {tx.date_chiffres(c.date_annonce)}"

    def _enseignants(self):
        return [p for p in rh.lister(self.f.conn) if p.categorie != "directeur"]

    def rafraichir(self) -> None:
        conn = self.f.conn
        s = lg.synthese(conn)
        for k, c in self.cartes.items():
            c.definir(s[k])
        self.cartes["vacants"].definir_alerte("سكن شاغر دون إجراء تباري مفتوح." if s["vacants"] and not s["ouverts"]
                                              else "")
        self.logements = lg.logements(conn)
        self.concours = lg.concours_liste(conn)
        # السكنيات
        vider_colonne_widgets(self.t_logements, 5)
        self.t_logements.setRowCount(len(self.logements))
        for i, l in enumerate(self.logements):
            o = lg.occupant_actuel(conn, l.id)
            it = cellule(l.adresse, l.id)
            it.setIcon(pictos.icone("maison", "#6D4C41", 16))
            self.t_logements.setItem(i, 0, it)
            for j, x in enumerate((f"⁦{l.numero}⁩" if l.numero else "—", l.unite or "—",
                                   "إداري" if l.categorie == "administratif" else "وظيفي",
                                   o["occupant"] if o else "شاغر"), start=1):
                c_ = cellule(x)
                if j == 4 and not o:
                    c_.setForeground(QColor("#EF8A00"))
                self.t_logements.setItem(i, j, c_)
            self.t_logements.setCellWidget(i, 5, boutons_ligne([
                ("تعديل", "#6D4C41", "modifier", lambda x=l.id: self.ouvrir_logement(x)),
                ("بطاقة المراقبة", "#3949AB", "apercu", lambda x=l.id: self.document("controle", "apercu", logement_id=x)),
                ("تباري", "#1565C0", "ajouter", lambda x=l.id: self.ouvrir_concours(logement_id=x))]))
        ajuster_colonne_actions(self.t_logements, 5)
        self.t_logements.setVisible(bool(self.logements))
        self.vide_logements.setVisible(not self.logements)
        # إجراءات التباري
        vider_colonne_widgets(self.t_concours, 7)
        self.t_concours.setRowCount(len(self.concours))
        for i, c in enumerate(self.concours):
            l = lg.logement(conn, c.logement_id)
            n = len(lg.candidats(conn, c.id))
            lib, coul = STATUTS[c.statut]
            vals = (l.adresse, tx.date_chiffres(c.date_annonce),
                    tx.date_chiffres(c.date_limite) if c.date_limite else "—",
                    tx.date_chiffres(c.date_commission) if c.date_commission else "—",
                    "قروي" if c.rural else "حضري", str(n), lib)
            for j, x in enumerate(vals):
                it = cellule(x, c.id if j == 0 else None)
                if j == 6:
                    it.setForeground(QColor(coul))
                self.t_concours.setItem(i, j, it)
            self.t_concours.setCellWidget(i, 7, boutons_ligne([
                ("المترشحون والنقط", OR, "statistiques", lambda x=c.id: self.ouvrir_points(x)),
                ("محضر اللجنة", "#2E7D32", "document", lambda x=c.id: self.document("pv", "apercu", concours_id=x)),
                ("تعديل", "#1565C0", "modifier", lambda x=c.id: self.ouvrir_concours(x))]))
        ajuster_colonne_actions(self.t_concours, 7)
        self.t_concours.setVisible(bool(self.concours))
        self.vide_concours.setVisible(not self.concours)
        # سياق المطبوعات
        actuel = self.ctx_concours.currentData()
        self.ctx_concours.blockSignals(True)
        self.ctx_concours.clear()
        self.ctx_concours.addItem("مطبوع فارغ (للملء باليد)", None)
        for c in self.concours:
            self.ctx_concours.addItem(self._libelle_concours(c), c.id)
        self.ctx_concours.setCurrentIndex(max(0, self.ctx_concours.findData(actuel)))
        self.ctx_concours.blockSignals(False)
        self._ctx_personnes()
        self._docs()

    def _ctx_personnes(self) -> None:
        cid = self.ctx_concours.currentData()
        actuel = self.ctx_personne.currentData()
        self.ctx_personne.clear()
        self.ctx_personne.addItem("—", None)
        if cid:
            c = lg.concours(self.f.conn, cid)
            for x in lg.candidats(self.f.conn, cid):
                p = rh.lire(self.f.conn, x.personnel_id)
                marque = " (المستفيد)" if c.beneficiaire_id == p.id else ""
                self.ctx_personne.addItem(f"{p.prenom_ar} {p.nom_ar}{marque}", p.id)
            if c.beneficiaire_id and actuel is None:
                actuel = c.beneficiaire_id
        else:
            for p in self._enseignants():
                self.ctx_personne.addItem(f"{p.prenom_ar} {p.nom_ar}", p.id)
        self.ctx_personne.setCurrentIndex(max(0, self.ctx_personne.findData(actuel)))

    def _docs(self) -> None:
        vider_colonne_widgets(self.t_docs, 3)
        self.t_docs.setRowCount(len(lg.MODELES))
        for i, (code, (num, titre, desc, dispo)) in enumerate(lg.MODELES.items()):
            self.t_docs.setItem(i, 0, cellule(str(num), code))
            it = cellule(titre)
            it.setIcon(pictos.icone("document" if dispo else "interdit", "#6D4C41" if dispo else "#90A4AE", 16))
            if not dispo:
                it.setForeground(QColor("#90A4AE"))
            self.t_docs.setItem(i, 1, it)
            self.t_docs.setItem(i, 2, cellule(desc))
            w = boutons_ligne([("معاينة", "#3949AB", "apercu", lambda c=code: self.document(c, "apercu")),
                               ("تعديل", "#00897B", "modifier", lambda c=code: self.document(c, "modifier")),
                               ("طبع", "#6D4C41", "imprimer", lambda c=code: self.document(c, "imprimer"))])
            for b in w.findChildren(QPushButton):
                b.setEnabled(dispo)
                if not dispo:
                    b.setToolTip("نموذج هذا المطبوع غير مرفق بالمذكرة: أرسله لبرمجته")
            self.t_docs.setCellWidget(i, 3, w)
        ajuster_colonne_actions(self.t_docs, 3)

    # ================= الأفعال =================

    def document(self, code: str, mode: str = "apercu", concours_id: int | None = None,
                 personnel_id: int | None = None, logement_id: int | None = None):
        """معاينة المطبوع أو تعديله أو طبعه. السياق: المعطى، وإلا ما اختير فوق جدول المطبوعات."""
        if concours_id is None and logement_id is None:
            concours_id = self.ctx_concours.currentData()
            personnel_id = personnel_id or self.ctx_personne.currentData()
        try:
            p = lg.generer(self.f.conn, self.f.dossier, code, concours_id, personnel_id, logement_id)
        except (lg.ErreurLogement, OSError) as e:
            message(self.message, str(e), True)
            return None
        message(self.message, f"وُلّد المطبوع: ⁦{p.name}⁩")
        e = self.f.ouvrir_document(p)
        if e is not None and mode == "modifier" and hasattr(e, "basculer_edition"):
            e.basculer_edition(True)
        elif e is not None and mode == "imprimer" and hasattr(e, "imprimer"):
            e.imprimer()
        return p

    def ouvrir_logement(self, lid: int | None = None):
        self.lid = lid
        self.l_unite.clear()
        from idara.services import etablissement as et
        self.l_unite.addItems([""] + et.unites(self.f.conn))
        self.l_occupant.clear()
        self.l_occupant.addItem("", None)
        for p in self._enseignants():
            self.l_occupant.addItem(f"{p.prenom_ar} {p.nom_ar}", p.id)
        if lid:
            l = lg.logement(self.f.conn, lid)
            self.l_adresse.setText(l.adresse)
            self.l_numero.setText(l.numero)
            self.l_unite.setCurrentText(l.unite)
            self.l_nature.setText(l.nature)
            self.l_categorie.setCurrentIndex(max(0, self.l_categorie.findData(l.categorie)))
            self.l_remarques.setText(l.remarques)
            o = lg.occupant_actuel(self.f.conn, lid)
            self.l_occupant.setEditText(o["occupant"] if o else "")
        else:
            for x in (self.l_adresse, self.l_numero, self.l_nature, self.l_remarques):
                x.clear()
        self.m_logement.hide()
        self.fiche_logement.definir_titre("تعديل السكن" if lid else "إضافة سكن")
        self.fiche_logement.ouvrir()
        return self.fiche_logement

    def enregistrer_logement(self) -> int | None:
        try:
            lid = lg.enregistrer_logement(self.f.conn, lg.Logement(
                self.l_adresse.text(), self.l_numero.text(), self.l_unite.currentText(), self.l_nature.text(),
                self.l_categorie.currentData(), self.l_remarques.text(), self.lid))
            occ = self.l_occupant.currentText().strip()
            o = lg.occupant_actuel(self.f.conn, lid)
            if occ and (o is None or o["occupant"] != occ):
                pid = self.l_occupant.currentData() if self.l_occupant.currentText() == occ else None
                lg.ajouter_occupation(self.f.conn, lid, occ, pid)
        except lg.ErreurLogement as e:
            self._msg_fiche(self.m_logement, str(e), True)
            return None
        self.lid = lid
        self.fiche_logement.hide()
        message(self.message, "حُفظ السكن.")
        self.rafraichir()
        return lid

    def ouvrir_concours(self, cid: int | None = None, logement_id: int | None = None):
        self.cid = cid
        self.c_logement.clear()
        for l in lg.logements(self.f.conn):
            self.c_logement.addItem(l.adresse + (f" ({l.numero})" if l.numero else ""), l.id)
        if cid:
            c = lg.concours(self.f.conn, cid)
            self.c_logement.setCurrentIndex(max(0, self.c_logement.findData(c.logement_id)))
            self.c_annonce.definir(c.date_annonce)
            self.c_limite.definir(c.date_limite or None)
            self.c_commission.definir(c.date_commission or None)
            self.c_rural.setChecked(c.rural)
            self.c_remarques.setText(c.remarques)
        else:
            self.c_logement.setCurrentIndex(max(0, self.c_logement.findData(logement_id)))
            self.c_annonce.definir(date.today().isoformat())
            self.c_limite.definir(None)
            self.c_commission.definir(None)
            from idara.services import etablissement as et
            e = et.lire_etablissement(self.f.conn)
            self.c_rural.setChecked(bool(e and e.milieu == "rural"))
            self.c_remarques.clear()
        self.m_concours.hide()
        if not self.c_logement.count():
            self._msg_fiche(self.m_concours, "سجّل السكن أولاً: «إضافة سكن».", True)
        self.fiche_concours.definir_titre("تعديل إجراء التباري" if cid else "إضافة إجراء تباري على السكن")
        self.fiche_concours.ouvrir()
        return self.fiche_concours

    def enregistrer_concours(self) -> int | None:
        try:
            if self.c_logement.currentData() is None:
                raise lg.ErreurLogement("سجّل السكن أولاً: «إضافة سكن».")
            ancien = lg.concours(self.f.conn, self.cid) if self.cid else None
            cid = lg.enregistrer_concours(self.f.conn, lg.Concours(
                self.c_logement.currentData(), self.c_annonce.iso(), self.c_limite.iso(), self.c_commission.iso(),
                self.c_rural.isChecked(), ancien.statut if ancien else "ouvert",
                ancien.beneficiaire_id if ancien else None, self.c_remarques.text(), self.cid))
        except (lg.ErreurLogement, ValueError) as e:
            self._msg_fiche(self.m_concours, str(e) or "تاريخ غير صحيح.", True)
            return None
        self.cid = cid
        self.fiche_concours.hide()
        message(self.message, "حُفظ إجراء التباري.")
        self.rafraichir()
        return cid

    # ---- نافذة حساب النقط ----

    def ouvrir_points(self, cid: int | None = None):
        self.p_concours.blockSignals(True)
        self.p_concours.clear()
        for c in lg.concours_liste(self.f.conn):
            self.p_concours.addItem(self._libelle_concours(c), c.id)
        self.p_concours.setCurrentIndex(max(0, self.p_concours.findData(cid)))
        self.p_concours.blockSignals(False)
        self.p_personne.blockSignals(True)
        self.p_personne.clear()
        for p in self._enseignants():
            self.p_personne.addItem(f"{p.prenom_ar} {p.nom_ar}", p.id)
        self.p_personne.blockSignals(False)
        self.m_points.hide()
        if not self.p_concours.count():
            self._msg_fiche(self.m_points, "أضف إجراء تباري على السكن أولاً.", True)
        self._maj_rural()
        self.proposer()
        self.fiche_points.ouvrir()
        return self.fiche_points

    def _rural(self) -> bool:
        cid = self.p_concours.currentData()
        return bool(cid and lg.concours(self.f.conn, cid).rural)

    def _maj_rural(self) -> None:
        r = self._rural()
        for x in (self.l_rural, self.p_femme, self.p_satellite):
            x.setVisible(r)
        self._classement()
        self.calculer()

    def proposer(self) -> None:
        """يملأ العناصر: من ترشيح محفوظ، وإلا من ملف الموظف."""
        pid, cid = self.p_personne.currentData(), self.p_concours.currentData()
        if pid is None:
            return
        cand = next((x for x in lg.candidats(self.f.conn, cid) if x.personnel_id == pid), None) if cid else None
        d = cand.donnees if cand else lg.proposition(self.f.conn, pid, self._rural())
        self._remplir(d)

    def _remplir(self, d: dict) -> None:
        widgets = (self.p_echelle, self.p_ag, self.p_al, self.p_situation, self.p_enfants, self.p_conjoint,
                   self.p_resp, self.p_rend, self.p_femme, self.p_satellite)
        for w in widgets:
            w.blockSignals(True)
        self.p_echelle.setCurrentIndex(max(0, self.p_echelle.findData(str(d.get("echelle") or ""))))
        self.p_ag.setValue(int(d.get("anciennete_generale") or 0))
        self.p_al.setValue(int(d.get("anciennete_locale") or 0))
        self.p_situation.setCurrentIndex(max(0, self.p_situation.findData(d.get("situation") or "celibataire")))
        self.p_enfants.setValue(int(d.get("enfants") or 0))
        self.p_conjoint.setChecked(bool(d.get("conjoint_sans_travail")))
        self.p_resp.setCurrentIndex(max(0, self.p_resp.findData(d.get("responsabilite") or "")))
        self.p_rend.setCurrentIndex(max(0, self.p_rend.findData(d.get("rendement") or "bien")))
        self.p_femme.setChecked(bool(d.get("femme_non_mariee")))
        self.p_satellite.setChecked(bool(d.get("satellite")))
        for w in widgets:
            w.blockSignals(False)
        self.calculer()

    def donnees(self) -> dict:
        return {"echelle": self.p_echelle.currentData(), "anciennete_generale": self.p_ag.value(),
                "anciennete_locale": self.p_al.value(), "situation": self.p_situation.currentData(),
                "enfants": self.p_enfants.value(), "conjoint_sans_travail": self.p_conjoint.isChecked(),
                "responsabilite": self.p_resp.currentData(), "rendement": self.p_rend.currentData(),
                "femme_non_mariee": self.p_femme.isChecked(), "satellite": self.p_satellite.isChecked()}

    def calculer(self) -> int:
        self.p_conjoint.setEnabled(self.p_situation.currentData() == "marie")
        r = lg.points(self.donnees(), self._rural())
        self.t_points.setRowCount(len(r["details"]))
        for i, (a, b, c) in enumerate(r["details"]):
            for j, x in enumerate((a, b, str(c))):
                it = cellule(x)
                if j == 2:
                    it.setTextAlignment(Qt.AlignCenter)
                    f_ = it.font()
                    f_.setBold(True)
                    it.setFont(f_)
                    it.setForeground(QColor(OR if c else "#90A4AE"))
                self.t_points.setItem(i, j, it)
        self.total = r["total"]
        self.l_total.setText(f"مجموع النقط: {r['total']}")
        return r["total"]

    def enregistrer_candidat(self):
        cid, pid = self.p_concours.currentData(), self.p_personne.currentData()
        if not cid or not pid:
            self._msg_fiche(self.m_points, "اختر إجراء التباري والموظف(ة).", True)
            return None
        try:
            c = lg.enregistrer_candidat(self.f.conn, cid, pid, self.donnees())
        except lg.ErreurLogement as e:
            self._msg_fiche(self.m_points, str(e), True)
            return None
        self._msg_fiche(self.m_points, f"حُفظ الترشيح: {c.points:g} نقطة.")
        self._classement()
        self.rafraichir()
        return c

    def _classement(self) -> None:
        cid = self.p_concours.currentData()
        cs = lg.candidats(self.f.conn, cid) if cid else []
        c = lg.concours(self.f.conn, cid) if cid else None
        vider_colonne_widgets(self.t_classement, 4)
        self.t_classement.setRowCount(len(cs))
        for i, x in enumerate(cs):
            p = rh.lire(self.f.conn, x.personnel_id)
            nom = f"{p.prenom_ar} {p.nom_ar}" + (" ★ المستفيد" if c and c.beneficiaire_id == p.id else "")
            for j, v in enumerate((str(i + 1), nom, f"{x.donnees.get('anciennete_generale', 0)} سنة", f"{x.points:g}")):
                it = cellule(v, p.id if j == 1 else None)
                if i == 0:
                    it.setForeground(QColor("#2E7D32"))
                self.t_classement.setItem(i, j, it)
            self.t_classement.setCellWidget(i, 4, boutons_ligne([
                ("طلب المشاركة", "#3949AB", "document",
                 lambda y=p.id: self.document("demande", "apercu", concours_id=cid, personnel_id=y)),
                ("إسناد السكن", "#2E7D32", "valider", lambda y=p.id: self.attribuer(y)),
                ("حذف", "", "", lambda y=p.id: self.retirer(y))]))
        ajuster_colonne_actions(self.t_classement, 4)
        if cs and lg.ex_aequo(cs):
            self._msg_fiche(self.m_points, "تساوى المرشحان الأولان في النقط والأقدمية: يُفصل بينهما بالقرعة.", True)

    def attribuer(self, pid: int) -> bool:
        cid = self.p_concours.currentData()
        try:
            lg.attribuer(self.f.conn, cid, pid)
        except lg.ErreurLogement as e:
            self._msg_fiche(self.m_points, str(e), True)
            return False
        self._msg_fiche(self.m_points, "أُسند السكن، وسُجل المستفيد شاغلاً له (بطاقة مراقبة السكن).")
        self._classement()
        self.rafraichir()
        return True

    def retirer(self, pid: int) -> None:
        lg.supprimer_candidat(self.f.conn, self.p_concours.currentData(), pid)
        self._classement()
        self.rafraichir()
