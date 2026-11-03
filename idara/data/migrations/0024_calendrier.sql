-- محطات السنة الدراسية (اقتراح المدير 2026-11-03): المحطات الوزارية تُحمَّل مع تحديث البرنامج من
-- resources/mouqarrar/<السنة>.json، والمحلية يضيفها المدير. يحفظ station_suivi ما أُنجز أو أُخفي.
CREATE TABLE station_locale (
  id           INTEGER PRIMARY KEY,
  annee_id     INTEGER NOT NULL REFERENCES annee_scolaire(id),
  titre        TEXT NOT NULL,
  type         TEXT NOT NULL DEFAULT 'local',
  debut        TEXT NOT NULL,
  fin          TEXT NOT NULL,
  rappel_jours INTEGER NOT NULL DEFAULT 7 CHECK (rappel_jours BETWEEN 0 AND 120),
  remarque     TEXT,
  CHECK (fin >= debut)
);
CREATE TABLE station_suivi (
  annee_id  INTEGER NOT NULL REFERENCES annee_scolaire(id),
  cle       TEXT NOT NULL,             -- m:<مفتاح المحطة الوزارية> أو l:<رقم المحطة المحلية>
  fait_le   TEXT,
  PRIMARY KEY (annee_id, cle)
);
