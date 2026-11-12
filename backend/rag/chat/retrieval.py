"""Retrieval entry points used by the chat loop and the search endpoint.

The staging snapshot may be produced by either pipeline version:

- v2 snapshots carry an explicit ``catalog`` list.
- v1 snapshots carry a ``charts`` object.

Both shapes feed the same dashboard allow-list and chart catalogue.
"""

from __future__ import annotations

import base64
import json
from typing import Any
import urllib.parse

from ..core import config as config_mod
from ..core.json_io import read_json
from ..core.models import Passage
from ..pipeline import embeddings, vector_store


def _snapshot() -> dict[str, Any]:
    return read_json(config_mod.settings.staging_snapshot, default={}) or {}


def _legacy_catalog(charts: dict[str, Any]) -> list[dict[str, Any]]:
    def sort_key(key: Any) -> tuple[int, Any]:
        text = str(key)
        return (0, int(text)) if text.isdigit() else (1, text)

    catalog: list[dict[str, Any]] = []
    for key in sorted(charts, key=sort_key):
        chart = charts[key]
        if not isinstance(chart, dict):
            continue
        catalog.append(
            {
                "slice_id": chart.get("slice_id", key),
                "slice_name": chart.get("slice_name") or f"Chart {key}",
                "dashboard_name": chart.get("dashboard_name") or "Unknown dashboard",
            }
        )
    return catalog


def catalog() -> list[dict[str, Any]]:
    """Return ``[{slice_id, slice_name, dashboard_name}]`` for the active snapshot."""
    snapshot = _snapshot()
    items = snapshot.get("catalog")
    if isinstance(items, list):
        return [
            {
                "slice_id": item.get("slice_id"),
                "slice_name": item.get("slice_name"),
                "dashboard_name": item.get("dashboard_name"),
            }
            for item in items
            if isinstance(item, dict)
        ]
    charts = snapshot.get("charts")
    return _legacy_catalog(charts) if isinstance(charts, dict) else []


def dashboard_names() -> list[str]:
    return sorted(
        {
            str(item["dashboard_name"])
            for item in catalog()
            if item.get("dashboard_name")
        }
    )


def resolve_portal_url(metadata: dict[str, Any]) -> str:
    """Resolve the public, login-free IDMC portal URL for the dashboard.
    
    Internal DWH URLs (dwh.jogjaprov.go.id) require staff authentication,
    so we always map to the public dashboard on idmc.jogjaprov.go.id.
    """
    portal_entries = metadata.get("portal_entries")
    if isinstance(portal_entries, str):
        try:
            portal_entries = json.loads(portal_entries)
        except Exception:
            portal_entries = []

    if portal_entries and isinstance(portal_entries, list) and isinstance(portal_entries[0], dict):
        entry = portal_entries[0]
        portal_path = entry.get("portal_path") or []
        source = entry.get("source") or ""

        # Beranda is the root of the portal (Dashboard Pembangunan)
        if portal_path == ["Beranda"] or entry.get("portal_page_id") == "home":
            return "https://idmc.jogjaprov.go.id/"

        if portal_path and source:
            slugs = [
                p.strip().lower()
                .replace("&", "-")
                .replace("  ", " ")
                .replace(" ", "-")
                .replace("(", "")
                .replace(")", "")
                .replace("/", "-")
                for p in portal_path
            ]
            slugs = ["-".join(filter(None, s.split("-"))) for s in slugs]
            encoded_source = base64.b64encode(urllib.parse.quote(source, safe="").encode("utf-8")).decode("utf-8")
            return f"https://idmc.jogjaprov.go.id/{'/'.join(slugs)}/{encoded_source}"

    d_name = (metadata.get("dashboard_name") or "").lower()
    if "pembangunan" in d_name or "beranda" in d_name:
        return "https://idmc.jogjaprov.go.id/"

    raw_url = metadata.get("source_url") or ""
    if raw_url.startswith("https://idmc.jogjaprov.go.id/"):
        return raw_url

    return "https://idmc.jogjaprov.go.id/"


def _to_passage(hit: dict[str, Any]) -> Passage:
    metadata = hit.get("metadata") or {}
    source_url = resolve_portal_url(metadata)

    return Passage(
        dashboard=metadata.get("dashboard_name") or "Unknown dashboard",
        chart=metadata.get("slice_name") or metadata.get("chart_name") or "Unknown chart",
        slice_id=metadata.get("slice_id"),
        rows_covered=(
            f"{metadata.get('row_start')}-{metadata.get('row_end')} "
            f"of {metadata.get('total_rows')}"
        ),
        data_as_of=(
            metadata.get("extracted_at")
            or metadata.get("last_successful_fetch_at")
            or ""
        ),
        possibly_outdated=bool(metadata.get("stale")),
        relevance=round(float(hit.get("score", 0.0)), 3),
        content=hit.get("content") or "",
        source_url=source_url,
    )


def search(query: str, top_k: int = 5, dashboard_name: str | None = None) -> list[Passage]:
    query = (query or "").strip()
    if not query:
        raise ValueError("'query' is required.")
    top_k = max(1, min(config_mod.settings.max_top_k, int(top_k or config_mod.settings.default_top_k)))
    vector = embeddings.embed_query(query)
    return [
        _to_passage(hit)
        for hit in vector_store.query(vector, top_k=top_k, dashboard_name=dashboard_name)
    ]


def list_charts() -> list[dict[str, Any]]:
    return catalog()
