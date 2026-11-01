"""الهوية البصرية المعتمدة: الألوان والخط وورقة الأنماط."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase

VERT = "#006233"         # أخضر العلم: الأزرار الرئيسية والعنصر النشط
VERT_FONCE = "#00451F"
VERT_CLAIR = "#E6F0EA"
ROUGE = "#C1272D"        # أحمر العلم: التنبيهات المهمة فقط
ROUGE_TEXTE = "#A61F25"
ROUGE_CLAIR = "#FBF1F1"
PLATRE = "#F6F4EE"       # خلفية الشاشات
BLANC = "#FFFFFF"
ENCRE = "#1D2620"        # النصوص
GRIS = "#5E6660"         # النصوص الثانوية
LIGNE = "#E3DED2"
BORDURE_CHAMP = "#CFC8B8"

DOSSIER_POLICES = Path(__file__).resolve().parent.parent / "resources" / "fonts"
POLICE_PREFEREE = "IBM Plex Sans Arabic"
POLICES_SECOURS = ["Segoe UI", "Tahoma", "Arial"]


def charger_police() -> QFont:
    """يحمّل الخط المرفق إن وُجد، وإلا يستعمل خطوط Windows العربية."""
    familles = []
    if DOSSIER_POLICES.exists():
        for f in sorted(DOSSIER_POLICES.glob("*.ttf")):
            fid = QFontDatabase.addApplicationFont(str(f))
            if fid >= 0:
                familles += QFontDatabase.applicationFontFamilies(fid)
    famille = POLICE_PREFEREE if POLICE_PREFEREE in familles else POLICES_SECOURS[0]
    police = QFont(famille, 10)
    police.setFamilies([famille, *POLICES_SECOURS])
    return police


FEUILLE_STYLE = f"""
QWidget {{ color: {ENCRE}; font-size: 10.5pt; }}
QMainWindow, #fond {{ background: {PLATRE}; }}
QScrollArea {{ background: {PLATRE}; border: 0; }}
QScrollArea > QWidget#qt_scrollarea_viewport {{ background: {PLATRE}; }}
QToolButton {{ background: {BLANC}; border: 1px solid {BORDURE_CHAMP}; border-radius: 10px;
    padding: 0 12px; min-height: 40px; }}
QToolButton::menu-indicator {{ image: none; }}
QMenu {{ background: {BLANC}; border: 1px solid {LIGNE}; padding: 4px; }}
QMenu::item {{ padding: 8px 18px; border-radius: 6px; }}
QMenu::item:selected {{ background: {VERT_CLAIR}; color: {VERT_FONCE}; }}
#ok {{ color: {VERT_FONCE}; }}
#alerte {{ color: {ROUGE_TEXTE}; }}
#barreLaterale {{ background: {BLANC}; border-left: 1px solid {LIGNE}; }}
#carte {{ background: {BLANC}; border: 1px solid {LIGNE}; border-radius: 12px; }}
#titrePage {{ font-size: 20pt; font-weight: 600; }}
#sousTitre {{ color: {GRIS}; }}
#titreCarte {{ font-size: 12pt; font-weight: 600; }}
#chiffre {{ font-size: 24pt; font-weight: 600; color: {VERT}; }}
#etiquette {{ color: {GRIS}; font-size: 9.5pt; }}
#erreur {{ color: {ROUGE_TEXTE}; background: {ROUGE_CLAIR}; border-radius: 8px; padding: 8px 12px; }}
#info {{ color: {VERT_FONCE}; background: {VERT_CLAIR}; border-radius: 8px; padding: 8px 12px; }}
QLineEdit, QComboBox, QDateEdit {{
    background: {BLANC}; border: 1px solid {BORDURE_CHAMP}; border-radius: 8px;
    padding: 0 10px; min-height: 38px; }}
QComboBox::drop-down {{ border: 0; width: 30px; }}
QComboBox QAbstractItemView {{ background: {BLANC}; selection-background-color: {VERT_CLAIR};
    selection-color: {VERT_FONCE}; }}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus {{ border: 2px solid {VERT}; }}
QPushButton {{
    background: {BLANC}; border: 1px solid {BORDURE_CHAMP}; border-radius: 10px;
    padding: 0 18px; min-height: 42px; }}
QPushButton:hover {{ border-color: {VERT}; }}
QPushButton#principal {{ background: {VERT}; color: {BLANC}; border: 0; font-weight: 600; }}
QPushButton#principal:hover {{ background: {VERT_FONCE}; }}
QPushButton#principal:disabled {{ background: #9DB8A8; }}
QPushButton#nav {{
    text-align: right; border: 0; border-radius: 8px; padding: 0 14px; min-height: 44px; }}
QPushButton#nav:checked {{ background: {VERT_CLAIR}; color: {VERT_FONCE}; font-weight: 600; }}
QPushButton#nav:hover:!checked {{ background: {PLATRE}; }}
QRadioButton {{ min-height: 36px; }}
QRadioButton::indicator, QCheckBox::indicator {{ width: 18px; height: 18px; }}
"""
