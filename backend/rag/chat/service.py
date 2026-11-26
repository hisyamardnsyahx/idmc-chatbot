"""Tool loop grounded on retrieved passages, backend-agnostic.

The loop only speaks plain messages and JSON tool calls. Concrete chat
providers (Gemini SDK, OpenAI-compatible endpoints) live in
:mod:`rag.chat.providers` and are chosen via settings. The web layer maps
the :class:`~rag.core.errors.ChatError` subclasses to HTTP status; unit
tests fake the backend and never touch the network.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Sequence

from ..core import config as config_mod
from ..core.errors import (
    ChatError,
    ConfigurationError,
    ModelBusyError,
    ModelEmptyError,
    QuotaExhaustedError,
    ToolLoopExhaustedError,
    UpstreamUnreachableError,
    translate_provider_error,
)
from ..core.models import ChatTurn, Passage
from . import providers, retrieval
from .prompts import SYSTEM_PROMPT

log = logging.getLogger("rag.chat")

SEARCH_TOOL = "search_knowledge"
LIST_TOOL = "list_charts"
REFUSE_TOOL = "refuse_out_of_scope"
MAX_SEARCH_ATTEMPTS = 2

_ALLOWED_DOMAINS_LIST = (
    "- Kepegawaian ASN (Dashboard SIMPEG)\n"
    "- SPBE DIY (Arsitektur dan Peta Rencana SPBE 2023, 2024, 2025)\n"
    "- Industri Kecil dan Menengah (DATAKU-IKM)\n"
    "- UMKM Marketplace\n"
    "- Pembangunan Daerah dan Infrastruktur\n"
    "- Perkebunan DIY\n"
    "- Jaringan Fiber Optic di DIY\n"
    "- Pemantauan CCTV dan Lalu Lintas (Surveillance, ATCS, perbatasan kota)\n"
    "- Masterplan Jogja Smart Province"
)

_GREETING_EXACT = {
    "halo",
    "hai",
    "hi",
    "hello",
    "helo",
    "hei",
    "oi",
    "oy",
    "p",
    "permisi",
    "assalamualaikum",
    "assalamu'alaikum",
    "selamat pagi",
    "selamat siang",
    "selamat sore",
    "selamat malam",
    "pagi",
    "siang",
    "sore",
    "malam",
    "apa kabar",
    "terima kasih",
    "terimakasih",
    "makasih",
    "thanks",
    "thank you",
    "oke",
    "ok",
    "baik",
    "siap",
    "bye",
    "dadah",
}

_SCOPE_PATTERNS = (
    re.compile(r"^(siapa|apa)\s+(kamu|anda|bot\s+ini)(\s+ini)?\??$"),
    re.compile(r"^(kamu|anda)\s+(siapa|bisa\s+apa|bisa\s+bantu\s+apa)\??$"),
    re.compile(r"^(apa\s+saja|apa)\s+(yang\s+)?(bisa\s+(kamu|anda)\s+bantu|fitur)\??$"),
    re.compile(
        r"^(data|informasi|dashboard|topik|cakupan)\s+(apa|apa\s+saja)\s+"
        r"(yang\s+)?(ada|tersedia|tidak\s+ada|belum\s+ada|dicakup|bisa\s+dicari).*$"
    ),
    re.compile(r"^(apa|sebutkan)\s+(data|daftar\s+data|daftar\s+dashboard)(\s+yang\s+(ada|tersedia|tidak\s+ada))?\??$"),
)

_REFUSAL_MARKERS = (
    "di luar cakupan",
    "di luar data warehouse",
    "tidak tersedia di",
    "tidak tersedia pada",
    "tidak ditemukan di",
    "tidak ditemukan pada",
    "tidak menemukan sumber yang relevan",
    "tidak mencakup",
    "belum mencakup",
    "tidak ada data mengenai",
    "tidak terdapat data",
    "tidak memiliki informasi",
    "tidak memiliki data",
    "bukan merupakan data",
    "di luar topik",
)


def build_out_of_scope_reply(topic: str | None = None) -> str:
    """Return a clean, deterministic refusal without any parametric LLM trivia."""
    topic_clean = (topic or "").strip().strip(".")
    if topic_clean:
        opening = (
            f"Maaf, informasi mengenai **{topic_clean}** berada di luar cakupan data "
            "yang tersedia pada gudang data (data warehouse) IDMC Pemerintah Daerah DIY."
        )
    else:
        opening = (
            "Maaf, pertanyaan tersebut berada di luar cakupan data "
            "yang tersedia pada gudang data (data warehouse) IDMC Pemerintah Daerah DIY."
        )
    return (
        f"{opening}\n\n"
        "Saya hanya dapat menjawab pertanyaan yang bersumber langsung dari dashboard resmi berikut:\n"
        f"{_ALLOWED_DOMAINS_LIST}\n\n"
        "Silakan ajukan pertanyaan yang berkaitan dengan topik data di atas."
    )


def _is_greeting_or_scope_query(message: str) -> bool:
    """Allow pure social greetings and bot-scope questions without retrieval."""
    cleaned = re.sub(r"[!?.,]+$", "", (message or "").strip().lower())
    cleaned = re.sub(r"\s+", " ", cleaned)
    if not cleaned:
        return False
    if cleaned in _GREETING_EXACT:
        return True
    return any(p.match(cleaned) for p in _SCOPE_PATTERNS)


def _looks_like_refusal(text: str) -> bool:
    low = (text or "").lower()
    return any(marker in low for marker in _REFUSAL_MARKERS)


@dataclass(frozen=True)
class ChatResult:
    """Raw model text plus the passages backing it."""

    text: str
    passages: list[Passage]


# Re-exported so existing imports (tests, web layer) keep working.
__all__ = [
    "ChatError",
    "ConfigurationError",
    "ModelBusyError",
    "ModelEmptyError",
    "QuotaExhaustedError",
    "ToolLoopExhaustedError",
    "UpstreamUnreachableError",
    "ChatResult",
    "run_chat",
    "passage_to_dict",
]


def tool_definitions() -> list[dict[str, Any]]:
    """Tool declarations in OpenAI style; backends convert as needed."""
    names = retrieval.dashboard_names()
    dashboard_prop: dict[str, Any] = {
        "type": "string",
        "description": "Optional dashboard filter.",
    }
    if names:
        dashboard_prop["enum"] = names
    return [
        {
            "type": "function",
            "function": {
                "name": LIST_TOOL,
                "description": (
                    "List available charts as {slice_id, slice_name, dashboard_name}."
                ),
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": SEARCH_TOOL,
                "description": (
                    "Semantic search over the dashboard data. Returns passages with "
                    "dashboard, chart, rows covered, and extraction time."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Focused search query."},
                        "dashboard_name": dashboard_prop,
                        "top_k": {
                            "type": "integer",
                            "description": (
                                f"Passages to return (1-{config_mod.settings.max_top_k})."
                            ),
                        },
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": REFUSE_TOOL,
                "description": (
                    "Call this IMMEDIATELY whenever the user asks any question outside the "
                    "scraped IDMC Yogyakarta dashboards (general knowledge, public figure "
                    "biographies, world geography, history, coding, recipes, math, or uncovered "
                    "domains like general population/kependudukan or public health), OR when "
                    "search_knowledge returns no passages directly answering the question."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "topic": {
                            "type": "string",
                            "description": "Short 2-5 word label of the out-of-scope topic asked.",
                        },
                    },
                    "required": ["topic"],
                },
            },
        },
    ]


def _quota_delay_s(exc: Exception, attempt: int) -> float:
    """Delay before retrying a 429, capped so daily quota fails fast."""
    from ..core.errors import parse_retry_after_s

    hinted = parse_retry_after_s(exc)
    if hinted is not None:
        return min(hinted + 1.0, 60.0)
    return 5.0 * attempt


def _retryable_quota(attempt: int, attempts: int) -> bool:
    return attempt < attempts


def _generate_with_retry(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
    attempts: int = 3,
    backends: list[providers.ChatBackend] | None = None,
    tool_choice_mode: str | None = None,
) -> providers.BackendTurn:
    """Call backends in order, falling back on overload (5xx).

    Quota (429) and config errors fail fast — retrying those on another
    model would not help. Pass ``backends`` to reuse already-built clients
    across tool round-trips; otherwise they are built once here.
    """
    if backends is None:
        backends = providers.build_backends()
    if not backends:
        raise ConfigurationError("No chat model configured — check .env.")
    last_err: Exception | None = None
    for backend in backends:
        model_name = getattr(backend, "model", None) or getattr(
            backend, "_model", backend.kind
        )
        for attempt in range(1, attempts + 1):
            try:
                if tool_choice_mode and getattr(backend, "supports_tool_choice", False):
                    turn = backend.generate(messages, tools, tool_choice_mode=tool_choice_mode)
                else:
                    turn = backend.generate(messages, tools)
                if model_name != getattr(backends[0], "model", getattr(backends[0], "_model", None)):
                    log.warning("Fell back to chat model %s.", model_name)
                return turn
            except QuotaExhaustedError as e:
                if _retryable_quota(attempt, attempts):
                    delay = e.retry_after_s or 5.0 * attempt
                    log.warning(
                        "Quota hit (429); retrying in %.0fs (attempt %d/%d)",
                        delay,
                        attempt,
                        attempts,
                    )
                    time.sleep(min(delay, 60.0))
                    last_err = e
                    continue
                raise
            except ModelBusyError as e:
                last_err = e
                log.warning("Chat backend %s overloaded; trying next.", model_name)
                break
            except (ConfigurationError, UpstreamUnreachableError):
                raise
            except ChatError as e:
                last_err = e
                break
            except Exception as e:  # noqa: BLE001 — last-resort translation
                raise translate_provider_error(e, operation="memanggil model chat") from e
    raise ModelBusyError(
        "Semua model chat sedang sibuk. Coba lagi beberapa saat."
    ) from last_err


def _normalise_history(history: Sequence[ChatTurn | dict[str, str]]) -> list[dict[str, str]]:
    out = []
    for h in history:
        if isinstance(h, ChatTurn):
            out.append({"role": h.role, "text": h.text})
        else:
            out.append({"role": h.get("role", "user"), "text": h.get("text", "")})
    return [h for h in out if h["text"]]


def _run_search(args: dict[str, Any], dashboard: str | None, top_k: int) -> dict[str, Any]:
    query = str(args.get("query") or "").strip()
    if not query:
        raise ValueError("'query' is required.")
    clamped = max(1, min(config_mod.settings.max_top_k, int(args.get("top_k") or top_k)))
    passages = retrieval.search(
        query, top_k=clamped, dashboard_name=args.get("dashboard_name") or dashboard
    )
    if not passages:
        return {"results": [], "note": "No relevant passages found."}
    return {"results": [passage_to_dict(p) for p in passages], "passages": passages}


def passage_to_dict(p: Passage) -> dict[str, Any]:
    return {
        "dashboard": p.dashboard,
        "chart": p.chart,
        "slice_id": p.slice_id,
        "rows_covered": p.rows_covered,
        "data_as_of": p.data_as_of,
        "possibly_outdated": p.possibly_outdated,
        "relevance": p.relevance,
        "content": p.content,
    }


def _tool_result_to_text(tool_name: str, result: dict[str, Any]) -> str:
    """Compact tool result text for backends without native tool history."""
    import json

    results = result.get("results")
    if tool_name == LIST_TOOL and isinstance(results, list):
        lines = [
            f"- {r.get('dashboard_name')}: {r.get('slice_name')} (id {r.get('slice_id')})"
            for r in results[:50]
        ]
        return "Available charts:\n" + "\n".join(lines) if lines else "No charts available."
    if isinstance(results, list):
        blocks = []
        for r in results[:10]:
            blocks.append(
                f"[{r.get('dashboard')} — {r.get('chart')} "
                f"(rows {r.get('rows_covered')}, data {r.get('data_as_of')})]\n"
                f"{r.get('content')}"
            )
        if not blocks:
            return result.get("note", "No results.")
        return (
            "\n\n".join(blocks)
            + "\n\n[VERIFIKASI KETAT: Periksa apakah potongan data di atas benar-benar "
            "menjawab pertanyaan pengguna secara langsung. Jika TIDAK relevan atau "
            "topik berada di luar gudang data IDMC Pemda DIY, WAJIB panggil alat "
            "`refuse_out_of_scope` dan DILARANG menjawab dari pengetahuan umum Anda.]"
        )
    return json.dumps(result, ensure_ascii=False)[:4000]


def run_chat(
    message: str,
    history: Sequence[ChatTurn | dict[str, str]] = (),
    dashboard: str | None = None,
    top_k: int | None = None,
) -> ChatResult:
    """Run the tool loop; returns the raw final text and backing passages."""
    message = (message or "").strip()
    if not message:
        raise ValueError("'message' is required.")
    top_k = top_k or config_mod.settings.default_top_k

    messages: list[dict[str, Any]] = [{"role": "system", "text": SYSTEM_PROMPT}]
    for h in _normalise_history(history):
        messages.append(
            {"role": "user" if h["role"] == "user" else "assistant", "text": h["text"]}
        )
    messages.append({"role": "user", "text": message})
    tools = tool_definitions()
    refuse_only_tools = [t for t in tools if t["function"]["name"] == REFUSE_TOOL]
    last_passages: list[Passage] = []
    search_attempts = 0
    listed_charts = False
    enforced_tool_turn = False
    is_social_or_scope = _is_greeting_or_scope_query(message)
    backends = providers.build_backends()
    if not backends:
        raise ConfigurationError("No chat model configured — check .env.")
    chat_started = time.monotonic()

    for step in range(1, config_mod.settings.max_tool_roundtrips + 1):
        turn_started = time.monotonic()
        final_only = search_attempts >= MAX_SEARCH_ATTEMPTS
        if final_only:
            if not last_passages:
                return ChatResult(text=build_out_of_scope_reply(), passages=[])
            messages[0]["text"] += (
                "\n\nSearch attempts are finished. Do not call `search_knowledge`. "
                "Answer ONLY from the tool results above. If the passages do not directly "
                "answer the question, call `refuse_out_of_scope` immediately."
            )
        force_tool = (
            not final_only
            and search_attempts == 0
            and not listed_charts
            and not is_social_or_scope
        )
        active_tools = refuse_only_tools if final_only else tools
        turn = _generate_with_retry(
            messages,
            active_tools,
            backends=backends,
            tool_choice_mode="ANY" if force_tool else None,
        )
        log.info("chat llm turn took %.1fs", time.monotonic() - turn_started)
        if not turn.tool_calls:
            if not (turn.text or "").strip():
                raise ModelEmptyError("The model returned no content.")
            # Gate 1: Reject direct parametric answers on non-greeting queries without retrieval.
            if search_attempts == 0 and not listed_charts and not is_social_or_scope:
                if not enforced_tool_turn and step < config_mod.settings.max_tool_roundtrips:
                    enforced_tool_turn = True
                    messages.append({"role": "assistant", "text": turn.text})
                    messages.append(
                        {
                            "role": "user",
                            "text": (
                                "[SISTEM] Dilarang menjawab langsung tanpa memeriksa data warehouse. "
                                "Panggil `search_knowledge` bila pertanyaan terkait data Pemda DIY, "
                                "atau panggil `refuse_out_of_scope` bila pertanyaan di luar cakupan."
                            ),
                        }
                    )
                    continue
                log.warning("Blocked ungrounded Turn-1 answer for out-of-scope/unverified query.")
                return ChatResult(text=build_out_of_scope_reply(), passages=[])
            # Gate 2: Never emit free-form answers when searches yielded zero passages.
            if search_attempts > 0 and not last_passages and not listed_charts:
                log.warning("Blocked free-form answer after 0-passage search.")
                return ChatResult(text=build_out_of_scope_reply(), passages=[])
            # Gate 3: If model refuses despite weak passages, scrub any leaked trivia and strip sources.
            if last_passages and not listed_charts and _looks_like_refusal(turn.text):
                log.info("Normalized refusal answer and cleared weak irrelevant passages.")
                return ChatResult(text=build_out_of_scope_reply(), passages=[])
            log.info("chat total took %.1fs", time.monotonic() - chat_started)
            return ChatResult(text=turn.text, passages=last_passages)

        # Short-circuit immediately when model calls refuse_out_of_scope.
        for tc in turn.tool_calls:
            if tc.name == REFUSE_TOOL:
                topic = str((tc.args or {}).get("topic") or "").strip() or None
                log.info("Model refused out-of-scope query cleanly via tool: topic=%r", topic)
                return ChatResult(text=build_out_of_scope_reply(topic), passages=[])

        messages.append(
            {
                "role": "assistant",
                "text": turn.text,
                "tool_calls": [
                    {
                        "name": tc.name,
                        "args": tc.args,
                        "call_id": tc.call_id,
                        "thought_signature": tc.thought_signature,
                    }
                    for tc in turn.tool_calls
                ],
            }
        )
        for tc in turn.tool_calls:
            tool_started = time.monotonic()
            try:
                if tc.name == SEARCH_TOOL:
                    if search_attempts >= MAX_SEARCH_ATTEMPTS:
                        result = {
                            "results": [],
                            "note": "Search limit reached. Answer from earlier results or call refuse_out_of_scope.",
                        }
                    else:
                        search_attempts += 1
                        result = _run_search(tc.args, dashboard, top_k)
                        last_passages = result.pop("passages", [])
                elif tc.name == LIST_TOOL:
                    listed_charts = True
                    result = {"results": retrieval.list_charts()}
                else:
                    raise ValueError(f"Unknown tool: {tc.name}")
                content = _tool_result_to_text(tc.name, result)
            except Exception as e:  # noqa: BLE001 — tool errors go back to the model
                content = f"Tool {tc.name} failed: {e}"
                result = {"error": str(e)}
            log.info(
                "chat tool %s took %.1fs", tc.name, time.monotonic() - tool_started
            )
            messages.append(
                {
                    "role": "tool",
                    "name": tc.name,
                    "call_id": tc.call_id,
                    "content": content,
                    "result": result,
                }
            )

    raise ToolLoopExhaustedError("Could not resolve the request after tool calls.")
