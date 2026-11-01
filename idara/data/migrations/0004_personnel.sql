-- المرحلة 6: ملف الموظفين.
-- ملاحظات (لمحضر التسليم: ملفات الموظفين)، وإسناد الأقسام لكل سنة
-- حتى يُحسب مستوى التدريس وعدد التلاميذ آلياً في وثائق الرخص.
ALTER TABLE personnel ADD COLUMN remarques TEXT;

CREATE TABLE affectation_classe (
  id           INTEGER PRIMARY KEY,
  personnel_id INTEGER NOT NULL REFERENCES personnel(id) ON DELETE CASCADE,
  classe_id    INTEGER NOT NULL REFERENCES classe(id) ON DELETE CASCADE,
  UNIQUE (personnel_id, classe_id)
);
CREATE INDEX idx_affectation_classe ON affectation_classe(classe_id);
