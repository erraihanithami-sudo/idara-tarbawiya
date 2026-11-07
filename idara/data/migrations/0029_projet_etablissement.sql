-- تتبع مشروع المؤسسة المندمج (قرار المدير 2026-11-07): الصياغة تتم في مسار؛ البرنامج يتتبع المؤشرات الثلاثة
-- وتنزيل العمليات، ويولّد التقارير التركيبية وحصيلة نهاية المشروع.
CREATE TABLE projet_etab (
  id           INTEGER PRIMARY KEY,
  intitule     TEXT NOT NULL,
  annee_debut  TEXT NOT NULL,   -- 2026/2027
  annee_fin    TEXT NOT NULL,
  actif        INTEGER NOT NULL DEFAULT 1,
  observations TEXT
);
-- المستهدف لكل مؤشر ولكل سنة؛ annee='ref' للقيمة المرجعية. realise_manuel: قيمة محققة تُدخل يدوياً حين لا
-- تتوفر معطيات السنة في البرنامج (سنة سابقة مثلاً).
CREATE TABLE projet_cible (
  projet_id      INTEGER NOT NULL REFERENCES projet_etab(id) ON DELETE CASCADE,
  indicateur     TEXT NOT NULL CHECK (indicateur IN ('tarl','hadar','activites')),
  annee          TEXT NOT NULL,
  cible          REAL,
  realise_manuel REAL,
  PRIMARY KEY (projet_id, indicateur, annee)
);
CREATE TABLE projet_operation (
  id              INTEGER PRIMARY KEY,
  projet_id       INTEGER NOT NULL REFERENCES projet_etab(id) ON DELETE CASCADE,
  ref_massar      TEXT,
  axe             TEXT,
  critere         TEXT,
  sous_critere    TEXT,
  evaluation      TEXT,
  intitule        TEXT NOT NULL,
  priorite        INTEGER,
  montant         REAL,
  budget_najah    REAL,
  contributeur    TEXT,
  contribution    REAL,
  domaine         TEXT,
  ligne           TEXT,
  date_debut      TEXT,
  date_fin        TEXT,
  statut          TEXT NOT NULL DEFAULT 'programmee'
                  CHECK (statut IN ('programmee','en_cours','realisee','reportee','annulee')),
  taux            REAL NOT NULL DEFAULT 0 CHECK (taux BETWEEN 0 AND 100),
  montant_depense REAL,
  observation     TEXT
);
CREATE INDEX idx_projet_operation ON projet_operation(projet_id);
