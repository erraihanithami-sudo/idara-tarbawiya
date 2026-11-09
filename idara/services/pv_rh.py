"""محاضر الموارد البشرية (طلب المدير 2026-11-09)، على نماذج المدير:

- محضر الالتحاق بالعمل: فردي، لكل موظف يلتحق بالمؤسسة، مع الحالة (التعيين الجديد، الانتقال، إنهاء الإلحاق...).
- محضر الدخول ومحضر الخروج: جماعيان (بداية السنة ونهايتها)، 10 موظفين في الصفحة، ومعهما لائحة من لم يوقعوا
  وسبب ذلك («لا أحد» إن وقّع الجميع).
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date

from idara.data.dossier import DossierDonnees
from idara.services import annee as annee_srv
from idara.services import documents as dc
from idara.services import etablissement as etab_srv
from idara.services import personnel as rh
from idara.services import textes as tx
from idara.services.moteur_docx import SUPPRIMER_LIGNE

CAS = ["التعيين الجديد", "التخرج من مراكز التكوين", "التخرج من مراكز المفتشين",
       "التخرج من المدرسة الوطنية للإدارة العمومية", "التخرج من مراكز تكوين المستشارين", "الانتقال",
       "تغيير الإطار", "إنهاء الإيداع الإداري", "إنهاء الإلحاق", "إنهاء رخصة طويلة الأمد",
       "استئناف العمل بعد مرض عادي", "تكليف بمهمة"]
SENS = {"entree": "محضر الدخول", "sortie": "محضر الخروج"}
CONCERNE = {"enseignants": "هيأة التدريس", "administratifs": "الأطر الإدارية والتقنية", "tous": "جميع الموظفين"}
LES = {"enseignants": "الأساتذة", "administratifs": "الموظفين", "tous": "الموظفين"}
LIGNES_PAGE = 10
LIGNES_NON_SIGNATAIRES = 10


class ErreurPV(ValueError):
    """رسالة موجهة للمدير بالعربية."""


def _date(v: str, lib: str) -> str:
    try:
        date.fromisoformat(v)
    except (TypeError, ValueError):
        raise ErreurPV(f"{lib}: تاريخ غير صحيح.") from None
    return v


# ---------- محضر الالتحاق بالعمل ----------

@dataclass
class PriseService:
    personnel_id: int
    date_prise: str
    cas: int
    reference: str = ""
    ancien_lieu: str = ""
    lieu_naissance: str = ""
    mission: str = ""
    date_redaction: str = ""
    id: int | None = None


def enregistrer_prise(conn: sqlite3.Connection, pv: PriseService) -> int:
    if not conn.execute("SELECT 1 FROM personnel WHERE id=?", (pv.personnel_id,)).fetchone():
        raise ErreurPV("اختر الموظف(ة).")
    _date(pv.date_prise, "تاريخ الالتحاق")
    if pv.cas not in range(1, len(CAS) + 1):
        raise ErreurPV("اختر حالة الالتحاق.")
    pv.date_redaction = _date(pv.date_redaction or pv.date_prise, "تاريخ التحرير")
    vals = (pv.personnel_id, pv.date_prise, pv.cas, " ".join(pv.reference.split()) or None,
            " ".join(pv.ancien_lieu.split()) or None, " ".join(pv.lieu_naissance.split()) or None,
            " ".join(pv.mission.split()) or None, pv.date_redaction)
    with conn:
        if pv.id:
            conn.execute("UPDATE pv_prise_service SET personnel_id=?, date_prise=?, cas=?, reference=?, ancien_lieu=?, "
                         "lieu_naissance=?, mission=?, date_redaction=? WHERE id=?", (*vals, pv.id))
        else:
            pv.id = conn.execute("INSERT INTO pv_prise_service(personnel_id, date_prise, cas, reference, ancien_lieu, "
                                 "lieu_naissance, mission, date_redaction) VALUES (?,?,?,?,?,?,?,?)", vals).lastrowid
    return pv.id


def lister_prises(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT v.*, p.prenom_ar || ' ' || p.nom_ar AS nom FROM pv_prise_service v JOIN personnel p ON "
        "p.id=v.personnel_id ORDER BY v.date_prise DESC, v.id DESC").fetchall()


def supprimer_prise(conn, pid: int) -> None:
    with conn:
        conn.execute("DELETE FROM pv_prise_service WHERE id=?", (pid,))


def valeurs_prise(conn: sqlite3.Connection, pv_id: int | None, r: dict | None = None,
                  p: rh.Personnel | None = None) -> dict[str, str]:
    r = r or conn.execute("SELECT * FROM pv_prise_service WHERE id=?", (pv_id,)).fetchone()
    if r is None:
        raise ErreurPV("المحضر غير موجود.")
    p = p or rh.lire(conn, r["personnel_id"])
    v = dc.champs_communs(conn)
    d = etab_srv.directeur_actuel(conn)
    a, s = tx.accord, p.sexe
    manque = [lib for val, lib in ((p.ppr, "رقم التأجير"), (p.cin, "رقم البطاقة الوطنية"), (p.cadre, "الإطار"))
              if not val]
    if manque:
        raise ErreurPV("بيانات ناقصة في ملف الموظف(ة): " + "، ".join(manque) + ".")
    naissance = "، ".join(x for x in (tx.date_chiffres(p.date_naissance) if p.date_naissance else "",
                                      r["lieu_naissance"] or "") if x)
    mission = r["mission"] or p.fonction or ("التدريس" if p.categorie in ("enseignant", "educatrice") else "")
    v.update({
        "ana_mouwaqqi": a(d["sexe"], "أنا الموقع أسفله", "أنا الموقعة أسفله"),
        "sayyid": a(s, "السيد", "السيدة"), "nom_complet": f"{p.prenom_ar} {p.nom_ar}", "ppr": p.ppr, "cin": p.cin,
        "naissance": naissance or "—", "cadre": rh.cadre_accorde(p.cadre, s), "mission": mission or "—",
        "hadara": a(s, "حضر", "حضرت"), "date_prise": tx.date_chiffres(r["date_prise"]),
        "reference": r["reference"] or "—", "ancien_lieu": r["ancien_lieu"] or "—", "adresse": p.adresse or "—",
        "date_redaction": tx.date_ar(r["date_redaction"]), "al_mouani": a(s, "المعني", "المعنية"),
    })
    for i in range(1, len(CAS) + 1):
        v[f"cas_{i}"] = "☑" if i == r["cas"] else "☐"
    return v


def generer_prise(conn: sqlite3.Connection, dossier: DossierDonnees, pv_id: int) -> dc.DocumentGenere:
    v = valeurs_prise(conn, pv_id)
    pid = conn.execute("SELECT personnel_id FROM pv_prise_service WHERE id=?", (pv_id,)).fetchone()[0]
    return dc.generer(conn, dossier, "pv_prise_service", v, libelle=f"محضر التحاق {v['nom_complet']}",
                      personnel_id=pid)


# ---------- محضر الدخول / الخروج ----------

def personnels(conn: sqlite3.Connection, concerne: str, unite: str | None = None) -> list[sqlite3.Row]:
    """الموظفون النشطون المعنيون (دون المدير)، الأساتذة أولاً."""
    if concerne not in CONCERNE:
        raise ErreurPV("الفئة المعنية غير معروفة.")
    cond = {"enseignants": "categorie IN ('enseignant','educatrice')",
            "administratifs": "categorie NOT IN ('enseignant','educatrice','directeur')",
            "tous": "categorie<>'directeur'"}[concerne]
    sql = (f"SELECT p.*, u.nom_ar AS unite FROM personnel p LEFT JOIN unite_scolaire u ON u.id=p.unite_id "
           f"WHERE p.statut='actif' AND {cond}")
    args: list = []
    if unite:
        sql += " AND u.nom_ar=?"
        args.append(unite)
    return conn.execute(sql + " ORDER BY p.categorie<>'enseignant', p.nom_ar, p.prenom_ar", args).fetchall()


def _ligne(i: int, p, cadre=True) -> dict[str, str]:
    return {f"r_{i}": str(i), f"nom_{i}": f"{p['prenom_ar']} {p['nom_ar']}", f"ppr_{i}": p["ppr"] or "",
            f"cin_{i}": p["cin"] or "", f"cadre_{i}": rh.cadre_accorde(p["cadre"], p["sexe"]) if p["cadre"] else "",
            f"matiere_{i}": p["matiere"] or "", f"tel_{i}": p["telephone"] or "", f"adresse_{i}": p["adresse"] or ""}


def _vide(i: int, champs: list[str]) -> dict[str, str]:
    return {f"{c}_{i}": SUPPRIMER_LIGNE if c == "r" else "" for c in champs}


def _entete_collectif(conn, sens: str, concerne: str, date_pv: str) -> dict[str, str]:
    v = dc.champs_communs(conn)
    e = etab_srv.lire_etablissement(conn)
    a = annee_srv.annee_courante(conn)
    v.update({"annee": a["libelle"] if a else "", "titre_pv": SENS[sens], "concerne": CONCERNE[concerne],
              "les_personnels": LES[concerne], "code_etab": (e.code_etab if e else "") or "—",
              "commune": (e.commune_ar if e else "") or "—", "date_pv": tx.date_chiffres(date_pv)})
    return v


def enregistrer_collectif(conn: sqlite3.Connection, sens: str, concerne: str, date_pv: str,
                          non_signataires: list[tuple[int, str]], unite: str | None = None) -> int:
    if sens not in SENS:
        raise ErreurPV("اختر: محضر الدخول أو محضر الخروج.")
    _date(date_pv, "تاريخ المحضر")
    ids = {p["id"] for p in personnels(conn, concerne, unite)}
    if not ids:
        raise ErreurPV("لا موظفين نشطين في هذه الفئة.")
    for pid, motif in non_signataires:
        if pid not in ids:
            raise ErreurPV("موظف(ة) غير وارد(ة) في لائحة المحضر.")
        if not motif.strip():
            raise ErreurPV("سبب عدم التوقيع إجباري لكل من لم يوقع.")
    a = annee_srv.annee_courante(conn)
    u = conn.execute("SELECT id FROM unite_scolaire WHERE nom_ar=?", (unite,)).fetchone() if unite else None
    with conn:
        return conn.execute(
            "INSERT INTO pv_collectif(annee_id, sens, concerne, unite_id, date_pv, non_signataires) VALUES "
            "(?,?,?,?,?,?)", (a["id"], sens, concerne, u[0] if u else None, date_pv,
                              json.dumps([[p, " ".join(m.split())] for p, m in non_signataires],
                                         ensure_ascii=False))).lastrowid


def lister_collectifs(conn) -> list[sqlite3.Row]:
    return conn.execute("SELECT c.*, u.nom_ar AS unite FROM pv_collectif c LEFT JOIN unite_scolaire u ON "
                        "u.id=c.unite_id ORDER BY c.date_pv DESC, c.id DESC").fetchall()


def generer_collectif(conn: sqlite3.Connection, dossier: DossierDonnees,
                      pv_id: int) -> tuple[dc.DocumentGenere, dc.DocumentGenere]:
    """المحضر (صفحة لكل 13 موظفاً) ولائحة من لم يوقعوا."""
    r = conn.execute("SELECT c.*, u.nom_ar AS unite FROM pv_collectif c LEFT JOIN unite_scolaire u ON "
                     "u.id=c.unite_id WHERE c.id=?", (pv_id,)).fetchone()
    if r is None:
        raise ErreurPV("المحضر غير موجود.")
    ps = personnels(conn, r["concerne"], r["unite"])
    v = _entete_collectif(conn, r["sens"], r["concerne"], r["date_pv"])
    champs = ["r", "nom", "ppr", "cin", "cadre", "matiere", "tel", "adresse", "obs"]
    nb_pages = max(1, -(-len(ps) // LIGNES_PAGE))
    pages = []
    for k in range(nb_pages):
        page = {"page": f"{k + 1:02d}/{nb_pages:02d}"}
        for i in range(1, LIGNES_PAGE + 1):
            n = k * LIGNES_PAGE + i
            if n <= len(ps):
                page.update(_ligne(i, ps[n - 1]))
                page[f"r_{i}"] = str(n)
                page[f"obs_{i}"] = ""
            else:
                page.update(_vide(i, champs))
        pages.append(page)
    lib = f"{SENS[r['sens']]} {CONCERNE[r['concerne']]}" + (f" ({r['unite']})" if r["unite"] else "")
    doc = dc.generer(conn, dossier, "pv_entree_sortie", v, pages, libelle=lib)
    non = json.loads(r["non_signataires"])
    par_id = {p["id"]: p for p in ps}
    vn = dict(v)
    champs_n = ["r", "nom", "ppr", "cin", "cadre", "matiere", "tel", "adresse", "motif"]
    if not non:
        vn.update({**_vide(1, champs_n), "r_1": "", "nom_1": "لا أحد"})
        for i in range(2, LIGNES_NON_SIGNATAIRES + 1):
            vn.update(_vide(i, champs_n))
    else:
        if len(non) > LIGNES_NON_SIGNATAIRES:
            raise ErreurPV(f"لائحة من لم يوقعوا تتسع لـ{LIGNES_NON_SIGNATAIRES} أسطر.")
        for i in range(1, LIGNES_NON_SIGNATAIRES + 1):
            if i <= len(non) and non[i - 1][0] in par_id:
                vn.update(_ligne(i, par_id[non[i - 1][0]]))
                vn[f"motif_{i}"] = non[i - 1][1]
            else:
                vn.update(_vide(i, champs_n))
    doc2 = dc.generer(conn, dossier, "pv_non_signataires", vn, libelle=f"من لم يوقعوا {lib}")
    return doc, doc2


# ---------- معاينة القوالب ببيانات وهمية ----------

def _exemple_personnel(sexe: str = "M", i: int = 1) -> dict:
    return {"id": i, "prenom_ar": ("سعيد" if sexe == "M" else "سلمى") + (f" {i}" if i > 1 else ""),
            "nom_ar": "التجريبي", "sexe": sexe, "ppr": "1234567", "cin": "[CIN]", "cadre": rh.CADRES[0],
            "matiere": "عربية", "telephone": "0600000000", "adresse": "[العنوان الشخصي]"}


def exemple(conn, code: str, sexe: str = "M"):
    an = date.today().year
    if code == "pv_prise_service":
        p = rh.Personnel(nom_ar="التجريبي", prenom_ar="سعيد" if sexe == "M" else "سلمى", sexe=sexe,
                         categorie="enseignant", ppr="1234567", cin="[CIN]", cadre=rh.CADRES[0], fonction="التدريس",
                         adresse="[العنوان الشخصي]", date_naissance="1990-01-01")
        r = {"personnel_id": 0, "date_prise": f"{an}-09-01", "cas": 6, "reference": "[مرجع الرسالة الوزارية]",
             "ancien_lieu": "[مقر العمل السابق]", "lieu_naissance": "[مكان الازدياد]", "mission": None,
             "date_redaction": f"{an}-09-01"}
        return valeurs_prise(conn, None, r=r, p=p), None
    v = _entete_collectif(conn, "entree", "enseignants", f"{an}-09-01")
    if code == "pv_entree_sortie":
        page = {"page": "01/01"}
        for i in range(1, LIGNES_PAGE + 1):
            page.update(_ligne(i, _exemple_personnel(sexe, i)) if i <= 3 else
                        _vide(i, ["r", "nom", "ppr", "cin", "cadre", "matiere", "tel", "adresse", "obs"]))
            page.setdefault(f"obs_{i}", "")
        return v, [page]
    if code == "pv_non_signataires":
        v.update({**_vide(1, ["r", "nom", "ppr", "cin", "cadre", "matiere", "tel", "adresse", "motif"]),
                  "r_1": "", "nom_1": "لا أحد"})
        for i in range(2, LIGNES_NON_SIGNATAIRES + 1):
            v.update(_vide(i, ["r", "nom", "ppr", "cin", "cadre", "matiere", "tel", "adresse", "motif"]))
        return v, None
    raise ErreurPV(f"قالب غير معروف: {code}")
