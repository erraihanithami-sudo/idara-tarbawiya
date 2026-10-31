-- التصميم الأولي لقاعدة البيانات — تطبيق الإدارة التربوية المغربية
-- الإصدار 0.2 — SQLite (v0.1 معتمد + الموارد البشرية في النسخة الأولية)
-- [MVP] = يدخل في النسخة الأولية ، [لاحق] = يُفعَّل مع وحداته


-- ============ 1. المؤسسة والسنة الدراسية [MVP] ============

CREATE TABLE etablissement (               -- صف واحد فقط
  id               INTEGER PRIMARY KEY CHECK (id = 1),
  nom_ar           TEXT NOT NULL,
  nom_fr           TEXT,
  code_etab        TEXT,
  type_etab        TEXT NOT NULL DEFAULT 'groupe' CHECK (type_etab IN ('independant','groupe')),
  commune_ar       TEXT, commune_fr TEXT,
  direction_ar     TEXT, direction_fr TEXT,   -- المديرية الإقليمية
  academie_ar      TEXT, academie_fr TEXT,
  ville_redaction_ar TEXT, ville_redaction_fr TEXT,  -- "حرر ب..."
  date_creation    TEXT,
  telephone        TEXT,
  adresse          TEXT,
  logo_path        TEXT, filigrane_path TEXT, pied_page TEXT
);

CREATE TABLE unite_scolaire (               -- الوحدات المدرسية (حقل فقط، دون واجهة تفصيلية)
  id        INTEGER PRIMARY KEY,
  nom_ar    TEXT NOT NULL UNIQUE,
  nom_fr    TEXT,
  est_centre INTEGER NOT NULL DEFAULT 0 CHECK (est_centre IN (0,1))
);

CREATE TABLE annee_scolaire (
  id          INTEGER PRIMARY KEY,
  libelle     TEXT NOT NULL UNIQUE CHECK (libelle GLOB '[0-9][0-9][0-9][0-9]/[0-9][0-9][0-9][0-9]'), -- 2026/2027
  code_court  TEXT NOT NULL UNIQUE,         -- 26-27 (لترقيم الصادر)
  date_debut  TEXT, date_fin TEXT,
  est_courante INTEGER NOT NULL DEFAULT 0 CHECK (est_courante IN (0,1))
);
CREATE UNIQUE INDEX ux_annee_courante ON annee_scolaire(est_courante) WHERE est_courante = 1;

-- ============ 2. المراجع [MVP] ============

CREATE TABLE niveau (                        -- المستويات بثلاث تسميات
  id              INTEGER PRIMARY KEY,
  code            TEXT NOT NULL UNIQUE,      -- PS1, PS2, 1AP ... 6AP
  ordre           INTEGER NOT NULL UNIQUE,
  cycle           TEXT NOT NULL CHECK (cycle IN ('prescolaire','primaire')),
  libelle_ar      TEXT NOT NULL,             -- كما في مسار العربي
  libelle_massar_fr TEXT,                    -- 6° Année Primaire Général
  libelle_doc_fr  TEXT                       -- 6ème année de l'enseignement primaire
);

CREATE TABLE lieu (                          -- أماكن الازدياد الموحدة
  id      INTEGER PRIMARY KEY,
  nom_ar  TEXT NOT NULL UNIQUE,
  nom_fr  TEXT
);

-- ============ 3. التلاميذ [MVP] ============

CREATE TABLE eleve (
  id                INTEGER PRIMARY KEY,
  code_massar       TEXT UNIQUE CHECK (code_massar IS NULL OR code_massar GLOB '[A-Z][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]'),
  num_registre      INTEGER UNIQUE,          -- رقم السجل العام (للتلاميذ ما قبل مسار أساساً)
  num_cahier_registre TEXT,                  -- رقم دفتر السجل (اختياري)
  nom_ar            TEXT NOT NULL,
  prenom_ar         TEXT NOT NULL,
  nom_fr            TEXT, prenom_fr TEXT,
  sexe              TEXT CHECK (sexe IN ('M','F')),
  date_naissance    TEXT,                    -- YYYY-MM-DD
  date_naissance_approx INTEGER NOT NULL DEFAULT 0 CHECK (date_naissance_approx IN (0,1)),
  lieu_naissance_id INTEGER REFERENCES lieu(id),
  source            TEXT NOT NULL CHECK (source IN ('massar','avant_massar','manuel')),
  champs_verrouilles TEXT,                   -- حقول عدّلها المدير يدوياً ولا تُمحى بالاستيراد (JSON)
  cree_le           TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  modifie_le        TEXT,
  CHECK (code_massar IS NOT NULL OR num_registre IS NOT NULL)  -- لا تلميذ بلا معرف
);

CREATE TABLE eleve_avant_massar (            -- المسار التاريخي للتلاميذ القدامى
  eleve_id          INTEGER PRIMARY KEY REFERENCES eleve(id) ON DELETE RESTRICT,
  date_entree       TEXT,
  date_sortie       TEXT,                    -- تاريخ الانقطاع
  dernier_niveau    TEXT,                    -- كما يُكتب في الشهادة: "القسم الخامس"
  motif_sortie      TEXT
);

CREATE TABLE classe (                        -- القسم في سنة معينة
  id        INTEGER PRIMARY KEY,
  annee_id  INTEGER NOT NULL REFERENCES annee_scolaire(id),
  unite_id  INTEGER REFERENCES unite_scolaire(id),
  code      TEXT NOT NULL,                   -- اسم الورقة في مسار: 4APG-5APG-6APG
  UNIQUE (annee_id, code)
);

CREATE TABLE inscription (                   -- يفصل التلميذ عن تسجيله السنوي
  id               INTEGER PRIMARY KEY,
  eleve_id         INTEGER NOT NULL REFERENCES eleve(id) ON DELETE RESTRICT,
  annee_id         INTEGER NOT NULL REFERENCES annee_scolaire(id),
  classe_id        INTEGER REFERENCES classe(id),
  niveau_id        INTEGER REFERENCES niveau(id),   -- مستقل عن القسم (الأقسام المشتركة)
  niveau_confirme  INTEGER NOT NULL DEFAULT 0 CHECK (niveau_confirme IN (0,1)),
  statut           TEXT NOT NULL DEFAULT 'inscrit'
                   CHECK (statut IN ('inscrit','arrive','parti','interrompu')),
  date_entree      TEXT,
  date_sortie      TEXT,
  etab_origine     TEXT,                     -- للوافدين
  etab_destination TEXT,                     -- للمغادرين
  motif_sortie     TEXT,
  UNIQUE (eleve_id, annee_id),
  CHECK (statut NOT IN ('parti','interrompu') OR date_sortie IS NOT NULL)
);

CREATE TABLE import_lot (                    -- سجل عمليات الاستيراد
  id          INTEGER PRIMARY KEY,
  date_import TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  fichier     TEXT NOT NULL,
  langue      TEXT NOT NULL CHECK (langue IN ('ar','fr')),
  annee_id    INTEGER REFERENCES annee_scolaire(id),
  nb_ajoutes  INTEGER, nb_mis_a_jour INTEGER, nb_absents INTEGER, nb_alertes INTEGER,
  rapport     TEXT
);

-- ============ 4. الوثائق والقوالب [MVP] ============

CREATE TABLE modele_document (
  id            INTEGER PRIMARY KEY,
  code          TEXT NOT NULL UNIQUE,        -- certificat_avant_massar, attestation_vacances ...
  titre         TEXT NOT NULL,
  langue        TEXT NOT NULL CHECK (langue IN ('ar','fr')),
  fichier_modele TEXT,                       -- قالب Word الحقيقي
  disponible    INTEGER NOT NULL DEFAULT 0 CHECK (disponible IN (0,1)),
  nb_copies     INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE document_genere (               -- أرشيف كل وثيقة مولدة + سجل التسليم
  id             INTEGER PRIMARY KEY,
  modele_id      INTEGER NOT NULL REFERENCES modele_document(id),
  date_generation TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  eleve_id       INTEGER REFERENCES eleve(id),
  personnel_id   INTEGER REFERENCES personnel(id),
  conge_id       INTEGER REFERENCES conge(id),
  courrier_id    INTEGER REFERENCES courrier(id),
  destinataire_nom TEXT,                     -- متسلم الشهادة
  destinataire_cin TEXT,
  donnees        TEXT NOT NULL,              -- لقطة JSON من البيانات وقت التوليد
  fichier_archive TEXT
);

-- ============ 5. الموارد البشرية [MVP منذ v0.2] ============

CREATE TABLE personnel (
  id          INTEGER PRIMARY KEY,
  ppr         TEXT UNIQUE,                   -- رقم التأجير
  cin         TEXT UNIQUE,
  nom_ar      TEXT NOT NULL, prenom_ar TEXT NOT NULL,
  nom_fr      TEXT, prenom_fr TEXT,
  sexe        TEXT NOT NULL CHECK (sexe IN ('M','F')),
  categorie   TEXT NOT NULL CHECK (categorie IN ('directeur','enseignant','educatrice','gardien','proprete','autre')),
  cadre       TEXT, grade TEXT, fonction TEXT, cycle TEXT, matiere TEXT,
  niveau_enseigne TEXT, nb_eleves INTEGER CHECK (nb_eleves IS NULL OR nb_eleves >= 0),
  heures_hebdo INTEGER CHECK (heures_hebdo IS NULL OR heures_hebdo >= 0),
  adresse     TEXT, telephone TEXT,
  unite_id    INTEGER REFERENCES unite_scolaire(id),
  date_affectation TEXT,
  statut      TEXT NOT NULL DEFAULT 'actif' CHECK (statut IN ('actif','retraite','mute','autre')),
  date_depart TEXT,
  dossier_disponible INTEGER NOT NULL DEFAULT 0 CHECK (dossier_disponible IN (0,1))
);

CREATE TABLE mandat_directeur (              -- المديرون المتعاقبون (لا محو)
  id               INTEGER PRIMARY KEY,
  personnel_id     INTEGER NOT NULL REFERENCES personnel(id),
  date_affectation TEXT NOT NULL,
  date_fin         TEXT,
  poste_precedent  TEXT
);

CREATE TABLE type_conge (
  id INTEGER PRIMARY KEY, libelle_ar TEXT NOT NULL UNIQUE
);
CREATE TABLE cas_reprise (                   -- الحالات العشر لمحضر الاستئناف
  id INTEGER PRIMARY KEY, libelle_ar TEXT NOT NULL UNIQUE
);

CREATE TABLE conge (                         -- ملف رخصة واحد يولد سلسلة الوثائق
  id               INTEGER PRIMARY KEY,
  personnel_id     INTEGER NOT NULL REFERENCES personnel(id),
  type_conge_id    INTEGER NOT NULL REFERENCES type_conge(id),
  prolongation_de  INTEGER REFERENCES conge(id),
  date_debut       TEXT NOT NULL,
  duree_jours      INTEGER NOT NULL CHECK (duree_jours > 0),
  date_fin         TEXT NOT NULL,
  adresse_conge    TEXT,
  avis_directeur   TEXT,
  mesures_prises   TEXT,
  medecin          TEXT, specialite TEXT,
  certificat_recu_le TEXT, certificat_remis_par TEXT, certificat_remis_par_cin TEXT,
  certificat_duree_jours INTEGER,
  demande_remplacement INTEGER NOT NULL DEFAULT 0 CHECK (demande_remplacement IN (0,1)),
  CHECK (date_fin >= date_debut)
);

CREATE TABLE reprise_travail (               -- محضر استئناف العمل (بعد رخصة أو بعد تغيب)
  id               INTEGER PRIMARY KEY,
  personnel_id     INTEGER NOT NULL REFERENCES personnel(id),
  conge_id         INTEGER UNIQUE REFERENCES conge(id),
  cas_reprise_id   INTEGER NOT NULL REFERENCES cas_reprise(id),
  date_debut_absence TEXT NOT NULL,
  date_fin_absence TEXT NOT NULL,
  date_reprise     TEXT NOT NULL,
  CHECK (date_fin_absence >= date_debut_absence),
  CHECK (date_reprise > date_fin_absence)
);

-- ============ 6. المراسلات [سجل الصادر وورقة الإرسال: MVP منذ v0.2 ؛ الباقي لاحق] ============

CREATE TABLE entite (                        -- الجهات: المديرية ← المصلحة ← المكتب
  id        INTEGER PRIMARY KEY,
  parent_id INTEGER REFERENCES entite(id),
  nom_ar    TEXT NOT NULL,
  UNIQUE (parent_id, nom_ar)
);

CREATE TABLE courrier (
  id            INTEGER PRIMARY KEY,
  sens          TEXT NOT NULL CHECK (sens IN ('entrant','sortant')),
  annee_id      INTEGER NOT NULL REFERENCES annee_scolaire(id),
  numero        INTEGER NOT NULL CHECK (numero > 0),  -- 98 → يُعرض 98/25-26
  date_courrier TEXT NOT NULL,
  entite_id     INTEGER REFERENCES entite(id),
  objet         TEXT NOT NULL,
  reference_externe TEXT,                    -- رقم مراسلة الجهة الأخرى (للوارد)
  date_reception TEXT,
  conge_id      INTEGER REFERENCES conge(id),
  UNIQUE (sens, annee_id, numero)            -- لا رقمان متطابقان في نفس السنة
);

CREATE TABLE piece_bordereau (               -- أسطر ورقة الإرسال
  id           INTEGER PRIMARY KEY,
  courrier_id  INTEGER NOT NULL REFERENCES courrier(id) ON DELETE CASCADE,
  designation  TEXT NOT NULL,
  nb_exemplaires INTEGER NOT NULL DEFAULT 1 CHECK (nb_exemplaires > 0)
);

CREATE TABLE piece_jointe (                  -- ملفات مرفقة لأي سجل
  id        INTEGER PRIMARY KEY,
  cible     TEXT NOT NULL,                   -- eleve, courrier, conge, ...
  cible_id  INTEGER NOT NULL,
  libelle   TEXT, chemin TEXT NOT NULL,
  ajoute_le TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

-- ============ 7. البنيات والجرد [لاحق] ============

CREATE TABLE local (                         -- الحجرات والمستودعات
  id        INTEGER PRIMARY KEY,
  unite_id  INTEGER REFERENCES unite_scolaire(id),
  type      TEXT NOT NULL,                   -- حجرة، مستودع، مقر إداري، قاعة متعددة الوسائط
  nom       TEXT NOT NULL,
  en_usage  INTEGER NOT NULL DEFAULT 1 CHECK (en_usage IN (0,1)),
  bon_etat  INTEGER NOT NULL DEFAULT 1 CHECK (bon_etat IN (0,1)),
  affectation TEXT,                          -- تعليم أولي، معارة لمركز التفتح...
  UNIQUE (unite_id, nom)
);

CREATE TABLE article_inventaire (            -- الجرد بالمجموعات مع حالة مفصلة
  id            INTEGER PRIMARY KEY,
  designation   TEXT NOT NULL,
  categorie     TEXT,
  local_id      INTEGER REFERENCES local(id),
  origine       TEXT, date_reception TEXT,
  num_inv_debut INTEGER, num_inv_fin INTEGER,
  quantite      INTEGER NOT NULL CHECK (quantite >= 0),
  qte_bon       INTEGER NOT NULL DEFAULT 0 CHECK (qte_bon >= 0),
  qte_maintenance INTEGER NOT NULL DEFAULT 0 CHECK (qte_maintenance >= 0),
  qte_hs        INTEGER NOT NULL DEFAULT 0 CHECK (qte_hs >= 0),
  CHECK (qte_bon + qte_maintenance + qte_hs = quantite),
  CHECK (num_inv_fin IS NULL OR num_inv_fin >= num_inv_debut)
);

CREATE TABLE equipement (                    -- القطع المفصلة (الحواسيب...)
  id         INTEGER PRIMARY KEY,
  article_id INTEGER NOT NULL REFERENCES article_inventaire(id),
  num_serie  TEXT UNIQUE,
  num_inventaire INTEGER
);

CREATE TABLE affectation_equipement (        -- إسناد معدة لموظف واسترجاعها
  id            INTEGER PRIMARY KEY,
  equipement_id INTEGER NOT NULL REFERENCES equipement(id),
  personnel_id  INTEGER NOT NULL REFERENCES personnel(id),
  date_remise   TEXT NOT NULL,
  date_retour   TEXT,
  remarque      TEXT
);
CREATE UNIQUE INDEX ux_affectation_active ON affectation_equipement(equipement_id) WHERE date_retour IS NULL;

-- ============ 8. السجلات الرسمية ومحضر التسليم [لاحق] ============

CREATE TABLE registre_officiel (             -- سجل التعميم، الصادر، الوارد، الممتلكات
  id           INTEGER PRIMARY KEY,
  type         TEXT NOT NULL,
  numero_cahier TEXT,
  date_debut   TEXT, numero_debut TEXT,
  remarques    TEXT
);

CREATE TABLE remise_mandat (                 -- محضر تسليم المهام
  id               INTEGER PRIMARY KEY,
  date_remise      TEXT NOT NULL,
  ancien_mandat_id INTEGER REFERENCES mandat_directeur(id),
  nouveau_mandat_id INTEGER REFERENCES mandat_directeur(id),
  sections_config  TEXT,                     -- المحاور المفعلة وترتيبها (JSON)
  elements_manuels TEXT,                     -- المفاتيح، الأختام، اللجنة (JSON)
  document_id      INTEGER REFERENCES document_genere(id)
);

-- الجمعيات، مشروع المؤسسة، الأنشطة، الغياب، التقويم: تُصمم بعد تحليل ملفاتها.

-- ============ 9. سجل العمليات [MVP] ============

CREATE TABLE journal (
  id        INTEGER PRIMARY KEY,
  date_op   TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  action    TEXT NOT NULL,                   -- ajout, modification, import, generation, sortie...
  cible     TEXT NOT NULL,
  cible_id  INTEGER,
  details   TEXT
);

-- ============ الفهارس ============
CREATE INDEX ix_eleve_nom ON eleve(nom_ar, prenom_ar);
CREATE INDEX ix_inscription_annee ON inscription(annee_id, classe_id);
CREATE INDEX ix_conge_personnel ON conge(personnel_id, date_debut);
CREATE INDEX ix_courrier_date ON courrier(date_courrier);
