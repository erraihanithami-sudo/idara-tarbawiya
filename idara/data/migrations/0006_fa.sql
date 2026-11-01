-- تدبير الفائض (المذكرة الإطار، الفقرة 3.1).
-- الاستثناء: الأساتذة المبرزون، وحاملو الدكتوراه الذين قضوا 5 سنوات على الأقل بهذه الصفة.
ALTER TABLE personnel ADD COLUMN exemption_fa TEXT CHECK (exemption_fa IS NULL OR exemption_fa IN ('agrege','doctorat'));
ALTER TABLE personnel ADD COLUMN date_exemption_fa TEXT;   -- تاريخ الحصول على الدكتوراه

CREATE TABLE poste_requis (                  -- عدد الأساتذة اللازم حسب البنية التربوية، لكل مادة وسنة
  annee_id INTEGER NOT NULL REFERENCES annee_scolaire(id),
  matiere  TEXT NOT NULL,
  nombre   INTEGER NOT NULL CHECK (nombre >= 0),
  PRIMARY KEY (annee_id, matiere)
);
