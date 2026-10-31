-- بيانات مرجعية أولية (قابلة للتعديل من التطبيق)
-- تنبيه: تسميات المستويات المرصودة فعلياً في ملفات مسار: الثانية أولي، الثالث، السادس (عربي) و Préscolaire Niveau 2، 3°، 6° (فرنسي)؛ الباقي مستنتج من نفس الصيغة ويُتحقق منه عند أول استيراد.
INSERT INTO niveau(code,ordre,cycle,libelle_ar,libelle_massar_fr,libelle_doc_fr) VALUES
 ('PS1',1,'prescolaire','الأولى أولي','Préscolaire Niveau 1',NULL),
 ('PS2',2,'prescolaire','الثانية أولي','Préscolaire Niveau 2',NULL),
 ('1AP',3,'primaire','الأول ابتدائي عام','1° Année Primaire Général','1ère année de l''enseignement primaire'),
 ('2AP',4,'primaire','الثاني ابتدائي عام','2° Année Primaire Général','2ème année de l''enseignement primaire'),
 ('3AP',5,'primaire','الثالث ابتدائي عام','3° Année Primaire Général','3ème année de l''enseignement primaire'),
 ('4AP',6,'primaire','الرابع ابتدائي عام','4° Année Primaire Général','4ème année de l''enseignement primaire'),
 ('5AP',7,'primaire','الخامس ابتدائي عام','5° Année Primaire Général','5ème année de l''enseignement primaire'),
 ('6AP',8,'primaire','السادس ابتدائي عام','6° Année Primaire Général','6ème année de l''enseignement primaire');
-- حالات استئناف العمل كما وردت في نموذج المحضر الحقيقي
INSERT INTO cas_reprise(libelle_ar) VALUES
 ('استئناف العمل بعد الاستيداع'),('استئناف العمل بعد الإلحاق'),('استئناف العمل بعد تدريب دراسي'),
 ('استئناف العمل بعد رخصة الولادة'),('استئناف العمل بعد رخصة استثنائية'),
 ('استئناف العمل بعد رخصة مرض قصيرة الأمد'),('استئناف العمل بعد رخصة مرض متوسطة الأمد'),
 ('استئناف العمل بعد رخصة مرض طويلة الأمد'),('استئناف العمل بعد إنهاء تكليف بمهمة'),
 ('استئناف العمل بعد تغيب أو انقطاع العمل');
-- أنواع الرخص المستخرجة من نفس النموذج (قائمة قابلة للإكمال)
INSERT INTO type_conge(libelle_ar) VALUES
 ('رخصة مرض قصيرة الأمد'),('رخصة مرض متوسطة الأمد'),('رخصة مرض طويلة الأمد'),
 ('رخصة الولادة'),('رخصة استثنائية');
