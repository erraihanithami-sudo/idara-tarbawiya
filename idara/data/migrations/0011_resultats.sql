-- قسم التقييم: نتائج مسار (مجمل المعدلات السنوية) ومجالس الأقسام.
CREATE TABLE resultat (
  id          INTEGER PRIMARY KEY,
  annee_id    INTEGER NOT NULL REFERENCES annee_scolaire(id),
  code_massar TEXT NOT NULL,
  eleve_id    INTEGER REFERENCES eleve(id),
  nom         TEXT NOT NULL,                 -- كما في ملف مسار
  classe      TEXT NOT NULL,
  niveau      TEXT,                          -- 1AP..6AP
  moyennes    TEXT NOT NULL,                 -- JSON: المادة ← المعدل
  moyenne     REAL,                          -- المعدل السنوي
  source_moyenne TEXT CHECK (source_moyenne IN ('massar','calcul')),
  importe_le  TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  UNIQUE (annee_id, code_massar)
);
CREATE TABLE conseil_niveau (
  annee_id     INTEGER NOT NULL REFERENCES annee_scolaire(id),
  niveau       TEXT NOT NULL,
  date_conseil TEXT,
  phase_isa    TEXT,
  difficultes  TEXT,
  solutions    TEXT,
  PRIMARY KEY (annee_id, niveau)
);
CREATE TABLE isa_classe (                     -- مؤشر ISA2 (يُدخله المدير من نتائج المدرسة الرائدة)
  annee_id INTEGER NOT NULL REFERENCES annee_scolaire(id),
  classe   TEXT NOT NULL,
  ar REAL, fr REAL, ma REAL, gl REAL,
  PRIMARY KEY (annee_id, classe)
);
INSERT INTO modele_document(code, titre, langue, fichier_modele, disponible, nb_copies) VALUES
 ('conseil_niveau', 'محضر مجلس القسم (المستوى)', 'ar', 'conseil_niveau.docx', 1, 1),
 ('synthese_conseils', 'تقرير تركيبي لمجالس الأقسام', 'ar', 'synthese_conseils.docx', 1, 1);
