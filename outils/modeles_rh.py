"""يبني قوالب محاضر الموارد البشرية (طلب المدير 2026-11-09) على نماذجه:
- pv_prise_service: محضر الالتحاق بالعمل (فردي، 12 حالة).
- pv_entree_sortie: محضر الدخول / الخروج (جماعي، 10 موظفين في الصفحة).
- pv_non_signataires: لائحة من لم يوقعوا المحضر.

الترويسة صورة باسم IDARA_ENTETE (تعوضها ترويسة المؤسسة عند التوليد)، مأخوذة من قالب محضر الاستئناف.
الاستعمال: python outils/modeles_rh.py
"""

from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from docx.enum.text import WD_ALIGN_PARAGRAPH  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402
from docx.shared import Cm, Pt  # noqa: E402

from idara.services.docs_association import _bordures, _cellule, _nouveau, _ombre, para, tableau  # noqa: E402

MODELES = RACINE / "idara" / "resources" / "modeles"
CAS = ["التعيين الجديد (2)", "التخرج من مراكز التكوين", "التخرج من مراكز المفتشين",
       "التخرج من المدرسة الوطنية للإدارة العمومية", "التخرج من مراكز تكوين المستشارين", "الانتقال",
       "تغيير الإطار", "إنهاء الإيداع الإداري", "إنهاء الإلحاق", "إنهاء رخصة طويلة الأمد",
       "استئناف العمل بعد مرض عادي", "تكليف بمهمة"]
LIGNES_PAGE = 10
LIGNES_NON_SIGNATAIRES = 10


def _image_entete() -> bytes:
    with zipfile.ZipFile(MODELES / "pv_reprise.docx") as z:
        return z.read("word/media/image2.png")


def _entete(d, largeur_cm: float) -> None:
    p = d.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    run.add_picture(io.BytesIO(_image_entete()), width=Cm(largeur_cm))
    for dp in p._p.iter(qn("wp:docPr")):
        dp.set("name", "IDARA_ENTETE")
    p.paragraph_format.space_after = Pt(4)


def _titre_encadre(d, texte: str, taille=18, largeur=9.0) -> None:
    t = tableau(d, 1, 1, largeurs=[largeur])
    t.alignment = 1
    _cellule(t.cell(0, 0), texte, gras=True, taille=taille)
    para(d, "", apres=4)


def pv_prise_service() -> Path:
    d = _nouveau()
    _entete(d, 16)
    _titre_encadre(d, "محضر الالتحاق بالعمل")
    t = tableau(d, 1, 1, largeurs=[17.5])
    c = t.cell(0, 0)
    c.paragraphs[0].text = ""
    lignes = [
        ("{{ana_mouwaqqi}}: {{directeur}}", True),
        ("بصفتي: {{mudir_moassasa}}", False),
        ("أشهد بأن {{sayyid}}: {{nom_complet}}          رقم التأجير: {{ppr}}", True),
        ("ر. ب. ت. و: {{cin}}", True),
        ("تاريخ ومكان الازدياد: {{naissance}}", True),
        ("الإطار: {{cadre}}", True),
        ("المهمة: {{mission}}", True),
        ("قد {{hadara}} بهذه المؤسسة بتاريخ: {{date_prise}}", True),
        ("مراجع الرسالة الوزارية (1): {{reference}}", True),
        ("مقر العمل السابق: {{ancien_lieu}}", True),
        ("العنوان الشخصي: {{adresse}}", True),
    ]
    for i, (txt, gras) in enumerate(lignes):
        p = c.paragraphs[0] if i == 0 else c.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        from idara.services.docs_association import _bidi, _rtl_run
        _bidi(p)
        _rtl_run(p.add_run(txt), gras=gras, taille=13)
        p.paragraph_format.space_after = Pt(5)
    para(d, "", apres=4)
    para(d, "حرر في: {{ville}}، بتاريخ: {{date_redaction}}                              "
            "توقيع {{al_mouani}} بالأمر:", taille=12, apres=10)
    t = tableau(d, 1 + 7, 4, largeurs=[1.0, 7.6, 1.0, 7.6])
    a = t.cell(0, 0).merge(t.cell(0, 3))
    _cellule(a, "مختلف الحالات", gras=True, taille=12)
    _ombre(a)
    gauche, droite = CAS[:7], CAS[7:]
    for i in range(7):
        _cellule(t.cell(i + 1, 0), "{{cas_%d}}" % (i + 1), taille=13)
        _cellule(t.cell(i + 1, 1), gauche[i], taille=11, centre=False)
        if i < len(droite):
            _cellule(t.cell(i + 1, 2), "{{cas_%d}}" % (i + 8), taille=13)
            _cellule(t.cell(i + 1, 3), droite[i], taille=11, centre=False)
    para(d, "", apres=6)
    para(d, "{{ville}} في: {{date_redaction}}", taille=12, apres=2)
    para(d, "توقيع وخاتم رئيس المؤسسة", gras=True, taille=12, apres=2)
    chemin = MODELES / "pv_prise_service.docx"
    d.save(chemin)
    return chemin


def _marges_reduites(d) -> None:
    s = d.sections[0]
    s.top_margin = s.bottom_margin = Cm(1.0)


def _serrer(t) -> None:
    """أسطر الجدول دون تباعد بين الفقرات، حتى تسع الصفحة كل الأسطر والتوقيع."""
    for r in t.rows:
        for c in r.cells:
            for p in c.paragraphs:
                p.paragraph_format.space_after = Pt(0)
                p.paragraph_format.space_before = Pt(0)
                p.paragraph_format.line_spacing = 1.0


def _ligne_info(d, texte: str) -> None:
    para(d, texte, taille=11, apres=2)


ENTETES_COLLECTIF = ["ر.ت", "الاسم الكامل", "رقم التأجير", "ر. ب. ت. و", "الإطار", "مادة التدريس", "رقم الهاتف",
                     "العنوان الشخصي"]
LARGEURS = [0.8, 3.8, 1.9, 2.0, 3.9, 1.8, 2.5, 4.2]


def pv_entree_sortie() -> Path:
    d = _nouveau(paysage=True)
    _marges_reduites(d)
    _entete(d, 10)
    para(d, "الموسم الدراسي: {{annee}}", taille=11, apres=2)
    _titre_encadre(d, "{{titre_pv}} يهم: {{concerne}}", taille=14, largeur=14)
    _ligne_info(d, "المؤسسة: {{etablissement}}      رمزها: {{code_etab}}      الجماعة: {{commune}}")
    ent = ENTETES_COLLECTIF + ["التوقيع", "ملاحظات"]
    t = tableau(d, 1 + LIGNES_PAGE, len(ent), largeurs=LARGEURS + [2.8, 2.3])
    for j, h in enumerate(ent):
        _cellule(t.cell(0, j), h, gras=True, taille=9)
        _ombre(t.cell(0, j))
    champs = ["r", "nom", "ppr", "cin", "cadre", "matiere", "tel", "adresse"]
    for i in range(LIGNES_PAGE):
        for j, ch in enumerate(champs):
            _cellule(t.cell(i + 1, j), "{{%s_%d}}" % (ch, i + 1), taille=9)
        _cellule(t.cell(i + 1, 9), "{{obs_%d}}" % (i + 1), taille=9)
        t.rows[i + 1].height = Cm(0.8)
    _serrer(t)
    para(d, "", apres=4)
    para(d, "حرر بـ: {{ville}}      بتاريخ: {{date_pv}}                                        "
            "ختم وتوقيع رئيس المؤسسة:", taille=11, apres=2)
    para(d, "الصفحة: {{page}}", taille=10, apres=0)
    chemin = MODELES / "pv_entree_sortie.docx"
    d.save(chemin)
    return chemin


def pv_non_signataires() -> Path:
    d = _nouveau(paysage=True)
    _marges_reduites(d)
    _entete(d, 10)
    para(d, "الموسم الدراسي: {{annee}}", taille=11, apres=2)
    _titre_encadre(d, "لائحة {{les_personnels}} الذين لم يوقعوا {{titre_pv}}", taille=14, largeur=16)
    _ligne_info(d, "المؤسسة: {{etablissement}}      رمزها: {{code_etab}}      الجماعة: {{commune}}")
    ent = ENTETES_COLLECTIF + ["سبب عدم التوقيع"]
    t = tableau(d, 1 + LIGNES_NON_SIGNATAIRES, len(ent), largeurs=LARGEURS + [5.0])
    for j, h in enumerate(ent):
        _cellule(t.cell(0, j), h, gras=True, taille=9)
        _ombre(t.cell(0, j))
    champs = ["r", "nom", "ppr", "cin", "cadre", "matiere", "tel", "adresse", "motif"]
    for i in range(LIGNES_NON_SIGNATAIRES):
        for j, ch in enumerate(champs):
            _cellule(t.cell(i + 1, j), "{{%s_%d}}" % (ch, i + 1), taille=9, gras=(ch == "nom"))
        t.rows[i + 1].height = Cm(0.8)
    _serrer(t)
    para(d, "", apres=4)
    para(d, "حرر بـ: {{ville}}      بتاريخ: {{date_pv}}                                        "
            "ختم وتوقيع رئيس المؤسسة:", taille=11, apres=2)
    chemin = MODELES / "pv_non_signataires.docx"
    d.save(chemin)
    return chemin


if __name__ == "__main__":
    for f in (pv_prise_service, pv_entree_sortie, pv_non_signataires):
        print(f())
    _ = _bordures
