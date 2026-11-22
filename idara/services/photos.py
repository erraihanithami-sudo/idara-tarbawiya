"""صور التقارير (طلب المدير 2026-11-22): زر «إضافة الصور» في تقارير الأنشطة والأيام التواصلية والأبواب المفتوحة،
وصور المرافق ونجم الأسبوع في شاشة العرض.

الصورة تُنسخ إلى pieces/photos/<objet>/ داخل مجلد البيانات (فتدخل في النسخ الاحتياطية) بعد تصغيرها إلى 1600 بكسل
على الأكثر، وتُسجَّل في جدول photo. صور الأطفال لا تُعرض على شاشة المؤسسة إلا بموافقة أوليائهم."""

from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path

OBJETS = {"activite": "نشاط", "rencontre": "لقاء مع الأسر", "structure": "مرفق", "etoile": "نجم الأسبوع"}
MAX_PX = 1600
MAX_PAR_RAPPORT = 24
EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".webp")


class ErreurPhoto(ValueError):
    """رسالة موجهة للمدير بالعربية."""


def _verifier(objet: str) -> None:
    if objet not in OBJETS:
        raise ErreurPhoto("نوع غير معروف للصور.")


def lister(conn: sqlite3.Connection, objet: str, ref) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT * FROM photo WHERE objet=? AND ref=? ORDER BY id",
                                          (objet, str(ref)))]


def nombre(conn: sqlite3.Connection, objet: str, ref) -> int:
    return conn.execute("SELECT COUNT(*) FROM photo WHERE objet=? AND ref=?", (objet, str(ref))).fetchone()[0]


def chemin(dossier, p: dict) -> Path:
    return Path(dossier.racine) / p["chemin"]


def ajouter(conn: sqlite3.Connection, dossier, objet: str, ref, source, legende: str = "") -> int:
    """ينسخ الصورة (مصغّرة) ويسجلها. يعيد رقمها."""
    _verifier(objet)
    if ref is None or str(ref) == "":
        raise ErreurPhoto("احفظ التقرير أولاً ثم أضف الصور.")
    source = Path(source)
    if source.suffix.lower() not in EXTENSIONS or not source.is_file():
        raise ErreurPhoto(f"«{source.name}» ليس صورة (PNG أو JPG).")
    if nombre(conn, objet, ref) >= MAX_PAR_RAPPORT:
        raise ErreurPhoto(f"بلغ التقرير {MAX_PAR_RAPPORT} صورة، وهو الحد الأقصى.")
    from PIL import Image, ImageOps
    try:
        with Image.open(source) as im:
            im = ImageOps.exif_transpose(im)
            im.thumbnail((MAX_PX, MAX_PX))
            if im.mode not in ("RGB", "L"):
                fond = Image.new("RGB", im.size, "white")
                fond.paste(im, mask=im.convert("RGBA").split()[-1])
                im = fond
            rel = Path("pieces") / "photos" / objet / f"{ref}_{uuid.uuid4().hex[:10]}.jpg"
            cible = Path(dossier.racine) / rel
            cible.parent.mkdir(parents=True, exist_ok=True)
            im.convert("RGB").save(cible, "JPEG", quality=88)
    except ErreurPhoto:
        raise
    except Exception as e:  # noqa: BLE001 — ملف تالف
        raise ErreurPhoto(f"تعذرت قراءة الصورة «{source.name}».") from e
    cur = conn.execute("INSERT INTO photo(objet, ref, chemin, legende) VALUES (?,?,?,?)",
                       (objet, str(ref), rel.as_posix(), " ".join((legende or "").split())))
    conn.commit()
    return cur.lastrowid


def ajouter_plusieurs(conn, dossier, objet: str, ref, sources) -> tuple[int, list[str]]:
    """(عدد الصور المضافة، الأخطاء)."""
    n, erreurs = 0, []
    for s in sources:
        try:
            ajouter(conn, dossier, objet, ref, s)
            n += 1
        except ErreurPhoto as e:
            erreurs.append(str(e))
    return n, erreurs


def definir_legende(conn: sqlite3.Connection, pid: int, legende: str) -> None:
    conn.execute("UPDATE photo SET legende=? WHERE id=?", (" ".join((legende or "").split()), pid))
    conn.commit()


def supprimer(conn: sqlite3.Connection, dossier, pid: int) -> None:
    r = conn.execute("SELECT chemin FROM photo WHERE id=?", (pid,)).fetchone()
    if r is None:
        return
    conn.execute("DELETE FROM photo WHERE id=?", (pid,))
    conn.commit()
    try:
        (Path(dossier.racine) / r[0]).unlink(missing_ok=True)
    except OSError:
        pass


def supprimer_tout(conn: sqlite3.Connection, dossier, objet: str, ref) -> None:
    for p in lister(conn, objet, ref):
        supprimer(conn, dossier, p["id"])


def inserer_docx(d, conn, dossier, objet: str, ref, titre: str = "صور من التقرير") -> int:
    """يضيف الصور إلى وثيقة Word في جدول من عمودين مع التعليق تحت كل صورة. يعيد عدد الصور."""
    ps = [p for p in lister(conn, objet, ref) if chemin(dossier, p).exists()]
    if not ps:
        return 0
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Cm, Pt
    from idara.services.docs_association import para
    para(d, "", apres=4)
    para(d, titre, gras=True, taille=15, apres=4)
    lignes = (len(ps) + 1) // 2
    t = d.add_table(rows=lignes, cols=2)
    t.autofit = False
    for k, p in enumerate(ps):
        c = t.cell(k // 2, 1 - k % 2)   # من اليمين
        c.width = Cm(8.6)
        pa = c.paragraphs[0]
        pa.alignment = WD_ALIGN_PARAGRAPH.CENTER
        pa.add_run().add_picture(str(chemin(dossier, p)), width=Cm(8.2))
        if p["legende"]:
            q = c.add_paragraph()
            q.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r = q.add_run(p["legende"])
            r.font.size = Pt(10)
            r.italic = True
    return len(ps)


def toutes(conn: sqlite3.Connection, objet: str) -> list[dict]:
    """كل صور نوع معين، الأحدث أولاً (لمعارض شاشة العرض)."""
    return [dict(r) for r in conn.execute("SELECT * FROM photo WHERE objet=? ORDER BY id DESC", (objet,))]
