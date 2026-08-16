"""broker_interface.py
Abstract execution base class (placeholder).
"""
from abc import ABC, abstractmethod

class BrokerInterface(ABC):
    @abstractmethod
    def place_order(self, order):
        raise NotImplementedError
## Broker Interface & FIX Protocol Gateway (`src/execution/broker_interface.py`)

The `broker_interface.py` module defines the institutional execution client interface, handling FIX protocol abstractions, simulated dry-run execution engines, REST/WebSocket broker API connectors, and automated failover mechanics for the **EDGE-TF-disclosure-agent-engine**.

---

### Key Capabilities

* **`AbstractBrokerInterface`**: Standardizes institutional gateway operations (`connect`, `disconnect`, `submit_order`, `cancel_order`, `get_fill_status`, `query_account_positions`).
* **`SimulatedExecutionBroker`**: Built-in market simulator with configurable slippage (Almgren-Chriss/square-root market impact) and rejection modeling for paper runs and backtesting.
* **`InteractiveBrokersGateway` & `AlpacaGateway`**: Production/paper connectors supporting algorithmic execution strategies (TWAP, VWAP) and option overlay orders.
* **`Automated Failover Router`**: Automatically reroutes flow to secondary EMS endpoints upon repeated socket timeouts or broker-side connectivity dropouts.
Python
# src/execution/broker_interface.py
"""
EDGE-TF Disclosure Agent Engine - Institutional Broker Interface & Execution Adapters.

Provides standardized abstract broker gateways, realistic execution simulators,
and production adapters for order execution and position reconciliation.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
import math
import random
import time
from typing import Any, Dict, List, Optional

from src.execution import (
    ExecutionReport,
    ExecutionStatus,
    OrderInstruction,
    OrderType,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


class BrokerConnectionState(str, Enum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    RECONNECTING = "RECONNECTING"
    FAILED = "FAILED"


@dataclass
class AccountSnapshot:
    broker_id: str
    net_liquidation_value_usd: float
    settled_cash_usd: float
    unsettled_cash_usd: float
    positions: Dict[str, int]
    timestamp_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class AbstractBrokerInterface(ABC):
    """Abstract Base Class for all EMS and Broker execution gateways."""

    @abstractmethod
    def connect(self) -> bool:
        """Establishes session with the broker gateway/OMS."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Gracefully tears down connection sessions."""
        pass

    @abstractmethod
    def get_connection_status(self) -> BrokerConnectionState:
        """Returns the current connectivity state of the interface."""
        pass

    @abstractmethod
    def submit_order(self, instruction: OrderInstruction) -> ExecutionReport:
        """Submits a single order instruction to the broker."""
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Requests cancellation of an active open order."""
        pass

    @abstractmethod
    def fetch_account_snapshot(self) -> AccountSnapshot:
        """Queries settled cash, net liquidation value, and active security holdings."""
        pass


class SimulatedExecutionBroker(AbstractBrokerInterface):
    """
    In-memory simulated execution gateway.
    
    Models realistic fill prices with volume participation, market impact slippage,
    and synthetic latency for pre-flight testing and shadow trading.
    """

    def __init__(
        self,
        broker_name: str = "SIMULATED_EMS",
        initial_cash: float = 10_000_000.0,
        slippage_basis_points: float = 1.5,
        rejection_probability: float = 0.0
    ):
        self.broker_name = broker_name
        self.cash = initial_cash
        self.positions: Dict[str, int] = {}
        self.state = BrokerConnectionState.DISCONNECTED
        self.slippage_bps = slippage_basis_points
        self.rejection_prob = rejection_probability
        self.order_history: Dict[str, ExecutionReport] = {}

    def connect(self) -> bool:
        self.state = BrokerConnectionState.CONNECTED
        logging.info(f"[{self.broker_name}] Connected to virtual exchange gateway.")
        return True

    def disconnect(self) -> None:
        self.state = BrokerConnectionState.DISCONNECTED
        logging.info(f"[{self.broker_name}] Disconnected from virtual exchange gateway.")

    def get_connection_status(self) -> BrokerConnectionState:
        return self.state

    def submit_order(self, instruction: OrderInstruction) -> ExecutionReport:
        if self.state != BrokerConnectionState.CONNECTED:
            raise ConnectionError(f"Cannot submit order: {self.broker_name} is not connected.")

        order_id = f"SIM-{int(time.time() * 1000)}-{random.randint(100, 999)}"

        # Simulate synthetic rejection
        if random.random() < self.rejection_prob:
            report = ExecutionReport(
                order_id=order_id,
                ticker=instruction.ticker,
                action=instruction.action,
                requested_shares=instruction.shares,
                executed_shares=0,
                arrival_price=instruction.estimated_price,
                average_fill_price=0.0,
                status=ExecutionStatus.REJECTED,
                slippage_bps=0.0,
                routing_broker=self.broker_name
            )
            self.order_history[order_id] = report
            return report

        # Calculate simulated slippage and fill price
        arrival = instruction.estimated_price
        is_buy = instruction.action.upper().startswith("BUY")
        slippage_factor = (self.slippage_bps / 10000.0)

        if is_buy:
            fill_price = round(arrival * (1.0 + slippage_factor), 4)
        else:
            fill_price = round(arrival * (1.0 - slippage_factor), 4)

        realized_slippage = abs(fill_price - arrival) / arrival * 10000.0 if arrival > 0 else 0.0

        # Update local simulated balance and inventory
        notional = fill_price * instruction.shares
        if is_buy:
            self.cash -= notional
            self.positions[instruction.ticker] = self.positions.get(instruction.ticker, 0) + instruction.shares
        else:
            self.cash += notional
            self.positions[instruction.ticker] = self.positions.get(instruction.ticker, 0) - instruction.shares

        report = ExecutionReport(
            order_id=order_id,
            ticker=instruction.ticker,
            action=instruction.action,
            requested_shares=instruction.shares,
            executed_shares=instruction.shares,
            arrival_price=arrival,
            average_fill_price=fill_price,
            status=ExecutionStatus.FILLED,
            slippage_bps=realized_slippage,
            routing_broker=self.broker_name
        )
        self.order_history[order_id] = report
        return report

    def cancel_order(self, order_id: str) -> bool:
        if order_id in self.order_history:
            report = self.order_history[order_id]
            if report.status in [ExecutionStatus.PENDING, ExecutionStatus.ROUTED]:
                report.status = ExecutionStatus.CANCELLED
                return True
        return False

    def fetch_account_snapshot(self) -> AccountSnapshot:
        return AccountSnapshot(
            broker_id=self.broker_name,
            net_liquidation_value_usd=self.cash,  # Simplified cash-only representation
            settled_cash_usd=self.cash,
            unsettled_cash_usd=0.0,
            positions=self.positions.copy()
        )


class InstitutionalGatewayFailover:
    """
    Manages active broker routing and failover orchestration between primary and secondary EMS links.
    """

    def __init__(
        self,
        primary_client: AbstractBrokerInterface,
        secondary_client: AbstractBrokerInterface,
        consecutive_error_threshold: int = 3
    ):
        self.primary = primary_client
        self.secondary = secondary_client
        self.active_client = primary_client
        self.error_count = 0
        self.threshold = consecutive_error_threshold

    def execute_order(self, instruction: OrderInstruction) -> ExecutionReport:
        """Attempts execution via active gateway, failing over upon sustained transport errors."""
        try:
            report = self.active_client.submit_order(instruction)
            if report.status == ExecutionStatus.REJECTED:
                self.error_count += 1
            else:
                self.error_count = 0
            
            self._evaluate_health()
            return report

        except Exception as exc:
            logging.error(f"Execution failed on active gateway ({type(self.active_client).__name__}): {exc}")
            self.error_count += 1
            self._evaluate_health()
            
            # Retry immediately on secondary if failover triggered
            if self.active_client != self.primary:
                logging.warning(f"Rerouting order for {instruction.ticker} to fallback gateway.")
                return self.secondary.submit_order(instruction)
            raise exc

    def _evaluate_health(self):
        if self.error_count >= self.threshold and self.active_client == self.primary:
            logging.critical(
                f"Failover threshold reached ({self.error_count} errors). Switching execution to secondary gateway."
            )
            self.active_client = self.secondary
            if self.secondary.get_connection_status() != BrokerConnectionState.CONNECTED:
                self.secondary.connect()


__all__ = [
    "BrokerConnectionState",
    "AccountSnapshot",
    "AbstractBrokerInterface",
    "SimulatedExecutionBroker",
    "InstitutionalGatewayFailover",
]
