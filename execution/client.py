"""
Reference client for the external execution service.

Path: execution/client.py

EDGE-TF is the decision engine; the executor is a separate service in its own
repo and runtime. This module is the executor's EDGE-facing half, kept here so
the wire contract has a tested consumer. Copy it into the executor repo and
plug in broker adapters - Schwab first, others behind the same BrokerAdapter
protocol.

    executor = ExternalExecutionService(
        client=EdgeExecutionClient(base_url, token),
        brokers=BrokerRegistry with SchwabAdapter registered,
    )
    executor.run_once()   # poll -> claim -> place -> report -> snapshot

Safety invariants enforced on this side of the wire:
    - only instructions returned by the gateway are ever placed
    - each trade is claimed exactly once (idempotency_key dedupes retries)
    - every broker outcome, including errors, is reported back to EDGE
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import requests

from execution.broker_interface import BrokerAdapter, BrokerRegistry
from execution.contracts import (
    BrokerAccountSnapshot,
    ExecutionInstruction,
    ExecutionReport,
    ExecutionReportStatus,
)

log = logging.getLogger(__name__)


class EdgeExecutionClient:
    """Authenticated HTTP client for api/execution_app."""

    def __init__(self, base_url: str, token: str, *, timeout: float = 15.0):
        if not token:
            raise ValueError("an EDGE_EXECUTION_TOKEN bearer token is required")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers["Authorization"] = f"Bearer {token}"

    # -- pulls ---------------------------------------------------------------

    def list_orders(self) -> List[ExecutionInstruction]:
        payload = self._request("GET", "/execution/orders")
        return [ExecutionInstruction.model_validate(item) for item in payload.get("orders", [])]

    def claim(self, trade_id: str, *, executor_id: str) -> ExecutionInstruction:
        payload = self._request(
            "POST", f"/execution/orders/{trade_id}/claim", json={"executor_id": executor_id}
        )
        return ExecutionInstruction.model_validate(payload)

    # -- pushes ----------------------------------------------------------------

    def report(self, report: ExecutionReport) -> Dict[str, Any]:
        return self._request(
            "POST",
            f"/execution/orders/{report.trade_id}/reports",
            json=report.model_dump(mode="json"),
        )

    def post_snapshot(self, snapshot: BrokerAccountSnapshot) -> Dict[str, Any]:
        return self._request(
            "POST", "/execution/portfolio/snapshots", json=snapshot.model_dump(mode="json")
        )

    def portfolio_state(self) -> Dict[str, Any]:
        return self._request("GET", "/execution/portfolio/state")

    # -- internals -------------------------------------------------------------

    def _request(self, method: str, path: str, **kwargs: Any) -> Dict[str, Any]:
        response = self._session.request(
            method, f"{self.base_url}{path}", timeout=self.timeout, **kwargs
        )
        if response.status_code >= 400:
            raise RuntimeError(
                f"gateway {method} {path} -> {response.status_code}: {response.text[:300]}"
            )
        return response.json()


class ExternalExecutionService:
    """
    Poll-claim-place-report loop. Broker logic lives behind BrokerAdapter;
    this class never sees broker credentials or payloads directly.
    """

    def __init__(
        self,
        *,
        client: EdgeExecutionClient,
        brokers: BrokerRegistry,
        default_broker: str,
        executor_id: str = "edge-executor-1",
    ):
        self.client = client
        self.brokers = brokers
        self.default_broker = default_broker
        self.executor_id = executor_id
        self._claimed: set[str] = set()  # idempotency keys claimed this process

    def run_once(self) -> List[Dict[str, Any]]:
        outcomes: List[Dict[str, Any]] = []
        for instruction in self.client.list_orders():
            if instruction.idempotency_key in self._claimed:
                continue
            outcomes.append(self._execute_one(instruction))
        return outcomes

    def report_snapshot(self, *, account_id: str) -> Dict[str, Any]:
        broker = self.brokers.get(self.default_broker)
        balances = broker.get_balances()
        positions = broker.get_positions()
        snapshot = BrokerAccountSnapshot(
            broker=broker.broker_id,
            account_id=account_id,
            cash=float(balances.get("cash", 0.0)),
            positions=positions,  # type: ignore[arg-type]
        )
        return self.client.post_snapshot(snapshot)

    # -- internals -------------------------------------------------------------

    def _execute_one(self, instruction: ExecutionInstruction) -> Dict[str, Any]:
        try:
            claimed = self.client.claim(instruction.trade_id, executor_id=self.executor_id)
        except RuntimeError as exc:
            log.warning("claim failed for %s: %s", instruction.trade_id, exc)
            return {"trade_id": instruction.trade_id, "outcome": "CLAIM_FAILED"}

        self._claimed.add(claimed.idempotency_key)
        broker = self._broker_for(claimed)
        try:
            ack = broker.place_order(claimed.model_dump(mode="json"))
        except Exception as exc:  # every failure goes back to EDGE
            self.client.report(
                ExecutionReport(
                    trade_id=claimed.trade_id,
                    instruction_id=claimed.instruction_id,
                    broker=broker.broker_id,
                    status=ExecutionReportStatus.ERROR,
                    message=str(exc),
                )
            )
            return {"trade_id": claimed.trade_id, "outcome": "ERROR"}

        status = (
            ExecutionReportStatus.FILLED
            if str(ack.get("status", "")).upper() == "FILLED"
            else ExecutionReportStatus.ACCEPTED
        )
        self.client.report(
            ExecutionReport(
                trade_id=claimed.trade_id,
                instruction_id=claimed.instruction_id,
                broker=broker.broker_id,
                broker_order_id=ack.get("order_id"),
                status=status,
                filled_quantity=float(ack.get("filled_quantity", 0.0)),
                average_price=ack.get("average_price"),
                message=ack.get("message"),
            )
        )
        return {"trade_id": claimed.trade_id, "outcome": status.value}

    def _broker_for(self, instruction: ExecutionInstruction) -> BrokerAdapter:
        # Multi-broker routing hook: instructions carry no broker today, so
        # everything goes to the default. Add a broker field to the strategy
        # payload and key off it here when the second broker arrives.
        return self.brokers.get(self.default_broker)


__all__ = ["EdgeExecutionClient", "ExternalExecutionService"]
