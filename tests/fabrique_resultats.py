"""ملف «مجمل المعدلات السنوية» وهمي بنفس بنية تصدير مسار (أسماء ونقط وهمية)."""

from pathlib import Path

import openpyxl

MATIERES = ["اللغة العربية", "اللغة الفرنسية", "الاجتماعيات", "الرياضيات", "التربية الإسلامية", "التربية البدنية",
            "النشاط العلمي ", "التربية الفنية "]


def classeur_resultats(chemin: Path, classes: dict[str, list[tuple[str, str, list[float]]]],
                       annee="2026/2027", niveau="الرابع ابتدائي عام", annuels: dict[str, float] | None = None,
                       semestres: dict[str, tuple] | None = None, examens: dict[str, tuple] | None = None) -> Path:
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for classe, eleves in classes.items():
        ws = wb.create_sheet(classe)
        ws.append(["وزارة التربية الوطنية", None, None, None, None, None, "مجمل المعدلات السنوية"])
        ws.append(["أكاديمية التربية والتكوين", "الجهة", ": السنة الدراسية", annee, "إقليم: الإقليم  في ", "03-07-2027"])
        ws.append([" : المديرية الإقليمية", "إقليم: الإقليم", ""])
        ws.append(["   : مؤسسة", "مدرسة تجريبية", ": عدد التلاميذ", len(eleves)])
        ws.append(["   : المستوى", niveau, ": القسم ", classe])
        ws.append([])
        ws.append([None, None, None, "معدل المراقبة المستمرة"])
        ws.append(["ر.ت", "رقم التلميذ", "اسم التلميذ", *MATIERES, "الدورة الاولى", "الدورة الثانية", "م.إم المحلي",
                   "م.إم الإقليمي", "المعدل السنوي"])
        for i, (code, nom, notes) in enumerate(eleves, 1):
            a = (annuels or {}).get(code, "")
            s1, s2 = ((semestres or {}).get(code) or ("", ""))
            loc, prov = ((examens or {}).get(code) or ("", ""))
            f = lambda x: "" if x in ("", None) else f"{x:05.2f}".replace(".", ",")  # noqa: E731
            ws.append([str(i), code, nom, *[f"{n:05.2f}".replace(".", ",") for n in notes], f(s1), f(s2), f(loc), f(prov),
                       "" if a == "" else str(a).replace(".", ",")])
    wb.save(chemin)
    return chemin
