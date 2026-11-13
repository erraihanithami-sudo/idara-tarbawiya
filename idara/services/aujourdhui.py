"""«ماذا أفعل اليوم؟» في لوحة القيادة (اقتراح مستلهم من مقارنة 2026-11-13، وافق عليه المدير).

لائحة قصيرة من الأعمال التي ينتظرها البرنامج من المدير اليوم، محسوبة من المعطيات: كل عنصر نص وصفحة تُفتح.
لا شيء منها يُنفَّذ آلياً.
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from idara.data.dossier import DossierDonnees
from idara.services import annee as annee_srv

DELAI_SAUVEGARDE = 7


def _mois_precedent(le: date) -> str:
    premier = le.replace(day=1)
    return (premier - timedelta(days=1)).strftime("%Y-%m")


def taches(conn: sqlite3.Connection, dossier: DossierDonnees | None = None, le: date | None = None) -> list[dict]:
    """[{"texte", "page", "urgence"}] مرتبة: العاجل أولاً."""
    le = le or date.today()
    res: list[dict] = []

    def ajouter(texte: str, page: str | None, urgence: int = 1) -> None:
        res.append({"texte": texte, "page": page, "urgence": urgence})

    a = annee_srv.annee_courante(conn)
    if a is None:
        return res
    # 1) رخص انتهت دون محضر استئناف العمل
    try:
        n = conn.execute(
            "SELECT COUNT(*) FROM conge c WHERE c.date_fin < ? AND c.annee_id=? AND NOT EXISTS "
            "(SELECT 1 FROM reprise_travail r WHERE r.conge_id=c.id) AND NOT EXISTS "
            "(SELECT 1 FROM conge p WHERE p.prolongation_de=c.id)", (le.isoformat(), a["id"])).fetchone()[0]
        if n:
            ajouter(f"{n} رخصة انتهت دون محضر استئناف العمل", "الرخص", 2)
        n = conn.execute("SELECT COUNT(*) FROM conge WHERE date_fin BETWEEN ? AND ? AND annee_id=?",
                         (le.isoformat(), (le + timedelta(days=2)).isoformat(), a["id"])).fetchone()[0]
        if n:
            ajouter(f"{n} رخصة تنتهي خلال يومين: هيئ محضر الاستئناف أو التمديد", "الرخص")
    except sqlite3.Error:
        pass
    # 2) حركية التلاميذ: ملفات لم تُرسل أو لم تُطلب، وطلبات تنتظر التذكير
    try:
        from idara.services import mouvements as mv
        al = mv.alertes(conn, le)
        if al["envoi"]:
            ajouter(f"{len(al['envoi'])} مغادراً لم يُرسل ملفه المدرسي", "حركية التلاميذ", 2)
        if al["demande"]:
            ajouter(f"{len(al['demande'])} وافداً لم يُطلب ملفه المدرسي", "حركية التلاميذ", 2)
        if al["relance"]:
            ajouter(f"{len(al['relance'])} طلب ملف دون جواب منذ أكثر من {mv.DELAI_RELANCE} يوماً: أرسل تذكيراً",
                    "حركية التلاميذ")
    except Exception:  # noqa: BLE001 (لا سنة جارية)
        pass
    # 3) نسب حضور الشهر المنصرم لم تُدرج
    try:
        from idara.services import absences as ab
        mp = _mois_precedent(le)
        if mp in dict(ab.mois_de_l_annee(conn)) and ab.lignes(conn, mp) and ab.synthese_mois(conn, mp) is None:
            ajouter(f"نسب حضور {ab.libelle_mois(mp)} لم تُدرج بعد", "تتبع الغياب")
    except Exception:  # noqa: BLE001
        pass
    # 4) أولياء الأمور: تلاميذ دون هاتف ولي
    try:
        tot = conn.execute("SELECT COUNT(*) FROM inscription WHERE annee_id=? AND statut IN ('inscrit','arrive')",
                           (a["id"],)).fetchone()[0]
        avec = conn.execute(
            "SELECT COUNT(DISTINCT i.eleve_id) FROM inscription i JOIN tuteur t ON t.eleve_id=i.eleve_id "
            "WHERE i.annee_id=? AND i.statut IN ('inscrit','arrive') AND t.telephone IS NOT NULL", (a["id"],)).fetchone()[0]
        if tot and avec == 0:
            ajouter("معلومات أولياء الأمور غير مستوردة: استورد ملف الأولياء من مسار", "أولياء الأمور", 0)
    except sqlite3.Error:
        pass
    # 5) النسخة الاحتياطية
    if dossier is not None:
        from idara.services import sauvegarde
        sv = sauvegarde.lister_sauvegardes(dossier)
        dernier = None
        if sv:
            s = sv[-1].name[len(sauvegarde.PREFIXE):len(sauvegarde.PREFIXE) + 8]
            try:
                dernier = date(int(s[:4]), int(s[4:6]), int(s[6:8]))
            except ValueError:
                dernier = None
        if dernier is None:
            ajouter("لا نسخة احتياطية بعد: أقفل البرنامج بزر «إقفال البرنامج» لتُحفظ نسخة جديدة", None, 2)
        elif (le - dernier).days > DELAI_SAUVEGARDE:
            ajouter(f"آخر نسخة احتياطية منذ {(le - dernier).days} يوماً: أقفل البرنامج بزر «إقفال البرنامج» لتُحفظ نسخة جديدة", None)
    return sorted(res, key=lambda t: -t["urgence"])
