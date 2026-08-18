"""Deterministic order dispatch boundary."""

from dataclasses import dataclass
from typing import Any, Dict, Protocol


@dataclass(frozen=True)
class OrderRequest:
    symbol: str
    quantity: float
    side: str
    order_type: str = "LIMIT"
    limit_price: float = 0.0


class BrokerClient(Protocol):
    def submit_order(self, request: OrderRequest) -> Dict[str, Any]: ...


class OrderRouter:
    """Routes only orders that have already passed a hard execution gate."""

    def __init__(self, broker: BrokerClient):
        self.broker = broker

    def route(self, request: OrderRequest, execution_permitted: bool) -> Dict[str, Any]:
        if not execution_permitted:
            return {"status": "REJECTED", "reason": "Deterministic execution gate failed"}
        if request.quantity <= 0 or request.symbol.strip() == "":
            return {"status": "REJECTED", "reason": "Invalid order request"}
        return self.broker.submit_order(request)


__all__ = ["OrderRequest", "BrokerClient", "OrderRouter"]
