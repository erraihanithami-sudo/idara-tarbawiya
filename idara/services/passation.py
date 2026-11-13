"""محضر تسليم مهام الإدارة التربوية (نموذج المدير 2026-11-12).

المحضر مقسم إلى محاور على ترتيب نموذج المدير. لكل محور خانات و/أو جدول:
- ما يوجد في البرنامج يُقترح آلياً: المؤسسة والوحدات، المدير الحالي، الموظفون وملفاتهم، أعداد التلاميذ، سجل الصادر،
  الوثائق المولَّدة، التأمين المدرسي، جمعية النجاح، مشروع المؤسسة.
- الباقي يُدخله المدير (البنايات، السكنيات، التجهيزات، الكتب، المفاتيح، الأختام، اللجنة...).
- «تحديث من البرنامج» يعيد الأرقام والأسطر الآلية، ويحتفظ بما أُدخل يدوياً في الخانات اليدوية.
- كل محور يمكن إخفاؤه من المحضر أو تغيير موضعه (القرار 8: بنية المحضر اختيارية).
الوثيقة تُبنى على شكل النموذج: صفحة غلاف، أشرطة عناوين المحاور، وفي أسفل كل صفحة «المدير السابق · التاريخ ·
المدير الجديد» ورقم الصفحة. لا نقط مكان معطى ناقص: الخانة الفارغة تبقى فارغة.
"""

from __future__ import annotations

import csv
import json
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from idara.data.dossier import DossierDonnees
from idara.data.journal import journaliser
from idara.services import annee as annee_srv
from idara.services import etablissement as etab_srv
from idara.services import personnel as rh
from idara.services import textes as tx


class ErreurPassation(ValueError):
    """رسالة موجهة للمدير بالعربية."""


@dataclass(frozen=True)
class Champ:
    cle: str
    libelle: str
    long: bool = False        # نص متعدد الأسطر


@dataclass(frozen=True)
class Section:
    cle: str
    titre: str
    champs: tuple = ()
    colonnes: tuple = ()
    groupes: tuple = ()          # رأس من مستويين: ((العنوان، عدد الأعمدة)...)؛ 1 = خانة تمتد على السطرين
    numero: bool = False         # عمود «ر.ت» يُضاف عند التوليد
    deux_colonnes: bool = False  # لائحة طويلة (عنوان، عدد) تُعرض في نصفين متجاورين
    total: tuple = ()            # الأعمدة المجموعة في سطر «المجموع»
    manuels: tuple = ()          # أعمدة يدوية تُحفظ عند التحديث (الباقي من البرنامج)
    fusion: bool = False         # دمج الخانات المتطابقة المتتالية في العمود الأول (الوحدة)
    source: str = ""
    defaut: tuple = ()           # أسطر مقترحة حين لا تتوفر معطيات في البرنامج
    annexe: bool = False         # لائحة طويلة: في المتن عدد العناوين والنسخ، والتفصيل في ملحق آخر المحضر


C = Champ
SECTIONS: list[Section] = [
    Section("etablissement", "تعريف المؤسسة",
            champs=(C("nom", "اسم المؤسسة"), C("code", "رمزها"), C("commune", "الجماعة"),
                    C("date_creation", "تاريخ إحداثها"), C("nb_unites", "عدد الفرعيات")),
            source="من إعداد المؤسسة والوحدات المدرسية. تاريخ الإحداث يُدخل يدوياً."),
    Section("parties", "طرفا عملية تسليم المهام",
            champs=(C("ancien_nom", "المدير السابق: الاسم الكامل"), C("ancien_ppr", "رقم التأجير"),
                    C("ancien_date", "تاريخ التعيين بالمؤسسة"), C("ancien_qualite", "بصفة (رسمية، مؤقتة)"),
                    C("nouveau_nom", "المدير الجديد: الاسم الكامل"), C("nouveau_ppr", "رقم التأجير"),
                    C("nouveau_poste", "مقر العمل السابق"), C("nouveau_direction", "المديرية"),
                    C("nouveau_type", "التعيين (رسمي أو مؤقت)"), C("decision", "قرار الإسناد")),
            source="المدير السابق: المدير المسجل حالياً في البرنامج. المدير الجديد يُدخل يدوياً."),
    Section("ressources", "البنية البشرية بالمؤسسة",
            champs=(C("dossiers_partis", "عدد ملفات الأساتذة المنتقلين والمتقاعدين"),
                    C("nb_eleves", "مجموع التلاميذ بالمؤسسة")),
            colonnes=("الفئة", "العدد", "الملفات المتوفرة", "الملفات غير المتوفرة", "ملاحظات"),
            total=(1, 2, 3), manuels=(4,),
            source="من الموارد البشرية: الموظفون في العمل (عدا المدير) حسب الفئة، وخانة «الملف متوفر»؛ "
                   "ومن لوائح التلاميذ الحاضرين."),
    Section("eleves", "وثائق المتعلمين",
            colonnes=("الوحدات المدرسية", "عدد التلاميذ", "الملفات المدرسية: المتوفر", "الملفات المدرسية: الخصاص",
                      "الملفات الصحية: المتوفر", "الملفات الصحية: الخصاص",
                      "المنقطعون: الملفات المدرسية المتوفرة"),
            groupes=(("الوحدات المدرسية", 1), ("عدد التلاميذ", 1), ("الملفات المدرسية", 2), ("الملفات الصحية", 2),
                     ("المنقطعون: الوثائق المتوفرة", 1)),
            numero=True, total=(1, 2, 3, 4, 5), manuels=(2, 3, 4, 5, 6),
            source="الوحدات وعدد تلاميذها الحاضرين من البرنامج؛ الملفات المتوفرة والخصاص تُدخل يدوياً."),
    Section("personnel", "ملفات الموظفين",
            colonnes=("الأستاذ(ة)", "رقم التأجير", "الوضعية الإدارية", "الملف (متوفر – غير متوفر)", "ملاحظات"),
            numero=True, manuels=(4,),
            source="من الموارد البشرية: الموظفون في العمل (عدا المدير)، وإطارهم، وخانة «الملف متوفر»."),
    Section("batiments", "البنايات (حجرات، مستودع، مرافق)",
            colonnes=("الوحدات المدرسية", "أنواع البنايات", "عددها", "مستعملة – غير مستعملة", "صالحة – غير صالحة",
                      "ملاحظات"),
            fusion=True, source="من صفحة البنية المادية (المكونات وأعدادها لكل وحدة) إن أُدخل فيها شيء، وإلا أسطر مقترحة لكل وحدة. الحالة (مستعملة، صالحة) تُدخل يدوياً."),
    Section("logements", "السكنيات",
            champs=(C("autres", "معلومات أخرى عن السكن بالمؤسسة", long=True),),
            colonnes=("الوحدات المدرسية", "رقم السكنية", "نوعها (صلب، مفكك)", "وظيفية – إدارية",
                      "من يشغلها (الاسم – ر.ت)", "ملاحظات"),
            source="يدوي."),
    Section("equip_admin", "تجهيزات الإدارة",
            colonnes=("النوع", "العدد", "رقم الجرد", "الحالة: صالح", "الحالة: يحتاج صيانة", "الحالة: معطل",
                      "ملاحظات"),
            groupes=(("النوع", 1), ("العدد", 1), ("رقم الجرد", 1), ("الحالة", 3), ("ملاحظات", 1)),
            numero=True, total=(1, 3, 4, 5), manuels=(6,), source="من سجل الجرد (التجهيزات غير الممحوة وحالة صيانتها) إن أُدخل فيه شيء، وإلا يدوي."),
    Section("equip_classes", "تجهيزات الحجرات الدراسية",
            colonnes=("الوحدة المدرسية", "عدد القاعات", "سبورة خشبية", "سبورة ألمنيوم", "سبورة متحركة",
                      "عدد المقاعد", "مكتب الأستاذ", "كرسي الأستاذ", "رفوف مكتبية"),
            total=(1, 2, 3, 4, 5, 6, 7, 8), manuels=(1, 2, 3, 4, 5, 6, 7, 8),
            source="سطر لكل وحدة مدرسية؛ الأعداد تُدخل يدوياً."),
    Section("moyens", "الوسائل التعليمية والموارد الرقمية", colonnes=("النوع", "العدد", "ملاحظات"), numero=True,
            source="يدوي."),
    Section("ordinateurs", "الحواسيب المسلمة للأساتذة",
            colonnes=("الاسم الكامل", "رقم التأجير", "الجهاز", "الرقم التسلسلي", "تاريخ التسليم",
                      "ملاحظات (الاسترجاع عند الانتقال أو التقاعد)"),
            numero=True, manuels=(5,),
            source="من إسناد التجهيزات للموظفين (القطع غير المسترجعة) إن أُدخل شيء، وإلا يدوي. محور مقترح، "
                   "غير موجود في النموذج الأصلي."),
    Section("livres", "الكتب والمراجع", colonnes=("الكتاب", "العدد"), deux_colonnes=True, annexe=True,
            source="يدوي، أو استيراد لائحة من Excel (العمود الأول العنوان والثاني العدد). في المحضر: عدد "
                   "العناوين والنسخ، واللائحة المفصلة في ملحق آخر المحضر."),
    Section("bibliotheque", "مكتبة المدرسة", colonnes=("الكتاب", "العدد"), deux_colonnes=True, annexe=True,
            source="يدوي، أو استيراد لائحة من Excel (العمود الأول العنوان والثاني العدد). في المحضر: عدد "
                   "العناوين والنسخ، واللائحة المفصلة في ملحق آخر المحضر."),
    Section("registres_eleves", "السجلات والدفاتر: سجلات التلاميذ",
            champs=(C("date_biens", "تاريخ حصر سجل الممتلكات"),),
            colonnes=("الوحدة المدرسية", "العدد", "الرقم الأخير", "تاريخه", "ملاحظات"),
            manuels=(1, 2, 3, 4),
            source="سطر لكل وحدة؛ الأرقام يدوية. تتقدمه جملة تصريح المدير الجديد بالتحقق من سجل الممتلكات."),
    Section("registres", "مختلف السجلات",
            colonnes=("نوع السجل", "العدد", "تاريخ ورقم بداية السجل", "الرقم الأخير وتاريخه", "ملاحظات"),
            manuels=(1, 4), source="سجل الصادرات من سجل الصادر في البرنامج؛ الباقي يدوي."),
    Section("documents", "باقي الوثائق الإدارية والتربوية", colonnes=("الموضوع", "العدد"), deux_colonnes=True,
            manuels=(1,), source="أعداد مقترحة من الوثائق المولَّدة في البرنامج، وتُصحح يدوياً."),
    Section("jardinage", "البستنة المدرسية", colonnes=("النوع", "العدد", "ملاحظات"), numero=True, source="يدوي."),
    Section("sport_equip", "تجهيزات التربية البدنية والرياضة المدرسية", colonnes=("النوع", "العدد", "ملاحظات"),
            numero=True, source="يدوي."),
    Section("associations", "الجمعيات المدرسية",
            colonnes=("الجمعية", "تاريخ التأسيس", "تاريخ التجديد", "الرئيس", "الأمين", "الرصيد (درهم)",
                      "آخر وضعية: المداخيل", "آخر وضعية: النفقات", "ملاحظات (ملف الجمعية...)"),
            groupes=(("الجمعية", 1), ("تاريخ التأسيس", 1), ("تاريخ التجديد", 1), ("الرئيس", 1), ("الأمين", 1),
                     ("الرصيد (درهم)", 1), ("آخر وضعية بسجل", 2), ("ملاحظات", 1)),
            manuels=(1, 2, 3, 4, 5, 6, 7, 8),
            source="جدول واحد للتعاونية المدرسية والجمعية الرياضية وجمعية الآباء. ما سُجل منها في البرنامج يُقترح "
                   "(الرئيس، الأمين، تاريخ التجديد)، والباقي يدوي. جمعية النجاح في محورها."),
    Section("sportive", "ممتلكات الجمعية الرياضية",
            colonnes=("النوع", "العدد", "رقم الجرد", "حالتها (جيدة – متلاشية)", "ملاحظات"), numero=True,
            source="يدوي."),
    Section("assurance", "التأمين المدرسي خلال الموسم الدراسي الحالي",
            champs=(C("nb_eleves", "عدد تلاميذ المؤسسة"), C("nb_assures", "عدد المنخرطين في التأمين المدرسي"),
                    C("montant", "المبلغ الإجمالي المودع (بالدرهم)"), C("societe", "في حساب الشركة")),
            source="من صفحة التسجيلات (واجب التأمين)؛ اسم الشركة يُدخل يدوياً."),
    Section("najah", "جمعية دعم مدرسة النجاح",
            champs=(C("date_creation", "تاريخ الإحداث"), C("date_renouvellement", "تاريخ التجديد"),
                    C("rib", "رقم الحساب البريدي"), C("solde_banque", "الرصيد في الحساب البريدي (درهم)"),
                    C("date_banque", "تاريخ آخر وضعية إدارية (الحساب)"), C("solde_caisse", "رصيد الصندوق (درهم)"),
                    C("date_caisse", "تاريخ آخر وضعية إدارية (الصندوق)"), C("total", "مجموع رصيد الجمعية (درهم)"),
                    C("releves", "عدد كشوفات الحساب الجارية وآخر تاريخ"),
                    C("rapports", "عدد التقارير المالية وآخرها"), C("cachets", "عدد أختام الجمعية")),
            colonnes=("سجلات الجمعية", "تاريخ أول عملية", "تاريخ آخر عملية"), manuels=(),
            source="من صفحة الجمعية: الحساب، الأرصدة، وتواريخ أول وآخر عملية في كل سجل. الكشوفات يدوية."),
    Section("najah_cheques", "جمعية دعم مدرسة النجاح: دفاتر الشيكات",
            colonnes=("الدفتر", "من رقم", "إلى رقم", "الحالة (مستعمل، غير مستعمل، ملغى)", "ملاحظات"),
            numero=True, source="يدوي: سطر لكل مجموعة شيكات متتالية لها نفس الحالة."),
    Section("projet", "مشروع المؤسسة",
            champs=(C("document", "وثيقة المشروع (متوفرة – غير متوفرة)"),),
            colonnes=("عنوان المشروع", "مجالاته", "فترة الإنجاز: من", "إلى", "المساهمون", "التكلفة الإجمالية",
                      "نسبة الإنجاز"),
            groupes=(("عنوان المشروع", 1), ("مجالاته", 1), ("فترة الإنجاز", 2), ("المساهمون", 1),
                     ("التكلفة الإجمالية", 1), ("نسبة الإنجاز", 1)),
            source="من صفحة مشروع المؤسسة: العنوان، المجالات، المساهمون، المبلغ المبرمج، ومتوسط نسبة الإنجاز."),
    Section("cles", "المفاتيح المسلمة للمدير الجديد", colonnes=("طبيعة المفاتيح", "عددها", "ملاحظات"),
            source="أنواع مقترحة؛ الأعداد يدوية.",
            defaut=(("مفاتيح الحجرات الدراسية", "", ""), ("مفاتيح السكنيات", "", ""),
                    ("مفاتيح الإدارة التربوية", "", ""), ("مفاتيح المدخل الرئيسي للمركزية والوحدات المدرسية", "", ""))),
    Section("declarations", "التصريحات والتوقيعات",
            champs=(C("ancien", "تصريح المدير السابق", long=True), C("nouveau", "تصريح المدير الجديد", long=True)),
            source="يدوي. التوقيعات بأسماء طرفي التسليم."),
    Section("cachets", "الأختام الخاصة بإدارة المؤسسة", colonnes=("نوع الخاتم", "العدد"), deux_colonnes=True,
            source="يدوي (يمكن ترك النوع فارغاً لختمه في المحضر الورقي)."),
    Section("commission", "أعضاء لجنة التسليم", colonnes=("الاسم والنسب", "الصفة", "التوقيع"), numero=True,
            source="يدوي.", defaut=(("", "", ""), ("", "", ""))),
]
PAR_CLE = {s.cle: s for s in SECTIONS}
GENERAL = (C("date_pv", "تاريخ المحضر (يظهر في أسفل كل صفحة)"), C("intitule", "عنوان المحضر في صفحة الغلاف"),
           C("etab_titre", "المؤسسة في صفحة الغلاف"), C("ville", "حرر ب"))


# ---------- المعطيات الآلية ----------

def _annee_id(conn) -> int | None:
    a = annee_srv.annee_courante(conn)
    return a["id"] if a else None


def _unites(conn) -> list[tuple[int | None, str]]:
    us = [(r[0], r[1]) for r in conn.execute("SELECT id, nom_ar FROM unite_scolaire ORDER BY id")]
    if us and etab_srv.est_groupe(conn):
        return us
    e = etab_srv.lire_etablissement(conn)
    return [(None, e.nom_ar if e else "المؤسسة")]


def _effectifs(conn) -> dict[int | None, int]:
    aid = _annee_id(conn)
    res: dict[int | None, int] = {}
    for r in conn.execute("SELECT c.unite_id, COUNT(*) FROM inscription i LEFT JOIN classe c ON c.id=i.classe_id "
                          "WHERE i.annee_id=? AND i.statut IN ('inscrit','arrive') GROUP BY c.unite_id", (aid,)):
        res[r[0]] = r[1]
    return res


def _d(v) -> str:
    try:
        return tx.date_chiffres(v) if v else ""
    except (ValueError, TypeError):
        return str(v or "")


def _nb(n) -> str:
    return "" if n is None else f"{n:02d}" if isinstance(n, int) else str(n)


def _mt(x) -> str:
    return "" if x is None else f"{x:,.2f}".replace(",", " ")


def _directeur_id(conn) -> int | None:
    d = etab_srv.directeur_actuel(conn)
    return d["id"] if d else None


def _auto_general(conn) -> dict:
    e = etab_srv.lire_etablissement(conn)
    titre = ""
    if e:
        titre = e.nom_ar if not etab_srv.est_groupe(conn) or e.nom_ar.startswith(("مجموعة", "م.م", "م/م")) \
            else f"مجموعة مدارس {e.nom_ar}"
    return {"champs": {"date_pv": "", "intitule": "محضر تسليم مهام الإدارة التربوية", "etab_titre": titre,
                       "ville": (e.ville_redaction_ar or e.commune_ar) if e else ""}}


def _auto_etablissement(conn) -> dict:
    e = etab_srv.lire_etablissement(conn)
    if not e:
        return {"champs": {}}
    # الوحدة الأولى هي المركزية (ترتيب الإدخال في الإعداد)، والباقي فرعيات
    fil = max(0, len(_unites(conn)) - 1) if etab_srv.est_groupe(conn) else 0
    return {"champs": {"nom": e.nom_ar, "code": e.code_etab, "commune": e.commune_ar,
                       "nb_unites": _nb(fil) if fil else ""}}


def _auto_parties(conn) -> dict:
    d = etab_srv.directeur_actuel(conn)
    if not d:
        return {"champs": {}}
    return {"champs": {"ancien_nom": f"{d['prenom_ar']} {d['nom_ar']}", "ancien_ppr": d["ppr"] or "",
                       "ancien_date": _d(d["mandat_debut"])}}


_ENSEIGNANTS = ("enseignant", "educatrice")


def _auto_ressources(conn) -> dict:
    tous = rh.lister(conn, actifs_seulement=False)
    did = _directeur_id(conn)
    actifs = [p for p in tous if p.statut == "actif" and p.id != did and p.categorie != "directeur"]
    partis = [p for p in tous if p.statut != "actif" and p.categorie in _ENSEIGNANTS and p.dossier_disponible]
    lignes = []
    for cat, (_, _, pluriel) in rh.CATEGORIES.items():
        ps_ = [p for p in actifs if p.categorie == cat]
        if ps_:
            dispo = sum(1 for p in ps_ if p.dossier_disponible)
            lignes.append([pluriel, _nb(len(ps_)), _nb(dispo), _nb(len(ps_) - dispo), ""])
    return {"champs": {"dossiers_partis": _nb(len(partis)), "nb_eleves": _nb(sum(_effectifs(conn).values()))},
            "lignes": lignes}


def _auto_eleves(conn) -> dict:
    eff = _effectifs(conn)
    us = _unites(conn)
    vide = ["", "", "", "", ""]
    sans_unite = sum(n for u, n in eff.items() if u is None or u not in {x for x, _ in us})
    if (len(us) == 1 and us[0][0] is None) or sans_unite == sum(eff.values()):
        # مؤسسة مستقلة، أو أقسام لم تُسند بعد إلى وحداتها: سطر واحد للمؤسسة
        e = etab_srv.lire_etablissement(conn)
        return {"lignes": [[e.nom_ar if e else us[0][1], str(sum(eff.values()))] + vide]}
    lignes = [[nom, str(eff.get(uid, 0))] + vide for uid, nom in us]
    if sans_unite:
        lignes.append(["أقسام غير مسندة إلى وحدة", str(sans_unite)] + vide)
    return {"lignes": lignes}


def _situation(p: rh.Personnel) -> str:
    if p.cadre:
        return rh.cadre_accorde(p.cadre, p.sexe)
    return rh.libelle_categorie(p.categorie, p.sexe)


def _auto_personnel(conn) -> dict:
    did = _directeur_id(conn)
    ps = [p for p in rh.lister(conn) if p.id != did and p.categorie != "directeur"]
    return {"lignes": [[f"{p.prenom_ar} {p.nom_ar}", p.ppr or "", _situation(p),
                        "متوفر" if p.dossier_disponible else "غير متوفر", p.remarques or ""] for p in ps]}


def _auto_batiments(conn) -> dict:
    from idara.services import structure as st
    lignes = st.pour_passation(conn)      # صفحة البنية المادية (2026-11-13) إن أُدخل فيها شيء
    if lignes:
        return {"lignes": lignes}
    locaux = conn.execute("SELECT u.nom_ar AS unite, l.type, COUNT(*) n, SUM(l.en_usage) u, SUM(l.bon_etat) b "
                          "FROM local l LEFT JOIN unite_scolaire u ON u.id=l.unite_id GROUP BY l.unite_id, l.type "
                          "ORDER BY u.id, l.type").fetchall()
    if locaux:
        return {"lignes": [[r["unite"] or "", r["type"], _nb(r["n"]),
                            "مستعملة" if r["u"] == r["n"] else "غير مستعملة" if not r["u"] else f"مستعملة: {r['u']}",
                            "صالحة" if r["b"] == r["n"] else "غير صالحة" if not r["b"] else f"صالحة: {r['b']}", ""]
                           for r in locaux]}
    return {"lignes": [[nom, t, "", "", "", ""] for _, nom in _unites(conn)
                       for t in ("حجرة دراسية", "مكتب", "مرافق صحية")]}


def _auto_equip_admin(conn) -> dict:
    from idara.services import inventaire as inv
    lignes = inv.pour_passation(conn)      # سجل الجرد (2026-11-13) إن أُدخل فيه شيء
    if lignes:
        return {"lignes": lignes}
    arts = conn.execute("SELECT designation, quantite, num_inv_debut, num_inv_fin, qte_bon, qte_maintenance, qte_hs "
                        "FROM article_inventaire ORDER BY id").fetchall()
    lignes = []
    for a in arts:
        q = a["quantite"] or 0
        inv = ""
        if a["num_inv_debut"]:
            fin = a["num_inv_fin"] or (a["num_inv_debut"] + q - 1)
            inv = str(a["num_inv_debut"]) if fin <= a["num_inv_debut"] else f"{a['num_inv_debut']} - {fin}"
        lignes.append([a["designation"], _nb(q), inv, _nb(a["qte_bon"] or 0), _nb(a["qte_maintenance"] or 0),
                       _nb(a["qte_hs"] or 0), ""])
    return {"lignes": lignes}


def _auto_ordinateurs(conn) -> dict:
    try:
        rs = conn.execute(
            "SELECT p.prenom_ar, p.nom_ar, p.ppr, ai.designation, e.num_serie, a.date_remise, a.remarque "
            "FROM affectation_equipement a JOIN equipement e ON e.id=a.equipement_id "
            "JOIN article_inventaire ai ON ai.id=e.article_id JOIN personnel p ON p.id=a.personnel_id "
            "WHERE a.date_retour IS NULL ORDER BY p.nom_ar, p.prenom_ar").fetchall()
    except sqlite3.Error:
        rs = []
    return {"lignes": [[f"{r['prenom_ar']} {r['nom_ar']}", r["ppr"] or "", r["designation"], r["num_serie"] or "",
                        _d(r["date_remise"]), r["remarque"] or ""] for r in rs]}


_ASSOCIATIONS = (("cooperative", "التعاونية المدرسية"), ("sportive", "الجمعية الرياضية"),
                 (None, "جمعية آباء وأولياء التلاميذ"))


def _auto_associations(conn) -> dict:
    lignes = []
    for typ, nom in _ASSOCIATIONS:
        a = conn.execute("SELECT * FROM association WHERE type=?", (typ,)).fetchone() if typ else None
        lignes.append([nom, "", _d(a["date_renouvellement"]) if a else "", (a["president"] or "") if a else "",
                       (a["tresorier"] or "") if a else "", "", "", "", ""])
    return {"lignes": lignes}


def _auto_equip_classes(conn) -> dict:
    return {"lignes": [[nom] + [""] * 8 for _, nom in _unites(conn)]}


def _auto_registres_eleves(conn) -> dict:
    us = _unites(conn)
    if len(us) == 1:
        return {"lignes": [["سجل التلاميذ", "", "", "", ""]]}
    return {"lignes": [[f"سجل تلاميذ {'' if i == 0 else 'فرعية '}{nom}", "", "", "", ""]
                       for i, (_, nom) in enumerate(us)]}


def _auto_registres(conn) -> dict:
    q = ("SELECT k.numero, k.date_courrier, a.code_court FROM courrier k JOIN annee_scolaire a ON a.id=k.annee_id "
         "WHERE k.sens='sortant' ORDER BY k.date_courrier {o}, k.id {o} LIMIT 1")
    premier, dernier = (conn.execute(q.format(o=o)).fetchone() for o in ("ASC", "DESC"))
    sortants = ["سجل الصادرات", "01", "", "", ""]
    if premier:
        sortants[2] = f"{_d(premier['date_courrier'])} - {premier['numero']}/{premier['code_court']}"
        sortants[3] = f"{_d(dernier['date_courrier'])} - {dernier['numero']}/{dernier['code_court']}"
    return {"lignes": [sortants, ["سجل الواردات", "01", "", "", ""], ["سجل الممتلكات", "01", "", "", ""]]}


def _compte(conn, sql: str, *args) -> int:
    try:
        return conn.execute(sql, args).fetchone()[0] or 0
    except sqlite3.Error:
        return 0


def _auto_documents(conn) -> dict:
    def docs(*codes) -> int:
        return _compte(conn, f"SELECT COUNT(*) FROM document_genere d JOIN modele_document m ON m.id=d.modele_id "
                             f"WHERE m.code IN ({','.join('?' * len(codes))})", *codes)
    lignes = [["التنظيم التربوي الحالي", _nb(docs("tanzim_tarbawi") or 1)],
              ["محاضر مجالس المؤسسة", _nb(_compte(conn, "SELECT COUNT(*) FROM conseil_seance"))],
              ["القانون الداخلي للمؤسسة", "01"],
              ["نتائج مجالس الأقسام", _nb(_compte(conn, "SELECT COUNT(*) FROM conseil_niveau"))],
              ["لائحة الوسائل التعليمية", "01"],
              ["محاضر الدخول والخروج", _nb(_compte(conn, "SELECT COUNT(*) FROM pv_collectif"))]]
    return {"lignes": lignes}


def _auto_assurance(conn) -> dict:
    from idara.services import frais_inscription as fr
    try:
        t = fr.totaux(conn)
    except Exception:   # noqa: BLE001 (لا سنة جارية أو لا تلاميذ)
        return {"champs": {}}
    a = t["elements"].get("assurance", {})
    return {"champs": {"nb_eleves": _nb(t["eleves"]), "nb_assures": _nb(a.get("payes", 0)),
                       "montant": _mt(a.get("montant"))}}


def _auto_najah(conn) -> dict:
    from idara.services import associations as asso
    a = asso.association(conn, "najah")
    ch = {"rib": (a["rib"] or "") if a else "", "date_renouvellement": _d(a["date_renouvellement"]) if a else ""}
    ex = asso.exercices(conn, "najah") if a else []
    lignes = []
    if ex:
        e = ex[0]
        for x in ex:
            if (x["date_debut"] or "") > (e["date_debut"] or ""):
                e = x
        s = asso.soldes(conn, e["id"])
        ch.update({"solde_banque": _mt(s["banque"]), "solde_caisse": _mt(s["caisse"]),
                   "total": _mt(s["banque"] + s["caisse"])})
        for reg, lib, cle in (("banque", "سجل البنك", "date_banque"), ("caisse", "سجل الصندوق", "date_caisse"),
                              (None, "سجل العمليات", None)):
            r = conn.execute("SELECT MIN(o.date_op), MAX(o.date_op) FROM operation_financiere o JOIN exercice x "
                             "ON x.id=o.exercice_id WHERE x.association_id=? AND (? IS NULL OR o.registre=?)",
                             (a["id"], reg, reg)).fetchone()
            lignes.append([lib, _d(r[0]), _d(r[1])])
            if cle and r[1]:
                ch[cle] = _d(r[1])
        lignes.append(["سجل تسليم الشيكات", "", ""])
    return {"champs": ch, "lignes": lignes}


def _auto_projet(conn) -> dict:
    from idara.services import projet_etab as pe
    p = pe.projet_actif(conn)
    if not p:
        return {"lignes": []}
    ops = pe.operations(conn, p["id"])
    s = pe.synthese_operations(conn, p["id"])
    domaines = " – ".join(dict.fromkeys(o["domaine"] or o["axe"] for o in ops if (o["domaine"] or o["axe"])))
    contrib = "، ".join(dict.fromkeys(o["contributeur"] for o in ops if o["contributeur"]))
    taux = f"{s['taux_global']:g}%" if s["taux_global"] is not None else ""
    return {"lignes": [[f"مشروع المؤسسة المندمج: {p['annee_debut']}-{p['annee_fin']}", domaines,
                        f"{p['annee_debut']}/09/01", f"{p['annee_fin']}/07/31", contrib,
                        _mt(s["montant_programme"]) if s["montant_programme"] else "", taux]]}


AUTO = {"_general": _auto_general, "etablissement": _auto_etablissement, "parties": _auto_parties,
        "ressources": _auto_ressources, "eleves": _auto_eleves, "personnel": _auto_personnel,
        "batiments": _auto_batiments, "equip_admin": _auto_equip_admin, "equip_classes": _auto_equip_classes,
        "registres_eleves": _auto_registres_eleves, "registres": _auto_registres, "documents": _auto_documents,
        "assurance": _auto_assurance, "najah": _auto_najah, "projet": _auto_projet,
        "ordinateurs": _auto_ordinateurs, "associations": _auto_associations}


def _auto(conn, cle: str) -> dict:
    f = AUTO.get(cle)
    d = f(conn) if f else {}
    d.setdefault("champs", {})
    d.setdefault("lignes", [])
    s = PAR_CLE.get(cle)
    if s and not d["lignes"] and s.defaut:
        d["lignes"] = [list(x) for x in s.defaut]
    return d


# ---------- الحفظ ----------

# ---------- المحاور التي يضيفها المدير (2026-11-13) ----------

def _perso(conn) -> list[Section]:
    res = []
    for r in conn.execute("SELECT * FROM passation_perso ORDER BY rowid"):
        cols = tuple(json.loads(r["colonnes"] or "[]"))
        res.append(Section(r["cle"], r["titre"], colonnes=cols, numero=bool(cols),
                           champs=(C("texte", "النص", long=True),) if r["avec_texte"] or not cols else (),
                           source="محور أضفتموه إلى المحضر: كل معطياته يدوية."))
    return res


def section(conn: sqlite3.Connection, cle: str) -> Section:
    if cle in PAR_CLE:
        return PAR_CLE[cle]
    for s in _perso(conn):
        if s.cle == cle:
            return s
    raise ErreurPassation("محور غير معروف.")


def ajouter_section(conn: sqlite3.Connection, titre: str, colonnes: list[str] | str = (), texte: bool = False) -> str:
    """يضيف محوراً خاصاً: عنوان، وأعمدة جدول (مفصولة بفاصلة إن كانت نصاً) و/أو نص حر. يُدرج في آخر المحضر."""
    titre = " ".join((titre or "").split())
    if not titre:
        raise ErreurPassation("عنوان المحور إجباري.")
    if isinstance(colonnes, str):
        colonnes = colonnes.replace("،", ",").split(",")
    cols = [" ".join(c.split()) for c in colonnes if c and c.strip()]
    if len(cols) > 8:
        raise ErreurPassation("ثمانية أعمدة على الأكثر حتى يتسع الجدول للصفحة.")
    if len(set(cols)) != len(cols):
        raise ErreurPassation("أسماء الأعمدة مكررة.")
    if titre in {s.titre for s in SECTIONS} | {s.titre for s in _perso(conn)}:
        raise ErreurPassation("يوجد محور بهذا العنوان.")
    n = conn.execute("SELECT COUNT(*) FROM passation_perso").fetchone()[0] + 1
    cle = f"perso_{n}"
    while conn.execute("SELECT 1 FROM passation_perso WHERE cle=?", (cle,)).fetchone():
        n += 1
        cle = f"perso_{n}"
    with conn:
        conn.execute("INSERT INTO passation_perso(cle, titre, colonnes, avec_texte) VALUES (?,?,?,?)",
                     (cle, titre, json.dumps(cols, ensure_ascii=False), int(texte or not cols)))
    _ecrire_etat(conn, sections(conn))      # يأخذ موضعه في آخر الترتيب الحالي
    return cle


def supprimer_section(conn: sqlite3.Connection, cle: str) -> None:
    if cle in PAR_CLE:
        raise ErreurPassation("محاور النموذج لا تُحذف: أزل علامتها لإخفائها من المحضر.")
    section(conn, cle)
    with conn:
        conn.execute("DELETE FROM passation_perso WHERE cle=?", (cle,))
        conn.execute("DELETE FROM passation_section WHERE cle=?", (cle,))


def _largeur(cle: str, s: Section | None = None) -> int:
    s = s or PAR_CLE.get(cle)
    return len(s.colonnes) if s else 0


def _normaliser(cle: str, donnees: dict, s: Section | None = None) -> dict:
    n = _largeur(cle, s)
    lignes = []
    for l in donnees.get("lignes", []):
        l = [" ".join(str(v if v is not None else "").split()) for v in l][:n] if n else []
        l += [""] * (n - len(l))
        if any(l):
            lignes.append(l)
    champs = {k: str(v if v is not None else "").strip() for k, v in donnees.get("champs", {}).items()}
    return {"champs": champs, "lignes": lignes}


def lire(conn: sqlite3.Connection, cle: str) -> dict:
    """معطيات المحور: المحفوظة، وإلا المقترحة من البرنامج."""
    s = None if cle == "_general" else section(conn, cle)
    r = conn.execute("SELECT donnees FROM passation_section WHERE cle=?", (cle,)).fetchone()
    if r and r[0]:
        return _normaliser(cle, _adapter(conn, cle, json.loads(r[0])), s)
    return _normaliser(cle, _auto(conn, cle), s)


# محاور تغيرت أعمدتها بعد الإصدار الأول (التحسينات التي وافق عليها المدير 2026-11-13)
_REFAITS = {"ressources", "equip_admin"}


def _adapter(conn, cle: str, d: dict) -> dict:
    """معطيات محفوظة بأعمدة قديمة: تُنقل الخانات حسب اسم العمود، وما لم يعد له مكان يُترك. إن لم تُحفظ أسماء
    الأعمدة (الإصدار الأول) والمحور أعيد تصميمه، تؤخذ أسطره من البرنامج وتبقى الخانات."""
    s = PAR_CLE.get(cle)
    if not s or not s.colonnes:
        return d
    anciennes = d.get("colonnes")
    if anciennes is None:
        if cle in _REFAITS:
            return {"champs": d.get("champs", {}), "lignes": _auto(conn, cle)["lignes"]}
        return d
    if list(anciennes) == list(s.colonnes):
        return d
    pos = {c: i for i, c in enumerate(anciennes)}
    return {"champs": d.get("champs", {}),
            "lignes": [[l[pos[c]] if c in pos and pos[c] < len(l) else "" for c in s.colonnes]
                       for l in d.get("lignes", [])]}


def enregistrer(conn: sqlite3.Connection, cle: str, donnees: dict) -> None:
    s = None if cle == "_general" else section(conn, cle)
    d = _normaliser(cle, donnees, s)
    if cle == "_general" and d["champs"].get("date_pv"):
        try:
            date.fromisoformat(d["champs"]["date_pv"])
        except ValueError:
            raise ErreurPassation("تاريخ المحضر غير صحيح.") from None
    with conn:
        conn.execute("INSERT INTO passation_section(cle, donnees, maj_le) VALUES (?,?,datetime('now','localtime')) "
                     "ON CONFLICT(cle) DO UPDATE SET donnees=excluded.donnees, maj_le=excluded.maj_le",
                     (cle, json.dumps({**d, "colonnes": list(s.colonnes) if s else []}, ensure_ascii=False)))


def actualiser(conn: sqlite3.Connection, cle: str) -> dict:
    """يعيد ما يأتي من البرنامج، ويحتفظ بما أُدخل يدوياً: الخانات التي لا يقترحها البرنامج، والأعمدة اليدوية
    للأسطر الموافقة (حسب العمود الأول)."""
    actuel = lire(conn, cle)
    auto = _normaliser(cle, _auto(conn, cle), None if cle == "_general" else section(conn, cle))
    champs = dict(actuel["champs"])
    champs.update({k: v for k, v in auto["champs"].items() if v})
    s = PAR_CLE.get(cle)
    lignes = actuel["lignes"]
    if s and cle in AUTO and auto["lignes"]:
        anciens = {l[0]: l for l in actuel["lignes"]}
        lignes = []
        for l in auto["lignes"]:
            a = anciens.get(l[0])
            if a:
                l = [a[j] if (j in s.manuels or not v) and a[j] else v for j, v in enumerate(l)]
            lignes.append(l)
    d = {"champs": champs, "lignes": lignes}
    enregistrer(conn, cle, d)
    return lire(conn, cle)


def reinitialiser(conn: sqlite3.Connection, cle: str) -> dict:
    """يحذف ما أُدخل في المحور ويعود إلى المقترح من البرنامج."""
    with conn:
        conn.execute("UPDATE passation_section SET donnees=NULL WHERE cle=?", (cle,))
    return lire(conn, cle)


def sections(conn: sqlite3.Connection) -> list[tuple[Section, bool]]:
    """المحاور بترتيبها الحالي، مع هل تُدرج في المحضر."""
    etat = {r["cle"]: r for r in conn.execute("SELECT cle, actif, ordre FROM passation_section")}
    res = []
    for i, s in enumerate(SECTIONS + _perso(conn)):
        r = etat.get(s.cle)
        ordre = r["ordre"] if r and r["ordre"] is not None else i
        res.append((ordre, i, s, bool(r["actif"]) if r else True))
    return [(s, a) for _, _, s, a in sorted(res, key=lambda x: (x[0], x[1]))]


def _ecrire_etat(conn, ordre: list[tuple[Section, bool]]) -> None:
    with conn:
        for i, (s, a) in enumerate(ordre):
            conn.execute("INSERT INTO passation_section(cle, actif, ordre) VALUES (?,?,?) "
                         "ON CONFLICT(cle) DO UPDATE SET actif=excluded.actif, ordre=excluded.ordre",
                         (s.cle, int(a), i))


def activer(conn: sqlite3.Connection, cle: str, actif: bool) -> None:
    _ecrire_etat(conn, [(s, actif if s.cle == cle else a) for s, a in sections(conn)])


def deplacer(conn: sqlite3.Connection, cle: str, pas: int) -> None:
    l = sections(conn)
    i = next(k for k, (s, _) in enumerate(l) if s.cle == cle)
    j = max(0, min(len(l) - 1, i + pas))
    l.insert(j, l.pop(i))
    _ecrire_etat(conn, l)


def retablir_ordre(conn: sqlite3.Connection) -> None:
    """ترتيب النموذج، وكل المحاور مدرجة."""
    _ecrire_etat(conn, [(s, True) for s in SECTIONS + _perso(conn)])


# ---------- استيراد لائحة (الكتب...) ----------

def importer_liste(chemin: Path | str) -> list[list[str]]:
    """من Excel أو CSV: العمود الأول العنوان والثاني العدد. يُتجاوز سطر العناوين وما لا عنوان له، ويُقبل ملف
    بنصفين متجاورين (عنوان، عدد، عنوان، عدد) كما في المحضر."""
    chemin = Path(chemin)
    if chemin.suffix.lower() in (".csv", ".txt"):
        texte = chemin.read_text(encoding="utf-8-sig")
        sep = ";" if texte.count(";") >= texte.count(",") and ";" in texte else ","
        brut = list(csv.reader(texte.splitlines(), delimiter=sep))
    elif chemin.suffix.lower() in (".xlsx", ".xlsm"):
        import openpyxl
        wb = openpyxl.load_workbook(chemin, read_only=True, data_only=True)
        brut = [list(r) for ws in wb.worksheets for r in ws.iter_rows(values_only=True)]
        wb.close()
    else:
        raise ErreurPassation("صيغة غير مدعومة: Excel (xlsx) أو CSV.")
    res = []
    for r in brut:
        cases = ["" if v is None else str(v).strip() for v in r]
        for k in range(0, len(cases), 2):
            titre, n = cases[k], cases[k + 1] if k + 1 < len(cases) else ""
            if not titre or titre in ("الكتاب", "العنوان", "النوع", "الموضوع"):
                continue
            if n.endswith(".0"):
                n = n[:-2]
            res.append([titre, n.zfill(2) if n.isdigit() else n])
    if not res:
        raise ErreurPassation("لم يُعثر على أي عنوان في الملف.")
    return res


# ---------- التوليد ----------

JAUNE, VERT_CLAIR, BLEU_CLAIR = "FFC000", "C5E0B3", "BDD6EE"


def _cellule(c, texte: str, gras=False, taille=None, centre=True) -> None:
    """يكتب في الخلية بعد حذف كل فقراتها (الخلايا المدمجة تجمع فقرات الخلايا الأصلية)."""
    from idara.services.docs_association import para
    for p in list(c.paragraphs):
        p._element.getparent().remove(p._element)
    para(c, texte, gras, taille, centre, apres=0)


def _bande(d, titre: str) -> None:
    from idara.services.docs_association import _ombre, para, tableau
    t = tableau(d, 1, 1, bordures=False, largeurs=[17.4])
    _cellule(t.cell(0, 0), titre, gras=True, taille=12)
    _ombre(t.cell(0, 0), JAUNE)
    t.cell(0, 0).paragraphs[0].paragraph_format.keep_with_next = True
    para(d, "", apres=2, taille=4).paragraph_format.keep_with_next = True


def _fusionner_vertical(t, col: int, debut: int, fin: int) -> None:
    if fin > debut:
        a = t.cell(debut, col)
        texte = a.text
        a.merge(t.cell(fin, col))
        _cellule(a, texte, taille=10)


def _largeurs(n: int, numero: bool, premier: float = 0.0) -> list[float]:
    total = 17.4
    l = []
    if numero:
        l.append(1.0)
        total -= 1.0
    if premier:
        l.append(premier)
        total -= premier
        n -= 1
    return l + [round(total / n, 2)] * n if n else l


_LARGEURS = {
    "eleves": [1.0, 3.4, 1.8, 1.8, 1.8, 1.8, 1.8, 4.0],
    "personnel": [1.0, 4.0, 2.4, 4.1, 2.8, 3.1],
    "batiments": [3.6, 3.8, 1.6, 2.7, 2.7, 3.0],
    "logements": [3.0, 2.0, 2.4, 2.6, 4.0, 3.4],
    "equip_classes": [2.9, 1.6, 1.6, 1.7, 1.6, 1.6, 1.6, 1.6, 1.6],
    "registres_eleves": [5.5, 1.6, 2.2, 3.0, 5.1],
    "registres": [3.3, 1.4, 4.2, 4.2, 4.3],
    "najah": [5.8, 5.8, 5.8],
    "projet": [2.6, 4.2, 1.8, 1.8, 3.0, 2.0, 2.0],
    "cles": [8.0, 2.4, 7.0],
    "commission": [1.0, 5.4, 5.0, 6.0],
    "sportive": [1.0, 4.6, 1.6, 3.0, 3.4, 3.8],
    "ressources": [5.4, 2.4, 3.0, 3.0, 3.6],
    "equip_admin": [1.0, 4.2, 1.4, 2.8, 1.6, 2.0, 1.6, 2.8],
    "ordinateurs": [1.0, 3.6, 2.2, 2.6, 2.8, 2.2, 3.0],
    "associations": [3.2, 1.7, 1.7, 2.0, 2.0, 1.7, 1.7, 1.7, 1.7],
    "najah_cheques": [1.0, 3.0, 2.4, 2.4, 4.6, 4.0],
}


def _tableau_section(d, s: Section, lignes: list[list[str]]) -> None:
    from idara.services.docs_association import _ombre, para, tableau
    if not lignes:     # جدول فارغ: أسطر بيضاء تُملأ باليد في المحضر الورقي
        lignes = [[""] * len(s.colonnes) for _ in range(3)]
    if s.deux_colonnes:
        moitie = (len(lignes) + 1) // 2
        t = tableau(d, 1 + moitie, 4, largeurs=[6.9, 1.8, 6.9, 1.8])
        for j, h in enumerate(list(s.colonnes) * 2):
            _cellule(t.cell(0, j), h, gras=True, taille=10)
            _ombre(t.cell(0, j), "F7CAAC")
        for i in range(moitie):
            for k, l in enumerate((lignes[i], lignes[moitie + i] if moitie + i < len(lignes) else ["", ""])):
                _cellule(t.cell(1 + i, 2 * k), l[0], taille=10)
                _cellule(t.cell(1 + i, 2 * k + 1), l[1], taille=10)
        para(d, "", apres=4, taille=6)
        return
    entetes = (["ر.ت"] if s.numero else []) + list(s.colonnes)
    deux = bool(s.groupes)
    total = bool(s.total) and lignes
    n = len(entetes)
    t = tableau(d, (2 if deux else 1) + len(lignes) + (1 if total else 0), n,
                largeurs=_LARGEURS.get(s.cle) or _largeurs(n, s.numero))
    dec = 1 if s.numero else 0
    if deux:
        if s.numero:
            _cellule(t.cell(0, 0), "ر.ت", gras=True, taille=10)
            t.cell(0, 0).merge(t.cell(1, 0))
        j = dec
        for lib, span in s.groupes:
            if span == 1:
                c = t.cell(0, j).merge(t.cell(1, j))
                _cellule(c, lib, gras=True, taille=10)
            else:
                c = t.cell(0, j).merge(t.cell(0, j + span - 1))
                _cellule(c, lib, gras=True, taille=10)
                for k in range(span):
                    sous = s.colonnes[j - dec + k].split(": ", 1)[-1] if ": " in s.colonnes[j - dec + k] \
                        else s.colonnes[j - dec + k]
                    _cellule(t.cell(1, j + k), sous, gras=True, taille=9)
            j += span
        for i in range(2):
            for c in t.rows[i].cells:
                _ombre(c, VERT_CLAIR)
    else:
        for j, h in enumerate(entetes):
            _cellule(t.cell(0, j), h, gras=True, taille=10)
            _ombre(t.cell(0, j), BLEU_CLAIR)
    debut = 2 if deux else 1
    for i, l in enumerate(lignes):
        valeurs = ([f"{i + 1:02d}"] if s.numero else []) + l
        for j, v in enumerate(valeurs):
            _cellule(t.cell(debut + i, j), v, taille=10)
    if s.fusion and lignes:
        k = 0
        while k < len(lignes):
            m = k
            while m + 1 < len(lignes) and lignes[m + 1][0] == lignes[k][0]:
                m += 1
            _fusionner_vertical(t, dec, debut + k, debut + m)
            k = m + 1
    if total:
        r = debut + len(lignes)
        _cellule(t.cell(r, dec), "المجموع", gras=True, taille=10)
        _ombre(t.cell(r, dec), VERT_CLAIR)
        if s.numero:
            t.cell(r, 0).merge(t.cell(r, dec))
            _cellule(t.cell(r, 0), "المجموع", gras=True, taille=10)
        for j in s.total:
            vals = [l[j] for l in lignes]
            nombres = []
            for v in vals:
                try:
                    nombres.append(int(v))
                except ValueError:
                    pass
            _cellule(t.cell(r, dec + j), _nb(sum(nombres)) if nombres else "", gras=True, taille=10)
    para(d, "", apres=4, taille=6)


def _champs_section(d, s: Section, champs: dict) -> None:
    """الخانات زوجين في كل سطر (كما في النموذج)، والنصوص الطويلة سطراً كاملاً."""
    from idara.services.docs_association import para, tableau
    courts = [(c, champs.get(c.cle, "")) for c in s.champs if not c.long]
    longs = [(c, champs.get(c.cle, "")) for c in s.champs if c.long]
    if courts:
        n = (len(courts) + 1) // 2
        t = tableau(d, n, 2, bordures=s.cle == "etablissement", largeurs=[9.2, 8.2])
        for i, (c, v) in enumerate(courts):
            _cellule(t.cell(i // 2, i % 2), f"{c.libelle}: {v}" if v else f"{c.libelle}:", taille=11,
                     centre=False)
    for c, v in longs:
        if not s.cle.startswith("perso_"):      # محور أضافه المدير: النص وحده، دون عنوان «النص»
            para(d, f"{c.libelle}:", gras=True, taille=11, apres=0)
        for l in (v or "").splitlines() or [""]:
            if l.strip():
                para(d, l, taille=11, apres=0)
    para(d, "", apres=2, taille=6)


def _pied(d, date_pv: str) -> None:
    """أسفل كل صفحة: المدير السابق · التاريخ · المدير الجديد، ثم رقم الصفحة."""
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    from idara.services.docs_association import para
    s = d.sections[0]
    from docx.shared import Cm
    s.footer_distance = Cm(0.6)
    pied = s.footer
    for p in list(pied.paragraphs):
        p._element.getparent().remove(p._element)
    from docx.enum.table import WD_TABLE_ALIGNMENT
    t = pied.add_table(1, 3, Cm(17.4))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t._tbl.tblPr.append(OxmlElement("w:bidiVisual"))
    for j, v in enumerate(("المدير السابق", date_pv, "المدير الجديد")):
        _cellule(t.cell(0, j), v, gras=True, taille=10)
    p = para(pied, "", centre=True, apres=0)
    r = p.add_run()
    for typ, texte in (("begin", None), (None, "PAGE"), ("end", None)):
        if typ:
            e = OxmlElement("w:fldChar")
            e.set(qn("w:fldCharType"), typ)
        else:
            e = OxmlElement("w:instrText")
            e.set(qn("xml:space"), "preserve")
            e.text = texte
        r._element.append(e)


def _couverture(d, conn, dossier: DossierDonnees, g: dict) -> None:
    from docx.shared import Cm

    from idara.services.docs_association import para, saut_page
    e = etab_srv.lire_etablissement(conn)
    if e and e.logo_path and (dossier.racine / e.logo_path).exists():
        d.add_picture(str(dossier.racine / e.logo_path), width=Cm(17.4))
    elif e:
        for l in ("المملكة المغربية", "وزارة التربية الوطنية والتعليم الأولي والرياضة", e.academie_ar,
                  e.direction_ar, e.nom_ar):
            if l:
                para(d, l, gras=True, taille=11, apres=0)
    for _ in range(7):
        para(d, "", apres=6)
    para(d, g.get("intitule") or "محضر تسليم مهام الإدارة التربوية", gras=True, taille=30, centre=True, apres=6)
    if g.get("etab_titre"):
        para(d, g["etab_titre"], gras=True, taille=30, centre=True, apres=6)
    para(d, "بتاريخ: " + (_d(g["date_pv"]) if g.get("date_pv") else ""), gras=True, taille=26, centre=True)
    saut_page(d)


def _texte_registres(champs: dict) -> str:
    dt = champs.get("date_biens", "")
    return ("يصرح السيد المدير الجديد أنه تحقق من كل ما هو مثبت بسجل الممتلكات الموجود فعلاً بالمؤسسة التي تسلم "
            "مهامها يومه بما في ذلك السجل المذكور وقد حصر بتاريخ: " + (dt or ""))


def resume_liste(lignes: list[list[str]]) -> str:
    """«عدد العناوين: 12، عدد النسخ: 40» (العدد غير الرقمي لا يُجمع)."""
    nb = 0
    for l in lignes:
        try:
            nb += int(l[1])
        except (ValueError, IndexError):
            pass
    return f"عدد العناوين: {_nb(len(lignes))}، عدد النسخ: {_nb(nb)}"


def generer(conn: sqlite3.Connection, dossier: DossierDonnees) -> Path:
    from idara.services.docs_association import _nouveau, para, saut_page, tableau
    g = lire(conn, "_general")["champs"]
    actives = [s for s, a in sections(conn) if a]
    if not actives:
        raise ErreurPassation("لا محور مدرج في المحضر: فعّل محوراً واحداً على الأقل.")
    d = _nouveau()
    sec = d.sections[0]
    from docx.shared import Cm
    sec.left_margin = sec.right_margin = Cm(1.8)
    sec.top_margin, sec.bottom_margin = Cm(1.3), Cm(2.0)
    sec.different_first_page_header_footer = True     # صفحة الغلاف دون تذييل
    _couverture(d, conn, dossier, g)
    parties = lire(conn, "parties")["champs"]
    annexes: list[tuple[Section, list]] = []
    for s in actives:
        donnees = lire(conn, s.cle)
        _bande(d, s.titre)
        if s.annexe and donnees["lignes"]:
            annexes.append((s, donnees["lignes"]))
            para(d, resume_liste(donnees["lignes"]) + f" (اللائحة المفصلة في الملحق رقم {len(annexes)}).",
                 taille=11, apres=6)
            continue
        if s.cle == "registres_eleves":
            para(d, _texte_registres(donnees["champs"]), taille=11, apres=4)
        elif s.cle == "declarations":
            for c in s.champs:
                para(d, f"{c.libelle}:", gras=True, souligne=True, taille=11, apres=0)
                v = donnees["champs"].get(c.cle, "")
                for l in v.splitlines() if v else []:
                    para(d, l, taille=11, apres=0)
                if not v:
                    para(d, "", apres=14)
            para(d, "التوقيعات:", gras=True, souligne=True, taille=12, centre=True, apres=4)
            t = tableau(d, 2, 2, bordures=False, largeurs=[8.7, 8.7])
            for j, (lib, cle) in enumerate((("المدير السابق", "ancien_nom"), ("المدير الجديد", "nouveau_nom"))):
                _cellule(t.cell(0, j), lib, gras=True, taille=11)
                _cellule(t.cell(1, j), parties.get(cle, ""), gras=True, taille=11)
            para(d, "", apres=30)
            continue
        elif s.champs and s.cle != "projet":
            _champs_section(d, s, donnees["champs"])
        if s.colonnes and (donnees["lignes"] or not s.champs or s.cle in ("projet", "ressources")):
            if s.cle == "najah":
                para(d, "سجلات الجمعية:", gras=True, souligne=True, taille=11, apres=2)
            _tableau_section(d, s, donnees["lignes"])
        if s.cle == "projet":
            v = donnees["champs"].get("document", "")
            para(d, f"وثيقة المشروع: {v}", gras=True, taille=11, apres=6)
    para(d, "", apres=6)
    ville = g.get("ville", "")
    para(d, f"حرر ب: {ville}، بتاريخ: {_d(g['date_pv']) if g.get('date_pv') else ''}", taille=12, centre=True, apres=8)
    para(d, "توقيع وخاتم المدير الإقليمي", gras=True, taille=12, centre=True)
    for i, (s, lignes) in enumerate(annexes, start=1):
        saut_page(d)
        para(d, f"الملحق رقم {i}: {s.titre}", gras=True, taille=14, centre=True, apres=2)
        para(d, resume_liste(lignes) + ".", taille=11, centre=True, apres=6)
        _tableau_section(d, s, lignes)
    _pied(d, _d(g.get("date_pv")) if g.get("date_pv") else "")
    rep = dossier.archives / "تسليم المهام"
    rep.mkdir(parents=True, exist_ok=True)
    chemin = rep / f"{datetime.now():%Y%m%d_%H%M%S}_محضر_تسليم_المهام.docx"
    n = 1
    while chemin.exists():
        n += 1
        chemin = chemin.with_name(f"{chemin.stem}_{n}.docx")
    d.save(chemin)
    journaliser(conn, "generation", "passation", None, chemin.name)
    return chemin
