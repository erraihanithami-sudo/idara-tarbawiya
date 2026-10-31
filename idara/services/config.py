"""إعدادات الجهاز: أين يوجد مجلد بيانات المؤسسة.

يُحفظ في ملف صغير خارج مجلد البيانات (في %APPDATA% على Windows)،
حتى يعرف التطبيق عند كل تشغيل أين يجد بياناته.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

NOM_DOSSIER_APP = "IdaraTarbawiya"
NOM_DOSSIER_DONNEES = "الإدارة التربوية"


def dossier_config() -> Path:
    surcharge = os.environ.get("IDARA_CONFIG_DIR")
    if surcharge:
        return Path(surcharge)
    base = os.environ.get("APPDATA")
    return (Path(base) if base else Path.home() / ".config") / NOM_DOSSIER_APP


def fichier_config() -> Path:
    return dossier_config() / "config.json"


def lire_config() -> dict:
    f = fichier_config()
    if not f.exists():
        return {}
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def ecrire_config(**valeurs) -> None:
    config = lire_config()
    config.update(valeurs)
    f = fichier_config()
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(f)


def dossier_donnees_enregistre() -> Path | None:
    chemin = lire_config().get("dossier_donnees")
    return Path(chemin) if chemin else None


def dossier_donnees_par_defaut() -> Path:
    documents = Path.home() / "Documents"
    return (documents if documents.exists() else Path.home()) / NOM_DOSSIER_DONNEES
