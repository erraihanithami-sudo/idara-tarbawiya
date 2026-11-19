"""طلب ملف أستاذ وإرسال ملف أستاذ (توجيه المدير 2026-11-15، حسب نموذجه «طلب ملف أستاذ»).

المراسلة من مدير المؤسسة إلى مدير مؤسسة أخرى، تحت إشراف المدير الإقليمي إن لزم. موضوعها «طلب ملف إداري وتربوي»
أو «إرسال ملف إداري وتربوي»، وفيها جدول: ر.ت، الاسم والنسب، رقم التأجير، ملاحظات. تُسجَّل في سجل الصادر
فيأخذ رقمها منه.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path

from idara.data.dossier import DossierDonnees
from idara.services import conges as cg
from idara.services import etablissement as etab_srv
from idara.services import textes as tx

SENS = {"demande": "طلب ملف إداري وتربوي", "envoi": "إرسال ملف إداري وتربوي"}


class ErreurDossierProf(ValueError):
    """رسالة موجهة للمدير بالعربية."""


def _propre(v) -> str:
    return " ".join(str(v or "").split())


def _ltr(t: str) -> str:
    return f"⁦{t}⁩" if t else ""


def generer(conn: sqlite3.Connection, dossier: DossierDonnees, sens: str, etab_cible: str,
            profs: list[tuple[str, str, str]], le: str | None = None, sous_couvert: str = "",
            reference: str = "", rappel: bool = False, pids: list[int] | None = None) -> tuple[Path, str]:
    """يرجع (مسار الوثيقة، رقم الصادر). profs: [(الاسم والنسب، رقم التأجير، ملاحظات)]."""
    from docx.shared import Cm

    from idara.services.docs_association import _nouveau, para
    from idara.services.soutien import _signature, _table
    if sens not in SENS:
        raise ErreurDossierProf("نوع المراسلة غير معروف.")
    etab_cible = _propre(etab_cible)
    if not etab_cible:
        raise ErreurDossierProf("المؤسسة المرسل إليها إجبارية.")
    profs = [(_propre(n), _propre(p), _propre(o)) for n, p, o in profs if _propre(n)]
    if not profs:
        raise ErreurDossierProf("أدخل أستاذاً واحداً على الأقل.")
    le = le or date.today().isoformat()
    noms = "، ".join(n for n, _, _ in profs)
    objet = ("تذكير ب" if rappel and sens == "demande" else "") + SENS[sens]
    try:
        _, numero = cg.enregistrer_sortant(conn, f"{objet}: {noms} ({etab_cible})", le)
    except cg.ErreurConge as e:
        raise ErreurDossierProf(str(e)) from e
    etab = etab_srv.lire_etablissement(conn)
    d = _nouveau()
    if etab and etab.logo_path and (dossier.racine / etab.logo_path).exists():
        d.add_picture(str(dossier.racine / etab.logo_path), width=Cm(17))
    elif etab:
        for l in ("المملكة المغربية", "وزارة التربية الوطنية والتعليم الأولي والرياضة",
                  f"المديرية الإقليمية: {etab.direction_ar}", f"المؤسسة: {etab.nom_ar}"):
            para(d, l, gras=True, taille=10, apres=0)
    ville = (etab.ville_redaction_ar or etab.commune_ar) if etab else ""
    para(d, (f"{ville} في: " if ville else "في: ") + tx.date_ar(date.fromisoformat(le)), taille=11, apres=0)
    para(d, f"سجل تحت عدد: {_ltr(numero)}", taille=11, apres=8)
    para(d, "من مدير(ة) " + (etab.nom_ar if etab else "المؤسسة"), gras=True, taille=12, apres=0)
    para(d, f"إلى السيد(ة) مدير(ة) {etab_cible}", gras=True, taille=12, apres=0)
    if _propre(sous_couvert):
        para(d, f"تحت إشراف السيد المدير الإقليمي {_propre(sous_couvert)}", taille=11, apres=0)
    para(d, "", apres=4)
    para(d, f"الموضوع: {objet}.", gras=True, taille=12, centre=True, apres=2)
    if _propre(reference):
        para(d, f"المرجع: {_propre(reference)}", taille=11, centre=True, apres=2)
    para(d, "سلام تام بوجود مولانا الإمام، وبعد،", taille=12, apres=4)
    pluriel = len(profs) > 1
    if sens == "demande":
        debut = ("وتذكيراً بطلبنا السابق في الموضوع، " if rappel else "")
        corps = (debut + "يشرفني أن أطلب منكم الملف الإداري والتربوي "
                 + ("للأطر المذكورين في الجدول أسفله، الملتحقين" if pluriel else "للأستاذ(ة) المذكور(ة) أسفله، الملتحق(ة)")
                 + " بمؤسستنا:")
    else:
        debut = ("بناء على مراسلتكم المشار إليها في المرجع أعلاه، " if _propre(reference) else "")
        corps = (debut + "يشرفني أن أوافيكم بالملف الإداري والتربوي "
                 + ("للأطر المذكورين في الجدول أسفله:" if pluriel else "للأستاذ(ة) المذكور(ة) أسفله:"))
    para(d, corps, taille=12, apres=4)
    _table(d, ["ر.ت", "الاسم والنسب", "رقم التأجير", "ملاحظات"],
           [[f"{i:02d}", n, _ltr(p), o] for i, (n, p, o) in enumerate(profs, 1)], [1.3, 6.6, 3.5, 6.0], taille=12)
    para(d, "", apres=4)
    para(d, "وتقبلوا أزكى التحيات.", taille=12, centre=True, apres=4)
    _signature(d, conn, "توقيع رئيس(ة) المؤسسة:")
    rep = dossier.archives / "ملفات الأساتذة"
    rep.mkdir(parents=True, exist_ok=True)
    chemin = rep / f"{datetime.now():%Y%m%d_%H%M%S}_{('طلب' if sens == 'demande' else 'إرسال')}_ملف_{profs[0][0]}.docx" \
        .replace(" ", "_")
    n = 1
    while chemin.exists():
        n += 1
        chemin = chemin.with_name(f"{chemin.stem}_{n}.docx")
    d.save(chemin)
    if pids:
        noter_envoi(conn, pids, sens, numero, le, rappel, etab_cible)
    return chemin, numero


# ---------- تتبع الملفات (طلب المدير 2026-11-19) ----------
# الصفحة الثابتة تتبع لكل أستاذ: هل ملفه موجود بالمؤسسة (خانة «الملف متوفر» في الموارد البشرية، وهي التي
# يقرؤها محضر تسليم المهام)، وطلبات الملف وتذكيراتها وإرساله، برقم الصادر وتاريخه.

ENSEIGNANTS = ("enseignant", "educatrice")


def _cle(pid: int) -> str:
    return f"dossier_prof:{int(pid)}"


def historique(conn: sqlite3.Connection, pid: int) -> list[dict]:
    from idara.services import fiches
    return list((fiches.lire(conn, _cle(pid)) or {}).get("envois", []))


def noter_envoi(conn: sqlite3.Connection, pids: list[int], sens: str, numero: str, le: str, rappel: bool,
                etab: str) -> None:
    from idara.services import fiches
    for pid in pids:
        h = historique(conn, pid)
        h.append({"sens": sens, "rappel": bool(rappel), "numero": numero, "date": le, "etab": etab})
        fiches.ecrire(conn, _cle(pid), {"envois": h})


def marquer_recu(conn: sqlite3.Connection, pid: int, recu: bool = True) -> None:
    """التوصل بملف الأستاذ: يحيّن خانة «الملف متوفر» فيتحيّن محضر تسليم المهام."""
    with conn:
        conn.execute("UPDATE personnel SET dossier_disponible=? WHERE id=?", (int(recu), pid))


def suivi(conn: sqlite3.Connection) -> list[dict]:
    """الأساتذة في العمل (الملف بالمؤسسة أو لا، والطلبات)، والمغادرون (إرسال ملفهم)."""
    from idara.services import personnel as rh
    res = []
    for p in rh.lister(conn, actifs_seulement=False):
        if p.categorie not in ENSEIGNANTS:
            continue
        h = historique(conn, p.id)
        demandes = [x for x in h if x["sens"] == "demande"]
        envois = [x for x in h if x["sens"] == "envoi"]
        actif = p.statut == "actif"
        if actif:
            etat = "recu" if p.dossier_disponible else ("demande" if demandes else "a_demander")
        else:
            etat = "envoye" if envois else "a_envoyer"
        res.append({"pid": p.id, "nom": f"{p.prenom_ar} {p.nom_ar}", "ppr": p.ppr or "", "actif": actif,
                    "recu": bool(p.dossier_disponible), "demandes": demandes, "envois": envois, "etat": etat,
                    "derniere": (demandes or envois or [None])[-1]})
    return res
