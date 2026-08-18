from pathlib import Path

import pytest

from execution.order_router import OrderRequest, OrderRouter
from execution.schwab_bridge import SchwabBridge, SchwabOrderRequest
from risk.kill_switch import EmergencyKillSwitchEngine, KillSwitchState, TripTriggerType


class FakeExecutionControl:
    def __init__(self):
        self.cancelled = False
        self.reconciled = False

    def cancel_all_open_orders(self):
        self.cancelled = True

    def reconcile_positions(self):
        self.reconciled = True


class FakeBroker:
    def __init__(self):
        self.submitted = False

    def submit_order(self, request):
        self.submitted = True
        return {"status": "SUBMITTED"}


def test_trip_cancels_orders_and_reconciles_positions(tmp_path):
    control = FakeExecutionControl()
    switch = EmergencyKillSwitchEngine(state_path=tmp_path / "lock.json", execution_control=control)
    switch.trip(TripTriggerType.MANUAL_OPERATOR_OVERRIDE, "operator halt")

    assert control.cancelled is True
    assert control.reconciled is True
    assert switch.control_actions == {"cancel_open_orders": "COMPLETED", "reconcile_positions": "COMPLETED"}


def test_router_blocks_transmission_when_kill_switch_is_locked():
    broker = FakeBroker()
    switch = EmergencyKillSwitchEngine()
    switch.trip(TripTriggerType.DATA_STALENESS, "feed stale")
    result = OrderRouter(broker, switch).route(OrderRequest("ABC", 1, "BUY"), True)

    assert result == {"status": "REJECTED", "reason": "KILL_SWITCH_LOCKED"}
    assert broker.submitted is False


def test_schwab_bridge_blocks_direct_transmission_when_locked():
    switch = EmergencyKillSwitchEngine()
    switch.trip(TripTriggerType.DATA_STALENESS, "feed stale")
    bridge = SchwabBridge(kill_switch=switch, enforce_dry_run=False)

    result = bridge.submit_order(SchwabOrderRequest(symbol="ABC", quantity=1))

    assert result == {"status": "REJECTED", "reason": "KILL_SWITCH_LOCKED"}


def test_restart_requires_authenticated_dual_signer_reset(tmp_path):
    state_path = tmp_path / "lock.json"
    verifier = lambda signor_id, role, justification: justification == "approved"
    first = EmergencyKillSwitchEngine(state_path=state_path, authorization_verifier=verifier)
    first.trip(TripTriggerType.DATA_STALENESS, "feed stale")

    with pytest.raises(PermissionError, match="Authenticated"):
        first.submit_reset_authorization("operator-1", "CHIEF_COMPLIANCE_OFFICER", "wrong")

    first.submit_reset_authorization("operator-1", "CHIEF_COMPLIANCE_OFFICER", "approved")
    restarted = EmergencyKillSwitchEngine(state_path=state_path, authorization_verifier=verifier)
    assert restarted.state == KillSwitchState.AWAITING_DUAL_AUTH
    restarted.submit_reset_authorization("operator-2", "LEAD_PORTFOLIO_MANAGER", "approved")

    assert restarted.is_locked is False
    assert restarted.state == KillSwitchState.ARMED_NOMINAL
