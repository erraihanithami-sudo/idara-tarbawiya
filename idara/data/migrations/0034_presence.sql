-- reconstruction
-- تتبع الحضور الشهري (طلب المدير 2026-11-13): نسبة الحضور الشهرية لكل قسم تُدخل يدوياً، ويحسب البرنامج نسبة
-- الوحدة والمؤسسة. أيام الدراسة الفعلية لم تعد إجبارية. المعطيات السابقة (أيام الغياب) تُحوَّل إلى نسبة حضور.
CREATE TABLE absence_mois_n (
  annee_id     INTEGER NOT NULL REFERENCES annee_scolaire(id),
  mois         TEXT NOT NULL,
  jours_etude  REAL CHECK (jours_etude IS NULL OR (jours_etude > 0 AND jours_etude <= 31)),
  PRIMARY KEY (annee_id, mois)
);
INSERT INTO absence_mois_n(annee_id, mois, jours_etude) SELECT annee_id, mois, jours_etude FROM absence_mois;
DROP TABLE absence_mois;
ALTER TABLE absence_mois_n RENAME TO absence_mois;

ALTER TABLE absence_classe ADD COLUMN taux_presence REAL
  CHECK (taux_presence IS NULL OR (taux_presence >= 0 AND taux_presence <= 100));
UPDATE absence_classe SET taux_presence = ROUND(100 - jours_absence * 100.0 / (effectif * (
    SELECT m.jours_etude FROM absence_mois m WHERE m.annee_id = absence_classe.annee_id
    AND m.mois = absence_classe.mois)), 2)
  WHERE effectif > 0 AND EXISTS (SELECT 1 FROM absence_mois m WHERE m.annee_id = absence_classe.annee_id
    AND m.mois = absence_classe.mois AND m.jours_etude > 0);
