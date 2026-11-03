-- مجالس المؤسسة (المرسوم 2.02.376 بمثابة النظام الأساسي الخاص بمؤسسات التربية والتعليم العمومي، المواد 17-31):
-- مجلس التدبير، المجلس التربوي، المجالس التعليمية (عربية، فرنسية). مجالس الأقسام في قسم التقييم.
CREATE TABLE conseil_membre (
  id          INTEGER PRIMARY KEY,
  annee_id    INTEGER NOT NULL REFERENCES annee_scolaire(id),
  conseil     TEXT NOT NULL CHECK (conseil IN ('gestion','pedagogique','enseignement')),
  groupe      TEXT,                            -- المجالس التعليمية: المادة (عربية، فرنسية...)
  nom         TEXT NOT NULL,
  qualite     TEXT NOT NULL,                   -- رئيس المجلس، ممثل القسم الأول...
  personnel_id INTEGER REFERENCES personnel(id),
  ordre       INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE conseil_seance (
  id           INTEGER PRIMARY KEY,
  annee_id     INTEGER NOT NULL REFERENCES annee_scolaire(id),
  conseil      TEXT NOT NULL CHECK (conseil IN ('gestion','pedagogique','enseignement')),
  numero       INTEGER NOT NULL,               -- رقم الاجتماع في السنة
  date_seance  TEXT NOT NULL,
  heure        TEXT,
  nature       TEXT NOT NULL DEFAULT 'ordinaire' CHECK (nature IN ('ordinaire','extraordinaire')),
  convocation  TEXT NOT NULL DEFAULT 'premiere' CHECK (convocation IN ('premiere','seconde')),
  ordre_du_jour TEXT NOT NULL,                 -- JSON: النقط
  deliberations TEXT,
  decisions    TEXT,                           -- JSON: القرارات والتوصيات
  inclure_resultats INTEGER NOT NULL DEFAULT 0,
  inclure_isa  INTEGER NOT NULL DEFAULT 0,
  UNIQUE (annee_id, conseil, numero)
);
CREATE TABLE conseil_presence (
  seance_id INTEGER NOT NULL REFERENCES conseil_seance(id) ON DELETE CASCADE,
  membre_id INTEGER NOT NULL REFERENCES conseil_membre(id) ON DELETE CASCADE,
  present   INTEGER NOT NULL DEFAULT 1 CHECK (present IN (0,1)),
  PRIMARY KEY (seance_id, membre_id)
);
