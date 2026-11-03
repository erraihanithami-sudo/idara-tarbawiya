"""محطات السنة الدراسية والتذكيرات وبرنامج العمل السنوي (اقتراح المدير 2026-11-03).

- المحطات الوزارية: تُستخرج من المقرر الوزاري لتنظيم السنة الدراسية عند صدوره، وتُراجَع، ثم تُوزَّع مع تحديث
  البرنامج في resources/mouqarrar/<2026-2027>.json (المقرر يصدر نسخة ممسوحة لا يمكن قراءتها آلياً).
- المحطات المحلية: يضيفها المدير (اجتماعات، أنشطة...)، ولا تمسها التحديثات.
- التذكير: تظهر المحطة في «التذكيرات» قبل موعدها بعدد الأيام المحدد، وطيلة مدتها، ما لم تُعلَّم «أُنجزت».
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from idara.services import annee as annee_srv
from idara.services import textes as tx

DOSSIER = Path(__file__).resolve().parent.parent / "resources" / "mouqarrar"

TYPES = {"rentree": "الدخول المدرسي", "conge": "عطلة", "fete": "عيد أو ذكرى", "evaluation": "المراقبة المستمرة",
         "examen": "امتحان", "conseil": "مجالس الأقسام", "resultats": "النتائج", "inscription": "التسجيل",
         "personnel": "الأطر", "concours": "مسابقة", "fin": "نهاية السنة", "local": "محطة محلية"}
PUBLICS = {"administration": "الإدارة", "enseignants": "الأساتذة", "eleves": "التلاميذ", "parents": "الأولياء"}
TYPES_LOCAUX = ("local", "conseil", "evaluation", "examen", "concours", "personnel", "inscription", "resultats")


class ErreurCalendrier(ValueError):
    """رسالة موجهة للمدير بالعربية."""


@dataclass
class Station:
    cle: str                 # m:<...> وزارية، l:<id> محلية
    titre: str
    type: str
    debut: date
    fin: date
    rappel_jours: int = 7
    reference: str = ""
    public: list[str] = field(default_factory=list)
    niveaux: list[str] = field(default_factory=list)
    lien: str = ""
    precision: str = ""      # hijri: حسب ثبوت الرؤية؛ mois: الشهر فقط
    note: str = ""
    fait_le: str = ""
    locale: bool = False
    id: int | None = None

    @property
    def periode(self) -> str:
        if self.precision == "mois":
            m1, m2 = tx.MOIS_AR[self.debut.month - 1], tx.MOIS_AR[self.fin.month - 1]
            return (f"خلال شهر {m1} {self.debut.year}" if (self.debut.month, self.debut.year) ==
                    (self.fin.month, self.fin.year) else f"{m1} – {m2} {self.fin.year}")
        txt = tx.date_ar(self.debut) if self.debut == self.fin else \
            f"من {tx.date_ar(self.debut)} إلى {tx.date_ar(self.fin)}"
        return txt + (" (تقريبي)" if self.precision == "hijri" else "")

    @property
    def libelle_type(self) -> str:
        return TYPES.get(self.type, self.type)


def _fichier(annee: str) -> Path:
    return DOSSIER / f"{annee.replace('/', '-')}.json"


def mouqarrar(annee: str) -> dict | None:
    """معلومات المقرر المرفق بالبرنامج لهذه السنة (أو None إن لم يصدر بعد / لم يُرفق)."""
    f = _fichier(annee)
    if not f.exists():
        return None
    d = json.loads(f.read_text(encoding="utf-8"))
    if d.get("annee") != annee:
        raise ErreurCalendrier(f"ملف المحطات {f.name} لا يخص السنة {annee}.")
    return d


def _d(v: str) -> date:
    return date.fromisoformat(v)


def stations_ministerielles(annee: str) -> list[Station]:
    d = mouqarrar(annee)
    if not d:
        return []
    return [Station(cle="m:" + s["cle"], titre=s["titre"], type=s["type"], debut=_d(s["debut"]),
                    fin=_d(s.get("fin") or s["debut"]), rappel_jours=int(s.get("rappel_jours", 7)),
                    reference=s.get("reference", ""), public=list(s.get("public", [])),
                    niveaux=list(s.get("niveaux", [])), lien=s.get("lien", ""), precision=s.get("precision", ""),
                    note=s.get("note", "")) for s in d["stations"]]


def _annee(conn) -> sqlite3.Row:
    a = annee_srv.annee_courante(conn)
    if a is None:
        raise ErreurCalendrier("لا سنة دراسية جارية.")
    return a


def stations(conn: sqlite3.Connection, inclure_locales: bool = True) -> list[Station]:
    """كل محطات السنة الجارية، مرتبة حسب التاريخ."""
    a = _annee(conn)
    res = stations_ministerielles(a["libelle"])
    if inclure_locales:
        for r in conn.execute("SELECT * FROM station_locale WHERE annee_id=?", (a["id"],)):
            res.append(Station(cle=f"l:{r['id']}", titre=r["titre"], type=r["type"], debut=_d(r["debut"]),
                               fin=_d(r["fin"]), rappel_jours=r["rappel_jours"], note=r["remarque"] or "",
                               locale=True, id=r["id"], reference="محطة محلية"))
    faits = {r["cle"]: r["fait_le"] for r in conn.execute(
        "SELECT cle, fait_le FROM station_suivi WHERE annee_id=? AND fait_le IS NOT NULL", (a["id"],))}
    for s in res:
        s.fait_le = faits.get(s.cle, "")
    res.sort(key=lambda s: (s.debut, s.fin, s.locale))
    return res


def rappels(conn: sqlite3.Connection, le: date | None = None) -> dict[str, list[Station]]:
    """«جارية» (اليوم ضمن مدتها)، «قادمة» (خلال مدة التذكير)، «فائتة» (انتهت دون أن تُعلَّم منجزة، آخر 30 يوماً).
    العطل والأعياد لا تُعدّ فائتة."""
    le = le or date.today()
    res = {"en_cours": [], "a_venir": [], "en_retard": []}
    for s in stations(conn):
        if s.fait_le:
            continue
        if s.debut <= le <= s.fin:
            res["en_cours"].append(s)
        elif le < s.debut <= le + timedelta(days=s.rappel_jours):
            res["a_venir"].append(s)
        elif s.fin < le <= s.fin + timedelta(days=30) and s.type not in ("conge", "fete", "rentree"):
            res["en_retard"].append(s)
    return res


def marquer(conn: sqlite3.Connection, cle: str, fait: bool = True, le: date | None = None) -> None:
    a = _annee(conn)
    with conn:
        if fait:
            conn.execute("INSERT INTO station_suivi(annee_id, cle, fait_le) VALUES (?,?,?) ON CONFLICT(annee_id, cle) "
                         "DO UPDATE SET fait_le=excluded.fait_le", (a["id"], cle, (le or date.today()).isoformat()))
        else:
            conn.execute("DELETE FROM station_suivi WHERE annee_id=? AND cle=?", (a["id"], cle))


def enregistrer_locale(conn: sqlite3.Connection, titre: str, debut: str, fin: str = "", type_: str = "local",
                       rappel_jours: int = 7, remarque: str = "", sid: int | None = None) -> int:
    a = _annee(conn)
    titre = " ".join((titre or "").split())
    if not titre:
        raise ErreurCalendrier("عنوان المحطة إجباري.")
    try:
        d1 = _d(debut)
        d2 = _d(fin) if fin else d1
    except (TypeError, ValueError):
        raise ErreurCalendrier("تاريخ المحطة غير صحيح.") from None
    if d2 < d1:
        raise ErreurCalendrier("تاريخ النهاية قبل تاريخ البداية.")
    if type_ not in TYPES:
        raise ErreurCalendrier("نوع المحطة غير صحيح.")
    if not 0 <= int(rappel_jours) <= 120:
        raise ErreurCalendrier("التذكير: بين 0 و120 يوماً.")
    with conn:
        if sid is None:
            sid = conn.execute("INSERT INTO station_locale(annee_id, titre, type, debut, fin, rappel_jours, remarque) "
                               "VALUES (?,?,?,?,?,?,?)", (a["id"], titre, type_, d1.isoformat(), d2.isoformat(),
                                                          int(rappel_jours), remarque or None)).lastrowid
        else:
            if not conn.execute("SELECT 1 FROM station_locale WHERE id=?", (sid,)).fetchone():
                raise ErreurCalendrier("المحطة غير موجودة.")
            conn.execute("UPDATE station_locale SET titre=?, type=?, debut=?, fin=?, rappel_jours=?, remarque=? "
                         "WHERE id=?", (titre, type_, d1.isoformat(), d2.isoformat(), int(rappel_jours),
                                        remarque or None, sid))
    return sid


def supprimer_locale(conn: sqlite3.Connection, sid: int) -> None:
    with conn:
        conn.execute("DELETE FROM station_suivi WHERE cle=?", (f"l:{sid}",))
        conn.execute("DELETE FROM station_locale WHERE id=?", (sid,))


def vacances(conn: sqlite3.Connection) -> list[Station]:
    """العطل البينية وعطلة منتصف السنة (لاقتراح فترة شهادة العطلة)."""
    return [s for s in stations(conn, inclure_locales=False) if s.type == "conge"]


def par_mois(liste: list[Station]) -> list[tuple[str, list[Station]]]:
    res: dict[tuple[int, int], list[Station]] = {}
    for s in liste:
        res.setdefault((s.debut.year, s.debut.month), []).append(s)
    return [(f"{tx.MOIS_AR[m - 1]} {y}", l) for (y, m), l in sorted(res.items())]


def generer_programme(conn: sqlite3.Connection, dossier) -> Path:
    """برنامج العمل السنوي (Word): المحطات الوزارية والمحلية مرتبة حسب الأشهر. نموذج من إعداد التطبيق، لا نموذج
    رسمي مفترض."""
    from idara.services import etablissement as etab_srv
    from idara.services.docs_association import _cellule, _nouveau, _ombre, para, tableau
    a = _annee(conn)
    etab = etab_srv.lire_etablissement(conn)
    if etab is None or not etab.nom_ar:
        raise ErreurCalendrier("أكمل إعداد المؤسسة أولاً.")
    liste = stations(conn)
    if not liste:
        raise ErreurCalendrier("لا محطات لهذه السنة بعد: المقرر الوزاري لم يُرفق بالبرنامج، ولم تُضف محطات محلية.")
    d = _nouveau(paysage=True)
    if etab.logo_path and (dossier.racine / etab.logo_path).exists():
        from docx.shared import Cm
        d.add_picture(str(dossier.racine / etab.logo_path), width=Cm(16))
    else:
        for l in ("المملكة المغربية", "وزارة التربية الوطنية والتعليم الأولي والرياضة",
                  f"الأكاديمية الجهوية للتربية والتكوين: {etab.academie_ar or ''}",
                  f"المديرية الإقليمية: {etab.direction_ar or ''}", f"المؤسسة: {etab.nom_ar}"):
            para(d, l, gras=True, taille=10, apres=0)
    para(d, f"برنامج العمل السنوي برسم السنة الدراسية {a['libelle']}", gras=True, taille=16, centre=True,
         souligne=True, apres=2)
    m = mouqarrar(a["libelle"])
    if m:
        para(d, f"وفق مقرر تنظيم السنة الدراسية رقم {m['mouqarrar']['numero']} بتاريخ "
                f"{tx.date_ar(m['mouqarrar']['date'])}، مع محطات المؤسسة.", taille=10, centre=True, apres=6)
    for mois, l in par_mois(liste):
        para(d, mois, gras=True, taille=12, apres=2)
        t = tableau(d, 1 + len(l), 5, largeurs=[5.2, 10.2, 3.2, 4.6, 2.8])
        for j, h in enumerate(("التاريخ", "المحطة / العملية", "النوع", "المعنيون", "المرجع")):
            _cellule(t.cell(0, j), h, gras=True, taille=10)
            _ombre(t.cell(0, j))
        for i, s in enumerate(l, start=1):
            pub = "، ".join(PUBLICS.get(p, p) for p in s.public) or "المؤسسة"
            if s.niveaux:
                pub += " (" + "، ".join(tx.niveau_ar(n) for n in s.niveaux if n in tx.NIVEAUX) + ")"
            for j, v in enumerate((s.periode, s.titre + (f"\n{s.note}" if s.note else ""), s.libelle_type, pub,
                                   s.reference)):
                _cellule(t.cell(i, j), v, taille=9, centre=j != 1)
        para(d, "", apres=4)
    para(d, "توقيع المدير(ة):", gras=True, taille=11, apres=0)
    rep = dossier.archives / a["libelle"].replace("/", "-") / "برنامج العمل السنوي"
    rep.mkdir(parents=True, exist_ok=True)
    chemin = rep / f"{datetime.now():%Y%m%d_%H%M%S}_برنامج_العمل_السنوي.docx"
    d.save(chemin)
    return chemin
