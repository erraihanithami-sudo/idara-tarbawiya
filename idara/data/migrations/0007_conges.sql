-- المرحلة 7: ملف الرخصة وسلسلة وثائقه، وسجل الصادر.
ALTER TABLE conge ADD COLUMN motif TEXT;                 -- «لسبب: مرض»
ALTER TABLE conge ADD COLUMN pieces TEXT;                -- مرفقات الطلب
ALTER TABLE conge ADD COLUMN remarques_certificat TEXT;  -- ملاحظات إيصال الشهادة الطبية
ALTER TABLE conge ADD COLUMN date_demande TEXT;          -- تاريخ الطلب وتسجيله في الصادر
ALTER TABLE reprise_travail ADD COLUMN autres_contacts TEXT;
ALTER TABLE reprise_travail ADD COLUMN date_redaction TEXT;

CREATE TABLE parametre (                     -- إعدادات بسيطة (صيغ المراسلات...)
  cle    TEXT PRIMARY KEY,
  valeur TEXT NOT NULL
);

INSERT INTO modele_document(code, titre, langue, fichier_modele, disponible, nb_copies) VALUES
 ('demande_conge', 'طلب رخصة', 'ar', 'demande_conge.docx', 1, 1),
 ('recu_certificat', 'إيصال باستلام شهادة طبية', 'ar', 'recu_certificat.docx', 1, 1),
 ('demande_remplacement', 'طلب تعويض أستاذ(ة) في رخصة', 'ar', 'demande_remplacement.docx', 1, 1),
 ('bordereau_envoi', 'ورقة إرسال', 'ar', 'bordereau_envoi.docx', 1, 1),
 ('pv_reprise', 'محضر استئناف العمل', 'ar', 'pv_reprise.docx', 1, 1);
