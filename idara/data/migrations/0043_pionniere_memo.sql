-- طلب المدير (2026-11-19):
-- 1) المدرسة الرائدة، مكون التواصل: الأيام التواصلية والأبواب المفتوحة وتقاريرها.
-- 2) مفكرة المدير: بطاقات تذكير (post-it) بموضوع وتاريخ وساعة.
CREATE TABLE rencontre_parents (
  id              INTEGER PRIMARY KEY,
  annee_id        INTEGER NOT NULL REFERENCES annee_scolaire(id),
  type            TEXT NOT NULL CHECK (type IN ('rencontre','portes')),
  date_rencontre  TEXT NOT NULL,
  heure           TEXT,
  theme           TEXT NOT NULL DEFAULT '',
  invites         INTEGER,
  presents        INTEGER,
  deroulement     TEXT NOT NULL DEFAULT '',
  recommandations TEXT NOT NULL DEFAULT ''
);
CREATE INDEX idx_rencontre_annee ON rencontre_parents(annee_id, date_rencontre);

CREATE TABLE memo_directeur (
  id        INTEGER PRIMARY KEY,
  sujet     TEXT NOT NULL,
  details   TEXT NOT NULL DEFAULT '',
  date_memo TEXT NOT NULL,
  heure     TEXT,
  couleur   TEXT NOT NULL DEFAULT 'jaune',
  fait      INTEGER NOT NULL DEFAULT 0 CHECK (fait IN (0,1)),
  cree_le   TEXT NOT NULL DEFAULT (datetime('now'))
);
