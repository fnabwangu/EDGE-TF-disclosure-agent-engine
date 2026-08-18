"""Backward-compatible exports for the relocated execution layer."""

from execution.order_router import BrokerClient, OrderRequest, OrderRouter
from execution.schwab_bridge import SchwabAuthManager, SchwabBridge, SchwabOrderRequest

OrderInstruction = OrderRequest
OrderType = str

__all__ = [
    "BrokerClient",
    "OrderRequest",
    "OrderRouter",
    "SchwabAuthManager",
    "SchwabBridge",
    "SchwabOrderRequest",
    "OrderInstruction",
    "OrderType",
]
