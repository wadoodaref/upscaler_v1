"""Dark theme and shared visual constants matching face_swap_v1."""

from __future__ import annotations

BG        = "#16181d"
BG_PANEL  = "#1d2027"
BG_INPUT  = "#12141a"
BORDER    = "#2c313c"
TEXT      = "#e4e7ee"
TEXT_DIM  = "#8b93a5"
ACCENT    = "#4c8dff"
ACCENT_HI = "#6ba0ff"
OK        = "#3ec98a"
WARN      = "#e5b567"
ERROR     = "#e5686f"

STYLESHEET = f"""
QWidget {{
    background: {BG};
    color: {TEXT};
    font-family: "Segoe UI", -apple-system, sans-serif;
    font-size: 13px;
}}

QLabel, QCheckBox {{
    background: transparent;
}}

QFrame#Panel {{
    background: {BG_PANEL};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}

QLabel#Heading {{
    font-size: 14px;
    font-weight: 600;
    color: {TEXT};
    padding: 2px 0;
}}

QLabel#SubHeading {{
    color: {TEXT_DIM};
    font-size: 12px;
}}

QLabel#StatusOk    {{ color: {OK}; }}
QLabel#StatusWarn  {{ color: {WARN}; }}
QLabel#StatusError {{ color: {ERROR}; }}

QPushButton {{
    background: {BG_PANEL};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 7px 14px;
    color: {TEXT};
    font-weight: 500;
}}

QPushButton:hover  {{
    border-color: {ACCENT};
}}

QPushButton:pressed {{
    background: {BG_INPUT};
}}

QPushButton:disabled {{
    color: {TEXT_DIM};
    border-color: {BORDER};
}}

QPushButton#Primary {{
    background: {ACCENT};
    border: 1px solid {ACCENT};
    color: #ffffff;
    font-weight: 600;
    padding: 9px 18px;
}}

QPushButton#Primary:hover {{
    background: {ACCENT_HI};
}}

QPushButton#Primary:disabled {{
    background: {BORDER};
    border-color: {BORDER};
    color: {TEXT_DIM};
}}

QPushButton#Danger {{
    border-color: {ERROR};
    color: {ERROR};
}}

QPushButton#Danger:hover {{
    background: rgba(229, 104, 111, 0.15);
}}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {BG_INPUT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 8px;
    color: {TEXT};
    selection-background-color: {ACCENT};
}}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border-color: {ACCENT};
}}

QComboBox::drop-down {{
    border: none;
    width: 20px;
}}

QComboBox QAbstractItemView {{
    background: {BG_PANEL};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT};
    color: {TEXT};
}}

QCheckBox {{
    spacing: 8px;
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid {BORDER};
    background: {BG_INPUT};
}}

QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}

QProgressBar {{
    background: {BG_INPUT};
    border: 1px solid {BORDER};
    border-radius: 4px;
    text-align: center;
    color: {TEXT};
    font-size: 11px;
    height: 12px;
}}

QProgressBar::chunk {{
    background: {ACCENT};
    border-radius: 3px;
}}

QTabWidget::pane {{
    border: 1px solid {BORDER};
    background: {BG_PANEL};
    border-radius: 6px;
}}

QTabBar::tab {{
    background: {BG};
    border: 1px solid {BORDER};
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 6px 14px;
    margin-right: 4px;
    color: {TEXT_DIM};
}}

QTabBar::tab:selected {{
    background: {BG_PANEL};
    color: {TEXT};
    border-color: {BORDER};
    font-weight: 600;
}}

QScrollBar:vertical {{
    background: {BG};
    width: 10px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background: {BORDER};
    min-height: 20px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical:hover {{
    background: {TEXT_DIM};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QTableWidget {{
    background: {BG_INPUT};
    border: 1px solid {BORDER};
    gridline-color: {BORDER};
    color: {TEXT};
    border-radius: 6px;
}}

QHeaderView::section {{
    background: {BG_PANEL};
    color: {TEXT_DIM};
    border: none;
    border-right: 1px solid {BORDER};
    border-bottom: 1px solid {BORDER};
    padding: 4px 8px;
    font-weight: 600;
}}
"""
