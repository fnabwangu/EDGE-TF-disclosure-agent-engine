"""
Deterministic transaction state machine.

Path: transactions/state_machine.py

The generative layer may *describe* states. It may not transition them.
Every transition is whitelisted here and is the only way state changes.
"""

from __future__ import annotations

from typing import Dict, Set

from transactions.schemas import TransactionState as S


class IllegalTransition(RuntimeError):
    def __init__(self, current: S, target: S):
        super().__init__(f"Illegal transaction transition {current.value} -> {target.value}")
        self.current = current
        self.target = target


TERMINAL: Set[S] = {S.REJECTED, S.FILLED, S.CANCELLED, S.ERROR, S.KILL_SWITCHED}

_ALLOWED: Dict[S, Set[S]] = {
    S.DRAFT: {S.VALIDATING, S.CANCELLED},
    S.VALIDATING: {S.REJECTED, S.AWAITING_APPROVAL, S.KILL_SWITCHED, S.ERROR},
    S.AWAITING_APPROVAL: {S.APPROVED, S.REJECTED, S.CANCELLED, S.KILL_SWITCHED, S.APPROVAL_EXPIRED},
    S.APPROVED: {S.REVALIDATING, S.CANCEL_REQUESTED, S.KILL_SWITCHED},
    S.REVALIDATING: {S.SUBMITTING, S.APPROVAL_EXPIRED, S.REJECTED, S.KILL_SWITCHED, S.ERROR},
    S.APPROVAL_EXPIRED: {S.VALIDATING, S.CANCELLED},
    S.SUBMITTING: {S.SUBMITTED, S.ERROR, S.REJECTED},
    S.SUBMITTED: {S.PARTIALLY_FILLED, S.FILLED, S.CANCEL_REQUESTED, S.ERROR},
    S.PARTIALLY_FILLED: {S.FILLED, S.CANCEL_REQUESTED, S.ERROR},
    S.CANCEL_REQUESTED: {S.CANCELLED, S.FILLED, S.PARTIALLY_FILLED, S.ERROR},
    S.REJECTED: set(),
    S.FILLED: set(),
    S.CANCELLED: set(),
    S.ERROR: set(),
    S.KILL_SWITCHED: set(),
}


def can_transition(current: S, target: S) -> bool:
    return target in _ALLOWED.get(current, set())


def assert_transition(current: S, target: S) -> S:
    if not can_transition(current, target):
        raise IllegalTransition(current, target)
    return target


def is_terminal(state: S) -> bool:
    return state in TERMINAL


def allowed_transitions(current: S) -> Set[S]:
    return set(_ALLOWED.get(current, set()))


__all__ = [
    "IllegalTransition",
    "allowed_transitions",
    "assert_transition",
    "can_transition",
    "is_terminal",
]
