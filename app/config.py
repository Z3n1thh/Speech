"""Load and save user settings as JSON."""

from __future__ import annotations

import json
import locale
from copy import deepcopy
from pathlib import Path
from typing import Any

APP_NAME = "ScreenReadAloud"
APP_VERSION = "5.0.1"


def _default_ocr_lang() -> str:
    try:
        lang, _ = locale.getdefaultlocale()
    except Exception:
        lang = None
    if lang and lang.lower().startswith("sv"):
        return "sv"
    return "en"


DEFAULTS: dict[str, Any] = {
    "hotkey_region": "ctrl+shift+r",
    "hotkey_selection": "ctrl+shift+s",
    "hotkey_stop": "ctrl+shift+x",
    "hotkey_faster": "ctrl+shift+up",
    "hotkey_slower": "ctrl+shift+down",
    "engine": "edge",
    "rate": 160,
    "volume": 1.0,
    "offline_voice": "",
    "edge_voice": "en-US-JennyNeural",
    "voice_filter": "all",  # all | en | sv | de | fr | es | ...
    "favorite_voices": [],  # [{engine, id, label}]
    "profiles": [],  # filled with builtins on first load if empty
    "active_profile": "",
    "auto_speak": True,
    "font_size": 18,
    "ocr_lang": _default_ocr_lang(),
    "autostart": False,
    "simple_mode": False,
    "quiet_mode": False,  # hide to tray after auto-speak starts
    "word_highlight": True,
    "theme": "dark",  # dark | light
    "pdf_max_pages": 40,
    "auto_detect_lang": True,
    "reading_mode": False,
}


def config_dir() -> Path:
    base = Path.home() / "AppData" / "Local" / APP_NAME
    base.mkdir(parents=True, exist_ok=True)
    return base


def config_path() -> Path:
    return config_dir() / "settings.json"


def load_settings() -> dict[str, Any]:
    from app.profiles import normalize_profiles

    path = config_path()
    settings = deepcopy(DEFAULTS)
    if not path.exists():
        settings["profiles"] = normalize_profiles([])
        return settings
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            if "hotkey" in data and "hotkey_region" not in data:
                settings["hotkey_region"] = data["hotkey"]
            for key, value in data.items():
                if key in DEFAULTS:
                    settings[key] = value
            favs = settings.get("favorite_voices", [])
            if not isinstance(favs, list):
                settings["favorite_voices"] = []
            settings["profiles"] = normalize_profiles(settings.get("profiles"))
    except (OSError, json.JSONDecodeError):
        settings["profiles"] = normalize_profiles([])
    return settings


def save_settings(settings: dict[str, Any]) -> None:
    from app.profiles import normalize_profiles

    path = config_path()
    payload = {key: settings.get(key, DEFAULTS[key]) for key in DEFAULTS}
    payload["profiles"] = normalize_profiles(payload.get("profiles"))
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
