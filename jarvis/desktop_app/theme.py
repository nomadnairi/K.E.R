"""
Visual themes for the desktop app.

Several named palettes share one layout; :func:`stylesheet` builds the Qt style
sheet for a chosen theme and :func:`bubble_html` renders chat bubbles in the
matching colours. Everything here is pure strings (no Qt import), so it stays
testable and reusable.
"""

from __future__ import annotations

# Font stacks — no bundled fonts needed; these look clean across OSes.
FONT_STACK = ('"Segoe UI", "SF Pro Display", "Inter", "Helvetica Neue", '
            "system-ui, Arial, sans-serif")
MONO_STACK = '"JetBrains Mono", "Cascadia Code", "SF Mono", Consolas, monospace'

# -- palettes -----------------------------------------------------------------
# Each theme defines the same keys so the stylesheet template stays shared.

THEMES: dict[str, dict[str, str]] = {
    # The first four mirror the Command Deck's themes one-for-one, so the native
    # shell (sign-in, config panels) and the embedded deck share one look.
    "obsidian": {
        "label": "Obsidian Amber",
        "bg": "#070a09", "panel": "#0f1412", "elevated": "#161c19",
        "border": "#1e2622", "text": "#e9efeb", "muted": "#8e9c96",
        "accent": "#e8b341", "accent_dim": "#9c7526", "accent_soft": "#1d1810",
        "accent_hi": "#f3c55a", "danger": "#ff6b5a", "success": "#3fd9b0",
        "on_accent": "#1a1205",
    },
    "aurora": {
        "label": "Aurora Glass (violet)",
        "bg": "#0b0b16", "panel": "#171728", "elevated": "#1f1f35",
        "border": "#2c2c48", "text": "#f2f3fa", "muted": "#a6a8c4",
        "accent": "#a78bfa", "accent_dim": "#6d4fd6", "accent_soft": "#1d1a34",
        "accent_hi": "#c4b5fd", "danger": "#fb7185", "success": "#4ade9b",
        "on_accent": "#0b0b16",
    },
    "carbon": {
        "label": "Carbon Minimal (mono)",
        "bg": "#0b0c0d", "panel": "#141518", "elevated": "#191a1e",
        "border": "#24262b", "text": "#f4f5f6", "muted": "#9a9da3",
        "accent": "#e6e8eb", "accent_dim": "#9aa0a6", "accent_soft": "#1b1d20",
        "accent_hi": "#ffffff", "danger": "#ef6b6b", "success": "#5bc98c",
        "on_accent": "#0d0e10",
    },
    "hud": {
        "label": "Reactor HUD (cyan)",
        "bg": "#00080c", "panel": "#00121a", "elevated": "#001c27",
        "border": "#0b3d4a", "text": "#dff6fa", "muted": "#78a6b2",
        "accent": "#00e5ff", "accent_dim": "#0090a8", "accent_soft": "#00222c",
        "accent_hi": "#7df2ff", "danger": "#ff6b6b", "success": "#5bffc0",
        "on_accent": "#001418",
    },
    "arc": {
        "label": "Arc Reactor (cyan)",
        "bg": "#0b0f14", "panel": "#121821", "elevated": "#1a2230",
        "border": "#243043", "text": "#e6edf3", "muted": "#8b98a9",
        "accent": "#22d3ee", "accent_dim": "#0e7490", "accent_soft": "#0b3a44",
        "accent_hi": "#38dbf0", "danger": "#f87171", "success": "#34d399",
        "on_accent": "#0b0f14",
    },
    "mark42": {
        "label": "Mark 42 (red / gold)",
        "bg": "#120a0a", "panel": "#1c1211", "elevated": "#271817",
        "border": "#3d2422", "text": "#f4e9e6", "muted": "#b39a94",
        "accent": "#e63946", "accent_dim": "#8f1d26", "accent_soft": "#3a1416",
        "accent_hi": "#ff5964", "danger": "#f87171", "success": "#e2b13c",
        "on_accent": "#120a0a",
    },
    "nebula": {
        "label": "Nebula (violet)",
        "bg": "#0d0b1a", "panel": "#161329", "elevated": "#201b3a",
        "border": "#2f2850", "text": "#eae7f7", "muted": "#9a93bd",
        "accent": "#a855f7", "accent_dim": "#6d28d9", "accent_soft": "#241a44",
        "accent_hi": "#c084fc", "danger": "#f87171", "success": "#34d399",
        "on_accent": "#0d0b1a",
    },
    "emerald": {
        "label": "Emerald (green)",
        "bg": "#08120e", "panel": "#101d17", "elevated": "#16281f",
        "border": "#22392d", "text": "#e4f2ea", "muted": "#8bab9a",
        "accent": "#10b981", "accent_dim": "#0a7d58", "accent_soft": "#0c2c22",
        "accent_hi": "#34d399", "danger": "#f87171", "success": "#34d399",
        "on_accent": "#08120e",
    },
    "light": {
        "label": "Daylight (light)",
        "bg": "#f4f6fb", "panel": "#ffffff", "elevated": "#eef1f7",
        "border": "#d3dae6", "text": "#1a2230", "muted": "#5b6675",
        "accent": "#0ea5e9", "accent_dim": "#0369a1", "accent_soft": "#dbeefb",
        "accent_hi": "#38bdf8", "danger": "#dc2626", "success": "#059669",
        "on_accent": "#ffffff",
    },
}

DEFAULT_THEME = "obsidian"


def theme_names() -> list[tuple[str, str]]:
    """(key, human label) pairs for the theme picker."""
    return [(key, val["label"]) for key, val in THEMES.items()]


def _palette(name: str) -> dict[str, str]:
    return THEMES.get(name) or THEMES[DEFAULT_THEME]


def stylesheet(theme: str = DEFAULT_THEME) -> str:
    """Return the global Qt style sheet for *theme*."""
    p = _palette(theme)
    return f"""
    * {{
        font-family: {FONT_STACK};
        font-size: 14px;
        color: {p['text']};
        outline: none;
    }}
    QMainWindow, QDialog {{ background: {p['bg']}; }}
    QScrollArea {{ background: transparent; border: none; }}
    QWidget#Card {{
        background: {p['panel']};
        border: 1px solid {p['border']};
        border-radius: 18px;
    }}
    QWidget#Header {{ background: {p['panel']}; border-bottom: 1px solid {p['border']}; }}
    QLabel#Wordmark {{
        font-family: {MONO_STACK};
        font-size: 21px; font-weight: 800; letter-spacing: 4px;
        color: {p['text']};
    }}
    QLabel#StatusDot {{ color: {p['success']}; font-size: 13px; font-weight: 600; }}
    QLabel#Subtle {{ color: {p['muted']}; font-size: 13px; }}
    QLabel#Hint {{ color: {p['muted']}; font-size: 12px; }}
    QLabel#Title {{ font-size: 22px; font-weight: 700; }}
    QLabel#PageTitle {{ font-size: 22px; font-weight: 800; letter-spacing: 0.3px; }}
    QLabel#PageSub {{ color: {p['muted']}; font-size: 13px; }}
    /* Form field labels sit muted above/next to their inputs. */
    QFormLayout > QLabel, QLabel#FieldLabel {{
        color: {p['muted']}; font-size: 12px; font-weight: 600;
        letter-spacing: 0.4px;
    }}

    /* Top navigation — a pill bar. */
    QTabWidget::pane {{ border: none; background: transparent; }}
    QTabBar {{ qproperty-drawBase: 0; }}
    QTabBar::tab {{
        background: transparent; color: {p['muted']};
        padding: 10px 20px; margin: 8px 4px; border-radius: 12px;
        font-weight: 700; font-size: 13px;
    }}
    QTabBar::tab:hover {{ color: {p['text']}; background: {p['elevated']}; }}
    QTabBar::tab:selected {{
        color: {p['on_accent']};
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 {p['accent_hi']}, stop:1 {p['accent']});
    }}

    QLineEdit, QPlainTextEdit, QTextEdit, QComboBox {{
        background: {p['elevated']}; border: 1px solid {p['border']};
        border-radius: 12px; padding: 11px 14px; min-height: 20px;
        selection-background-color: {p['accent_dim']};
    }}
    QLineEdit:hover, QComboBox:hover {{ border: 1px solid {p['muted']}; }}
    QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus {{
        border: 1px solid {p['accent']};
    }}
    QComboBox::drop-down {{ border: none; width: 28px; }}
    QComboBox QAbstractItemView {{
        background: {p['panel']}; border: 1px solid {p['border']};
        selection-background-color: {p['accent_soft']}; border-radius: 10px;
        padding: 4px;
    }}

    QPushButton {{
        background: {p['elevated']}; border: 1px solid {p['border']};
        border-radius: 12px; padding: 11px 20px; font-weight: 700;
        min-height: 20px;
    }}
    QPushButton:hover {{ border: 1px solid {p['accent']}; color: {p['accent']}; }}
    QPushButton:pressed {{ background: {p['panel']}; }}
    QPushButton#Primary {{
        color: {p['on_accent']}; border: none; font-size: 14px;
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 {p['accent_hi']}, stop:1 {p['accent']});
    }}
    QPushButton#Primary:hover {{ background: {p['accent_hi']}; color: {p['on_accent']}; }}
    QPushButton#Primary:pressed {{ background: {p['accent_dim']}; }}
    QPushButton#Danger:hover {{ border: 1px solid {p['danger']}; color: {p['danger']}; }}
    QPushButton#Record {{
        background: {p['accent_soft']}; border: 1px solid {p['accent']};
        color: {p['accent']}; font-size: 16px; font-weight: 700;
        border-radius: 16px; min-height: 30px;
    }}
    QPushButton#Record:hover {{ background: {p['accent_dim']}; color: {p['on_accent']}; }}

    QCheckBox, QRadioButton {{ spacing: 10px; padding: 7px 0; font-size: 14px; }}
    QCheckBox::indicator, QRadioButton::indicator {{
        width: 20px; height: 20px; border: 1px solid {p['border']};
        border-radius: 6px; background: {p['elevated']};
    }}
    QRadioButton::indicator {{ border-radius: 10px; }}
    QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
        border: 1px solid {p['accent']};
    }}
    QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
        background: {p['accent']}; border: 1px solid {p['accent']};
    }}

    QScrollBar:vertical {{ background: transparent; width: 12px; margin: 4px; }}
    QScrollBar::handle:vertical {{ background: {p['border']}; border-radius: 6px; min-height: 36px; }}
    QScrollBar::handle:vertical:hover {{ background: {p['muted']}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}
    """


def bubble_html(role: str, text: str, theme: str = DEFAULT_THEME) -> str:
    """Return an HTML fragment for one chat message bubble in *theme*."""
    p = _palette(theme)
    safe = (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(
        ">", "&gt;").replace("\n", "<br>")
    if role == "user":
        return (
            f'<div style="margin:10px 0; text-align:right;">'
            f'<span style="display:inline-block; max-width:78%; text-align:left;'
            f" background:{p['accent_soft']}; color:{p['text']};"
            f" border:1px solid {p['accent_dim']};"
            f' padding:9px 13px; border-radius:14px 14px 4px 14px;">{safe}</span>'
            f'</div>'
        )
    if role == "system":
        return (f'<div style="margin:8px 0; text-align:center; color:{p["muted"]};'
                f' font-size:12px;">{safe}</div>')
    return (
        f'<div style="margin:10px 0; text-align:left;">'
        f'<span style="display:inline-block; max-width:78%;'
        f" background:{p['panel']}; color:{p['text']}; border:1px solid {p['border']};"
        f' padding:9px 13px; border-radius:14px 14px 14px 4px;">{safe}</span>'
        f'</div>'
    )
