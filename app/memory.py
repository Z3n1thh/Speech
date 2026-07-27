"""Remember reading position so the user can continue later."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.config import config_dir


def memory_path():
    return config_dir() / "reading_memory.json"


def load_memory() -> dict[str, Any] | None:
    path = memory_path()
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict) and data.get("text"):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return None


def save_memory(
    text: str,
    offset: int = 0,
    *,
    source: str = "",
    path: str = "",
) -> dict[str, Any]:
    text = text or ""
    offset = max(0, min(int(offset), len(text)))
    preview = text[offset:].replace("\n", " ").strip()
    if len(preview) > 60:
        preview = preview[:57] + "..."
    entry = {
        "text": text,
        "offset": offset,
        "source": source or "",
        "path": path or "",
        "preview": preview or "(end)",
        "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    with memory_path().open("w", encoding="utf-8") as fh:
        json.dump(entry, fh, indent=2, ensure_ascii=False)
    return entry


def clear_memory() -> None:
    path = memory_path()
    if path.exists():
        try:
            path.unlink()
        except OSError:
            pass


def has_memory() -> bool:
    mem = load_memory()
    return bool(mem and mem.get("text"))
