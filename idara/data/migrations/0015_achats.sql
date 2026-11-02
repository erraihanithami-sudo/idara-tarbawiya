-- مسطرة الصرف لجمعية دعم مدرسة النجاح حسب الدليل المسطري (يوليوز 2023):
-- الشراء بسند الطلب (الملاحق 2 إلى 8) والصرف بواسطة الاتفاقية أو الشراكة (الملاحق 26 إلى 28)،
-- ووصل تسلم تجهيز للمداخيل العينية (الملحق 14) والتصريح بتلقي مساعدة أجنبية (الملحق 15).

CREATE TABLE fournisseur (                   -- الممون أو المكلف بالأعمال
  id         INTEGER PRIMARY KEY,
  nom        TEXT NOT NULL UNIQUE,           -- اسم الممون أو الشركة أو المقاولة
  represente_par TEXT,                       -- المتصرف باسمه أو نيابة عن (الاتفاقية)
  cin        TEXT,
  adresse    TEXT,                           -- العنوان الاجتماعي / محل الإقامة
  telephone  TEXT,
  rc         TEXT,                           -- رقم القيد في السجل التجاري
  patente    TEXT,                           -- رقم الضريبة المهنية
  cnss       TEXT,                           -- رقم ص.و.ض.ج
  ice        TEXT,                           -- التعريف الضريبي
  compte_bancaire TEXT
);

CREATE TABLE achat (                         -- ملف صرف واحد: الحاجة ← المنافسة ← التنفيذ ← الأداء
  id           INTEGER PRIMARY KEY,
  exercice_id  INTEGER NOT NULL REFERENCES exercice(id) ON DELETE CASCADE,
  mode         TEXT NOT NULL CHECK (mode IN ('bon_commande','convention')),
  objet        TEXT NOT NULL,
  rubrique_id  INTEGER REFERENCES rubrique(id),
  service_type TEXT,                         -- الاتفاقية: من لائحة الملحق 27
  date_besoin  TEXT,
  -- طلب عروض الأثمان (الملحق 2)
  date_demande TEXT,
  delai_jours  INTEGER,
  nb_demandes  INTEGER,
  -- لجنة دراسة العروض (الملاحق 4 و5)
  date_commission TEXT,
  heure_commission TEXT,
  membres      TEXT,                         -- JSON: [[الاسم، الصفة]...] الحاضرون
  absents      TEXT,
  fournisseur_id INTEGER REFERENCES fournisseur(id),   -- العرض المختار
  justification TEXT,                        -- إن لم يكن العرض الأقل ثمناً
  taux_tva     REAL NOT NULL DEFAULT 20,
  -- التنفيذ
  date_bc      TEXT,                         -- سند الطلب (الملحق 6) أو الطلب المقدم للمكلف بالأعمال
  date_convention TEXT,
  date_livraison TEXT,                       -- سند التسليم (الملحق 7) / إنجاز الخدمة (الملحق 28)
  commission_reception TEXT,                 -- JSON: لجنة التسليم (الملحق 28)
  facture_numero TEXT,
  facture_date TEXT,
  operation_id INTEGER REFERENCES operation_financiere(id),  -- الأداء بالشيك أو التحويل
  cree_le      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE achat_article (                 -- التعيين، الكمية، الوحدة، الثمن الفردي (دون الضريبة)
  achat_id     INTEGER NOT NULL REFERENCES achat(id) ON DELETE CASCADE,
  ordre        INTEGER NOT NULL,
  designation  TEXT NOT NULL,
  quantite     REAL NOT NULL CHECK (quantite > 0),
  unite        TEXT,
  prix_unitaire REAL CHECK (prix_unitaire IS NULL OR prix_unitaire >= 0),
  PRIMARY KEY (achat_id, ordre)
);

CREATE TABLE achat_offre (                   -- العروض المالية المتوصل بها
  achat_id      INTEGER NOT NULL REFERENCES achat(id) ON DELETE CASCADE,
  fournisseur_id INTEGER NOT NULL REFERENCES fournisseur(id),
  montant       REAL NOT NULL CHECK (montant > 0),   -- المبلغ باحتساب الضريبة
  PRIMARY KEY (achat_id, fournisseur_id)
);

CREATE TABLE numero_achat (                  -- أرقام الوثائق داخل السنة المالية، تُمنح عند أول إصدار
  exercice_id INTEGER NOT NULL REFERENCES exercice(id) ON DELETE CASCADE,
  type        TEXT NOT NULL,
  numero      INTEGER NOT NULL,
  achat_id    INTEGER NOT NULL REFERENCES achat(id) ON DELETE CASCADE,
  UNIQUE (exercice_id, type, numero),
  UNIQUE (type, achat_id)
);

CREATE TABLE don_nature (                    -- المداخيل العينية: وصل تسلم تجهيز (الملحق 14)
  id          INTEGER PRIMARY KEY,
  exercice_id INTEGER NOT NULL REFERENCES exercice(id) ON DELETE CASCADE,
  numero      INTEGER NOT NULL,
  date_don    TEXT NOT NULL,
  donateur    TEXT NOT NULL,
  description TEXT NOT NULL,
  UNIQUE (exercice_id, numero)
);
