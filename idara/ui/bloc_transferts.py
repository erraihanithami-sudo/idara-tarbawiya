"""تبويب «الاستخلاص وتحويل الحصص» في صفحتي الجمعية الرياضية المدرسية وجمعية تنمية التعاون المدرسي
(وثائق المدير 2026-11-24). كل الإدخالات في نوافذ منبثقة."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QComboBox, QFormLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from idara.services import bureautique
from idara.services import transferts as tr
from idara.ui.composants import carte
from idara.ui.formulaires import champ
from idara.ui.saisie import ChampDate, cellule, message, tableau


class BlocTransferts(QWidget):
    def __init__(self, page, type_: str):
        super().__init__()
        from idara.ui.vitrine import bouton_couleur
        self.page, self.f, self.type_ = page, page.f, type_
        self.rg = tr.regime(type_)
        v0 = QVBoxLayout(self)
        v0.setContentsMargins(0, 0, 0, 0)
        v0.setSpacing(16)
        self.message = page.message
        # 1. المبلغ المستخلص
        c, v = carte("المبلغ المستخلص")
        self.l_collecte = QLabel()
        self.l_collecte.setWordWrap(True)
        self.l_collecte.setStyleSheet("font-size: 16px; font-weight: 800;")
        v.addWidget(self.l_collecte)
        self.l_ref = QLabel(f"المرجع: {self.rg.reference}.")
        self.l_ref.setObjectName("etiquette")
        self.l_ref.setWordWrap(True)
        v.addWidget(self.l_ref)
        h = QHBoxLayout()
        b = bouton_couleur("المبلغ المستخلص (مسك يدوي)", "#1565C0", "modifier",
                           "إن كان الاستخلاص بمطبوع الأساتذة: اكتب المجموع وعدد المنخرطين")
        b.clicked.connect(lambda: self.ouvrir_collecte())
        h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        self.l_alertes = QLabel()
        self.l_alertes.setWordWrap(True)
        self.l_alertes.setStyleSheet("color: #B5462F; font-weight: 700;")
        v.addWidget(self.l_alertes)
        v0.addWidget(c)
        # 2. التوزيع
        c, v = carte("توزيع الحصص وتحويلها")
        self.table = tableau(["الجهة", "النسبة", "المستحق (درهم)", "المحوَّل", "الباقي", "رقم الحساب الجاري",
                              "الإجراءات"], etirer=0)
        self.table.setMinimumHeight(260)
        self.table.verticalHeader().setDefaultSectionSize(44)
        v.addWidget(self.table)
        h = QHBoxLayout()
        for lib, coul, pic, fn, aide in (
                ("تحويل حصة", "#2E7D32", "envoyer", lambda: self.ouvrir_virement(), ""),
                ("محضر الاستخلاص والتوزيع", "#6A1B9A", "document", lambda: self.generer("pv"),
                 "يُرفق بالتحويلات"),
                ("شهادة نفقة", "#00838F", "document", lambda: self.generer("certificat"),
                 "المبالغ المحوَّلة وتواريخها وأرقام الحسابات"),
                ("تسجيل حصة الجمعية في مداخيلها", "#B07A16", "ajouter", lambda: self.ouvrir_part(),
                 "مدخول في السنة المالية للجمعية (تبويب المداخيل والمصاريف)")):
            bb = bouton_couleur(lib, coul, pic, aide)
            bb.clicked.connect(fn)
            h.addWidget(bb)
        h.addStretch()
        v.addLayout(h)
        v0.addWidget(c)
        # 3. برمجة الصرف (التعاونية)
        self.t_prog = None
        if self.rg.programme:
            c, v = carte("مجالات صرف حصة التعاونية المدرسية بالمؤسسة")
            self.t_prog = tableau(["المجال", "النسبة", "المبلغ المبرمج (درهم)"], etirer=0)
            self.t_prog.setMinimumHeight(220)
            v.addWidget(self.t_prog)
            v0.addWidget(c)
        # 4. التحويلات المسجلة
        c, v = carte("التحويلات المسجلة")
        self.t_ops = tableau(["التاريخ", "الجهة", "المبلغ (درهم)", "المرجع", "الإجراءات"], etirer=1)
        self.t_ops.setMinimumHeight(180)
        self.t_ops.verticalHeader().setDefaultSectionSize(44)
        v.addWidget(self.t_ops)
        v0.addWidget(c)
        v0.addStretch()
        self._fiches()

    # ---------- النوافذ ----------
    def _fiches(self) -> None:
        from idara.ui.vitrine import FenetreFiche, bouton_couleur

        def fiche(titre, sous, lignes, boutons, largeur=620):
            w = QWidget()
            v = QVBoxLayout(w)
            fl = QFormLayout()
            for lib, x in lignes:
                fl.addRow(lib, x)
            v.addLayout(fl)
            h = QHBoxLayout()
            for lib, coul, fn in boutons:
                b = bouton_couleur(lib, coul, "enregistrer")
                b.clicked.connect(fn)
                h.addWidget(b)
            h.addStretch()
            v.addLayout(h)
            m = QLabel()
            m.setWordWrap(True)
            m.hide()
            v.addWidget(m)
            fi = FenetreFiche(self, titre, sous, w, largeur=largeur)
            fi.msg = m
            return fi
        self.c_montant, self.c_eleves = champ("بالدرهم", ltr=True), champ("عدد التلاميذ المنخرطين", ltr=True)
        self.fiche_collecte = fiche("المبلغ المستخلص", "المجموع الفعلي من محاضر الاستخلاص (المطبوع اليدوي).",
                                    [("المبلغ المستخلص", self.c_montant), ("عدد المنخرطين", self.c_eleves)],
                                    [("حفظ", "#2E7D32", lambda: self.enregistrer_collecte()),
                                     ("الرجوع إلى ما سُجّل في «التسجيلات»", "#546E7A",
                                      lambda: self.enregistrer_collecte(retour=True))])
        self.c_part = QComboBox()
        for p in self.rg.parts:
            self.c_part.addItem(p.libelle, p.cle)
        self.c_date = ChampDate()
        self.c_mt = champ("فارغ: الباقي المستحق كاملاً", ltr=True)
        self.c_reference = champ("رقم الشيك أو الحوالة أو التوصيل")
        self.fiche_virement = fiche("تحويل حصة", "يُسجَّل في الشهادة بتاريخه ومبلغه.",
                                    [("الجهة", self.c_part), ("تاريخ التحويل", self.c_date), ("المبلغ", self.c_mt),
                                     ("المرجع", self.c_reference)],
                                    [("تسجيل التحويل", "#2E7D32", lambda: self.enregistrer_virement())], 700)
        self.c_compte = champ("رقم الحساب الجاري أو البريدي", ltr=True)
        self.l_compte = QLabel()
        self.fiche_compte = fiche("رقم الحساب الجاري", "", [("الجهة", self.l_compte), ("رقم الحساب", self.c_compte)],
                                  [("حفظ", "#2E7D32", lambda: self.enregistrer_compte())])
        self.c_date_part = ChampDate()
        self.c_registre = QComboBox()
        self.c_registre.addItem("البنك", "banque")
        self.c_registre.addItem("الصندوق", "caisse")
        self.fiche_part = fiche("تسجيل حصة الجمعية في مداخيلها", "يُسجَّل مدخولاً في السنة المالية التي يقع فيها التاريخ.",
                                [("التاريخ", self.c_date_part), ("السجل", self.c_registre)],
                                [("تسجيل", "#2E7D32", lambda: self.inscrire_part())])

    def _erreur(self, fi, e) -> None:
        message(fi.msg, str(e), True)

    def ouvrir_collecte(self):
        c = tr.collecte(self.f.conn, self.type_)
        self.c_montant.setText(f"{c['montant']:g}" if c["source"] == "manuel" else "")
        self.c_eleves.setText(str(c["eleves"] or "") if c["source"] == "manuel" else "")
        self.fiche_collecte.msg.hide()
        self.fiche_collecte.ouvrir()
        return self.fiche_collecte

    def enregistrer_collecte(self, retour: bool = False) -> bool:
        try:
            tr.definir_collecte(self.f.conn, self.type_, None if retour else self.c_montant.text(),
                                None if retour else self.c_eleves.text())
        except tr.ErreurTransfert as e:
            self._erreur(self.fiche_collecte, e)
            return False
        self.fiche_collecte.hide()
        self.rafraichir()
        return True

    def ouvrir_virement(self, part: str | None = None):
        if part:
            self.c_part.setCurrentIndex(max(0, self.c_part.findData(part)))
        self.c_date.definir(date.today().isoformat())
        self.c_mt.clear()
        self.c_reference.clear()
        self.fiche_virement.msg.hide()
        self.fiche_virement.ouvrir()
        return self.fiche_virement

    def enregistrer_virement(self) -> int | None:
        try:
            vid = tr.enregistrer_virement(self.f.conn, self.type_, self.c_part.currentData(), self.c_date.iso() or "",
                                          self.c_mt.text() or None, self.c_reference.text())
        except (tr.ErreurTransfert, ValueError) as e:
            self._erreur(self.fiche_virement, e if isinstance(e, tr.ErreurTransfert) else "تاريخ التحويل غير صحيح.")
            return None
        self.fiche_virement.hide()
        self.rafraichir()
        message(self.message, "سُجّل التحويل.")
        return vid

    def ouvrir_compte(self, part: str):
        self._part_compte = part
        self.l_compte.setText(next(p.libelle for p in self.rg.parts if p.cle == part))
        self.c_compte.setText(tr.comptes(self.f.conn, self.type_).get(part, ""))
        self.fiche_compte.msg.hide()
        self.fiche_compte.ouvrir()
        return self.fiche_compte

    def enregistrer_compte(self) -> bool:
        tr.definir_compte(self.f.conn, self.type_, self._part_compte, self.c_compte.text())
        self.fiche_compte.hide()
        self.rafraichir()
        return True

    def ouvrir_part(self):
        self.c_date_part.definir(date.today().isoformat())
        self.fiche_part.msg.hide()
        self.fiche_part.ouvrir()
        return self.fiche_part

    def inscrire_part(self) -> int | None:
        try:
            oid = tr.inscrire_part_association(self.f.conn, self.type_, self.c_date_part.iso() or None,
                                               self.c_registre.currentData())
        except (tr.ErreurTransfert, ValueError) as e:
            self._erreur(self.fiche_part, e)
            return None
        except Exception as e:  # noqa: BLE001 — رصيد أو سنة مالية
            self._erreur(self.fiche_part, e)
            return None
        self.fiche_part.hide()
        message(self.message, "سُجّلت حصة الجمعية مدخولاً في سجلاتها.")
        if hasattr(self.page, "rafraichir_finance"):
            self.page.rafraichir_finance()
        return oid

    def supprimer(self, vid: int) -> None:
        tr.supprimer_virement(self.f.conn, self.type_, vid)
        self.rafraichir()

    def generer(self, quoi: str):
        try:
            if quoi == "pv":
                p = tr.generer_pv_collecte(self.f.conn, self.f.dossier, self.type_)
            else:
                p = tr.generer_certificat(self.f.conn, self.f.dossier, self.type_)
        except tr.ErreurTransfert as e:
            message(self.message, str(e), True)
            return None
        message(self.message, f"وُلّدت الوثيقة: ⁦{p.name}⁩")
        try:
            bureautique.ouvrir(p)
        except OSError:
            pass
        return p

    # ---------- العرض ----------
    def rafraichir(self) -> None:
        from idara.services import textes as tx
        from idara.ui.vitrine import ajuster_colonne_actions, boutons_ligne, vider_colonne_widgets
        try:
            r = tr.repartition(self.f.conn, self.type_)
        except tr.ErreurTransfert as e:
            self.l_collecte.setText(str(e))
            return
        c = r["collecte"]
        if c["source"] == "manuel":
            src = "مسك يدوي من محاضر الاستخلاص"
            p = c["programme"]
            if p["montant"]:
                src += f" (المسجل في «التسجيلات»: {tr._dh(p['montant'])} درهم)"
        else:
            src = "من الأداءات المسجلة في «التسجيلات»"
        n = f" · {c['eleves']} منخرطاً" if c["eleves"] else ""
        self.l_collecte.setText(f"{tr._dh(c['montant'])} درهم{n} · {src}")
        al = tr.echeances(self.f.conn, self.type_)
        self.l_alertes.setText("\n".join(al))
        self.l_alertes.setVisible(bool(al))
        lignes = []
        for l in r["lignes"]:
            lignes.append((l, None))
            for s in l["sous"]:
                lignes.append((l, s))
        vider_colonne_widgets(self.table, 6)
        self.table.setRowCount(len(lignes) + 1)
        for i, (l, s) in enumerate(lignes):
            if s is None:
                vals = (l["libelle"], f"{l['pct']:g}%", tr._dh(l["du"]), tr._dh(l["vire"]), tr._dh(l["reste"]),
                        l["compte"] or "—")
            else:
                vals = (f"   منها: {s[0]}", f"{s[1]:g}%", tr._dh(s[2]), "", "", "")
            for j, x in enumerate(vals):
                it = cellule(x)
                if s is not None:
                    it.setForeground(QColor("#6B6B7B"))
                elif j == 4 and l["reste"] > 0 and not l["association"]:
                    it.setForeground(QColor("#C62828"))
                self.table.setItem(i, j, it)
            if s is None:
                acts = [("الحساب", "#546E7A", "modifier", lambda k=l["cle"]: self.ouvrir_compte(k))]
                if not l["association"]:
                    acts.insert(0, ("تحويل", "#2E7D32", "envoyer", lambda k=l["cle"]: self.ouvrir_virement(k)))
                self.table.setCellWidget(i, 6, boutons_ligne(acts))
        i = len(lignes)
        for j, x in enumerate(("المجموع", "100%", tr._dh(r["total_du"]), tr._dh(r["total_vire"]),
                               tr._dh(r["total_du"] - r["total_vire"]), "")):
            it = cellule(x)
            f = it.font()
            f.setBold(True)
            it.setFont(f)
            self.table.setItem(i, j, it)
        ajuster_colonne_actions(self.table, 6)
        if self.t_prog is not None:
            self.t_prog.setRowCount(len(r["programme"]))
            for i, (lib, pc, m) in enumerate(r["programme"]):
                for j, x in enumerate((lib, f"{pc:g}%", tr._dh(m))):
                    self.t_prog.setItem(i, j, cellule(x))
        noms = {p.cle: p.libelle for p in self.rg.parts}
        ops = r["operations"]
        vider_colonne_widgets(self.t_ops, 4)
        self.t_ops.setRowCount(len(ops))
        for i, o in enumerate(ops):
            for j, x in enumerate((tx.date_chiffres(o["date"]), noms.get(o["part"], o["part"]), tr._dh(o["montant"]),
                                   o["reference"] or "—")):
                self.t_ops.setItem(i, j, cellule(x))
            self.t_ops.setCellWidget(i, 4, boutons_ligne([("حذف", "#C62828", "annuler",
                                                           lambda x=o["id"]: self.supprimer(x))]))
        ajuster_colonne_actions(self.t_ops, 4)
