"""قواعد التحقق التي تفرضها القاعدة نفسها (منقولة من اختبار التصميم v0.2). بيانات وهمية."""

import sqlite3


def test_regles_de_la_base(conn):
    db = conn
    results = []
    def expect(name, sql, params=(), ok=True):
        try:
            db.execute(sql, params); db.commit(); passed = ok; err = ""
        except sqlite3.Error as e:
            db.rollback(); passed = not ok; err = str(e)
        results.append((name, "مقبول" if ok else "مرفوض", passed, err))

    E = "INSERT INTO eleve(code_massar,num_registre,nom_ar,prenom_ar,sexe,source) VALUES (?,?,?,?,?,?)"
    expect("T01 إعداد المؤسسة", "INSERT INTO etablissement(id,nom_ar) VALUES (1,'مدرسة تجريبية')")
    expect("T02 منع مؤسسة ثانية", "INSERT INTO etablissement(id,nom_ar) VALUES (2,'أخرى')", ok=False)
    expect("T03 سنة دراسية", "INSERT INTO annee_scolaire(id,libelle,code_court,est_courante) VALUES (1,'2026/2027','26-27',1)")
    expect("T04 منع سنتين جاريتين", "INSERT INTO annee_scolaire(id,libelle,code_court,est_courante) VALUES (2,'2027/2028','27-28',1)", ok=False)
    expect("T05 سنة ثانية غير جارية", "INSERT INTO annee_scolaire(id,libelle,code_court) VALUES (2,'2027/2028','27-28')")
    expect("T06 صيغة سنة خاطئة", "INSERT INTO annee_scolaire(libelle,code_court) VALUES ('2026-27','x')", ok=False)
    expect("T07 تلميذ مسار", E, ("X123456789", None, "تجريبي", "أحمد", "M", "massar"))
    expect("T08 رمز مسار مكرر", E, ("X123456789", None, "آخر", "علي", "M", "massar"), ok=False)
    expect("T09 رمز مسار بصيغة خاطئة", E, ("X12345", None, "آخر", "علي", "M", "massar"), ok=False)
    expect("T10 تلميذ دون أي معرف", E, (None, None, "آخر", "علي", "M", "manuel"), ok=False)
    expect("T11 تلميذ ما قبل مسار برقم السجل فقط", E, (None, 9001, "قديم", "سعيد", "M", "avant_massar"))
    expect("T12 رقم سجل مكرر", E, (None, 9001, "قديم2", "رشيد", "M", "avant_massar"), ok=False)
    expect("T13 المسار التاريخي", "INSERT INTO eleve_avant_massar(eleve_id,date_entree,date_sortie,dernier_niveau) VALUES (2,'1990-09-15','1996-06-30','القسم الخامس')")
    db.execute("INSERT INTO classe(id,annee_id,code) VALUES (1,1,'1APG-2APG-3APG')")
    db.commit()
    I = "INSERT INTO inscription(eleve_id,annee_id,classe_id,niveau_id,statut,date_sortie) VALUES (?,?,?,?,?,?)"
    expect("T14 تسجيل سنوي", I, (1, 1, 1, 1, "inscrit", None))
    expect("T15 تسجيل مكرر في نفس السنة", I, (1, 1, 1, 1, "inscrit", None), ok=False)
    expect("T16 تسجيل نفس التلميذ في سنة أخرى", I, (1, 2, None, 1, "inscrit", None))
    expect("T17 مغادرة دون تاريخ", "UPDATE inscription SET statut='parti' WHERE id=1", ok=False)
    expect("T18 مغادرة بتاريخ", "UPDATE inscription SET statut='parti', date_sortie='2026-12-01' WHERE id=1")
    expect("T19 منع حذف تلميذ له تاريخ", "DELETE FROM eleve WHERE id=1", ok=False)
    expect("T20 قسم مكرر في نفس السنة", "INSERT INTO classe(annee_id,code) VALUES (1,'1APG-2APG-3APG')", ok=False)
    C = "INSERT INTO courrier(sens,annee_id,numero,date_courrier,objet) VALUES (?,?,?,?,?)"
    expect("T21 صادر رقم 98", C, ("sortant", 1, 98, "2026-11-02", "ورقة إرسال"))
    expect("T22 نفس الرقم في نفس السنة", C, ("sortant", 1, 98, "2026-11-03", "أخرى"), ok=False)
    expect("T23 نفس الرقم كوارد", C, ("entrant", 1, 98, "2026-11-03", "وارد"))
    expect("T24 نفس الرقم في سنة أخرى", C, ("sortant", 2, 98, "2027-11-03", "أخرى"))
    A = "INSERT INTO article_inventaire(designation,quantite,qte_bon,qte_maintenance,qte_hs) VALUES (?,?,?,?,?)"
    expect("T25 جرد بحالة مفصلة 18=13+3+2", A, ("حاسوب مكتبي", 18, 13, 3, 2))
    expect("T26 حالات لا تساوي العدد", A, ("حاسوب مكتبي", 18, 13, 3, 1), ok=False)
    db.execute("INSERT INTO personnel(id,nom_ar,prenom_ar,sexe,categorie) VALUES (1,'أستاذ','تجريبي','F','enseignant')")
    db.execute("INSERT INTO personnel(id,nom_ar,prenom_ar,sexe,categorie) VALUES (2,'أستاذ','ثان','M','enseignant')")
    db.execute("INSERT INTO equipement(id,article_id,num_serie) VALUES (1,1,'SN-TEST-1')"); db.commit()
    F = "INSERT INTO affectation_equipement(equipement_id,personnel_id,date_remise,date_retour) VALUES (?,?,?,?)"
    expect("T27 إسناد حاسوب", F, (1, 1, "2026-09-01", None))
    expect("T28 إسناد نفس الحاسوب لثان قبل استرجاعه", F, (1, 2, "2026-09-02", None), ok=False)
    expect("T29 استرجاع ثم إسناد جديد", "UPDATE affectation_equipement SET date_retour='2026-10-01' WHERE id=1")
    expect("T30 الإسناد الجديد بعد الاسترجاع", F, (1, 2, "2026-10-02", None))
    K = "INSERT INTO conge(personnel_id,type_conge_id,date_debut,duree_jours,date_fin,prolongation_de) VALUES (?,?,?,?,?,?)"
    expect("T31 رخصة", K, (1, 1, "2026-02-10", 10, "2026-02-19", None))
    expect("T32 تمديد مرتبط بالرخصة الأولى", K, (1, 1, "2026-02-20", 10, "2026-03-01", 1))
    expect("T33 نهاية قبل البداية", K, (1, 1, "2026-02-10", 3, "2026-02-01", None), ok=False)
    expect("T34 مدة صفرية", K, (1, 1, "2026-02-10", 0, "2026-02-10", None), ok=False)

    # --- v0.2: البيانات المرجعية والموارد البشرية ---
    def count(t): return db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    results.append(("T35 المستويات المرجعية = 8", "مقبول", count("niveau")==8, ""))
    results.append(("T36 حالات الاستئناف = 10 (كما في المحضر الحقيقي)", "مقبول", count("cas_reprise")==10, ""))
    results.append(("T37 إصدار القاعدة = آخر ترحيل (2)", "مقبول", db.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]==2, ""))
    R = "INSERT INTO reprise_travail(personnel_id,conge_id,cas_reprise_id,date_debut_absence,date_fin_absence,date_reprise) VALUES (?,?,?,?,?,?)"
    expect("T38 محضر استئناف بعد رخصة", R, (1, 2, 6, "2026-02-10", "2026-03-01", "2026-03-02"))
    expect("T39 محضر ثان لنفس الرخصة", R, (1, 2, 6, "2026-02-10", "2026-03-01", "2026-03-02"), ok=False)
    expect("T40 استئناف بعد تغيب دون رخصة", R, (2, None, 10, "2026-04-06", "2026-04-08", "2026-04-09"))
    expect("T41 استئناف قبل نهاية الغياب", R, (2, None, 10, "2026-04-06", "2026-04-08", "2026-04-08"), ok=False)
    expect("T42 طلب تعويض مسجل على الرخصة", "UPDATE conge SET demande_remplacement=1 WHERE id=1")
    expect("T43 قيمة غير صالحة لطلب التعويض", "UPDATE conge SET demande_remplacement=2 WHERE id=1", ok=False)
    expect("T44 عدد تلاميذ سالب", "UPDATE personnel SET nb_eleves=-1 WHERE id=1", ok=False)
    C2 = "INSERT INTO courrier(sens,annee_id,numero,date_courrier,objet,conge_id) VALUES (?,?,?,?,?,?)"
    expect("T45 صادر مرتبط بملف الرخصة", C2, ("sortant", 1, 99, "2026-02-21", "طلب رخصة", 1))

    echecs = [f"{n} (المتوقع: {e}) {err}" for n, e, ok, err in results if not ok]
    assert not echecs, "\n".join(echecs)
    assert len(results) == 45
