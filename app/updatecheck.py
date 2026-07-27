"""Check GitHub Releases for a newer app version."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from app.config import APP_VERSION

GITHUB_REPO = "Z3n1thh/Speech"
RELEASES_URL = f"https://github.com/{GITHUB_REPO}/releases"
API_LATEST = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


class UpdateError(Exception):
    """Raised when update check fails."""


def _parse_version(tag: str) -> tuple[int, ...]:
    raw = (tag or "").strip().lstrip("vV")
    parts: list[int] = []
    for chunk in raw.split("."):
        digits = "".join(ch for ch in chunk if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:4])


def is_newer(remote: str, local: str = APP_VERSION) -> bool:
    return _parse_version(remote) > _parse_version(local)


def check_latest(timeout: float = 8.0) -> dict[str, Any]:
    """Return latest release info from GitHub."""
    req = urllib.request.Request(
        API_LATEST,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"ScreenReadAloud/{APP_VERSION}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise UpdateError(f"GitHub returned HTTP {exc.code}") from exc
    except Exception as exc:  # noqa: BLE001
        raise UpdateError(f"Could not check for updates: {exc}") from exc

    tag = str(data.get("tag_name") or "")
    if not tag:
        raise UpdateError("No release tag found")
    return {
        "tag": tag,
        "name": str(data.get("name") or tag),
        "url": str(data.get("html_url") or RELEASES_URL),
        "newer": is_newer(tag, APP_VERSION),
        "local": APP_VERSION,
    }
