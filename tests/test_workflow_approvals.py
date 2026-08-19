"""Tests for generic workflow-action approvals."""

from datetime import timedelta

import pytest

from approvals.policy import ApprovalPolicy, TierRule
from approvals.schemas import ActionKind, ActionRequest, ApprovalState, RiskTier
from approvals.service import ApprovalError, ApprovalService
from approvals.state_machine import IllegalApprovalTransition, assert_transition
from workbench.store import WorkbenchStore


@pytest.fixture()
def store(tmp_path) -> WorkbenchStore:
    store = WorkbenchStore(log_path=tmp_path / "events.jsonl")
    store.create_project(name="Nuclear power", project_id="proj-nuclear")
    return store


@pytest.fixture()
def service(store) -> ApprovalService:
    svc = ApprovalService(workbench=store)
    svc.register_executor(ActionKind.RISK_PARAMETER_CHANGE, lambda req: {"applied": req.payload})
    svc.register_executor(ActionKind.DATA_SOURCE_ONBOARDING, lambda req: {"onboarded": req.payload.get("source")})
    return svc


def make_request(**overrides) -> ActionRequest:
    payload = {
        "request_id": "req-1",
        "project_id": "proj-nuclear",
        "kind": ActionKind.DATA_SOURCE_ONBOARDING,
        "title": "Onboard NPORT bulk feed",
        "summary": "Adds a new disclosure source to the ingestion pipeline.",
        "payload": {"source": "sec-nport-bulk"},
        "risk_tier": RiskTier.LOW,
        "consequences": ["New rows enter the canonical store."],
    }
    payload.update(overrides)
    return ActionRequest.model_validate(payload)


def test_low_risk_action_needs_one_approval_then_executes(service):
    service.propose(make_request())
    record = service.submit_for_approval("req-1")
    assert record.state is ApprovalState.AWAITING_APPROVAL
    assert record.required_approvals == 1

    service.approve("req-1", action_hash=record.action_hash, approver_id="op-1")
    final = service.execute("req-1")

    assert final.state is ApprovalState.EXECUTED
    assert final.result == {"onboarded": "sec-nport-bulk"}


def test_mutating_the_request_after_approval_voids_it(service):
    service.propose(make_request())
    record = service.submit_for_approval("req-1")
    service.approve("req-1", action_hash=record.action_hash, approver_id="op-1")

    record.request.payload["source"] = "some-other-feed"

    final = service.execute("req-1")
    assert final.state is ApprovalState.APPROVAL_EXPIRED


def test_stale_hash_is_not_an_approval(service):
    service.propose(make_request())
    service.submit_for_approval("req-1")

    record = service.approve("req-1", action_hash="0" * 64, approver_id="op-1")
    assert record.state is ApprovalState.APPROVAL_EXPIRED
    assert record.approvals == []


def test_expired_approval_blocks_execution(service):
    service.propose(make_request())
    record = service.submit_for_approval("req-1")
    service.approve("req-1", action_hash=record.action_hash, approver_id="op-1")
    record.approvals[0].approved_at -= timedelta(seconds=record.approvals[0].ttl_seconds + 1)

    assert service.execute("req-1").state is ApprovalState.APPROVAL_EXPIRED


def test_high_risk_actions_require_a_second_person(service):
    service.propose(
        make_request(
            request_id="req-2",
            kind=ActionKind.RISK_PARAMETER_CHANGE,
            title="Raise illiquid cap to 20%",
            payload={"rule_22e4_illiquid_cap": 0.20},
        )
    )
    record = service.submit_for_approval("req-2")
    assert record.required_approvals == 2

    record = service.approve("req-2", action_hash=record.action_hash, approver_id="op-1")
    assert record.state is ApprovalState.AWAITING_APPROVAL
    assert record.outstanding_approvals == 1

    record = service.approve("req-2", action_hash=record.action_hash, approver_id="op-2")
    assert record.state is ApprovalState.APPROVED
    assert service.execute("req-2").state is ApprovalState.EXECUTED


def test_requester_cannot_self_approve_a_high_risk_action(service):
    service.propose(
        make_request(
            request_id="req-3",
            kind=ActionKind.RISK_PARAMETER_CHANGE,
            payload={"rule_22e4_illiquid_cap": 0.20},
            requested_by="op-1",
        )
    )
    record = service.submit_for_approval("req-3")
    record = service.approve("req-3", action_hash=record.action_hash, approver_id="op-1")

    assert record.state is ApprovalState.REJECTED


def test_the_same_person_cannot_approve_twice(service):
    service.propose(
        make_request(request_id="req-4", kind=ActionKind.RISK_PARAMETER_CHANGE, payload={"x": 1})
    )
    record = service.submit_for_approval("req-4")
    service.approve("req-4", action_hash=record.action_hash, approver_id="op-2")

    with pytest.raises(ApprovalError):
        service.approve("req-4", action_hash=record.action_hash, approver_id="op-2")


def test_irreversible_actions_are_escalated_to_two_approvers(store):
    policy = ApprovalPolicy()
    request = make_request(reversible=False, risk_tier=RiskTier.LOW)
    assert policy.effective_tier(request) is RiskTier.HIGH
    assert policy.rule_for(request).required_approvals == 2


def test_kill_switch_reset_is_floored_at_critical():
    policy = ApprovalPolicy()
    request = make_request(kind=ActionKind.KILL_SWITCH_RESET, risk_tier=RiskTier.LOW)
    assert policy.effective_tier(request) is RiskTier.CRITICAL


def test_action_without_a_registered_executor_is_rejected(service):
    service.propose(make_request(request_id="req-5", kind=ActionKind.CAPITAL_ALLOCATION))
    record = service.submit_for_approval("req-5")

    assert record.state is ApprovalState.REJECTED
    assert record.blockers == ["NO_EXECUTOR_REGISTERED:CAPITAL_ALLOCATION"]


def test_validators_block_submission(service):
    service.register_validator(
        ActionKind.DATA_SOURCE_ONBOARDING,
        lambda req: ["SOURCE_NOT_WHITELISTED"] if req.payload.get("source") != "approved" else [],
    )
    service.propose(make_request(request_id="req-6"))
    record = service.submit_for_approval("req-6")

    assert record.state is ApprovalState.REJECTED
    assert "SOURCE_NOT_WHITELISTED" in record.blockers


def test_execution_requires_approval(service):
    service.propose(make_request(request_id="req-7"))
    service.submit_for_approval("req-7")
    with pytest.raises(ApprovalError):
        service.execute("req-7")


def test_state_machine_forbids_draft_to_executed():
    with pytest.raises(IllegalApprovalTransition):
        assert_transition(ApprovalState.DRAFT, ApprovalState.EXECUTED)


def test_executor_failure_is_recorded_not_swallowed(store):
    service = ApprovalService(workbench=store)

    def boom(request):
        raise RuntimeError("downstream unavailable")

    service.register_executor(ActionKind.DATA_SOURCE_ONBOARDING, boom)
    service.propose(make_request(request_id="req-8"))
    record = service.submit_for_approval("req-8")
    service.approve("req-8", action_hash=record.action_hash, approver_id="op-1")

    final = service.execute("req-8")
    assert final.state is ApprovalState.FAILED
    assert final.result == {"error": "downstream unavailable"}


def test_pending_approvals_reach_the_next_session(store, service):
    service.propose(make_request(request_id="req-9"))
    service.submit_for_approval("req-9")

    brief = store.open_session(project_id="proj-nuclear")
    assert [a["request_id"] for a in brief.pending_actions] == ["req-9"]
    assert store.workspace_brief().total_pending_approvals == 1


def test_custom_policy_overrides_quorum(store):
    policy = ApprovalPolicy(
        tier_rules={
            RiskTier.LOW: TierRule(required_approvals=3, ttl_seconds=60),
            RiskTier.MEDIUM: TierRule(required_approvals=1, ttl_seconds=60),
            RiskTier.HIGH: TierRule(required_approvals=2, ttl_seconds=60, self_approval_allowed=False),
            RiskTier.CRITICAL: TierRule(required_approvals=2, ttl_seconds=60, self_approval_allowed=False),
        }
    )
    service = ApprovalService(workbench=store, policy=policy)
    service.register_executor(ActionKind.DATA_SOURCE_ONBOARDING, lambda req: {})
    service.propose(make_request(request_id="req-10"))

    assert service.submit_for_approval("req-10").required_approvals == 3
