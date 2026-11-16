-- reconstruction
-- بطاقة التلميذ (توجيهات المدير 2026-11-15): مستوى تحكم كل تلميذ في كل مادة لكل رائز ومرحلة،
-- من ملف النتائج المستورد أو بإدخال المدير. المرحلة -1: الرائز القبلي، 0: الرائز البعدي، 1..8: المراحل.
CREATE TABLE isa_eleve (
  annee_id    INTEGER NOT NULL REFERENCES annee_scolaire(id),
  code_massar TEXT NOT NULL,
  eleve_id    INTEGER REFERENCES eleve(id),
  classe      TEXT,
  phase       INTEGER NOT NULL CHECK (phase BETWEEN -1 AND 8),
  matiere     TEXT NOT NULL CHECK (matiere IN ('ar','fr','ma')),
  niveau      TEXT NOT NULL CHECK (niveau IN ('A','B','C')),
  source      TEXT,
  PRIMARY KEY (annee_id, code_massar, phase, matiere)
);
CREATE INDEX idx_isa_eleve_eleve ON isa_eleve(eleve_id);

-- الرائز القبلي في جدول نسب التحكم (المرحلة -1)، بجانب الرائز البعدي (0) والمراحل.
CREATE TABLE isa_phase_n (
  annee_id INTEGER NOT NULL REFERENCES annee_scolaire(id),
  classe   TEXT NOT NULL,
  phase    INTEGER NOT NULL CHECK (phase BETWEEN -1 AND 8),   -- -1: الرائز القبلي، 0: الرائز البعدي، 1..: المرحلة
  matiere  TEXT NOT NULL CHECK (matiere IN ('ar','fr','ma')),
  valeur   REAL NOT NULL CHECK (valeur BETWEEN 0 AND 100),
  PRIMARY KEY (annee_id, classe, phase, matiere)
);
INSERT INTO isa_phase_n SELECT annee_id, classe, phase, matiere, valeur FROM isa_phase;
DROP TABLE isa_phase;
ALTER TABLE isa_phase_n RENAME TO isa_phase;
