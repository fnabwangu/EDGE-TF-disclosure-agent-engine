"""
Approval state machine.

Path: approvals/state_machine.py

Same discipline as the trade path: transitions are whitelisted, so no caller -
model or human - can jump from a draft straight to an executed change.
"""

from __future__ import annotations

from typing import Dict, Set

from approvals.schemas import ApprovalState as S


class IllegalApprovalTransition(RuntimeError):
    def __init__(self, current: S, target: S):
        super().__init__(f"Illegal approval transition {current.value} -> {target.value}")
        self.current = current
        self.target = target


TERMINAL: Set[S] = {S.REJECTED, S.EXECUTED, S.FAILED, S.CANCELLED}

_ALLOWED: Dict[S, Set[S]] = {
    S.DRAFT: {S.VALIDATING, S.CANCELLED},
    S.VALIDATING: {S.AWAITING_APPROVAL, S.REJECTED},
    S.AWAITING_APPROVAL: {S.AWAITING_APPROVAL, S.APPROVED, S.REJECTED, S.CANCELLED, S.APPROVAL_EXPIRED},
    S.APPROVED: {S.REVALIDATING, S.CANCELLED, S.APPROVAL_EXPIRED},
    S.REVALIDATING: {S.EXECUTING, S.APPROVAL_EXPIRED, S.REJECTED},
    S.APPROVAL_EXPIRED: {S.VALIDATING, S.CANCELLED},
    S.EXECUTING: {S.EXECUTED, S.FAILED},
    S.EXECUTED: set(),
    S.REJECTED: set(),
    S.FAILED: set(),
    S.CANCELLED: set(),
}


def can_transition(current: S, target: S) -> bool:
    return target in _ALLOWED.get(current, set())


def assert_transition(current: S, target: S) -> S:
    if not can_transition(current, target):
        raise IllegalApprovalTransition(current, target)
    return target


def is_terminal(state: S) -> bool:
    return state in TERMINAL


__all__ = ["IllegalApprovalTransition", "assert_transition", "can_transition", "is_terminal"]
