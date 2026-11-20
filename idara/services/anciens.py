"""التلاميذ ما قبل مسار: تسجيلهم برقم السجل العام، والشهادة المدرسية بكل حقول النموذج.

يُنشأ التلميذ عند أول طلب شهادة، ويبقى في القاعدة لتيسير إعادة الطباعة.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date

from idara.data.dossier import DossierDonnees
from idara.services import documents as dc
from idara.services import eleves as el

NIVEAUX_ANCIENS = ["الأول", "الثاني", "الثالث", "الرابع", "الخامس", "السادس"]


class ErreurAncien(ValueError):
    """رسالة موجهة للمدير بالعربية."""


@dataclass
class Ancien:
    num_registre: str = ""
    nom_ar: str = ""
    prenom_ar: str = ""
    sexe: str = ""
    date_naissance: str = ""      # YYYY-MM-DD
    date_naissance_approx: bool = False
    lieu_ar: str = ""
    date_entree: str = ""
    date_sortie: str = ""
    dernier_niveau: str = ""
    num_cahier_registre: str = ""
    id: int | None = None
    tuteur: str = ""          # اسم ولي الأمر (2026-11-20)
    nationalite: str = ""
    adresse: str = ""
    motif_sortie: str = ""    # سبب الانقطاع
    erreurs: list[str] = field(default_factory=list)

    def valider(self) -> None:
        """كل حقول الشهادة إجبارية."""
        for k in ("num_registre", "nom_ar", "prenom_ar", "lieu_ar", "dernier_niveau"):
            setattr(self, k, " ".join(str(getattr(self, k)).split()))
        manquants = [lib for k, lib in [
            ("num_registre", "رقم التسجيل في السجل العام"), ("nom_ar", "النسب"), ("prenom_ar", "الاسم"),
            ("sexe", "النوع"), ("date_naissance", "تاريخ الازدياد"), ("lieu_ar", "مكان الازدياد"),
            ("date_entree", "تاريخ الالتحاق"), ("date_sortie", "تاريخ الانقطاع"),
            ("dernier_niveau", "آخر قسم درس به")] if not getattr(self, k)]
        if manquants:
            raise ErreurAncien("حقول إجبارية فارغة: " + "، ".join(manquants))
        if not self.num_registre.isdigit() or int(self.num_registre) <= 0:
            raise ErreurAncien("رقم التسجيل في السجل العام يتكون من أرقام فقط.")
        if self.sexe not in ("M", "F"):
            raise ErreurAncien("النوع غير صحيح.")
        try:
            n, e, s = (date.fromisoformat(x) for x in (self.date_naissance, self.date_entree, self.date_sortie))
        except ValueError as ex:
            raise ErreurAncien("أحد التواريخ غير صحيح.") from ex
        if not (n < e <= s <= date.today()):
            raise ErreurAncien("التواريخ غير منطقية: الازدياد قبل الالتحاق، والالتحاق قبل الانقطاع، "
                               "والانقطاع ليس في المستقبل.")


def lire(conn: sqlite3.Connection, eleve_id: int) -> Ancien:
    r = conn.execute(
        "SELECT e.*, l.nom_ar AS lieu_ar, a.date_entree, a.date_sortie, a.dernier_niveau, a.tuteur, a.nationalite, "
        "a.adresse, a.motif_sortie "
        "FROM eleve e LEFT JOIN lieu l ON l.id=e.lieu_naissance_id "
        "LEFT JOIN eleve_avant_massar a ON a.eleve_id=e.id WHERE e.id=?", (eleve_id,)).fetchone()
    if r is None:
        raise ErreurAncien("التلميذ غير موجود.")
    return Ancien(str(r["num_registre"] or ""), r["nom_ar"], r["prenom_ar"], r["sexe"] or "",
                  r["date_naissance"] or "", bool(r["date_naissance_approx"]), r["lieu_ar"] or "",
                  r["date_entree"] or "", r["date_sortie"] or "", r["dernier_niveau"] or "",
                  r["num_cahier_registre"] or "", r["id"], tuteur=r["tuteur"] or "",
                  nationalite=r["nationalite"] or "", adresse=r["adresse"] or "", motif_sortie=r["motif_sortie"] or "")


def par_numero(conn: sqlite3.Connection, num_registre: str) -> Ancien | None:
    r = conn.execute("SELECT id FROM eleve WHERE num_registre=?", (num_registre.strip(),)).fetchone() \
        if num_registre.strip().isdigit() else None
    return lire(conn, r["id"]) if r else None


def enregistrer(conn: sqlite3.Connection, a: Ancien) -> int:
    """ينشئ التلميذ القديم أو يحدّثه. رقم السجل فريد."""
    a.valider()
    num = int(a.num_registre)
    autre = conn.execute("SELECT id, source FROM eleve WHERE num_registre=?", (num,)).fetchone()
    if autre and autre["id"] != a.id:
        raise ErreurAncien(f"رقم التسجيل {num} مسجل لتلميذ آخر. ابحث عنه بهذا الرقم.")
    with conn:
        lid = el.lieu_id(conn, a.lieu_ar)
        valeurs = (num, a.num_cahier_registre or None, a.nom_ar, a.prenom_ar, a.sexe, a.date_naissance,
                   int(a.date_naissance_approx), lid)
        if a.id is None:
            a.id = conn.execute(
                "INSERT INTO eleve(num_registre, num_cahier_registre, nom_ar, prenom_ar, sexe, date_naissance,"
                " date_naissance_approx, lieu_naissance_id, source) VALUES (?,?,?,?,?,?,?,?,'avant_massar')",
                valeurs).lastrowid
        else:
            conn.execute(
                "UPDATE eleve SET num_registre=?, num_cahier_registre=?, nom_ar=?, prenom_ar=?, sexe=?,"
                " date_naissance=?, date_naissance_approx=?, lieu_naissance_id=?,"
                " modifie_le=datetime('now','localtime') WHERE id=?", (*valeurs, a.id))
        conn.execute(
            "INSERT INTO eleve_avant_massar(eleve_id, date_entree, date_sortie, dernier_niveau, tuteur, nationalite, "
            "adresse, motif_sortie) VALUES (?,?,?,?,?,?,?,?) "
            "ON CONFLICT(eleve_id) DO UPDATE SET date_entree=excluded.date_entree, "
            "date_sortie=excluded.date_sortie, dernier_niveau=excluded.dernier_niveau, tuteur=excluded.tuteur, "
            "nationalite=excluded.nationalite, adresse=excluded.adresse, motif_sortie=excluded.motif_sortie",
            (a.id, a.date_entree, a.date_sortie, a.dernier_niveau, " ".join(a.tuteur.split()),
             " ".join(a.nationalite.split()), " ".join(a.adresse.split()), " ".join(a.motif_sortie.split())))
        conn.execute("INSERT INTO journal(action, cible, cible_id, details) VALUES ('enregistrement','ancien',?,?)",
                     (a.id, f"{num} {a.prenom_ar} {a.nom_ar}"))
    return a.id


def generer_certificat(conn: sqlite3.Connection, dossier: DossierDonnees, eleve_id: int,
                       destinataire_nom: str, destinataire_cin: str,
                       le: date | None = None) -> dc.DocumentGenere:
    a = lire(conn, eleve_id)
    a.valider()
    donnees = {"nom_ar": a.nom_ar, "prenom_ar": a.prenom_ar, "sexe": a.sexe,
               "date_naissance": a.date_naissance, "lieu_ar": a.lieu_ar, "num_registre": a.num_registre,
               "date_entree": a.date_entree, "date_sortie": a.date_sortie, "dernier_niveau": a.dernier_niveau}
    v = dc.champs_certificat_ancien(conn, donnees, destinataire_nom, destinataire_cin.upper(), le)
    return dc.generer(conn, dossier, "certificat_scolarite_ancien", v, eleve_id=eleve_id,
                      destinataire_nom=v["destinataire_nom"], destinataire_cin=v["destinataire_cin"],
                      libelle=f"{a.prenom_ar} {a.nom_ar} ({a.num_registre})")


def remises(conn: sqlite3.Connection, eleve_id: int) -> list[sqlite3.Row]:
    """سجل تسليم الشهادات لهذا التلميذ."""
    return conn.execute(
        "SELECT d.id, d.date_generation, d.destinataire_nom, d.destinataire_cin, d.fichier_archive "
        "FROM document_genere d JOIN modele_document m ON m.id=d.modele_id "
        "WHERE d.eleve_id=? AND m.code='certificat_scolarite_ancien' ORDER BY d.id DESC", (eleve_id,)).fetchall()


# ---------------------------------------------------------------------------
# نموذج الإكسل (طلب المدير 2026-11-20): يُصدَّر فارغاً أو بالتلاميذ المسجلين، يُعبَّأ ثم يُستورد.
# ---------------------------------------------------------------------------
COLONNES_EXCEL = (
    ("num_registre", "رقم التلميذ في السجل العام *"), ("nom_ar", "النسب *"), ("prenom_ar", "الاسم *"),
    ("sexe", "النوع * (ذكر/أنثى)"), ("date_naissance", "تاريخ الازدياد * (يوم/شهر/سنة)"),
    ("lieu_ar", "مكان الازدياد *"), ("tuteur", "اسم ولي الأمر"), ("nationalite", "الجنسية"),
    ("adresse", "العنوان"), ("date_entree", "تاريخ التسجيل *"), ("date_sortie", "تاريخ الانقطاع *"),
    ("dernier_niveau", "آخر مستوى درس به *"), ("motif_sortie", "سبب الانقطاع"),
)
MOTIFS_SORTIE = ("انتقال إلى مؤسسة أخرى", "نهاية المرحلة الابتدائية", "انقطاع عن الدراسة", "الفصل", "الوفاة")


def _date_fr(iso: str) -> str:
    return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}" if iso and len(iso) == 10 else ""


def _lire_date(v) -> tuple[str, bool]:
    """(YYYY-MM-DD، تقريبي؟) من خانة إكسل: تاريخ، أو نص يوم/شهر/سنة، أو سنة وحدها (تقريبي)."""
    from datetime import datetime
    if v in (None, ""):
        return "", False
    if isinstance(v, datetime):
        return v.date().isoformat(), False
    if isinstance(v, date):
        return v.isoformat(), False
    t = str(v).strip().replace("-", "/").replace(".", "/")
    if isinstance(v, (int, float)) or t.isdigit():
        n = int(float(t))
        if 1900 <= n <= 2100:
            return f"{n}-01-01", True
        raise ErreurAncien(f"تاريخ غير مفهوم: {t}")
    parts = t.split("/")
    try:
        if len(parts) == 3 and len(parts[0]) == 4:
            return date(int(parts[0]), int(parts[1]), int(parts[2])).isoformat(), False
        if len(parts) == 3:
            return date(int(parts[2]), int(parts[1]), int(parts[0])).isoformat(), False
    except ValueError:
        pass
    raise ErreurAncien(f"تاريخ غير مفهوم: {t} (اكتبه يوم/شهر/سنة)")


def _niveau(v) -> str:
    t = " ".join(str(v or "").split())
    if t.isdigit() and 1 <= int(t) <= 6:
        return NIVEAUX_ANCIENS[int(t) - 1]
    for pre in ("القسم ", "المستوى "):
        if t.startswith(pre):
            t = t[len(pre):]
    return t


def exporter_excel(conn: sqlite3.Connection, chemin, avec_eleves: bool = True):
    """نموذج إكسل للتعبئة: رؤوس الأعمدة، قوائم منسدلة للنوع والمستوى وسبب الانقطاع، وصفحة إرشادات.
    avec_eleves: يُملأ بالتلاميذ القدامى المسجلين (لتعديلهم وإعادة استيرادهم)."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.worksheet.datavalidation import DataValidation
    from pathlib import Path
    wb = Workbook()
    ws = wb.active
    ws.title = "التلاميذ ما قبل مسار"
    ws.sheet_view.rightToLeft = True
    fond = PatternFill("solid", fgColor="0B1C2C")
    fin = Side(style="thin", color="C9A04A")
    for j, (_, lib) in enumerate(COLONNES_EXCEL, start=1):
        c = ws.cell(row=1, column=j, value=lib)
        c.font = Font(bold=True, color="F3D27A", size=11)
        c.fill = fond
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = Border(bottom=fin, left=fin, right=fin)
        ws.column_dimensions[c.column_letter].width = 26 if j in (3, 9, 13) else 20
    ws.row_dimensions[1].height = 42
    ws.freeze_panes = "A2"
    lignes = []
    if avec_eleves:
        for r in conn.execute("SELECT id FROM eleve WHERE source='avant_massar' ORDER BY num_registre"):
            a = lire(conn, r["id"])
            lignes.append([int(a.num_registre) if a.num_registre.isdigit() else a.num_registre, a.nom_ar,
                           a.prenom_ar, {"M": "ذكر", "F": "أنثى"}.get(a.sexe, ""),
                           a.date_naissance[:4] if a.date_naissance_approx else _date_fr(a.date_naissance),
                           a.lieu_ar, a.tuteur, a.nationalite, a.adresse, _date_fr(a.date_entree),
                           _date_fr(a.date_sortie), a.dernier_niveau, a.motif_sortie])
    for i, l in enumerate(lignes, start=2):
        for j, v in enumerate(l, start=1):
            ws.cell(row=i, column=j, value=v)
    for lettre, valeurs in (("D", ("ذكر", "أنثى")), ("L", NIVEAUX_ANCIENS), ("M", MOTIFS_SORTIE)):
        dv = DataValidation(type="list", formula1='"' + ",".join(valeurs) + '"', allow_blank=True,
                            showErrorMessage=lettre == "D")
        ws.add_data_validation(dv)
        dv.add(f"{lettre}2:{lettre}501")
    g = wb.create_sheet("إرشادات")
    g.sheet_view.rightToLeft = True
    g.column_dimensions["A"].width = 110
    for i, t in enumerate((
            "نموذج التلاميذ ما قبل مسار — الشامل في الإدارة التربوية",
            "سطر واحد لكل تلميذ. الأعمدة المعلّمة بـ * إجبارية لتوليد الشهادة المدرسية.",
            "رقم التلميذ هو رقمه في السجل العام للمؤسسة: إن كان مسجلاً في البرنامج تُحدَّث بياناته، وإلا يُضاف.",
            "التواريخ بصيغة يوم/شهر/سنة (مثال 15/10/1992). إن لم يُعرف إلا عام الازدياد فاكتب السنة وحدها.",
            "النوع: ذكر أو أنثى. آخر مستوى: الأول … السادس (من القائمة).",
            "بعد التعبئة: صفحة «التلاميذ القدامى (ما قبل مسار)» ← «استيراد من الإكسل».",
    ), start=1):
        c = g.cell(row=i, column=1, value=t)
        c.font = Font(bold=i == 1, size=13 if i == 1 else 11, color="0B1C2C")
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    wb.save(chemin)
    return chemin, len(lignes)


@dataclass
class RapportImport:
    ajoutes: int = 0
    modifies: int = 0
    erreurs: list[tuple[int, str]] = field(default_factory=list)

    def resume(self) -> str:
        t = f"أُضيف {self.ajoutes} تلميذاً وحُدّث {self.modifies}."
        if self.erreurs:
            t += f" لم يُستورد {len(self.erreurs)} سطراً: " + "؛ ".join(f"السطر {n}: {m}" for n, m in self.erreurs[:5])
            if len(self.erreurs) > 5:
                t += " …"
        return t


def importer_excel(conn: sqlite3.Connection, chemin) -> RapportImport:
    """يستورد النموذج المعبأ: يضيف التلاميذ الجدد ويحدّث الموجودين برقم السجل، ويسرد الأسطر المرفوضة وسببها."""
    import openpyxl
    try:
        wb = openpyxl.load_workbook(chemin, read_only=True, data_only=True)
    except Exception as e:  # noqa: BLE001
        raise ErreurAncien("تعذر فتح ملف الإكسل: تأكد أنه نموذج .xlsx.") from e
    ws = wb.worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    if not rows:
        raise ErreurAncien("الملف فارغ.")
    entetes = [" ".join(str(x or "").split()) for x in rows[0]]
    index = {}
    for cle, lib in COLONNES_EXCEL:
        court = lib.split(" *")[0].split(" (")[0]
        for j, e in enumerate(entetes):
            if e.startswith(court):
                index[cle] = j
                break
    manquants = [lib for cle, lib in COLONNES_EXCEL if cle not in index and "*" in lib]
    if manquants:
        raise ErreurAncien("أعمدة إجبارية غير موجودة في الملف: " + "، ".join(manquants)
                           + ". استعمل النموذج المصدَّر من البرنامج.")
    rap = RapportImport()
    for n, row in enumerate(rows[1:], start=2):
        val = {cle: (row[j] if j < len(row) else None) for cle, j in index.items()}
        if all(v in (None, "") for v in val.values()):
            continue
        try:
            num = str(val.get("num_registre") or "").strip()
            if num.endswith(".0"):
                num = num[:-2]
            sexe_t = " ".join(str(val.get("sexe") or "").split())
            sexe = {"ذكر": "M", "أنثى": "F", "انثى": "F", "M": "M", "F": "F", "ذ": "M", "أ": "F"}.get(sexe_t, "")
            dn, approx = _lire_date(val.get("date_naissance"))
            de, _ = _lire_date(val.get("date_entree"))
            ds, _ = _lire_date(val.get("date_sortie"))
            existant = par_numero(conn, num)
            a = Ancien(num_registre=num, nom_ar=str(val.get("nom_ar") or ""), prenom_ar=str(val.get("prenom_ar") or ""),
                       sexe=sexe, date_naissance=dn, date_naissance_approx=approx,
                       lieu_ar=str(val.get("lieu_ar") or ""), date_entree=de, date_sortie=ds,
                       dernier_niveau=_niveau(val.get("dernier_niveau")),
                       num_cahier_registre=existant.num_cahier_registre if existant else "",
                       id=existant.id if existant else None,
                       tuteur=str(val.get("tuteur") or ""), nationalite=str(val.get("nationalite") or ""),
                       adresse=str(val.get("adresse") or ""), motif_sortie=str(val.get("motif_sortie") or ""))
            if sexe_t and not sexe:
                raise ErreurAncien(f"النوع «{sexe_t}» غير مفهوم (ذكر أو أنثى).")
            enregistrer(conn, a)
            if existant:
                rap.modifies += 1
            else:
                rap.ajoutes += 1
        except ErreurAncien as e:
            rap.erreurs.append((n, str(e)))
    return rap
