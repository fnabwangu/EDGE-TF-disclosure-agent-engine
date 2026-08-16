"""schwab_bridge.py
Very small mock of Schwab bridge for tests.
"""
class SchwabBridge:
    def __init__(self, token: str = None):
        self.token = token

    def submit_order(self, payload: dict) -> dict:
        # Mock behavior for tests
        return {"status": "submitted", "order": payload}
## Charles Schwab Execution Bridge (`src/execution/schwab_bridge.py`)

The `schwab_bridge.py` module integrates the **EDGE-TF-disclosure-agent-engine** with the Charles Schwab Trader API. It handles OAuth2 token lifecycle management, account position auditing, equity basket order generation, option overlay execution (such as covered calls and short LEAP puts), and FIX-compatible execution status mapping.

---

### Key Capabilities

* **`OAuth2 Token Lifecycle`**: Automates token refresh routines, payload signing, and secure header construction.
* **`Multi-Asset Order Construction`**: Formats equity spot trades alongside derivative legs (covered calls, short puts) adhering to Schwab API schema.
* **`Position & Balances Reconciliation`**: Fetches real-time settled/unsettled cash balances, equity positions, and option contracts.
* **`AbstractBrokerInterface Conformance`**: Implements `AbstractBrokerInterface` for drop-in routing compatibility with the failover engine and TCA modules.
Python
# src/execution/schwab_bridge.py
"""
EDGE-TF Disclosure Agent Engine - Charles Schwab Broker Bridge.

Integrates with Charles Schwab Trader API for cash management, equity basket routing,
options overlay execution (covered calls, short LEAP puts), and account reconciliation.
"""

from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Optional
import requests

from src.execution import (
    ExecutionReport,
    ExecutionStatus,
    OrderInstruction,
    OrderType,
)
from src.execution.broker_interface import (
    AbstractBrokerInterface,
    AccountSnapshot,
    BrokerConnectionState,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


class SchwabBridge(AbstractBrokerInterface):
    """
    Charles Schwab REST API execution adapter for the EDGE-TF engine.
    Supports equity and options order execution, balance polling, and position auditing.
    """

    BASE_URL = "https://api.schwabapi.com/trader/v1"
    AUTH_URL = "https://api.schwabapi.com/v1/oauth/token"

    def __init__(
        self,
        app_key: str,
        app_secret: str,
        account_hash: str,
        refresh_token: str,
        session_timeout_seconds: int = 10
    ):
        self.app_key = app_key
        self.app_secret = app_secret
        self.account_hash = account_hash
        self.refresh_token = refresh_token
        self.timeout = session_timeout_seconds
        
        self.access_token: Optional[str] = None
        self.state: BrokerConnectionState = BrokerConnectionState.DISCONNECTED
        self.session = requests.Session()

    def connect(self) -> bool:
        """Refreshes the OAuth2 access token and verifies API connectivity."""
        self.state = BrokerConnectionState.CONNECTING
        try:
            payload = {
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
            }
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            
            response = self.session.post(
                self.AUTH_URL,
                data=payload,
                auth=(self.app_key, self.app_secret),
                headers=headers,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                self.access_token = data.get("access_token")
                self.session.headers.update({
                    "Authorization": f"Bearer {self.access_token}",
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                })
                self.state = BrokerConnectionState.CONNECTED
                logging.info("Successfully connected to Charles Schwab Trader API.")
                return True
            else:
                self.state = BrokerConnectionState.FAILED
                logging.error(f"Failed to authenticate with Schwab API: {response.status_code} {response.text}")
                return False

        except Exception as exc:
            self.state = BrokerConnectionState.FAILED
            logging.error(f"Error during Schwab connection handshake: {exc}")
            return False

    def disconnect(self) -> None:
        """Tears down the authenticated session."""
        self.access_token = None
        self.session.headers.pop("Authorization", None)
        self.state = BrokerConnectionState.DISCONNECTED
        logging.info("Disconnected from Charles Schwab Trader API.")

    def get_connection_status(self) -> BrokerConnectionState:
        return self.state

    def _map_order_type(self, order_type: OrderType) -> str:
        """Maps engine OrderType to Schwab API orderType enum."""
        mapping = {
            OrderType.MARKET: "MARKET",
            OrderType.LIMIT: "LIMIT",
            OrderType.VWAP: "MARKET",  # Handled via broker algo tags if supported
            OrderType.TWAP: "MARKET",
        }
        return mapping.get(order_type, "MARKET")

    def _build_order_payload(self, instruction: OrderInstruction) -> Dict[str, Any]:
        """Constructs Schwab Trader API compliant JSON order payload."""
        schwab_order_type = self._map_order_type(instruction.order_type)
        
        # Determine instruction type (Equity vs Options)
        action_upper = instruction.action.upper()
        if "CALL" in action_upper or "PUT" in action_upper or len(instruction.ticker) > 10:
            asset_type = "OPTION"
            instruction_str = "BUY_TO_OPEN" if "BUY" in action_upper else "SELL_TO_OPEN"
        else:
            asset_type = "EQUITY"
            instruction_str = "BUY" if "BUY" in action_upper else "SELL"

        order_leg = {
            "orderLegType": asset_type,
            "legId": 1,
            "instrument": {
                "assetType": asset_type,
                "symbol": instruction.ticker
            },
            "instruction": instruction_str,
            "quantity": abs(instruction.shares)
        }

        payload: Dict[str, Any] = {
            "orderType": schwab_order_type,
            "session": "NORMAL",
            "duration": instruction.time_in_force,
            "orderStrategyType": "SINGLE",
            "orderLegCollection": [order_leg]
        }

        if instruction.order_type == OrderType.LIMIT and instruction.limit_price:
            payload["price"] = round(instruction.limit_price, 2)

        return payload

    def submit_order(self, instruction: OrderInstruction) -> ExecutionReport:
        """Dispatches an order instruction to Schwab endpoints."""
        if self.state != BrokerConnectionState.CONNECTED or not self.access_token:
            raise ConnectionError("Schwab API bridge is not connected.")

        endpoint = f"{self.BASE_URL}/accounts/{self.account_hash}/orders"
        payload = self._build_order_payload(instruction)
        
        try:
            response = self.session.post(endpoint, json=payload, timeout=self.timeout)
            now_iso = datetime.now(timezone.utc).isoformat()
            
            if response.status_code in (200, 201):
                # Schwab returns Order ID in the 'Location' header URL
                location_header = response.headers.get("Location", "")
                order_id = location_header.split("/")[-1] if location_header else f"SCHWAB-{int(datetime.now().timestamp())}"
                
                return ExecutionReport(
                    order_id=order_id,
                    ticker=instruction.ticker,
                    action=instruction.action,
                    requested_shares=instruction.shares,
                    executed_shares=0,  # Async fill polling required
                    arrival_price=instruction.estimated_price,
                    average_fill_price=instruction.estimated_price,
                    status=ExecutionStatus.ROUTED,
                    slippage_bps=0.0,
                    routing_broker="CHARLES_SCHWAB",
                    execution_timestamp_utc=now_iso
                )
            else:
                logging.error(f"Schwab order rejected: {response.status_code} - {response.text}")
                return ExecutionReport(
                    order_id=f"REJ-{int(datetime.now().timestamp())}",
                    ticker=instruction.ticker,
                    action=instruction.action,
                    requested_shares=instruction.shares,
                    executed_shares=0,
                    arrival_price=instruction.estimated_price,
                    average_fill_price=0.0,
                    status=ExecutionStatus.REJECTED,
                    slippage_bps=0.0,
                    routing_broker="CHARLES_SCHWAB",
                    execution_timestamp_utc=now_iso
                )

        except Exception as exc:
            logging.error(f"Exception submitting order to Schwab: {exc}")
            raise exc

    def cancel_order(self, order_id: str) -> bool:
        """Cancels an existing order by ID."""
        if self.state != BrokerConnectionState.CONNECTED:
            raise ConnectionError("Schwab API bridge is not connected.")

        endpoint = f"{self.BASE_URL}/accounts/{self.account_hash}/orders/{order_id}"
        try:
            response = self.session.delete(endpoint, timeout=self.timeout)
            return response.status_code in (200, 204)
        except Exception as exc:
            logging.error(f"Failed to cancel Schwab order {order_id}: {exc}")
            return False

    def fetch_account_snapshot(self) -> AccountSnapshot:
        """Polls current account balances and position allocations."""
        if self.state != BrokerConnectionState.CONNECTED:
            raise ConnectionError("Schwab API bridge is not connected.")

        endpoint = f"{self.BASE_URL}/accounts/{self.account_hash}?fields=positions"
        response = self.session.get(endpoint, timeout=self.timeout)
        
        if response.status_code != 200:
            raise RuntimeError(f"Failed to fetch Schwab account data: {response.status_code} {response.text}")

        data = response.json().get("securitiesAccount", {})
        balances = data.get("currentBalances", {})
        raw_positions = data.get("positions", [])

        positions: Dict[str, int] = {}
        for pos in raw_positions:
            symbol = pos.get("instrument", {}).get("symbol")
            quantity = int(pos.get("longQuantity", 0) - pos.get("shortQuantity", 0))
            if symbol:
                positions[symbol] = quantity

        return AccountSnapshot(
            broker_id="CHARLES_SCHWAB",
            net_liquidation_value_usd=float(balances.get("liquidationValue", 0.0)),
            settled_cash_usd=float(balances.get("cashBalance", 0.0)),
            unsettled_cash_usd=float(balances.get("unsettledCash", 0.0)),
            positions=positions
        )


__all__ = ["SchwabBridge"]
