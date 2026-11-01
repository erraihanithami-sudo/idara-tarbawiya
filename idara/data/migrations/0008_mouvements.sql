-- حركية التلاميذ (اقتراح المدير 2026-11-01): الوافدون وطلب ملفاتهم، والمغادرون وإرسال ملفاتهم.
CREATE TABLE mouvement (
  id               INTEGER PRIMARY KEY,
  eleve_id         INTEGER NOT NULL REFERENCES eleve(id),
  annee_id         INTEGER NOT NULL REFERENCES annee_scolaire(id),
  sens             TEXT NOT NULL CHECK (sens IN ('arrive','parti')),
  date_mouvement   TEXT NOT NULL,
  etablissement    TEXT NOT NULL,            -- المؤسسة الأصلية (وافد) أو المستقبلة (مغادر)
  direction        TEXT,
  academie         TEXT,
  hors_province    INTEGER NOT NULL DEFAULT 0 CHECK (hors_province IN (0,1)),
  niveau           TEXT,                     -- كما يُكتب في المراسلة
  ref_numero       TEXT,                     -- شهادة المغادرة (وافد) أو مراسلتهم (مغادر)
  ref_date         TEXT,
  demande1_courrier_id INTEGER REFERENCES courrier(id),
  demande1_le      TEXT,
  demande2_courrier_id INTEGER REFERENCES courrier(id),
  demande2_le      TEXT,
  dossier_recu_le  TEXT,
  envoi_courrier_id INTEGER REFERENCES courrier(id),
  dossier_envoye_le TEXT,
  remarques        TEXT,
  UNIQUE (eleve_id, annee_id, sens)
);

INSERT INTO modele_document(code, titre, langue, fichier_modele, disponible, nb_copies) VALUES
 ('demande_dossier', 'طلب وثائق مدرسية (داخل الإقليم)', 'ar', 'demande_dossier.docx', 1, 1),
 ('demande_dossier_hors', 'طلب وثائق مدرسية (خارج الإقليم)', 'ar', 'demande_dossier_hors.docx', 1, 1),
 ('envoi_dossier', 'إرسال وثائق مدرسية (داخل الإقليم)', 'ar', 'envoi_dossier.docx', 1, 1),
 ('envoi_dossier_hors', 'إرسال وثائق مدرسية (خارج الإقليم)', 'ar', 'envoi_dossier_hors.docx', 1, 1);
