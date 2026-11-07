-- تتبع الغياب الشهري (طلب المدير 2026-11-07): لكل شهر أيام الدراسة الفعلية، ولكل قسم عدد التلاميذ ومجموع
-- أيام الغياب (أنصاف الأيام مقبولة: 0.5) وعدد المتغيبين.
CREATE TABLE absence_mois (
  annee_id     INTEGER NOT NULL REFERENCES annee_scolaire(id),
  mois         TEXT NOT NULL,                 -- YYYY-MM
  jours_etude  REAL NOT NULL CHECK (jours_etude > 0 AND jours_etude <= 31),
  PRIMARY KEY (annee_id, mois)
);
CREATE TABLE absence_classe (
  annee_id      INTEGER NOT NULL REFERENCES annee_scolaire(id),
  mois          TEXT NOT NULL,
  classe_id     INTEGER NOT NULL REFERENCES classe(id),
  effectif      INTEGER NOT NULL CHECK (effectif >= 0),
  jours_absence REAL NOT NULL DEFAULT 0 CHECK (jours_absence >= 0),
  absents       INTEGER NOT NULL DEFAULT 0 CHECK (absents >= 0),
  PRIMARY KEY (annee_id, mois, classe_id)
);
