-- reconstruction: إعادة بناء جدول classe (المفاتيح الخارجية معطلة خلال الترحيل ثم تُفحص)
-- في المجموعة المدرسية قد تحمل أقسام وحدتين نفس الاسم في مسار (مثلاً 1APG-1)، وكان القيد UNIQUE(annee_id, code)
-- يدمجهما في قسم واحد (خطأ أبلغ عنه المدير 2026-11-09). القسم يُعرَّف الآن بالسنة والوحدة والاسم.
CREATE TABLE classe_nouvelle (
  id        INTEGER PRIMARY KEY,
  annee_id  INTEGER NOT NULL REFERENCES annee_scolaire(id),
  unite_id  INTEGER REFERENCES unite_scolaire(id),
  code      TEXT NOT NULL                    -- اسم الورقة في مسار: 4APG-5APG-6APG
);
INSERT INTO classe_nouvelle(id, annee_id, unite_id, code) SELECT id, annee_id, unite_id, code FROM classe;
DROP TABLE classe;
ALTER TABLE classe_nouvelle RENAME TO classe;
CREATE UNIQUE INDEX ux_classe_annee_unite_code ON classe(annee_id, COALESCE(unite_id, 0), code);
