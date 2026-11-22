"""الشواهد التقديرية المزخرفة (طلب المدير 2026-11-22): مكوّن «التحفيز والتشجيع».

التصاميم مأخوذة من نماذج المدير (PowerPoint) بعد تجريدها من كل المعطيات الخاصة (أسماء المؤسسات والأشخاص
ورؤوس المراسلات وشعارات المؤسسات): لم تبق إلا الزخرفة، مسطّحةً في صورة خلفية لكل نموذج (resources/chawahid).
النصوص تُرسم فوقها من معطيات البرنامج: رأس رسمي (شعار الوزارة + الأكاديمية والمديرية والمؤسسة)، والعنوان،
واسم التلميذ(ة) من اللائحة، والسبب، والتاريخ، والتوقيع. الرسم (المعاينة وPDF) في ui/chawahid_rendu.py،
وهذه الوحدة تجمع المعطيات وتسجل التحفيز في سجل «التحفيز والتشجيع» وتصدر PowerPoint قابلاً للتعديل.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from idara.services import annee as annee_srv
from idara.services import etablissement as etab_srv
from idara.services import textes as tx

DOSSIER = Path(__file__).resolve().parent.parent / "resources" / "chawahid"
MINISTERE = Path(__file__).resolve().parent.parent / "resources" / "ministere.png"


class ErreurChahada(ValueError):
    """رسالة موجهة للمدير بالعربية."""


Zone = tuple[float, float, float, float]   # x، y، العرض، الارتفاع بالنسبة المئوية من الخلفية


@dataclass(frozen=True)
class Modele:
    cle: str
    nom: str
    description: str
    ratio: float                      # العرض/الارتفاع
    zones: dict                       # entete, titre?, corps, date, signature, logo?, medaille?
    nom_couleur: str = "#9A6A0F"
    texte_couleur: str = "#1B2A4A"
    titre_couleur: str = "#1B2A4A"
    titre_fixe: str = ""              # عنوان مخطوط ضمن الزخرفة (لا يُكتب فوقه عنوان)
    pour: tuple = field(default=("eleve",))

    @property
    def fond(self) -> Path:
        return DOSSIER / f"{self.cle}.jpg"


MODELES: tuple[Modele, ...] = (
    Modele("almasi", "الماسي بالوسام", "إطار داكن بحواف ذهبية ووسام يحمل شعار المؤسسة، وعنوان «شهادة شكر وتقدير».",
           2167 / 1500, {"entete": (60, 6, 34, 22), "logo": (24, 11, 12.5, 18), "corps": (9, 35, 82, 45),
                         "date": (9, 80, 82, 5), "signature": (9, 85, 82, 8)},
           nom_couleur="#B07A16", titre_fixe="شهادة شكر وتقدير"),
    Modele("banafsaji", "البنفسجي بالوسام", "شريط بنفسجي وذهبي ووسام بشريطين، وعنوان «شهادة تفوق».",
           2167 / 1500, {"entete": (2, 3, 30, 20), "corps": (10, 38, 74, 31), "date": (10, 70, 74, 6),
                         "signature": (60, 84, 37, 11)},
           nom_couleur="#6A1B9A", titre_fixe="شهادة تفوق"),
    Modele("dhahabi_taqdir", "الذهبي المزخرف: شهادة تقدير",
           "إطار بزخارف ذهبية على أرضية زليج خفيفة، وعنوان مخطوط «شهادة تقدير».",
           2167 / 1500, {"entete": (18, 4.5, 64, 15), "corps": (10, 36, 80, 41), "date": (10, 77, 80, 5),
                         "signature": (14, 82, 72, 9)},
           nom_couleur="#A0522D", titre_fixe="شهادة تقدير"),
    Modele("dhahabi_chukr", "الذهبي المزخرف: شكر وتقدير",
           "الإطار الذهبي نفسه بعنوان مخطوط «شهادة شكر وتقدير» (للتلاميذ وللأطر والشركاء).",
           2167 / 1500, {"entete": (18, 4.5, 64, 12), "corps": (10, 36, 80, 41), "date": (10, 77, 80, 5),
                         "signature": (14, 82, 72, 9)},
           nom_couleur="#A0522D", titre_fixe="شهادة شكر وتقدير", pour=("eleve", "adulte")),
    Modele("satair", "الستائر الذهبية", "ستائر ذهبية ووسام يحمل تاريخ التتويج، وعنوان «شهادة شكر وتقدير».",
           2000 / 1500, {"entete": (17, 9, 62, 20), "medaille": (82.5, 9.5, 14.5, 18), "corps": (9, 45, 78, 35),
                         "date": (9, 80, 78, 5), "signature": (9, 85, 78, 8)},
           nom_couleur="#8C6A00", titre_fixe="شهادة شكر وتقدير", pour=("eleve", "adulte")),
    Modele("rasmi", "الرسمي بالأحمر والأخضر", "ألوان العلم الوطني ووسام بشعار المملكة، والعنوان حسب نوع التحفيز.",
           2000 / 1500, {"entete": (24, 3, 46, 17), "titre": (24, 20, 52, 12), "corps": (22, 33, 68, 42),
                         "date": (28, 76, 66, 5), "signature": (34, 81, 60, 10)},
           nom_couleur="#C1272D", titre_couleur="#1E6B2F", pour=("eleve", "adulte")),
    Modele("nuhasi", "الإطار النحاسي", "إطار نحاسي بزخارف أندلسية على أرضية بيضاء، والعنوان حسب نوع التحفيز.",
           2000 / 1500, {"entete": (12, 12, 76, 13), "titre": (12, 25, 76, 11), "corps": (12, 37, 76, 37),
                         "date": (12, 74, 76, 5), "signature": (12, 79, 76, 8)},
           nom_couleur="#8B4513", titre_couleur="#8B4513", pour=("eleve", "adulte")),
)
PAR_CLE = {m.cle: m for m in MODELES}

TYPES = ("شهادة تقديرية", "شهادة تفوق", "تهنئة", "تشجيع", "لوحة الشرف")
TITRES = {"شهادة تقديرية": "شهادة تقديرية", "شهادة تفوق": "شهادة تفوق", "تهنئة": "شهادة تهنئة",
          "تشجيع": "شهادة تشجيع", "لوحة الشرف": "شهادة استحقاق"}
NATURES = {"شهادة تقديرية": "الشهادة التقديرية", "شهادة تفوق": "شهادة التفوق", "تهنئة": "شهادة التهنئة",
           "تشجيع": "شهادة التشجيع", "لوحة الشرف": "شهادة الاستحقاق"}
PERIODES = ("الأسدوس الأول", "الأسدوس الثاني", "نهاية السنة")
# أسباب مقترحة: {ه} ← ه/ها، {له} ← له/لها، {الفترة} ← الفترة والموسم
MOTIFS = (
    "تقديراً لتفوق{ه} الدراسي ونتائج{ه} المتميزة خلال {الفترة}.",
    "تقديراً لحصول{ه} على الرتبة الأولى في قسم{ه} خلال {الفترة}.",
    "تقديراً لحصول{ه} على الرتبة الثانية في قسم{ه} خلال {الفترة}.",
    "تقديراً لحصول{ه} على الرتبة الثالثة في قسم{ه} خلال {الفترة}.",
    "تقديراً لانضباط{ه} وحسن سلوك{ه} ومواظبت{ه} على الحضور.",
    "تشجيعاً ل{ه} على التحسن الملحوظ في نتائج{ه} خلال {الفترة}.",
    "تقديراً لمشاركت{ه} المتميزة في أنشطة المؤسسة.",
    "تهنئةً ل{ه} على تتويج{ه} في المسابقة.",
)
VOEU = "متمنين {له} مزيداً من التألق والنجاح."


def accorder(texte: str, feminin: bool) -> str:
    """صيغ التذكير والتأنيث: {ه} {له} {ة} و«(ة)»."""
    t = texte or ""
    for a, m, f in (("{ه}", "ه", "ها"), ("{له}", "له", "لها"), ("{ة}", "", "ة"), ("(ة)", "", "ة")):
        t = t.replace(a, f if feminin else m)
    return t


def entete(conn: sqlite3.Connection) -> list[str]:
    """أسطر الرأس تحت شعار الوزارة: الأكاديمية، المديرية الإقليمية، المؤسسة."""
    from idara.services.mouvements import formule_academie, formule_direction
    e = etab_srv.lire_etablissement(conn)
    if e is None:
        return []
    return [x for x in (formule_academie(e.academie_ar), formule_direction(e.direction_ar), e.nom_ar) if x]


def logo_etablissement(conn: sqlite3.Connection, dossier) -> str:
    """شعار المؤسسة إن وُجد (شعار شاشة العرض أولاً، ثم شعار الإعداد)."""
    try:
        from idara.services import ecran as ec
        p = ec.chemin_logo(conn, dossier)
        if p:
            return p
    except Exception:  # noqa: BLE001
        pass
    e = etab_srv.lire_etablissement(conn)
    if e and e.logo_path and dossier is not None:
        p = Path(dossier.racine) / e.logo_path
        if p.exists():
            return str(p)
    return ""


def eleves(conn: sqlite3.Connection, classe: str | None = None) -> list[dict]:
    """تلاميذ السنة الجارية: {id، nom، classe، sexe}، مرتبين حسب القسم ثم الاسم."""
    a = annee_srv.annee_courante(conn)
    if a is None:
        return []
    sql = ("SELECT e.id, e.nom_ar, e.prenom_ar, e.sexe, c.code AS classe FROM inscription i JOIN eleve e "
           "ON e.id=i.eleve_id LEFT JOIN classe c ON c.id=i.classe_id WHERE i.annee_id=? AND "
           "i.statut IN ('inscrit','arrive')")
    args: list = [a["id"]]
    if classe:
        sql += " AND c.code=?"
        args.append(classe)
    rs = conn.execute(sql + " ORDER BY c.code, e.prenom_ar, e.nom_ar", args).fetchall()
    return [{"id": r["id"], "nom": f"{r['prenom_ar']} {r['nom_ar']}".strip(), "classe": r["classe"] or "",
             "sexe": r["sexe"] or "M"} for r in rs]


def classes(conn: sqlite3.Connection) -> list[str]:
    return sorted({e["classe"] for e in eleves(conn) if e["classe"]})


def _periode_complete(conn, periode: str) -> str:
    a = annee_srv.annee_courante(conn)
    an = f"الموسم الدراسي {a['libelle']}" if a else ""
    if not periode:
        return an
    if periode == "نهاية السنة":
        return f"{an}" if an else "السنة الدراسية"
    return f"{periode} من {an}" if an else periode


def contenu(conn: sqlite3.Connection, eleve: dict, type_: str = "شهادة تقديرية", motif: str = "",
            periode: str = "", le: str | None = None, intro: str | None = None, voeu: str | None = None,
            signataires: tuple = ("مدير المؤسسة",), afficher_classe: bool = True) -> dict:
    """كل نصوص الشهادة لتلميذ(ة) واحد(ة). eleve: {nom، classe، sexe}."""
    if type_ not in TYPES:
        raise ErreurChahada("نوع التحفيز غير معروف.")
    nom = " ".join((eleve.get("nom") or "").split())
    if not nom:
        raise ErreurChahada("اختر التلميذ(ة) من اللائحة.")
    fem = (eleve.get("sexe") or "M") == "F"
    e = etab_srv.lire_etablissement(conn)
    etab = e.nom_ar if e else "المؤسسة"
    motif = " ".join((motif or "").split())
    if not motif:
        raise ErreurChahada("اكتب سبب التحفيز أو اختر واحداً من المقترحات.")
    motif = motif.replace("{الفترة}", _periode_complete(conn, periode))
    reste = re.findall(r"\{([^}]*)\}", motif.replace("{ه}", "").replace("{له}", "").replace("{ة}", ""))
    if reste:
        raise ErreurChahada(f"أكمل في السبب: «{reste[0]}».")
    le = le or date.today().isoformat()
    if intro is None:
        intro = f"يتشرف مدير وأطر {etab} بتقديم هذه {NATURES[type_]} إلى التلميذ(ة):"
    ville = e.ville_redaction_ar if e and e.ville_redaction_ar else ""
    y, m, j = le.split("-")
    return {
        "entete": entete(conn),
        "titre": TITRES[type_],
        "intro": accorder(" ".join(intro.split()), fem),
        "nom": nom,
        "classe": f"القسم: {eleve.get('classe')}" if afficher_classe and eleve.get("classe") else "",
        "motif": accorder(motif, fem),
        "voeu": accorder(VOEU if voeu is None else voeu, fem),
        "date": (f"حرر في {ville} بتاريخ {tx.date_chiffres(le)}" if ville else f"حرر بتاريخ {tx.date_chiffres(le)}"),
        "signataires": [s for s in signataires if s],
        "jour": str(int(j)), "mois": tx.MOIS_AR[int(m) - 1], "annee": y,
        "_eleve": eleve, "_type": type_, "_motif": accorder(motif, fem), "_periode": periode, "_date": le,
    }


def enregistrer(conn: sqlite3.Connection, contenus: list[dict], modele: str) -> list[int]:
    """يسجل كل شهادة في سجل «التحفيز والتشجيع» (يظهر أيضاً في الملف الشامل للتلميذ)."""
    from idara.services import registres as rg
    ids = []
    for c in contenus:
        el = c["_eleve"]
        ids.append(rg.enregistrer(conn, "tahfiz", {
            "date": c["_date"], "eleve": el["nom"], "classe": el.get("classe", ""), "type": c["_type"],
            "motif": c["_motif"], "periode": c["_periode"] if c["_periode"] in PERIODES else "",
            "modele": PAR_CLE[modele].nom if modele in PAR_CLE else ""}))
    return ids


def exemple(conn: sqlite3.Connection, type_: str = "شهادة تقديرية") -> dict:
    """محتوى توضيحي لمعرض الشواهد."""
    return contenu(conn, {"nom": "اسم التلميذة أو التلميذ", "classe": "", "sexe": "M"}, type_,
                   "تقديراً لتفوق{ه} الدراسي ونتائج{ه} المتميزة خلال {الفترة}.", "الأسدوس الأول")


def chemin_sortie(dossier, nom: str, ext: str) -> Path:
    from datetime import datetime
    rep = Path(dossier.archives) / "الشواهد التقديرية"
    rep.mkdir(parents=True, exist_ok=True)
    propre = re.sub(r'[\\/:*?"<>|]', "_", nom).replace(" ", "_")
    chemin = rep / f"{datetime.now():%Y%m%d_%H%M%S}_{propre}.{ext}"
    n = 1
    while chemin.exists():
        n += 1
        chemin = chemin.with_name(f"{chemin.stem}_{n}.{ext}")
    return chemin


def nom_fichier(contenus: list[dict], modele: str) -> str:
    n = len(contenus)
    qui = contenus[0]["nom"] if n == 1 else f"{n} تلاميذ"
    return f"{contenus[0]['titre']} - {qui}"


# ---------- PowerPoint قابل للتعديل ----------

def _rgb(h: str):
    from pptx.dml.color import RGBColor
    return RGBColor.from_string(h.lstrip("#"))


def _boite(sl, prs, zone: Zone, lignes: list[tuple[str, float, str, bool]]) -> None:
    """مربع نص عربي (من اليمين، في الوسط) بأسطر (النص، الحجم بالنقط، اللون، عريض)."""
    from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
    from pptx.oxml.ns import qn
    from pptx.util import Pt
    x, y, w, h = zone
    W, H = prs.slide_width, prs.slide_height
    tb = sl.shapes.add_textbox(int(W * x / 100), int(H * y / 100), int(W * w / 100), int(H * h / 100))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    for k, (t, taille, coul, gras) in enumerate(lignes):
        p = tf.paragraphs[0] if k == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.CENTER
        p._p.get_or_add_pPr().set("rtl", "1")
        r = p.add_run()
        r.text = t
        f = r.font
        f.size = Pt(taille)
        f.bold = gras
        f.color.rgb = _rgb(coul)
        f.name = "Sakkal Majalla"
        rpr = r._r.get_or_add_rPr()
        cs = rpr.find(qn("a:cs"))
        if cs is None:
            cs = rpr.makeelement(qn("a:cs"), {})
            rpr.append(cs)
        cs.set("typeface", "Sakkal Majalla")
        rpr.set("lang", "ar-MA")


def generer_pptx(contenus: list[dict], modele: str, chemin: Path, logo: str = "") -> Path:
    """شريحة لكل تلميذ(ة): الزخرفة صورة خلفية، والنصوص مربعات قابلة للتعديل في PowerPoint."""
    from pptx import Presentation
    from pptx.util import Emu
    m = PAR_CLE[modele]
    prs = Presentation()
    prs.slide_height = Emu(6858000)
    prs.slide_width = Emu(int(6858000 * m.ratio))
    W, H = prs.slide_width, prs.slide_height
    for c in contenus:
        sl = prs.slides.add_slide(prs.slide_layouts[6])
        sl.shapes.add_picture(str(m.fond), 0, 0, W, H)
        x, y, w, h = m.zones["entete"]
        if MINISTERE.exists():
            hi = h * 0.42
            wi = min(w, hi * H / W * 694 / 82)
            sl.shapes.add_picture(str(MINISTERE), int(W * (x + (w - wi) / 2) / 100), int(H * y / 100),
                                  int(W * wi / 100), int(H * hi / 100))
            _boite(sl, prs, (x, y + hi, w, h - hi), [(l, 10, m.texte_couleur, k == 2)
                                                      for k, l in enumerate(c["entete"])])
        if logo and "logo" in m.zones:
            lx, ly, lw, lh = m.zones["logo"]
            s = min(lw * W / 100, lh * H / 100) * 0.8
            sl.shapes.add_picture(logo, int(W * (lx + lw / 2) / 100 - s / 2), int(H * (ly + lh / 2) / 100 - s / 2),
                                  int(s), int(s))
        if "titre" in m.zones:
            _boite(sl, prs, m.zones["titre"], [(c["titre"], 44, m.titre_couleur, True)])
        lignes = [(c["intro"], 18, m.texte_couleur, False), (c["nom"], 36, m.nom_couleur, True)]
        if c["classe"]:
            lignes.append((c["classe"], 15, m.texte_couleur, True))
        lignes += [(c["motif"], 18, m.texte_couleur, False), (c["voeu"], 15, m.texte_couleur, False)]
        _boite(sl, prs, m.zones["corps"], lignes)
        _boite(sl, prs, m.zones["date"], [(c["date"], 13, m.texte_couleur, False)])
        _boite(sl, prs, m.zones["signature"], [("        ".join(c["signataires"]), 15, m.texte_couleur, True)])
        if "medaille" in m.zones:
            _boite(sl, prs, m.zones["medaille"], [(c["jour"], 22, "#5A4300", True), (c["mois"], 13, "#5A4300", True),
                                                  (c["annee"], 13, "#5A4300", True)])
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(chemin))
    return chemin
