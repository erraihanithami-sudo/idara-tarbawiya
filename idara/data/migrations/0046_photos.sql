-- صور التقارير والأنشطة والمرافق (طلب المدير 2026-11-22): زر «إضافة الصور» في تقارير الأنشطة والأيام التواصلية
-- والأبواب المفتوحة، وتُستعمل أيضاً في معارض شاشة العرض. الملفات تُنسخ (مصغّرة) إلى pieces/photos داخل مجلد البيانات.
CREATE TABLE photo (
  id        INTEGER PRIMARY KEY,
  objet     TEXT NOT NULL,           -- activite، rencontre، structure، etoile...
  ref       TEXT NOT NULL,           -- معرف العنصر (رقم النشاط أو مفتاح المكوّن)
  chemin    TEXT NOT NULL,           -- نسبي إلى مجلد البيانات
  legende   TEXT NOT NULL DEFAULT '',
  ajoute_le TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX idx_photo_objet ON photo(objet, ref);
