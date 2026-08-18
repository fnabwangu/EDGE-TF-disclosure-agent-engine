"""
EDGE-TF Disclosure Agent Engine - Indicative Intra-Day Value (IIV / INAV / IAV) Calculator.

Path: analytics/iav_calculator.py

Complies with SEC Rule 6c-11 requirements by computing real-time, intra-day indicative NAV
across equity holdings, cash buffers, and derivatives overlays.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


@dataclass
class OptionPositionState:
    """State tracking for open derivatives overlay positions."""
    symbol: str
    underlying_ticker: str
    option_type: str  # "CALL" or "PUT"
    contracts: int    # Positive for long, negative for short (e.g. -10 for 10 short contracts)
    strike_price: float
    dte_years: float
    implied_volatility: float
    risk_free_rate: float = 0.045


@dataclass
class IAVSnapshot:
    """Real-time calculated indicative value state container."""
    timestamp_utc: str
    indicative_nav_per_share: float
    total_gross_asset_value: float
    total_net_asset_value: float
    equity_component_value: float
    options_overlay_liability_value: float
    cash_and_accruals_value: float
    total_shares_outstanding: int
    etf_market_price: Optional[float]
    premium_discount_bps: Optional[float]
    dislocation_flag: bool
    details: Dict[str, Any] = field(default_factory=dict)


class IAVCalculator:
    """
    Computes real-time Indicative Intra-Day Value (IAV / INAV) for ETF shares
    and evaluates secondary-market premium/discount dislocations.
    """

    def __init__(
        self,
        total_shares_outstanding: int,
        creation_unit_size: int = 25_000,
        dislocation_threshold_bps: float = 20.0,
        annual_expense_ratio: float = 0.0075,  # 75 bps management fee
    ):
        self.shares_outstanding = total_shares_outstanding
        self.creation_unit_size = creation_unit_size
        self.dislocation_threshold_bps = dislocation_threshold_bps
        self.daily_expense_drag = annual_expense_ratio / 365.0

    @staticmethod
    def _black_scholes_price(
        option_type: str,
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
    ) -> float:
        """Standard closed-form Black-Scholes valuation for intra-day option repricing."""
        if T <= 0.0 or sigma <= 0.0 or S <= 0.0 or K <= 0.0:
            # Intrinsic value at expiration or edge cases
            if option_type.upper() == "CALL":
                return max(0.0, S - K)
            return max(0.0, K - S)

        d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)

        # Standard normal CDF approximation (erf)
        cdf_d1 = 0.5 * (1.0 + math.erf(d1 / math.sqrt(2.0)))
        cdf_d2 = 0.5 * (1.0 + math.erf(d2 / math.sqrt(2.0)))

        if option_type.upper() == "CALL":
            price = S * cdf_d1 - K * math.exp(-r * T) * cdf_d2
        else:  # PUT
            cdf_neg_d1 = 0.5 * (1.0 + math.erf(-d1 / math.sqrt(2.0)))
            cdf_neg_d2 = 0.5 * (1.0 + math.erf(-d2 / math.sqrt(2.0)))
            price = K * math.exp(-r * T) * cdf_neg_d2 - S * cdf_neg_d1

        return max(0.0, price)

    def calculate_iav(
        self,
        spot_positions: Dict[str, int],
        current_prices: Dict[str, float],
        options_positions: List[OptionPositionState],
        settled_cash: float,
        etf_secondary_market_price: Optional[float] = None,
        accrued_income: float = 0.0,
    ) -> IAVSnapshot:
        """
        Executes a real-time synthetic NAV calculation cycle.
        """
        now_ts = datetime.now(timezone.utc).isoformat()

        # 1. Calculate Equity Valuation Component
        equity_nav = 0.0
        position_breakdown: Dict[str, float] = {}

        for ticker, shares in spot_positions.items():
            price = current_prices.get(ticker.upper(), 0.0)
            val = shares * price
            equity_nav += val
            position_breakdown[ticker] = val

        # 2. Calculate Options Overlay Fair Value (Liability/Asset)
        options_nav = 0.0
        options_breakdown: Dict[str, float] = {}

        for opt in options_positions:
            underlying_px = current_prices.get(opt.underlying_ticker.upper(), 0.0)
            if underlying_px > 0:
                unit_fair_value = self._black_scholes_price(
                    option_type=opt.option_type,
                    S=underlying_px,
                    K=opt.strike_price,
                    T=opt.dte_years,
                    r=opt.risk_free_rate,
                    sigma=opt.implied_volatility,
                )
                # 1 contract = 100 shares
                total_opt_val = opt.contracts * 100 * unit_fair_value
                options_nav += total_opt_val
                options_breakdown[opt.symbol] = total_opt_val

        # 3. Cash & Daily Accrued Expense Drag
        gross_assets = equity_nav + settled_cash + accrued_income
        accrued_fee = gross_assets * self.daily_expense_drag
        net_cash_accruals = settled_cash + accrued_income - accrued_fee

        total_net_asset_value = equity_nav + options_nav + net_cash_accruals
        iav_per_share = (
            total_net_asset_value / self.shares_outstanding
            if self.shares_outstanding > 0
            else 0.0
        )

        # 4. Premium / Discount & Dislocation Analysis
        premium_discount_bps = None
        dislocation_flag = False

        if etf_secondary_market_price and etf_secondary_market_price > 0 and iav_per_share > 0:
            spread = etf_secondary_market_price - iav_per_share
            premium_discount_bps = round((spread / iav_per_share) * 10_000, 2)
            if abs(premium_discount_bps) >= self.dislocation_threshold_bps:
                dislocation_flag = True
                logging.warning(
                    f"IAV Dislocation Alert: ETF trading at {premium_discount_bps:+.1f} bps "
                    f"(Market: ${etf_secondary_market_price:.2f}, IAV: ${iav_per_share:.2f})."
                )

        return IAVSnapshot(
            timestamp_utc=now_ts,
            indicative_nav_per_share=round(iav_per_share, 4),
            total_gross_asset_value=round(gross_assets, 2),
            total_net_asset_value=round(total_net_asset_value, 2),
            equity_component_value=round(equity_nav, 2),
            options_overlay_liability_value=round(options_nav, 2),
            cash_and_accruals_value=round(net_cash_accruals, 2),
            total_shares_outstanding=self.shares_outstanding,
            etf_market_price=etf_secondary_market_price,
            premium_discount_bps=premium_discount_bps,
            dislocation_flag=dislocation_flag,
            details={
                "equity_positions": position_breakdown,
                "options_positions": options_breakdown,
                "creation_unit_iav": round(iav_per_share * self.creation_unit_size, 2),
            },
        )


__all__ = [
    "OptionPositionState",
    "IAVSnapshot",
    "IAVCalculator",
]
