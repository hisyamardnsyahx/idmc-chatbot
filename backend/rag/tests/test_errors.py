"""Error vocabulary tests: provider exceptions map to honest ChatErrors."""

import pytest

from rag.core import errors as errors_mod


class _StubError(Exception):
    def __init__(self, code, message="boom"):
        super().__init__(f"{code} {message}")
        self.code = code


def test_quota_maps_with_retry_delay():
    err = errors_mod.translate_provider_error(
        _StubError(429, "Please retry in 24.5s"), operation="menguji"
    )
    assert isinstance(err, errors_mod.QuotaExhaustedError)
    assert err.retry_after_s == pytest.approx(24.5)
    assert "429" in str(err)


def test_quota_without_delay_still_honest():
    err = errors_mod.translate_provider_error(_StubError(429, "limit"), operation="menguji")
    assert isinstance(err, errors_mod.QuotaExhaustedError)
    assert err.retry_after_s is None


def test_auth_maps_to_configuration():
    err = errors_mod.translate_provider_error(_StubError(401), operation="menguji")
    assert isinstance(err, errors_mod.ConfigurationError)


def test_unknown_model_maps_to_configuration():
    err = errors_mod.translate_provider_error(_StubError(404), operation="menguji")
    assert isinstance(err, errors_mod.ConfigurationError)


def test_server_error_maps_to_busy():
    err = errors_mod.translate_provider_error(_StubError(503), operation="menguji")
    assert isinstance(err, errors_mod.ModelBusyError)


def test_timeout_maps_to_unreachable():
    err = errors_mod.translate_provider_error(TimeoutError("timed out"), operation="menguji")
    assert isinstance(err, errors_mod.UpstreamUnreachableError)


def test_unexpected_error_stays_generic_but_typed():
    err = errors_mod.translate_provider_error(ValueError("weird"), operation="menguji")
    assert type(err) is errors_mod.ChatError
    assert "menguji" in str(err)
