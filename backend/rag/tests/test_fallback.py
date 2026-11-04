"""Fallback tests: overloaded backends yield to the next backend."""

from rag.chat import providers as providers_mod
from rag.chat import service as chat_service
from rag.core import config as config_mod


class _Backend:
    def __init__(self, model, behaviour):
        self.model = model
        self.kind = "fake"
        self._behaviour = behaviour
        self.calls = 0

    def generate(self, messages, tools=None):
        self.calls += 1
        if self._behaviour == "busy":
            raise chat_service.ModelBusyError("sibuk")
        return providers_mod.BackendTurn(text=f"ok from {self.model}")


def test_falls_back_to_next_backend_on_busy(monkeypatch):
    primary, fallback = _Backend("primary", "busy"), _Backend("fallback", "ok")
    monkeypatch.setattr(providers_mod, "build_backends", lambda: [primary, fallback])
    turn = chat_service._generate_with_retry([{"role": "user", "text": "halo"}], [], attempts=1)
    assert turn.text == "ok from fallback"
    assert primary.calls == 1 and fallback.calls == 1


def test_primary_success_uses_no_fallback(monkeypatch):
    primary, fallback = _Backend("primary", "ok"), _Backend("fallback", "ok")
    monkeypatch.setattr(providers_mod, "build_backends", lambda: [primary, fallback])
    turn = chat_service._generate_with_retry([{"role": "user", "text": "halo"}], [], attempts=1)
    assert turn.text == "ok from primary"
    assert primary.calls == 1 and fallback.calls == 0


def test_all_backends_overloaded_raises_busy(monkeypatch):
    backends = [_Backend("primary", "busy"), _Backend("fallback", "busy")]
    monkeypatch.setattr(providers_mod, "build_backends", lambda: backends)
    try:
        chat_service._generate_with_retry([{"role": "user", "text": "halo"}], [], attempts=1)
    except chat_service.ModelBusyError as e:
        assert "sibuk" in str(e) or "503" in str(e) or "Semua" in str(e)
        return
    raise AssertionError("expected ModelBusyError")


def test_quota_is_not_fallen_back(monkeypatch):
    class _Quota(_Backend):
        def generate(self, messages, tools=None):
            self.calls += 1
            raise chat_service.QuotaExhaustedError("habis", retry_after_s=999.0)

    primary, fallback = _Quota("primary", "quota"), _Backend("fallback", "ok")
    monkeypatch.setattr(providers_mod, "build_backends", lambda: [primary, fallback])
    monkeypatch.setattr(chat_service.time, "sleep", lambda s: None)
    try:
        chat_service._generate_with_retry([{"role": "user", "text": "halo"}], [], attempts=1)
    except chat_service.QuotaExhaustedError:
        assert primary.calls == 1 and fallback.calls == 0
        return
    raise AssertionError("expected QuotaExhaustedError")


def test_default_settings_include_known_good_fallbacks():
    assert config_mod.settings.gemini_fallback_models
    assert config_mod.settings.gemini_model not in config_mod.settings.gemini_fallback_models
