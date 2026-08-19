"""
Generative UI schema.

Path: ui/schemas.py

The model composes a *view*, not markup. It may only emit component types that
exist in the registry, and it may only emit actions that the registry marks as
permitted for its role. This is what makes "generative presentation" safe while
keeping "generative authorization" impossible.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class ComponentType(str, Enum):
    METRIC = "metric"
    TABLE = "table"
    CHART = "chart"
    SIGNAL_CARD = "signal_card"
    EVIDENCE_CARD = "evidence_card"
    COUNTER_THESIS_PANEL = "counter_thesis_panel"
    IAV_GAUGE = "iav_gauge"
    ADOPTION_CURVE = "adoption_curve"
    MANAGER_BREADTH_GRAPH = "manager_breadth_graph"
    HOLDINGS_DELTA_TABLE = "holdings_delta_table"
    AQD_WATERFALL = "aqd_waterfall"
    EVIDENCE_TIMELINE = "evidence_timeline"
    SCENARIO_TREE = "scenario_tree"
    ETF_IMPLEMENTATION_COMPARISON = "etf_implementation_comparison"
    RISK_BUDGET_PANEL = "risk_budget_panel"
    TRADE_TICKET = "trade_ticket"
    APPROVAL_PANEL = "approval_panel"
    ACTION_APPROVAL_PANEL = "action_approval_panel"
    APPROVAL_INBOX = "approval_inbox"
    PROJECT_SWITCHER = "project_switcher"
    PROJECT_CARD = "project_card"
    CONTINUITY_BRIEF = "continuity_brief"
    FUNNEL_RAIL = "funnel_rail"
    STRATEGY_CANDIDATES = "strategy_candidates"
    AUDIT_TRAIL = "audit_trail"
    THESIS_TIMELINE = "thesis_timeline"
    STATE_DIFF = "state_diff"


class ActionType(str, Enum):
    """Actions a rendered component may offer. Execution is not among them."""

    OPEN_EVIDENCE = "open_evidence"
    DRILL_DOWN = "drill_down"
    RUN_SCENARIO = "run_scenario"
    DRAFT_INTENT = "draft_intent"
    REQUEST_PREVIEW = "request_preview"
    REQUEST_APPROVAL = "request_approval"
    MODIFY_INTENT = "modify_intent"
    REJECT_INTENT = "reject_intent"
    PIN_TO_WORKBENCH = "pin_to_workbench"
    PROPOSE_ACTION = "propose_action"
    CANCEL_ACTION = "cancel_action"
    SWITCH_PROJECT = "switch_project"
    RESUME_THREAD = "resume_thread"
    SYNTHESIZE_DISCLOSURES = "synthesize_disclosures"
    OPEN_THESIS = "open_thesis"


class UIAction(BaseModel):
    type: ActionType
    label: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    # Approval actions must carry the hash the user actually saw.
    binds_intent_hash: Optional[str] = None
    binds_action_hash: Optional[str] = None


class UIComponent(BaseModel):
    type: ComponentType
    title: str
    data: Dict[str, Any] = Field(default_factory=dict)
    actions: List[UIAction] = Field(default_factory=list)
    provenance: List[str] = Field(default_factory=list)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class GenerativeView(BaseModel):
    """A renderable answer. Every number in it must be traceable to a tool call."""

    view_id: str
    title: str
    summary: Optional[str] = None
    components: List[UIComponent] = Field(default_factory=list)
    project_id: Optional[str] = None
    session_id: Optional[str] = None
    thesis_id: Optional[str] = None
    surface: Literal["WEB", "CHAT_APP", "API", "CONSOLE"] = "WEB"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    tool_calls: List[str] = Field(default_factory=list)


__all__ = ["ActionType", "ComponentType", "GenerativeView", "UIAction", "UIComponent"]
