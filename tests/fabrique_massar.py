"""يصنع لوائح وهمية بنفس بنية تصدير مسار (رأس بخلايا مدمجة، العناوين في الصف 10)."""

from openpyxl import Workbook

ENTETE_AR = ["ر.ت", "الرمز", "النسب ", "الإسم", "النوع", "تاريخ الإزدياد", "مكان الازدياد"]
ENTETE_FR = ["N.O", "Code ", "Nom ", "Prénom", "Genre", "Date de naissance", "Lieu naissance"]


def classeur(chemin, classes: dict, langue="ar", annee="2026/2027", etab="مدرسة تجريبية",
             decalage=0):
    """classes: {رمز القسم: [(رمز، نسب، اسم، نوع، تاريخ YYYY-MM-DD، مكان), ...]}"""
    wb = Workbook()
    wb.remove(wb.active)
    for code_classe, eleves in classes.items():
        ws = wb.create_sheet(code_classe)
        d = decalage
        if langue == "ar":
            ws.cell(2 + d, 3, "لائحة التلاميذ")
            ws.cell(5 + d, 1, "الأكاديمية:"); ws.cell(5 + d, 3, "الأكاديمية التجريبية")
            ws.cell(5 + d, 6, "الجماعة:"); ws.cell(5 + d, 7, "الجماعة التجريبية")
            ws.cell(6 + d, 1, " : المديرية الإقليمية"); ws.cell(6 + d, 3, "إقليم: تجريبي")
            ws.cell(6 + d, 6, "المؤسسة:"); ws.cell(6 + d, 7, etab)
            ws.cell(7 + d, 1, "   : المستوى"); ws.cell(7 + d, 3, "مستوى تجريبي")
            ws.cell(7 + d, 6, "السنة الدراسية:"); ws.cell(7 + d, 7, annee)
            ws.cell(8 + d, 1, "   : القسم"); ws.cell(8 + d, 3, code_classe)
            entete = ENTETE_AR
        else:
            ws.cell(2 + d, 3, "Liste des élèves")
            ws.cell(5 + d, 1, "Académie:"); ws.cell(5 + d, 3, "Académie test")
            ws.cell(6 + d, 6, "Etablissement:"); ws.cell(6 + d, 7, "ECOLE TEST")
            ws.cell(7 + d, 6, "Année Scolaire:"); ws.cell(7 + d, 7, annee)
            ws.cell(8 + d, 1, "Classe:"); ws.cell(8 + d, 3, code_classe)
            entete = ENTETE_FR
        for c in ("A5:B5", "C5:D5", "A6:B6", "C6:D6", "A7:B7", "C7:D7", "A8:B8", "C8:D8"):
            if not d:
                ws.merge_cells(c)
        for j, t in enumerate(entete, start=1):
            ws.cell(10 + d, j, t)
        for i, (code, nom, prenom, sexe, dn, lieu) in enumerate(eleves, start=1):
            if langue == "ar":
                genre = {"M": "ذكر", "F": "أنثى"}.get(sexe, sexe)
                date = dn
            else:
                genre = {"M": "Garçon", "F": "Fille"}.get(sexe, sexe)
                date = dn.replace("-", "/") if dn else dn
            for j, v in enumerate([i, code, nom, prenom, genre, date, lieu], start=1):
                ws.cell(10 + d + i, j, v)
    wb.save(chemin)
    return chemin
