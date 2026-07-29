"""Load and save user settings as JSON."""

from __future__ import annotations

import json
import locale
from copy import deepcopy
from pathlib import Path
from typing import Any

APP_NAME = "ScreenReadAloud"
APP_VERSION = "6.2.2"


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
    "hotkey_stop": "ctrl+shift+x",
    "engine": "edge",
    "rate": 160,
    "volume": 1.0,
    "offline_voice": "",
    "edge_voice": "en-US-JennyNeural",
    "voice_filter": "sv" if _default_ocr_lang() == "sv" else "en",
    "ocr_lang": _default_ocr_lang(),
    "theme": "dark",  # dark | light
    "font_size": 18,
}


def config_dir() -> Path:
    base = Path.home() / "AppData" / "Local" / APP_NAME
    base.mkdir(parents=True, exist_ok=True)
    return base


def config_path() -> Path:
    return config_dir() / "settings.json"


def load_settings() -> dict[str, Any]:
    path = config_path()
    settings = deepcopy(DEFAULTS)
    if not path.exists():
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
    except (OSError, json.JSONDecodeError):
        pass
    return settings


def save_settings(settings: dict[str, Any]) -> None:
    path = config_path()
    payload = {key: settings.get(key, DEFAULTS[key]) for key in DEFAULTS}
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
