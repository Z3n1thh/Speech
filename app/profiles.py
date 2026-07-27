"""Named voice/reading profiles (e.g. Swedish slow, English fast)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

PROFILE_KEYS = (
    "engine",
    "rate",
    "volume",
    "offline_voice",
    "edge_voice",
    "voice_filter",
    "ocr_lang",
    "word_highlight",
    "font_size",
)

BUILTIN_PROFILES: list[dict[str, Any]] = [
    {
        "name": "Svenska långsam",
        "engine": "edge",
        "rate": 130,
        "volume": 1.0,
        "offline_voice": "",
        "edge_voice": "sv-SE-SofieNeural",
        "voice_filter": "sv",
        "ocr_lang": "sv",
        "word_highlight": True,
        "font_size": 20,
    },
    {
        "name": "Engelska snabb",
        "engine": "edge",
        "rate": 200,
        "volume": 1.0,
        "offline_voice": "",
        "edge_voice": "en-US-JennyNeural",
        "voice_filter": "en",
        "ocr_lang": "en",
        "word_highlight": True,
        "font_size": 18,
    },
]


def normalize_profiles(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return deepcopy(BUILTIN_PROFILES)
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        profile = {key: item.get(key) for key in PROFILE_KEYS}
        profile["name"] = name
        out.append(profile)
    return out or deepcopy(BUILTIN_PROFILES)


def snapshot_from_settings(settings: dict[str, Any], name: str) -> dict[str, Any]:
    name = (name or "").strip() or "Custom"
    profile: dict[str, Any] = {"name": name}
    for key in PROFILE_KEYS:
        profile[key] = settings.get(key)
    return profile


def apply_profile(settings: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    updated = dict(settings)
    for key in PROFILE_KEYS:
        if key in profile and profile[key] is not None:
            updated[key] = profile[key]
    updated["active_profile"] = str(profile.get("name", ""))
    return updated


def upsert_profile(profiles: list[dict[str, Any]], profile: dict[str, Any]) -> list[dict[str, Any]]:
    name = str(profile.get("name", "")).strip()
    if not name:
        return profiles
    items = [p for p in profiles if str(p.get("name", "")).strip() != name]
    items.insert(0, profile)
    return items[:20]


def delete_profile(profiles: list[dict[str, Any]], name: str) -> list[dict[str, Any]]:
    name = (name or "").strip()
    items = [p for p in profiles if str(p.get("name", "")).strip() != name]
    return items or deepcopy(BUILTIN_PROFILES)


def find_profile(profiles: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    name = (name or "").strip()
    for profile in profiles:
        if str(profile.get("name", "")).strip() == name:
            return profile
    return None
