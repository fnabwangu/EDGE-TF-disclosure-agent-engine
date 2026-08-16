"""broker_interface.py
Abstract execution base class (placeholder).
"""
from abc import ABC, abstractmethod

class BrokerInterface(ABC):
    @abstractmethod
    def place_order(self, order):
        raise NotImplementedError
