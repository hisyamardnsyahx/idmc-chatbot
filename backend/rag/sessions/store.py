"""File-based chat sessions (no database needed)."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..core.config import Settings, settings
from ..core.json_io import atomic_write_json, read_json

SESSION_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _path(cfg: Settings, session_id: str) -> Path:
    if not isinstance(session_id, str) or not SESSION_ID_RE.match(session_id):
        raise ValueError(f"Invalid session id: {session_id!r}")
    target = (cfg.sessions_dir / f"{session_id}.json").resolve()
    base = cfg.sessions_dir.resolve()
    if not target.is_relative_to(base):
        raise ValueError(f"Session path escape attempt: {session_id!r}")
    return target


def create_session(title: str = "New chat", cfg: Settings | None = None) -> dict[str, Any]:
    cfg = cfg or settings
    session_id = uuid.uuid4().hex[:12]
    session = {
        "id": session_id,
        "title": title,
        "created_at": _now(),
        "updated_at": _now(),
        "turns": [],
    }
    atomic_write_json(_path(cfg, session_id), session)
    return session


def get_session(session_id: str, cfg: Settings | None = None) -> dict[str, Any] | None:
    cfg = cfg or settings
    try:
        p = _path(cfg, session_id)
    except (ValueError, TypeError):
        return None
    data = read_json(p)
    return data if isinstance(data, dict) else None


def list_sessions(cfg: Settings | None = None) -> list[dict[str, Any]]:
    cfg = cfg or settings
    cfg.sessions_dir.mkdir(parents=True, exist_ok=True)
    out = []
    for f in cfg.sessions_dir.glob("*.json"):
        data = read_json(f)
        if isinstance(data, dict):
            out.append(
                {
                    "id": data.get("id", f.stem),
                    "title": data.get("title", "Chat"),
                    "updated_at": data.get("updated_at", ""),
                    "turn_count": len(data.get("turns") or []),
                }
            )
    out.sort(key=lambda s: s["updated_at"], reverse=True)
    return out


def append_turn(
    session_id: str,
    role: str,
    text: str,
    sources: list[dict[str, Any]] | None = None,
    cfg: Settings | None = None,
) -> dict[str, Any]:
    cfg = cfg or settings
    session = get_session(session_id, cfg)
    if session is None:
        raise ValueError(f"session {session_id} not found")
    session.setdefault("turns", []).append(
        {"role": role, "text": text, "sources": sources or [], "at": _now()}
    )
    if role == "user" and len(session["turns"]) == 1 and text.strip():
        session["title"] = text.strip()[:60]
    session["updated_at"] = _now()
    atomic_write_json(_path(cfg, session_id), session)
    return session


def delete_session(session_id: str, cfg: Settings | None = None) -> bool:
    cfg = cfg or settings
    try:
        p = _path(cfg, session_id)
    except (ValueError, TypeError):
        return False
    if p.exists():
        p.unlink()
        return True
    return False


def history_for_model(
    session: dict[str, Any], cfg: Settings | None = None, limit: int | None = None
) -> list[dict[str, str]]:
    cfg = cfg or settings
    limit = limit or cfg.history_turns
    turns = (session.get("turns") or [])[-limit * 2 :]
    return [{"role": t["role"], "text": t["text"]} for t in turns if t.get("text")]
