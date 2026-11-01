-- القوالب المتوفرة في المرحلة 2 (وثائق التلاميذ). وثائق الرخص تُضاف في المرحلة 7.
INSERT INTO modele_document(code, titre, langue, fichier_modele, disponible, nb_copies) VALUES
 ('certificat_scolarite_ancien', 'شهادة مدرسية (ما قبل مسار)', 'ar', 'certificat_scolarite_ancien.docx', 1, 1),
 ('attestation_vacances', 'شهادة العطلة', 'fr', 'attestation_vacances.docx', 1, 1),
 ('convocation_parent', 'استدعاء ولي الأمر', 'ar', 'convocation_parent.docx', 1, 1),
 ('visite_medicale', 'ورقة الزيارة الطبية', 'ar', 'visite_medicale.docx', 1, 1);
