"""
Model-facing tool registry.

Path: orchestration/tool_registry.py

The complete set of things a language model may do. Tools are bound to one
project and one session at construction time, so the model cannot reach across
projects except through the explicitly read-only workspace overview.

Approval and execution - for trades and for workflow actions alike - are
absent by construction and enforced by `assert_model_safe`.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from approvals.schemas import ActionKind, ActionRequest, RiskTier
from approvals.service import ApprovalService
from orchestration.guardrails import Capability, ToolSpec, assert_model_safe
from transactions.schemas import TradeIntent
from transactions.service import TransactionService
from transactions.validator import validate_intent
from ui.registry import (
    action_approval_panel,
    approval_inbox,
    approval_panel,
    component_catalog,
    project_switcher,
)
from workbench.schemas import EventKind, Evidence, IdeaState, PinnedView, Thesis, WatchCondition
from workbench.store import WorkbenchStore


def build_tools(
    *,
    transactions: TransactionService,
    approvals: ApprovalService,
    workbench: WorkbenchStore,
    project_id: str,
    session_id: str,
    user_id: str,
) -> List[ToolSpec]:
    def _append(kind: EventKind, **kwargs: Any):
        return workbench.append(kind, project_id=project_id, session_id=session_id, actor=user_id, **kwargs)

    def get_component_catalog() -> Dict[str, Any]:
        """Return the renderable component vocabulary a view must be built from."""
        return component_catalog()

    def get_workspace_overview() -> Dict[str, Any]:
        """Read-only cross-project digest: which workstreams are waiting on a human."""
        brief = workbench.workspace_brief()
        return {
            "brief": brief.model_dump(mode="json"),
            "component": project_switcher(brief).model_dump(mode="json"),
        }

    def get_current_project() -> Dict[str, Any]:
        """Describe the project this session is bound to."""
        state = workbench.projection(project_id=project_id)
        project = state.projects.get(project_id)
        return project.model_dump(mode="json") if project else {"project_id": project_id}

    def list_theses() -> List[Dict[str, Any]]:
        """List durable theses in this project, carried over from earlier sessions."""
        state = workbench.projection(project_id=project_id)
        return [t.model_dump(mode="json") for t in state.theses.values()]

    def get_thesis(thesis_id: str) -> Dict[str, Any]:
        """Return one thesis with its evidence and standing watch conditions."""
        state = workbench.projection(project_id=project_id)
        thesis = state.theses[thesis_id]
        return {
            "thesis": thesis.model_dump(mode="json"),
            "evidence": [
                state.evidence[e].model_dump(mode="json")
                for e in thesis.evidence_ids + thesis.counter_evidence_ids
                if e in state.evidence
            ],
        }

    def create_thesis(
        title: str, claim: str, universe: Optional[List[str]] = None, invalidation_condition: Optional[str] = None
    ) -> Dict[str, Any]:
        """Open a durable idea in this project. It outlives this conversation."""
        thesis = Thesis(
            thesis_id=str(uuid.uuid4()),
            project_id=project_id,
            title=title,
            claim=claim,
            universe=universe or [],
            invalidation_condition=invalidation_condition,
        )
        _append(EventKind.THESIS_CREATED, subject_id=thesis.thesis_id, payload=thesis.model_dump(mode="json"))
        _append(
            EventKind.STATE_CHANGED,
            subject_id=thesis.thesis_id,
            payload={"state": IdeaState.RESEARCHING.value, "reason": "opened for research"},
        )
        return {"thesis_id": thesis.thesis_id}

    def record_evidence(
        thesis_id: str,
        claim: str,
        stance: str,
        source_uri: Optional[str] = None,
        metric: Optional[str] = None,
        value: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Attach supporting or contradicting evidence to a thesis, permanently."""
        evidence = Evidence(
            evidence_id=str(uuid.uuid4()),
            thesis_id=thesis_id,
            claim=claim,
            stance="CONTRADICTS" if stance.upper().startswith("CONTRA") else "SUPPORTS",
            source_uri=source_uri,
            metric=metric,
            value=value,
        )
        kind = EventKind.EVIDENCE_ADDED if evidence.stance == "SUPPORTS" else EventKind.COUNTER_EVIDENCE_ADDED
        _append(kind, subject_id=thesis_id, payload=evidence.model_dump(mode="json"))
        return evidence.model_dump(mode="json")

    def set_watch_condition(
        thesis_id: str,
        metric: str,
        operator: str,
        threshold: float,
        on_breach: str = "ALERT",
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Attach a standing, machine-checkable invalidation trigger to a thesis."""
        condition = WatchCondition(
            condition_id=str(uuid.uuid4()),
            metric=metric,
            operator=operator,
            threshold=threshold,
            on_breach=on_breach,
            description=description,
        )
        _append(EventKind.WATCH_CONDITION_SET, subject_id=thesis_id, payload=condition.model_dump(mode="json"))
        return condition.model_dump(mode="json")

    def draft_trade_intent(intent: Dict[str, Any]) -> Dict[str, Any]:
        """Compose a DRAFT TradeIntent. Drafting is not authorization."""
        payload = dict(intent)
        payload.setdefault("intent_id", str(uuid.uuid4()))
        payload["generated_by"] = "EDGE_TF"
        parsed = TradeIntent.model_validate(payload)
        record = transactions.register_draft(parsed)
        _append(
            EventKind.INTENT_LINKED,
            subject_id=parsed.thesis_id,
            payload={"intent_id": parsed.intent_id, "state": record.state.value},
        )
        return {"intent_id": parsed.intent_id, "state": record.state.value}

    def check_intent_completeness(intent_id: str) -> Dict[str, Any]:
        """Report which mandatory fields are still missing, for UI highlighting."""
        result = validate_intent(transactions.get(intent_id).intent)
        return result.model_dump(mode="json") | {"missing_fields": result.missing_fields}

    def request_preview(intent_id: str, strategy_state: str = "UNKNOWN") -> Dict[str, Any]:
        """Ask the deterministic core to price, risk-check and hash a trade preview."""
        record = transactions.create_preview(intent_id, user_id=user_id, strategy_state=strategy_state)
        _append(EventKind.INTENT_STATE_CHANGED, payload={"intent_id": intent_id, "state": record.state.value})
        if record.preview is None:
            return {"state": record.state.value, "preview": None}
        return {
            "state": record.state.value,
            "preview": record.preview.model_dump(mode="json"),
            "approval_component": approval_panel(record.preview).model_dump(mode="json"),
        }

    def propose_action(
        kind: str,
        title: str,
        summary: str,
        payload: Optional[Dict[str, Any]] = None,
        risk_tier: str = "MEDIUM",
        reversible: bool = True,
        consequences: Optional[List[str]] = None,
        thesis_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Propose a non-trade workflow action for human approval. Proposing is not approving."""
        request = ActionRequest(
            request_id=str(uuid.uuid4()),
            project_id=project_id,
            kind=ActionKind(kind),
            title=title,
            summary=summary,
            payload=payload or {},
            risk_tier=RiskTier(risk_tier),
            reversible=reversible,
            consequences=consequences or [],
            thesis_id=thesis_id,
            requested_by="EDGE_TF",
        )
        approvals.propose(request, session_id=session_id)
        record = approvals.submit_for_approval(request.request_id, session_id=session_id)
        return {
            "request_id": record.request_id,
            "state": record.state.value,
            "blockers": record.blockers,
            "approval_component": action_approval_panel(record, policy=approvals.policy).model_dump(mode="json"),
        }

    def get_approval_inbox() -> Dict[str, Any]:
        """Everything in this project currently blocked on a human decision."""
        pending_actions = approvals.pending(project_id=project_id)
        pending_trades = [
            record.preview
            for record in transactions.records()
            if record.preview is not None and record.state.value == "AWAITING_APPROVAL"
        ]
        component = approval_inbox(previews=pending_trades, actions=pending_actions)
        return {
            "count": len(pending_actions) + len(pending_trades),
            "component": component.model_dump(mode="json"),
        }

    def get_transaction_state(intent_id: str) -> Dict[str, Any]:
        """Describe - not change - the lifecycle state of a transaction."""
        record = transactions.get(intent_id)
        return {"intent_id": intent_id, "state": record.state.value, "history": record.history}

    def get_action_state(request_id: str) -> Dict[str, Any]:
        """Describe - not change - the lifecycle state of a workflow action."""
        record = approvals.get(request_id)
        return {"request_id": request_id, "state": record.state.value, "history": record.history}

    def pin_view(title: str, view: Dict[str, Any], thesis_id: Optional[str] = None) -> Dict[str, Any]:
        """Persist a rendered view so it can be rehydrated in any future session."""
        pin = PinnedView(pin_id=str(uuid.uuid4()), thesis_id=thesis_id, title=title, view=view)
        _append(EventKind.VIEW_PINNED, subject_id=thesis_id, payload=pin.model_dump(mode="json"))
        return {"pin_id": pin.pin_id}

    def _spec(fn, capability: Capability) -> ToolSpec:
        return ToolSpec(fn.__name__, (fn.__doc__ or "").strip(), capability, fn)

    tools = [
        _spec(get_component_catalog, Capability.PRESENT),
        _spec(get_workspace_overview, Capability.READ),
        _spec(get_current_project, Capability.READ),
        _spec(list_theses, Capability.READ),
        _spec(get_thesis, Capability.READ),
        _spec(create_thesis, Capability.DRAFT),
        _spec(record_evidence, Capability.DRAFT),
        _spec(set_watch_condition, Capability.DRAFT),
        _spec(draft_trade_intent, Capability.DRAFT),
        _spec(check_intent_completeness, Capability.COMPUTE),
        _spec(request_preview, Capability.COMPUTE),
        _spec(propose_action, Capability.DRAFT),
        _spec(get_approval_inbox, Capability.READ),
        _spec(get_transaction_state, Capability.READ),
        _spec(get_action_state, Capability.READ),
        _spec(pin_view, Capability.DRAFT),
    ]
    return assert_model_safe(tools)


__all__ = ["build_tools"]
