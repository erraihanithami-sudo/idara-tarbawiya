"""الهوية البصرية المعتمدة: الألوان والخط وورقة الأنماط."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase

# لوحة الألوان (اختيار المدير 2026-11-03، من إنفوغرافيا «خارج الفصل... وأولويات التطوير»).
# الأسماء القديمة محفوظة لأن الواجهة كلها تستعملها. التباين محسوب (WCAG): النص العادي 4.5:1 على الأقل.
# ---------------------------------------------------------------------------
# مظاهر البرنامج (اقتراح المدير 2026-11-06): يختارها المدير من الإعدادات. القيم أسفله هي «الأصلي»؛
# appliquer() تعوّضها بقيم المظهر المختار وتعيد بناء ورقة الأنماط. كل الألوان المكتوب بها نص تحترم
# تباين 4.5:1 على خلفيتها (مختبر في tests/test_theme.py).
# ---------------------------------------------------------------------------
from idara.ui.palettes import NOMS_THEMES, PALETTES  # noqa: E402

THEME_ACTUEL = "classique"
globals().update(PALETTES["classique"])
DORE = "#C9A04A"   # الخط الذهبي في البطاقات

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


def feuille() -> str:
    return f"""
QWidget {{ color: {ENCRE}; font-size: 10.5pt; }}
QMainWindow, #fond {{ background: {PLATRE}; }}
QScrollArea {{ background: {PLATRE}; border: 0; }}
QScrollArea > QWidget#qt_scrollarea_viewport {{ background: {PLATRE}; }}
QToolButton {{ background: {BLANC}; border: 1px solid {BORDURE_CHAMP}; border-radius: 10px;
    padding: 0 12px; min-height: 40px; }}
QToolButton::menu-indicator {{ image: none; }}
QMenu {{ background: {BLANC}; border: 1px solid {BORDURE_CHAMP}; padding: 4px; }}
QMenu::item {{ padding: 8px 18px; border-radius: 6px; }}
QMenu::item:selected {{ background: {VERT_CLAIR}; color: {VERT_FONCE}; }}
#ok {{ color: {VERT_FONCE}; }}
#alerte {{ color: {ROUGE_TEXTE}; }}
#barreLaterale {{ border-left: 2px solid {NAV_BORD}; }}
#carte {{ background: {BLANC}; border: 1px solid {BORDURE_CARTE}; border-radius: 12px; }}
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
QPushButton#danger {{ color: {ROUGE_TEXTE}; border: 1.5px solid {ROSE}; background: {ROUGE_CLAIR}; font-weight: 600; }}
QPushButton#danger:hover {{ background: {ROSE}; color: {BLANC}; }}
QPushButton#danger:disabled {{ color: #C9A3B5; border-color: #E8C6D5; background: {BLANC}; }}
QPushButton#nav {{ border: 0; border-radius: 10px; min-height: 46px; }}
QPushButton#nav QLabel {{ background: transparent; }}
QTabWidget#sections::pane {{ border: 0; }}
QTabWidget#sections > QTabBar {{ background: {PLATRE}; }}
QTabBar::tab {{ background: transparent; color: {GRIS}; padding: 10px 22px; margin: 0 2px;
    border: 0; border-bottom: 3px solid transparent; font-size: 11pt; }}
QTabBar::tab:selected {{ color: {VERT_FONCE}; border-bottom: 3px solid {VERT}; font-weight: 600; }}
QTabBar::tab:hover:!selected {{ color: {ENCRE}; }}
QPushButton#nav {{ background: transparent; }}
QPushButton#nav:checked {{ background: {NAV_ACTIF}; font-weight: 600; border-right: 4px solid {NAV_ACCENT}; }}
QPushButton#nav:hover:!checked {{ background: {NAV_SURVOL}; }}
QPushButton#sousnav {{ border: 0; border-radius: 8px; min-height: 38px; background: transparent; }}
QPushButton#sousnav QLabel {{ background: transparent; }}
QPushButton#sousnav:checked {{ background: {NAV_ACTIF}; border-right: 3px solid {NAV_ACCENT}; }}
QPushButton#sousnav:hover:!checked {{ background: {NAV_SURVOL}; }}
QScrollArea#defilNav, QWidget#navigation {{ background: transparent; border: 0; }}
QScrollArea#defilNav > QWidget#qt_scrollarea_viewport {{ background: transparent; }}
QRadioButton {{ min-height: 36px; }}
QRadioButton::indicator, QCheckBox::indicator {{ width: 18px; height: 18px; }}
QTableWidget, QTableView, QListWidget, QPlainTextEdit, QTextEdit {{
    background: {BLANC}; border: 1px solid {BORDURE_CHAMP}; border-radius: 6px; gridline-color: {BORDURE_CARTE}; }}
QHeaderView::section {{ background: {PLATRE}; color: {MARINE}; font-weight: 600; padding: 6px 8px;
    border: 0; border-bottom: 2px solid {BORDURE_CHAMP}; border-left: 1px solid {BORDURE_CARTE}; }}
QTableWidget::item:selected, QListWidget::item:selected {{ background: {VERT_CLAIR}; color: {MARINE}; }}
QPlainTextEdit:focus, QTextEdit:focus {{ border: 2px solid {VERT}; }}
QTabWidget#sections > QTabBar {{ border-bottom: 1px solid {BORDURE_CARTE}; }}
QScrollArea#defilNav QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px; }}
QScrollArea#defilNav QScrollBar::handle:vertical {{ background: {NAV_TEXTE2}; border-radius: 4px; min-height: 30px; }}
QScrollArea#defilNav QScrollBar::add-line:vertical, QScrollArea#defilNav QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollArea#defilNav QScrollBar::add-page:vertical, QScrollArea#defilNav QScrollBar::sub-page:vertical {{
    background: transparent; }}
#navTitre {{ color: {NAV_TEXTE}; font-weight: 700; font-size: 12.5pt; background: transparent; }}
#navSous {{ color: {NAV_TEXTE2}; font-size: 9pt; background: transparent; }}
#badge {{ background: {BADGE_FOND}; color: {BADGE_TEXTE}; border-radius: 9px; padding: 1px 8px;
    font-size: 8.5pt; font-weight: 600; }}
QLineEdit#rechercheNav {{ background: {RECHERCHE_FOND}; color: {RECHERCHE_TEXTE}; border: 1px solid {NAV_TEXTE2};
    border-radius: 12px; min-height: 40px; }}
QLineEdit#rechercheNav:focus {{ border: 2px solid {NAV_ACCENT}; }}
#tuile {{ background: {BLANC}; border: 1px solid {BORDURE_CARTE}; border-radius: 12px; }}
#tuileChiffre {{ font-size: 19pt; font-weight: 700; color: {ENCRE}; background: transparent; }}
#tuileLib {{ color: {GRIS}; font-size: 9.5pt; font-weight: 600; background: transparent; }}
#etape {{ background: qlineargradient(x1:1, y1:0, x2:0, y2:1, stop:0 {HERO_FOND}, stop:1 {HERO_FOND2});
    border-radius: 16px; }}
#etapeTitre {{ color: {HERO_TEXTE}; font-size: 15pt; font-weight: 700; background: transparent; }}
#etapeTexte {{ color: {HERO_TEXTE2}; background: transparent; }}
#numero {{ background: {NAV_ACCENT}; color: #1A1A1A; border-radius: 13px; font-weight: 700; }}
#pastille {{ background: {VERT_CLAIR}; color: {VERT_FONCE}; border-radius: 10px; padding: 2px 10px;
    font-weight: 600; font-size: 9pt; }}
"""


def appliquer(nom: str) -> str:
    """يفعّل مظهراً ويرجع ورقة الأنماط المناسبة له (المظهر غير المعروف ← الأصلي)."""
    global THEME_ACTUEL, FEUILLE_STYLE
    THEME_ACTUEL = nom if nom in PALETTES else "classique"
    globals().update(PALETTES[THEME_ACTUEL])
    FEUILLE_STYLE = feuille()
    return FEUILLE_STYLE


FEUILLE_STYLE = feuille()
