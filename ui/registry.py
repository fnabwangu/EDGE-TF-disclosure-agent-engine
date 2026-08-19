"""
Generative UI registry and validator.

Path: ui/registry.py

A model-authored view is untrusted input. It is accepted only if every
component type is known, every required data field is present, every action is
permitted for that component, and every approval-bearing component carries an
intent hash that the deterministic core actually issued.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

from approvals.policy import ApprovalPolicy
from approvals.schemas import ActionRecord
from transactions.schemas import TransactionPreview
from ui.schemas import ActionType, ComponentType, GenerativeView, UIAction, UIComponent
from workbench.schemas import ContinuityBrief, WorkspaceBrief


class UISchemaViolation(ValueError):
    def __init__(self, violations: List[str]):
        super().__init__("; ".join(violations))
        self.violations = violations


@dataclass(frozen=True)
class ComponentSpec:
    required_fields: Set[str] = field(default_factory=set)
    allowed_actions: Set[ActionType] = field(default_factory=set)
    requires_provenance: bool = False
    deterministic_only: bool = False
    hash_field: Optional[str] = None
    hashed_items_field: Optional[str] = None


REGISTRY: Dict[ComponentType, ComponentSpec] = {
    ComponentType.METRIC: ComponentSpec({"value"}, {ActionType.DRILL_DOWN, ActionType.PIN_TO_WORKBENCH}),
    ComponentType.TABLE: ComponentSpec({"columns", "rows"}, {ActionType.DRILL_DOWN, ActionType.PIN_TO_WORKBENCH}),
    ComponentType.CHART: ComponentSpec({"series"}, {ActionType.DRILL_DOWN}),
    ComponentType.SIGNAL_CARD: ComponentSpec(
        {"ticker", "state"}, {ActionType.DRILL_DOWN, ActionType.DRAFT_INTENT, ActionType.PIN_TO_WORKBENCH}, True
    ),
    ComponentType.EVIDENCE_CARD: ComponentSpec({"claim", "sources"}, {ActionType.OPEN_EVIDENCE}, True),
    ComponentType.COUNTER_THESIS_PANEL: ComponentSpec({"counter_claims"}, {ActionType.OPEN_EVIDENCE}, True),
    ComponentType.IAV_GAUGE: ComponentSpec({"value", "state"}, {ActionType.DRILL_DOWN}, True),
    ComponentType.ADOPTION_CURVE: ComponentSpec({"points"}, {ActionType.DRILL_DOWN}, True),
    ComponentType.MANAGER_BREADTH_GRAPH: ComponentSpec({"nodes", "edges"}, {ActionType.DRILL_DOWN}, True),
    ComponentType.HOLDINGS_DELTA_TABLE: ComponentSpec({"columns", "rows"}, {ActionType.DRILL_DOWN}, True),
    ComponentType.AQD_WATERFALL: ComponentSpec({"steps"}, {ActionType.DRILL_DOWN}, True),
    ComponentType.EVIDENCE_TIMELINE: ComponentSpec({"events"}, {ActionType.OPEN_EVIDENCE}, True),
    ComponentType.SCENARIO_TREE: ComponentSpec({"root"}, {ActionType.RUN_SCENARIO, ActionType.PIN_TO_WORKBENCH}),
    ComponentType.ETF_IMPLEMENTATION_COMPARISON: ComponentSpec(
        {"candidates"}, {ActionType.DRAFT_INTENT, ActionType.DRILL_DOWN}, True
    ),
    ComponentType.RISK_BUDGET_PANEL: ComponentSpec({"budgets"}, set(), True),
    ComponentType.TRADE_TICKET: ComponentSpec(
        {"intent_id", "symbol", "side", "quantity"},
        {ActionType.MODIFY_INTENT, ActionType.REQUEST_PREVIEW, ActionType.REJECT_INTENT},
    ),
    ComponentType.APPROVAL_PANEL: ComponentSpec(
        {"intent_id", "intent_hash", "risk_gate_passed"},
        {ActionType.REQUEST_APPROVAL, ActionType.MODIFY_INTENT, ActionType.REJECT_INTENT, ActionType.OPEN_EVIDENCE},
        requires_provenance=True,
        deterministic_only=True,
        hash_field="intent_hash",
    ),
    ComponentType.ACTION_APPROVAL_PANEL: ComponentSpec(
        {"request_id", "action_hash", "kind", "risk_tier", "outstanding_approvals"},
        {ActionType.REQUEST_APPROVAL, ActionType.CANCEL_ACTION, ActionType.OPEN_EVIDENCE, ActionType.DRILL_DOWN},
        requires_provenance=True,
        deterministic_only=True,
        hash_field="action_hash",
    ),
    ComponentType.APPROVAL_INBOX: ComponentSpec(
        {"items"},
        {ActionType.REQUEST_APPROVAL, ActionType.DRILL_DOWN, ActionType.SWITCH_PROJECT},
        requires_provenance=True,
        deterministic_only=True,
        hashed_items_field="items",
    ),
    ComponentType.PROJECT_SWITCHER: ComponentSpec(
        {"projects"}, {ActionType.SWITCH_PROJECT, ActionType.DRILL_DOWN}
    ),
    ComponentType.PROJECT_CARD: ComponentSpec(
        {"project_id", "name", "state"},
        {ActionType.SWITCH_PROJECT, ActionType.DRILL_DOWN, ActionType.PIN_TO_WORKBENCH},
    ),
    ComponentType.CONTINUITY_BRIEF: ComponentSpec(
        {"project_id", "session_id", "active_theses"},
        {ActionType.RESUME_THREAD, ActionType.DRILL_DOWN, ActionType.SWITCH_PROJECT},
    ),
    ComponentType.AUDIT_TRAIL: ComponentSpec({"entries"}, set(), True),
    ComponentType.THESIS_TIMELINE: ComponentSpec({"events"}, {ActionType.OPEN_EVIDENCE, ActionType.DRILL_DOWN}, True),
    ComponentType.STATE_DIFF: ComponentSpec({"changes"}, {ActionType.OPEN_EVIDENCE}),
}


def validate_view(view: GenerativeView, *, authorized_hashes: Iterable[str] = ()) -> GenerativeView:
    """Raise UISchemaViolation unless the whole view is renderable and safe."""
    authorized = set(authorized_hashes)
    violations: List[str] = []

    for index, component in enumerate(view.components):
        spec = REGISTRY.get(component.type)
        if spec is None:
            violations.append(f"components[{index}]: unknown component type {component.type}")
            continue

        missing = spec.required_fields - set(component.data)
        if missing:
            violations.append(f"components[{index}] ({component.type.value}): missing data fields {sorted(missing)}")

        for action in component.actions:
            if action.type not in spec.allowed_actions:
                violations.append(
                    f"components[{index}] ({component.type.value}): action {action.type.value} not permitted"
                )

        if spec.requires_provenance and not component.provenance:
            violations.append(f"components[{index}] ({component.type.value}): provenance required")

        violations.extend(_validate_hash_binding(index, component, spec, authorized))

    if violations:
        raise UISchemaViolation(violations)
    return view


def _validate_hash_binding(
    index: int, component: UIComponent, spec: ComponentSpec, authorized: Set[str]
) -> List[str]:
    if not spec.deterministic_only:
        return []
    label = f"components[{index}] ({component.type.value})"
    violations: List[str] = []

    if spec.hashed_items_field:
        items = component.data.get(spec.hashed_items_field) or []
        if not isinstance(items, list):
            return [f"{label}: {spec.hashed_items_field} must be a list"]
        for position, item in enumerate(items):
            item_hash = (item or {}).get("approval_hash")
            if item_hash not in authorized:
                violations.append(f"{label}: item {position} carries a hash the core did not issue")
        return violations

    declared = component.data.get(spec.hash_field or "")
    if declared not in authorized:
        violations.append(f"{label}: {spec.hash_field} was not issued by the core")
    for action in component.actions:
        if action.type is not ActionType.REQUEST_APPROVAL:
            continue
        bound = action.binds_intent_hash or action.binds_action_hash
        if bound != declared:
            violations.append(f"{label}: approval action does not bind the displayed {spec.hash_field}")
    return violations


def approval_panel(preview: TransactionPreview) -> UIComponent:
    """Deterministically built - never model-authored - so the hash cannot drift."""
    blockers = [f.message for f in preview.validation.errors] + list(preview.risk_reasons)
    return UIComponent(
        type=ComponentType.APPROVAL_PANEL,
        title=f"Approve {preview.side} {preview.symbol}",
        data={
            "intent_id": preview.intent_id,
            "intent_hash": preview.intent_hash,
            "symbol": preview.symbol,
            "side": preview.side,
            "quantity": preview.quantity,
            "estimated_price": preview.estimated_price,
            "estimated_notional": preview.estimated_notional,
            "weight_before": preview.estimated_portfolio_weight_before,
            "weight_after": preview.estimated_portfolio_weight_after,
            "expected_max_loss": preview.expected_max_loss,
            "liquidity_status": preview.liquidity_status,
            "strategy_state": preview.strategy_state,
            "risk_gate_passed": preview.risk_gate_passed,
            "blockers": blockers,
            "rationale": preview.rationale,
            "invalidation": preview.invalidation_condition,
            "quote_timestamp": preview.quote_timestamp.isoformat(),
        },
        actions=_approval_actions(preview),
        provenance=[f"preview:{preview.intent_id}", f"quote:{preview.quote_timestamp.isoformat()}"],
    )


def _approval_actions(preview: TransactionPreview) -> List[UIAction]:
    actions: List[UIAction] = []
    if preview.risk_gate_passed and preview.validation.passed and preview.liquidity_status != "FAIL":
        actions.append(
            UIAction(
                type=ActionType.REQUEST_APPROVAL,
                label="Approve order",
                payload={"intent_id": preview.intent_id},
                binds_intent_hash=preview.intent_hash,
            )
        )
    actions.append(UIAction(type=ActionType.MODIFY_INTENT, label="Modify", payload={"intent_id": preview.intent_id}))
    actions.append(UIAction(type=ActionType.REJECT_INTENT, label="Reject", payload={"intent_id": preview.intent_id}))
    actions.append(UIAction(type=ActionType.OPEN_EVIDENCE, label="Show evidence", payload={"intent_id": preview.intent_id}))
    return actions


def component_catalog() -> Dict[str, Dict[str, Any]]:
    """Machine-readable catalog handed to the model as its rendering vocabulary."""
    return {
        component.value: {
            "required_fields": sorted(spec.required_fields),
            "allowed_actions": sorted(a.value for a in spec.allowed_actions),
            "requires_provenance": spec.requires_provenance,
            "model_authorable": not spec.deterministic_only,
        }
        for component, spec in REGISTRY.items()
    }


def action_approval_panel(record: ActionRecord, *, policy: Optional[ApprovalPolicy] = None) -> UIComponent:
    """Deterministic approval card for any workflow action, not just trades."""
    policy = policy or ApprovalPolicy()
    request = record.request
    tier = policy.effective_tier(request)
    actions: List[UIAction] = []

    if record.action_hash and not record.blockers:
        actions.append(
            UIAction(
                type=ActionType.REQUEST_APPROVAL,
                label=f"Approve ({record.outstanding_approvals} remaining)"
                if record.outstanding_approvals > 1
                else "Approve",
                payload={"request_id": record.request_id},
                binds_action_hash=record.action_hash,
            )
        )
    actions.append(UIAction(type=ActionType.CANCEL_ACTION, label="Reject", payload={"request_id": record.request_id}))
    actions.append(UIAction(type=ActionType.DRILL_DOWN, label="Show detail", payload={"request_id": record.request_id}))

    return UIComponent(
        type=ComponentType.ACTION_APPROVAL_PANEL,
        title=request.title,
        data={
            "request_id": record.request_id,
            "action_hash": record.action_hash,
            "project_id": request.project_id,
            "kind": request.kind.value,
            "summary": request.summary,
            "risk_tier": tier.value,
            "reversible": request.reversible,
            "consequences": request.consequences,
            "state": record.state.value,
            "required_approvals": record.required_approvals,
            "outstanding_approvals": record.outstanding_approvals,
            "approvers": record.approvers,
            "blockers": record.blockers,
            "requested_by": request.requested_by,
        },
        actions=actions,
        provenance=[f"action:{record.request_id}", f"policy:{policy.version}"],
    )


def approval_inbox(
    *,
    previews: Sequence[TransactionPreview] = (),
    actions: Sequence[ActionRecord] = (),
    title: str = "Waiting on you",
) -> UIComponent:
    """One queue merging trade approvals and workflow approvals across projects."""
    items: List[Dict[str, Any]] = []

    for preview in previews:
        items.append(
            {
                "item_type": "TRADE",
                "reference_id": preview.intent_id,
                "approval_hash": preview.intent_hash,
                "title": f"{preview.side} {preview.quantity:g} {preview.symbol}",
                "detail": f"{preview.estimated_notional:,.0f} notional, {preview.strategy_state}",
                "risk_tier": "HIGH",
                "blocked": not preview.risk_gate_passed or not preview.validation.passed,
            }
        )

    for record in actions:
        items.append(
            {
                "item_type": "ACTION",
                "reference_id": record.request_id,
                "approval_hash": record.action_hash,
                "project_id": record.request.project_id,
                "title": record.request.title,
                "detail": record.request.summary,
                "risk_tier": record.request.risk_tier.value,
                "blocked": bool(record.blockers),
            }
        )

    return UIComponent(
        type=ComponentType.APPROVAL_INBOX,
        title=title,
        data={"items": items, "count": len(items)},
        actions=[UIAction(type=ActionType.DRILL_DOWN, label="Open", payload={})],
        provenance=["approval_service", "transaction_service"],
    )


def project_switcher(brief: WorkspaceBrief) -> UIComponent:
    """Cross-project overview with the ones needing a human sorted to the top."""
    return UIComponent(
        type=ComponentType.PROJECT_SWITCHER,
        title="Projects",
        data={
            "projects": [digest.model_dump(mode="json") for digest in brief.projects],
            "total_pending_approvals": brief.total_pending_approvals,
        },
        actions=[
            UIAction(
                type=ActionType.SWITCH_PROJECT,
                label=digest.name,
                payload={"project_id": digest.project_id},
            )
            for digest in brief.projects
        ],
    )


def continuity_panel(brief: ContinuityBrief) -> UIComponent:
    """What carried over from the last session in this project."""
    return UIComponent(
        type=ComponentType.CONTINUITY_BRIEF,
        title=f"Where we left off{f' - {brief.project.name}' if brief.project else ''}",
        data={
            "project_id": brief.project_id,
            "session_id": brief.session_id,
            "previous_session_id": brief.previous_session_id,
            "active_theses": [
                {"thesis_id": t.thesis_id, "title": t.title, "state": t.state.value, "conviction": t.conviction}
                for t in brief.active_theses
            ],
            "open_transactions": brief.open_transactions,
            "pending_actions": brief.pending_actions,
            "breached_conditions": brief.breached_conditions,
            "changed_since_last_session": brief.changed_since_last_session,
            "unresolved_questions": brief.unresolved_questions,
        },
        actions=[
            UIAction(
                type=ActionType.RESUME_THREAD,
                label=f"Resume {t.title}",
                payload={"thesis_id": t.thesis_id, "project_id": brief.project_id},
            )
            for t in brief.active_theses
        ],
    )


__all__ = [
    "REGISTRY",
    "ComponentSpec",
    "UISchemaViolation",
    "action_approval_panel",
    "approval_inbox",
    "approval_panel",
    "component_catalog",
    "continuity_panel",
    "project_switcher",
    "validate_view",
]
