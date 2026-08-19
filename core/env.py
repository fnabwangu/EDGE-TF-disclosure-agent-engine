"""
Environment file loading.

Path: core/env.py

Reads `.env` into the process environment so a locally run console or API sees
the same variables `docker compose` injects via `env_file`.

Deliberately not `python-dotenv`: this is thirty lines and avoids a dependency
for one file format, consistent with building the HTTP surface on the Starlette
that was already present.

Real environment variables always win over the file, so an exported key or a
CI secret is never silently overridden by a stale local file.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict

DEFAULT_ENV_PATH = Path(".env")

_loaded_paths: set[str] = set()


def parse_env_file(text: str) -> Dict[str, str]:
    """Parse KEY=VALUE lines, tolerating comments, blanks and `export` prefixes."""
    values: Dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        key, separator, value = line.partition("=")
        if not separator:
            continue
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[key] = value
    return values


def load_env_file(path: Path | str = DEFAULT_ENV_PATH, *, override: bool = False) -> Dict[str, str]:
    """Load `path` into os.environ. Returns the names applied, never the values."""
    path = Path(path)
    if not path.is_file():
        return {}

    applied: Dict[str, str] = {}
    for key, value in parse_env_file(path.read_text(encoding="utf-8")).items():
        if override or key not in os.environ:
            os.environ[key] = value
            applied[key] = "set"
    return applied


def ensure_env_loaded(path: Path | str = DEFAULT_ENV_PATH) -> None:
    """Idempotent: safe to call from every entry point."""
    resolved = str(Path(path).resolve())
    if resolved in _loaded_paths:
        return
    _loaded_paths.add(resolved)
    load_env_file(path)


def reset_for_tests() -> None:
    _loaded_paths.clear()


__all__ = [
    "DEFAULT_ENV_PATH",
    "ensure_env_loaded",
    "load_env_file",
    "parse_env_file",
    "reset_for_tests",
]
