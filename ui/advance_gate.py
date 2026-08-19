"""Deterministic gate for UI-authoritative workflow transitions."""

from __future__ import annotations

import logging
from enum import Enum
from typing import Optional

from pydantic import BaseModel

from ui.registry import REGISTRY
from ui.schemas import GenerativeView, UIComponent

logger = logging.getLogger(__name__)


class WorkflowState(str, Enum):
    NEW = "NEW"
    STRATEGY = "STRATEGY"
    RESEARCH = "RESEARCH"
    IMPLEMENTATION = "IMPLEMENTATION"
    OPTIONS_DESIGN = "OPTIONS_DESIGN"
    TRADE_PREVIEW = "TRADE_PREVIEW"


UI_REQUIRED_STATES = frozenset(WorkflowState)


class UIAdvanceGateResult(BaseModel):
    passed: bool
    reason: Optional[str] = None


def component_is_renderable(component: UIComponent) -> bool:
    spec = REGISTRY.get(component.type)
    if spec is None or spec.required_fields - set(component.data):
        return False
    if spec.requires_provenance and not component.provenance:
        return False
    if any(action.type not in spec.allowed_actions for action in component.actions):
        return False
    return True


def ui_advance_gate(
    *,
    previous_state: WorkflowState | str,
    proposed_state: WorkflowState | str,
    view: Optional[GenerativeView],
    project_id: Optional[str] = None,
    project_revision: Optional[int] = None,
) -> UIAdvanceGateResult:
    """Require a valid, hydrated view before a visible state can advance."""
    previous = WorkflowState(previous_state)
    proposed = WorkflowState(proposed_state)
    if proposed is previous:
        _audit(True, previous, proposed, "NO_TRANSITION")
        return UIAdvanceGateResult(passed=True)

    if proposed not in UI_REQUIRED_STATES:
        _audit(True, previous, proposed, "BACKGROUND_STATE")
        return UIAdvanceGateResult(passed=True)

    if view is None:
        reason = "PROSE_ONLY_STATE_ADVANCE_FORBIDDEN"
        _audit(False, previous, proposed, reason)
        return UIAdvanceGateResult(passed=False, reason=reason)

    if not view.components:
        reason = "GENERATIVE_VIEW_HAS_NO_COMPONENTS"
        _audit(False, previous, proposed, reason)
        return UIAdvanceGateResult(passed=False, reason=reason)

    if not any(component_is_renderable(component) for component in view.components):
        reason = "NO_RENDERABLE_UI_COMPONENT"
        _audit(False, previous, proposed, reason)
        return UIAdvanceGateResult(passed=False, reason=reason)

    if project_id is not None and view.project_id != project_id:
        reason = "GENERATIVE_VIEW_PROJECT_MISMATCH"
        _audit(False, previous, proposed, reason)
        return UIAdvanceGateResult(passed=False, reason=reason)

    if project_revision is not None and view.project_revision != project_revision:
        reason = "GENERATIVE_VIEW_REVISION_MISMATCH"
        _audit(False, previous, proposed, reason)
        return UIAdvanceGateResult(passed=False, reason=reason)

    _audit(True, previous, proposed, "VALID_GENERATIVE_VIEW")
    return UIAdvanceGateResult(passed=True)


def _audit(passed: bool, previous: WorkflowState, proposed: WorkflowState, reason: str) -> None:
    logger.info(
        "ui_advance_gate",
        extra={
            "passed": passed,
            "previous_state": previous.value,
            "proposed_state": proposed.value,
            "reason": reason,
        },
    )


class WorkflowTransitionBlocked(RuntimeError):
    def __init__(self, result: UIAdvanceGateResult):
        self.result = result
        super().__init__(result.reason or "UI workflow transition blocked")


__all__ = [
    "UIAdvanceGateResult",
    "UI_REQUIRED_STATES",
    "WorkflowState",
    "WorkflowTransitionBlocked",
    "component_is_renderable",
    "ui_advance_gate",
]
