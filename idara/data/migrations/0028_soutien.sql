-- الدعم التربوي (طلب المدير 2026-11-07): مراحل الدعم، فئات التلاميذ المتعثرين، مجموعات يؤطرها أساتذة متدخلون،
-- التلاميذ المستفيدون مع نتائجهم قبل الدعم وبعده (على 10)، واستعمال زمن الدعم.
CREATE TABLE soutien_etape (
  id          INTEGER PRIMARY KEY,
  annee_id    INTEGER NOT NULL REFERENCES annee_scolaire(id),
  nom         TEXT NOT NULL,
  date_debut  TEXT,
  date_fin    TEXT,
  UNIQUE (annee_id, nom)
);
CREATE TABLE soutien_categorie (
  id        INTEGER PRIMARY KEY,
  annee_id  INTEGER NOT NULL REFERENCES annee_scolaire(id),
  nom       TEXT NOT NULL,
  UNIQUE (annee_id, nom)
);
CREATE TABLE soutien_groupe (
  id            INTEGER PRIMARY KEY,
  etape_id      INTEGER NOT NULL REFERENCES soutien_etape(id) ON DELETE CASCADE,
  categorie_id  INTEGER NOT NULL REFERENCES soutien_categorie(id),
  personnel_id  INTEGER NOT NULL REFERENCES personnel(id),
  matiere       TEXT,
  nom           TEXT NOT NULL
);
CREATE TABLE soutien_eleve (
  groupe_id       INTEGER NOT NULL REFERENCES soutien_groupe(id) ON DELETE CASCADE,
  inscription_id  INTEGER NOT NULL REFERENCES inscription(id),
  note_avant      REAL CHECK (note_avant IS NULL OR (note_avant >= 0 AND note_avant <= 10)),
  note_apres      REAL CHECK (note_apres IS NULL OR (note_apres >= 0 AND note_apres <= 10)),
  observation     TEXT,
  PRIMARY KEY (groupe_id, inscription_id)
);
CREATE TABLE soutien_seance (
  id          INTEGER PRIMARY KEY,
  groupe_id   INTEGER NOT NULL REFERENCES soutien_groupe(id) ON DELETE CASCADE,
  jour        INTEGER NOT NULL CHECK (jour BETWEEN 0 AND 5),   -- 0 الإثنين … 5 السبت
  heure_debut TEXT NOT NULL,                                    -- HH:MM
  heure_fin   TEXT NOT NULL,
  lieu        TEXT
);
