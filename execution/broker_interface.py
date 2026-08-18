"""Authoritative broker interface for execution adapters."""

from abc import ABC, abstractmethod
from typing import Any, Dict


class BrokerInterface(ABC):
    @abstractmethod
    def place_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError


__all__ = ["BrokerInterface"]
