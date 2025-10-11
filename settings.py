# -*- coding: utf-8 -*-
# Sticky Anki Add-on - Settings
#
# Author: Gemini
# License: GNU AGPLv3

import os
import json
import webbrowser
from aqt import mw
from aqt.qt import *
from PyQt6.QtCore import pyqtSignal as Signal
from PyQt6.QtGui import QFontDatabase


# Flag to ensure fonts are loaded only once per Anki session
fonts_loaded = False
FONT_NAME_MAP = {}

def load_custom_fonts():
    """Finds and loads custom .ttf fonts, mapping the filename to the actual family name."""
    global fonts_loaded, FONT_NAME_MAP
    if fonts_loaded:
        return

    addon_folder = os.path.dirname(__file__)
    fonts_dir = os.path.join(addon_folder, "fonts")
    if os.path.isdir(fonts_dir):
        for filename in os.listdir(fonts_dir):
            if filename.lower().endswith(".ttf"):
                font_path = os.path.join(fonts_dir, filename)
                font_id = QFontDatabase.addApplicationFont(font_path)

                families = QFontDatabase.applicationFontFamilies(font_id)
                if families:
                    ui_name = os.path.splitext(filename)[0]
                    FONT_NAME_MAP[ui_name] = families[0]
    fonts_loaded = True
    
# --- Helper Function ---

def get_contrasting_font_color(hex_color: str) -> str:
    """Calculates a readable font color based on the background color's luminance."""
    try:
        color = QColor(hex_color)
        h, s, l, _ = color.getHslF()

        if l > 0.55:
            new_l = max(0, l - 0.5)
            new_s = max(0, s - 0.2)
            font_color = QColor.fromHslF(h, new_s, new_l, 1.0)
        else:
            new_l = min(1, l + 0.6)
            new_s = max(0, s - 0.1)
            font_color = QColor.fromHslF(h, new_s, new_l, 1.0)
        
        return font_color.name()
    except Exception:
        return "#000000"

# --- Custom Widgets ---

class ColorButton(QPushButton):
    """A button that displays a color and opens a color picker when clicked."""
    color_changed = Signal(str)

    def __init__(self, initial_color="#FFFFFF", parent=None, is_custom=False):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._color = QColor(initial_color)
        self.is_custom = is_custom
        if self.is_custom:
            self.clicked.connect(self.on_click)
        self.setFixedSize(28, 28)

    def on_click(self):
        new_color = QColorDialog.getColor(self._color, self, "Select Color")
        if new_color.isValid():
            self.set_color(new_color.name())

    def set_color(self, color_hex):
        if self._color.name() != color_hex:
            self._color = QColor(color_hex)
            self.update()
            self.color_changed.emit(self.get_color())

    def get_color(self):
        return self._color.name()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(self._color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 6, 6)

class SegmentedControl(QWidget):
    """A custom widget that functions like a radio button group."""
    current_changed = Signal(str)

    def __init__(self, options=None, parent=None):
        super().__init__(parent)
        self._options = options if options else []
        self._buttons = []
        self._current_selection = self._options[0] if self._options else ""
        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        for i, option in enumerate(self._options):
            button = QPushButton(option)
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.button_group.addButton(button)
            self._buttons.append(button)
            layout.addWidget(button)

        self.button_group.buttonClicked.connect(self._on_button_clicked)

    def _on_button_clicked(self, button):
        self._current_selection = button.text()
        self.current_changed.emit(self._current_selection)
    
    def current_text(self):
        checked_button = self.button_group.checkedButton()
        if checked_button:
            return checked_button.text()
        return self._current_selection

    def set_current(self, text):
        for button in self._buttons:
            if button.text().lower() == text.lower():
                button.setChecked(True)
                self._current_selection = button.text()
                break

# --- Main Settings Dialog ---

class SettingsDialog(QDialog):
    def __init__(self, parent=None, config=None, config_path=None):
        super().__init__(parent)
        load_custom_fonts()
        self.config_path = config_path
        self.config = config
        self.setWindowTitle("Sticky Settings")
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(20)

        # Timer for debouncing preview updates to prevent lag
        self.preview_update_timer = QTimer(self)
        self.preview_update_timer.setSingleShot(True)
        self.preview_update_timer.timeout.connect(self.update_preview)
        
        self.setup_ui()
        self.apply_styles()
        self.connect_signals()
        
        QTimer.singleShot(0, self.update_preview)

    def setup_ui(self):
        # --- Header Section ---
        header_layout = QHBoxLayout()
        header_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.setSpacing(15)

        addon_path = os.path.dirname(__file__)
        logo_path = os.path.join(addon_path, "sticky_logo.png")
        if os.path.exists(logo_path):
            logo_label = QLabel()
            pixmap = QPixmap(logo_path)
            logo_label.setPixmap(pixmap.scaledToHeight(40, Qt.TransformationMode.SmoothTransformation))
            header_layout.addWidget(logo_label)

        donate_button = QPushButton("Donation")
        donate_button.setCursor(Qt.CursorShape.PointingHandCursor)
        donate_button.setObjectName("linkButton")
        donate_button.clicked.connect(lambda: webbrowser.open("https://buymeacoffee.com/peacemonk"))
        
        report_button = QPushButton("Report bugs")
        report_button.setCursor(Qt.CursorShape.PointingHandCursor)
        report_button.setObjectName("linkButton")
        report_button.clicked.connect(lambda: webbrowser.open("https://github.com/thepeacemonk/Sticky"))

        header_layout.addWidget(donate_button)
        header_layout.addWidget(report_button)
        
        self.main_layout.addLayout(header_layout)

        # --- Main Content ---
        main_hbox = QHBoxLayout()
        left_vbox = QVBoxLayout()
        main_hbox.addLayout(left_vbox, 1)

        note_group = QGroupBox("Note Content")
        note_layout = QVBoxLayout(note_group)
        self.note_editor = QTextEdit()
        self.note_editor.setPlaceholderText("Write your note here...")
        initial_text = self.config.get("note_text", "")
        self.note_editor.setText(initial_text)
        note_layout.addWidget(self.note_editor, 0, Qt.AlignmentFlag.AlignCenter)
        main_hbox.addWidget(note_group, 1)

        size_group = QGroupBox("Size")
        size_layout = QVBoxLayout(size_group)
        self.size_control = SegmentedControl(["Small", "Medium", "Big"])
        self.size_control.set_current(self.config.get("size", "Small"))
        size_layout.addWidget(self.size_control)
        left_vbox.addWidget(size_group)
        
        font_group = QGroupBox("Font")
        font_layout = QVBoxLayout(font_group)
        self.font_control = SegmentedControl(["Noto", "Bentham", "Montserrat", "Nunito", "SpaceMono"])
        self.font_control.set_current(self.config.get("font", "Noto"))
        font_layout.addWidget(self.font_control)
        left_vbox.addWidget(font_group)
        
        font_size_group = QGroupBox("Font Size")
        font_size_layout = QVBoxLayout(font_size_group)
        self.font_size_control = SegmentedControl(["Small", "Medium", "Large"])
        self.font_size_control.set_current(self.config.get("font_size", "Medium"))
        font_size_layout.addWidget(self.font_size_control)
        left_vbox.addWidget(font_size_group)

        align_group = QGroupBox("Text Alignment")
        align_layout = QVBoxLayout(align_group)
        self.align_control = SegmentedControl(["Left", "Center", "Right"])
        self.align_control.set_current(self.config.get("text_align", "Left"))
        align_layout.addWidget(self.align_control)
        left_vbox.addWidget(align_group)

        colors_group = QGroupBox("Color")
        colors_layout = QHBoxLayout(colors_group)
        self.preset_colors = ["#fef3c7", "#dbeafe", "#dcfce7", "#f3e8ff", "#fee2e2", "#424242"]
        
        for color in self.preset_colors:
            btn = ColorButton(color, is_custom=False)
            btn.clicked.connect(lambda _, c=color: self.main_color_btn.set_color(c))
            colors_layout.addWidget(btn)

        colors_layout.addStretch()

        customize_label = QLabel("Custom:")
        colors_layout.addWidget(customize_label)
        self.main_color_btn = ColorButton(self.config.get("bg_color", "#fef3c7"), is_custom=True)
        colors_layout.addWidget(self.main_color_btn)

        left_vbox.addWidget(colors_group)

        opacity_group = QGroupBox("Opacity")
        opacity_layout = QHBoxLayout(opacity_group)
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(10, 100)
        self.opacity_slider.setValue(int(self.config.get("opacity", 1.0) * 100))
        self.opacity_label = QLabel(f"{self.opacity_slider.value()}%")
        self.opacity_label.setMinimumWidth(40)
        opacity_layout.addWidget(self.opacity_slider)
        opacity_layout.addWidget(self.opacity_label)
        left_vbox.addWidget(opacity_group)
        
        left_vbox.addStretch()
        self.main_layout.addLayout(main_hbox)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.main_layout.addWidget(self.button_box)

    def on_text_changed(self):
        """Debounces the preview update to avoid lagging."""
        self.preview_update_timer.start(300)

    def connect_signals(self):
        # Update preview after a delay when text changes
        self.note_editor.textChanged.connect(self.on_text_changed)
        
        # Update preview instantly for other controls
        self.size_control.current_changed.connect(self.update_preview)
        self.font_control.current_changed.connect(self.update_preview)
        self.font_size_control.current_changed.connect(self.update_preview)
        self.align_control.current_changed.connect(self.update_preview)
        self.opacity_slider.valueChanged.connect(lambda v: self.opacity_label.setText(f"{v}%"))
        self.opacity_slider.valueChanged.connect(self.update_preview)
        self.main_color_btn.color_changed.connect(self.update_preview)
        
        self.button_box.accepted.connect(self.save_settings)
        self.button_box.rejected.connect(self.reject)

    def update_preview(self):
        size_str = self.size_control.current_text()
        size_map = {"Small": 200, "Medium": 300, "Big": 410}
        size_px = size_map.get(size_str, 200)

        bg_color = self.main_color_btn.get_color()
        opacity = self.opacity_slider.value() / 100.0
        font_family = self.font_control.current_text()
        font_size_str = self.font_size_control.current_text()
        align_str = self.align_control.current_text()

        font_size_map = {"Small": "12px", "Medium": "14px", "Large": "16px"}
        font_size = font_size_map.get(font_size_str, "14px")
        
        correct_font_name = FONT_NAME_MAP.get(font_family, font_family)
        font_family_str = f'"{correct_font_name}"'
        
        font_color = get_contrasting_font_color(bg_color)
        
        q_bg_color = QColor(bg_color)
        r, g, b, _ = q_bg_color.getRgb()
        bg_rgba = f"rgba({r}, {g}, {b}, {int(opacity * 255)})"
        
        align_map = {
            "Left": Qt.AlignmentFlag.AlignLeft,
            "Center": Qt.AlignmentFlag.AlignCenter,
            "Right": Qt.AlignmentFlag.AlignRight,
        }
        self.note_editor.setAlignment(align_map.get(align_str, Qt.AlignmentFlag.AlignLeft))
        
        style = f"""
            QTextEdit {{
                background-color: {bg_rgba};
                color: {font_color};
                border-radius: 20px;
                font-family: {font_family_str};
                font-size: {font_size};
                padding: 16px;
                border: 1px solid rgba(0,0,0,0.1);
            }}
        """
        self.note_editor.setStyleSheet(style)
        
        preview_size = size_px
        self.note_editor.setFixedSize(preview_size, preview_size)
        
    def save_settings(self):
        """Saves the current UI settings to the config.json file."""
        new_config = {
            "note_text": self.note_editor.toPlainText(),
            "size": self.size_control.current_text(),
            "font": self.font_control.current_text(),
            "font_size": self.font_size_control.current_text(),
            "text_align": self.align_control.current_text(),
            "bg_color": self.main_color_btn.get_color(),
            "opacity": self.opacity_slider.value() / 100.0
        }
        
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(new_config, f, indent=4)
        except (IOError, TypeError):
            self.reject()
            return

        self.accept()

    def apply_styles(self):
        is_dark = mw.pm.night_mode()
        bg_color = "#2F2F2F" if is_dark else "#F5F5F5"
        text_color = "#E0E0E0" if is_dark else "#212121"
        group_bg = "#3a3a3a" if is_dark else "#FFFFFF"
        group_border = "#555555" if is_dark else "#C5C5C5"
        btn_bg = "#555555" if is_dark else "#E0E0E0"
        btn_hover_bg = "#666666" if is_dark else "#D5D5D5"
        
        # MODIFIED: Replaced blue with yellow, and set a contrasting dark gray for text
        seg_checked_bg = "#FFE699"
        seg_checked_text_color = "#3a3a3a"

        self.setStyleSheet(f"""
            QDialog {{ background-color: {bg_color}; }}
            QLabel, QCheckBox {{ color: {text_color}; }}
            QGroupBox {{ 
                background-color: {group_bg};
                border: 1px solid {group_border};
                border-radius: 8px;
                margin-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px 5px 5px;
                color: {text_color};
            }}
            QPushButton {{ 
                background-color: {btn_bg}; color: {text_color}; 
                border: 1px solid {group_border}; border-radius: 8px; padding: 6px 12px;
            }}
            QPushButton:hover {{ background-color: {btn_hover_bg}; }}
            
            /* Styles for header buttons */
            QPushButton#linkButton {{
                background-color: transparent;
            }}
            QPushButton#linkButton:hover {{
                border: 1px solid {seg_checked_bg};
            }}
            
            SegmentedControl QPushButton {{
                padding: 6px 16px;
                font-size: 14px;
                border: none;
                background-color: transparent;
                color: {text_color};
                border-radius: 8px;
            }}
            SegmentedControl QPushButton:hover {{ background-color: {btn_hover_bg}; }}
            SegmentedControl QPushButton:checked {{
                background-color: {seg_checked_bg};
                color: {seg_checked_text_color};
            }}

            /* Opacity Slider */
            QSlider::groove:horizontal {{
                border: 1px solid {group_border};
                height: 4px;
                background: {btn_bg};
                margin: 2px 0;
                border-radius: 2px;
            }}

            QSlider::handle:horizontal {{
                background: {text_color};
                border: 1px solid {group_border};
                width: 14px;
                height: 14px;
                margin: -6px 0;
                border-radius: 8px;
            }}
            
            QSlider::sub-page:horizontal {{
                background: {seg_checked_bg};
                border: 1px solid {seg_checked_bg};
                height: 4px;
                border-radius: 2px;
            }}
        """)