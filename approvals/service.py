"""
Approval service.

Path: approvals/service.py

    propose -> validate -> present (hash) -> approve (quorum) -> revalidate -> execute

Executors are registered in Python at wiring time. A model can propose an
action and describe its state; it can never register an executor, approve a
request, or invoke one.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from approvals.policy import ApprovalPolicy
from approvals.schemas import (
    ActionApproval,
    ActionKind,
    ActionRecord,
    ActionRequest,
    ApprovalState,
    compute_action_hash,
)
from approvals.state_machine import assert_transition
from transactions.schemas import canonical_hash
from workbench.schemas import EventKind
from workbench.store import WorkbenchStore

Validator = Callable[[ActionRequest], List[str]]
Executor = Callable[[ActionRequest], Dict[str, Any]]


class ApprovalError(RuntimeError):
    pass


class ApprovalService:
    def __init__(
        self,
        *,
        workbench: WorkbenchStore,
        policy: Optional[ApprovalPolicy] = None,
    ):
        self.workbench = workbench
        self.policy = policy or ApprovalPolicy()
        self._records: Dict[str, ActionRecord] = {}
        self._validators: Dict[ActionKind, List[Validator]] = {}
        self._executors: Dict[ActionKind, Executor] = {}

    # -- wiring (code only, never model-driven) ----------------------------

    def register_validator(self, kind: ActionKind, validator: Validator) -> None:
        self._validators.setdefault(kind, []).append(validator)

    def register_executor(self, kind: ActionKind, executor: Executor) -> None:
        if kind in self._executors:
            raise ApprovalError(f"executor already registered for {kind.value}")
        self._executors[kind] = executor

    # -- lifecycle ---------------------------------------------------------

    def propose(self, request: ActionRequest, *, session_id: Optional[str] = None) -> ActionRecord:
        if request.request_id in self._records:
            raise ApprovalError(f"request {request.request_id} already exists")
        record = ActionRecord(
            request_id=request.request_id,
            request=request,
            required_approvals=self.policy.rule_for(request).required_approvals,
        )
        self._records[request.request_id] = record
        self._log(record, "PROPOSED", {"requested_by": request.requested_by})
        self.workbench.append(
            EventKind.ACTION_REQUESTED,
            project_id=request.project_id,
            session_id=session_id,
            actor=request.requested_by,
            subject_id=request.thesis_id,
            payload={
                "request_id": request.request_id,
                "kind": request.kind.value,
                "title": request.title,
                "risk_tier": self.policy.effective_tier(request).value,
                "state": record.state.value,
            },
        )
        return record

    def submit_for_approval(self, request_id: str, *, session_id: Optional[str] = None) -> ActionRecord:
        record = self.get(request_id)
        self._set_state(record, ApprovalState.VALIDATING, session_id=session_id)

        blockers: List[str] = []
        if record.request.kind not in self._executors:
            blockers.append(f"NO_EXECUTOR_REGISTERED:{record.request.kind.value}")
        for validator in self._validators.get(record.request.kind, []):
            blockers.extend(validator(record.request))
        record.blockers = blockers

        if blockers:
            self._set_state(record, ApprovalState.REJECTED, {"blockers": blockers}, session_id=session_id)
            return record

        record.required_approvals = self.policy.rule_for(record.request).required_approvals
        record.presented_at = datetime.now(timezone.utc)
        record.action_hash = compute_action_hash(
            record.request,
            policy_version=self.policy.version,
            presented_at=record.presented_at,
        )
        self._set_state(
            record,
            ApprovalState.AWAITING_APPROVAL,
            {"action_hash": record.action_hash, "required_approvals": record.required_approvals},
            session_id=session_id,
        )
        return record

    def approve(
        self,
        request_id: str,
        *,
        action_hash: str,
        approver_id: str,
        session_id: Optional[str] = None,
    ) -> ActionRecord:
        record = self.get(request_id)
        if record.state is not ApprovalState.AWAITING_APPROVAL:
            raise ApprovalError(f"request {request_id} is not awaiting approval")
        if record.action_hash != action_hash:
            self._set_state(
                record, ApprovalState.APPROVAL_EXPIRED, {"reason": "ACTION_HASH_MISMATCH"}, session_id=session_id
            )
            return record

        rule = self.policy.rule_for(record.request)
        if not rule.self_approval_allowed and approver_id == record.request.requested_by:
            self._set_state(
                record, ApprovalState.REJECTED, {"reason": "SELF_APPROVAL_FORBIDDEN"}, session_id=session_id
            )
            return record
        if approver_id in record.approvers:
            raise ApprovalError(f"{approver_id} has already approved {request_id}")

        record.approvals.append(
            ActionApproval(
                approval_id=str(uuid.uuid4()),
                request_id=request_id,
                action_hash=action_hash,
                approver_id=approver_id,
                ttl_seconds=rule.ttl_seconds,
            )
        )

        target = (
            ApprovalState.APPROVED
            if len(record.approvals) >= record.required_approvals
            else ApprovalState.AWAITING_APPROVAL
        )
        self._set_state(
            record,
            target,
            {"approver_id": approver_id, "outstanding": record.outstanding_approvals},
            session_id=session_id,
        )
        return record

    def execute(self, request_id: str, *, actor: str = "SYSTEM", session_id: Optional[str] = None) -> ActionRecord:
        record = self.get(request_id)
        if record.state is not ApprovalState.APPROVED:
            raise ApprovalError(f"request {request_id} is not approved")

        self._set_state(record, ApprovalState.REVALIDATING, session_id=session_id)

        if any(approval.is_expired() for approval in record.approvals):
            self._set_state(
                record, ApprovalState.APPROVAL_EXPIRED, {"reason": "APPROVAL_TTL_ELAPSED"}, session_id=session_id
            )
            return record

        recomputed = compute_action_hash(
            record.request,
            policy_version=self.policy.version,
            presented_at=record.presented_at,
        )
        if recomputed != record.action_hash:
            self._set_state(
                record, ApprovalState.APPROVAL_EXPIRED, {"reason": "REQUEST_MUTATED"}, session_id=session_id
            )
            return record

        blockers: List[str] = []
        for validator in self._validators.get(record.request.kind, []):
            blockers.extend(validator(record.request))
        if blockers:
            record.blockers = blockers
            self._set_state(record, ApprovalState.REJECTED, {"blockers": blockers}, session_id=session_id)
            return record

        self._set_state(record, ApprovalState.EXECUTING, {"actor": actor}, session_id=session_id)
        try:
            record.result = self._executors[record.request.kind](record.request)
        except Exception as exc:  # executor failures must not corrupt the log
            record.result = {"error": str(exc)}
            self._set_state(record, ApprovalState.FAILED, {"error": str(exc)}, session_id=session_id)
            return record

        self._set_state(record, ApprovalState.EXECUTED, {"result": record.result}, session_id=session_id)
        return record

    def cancel(self, request_id: str, *, reason: str = "USER_CANCELLED", session_id: Optional[str] = None) -> ActionRecord:
        record = self.get(request_id)
        self._set_state(record, ApprovalState.CANCELLED, {"reason": reason}, session_id=session_id)
        return record

    # -- queries -----------------------------------------------------------

    def get(self, request_id: str) -> ActionRecord:
        record = self._records.get(request_id)
        if record is None:
            raise ApprovalError(f"unknown request {request_id}")
        return record

    def pending(self, *, project_id: Optional[str] = None) -> List[ActionRecord]:
        return [
            record
            for record in self._records.values()
            if record.state is ApprovalState.AWAITING_APPROVAL
            and (project_id is None or record.request.project_id == project_id)
        ]

    # -- internals ---------------------------------------------------------

    def _set_state(
        self,
        record: ActionRecord,
        target: ApprovalState,
        detail: Optional[Dict[str, Any]] = None,
        *,
        session_id: Optional[str] = None,
    ) -> None:
        assert_transition(record.state, target)
        record.state = target
        self._log(record, target.value, detail or {})
        self.workbench.append(
            EventKind.ACTION_STATE_CHANGED,
            project_id=record.request.project_id,
            session_id=session_id,
            subject_id=record.request.thesis_id,
            payload={"request_id": record.request_id, "state": target.value},
        )

    @staticmethod
    def _log(record: ActionRecord, event: str, detail: Dict[str, Any]) -> None:
        entry = {"at": datetime.now(timezone.utc).isoformat(), "event": event, "detail": detail}
        entry["entry_hash"] = canonical_hash(entry)
        record.history.append(entry)


__all__ = ["ApprovalError", "ApprovalService", "Executor", "Validator"]
