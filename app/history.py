"""Recent reading history."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.config import config_dir

MAX_ITEMS = 20


def history_path():
    return config_dir() / "history.json"


def load_history() -> list[dict[str, Any]]:
    path = history_path()
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict) and item.get("text")]
    except (OSError, json.JSONDecodeError):
        pass
    return []


def add_history(text: str, source: str = "ocr") -> list[dict[str, Any]]:
    text = (text or "").strip()
    if not text:
        return load_history()
    items = load_history()
    preview = text.replace("\n", " ")
    if len(preview) > 60:
        preview = preview[:57] + "..."
    entry = {
        "text": text,
        "preview": preview,
        "source": source,
        "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    items = [entry] + [i for i in items if i.get("text") != text]
    items = items[:MAX_ITEMS]
    with history_path().open("w", encoding="utf-8") as fh:
        json.dump(items, fh, indent=2, ensure_ascii=False)
    return items
