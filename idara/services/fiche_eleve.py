"""بطاقة التلميذ (توجيهات المدير 2026-11-15): تتبع مسار كل تلميذ وتطور مستواه من الرائز القبلي إلى الرائز
البعدي ثم المراحل، مع مبيانات.

المصادر:
- رائزا الموضعة (TaRL): مستوى التلميذ على سلم كل مادة (niveau_apprentissage)، والمستوى المتوقع لمستواه الدراسي.
- مستويات التحكم A/B/C لكل رائز ومرحلة (isa_eleve): من ملف النتائج المستورد في «مؤسسات الريادة»، أو بإدخال المدير
  في البطاقة نفسها.
المبيانات ترسمها الواجهة (Qt) وتمرَّر صوراً إلى الوثيقة، كما في السبورة المرجعية.
"""

from __future__ import annotations

import io
import sqlite3
from datetime import datetime
from pathlib import Path

from idara.data.dossier import DossierDonnees
from idara.services import annee as annee_srv
from idara.services import evaluation as ev
from idara.services import tarl
from idara.services import textes as tx

MATIERES = {"ar": "اللغة العربية", "fr": "اللغة الفرنسية", "ma": "الرياضيات"}
PHASES = list(range(-1, 7))
NIVEAUX = {"A": "تحكم تام", "B": "تحكم مقنع", "C": "تحكم ضعيف"}
VALEUR = {"A": 3, "B": 2, "C": 1}


class ErreurFiche(ValueError):
    """رسالة موجهة للمدير بالعربية."""


def libelle_phase(p: int) -> str:
    return {-1: "الرائز القبلي", 0: "الرائز البعدي"}.get(p, f"المرحلة {p}")


def _ltr(x) -> str:
    return f"⁦{x}⁩"


def annees(conn: sqlite3.Connection) -> list[str]:
    a = annee_srv.annee_courante(conn)
    res = [a["libelle"]] if a else []
    for (lib,) in conn.execute(
            "SELECT DISTINCT s.libelle FROM annee_scolaire s WHERE s.id IN (SELECT annee_id FROM niveau_apprentissage "
            "UNION SELECT annee_id FROM isa_eleve) ORDER BY s.libelle DESC"):
        if lib not in res:
            res.append(lib)
    return res


def eleves(conn: sqlite3.Connection, classe_id: int | None = None, texte: str = "") -> list[dict]:
    """تلاميذ السنة الجارية (قسم أو الكل، مع بحث بالاسم أو رمز مسار)."""
    a = annee_srv.annee_courante(conn)
    if a is None:
        return []
    sql = ("SELECT e.id, e.nom_ar, e.prenom_ar, e.sexe, e.code_massar, c.code AS classe, c.id AS classe_id "
           "FROM inscription i JOIN eleve e ON e.id=i.eleve_id LEFT JOIN classe c ON c.id=i.classe_id "
           "WHERE i.annee_id=? AND i.statut IN ('inscrit','arrive')")
    args: list = [a["id"]]
    if classe_id is not None:
        sql += " AND i.classe_id=?"
        args.append(classe_id)
    res = [dict(r) for r in conn.execute(sql + " ORDER BY c.code, e.prenom_ar, e.nom_ar", args)]
    mots = texte.split()
    if mots:
        res = [r for r in res if all(m in f"{r['prenom_ar']} {r['nom_ar']} {r['code_massar']}" for m in mots)]
    return res


def identite(conn: sqlite3.Connection, eleve_id: int) -> dict:
    r = conn.execute("SELECT * FROM eleve WHERE id=?", (eleve_id,)).fetchone()
    if r is None:
        raise ErreurFiche("التلميذ(ة) غير موجود(ة).")
    a = annee_srv.annee_courante(conn)
    c = conn.execute("SELECT c.code FROM inscription i JOIN classe c ON c.id=i.classe_id WHERE i.eleve_id=? "
                     "AND i.annee_id=?", (eleve_id, a["id"] if a else -1)).fetchone()
    return {"id": r["id"], "nom": f"{r['prenom_ar']} {r['nom_ar']}", "sexe": r["sexe"],
            "code_massar": r["code_massar"] or "", "date_naissance": r["date_naissance"] or "",
            "classe": c[0] if c else ""}


def parcours(conn: sqlite3.Connection, eleve_id: int, annee: str | None = None) -> dict:
    """مسار التلميذ في سنة: رائزا الموضعة لكل مادة، ومستويات التحكم حسب الروائز والمراحل."""
    idt = identite(conn, eleve_id)
    if annee is None:
        a = annee_srv.annee_courante(conn)
        annee = a["libelle"] if a else ""
    code = idt["code_massar"]
    res_tarl: dict[str, dict] = {}
    rows = conn.execute(
        "SELECT n.* FROM niveau_apprentissage n JOIN annee_scolaire a ON a.id=n.annee_id WHERE a.libelle=? AND "
        "(n.eleve_id=? OR (n.code_massar=? AND ?<>''))", (annee, eleve_id, code, code)).fetchall()
    for m in MATIERES:
        par = {r["epreuve"]: r for r in rows if r["matiere"] == m}
        if not par:
            continue
        echelle = tarl.ECHELLES[m]
        niveau = next((r["niveau"] for r in par.values() if r["niveau"]), None)
        att = tarl.attendu(conn, annee, niveau, m) if niveau else None
        pre = par["pre"]["valeur"] if "pre" in par else None
        post = par["post"]["valeur"] if "post" in par else None
        rg = lambda v: None if v is None else tarl.rang(m, v)  # noqa: E731
        res_tarl[m] = {"echelle": echelle, "pre": pre, "post": post, "attendu": att, "rang_pre": rg(pre),
                       "rang_post": rg(post), "rang_attendu": rg(att)}
    etapes: dict[str, dict[int, str]] = {}
    for r in conn.execute(
            "SELECT s.phase, s.matiere, s.niveau FROM isa_eleve s JOIN annee_scolaire a ON a.id=s.annee_id "
            "WHERE a.libelle=? AND (s.eleve_id=? OR (s.code_massar=? AND ?<>''))", (annee, eleve_id, code, code)):
        etapes.setdefault(r["matiere"], {})[r["phase"]] = r["niveau"]
    return {"annee": annee, "eleve": idt, "tarl": res_tarl, "etapes": etapes}


def dossier_complet(conn: sqlite3.Connection, eleve_id: int) -> dict:
    """الملف الشامل للتلميذ عبر السنوات (طلب المدير 2026-11-20): المسار الدراسي، المعدلات، الحركية، السلوك،
    الفحوصات الطبية، والتنويهات والتشجيعات. كل قسم لائحة أسطر (قد تكون فارغة)."""
    from idara.services import deliberations as dl
    from idara.services import eleves as el
    from idara.services import registres as rg
    idt = identite(conn, eleve_id)
    code = idt["code_massar"]
    parcours_ = [{"annee": r["annee"], "classe": r["classe"] or "", "niveau": r["niveau"] or "",
                  "statut": el.STATUTS.get(r["statut"], r["statut"]), "entree": r["date_entree"] or "",
                  "sortie": r["date_sortie"] or "", "motif": r["motif_sortie"] or ""}
                 for r in conn.execute(
                     "SELECT a.libelle AS annee, c.code AS classe, n.libelle_ar AS niveau, i.statut, i.date_entree, "
                     "i.date_sortie, i.motif_sortie FROM inscription i JOIN annee_scolaire a ON a.id=i.annee_id "
                     "LEFT JOIN classe c ON c.id=i.classe_id LEFT JOIN niveau n ON n.id=i.niveau_id "
                     "WHERE i.eleve_id=? ORDER BY a.libelle DESC", (eleve_id,))]
    moyennes = [{"annee": r["annee"], "classe": r["classe"], "moyenne": r["moyenne"],
                 "mention": dl.mention(r["moyenne"])}
                for r in conn.execute(
                    "SELECT a.libelle AS annee, r.classe, r.moyenne FROM resultat r JOIN annee_scolaire a "
                    "ON a.id=r.annee_id WHERE r.eleve_id=? OR (r.code_massar=? AND ?<>'') ORDER BY a.libelle DESC",
                    (eleve_id, code, code))]
    mouvements = [{"annee": r["annee"], "sens": "وافد" if r["sens"] == "arrive" else "مغادر",
                   "date": r["date_mouvement"], "etablissement": r["etablissement"] or "",
                   "dossier": ("توصّلنا بالملف " + tx.date_chiffres(r["dossier_recu_le"]) if r["dossier_recu_le"] else
                               "أُرسل الملف " + tx.date_chiffres(r["dossier_envoye_le"]) if r["dossier_envoye_le"]
                               else "الملف في الانتظار")}
                  for r in conn.execute(
                      "SELECT a.libelle AS annee, m.* FROM mouvement m JOIN annee_scolaire a ON a.id=m.annee_id "
                      "WHERE m.eleve_id=? ORDER BY m.date_mouvement DESC", (eleve_id,))]
    comportement = [{"annee": r["annee"], "date": r["date_obs"], "nature": r["nature"], "mesure": r["mesure"] or "",
                     "convocation": r["date_convocation"] or ""}
                    for r in conn.execute(
                        "SELECT a.libelle AS annee, o.* FROM observation_comportement o JOIN annee_scolaire a "
                        "ON a.id=o.annee_id WHERE o.eleve_id=? ORDER BY o.date_obs DESC, o.id DESC", (eleve_id,))]
    medical = [{"annee": l["annee"], "date": l["date"], "type": l["type"], "resultat": l["resultat"],
                "suite": l["suite"]} for l in rg.lignes_eleve(conn, "examens_medicaux", idt["nom"])]
    distinctions = [{"annee": l["annee"], "date": l["date"], "type": l["type"], "motif": l["motif"],
                     "periode": l["periode"]} for l in rg.lignes_eleve(conn, "tahfiz", idt["nom"])]
    for m in moyennes:   # الميزة المستحقة بالمعدل السنوي (تنويه، تشجيع، لوحة الشرف)
        if m["mention"]:
            distinctions.append({"annee": m["annee"], "date": "", "type": m["mention"],
                                 "motif": f"المعدل السنوي {m['moyenne']:.2f}", "periode": "نهاية السنة"})
    return {"eleve": idt, "parcours": parcours_, "moyennes": moyennes, "mouvements": mouvements,
            "comportement": comportement, "medical": medical, "distinctions": distinctions}


# أقسام الملف الشامل: (المفتاح، العنوان، رؤوس الأعمدة، الحقول)
SECTIONS_DOSSIER = (
    ("parcours", "المسار الدراسي", ("السنة", "المستوى", "القسم", "الوضعية", "تاريخ الخروج", "السبب"),
     ("annee", "niveau", "classe", "statut", "sortie", "motif")),
    ("moyennes", "المعدلات السنوية", ("السنة", "القسم", "المعدل", "الميزة"), ("annee", "classe", "moyenne", "mention")),
    ("mouvements", "الحركية", ("السنة", "الحركة", "التاريخ", "المؤسسة", "الملف"),
     ("annee", "sens", "date", "etablissement", "dossier")),
    ("comportement", "السلوك", ("السنة", "التاريخ", "الملاحظة", "الإجراء", "استدعاء ولي الأمر"),
     ("annee", "date", "nature", "mesure", "convocation")),
    ("medical", "الفحوصات الطبية", ("السنة", "التاريخ", "نوع الفحص", "النتيجة", "الإجراء"),
     ("annee", "date", "type", "resultat", "suite")),
    ("distinctions", "التنويهات والتشجيعات", ("السنة", "التاريخ", "النوع", "المناسبة أو السبب", "الفترة"),
     ("annee", "date", "type", "motif", "periode")),
)


def valeur_dossier(cle: str, v) -> str:
    """قيمة خانة في الملف الشامل كما تُعرض (التواريخ بالأرقام، المعدل برقمين بعد الفاصلة)."""
    if v in ("", None):
        return ""
    if cle == "moyenne":
        return f"{float(v):.2f}"
    if cle in ("date", "sortie", "convocation") and len(str(v)) == 10 and str(v)[4] == "-":
        return tx.date_chiffres(v)
    return str(v).replace("\n", " · ")


def enregistrer_etape(conn: sqlite3.Connection, eleve_id: int, annee: str, phase: int, matiere: str,
                      niveau: str | None) -> None:
    """مستوى التحكم A/B/C لتلميذ في مادة ورائز أو مرحلة (فارغ: يُحذف)."""
    if matiere not in MATIERES or phase not in range(-1, 9):
        raise ErreurFiche("مادة أو مرحلة غير صحيحة.")
    niveau = (niveau or "").strip().upper()[:1]
    if niveau and niveau not in VALEUR:
        raise ErreurFiche("المستوى: A أو B أو C.")
    idt = identite(conn, eleve_id)
    code = idt["code_massar"] or f"#{eleve_id}"
    aid = ev._annee_id(conn, annee)
    with conn:
        if not niveau:
            conn.execute("DELETE FROM isa_eleve WHERE annee_id=? AND code_massar=? AND phase=? AND matiere=?",
                         (aid, code, phase, matiere))
        else:
            conn.execute("INSERT INTO isa_eleve(annee_id, code_massar, eleve_id, classe, phase, matiere, niveau, source) "
                         "VALUES (?,?,?,?,?,?,?, 'إدخال يدوي') ON CONFLICT(annee_id, code_massar, phase, matiere) DO "
                         "UPDATE SET niveau=excluded.niveau, eleve_id=excluded.eleve_id, source=excluded.source",
                         (aid, code, eleve_id, idt["classe"], phase, matiere, niveau))


def observations(p: dict) -> list[str]:
    """ملاحظات آلية: التطور بين الرائزين، والموقع من المستوى المتوقع، وآخر مستوى تحكم في المراحل."""
    res = []
    for m, t in p["tarl"].items():
        lib = MATIERES[m]
        if t["pre"] and t["post"]:
            d = t["rang_post"] - t["rang_pre"]
            sens = (f"تقدم بـ{d} {'درجة' if d == 1 else 'درجات'}" if d > 0 else "استقر" if d == 0
                    else f"تراجع بـ{-d} {'درجة' if d == -1 else 'درجات'}")
            res.append(f"{lib}: من «{t['pre']}» إلى «{t['post']}» ({sens}).")
        elif t["pre"] or t["post"]:
            res.append(f"{lib}: «{t['pre'] or t['post']}» في {'الرائز القبلي' if t['pre'] else 'الرائز البعدي'} فقط.")
        dernier = t["post"] or t["pre"]
        if dernier and t["attendu"]:
            ecart = t["rang_attendu"] - (t["rang_post"] if t["post"] else t["rang_pre"])
            if ecart <= 0:
                res.append(f"{lib}: بلغ(ت) المستوى المتوقع «{t['attendu']}».")
            else:
                res.append(f"{lib}: دون المستوى المتوقع «{t['attendu']}» بـ{ecart} "
                           + ("درجة." if ecart == 1 else "درجات."))
    for m, ph in p["etapes"].items():
        etapes = {k: v for k, v in ph.items() if k >= 1}
        if etapes:
            k = max(etapes)
            res.append(f"{MATIERES[m]}: {NIVEAUX[etapes[k]]} في {libelle_phase(k)}.")
    return res


def a_besoin_soutien(p: dict) -> bool:
    """دون المستوى المتوقع في آخر رائز، أو تحكم ضعيف في آخر مرحلة."""
    for t in p["tarl"].values():
        r = t["rang_post"] if t["post"] else t["rang_pre"]
        if r is not None and t["rang_attendu"] is not None and r < t["rang_attendu"]:
            return True
    return any(ph[max(k for k in ph if k >= 1)] == "C" for ph in p["etapes"].values() if any(k >= 1 for k in ph))


# ====================== الوثيقة ======================

def generer(conn: sqlite3.Connection, dossier: DossierDonnees, eleve_ids: list[int], annee: str | None = None,
            graphiques=None) -> Path:
    """بطاقة لكل تلميذ (صفحة لكل واحد). graphiques(parcours) ← (صورة مبيان TaRL، صورة مبيان المراحل) أو None."""
    from docx.shared import Cm

    from idara.services.docs_association import _nouveau, para, saut_page
    from idara.services.soutien import _entete, _signature, _table
    if not eleve_ids:
        raise ErreurFiche("اختر تلميذاً واحداً على الأقل.")
    d = _nouveau()
    s = d.sections[0]
    s.top_margin = s.bottom_margin = Cm(1.2)
    s.left_margin = s.right_margin = Cm(1.5)
    vides = 0
    for k, eid in enumerate(eleve_ids):
        p = parcours(conn, eid, annee)
        if not p["tarl"] and not p["etapes"]:
            vides += 1
        if k:
            saut_page(d)
        e = p["eleve"]
        _entete(d, conn, dossier, "بطاقة التلميذ(ة): تتبع المسار والتعلمات", f"السنة الدراسية {p['annee']}")
        _table(d, ["الاسم الكامل", "رقم مسار", "تاريخ الازدياد", "القسم"],
               [[e["nom"], _ltr(e["code_massar"]) if e["code_massar"] else "",
                 _ltr(tx.date_chiffres(e["date_naissance"])) if e["date_naissance"] else "",
                 _ltr(e["classe"]) if e["classe"] else ""]], [6.4, 3.8, 3.4, 4.4], taille=11)
        imgs = graphiques(p) if graphiques else (None, None)
        para(d, "", apres=4)
        para(d, "1. رائزا الموضعة (TaRL): المستوى على سلم كل مادة", gras=True, taille=12, apres=2)
        if p["tarl"]:
            lignes = []
            for m, t in p["tarl"].items():
                d_ = (None if t["rang_pre"] is None or t["rang_post"] is None else t["rang_post"] - t["rang_pre"])
                r = t["rang_post"] if t["post"] else t["rang_pre"]
                statut = ("" if r is None or t["rang_attendu"] is None else
                          "بلغ المتوقع" if r >= t["rang_attendu"] else "دون المتوقع")
                lignes.append([MATIERES[m], t["pre"] or "", t["post"] or "", t["attendu"] or "",
                               "" if d_ is None else (f"+{d_}" if d_ > 0 else str(d_)), statut])
            _table(d, ["المادة", "الرائز القبلي", "الرائز البعدي", "المستوى المتوقع", "التطور (درجات)", "الوضعية"],
                   lignes, [3.2, 3.0, 3.0, 3.0, 2.6, 3.2], taille=11)
            if imgs and imgs[0]:
                d.add_picture(io.BytesIO(imgs[0]), width=Cm(16.5))
                d.paragraphs[-1].alignment = 1
        else:
            para(d, "لم تُستورد مستويات التعلم لهذا التلميذ بعد.", taille=11, apres=2)
        para(d, "2. مستوى التحكم حسب الروائز والمراحل (A تام، B مقنع، C ضعيف)", gras=True, taille=12, apres=2)
        phases = sorted({ph for v in p["etapes"].values() for ph in v})
        if phases:
            _table(d, ["المادة", *[libelle_phase(ph) for ph in phases]],
                   [[MATIERES[m], *[p["etapes"].get(m, {}).get(ph, "") for ph in phases]] for m in MATIERES
                    if m in p["etapes"]], [3.2] + [round(14.8 / len(phases), 2)] * len(phases), taille=11)
            if imgs and imgs[1]:
                d.add_picture(io.BytesIO(imgs[1]), width=Cm(16.5))
                d.paragraphs[-1].alignment = 1
        else:
            para(d, "لا نتائج مراحل مسجلة لهذا التلميذ بعد.", taille=11, apres=2)
        obs = observations(p)
        if obs:
            para(d, "3. ملاحظات", gras=True, taille=12, apres=2)
            for o in obs:
                para(d, "- " + o, taille=11, apres=0)
            if a_besoin_soutien(p):
                para(d, "يُقترح إدراجه(ا) في مجموعات الدعم.", gras=True, taille=11, apres=0)
        dos = dossier_complet(conn, eid)
        if any(dos[k] for k, *_ in SECTIONS_DOSSIER):
            para(d, "4. الملف الشامل", gras=True, taille=12, apres=2)
            for cle, titre, entetes, champs in SECTIONS_DOSSIER:
                if not dos[cle]:
                    continue
                para(d, titre, gras=True, taille=11, apres=1)
                _table(d, list(entetes), [[_ltr(valeur_dossier(c, x[c])) if c in ("annee", "moyenne", "date")
                                           and x[c] not in ("", None) else valeur_dossier(c, x[c]) for c in champs]
                                          for x in dos[cle]],
                       [round(18.0 / len(entetes), 2)] * len(entetes), taille=10)
            if not p["tarl"] and not p["etapes"] and any(dos[k] for k, *_ in SECTIONS_DOSSIER if k != "parcours"):
                vides -= 1
        _signature(d, conn)
    if vides == len(eleve_ids):
        raise ErreurFiche("لا معطيات تقويم لهذا التلميذ: استورد مستويات التعلم أو نتائج الروائز، أو أدخل المستويات "
                          "في البطاقة.")
    rep = dossier.archives / "بطاقات التلاميذ"
    rep.mkdir(parents=True, exist_ok=True)
    nom = (parcours(conn, eleve_ids[0], annee)["eleve"]["nom"].replace(" ", "_") if len(eleve_ids) == 1
           else f"{len(eleve_ids)}_تلميذاً")
    chemin = rep / f"{datetime.now():%Y%m%d_%H%M%S}_بطاقة_{nom}.docx"
    d.save(chemin)
    return chemin
