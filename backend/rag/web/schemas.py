"""Pydantic request/response models for the web API."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    dashboard_name: Optional[str] = None
    top_k: int = 5


class Source(BaseModel):
    dashboard: Optional[str] = None
    chart: Optional[str] = None
    slice_id: Optional[str | int] = None
    rows_covered: Optional[str] = None
    data_as_of: Optional[str] = None
    possibly_outdated: bool = False
    relevance: float = 0.0
    content: str = ""
    source_url: Optional[str] = None


class SearchResponse(BaseModel):
    results: list[Source]


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = Field(None, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    dashboard_name: Optional[str] = None
    top_k: int = 5


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    reply_format: str = "markdown"
    sources: list[Source] = Field(default_factory=list)


class Turn(BaseModel):
    role: str
    text: str
    sources: list[Source] = Field(default_factory=list)
    at: str = ""


class SessionDetail(BaseModel):
    id: str
    title: str
    created_at: str = ""
    updated_at: str = ""
    turns: list[Turn] = Field(default_factory=list)


class SessionRenameRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)


class StatsResponse(BaseModel):
    collection: str
    count: int
    embed_model: str
    chat_provider: str
    chat_model: str
    indexed_at: Optional[str] = None
    last_summary: dict[str, Any] = Field(default_factory=dict)
    charts: int = 0
    sessions: int = 0
