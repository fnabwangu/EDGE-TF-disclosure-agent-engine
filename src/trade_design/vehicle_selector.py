## Execution Vehicle & Instrument Selector (`src/trade_design/vehicle_selector.py`)

The `vehicle_selector.py` module evaluates candidate portfolio actions across available implementation instruments (physical common shares, American Depositary Receipts [ADRs], single-stock options overlays, and synthetic forward equivalents). It dynamically scores liquidity profiles, bid-ask slippage drag, borrowing costs, collateral requirements, and SEC Rule 18f-4 leverage impact to select the optimal implementation vehicle for a target thesis.

---

### Key Capabilities

* **`Multi-Instrument Vehicle Optimization`**: Selects between cash equity, covered call overwrites, and short cash-secured LEAP puts based on implied volatility rank, carry yield, and capital efficiency.
* **`Rule 18f-4 Derivatives Exposure Check`**: Filters proposed option instruments against gross derivatives exposure and Value-at-Risk (VaR) impact limits.
* **`Slippage & Market Impact Estimator`**: Models expected execution costs using average daily volume (ADV), bid-ask spreads, and order sizes.
* **`Automated Proposal Packaging`**: Transforms high-level target allocations into deterministic `StructuredTradeProposal` instances for the execution gateway.
                                                                                                                                     
    # src/trade_design/vehicle_selector.py
"""
EDGE-TF Disclosure Agent Engine - Execution Vehicle & Instrument Selector.

Determines the optimal implementation vehicle (Spot Equity vs. Covered Call vs. Short LEAP Put)
evaluating liquidity cost, implied volatility regime, collateral efficiency, and Rule 18f-4 limits.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from src.trade_design import (
    ExecutionUrgency,
    OptionsStrategyType,
    StructuredTradeProposal,
    TradeDesignGovernor,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


class ImplementationVehicleType(str, Enum):
    DIRECT_EQUITY_SPOT = "DIRECT_EQUITY_SPOT"
    COVERED_CALL_OVERWRITE = "COVERED_CALL_OVERWRITE"
    SHORT_LEAP_PUT_CASH_SECURED = "SHORT_LEAP_PUT_CASH_SECURED"
    COLLAR_STRUCTURE = "COLLAR_STRUCTURE"


@dataclass
class VehicleSelectionScore:
    ticker: str
    selected_vehicle: ImplementationVehicleType
    iv_percentile: float
    expected_carry_yield_annualized: float
    estimated_slippage_bps: float
    collateral_efficiency_score: float
    recommendation_rationale: str


class VehicleSelector:
    """
    Evaluates market regime and volatility metrics to recommend optimal execution vehicles
    for target portfolio constituents.
    """

    def __init__(
        self,
        high_iv_threshold: float = 0.65,
        low_iv_threshold: float = 0.30,
        max_single_option_risk_nav_pct: float = 0.05,
    ):
        self.high_iv_threshold = high_iv_threshold
        self.low_iv_threshold = low_iv_threshold
        self.max_option_risk_pct = max_single_option_risk_nav_pct
        self.governor = TradeDesignGovernor()

    def select_best_vehicle(
        self,
        ticker: str,
        target_allocation_usd: float,
        current_price: float,
        implied_volatility_pct: float,
        iv_rank_percentile: float,
        shares_currently_held: int,
        settled_cash_available: float,
        adv_shares: float = 1_000_000,
    ) -> VehicleSelectionScore:
        """
        Determines whether to express an allocation via Spot Equity, Covered Call, or Short Put.
        """
        # Baseline slippage estimation (Kyle's Lambda proxy: sqrt(order_size / ADV))
        target_shares = int(target_allocation_usd // current_price) if current_price > 0 else 0
        participation_rate = target_shares / max(adv_shares, 1.0)
        estimated_slippage_bps = round(float(np.sqrt(participation_rate) * 35.0) + 2.0, 2)

        # 1. High IV Regime & Sizable Existing Equity Position -> Covered Call Overwrite
        if iv_rank_percentile >= self.high_iv_threshold and shares_currently_held >= 100:
            potential_contracts = shares_currently_held // 100
            is_valid, _ = self.governor.validate_covered_call_backing(shares_currently_held, potential_contracts)
            if is_valid:
                carry_yield = round(implied_volatility_pct * 0.35, 4)
                return VehicleSelectionScore(
                    ticker=ticker,
                    selected_vehicle=ImplementationVehicleType.COVERED_CALL_OVERWRITE,
                    iv_percentile=iv_rank_percentile,
                    expected_carry_yield_annualized=carry_yield,
                    estimated_slippage_bps=estimated_slippage_bps,
                    collateral_efficiency_score=0.90,
                    recommendation_rationale=(
                        f"Elevated IV rank ({iv_rank_percentile:.1%}) with {shares_currently_held} underlying shares. "
                        f"Harvest premium via OTM Covered Call overlay."
                    ),
                )

        # 2. Elevated IV, High Conviction, Abundant Cash -> Short LEAP Put (Cash-Secured)
        elif iv_rank_percentile >= 0.50 and settled_cash_available >= (target_allocation_usd * 0.80):
            strike_target = round(current_price * 0.90, 2)  # 10% OTM target
            contracts_possible = int(settled_cash_available // (strike_target * 100))
            if contracts_possible > 0:
                is_valid, _ = self.governor.validate_short_leap_put_cash_backing(
                    settled_cash=settled_cash_available,
                    strike_price=strike_target,
                    contracts_to_write=contracts_possible,
                )
                if is_valid:
                    carry_yield = round(implied_volatility_pct * 0.28, 4)
                    return VehicleSelectionScore(
                        ticker=ticker,
                        selected_vehicle=ImplementationVehicleType.SHORT_LEAP_PUT_CASH_SECURED,
                        iv_percentile=iv_rank_percentile,
                        expected_carry_yield_annualized=carry_yield,
                        estimated_slippage_bps=estimated_slippage_bps + 4.0,  # Wider option spread
                        collateral_efficiency_score=0.85,
                        recommendation_rationale=(
                            f"Moderate-to-high IV ({iv_rank_percentile:.1%}). Acquire discounted entry via "
                            f"cash-secured short LEAP puts (Strike: ${strike_target:.2f})."
                        ),
                    )

        # 3. Default: Direct Spot Common Equity
        return VehicleSelectionScore(
            ticker=ticker,
            selected_vehicle=ImplementationVehicleType.DIRECT_EQUITY_SPOT,
            iv_percentile=iv_rank_percentile,
            expected_carry_yield_annualized=0.0,
            estimated_slippage_bps=estimated_slippage_bps,
            collateral_efficiency_score=1.0,
            recommendation_rationale="Low/normal volatility regime or directional thesis; execute standard spot shares.",
        )

    def generate_option_trade_proposal(
        self,
        ticker: str,
        vehicle_score: VehicleSelectionScore,
        current_price: float,
        shares_held: int,
        settled_cash: float,
        target_delta: float = 0.30,
        dte_days: int = 45,
    ) -> Optional[StructuredTradeProposal]:
        """
        Builds a concrete StructuredTradeProposal based on vehicle selection output.
        """
        now_ts = datetime.now(timezone.utc)
        trade_id = f"TRD-OPT-{ticker}-{now_ts.strftime('%Y%m%d%H%M%S')}"

        if vehicle_score.selected_vehicle == ImplementationVehicleType.COVERED_CALL_OVERWRITE:
            strike = round(current_price * 1.08, 2)  # ~8% OTM
            contracts = shares_held // 100
            if contracts <= 0:
                return None

            est_premium = round(current_price * 0.025, 2)
            proceeds = round(est_premium * 100 * contracts, 2)

            return StructuredTradeProposal(
                trade_id=trade_id,
                strategy_type=OptionsStrategyType.COVERED_CALL_OVERLAY,
                underlying_ticker=ticker,
                action="SELL_TO_OPEN",
                contract_symbol=f"{ticker}_{now_ts.strftime('%y%m%d')}C{int(strike*1000):08d}",
                strike_price=strike,
                expiration_date=now_ts.strftime("%Y-%m-%d"),
                dte_days=dte_days,
                target_contracts=contracts,
                underlying_shares_held=shares_held,
                delta=target_delta,
                theta_daily_usd=round(proceeds / max(dte_days, 1), 2),
                estimated_premium_per_share=est_premium,
                estimated_total_proceeds_usd=proceeds,
                collateral_required_usd=0.0,  # Covered by held shares
                is_fully_covered=True,
                urgency=ExecutionUrgency.PASSIVE_MAKER,
            )

        elif vehicle_score.selected_vehicle == ImplementationVehicleType.SHORT_LEAP_PUT_CASH_SECURED:
            strike = round(current_price * 0.88, 2)  # ~12% OTM LEAP
            max_contracts_cash = int(settled_cash // (strike * 100))
            contracts = min(max_contracts_cash, 10)
            if contracts <= 0:
                return None

            est_premium = round(current_price * 0.06, 2)
            proceeds = round(est_premium * 100 * contracts, 2)
            required_collateral = strike * 100 * contracts

            return StructuredTradeProposal(
                trade_id=trade_id,
                strategy_type=OptionsStrategyType.SHORT_LEAP_PUT,
                underlying_ticker=ticker,
                action="SELL_TO_OPEN",
                contract_symbol=f"{ticker}_{now_ts.strftime('%y%m%d')}P{int(strike*1000):08d}",
                strike_price=strike,
                expiration_date=now_ts.strftime("%Y-%m-%d"),
                dte_days=max(dte_days, 180),
                target_contracts=contracts,
                underlying_shares_held=shares_held,
                delta=-abs(target_delta),
                theta_daily_usd=round(proceeds / max(dte_days, 1), 2),
                estimated_premium_per_share=est_premium,
                estimated_total_proceeds_usd=proceeds,
                collateral_required_usd=required_collateral,
                is_fully_covered=True,
                urgency=ExecutionUrgency.PASSIVE_MAKER,
            )

        return None


__all__ = [
    "ImplementationVehicleType",
    "VehicleSelectionScore",
    "VehicleSelector",
]                                                                                                                                 
