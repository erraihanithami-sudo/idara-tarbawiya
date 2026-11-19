-- طلب المدير (2026-11-19): تدبير السكنيات حسب المذكرة 40 (10 ماي 2004) حول تدبير المساكن الإدارية والوظيفية.
CREATE TABLE logement (
  id         INTEGER PRIMARY KEY,
  numero     TEXT NOT NULL DEFAULT '',     -- الرقم المخزني
  adresse    TEXT NOT NULL,                -- رقم السكن والشارع أو الزنقة والحي والبلدة
  unite      TEXT NOT NULL DEFAULT '',     -- الوحدة المدرسية
  nature     TEXT NOT NULL DEFAULT '',     -- صلب، مفكك...
  categorie  TEXT NOT NULL DEFAULT 'administratif' CHECK (categorie IN ('administratif','fonction')),
  remarques  TEXT NOT NULL DEFAULT ''
);

CREATE TABLE logement_concours (
  id              INTEGER PRIMARY KEY,
  logement_id     INTEGER NOT NULL REFERENCES logement(id) ON DELETE CASCADE,
  date_annonce    TEXT NOT NULL,
  date_limite     TEXT,
  date_commission TEXT,
  rural           INTEGER NOT NULL DEFAULT 0 CHECK (rural IN (0,1)),
  statut          TEXT NOT NULL DEFAULT 'ouvert' CHECK (statut IN ('ouvert','attribue','annule')),
  beneficiaire_id INTEGER REFERENCES personnel(id),
  remarques       TEXT NOT NULL DEFAULT ''
);

CREATE TABLE logement_candidat (
  id           INTEGER PRIMARY KEY,
  concours_id  INTEGER NOT NULL REFERENCES logement_concours(id) ON DELETE CASCADE,
  personnel_id INTEGER NOT NULL REFERENCES personnel(id),
  donnees      TEXT NOT NULL DEFAULT '{}',   -- عناصر التنقيط (JSON)
  points       REAL NOT NULL DEFAULT 0,
  UNIQUE (concours_id, personnel_id)
);

CREATE TABLE logement_occupation (
  id           INTEGER PRIMARY KEY,
  logement_id  INTEGER NOT NULL REFERENCES logement(id) ON DELETE CASCADE,
  occupant     TEXT NOT NULL,
  personnel_id INTEGER REFERENCES personnel(id),
  ppr          TEXT NOT NULL DEFAULT '',
  cadre        TEXT NOT NULL DEFAULT '',
  fonction     TEXT NOT NULL DEFAULT '',
  date_naissance TEXT NOT NULL DEFAULT '',
  acte_numero  TEXT NOT NULL DEFAULT '',
  acte_date    TEXT NOT NULL DEFAULT '',
  date_sortie  TEXT NOT NULL DEFAULT '',
  motif_sortie TEXT NOT NULL DEFAULT '',
  sortie_ref   TEXT NOT NULL DEFAULT ''
);
