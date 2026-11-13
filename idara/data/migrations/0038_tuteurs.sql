-- أولياء الأمور (طلب المدير 2026-11-13، ملف «export_Tuteur» من مسار): لكل تلميذ الولي ونوع الوصاية، والأب والأم،
-- ولكل منهم: رقم البطاقة الوطنية، الاسم والنسب بالعربية وبالفرنسية، المهنة، الهاتف، العنوان.
CREATE TABLE tuteur (
  id          INTEGER PRIMARY KEY,
  eleve_id    INTEGER NOT NULL REFERENCES eleve(id),
  role        TEXT NOT NULL CHECK (role IN ('tuteur', 'pere', 'mere')),
  tutelle     TEXT,                       -- نوع الوصاية (للولي): أب، أم، وصي
  cin         TEXT,
  prenom_ar   TEXT, nom_ar TEXT,
  prenom_fr   TEXT, nom_fr TEXT,
  profession  TEXT,
  telephone   TEXT,
  adresse     TEXT,
  maj_le      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  UNIQUE (eleve_id, role)
);
