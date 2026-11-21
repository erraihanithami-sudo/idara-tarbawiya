"""شاشة العرض (طلب المدير 2026-11-21): شرائح تُعرض على تلفاز أو شاشة المؤسسة أمام الزوار والآباء والمرتفقين
واللجان، تُولَّد مباشرة من معطيات البرنامج دون أي استيراد. أرقام مجمَّعة فقط: لا أسماء تلاميذ ولا نقط فردية
(قانون 09-08 لحماية المعطيات الشخصية).

لكل شريحة «نقاط» (بطاقة رقم، مستوى، مادة، عملية، منجز، شراكة…) يختار المدير منها ما يُعرض ويزيل العلامة عما لا
يريد عرضه (2026-11-21، الدفعة الثانية)."""

from __future__ import annotations

import sqlite3
from datetime import date

from idara.services import annee as annee_srv
from idara.services import etablissement as etab_srv
from idara.services import fiches

CLE = "ecran_affichage"
CLE_REALISATIONS = "ecran_realisations"

# (المفتاح، العنوان، الوصف)
CATALOGUE = (
    ("couverture", "المؤسسة بالأرقام", "اسم المؤسسة وشعارها والموسم، وعدد التلاميذ (ذكور وإناث) والأقسام والأطر."),
    ("niveaux", "التلاميذ حسب المستوى", "الذكور والإناث في كل مستوى."),
    ("maitrise", "مستوى التحكم في التعلمات الأساس", "نسبة المتحكمين في كل مادة (آخر رائز متوفر)."),
    ("tarl", "تطور التعلمات الأساس", "نسبة من بلغوا المستوى المتوقع في الرائز القبلي ثم البعدي لكل مستوى."),
    ("resultats", "النتائج التربوية", "نسبة النجاح، والمستفيدون من الأنشطة."),
    ("projet", "منجزات مشروع المؤسسة", "نسبة الإنجاز، والعمليات المنجزة من مشروع المؤسسة المندمج."),
    ("realisations", "أهم منجزات المؤسسة", "المنجزات في محاور التلميذ والمدرسة والأستاذ (يكتبها المدير)."),
    ("partenariats", "منجزات الشراكة", "الشراكات وموضوعاتها من سجل «الانفتاح والشراكة»."),
    ("mouvements", "حركية التلاميذ", "الوافدون والمغادرون والمنقطعون خلال الموسم."),
)
TITRES = {c: t for c, t, _ in CATALOGUE}
DUREE_DEFAUT = 12      # ثوانٍ لكل شريحة
DUREES = (6, 8, 10, 12, 15, 20, 30, 45, 60)
AXES = (("eleve", "محور التلميذ"), ("ecole", "محور المدرسة"), ("professeur", "محور الأستاذ"))
LIB_AXES = dict(AXES)


class ErreurEcran(ValueError):
    pass


def reglages(conn: sqlite3.Connection) -> dict:
    """الإعدادات: الترتيب، الشرائح المفعّلة، المدة، الشريط المتحرك، الشعار، والنقاط المخفية لكل شريحة."""
    d = fiches.lire(conn, CLE) or {}
    ordre = [c for c in d.get("ordre", []) if c in TITRES]
    ordre += [c for c, *_ in CATALOGUE if c not in ordre]
    actives = d.get("actives")
    actives = [c for c in ordre if c in actives] if isinstance(actives, list) else list(ordre)
    durees = {c: int(d.get("durees", {}).get(c, DUREE_DEFAUT)) for c in ordre}
    masques = {c: list(v) for c, v in (d.get("masques") or {}).items() if c in TITRES}
    return {"ordre": ordre, "actives": actives, "durees": durees, "bandeau": d.get("bandeau", ""),
            "logo": d.get("logo", ""), "masques": masques}


def _ecrire(conn, r: dict) -> dict:
    fiches.ecrire(conn, CLE, {k: r[k] for k in ("ordre", "actives", "durees", "bandeau", "logo", "masques")})
    return reglages(conn)


def enregistrer_reglages(conn: sqlite3.Connection, ordre: list[str], actives: list[str], durees: dict[str, int],
                         bandeau: str = "") -> dict:
    ordre = [c for c in ordre if c in TITRES]
    if not ordre:
        raise ErreurEcran("الشرائح غير معروفة.")
    ordre += [c for c, *_ in CATALOGUE if c not in ordre]
    actives = [c for c in ordre if c in actives]
    if not actives:
        raise ErreurEcran("اختر شريحة واحدة على الأقل للعرض.")
    r = reglages(conn)
    r.update(ordre=ordre, actives=actives, bandeau=" ".join((bandeau or "").split()),
             durees={c: max(3, min(300, int(durees.get(c, r["durees"].get(c, DUREE_DEFAUT))))) for c in ordre})
    return _ecrire(conn, r)


def definir_masques(conn: sqlite3.Connection, cle: str, caches: list[str]) -> dict:
    """النقاط التي أزال المدير علامتها في شريحة (لا تُعرض)."""
    if cle not in TITRES:
        raise ErreurEcran("شريحة غير معروفة.")
    r = reglages(conn)
    r["masques"][cle] = [str(x) for x in caches]
    return _ecrire(conn, r)


def definir_logo(conn: sqlite3.Connection, dossier, source) -> str:
    """ينسخ شعار المؤسسة (PNG/JPG) إلى مجلد البيانات ويحفظه للعرض. source=None يزيله."""
    r = reglages(conn)
    if source is None:
        r["logo"] = ""
    else:
        try:
            r["logo"] = etab_srv.importer_image(dossier, source, "logo_ecran")
        except Exception as e:  # noqa: BLE001 — ErreurValidation
            raise ErreurEcran(str(e)) from e
    _ecrire(conn, r)
    return r["logo"]


def chemin_logo(conn: sqlite3.Connection, dossier) -> str:
    rel = reglages(conn)["logo"]
    if not rel or dossier is None:
        return ""
    p = dossier.racine / rel
    return str(p) if p.exists() else ""


# ---------- المنجزات حسب المحاور (يكتبها المدير) ----------

def realisations(conn: sqlite3.Connection) -> list[dict]:
    return list((fiches.lire(conn, CLE_REALISATIONS) or {}).get("lignes", []))


def ajouter_realisation(conn: sqlite3.Connection, axe: str, texte: str) -> dict:
    if axe not in LIB_AXES:
        raise ErreurEcran("اختر المحور: التلميذ أو المدرسة أو الأستاذ.")
    texte = " ".join((texte or "").split())
    if not texte:
        raise ErreurEcran("اكتب المنجز.")
    if len(texte) > 140:
        raise ErreurEcran("المنجز طويل: جملة قصيرة تُقرأ من بعيد (140 حرفاً على الأكثر).")
    ls = realisations(conn)
    nid = max([int(l["id"]) for l in ls] + [0]) + 1
    l = {"id": nid, "axe": axe, "texte": texte}
    fiches.ecrire(conn, CLE_REALISATIONS, {"lignes": ls + [l]})
    return l


def supprimer_realisation(conn: sqlite3.Connection, rid: int) -> None:
    fiches.ecrire(conn, CLE_REALISATIONS, {"lignes": [l for l in realisations(conn) if int(l["id"]) != int(rid)]})


# ---------- محتوى الشرائح ----------

def _pct(n: int, d: int) -> float | None:
    return round(100 * n / d, 1) if d else None


def identite(conn: sqlite3.Connection, dossier=None) -> dict:
    e = etab_srv.lire_etablissement(conn)
    a = annee_srv.annee_courante(conn)
    return {"nom": (e.nom_ar if e else "") or "المؤسسة", "annee": a["libelle"] if a else "",
            "pionniere": bool(e and getattr(e, "est_pionniere", False)), "logo": chemin_logo(conn, dossier)}


def bandeau_defaut(conn: sqlite3.Connection) -> str:
    i = identite(conn)
    return f"مرحباً بكم في {i['nom']}   ·   مدرسة الجودة والإنصاف   ·   الموسم الدراسي {i['annee']}"


def _items(conn: sqlite3.Connection, cle: str) -> tuple[list[dict], dict]:
    """(النقاط، معطيات إضافية للشريحة). لكل نقطة id ثابت و libelle (يظهر في نافذة الاختيار)."""
    from idara.services import statistiques as st
    from idara.services import tableau_bord as tb
    if cle == "couverture":
        ind = tb.indicateurs(conn)
        return [{"id": "eleves", "libelle": "تلميذة وتلميذاً", "valeur": ind["eleves"], "sous": "مجموع المتمدرسين",
                 "couleur": "or"},
                {"id": "garcons", "libelle": "ذكور", "valeur": ind["garcons"], "couleur": "bleu"},
                {"id": "filles", "libelle": "إناث", "valeur": ind["filles"], "couleur": "rose"},
                {"id": "classes", "libelle": "قسماً", "valeur": len(ind["classes"]), "couleur": "violet"},
                {"id": "personnel", "libelle": "إطاراً", "valeur": ind["personnel"], "sous": "تربوياً وإدارياً",
                 "couleur": "vert"}], {"vide": not ind["eleves"] and not ind["personnel"]}
    if cle == "niveaux":
        return [{"id": n["niveau"], "libelle": n["libelle"], "valeurs": [n["garcons"], n["filles"]]}
                for n in st.par_niveau(conn)], {}
    if cle == "maitrise":
        a = annee_srv.annee_courante(conn)
        m = tb._maitrise(conn, a["libelle"], None) if a else {}
        return [{"id": k, "libelle": v["matiere"], "taux": v["taux"], "sous": v["epreuve"]}
                for k, v in m.items() if v["total"]], {}
    if cle == "tarl":
        return [{"id": n["niveau"], "libelle": n["libelle"], "valeurs": [n["pre"], n["post"]]}
                for n in st.evolution_tarl(conn) if n["pre"] is not None or n["post"] is not None], {}
    if cle == "resultats":
        ind = tb.indicateurs(conn)
        r = tb._reussite(conn, annee_srv.annee_courante(conn)["id"], None) if annee_srv.annee_courante(conn) else {}
        items = []
        if r.get("total"):
            items.append({"id": "reussite", "libelle": "نسبة النجاح", "taux": r["taux"], "sous": r["source"]})
        if ind["eleves"]:
            items.append({"id": "activites", "libelle": "المستفيدون من الأنشطة", "taux": ind["activites"]["taux"],
                          "sous": "الأندية والأنشطة"})
        h = ind["hadar"]
        if h["concernes"] and h["taux"] is not None:
            items.append({"id": "hadar", "libelle": "نسبة الهدر المدرسي", "taux": h["taux"],
                          "sous": "المنقطعون والمفصولون"})
        return items, {}
    if cle == "projet":
        from idara.services import projet_etab as pe
        p = pe.projet_actif(conn)
        if p is None:
            return [], {}
        s = pe.synthese_operations(conn, p["id"])
        ops = [o for o in pe.operations(conn, p["id"]) if o["statut"] == "realisee"]
        return ([{"id": str(o["id"]), "libelle": o["intitule"], "axe": o["axe"] or ""} for o in ops],
                {"intitule": p["intitule"], "pct_realisees": s["pct_realisees"], "taux_global": s["taux_global"],
                 "actives": s["actives"], "realisees": s["par_statut"]["realisee"]})
    if cle == "realisations":
        return [{"id": str(l["id"]), "libelle": l["texte"], "axe": l["axe"]} for l in realisations(conn)], {}
    if cle == "partenariats":
        from idara.services import registres as rg
        ls = [l for l in rg.lister(conn, "partenariats") if l.get("etat") != "قيد الإعداد"]
        return [{"id": str(l["id"]), "libelle": l["partenaire"], "objet": l["objet"], "etat": l.get("etat", "")}
                for l in ls], {}
    if cle == "mouvements":
        from idara.services import mouvements as mv
        try:
            t = mv.statistiques(conn)["totaux"]
        except Exception:  # noqa: BLE001 — لا سنة جارية
            t = {}
        items = [{"id": "arrive", "libelle": "وافدون", "valeur": t.get("arrive", 0), "sous": "التحقوا بمؤسستنا",
                  "couleur": "vert"},
                 {"id": "parti", "libelle": "مغادرون", "valeur": t.get("parti", 0),
                  "sous": "انتقلوا إلى مؤسسات أخرى", "couleur": "orange"},
                 {"id": "interrompu", "libelle": "منقطعون", "valeur": t.get("interrompu", 0),
                  "sous": "نتابعهم لإرجاعهم", "couleur": "rouge"},
                 {"id": "exclu", "libelle": "مفصولون", "valeur": t.get("exclu", 0), "couleur": "violet"}]
        return items, {"vide": not any(i["valeur"] for i in items)}
    raise ErreurEcran("شريحة غير معروفة.")


def points(conn: sqlite3.Connection, cle: str) -> list[dict]:
    """كل نقاط الشريحة مع حالة العرض (للنافذة التي يختار منها المدير)."""
    caches = set(reglages(conn)["masques"].get(cle, []))
    return [{"id": i["id"], "libelle": i["libelle"] + (f" ({LIB_AXES.get(i.get('axe'), i.get('axe'))})"
                                                       if i.get("axe") else ""),
             "affiche": i["id"] not in caches} for i in _items(conn, cle)[0]]


def diapositive(conn: sqlite3.Connection, cle: str, le: date | None = None, masques: dict | None = None) -> dict:
    """محتوى شريحة واحدة بعد إخفاء النقاط التي أزال المدير علامتها: {cle، titre، vide، items، ...}."""
    if masques is None:
        masques = reglages(conn)["masques"]
    items, extra = _items(conn, cle)
    caches = set(masques.get(cle, []))
    items = [i for i in items if i["id"] not in caches]
    d = {"cle": cle, "titre": TITRES[cle], "items": items}
    d.update(extra)
    d["vide"] = extra.get("vide", False) or not items
    return d


def diaporama(conn: sqlite3.Connection, le: date | None = None, avec_vides: bool = False) -> list[dict]:
    """الشرائح المفعّلة بترتيبها مع مدة كل واحدة. الشريحة التي لا نقاط لها تُسقط (إلا الغلاف)."""
    r = reglages(conn)
    res = []
    for c in r["actives"]:
        d = diapositive(conn, c, le, r["masques"])
        if d["vide"] and c != "couverture" and not avec_vides:
            continue
        d["duree"] = r["durees"][c]
        res.append(d)
    return res
