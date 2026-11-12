-- محضر تسليم مهام الإدارة التربوية (نموذج المدير 2026-11-12):
-- لكل محور: هل يُدرج في المحضر، ترتيبه، ومعطياته (JSON: الخانات و/أو أسطر الجدول).
-- المعطيات المأخوذة من البرنامج تُقترح عند أول فتح وتُحدَّث بطلب المدير، وما يُدخله يدوياً يبقى.
CREATE TABLE passation_section (
  cle     TEXT PRIMARY KEY,
  actif   INTEGER NOT NULL DEFAULT 1 CHECK (actif IN (0, 1)),
  ordre   INTEGER,
  donnees TEXT,
  maj_le  TEXT
);
