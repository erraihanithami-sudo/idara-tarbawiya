"""وثيقة «التنظيم التربوي» للموسم الدراسي (نموذج المدير، 2026-11-03).

تُملأ في قالب المدير نفسه (resources/gabarits/tanzim_tarbawi.docx، مفرغاً من الصور والخطوط المضمنة):
الرأس (المؤسسة، رمزها، عدد الوحدات، الهاتف، الجماعة، المفتشون حسب المادة)، هيئة الإدارة التربوية مع أنصاف أيام
العطلة الأسبوعية، المساعدون التربويون، البنية التربوية، هيئة التدريس، الأساتذة المكلفون بالمؤسسة، والمكلفون خارجها.
جدولا «المساعدون التربويون» و«أنصاف أيام العطلة الأسبوعية» موجودان في نسخة PDF من النموذج دون نسخة Word، فأُضيفا
على شكلهما في PDF.
"""

from __future__ import annotations

import copy
import sqlite3
from datetime import date, datetime
from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

from idara.services import annee as annee_srv
from idara.services import etablissement as etab_srv
from idara.services import personnel as rh
from idara.services import textes as tx
from idara.data.dossier import DossierDonnees
from idara.services.massar import niveaux_du_code_classe

GABARIT = Path(__file__).resolve().parent.parent / "resources" / "gabarits" / "tanzim_tarbawi.docx"
INSPECTEURS = {"tanzim_insp_ar": "عربية", "tanzim_insp_fr": "فرنسية", "tanzim_insp_mixte": "مزدوج"}
NIVEAUX_PRIMAIRE = ("1AP", "2AP", "3AP", "4AP", "5AP", "6AP")


class ErreurTanzim(ValueError):
    """رسالة موجهة للمدير بالعربية."""


# ---------- المفتشون ----------

def inspecteurs(conn) -> dict[str, str]:
    lus = {r["cle"]: r["valeur"] for r in conn.execute("SELECT cle, valeur FROM parametre WHERE cle LIKE 'tanzim_%'")}
    return {k: lus.get(k, "") for k in INSPECTEURS}


def definir_inspecteurs(conn, valeurs: dict[str, str]) -> None:
    with conn:
        for k, v in valeurs.items():
            if k not in INSPECTEURS:
                raise ErreurTanzim(f"إعداد غير معروف: {k}")
            v = " ".join((v or "").split())
            if v:
                conn.execute("INSERT INTO parametre(cle, valeur) VALUES (?,?) "
                             "ON CONFLICT(cle) DO UPDATE SET valeur=excluded.valeur", (k, v))
            else:
                conn.execute("DELETE FROM parametre WHERE cle=?", (k,))


# ---------- المعطيات ----------

def _d(v) -> str:
    return tx.date_chiffres(v) if v else ""


def _note(p: rh.Personnel) -> tuple[str, str]:
    if p.sans_inspection:
        return "لم يُفتَّش بعد", ""
    if p.note_inspection in (None, ""):
        return "", ""
    return f"{float(p.note_inspection):g}", _d(p.date_inspection)


def structure(conn) -> list[dict]:
    """البنية التربوية: لكل مستوى، الأفواج (الأقسام التي فيها تلاميذ من المستوى) وعدد تلاميذ المستوى في كل فوج.
    القسم المشترك يُعد فوجاً في كل مستوى من مستوياته."""
    a = annee_srv.annee_courante(conn)
    lignes = conn.execute(
        "SELECT c.code, n.code AS niveau, COUNT(*) AS n FROM inscription i JOIN classe c ON c.id=i.classe_id "
        "JOIN niveau n ON n.id=i.niveau_id WHERE i.annee_id=? AND i.statut IN ('inscrit','arrive') "
        "GROUP BY c.code, n.code ORDER BY c.code", (a["id"] if a else -1,)).fetchall()
    res = []
    for niv in NIVEAUX_PRIMAIRE:
        groupes = [(r["code"], r["n"]) for r in lignes if r["niveau"] == niv]
        total = sum(n for _, n in groupes)
        res.append({"niveau": niv, "libelle": tx.niveau_ar(niv), "groupes": groupes, "total": total,
                    "moyenne": round(total / len(groupes), 2) if groupes else None})
    return res


def _classes(conn, p: rh.Personnel) -> tuple[str, int | None]:
    e = rh.enseignement(conn, p)
    return (" / ".join(e["classes"]) or p.niveau_enseigne or ""), e["nb_eleves"]


def donnees(conn) -> dict:
    etab = etab_srv.lire_etablissement(conn)
    actifs = [p for p in rh.lister(conn) if p.statut == "actif"]
    unites = conn.execute("SELECT COUNT(*) FROM unite_scolaire").fetchone()[0]
    ens = sorted((p for p in actifs if p.categorie == "enseignant"), key=lambda p: (p.unite, p.nom_ar, p.prenom_ar))
    return {
        "etab": etab, "annee": (annee_srv.annee_courante(conn) or {"libelle": ""})["libelle"],
        "unites": unites or 1, "inspecteurs": inspecteurs(conn),
        "administration": [p for p in actifs if p.categorie == "directeur"],
        "assistants": [p for p in actifs if p.categorie == "assistant"],
        "structure": structure(conn),
        "enseignants": [p for p in ens if p.situation == "normal"],
        "charges_in": [p for p in ens if p.situation == "charge_in"],
        "charges_out": [p for p in ens if p.situation == "charge_out"],
    }


def manquants(conn) -> list[str]:
    """ما ينقص لتوليد الوثيقة دون خانات فارغة: «الاسم: الحقول». لا يُولَّد قبل إكماله (قاعدة المدير)."""
    d = donnees(conn)
    res = []
    if d["etab"] is None:
        return ["إعداد المؤسسة"]
    for lib, v in (("رمز المؤسسة", d["etab"].code_etab), ("هاتف المؤسسة", d["etab"].telephone),
                   ("الجماعة", d["etab"].commune_ar)):
        if not v:
            res.append(f"المؤسسة: {lib} (صفحة «المؤسسة» في الإعدادات)")
    for groupe in ("administration", "assistants", "enseignants", "charges_in", "charges_out"):
        for p in d[groupe]:
            m = rh.manquants_tanzim(conn, p)
            if m:
                res.append(f"{p.prenom_ar} {p.nom_ar}: " + "، ".join(m))
    return res


# ---------- الكتابة في القالب ----------

def _ecrire(tc, texte: str, gras: bool = False) -> None:
    """يكتب النص في خلية مع الاحتفاظ بتنسيق فقرتها الأولى."""
    ps = tc.findall(qn("w:p"))
    p = ps[0]
    for autre in ps[1:]:
        tc.remove(autre)
    rpr_modele = None
    ppr = p.find(qn("w:pPr"))
    if ppr is not None and ppr.find(qn("w:rPr")) is not None:
        rpr_modele = ppr.find(qn("w:rPr"))
    for r in p.findall(qn("w:r")):
        if rpr_modele is None and r.find(qn("w:rPr")) is not None:
            rpr_modele = r.find(qn("w:rPr"))
        p.remove(r)
    r = OxmlElement("w:r")
    if rpr_modele is not None:
        rpr = copy.deepcopy(rpr_modele)
        rpr.tag = qn("w:rPr")
        r.append(rpr)
    if gras and r.find(qn("w:rPr")) is not None and r.find(qn("w:rPr")).find(qn("w:b")) is None:
        r.find(qn("w:rPr")).append(OxmlElement("w:b"))
    t = OxmlElement("w:t")
    t.text = texte
    t.set(qn("xml:space"), "preserve")
    r.append(t)
    p.append(r)


def _cellules(tr) -> list:
    return tr.findall(qn("w:tc"))


def _sans_fusion_verticale(tc) -> None:
    pr = tc.find(qn("w:tcPr"))
    if pr is not None:
        for v in pr.findall(qn("w:vMerge")):
            pr.remove(v)


def _fusion_verticale(tc, debut: bool) -> None:
    pr = tc.find(qn("w:tcPr"))
    if pr is None:
        pr = OxmlElement("w:tcPr")
        tc.insert(0, pr)
    v = OxmlElement("w:vMerge")
    if debut:
        v.set(qn("w:val"), "restart")
    pr.append(v)


def _lignes_donnees(tbl, entetes: int, n: int) -> list:
    """يُبقي n سطراً بعد سطور العنوان (ينسخ آخر سطر إن لزم، ويحذف الزائد) ويزيل الفوارق العمودية فيها."""
    trs = tbl.findall(qn("w:tr"))
    donnees_ = trs[entetes:]
    modele = donnees_[-1]
    while len(donnees_) < n:
        nouveau = copy.deepcopy(modele)
        donnees_[-1].addnext(nouveau)
        donnees_.append(nouveau)
    for tr in donnees_[n:]:
        tbl.remove(tr)
    donnees_ = donnees_[:n]
    for tr in donnees_:
        for tc in _cellules(tr):
            _sans_fusion_verticale(tc)
    return donnees_


def _remplir_lignes(tbl, entetes: int, lignes: list[list[str]], col_unite: int | None = None) -> None:
    trs = _lignes_donnees(tbl, entetes, max(1, len(lignes)))
    if not lignes:  # جدول دون أسطر: «لا يوجد» في الخانة الثانية
        tcs = _cellules(trs[0])
        for i, tc in enumerate(tcs):
            _ecrire(tc, "لا يوجد" if i == min(2, len(tcs) - 1) else "")
        return
    for tr, valeurs in zip(trs, lignes):
        for tc, v in zip(_cellules(tr), valeurs):
            _ecrire(tc, v)
    if col_unite is not None:  # دمج خانات الوحدة المدرسية المتتالية المتطابقة
        precedente = None
        for tr, valeurs in zip(trs, lignes):
            tc = _cellules(tr)[col_unite]
            debut = valeurs[col_unite] != precedente
            _fusion_verticale(tc, debut)
            if not debut:
                _ecrire(tc, "")
            precedente = valeurs[col_unite]


def _completer_paragraphe(p, valeur: str) -> None:
    r = OxmlElement("w:r")
    runs = p.findall(qn("w:r"))
    if runs and runs[-1].find(qn("w:rPr")) is not None:
        r.append(copy.deepcopy(runs[-1].find(qn("w:rPr"))))
    t = OxmlElement("w:t")
    t.text = " " + valeur
    t.set(qn("xml:space"), "preserve")
    r.append(t)
    p.append(r)


def _texte(p) -> str:
    return "".join(x.text or "" for x in p.iter(qn("w:t")))


def _remplacer_paragraphe(p, texte: str) -> None:
    runs = p.findall(qn("w:r"))
    for r in runs[1:]:
        p.remove(r)
    ts = list(runs[0].iter(qn("w:t")))
    ts[0].text = texte
    ts[0].set(qn("xml:space"), "preserve")
    for t in ts[1:]:
        t.text = ""


def _entete(doc, dossier: DossierDonnees, d: dict) -> None:
    t0 = doc.tables[0]._tbl
    trs = t0.findall(qn("w:tr"))
    c = _cellules(trs[0])
    etab = d["etab"]
    if etab.logo_path and (dossier.racine / etab.logo_path).exists():   # ترويسة المؤسسة من الإعداد
        doc.tables[0].cell(0, 0).paragraphs[0].add_run().add_picture(str(dossier.racine / etab.logo_path),
                                                                     width=Cm(9.3))
    for p in c[1].findall(qn("w:p")):
        if "للموسم الدراسي" in _texte(p):
            _remplacer_paragraphe(p, f"للموسم الدراسي {d['annee']}")
    valeurs = {"المؤسسة": etab.nom_ar, "رمزها": etab.code_etab or "", "عدد الوحدات المدرسية": str(d["unites"]),
               "الهاتف": etab.telephone or "", "الجماعة": etab.commune_ar or ""}
    for tc in c[2:]:
        for p in tc.findall(qn("w:p")):
            t = _texte(p)
            for lib, v in valeurs.items():
                if lib in t:
                    _remplacer_paragraphe(p, t.rstrip() + " " + v)
                    break
    insp = d["inspecteurs"]
    for tc in _cellules(trs[1])[2:]:
        for p in tc.findall(qn("w:p")):
            if "عربية" in _texte(p):
                _remplacer_paragraphe(p, "    ".join(f"{lib}: {insp[k] or '—'}" for k, lib in INSPECTEURS.items()))


def _ajouter_repos(tbl_admin, admins: list[rh.Personnel]) -> None:
    """عمودا «أنصاف أيام العطلة الأسبوعية: صباحاً، مساءً» (نسخة PDF من النموذج) في جدول هيئة الإدارة."""
    grille = tbl_admin.find(qn("w:tblGrid"))
    cols = grille.findall(qn("w:gridCol"))
    total = sum(int(g.get(qn("w:w"))) for g in cols)
    ajout = 1500
    facteur = (total - 2 * ajout) / total
    for g in cols:
        g.set(qn("w:w"), str(int(int(g.get(qn("w:w"))) * facteur)))
    for _ in range(2):
        g = OxmlElement("w:gridCol")
        g.set(qn("w:w"), str(ajout))
        grille.append(g)
    for tr in tbl_admin.findall(qn("w:tr")):
        for tc in _cellules(tr):
            pr = tc.find(qn("w:tcPr"))
            w = pr.find(qn("w:tcW")) if pr is not None else None
            if w is not None and w.get(qn("w:type")) == "dxa":
                w.set(qn("w:w"), str(int(int(w.get(qn("w:w"))) * facteur)))
    trs = tbl_admin.findall(qn("w:tr"))
    # العنوان: خلية تمتد على العمودين
    tete = copy.deepcopy(_cellules(trs[0])[-1])
    pr = tete.find(qn("w:tcPr"))
    pr.find(qn("w:tcW")).set(qn("w:w"), str(2 * ajout))
    gs = OxmlElement("w:gridSpan")
    gs.set(qn("w:val"), "2")
    pr.insert(1, gs)
    _ecrire(tete, "أنصاف أيام العطلة الأسبوعية (صباحاً / مساءً)")
    trs[0].append(tete)
    for tr, p in zip(trs[1:], admins or [None]):
        for v in ((p.repos_matin, p.repos_soir) if p else ("", "")):
            tc = copy.deepcopy(_cellules(tr)[-1])
            tc.find(qn("w:tcPr")).find(qn("w:tcW")).set(qn("w:w"), str(ajout))
            _ecrire(tc, v or "—")
            tr.append(tc)


def _table_assistants(doc, apres, assistants: list[rh.Personnel], modele_tblpr) -> None:
    """جدول «المساعدون التربويون» (نسخة PDF من النموذج) بعد جدول هيئة الإدارة."""
    titre = doc.add_paragraph()
    titre.alignment = 1
    titre._p.get_or_add_pPr().append(OxmlElement("w:bidi"))
    r = titre.add_run("المساعدون التربويون")
    r.bold = True
    r.font.rtl = True
    r.font.size = Pt(14)
    r.font.underline = True
    t = doc.add_table(rows=1 + max(1, len(assistants)), cols=4)
    t._tbl.remove(t._tbl.tblPr)
    t._tbl.insert(0, copy.deepcopy(modele_tblpr))
    for g, w in zip(t._tbl.tblGrid.findall(qn("w:gridCol")), (700, 4200, 2800, 2800)):
        g.set(qn("w:w"), str(w))
    lignes = [["رت", "الاسم الكامل", "رقم البطاقة الوطنية", "تاريخ الالتحاق بالمؤسسة"]]
    lignes += [[str(i), f"{p.prenom_ar} {p.nom_ar}", p.cin, _d(p.date_affectation)]
               for i, p in enumerate(assistants, start=1)] or [["", "لا يوجد", "", ""]]
    # تنسيق الخط من خلايا جدول هيئة الإدارة (العنوان والمعطيات)
    trs_admin = apres.findall(qn("w:tr"))
    modeles = [_cellules(trs_admin[0])[1], _cellules(trs_admin[1])[1]]
    for k, (row, vals) in enumerate(zip(t.rows, lignes)):
        for cell, v, w in zip(row.cells, vals, (700, 4200, 2800, 2800)):
            cell.width = w * 635
            tc = cell._tc
            for p_ in tc.findall(qn("w:p")):
                tc.remove(p_)
            tc.append(copy.deepcopy(modeles[0 if k == 0 else 1].find(qn("w:p"))))
            _ecrire(tc, v, gras=(k == 0))
    apres.addnext(titre._p)
    titre._p.addnext(t._tbl)
    t._tbl.tblPr.find(qn("w:tblW")).set(qn("w:w"), str(10500))


def generer(conn, dossier: DossierDonnees) -> Path:
    m = manquants(conn)
    if m:
        raise ErreurTanzim("معطيات ناقصة (تُكمل في «معلومات الأطر» أو الإعداد):\n" + "\n".join(m))
    d = donnees(conn)
    doc = Document(str(GABARIT))
    tbls = list(doc.element.body.iter(qn("w:tbl")))
    # جداول القالب «عائمة» (موضوعة بإحداثيات): عدد الأسطر يتغير، فتُجعل متتالية حتى لا تتراكب
    for t in tbls:
        pr = t.find(qn("w:tblPr"))
        for fp in pr.findall(qn("w:tblpPr")) + pr.findall(qn("w:tblOverlap")):
            pr.remove(fp)
    t_admin, t_struct, t_ens, t_in, t_out = tbls[1], tbls[2], tbls[3], tbls[4], tbls[6]
    _entete(doc, dossier, d)
    # هيئة الإدارة التربوية: العمود الأول (العنوان العمودي) يمتد على كل الأسطر
    admins = d["administration"]
    trs = _lignes_donnees(t_admin, 1, max(1, len(admins)))
    for k, (tr, p) in enumerate(zip(trs, admins)):
        cs = _cellules(tr)
        _fusion_verticale(cs[0], False)
        for tc, v in zip(cs[1:], (f"{p.prenom_ar} {p.nom_ar}", p.ppr, _d(p.date_recrutement), _d(p.date_fonction),
                                  _d(p.date_affectation))):
            _ecrire(tc, v)
    _ajouter_repos(t_admin, admins)
    _table_assistants(doc, t_admin, d["assistants"], t_admin.find(qn("w:tblPr")))
    # البنية التربوية
    for tr, s in zip(t_struct.findall(qn("w:tr"))[2:], d["structure"]):
        cs = _cellules(tr)
        _ecrire(cs[2], str(len(s["groupes"])) if s["groupes"] else "0")
        for k in range(5):
            _ecrire(cs[3 + k], str(s["groupes"][k][1]) if k < len(s["groupes"]) else "—")
        _ecrire(cs[8], str(s["total"]))
        _ecrire(cs[9], f"{s['moyenne']:g}" if s["moyenne"] is not None else "—")
    if any(len(s["groupes"]) > 5 for s in d["structure"]):
        raise ErreurTanzim("مستوى بأكثر من 5 أفواج: النموذج يتسع لخمسة فقط.")

    def ligne_prof(i, p, extra_debut=(), extra_milieu=()):
        cl, nb = _classes(conn, p)
        mat_tarl = p.matiere_tarl or p.matiere
        note, dnote = _note(p)
        return [str(i), p.unite or "—", f"{p.prenom_ar} {p.nom_ar}", p.ppr, *extra_debut,
                _d(p.date_recrutement), _d(p.date_affectation), *extra_milieu,
                rh.grade_court(p.grade), _d(p.date_grade), p.echelon, _d(p.date_echelon), note, dnote,
                ], (mat_tarl, p.matiere, p.classes_tarl or cl, cl, str(nb if nb is not None else ""))

    lignes = []
    for i, p in enumerate(d["enseignants"], start=1):
        base, fin = ligne_prof(i, p)
        lignes.append(base + list(fin))
    _remplir_lignes(t_ens, 2, lignes, col_unite=1)
    lignes = []
    for i, p in enumerate(d["charges_in"], start=1):
        cl, nb = _classes(conn, p)
        note, dnote = _note(p)
        lignes.append([str(i), p.unite or "—", f"{p.prenom_ar} {p.nom_ar}", p.ppr, p.matiere_tarl or p.matiere,
                       p.matiere, _d(p.date_recrutement), _d(p.date_affectation), p.etab_charge, _d(p.date_charge),
                       rh.grade_court(p.grade), _d(p.date_grade), p.echelon, _d(p.date_echelon), note, dnote,
                       p.classes_tarl or cl, cl, str(nb if nb is not None else "")])
    _remplir_lignes(t_in, 2, lignes, col_unite=1)
    lignes = []
    for i, p in enumerate(d["charges_out"], start=1):
        note, dnote = _note(p)
        lignes.append([str(i), p.unite or "—", f"{p.prenom_ar} {p.nom_ar}", p.ppr, _d(p.date_recrutement),
                       _d(p.date_affectation), p.etab_charge, _d(p.date_charge), rh.grade_court(p.grade),
                       _d(p.date_grade), p.echelon, _d(p.date_echelon), note, dnote])
    _remplir_lignes(t_out, 1, lignes, col_unite=1)
    # حرر في ... بتاريخ ...
    for p in doc.paragraphs:
        if "حرر في" in p.text and "بتاريخ" in p.text:
            ville = d["etab"].ville_redaction_ar or ""
            _remplacer_paragraphe(p._p, f" حرر في: {ville}                                بتاريخ: "
                                        f"{tx.date_chiffres(date.today().isoformat())}")
            break
    rep = dossier.archives / d["annee"].replace("/", "-") / "التنظيم التربوي"
    rep.mkdir(parents=True, exist_ok=True)
    chemin = rep / f"{datetime.now():%Y%m%d_%H%M%S}_التنظيم التربوي {d['annee'].replace('/', '-')}.docx"
    doc.save(chemin)
    with conn:
        conn.execute("INSERT INTO journal(action, cible, cible_id, details) VALUES ('generation','tanzim',NULL,?)",
                     (chemin.name,))
    return chemin
