"""Atomic JSON file helpers shared by the pipeline and the session store."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


def read_json(path: Path, default: Any = None) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def atomic_write_json(path: Path, obj: Any, indent: int | None = 2) -> None:
    """Write via temp file + rename so a crash never leaves half-written JSON."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=indent, default=str)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def canonical_json(obj: Any) -> str:
    """Deterministic JSON string (sorted keys, no whitespace) — safe to hash."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def md5_hex(text: str) -> str:
    # Change detection, not security. usedforsecurity=False keeps this working
    # on FIPS-enabled systems (Python 3.9+).
    return hashlib.md5(text.encode("utf-8"), usedforsecurity=False).hexdigest()
