"""تدبير تسجيلات التلاميذ (طلب المدير 2026-11-07): لائحة التلاميذ حسب المستوى، وأمام كل تلميذ خانات واجبات
التسجيل (التأمين المدرسي، الجمعية الرياضية، جمعية تنمية التعاون المدرسي)، مع عدّاد تراكمي لكل عنصر.

المبالغ (كما حددها المدير): التأمين 8 دراهم في الوسط القروي و12 درهماً في الوسط الحضري (وسط المؤسسة يُحدَّد في
الإعدادات)، الجمعية الرياضية 10 دراهم، جمعية تنمية التعاون المدرسي 10 دراهم.

طلب المدير 2026-11-19: المدير يكتب المبالغ بنفسه في «تهيئة المبالغ» (نافذة منبثقة)، وتُعتمد بدل ما سبق. ولا يظهر
تلاميذ التعليم الأولي في اللائحة لأنهم يُؤمَّنون من خلال جمعيتهم. واللائحة تُعرض حسب القسم.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from idara.services import annee as annee_srv
from idara.services import etablissement as etab_srv

ELEMENTS = {"assurance": "التأمين المدرسي", "sport": "الجمعية الرياضية", "cooperative": "جمعية تنمية التعاون المدرسي"}
ASSURANCE = {"rural": 8, "urbain": 12}
MONTANTS_FIXES = {"sport": 10, "cooperative": 10}


class ErreurFrais(ValueError):
    """رسالة موجهة للمدير بالعربية."""


def montants_saisis(conn: sqlite3.Connection) -> dict[str, float]:
    """المبالغ التي كتبها المدير في «تهيئة المبالغ»."""
    from idara.services import fiches
    return {k: v for k, v in (fiches.lire(conn, "frais_montants") or {}).items() if k in ELEMENTS and v is not None}


def _nombre(v):
    return int(v) if float(v).is_integer() else round(float(v), 2)


def montants(conn: sqlite3.Connection) -> dict[str, int | float | None]:
    """مبلغ كل عنصر: ما كتبه المدير، وإلا القيم السابقة (التأمين حسب الوسط، None إن لم يُحدَّد)."""
    e = etab_srv.lire_etablissement(conn)
    res = {"assurance": ASSURANCE.get(e.milieu if e else ""), **MONTANTS_FIXES}
    res.update({k: _nombre(v) for k, v in montants_saisis(conn).items()})
    return res


def definir_montants(conn: sqlite3.Connection, valeurs: dict[str, object]) -> dict:
    from idara.services import fiches
    propres = {}
    for k, v in valeurs.items():
        if k not in ELEMENTS:
            raise ErreurFrais("عنصر تسجيل غير معروف.")
        t = str(v if v is not None else "").replace(",", ".").strip()
        if not t:
            raise ErreurFrais(f"اكتب مبلغ «{ELEMENTS[k]}».")
        try:
            x = float(t)
        except ValueError:
            raise ErreurFrais(f"مبلغ «{ELEMENTS[k]}» رقم بالدرهم.") from None
        if x < 0:
            raise ErreurFrais(f"مبلغ «{ELEMENTS[k]}» لا يكون سالباً.")
        propres[k] = x
    fiches.ecrire(conn, "frais_montants", {**montants_saisis(conn), **propres})
    return montants(conn)


def _prescolaire(x) -> bool:
    from idara.services.massar import niveaux_du_code_classe
    if x["niveau"]:
        return x["niveau"].startswith("PS")
    ns = niveaux_du_code_classe(x["classe"] or "")
    return bool(ns) and all(n.startswith("PS") for n in ns) or (x["classe"] or "").upper().startswith(("PS", "MS", "GS"))


def classes(conn: sqlite3.Connection, unite: str | None = None) -> list[str]:
    """أقسام اللائحة (دون أقسام التعليم الأولي)."""
    return list(dict.fromkeys(x["classe"] for x in lister(conn, unite=unite)))


def _annee(conn) -> int:
    a = annee_srv.annee_courante(conn)
    if a is None:
        raise ErreurFrais("لا سنة دراسية جارية.")
    return a["id"]


def lister(conn: sqlite3.Connection, niveau: str | None = None, unite: str | None = None,
           classe: str | None = None) -> list[dict]:
    """التلاميذ الذين يتابعون دراستهم (دون التعليم الأولي)، مرتبين حسب المستوى ثم القسم ثم الاسم، مع ما أدّوه."""
    aid = _annee(conn)
    sql = ("SELECT e.id, e.code_massar, e.nom_ar, e.prenom_ar, c.code AS classe, n.code AS niveau, "
           "COALESCE(f.assurance,0) AS assurance, COALESCE(f.sport,0) AS sport, "
           "COALESCE(f.cooperative,0) AS cooperative FROM inscription i JOIN eleve e ON e.id=i.eleve_id "
           "JOIN classe c ON c.id=i.classe_id LEFT JOIN niveau n ON n.id=i.niveau_id "
           "LEFT JOIN frais_inscription f ON f.eleve_id=e.id AND f.annee_id=i.annee_id "
           "WHERE i.annee_id=? AND i.statut IN ('inscrit','arrive')")
    args: list = [aid]
    if niveau:
        sql += " AND n.code=?"
        args.append(niveau)
    if unite:
        sql += " AND c.unite_id=(SELECT id FROM unite_scolaire WHERE nom_ar=?)"
        args.append(unite)
    if classe:
        sql += " AND c.code=?"
        args.append(classe)
    sql += " ORDER BY c.code, n.ordre, e.nom_ar, e.prenom_ar"
    return [x for x in (dict(r) for r in conn.execute(sql, args)) if not _prescolaire(x)]


def marquer(conn: sqlite3.Connection, eleve_id: int, element: str, paye: bool) -> None:
    if element not in ELEMENTS:
        raise ErreurFrais("عنصر تسجيل غير معروف.")
    aid = _annee(conn)
    with conn:
        conn.execute("INSERT INTO frais_inscription(annee_id, eleve_id) VALUES (?,?) ON CONFLICT DO NOTHING",
                     (aid, eleve_id))
        conn.execute(f"UPDATE frais_inscription SET {element}=?, maj_le=? WHERE annee_id=? AND eleve_id=?",
                     (1 if paye else 0, datetime.now().isoformat(timespec="seconds"), aid, eleve_id))


def marquer_tous(conn: sqlite3.Connection, eleves: list[int], element: str, paye: bool = True) -> int:
    for e in eleves:
        marquer(conn, e, element, paye)
    return len(eleves)


def totaux(conn: sqlite3.Connection, niveau: str | None = None, unite: str | None = None,
           classe: str | None = None) -> dict:
    """العدد والمبلغ لكل عنصر، والمجموع التراكمي."""
    liste = lister(conn, niveau, unite, classe)
    m = montants(conn)
    res = {"eleves": len(liste), "elements": {}, "total": 0}
    for k, lib in ELEMENTS.items():
        n = sum(1 for x in liste if x[k])
        mt = n * m[k] if m[k] is not None else None
        res["elements"][k] = {"libelle": lib, "payes": n, "montant_unitaire": m[k], "montant": mt}
        res["total"] += mt or 0
    res["total"] = _nombre(res["total"])
    return res


# ---------- وثيقة «مخرجات الواجبات المدرسية» (طلب المدير 2026-11-23) ----------

PORTEES = {"etablissement": "المؤسسة كاملة", "classes": "حسب الأقسام", "classe": "قسم واحد (لائحة التلاميذ)"}


def _dh(v) -> str:
    if v is None:
        return "غير محدد"
    return f"{_nombre(v):,}".replace(",", " ")


def releve(conn: sqlite3.Connection, portee: str = "classes", classe: str | None = None,
           unite: str | None = None) -> dict:
    """معطيات الوثيقة: أسطر (قسم أو مستوى أو تلميذ) مع عدد المؤدين ومبلغ كل عنصر، والمجموع."""
    if portee not in PORTEES:
        raise ErreurFrais("نطاق الوثيقة غير معروف.")
    m = montants(conn)
    if portee == "classe":
        if not classe:
            raise ErreurFrais("اختر القسم.")
        ls = lister(conn, unite=unite, classe=classe)
        if not ls:
            raise ErreurFrais(f"لا تلاميذ في القسم {classe}.")
        lignes = []
        for x in ls:
            mt = sum(m[k] or 0 for k in ELEMENTS if x[k])
            lignes.append({"libelle": f"{x['prenom_ar']} {x['nom_ar']}".strip(), "code": x["code_massar"] or "",
                           "elements": {k: bool(x[k]) for k in ELEMENTS}, "total": _nombre(mt)})
        return {"portee": portee, "classe": classe, "lignes": lignes, "totaux": totaux(conn, unite=unite,
                                                                                         classe=classe), "montants": m}
    if portee == "classes":
        groupes = [(c, totaux(conn, unite=unite, classe=c)) for c in classes(conn, unite)]
    else:
        from idara.services import textes as tx
        niveaux = list(dict.fromkeys(x["niveau"] for x in lister(conn, unite=unite) if x["niveau"]))
        groupes = [(tx.niveau_ar(n) if n in tx.NIVEAUX else n, totaux(conn, niveau=n, unite=unite))
                   for n in niveaux]
    if not groupes:
        raise ErreurFrais("لا تلاميذ مسجلين هذه السنة.")
    return {"portee": portee, "classe": None, "montants": m, "totaux": totaux(conn, unite=unite),
            "lignes": [{"libelle": lib, "eleves": t["eleves"],
                        "elements": {k: (v["payes"], v["montant"]) for k, v in t["elements"].items()},
                        "total": t["total"]} for lib, t in groupes]}


def generer_releve(conn: sqlite3.Connection, dossier, portee: str = "classes", classe: str | None = None,
                   unite: str | None = None) -> Path:
    """وثيقة Word: الواجبات المتحصل عليها حسب الأقسام، أو للمؤسسة كاملة (حسب المستوى)، أو لائحة قسم."""
    from docx.shared import Cm
    from idara.services import documents as dc
    from idara.services import textes as tx
    from idara.services.docs_association import _cellule, _nouveau, _ombre, para, tableau
    r = releve(conn, portee, classe, unite)
    a = annee_srv.annee_courante(conn)
    try:
        c = dc.champs_communs(conn)
    except dc.ErreurDocument as e:
        raise ErreurFrais(str(e)) from None
    m = r["montants"]
    d = _nouveau(paysage=portee != "classe")
    e = etab_srv.lire_etablissement(conn)
    if e and e.logo_path and (dossier.racine / e.logo_path).exists():
        d.add_picture(str(dossier.racine / e.logo_path), width=Cm(17 if portee == "classe" else 24))
    para(d, "مخرجات الواجبات المدرسية", gras=True, taille=20, centre=True, apres=0)
    sous = {"etablissement": "المؤسسة كاملة (حسب المستوى)", "classes": "حسب الأقسام",
            "classe": f"القسم {classe}"}[portee]
    para(d, f"{sous} · الموسم الدراسي {a['libelle']}" + (f" · {unite}" if unite else ""), centre=True, taille=13,
         apres=4)
    para(d, "المبالغ المعتمدة للتلميذ الواحد: " + "، ".join(
        f"{lib} {_dh(m[k])}" + (" درهم" if m[k] is not None else "") for k, lib in ELEMENTS.items()), taille=11,
        apres=6)
    ks = list(ELEMENTS)
    if portee == "classe":
        entetes = ["ر.ت", "الاسم الكامل", "رمز مسار"] + [ELEMENTS[k] for k in ks] + ["المبلغ المؤدى (درهم)"]
        t = tableau(d, 2 + len(r["lignes"]), len(entetes), largeurs=[1.0, 4.8, 2.8, 2.3, 2.3, 2.3, 2.5])
        for j, lib in enumerate(entetes):
            _cellule(t.cell(0, j), lib, gras=True, taille=10)
            _ombre(t.cell(0, j))
        for i, l in enumerate(r["lignes"], start=1):
            vals = [str(i), l["libelle"], l["code"]] + ["✓" if l["elements"][k] else "—" for k in ks] + \
                [_dh(l["total"])]
            for j, v in enumerate(vals):
                _cellule(t.cell(i, j), v, taille=10, centre=j != 1)
        i = len(r["lignes"]) + 1
        tt = r["totaux"]["elements"]
        vals = ["", "المجموع", f"{r['totaux']['eleves']} تلميذاً"] + [f"{tt[k]['payes']} · {_dh(tt[k]['montant'])}"
                                                                     for k in ks] + [_dh(r["totaux"]["total"])]
    else:
        entetes = ["القسم" if portee == "classes" else "المستوى", "عدد التلاميذ"]
        for k in ks:
            entetes += [f"{ELEMENTS[k]}: المؤدون", "المبلغ"]
        entetes += ["المجموع (درهم)"]
        t = tableau(d, 2 + len(r["lignes"]), len(entetes),
                    largeurs=[3.0, 2.0] + [2.4, 2.4] * len(ks) + [3.0])
        for j, lib in enumerate(entetes):
            _cellule(t.cell(0, j), lib, gras=True, taille=9)
            _ombre(t.cell(0, j))
        for i, l in enumerate(r["lignes"], start=1):
            vals = [l["libelle"], str(l["eleves"])]
            for k in ks:
                n, mt = l["elements"][k]
                vals += [str(n), _dh(mt)]
            vals.append(_dh(l["total"]))
            for j, v in enumerate(vals):
                _cellule(t.cell(i, j), v, taille=10)
        i = len(r["lignes"]) + 1
        tt = r["totaux"]
        vals = ["المجموع", str(tt["eleves"])]
        for k in ks:
            vals += [str(tt["elements"][k]["payes"]), _dh(tt["elements"][k]["montant"])]
        vals.append(_dh(tt["total"]))
    for j, v in enumerate(vals):
        _cellule(t.cell(i, j), v, gras=True, taille=10)
        _ombre(t.cell(i, j))
    tt = r["totaux"]
    para(d, apres=6)
    para(d, f"المبلغ الإجمالي المتحصل عليه: {_dh(tt['total'])} درهم، من {tt['eleves']} تلميذاً وتلميذة.", gras=True,
         taille=12, apres=2)
    for k, lib in ELEMENTS.items():
        x = tt["elements"][k]
        reste = tt["eleves"] - x["payes"]
        para(d, f"• {lib}: أدّاه {x['payes']} من {tt['eleves']}" + (f"، والباقي {reste}" if reste else "، الجميع")
             + (f" · {_dh(x['montant'])} درهم" if x["montant"] is not None else ""), taille=11, apres=0)
    para(d, apres=8)
    para(d, f"حرر ب{c['ville']} في: {tx.date_chiffres(datetime.now().date().isoformat())}", taille=12, apres=4)
    para(d, f"توقيع {c['mudir_moassasa']}", gras=True, taille=13)
    rep = dossier.archives / a["libelle"].replace("/", "-") / "التسجيلات"
    rep.mkdir(parents=True, exist_ok=True)
    nom = {"etablissement": "المؤسسة", "classes": "حسب الأقسام", "classe": f"القسم {classe}"}[portee]
    chemin = rep / f"{datetime.now():%Y%m%d_%H%M%S}_مخرجات الواجبات المدرسية - {nom}.docx"
    d.save(chemin)
    return chemin
