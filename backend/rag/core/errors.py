"""Error vocabulary shared by pipeline, chat, and web layers.

Duck-typed on purpose: this module never imports google-genai or httpx,
so unit tests can feed stub exceptions and the core stays dependency-free.
"""

from __future__ import annotations

import re


class ChatError(RuntimeError):
    """Base for failures the chat pipeline reports honestly to the user."""


class ConfigurationError(ChatError):
    """Server misconfiguration: missing/invalid API key, unknown model."""


class QuotaExhaustedError(ChatError):
    """Provider quota exhausted (HTTP 429). Carries an optional retry delay."""

    def __init__(self, message: str, retry_after_s: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_s = retry_after_s


class ModelBusyError(ChatError):
    """Provider-side transient failure (HTTP 5xx). Worth retrying soon."""


class UpstreamUnreachableError(ChatError):
    """Network failure reaching the provider (timeout, DNS, refused)."""


class ModelEmptyError(ChatError):
    """Provider returned no usable content."""


class ToolLoopExhaustedError(ChatError):
    """Tool loop hit its round-trip cap without a final answer."""


_NETWORK_NAMES = {
    "ConnectError",
    "TimeoutException",
    "ReadTimeout",
    "WriteTimeout",
    "PoolTimeout",
    "NetworkError",
    "RemoteProtocolError",
    "LocalProtocolError",
    "ProxyError",
}


def _is_network_error(exc: BaseException) -> bool:
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return True
    module = type(exc).__module__.split(".")[0]
    return (
        module in ("httpx", "httpcore")
        or isinstance(exc, OSError)
        or type(exc).__name__ in _NETWORK_NAMES
    )


def _retry_after_s(exc: BaseException) -> float | None:
    return _retry_after_s_from_text(str(exc))


def _retry_after_s_from_text(text: str) -> float | None:
    m = re.search(r"[Pp]lease retry in ([\d.]+)s", text)
    return float(m.group(1)) if m else None


def parse_retry_after_s(exc: BaseException) -> float | None:
    """Public alias: seconds the provider asks us to wait, if stated."""
    return _retry_after_s(exc)


def translate_http_error(code: int | None, message: str, *, operation: str) -> ChatError:
    """Map an HTTP-style provider failure to an honest ChatError.

    Shared by every provider backend (Gemini SDK, OpenAI-compatible
    endpoints, future backends): same code, same user-facing meaning.
    """
    text = str(message or "")
    if code == 429:
        retry_after = _retry_after_s_from_text(text)
        hint = (
            f"Coba lagi dalam {retry_after:.0f} detik."
            if retry_after is not None
            else "Coba lagi nanti."
        )
        return QuotaExhaustedError(
            f"Kuota AI habis (429) saat {operation}. {hint}",
            retry_after_s=retry_after,
        )
    if code in (401, 403):
        return ConfigurationError(
            "Kunci API ditolak provider (401/403). "
            "Periksa API key di server."
        )
    if code == 404:
        return ConfigurationError(
            "Model AI tidak ditemukan (404). "
            "Periksa nama model di server."
        )
    if isinstance(code, int) and 400 <= code < 500:
        return ConfigurationError(
            f"Permintaan ke AI ditolak ({code}) saat {operation}. "
            "Periksa konfigurasi model di server."
        )
    if isinstance(code, int) and code >= 500:
        return ModelBusyError(
            f"Layanan AI bermasalah ({code}) saat {operation}. "
            "Coba lagi beberapa saat."
        )
    return ChatError(f"Gagal {operation}: {text or 'unknown error'}")


def translate_provider_error(exc: Exception, *, operation: str) -> ChatError:
    """Map a provider/SDK exception to a user-honest ChatError.

    ``operation`` names what was attempted (e.g. "membuat embedding",
    "memanggil model chat") so messages read well in Indonesian UI.
    """
    code = getattr(exc, "code", None)
    if isinstance(code, int):
        return translate_http_error(code, str(exc), operation=operation)
    if _is_network_error(exc):
        return UpstreamUnreachableError(
            f"Tidak dapat menghubungi layanan AI saat {operation}. "
            "Periksa jaringan server lalu coba lagi."
        )
    return ChatError(f"Gagal {operation}: {exc}")
