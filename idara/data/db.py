"""الاتصال بقاعدة SQLite وترحيل بنيتها.

كل ملف في مجلد migrations يحمل رقماً متسلسلاً (0001_...) ويُطبَّق مرة واحدة
داخل معاملة واحدة: إما يُطبَّق كاملاً أو لا يُطبَّق شيء منه.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

DOSSIER_MIGRATIONS = Path(__file__).parent / "migrations"
_MOTIF_MIGRATION = re.compile(r"^(\d{4})_[\w-]+\.sql$")


class ErreurMigration(RuntimeError):
    pass


def connecter(chemin: Path | str) -> sqlite3.Connection:
    """يفتح القاعدة مع تفعيل المفاتيح الخارجية."""
    conn = sqlite3.connect(str(chemin))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def lister_migrations(dossier: Path = DOSSIER_MIGRATIONS) -> list[tuple[int, str, Path]]:
    resultat = []
    for f in sorted(dossier.iterdir()):
        m = _MOTIF_MIGRATION.match(f.name)
        if m:
            resultat.append((int(m.group(1)), f.stem, f))
    numeros = [n for n, _, _ in resultat]
    if numeros != list(range(1, len(numeros) + 1)):
        raise ErreurMigration(f"ترقيم ملفات الترحيل غير متسلسل: {numeros}")
    return resultat


def version_actuelle(conn: sqlite3.Connection) -> int:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_version ("
        " version INTEGER PRIMARY KEY,"
        " nom TEXT NOT NULL,"
        " applique_le TEXT NOT NULL DEFAULT (datetime('now','localtime')))"
    )
    ligne = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
    return ligne[0] or 0


def migrer(conn: sqlite3.Connection, dossier: Path = DOSSIER_MIGRATIONS) -> list[str]:
    """يطبق الترحيلات الناقصة بالترتيب، ويعيد أسماء ما طُبّق."""
    actuelle = version_actuelle(conn)
    conn.commit()
    appliquees = []
    for numero, nom, fichier in lister_migrations(dossier):
        if numero <= actuelle:
            continue
        script = fichier.read_text(encoding="utf-8")
        nom_sql = nom.replace("'", "''")
        # إعادة بناء جدول (لتغيير قيد CHECK مثلاً) حسب طريقة SQLite: المفاتيح الخارجية معطلة خلال الترحيل،
        # ثم فحص سلامتها قبل الحفظ.
        reconstruction = script.lstrip().startswith("-- reconstruction")
        if reconstruction:
            conn.execute("PRAGMA foreign_keys = OFF")
        try:
            conn.executescript(
                "BEGIN;\n"
                + script
                + f"\nINSERT INTO schema_version(version, nom) VALUES ({numero}, '{nom_sql}');\n"
                + ("" if reconstruction else "COMMIT;")
            )
            if reconstruction:
                erreurs = conn.execute("PRAGMA foreign_key_check").fetchall()
                if erreurs:
                    raise sqlite3.IntegrityError(f"مفاتيح خارجية غير سليمة: {erreurs[:3]}")
                conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            conn.execute("PRAGMA foreign_keys = ON")
            raise ErreurMigration(f"فشل الترحيل {nom}: {e}") from e
        conn.execute("PRAGMA foreign_keys = ON")
        appliquees.append(nom)
    return appliquees


def ouvrir_base(chemin: Path | str) -> sqlite3.Connection:
    """يفتح القاعدة وينشئها أو يرحّلها إلى آخر إصدار."""
    conn = connecter(chemin)
    migrer(conn)
    return conn
