-- محاضر الموارد البشرية (طلب المدير 2026-11-09): محضر الالتحاق بالعمل (فردي)، ومحضرا الدخول والخروج (جماعيان)
-- مع لائحة من لم يوقعوا.
CREATE TABLE pv_prise_service (
  id              INTEGER PRIMARY KEY,
  personnel_id    INTEGER NOT NULL REFERENCES personnel(id),
  date_prise      TEXT NOT NULL,
  cas             INTEGER NOT NULL CHECK (cas BETWEEN 1 AND 12),
  reference       TEXT,
  ancien_lieu     TEXT,
  lieu_naissance  TEXT,
  mission         TEXT,
  date_redaction  TEXT NOT NULL,
  cree_le         TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE TABLE pv_collectif (
  id              INTEGER PRIMARY KEY,
  annee_id        INTEGER NOT NULL REFERENCES annee_scolaire(id),
  sens            TEXT NOT NULL CHECK (sens IN ('entree','sortie')),
  concerne        TEXT NOT NULL CHECK (concerne IN ('enseignants','administratifs','tous')),
  unite_id        INTEGER REFERENCES unite_scolaire(id),
  date_pv         TEXT NOT NULL,
  non_signataires TEXT NOT NULL DEFAULT '[]',   -- JSON: [[personnel_id, السبب], ...]
  cree_le         TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
INSERT INTO modele_document(code, titre, langue, fichier_modele, disponible, nb_copies) VALUES
 ('pv_prise_service', 'محضر الالتحاق بالعمل', 'ar', 'pv_prise_service.docx', 1, 1),
 ('pv_entree_sortie', 'محضر الدخول / الخروج', 'ar', 'pv_entree_sortie.docx', 1, 1),
 ('pv_non_signataires', 'لائحة من لم يوقعوا محضر الدخول / الخروج', 'ar', 'pv_non_signataires.docx', 1, 1);
