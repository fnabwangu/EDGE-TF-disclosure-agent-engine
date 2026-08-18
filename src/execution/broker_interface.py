"""Legacy compatibility shim; use execution.broker_interface."""

from execution.broker_interface import BrokerInterface

__all__ = ["BrokerInterface"]
