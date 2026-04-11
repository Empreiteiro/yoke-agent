"""Persistent CLI configuration stored at ``~/.yoke/config.json``.

Holds the user's preferred backend URL, API key, and the path to a
local Yoke checkout (when ``yoke install`` / ``yoke serve`` are used to
manage a self-hosted stack via docker compose).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

CONFIG_DIR = Path(os.environ.get("YOKE_HOME", str(Path.home() / ".yoke")))
CONFIG_PATH = CONFIG_DIR / "config.json"


def _ensure_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load() -> dict:
    """Load config from disk. Returns ``{}`` if it doesn't exist."""
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def save(data: dict) -> None:
    _ensure_dir()
    CONFIG_PATH.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    # Best-effort: keep the file readable only by the user since it
    # may contain an API key.
    try:
        os.chmod(CONFIG_PATH, 0o600)
    except OSError:
        pass


def get(key: str, default=None):
    return load().get(key, default)


def set_value(key: str, value) -> None:
    data = load()
    data[key] = value
    save(data)


def resolve_base_url(override: Optional[str] = None) -> str:
    """Resolve the backend base URL from CLI flag, env, or config file."""
    if override:
        return override
    return (
        os.environ.get("YOKE_BASE_URL")
        or os.environ.get("RAG_BASE_URL")
        or get("base_url")
        or "http://localhost:4040/api"
    )


def resolve_api_key(override: Optional[str] = None) -> str:
    if override is not None:
        return override
    return (
        os.environ.get("YOKE_API_KEY")
        or os.environ.get("RAG_API_KEY")
        or get("api_key")
        or ""
    )


def resolve_repo_path() -> Optional[Path]:
    """Path to a local Yoke checkout (set by ``yoke install``).

    Used by ``yoke serve`` to know where to invoke ``docker compose``.
    """
    p = get("repo_path")
    return Path(p) if p else None
