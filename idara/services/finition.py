"""إنهاء الوثائق قبل عرضها (طلب المدير 2026-11-15).

1. `nettoyer_marques`: علامات عزل الاتجاه (U+2066 … U+2069) التي نحيط بها الأرقام والتواريخ كانت تظهر في Word
   مربعات مكتوب فيها «LRI» و«PDI». نحذفها ونضع النص المعزول في مقطع (run) من اليسار إلى اليمين: نفس العرض
   دون أي حرف دخيل.
2. `en_html`: تحويل الوثيقة إلى HTML بسيط يفهمه محرر البرنامج (فقرات، جداول بخلايا مدمجة وتظليل، صور).
"""

from __future__ import annotations

import base64
import copy
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from html import escape
from pathlib import Path

from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
XML = "http://www.w3.org/XML/1998/namespace"

DEBUT, FIN = "⁦", "⁩"
_AUTRES = "⁧⁨‪‫‬‭‮"   # علامات اتجاه أخرى: تُحذف فقط
_PARTIES = re.compile(r"word/(document|header\d*|footer\d*)\.xml$")


def _q(tag: str) -> str:
    return f"{{{W}}}{tag}"


def sans_marques(texte: str) -> str:
    return texte.translate({ord(c): None for c in DEBUT + FIN + _AUTRES})


def _segments(texte: str) -> list[tuple[str, bool]]:
    """يقسم النص إلى (مقطع، معزول؟). العلامات نفسها تُحذف."""
    res, courant, niveau = [], "", 0
    for c in texte:
        if c == DEBUT:
            if niveau == 0 and courant:
                res.append((courant, False))
                courant = ""
            niveau += 1
        elif c == FIN:
            if niveau == 1 and courant:
                res.append((courant, True))
                courant = ""
            niveau = max(0, niveau - 1)
        elif c not in _AUTRES:
            courant += c
    if courant:
        res.append((courant, niveau > 0))
    return res


def _nettoyer_xml(racine) -> bool:
    change = False
    for r in list(racine.iter(_q("r"))):
        ts = r.findall(_q("t"))
        if not any(any(c in (t.text or "") for c in DEBUT + FIN + _AUTRES) for t in ts):
            continue
        change = True
        if len(r) - (1 if r.find(_q("rPr")) is not None else 0) != len(ts) or len(ts) != 1:
            for t in ts:   # مقطع مركّب (فواصل، صور): نحذف العلامات دون تقسيم
                t.text = sans_marques(t.text or "")
            continue
        parent, pos = r.getparent(), r.getparent().index(r)
        parent.remove(r)
        for k, (seg, isole) in enumerate(_segments(ts[0].text or "")):
            n = copy.deepcopy(r)
            t = n.find(_q("t"))
            t.text = seg
            t.set(f"{{{XML}}}space", "preserve")
            if isole:
                rpr = n.find(_q("rPr"))
                if rpr is not None:
                    for e in rpr.findall(_q("rtl")):
                        rpr.remove(e)
            parent.insert(pos + k, n)
    return change


def nettoyer_marques(chemin: Path) -> bool:
    """يحذف علامات العزل من وثيقة Word محفوظة. يرجع True إن تغيّر الملف. لا يمس غير ‎.docx‎."""
    chemin = Path(chemin)
    if chemin.suffix.lower() != ".docx" or not chemin.exists():
        return False
    change = False
    with zipfile.ZipFile(chemin) as z:
        contenus = {i.filename: z.read(i.filename) for i in z.infolist()}
        infos = z.infolist()
    for nom, brut in contenus.items():
        if not _PARTIES.search(nom) or not any(m.encode() in brut for m in DEBUT + FIN + _AUTRES):
            continue
        racine = etree.fromstring(brut)
        if _nettoyer_xml(racine):
            contenus[nom] = etree.tostring(racine, xml_declaration=True, encoding="UTF-8", standalone=True)
            change = True
    if not change:
        return False
    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx", dir=chemin.parent) as tmp:
        tmp_chemin = Path(tmp.name)
    try:
        with zipfile.ZipFile(tmp_chemin, "w", zipfile.ZIP_DEFLATED) as z:
            for i in infos:
                z.writestr(i, contenus[i.filename])
        shutil.move(str(tmp_chemin), str(chemin))
    finally:
        tmp_chemin.unlink(missing_ok=True)
    return True


# ====================== DOCX → HTML ======================

@dataclass
class Page:
    html: str
    paysage: bool
    largeur_mm: float
    hauteur_mm: float
    marges_mm: tuple[float, float, float, float]   # يسار، أعلى، يمين، أسفل


_MIME = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "gif": "image/gif", "bmp": "image/bmp"}


class _Convertisseur:
    def __init__(self, z: zipfile.ZipFile):
        self.z = z
        self.police, self.taille = "Sakkal Majalla", 15.0

    def _rels(self, partie: str) -> dict[str, str]:
        nom = f"word/_rels/{Path(partie).name}.rels"
        if nom not in self.z.namelist():
            return {}
        return {e.get("Id"): e.get("Target") for e in etree.fromstring(self.z.read(nom))}

    def _image(self, r, rels) -> str:
        res = ""
        for blip in r.iter(f"{{{A}}}blip"):
            cible = rels.get(blip.get(f"{{{R}}}embed"), "")
            nom = "word/" + cible.lstrip("/").removeprefix("word/")
            if nom not in self.z.namelist():
                continue
            mime = _MIME.get(Path(nom).suffix.lower().lstrip("."))
            if not mime:
                continue
            ext = next(r.iter(f"{{{WP}}}extent"), None)
            larg = round(int(ext.get("cx")) / 9525) if ext is not None else 0   # EMU → بكسل (96 نقطة/بوصة)
            data = base64.b64encode(self.z.read(nom)).decode()
            res += f'<img src="data:{mime};base64,{data}"' + (f' width="{larg}"' if larg else "") + "/>"
        return res

    def _run(self, r, rels) -> str:
        rpr = r.find(_q("rPr"))
        styles = []
        if rpr is not None:
            sz = rpr.find(_q("szCs")) if rpr.find(_q("szCs")) is not None else rpr.find(_q("sz"))
            if sz is not None and (sz.get(_q("val")) or "").isdigit():
                styles.append(f"font-size:{int(sz.get(_q('val'))) / 2:g}pt")
            coul = rpr.find(_q("color"))
            if coul is not None and re.fullmatch(r"[0-9A-Fa-f]{6}", coul.get(_q("val")) or ""):
                styles.append(f"color:#{coul.get(_q('val'))}")

            def actif(nom):
                e = rpr.find(_q(nom))
                return e is not None and e.get(_q("val")) not in ("0", "false", "none")
            if actif("b") or actif("bCs"):
                styles.append("font-weight:bold")
            if actif("u"):
                styles.append("text-decoration:underline")
            if actif("i") or actif("iCs"):
                styles.append("font-style:italic")
        corps = ""
        for e in r:
            if e.tag == _q("t"):
                corps += escape(sans_marques(e.text or ""))
            elif e.tag == _q("tab"):
                corps += "&nbsp;&nbsp;&nbsp;&nbsp;"
            elif e.tag == _q("br"):
                corps += "" if e.get(_q("type")) == "page" else "<br/>"
            elif e.tag == _q("drawing"):
                corps += self._image(e, rels)
        if not corps:
            return ""
        return f'<span style="{";".join(styles)}">{corps}</span>' if styles else corps

    def _para(self, p, rels, dans_cellule=False) -> str:
        ppr = p.find(_q("pPr"))
        aligne, apres, saut = "right", None, False
        if ppr is not None:
            jc = ppr.find(_q("jc"))
            if jc is not None:
                aligne = {"center": "center", "both": "justify", "left": "right", "start": "right",
                          "right": "left", "end": "left"}.get(jc.get(_q("val")), "right")
            sp = ppr.find(_q("spacing"))
            if sp is not None and (sp.get(_q("after")) or "").isdigit():
                apres = int(sp.get(_q("after"))) / 20
            saut = ppr.find(_q("pageBreakBefore")) is not None
        saut = saut or any(b.get(_q("type")) == "page" for b in p.iter(_q("br")))
        corps = "".join(self._run(r, rels) for r in p.iter(_q("r")))
        style = f"margin-top:0;margin-bottom:{(apres if apres is not None else (0 if dans_cellule else 6)):g}pt"
        if saut:
            style += ";page-break-before:always"
        return f'<p dir="rtl" align="{aligne}" style="{style}">{corps or "&nbsp;"}</p>'

    def _table(self, t, rels) -> str:
        grille = [int(g.get(_q("w")) or 0) for g in t.iter(_q("gridCol")) if g.getparent().getparent() is t]
        total = sum(grille) or 1
        tblpr = t.find(_q("tblPr"))
        visuel_rtl = tblpr is not None and tblpr.find(_q("bidiVisual")) is not None
        bordures = tblpr is not None and tblpr.find(_q("tblBorders")) is not None
        lignes = []   # لكل سطر: [dict(col, span, vmerge, cellule)]
        for tr in t.findall(_q("tr")):
            col, ligne = 0, []
            for tc in tr.findall(_q("tc")):
                tcpr = tc.find(_q("tcPr"))
                span, vm, fond = 1, None, None
                if tcpr is not None:
                    gs = tcpr.find(_q("gridSpan"))
                    span = int(gs.get(_q("val"))) if gs is not None else 1
                    v = tcpr.find(_q("vMerge"))
                    vm = (v.get(_q("val")) or "continue") if v is not None else None
                    shd = tcpr.find(_q("shd"))
                    if shd is not None and re.fullmatch(r"[0-9A-Fa-f]{6}", shd.get(_q("fill")) or ""):
                        fond = shd.get(_q("fill"))
                ligne.append({"col": col, "span": span, "vm": vm, "fond": fond, "tc": tc, "rows": 1})
                col += span
            lignes.append(ligne)
        for i, ligne in enumerate(lignes):   # الدمج العمودي → rowspan
            for c in ligne:
                if c["vm"] == "restart":
                    for suiv in lignes[i + 1:]:
                        bas = next((x for x in suiv if x["col"] == c["col"] and x["vm"] == "continue"), None)
                        if bas is None:
                            break
                        c["rows"] += 1
        html = (f'<table dir="ltr" width="100%" cellspacing="0" cellpadding="4" border="{1 if bordures else 0}" '
                'style="border-collapse:collapse;margin-top:2pt;margin-bottom:6pt">')
        for ligne in lignes:
            cellules = [c for c in ligne if c["vm"] != "continue"]
            if visuel_rtl:
                cellules = cellules[::-1]
            html += "<tr>"
            for c in cellules:
                larg = sum(grille[c["col"]:c["col"] + c["span"]]) if grille else 0
                attrs = (f' colspan="{c["span"]}"' if c["span"] > 1 else "") + \
                        (f' rowspan="{c["rows"]}"' if c["rows"] > 1 else "") + \
                        (f' width="{round(100 * larg / total)}%"' if larg else "") + \
                        (f' bgcolor="#{c["fond"]}"' if c["fond"] else "")
                html += f'<td{attrs} valign="middle">{self._blocs(c["tc"], rels, True)}</td>'
            html += "</tr>"
        return html + "</table>"

    def _blocs(self, conteneur, rels, dans_cellule=False) -> str:
        res = ""
        for e in conteneur:
            if e.tag == _q("p"):
                res += self._para(e, rels, dans_cellule)
            elif e.tag == _q("tbl"):
                res += self._table(e, rels)
        return res

    def convertir(self) -> Page:
        doc = etree.fromstring(self.z.read("word/document.xml"))
        corps = doc.find(_q("body"))
        rels = self._rels("document.xml")
        if "word/styles.xml" in self.z.namelist():
            st = etree.fromstring(self.z.read("word/styles.xml"))
            for s in st.iter(_q("style")):
                if s.get(_q("default")) == "1" and s.get(_q("type")) == "paragraph":
                    f = next(s.iter(_q("rFonts")), None)
                    if f is not None and (f.get(_q("cs")) or f.get(_q("ascii"))):
                        self.police = f.get(_q("cs")) or f.get(_q("ascii"))
                    z = next(s.iter(_q("szCs")), None) or next(s.iter(_q("sz")), None)
                    if z is not None and (z.get(_q("val")) or "").isdigit():
                        self.taille = int(z.get(_q("val"))) / 2
        sect = corps.find(_q("sectPr"))
        larg, haut, marges = 210.0, 297.0, (18.0, 15.0, 18.0, 15.0)
        haut_page = bas_page = ""
        if sect is not None:
            pg = sect.find(_q("pgSz"))
            if pg is not None:
                larg, haut = int(pg.get(_q("w"))) / 56.6929, int(pg.get(_q("h"))) / 56.6929   # twip → مم
            mar = sect.find(_q("pgMar"))
            if mar is not None:
                marges = tuple(int(mar.get(_q(k)) or 0) / 56.6929 for k in ("left", "top", "right", "bottom"))
            for ref, cote in ((sect.find(_q("headerReference")), "h"), (sect.find(_q("footerReference")), "f")):
                if ref is None:
                    continue
                cible = rels.get(ref.get(f"{{{R}}}id"), "")
                nom = "word/" + cible
                if nom in self.z.namelist():
                    bloc = self._blocs(etree.fromstring(self.z.read(nom)), self._rels(cible))
                    if re.sub(r"<[^>]+>|&nbsp;|\s", "", bloc) or "<img" in bloc:
                        if cote == "h":
                            haut_page = bloc
                        else:
                            bas_page = bloc
        html = (f'<html dir="rtl"><body dir="rtl" style="font-family:\'{self.police}\';font-size:{self.taille:g}pt">'
                f"{haut_page}{self._blocs(corps, rels)}{bas_page}</body></html>")
        return Page(html, larg > haut, round(larg, 1), round(haut, 1), tuple(round(m, 1) for m in marges))


def en_html(chemin: Path) -> Page:
    """وثيقة Word → صفحة HTML لمحرر البرنامج. ما لا يُنقل: إطارات الصفحة، مربعات النص، الصور العائمة."""
    with zipfile.ZipFile(chemin) as z:
        return _Convertisseur(z).convertir()
