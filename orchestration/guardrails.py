"""
Orchestration guardrails.

Path: orchestration/guardrails.py

Two invariants are enforced here, both mechanically testable:
  1. No tool exposed to a model may carry EXECUTE capability.
  2. No tool name may collide with a broker/router surface, even by accident.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, Iterable, List


class Capability(str, Enum):
    READ = "READ"
    COMPUTE = "COMPUTE"
    DRAFT = "DRAFT"
    PRESENT = "PRESENT"
    EXECUTE = "EXECUTE"


MODEL_PERMITTED_CAPABILITIES = {
    Capability.READ,
    Capability.COMPUTE,
    Capability.DRAFT,
    Capability.PRESENT,
}

FORBIDDEN_TOOL_NAMES = {
    "place_trade",
    "submit_order",
    "route",
    "execute",
    "execute_transaction",
    "approve",
    "approve_transaction",
    "cancel_order",
    "reset_kill_switch",
}


class GuardrailViolation(RuntimeError):
    pass


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    capability: Capability
    handler: Callable[..., Any]


def assert_model_safe(tools: Iterable[ToolSpec]) -> List[ToolSpec]:
    """Raise unless every tool is safe to hand to a language model."""
    tools = list(tools)
    violations: List[str] = []
    seen: Dict[str, ToolSpec] = {}

    for tool in tools:
        if tool.name in FORBIDDEN_TOOL_NAMES:
            violations.append(f"tool '{tool.name}' is on the forbidden execution surface list")
        if tool.capability not in MODEL_PERMITTED_CAPABILITIES:
            violations.append(f"tool '{tool.name}' carries capability {tool.capability.value}")
        if tool.name in seen:
            violations.append(f"duplicate tool name '{tool.name}'")
        seen[tool.name] = tool

    if violations:
        raise GuardrailViolation("; ".join(violations))
    return tools


__all__ = [
    "Capability",
    "FORBIDDEN_TOOL_NAMES",
    "GuardrailViolation",
    "MODEL_PERMITTED_CAPABILITIES",
    "ToolSpec",
    "assert_model_safe",
]
