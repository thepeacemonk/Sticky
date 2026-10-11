import importlib
import json
import os
import sys
from typing import Callable, Iterable, Optional, Tuple

from aqt import mw
from aqt.qt import (
    QAction,
    QFormLayout,
    QFrame,
    QGroupBox,
    QLabel,
    QMenu,
    QPainter,
    QPixmap,
    Qt,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from aqt.theme import theme_manager

try:
    try:
        from PyQt6.QtSvg import QSvgRenderer
    except ImportError:
        from PyQt5.QtSvg import QSvgRenderer
except ImportError:
    QSvgRenderer = None

ONIGIRI_ADDON_ID = "1011095603"
BENTO_MENU_OBJECT = "bentoWidgetsMenu"
WIDTH_KEY = "manual_widget_width"
HEIGHT_KEY = "manual_widget_height"
ONIGIRI_ICON_SVG = "onigiri.svg"
ONIGIRI_ICON_DIR = "assets"
STICKY_ACCENT = "#FFE699"


def _theme_tokens() -> dict:
    is_dark = theme_manager.night_mode
    if is_dark:
        return {"fg": "#f4f4f5", "muted": "#c4c4c4", "border": "#454545", "accent": STICKY_ACCENT}
    return {"fg": "#202124", "muted": "#6f7177", "border": "#dcdde1", "accent": STICKY_ACCENT}


_icon_cache = {}


def _onigiri_icon_pixmap(size: int) -> Optional[QPixmap]:
    if QSvgRenderer is None:
        return None
    dpr = mw.devicePixelRatioF() if hasattr(mw, "devicePixelRatioF") else 1.0
    cache_key = (size, dpr)
    if cache_key in _icon_cache:
        return _icon_cache[cache_key]

    svg_path = os.path.join(os.path.dirname(__file__), ONIGIRI_ICON_DIR, ONIGIRI_ICON_SVG)
    if not os.path.exists(svg_path):
        return None

    renderer = QSvgRenderer(svg_path)
    if not renderer.isValid():
        return None

    pixel_size = max(1, int(size * dpr))
    pixmap = QPixmap(pixel_size, pixel_size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(dpr)

    _icon_cache[cache_key] = pixmap
    return pixmap


def _addon_id() -> str:
    return os.path.basename(os.path.dirname(os.path.abspath(__file__)))


def _manifest_version(addon_id: str) -> str:
    manifest_path = os.path.join(mw.addonManager.addonsFolder(), addon_id, "manifest.json")
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            return str(json.load(f).get("version") or "")
    except Exception:
        return ""


def get_onigiri_info() -> Optional[dict]:
    api = getattr(mw, "onigiri_api", None)
    if isinstance(api, dict) and api.get("id") == ONIGIRI_ADDON_ID:
        return api

    for module_name, module in list(sys.modules.items()):
        if module_name == ONIGIRI_ADDON_ID or module_name.startswith(f"{ONIGIRI_ADDON_ID}."):
            module_api = getattr(module, "ONIGIRI_API", None)
            if isinstance(module_api, dict):
                return module_api
            return {
                "id": ONIGIRI_ADDON_ID,
                "version": _manifest_version(ONIGIRI_ADDON_ID),
                "status": "module-loaded",
            }

    try:
        addon_name = mw.addonManager.addonName(ONIGIRI_ADDON_ID)
    except Exception:
        addon_name = ""
    if addon_name:
        return {
            "id": ONIGIRI_ADDON_ID,
            "version": _manifest_version(ONIGIRI_ADDON_ID),
            "status": "installed",
        }
    return None


def is_onigiri_detected() -> bool:
    return get_onigiri_info() is not None


def detection_label() -> str:
    info = get_onigiri_info()
    if not info:
        return "⚠️ Onigiri not found"
    version = info.get("version") or "unknown version"
    return (
        f"<div style='text-align: center;'>"
        f"<b>Onigiri Integration Active</b><br>"
        f"<span style='font-size: 11px; opacity: 0.7;'>(v{version})</span>"
        f"</div>"
    )


def _find_bento_menu() -> Optional[QMenu]:
    for action in mw.form.menubar.actions():
        menu = action.menu()
        if menu and menu.objectName() == BENTO_MENU_OBJECT:
            return menu
    return None


def get_bento_menu() -> QMenu:
    menu = _find_bento_menu()
    if menu:
        _ensure_onigiri_shortcut(menu)
        return menu

    menu = QMenu("Bento Widgets", mw)
    menu.setObjectName(BENTO_MENU_OBJECT)
    mw.form.menubar.addMenu(menu)
    _ensure_onigiri_shortcut(menu)
    return menu


def _has_action(menu: QMenu, marker: str) -> bool:
    return any(action.property("bento_marker") == marker for action in menu.actions())


def _open_onigiri_settings() -> None:
    api = getattr(mw, "onigiri_api", None)
    opener = api.get("open_settings") if isinstance(api, dict) else None
    if callable(opener):
        opener()
        return
    for module_name in (f"{ONIGIRI_ADDON_ID}.settings", f"{ONIGIRI_ADDON_ID}.menu_buttons"):
        try:
            importlib.import_module(module_name).open_settings(0)
            return
        except Exception:
            continue


def _ensure_onigiri_shortcut(menu: QMenu) -> None:
    if not is_onigiri_detected() or _has_action(menu, "onigiri-settings"):
        return
    if menu.actions():
        menu.addSeparator()
    action = QAction("Onigiri Settings", mw)
    action.setProperty("bento_marker", "onigiri-settings")
    action.triggered.connect(_open_onigiri_settings)
    menu.addAction(action)


def add_menu_action(label: str, callback: Callable, marker: Optional[str] = None) -> QAction:
    menu = get_bento_menu()
    marker = marker or f"{_addon_id()}:{label}"
    for action in menu.actions():
        if action.property("bento_marker") == marker:
            return action
    action = QAction(label, mw)
    action.setProperty("bento_marker", marker)
    action.triggered.connect(callback)
    menu.addAction(action)
    _ensure_onigiri_shortcut(menu)
    return action


def add_submenu(title: str, actions: Iterable[Tuple[str, Callable]]) -> QMenu:
    menu = get_bento_menu()
    marker = f"{_addon_id()}:submenu:{title}"
    for action in menu.actions():
        submenu = action.menu()
        if submenu and submenu.property("bento_marker") == marker:
            submenu.clear()
            break
    else:
        submenu = QMenu(title, mw)
        submenu.setProperty("bento_marker", marker)
        menu.addMenu(submenu)

    for label, callback in actions:
        action = QAction(label, mw)
        action.triggered.connect(callback)
        submenu.addAction(action)

    _ensure_onigiri_shortcut(menu)
    return submenu


def register_widget(
    name: str,
    settings_callback: Optional[Callable] = None,
    open_callback: Optional[Callable] = None,
    kind: str = "widget",
) -> dict:
    if not hasattr(mw, "bento_widgets") or not isinstance(mw.bento_widgets, dict):
        mw.bento_widgets = {}
    data = {
        "id": _addon_id(),
        "name": name,
        "kind": kind,
        "settings_callback": settings_callback,
        "open_callback": open_callback,
        "onigiri_detected": is_onigiri_detected(),
    }
    mw.bento_widgets[_addon_id()] = data
    return data


def manual_size(config: Optional[dict], default_width: int = 200, default_height: int = 200) -> Tuple[int, int]:
    config = config or {}
    return (
        int(config.get(WIDTH_KEY, default_width) or default_width),
        int(config.get(HEIGHT_KEY, default_height) or default_height),
    )


def onigiri_widget_radius(default: int = 20) -> int:
    info = get_onigiri_info()
    getter = info.get("get_widget_radius") if isinstance(info, dict) else None
    if callable(getter):
        try:
            return max(0, min(60, int(getter(default))))
        except Exception:
            pass

    if info:
        try:
            value = mw.col.conf.get("onigiri_canvas_inset_border_radius", default)
            return max(0, min(60, int(value if value not in (None, "") else default)))
        except Exception:
            pass
    return default


def main_menu_wallpaper(is_dark: bool) -> Optional[dict]:
    """Reads Onigiri's current deck-browser wallpaper for use as a preview backdrop.

    Returns {"kind": "color", "color": hex} or
    {"kind": "image", "url": str, "color": hex, "blur_px": float, "opacity": float},
    or None if Onigiri isn't installed or its config can't be read.
    """
    if not is_onigiri_detected():
        return None
    try:
        conf = mw.col.conf
    except Exception:
        return None

    light_color = conf.get("modern_menu_bg_color_light", "#F5F5F5")
    dark_color = conf.get("modern_menu_bg_color_dark", "#2C2C2C")
    color = dark_color if is_dark else light_color
    mode = conf.get("modern_menu_background_mode", "color")

    filename = ""
    if mode == "slideshow":
        images = conf.get("modern_menu_slideshow_images", []) or []
        filename = images[0] if images else ""
    elif mode in ("image", "image_color"):
        if conf.get("modern_menu_background_image_mode", "single") == "separate":
            key = "modern_menu_background_image_dark" if is_dark else "modern_menu_background_image_light"
            filename = conf.get(key, "")
        else:
            filename = conf.get("modern_menu_background_image", "")

    if not filename:
        return {"kind": "color", "color": color}

    return {
        "kind": "image",
        "url": f"/_addons/{ONIGIRI_ADDON_ID}/user_files/main_bg/{filename}",
        "color": color,
        "blur_px": conf.get("modern_menu_background_blur", 0) * 0.2,
        "opacity": conf.get("modern_menu_background_opacity", 100) / 100.0,
    }


def sizing_css(
    wrapper_selector: str,
    widget_selector: str,
    config: Optional[dict],
    default_width: int = 200,
    default_height: int = 200,
) -> str:
    width, height = manual_size(config, default_width, default_height)
    radius = onigiri_widget_radius()
    radius_value = f"var(--onigiri-box-effect-radius, {radius}px)"
    base_radius_css = f"border-radius: {radius_value};" if is_onigiri_detected() else ""
    widget_base = ""
    external_widget = ""
    if widget_selector != wrapper_selector:
        widget_base = f"""
        {widget_selector} {{
            width: 100%;
            height: 100%;
            max-width: 100%;
            max-height: 100%;
            box-sizing: border-box;
            {base_radius_css}
        }}
        """
        external_widget = f"""
        .external-widget-container {widget_selector} {{
            width: 100% !important;
            height: 100% !important;
            max-width: none !important;
            max-height: none !important;
            min-width: 0 !important;
            min-height: 0 !important;
            margin: 0 !important;
            flex: 1 1 auto !important;
            border-radius: inherit !important;
        }}
        """
    return f"""
        {wrapper_selector} {{
            width: {width}px;
            height: {height}px;
            max-width: 100%;
            box-sizing: border-box;
            {base_radius_css}
        }}
        {widget_base}
        .external-widget-container {wrapper_selector} {{
            width: 100% !important;
            height: 100% !important;
            min-width: 0 !important;
            min-height: 0 !important;
            margin: 0 !important;
            display: flex !important;
            border-radius: {radius_value} !important;
            overflow: hidden !important;
        }}
        {external_widget}
    """


def create_settings_group(
    config: Optional[dict],
    default_width: int = 200,
    default_height: int = 200,
) -> Tuple[QGroupBox, QSpinBox, QSpinBox]:
    tokens = _theme_tokens()

    group = QGroupBox("Onigiri Integration")
    group.setStyleSheet(
        "QGroupBox {"
        f"  color: {tokens['fg']};"
        "  font-weight: 600;"
        f"  border: 1px solid {tokens['border']};"
        "  border-radius: 10px;"
        "  margin-top: 10px;"
        "  padding-top: 6px;"
        "}"
        "QGroupBox::title {"
        "  subcontrol-origin: margin;"
        "  left: 10px;"
        "  padding: 0 4px;"
        "}"
    )
    try:
        group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    except AttributeError:
        group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    outer = QVBoxLayout(group)

    detected = is_onigiri_detected()
    status = QFrame()
    status.setObjectName("OnigiriDetectionStatus")
    status_layout = QVBoxLayout(status)
    status_layout.setSpacing(2)
    status_layout.setContentsMargins(12, 10, 12, 10)

    icon_label = QLabel()
    icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    if detected:
        icon_pixmap = _onigiri_icon_pixmap(28)
        if icon_pixmap is not None:
            icon_label.setPixmap(icon_pixmap)
        else:
            icon_label.setText("🍙")
    else:
        icon_label.setText("⚠️")
    status_layout.addWidget(icon_label)

    text_label = QLabel(detection_label())
    text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    status_layout.addWidget(text_label)

    if detected:
        accent = tokens["accent"]
        r, g, b = int(accent[1:3], 16), int(accent[3:5], 16), int(accent[5:7], 16)
        status.setStyleSheet(
            "QFrame#OnigiriDetectionStatus {"
            f"  border: 1px solid {accent};"
            "  border-radius: 10px;"
            f"  background-color: rgba({r}, {g}, {b}, 0.16);"
            "}"
            "QFrame#OnigiriDetectionStatus QLabel {"
            f"  color: {tokens['fg']};"
            "  background: transparent;"
            "  border: none;"
            "}"
        )
    else:
        status.setStyleSheet(
            "QFrame#OnigiriDetectionStatus {"
            f"  border: 1px dashed {tokens['border']};"
            "  border-radius: 10px;"
            "  background: transparent;"
            "}"
            "QFrame#OnigiriDetectionStatus QLabel {"
            f"  color: {tokens['muted']};"
            "  background: transparent;"
            "  border: none;"
            "  font-style: italic;"
            "}"
        )
    outer.addWidget(status)

    manual_container = QWidget()
    manual_layout = QFormLayout(manual_container)
    manual_layout.setContentsMargins(0, 0, 0, 0)

    width_spin = QSpinBox()
    width_spin.setRange(120, 1200)
    width_spin.setSuffix(" px")
    height_spin = QSpinBox()
    height_spin.setRange(120, 1200)
    height_spin.setSuffix(" px")
    width, height = manual_size(config, default_width, default_height)
    width_spin.setValue(width)
    height_spin.setValue(height)

    manual_layout.addRow("Standalone width:", width_spin)
    manual_layout.addRow("Standalone height:", height_spin)
    outer.addWidget(manual_container)

    if is_onigiri_detected():
        manual_container.hide()
        status.setToolTip("Widget size is controlled by Onigiri's Widget Grid.")
    else:
        status.setToolTip("Set a manual size for the native Anki deck browser.")

    return group, width_spin, height_spin


def save_settings_group(config: dict, width_spin: QSpinBox, height_spin: QSpinBox) -> None:
    config[WIDTH_KEY] = int(width_spin.value())
    config[HEIGHT_KEY] = int(height_spin.value())
