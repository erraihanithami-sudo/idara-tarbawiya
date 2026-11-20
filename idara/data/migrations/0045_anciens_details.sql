-- طلب المدير 2026-11-20: معلومات إضافية للتلاميذ ما قبل مسار (نموذج الإكسل)
ALTER TABLE eleve_avant_massar ADD COLUMN tuteur TEXT;
ALTER TABLE eleve_avant_massar ADD COLUMN nationalite TEXT;
ALTER TABLE eleve_avant_massar ADD COLUMN adresse TEXT;
