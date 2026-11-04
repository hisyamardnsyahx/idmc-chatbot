"""Chat provider abstraction: Gemini SDK or any OpenAI-compatible endpoint.

The RAG loop only speaks :class:`ChatBackend` (plain messages in, plain
turns out). Concrete backends translate to/from their wire format:

- :class:`GeminiBackend` — google-genai SDK with native function calling.
- :class:`OpenAICompatBackend` — ``/v1/chat/completions`` (streaming)
  with OpenAI-style ``tools``/``tool_calls``. Covers local gateways
  such as ``http://localhost:20128/v1``.

Tool calls cross the boundary as JSON-serialisable dicts so no SDK
types leak into the loop.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

log = logging.getLogger("rag.chat.providers")

# Reuse HTTP clients across requests. Building a new OpenAI/GenAI client per
# chat turn costs ~0.2-1s (imports + httpx client). The settings are loaded
# once, so caching by connection parameters is safe. Tests that monkeypatch
# settings still get fresh backend wrappers; only the transport is shared.
_openai_clients: dict[tuple[str, str], object] = {}
_genai_clients: dict[str, object] = {}


def _cached_openai_client(base_url: str, api_key: str):
    from openai import OpenAI

    key = (base_url.rstrip("/"), api_key or "x")
    client = _openai_clients.get(key)
    if client is None:
        client = OpenAI(base_url=key[0], api_key=key[1])
        _openai_clients[key] = client
    return client


def _cached_genai_client(api_key: str):
    from google import genai

    client = _genai_clients.get(api_key)
    if client is None:
        client = genai.Client(api_key=api_key)
        _genai_clients[api_key] = client
    return client


@dataclass(frozen=True)
class ToolCall:
    """One model-requested tool invocation."""

    name: str
    args: dict[str, Any]
    call_id: str = ""
    thought_signature: bytes | None = None


@dataclass(frozen=True)
class BackendTurn:
    """One assistant turn: final text and/or tool calls."""

    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)


class ChatBackend(Protocol):
    kind: str

    def generate(
        self, messages: list[dict[str, str]], tools: list[dict[str, Any]] | None = None
    ) -> BackendTurn: ...


def openai_tools_to_gemini(tools: list[dict[str, Any]]):
    """Convert OpenAI-style tool dicts to google-genai Tool objects."""
    from google.genai import types

    decls = []
    for tool in tools or []:
        fn = tool.get("function", tool)
        name = fn.get("name", "")
        description = fn.get("description", "")
        params = fn.get("parameters", {"type": "object", "properties": {}})
        decls.append(
            types.FunctionDeclaration(
                name=name,
                description=description,
                parameters=_json_schema_to_gemini(params),
            )
        )
    return [types.Tool(function_declarations=decls)]


def _json_schema_to_gemini(schema: dict[str, Any]):
    from google.genai import types

    type_map = {
        "object": types.Type.OBJECT,
        "string": types.Type.STRING,
        "integer": types.Type.INTEGER,
        "number": types.Type.NUMBER,
        "boolean": types.Type.BOOLEAN,
        "array": types.Type.ARRAY,
    }
    kwargs: dict[str, Any] = {
        "type": type_map.get(str(schema.get("type", "object")).lower(), types.Type.OBJECT)
    }
    if schema.get("description"):
        kwargs["description"] = schema["description"]
    if schema.get("enum"):
        kwargs["enum"] = schema["enum"]
    props = schema.get("properties") or {}
    if props:
        kwargs["properties"] = {k: _json_schema_to_gemini(v) for k, v in props.items()}
    if schema.get("required"):
        kwargs["required"] = list(schema["required"])
    if schema.get("items"):
        kwargs["items"] = _json_schema_to_gemini(schema["items"])
    return types.Schema(**kwargs)


def gemini_tools_to_openai(gemini_tools) -> list[dict[str, Any]]:
    """Convert google-genai Tool objects to OpenAI-style tool dicts."""
    out: list[dict[str, Any]] = []
    for tool in gemini_tools or []:
        for decl in getattr(tool, "function_declarations", None) or []:
            params = decl.parameters
            out.append(
                {
                    "type": "function",
                    "function": {
                        "name": decl.name,
                        "description": decl.description or "",
                        "parameters": _gemini_schema_to_json(params),
                    },
                }
            )
    return out


def _gemini_schema_to_json(schema) -> dict[str, Any]:
    if schema is None:
        return {"type": "object", "properties": {}}
    if isinstance(schema, dict):
        return schema
    out: dict[str, Any] = {}
    type_name = str(getattr(schema, "type", "OBJECT")).split(".")[-1].lower()
    out["type"] = {
        "object": "object",
        "string": "string",
        "integer": "integer",
        "number": "number",
        "boolean": "boolean",
        "array": "array",
    }.get(type_name, "object")
    if getattr(schema, "description", None):
        out["description"] = schema.description
    if getattr(schema, "enum", None):
        out["enum"] = list(schema.enum)
    props = getattr(schema, "properties", None) or {}
    if props:
        out["properties"] = {k: _gemini_schema_to_json(v) for k, v in props.items()}
    if getattr(schema, "required", None):
        out["required"] = list(schema.required)
    items = getattr(schema, "items", None)
    if items is not None:
        out["items"] = _gemini_schema_to_json(items)
    return out


class GeminiBackend:
    """Chat via the google-genai SDK (native function calling).

    Takes plain ``messages`` (an optional leading ``system`` message plus
    ``user``/``assistant``/``tool`` turns) so the RAG loop stays
    backend-agnostic. Single model per instance; model fallback across
    instances is owned by the caller.
    """

    kind = "gemini"

    def __init__(self, model: str, api_key: str = "") -> None:
        if not api_key:
            raise ValueError("GEMINI_API_KEY is missing — set it in .env")
        if not model:
            raise ValueError("chat model is missing — set it in .env")
        self._client = _cached_genai_client(api_key)
        self._model = model
        self.model = model

    def generate(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None
    ) -> BackendTurn:
        from ..core.errors import translate_provider_error
        from google.genai import errors, types

        system = next((m.get("text", "") for m in messages if m.get("role") == "system"), "")
        contents = [_message_to_content(m) for m in messages if m.get("role") != "system"]
        try:
            resp = self._client.models.generate_content(
                model=self._model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system or None,
                    tools=openai_tools_to_gemini(tools) if tools else None,
                ),
            )
        except (errors.ServerError, errors.ClientError) as e:
            raise translate_provider_error(e, operation="memanggil model chat") from e
        except Exception as e:  # network/SDK failure — translate, never leak raw
            raise translate_provider_error(e, operation="memanggil model chat") from e
        return self._to_turn(resp)

    @staticmethod
    def _to_turn(resp) -> BackendTurn:
        if not resp.candidates or not resp.candidates[0].content:
            from ..core.errors import ModelEmptyError

            raise ModelEmptyError("The model returned no content.")
        parts = resp.candidates[0].content.parts or []
        calls = []
        for i, p in enumerate(parts):
            fc = getattr(p, "function_call", None)
            if fc is not None:
                calls.append(
                    ToolCall(
                        name=fc.name,
                        args=dict(fc.args or {}),
                        call_id=f"call_{i}",
                        thought_signature=getattr(p, "thought_signature", None),
                    )
                )
        text = "".join(p.text for p in parts if getattr(p, "text", None))
        return BackendTurn(text=text, tool_calls=calls)


def _message_to_content(m: dict[str, Any]):
    """Plain loop message -> google-genai Content (incl. tool history)."""
    from google.genai import types

    role = m.get("role", "user")
    if role == "assistant" and m.get("tool_calls"):
        parts = []
        if m.get("text"):
            parts.append(types.Part.from_text(text=m["text"]))
        for tc in m["tool_calls"]:
            parts.append(
                types.Part(
                    function_call=types.FunctionCall(
                        name=tc["name"], args=tc.get("args") or {}
                    ),
                    thought_signature=tc.get("thought_signature"),
                )
            )
        return types.Content(role="model", parts=parts)
    if role == "tool":
        payload: Any = {"result": m.get("content", "")}
        try:
            payload = {"result": json.loads(m.get("content") or "{}")}
        except (json.JSONDecodeError, TypeError):
            pass
        return types.Content(
            role="user",
            parts=[types.Part.from_function_response(name=m.get("name", ""), response=payload)],
        )
    return types.Content(
        role="user" if role == "user" else "model",
        parts=[types.Part.from_text(text=m.get("text", ""))],
    )


class OpenAICompatBackend:
    """Chat via any OpenAI-compatible ``/v1/chat/completions`` endpoint.

    Uses streaming because some gateways return empty ``content`` on
    non-streaming calls while streaming works. Tool calls stream as
    ``delta.tool_calls`` fragments and are reassembled here.
    """

    kind = "openai-compat"

    def __init__(
        self,
        model: str,
        base_url: str,
        api_key: str = "x",
        timeout_s: float = 120.0,
        reasoning_effort: str = "",
    ) -> None:
        if not base_url:
            raise ValueError("CHAT_BASE_URL is missing — set it in .env")
        if not model:
            raise ValueError("CHAT_MODEL is missing — set it in .env")
        self._client = _cached_openai_client(base_url, api_key or "x")
        self._model = model
        self._timeout_s = timeout_s
        self._reasoning_effort = (reasoning_effort or "").strip().lower()

    @property
    def model(self) -> str:
        return self._model

    def generate(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None
    ) -> BackendTurn:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": _messages_to_openai(messages),
            "stream": True,
        }
        if tools:
            payload["tools"] = tools
        if self._reasoning_effort:
            payload["extra_body"] = {"reasoning": {"effort": self._reasoning_effort}}
        try:
            stream = self._client.chat.completions.create(**payload, timeout=self._timeout_s)
        except Exception as e:  # connect/auth failure before first byte
            raise _translate_openai_error(e, operation="memanggil model chat") from e
        text_parts: list[str] = []
        fragments: dict[int, dict[str, str]] = {}
        try:
            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if getattr(delta, "content", None):
                    text_parts.append(delta.content)
                for tc in getattr(delta, "tool_calls", None) or []:
                    slot = fragments.setdefault(tc.index, {"id": "", "name": "", "args": ""})
                    if getattr(tc, "id", None):
                        slot["id"] = tc.id
                    fn = getattr(tc, "function", None)
                    if fn is not None:
                        if getattr(fn, "name", None):
                            slot["name"] += fn.name
                        if getattr(fn, "arguments", None):
                            slot["args"] += fn.arguments
        except Exception as e:  # mid-stream failure
            raise _translate_openai_error(e, operation="memanggil model chat") from e
        calls = []
        for slot in fragments.values():
            if not slot["name"]:
                continue
            try:
                args = json.loads(slot["args"]) if slot["args"] else {}
            except json.JSONDecodeError:
                args = {}
            calls.append(
                ToolCall(name=slot["name"], args=args, call_id=slot["id"] or f"call_{len(calls)}")
            )
        return BackendTurn(text="".join(text_parts), tool_calls=calls)


def _messages_to_openai(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Plain loop messages -> OpenAI chat messages (incl. tool history)."""
    out: list[dict[str, Any]] = []
    for m in messages:
        role = m.get("role", "user")
        if role == "system":
            out.append({"role": "system", "content": m.get("text", "")})
        elif role == "assistant" and m.get("tool_calls"):
            out.append(
                {
                    "role": "assistant",
                    "content": m.get("text") or None,
                    "tool_calls": [
                        {
                            "id": tc.get("call_id") or f"call_{i}",
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": json.dumps(tc.get("args") or {}),
                            },
                        }
                        for i, tc in enumerate(m["tool_calls"])
                    ],
                }
            )
        elif role == "tool":
            out.append(
                {
                    "role": "tool",
                    "tool_call_id": m.get("call_id", ""),
                    "content": m.get("content", ""),
                }
            )
        elif m.get("text"):
            out.append({"role": "user" if role == "user" else "assistant", "content": m["text"]})
    return out


def _translate_openai_error(exc: Exception, *, operation: str):
    from ..core.errors import translate_http_error

    status = getattr(exc, "status_code", None)
    if status is None:
        resp = getattr(exc, "response", None)
        status = getattr(resp, "status_code", None)
    if isinstance(status, int):
        return translate_http_error(status, str(exc), operation=operation)
    from ..core.errors import translate_provider_error

    return translate_provider_error(exc, operation=operation)


def build_backends() -> list[ChatBackend]:
    """Ordered backends from settings: primary then fallbacks.

    Gemini: one backend per model (primary + ``GEMINI_FALLBACK_MODELS``).
    OpenAI-compatible: one backend per model (``CHAT_MODEL`` +
    ``CHAT_FALLBACK_MODELS``) sharing the same base URL.
    """
    from ..core import config as config_mod

    cfg = config_mod.settings
    if cfg.chat_provider == "openai-compat":
        return [
            OpenAICompatBackend(
                model=model,
                base_url=cfg.chat_base_url,
                api_key=cfg.chat_api_key,
                timeout_s=cfg.chat_timeout_s,
                reasoning_effort=getattr(cfg, "chat_reasoning_effort", ""),
            )
            for model in [cfg.chat_model, *cfg.chat_fallback_models]
            if model
        ]
    return [
        GeminiBackend(model=model, api_key=cfg.gemini_api_key)
        for model in [cfg.gemini_model, *cfg.gemini_fallback_models]
        if model
    ]


__all__ = [
    "BackendTurn",
    "ChatBackend",
    "GeminiBackend",
    "OpenAICompatBackend",
    "ToolCall",
    "build_backends",
    "gemini_tools_to_openai",
    "openai_tools_to_gemini",
]
