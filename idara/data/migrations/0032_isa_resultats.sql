-- مؤشر ISA2 محسوب من نتائج الروائز (طلب المدير 2026-11-12):
-- لكل قسم ومادة ومرحلة: عدد التلاميذ في كل مستوى تحكم (A تام، B مقنع، C ضعيف).
-- المرحلة -1: الرائز القبلي، 0: الرائز البعدي، 1..8: مراحل التعليم الصريح.
CREATE TABLE isa_resultat (
  annee_id INTEGER NOT NULL REFERENCES annee_scolaire(id),
  classe   TEXT NOT NULL,
  phase    INTEGER NOT NULL CHECK (phase BETWEEN -1 AND 8),
  matiere  TEXT NOT NULL CHECK (matiere IN ('ar','fr','ma')),
  nb_a     INTEGER NOT NULL DEFAULT 0 CHECK (nb_a >= 0),
  nb_b     INTEGER NOT NULL DEFAULT 0 CHECK (nb_b >= 0),
  nb_c     INTEGER NOT NULL DEFAULT 0 CHECK (nb_c >= 0),
  source   TEXT,
  PRIMARY KEY (annee_id, classe, phase, matiere)
);
