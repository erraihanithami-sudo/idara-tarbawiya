"""النسخ الاحتياطي والاسترجاع.

- النسخ بطريقة SQLite الآمنة (backup API)، لا بنسخ الملف أثناء العمل.
- كل نسخة يُتحقق من سلامتها قبل اعتمادها.
- الاحتفاظ بآخر 30 نسخة في مجلد sauvegardes.
- الاسترجاع يأخذ أولاً نسخة من الحالة الحالية.
- التصدير إلى قرص خارجي: ملف مضغوط واحد (القاعدة + القوالب + الأرشيف + المرفقات).
"""

from __future__ import annotations

import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime, date
from pathlib import Path

from idara.data.db import connecter
from idara.data.dossier import DossierDonnees, NOM_BASE

MAX_SAUVEGARDES = 30
PREFIXE = "sauvegarde_"
DOSSIERS_EXPORTES = ("modeles", "archives", "pieces")


class ErreurSauvegarde(RuntimeError):
    pass


def _horodatage() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _copier_base(source: Path, destination: Path) -> None:
    """نسخ آمن لقاعدة SQLite، حتى وهي مفتوحة."""
    src = sqlite3.connect(str(source))
    dst = sqlite3.connect(str(destination))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


def verifier_base(chemin: Path) -> None:
    """يرفض أي ملف ليس قاعدة سليمة لهذا التطبيق."""
    try:
        conn = sqlite3.connect(f"file:{chemin.as_posix()}?mode=ro", uri=True)
        try:
            resultat = conn.execute("PRAGMA integrity_check").fetchone()[0]
            if resultat != "ok":
                raise ErreurSauvegarde(f"الملف تالف: {resultat}")
            conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
        finally:
            conn.close()
    except sqlite3.DatabaseError as e:
        raise ErreurSauvegarde(f"ليس قاعدة بيانات صالحة للتطبيق: {e}") from e


def lister_sauvegardes(dossier: DossierDonnees) -> list[Path]:
    """من الأقدم إلى الأحدث."""
    return sorted(dossier.sauvegardes.glob(f"{PREFIXE}*.db"))


def creer_sauvegarde(dossier: DossierDonnees, motif: str = "manuelle") -> Path:
    dossier.preparer()
    if not dossier.base.exists():
        raise ErreurSauvegarde("لا توجد قاعدة بيانات لنسخها.")
    base_nom = f"{PREFIXE}{_horodatage()}_{motif}"
    cible = dossier.sauvegardes / f"{base_nom}.db"
    n = 1
    while cible.exists():
        n += 1
        cible = dossier.sauvegardes / f"{base_nom}_{n}.db"
    _copier_base(dossier.base, cible)
    verifier_base(cible)
    _elaguer(dossier)
    return cible


def _elaguer(dossier: DossierDonnees) -> None:
    sauvegardes = lister_sauvegardes(dossier)
    for ancienne in sauvegardes[:-MAX_SAUVEGARDES]:
        ancienne.unlink()


def sauvegarde_quotidienne(dossier: DossierDonnees, aujourd_hui: date | None = None) -> Path | None:
    """نسخة عند الإغلاق، مرة في اليوم على الأكثر."""
    jour = (aujourd_hui or date.today()).strftime("%Y%m%d")
    if any(f.name.startswith(f"{PREFIXE}{jour}") for f in lister_sauvegardes(dossier)):
        return None
    return creer_sauvegarde(dossier, "quotidienne")


def restaurer_sauvegarde(dossier: DossierDonnees, fichier: Path) -> Path:
    """يسترجع نسخة. يعيد مسار النسخة المأخوذة من الحالة السابقة."""
    fichier = Path(fichier)
    verifier_base(fichier)
    securite = creer_sauvegarde(dossier, "avant_restauration")
    _copier_base(fichier, dossier.base)
    verifier_base(dossier.base)
    return securite


def exporter(dossier: DossierDonnees, destination: Path) -> Path:
    """ملف مضغوط واحد للنقل إلى قرص خارجي."""
    destination = Path(destination)
    if destination.is_dir():
        destination = destination / f"idara_export_{_horodatage()}.zip"
    with tempfile.TemporaryDirectory() as tmp:
        cliche = Path(tmp) / NOM_BASE
        _copier_base(dossier.base, cliche)
        verifier_base(cliche)
        with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(cliche, NOM_BASE)
            for nom in DOSSIERS_EXPORTES:
                racine = dossier.racine / nom
                if not racine.exists():
                    continue
                for f in sorted(racine.rglob("*")):
                    if f.is_file():
                        z.write(f, f.relative_to(dossier.racine).as_posix())
    return destination


def importer_export(dossier: DossierDonnees, archive: Path) -> Path | None:
    """يسترجع كل شيء من ملف مضغوط. يأخذ أولاً تصديراً كاملاً للحالة الحالية."""
    archive = Path(archive)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        with zipfile.ZipFile(archive) as z:
            for nom in z.namelist():
                cible = (tmp / nom).resolve()
                if not str(cible).startswith(str(tmp.resolve())):
                    raise ErreurSauvegarde(f"مسار غير مقبول داخل الملف المضغوط: {nom}")
            z.extractall(tmp)
        base = tmp / NOM_BASE
        if not base.exists():
            raise ErreurSauvegarde("الملف المضغوط لا يحتوي على قاعدة بيانات.")
        verifier_base(base)

        dossier.preparer()
        securite = None
        if dossier.base.exists():
            securite = exporter(
                dossier, dossier.sauvegardes / f"{PREFIXE}{_horodatage()}_avant_import.zip")

        _copier_base(base, dossier.base)
        for nom in DOSSIERS_EXPORTES:
            source = tmp / nom
            cible = dossier.racine / nom
            if cible.exists():
                shutil.rmtree(cible)
            if source.exists():
                shutil.copytree(source, cible)
            else:
                cible.mkdir()
        verifier_base(dossier.base)
    return securite


MOT_CONFIRMATION = "تصفير"


def reinitialiser(dossier: DossierDonnees) -> Path:
    """تصفير البرنامج (طلب المدير 2026-11-04): يحذف كل ما أدخله المستعمل (القاعدة: التلاميذ، الموظفون، الرخص،
    الجمعيات...، والقوالب المعدّلة والهوية البصرية والوثائق المولَّدة والمرفقات)، فيعود البرنامج إلى حالة التثبيت
    الأول. قبل ذلك يُؤخذ تصدير كامل في مجلد النسخ الاحتياطية، يُسترجع عند الحاجة من مساعد الإعداد
    («استيراد نسخة»). مجلد النسخ الاحتياطية لا يُحذف. يجب إغلاق الاتصال بالقاعدة قبل الاستدعاء."""
    dossier.preparer()
    securite = None
    if dossier.base.exists():
        securite = exporter(dossier, dossier.sauvegardes / f"{PREFIXE}{_horodatage()}_avant_reinitialisation.zip")
        with zipfile.ZipFile(securite) as z:   # لا حذف قبل التأكد من سلامة النسخة
            if NOM_BASE not in z.namelist() or z.testzip() is not None:
                raise ErreurSauvegarde("تعذر التحقق من النسخة الاحتياطية؛ لم يُحذف شيء.")
    for suffixe in ("", "-wal", "-shm", "-journal"):
        f = dossier.racine / f"{NOM_BASE}{suffixe}"
        if f.exists():
            f.unlink()
    for nom in DOSSIERS_EXPORTES:
        rep = dossier.racine / nom
        if rep.exists():
            shutil.rmtree(rep)
    dossier.preparer()
    return securite
