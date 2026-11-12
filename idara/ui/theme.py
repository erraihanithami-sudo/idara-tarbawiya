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
from idara.ui.palettes import NOMS_THEMES, PALETTES, THEME_DEFAUT  # noqa: E402

THEME_ACTUEL = THEME_DEFAUT
globals().update(PALETTES[THEME_DEFAUT])
DORE = "#C9A04A"   # الخط الذهبي في البطاقات

DOSSIER_POLICES = Path(__file__).resolve().parent.parent / "resources" / "fonts"
POLICE_PREFEREE = "IBM Plex Sans Arabic"
POLICES_SECOURS = ["Segoe UI", "Tahoma", "Arial"]


_FAMILLES_CHARGEES: list[str] | None = None


def familles_chargees() -> list[str]:
    """الخطوط المرفقة (تُحمَّل مرة واحدة)."""
    global _FAMILLES_CHARGEES
    from PySide6.QtGui import QGuiApplication
    if QGuiApplication.instance() is None:   # قبل إنشاء التطبيق لا يمكن تحميل الخطوط (ولا نحفظ النتيجة)
        return []
    if _FAMILLES_CHARGEES is None:
        _FAMILLES_CHARGEES = []
        if DOSSIER_POLICES.exists():
            for f in sorted(DOSSIER_POLICES.glob("*.ttf")):
                fid = QFontDatabase.addApplicationFont(str(f))
                if fid >= 0:
                    _FAMILLES_CHARGEES += QFontDatabase.applicationFontFamilies(fid)
    return _FAMILLES_CHARGEES


def police_titres() -> str | None:
    """خط العناوين الخاص بالمظهر (أميري في المظهر المغربي) إن كان مرفقاً ومختلفاً عن خط الواجهة."""
    t = globals().get("POLICE_TITRE")
    return t if t and t != globals().get("POLICE") and t in familles_chargees() else None


def charger_police() -> QFont:
    """يحمّل خط المظهر المختار إن كان مرفقاً، وإلا الخط الافتراضي، وإلا خطوط Windows العربية."""
    familles = familles_chargees()
    voulu = globals().get("POLICE") or POLICE_PREFEREE
    famille = next((f for f in (voulu, POLICE_PREFEREE) if f in familles), POLICES_SECOURS[0])
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
QLineEdit:focus, QComboBox:focus, QDateEdit:focus {{ border: 2px solid {FOCUS}; }}
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
QPushButton#navQuitter {{ border: 1px solid {NAV_BORD}; border-radius: 10px; min-height: 42px; background: transparent;
    color: {NAV_TEXTE}; font-weight: 600; }}
QPushButton#navQuitter:hover {{ background: #B4235A; color: #FFFFFF; border-color: #B4235A; }}
QScrollArea#defilNav, QWidget#navigation {{ background: transparent; border: 0; }}
QScrollArea#defilNav > QWidget#qt_scrollarea_viewport {{ background: transparent; }}
QRadioButton {{ min-height: 36px; }}
QRadioButton::indicator, QCheckBox::indicator {{ width: 18px; height: 18px; }}
QTableWidget, QTableView, QListWidget, QPlainTextEdit, QTextEdit {{
    background: {BLANC}; border: 1px solid {BORDURE_CHAMP}; border-radius: 6px; gridline-color: {BORDURE_CARTE}; }}
QHeaderView::section {{ background: {ENTETE_FOND}; color: {ENTETE_TEXTE}; font-weight: 600; padding: 6px 8px;
    border: 0; border-bottom: 2px solid {BORDURE_CHAMP}; border-left: 1px solid {BORDURE_CARTE}; }}
QTableWidget::item:selected, QListWidget::item:selected {{ background: {VERT_CLAIR}; color: {MARINE}; }}
QPlainTextEdit:focus, QTextEdit:focus {{ border: 2px solid {FOCUS}; }}
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
QPushButton#boutonAnnee {{ background: {BADGE_FOND}; color: {BADGE_TEXTE}; border: 0; border-radius: 12px;
    min-height: 36px; font-weight: 700; }}
QPushButton#boutonAnnee:hover {{ border: 2px solid {NAV_ACCENT}; }}
#bandeauArchive {{ background: {ROUGE_CLAIR}; border-bottom: 2px solid {ROUGE}; }}
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
""" + feuille_maghribi()


def feuille_maghribi() -> str:
    """لمسات إضافية خاصة بالمظاهر ذات العناوين المزخرفة (المغربي): خط أميري، خط ذهبي، زوايا أنعم."""
    if not TITRE_SOULIGNE:
        return ""
    titre = police_titres()
    fam = f'font-family: "{titre}";' if titre else ""
    return f"""
#titrePage {{ {fam} font-size: 24pt; font-weight: 700; color: {VERT_FONCE};
    border-bottom: 2px solid {TITRE_SOULIGNE}; padding-bottom: 4px; }}
#etapeTitre {{ {fam} font-size: 19pt; }}
#navTitre {{ {fam} font-size: 15pt; }}
#titreCarte {{ color: {VERT_FONCE}; }}
#carte, #tuile {{ border-radius: 16px; border: 1px solid {BORDURE_CARTE}; }}
#tuile {{ border-top: 3px solid {TITRE_SOULIGNE}; }}
#chiffre {{ color: {VERT_FONCE}; }}
QPushButton {{ border-radius: 11px; color: {VERT_FONCE}; font-weight: 600; }}
QPushButton:hover {{ background: {VERT_CLAIR}; border-color: {TITRE_SOULIGNE}; }}
QPushButton#principal {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1E6B4A, stop:1 {VERT});
    color: {BLANC}; border: 1px solid {VERT_FONCE}; }}
QPushButton#principal:hover {{ background: {VERT_FONCE}; border-color: {TITRE_SOULIGNE}; }}
QPushButton#nav, QPushButton#sousnav {{ color: {NAV_TEXTE}; }}
QPushButton#nav:checked {{ border-right: 4px solid {NAV_ACCENT}; }}
QLineEdit, QComboBox, QDateEdit {{ border-radius: 10px; }}
QLineEdit:hover, QComboBox:hover, QDateEdit:hover {{ border-color: {TITRE_SOULIGNE}; }}
QTableWidget, QTableView {{ border-radius: 12px; alternate-background-color: #FBF8F1;
    selection-background-color: {VERT_CLAIR}; }}
QTableWidget::item:selected, QTableView::item:selected {{ background: {VERT_CLAIR}; color: {VERT_FONCE}; }}
QHeaderView::section {{ border-left: 1px solid #164B39; border-bottom: 2px solid {TITRE_SOULIGNE}; padding: 8px; }}
QTabBar::tab:selected {{ border-bottom: 3px solid {TITRE_SOULIGNE}; }}
#pastille {{ background: {VERT_CLAIR}; color: {VERT_FONCE}; border: 1px solid #E8D49C; }}
QScrollBar:vertical {{ background: transparent; width: 11px; margin: 3px; }}
QScrollBar::handle:vertical {{ background: #D8CCB2; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {TITRE_SOULIGNE}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QToolTip {{ background: {VERT_FONCE}; color: #FFFFFF; border: 1px solid {TITRE_SOULIGNE}; padding: 5px; }}
"""


def appliquer(nom: str) -> str:
    """يفعّل مظهراً ويرجع ورقة الأنماط المناسبة له (المظهر غير المعروف ← الأصلي)."""
    global THEME_ACTUEL, FEUILLE_STYLE
    THEME_ACTUEL = nom if nom in PALETTES else THEME_DEFAUT
    globals().update(PALETTES[THEME_ACTUEL])
    FEUILLE_STYLE = feuille()
    return FEUILLE_STYLE


FEUILLE_STYLE = feuille()
