"""
Edge-TF Disclosure Agent Engine - Position Sizer
Path: analytics/position_sizer.py

Converts approved (risk-capped) leverage into concrete shares, contracts, or
notional amounts. This is the final deterministic step before the Risk
Governor and Order Router; it performs no conviction or risk-cap logic of
its own.
"""

from __future__ import annotations

import math
from typing import List, Optional

from analytics.leverage_engine import LeverageDecision
from core.schemas import SizingResult


class PositionSizer:
    """Deterministic notional, share, and options-contract sizing."""

    @staticmethod
    def compute_target_notional(portfolio_nav: float, base_allocation: float, approved_leverage: float) -> float:
        """TargetNotional = PortfolioNAV * BaseAllocation * L*."""
        if portfolio_nav < 0 or base_allocation < 0 or approved_leverage < 0:
            raise ValueError("portfolio_nav, base_allocation, and approved_leverage must be non-negative")
        return portfolio_nav * base_allocation * approved_leverage

    @staticmethod
    def split_long_short(target_notional: float, long_weight: float = 0.5, short_weight: float = 0.5) -> tuple[float, float]:
        """Split target notional across a long/short spread structure."""
        if not math.isclose(long_weight + short_weight, 1.0, abs_tol=1e-6):
            raise ValueError("long_weight and short_weight must sum to 1.0")
        return target_notional * long_weight, target_notional * short_weight

    @staticmethod
    def shares_from_notional(notional: float, price: float) -> int:
        """Shares = floor(Notional / Price); non-positive price yields zero shares."""
        if price <= 0.0 or notional <= 0.0:
            return 0
        return math.floor(notional / price)

    @staticmethod
    def contracts_from_premium(allowed_premium_loss: float, premium_per_contract: float) -> int:
        """Contracts = floor(AllowedPremiumLoss / (Premium * 100)); sizes on premium-at-risk."""
        if premium_per_contract <= 0.0 or allowed_premium_loss <= 0.0:
            return 0
        return math.floor(allowed_premium_loss / (premium_per_contract * 100.0))

    def size_equity(
        self,
        leverage_decision: LeverageDecision,
        portfolio_nav: float,
        base_allocation: float,
        price: float,
        long_weight: float = 1.0,
        short_weight: float = 0.0,
    ) -> SizingResult:
        """Size a single-leg or long/short equity spread from approved leverage."""
        reason_codes = list(leverage_decision.reason_codes)
        target_notional = self.compute_target_notional(portfolio_nav, base_allocation, leverage_decision.approved_leverage)
        long_notional, short_notional = self.split_long_short(target_notional, long_weight, short_weight)

        long_shares = self.shares_from_notional(long_notional, price)
        short_shares = self.shares_from_notional(short_notional, price)
        shares = long_shares + short_shares if short_weight > 0.0 else long_shares

        execution_permitted = leverage_decision.approved_leverage > 0.0 and shares > 0
        if not execution_permitted:
            reason_codes.append("SIZING_ZERO_SHARES_NO_TRADE")

        return SizingResult(
            requested_leverage=leverage_decision.requested_leverage,
            approved_leverage=leverage_decision.approved_leverage,
            limiting_constraint=leverage_decision.limiting_constraint,
            target_notional=target_notional,
            long_notional=long_notional if short_weight > 0.0 else target_notional,
            short_notional=short_notional if short_weight > 0.0 else None,
            shares=shares,
            contracts=None,
            execution_permitted=execution_permitted,
            reason_codes=reason_codes,
        )

    def size_options(
        self,
        leverage_decision: LeverageDecision,
        portfolio_nav: float,
        base_allocation: float,
        premium_per_contract: float,
    ) -> SizingResult:
        """Size an options sleeve using premium-at-risk rather than underlying notional."""
        reason_codes = list(leverage_decision.reason_codes)
        allowed_premium_loss = self.compute_target_notional(portfolio_nav, base_allocation, leverage_decision.approved_leverage)
        contracts = self.contracts_from_premium(allowed_premium_loss, premium_per_contract)

        execution_permitted = leverage_decision.approved_leverage > 0.0 and contracts > 0
        if not execution_permitted:
            reason_codes.append("SIZING_ZERO_CONTRACTS_NO_TRADE")

        return SizingResult(
            requested_leverage=leverage_decision.requested_leverage,
            approved_leverage=leverage_decision.approved_leverage,
            limiting_constraint=leverage_decision.limiting_constraint,
            target_notional=allowed_premium_loss,
            long_notional=None,
            short_notional=None,
            shares=None,
            contracts=contracts,
            execution_permitted=execution_permitted,
            reason_codes=reason_codes,
        )


__all__ = ["PositionSizer"]
