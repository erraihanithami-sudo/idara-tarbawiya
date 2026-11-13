-- محاور يضيفها المدير إلى محضر تسليم المهام (طلب المدير 2026-11-13): عنوان، وأعمدة جدول و/أو نص حر.
CREATE TABLE passation_perso (
  cle        TEXT PRIMARY KEY,
  titre      TEXT NOT NULL,
  colonnes   TEXT NOT NULL DEFAULT '[]',     -- JSON
  avec_texte INTEGER NOT NULL DEFAULT 0 CHECK (avec_texte IN (0, 1))
);
