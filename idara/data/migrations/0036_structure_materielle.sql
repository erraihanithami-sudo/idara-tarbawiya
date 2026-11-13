-- البنية المادية (طلب المدير 2026-11-13): عدد كل مكوّن (الحجرات الدراسية، المباني الإدارية، حجرات التعليم الأولي،
-- الملاعب، المرافق الصحية...) لكل وحدة مدرسية (أو للمؤسسة إن كانت مستقلة)، مع ملاحظة لكل مكوّن.
CREATE TABLE structure_materielle (
  id        INTEGER PRIMARY KEY,
  element   TEXT NOT NULL,            -- مفتاح المكوّن، أو «autre:…» لمكوّن أضافه المدير
  libelle   TEXT NOT NULL,
  unite_id  INTEGER REFERENCES unite_scolaire(id),
  nombre    INTEGER NOT NULL DEFAULT 0 CHECK (nombre >= 0),
  ordre     INTEGER NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX ux_structure ON structure_materielle(element, COALESCE(unite_id, 0));
CREATE TABLE structure_remarque (
  element   TEXT PRIMARY KEY,
  remarques TEXT
);
