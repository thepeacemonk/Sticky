# -*- coding: utf-8 -*-
# Sticky Anki Add-on
#
# Author: Gemini
# License: GNU AGPLv3

import os
import base64
import html
import json

from aqt import mw, gui_hooks
from aqt.qt import *
import aqt.deckbrowser


from .settings import SettingsDialog, get_contrasting_font_color
from . import bento_integration

# --- Globals ---
ADDON_NAME = "Sticky"
ADDON_FOLDER = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(ADDON_FOLDER, "config.json")
CONFIG = {} # Start with an empty dict, will be populated by load_config
cached_html = None
config_loaded = False
DEFAULT_CONFIG = {
    "note_text": "Welcome to Sticky! Open settings to edit this note.",
    "size": "Small",
    "font": "Noto",
    "font_size": "Medium",
    "text_align": "Left",
    "bg_color": "#fef3c7",
    "opacity": 1.0,
    "manual_widget_width": 200,
    "manual_widget_height": 200
}

# --- Config Management ---
def load_config():
    """
    Loads configuration from config.json, creating it with defaults if it
    doesn't exist. This is the single source of truth for the add-on's config.
    """
    global CONFIG, cached_html, config_loaded
    
    final_config = DEFAULT_CONFIG.copy()

    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                user_config = json.load(f)
                final_config.update(user_config)
        
        # Write back to file to create it or add new default keys.
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(final_config, f, indent=4)

    except (IOError, json.JSONDecodeError):
        # Fallback to defaults if file is corrupted or not readable
        final_config = DEFAULT_CONFIG.copy()
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(final_config, f, indent=4)
        except IOError:
            pass # In-memory config will be used if write fails

    CONFIG.clear()
    CONFIG.update(final_config)
    cached_html = None
    config_loaded = True


def ensure_config_loaded():
    """Load config before rendering if Anki/Onigiri asks for HTML early."""
    if not config_loaded:
        load_config()


def reset_cache(reload: bool = True):
    """
    Clears the cached HTML and optionally reloads the configuration from disk
    to ensure changes are applied everywhere.
    """
    global cached_html
    cached_html = None
    if reload:
        load_config() # Reload the configuration from the saved file
    
    if mw.state == "deckBrowser":
        mw.deckBrowser.refresh()

# --- Helper Functions ---

def get_font_face_rules(selected_font=None):
    """Generates @font-face rules for the fonts in the /fonts folder."""
    fonts_dir = os.path.join(ADDON_FOLDER, "fonts")
    if not os.path.isdir(fonts_dir):
        return ""
    
    known_fonts = ["Noto", "Bentham", "Montserrat", "Nunito", "SpaceMono"]
    rules = ""
    
    for filename in os.listdir(fonts_dir):
        if filename.lower().endswith(".ttf"):
            basename = os.path.splitext(filename)[0]
            font_family_name = next((name for name in known_fonts if basename.lower().startswith(name.lower())), None)

            if font_family_name:
                if selected_font and font_family_name.lower() != selected_font.lower():
                    continue
                font_path = os.path.join(fonts_dir, filename)
                try:
                    with open(font_path, "rb") as f:
                        encoded_font = base64.b64encode(f.read()).decode('utf-8')
                    rules += f"""
                        @font-face {{
                            font-family: '{font_family_name}';
                            src: url(data:font/truetype;charset=utf-8;base64,{encoded_font});
                        }}
                    """
                except Exception:
                    pass
    return rules

def hex_to_rgba(hex_code, alpha):
    """Converts a hex color code to an rgba string."""
    hex_code = hex_code.lstrip('#')
    try:
        r, g, b = tuple(int(hex_code[i:i+2], 16) for i in (0, 2, 4))
        return f"rgba({r}, {g}, {b}, {alpha})"
    except ValueError:
        return f"rgba(0, 0, 0, {alpha})"


# --- HTML & CSS Generation ---

def generate_css():
    """Generates the complete CSS for the sticky note widget based on config."""
    ensure_config_loaded()
    conf = CONFIG
    size_str = conf.get("size", "Small")
    size_map = {"Small": 200, "Medium": 300, "Big": 410}
    size_px = size_map.get(size_str, 200)

    bg_color = conf.get("bg_color", "#fef3c7")
    opacity = conf.get("opacity", 1.0)
    font = conf.get("font", "Noto")
    font_size_str = conf.get("font_size", "Medium")
    text_align_str = conf.get("text_align", "Left")

    font_size_map = {"Small": "12px", "Medium": "14px", "Large": "16px"}
    font_size = font_size_map.get(font_size_str, "14px")
    
    font_color = get_contrasting_font_color(bg_color)
    bg_rgba = hex_to_rgba(bg_color, opacity)
    
    font_family_str = f"'{font}', system-ui, sans-serif"

    return f"""
        {get_font_face_rules(font)}
        #sticky-wrapper {{
            width: 100%;
            height: 100%;
            min-width: 0;
            min-height: 0;
            display: flex;
            box-sizing: border-box;
        }}
        #sticky-container {{
            width: {size_px}px;
            height: {size_px}px;
            margin: 20px auto;
            position: relative;
        }}
        #sticky-note-display {{
            width: 100%;
            height: 100%;
            padding: 16px;
            border-radius: 20px;
            border: 1px solid rgba(0,0,0,0.1);
            font-size: {font_size};
            text-align: {text_align_str.lower()};
            line-height: 1.5;
            box-sizing: border-box; /* Important for padding */
            background-color: {bg_rgba};
            color: {font_color};
            font-family: {font_family_str};
            white-space: pre-wrap; /* Render newlines */
            word-wrap: break-word; /* Wrap long words */
            overflow-y: auto; /* Add scrollbar if content overflows */
        }}
        .external-widget-container #sticky-wrapper {{
            width: 100% !important;
            height: 100% !important;
            min-width: 0 !important;
            min-height: 0 !important;
            display: flex !important;
            flex: 1 1 auto !important;
        }}
        .external-widget-container #sticky-container {{
            flex: 1 1 auto !important;
        }}
        .external-widget-container #sticky-note-display {{
            min-width: 0 !important;
            min-height: 0 !important;
        }}
        {bento_integration.sizing_css("#sticky-container", "#sticky-note-display", conf, size_px, size_px)}
    """

def generate_html():
    """Generates the HTML for the sticky note display."""
    ensure_config_loaded()
    note_text = CONFIG.get("note_text", "")
    display_html = html.escape(note_text)
    
    return f"""
        <div id="sticky-container">
            <div id="sticky-note-display">{display_html}</div>
        </div>
    """

# --- Anki Integration ---

def add_sticky_to_deck_browser(deck_browser: aqt.deckbrowser.DeckBrowser, content: aqt.deckbrowser.DeckBrowserContent):
    """Appends the sticky note widget to the deck browser's stats area."""
    global cached_html
    ensure_config_loaded()

    if "<div id='sticky-wrapper'>" in content.stats:
        return

    if cached_html is None:
        css = generate_css()
        html_content = generate_html()
        cached_html = f"<div id='sticky-wrapper'><style>{css}</style>{html_content}</div>"

    content.stats += cached_html

def on_theme_change():
    """Reset cache and refresh when theme changes."""
    reset_cache()



_is_settings_open = False
def debounce_settings(func):
    def wrapper(*args, **kwargs):
        global _is_settings_open
        if _is_settings_open:
            return
        _is_settings_open = True
        try:
            return func()
        finally:
            _is_settings_open = False
    return wrapper

@debounce_settings
def show_settings():
    """Shows the settings dialog and reloads config upon a successful save."""
    ensure_config_loaded()
    # Pass a copy of the config to prevent the dialog from changing the
    # global state directly. Also pass the path for saving.
    dialog = SettingsDialog(mw, config=CONFIG.copy(), config_path=CONFIG_PATH)
    
    # If the user clicked "Save" (dialog.exec() returns true)...
    if dialog.exec():
        # ...force a reload from the file and refresh the deck browser.
        reset_cache(reload=True)

# --- Hooks and Menu ---
# Load the config once the user profile has been loaded. This is crucial.
gui_hooks.profile_did_open.append(load_config)

# Render the note on the deck browser screen
gui_hooks.deck_browser_will_render_content.append(add_sticky_to_deck_browser)

# Reset cache on certain events to ensure the note is up-to-date
gui_hooks.reviewer_will_end.append(reset_cache)
gui_hooks.sync_did_finish.append(reset_cache)
gui_hooks.theme_did_change.append(on_theme_change)

bento_integration.register_widget("Sticky", settings_callback=show_settings)
bento_integration.add_menu_action("Sticky Settings", show_settings)
