"""
Workbench data contracts.

Path: workbench/schemas.py

A chat session is ephemeral; a thesis is not. The workbench is the durable
substrate that survives every session: each idea carries an explicit lifecycle
state, the evidence that moved it, the conditions that would kill it, and the
trades it authorized. State is derived by replaying a hash-chained event log,
so "what did we believe, when, and why" is reconstructible at any timestamp.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from ui.state import UIFieldState


WORKSPACE_SCOPE = "__workspace__"


class IdeaState(str, Enum):
    NASCENT = "NASCENT"
    RESEARCHING = "RESEARCHING"
    EVIDENCED = "EVIDENCED"
    CONTESTED = "CONTESTED"
    CONFIRMED = "CONFIRMED"
    IMPLEMENTED = "IMPLEMENTED"
    INVALIDATED = "INVALIDATED"
    ARCHIVED = "ARCHIVED"


class ProjectState(str, Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    ARCHIVED = "ARCHIVED"


class EventKind(str, Enum):
    SESSION_OPENED = "SESSION_OPENED"
    SESSION_CLOSED = "SESSION_CLOSED"
    PROJECT_CREATED = "PROJECT_CREATED"
    PROJECT_UPDATED = "PROJECT_UPDATED"
    PROJECT_STATE_CHANGED = "PROJECT_STATE_CHANGED"
    ACTION_REQUESTED = "ACTION_REQUESTED"
    ACTION_STATE_CHANGED = "ACTION_STATE_CHANGED"
    THESIS_CREATED = "THESIS_CREATED"
    THESIS_UPDATED = "THESIS_UPDATED"
    STATE_CHANGED = "STATE_CHANGED"
    EVIDENCE_ADDED = "EVIDENCE_ADDED"
    COUNTER_EVIDENCE_ADDED = "COUNTER_EVIDENCE_ADDED"
    WATCH_CONDITION_SET = "WATCH_CONDITION_SET"
    WATCH_CONDITION_BREACHED = "WATCH_CONDITION_BREACHED"
    INTENT_LINKED = "INTENT_LINKED"
    INTENT_STATE_CHANGED = "INTENT_STATE_CHANGED"
    UI_FIELD_CHANGED = "UI_FIELD_CHANGED"
    UI_INTERACTION = "UI_INTERACTION"
    VIEW_PINNED = "VIEW_PINNED"
    NOTE_ADDED = "NOTE_ADDED"


class Project(BaseModel):
    """A durable workstream. Sessions attach to a project; state outlives them."""

    project_id: str
    name: str
    description: Optional[str] = None
    mandate: Optional[str] = None
    state: ProjectState = ProjectState.ACTIVE
    tags: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Evidence(BaseModel):
    evidence_id: str
    thesis_id: str
    claim: str
    stance: Literal["SUPPORTS", "CONTRADICTS"]
    source_uri: Optional[str] = None
    metric: Optional[str] = None
    value: Optional[float] = None
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    recorded_in_session: Optional[str] = None


class WatchCondition(BaseModel):
    """A standing, machine-checkable condition attached to an idea."""

    condition_id: str
    metric: str
    operator: Literal["<", "<=", ">", ">=", "=="]
    threshold: float
    on_breach: Literal["ALERT", "DEMOTE", "INVALIDATE"] = "ALERT"
    description: Optional[str] = None
    breached_at: Optional[datetime] = None

    def evaluate(self, value: float) -> bool:
        return {
            "<": value < self.threshold,
            "<=": value <= self.threshold,
            ">": value > self.threshold,
            ">=": value >= self.threshold,
            "==": value == self.threshold,
        }[self.operator]


class Thesis(BaseModel):
    thesis_id: str
    project_id: str
    title: str
    claim: str
    state: IdeaState = IdeaState.NASCENT
    conviction: float = Field(default=0.0, ge=0.0, le=1.0)
    strategy_module: Optional[str] = None
    universe: List[str] = Field(default_factory=list)
    invalidation_condition: Optional[str] = None
    evidence_ids: List[str] = Field(default_factory=list)
    counter_evidence_ids: List[str] = Field(default_factory=list)
    watch_conditions: List[WatchCondition] = Field(default_factory=list)
    linked_intent_ids: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_touched_session: Optional[str] = None


class PinnedView(BaseModel):
    """A view a user chose to keep. Rehydrated verbatim in any later session."""

    pin_id: str
    thesis_id: Optional[str]
    title: str
    view: Dict[str, Any]
    pinned_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    pinned_in_session: Optional[str] = None


class WorkbenchEvent(BaseModel):
    """Append-only, hash-chained. The chain is the permanence guarantee."""

    event_id: str
    kind: EventKind
    at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    project_id: str = WORKSPACE_SCOPE
    session_id: Optional[str] = None
    actor: str = "SYSTEM"
    subject_id: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    prev_hash: Optional[str] = None
    entry_hash: Optional[str] = None

    def hashable(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "kind": self.kind.value,
            "at": self.at.isoformat(),
            "project_id": self.project_id,
            "session_id": self.session_id,
            "actor": self.actor,
            "subject_id": self.subject_id,
            "payload": self.payload,
            "prev_hash": self.prev_hash,
        }


class WorkbenchState(BaseModel):
    """Materialized projection of the event log at a point in time."""

    projects: Dict[str, Project] = Field(default_factory=dict)
    theses: Dict[str, Thesis] = Field(default_factory=dict)
    evidence: Dict[str, Evidence] = Field(default_factory=dict)
    pins: Dict[str, PinnedView] = Field(default_factory=dict)
    intent_states: Dict[str, str] = Field(default_factory=dict)
    action_states: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    field_states: Dict[str, UIFieldState] = Field(default_factory=dict)
    ui_event_ids: List[str] = Field(default_factory=list)
    notes: List[Dict[str, Any]] = Field(default_factory=list)
    last_event_hash: Optional[str] = None
    event_count: int = 0


class ContinuityBrief(BaseModel):
    """What a brand-new chat session is rehydrated with, scoped to one project."""

    session_id: str
    project_id: str
    project: Optional[Project] = None
    previous_session_id: Optional[str]
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    active_theses: List[Thesis] = Field(default_factory=list)
    open_transactions: Dict[str, str] = Field(default_factory=dict)
    pending_actions: List[Dict[str, Any]] = Field(default_factory=list)
    breached_conditions: List[Dict[str, Any]] = Field(default_factory=list)
    changed_since_last_session: List[Dict[str, Any]] = Field(default_factory=list)
    pinned_views: List[PinnedView] = Field(default_factory=list)
    unresolved_questions: List[str] = Field(default_factory=list)


class ProjectDigest(BaseModel):
    """One row in the cross-project overview: what needs you, and how urgently."""

    project_id: str
    name: str
    state: ProjectState
    active_thesis_count: int = 0
    contested_thesis_count: int = 0
    open_transaction_count: int = 0
    pending_approval_count: int = 0
    breached_condition_count: int = 0
    last_activity_at: Optional[datetime] = None
    needs_attention: bool = False


class WorkspaceBrief(BaseModel):
    """The cross-project landing view: every workstream and what it is waiting on."""

    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    projects: List[ProjectDigest] = Field(default_factory=list)
    total_pending_approvals: int = 0

    @property
    def attention_projects(self) -> List[ProjectDigest]:
        return [p for p in self.projects if p.needs_attention]


__all__ = [
    "ContinuityBrief",
    "EventKind",
    "Evidence",
    "IdeaState",
    "PinnedView",
    "Project",
    "ProjectDigest",
    "ProjectState",
    "Thesis",
    "WORKSPACE_SCOPE",
    "WatchCondition",
    "WorkbenchEvent",
    "WorkbenchState",
    "WorkspaceBrief",
]
