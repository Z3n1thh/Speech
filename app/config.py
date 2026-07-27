"""Load and save user settings as JSON."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

APP_NAME = "ScreenReadAloud"

DEFAULTS: dict[str, Any] = {
    "hotkey": "ctrl+shift+r",
    "engine": "offline",  # "offline" | "edge"
    "rate": 160,  # pyttsx3 words-per-minute style rate
    "volume": 1.0,
    "edge_voice": "en-US-JennyNeural",
    "offline_voice": "",
    "auto_speak": True,
    "font_size": 18,
    "ocr_lang": "en",
    "edge_rate": "+0%",
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
        json.dump(payload, fh, indent=2)
