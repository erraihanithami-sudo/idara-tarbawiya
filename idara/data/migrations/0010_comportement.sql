-- تتبع سلوك التلاميذ (اقتراح المدير 2026-11-01)، ومنه يُولد استدعاء ولي الأمر.
CREATE TABLE observation_comportement (
  id            INTEGER PRIMARY KEY,
  eleve_id      INTEGER NOT NULL REFERENCES eleve(id),
  annee_id      INTEGER NOT NULL REFERENCES annee_scolaire(id),
  date_obs      TEXT NOT NULL,
  nature        TEXT NOT NULL,              -- نص حر مع اقتراح ما سبق إدخاله (لا تصنيف رسمي مفترض)
  description   TEXT,
  signale_par   TEXT,                       -- الأستاذ(ة) أو المصدر
  mesure        TEXT,                       -- الإجراء المتخذ
  convocation_document_id INTEGER REFERENCES document_genere(id),
  date_convocation TEXT,
  cree_le       TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX ix_obs_eleve ON observation_comportement(eleve_id, annee_id);
