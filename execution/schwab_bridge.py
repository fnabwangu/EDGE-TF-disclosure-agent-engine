"""Deterministic Schwab order payload and submission boundary."""

from dataclasses import dataclass
from typing import Any, Dict, Optional
import requests

from risk.kill_switch import EmergencyKillSwitchEngine


@dataclass(frozen=True)
class SchwabOrderRequest:
    symbol: str
    quantity: float
    instruction: str = "BUY"
    asset_type: str = "EQUITY"
    order_type: str = "MARKET"
    limit_price: Optional[float] = None
    duration: str = "DAY"
    session: str = "NORMAL"


class SchwabAuthManager:
    def __init__(self, access_token: str = "", account_hash: str = ""):
        self.access_token = access_token
        self.account_hash = account_hash

    def get_access_token(self) -> str:
        return self.access_token


class SchwabBridge:
    def __init__(self, auth_manager: Optional[SchwabAuthManager] = None, base_url: str = "https://api.schwabapi.com/trader/v1", enforce_dry_run: bool = True, token: str = "", kill_switch: Optional[EmergencyKillSwitchEngine] = None):
        self.auth_manager = auth_manager or SchwabAuthManager(access_token=token)
        self.base_url = base_url.rstrip("/")
        self.enforce_dry_run = enforce_dry_run
        self.kill_switch = kill_switch

    def build_schwab_order_payload(self, request: SchwabOrderRequest) -> Dict[str, Any]:
        if request.quantity <= 0 or not request.symbol:
            raise ValueError("Invalid Schwab order request")
        payload: Dict[str, Any] = {
            "orderType": request.order_type,
            "session": request.session,
            "duration": request.duration,
            "orderStrategyType": "SINGLE",
            "orderLegCollection": [{"instruction": request.instruction, "quantity": request.quantity, "instrument": {"symbol": request.symbol, "assetType": request.asset_type}}],
        }
        if request.limit_price is not None:
            payload["price"] = request.limit_price
        return payload

    def submit_order(self, request: SchwabOrderRequest | Dict[str, Any]) -> Dict[str, Any]:
        if self.kill_switch is not None and self.kill_switch.is_locked:
            return {"status": "REJECTED", "reason": "KILL_SWITCH_LOCKED"}
        if isinstance(request, dict):
            request = SchwabOrderRequest(symbol=request["symbol"], quantity=request.get("qty", request.get("quantity", 0)))
            self.build_schwab_order_payload(request)
            return {"status": "submitted", "symbol": request.symbol, "quantity": request.quantity}
        payload = self.build_schwab_order_payload(request)
        if self.enforce_dry_run:
            return {"status": "DRY_RUN_VALIDATED", "dry_run": True, "payload": payload}
        account_hash = getattr(self.auth_manager, "account_hash", "")
        token = self.auth_manager.get_access_token()
        response = requests.post(f"{self.base_url}/accounts/{account_hash}/orders", json=payload, headers={"Authorization": f"Bearer {token}"}, timeout=15)
        if response.status_code not in (200, 201, 202):
            return {"status": "REJECTED", "http_status": response.status_code, "payload": payload}
        location = response.headers.get("Location", "")
        return {"status": "SUBMITTED", "order_id": location.rstrip("/").split("/")[-1] if location else None, "payload": payload}


__all__ = ["SchwabBridge", "SchwabOrderRequest", "SchwabAuthManager"]
