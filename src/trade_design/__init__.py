# src/trade_design/__init__.py
"""
EDGE-TF Disclosure Agent Engine - Systematic Trade Design & Options Structuring Module.

Coordinates options overlay generation, covered call strike selection, short LEAP put
cash-secured sizing, delta-hedging ratios, and collateral requirement modeling adhering
to SEC Rule 18f-4 derivatives risk governance and IRC Subchapter M asset segregation.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
from typing import Any, Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


class OptionsStrategyType(str, Enum):
    COVERED_CALL_OVERLAY = "COVERED_CALL_OVERLAY"
    SHORT_LEAP_PUT = "SHORT_LEAP_PUT"
    COLLAR_OVERLAY = "COLLAR_OVERLAY"
    CASH_SECURED_EQUITY_PUT = "CASH_SECURED_EQUITY_PUT"


class ExecutionUrgency(str, Enum):
    PASSIVE_MAKER = "PASSIVE_MAKER"
    TWAP_SCHEDULED = "TWAP_SCHEDULED"
    VWAP_BENCHMARK = "VWAP_BENCHMARK"
    IMMEDIATE_TAKER = "IMMEDIATE_TAKER"


@dataclass
class StructuredTradeProposal:
    trade_id: str
    strategy_type: OptionsStrategyType
    underlying_ticker: str
    action: str  # e.g., "SELL_TO_OPEN", "BUY_TO_CLOSE"
    contract_symbol: str
    strike_price: float
    expiration_date: str
    dte_days: int
    target_contracts: int
    underlying_shares_held: int
    delta: float
    theta_daily_usd: float
    estimated_premium_per_share: float
    estimated_total_proceeds_usd: float
    collateral_required_usd: float
    is_fully_covered: bool
    urgency: ExecutionUrgency = ExecutionUrgency.PASSIVE_MAKER
    timestamp_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trade_id": self.trade_id,
            "strategy_type": self.strategy_type.value,
            "underlying_ticker": self.underlying_ticker,
            "action": self.action,
            "contract_symbol": self.contract_symbol,
            "strike_price": self.strike_price,
            "expiration_date": self.expiration_date,
            "dte_days": self.dte_days,
            "target_contracts": self.target_contracts,
            "underlying_shares_held": self.underlying_shares_held,
            "delta": self.delta,
            "theta_daily_usd": self.theta_daily_usd,
            "estimated_premium_per_share": self.estimated_premium_per_share,
            "estimated_total_proceeds_usd": self.estimated_total_proceeds_usd,
            "collateral_required_usd": self.collateral_required_usd,
            "is_fully_covered": self.is_fully_covered,
            "urgency": self.urgency.value,
            "timestamp_utc": self.timestamp_utc,
        }


class TradeDesignGovernor:
    """
    Validates structural derivatives risk and coverage constraints
    prior to submitting proposals to the execution router.
    """

    @staticmethod
    def validate_covered_call_backing(
        shares_held: int,
        contracts_to_write: int,
    ) -> Tuple[bool, str]:
        """
        Enforces 100:1 share backing per call contract to eliminate naked short risk.
        """
        required_shares = contracts_to_write * 100
        if shares_held < required_shares:
            return (
                False,
                f"Deficient share collateral: Requires {required_shares} shares, but only {shares_held} held.",
            )
        return True, "Fully backed by underlying equity."

    @staticmethod
    def validate_short_leap_put_cash_backing(
        settled_cash: float,
        strike_price: float,
        contracts_to_write: int,
    ) -> Tuple[bool, str]:
        """
        Verifies 100% cash-secured collateral for short put positions.
        """
        required_cash = strike_price * 100 * contracts_to_write
        if settled_cash < required_cash:
            return (
                False,
                f"Insufficient cash segregation: Requires ${required_cash:,.2f}, available ${settled_cash:,.2f}.",
            )
        return True, "100% cash secured."


__all__ = [
    "OptionsStrategyType",
    "ExecutionUrgency",
    "StructuredTradeProposal",
    "TradeDesignGovernor",
]# trade_design package
