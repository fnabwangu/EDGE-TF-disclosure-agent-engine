"""
Language model adapters.

Path: orchestration/llm.py

Fills the `LanguageModel` seam. The model is used for one job only - mapping a
free-text message onto a known Intent and its arguments. It never sees tool
results, never produces numbers, and never emits an approval. If no API key is
configured, `build_language_model` returns None and the agent falls back to
deterministic keyword routing.

Uses `requests` (already a dependency) rather than a vendor SDK.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests

from core.env import ensure_env_loaded

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
TIMEOUT_SECONDS = 20

ROUTING_SYSTEM = """You route messages for EDGE-TF, an institutional ETF disclosure engine.

Reply with ONLY a JSON object: {"intent": "<name>", "args": {...}}

Intents:
- generate        args: {"query": "<the theme or subject>"}   find strategy candidates
- synthesize      args: {"query": "..."} or {"strategy_id": "theme:function"}  run disclosure synthesis
- open_thesis     args: {"query": "..."}   make the current idea durable
- design_trade    args: {"query": "..."}   size and price an implementation
- catalyst        args: {"query": "...", "stance": "HAWKISH|DOVISH|VOLATILITY"}  a DATED macro event
                  (FOMC, Jackson Hole, CPI, payrolls, elections) rather than an adoption theme
- proceed         args: {}   a bare continuation such as "go", "continue", "do it" - resume from
                  whatever the project state already holds
- inbox           args: {}   what needs a human decision
- continuity      args: {}   what carried over from previous sessions
- board           args: {}   pipeline status
- help            args: {}

Rules:
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


def resolve_config() -> Optional[ModelConfig]:
    ensure_env_loaded()

    openai_key = os.getenv("OPENAI_API_KEY")
    if not _placeholder(openai_key):
        return ModelConfig("openai", os.getenv("OPENAI_MODEL", "gpt-4o"), openai_key)

    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if not _placeholder(anthropic_key):
        return ModelConfig(
            "anthropic", os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"), anthropic_key
        )
    return None


class HostedLanguageModel:
    """Routes a message to an Intent using a hosted chat model."""

    def __init__(self, config: ModelConfig, *, session: Optional[requests.Session] = None):
        self.config = config
        self.session = session or requests.Session()

    def route(self, message: str, *, history: List[Any], intents: List[str], context: str = ""):
        from orchestration.agent import Intent  # imported here to avoid a cycle

        try:
            raw = self._complete(message, history, context)
        except (requests.RequestException, ValueError, KeyError):
            return None

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
        response = self.session.post(
            OPENAI_URL,
            headers={"Authorization": f"Bearer {self.config.api_key}"},
            json={
                "model": self.config.model,
                "temperature": 0,
                "response_format": {"type": "json_object"},
                "messages": [{"role": "system", "content": system}, *turns, {"role": "user", "content": message}],
            },
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

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
    return config.label if config else "keyword router (no API key configured)"


__all__ = [
    "HostedLanguageModel",
    "ModelConfig",
    "ROUTING_SYSTEM",
    "build_language_model",
    "model_status",
    "resolve_config",
]
