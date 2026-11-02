-- قسم التدبير التربوي (طلب المدير 2026-11-02):
-- 1) أداء المؤسسة حسب النتائج ومقارنة كل أسدوس بالذي قبله: معدلا الدورتين من ملف «مجمل المعدلات» (مسار).
-- 2) التعلمات الأساس (مؤسسات الريادة): مستويات التعلم من تصدير مسار ExportNiveauxApprentissage.
-- 3) الأندية التربوية والأنشطة الموازية.
ALTER TABLE resultat ADD COLUMN moyenne_s1 REAL;
ALTER TABLE resultat ADD COLUMN moyenne_s2 REAL;

CREATE TABLE niveau_apprentissage (            -- مستوى التلميذ في رائز (قبلي/بعدي) لكل مادة
  annee_id    INTEGER NOT NULL REFERENCES annee_scolaire(id),
  code_massar TEXT NOT NULL,
  eleve_id    INTEGER REFERENCES eleve(id),
  nom         TEXT NOT NULL,
  classe      TEXT NOT NULL,
  niveau      TEXT,                            -- 1AP..6AP
  matiere     TEXT NOT NULL CHECK (matiere IN ('ar','fr','ma')),
  epreuve     TEXT NOT NULL,                   -- pre: رائز الموضعة القبلي، post: البعدي
  valeur      TEXT NOT NULL,                   -- كما في مسار (حرف، Mot simple، جمع...)
  importe_le  TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  PRIMARY KEY (annee_id, code_massar, matiere, epreuve)
);
CREATE TABLE niveau_attendu (                  -- المستوى المتوقع في TaRL لكل مستوى دراسي (من رأس التصدير)
  annee_id INTEGER NOT NULL REFERENCES annee_scolaire(id),
  niveau   TEXT NOT NULL,
  matiere  TEXT NOT NULL,
  valeur   TEXT NOT NULL,
  PRIMARY KEY (annee_id, niveau, matiere)
);

CREATE TABLE club (                            -- الأندية التربوية
  id          INTEGER PRIMARY KEY,
  annee_id    INTEGER NOT NULL REFERENCES annee_scolaire(id),
  nom         TEXT NOT NULL,
  animateur_id INTEGER REFERENCES personnel(id),
  objectifs   TEXT,
  horaire     TEXT,                            -- مثلا: الأربعاء 15:00-16:00
  UNIQUE (annee_id, nom)
);
CREATE TABLE club_membre (
  club_id  INTEGER NOT NULL REFERENCES club(id) ON DELETE CASCADE,
  eleve_id INTEGER NOT NULL REFERENCES eleve(id),
  role     TEXT,                               -- رئيس(ة) النادي، كاتب(ة)...
  PRIMARY KEY (club_id, eleve_id)
);
CREATE TABLE activite (                        -- البرنامج السنوي للأنشطة وحصيلتها
  id          INTEGER PRIMARY KEY,
  annee_id    INTEGER NOT NULL REFERENCES annee_scolaire(id),
  type        TEXT NOT NULL,                   -- نشاط موازٍ، يوم وطني أو دولي، مسابقة...
  titre       TEXT NOT NULL,                   -- العمليات والأنشطة المبرمجة
  club_id     INTEGER REFERENCES club(id) ON DELETE SET NULL,
  intervenants TEXT,                           -- المتدخلون فيه
  cibles      TEXT,                            -- المستهدفون منه
  periode     TEXT,                            -- فترة الإنجاز كما تُكتب في البرنامج
  date_debut  TEXT,
  date_fin    TEXT,
  mecanismes  TEXT,                            -- آليات التنفيذ
  statut      TEXT NOT NULL DEFAULT 'prevue' CHECK (statut IN ('prevue','realisee','annulee')),
  nb_garcons  INTEGER CHECK (nb_garcons IS NULL OR nb_garcons >= 0),
  nb_filles   INTEGER CHECK (nb_filles IS NULL OR nb_filles >= 0),
  bilan       TEXT                             -- الحصيلة والملاحظات
);
