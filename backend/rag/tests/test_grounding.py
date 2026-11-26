"""Grounding and out-of-domain guard tests for rag.chat.service."""

from __future__ import annotations

from rag.chat import providers as providers_mod
from rag.chat import retrieval as retrieval_mod
from rag.chat import service as chat_service
from rag.core.models import Passage


def _passage(dashboard: str = "Arsitektur SPBE", chart: str = "Table 1") -> Passage:
    return Passage(
        dashboard=dashboard,
        chart=chart,
        slice_id=101,
        rows_covered="1-3 of 10",
        data_as_of="2026-10-06",
        possibly_outdated=False,
        relevance=0.62,
        content="Arsitektur aplikasi SPBE DIY tahun 2024.",
    )


def test_refuse_tool_returns_canonical_reply_without_passages(monkeypatch):
    class FakeBackend:
        kind = "fake"
        model = "fake-model"

        def generate(self, messages, tools=None):
            return providers_mod.BackendTurn(
                tool_calls=[
                    providers_mod.ToolCall(
                        name=chat_service.REFUSE_TOOL,
                        args={"topic": "biografi Joko Widodo"},
                    )
                ]
            )

    monkeypatch.setattr(providers_mod, "build_backends", lambda: [FakeBackend()])
    res = chat_service.run_chat("siapa itu jokowi", [])
    assert res.passages == []
    assert "di luar cakupan data" in res.text
    assert "Joko Widodo adalah Presiden" not in res.text
    assert "biografi Joko Widodo" in res.text


def test_turn1_parametric_answer_without_tool_is_blocked(monkeypatch):
    class LeakyBackend:
        kind = "fake"
        model = "fake-model"
        supports_tool_choice = True

        def __init__(self):
            self.calls = 0

        def generate(self, messages, tools=None, tool_choice_mode=None):
            self.calls += 1
            return providers_mod.BackendTurn(
                text="Joko Widodo adalah Presiden Republik Indonesia."
            )

    backend = LeakyBackend()
    monkeypatch.setattr(providers_mod, "build_backends", lambda: [backend])
    res = chat_service.run_chat("siapa itu jokowi", [])
    assert res.passages == []
    assert "Presiden Republik Indonesia" not in res.text
    assert "di luar cakupan data" in res.text
    assert backend.calls >= 2


def test_zero_passage_search_blocks_freeform_answer(monkeypatch):
    monkeypatch.setattr(retrieval_mod, "search", lambda q, top_k=5, dashboard_name=None: [])

    class FakeBackend:
        kind = "fake"
        model = "fake-model"

        def __init__(self):
            self.calls = 0

        def generate(self, messages, tools=None):
            self.calls += 1
            if self.calls == 1:
                return providers_mod.BackendTurn(
                    tool_calls=[
                        providers_mod.ToolCall(
                            name=chat_service.SEARCH_TOOL, args={"query": "jokowi"}
                        )
                    ]
                )
            return providers_mod.BackendTurn(
                text="Joko Widodo adalah Presiden Indonesia ke-7."
            )

    monkeypatch.setattr(providers_mod, "build_backends", lambda: [FakeBackend()])
    res = chat_service.run_chat("siapa itu jokowi", [])
    assert res.passages == []
    assert "Presiden Indonesia" not in res.text
    assert "di luar cakupan data" in res.text


def test_weak_passage_refusal_strips_irrelevant_sources_and_leaked_preamble(monkeypatch):
    monkeypatch.setattr(
        retrieval_mod, "search", lambda q, top_k=5, dashboard_name=None: [_passage()]
    )

    class LeakyAfterSearchBackend:
        kind = "fake"
        model = "fake-model"

        def __init__(self):
            self.calls = 0

        def generate(self, messages, tools=None):
            self.calls += 1
            if self.calls == 1:
                return providers_mod.BackendTurn(
                    tool_calls=[
                        providers_mod.ToolCall(
                            name=chat_service.SEARCH_TOOL, args={"query": "jokowi"}
                        )
                    ]
                )
            return providers_mod.BackendTurn(
                text=(
                    "Joko Widodo adalah Presiden RI ke-7.\n\n"
                    "Perlu saya sampaikan bahwa informasi tersebut berada di luar cakupan "
                    "data internal Pemda DIY."
                )
            )

    monkeypatch.setattr(providers_mod, "build_backends", lambda: [LeakyAfterSearchBackend()])
    res = chat_service.run_chat("siapa itu jokowi", [])
    assert res.passages == []
    assert "Presiden RI" not in res.text
    assert "di luar cakupan data" in res.text


def test_greeting_and_scope_checks_distinguish_greetings_from_general_queries():
    assert chat_service._is_greeting_or_scope_query("halo") is True
    assert chat_service._is_greeting_or_scope_query("Selamat pagi!") is True
    assert chat_service._is_greeting_or_scope_query("data apa saja yang tersedia?") is True
    assert chat_service._is_greeting_or_scope_query("siapa itu jokowi") is False
    assert chat_service._is_greeting_or_scope_query("halo siapa itu jokowi") is False
    assert chat_service._is_greeting_or_scope_query("berapa jumlah sentra ikm?") is False
