-- طلب المدير (2026-11-01): تواريخ المسار المهني، لازمة لتحديد الفائض (معاييره ستُضاف لاحقاً).
-- date_affectation الموجود = تاريخ التعيين بالمؤسسة.
ALTER TABLE personnel ADD COLUMN date_naissance TEXT;
ALTER TABLE personnel ADD COLUMN date_recrutement TEXT;
ALTER TABLE personnel ADD COLUMN date_affectation_academie TEXT;
ALTER TABLE personnel ADD COLUMN date_affectation_direction TEXT;
