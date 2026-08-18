"""
Edge-TF Disclosure Agent Engine - Leverage Engine
Path: analytics/leverage_engine.py

Converts a conviction-derived *requested* leverage into a risk-capped,
approved leverage. Conviction never equals leverage directly: this module
computes independent loss-budget, volatility, liquidity, concentration, and
portfolio caps and applies the deterministic rule

    L* = min(L_requested, L_max_absolute, L_loss, L_vol, L_liquidity,
              L_concentration, L_portfolio)

so that risk rules can always override signal strength.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from core.schemas import LeverageLimits


@dataclass(frozen=True)
class LeverageDecision:
    """Auditable leverage decision with every candidate cap preserved."""

    requested_leverage: float
    approved_leverage: float
    limiting_constraint: str
    caps: Dict[str, float] = field(default_factory=dict)
    reason_codes: List[str] = field(default_factory=list)


class LeverageEngine:
    """Applies deterministic, config-driven risk caps to requested leverage."""

    @staticmethod
    def compute_loss_budget_cap(worst_case_loss_pct: float, max_trade_loss_pct: float) -> float:
        """L_loss = max_trade_loss_pct / |worst_case_loss_pct|; undefined risk caps to zero."""
        magnitude = abs(worst_case_loss_pct)
        if magnitude <= 0.0:
            return 0.0
        return max_trade_loss_pct / magnitude

    @staticmethod
    def compute_volatility_cap(strategy_volatility: float, target_volatility: float) -> float:
        """L_vol = target_volatility / strategy_volatility; zero/negative vol caps to zero."""
        if strategy_volatility <= 0.0:
            return 0.0
        return target_volatility / strategy_volatility

    @staticmethod
    def compute_liquidity_cap(base_strategy_notional: float, maximum_executable_notional: float) -> float:
        """L_liq = maximum_executable_notional / base_strategy_notional."""
        if base_strategy_notional <= 0.0:
            return 0.0
        return maximum_executable_notional / base_strategy_notional

    def evaluate(
        self,
        requested_leverage: float,
        limits: LeverageLimits,
        worst_case_loss_pct: float,
        strategy_volatility: float,
        base_strategy_notional: float,
        maximum_executable_notional: float,
    ) -> LeverageDecision:
        """Compute every independent cap and select the binding constraint."""
        reason_codes: List[str] = []
        if requested_leverage < 0:
            raise ValueError("requested_leverage cannot be negative")

        loss_cap = self.compute_loss_budget_cap(worst_case_loss_pct, limits.max_trade_loss_pct)
        vol_cap = self.compute_volatility_cap(strategy_volatility, limits.volatility_limit)
        liquidity_cap = self.compute_liquidity_cap(base_strategy_notional, maximum_executable_notional)

        caps = {
            "requested_leverage": requested_leverage,
            "max_absolute_leverage": limits.max_absolute_leverage,
            "loss_budget_cap": loss_cap,
            "volatility_cap": vol_cap,
            "liquidity_cap": liquidity_cap,
            "concentration_limit": limits.concentration_limit,
            "portfolio_limit": limits.portfolio_limit,
        }

        limiting_constraint = min(caps, key=lambda name: caps[name])
        approved_leverage = max(0.0, caps[limiting_constraint])

        if limiting_constraint != "requested_leverage":
            reason_codes.append(f"LEVERAGE_CAPPED_BY_{limiting_constraint.upper()}")
        else:
            reason_codes.append("LEVERAGE_UNCONSTRAINED_BY_RISK_CAPS")
        if approved_leverage <= 0.0:
            reason_codes.append("LEVERAGE_ZERO_NO_TRADE")

        return LeverageDecision(
            requested_leverage=requested_leverage,
            approved_leverage=approved_leverage,
            limiting_constraint=limiting_constraint,
            caps=caps,
            reason_codes=reason_codes,
        )


__all__ = ["LeverageDecision", "LeverageEngine"]
