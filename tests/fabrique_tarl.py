"""ملف «مستويات التعلم» وهمي بنفس بنية تصدير مسار ExportNiveauxApprentissage (أسماء ورموز وهمية)."""

from pathlib import Path

import openpyxl


def classeur_niveaux(chemin: Path, classes: dict[str, list[tuple]], annee="2026/2027", niveau="الثاني ابتدائي عام",
                     attendus=("كلمة", "Mot simple", "جمع")) -> Path:
    """classes: القسم ← [(الرمز، الاسم، عربية قبلي، عربية بعدي، فرنسية قبلي، فرنسية بعدي، رياضيات قبلي، رياضيات بعدي)]"""
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for classe, eleves in classes.items():
        ws = wb.create_sheet(f"TARL-{classe}")
        ws.append(["A", "D", "E", None, "F", "H"])
        for _ in range(5):
            ws.append([])
        ws.append([None, None, "مستويات التعلم"])
        ws.append([])
        ws.append([])
        ws.append([None, "الأكاديمية", "الجهة", None, None, "المديرية الإقليمية ", "إقليم: الإقليم"])
        ws.append([])
        ws.append([None, "المؤسسة", "مدرسة تجريبية", None, None, "السنة الدراسية", annee])
        ws.append([])
        ws.append([None, "المستوى", niveau])
        ws.append([])
        ws.append([None, "TaRL المستوى المتوقع في", None, None, "اللغة العربية", "اللغة الفرنسية", "الرياضيات"])
        ws.append([None, None, None, None, *attendus])
        ws.append([])
        ws.append([None, None, None, "اللغة العربية", "اللغة العربية", "اللغة الفرنسية", "اللغة الفرنسية",
                   "الرياضيات", "الرياضيات"])
        ws.append([None, "رقم التلميذ", "الإسم الكامل", "رائز الموضعة القبلي", " رائز الموضعة البعدي",
                   "رائز الموضعة القبلي", " رائز الموضعة البعدي", "رائز الموضعة القبلي", " رائز الموضعة البعدي"])
        for e in eleves:
            ws.append([None, *e])
    wb.save(chemin)
    return chemin


def classeur_groupes(chemin: Path, classes: dict[str, tuple[str, str, str]], annee="2026/2027",
                     niveau="الرابع ابتدائي عام") -> Path:
    """تصدير «مجموعات الدعم» وهمي: القسم ← (مسار العربية، مسار الفرنسية، مسار الرياضيات)."""
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for classe, (ar, fr, ma) in classes.items():
        ws = wb.create_sheet(f"TARL-{classe}")
        ws.append(["A", "D", "E", None, "F", "H"])
        for _ in range(5):
            ws.append([])
        ws.append([None, None, "  مجموعات الدعم بتلاميذ المؤسسة"])
        ws.append([])
        ws.append([])
        ws.append([None, "الأكاديمية", "الجهة", None, None, "المديرية الإقليمية ", "إقليم: الإقليم"])
        ws.append([])
        ws.append([None, "المؤسسة", "مدرسة تجريبية", None, None, "السنة الدراسية", annee])
        ws.append([])
        ws.append([None, "المستوى", niveau])
        ws.append([None, None, None, None, None, None, "اللغة العربية", "اللغة الفرنسية", "الرياضيات"])
        ws.append([None, None, None, None, None, None, ar, fr, ma])
        ws.append([])
        ws.append([None, "رقم التلميذ", "الإسم الكامل", "النوع", "تاريخ الازدياد", "نتيجة", "اللغة العربية",
                   "اللغة الفرنسية", "الرياضيات"])
        ws.append([None, "X000000001", "أ", "ذكر", "01-01-2016", 17, "أقصوصة ", "Phrase (D.P)", "ضرب"])
    wb.save(chemin)
    return chemin
