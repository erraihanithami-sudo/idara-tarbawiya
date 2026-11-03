-- reconstruction: جدول الموظفين يُعاد بناؤه لإضافة فئة «المساعدون التربويون» إلى قيد CHECK.
-- معطيات وثيقة «التنظيم التربوي» (نموذج المدير، 2026-11-03): الدرجة وتاريخها، الرتبة وتاريخها، آخر نقطة تفتيش
-- وتاريخها والمفتش الذي منحها، تاريخ المهمة الحالية، أنصاف أيام العطلة الأسبوعية (الإدارة)، التكليف بالمؤسسة
-- أو خارجها، ومادة وأقسام فترة الدعم TaRL.
CREATE TABLE personnel_nouveau (
  id          INTEGER PRIMARY KEY,
  ppr         TEXT UNIQUE,
  cin         TEXT UNIQUE,
  nom_ar      TEXT NOT NULL, prenom_ar TEXT NOT NULL,
  nom_fr      TEXT, prenom_fr TEXT,
  sexe        TEXT NOT NULL CHECK (sexe IN ('M','F')),
  categorie   TEXT NOT NULL CHECK (categorie IN ('directeur','enseignant','educatrice','assistant','gardien','proprete','autre')),
  cadre       TEXT, grade TEXT, fonction TEXT, cycle TEXT, matiere TEXT,
  niveau_enseigne TEXT, nb_eleves INTEGER CHECK (nb_eleves IS NULL OR nb_eleves >= 0),
  heures_hebdo INTEGER CHECK (heures_hebdo IS NULL OR heures_hebdo >= 0),
  adresse     TEXT, telephone TEXT,
  unite_id    INTEGER REFERENCES unite_scolaire(id),
  date_affectation TEXT,
  statut      TEXT NOT NULL DEFAULT 'actif' CHECK (statut IN ('actif','retraite','mute','autre')),
  date_depart TEXT,
  dossier_disponible INTEGER NOT NULL DEFAULT 0 CHECK (dossier_disponible IN (0,1)),
  remarques   TEXT,
  date_naissance TEXT, date_recrutement TEXT, date_affectation_academie TEXT, date_affectation_direction TEXT,
  exemption_fa TEXT CHECK (exemption_fa IS NULL OR exemption_fa IN ('agrege','doctorat')),
  date_exemption_fa TEXT,
  -- التنظيم التربوي
  date_grade      TEXT,
  echelon         TEXT,
  date_echelon    TEXT,
  note_inspection REAL CHECK (note_inspection IS NULL OR (note_inspection >= 0 AND note_inspection <= 20)),
  date_inspection TEXT,
  inspecteur      TEXT,
  sans_inspection INTEGER NOT NULL DEFAULT 0 CHECK (sans_inspection IN (0,1)),
  date_fonction   TEXT,                       -- تاريخ المهمة الحالية
  repos_matin     TEXT, repos_soir TEXT,      -- أنصاف أيام العطلة الأسبوعية
  situation       TEXT NOT NULL DEFAULT 'normal' CHECK (situation IN ('normal','charge_in','charge_out')),
  etab_charge     TEXT,                       -- المؤسسة الأصلية (مكلف بالمؤسسة) أو مؤسسة التكليف (خارجها)
  date_charge     TEXT,
  matiere_tarl    TEXT,                       -- المادة المدرسة خلال فترة الدعم TaRL
  classes_tarl    TEXT                        -- الأقسام أو المجموعات خلال فترة الدعم TaRL
);
INSERT INTO personnel_nouveau(id, ppr, cin, nom_ar, prenom_ar, nom_fr, prenom_fr, sexe, categorie, cadre, grade,
  fonction, cycle, matiere, niveau_enseigne, nb_eleves, heures_hebdo, adresse, telephone, unite_id, date_affectation,
  statut, date_depart, dossier_disponible, remarques, date_naissance, date_recrutement, date_affectation_academie,
  date_affectation_direction, exemption_fa, date_exemption_fa)
SELECT id, ppr, cin, nom_ar, prenom_ar, nom_fr, prenom_fr, sexe, categorie, cadre, grade,
  fonction, cycle, matiere, niveau_enseigne, nb_eleves, heures_hebdo, adresse, telephone, unite_id, date_affectation,
  statut, date_depart, dossier_disponible, remarques, date_naissance, date_recrutement, date_affectation_academie,
  date_affectation_direction, exemption_fa, date_exemption_fa FROM personnel;
DROP TABLE personnel;
ALTER TABLE personnel_nouveau RENAME TO personnel;
