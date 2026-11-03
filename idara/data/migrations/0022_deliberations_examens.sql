-- محاضر نهاية الأسدوس والامتحان (ملفا المدير، 2026-11-03).
-- معدلا الامتحان الموحد المحلي والإقليمي للسادس (من ملف مسار «مجمل المعدلات»).
ALTER TABLE resultat ADD COLUMN exam_local REAL;
ALTER TABLE resultat ADD COLUMN exam_prov REAL;

-- قرار مجلس القسم لكل تلميذ: الإنذار أو التوبيخ والتوجيه (يقررهما المجلس، لا تُحسب من المعدل)
CREATE TABLE deliberation (
  annee_id    INTEGER NOT NULL REFERENCES annee_scolaire(id),
  periode     TEXT NOT NULL CHECK (periode IN ('S1','S2')),
  code_massar TEXT NOT NULL,
  sanction    TEXT CHECK (sanction IS NULL OR sanction IN ('إنذار','توبيخ')),
  orientation TEXT,
  PRIMARY KEY (annee_id, periode, code_massar)
);

-- الامتحان: المحلي (تلاميذ السادس من لوائح المؤسسة) أو الإقليمي (لائحة المديرية بأرقامها وقاعاتها)
CREATE TABLE examen (
  id          INTEGER PRIMARY KEY,
  annee_id    INTEGER NOT NULL REFERENCES annee_scolaire(id),
  type        TEXT NOT NULL CHECK (type IN ('local','provincial')),
  intitule    TEXT NOT NULL,              -- مثال: الامتحان الموحد المحلي لنيل شهادة الدروس الابتدائية
  session     TEXT,                       -- الدورة: يونيو 2027
  centre      TEXT,                       -- مركز الامتحان (افتراضياً المؤسسة)
  code_centre TEXT,
  premier_numero INTEGER NOT NULL DEFAULT 1,
  capacite    INTEGER NOT NULL DEFAULT 20 CHECK (capacite > 0),
  UNIQUE (annee_id, type)
);
CREATE TABLE examen_matiere (            -- جدولة الامتحان
  id          INTEGER PRIMARY KEY,
  examen_id   INTEGER NOT NULL REFERENCES examen(id) ON DELETE CASCADE,
  matiere     TEXT NOT NULL,
  jour        TEXT NOT NULL,              -- YYYY-MM-DD
  debut       TEXT NOT NULL,              -- HH:MM
  fin         TEXT NOT NULL,
  ordre       INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE examen_salle (
  id          INTEGER PRIMARY KEY,
  examen_id   INTEGER NOT NULL REFERENCES examen(id) ON DELETE CASCADE,
  numero      INTEGER NOT NULL,
  nom         TEXT NOT NULL,
  UNIQUE (examen_id, numero)
);
CREATE TABLE examen_candidat (
  id          INTEGER PRIMARY KEY,
  examen_id   INTEGER NOT NULL REFERENCES examen(id) ON DELETE CASCADE,
  numero      INTEGER NOT NULL,           -- رقم الامتحان (من ملف المديرية للإقليمي)
  salle_id    INTEGER REFERENCES examen_salle(id) ON DELETE SET NULL,
  code_massar TEXT,
  eleve_id    INTEGER REFERENCES eleve(id),
  nom         TEXT NOT NULL,
  sexe        TEXT,
  date_naissance TEXT,
  classe      TEXT,
  UNIQUE (examen_id, numero)
);
CREATE TABLE examen_affectation (        -- المكلفون: المراقبة في القاعات وباقي المهام
  id          INTEGER PRIMARY KEY,
  examen_id   INTEGER NOT NULL REFERENCES examen(id) ON DELETE CASCADE,
  personnel_id INTEGER REFERENCES personnel(id),
  nom         TEXT NOT NULL,              -- للمكلفين من خارج المؤسسة أيضاً
  ppr         TEXT,
  cadre       TEXT,
  role        TEXT NOT NULL,              -- مراقب(ة)، رئيس(ة) المركز، مراقب جودة الإجراء، عضو الكتابة، مداوم(ة)...
  salle_id    INTEGER REFERENCES examen_salle(id) ON DELETE SET NULL,
  matiere_id  INTEGER REFERENCES examen_matiere(id) ON DELETE CASCADE
);
