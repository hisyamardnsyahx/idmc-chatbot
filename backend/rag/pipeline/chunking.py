"""Render staging chart rows as self-contained embedding-ready chunks.

Each chart becomes one or more documents split by a character budget
(rows vary a lot in width). Every chunk repeats a small header —
dashboard, chart, columns, row range — so a chunk retrieved on its own
still says what the numbers mean. Rows are rendered as
``col: value | col: value`` lines, which embed and read better than raw JSON.
"""

from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timezone
from typing import Any

from ..core import config as config_mod
from ..core.json_io import md5_hex
from ..core.models import Document

log = logging.getLogger("rag.pipeline.chunk")


def format_value(col: str, value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if not math.isfinite(value):
            return "N/A"
        if value.is_integer():
            return str(int(value))
        return f"{value:.4f}".rstrip("0").rstrip(".")
    if col == "__timestamp" and isinstance(value, int) and abs(value) > 10**11:
        dt = datetime.fromtimestamp(value / 1000, tz=timezone.utc)
        if (dt.hour, dt.minute, dt.second) == (0, 0, 0):
            return dt.strftime("%Y-%m-%d")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    if value is None:
        return ""
    return str(value)


def format_row(row: Any, colnames: list[str]) -> str:
    if isinstance(row, (list, tuple)):
        row = dict(zip(colnames, row))
    if not isinstance(row, dict):
        return ""
    cols = colnames or list(row.keys())
    parts = []
    for col in cols:
        v = row.get(col)
        if v is None or v == "":
            continue
        text = format_value(col, v)
        if text == "":
            continue
        parts.append(f"{col}: {text}")
    return ("- " + " | ".join(parts)) if parts else ""


def chunk_chart(chart: dict[str, Any], max_chars: int | None = None) -> list[Document]:
    max_chars = max_chars or config_mod.settings.max_chunk_chars
    rows = chart.get("rows") or []
    colnames = chart.get("colnames") or (
        list(rows[0].keys()) if rows and isinstance(rows[0], dict) else []
    )
    dashboard = chart.get("dashboard_name") or "Unknown dashboard"
    chart_name = chart.get("slice_name") or f"Chart {chart.get('slice_id')}"
    slice_id = chart.get("slice_id")

    lines = [(i, format_row(r, colnames)) for i, r in enumerate(rows, start=1)]
    lines = [(i, t) for i, t in lines if t]
    if not lines or slice_id is None:
        return []

    header_base = [
        f"Dashboard: {dashboard}",
        f"Chart: {chart_name}",
        f"Columns: {', '.join(colnames)}",
    ]
    budget = max(200, max_chars - sum(len(h) + 1 for h in header_base) - 40)

    groups: list[list[Any]] = []
    current: list[Any] = []
    size = 0
    for item in lines:
        line_len = len(item[1]) + 1
        if current and size + line_len > budget:
            groups.append(current)
            current, size = [], 0
        current.append(item)
        size += line_len
    if current:
        groups.append(current)

    total_rows = len(rows)
    docs: list[Document] = []
    for idx, group in enumerate(groups):
        first, last = group[0][0], group[-1][0]
        header = list(header_base)
        if len(groups) > 1:
            header.append(f"Rows {first}-{last} of {total_rows}")
        content = "\n".join(header + [""] + [text for _, text in group])
        docs.append(
            Document(
                id=f"slice{slice_id}-chunk{idx}",
                page_content=content,
                metadata={
                    "dashboard_name": dashboard,
                    "dashboard_uuid": chart.get("dashboard_uuid") or "",
                    "slice_id": int(slice_id),
                    "slice_name": chart_name,
                    "chunk_index": idx,
                    "chunk_count": len(groups),
                    "row_start": first,
                    "row_end": last,
                    "total_rows": total_rows,
                    "columns": ", ".join(colnames),
                    "content_hash": md5_hex(content),
                    "extracted_at": chart.get("fetched_at") or "",
                    "stale": bool(chart.get("stale", False)),
                },
            )
        )
    return docs


def chunk_charts(charts: dict[Any, dict[str, Any]]) -> list[Document]:
    docs: list[Document] = []
    for key in sorted(charts, key=lambda k: int(k)):
        chart_docs = chunk_chart(charts[key])
        if not chart_docs:
            log.warning("slice %s produced no chunks (no usable rows)", key)
        docs.extend(chart_docs)
    return docs
