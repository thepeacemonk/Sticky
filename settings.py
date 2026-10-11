# -*- coding: utf-8 -*-
# Sticky Anki Add-on - Settings
import os
import json
import importlib
import webbrowser
from aqt import mw
from aqt.qt import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QWidget, QFormLayout,
    QColorDialog, QColor, QSlider, QSpinBox, Qt, QPixmap, QScrollArea, QLineEdit,
    pyqtSignal, QFrame, QButtonGroup, QAbstractButton, QApplication, QTextEdit, QTimer, QDesktopServices
)
try:
    from PyQt6.QtCore import pyqtProperty, QPropertyAnimation, QEasingCurve, QRectF, QParallelAnimationGroup, QPointF, QUrl, QSize
    from PyQt6.QtGui import QPainter, QPen, QColor as QColor2, QPainterPath, QFont, QFontDatabase
    from PyQt6.QtWidgets import QSizePolicy
except ImportError:
    from PyQt5.QtCore import pyqtProperty, QPropertyAnimation, QEasingCurve, QRectF, QParallelAnimationGroup, QPointF, QUrl, QSize
    from PyQt5.QtGui import QPainter, QPen, QColor as QColor2, QPainterPath, QFont, QFontDatabase
    from PyQt5.QtWidgets import QSizePolicy
from aqt.theme import theme_manager
from aqt.webview import AnkiWebView
from . import bento_integration

# Flag to ensure fonts are loaded only once per Anki session
fonts_loaded = False
FONT_NAME_MAP = {}

def load_custom_fonts():
    """Finds and loads custom .ttf fonts, mapping the filename to the actual family name."""
    global fonts_loaded, FONT_NAME_MAP
    if fonts_loaded: return
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

def get_contrasting_font_color(hex_color: str) -> str:
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

# --- Shared UI Components ---
class GooeySegmentedControl(QWidget):
    def __init__(self, accent_color="#FFE699", parent=None, bg_color="#f2f2f2", border_color="#dcdde1"):
        super().__init__(parent)
        self.setObjectName("themeToggleContainer")
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(0)
        self._accent_color = QColor(accent_color)
        self._bg_color = QColor(bg_color)
        self._border_color = QColor(border_color)
        self._indicator_rect = QRectF(4, 4, 0, 0)
        self.anim_group = QParallelAnimationGroup(self)
        self.anim_x = QPropertyAnimation(self, b"indicator_x")
        self.anim_width = QPropertyAnimation(self, b"indicator_width")
        self.anim_group.addAnimation(self.anim_x)
        self.anim_group.addAnimation(self.anim_width)
        self.anim_x.setEasingCurve(QEasingCurve.Type.InOutBack)
        self.anim_width.setEasingCurve(QEasingCurve.Type.InOutBack)
        self.anim_x.setDuration(400)
        self.anim_width.setDuration(400)
        self.button_group = QButtonGroup(self)
        self.button_group.buttonClicked.connect(self.animate_to)

    @pyqtProperty(float)
    def indicator_x(self):
        return self._indicator_rect.x()

    @indicator_x.setter
    def indicator_x(self, value):
        self._indicator_rect.setX(value)
        self.update()

    @pyqtProperty(float)
    def indicator_width(self):
        return self._indicator_rect.width()

    @indicator_width.setter
    def indicator_width(self, value):
        self._indicator_rect.setWidth(value)
        self.update()

    def add_button(self, btn):
        btn.setMinimumWidth(0)
        btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._layout.addWidget(btn, 1)
        self.button_group.addButton(btn)

    def current_text(self):
        btn = self.button_group.checkedButton()
        return btn.text() if btn else ""

    def animate_to(self, btn):
        if not btn: return
        target_rect = btn.geometry()
        if target_rect.width() == 0: return
        self.anim_x.setStartValue(self.indicator_x)
        self.anim_x.setEndValue(float(target_rect.x()))
        self.anim_width.setStartValue(self.indicator_width)
        self.anim_width.setEndValue(float(target_rect.width()))
        self.anim_group.start()

    def update_indicator_no_animation(self):
        checked_btn = self.button_group.checkedButton()
        if checked_btn and checked_btn.geometry().width() > 0:
            r = checked_btn.geometry()
            self._indicator_rect.setX(r.x())
            self._indicator_rect.setWidth(r.width())
            self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_indicator_no_animation()

    def showEvent(self, event):
        super().showEvent(event)
        try:
            from PyQt6.QtCore import QTimer
        except ImportError:
            from PyQt5.QtCore import QTimer
        QTimer.singleShot(50, self.update_indicator_no_animation)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw the pill track ourselves (radius = actual height / 2) instead
        # of relying on QSS border-radius, which doesn't clamp large values
        # the way CSS does and can render as a barely-rounded rectangle.
        track_radius = self.height() / 2.0
        track_rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        track_path = QPainterPath()
        track_path.addRoundedRect(track_rect, track_radius, track_radius)
        p.setPen(QPen(self._border_color, 1))
        p.setBrush(self._bg_color)
        p.drawPath(track_path)

        if self._indicator_rect.width() > 0:
            # The InOutBack easing on the slide animation overshoots past its
            # target (that's what gives it the "gooey" bounce), which can push
            # the indicator's rounded corner past x=0 mid-animation. Clipping
            # to the track's own rounded path (rather than the widget's plain
            # rectangular bounds) means any overshoot gets bounded by the
            # pill's curve instead of being sliced off into a flat edge.
            p.setClipPath(track_path)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(self._accent_color)
            checked_btn = self.button_group.checkedButton()
            h = checked_btn.geometry().height() if checked_btn else 28
            y = checked_btn.geometry().y() if checked_btn else 4
            rect = QRectF(self._indicator_rect.x(), float(y), self._indicator_rect.width(), float(h))
            radius = h / 2.0
            p.drawRoundedRect(rect, radius, radius)

class ModernSlider(QSlider):
    def __init__(self, accent_color="#FFE699", parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.accent_color = QColor(accent_color)
        self.setMinimumHeight(24)

    def _theme_tokens(self):
        curr = self.parent()
        while curr:
            if hasattr(curr, "_theme_tokens"):
                return curr._theme_tokens()
            curr = curr.parent()
        return {
            "border": "#d1d5db" if not theme_manager.night_mode else "#444444",
            "surface": "#eaeaea" if not theme_manager.night_mode else "#2d2d2d",
        }

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        enabled = self.isEnabled()
        w = self.width()
        h = self.height()

        # Track parameters
        track_h = 18
        track_y = (h - track_h) // 2
        track_rx = track_h // 2

        min_val = self.minimum()
        max_val = self.maximum()
        val = self.value()

        range_val = max_val - min_val
        if range_val <= 0:
            range_val = 1

        handle_d = 12
        padding_x = 9

        x_min = padding_x
        x_max = w - padding_x
        pct = (val - min_val) / range_val
        handle_cx = x_min + pct * (x_max - x_min)

        # Get background color from tokens
        tokens = self._theme_tokens()
        bg_color_hex = tokens.get("surface", "#eaeaea")
        bg_color = QColor(bg_color_hex)

        if enabled:
            active_color = self.accent_color
        else:
            active_color = QColor(self.accent_color.red(), self.accent_color.green(), self.accent_color.blue(), 76)
            bg_color.setAlpha(76)

        # Draw background track
        track_rect = QRectF(0, track_y, w, track_h)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg_color)
        painter.drawRoundedRect(track_rect, track_rx, track_rx)

        # Draw active track
        active_right = handle_cx + 10
        if active_right > w:
            active_right = w
        if active_right < track_rx * 2:
            active_right = track_rx * 2

        active_rect = QRectF(0, track_y, active_right, track_h)
        painter.setBrush(active_color)
        painter.drawRoundedRect(active_rect, track_rx, track_rx)

        # Draw handle (white circle centered at handle_cx)
        handle_cy = track_y + track_h / 2
        handle_color = QColor("#ffffff") if enabled else QColor(255, 255, 255, 120)
        painter.setBrush(handle_color)
        painter.drawEllipse(QPointF(handle_cx, handle_cy), 6, 6)

class SectionGroup(QWidget):
    def __init__(self, title="", parent=None, description=""):
        super().__init__(parent)
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(0, 5, 0, 0)
        title_label = QLabel(title)
        title_label.setStyleSheet("font-weight: bold; font-size: 17px; margin-bottom: 2px;")
        main_layout.addWidget(title_label)
        if description:
            desc_label = QLabel(description)
            desc_label.setStyleSheet("font-size: 11px; color: #888; margin-bottom: 5px;")
            desc_label.setWordWrap(True)
            main_layout.addWidget(desc_label)
        self.content_area = QWidget()
        self.content_area.setObjectName("innerGroup")
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(15, 15, 15, 15)
        self.content_layout.setSpacing(10)
        main_layout.addWidget(self.content_area)

    def add_widget(self, widget):
        self.content_layout.addWidget(widget)
    def add_layout(self, layout):
        self.content_layout.addLayout(layout)

class ColorButton(QPushButton):
    color_changed = pyqtSignal(str)
    def __init__(self, initial_color="#FFFFFF", parent=None, is_custom=False):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._color = QColor(initial_color)
        self.is_custom = is_custom
        if self.is_custom:
            self.clicked.connect(self.on_click)
        self.setFixedSize(28, 28)
    def on_click(self):
        try:
            onigiri_color_picker = importlib.import_module("1011095603.onigiri_color_picker")
            OnigiriColorDialog = onigiri_color_picker.OnigiriColorDialog
            new_color_hex, ok = OnigiriColorDialog.getColor(self.get_color(), self, anchor=self)
            if ok:
                self.set_color(new_color_hex)
            return
        except Exception as e:
            print(f"[Sticky] Failed to load OnigiriColorDialog: {e}")

        new_color = QColorDialog.getColor(
            self._color,
            self,
            "Select Color",
            QColorDialog.ColorDialogOption.DontUseNativeDialog,
        )
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


# ─── Live Preview ────────────────────────────────────────────────────────────

class StickyPreviewWidget(QWidget):
    """Renders a live HTML preview of the Sticky note widget using the
    in-progress (unsaved) settings-dialog config."""

    # #sticky-container's actual width/height are dictated by the Onigiri
    # integration's manual width/height (see bento_integration.sizing_css(),
    # which overrides them last in the cascade), plus the 20px top/bottom
    # `margin: 20px auto` baked into its own CSS.

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config

        self.preview_layout = QVBoxLayout(self)
        self.preview_layout.setContentsMargins(0, 0, 0, 0)

        self.webview = None

        # As with Global, the centering/scale math is computed in Python from
        # Qt's actual widget size and baked into the generated HTML (see
        # refresh()) rather than measured at runtime via JS.
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self.refresh)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._resize_timer.start(120)

    def cleanup(self):
        """Release the embedded AnkiWebView before this widget is destroyed.

        AnkiWebView wraps a QWebEngineView; if it is left to be torn down
        implicitly during Python interpreter finalization (Anki quitting),
        Qt dereferences already-freed child widgets and segfaults. Cleaning
        it up explicitly on dialog close avoids that.
        """
        if getattr(self, "_resize_timer", None) is not None:
            self._resize_timer.stop()
        if getattr(self, "webview", None) is not None:
            if getattr(self, "webview", None):
                self.webview.cleanup()
            self.webview = None


    def showEvent(self, event):
        super().showEvent(event)
        if getattr(self, "webview", None) is None:
            self.webview = AnkiWebView(title="sticky_preview", parent=self)
            self.webview.setMinimumSize(260, 300)
            self.webview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self.webview.disable_zoom()
            page = self.webview.page()
            page.setBackgroundColor(QColor(0, 0, 0, 0))
            self.preview_layout.addWidget(self.webview)
            self.refresh()

    def refresh(self):
        if not getattr(self, "webview", None):
            return
        addon_module = importlib.import_module(__package__)
        is_dark = theme_manager.night_mode

        # Sticky's generate_css()/generate_html() take no config argument —
        # they read the add-on's module-level CONFIG directly. To preview
        # unsaved edits from this dialog, temporarily swap that module-level
        # CONFIG for the in-progress one, render, then restore it so the
        # real deck-browser widget (and its cache) are left untouched.
        original_config = dict(addon_module.CONFIG)
        try:
            addon_module.CONFIG.clear()
            addon_module.CONFIG.update(self.config)
            css = addon_module.generate_css()
            html_content = addon_module.generate_html()
        finally:
            addon_module.CONFIG.clear()
            addon_module.CONFIG.update(original_config)

        # Behind the widget: Onigiri's actual deck-browser wallpaper when the
        # integration is active, otherwise the same flat color as this dialog.
        settings_bg = "#181818" if is_dark else "#f7f7f7"
        wallpaper = None
        if bento_integration.is_onigiri_detected():
            wallpaper = bento_integration.main_menu_wallpaper(is_dark)
        if not wallpaper:
            wallpaper = {"kind": "color", "color": settings_bg}

        if wallpaper["kind"] == "image":
            bg_layer_css = f"""
                background-color: {wallpaper['color']};
                background-image: url('{wallpaper['url']}');
                background-size: cover; background-position: center; background-repeat: no-repeat;
                filter: blur({wallpaper['blur_px']}px);
                opacity: {wallpaper['opacity']};
            """
        else:
            bg_layer_css = f"background-color: {wallpaper['color']}; opacity: 1;"

        # Natural (unscaled) size: #sticky-container's real width/height come
        # from the Onigiri integration's manual size (bento_integration
        # overrides them last in the CSS cascade), plus the 20px margin
        # above/below baked into its own CSS.
        natural_w = int(self.config.get(bento_integration.WIDTH_KEY, 200) or 200)
        natural_h = int(self.config.get(bento_integration.HEIGHT_KEY, 200) or 200) + 40

        panel_w = self.webview.width()
        panel_h = self.webview.height()
        if panel_w < 100 or panel_h < 100:
            panel_w, panel_h = 320, 400

        avail_w = panel_w - 40
        avail_h = panel_h - 40
        factor = min(1.0, avail_w / natural_w, avail_h / natural_h) * 0.94
        # +2px so sub-pixel rendering of the scaled content can never end up
        # a hair taller/wider than the box it's placed in.
        final_w = natural_w * factor + 2
        final_h = natural_h * factor + 2

        full_html = f"""
        <html><head><style>
            html, body {{ margin: 0; padding: 0; height: 100%; overflow: hidden; background: transparent; }}
            body {{
                position: relative;
                display: flex; align-items: center; justify-content: center;
                background: transparent;
            }}
            #onigiri-bg-container {{
                position: absolute; inset: 10px; z-index: 0;
                border-radius: 20px; overflow: hidden;
                transform: translateZ(0);
            }}
            #onigiri-bg-layer {{
                position: absolute; inset: -50px;
                {bg_layer_css}
            }}
            /* Only the box's own size (final_w/final_h) comes from Python;
               centering it is left entirely to flexbox on <body> above.
               No overflow:hidden here: if the estimate falls a hair short,
               the card should spill slightly into the margin rather than
               have its rounded corner sliced flat. */
            #scale-wrapper {{
                position: relative; z-index: 1;
                width: {final_w}px; height: {final_h}px;
                flex-shrink: 0;
            }}
            /* Named distinctly from "#sticky-wrapper" (below) so this
               positioning/scaling rule never collides with generate_css()'s
               own #sticky-wrapper rule (width:100%/height:100%/display:flex,
               meant for its real deck-browser embedding) — colliding the two
               used to double-apply sizing and knock the note off-center. */
            #sticky-preview-inner {{
                position: absolute; top: 0; left: 0;
                width: {natural_w}px; height: {natural_h}px;
                transform: scale({factor}); transform-origin: top left;
            }}
        </style></head>
        <body>
            <div id="onigiri-bg-container">
                <div id="onigiri-bg-layer"></div>
            </div>
            <div id="scale-wrapper">
                <div id="sticky-preview-inner">
                    <div id="sticky-wrapper">
                        <style>{css}</style>
                        {html_content}
                    </div>
                </div>
            </div>
        </body></html>
        """
        self.webview.setHtml(full_html)


class SettingsDialog(QDialog):
    def __init__(self, parent=None, config=None, config_path=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        load_custom_fonts()
        self.setWindowTitle("Sticky Settings")
        
        screen = QApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            self.resize(int(avail.width() * 0.5), int(avail.height() * 0.55))
        else:
            self.resize(820, 600)
        self.setMinimumSize(760, 500)

        self.config_path = config_path
        self.config = config
        
        self.preview_update_timer = QTimer(self)
        self.preview_update_timer.setSingleShot(True)
        self.preview_update_timer.timeout.connect(self.update_preview)

        self.setup_ui()
        self.connect_signals()

        QTimer.singleShot(0, self.update_preview)

        # Tear down the embedded AnkiWebView and schedule the dialog for
        # deletion when it closes, so it does not linger as a child of the
        # main window with a live QWebEngineView (which segfaults during
        # interpreter shutdown). deleteLater() is used instead of
        # WA_DeleteOnClose because this dialog is shown with exec(): a
        # WA_DeleteOnClose delete happens inside the modal loop and frees the
        # dialog while exec() is still unwinding, which itself crashes.
        self.finished.connect(self._cleanup_on_close)

    def _cleanup_on_close(self, *args):
        if getattr(self, "preview_update_timer", None) is not None:
            self.preview_update_timer.stop()
        preview = getattr(self, "preview_widget", None)
        if preview is not None:
            preview.cleanup()
        self.deleteLater()

    def _theme_tokens(self):
        is_dark = theme_manager.night_mode
        accent = "#FFE699" # Sticky accent
        if is_dark:
            return {"bg": "#181818", "panel": "#242424", "surface": "#303030", "fg": "#f4f4f5", "muted": "#c4c4c4", "border": "#454545", "accent": accent, "accent_text": "#3a3a3a"}
        return {"bg": "#f7f7f7", "panel": "#ffffff", "surface": "#f2f2f2", "fg": "#202124", "muted": "#6f7177", "border": "#dcdde1", "accent": accent, "accent_text": "#3a3a3a"}

    def setup_ui(self):
        tokens = self._theme_tokens()
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        content_h_layout = QHBoxLayout()
        content_h_layout.setSpacing(0)
        content_h_layout.setContentsMargins(0, 0, 0, 0)

        # --- Left: Controls panel ---
        controls_outer = QWidget()
        controls_outer.setObjectName("controlsOuter")
        controls_outer_layout = QVBoxLayout(controls_outer)
        controls_outer_layout.setContentsMargins(8, 10, 8, 0)
        controls_outer_layout.setSpacing(0)

        controls_container = QFrame()
        controls_container.setObjectName("controlsContainer")
        controls_container.setFrameShape(QFrame.Shape.NoFrame)
        controls_container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        controls_container_layout = QVBoxLayout(controls_container)
        controls_container_layout.setContentsMargins(0, 0, 0, 0)
        controls_container_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setObjectName("controlsScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(28, 24, 28, 20)
        scroll_layout.setSpacing(20)
        scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Note text
        note_group = SectionGroup("Note Text", self)
        self.note_editor = QTextEdit()
        self.note_editor.setObjectName("noteEditor")
        self.note_editor.setFrameShape(QFrame.Shape.NoFrame)
        self.note_editor.setPlaceholderText("Write your note here...")
        self.note_editor.setText(self.config.get("note_text", ""))
        self.note_editor.setFixedHeight(140)
        note_group.add_widget(self.note_editor)
        scroll_layout.addWidget(note_group)

        # Setup right side options
        def create_segmented(group_title, options, dict_key, default):
            group = SectionGroup(group_title, self)
            seg = GooeySegmentedControl(tokens["accent"], self, bg_color=tokens["surface"], border_color=tokens["border"])
            curr = self.config.get(dict_key, default)
            for opt in options:
                btn = QPushButton(opt)
                btn.setCheckable(True)
                btn.setObjectName("themeToggleButton")
                btn.setFixedHeight(28)
                if opt == curr: btn.setChecked(True)
                seg.add_button(btn)
            group.add_widget(seg)
            scroll_layout.addWidget(group)
            return seg

        self.font_control = create_segmented("Font", ["Noto", "Bentham", "Montserrat", "Nunito", "SpaceMono"], "font", "Noto")
        self.font_size_control = create_segmented("Font Size", ["Small", "Medium", "Large"], "font_size", "Medium")
        self.align_control = create_segmented("Text Alignment", ["Left", "Center", "Right"], "text_align", "Left")

        colors_group = SectionGroup("Color", self)
        colors_layout = QHBoxLayout()
        colors_layout.setContentsMargins(0,0,0,0)
        self.preset_colors = ["#fef3c7", "#dbeafe", "#dcfce7", "#f3e8ff", "#fee2e2", "#424242"]
        for color in self.preset_colors:
            btn = ColorButton(color, is_custom=False)
            btn.clicked.connect(lambda _, c=color: self.main_color_btn.set_color(c))
            colors_layout.addWidget(btn)
        colors_layout.addStretch()
        colors_layout.addWidget(QLabel("Custom:"))
        self.main_color_btn = ColorButton(self.config.get("bg_color", "#fef3c7"), is_custom=True)
        colors_layout.addWidget(self.main_color_btn)
        colors_group.add_layout(colors_layout)
        scroll_layout.addWidget(colors_group)

        opacity_group = SectionGroup("Opacity", self)
        opacity_layout = QHBoxLayout()
        opacity_layout.setContentsMargins(0,0,0,0)
        self.opacity_slider = ModernSlider(tokens["accent"], self)
        self.opacity_slider.setObjectName("berrySlider")
        self.opacity_slider.setRange(10, 100)
        self.opacity_slider.setCursor(Qt.CursorShape.PointingHandCursor)
        self.opacity_slider.setValue(int(self.config.get("opacity", 1.0) * 100))
        self.opacity_label = QLabel(f"{self.opacity_slider.value()}%")
        self.opacity_slider.valueChanged.connect(lambda v: self.opacity_label.setText(f"{v}%"))
        opacity_layout.addWidget(self.opacity_slider, 1)
        opacity_layout.addWidget(self.opacity_label)
        opacity_group.add_layout(opacity_layout)
        scroll_layout.addWidget(opacity_group)

        integration_group, self.bento_width_spin, self.bento_height_spin = bento_integration.create_settings_group(
            self.config, default_width=200, default_height=200
        )
        scroll_layout.addWidget(integration_group)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        scroll.viewport().setAutoFillBackground(False)
        scroll_content.setAutoFillBackground(False)
        controls_container.setAutoFillBackground(False)
        controls_container_layout.addWidget(scroll)
        controls_outer_layout.addWidget(controls_container)

        # --- Right: Preview panel ---
        preview_wrapper = QWidget()
        preview_wrapper.setObjectName("previewWrapper")
        preview_wrapper_layout = QVBoxLayout(preview_wrapper)
        preview_wrapper_layout.setContentsMargins(10, 24, 20, 20)
        preview_wrapper_layout.setSpacing(12)

        preview_title = QLabel("Preview")
        preview_title.setStyleSheet(f"font-size: 12px; font-weight: 700; letter-spacing: 0.6px; color: {tokens['muted']};")
        preview_wrapper_layout.addWidget(preview_title)

        self.preview_widget = StickyPreviewWidget(self._collect_config(), self)
        preview_wrapper_layout.addWidget(self.preview_widget, 1)

        content_h_layout.addWidget(controls_outer, 1)
        content_h_layout.addWidget(preview_wrapper, 1)
        root_layout.addLayout(content_h_layout, 1)

        # Bottom Pill Bar
        bottom_container = QWidget()
        bottom_container.setObjectName("bottomContainer")
        bottom_container_layout = QVBoxLayout(bottom_container)
        bottom_container_layout.setContentsMargins(20, 8, 20, 20)
        
        bottom_bar = QWidget()
        bottom_bar.setObjectName("bottomPillBar")
        bottom_bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        bottom_bar_layout = QHBoxLayout(bottom_bar)
        bottom_bar_layout.setContentsMargins(10, 10, 10, 10)
        bottom_bar_layout.setSpacing(8)

        logo_label = QLabel()
        logo_path = os.path.join(os.path.dirname(__file__), "sticky_logo.svg")
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            scaled_pixmap = pixmap.scaled(200, 36, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            logo_label.setPixmap(scaled_pixmap)
            logo_label.setFixedSize(scaled_pixmap.size())
            logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            bottom_bar_layout.addWidget(logo_label)

        bottom_bar_layout.addSpacing(8)
        self.donate_button = QPushButton("Donate")
        self.donate_button.setObjectName("cancelButton")
        self.donate_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.report_button = QPushButton("Report Bug")
        self.report_button.setObjectName("cancelButton")
        self.report_button.setCursor(Qt.CursorShape.PointingHandCursor)
        bottom_bar_layout.addWidget(self.donate_button)
        bottom_bar_layout.addWidget(self.report_button)
        
        self.donate_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://buymeacoffee.com/peacemonk")))
        self.report_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/thepeacemonk/Sticky")))

        bottom_bar_layout.addStretch()
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("cancelButton")
        self.cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_button.clicked.connect(self.reject)
        self.save_button = QPushButton("Save")
        self.save_button.setObjectName("saveButton")
        self.save_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_button.clicked.connect(self.save_settings)
        
        bottom_bar_layout.addWidget(self.cancel_button)
        bottom_bar_layout.addWidget(self.save_button)

        bottom_container_layout.addWidget(bottom_bar)
        root_layout.addWidget(bottom_container)

        self._apply_stylesheet()

    def on_text_changed(self):
        self.preview_update_timer.start(300)

    def connect_signals(self):
        self.note_editor.textChanged.connect(self.on_text_changed)
        for sg in [self.font_control, self.font_size_control, self.align_control]:
            for btn in sg.button_group.buttons():
                btn.clicked.connect(self.update_preview)

        self.opacity_slider.valueChanged.connect(self.update_preview)
        self.main_color_btn.color_changed.connect(self.update_preview)
        self.bento_width_spin.valueChanged.connect(self.update_preview)
        self.bento_height_spin.valueChanged.connect(self.update_preview)

    def _collect_config(self):
        """Snapshot the dialog's current (possibly unsaved) settings as a
        plain config dict, in the same shape as the add-on's saved config."""
        config = {
            "note_text": self.note_editor.toPlainText() if hasattr(self, "note_editor") else self.config.get("note_text", ""),
            "font": self.font_control.current_text() if hasattr(self, "font_control") else self.config.get("font", "Noto"),
            "font_size": self.font_size_control.current_text() if hasattr(self, "font_size_control") else self.config.get("font_size", "Medium"),
            "text_align": self.align_control.current_text() if hasattr(self, "align_control") else self.config.get("text_align", "Left"),
            "bg_color": self.main_color_btn.get_color() if hasattr(self, "main_color_btn") else self.config.get("bg_color", "#fef3c7"),
            "opacity": (self.opacity_slider.value() / 100.0) if hasattr(self, "opacity_slider") else self.config.get("opacity", 1.0),
        }
        config[bento_integration.WIDTH_KEY] = self.bento_width_spin.value() if hasattr(self, "bento_width_spin") else self.config.get(bento_integration.WIDTH_KEY, 200)
        config[bento_integration.HEIGHT_KEY] = self.bento_height_spin.value() if hasattr(self, "bento_height_spin") else self.config.get(bento_integration.HEIGHT_KEY, 200)
        return config

    def _refresh_preview(self):
        if hasattr(self, "preview_widget"):
            self.preview_widget.config = self._collect_config()
            self.preview_widget.refresh()

    def update_preview(self):
        self._refresh_preview()

    def save_settings(self):
        new_config = self._collect_config()

        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(new_config, f, indent=4)
        except (IOError, TypeError):
            self.reject()
            return
        self.accept()

    def _apply_stylesheet(self):
        t = self._theme_tokens()
        bg, panel, fg, muted, surface, border, accent, accent_text = t["bg"], t["panel"], t["fg"], t["muted"], t["surface"], t["border"], t["accent"], t["accent_text"]
        accent_hex = accent.lstrip("#")
        accent_rgb = tuple(int(accent_hex[i:i+2], 16) for i in (0, 2, 4))
        scrollbar_thumb = f"rgba({accent_rgb[0]}, {accent_rgb[1]}, {accent_rgb[2]}, 0.45)"
        scrollbar_thumb_hover = f"rgba({accent_rgb[0]}, {accent_rgb[1]}, {accent_rgb[2]}, 0.75)"

        self.setStyleSheet(f"""
            QDialog {{ background-color: {bg}; color: {fg}; }}
            QWidget#previewWrapper {{ background-color: transparent; border: none; }}
            QFrame#controlsContainer {{
                background-color: transparent; border: none;
                border-top-left-radius: 28px; border-top-right-radius: 28px;
            }}
            QWidget#controlsOuter {{ background-color: transparent; }}
            QScrollArea#controlsScroll, QScrollArea#controlsScroll > QWidget {{
                background: transparent; border: none;
            }}
            QWidget#innerGroup {{
                background-color: transparent; border: none; border-radius: 12px;
            }}
            QTextEdit#noteEditor {{
                background-color: {surface}; color: {fg};
                border: 1px solid {border}; border-radius: 12px;
                padding: 14px 16px; font-size: 14px;
                selection-background-color: {accent}; selection-color: {accent_text};
            }}
            QTextEdit#noteEditor:focus {{ border: 1.5px solid {accent}; }}
            QLabel, QCheckBox {{ color: {fg}; font-size: 13px; }}
            #themeToggleButton {{
                background-color: transparent; border: none; border-radius: 14px;
                padding: 4px 6px; font-size: 12px; font-weight: 600; color: {muted};
            }}
            #themeToggleButton:checked {{ color: {accent_text}; }}
            #themeToggleButton:hover:!checked {{ color: {fg}; }}
            QSlider#berrySlider::groove:horizontal {{
                height: 18px;
                border-radius: 9px;
                background-color: {surface};
            }}
            QSlider#berrySlider::sub-page:horizontal {{
                background-color: {accent};
                border-radius: 9px;
            }}
            QSlider#berrySlider::handle:horizontal {{
                background-color: #ffffff;
                width: 12px;
                height: 12px;
                margin: 3px 3px;
                border-radius: 6px;
            }}
            QPushButton {{
                background-color: {surface}; color: {fg}; border: 1px solid {border};
                padding: 6px 12px; border-radius: 14px;
            }}
            QPushButton:hover {{ background-color: {border}; }}
            QPushButton#saveButton {{
                background-color: {accent}; color: {accent_text}; border: none;
                border-radius: 18px; min-height: 36px; max-height: 36px;
                padding: 0px 14px; font-size: 13px; font-weight: bold;
            }}
            QPushButton#saveButton:hover {{ opacity: 0.9; }}
            QPushButton#cancelButton {{
                background-color: {surface}; color: {fg}; border: 1px solid {border};
                border-radius: 18px; min-height: 36px; max-height: 36px;
                padding: 0px 14px; font-size: 13px; font-weight: bold;
            }}
            QPushButton#cancelButton:hover {{ background-color: {border}; }}
            QWidget#bottomContainer {{ background-color: transparent; }}
            QWidget#bottomPillBar {{
                background-color: {panel}; border-radius: 28px; border: 1px solid {border};
            }}
            QSpinBox {{
                background-color: {panel}; color: {fg}; border: 1px solid {border};
                border-radius: 4px; padding: 5px;
            }}
            QScrollArea#controlsScroll QScrollBar:vertical {{
                background: {surface};
                width: 8px;
                margin: 0px;
                border: none;
            }}
            QScrollArea#controlsScroll QScrollBar::handle:vertical {{
                background: {scrollbar_thumb};
                min-height: 24px;
                border-radius: 4px;
            }}
            QScrollArea#controlsScroll QScrollBar::handle:vertical:hover {{
                background: {scrollbar_thumb_hover};
            }}
            QScrollArea#controlsScroll QScrollBar::add-line:vertical,
            QScrollArea#controlsScroll QScrollBar::sub-line:vertical {{
                height: 0px;
                background: none;
                border: none;
            }}
            QScrollArea#controlsScroll QScrollBar::add-page:vertical,
            QScrollArea#controlsScroll QScrollBar::sub-page:vertical {{
                background: none;
            }}
        """)


# ── Bento WebUI settings -----------------------------------------------------
try:
    if getattr(mw, "onigiri_api", {}).get("id") != "1011095603":
        raise ImportError("Onigiri Bento API is not active")
    _bws = importlib.import_module("1011095603.api.widget_settings")
except Exception:
    _bws = None

if _bws is not None:
    class SettingsDialog(_bws.BentoSettingsDialog):
        def __init__(self, parent=None, config=None, config_path=None):
            source = config if isinstance(config, dict) else {}
            path = config_path or os.path.join(os.path.dirname(__file__), "config.json")
            defaults = {
                "note_text": "Welcome to Sticky! Open settings to edit this note.",
                "size": "Small", "font": "Noto", "font_size": "Medium",
                "text_align": "Left", "bg_color": "#fef3c7", "opacity": 1.0,
                "manual_widget_width": 200, "manual_widget_height": 200,
            }

            def save(updated):
                with open(path, "w", encoding="utf-8") as handle:
                    json.dump(updated, handle, ensure_ascii=False, indent=4)
                source.clear(); source.update(updated)
                addon = importlib.import_module(__package__)
                addon.CONFIG.clear(); addon.CONFIG.update(updated)
                addon.cached_html = None
                addon.config_loaded = True
                if getattr(mw, "state", "") == "deckBrowser":
                    mw.deckBrowser.refresh()

            def preview(updated, _variant, theme):
                addon = importlib.import_module(__package__)
                original = dict(addon.CONFIG)
                try:
                    addon.CONFIG.clear(); addon.CONFIG.update(updated)
                    css, body = addon.generate_css(), addon.generate_html()
                finally:
                    addon.CONFIG.clear(); addon.CONFIG.update(original)
                dark = theme == "dark"
                return _bws.preview_document(f'<div id="sticky-wrapper">{body}</div>', css, dark=dark, wallpaper=bento_integration.main_menu_wallpaper(dark))

            pages = [
                _bws.page("note", "Note", [
                    _bws.section("Content", [
                        _bws.field("note_text", "Note text", "textarea", default=defaults["note_text"], rows=6, placeholder="Write your note here…"),
                        _bws.field("text_align", "Alignment", "select", default="Left", options=["Left", "Center", "Right"]),
                    ]),
                ], "Edit the note shown on your Anki menu.", "S"),
                _bws.page("appearance", "Appearance", [
                    _bws.section("Typography", [
                        _bws.field("font", "Font", "select", default="Noto", options=["Noto", "Bentham", "Montserrat", "Nunito", "SpaceMono"]),
                        _bws.field("font_size", "Font size", "select", default="Medium", options=["Small", "Medium", "Large"]),
                    ]),
                    _bws.section("Card", [
                        _bws.field("bg_color", "Background", "color", default="#fef3c7"),
                        _bws.field("opacity", "Opacity", "range", default=100, minimum=10, maximum=100, unit="%", scale=.01),
                    ]),
                ], "Typography and paper color, rendered by Sticky itself.", "◐"),
            ]
            super().__init__(
                parent, title="Sticky", subtitle="Quick notes on your Anki menu", accent="#D7B94A",
                pages=pages, config=source, defaults=defaults, save_callback=save,
                logo_path=os.path.join(os.path.dirname(__file__), "sticky_logo.svg"),
                mini_logo_path=os.path.join(os.path.dirname(__file__), "mini_sticky_logo.svg"),
                preview_callback=preview, bugs_url="https://github.com/thepeacemonk/Sticky",
            )
