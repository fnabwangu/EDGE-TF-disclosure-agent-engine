"""Authoritative broker interface for execution adapters."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Protocol, runtime_checkable


class BrokerInterface(ABC):
    @abstractmethod
    def place_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError


@runtime_checkable
class BrokerAdapter(Protocol):
    """
    Broker-agnostic adapter contract for the external execution service.

    One implementation per broker (Schwab, IBKR, Fidelity, ...). The execution
    service talks only to this shape, so adding a broker never changes the
    claim -> place -> report loop. Implementations live in the execution
    service repo, not in EDGE-TF.
    """

    broker_id: str

    def place_order(self, instruction: Dict[str, Any]) -> Dict[str, Any]:
        """Submit an ExecutionInstruction payload; return broker ack with order id."""
        ...

    def cancel_order(self, broker_order_id: str) -> Dict[str, Any]:
        ...

    def get_balances(self) -> Dict[str, Any]:
        """Cash and buying power, shaped for BrokerAccountSnapshot."""
        ...

    def get_positions(self) -> List[Dict[str, Any]]:
        """Open positions, shaped for BrokerAccountSnapshot.positions."""
        ...


class BrokerRegistry:
    """Name-keyed registry so the executor can route by instruction target."""

    def __init__(self) -> None:
        self._adapters: Dict[str, BrokerAdapter] = {}

    def register(self, adapter: BrokerAdapter) -> None:
        broker_id = getattr(adapter, "broker_id", "")
        if not broker_id:
            raise ValueError("adapter must expose a non-empty broker_id")
        if broker_id in self._adapters:
            raise ValueError(f"adapter already registered for {broker_id}")
        self._adapters[broker_id] = adapter

    def get(self, broker_id: str) -> BrokerAdapter:
        try:
            return self._adapters[broker_id]
        except KeyError:
            raise KeyError(f"no broker adapter registered for {broker_id}") from None

    def brokers(self) -> List[str]:
        return sorted(self._adapters)


__all__ = ["BrokerAdapter", "BrokerInterface", "BrokerRegistry"]
