"""شاشة العرض (طلب المدير 2026-11-21): شرائح تُعرض على تلفاز أو شاشة المؤسسة أمام الزوار والآباء والمرتفقين
واللجان، تُولَّد مباشرة من معطيات البرنامج دون أي استيراد. أرقام مجمَّعة فقط: لا أسماء تلاميذ ولا نقط فردية
(قانون 09-08 لحماية المعطيات الشخصية)."""

from __future__ import annotations

import sqlite3
from datetime import date

from idara.services import annee as annee_srv
from idara.services import etablissement as etab_srv
from idara.services import fiches

CLE = "ecran_affichage"

# (المفتاح، العنوان، الوصف)
CATALOGUE = (
    ("couverture", "المؤسسة بالأرقام", "اسم المؤسسة والموسم، وعدد التلاميذ (ذكور وإناث) والأقسام والأطر."),
    ("niveaux", "التلاميذ حسب المستوى", "عدد التلاميذ والأقسام في كل مستوى، مع الذكور والإناث."),
    ("mouvements", "حركية التلاميذ", "الوافدون والمغادرون والمنقطعون خلال الموسم."),
    ("resultats", "النتائج التربوية", "نسبة النجاح، أو نسب التحكم في التعلمات الأساس للمدرسة الرائدة."),
    ("tarl", "تطور التعلمات الأساس", "نسبة من بلغوا المستوى المتوقع في الرائز القبلي ثم البعدي لكل مستوى."),
    ("actualites", "المستجدات والمواعيد", "المحطات الجارية والقادمة من برنامج العمل والمقرر الوزاري."),
)
TITRES = {c: t for c, t, _ in CATALOGUE}
DUREE_DEFAUT = 12      # ثوانٍ لكل شريحة
DUREES = (6, 8, 10, 12, 15, 20, 30, 45, 60)


def reglages(conn: sqlite3.Connection) -> dict:
    """الإعدادات المحفوظة: ترتيب الشرائح، المفعّلة منها، مدة كل شريحة، نص الشريط المتحرك."""
    d = fiches.lire(conn, CLE) or {}
    ordre = [c for c in d.get("ordre", []) if c in TITRES]
    ordre += [c for c, *_ in CATALOGUE if c not in ordre]
    actives = d.get("actives")
    actives = [c for c in ordre if c in actives] if isinstance(actives, list) else list(ordre)
    durees = {c: int(d.get("durees", {}).get(c, DUREE_DEFAUT)) for c in ordre}
    return {"ordre": ordre, "actives": actives, "durees": durees, "bandeau": d.get("bandeau", "")}


def enregistrer_reglages(conn: sqlite3.Connection, ordre: list[str], actives: list[str], durees: dict[str, int],
                         bandeau: str = "") -> dict:
    ordre = [c for c in ordre if c in TITRES]
    if not ordre:
        raise ValueError("الشرائح غير معروفة.")
    actives = [c for c in ordre if c in actives]
    if not actives:
        raise ValueError("اختر شريحة واحدة على الأقل للعرض.")
    durees = {c: max(3, min(300, int(durees.get(c, DUREE_DEFAUT)))) for c in ordre}
    fiches.ecrire(conn, CLE, {"ordre": ordre, "actives": actives, "durees": durees,
                              "bandeau": " ".join((bandeau or "").split())})
    return reglages(conn)


def _pct(n: int, d: int) -> float | None:
    return round(100 * n / d, 1) if d else None


def identite(conn: sqlite3.Connection) -> dict:
    e = etab_srv.lire_etablissement(conn)
    a = annee_srv.annee_courante(conn)
    return {"nom": (e.nom_ar if e else "") or "المؤسسة", "annee": a["libelle"] if a else "",
            "pionniere": bool(e and getattr(e, "est_pionniere", False))}


def bandeau_defaut(conn: sqlite3.Connection) -> str:
    i = identite(conn)
    return f"مرحباً بكم في {i['nom']}  ✦  مدرسة الجودة والإنصاف  ✦  الموسم الدراسي {i['annee']}"


def diapositive(conn: sqlite3.Connection, cle: str, le: date | None = None) -> dict:
    """محتوى شريحة واحدة: {cle، titre، vide (لا معطيات)، ...حقولها}."""
    from idara.services import statistiques as st
    from idara.services import tableau_bord as tb
    d: dict = {"cle": cle, "titre": TITRES[cle], "vide": False}
    if cle == "couverture":
        ind = tb.indicateurs(conn)
        d.update(eleves=ind["eleves"], garcons=ind["garcons"], filles=ind["filles"],
                 classes=len(ind["classes"]), personnel=ind["personnel"])
        d["vide"] = not ind["eleves"] and not ind["personnel"]
    elif cle == "niveaux":
        d["niveaux"] = [{"libelle": n["libelle"], "eleves": n["eleves"], "classes": n["classes"],
                         "garcons": n["garcons"], "filles": n["filles"]} for n in st.par_niveau(conn)]
        d["vide"] = not d["niveaux"]
    elif cle == "mouvements":
        from idara.services import mouvements as mv
        try:
            t = mv.statistiques(conn)["totaux"]
        except Exception:  # noqa: BLE001 — لا سنة جارية
            t = {}
        d.update(arrive=t.get("arrive", 0), parti=t.get("parti", 0), interrompu=t.get("interrompu", 0),
                 exclu=t.get("exclu", 0))
        d["vide"] = not any(d[k] for k in ("arrive", "parti", "interrompu", "exclu"))
    elif cle == "resultats":
        ind = tb.indicateurs(conn)
        if ind["maitrise"]:
            d["mode"] = "maitrise"
            d["matieres"] = [{"libelle": v["matiere"], "taux": v["taux"], "epreuve": v["epreuve"]}
                             for v in ind["maitrise"].values() if v["total"]]
            d["vide"] = not d["matieres"]
        else:
            r = ind["reussite"] or {}
            d.update(mode="reussite", taux=r.get("taux"), admis=r.get("admis", 0), total=r.get("total", 0),
                     source=r.get("source", ""))
            d["vide"] = not r.get("total")
        d["activites"] = ind["activites"]["taux"]
    elif cle == "tarl":
        d["niveaux"] = [{"libelle": n["libelle"], "pre": n["pre"], "post": n["post"]}
                        for n in st.evolution_tarl(conn) if n["pre"] is not None or n["post"] is not None]
        d["vide"] = not d["niveaux"]
    elif cle == "actualites":
        from idara.services import calendrier as cal
        le = le or date.today()
        try:
            r = cal.rappels(conn, le)
            items = r["en_cours"] + r["a_venir"]
        except Exception:  # noqa: BLE001
            items = []
        d["items"] = [{"titre": s.titre, "debut": s.debut.isoformat(), "fin": s.fin.isoformat(),
                       "en_cours": s.debut <= le <= s.fin} for s in sorted(items, key=lambda s: s.debut)][:6]
        d["vide"] = not d["items"]
    return d


def diaporama(conn: sqlite3.Connection, le: date | None = None, avec_vides: bool = False) -> list[dict]:
    """الشرائح المفعّلة بترتيبها مع مدة كل واحدة. الشريحة التي لا معطيات لها تُسقط (إلا الغلاف)."""
    r = reglages(conn)
    res = []
    for c in r["actives"]:
        d = diapositive(conn, c, le)
        if d["vide"] and c != "couverture" and not avec_vides:
            continue
        d["duree"] = r["durees"][c]
        res.append(d)
    return res
