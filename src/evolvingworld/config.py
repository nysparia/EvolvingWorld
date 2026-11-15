"""Configuration resolution for EvolvingWorld.

Every module that talks to an OpenAI-compatible endpoint needs an ``api_key``
and a ``base_url``.  Historically these were read from a ``config.json`` sitting
next to the scripts, which meant the package could only be imported from the
repository root.  This module centralises the lookup so that the package works
from any working directory.

Resolution order (first source that yields a non-empty value wins):

1. an explicit ``path`` argument,
2. ``$EVOLVINGWORLD_CONFIG``,
3. ``./config.json`` (relative to the current working directory),
4. ``~/.config/evolvingworld/config.json``,
5. ``$EVOLVINGWORLD_API_KEY`` / ``$EVOLVINGWORLD_BASE_URL``.

Missing values fall back to empty strings, so importing the package never fails
just because no credentials have been configured yet.  A clear error is raised
later, at the point where a request is actually made.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

__all__ = [
    "CONFIG_ENV_VAR",
    "API_KEY_ENV_VAR",
    "BASE_URL_ENV_VAR",
    "DEFAULT_CONFIG",
    "config_candidates",
    "load_config",
    "require_credentials",
]

CONFIG_ENV_VAR = "EVOLVINGWORLD_CONFIG"
API_KEY_ENV_VAR = "EVOLVINGWORLD_API_KEY"
BASE_URL_ENV_VAR = "EVOLVINGWORLD_BASE_URL"

DEFAULT_CONFIG: dict[str, str] = {"api_key": "", "base_url": ""}


def config_candidates() -> list[Path]:
    """Return the config file locations that are searched, in order."""
    candidates: list[Path] = []
    env_path = os.environ.get(CONFIG_ENV_VAR)
    if env_path:
        candidates.append(Path(env_path).expanduser())
    candidates.append(Path("config.json"))
    candidates.append(Path.home() / ".config" / "evolvingworld" / "config.json")
    return candidates


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object, got {type(data).__name__}")
    return data


def load_config(path: str | Path | None = None) -> dict[str, str]:
    """Load API credentials.

    Args:
        path: Optional explicit config file.  When given, it must exist.

    Returns:
        A dict with at least ``api_key`` and ``base_url`` keys.  Values are
        strings; missing entries are empty strings.

    Raises:
        FileNotFoundError: if ``path`` was given explicitly but does not exist.
        ValueError: if a config file is not a JSON object.
    """
    merged: dict[str, str] = dict(DEFAULT_CONFIG)

    if path is not None:
        explicit = Path(path).expanduser()
        if not explicit.is_file():
            raise FileNotFoundError(f"Config file not found: {explicit}")
        merged.update({k: v for k, v in _read_json(explicit).items() if v})

    for candidate in config_candidates():
        if not candidate.is_file():
            continue
        try:
            data = _read_json(candidate)
        except (OSError, ValueError):
            continue
        for key, value in data.items():
            if value and not merged.get(key):
                merged[key] = value

    if not merged.get("api_key"):
        merged["api_key"] = os.environ.get(API_KEY_ENV_VAR, "")
    if not merged.get("base_url"):
        merged["base_url"] = os.environ.get(BASE_URL_ENV_VAR, "")

    return merged


def require_credentials(config: Mapping[str, Any]) -> tuple[str, str]:
    """Return ``(api_key, base_url)`` or raise a helpful error.

    Used by entry points that cannot do anything useful without credentials.
    """
    api_key = str(config.get("api_key") or "")
    base_url = str(config.get("base_url") or "")
    if not api_key or not base_url:
        raise RuntimeError(
            "No API credentials configured. Provide them in one of these ways:\n"
            "  1. create ./config.json with {\"api_key\": \"...\", \"base_url\": \"...\"}\n"
            f"  2. set ${CONFIG_ENV_VAR} to the path of such a file\n"
            f"  3. export ${API_KEY_ENV_VAR} and ${BASE_URL_ENV_VAR}\n"
            "  4. write ~/.config/evolvingworld/config.json"
        )
    return api_key, base_url
