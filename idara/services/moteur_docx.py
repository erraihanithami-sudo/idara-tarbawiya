"""محرك قوالب Word.

- الحقول تُكتب في القالب بصيغة {{اسم_الحقل}} (أسماء لاتينية).
- يعمل على متن الوثيقة ومربعات النص والترويسات والتذييلات.
- يتحمل تقطيع Word للنص إلى مقاطع (runs): الحقل يُستبدل ولو توزع على عدة مقاطع،
  ويأخذ تنسيق المقطع الذي يبدأ فيه.
- لا يغير أي شيء آخر في الملف (الصور، العلامة المائية، التنسيق).
"""

from __future__ import annotations

import copy
import io
import re
import zipfile
from pathlib import Path
from typing import Callable, Iterable

from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
W14 = "http://schemas.microsoft.com/office/word/2010/wordml"
MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"

MOTIF_CHAMP = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")
MOTIF_CASE = re.compile(r"^[A-Za-z_]+_\d+$")  # حقول الخانات: eleve_1، eleve_2...
_PARTIES = re.compile(r"^word/(document|header\d+|footer\d+)\.xml$")


class ErreurModele(ValueError):
    """رسالة موجهة للمدير بالعربية."""


def _q(ns: str, tag: str) -> str:
    return f"{{{ns}}}{tag}"


# ---------- العمل على فقرة واحدة ----------

def _textes_propres(p: etree._Element) -> list[etree._Element]:
    """عناصر w:t التابعة لهذه الفقرة مباشرة (دون فقرات مربعات النص المتداخلة فيها)."""
    res = []
    for t in p.iter(_q(W, "t")):
        parent_p = next((a for a in t.iterancestors(_q(W, "p"))), None)
        if parent_p is p:
            res.append(t)
    return res


def texte_paragraphe(p: etree._Element) -> str:
    return "".join(t.text or "" for t in _textes_propres(p))


def _remplacer_span(ts: list[etree._Element], debut: int, fin: int, nouveau: str) -> None:
    """يضع النص الجديد في المقطع الذي يبدأ فيه التطابق، ويحذف بقيته من المقاطع التالية."""
    pos = 0
    premier = True
    for t in ts:
        txt = t.text or ""
        a, b = pos, pos + len(txt)
        pos = b
        if b <= debut or a >= fin:
            continue
        g, d = max(debut, a) - a, min(fin, b) - a
        t.text = txt[:g] + (nouveau if premier else "") + txt[d:]
        premier = False
        t.set(XML_SPACE, "preserve")


def remplacer_dans_paragraphe(p: etree._Element, motif: re.Pattern,
                              fonction: Callable[[re.Match], str]) -> int:
    """يستبدل كل تطابق للنمط في نص الفقرة، ولو امتد على عدة مقاطع. يعيد عدد الاستبدالات."""
    ts = _textes_propres(p)
    if not ts:
        return 0
    texte = "".join(t.text or "" for t in ts)
    matches = list(motif.finditer(texte))
    for m in reversed(matches):  # من اليمين حتى لا تتغير مواقع ما قبله
        _remplacer_span(ts, m.start(), m.end(), fonction(m))
    return len(matches)


def paragraphes(racine: etree._Element) -> Iterable[etree._Element]:
    return list(racine.iter(_q(W, "p")))


# ---------- قراءة وكتابة الملف ----------

def _lire_parties(chemin: Path | bytes) -> tuple[list[zipfile.ZipInfo], dict[str, bytes]]:
    source = io.BytesIO(chemin) if isinstance(chemin, bytes) else Path(chemin)
    with zipfile.ZipFile(source) as z:
        infos = z.infolist()
        contenus = {i.filename: z.read(i.filename) for i in infos}
    return infos, contenus


def _ecrire(infos, contenus: dict[str, bytes]) -> bytes:
    sortie = io.BytesIO()
    with zipfile.ZipFile(sortie, "w", zipfile.ZIP_DEFLATED) as z:
        for i in infos:
            z.writestr(i, contenus[i.filename])
    return sortie.getvalue()


def _xml(racine) -> bytes:
    return etree.tostring(racine, xml_declaration=True, encoding="UTF-8", standalone=True)


def champs_du_modele(chemin: Path | bytes) -> set[str]:
    """أسماء الحقول الموجودة في القالب."""
    _, contenus = _lire_parties(chemin)
    noms = set()
    for nom, data in contenus.items():
        if _PARTIES.match(nom):
            for p in paragraphes(etree.fromstring(data)):
                noms.update(MOTIF_CHAMP.findall(texte_paragraphe(p)))
    return noms


# ---------- الخانات (عدة تلاميذ في صفحة واحدة) ----------

def _supprimer_case(racine, nom_champ: str) -> None:
    """يحذف مربع النص الذي يحمل حقلاً فارغاً (خانة غير مستعملة في آخر صفحة)."""
    motif = re.compile(r"\{\{\s*" + re.escape(nom_champ) + r"\s*\}\}")
    for p in paragraphes(racine):
        if p.getparent() is None or not motif.search(texte_paragraphe(p)):
            continue
        ancre = None
        for a in p.iterancestors():
            if a.tag == _q(W, "r"):
                ancre = a  # أقرب مقطع يحمل مربع النص
                break
        if ancre is not None and ancre.getparent() is not None:
            ancre.getparent().remove(ancre)
        else:
            for t in _textes_propres(p):
                t.text = ""


def _dupliquer_pages(racine, n: int) -> list[list[etree._Element]]:
    """ينسخ محتوى المتن n مرة، كل نسخة في صفحة. يعيد عناصر كل صفحة."""
    body = racine.find(_q(W, "body"))
    enfants = list(body)
    sect = enfants[-1] if enfants and enfants[-1].tag == _q(W, "sectPr") else None
    contenu = [e for e in enfants if e is not sect]
    pages = [contenu]
    for _ in range(n - 1):
        saut = etree.Element(_q(W, "p"))
        r = etree.SubElement(saut, _q(W, "r"))
        etree.SubElement(r, _q(W, "br")).set(_q(W, "type"), "page")
        copies = [copy.deepcopy(e) for e in contenu]
        if sect is not None:
            sect.addprevious(saut)
            for c in copies:
                sect.addprevious(c)
        else:
            body.append(saut)
            body.extend(copies)
        pages.append(copies)
    # معرفات فريدة للرسومات، وحذف معرفات الفقرات المكررة
    for i, dp in enumerate(racine.iter(_q(WP, "docPr")), start=1):
        dp.set("id", str(i))
    if n > 1:
        for el in racine.iter():
            for att in (_q(W14, "paraId"), _q(W14, "textId")):
                if att in el.attrib:
                    del el.attrib[att]
    return pages


# ---------- الملء ----------

# قيمة خاصة: الفقرة التي تحمل هذا الحقل تُحذف كلها (أسطر اختيارية: مرفقات ورقة الإرسال...)
SUPPRIMER = "\ue000supprimer\ue000"
# قيمة خاصة: سطر الجدول الذي يحمل هذا الحقل يُحذف (أسطر التلاميذ غير المستعملة في المراسلة)
SUPPRIMER_LIGNE = "\ue000supprimer-ligne\ue000"


def _sauts_de_ligne(p: etree._Element) -> None:
    """"\n" في قيمة حقل ← سطر جديد داخل نفس الفقرة (w:br)."""
    for t in list(p.iter(_q(W, "t"))):
        if not t.text or "\n" not in t.text:
            continue
        morceaux = t.text.split("\n")
        t.text = morceaux[0]
        t.set(XML_SPACE, "preserve")
        apres = t
        for m in morceaux[1:]:
            br = etree.Element(_q(W, "br"))
            nt = etree.Element(_q(W, "t"))
            nt.text = m
            nt.set(XML_SPACE, "preserve")
            apres.addnext(br)
            br.addnext(nt)
            apres = nt


def _remplir_elements(elements, valeurs: dict[str, str], manquants: set[str]) -> None:
    def remplacement(m):
        nom = m.group(1)
        if nom not in valeurs or valeurs[nom] is None:
            manquants.add(nom)
            return m.group(0)
        return str(valeurs[nom]).replace("{{", "{ {")

    for el in elements:
        for p in paragraphes(el):
            remplacer_dans_paragraphe(p, MOTIF_CHAMP, remplacement)
            texte = texte_paragraphe(p)
            if SUPPRIMER in texte or SUPPRIMER_LIGNE in texte:
                tr = next(p.iterancestors(_q(W, "tr")), None) if SUPPRIMER_LIGNE in texte else None
                cible = tr if tr is not None else p
                if cible.getparent() is not None:
                    cible.getparent().remove(cible)
                continue
            _sauts_de_ligne(p)


def remplir(modele: Path | bytes, valeurs: dict[str, str],
            pages: list[dict[str, str]] | None = None) -> bytes:
    """يملأ القالب ويعيد محتوى ملف Word الناتج.

    valeurs: الحقول المشتركة (الترويسة، المؤسسة، التاريخ...).
    pages: لوثائق الخانات (الاستدعاءات): قائمة بحقول كل صفحة؛ الخانة غير الموجودة
           في صفحة ما يُحذف مربعها.
    يرفض النتيجة إذا بقي أي حقل دون قيمة.
    """
    infos, contenus = _lire_parties(modele)
    manquants: set[str] = set()
    for nom, data in list(contenus.items()):
        if not _PARTIES.match(nom):
            continue
        racine = etree.fromstring(data)
        if nom == "word/document.xml" and pages:
            groupes = _dupliquer_pages(racine, len(pages))
            cases = set()
            for p in paragraphes(racine):
                cases.update(c for c in MOTIF_CHAMP.findall(texte_paragraphe(p)) if MOTIF_CASE.match(c))
            for elements, vals_page in zip(groupes, pages):
                fusion = {**valeurs, **vals_page}
                for champ in cases - {k for k, v in fusion.items() if v}:
                    for e in elements:
                        _supprimer_case(e, champ)
                _remplir_elements(elements, fusion, manquants)
        else:
            _remplir_elements([racine], valeurs, manquants)
        contenus[nom] = _xml(racine)
    if manquants:
        raise ErreurModele("حقول بلا قيمة في القالب: " + "، ".join(sorted(manquants)))
    return _ecrire(infos, contenus)


def remplacer_litteral(modele: Path | bytes, remplacements: list[tuple[str, str]],
                       parties: str = "document") -> tuple[bytes, dict[str, int]]:
    """أداة إعداد القوالب: يستبدل نصوصاً حرفية بحقول. يعيد الملف وعدد مرات كل استبدال."""
    infos, contenus = _lire_parties(modele)
    compte = {a: 0 for a, _ in remplacements}
    for nom, data in list(contenus.items()):
        if not _PARTIES.match(nom) or not nom.startswith(f"word/{parties}"):
            continue
        racine = etree.fromstring(data)
        for ancien, nouveau in remplacements:
            motif = re.compile(re.escape(ancien))
            for p in paragraphes(racine):
                compte[ancien] += remplacer_dans_paragraphe(p, motif, lambda m, n=nouveau: n)
        contenus[nom] = _xml(racine)
    return _ecrire(infos, contenus), compte


def texte_complet(chemin: Path | bytes) -> str:
    """كل نص الوثيقة (للاختبارات والتحقق)، فقرة في كل سطر."""
    _, contenus = _lire_parties(chemin)
    lignes = []
    for nom in sorted(contenus):
        if _PARTIES.match(nom):
            for p in paragraphes(etree.fromstring(contenus[nom])):
                t = texte_paragraphe(p)
                if t.strip():
                    lignes.append(t)
    return "\n".join(lignes)


# ---------- ضبط الوثيقة في صفحة واحدة (طلب المدير 2026-11-09) ----------

MARGE_MAX = 680        # 1.2 سم (twips): الهامشان العلوي والسفلي
ENTETE_MAX = 284       # 0.5 سم: بُعد الترويسة والتذييل عن حافة الصفحة
TAILLE_VIDE = 12       # 6 نقط: حجم الأسطر الفارغة الفاصلة
INTERLIGNE_MAX = 276   # تباعد الأسطر 1.15
ESPACE_MAX = 120       # 6 نقط قبل الفقرة وبعدها


def _paragraphe_vide(p, saut_ok: bool = False) -> bool:
    """saut_ok: سطر لا يحمل إلا فاصل صفحة يُعد فارغاً (في آخر الوثيقة يصنع صفحة ثانية بيضاء)."""
    if any((t.text or "").strip() for t in p.iter(_q(W, "t"))):
        return False
    for tag in ((W, "drawing"), (W, "pict"), (MC, "AlternateContent"), (W, "object"), (W, "sectPr"),
                (W, "fldSimple"), (W, "instrText")):
        if next(p.iter(_q(*tag)), None) is not None:
            return False
    return saut_ok or not any(br.get(_q(W, "type")) == "page" for br in p.iter(_q(W, "br")))


def _resserrer(p) -> None:
    """سطر فارغ فاصل: يُصغَّر حجمه وتُلغى المسافات قبله وبعده."""
    ppr = p.find(_q(W, "pPr"))
    if ppr is None:
        ppr = etree.SubElement(p, _q(W, "pPr"))
        p.remove(ppr)
        p.insert(0, ppr)
    sp = ppr.find(_q(W, "spacing"))
    if sp is None:
        sp = etree.SubElement(ppr, _q(W, "spacing"))
    sp.set(_q(W, "before"), "0")
    sp.set(_q(W, "after"), "0")
    sp.set(_q(W, "line"), "240")
    sp.set(_q(W, "lineRule"), "auto")
    for conteneur in [ppr] + list(p.iter(_q(W, "r"))):
        rpr = conteneur.find(_q(W, "rPr"))
        if rpr is None:
            rpr = etree.SubElement(conteneur, _q(W, "rPr"))
            if conteneur.tag == _q(W, "r"):
                conteneur.remove(rpr)
                conteneur.insert(0, rpr)
        for tag in ("sz", "szCs"):
            e = rpr.find(_q(W, tag))
            if e is None:
                e = etree.SubElement(rpr, _q(W, tag))
            e.set(_q(W, "val"), str(TAILLE_VIDE))


def _a_cadres_flottants(body) -> bool:
    if next(body.iter(_q(MC, "AlternateContent")), None) is not None:
        return True
    if next(body.iter(_q(W, "pict")), None) is not None:
        return True
    return any(a.find(_q(WP, "docPr")) is None or a.find(_q(WP, "docPr")).get("name") != "IDARA_ENTETE"
               for a in body.iter(_q(WP, "anchor")))


def compacter(contenu: bytes) -> bytes:
    """يضبط وثيقة من صفحة واحدة حتى لا تنتقل آخر أسطرها إلى صفحة ثانية في Word:
    هامشان علوي وسفلي لا يتجاوزان 1.2 سم، وترويسة وتذييل قريبان من الحافة، وحذف الأسطر الفارغة في آخر
    الوثيقة، وتصغير الأسطر الفارغة الفاصلة داخلها، وتباعد أسطر لا يتجاوز 1.15. لا يمس النصوص ولا الصور."""
    infos, contenus = _lire_parties(contenu)
    racine = etree.fromstring(contenus["word/document.xml"])
    body = racine.find(_q(W, "body"))
    for sect in racine.iter(_q(W, "sectPr")):
        mar = sect.find(_q(W, "pgMar"))
        if mar is None:
            continue
        for att, maxi in (("top", MARGE_MAX), ("bottom", MARGE_MAX), ("header", ENTETE_MAX), ("footer", ENTETE_MAX)):
            v = mar.get(_q(W, att))
            if v is not None and v.lstrip("-").isdigit() and abs(int(v)) > maxi:
                mar.set(_q(W, att), str(maxi if int(v) > 0 else -maxi))
    enfants = [e for e in body if e.tag != _q(W, "sectPr")]
    # الأسطر الفارغة في آخر الوثيقة (يبقى سطر واحد بعد جدول، فـWord يشترطه)
    while enfants and enfants[-1].tag == _q(W, "p") and _paragraphe_vide(enfants[-1], saut_ok=True):
        if len(enfants) > 1 and enfants[-2].tag == _q(W, "tbl"):
            _resserrer(enfants[-1])
            break
        body.remove(enfants.pop())
    # الأسطر الفارغة الفاصلة وتباعد الأسطر: فقط في الوثائق دون إطارات نصية عائمة، لأن مواضع تلك الإطارات
    # مرتبطة بالأسطر الفارغة (محضر الاستئناف مثلاً)
    if _a_cadres_flottants(body):
        contenus["word/document.xml"] = _xml(racine)
        return _ecrire(infos, contenus)
    for e in enfants:
        if e.tag == _q(W, "p") and _paragraphe_vide(e):
            _resserrer(e)
    # تباعد الأسطر لا يتجاوز 1.15، والمسافة بعد الفقرة لا تتجاوز 6 نقط
    for sp in body.iter(_q(W, "spacing")):
        if sp.get(_q(W, "lineRule"), "auto") == "auto" and int(sp.get(_q(W, "line"), "0") or 0) > INTERLIGNE_MAX:
            sp.set(_q(W, "line"), str(INTERLIGNE_MAX))
        for att in ("after", "before"):
            v = sp.get(_q(W, att))
            if v and v.isdigit() and int(v) > ESPACE_MAX:
                sp.set(_q(W, att), str(ESPACE_MAX))
    contenus["word/document.xml"] = _xml(racine)
    return _ecrire(infos, contenus)
