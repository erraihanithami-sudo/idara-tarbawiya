-- مؤسسات الريادة (طلب المدير 2026-11-02: «كل ذلك مهم»):
-- مؤشر ISA2 حسب مراحل التعليم الصريح (يُدخله المدير من مسار)، مسارات الدعم من تصدير «مجموعات الدعم»،
-- وملف شارة الريادة (الوثائق العشرون من «معايير الريادة»).
CREATE TABLE isa_phase (
  annee_id INTEGER NOT NULL REFERENCES annee_scolaire(id),
  classe   TEXT NOT NULL,
  phase    INTEGER NOT NULL CHECK (phase BETWEEN 0 AND 8),   -- 0: الرائز البعدي، 1..: المرحلة
  matiere  TEXT NOT NULL CHECK (matiere IN ('ar','fr','ma')),
  valeur   REAL NOT NULL CHECK (valeur BETWEEN 0 AND 100),
  PRIMARY KEY (annee_id, classe, phase, matiere)
);
CREATE TABLE tarl_parcours (                   -- مسار الدعم لكل قسم ومادة (تصدير «مجموعات الدعم»)
  annee_id INTEGER NOT NULL REFERENCES annee_scolaire(id),
  classe   TEXT NOT NULL,
  matiere  TEXT NOT NULL,
  parcours TEXT NOT NULL,
  PRIMARY KEY (annee_id, classe, matiere)
);
CREATE TABLE riyada_piece (                    -- ملف شارة الريادة: توفر كل وثيقة
  annee_id   INTEGER NOT NULL REFERENCES annee_scolaire(id),
  numero     INTEGER NOT NULL CHECK (numero BETWEEN 1 AND 20),
  disponible INTEGER NOT NULL DEFAULT 0 CHECK (disponible IN (0,1)),
  observation TEXT,
  PRIMARY KEY (annee_id, numero)
);
