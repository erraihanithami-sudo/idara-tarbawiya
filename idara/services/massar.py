"""قراءة لوائح التلاميذ المصدّرة من منظومة مسار (بالعربية أو بالفرنسية).

لا يعتمد على أرقام صفوف ثابتة: يبحث عن صف العناوين بنصوصه، ويقرأ الرأس بتسمياته،
فلا يتعطل إذا أضاف مسار صفاً أو غيّر الترتيب.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

MOTIF_CODE = re.compile(r"^[A-Z]\d{9}$")
_ARABE = re.compile(r"[؀-ۿ]")


class ErreurMassar(ValueError):
    """رسالة موجهة للمدير بالعربية."""


def normaliser(texte) -> str:
    """لمقارنة التسميات: دون مسافات أو نقطتين أو تشكيل، وتوحيد الهمزات والأحرف اللاتينية."""
    if texte is None:
        return ""
    t = unicodedata.normalize("NFKD", str(texte))
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.translate(str.maketrans("أإآ", "ااا")).replace("ـ", "")
    return re.sub(r"[\s:. °]", "", t).lower()


def propre(texte) -> str:
    return " ".join(str(texte).split()) if texte not in (None, "") else ""


# ---------- الأعمدة والرأس ----------

COLONNES = {
    "ar": {"code": "الرمز", "nom": "النسب", "prenom": "الإسم", "sexe": "النوع",
           "date_naissance": "تاريخ الإزدياد", "lieu": "مكان الازدياد"},
    "fr": {"code": "Code", "nom": "Nom", "prenom": "Prénom", "sexe": "Genre",
           "date_naissance": "Date de naissance", "lieu": "Lieu naissance"},
}
ENTETE = {
    "ar": {"academie": "الأكاديمية", "direction": "المديرية الإقليمية", "commune": "الجماعة",
           "etablissement": "المؤسسة", "niveau": "المستوى", "classe": "القسم", "annee": "السنة الدراسية"},
    "fr": {"academie": "Académie", "direction": "Direction provinciale", "commune": "Commune",
           "etablissement": "Etablissement", "niveau": "Niveau", "classe": "Classe", "annee": "Année Scolaire"},
}
SEXES = {normaliser("ذكر"): "M", normaliser("أنثى"): "F", "garcon": "M", "fille": "F",
         "m": "M", "f": "F", "masculin": "M", "feminin": "F"}


@dataclass
class LigneMassar:
    code: str
    classe: str
    nom: str
    prenom: str
    sexe: str | None
    date_naissance: str | None  # YYYY-MM-DD
    lieu: str
    ligne: int


@dataclass
class FeuilleMassar:
    nom: str
    langue: str
    entete: dict[str, str]
    lignes: list[LigneMassar]

    @property
    def classe(self) -> str:
        return self.entete.get("classe") or self.nom


@dataclass
class FichierMassar:
    chemin: Path
    langue: str
    feuilles: list[FeuilleMassar]
    alertes: list[str] = field(default_factory=list)


def _date(valeur) -> str | None:
    if valeur in (None, ""):
        return None
    if isinstance(valeur, datetime):
        return valeur.date().isoformat()
    if isinstance(valeur, date):
        return valeur.isoformat()
    t = str(valeur).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(t, fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError(t)


def _trouver_entetes(lignes: list[tuple]) -> tuple[int, str, dict[str, int]] | None:
    """صف العناوين: أول صف تتطابق فيه أعمدة إحدى اللغتين."""
    for i, ligne in enumerate(lignes):
        textes = [normaliser(v) for v in ligne]
        for langue, cols in COLONNES.items():
            idx = {}
            for cle, libelle in cols.items():
                cible = normaliser(libelle)
                if cible in textes:
                    idx[cle] = textes.index(cible)
            if {"code", "nom", "prenom"} <= idx.keys() and len(idx) >= 5:
                return i, langue, idx
    return None


def _lire_entete(lignes: list[tuple], jusqua: int, langue: str) -> dict[str, str]:
    res = {}
    cibles = {normaliser(v): k for k, v in ENTETE[langue].items()}
    for ligne in lignes[:jusqua]:
        for j, v in enumerate(ligne):
            cle = cibles.get(normaliser(v))
            if cle and cle not in res:
                suite = next((propre(x) for x in ligne[j + 1:] if propre(x)), "")
                res[cle] = suite
    return res


def lire_fichier(chemin: Path | str) -> FichierMassar:
    from openpyxl import load_workbook

    chemin = Path(chemin)
    try:
        wb = load_workbook(chemin, read_only=True, data_only=True)
    except Exception as e:  # noqa: BLE001
        raise ErreurMassar(f"تعذرت قراءة الملف {chemin.name}: ليس ملف Excel صالحاً.") from e
    feuilles, alertes, langues = [], [], set()
    try:
        for ws in wb.worksheets:
            lignes = [tuple(r) for r in ws.iter_rows(values_only=True)]
            trouve = _trouver_entetes(lignes)
            if trouve is None:
                continue
            i_ent, langue, idx = trouve
            langues.add(langue)
            entete = _lire_entete(lignes, i_ent, langue)
            classe = entete.get("classe") or ws.title
            res = []
            for n, ligne in enumerate(lignes[i_ent + 1:], start=i_ent + 2):
                def val(cle):
                    j = idx.get(cle)
                    return ligne[j] if j is not None and j < len(ligne) else None
                code = propre(val("code")).upper()
                if not code:
                    if any(propre(v) for v in ligne):
                        alertes.append(f"{ws.title}، السطر {n}: سطر بلا رمز مسار تم تجاهله.")
                    continue
                if not MOTIF_CODE.match(code):
                    alertes.append(f"{ws.title}، السطر {n}: رمز غير صالح «{code}» تم تجاهله.")
                    continue
                try:
                    dn = _date(val("date_naissance"))
                except ValueError as e:
                    dn = None
                    alertes.append(f"{code}: تاريخ ازدياد غير مفهوم «{e}».")
                sexe = SEXES.get(normaliser(val("sexe")))
                if sexe is None:
                    alertes.append(f"{code}: النوع غير محدد.")
                res.append(LigneMassar(code, classe, propre(val("nom")), propre(val("prenom")),
                                       sexe, dn, propre(val("lieu")), n))
            feuilles.append(FeuilleMassar(ws.title, langue, entete, res))
    finally:
        wb.close()
    if not feuilles:
        raise ErreurMassar(f"الملف {chemin.name} لا يحتوي على لائحة تلاميذ بصيغة مسار.")
    if len(langues) > 1:
        raise ErreurMassar(f"الملف {chemin.name} يخلط اللائحة العربية والفرنسية.")
    return FichierMassar(chemin, langues.pop(), feuilles, alertes)


# ---------- الدمج ----------

@dataclass
class EleveMassar:
    code: str
    classe: str
    nom_ar: str = ""
    prenom_ar: str = ""
    nom_fr: str = ""
    prenom_fr: str = ""
    sexe: str | None = None
    date_naissance: str | None = None
    lieu_ar: str = ""
    lieu_fr: str = ""


@dataclass
class ListeMassar:
    eleves: dict[str, EleveMassar]
    classes: list[str]
    annee: str | None
    etablissement: str | None
    alertes: list[str]
    langues: list[str]


def fusionner(fichiers: list[FichierMassar]) -> ListeMassar:
    """يدمج اللائحتين العربية والفرنسية بالرمز. العربية مرجع النوع والتاريخ."""
    if not fichiers:
        raise ErreurMassar("اختر لائحة واحدة على الأقل.")
    langues = [f.langue for f in fichiers]
    if len(langues) != len(set(langues)):
        raise ErreurMassar("اخترت لائحتين بنفس اللغة. اختر العربية و/أو الفرنسية.")
    fichiers = sorted(fichiers, key=lambda f: f.langue != "ar")  # العربية أولاً
    eleves: dict[str, EleveMassar] = {}
    alertes: list[str] = []
    classes: list[str] = []
    annees, etabs = set(), set()
    for f in fichiers:
        alertes += f.alertes
        vus = set()
        for feuille in f.feuilles:
            if feuille.classe not in classes:
                classes.append(feuille.classe)
            if feuille.entete.get("annee"):
                annees.add(feuille.entete["annee"].replace(" ", ""))
            if f.langue == "ar" and feuille.entete.get("etablissement"):
                etabs.add(feuille.entete["etablissement"])
            for l in feuille.lignes:
                if l.code in vus:
                    alertes.append(f"{l.code}: مكرر في نفس الملف (أُخذ أول ظهور فقط).")
                    continue
                vus.add(l.code)
                e = eleves.setdefault(l.code, EleveMassar(l.code, l.classe))
                if f.langue == "ar":
                    e.nom_ar, e.prenom_ar, e.sexe, e.date_naissance = l.nom, l.prenom, l.sexe, l.date_naissance
                    e.lieu_ar = l.lieu
                else:
                    e.nom_fr, e.prenom_fr = l.nom.upper(), l.prenom.upper()
                    if l.lieu and not _ARABE.search(l.lieu):
                        e.lieu_fr = l.lieu.upper()
                    if e.sexe is None:
                        e.sexe = l.sexe
                    elif l.sexe and l.sexe != e.sexe:
                        alertes.append(f"{l.code}: النوع مختلف بين اللائحتين (اعتُمدت العربية).")
                    if e.date_naissance is None:
                        e.date_naissance = l.date_naissance
                    elif l.date_naissance and l.date_naissance != e.date_naissance:
                        alertes.append(f"{l.code}: تاريخ الازدياد مختلف بين اللائحتين (اعتُمدت العربية).")
                    if e.classe != l.classe:
                        alertes.append(f"{l.code}: القسم مختلف بين اللائحتين ({e.classe} / {l.classe}).")
    if len(annees) > 1:
        raise ErreurMassar("اللوائح المختارة تخص سنوات دراسية مختلفة: " + "، ".join(sorted(annees)))
    if "ar" in langues and "fr" in langues:
        ar = {c for c, e in eleves.items() if e.nom_ar}
        fr = {c for c, e in eleves.items() if e.nom_fr}
        for c in sorted(ar - fr):
            alertes.append(f"{c}: موجود في اللائحة العربية دون الفرنسية.")
        for c in sorted(fr - ar):
            alertes.append(f"{c}: موجود في اللائحة الفرنسية دون العربية.")
    return ListeMassar(eleves, classes, annees.pop() if annees else None,
                       next(iter(etabs), None), alertes, langues)


# ---------- المستويات حسب القسم والسن ----------

def niveaux_du_code_classe(code: str) -> list[str]:
    """«1APG-2APG-3APG» ← [1AP, 2AP, 3AP]؛ «PS1-PS2» ← [PS1, PS2]."""
    res = []
    for partie in re.split(r"[-_/ ]+", code.upper()):
        m = re.match(r"^([1-6])AP", partie)
        if m:
            res.append(f"{m.group(1)}AP")
            continue
        m = re.match(r"^PS([12])$", partie)
        if m:
            res.append(f"PS{m.group(1)}")
    return list(dict.fromkeys(res))


ORDRE = ["PS1", "PS2", "1AP", "2AP", "3AP", "4AP", "5AP", "6AP"]
AGE_NORMAL = {n: i + 4 for i, n in enumerate(ORDRE)}  # PS1: 4 سنوات ... 6AP: 11 سنة


def proposer_niveau(code_classe: str, date_naissance: str | None,
                    annee_debut: int) -> tuple[str | None, bool]:
    """يقترح المستوى حسب السن ضمن مستويات القسم.
    يعيد (المستوى، هل السن ضمن المعتاد). قسم بمستوى واحد ← ذلك المستوى."""
    candidats = niveaux_du_code_classe(code_classe)
    if len(candidats) == 1:
        return candidats[0], True
    if not candidats or not date_naissance:
        return None, False
    age = annee_debut - int(date_naissance[:4])
    meilleur = min(candidats, key=lambda n: (abs(AGE_NORMAL[n] - age), ORDRE.index(n)))
    return meilleur, abs(AGE_NORMAL[meilleur] - age) <= 1
