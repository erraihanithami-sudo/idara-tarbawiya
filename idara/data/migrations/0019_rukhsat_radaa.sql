-- رخصة الرضاعة (الفصل 46 من النظام الأساسي العام للوظيفة العمومية كما غُيّر بالقانون 30.22، 2022):
-- ساعة واحدة في اليوم، من انتهاء رخصة الولادة أو الكفالة إلى أن يبلغ الطفل 24 شهراً. لا تُعد تغيباً.
INSERT OR IGNORE INTO type_conge(libelle_ar) VALUES ('رخصة الرضاعة');
ALTER TABLE conge ADD COLUMN date_naissance_enfant TEXT;   -- تاريخ ازدياد الطفل (أو تاريخ الكفالة)
ALTER TABLE conge ADD COLUMN horaire_allaitement TEXT;     -- الساعة المخصصة يومياً، مثلاً: 11:00 - 12:00
