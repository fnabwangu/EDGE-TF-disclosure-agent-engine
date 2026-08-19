"""
Generative UI state contract.

Path: ui/state.py

`GenerativeView` is a render contract: it says what to draw. This is the
companion state contract: what the user has entered, and what they just
changed. Without it a rendered control holds its value only in browser memory,
so anything typed into a generated panel is lost the moment the panel is
replaced - and is never visible to the model on the next turn.

The rule the renderer follows:

    Never create a control carrying a semantic value that exists only in
    browser memory.

Two persistence levels, because they have different lifetimes:

    SESSION  transient interaction state - sort order, expanded panel
    PROJECT  semantic state - dates, assumptions, thesis edits, decisions
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Persistence(str, Enum):
    SESSION = "SESSION"
    PROJECT = "PROJECT"


class FieldKind(str, Enum):
    TEXT = "TEXT"
    DATE = "DATE"
    NUMBER = "NUMBER"
    CHOICE = "CHOICE"
    BOOLEAN = "BOOLEAN"


class UIEventType(str, Enum):
    FIELD_CHANGED = "FIELD_CHANGED"
    ACTION_CLICKED = "ACTION_CLICKED"
    SELECTION_CHANGED = "SELECTION_CHANGED"
    SUBMITTED = "SUBMITTED"
    DISMISSED = "DISMISSED"


class FieldSpec(BaseModel):
    """A control a component declares. The renderer draws it; it does not invent it."""

    field_id: str
    label: str
    kind: FieldKind = FieldKind.TEXT
    persistence: Persistence = Persistence.PROJECT
    options: List[str] = Field(default_factory=list)
    placeholder: Optional[str] = None
    help: Optional[str] = None
    required: bool = False


class UIFieldState(BaseModel):
    field_id: str
    value: Any = None
    persistence: Persistence = Persistence.PROJECT
    revision: int = 0
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_by: Optional[str] = None
    updated_in_session: Optional[str] = None

    @property
    def is_set(self) -> bool:
        return self.value not in (None, "")


class UIEvent(BaseModel):
    """A user interaction, persisted before it can affect anything."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    view_id: str
    project_id: str
    session_id: Optional[str] = None
    event_type: UIEventType
    field_id: Optional[str] = None
    value: Any = None
    action: Optional[str] = None
    persistence: Persistence = Persistence.PROJECT
    actor: str = "USER"
    at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def field_changed(
        cls,
        *,
        view_id: str,
        project_id: str,
        field_id: str,
        value: Any,
        session_id: Optional[str] = None,
        persistence: Persistence = Persistence.PROJECT,
        actor: str = "USER",
    ) -> "UIEvent":
        return cls(
            view_id=view_id,
            project_id=project_id,
            session_id=session_id,
            event_type=UIEventType.FIELD_CHANGED,
            field_id=field_id,
            value=value,
            persistence=persistence,
            actor=actor,
        )


class ProjectStateSnapshot(BaseModel):
    """The authoritative state handed to the model and used to hydrate views."""

    project_id: str
    project_name: Optional[str] = None
    session_id: Optional[str] = None
    phase: Optional[str] = None
    fields: Dict[str, UIFieldState] = Field(default_factory=dict)
    theses: List[Dict[str, Any]] = Field(default_factory=list)
    open_transactions: Dict[str, str] = Field(default_factory=dict)
    pending_actions: List[str] = Field(default_factory=list)
    breached_conditions: List[str] = Field(default_factory=list)

    def value(self, field_id: str, default: Any = None) -> Any:
        state = self.fields.get(field_id)
        return state.value if state is not None and state.is_set else default

    def as_context(self) -> str:
        """Rendered into the model's context so entered values survive the turn."""
        lines = [
            "ACTIVE PROJECT STATE",
            f"Project: {self.project_name or self.project_id}",
        ]
        if self.phase:
            lines.append(f"Phase: {self.phase}")

        entered = {k: v for k, v in sorted(self.fields.items()) if v.is_set}
        if entered:
            lines.append("Entered by the user:")
            lines.extend(f"  {field_id} = {state.value}" for field_id, state in entered.items())

        if self.theses:
            lines.append("Theses:")
            lines.extend(f"  {t.get('state')} {t.get('title')}" for t in self.theses)
        if self.open_transactions:
            lines.append(f"Open transactions: {self.open_transactions}")
        if self.pending_actions:
            lines.append(f"Awaiting approval: {', '.join(self.pending_actions)}")
        if self.breached_conditions:
            lines.append(f"Breached watch conditions: {', '.join(self.breached_conditions)}")
        return "\n".join(lines)


__all__ = [
    "FieldKind",
    "FieldSpec",
    "Persistence",
    "ProjectStateSnapshot",
    "UIEvent",
    "UIEventType",
    "UIFieldState",
]
