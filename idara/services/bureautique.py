"""فتح الوثائق وتحويلها إلى PDF وطباعتها عبر Microsoft Word المثبت على الحاسوب.

يعمل على Windows فقط. إن لم يتوفر Word، تُفتح الوثيقة بالبرنامج الافتراضي ليطبعها المدير.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

FORMAT_PDF = 17  # wdFormatPDF


class ErreurBureautique(RuntimeError):
    pass


# دالة يسجلها البرنامج عند تشغيله لفتح وثائق Word في محرره الداخلي (2026-11-15). None: الفتح خارجي دائماً
ouvreur = None


def finir(chemin: Path) -> None:
    """يحذف علامات الاتجاه التي كانت تظهر «LRI/PDI» في Word. لا يفشل الفتح بسببه."""
    from idara.services import finition
    try:
        finition.nettoyer_marques(Path(chemin))
    except Exception:  # noqa: BLE001, S110 — ملف مفتوح في Word أو تالف: يُفتح كما هو
        pass


def ouvrir(chemin: Path) -> None:
    """يفتح الوثيقة في محرر البرنامج إن سُجّل، وإلا بالبرنامج المرتبط بها على الحاسوب."""
    chemin = Path(chemin)
    if ouvreur is not None and chemin.suffix.lower() == ".docx":
        finir(chemin)
        ouvreur(chemin)
        return
    ouvrir_externe(chemin)


def ouvrir_externe(chemin: Path) -> None:
    """يفتح الملف بالبرنامج المرتبط به على الحاسوب (لتعديل القوالب، ولما لا يفهمه المحرر)."""
    chemin = Path(chemin)
    finir(chemin)
    if sys.platform == "win32":
        os.startfile(str(chemin))  # noqa: S606
    else:
        subprocess.Popen(["xdg-open", str(chemin)])  # للتطوير فقط


def _word():
    try:
        import win32com.client  # type: ignore
    except ImportError as e:
        raise ErreurBureautique("Microsoft Word غير متاح على هذا الحاسوب.") from e
    try:
        word = win32com.client.DispatchEx("Word.Application")
    except Exception as e:  # noqa: BLE001
        raise ErreurBureautique(f"تعذر تشغيل Microsoft Word: {e}") from e
    word.Visible = False
    word.DisplayAlerts = 0
    return word


def word_disponible() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import winreg  # type: ignore
        winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"Word.Application\CLSID")
        return True
    except OSError:
        return False


def convertir_pdf(docx: Path, pdf: Path | None = None) -> Path:
    docx = Path(docx).resolve()
    finir(docx)
    pdf = Path(pdf).resolve() if pdf else docx.with_suffix(".pdf")
    word = _word()
    try:
        doc = word.Documents.Open(str(docx), ReadOnly=True, AddToRecentFiles=False)
        try:
            doc.SaveAs2(str(pdf), FileFormat=FORMAT_PDF)
        finally:
            doc.Close(False)
    except Exception as e:  # noqa: BLE001
        raise ErreurBureautique(f"تعذر التحويل إلى PDF: {e}") from e
    finally:
        word.Quit()
    if not pdf.exists():
        raise ErreurBureautique("لم يُنشأ ملف PDF.")
    return pdf


def imprimer(docx: Path, copies: int = 1) -> None:
    finir(docx)
    word = _word()
    try:
        doc = word.Documents.Open(str(Path(docx).resolve()), ReadOnly=True, AddToRecentFiles=False)
        try:
            doc.PrintOut(Background=False, Copies=copies)
        finally:
            doc.Close(False)
    except Exception as e:  # noqa: BLE001
        raise ErreurBureautique(f"تعذرت الطباعة: {e}") from e
    finally:
        word.Quit()


def ouvrir_lien(url: str) -> None:
    """يفتح رابطاً في المتصفح أو التطبيق المرتبط به (واتساب). لا شيء يُرسل دون ضغط المستعمل."""
    import webbrowser
    webbrowser.open(url)
