-- طلب المدير (2026-11-01): وضعية «مفصول» ضمن حركية التلاميذ.
-- SQLite لا يعدل قيد CHECK: يُعاد إنشاء جدول التسجيل بنفس البيانات.
CREATE TABLE inscription_v9 (
  id               INTEGER PRIMARY KEY,
  eleve_id         INTEGER NOT NULL REFERENCES eleve(id) ON DELETE RESTRICT,
  annee_id         INTEGER NOT NULL REFERENCES annee_scolaire(id),
  classe_id        INTEGER REFERENCES classe(id),
  niveau_id        INTEGER REFERENCES niveau(id),
  niveau_confirme  INTEGER NOT NULL DEFAULT 0 CHECK (niveau_confirme IN (0,1)),
  statut           TEXT NOT NULL DEFAULT 'inscrit'
                   CHECK (statut IN ('inscrit','arrive','parti','interrompu','exclu')),
  date_entree      TEXT,
  date_sortie      TEXT,
  etab_origine     TEXT,
  etab_destination TEXT,
  motif_sortie     TEXT,
  UNIQUE (eleve_id, annee_id),
  CHECK (statut NOT IN ('parti','interrompu','exclu') OR date_sortie IS NOT NULL)
);
INSERT INTO inscription_v9 SELECT id, eleve_id, annee_id, classe_id, niveau_id, niveau_confirme, statut,
  date_entree, date_sortie, etab_origine, etab_destination, motif_sortie FROM inscription;
DROP TABLE inscription;
ALTER TABLE inscription_v9 RENAME TO inscription;
CREATE INDEX ix_inscription_annee ON inscription(annee_id, classe_id);
