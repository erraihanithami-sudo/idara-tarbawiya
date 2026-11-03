"""الهوية البصرية المعتمدة: الألوان والخط وورقة الأنماط."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase

# لوحة الألوان (اختيار المدير 2026-11-03، من إنفوغرافيا «خارج الفصل... وأولويات التطوير»).
# الأسماء القديمة محفوظة لأن الواجهة كلها تستعملها. التباين محسوب (WCAG): النص العادي 4.5:1 على الأقل.
MARINE = "#1F2A44"       # الكحلي: النصوص والعناوين
SARCELLE = "#0E9688"     # الأخضر المزرق: الأيقونات والتعبئات (3.7:1، لا يُكتب به نص صغير)
MENTHE = "#5EE6D3"
VIOLET = "#7C3AED"
BLEU = "#2563EB"
ROSE = "#DB2777"
ORANGE = "#D97706"       # للأيقونات فقط (3.2:1 على الأبيض)

VERT = "#0B7A6F"         # الأزرار الرئيسية والعنصر النشط (الأبيض عليه 5.2:1)
VERT_FONCE = MARINE      # النص على الخلفيات الفاتحة، وتمرير الفأرة على الأزرار الرئيسية
VERT_CLAIR = "#DDF1EC"   # خلفية العنصر النشط والتحديد (الكحلي عليها 12:1)
ROUGE = ROSE             # التنبيهات المهمة فقط
ROUGE_TEXTE = "#9D174D"  # نص التنبيه (6.7:1 على خلفيته)
ROUGE_CLAIR = "#FCE8F1"
PLATRE = "#F6F5F1"       # خلفية الشاشات
BLANC = "#FFFFFF"
ENCRE = MARINE           # النصوص (13:1 على الخلفية)
GRIS = "#5A6172"         # النصوص الثانوية (5.7:1)
LIGNE = "#E4E2DD"
BORDURE_CHAMP = "#C9C6BD"

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
QPushButton#principal:disabled {{ background: #A9CFC9; }}
QPushButton#nav {{
    text-align: right; border: 0; border-radius: 10px; padding: 0 12px; min-height: 46px; }}
QTabWidget#sections::pane {{ border: 0; }}
QTabWidget#sections > QTabBar {{ background: {PLATRE}; }}
QTabBar::tab {{ background: transparent; color: {GRIS}; padding: 10px 22px; margin: 0 2px;
    border: 0; border-bottom: 3px solid transparent; font-size: 11pt; }}
QTabBar::tab:selected {{ color: {VERT_FONCE}; border-bottom: 3px solid {VERT}; font-weight: 600; }}
QTabBar::tab:hover:!selected {{ color: {ENCRE}; }}
QPushButton#nav:checked {{ background: {VERT_CLAIR}; color: {MARINE}; font-weight: 600;
    border-right: 4px solid {VERT}; }}
QPushButton#nav:hover:!checked {{ background: {PLATRE}; }}
QRadioButton {{ min-height: 36px; }}
QRadioButton::indicator, QCheckBox::indicator {{ width: 18px; height: 18px; }}
"""
