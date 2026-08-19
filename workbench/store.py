"""
Hash-chained, project-scoped workbench event store.

Path: workbench/store.py

One global append-only chain holds every event across every project, so audit
history is a single tamper-evident sequence. Reads are scoped: a projection
filtered to one `project_id` gives that workstream's world, while
`workspace_brief()` gives the cross-project view of what is waiting on a human.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from transactions.schemas import canonical_hash
from ui.state import Persistence, ProjectStateSnapshot, UIEvent, UIEventType, UIFieldState
from workbench.schemas import (
    WORKSPACE_SCOPE,
    ContinuityBrief,
    Evidence,
    EventKind,
    IdeaState,
    PinnedView,
    Project,
    ProjectDigest,
    ProjectState,
    Thesis,
    WatchCondition,
    WorkbenchEvent,
    WorkbenchState,
    WorkspaceBrief,
)

DEFAULT_LOG_PATH = Path("data/workbench/events.jsonl")

ACTIVE_STATES = {
    IdeaState.RESEARCHING,
    IdeaState.EVIDENCED,
    IdeaState.CONTESTED,
    IdeaState.CONFIRMED,
    IdeaState.IMPLEMENTED,
}

CLOSED_TRANSACTION_STATES = {"FILLED", "CANCELLED", "REJECTED", "ERROR", "KILL_SWITCHED"}

_IDEA_TRANSITIONS: Dict[IdeaState, set] = {
    IdeaState.NASCENT: {IdeaState.RESEARCHING, IdeaState.ARCHIVED},
    IdeaState.RESEARCHING: {IdeaState.EVIDENCED, IdeaState.CONTESTED, IdeaState.INVALIDATED, IdeaState.ARCHIVED},
    IdeaState.EVIDENCED: {IdeaState.CONFIRMED, IdeaState.CONTESTED, IdeaState.INVALIDATED, IdeaState.ARCHIVED},
    IdeaState.CONTESTED: {IdeaState.EVIDENCED, IdeaState.RESEARCHING, IdeaState.INVALIDATED, IdeaState.ARCHIVED},
    IdeaState.CONFIRMED: {IdeaState.IMPLEMENTED, IdeaState.CONTESTED, IdeaState.INVALIDATED, IdeaState.ARCHIVED},
    IdeaState.IMPLEMENTED: {IdeaState.CONTESTED, IdeaState.INVALIDATED, IdeaState.ARCHIVED},
    IdeaState.INVALIDATED: {IdeaState.ARCHIVED},
    IdeaState.ARCHIVED: set(),
}

_PROJECT_TRANSITIONS: Dict[ProjectState, set] = {
    ProjectState.ACTIVE: {ProjectState.PAUSED, ProjectState.ARCHIVED},
    ProjectState.PAUSED: {ProjectState.ACTIVE, ProjectState.ARCHIVED},
    ProjectState.ARCHIVED: set(),
}


class ChainIntegrityError(RuntimeError):
    pass


class IllegalIdeaTransition(ValueError):
    pass


class IllegalProjectTransition(ValueError):
    pass


class WorkbenchStore:
    def __init__(self, log_path: Path | str = DEFAULT_LOG_PATH):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    # -- write path --------------------------------------------------------

    def append(
        self,
        kind: EventKind,
        *,
        project_id: str = WORKSPACE_SCOPE,
        session_id: Optional[str] = None,
        actor: str = "SYSTEM",
        subject_id: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> WorkbenchEvent:
        prev_hash = self._last_hash()
        event = WorkbenchEvent(
            event_id=str(uuid.uuid4()),
            kind=kind,
            project_id=project_id,
            session_id=session_id,
            actor=actor,
            subject_id=subject_id,
            payload=payload or {},
            prev_hash=prev_hash,
        )
        event.entry_hash = canonical_hash(event.hashable())
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(event.model_dump_json() + "\n")
        return event

    def create_project(
        self,
        *,
        name: str,
        project_id: Optional[str] = None,
        description: Optional[str] = None,
        mandate: Optional[str] = None,
        tags: Optional[List[str]] = None,
        actor: str = "USER",
    ) -> Project:
        project = Project(
            project_id=project_id or str(uuid.uuid4()),
            name=name,
            description=description,
            mandate=mandate,
            tags=tags or [],
        )
        self.append(
            EventKind.PROJECT_CREATED,
            project_id=project.project_id,
            actor=actor,
            subject_id=project.project_id,
            payload=project.model_dump(mode="json"),
        )
        return project

    def set_project_state(
        self,
        project_id: str,
        state: ProjectState,
        *,
        actor: str = "USER",
        reason: Optional[str] = None,
    ) -> Project:
        self.append(
            EventKind.PROJECT_STATE_CHANGED,
            project_id=project_id,
            actor=actor,
            subject_id=project_id,
            payload={"state": state.value, "reason": reason},
        )
        return self.projection(project_id=project_id).projects[project_id]

    # -- read path ---------------------------------------------------------

    def events(
        self,
        *,
        project_id: Optional[str] = None,
        until: Optional[datetime] = None,
    ) -> List[WorkbenchEvent]:
        if not self.log_path.exists():
            return []
        out: List[WorkbenchEvent] = []
        with self.log_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                event = WorkbenchEvent.model_validate_json(line)
                if until is not None and event.at > until:
                    break
                if project_id is not None and event.project_id != project_id:
                    continue
                out.append(event)
        return out

    def verify_chain(self) -> bool:
        """Integrity is checked over the whole chain, never a project slice."""
        prev: Optional[str] = None
        for event in self.events():
            if event.prev_hash != prev:
                raise ChainIntegrityError(f"broken chain at {event.event_id}")
            if event.entry_hash != canonical_hash(event.hashable()):
                raise ChainIntegrityError(f"tampered event {event.event_id}")
            prev = event.entry_hash
        return True

    def projection(
        self,
        *,
        project_id: Optional[str] = None,
        until: Optional[datetime] = None,
    ) -> WorkbenchState:
        return reduce_events(self.events(project_id=project_id, until=until))

    def list_projects(self, *, include_archived: bool = False) -> List[Project]:
        projects = list(self.projection().projects.values())
        if include_archived:
            return projects
        return [p for p in projects if p.state is not ProjectState.ARCHIVED]

    def _last_hash(self) -> Optional[str]:
        events = self.events()
        return events[-1].entry_hash if events else None

    # -- session continuity ------------------------------------------------

    def open_session(
        self,
        *,
        project_id: str,
        actor: str = "USER",
        session_id: Optional[str] = None,
    ) -> ContinuityBrief:
        """Start a chat session inside a project and rehydrate that project's state."""
        session_id = session_id or str(uuid.uuid4())
        previous = self._last_session_id(project_id)
        cutoff = self._session_opened_at(project_id, previous) if previous else None

        state = self.projection(project_id=project_id)
        self.append(
            EventKind.SESSION_OPENED,
            project_id=project_id,
            session_id=session_id,
            actor=actor,
            payload={"previous_session_id": previous},
        )

        changed = [
            {
                "at": event.at.isoformat(),
                "kind": event.kind.value,
                "subject_id": event.subject_id,
                "summary": _summarize(event),
            }
            for event in self.events(project_id=project_id)
            if cutoff is not None and event.at > cutoff and event.kind is not EventKind.SESSION_OPENED
        ]

        return ContinuityBrief(
            session_id=session_id,
            project_id=project_id,
            project=state.projects.get(project_id),
            previous_session_id=previous,
            active_theses=[t for t in state.theses.values() if t.state in ACTIVE_STATES],
            open_transactions=open_transactions(state),
            pending_actions=pending_actions(state),
            breached_conditions=breached_conditions(state),
            changed_since_last_session=changed,
            pinned_views=list(state.pins.values()),
            unresolved_questions=[n["text"] for n in state.notes if n.get("kind") == "OPEN_QUESTION"],
        )

    def workspace_brief(self, *, include_archived: bool = False) -> WorkspaceBrief:
        """Cross-project overview: which workstreams are blocked on a human."""
        digests: List[ProjectDigest] = []
        total_pending = 0

        for project in self.list_projects(include_archived=include_archived):
            events = self.events(project_id=project.project_id)
            state = reduce_events(events)
            pending = pending_actions(state)
            open_txns = open_transactions(state)
            breached = breached_conditions(state)
            contested = [t for t in state.theses.values() if t.state is IdeaState.CONTESTED]
            awaiting_txns = [s for s in open_txns.values() if s == "AWAITING_APPROVAL"]
            total_pending += len(pending) + len(awaiting_txns)

            digests.append(
                ProjectDigest(
                    project_id=project.project_id,
                    name=project.name,
                    state=project.state,
                    active_thesis_count=len([t for t in state.theses.values() if t.state in ACTIVE_STATES]),
                    contested_thesis_count=len(contested),
                    open_transaction_count=len(open_txns),
                    pending_approval_count=len(pending) + len(awaiting_txns),
                    breached_condition_count=len(breached),
                    last_activity_at=events[-1].at if events else None,
                    needs_attention=bool(pending or awaiting_txns or breached or contested),
                )
            )

        digests.sort(key=lambda d: (not d.needs_attention, -d.pending_approval_count, d.name))
        return WorkspaceBrief(projects=digests, total_pending_approvals=total_pending)

    def record_ui_event(self, event: UIEvent) -> UIFieldState | None:
        """Persist an interaction. Field changes become authoritative project state.

        Idempotent on `event_id`: a retried delivery from a remote host must not
        append a second revision.
        """
        projected = self.projection(project_id=event.project_id)
        if event.event_id in projected.ui_event_ids:
            return projected.field_states.get(event.field_id or "")

        if event.event_type is UIEventType.FIELD_CHANGED and event.field_id:
            self.append(
                EventKind.UI_FIELD_CHANGED,
                project_id=event.project_id,
                session_id=event.session_id,
                actor=event.actor,
                subject_id=event.view_id,
                payload={
                    "event_id": event.event_id,
                    "field_id": event.field_id,
                    "value": event.value,
                    "persistence": event.persistence.value,
                    "view_id": event.view_id,
                },
            )
            return self.projection(project_id=event.project_id).field_states.get(event.field_id)

        self.append(
            EventKind.UI_INTERACTION,
            project_id=event.project_id,
            session_id=event.session_id,
            actor=event.actor,
            subject_id=event.view_id,
            payload={
                "event_id": event.event_id,
                "event_type": event.event_type.value,
                "action": event.action,
                "field_id": event.field_id,
                "value": event.value,
            },
        )
        return None

    def project_state(
        self, project_id: str, *, session_id: Optional[str] = None
    ) -> ProjectStateSnapshot:
        """Authoritative state for a project, as handed to the model and to hydration."""
        state = self.projection(project_id=project_id)
        project = state.projects.get(project_id)

        fields = {
            field_id: field
            for field_id, field in state.field_states.items()
            # Session-scoped values belong to the session that set them.
            if field.persistence is Persistence.PROJECT
            or session_id is None
            or field.updated_in_session == session_id
        }

        return ProjectStateSnapshot(
            project_id=project_id,
            project_name=project.name if project else None,
            session_id=session_id,
            revision=state.event_count,
            fields=fields,
            theses=[
                {"thesis_id": t.thesis_id, "title": t.title, "state": t.state.value}
                for t in state.theses.values()
                if t.state in ACTIVE_STATES
            ],
            open_transactions=open_transactions(state),
            pending_actions=[a["request_id"] for a in pending_actions(state)],
            breached_conditions=[c["condition_id"] for c in breached_conditions(state)],
        )

    def evaluate_watch_conditions(
        self,
        metrics: Dict[str, float],
        *,
        project_id: str,
        session_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Apply standing conditions to fresh metrics; breaches demote ideas deterministically."""
        state = self.projection(project_id=project_id)
        breaches: List[Dict[str, Any]] = []
        for thesis in state.theses.values():
            for condition in thesis.watch_conditions:
                if condition.breached_at is not None or condition.metric not in metrics:
                    continue
                value = metrics[condition.metric]
                if not condition.evaluate(value):
                    continue
                self.append(
                    EventKind.WATCH_CONDITION_BREACHED,
                    project_id=project_id,
                    session_id=session_id,
                    subject_id=thesis.thesis_id,
                    payload={"condition_id": condition.condition_id, "value": value},
                )
                if condition.on_breach in {"DEMOTE", "INVALIDATE"}:
                    target = IdeaState.INVALIDATED if condition.on_breach == "INVALIDATE" else IdeaState.CONTESTED
                    if target in _IDEA_TRANSITIONS[thesis.state]:
                        self.append(
                            EventKind.STATE_CHANGED,
                            project_id=project_id,
                            session_id=session_id,
                            subject_id=thesis.thesis_id,
                            payload={"state": target.value, "reason": f"watch:{condition.condition_id}"},
                        )
                breaches.append(
                    {"thesis_id": thesis.thesis_id, "condition_id": condition.condition_id, "value": value}
                )
        return breaches

    def _last_session_id(self, project_id: str) -> Optional[str]:
        for event in reversed(self.events(project_id=project_id)):
            if event.kind is EventKind.SESSION_OPENED:
                return event.session_id
        return None

    def _session_opened_at(self, project_id: str, session_id: str) -> Optional[datetime]:
        for event in self.events(project_id=project_id):
            if event.kind is EventKind.SESSION_OPENED and event.session_id == session_id:
                return event.at
        return None


def reduce_events(events: Iterable[WorkbenchEvent]) -> WorkbenchState:
    state = WorkbenchState()
    for event in events:
        _apply(state, event)
        state.last_event_hash = event.entry_hash
        state.event_count += 1
    return state


def open_transactions(state: WorkbenchState) -> Dict[str, str]:
    return {
        intent_id: intent_state
        for intent_id, intent_state in state.intent_states.items()
        if intent_state not in CLOSED_TRANSACTION_STATES
    }


def pending_actions(state: WorkbenchState) -> List[Dict[str, Any]]:
    return [record for record in state.action_states.values() if record.get("state") == "AWAITING_APPROVAL"]


def breached_conditions(state: WorkbenchState) -> List[Dict[str, Any]]:
    return [
        {
            "thesis_id": thesis.thesis_id,
            "condition_id": condition.condition_id,
            "metric": condition.metric,
            "threshold": condition.threshold,
            "on_breach": condition.on_breach,
            "breached_at": condition.breached_at.isoformat() if condition.breached_at else None,
        }
        for thesis in state.theses.values()
        for condition in thesis.watch_conditions
        if condition.breached_at is not None
    ]


def _apply(state: WorkbenchState, event: WorkbenchEvent) -> None:
    kind = event.kind
    payload = event.payload

    if kind is EventKind.PROJECT_CREATED:
        project = Project.model_validate(payload)
        state.projects[project.project_id] = project

    elif kind is EventKind.PROJECT_UPDATED:
        project = _require_project(state, event)
        for key, value in payload.items():
            if key in {"project_id", "state", "created_at"}:
                continue
            if hasattr(project, key):
                setattr(project, key, value)
        project.updated_at = event.at

    elif kind is EventKind.PROJECT_STATE_CHANGED:
        project = _require_project(state, event)
        target = ProjectState(payload["state"])
        if target not in _PROJECT_TRANSITIONS[project.state]:
            raise IllegalProjectTransition(f"{project.state.value} -> {target.value} for {project.project_id}")
        project.state = target
        project.updated_at = event.at

    elif kind is EventKind.THESIS_CREATED:
        thesis = Thesis.model_validate(payload)
        thesis.last_touched_session = event.session_id
        state.theses[thesis.thesis_id] = thesis

    elif kind is EventKind.THESIS_UPDATED:
        thesis = _require_thesis(state, event)
        for key, value in payload.items():
            if key in {"thesis_id", "project_id", "state", "created_at"}:
                continue
            if hasattr(thesis, key):
                setattr(thesis, key, value)
        _touch(thesis, event)

    elif kind is EventKind.STATE_CHANGED:
        thesis = _require_thesis(state, event)
        target = IdeaState(payload["state"])
        if target not in _IDEA_TRANSITIONS[thesis.state]:
            raise IllegalIdeaTransition(f"{thesis.state.value} -> {target.value} for {thesis.thesis_id}")
        thesis.state = target
        _touch(thesis, event)

    elif kind in {EventKind.EVIDENCE_ADDED, EventKind.COUNTER_EVIDENCE_ADDED}:
        evidence = Evidence.model_validate(payload)
        evidence.recorded_in_session = event.session_id
        state.evidence[evidence.evidence_id] = evidence
        thesis = _require_thesis(state, event)
        bucket = thesis.evidence_ids if kind is EventKind.EVIDENCE_ADDED else thesis.counter_evidence_ids
        if evidence.evidence_id not in bucket:
            bucket.append(evidence.evidence_id)
        _touch(thesis, event)

    elif kind is EventKind.WATCH_CONDITION_SET:
        thesis = _require_thesis(state, event)
        condition = WatchCondition.model_validate(payload)
        thesis.watch_conditions = [c for c in thesis.watch_conditions if c.condition_id != condition.condition_id]
        thesis.watch_conditions.append(condition)
        _touch(thesis, event)

    elif kind is EventKind.WATCH_CONDITION_BREACHED:
        thesis = _require_thesis(state, event)
        for condition in thesis.watch_conditions:
            if condition.condition_id == payload.get("condition_id"):
                condition.breached_at = event.at
        _touch(thesis, event)

    elif kind is EventKind.INTENT_LINKED:
        thesis = _require_thesis(state, event)
        intent_id = payload["intent_id"]
        if intent_id not in thesis.linked_intent_ids:
            thesis.linked_intent_ids.append(intent_id)
        state.intent_states.setdefault(intent_id, payload.get("state", "DRAFT"))
        _touch(thesis, event)

    elif kind is EventKind.INTENT_STATE_CHANGED:
        state.intent_states[payload["intent_id"]] = payload["state"]

    elif kind is EventKind.UI_FIELD_CHANGED:
        if payload.get("event_id"):
            state.ui_event_ids.append(payload["event_id"])
        field_id = payload["field_id"]
        previous = state.field_states.get(field_id)
        state.field_states[field_id] = UIFieldState(
            field_id=field_id,
            value=payload.get("value"),
            persistence=Persistence(payload.get("persistence", Persistence.PROJECT.value)),
            revision=(previous.revision + 1) if previous else 1,
            updated_at=event.at,
            updated_by=event.actor,
            updated_in_session=event.session_id,
        )

    elif kind is EventKind.ACTION_REQUESTED:
        state.action_states[payload["request_id"]] = {
            "request_id": payload["request_id"],
            "kind": payload.get("kind"),
            "title": payload.get("title"),
            "risk_tier": payload.get("risk_tier"),
            "state": payload.get("state", "DRAFT"),
        }

    elif kind is EventKind.ACTION_STATE_CHANGED:
        record = state.action_states.setdefault(payload["request_id"], {"request_id": payload["request_id"]})
        record["state"] = payload["state"]

    elif kind is EventKind.UI_INTERACTION:
        if payload.get("event_id"):
            state.ui_event_ids.append(payload["event_id"])

    elif kind is EventKind.VIEW_PINNED:
        pin = PinnedView.model_validate(payload)
        pin.pinned_in_session = event.session_id
        state.pins[pin.pin_id] = pin

    elif kind is EventKind.NOTE_ADDED:
        state.notes.append({**payload, "session_id": event.session_id, "at": event.at.isoformat()})

def _require_project(state: WorkbenchState, event: WorkbenchEvent) -> Project:
    project = state.projects.get(event.subject_id or "")
    if project is None:
        raise KeyError(f"event {event.event_id} references unknown project {event.subject_id}")
    return project


def _require_thesis(state: WorkbenchState, event: WorkbenchEvent) -> Thesis:
    thesis = state.theses.get(event.subject_id or "")
    if thesis is None:
        raise KeyError(f"event {event.event_id} references unknown thesis {event.subject_id}")
    return thesis


def _touch(thesis: Thesis, event: WorkbenchEvent) -> None:
    thesis.updated_at = event.at
    thesis.last_touched_session = event.session_id or thesis.last_touched_session


def _summarize(event: WorkbenchEvent) -> str:
    payload = event.payload
    if event.kind is EventKind.STATE_CHANGED:
        return f"state -> {payload.get('state')} ({payload.get('reason', 'manual')})"
    if event.kind in {EventKind.EVIDENCE_ADDED, EventKind.COUNTER_EVIDENCE_ADDED}:
        return str(payload.get("claim", ""))[:200]
    if event.kind is EventKind.INTENT_STATE_CHANGED:
        return f"{payload.get('intent_id')} -> {payload.get('state')}"
    if event.kind is EventKind.ACTION_STATE_CHANGED:
        return f"{payload.get('request_id')} -> {payload.get('state')}"
    if event.kind is EventKind.WATCH_CONDITION_BREACHED:
        return f"{payload.get('condition_id')} breached at {payload.get('value')}"
    return event.kind.value


__all__ = [
    "ACTIVE_STATES",
    "ChainIntegrityError",
    "IllegalIdeaTransition",
    "IllegalProjectTransition",
    "WorkbenchStore",
    "breached_conditions",
    "open_transactions",
    "pending_actions",
    "reduce_events",
]
