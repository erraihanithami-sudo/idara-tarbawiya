-- مخزن عام لمعطيات صفحات صغيرة (2026-11-13): مكاتب الجمعيات ووثائقها القانونية، جدول الحراسة، النقل المدرسي،
-- استعمالات الزمن. لكل مفتاح وثيقة JSON.
CREATE TABLE fiche_json (
  cle     TEXT PRIMARY KEY,
  donnees TEXT NOT NULL,
  maj_le  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
