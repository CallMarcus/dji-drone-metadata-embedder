"""Persistent UI state (recent folders, preferences) under the user config dir."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

_MAX_RECENT = 10


def _config_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config"))
    cfg = base / "dji-embed"
    cfg.mkdir(parents=True, exist_ok=True)
    return cfg


def _state_path() -> Path:
    return _config_dir() / "ui.json"


def load() -> dict[str, Any]:
    path = _state_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def save(state: dict[str, Any]) -> None:
    _state_path().write_text(json.dumps(state, indent=2))


def get_recent_folders() -> list[str]:
    return list(load().get("recent_folders", []))


def add_recent_folder(folder: str) -> list[str]:
    state = load()
    recents = [p for p in state.get("recent_folders", []) if p != folder]
    recents.insert(0, folder)
    state["recent_folders"] = recents[:_MAX_RECENT]
    save(state)
    return state["recent_folders"]
