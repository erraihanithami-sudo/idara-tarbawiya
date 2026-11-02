-- أبواب وبنود ميزانية جمعية دعم مدرسة النجاح مطابقة للملحق 1 من الدليل المسطري (يوليوز 2023)،
-- المعتمد رسمياً (قرار المدير 2026-11-02). البنود المحذوفة في الدليل لا تُمسح (قد تحمل عمليات سابقة):
-- تصير غير نشطة، فلا تظهر في العمليات الجديدة ولا في الميزانية إلا إن كان لها مبلغ.
ALTER TABLE rubrique ADD COLUMN actif INTEGER NOT NULL DEFAULT 1;

-- المجالات بأسماء الملحق 1
UPDATE rubrique SET chapitre='الأندية التربوية' WHERE type_association='najah' AND chapitre='أ- الأندية التربوية';
UPDATE rubrique SET chapitre='التظاهرات المدرسية' WHERE type_association='najah' AND chapitre='ب- نفقات التظاهرات المدرسية';
UPDATE rubrique SET chapitre='نفقات تشجيع التميز والإبداع والابتكار' WHERE type_association='najah' AND chapitre='ت- نفقات تشجيع التميز والإبداع والابتكار';
UPDATE rubrique SET chapitre='التوجيه المدرسي والمهني' WHERE type_association='najah' AND chapitre='ث- نفقات التوجيه';
UPDATE rubrique SET chapitre='الدعم التربوي' WHERE type_association='najah' AND chapitre='ج- نفقات الدعم التربوي';
UPDATE rubrique SET chapitre='دعم الصحة المدرسية' WHERE type_association='najah' AND chapitre='ح- نفقات دعم الصحة المدرسية';
UPDATE rubrique SET chapitre='الدعم النفسي' WHERE type_association='najah' AND chapitre='خ- نفقات الدعم النفسي';
UPDATE rubrique SET chapitre='التدبير والشراكة' WHERE type_association='najah' AND chapitre='د- نفقات التدبير والشراكة';
UPDATE rubrique SET chapitre='التجهيزات' WHERE type_association='najah' AND chapitre='ر- التجهيزات';
UPDATE rubrique SET chapitre='صيانة وإصلاح تجهيزات وبنيات المؤسسة وتأهيلها' WHERE type_association='najah' AND chapitre='ه- صيانة وإصلاح تجهيزات وبنيات المؤسسة وتأهيلها';
UPDATE rubrique SET chapitre='نفقات استثنائية' WHERE type_association='najah' AND chapitre='و- نفقات استثنائية';

-- البنود بصيغة الملحق 1
UPDATE rubrique SET ligne='مصاريف التنقل للتلاميذ' WHERE type_association='najah' AND chapitre IN ('الأندية التربوية','التظاهرات المدرسية') AND ligne IN ('مصاريف التنقل','مصاريف التنقل والتغذية');
UPDATE rubrique SET ligne='الطبع والنسخ والتصوير' WHERE type_association='najah' AND chapitre='نفقات تشجيع التميز والإبداع والابتكار' AND ligne LIKE 'مطبوعات%';
UPDATE rubrique SET ligne='مصاريف الحفلات والاستقبال' WHERE type_association='najah' AND chapitre='نفقات تشجيع التميز والإبداع والابتكار' AND ligne LIKE 'مصاريف الحفلات%';
UPDATE rubrique SET ligne='مصاريف شراء الجوائز' WHERE type_association='najah' AND ligne='مصاريف شراء الجوائز لتشجيع التميز';
UPDATE rubrique SET ligne='الطبع والنسخ' WHERE type_association='najah' AND chapitre='التوجيه المدرسي والمهني' AND ligne LIKE 'مطبوعات%';
UPDATE rubrique SET ligne='مصاريف التنقل للتلميذات والتلاميذ' WHERE type_association='najah' AND chapitre IN ('التوجيه المدرسي والمهني','التدبير والشراكة') AND ligne='مصاريف التنقل';
UPDATE rubrique SET ligne='شراء اللوازم الطبية للتلميذات والتلاميذ' WHERE type_association='najah' AND ligne LIKE 'شراء بعض المعدات الطبية%';
UPDATE rubrique SET ligne='مطبوعات والطبع والنسخ والتصوير' WHERE type_association='najah' AND chapitre='التدبير والشراكة' AND ligne LIKE 'مطبوعات%';

UPDATE rubrique SET ligne='صيانة وتأهيل البنيات المادية للمؤسسة والتي لا تحتاج إلى مهندس معماري أو مكتب للدراسات' WHERE type_association='najah' AND ligne LIKE 'صيانة وتأهيل البنيات المادية%';

-- بنود نموذج Access غير الواردة في الملحق 1
UPDATE rubrique SET actif=0 WHERE type_association='najah' AND (
     (chapitre='الدعم النفسي' AND ligne='مستحقات الأطباء')
  OR ligne LIKE 'معدات ولوازم الأسرة%' OR ligne='معدات تكييف الهواء'
  OR ligne LIKE 'تحمل استثنائي%');

-- مداخيل الأنشطة: «مداخيل أخرى» (الملحق 1)
INSERT INTO rubrique(type_association, sens, chapitre, ligne, observation, ordre)
SELECT 'najah', 'recette', 'مداخيل الأنشطة', 'مداخيل أخرى', NULL, 4
WHERE EXISTS (SELECT 1 FROM association WHERE type='najah');

-- ترتيب المجالات كما في الملحق 1
UPDATE rubrique SET ordre = ordre + 100 * (CASE chapitre
  WHEN 'مداخيل الأنشطة' THEN 1 WHEN 'المنح' THEN 2 WHEN 'الهبات' THEN 3 WHEN 'مداخيل استثنائية' THEN 4
  WHEN 'الأندية التربوية' THEN 11 WHEN 'التظاهرات المدرسية' THEN 12 WHEN 'الدعم التربوي' THEN 13
  WHEN 'دعم الصحة المدرسية' THEN 14 WHEN 'الدعم النفسي' THEN 15 WHEN 'التوجيه المدرسي والمهني' THEN 16
  WHEN 'التدبير والشراكة' THEN 17 WHEN 'نفقات تشجيع التميز والإبداع والابتكار' THEN 18 WHEN 'التجهيزات' THEN 19
  WHEN 'صيانة وإصلاح تجهيزات وبنيات المؤسسة وتأهيلها' THEN 20 WHEN 'نفقات استثنائية' THEN 21 ELSE 30 END)
WHERE type_association='najah';
