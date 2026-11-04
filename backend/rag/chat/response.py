"""Post-process the model reply into a tidy, predictable shape.

The chat model is instructed to emit an opening line, a Markdown table or
bullets, and a ``Sumber:`` line — but models drift. This module enforces
the contract defensively:

- normalises whitespace and heading depth,
- guarantees exactly one ``Sumber:`` block built from the retrieved
  passages (never from model-invented names),
- appends a freshness note when every passage is stale or partial,
- leaves plain-text answers (greetings, "no data" replies) untouched.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..core.models import Passage

_SOURCE_HEADING = re.compile(r"^#{1,4}\s*sumber\s*:?\s*$", re.IGNORECASE | re.MULTILINE)
_SOURCE_LINE = re.compile(r"^\s*(sumber|sources)\s*:", re.IGNORECASE | re.MULTILINE)


@dataclass(frozen=True)
class FormattedReply:
    text: str
    truncated_sources_note: bool = False


def _source_line(p: Passage) -> str:
    stale = " — mungkin basi" if p.possibly_outdated else ""
    when = f", data {p.data_as_of}" if p.data_as_of else ""
    return f"- {p.dashboard} — {p.chart} (baris {p.rows_covered}{when}){stale}"


def build_sources_block(passages: list[Passage]) -> str:
    lines = [_source_line(p) for p in passages if p.dashboard and p.chart]
    if not lines:
        return ""
    seen: list[str] = []
    for line in lines:
        if line not in seen:
            seen.append(line)
    return "Sumber:\n" + "\n".join(seen)


def _strip_model_sources(text: str) -> str:
    """Remove any model-written sources section; we rebuild it from passages."""
    match = _SOURCE_LINE.search(text)
    if match:
        return text[: match.start()].rstrip()
    match = _SOURCE_HEADING.search(text)
    if match:
        return text[: match.start()].rstrip()
    return text


def _collapse_whitespace(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def format_reply(raw: str, passages: list[Passage]) -> FormattedReply:
    """Return the user-facing reply text for a model answer."""
    text = _collapse_whitespace(raw or "")
    if not text:
        return FormattedReply(text="Maaf, saya tidak mendapatkan jawaban dari model.")
    if not passages:
        return FormattedReply(text=text)

    body = _strip_model_sources(text)
    block = build_sources_block(passages)
    if block and block not in body:
        body = f"{body.rstrip()}\n\n{block}" if body else block

    notes: list[str] = []
    if passages and all(p.possibly_outdated for p in passages):
        notes.append("_Catatan: seluruh sumber data ini ditandai mungkin basi._")
    elif any(" of " in p.rows_covered for p in passages):
        partial = [p for p in passages if not _covers_all(p)]
        if partial:
            notes.append("_Catatan: data yang ditampilkan bersifat parsial dari tabel sumber._")
    if notes:
        body = f"{body.rstrip()}\n\n" + "\n".join(notes)
    return FormattedReply(text=_collapse_whitespace(body))


def _covers_all(p: Passage) -> bool:
    m = re.match(r"(\d+)-(\d+) of (\d+)", p.rows_covered or "")
    if not m:
        return True
    start, end, total = (int(g) for g in m.groups())
    return start <= 1 and end >= total
