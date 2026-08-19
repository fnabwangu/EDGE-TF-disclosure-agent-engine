"""
Language model adapters.

Path: orchestration/llm.py

Fills the `LanguageModel` seam. The model is used for one job only - mapping a
free-text message onto a known Intent and its arguments. It never sees tool
results, never produces numbers, and never emits an approval. If no API key is
configured, `build_language_model` returns None and the agent falls back to
deterministic keyword routing.

OpenAI is called through the official `openai` SDK against the Responses API.
Anthropic remains on `requests`, since only the OpenAI path was asked to move.

The API key is read exactly once, from the `OPENAI_API_KEY` environment
variable, and never logged, hard-coded, or handed to the generative UI or MCP
surfaces - `openai_configured()` and `test_openai_connection()` report state,
never the secret.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests

from core.env import ensure_env_loaded

try:
    import openai as openai_sdk
except ImportError:  # pragma: no cover - exercised only if the dependency is missing
    openai_sdk = None

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
TIMEOUT_SECONDS = 20
CONNECTION_TEST_TIMEOUT_SECONDS = 10
MODEL_LIST_TIMEOUT_SECONDS = 10
CONNECTED_MARKER = "EDGE_OPENAI_CONNECTED"
DEFAULT_OPENAI_MODEL = "gpt-4o"

# Best-to-worst chat-capable families. An id is matched by prefix, so a dated
# snapshot ("gpt-4o-2024-08-06") still ranks under its family. Anything not
# matching a known family, or matching an excluded one, is never auto-selected -
# an account's model list also includes embeddings, TTS, image and moderation
# models that cannot do intent routing at all.
PREFERRED_OPENAI_FAMILIES = ("gpt-5", "o3", "o1", "gpt-4.1", "gpt-4o", "gpt-4-turbo", "gpt-4", "gpt-3.5")
EXCLUDED_MODEL_SUBSTRINGS = (
    "embedding", "whisper", "tts", "dall-e", "moderation", "davinci", "babbage",
    "realtime", "audio", "transcribe", "image", "search", "instruct",
)

# One resolved model per API key per process, so routing a message never
# triggers a fresh models.list() call - only the first one does.
_resolved_model_cache: Dict[str, str] = {}

ROUTING_SYSTEM = """You route messages for EDGE-TF, an institutional ETF disclosure engine.

Reply with ONLY a JSON object: {"intent": "<name>", "args": {...}}

Intents:
- generate        args: {"query": "<the theme or subject>"}   find strategy candidates
- synthesize      args: {"query": "..."} or {"strategy_id": "theme:function"}  run disclosure synthesis
- open_thesis     args: {"query": "..."}   make the current idea durable
- generate_implementations
                  args: {"query": "..."} or {"strategy_id": "theme:function"}
                  generate every eligible way to express a confirmed thesis, side by side,
                  from EDGE's deterministic engines
- generate_implementations_llm
                  args: {"query": "..."} or {"strategy_id": "theme:function"}
                  ask a hosted model to propose implementations instead - only when the user
                  explicitly asks to use the model/AI/GPT for this. Every proposal still passes
                  through EDGE's own gates before publication.
- select_implementation
                  args: {"strategy_id": "theme:function", "implementation_id": "..."}
                  choose one of the already-generated candidates - never invent an id
- design_trade    args: {"query": "..."}   size and price the selected implementation
- catalyst        args: {"query": "...", "stance": "HAWKISH|DOVISH|VOLATILITY"}  a DATED macro event
                  (FOMC, Jackson Hole, CPI, payrolls, elections) rather than an adoption theme
- proceed         args: {}   a bare continuation such as "go", "continue", "do it" - resume from
                  whatever the project state already holds
- inbox           args: {}   what needs a human decision
- continuity      args: {}   what carried over from previous sessions
- board           args: {}   pipeline status
- help            args: {}

Rules:
- Never jump straight to design_trade from a thesis. Implementations must be generated and one
  selected first; if unsure whether they have been, prefer generate_implementations.
- A dated macro or policy event is ALWAYS "catalyst", never "generate".
- Preserve the user's subject wording verbatim in args.query.
- Never invent tickers, prices or scores. You only choose an intent.
"""


@dataclass
class ModelConfig:
    provider: str
    model: str
    api_key: str

    @property
    def label(self) -> str:
        return f"{self.provider}:{self.model}"


def _placeholder(value: Optional[str]) -> bool:
    return not value or value.startswith("your_") or value.strip() == ""


def _family_rank(model_id: str) -> Optional[int]:
    lower = model_id.lower()
    if any(bad in lower for bad in EXCLUDED_MODEL_SUBSTRINGS):
        return None
    for index, family in enumerate(PREFERRED_OPENAI_FAMILIES):
        if lower.startswith(family):
            return index
    return None


def select_best_model(client, *, fallback: str = DEFAULT_OPENAI_MODEL) -> str:
    """Picks the most capable chat model this API key actually has access to.

    Ranks by family (newest/most capable first), then by the model's own
    ``created`` timestamp within a family. Never raises: any failure to list
    models - network, auth, an empty account - falls back to a fixed default.
    """
    try:
        models = list(client.models.list())
    except Exception:
        return fallback

    ranked = []
    for entry in models:
        rank = _family_rank(entry.id)
        if rank is not None:
            ranked.append((rank, -(getattr(entry, "created", 0) or 0), entry.id))
    if not ranked:
        return fallback
    ranked.sort()
    return ranked[0][2]


def resolve_openai_model(api_key: str, *, client: Optional[Any] = None) -> str:
    """An explicit OPENAI_MODEL always wins; otherwise auto-select and cache it."""
    ensure_env_loaded()
    explicit = os.getenv("OPENAI_MODEL")
    if not _placeholder(explicit):
        return explicit

    cached = _resolved_model_cache.get(api_key)
    if cached is not None:
        return cached

    if openai_sdk is None:
        return DEFAULT_OPENAI_MODEL
    try:
        resolved_client = client or openai_sdk.OpenAI(api_key=api_key)
        chosen = select_best_model(resolved_client)
    except Exception:
        chosen = DEFAULT_OPENAI_MODEL
    _resolved_model_cache[api_key] = chosen
    return chosen


def reset_model_cache() -> None:
    _resolved_model_cache.clear()


def resolve_config() -> Optional[ModelConfig]:
    """OPENAI_API_KEY is read here and nowhere else in the codebase."""
    ensure_env_loaded()

    openai_key = os.getenv("OPENAI_API_KEY")
    if not _placeholder(openai_key):
        return ModelConfig("openai", resolve_openai_model(openai_key), openai_key)

    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if not _placeholder(anthropic_key):
        return ModelConfig(
            "anthropic", os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"), anthropic_key
        )
    return None


def openai_configured() -> bool:
    """Startup check: confirms an OpenAI key is present without printing it."""
    ensure_env_loaded()
    return not _placeholder(os.getenv("OPENAI_API_KEY")) and openai_sdk is not None


def test_openai_connection(*, model: Optional[str] = None) -> str:
    """
    Calls the Responses API with a trivial prompt to prove connectivity.

    Returns the literal string "EDGE_OPENAI_CONNECTED" on success. Raises
    RuntimeError with a message that never contains the API key on failure -
    the SDK's own exceptions are caught and re-raised, not passed through
    verbatim, since some embed request headers.
    """
    ensure_env_loaded()
    if openai_sdk is None:
        raise RuntimeError("the openai package is not installed")

    api_key = os.getenv("OPENAI_API_KEY")
    if _placeholder(api_key):
        raise RuntimeError("OPENAI_API_KEY is not configured")

    client = openai_sdk.OpenAI(api_key=api_key)
    try:
        response = client.responses.create(
            model=model or resolve_openai_model(api_key, client=client),
            input="Reply with the single word: ok",
            max_output_tokens=16,
            timeout=CONNECTION_TEST_TIMEOUT_SECONDS,
        )
    except openai_sdk.OpenAIError as exc:
        raise RuntimeError(f"OpenAI connection failed: {type(exc).__name__}") from None

    if not (response.output_text or "").strip():
        raise RuntimeError("OpenAI connection returned an empty response")
    return CONNECTED_MARKER


class HostedLanguageModel:
    """Routes a message to an Intent using a hosted chat model."""

    def __init__(self, config: ModelConfig, *, session: Optional[requests.Session] = None):
        self.config = config
        self.session = session or requests.Session()
        self._client = None
        if config.provider == "openai" and openai_sdk is not None:
            self._client = openai_sdk.OpenAI(api_key=config.api_key)

    def route(self, message: str, *, history: List[Any], intents: List[str], context: str = ""):
        from orchestration.agent import Intent  # imported here to avoid a cycle

        try:
            raw = self._complete(message, history, context)
        except (requests.RequestException, ValueError, KeyError):
            return None
        except Exception as exc:  # openai.OpenAIError, but the SDK is an optional import
            if openai_sdk is not None and isinstance(exc, openai_sdk.OpenAIError):
                return None
            raise

        try:
            parsed = json.loads(self._strip_fences(raw))
        except json.JSONDecodeError:
            return None

        name = parsed.get("intent")
        if name not in intents:
            return None
        args = parsed.get("args") or {}
        return Intent(name=name, args={k: v for k, v in args.items() if isinstance(v, (str, int, float))})

    # -- providers ---------------------------------------------------------

    def _complete(self, message: str, history: List[Any], context: str = "") -> str:
        turns = [
            {"role": item.role, "content": item.content}
            for item in history[-6:]
            if getattr(item, "content", None)
        ]
        system = f"{ROUTING_SYSTEM}\n\n{context}" if context else ROUTING_SYSTEM
        if self.config.provider == "openai":
            return self._openai(turns, message, system)
        return self._anthropic(turns, message, system)

    def _openai(self, turns: List[Dict[str, str]], message: str, system: str) -> str:
        if self._client is None:
            raise RuntimeError("openai SDK is not available")
        response = self._client.responses.create(
            model=self.config.model,
            instructions=system,
            input=[*turns, {"role": "user", "content": message}],
            temperature=0,
            text={"format": {"type": "json_object"}},
            timeout=TIMEOUT_SECONDS,
        )
        return response.output_text

    def _anthropic(self, turns: List[Dict[str, str]], message: str, system: str) -> str:
        response = self.session.post(
            ANTHROPIC_URL,
            headers={
                "x-api-key": self.config.api_key,
                "anthropic-version": ANTHROPIC_VERSION,
                "content-type": "application/json",
            },
            json={
                "model": self.config.model,
                "max_tokens": 256,
                "temperature": 0,
                "system": system,
                "messages": [*turns, {"role": "user", "content": message}],
            },
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json()["content"][0]["text"]

    @staticmethod
    def _strip_fences(text: str) -> str:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0]
        return cleaned.strip()


def build_language_model() -> Optional[HostedLanguageModel]:
    config = resolve_config()
    return HostedLanguageModel(config) if config else None


def model_status() -> str:
    config = resolve_config()
    if config is None:
        return "keyword router (no API key configured)"
    if config.provider == "openai" and _placeholder(os.getenv("OPENAI_MODEL")):
        return f"{config.label} (auto-selected)"
    return config.label


__all__ = [
    "CONNECTED_MARKER",
    "DEFAULT_OPENAI_MODEL",
    "HostedLanguageModel",
    "ModelConfig",
    "PREFERRED_OPENAI_FAMILIES",
    "ROUTING_SYSTEM",
    "build_language_model",
    "model_status",
    "openai_configured",
    "reset_model_cache",
    "resolve_config",
    "resolve_openai_model",
    "select_best_model",
    "test_openai_connection",
]
