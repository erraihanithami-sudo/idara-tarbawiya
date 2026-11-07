-- طلبات المدير 2026-11-07:
-- التذييل بصورة يختارها من الحاسوب (بدل النص أو معه)، ووسط المؤسسة (حضري/قروي) لحساب واجب التأمين.
ALTER TABLE etablissement ADD COLUMN pied_image_path TEXT;
ALTER TABLE etablissement ADD COLUMN milieu TEXT;
