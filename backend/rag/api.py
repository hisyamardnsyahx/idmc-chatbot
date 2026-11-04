"""Compat: ``rag.api`` is now ``rag.web.app``.

Kept so ``uvicorn rag.api:app`` and existing imports keep working.
New code should import from ``rag.web.app``.
"""

from __future__ import annotations

from .web.app import *  # noqa: F401,F403
from .web.app import app  # noqa: F401
