-- سجل الجرد على نموذج السجل الورقي (طلب المدير 2026-11-13):
-- الرقم الترتيبي، تاريخ التسجيل، وصف التجهيزات، مصدرها (رقم الفاتورة وتاريخها، اسم التاجر)، عدد الأشياء،
-- ثمن الشراء (الوحدة، والمجموع يُحسب)، تخصيص التجهيزات، حالة صيانتها، محو التجهيزات من السجل (التاريخ، السبب،
-- رقم القرار)، ملاحظات. ويضاف «نوع التجهيز» لفرز السجل حسبه.
CREATE TABLE inventaire (
  id                 INTEGER PRIMARY KEY,
  numero             INTEGER NOT NULL UNIQUE CHECK (numero > 0),
  date_inscription   TEXT NOT NULL,
  designation        TEXT NOT NULL,
  type               TEXT NOT NULL DEFAULT 'أخرى',
  facture_numero     TEXT,
  facture_date       TEXT,
  fournisseur        TEXT,
  quantite           INTEGER NOT NULL DEFAULT 1 CHECK (quantite > 0),
  prix_unitaire      REAL CHECK (prix_unitaire IS NULL OR prix_unitaire >= 0),
  affectation        TEXT,
  entretien          TEXT,
  radie_le           TEXT,
  radiation_motif    TEXT,
  radiation_decision TEXT,
  remarques          TEXT,
  unite_id           INTEGER REFERENCES unite_scolaire(id),
  cree_le            TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX ix_inventaire_type ON inventaire(type);
