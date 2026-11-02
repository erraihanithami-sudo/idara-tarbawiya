-- وثائق الجمعية حسب الدليل المسطري للتدبير المالي لجمعيات دعم مدرسة النجاح (يوليوز 2023، الملاحق 9 إلى 13):
-- الطرف المعني بالعملية، وترقيم الوصولات والسندات حسب نوعها داخل السنة المالية (رقم يُحفظ عند أول إصدار).
ALTER TABLE operation_financiere ADD COLUMN tiers TEXT;          -- المؤدي (وصل مداخيل) أو المستفيد (سند تسلم)
ALTER TABLE operation_financiere ADD COLUMN tiers_qualite TEXT;  -- صفته

CREATE TABLE piece_association (
  id           INTEGER PRIMARY KEY,
  exercice_id  INTEGER NOT NULL REFERENCES exercice(id) ON DELETE CASCADE,
  type         TEXT NOT NULL CHECK (type IN ('recu','ordre_paiement','autorisation_retrait','bon_caisse','bon_reception')),
  numero       INTEGER NOT NULL,
  operation_id INTEGER NOT NULL REFERENCES operation_financiere(id) ON DELETE CASCADE,
  cree_le      TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (exercice_id, type, numero),
  UNIQUE (type, operation_id)
);
