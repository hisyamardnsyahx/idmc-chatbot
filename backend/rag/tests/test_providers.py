"""Provider abstraction tests: tool-shape conversion + backend-agnostic loop."""

import json

from rag.chat import providers as providers_mod
from rag.chat import service as chat_service
from rag.core import config as config_mod
from rag.core.models import Passage


def _passage():
    return Passage(
        dashboard="D",
        chart="C",
        slice_id=1,
        rows_covered="1-1 of 1",
        data_as_of="x",
        possibly_outdated=False,
        relevance=0.9,
        content="isi data",
    )


def test_openai_tool_shape_round_trip():
    tools = chat_service.tool_definitions()
    assert tools[1]["function"]["name"] == "search_knowledge"
    # OpenAI tool dicts must be JSON-serialisable for any HTTP backend.
    json.dumps(tools)


def test_run_chat_uses_backend_turns(monkeypatch):
    from rag.chat import retrieval as retrieval_mod

    monkeypatch.setattr(retrieval_mod, "search", lambda q, top_k=5, dashboard_name=None: [_passage()])

    calls = []

    class FakeBackend:
        kind = "fake"
        model = "fake-model"

        def generate(self, messages, tools=None):
            calls.append([m["role"] for m in messages])
            if len(calls) == 1:
                return providers_mod.BackendTurn(
                    tool_calls=[providers_mod.ToolCall(name="search_knowledge", args={"query": "x"})]
                )
            return providers_mod.BackendTurn(text="Jawaban final")

    monkeypatch.setattr(providers_mod, "build_backends", lambda: [FakeBackend()])
    result = chat_service.run_chat("berapa?", [])
    assert result.text == "Jawaban final"
    assert result.passages and result.passages[0].dashboard == "D"
    # Second call carries system + user + assistant(tool) + tool result.
    assert "tool" in calls[1]


def test_run_chat_empty_final_text_raises(monkeypatch):
    class FakeBackend:
        kind = "fake"
        model = "fake-model"

        def generate(self, messages, tools=None):
            return providers_mod.BackendTurn(text="   ")

    monkeypatch.setattr(providers_mod, "build_backends", lambda: [FakeBackend()])
    try:
        chat_service.run_chat("halo", [])
    except chat_service.ModelEmptyError:
        return
    raise AssertionError("expected ModelEmptyError")


def test_build_backends_respects_openai_provider(monkeypatch):
    monkeypatch.setattr(config_mod.settings, "chat_provider", "openai-compat")
    monkeypatch.setattr(config_mod.settings, "chat_base_url", "http://localhost:20128/v1")
    monkeypatch.setattr(config_mod.settings, "chat_model", "ocg/muse-spark-1.3-contributor")
    monkeypatch.setattr(config_mod.settings, "chat_fallback_models", ())
    backends = providers_mod.build_backends()
    assert len(backends) == 1
    assert isinstance(backends[0], providers_mod.OpenAICompatBackend)


def test_messages_to_openai_carries_tool_history():
    msgs = [
        {"role": "system", "text": "sys"},
        {"role": "user", "text": "berapa?"},
        {
            "role": "assistant",
            "text": "",
            "tool_calls": [{"name": "search_knowledge", "args": {"query": "x"}, "call_id": "c1"}],
        },
        {"role": "tool", "name": "search_knowledge", "call_id": "c1", "content": "hasil"},
    ]
    out = providers_mod._messages_to_openai(msgs)
    assert out[0] == {"role": "system", "content": "sys"}
    assert out[2]["tool_calls"][0]["id"] == "c1"
    assert out[3] == {"role": "tool", "tool_call_id": "c1", "content": "hasil"}
