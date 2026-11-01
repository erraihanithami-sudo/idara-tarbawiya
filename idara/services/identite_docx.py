"""تطبيق الهوية البصرية للمؤسسة على الوثائق المولدة.

ما يُعوَّض (فقط إذا حدده المدير في إعداد المؤسسة):
- الترويسة: الصورة الموسومة IDARA_ENTETE في القالب تُعوَّض بصورة المؤسسة، في نفس مكانها،
  مع الحفاظ على نسبة أبعاد الصورة.
- العلامة المائية: علامة Word المائية في الترويسات تُعوَّض بصورة المؤسسة (بنفس التخفيف)،
  وتُضاف إلى الترويسة الافتراضية إن لم يكن للقالب علامة.
- التذييل: الصورة الموسومة IDARA_PIED تُعوَّض بنص التذييل.
القالب المحفوظ لا يتغير؛ التعويض يتم على الوثيقة المولدة فقط.
"""

from __future__ import annotations

import hashlib
import posixpath
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

from lxml import etree

from idara.services.moteur_docx import W, WP, _ecrire, _lire_parties, _xml

A = "http://schemas.openxmlformats.org/drawingml/2006/main"
PIC = "http://schemas.openxmlformats.org/drawingml/2006/picture"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
V = "urn:schemas-microsoft-com:vml"
PR = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
TYPE_IMAGE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"

ETIQUETTE_ENTETE = "IDARA_ENTETE"
ETIQUETTE_DECOR = "IDARA_ENTETE_DECOR"  # زخرفة مرافقة للترويسة الأصلية (خط، إطار)
ETIQUETTE_PIED = "IDARA_PIED"
ETIQUETTE_FILIGRANE = "IDARA_FILIGRANE"

EMU_CM = 360000
HAUTEUR_MAX_ENTETE = int(3.2 * EMU_CM)       # لا تتجاوز الترويسة 3.2 سم
CADRE_FILIGRANE = (int(14 * EMU_CM), int(14 * EMU_CM))  # للقوالب التي لا علامة لها

_PARTIE = re.compile(r"^word/(document|header\d+|footer\d+)\.xml$")


def q(ns: str, tag: str) -> str:
    return f"{{{ns}}}{tag}"


@dataclass(frozen=True)
class Image:
    png: bytes
    largeur: int  # بالبكسل
    hauteur: int

    @staticmethod
    def depuis_fichier(chemin: Path) -> "Image":
        """يقرأ أي صورة (PNG/JPG/BMP/GIF) ويحولها إلى PNG."""
        import io

        from PIL import Image as PILImage
        with PILImage.open(chemin) as im:
            im.load()
            if im.mode not in ("RGB", "RGBA"):
                im = im.convert("RGBA")
            sortie = io.BytesIO()
            im.save(sortie, "PNG")
            return Image(sortie.getvalue(), im.width, im.height)


def ajuster(largeur_px: int, hauteur_px: int, cadre_cx: int, cadre_cy: int) -> tuple[int, int]:
    """أكبر حجم يدخل في الإطار مع الحفاظ على نسبة الأبعاد (بوحدة EMU)."""
    echelle = min(cadre_cx / largeur_px, cadre_cy / hauteur_px)
    return int(largeur_px * echelle), int(hauteur_px * echelle)


# ---------- الحزمة: الصور والعلاقات وأنواع المحتوى ----------

class Paquet:
    def __init__(self, contenu: bytes):
        self.infos, self.c = _lire_parties(contenu)
        self._medias: dict[bytes, str] = {}

    def _ajouter(self, nom: str, data: bytes) -> None:
        if nom not in self.c:
            self.infos.append(zipfile.ZipInfo(nom))
        self.c[nom] = data

    def media(self, png: bytes) -> str:
        if png not in self._medias:
            nom = f"word/media/idara_{hashlib.sha1(png).hexdigest()[:10]}.png"
            self._ajouter(nom, png)
            self._medias[png] = nom
            self._type_png()
        return self._medias[png]

    def _type_png(self) -> None:
        racine = etree.fromstring(self.c["[Content_Types].xml"])
        if not any(d.get("Extension", "").lower() == "png" for d in racine.iter(q(CT, "Default"))):
            etree.SubElement(racine, q(CT, "Default"), Extension="png", ContentType="image/png")
            self.c["[Content_Types].xml"] = _xml(racine)

    @staticmethod
    def chemin_rels(partie: str) -> str:
        d, f = posixpath.split(partie)
        return f"{d}/_rels/{f}.rels"

    def relations(self, partie: str) -> etree._Element:
        nom = self.chemin_rels(partie)
        if nom in self.c:
            return etree.fromstring(self.c[nom])
        return etree.Element(q(PR, "Relationships"), nsmap={None: PR})

    def ajouter_relation(self, partie: str, media: str) -> str:
        rels = self.relations(partie)
        cible = posixpath.relpath(media, posixpath.dirname(partie))
        for r in rels:
            if r.get("Target") == cible and r.get("Type") == TYPE_IMAGE:
                return r.get("Id")
        existants = {r.get("Id") for r in rels}
        n = 1
        while f"rIdIdara{n}" in existants:
            n += 1
        rid = f"rIdIdara{n}"
        etree.SubElement(rels, q(PR, "Relationship"), Id=rid, Type=TYPE_IMAGE, Target=cible)
        self._ajouter(self.chemin_rels(partie), _xml(rels))
        return rid

    def cible(self, partie: str, rid: str) -> str | None:
        for r in self.relations(partie):
            if r.get("Id") == rid:
                return posixpath.normpath(posixpath.join(posixpath.dirname(partie), r.get("Target")))
        return None

    def parties_section(self) -> tuple[str | None, str | None, list[str]]:
        """الترويسة والتذييل الافتراضيان للقسم الأخير، وكل ترويسات كل الأقسام."""
        doc = etree.fromstring(self.c["word/document.xml"])
        sects = list(doc.iter(q(W, "sectPr")))
        if not sects:
            return None, None, []
        defaut = {}
        toutes = []
        for i, sect in enumerate(sects):  # قد تتعدد الأقسام (لكل نسخة من الشهادة قسمها)
            for tag in ("headerReference", "footerReference"):
                for ref in sect.findall(q(W, tag)):
                    cible = self.cible("word/document.xml", ref.get(q(R, "id")))
                    if not cible:
                        continue
                    if tag == "headerReference" and cible not in toutes:
                        toutes.append(cible)
                    if i == len(sects) - 1 and ref.get(q(W, "type")) == "default":
                        defaut[tag] = cible
        return defaut.get("headerReference"), defaut.get("footerReference"), toutes

    def resultat(self) -> bytes:
        return _ecrire(self.infos, self.c)


# ---------- عناصر الرسم ----------

def _dessins_etiquetes(racine, etiquette: str):
    for dp in racine.iter(q(WP, "docPr")):
        if dp.get("name") == etiquette:
            yield dp.getparent()  # wp:anchor أو wp:inline


def _remplacer_image(conteneur, rid: str, image: Image, cadre_cy_max: int) -> None:
    ext = conteneur.find(q(WP, "extent"))
    cx0, cy0 = int(ext.get("cx")), int(ext.get("cy"))
    cx, cy = ajuster(image.largeur, image.hauteur, cx0, max(cy0, cadre_cy_max))
    ext.set("cx", str(cx))
    ext.set("cy", str(cy))
    for e in conteneur.iter(q(A, "ext")):
        if e.getparent().tag == q(A, "xfrm"):
            e.set("cx", str(cx))
            e.set("cy", str(cy))
    blip = next(conteneur.iter(q(A, "blip")))
    blip.set(q(R, "embed"), rid)
    for src in list(conteneur.iter(q(A, "srcRect"))):
        src.getparent().remove(src)
    # الإحاطة القديمة تتبع حدود الصورة الأصلية (wrapPolygon) فتقص الصورة الجديدة:
    # نعوضها بإحاطة "أعلى وأسفل" التي تدفع النص تحت الصورة مهما كان ارتفاعها
    for tag in ("wrapTight", "wrapThrough", "wrapSquare", "wrapNone", "wrapTopAndBottom"):
        ancien = conteneur.find(q(WP, tag))
        if ancien is not None:
            ancien.addprevious(etree.Element(q(WP, "wrapTopAndBottom")))
            conteneur.remove(ancien)
    if conteneur.tag == q(WP, "anchor"):
        conteneur.set("behindDoc", "0")
    pos_h = conteneur.find(q(WP, "positionH"))
    if pos_h is not None:  # توسيط أفقي في نفس الإطار
        for e in list(pos_h):
            pos_h.remove(e)
        etree.SubElement(pos_h, q(WP, "align")).text = "center"


def _ancre_filigrane(rid: str, cx: int, cy: int, id_dessin: int) -> etree._Element:
    xml = f"""<w:r xmlns:w="{W}" xmlns:wp="{WP}" xmlns:a="{A}" xmlns:pic="{PIC}" xmlns:r="{R}">
<w:rPr><w:noProof/></w:rPr><w:drawing>
<wp:anchor distT="0" distB="0" distL="0" distR="0" simplePos="0" relativeHeight="251640000"
 behindDoc="1" locked="0" layoutInCell="1" allowOverlap="1">
<wp:simplePos x="0" y="0"/>
<wp:positionH relativeFrom="margin"><wp:align>center</wp:align></wp:positionH>
<wp:positionV relativeFrom="margin"><wp:align>center</wp:align></wp:positionV>
<wp:extent cx="{cx}" cy="{cy}"/><wp:effectExtent l="0" t="0" r="0" b="0"/><wp:wrapNone/>
<wp:docPr id="{id_dessin}" name="{ETIQUETTE_FILIGRANE}"/>
<wp:cNvGraphicFramePr><a:graphicFrameLocks noChangeAspect="1"/></wp:cNvGraphicFramePr>
<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
<pic:pic><pic:nvPicPr><pic:cNvPr id="0" name="filigrane.png"/><pic:cNvPicPr/></pic:nvPicPr>
<pic:blipFill><a:blip r:embed="{rid}"><a:lum bright="70000" contrast="-70000"/></a:blip>
<a:stretch><a:fillRect/></a:stretch></pic:blipFill>
<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>
<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic>
</a:graphicData></a:graphic></wp:anchor></w:drawing></w:r>"""
    return etree.fromstring(xml)


def _cadre_vml(shape) -> tuple[int, int]:
    style = dict(p.split(":", 1) for p in shape.get("style", "").split(";") if ":" in p)

    def emu(v: str) -> int:
        v = v.strip()
        if v.endswith("pt"):
            return int(float(v[:-2]) * 12700)
        if v.endswith("in"):
            return int(float(v[:-2]) * 914400)
        return 0
    cx, cy = emu(style.get("width", "")), emu(style.get("height", ""))
    return (cx, cy) if cx and cy else CADRE_FILIGRANE


def _retirer_filigranes_vml(racine) -> tuple[int, int] | None:
    """يحذف علامة Word المائية القديمة ويعيد إطارها."""
    cadre = None
    for shape in list(racine.iter(q(V, "shape"))):
        if not (shape.get("id") or "").startswith("WordPictureWatermark"):
            continue
        cadre = cadre or _cadre_vml(shape)
        run = next((a for a in shape.iterancestors(q(W, "r"))), None)
        if run is not None and run.getparent() is not None:
            run.getparent().remove(run)
    return cadre


def _retirer_decor_vml(racine) -> None:
    """يحذف الخطوط والأشكال الزخرفية القديمة المرافقة للترويسة (دون العلامة المائية)،
    لأنها صُممت لمقاس الترويسة الأصلية وتتقاطع مع الترويسة الجديدة."""
    for pict in list(racine.iter(q(W, "pict"))):
        if any((s.get("id") or "").startswith("WordPictureWatermark") for s in pict.iter(q(V, "shape"))):
            continue
        run = next((a for a in pict.iterancestors(q(W, "r"))), None)
        if run is not None and run.getparent() is not None:
            run.getparent().remove(run)


def _premier_paragraphe(racine):
    p = racine.find(q(W, "p"))
    if p is None:
        p = etree.SubElement(racine, q(W, "p"))
    return p


def _id_libre(racine) -> int:
    ids = [int(d.get("id")) for d in racine.iter(q(WP, "docPr")) if (d.get("id") or "").isdigit()]
    return max(ids, default=0) + 1000


def _paragraphe_texte(texte: str) -> etree._Element:
    p = etree.Element(q(W, "p"))
    ppr = etree.SubElement(p, q(W, "pPr"))
    etree.SubElement(ppr, q(W, "bidi"))
    etree.SubElement(ppr, q(W, "jc")).set(q(W, "val"), "center")
    r = etree.SubElement(p, q(W, "r"))
    rpr = etree.SubElement(r, q(W, "rPr"))
    etree.SubElement(rpr, q(W, "rtl"))
    etree.SubElement(rpr, q(W, "sz")).set(q(W, "val"), "18")
    etree.SubElement(rpr, q(W, "szCs")).set(q(W, "val"), "18")
    t = etree.SubElement(r, q(W, "t"))
    t.text = texte
    return p


# ---------- التطبيق ----------

def appliquer_identite(contenu: bytes, entete: Image | None = None,
                       filigrane: Image | None = None, pied: str = "") -> bytes:
    if not (entete or filigrane or pied):
        return contenu
    pk = Paquet(contenu)
    entete_defaut, pied_defaut, entetes = pk.parties_section()
    racines = {n: etree.fromstring(d) for n, d in pk.c.items() if _PARTIE.match(n)}
    filigrane_pose = False
    pied_pose = False

    for nom, racine in racines.items():
        if entete:
            conteneurs = list(_dessins_etiquetes(racine, ETIQUETTE_ENTETE))
            for conteneur in conteneurs:
                rid = pk.ajouter_relation(nom, pk.media(entete.png))
                _remplacer_image(conteneur, rid, entete, HAUTEUR_MAX_ENTETE)
            if conteneurs and nom in entetes:
                _retirer_decor_vml(racine)
            for conteneur in list(_dessins_etiquetes(racine, ETIQUETTE_DECOR)):
                run = next(conteneur.iterancestors(q(W, "r")))
                run.getparent().remove(run)
        if filigrane and nom in entetes:
            cadre = _retirer_filigranes_vml(racine)
            if cadre:
                rid = pk.ajouter_relation(nom, pk.media(filigrane.png))
                cx, cy = ajuster(filigrane.largeur, filigrane.hauteur, *cadre)
                _premier_paragraphe(racine).append(_ancre_filigrane(rid, cx, cy, _id_libre(racine)))
                filigrane_pose = True
        if pied:
            for conteneur in list(_dessins_etiquetes(racine, ETIQUETTE_PIED)):
                run = next(conteneur.iterancestors(q(W, "r")))
                p = next(run.iterancestors(q(W, "p")))
                run.getparent().remove(run)
                p.addnext(_paragraphe_texte(pied))
                pied_pose = True

    if filigrane and not filigrane_pose and entete_defaut in racines:
        racine = racines[entete_defaut]
        rid = pk.ajouter_relation(entete_defaut, pk.media(filigrane.png))
        cx, cy = ajuster(filigrane.largeur, filigrane.hauteur, *CADRE_FILIGRANE)
        _premier_paragraphe(racine).append(_ancre_filigrane(rid, cx, cy, _id_libre(racine)))
    if pied and not pied_pose and pied_defaut in racines:
        racines[pied_defaut].append(_paragraphe_texte(pied))

    for nom, racine in racines.items():
        pk.c[nom] = _xml(racine)
    return pk.resultat()
