-- تدبير تسجيلات التلاميذ (طلب المدير 2026-11-07): ما أدّاه كل تلميذ هذه السنة من واجبات التسجيل.
CREATE TABLE frais_inscription (
  annee_id     INTEGER NOT NULL REFERENCES annee_scolaire(id),
  eleve_id     INTEGER NOT NULL REFERENCES eleve(id),
  assurance    INTEGER NOT NULL DEFAULT 0 CHECK (assurance IN (0, 1)),
  sport        INTEGER NOT NULL DEFAULT 0 CHECK (sport IN (0, 1)),
  cooperative  INTEGER NOT NULL DEFAULT 0 CHECK (cooperative IN (0, 1)),
  maj_le       TEXT,
  PRIMARY KEY (annee_id, eleve_id)
);
