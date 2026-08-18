"""options_modeler.py
Placeholder for options greeks and IV surfaces.
"""

def price_option():
    return {"price": 0.0}
"""========================================================================================
MODULE: Options Modeler & Duration Matching Engine (src/trade_design/options_modeler.py)
PURPOSE: Structure derivative expressions (e.g., deep ITM LEAPS, vertical call spreads) 
         by aligning option maturity and Greek profiles directly with thesis horizon.
========================================================================================

INPUT:
    - thesis_horizon_months: Multi-quarter fundamental thesis duration (e.g., 12-24m)[cite: 1, 2].
    - underlying_price (S): Current spot price of the underlying candidate[cite: 1].
    - options_chain_df: Available strikes, expiries, bid/ask spreads, IV, and open interest[cite: 1].
    - delta_target (Δ): Target directional sensitivity (e.g., 0.70 ITM calls)[cite: 1].
    - risk_free_rate (r) & dividend_yield (q): Yield inputs for pricing and Greeks[cite: 1].

STEP 1: THESIS DURATION MATCHING
    SET target_days = thesis_horizon_months * 30[cite: 1, 2]
    SELECT available option expiry T from chain closest to target_days WHERE T >= target_days[cite: 1, 2].
    COMMENT: Avoids mismatched short-duration contracts for multi-quarter thesis cycles[cite: 1, 2].

STEP 2: GREEKS SURFACE COMPUTATION & STRIKE SEARCH
    FOR EACH call strike K IN selected_expiry:
        COMPUTE Black-Scholes-Merton Price, Delta (Δ), Gamma (Γ), Theta (Θ), Vega (ν)[cite: 1].
    FILTER strikes where Delta (Δ) is closest to delta_target (e.g., 0.70 ITM)[cite: 1].
    ASSIGN long_strike = K_selected[cite: 1].

STEP 3: SPREAD TOPOLOGY vs OUTRIGHT ASYMMETRY EVALUATION
    IF Implied Volatility (IV) > Historical Volatility (HV) (Expensive Premium):
        STRUCTURE Vertical Call Spread:
            - BUY Long Call at long_strike (Delta ~ 0.70)[cite: 1]
            - SELL Short Call at short_strike = underlying_price * (1.0 + upside_target_pct)[cite: 1]
        CALCULATE Net Debit, Max Loss = Net Debit, Max Gain = (short_strike - long_strike) - Net Debit[cite: 1].
    ELSE:
        STRUCTURE Outright LEAP Call:
            - BUY Long Call at long_strike (Delta ~ 0.70)[cite: 1]
            - Max Gain = Uncapped, Capital at Risk = Premium Paid[cite: 1].

STEP 4: MULTI-SCENARIO PAYOFF SIMULATION
    SIMULATE PnL across a 2D matrix of:
        - Underlying terminal price: [-30%, -15%, 0%, +15%, +30%, +50%][cite: 1]
        - Implied Volatility shifts: [-5% IV, 0% IV, +5% IV][cite: 1]
        - Time decay progression: [t = 0, t = horizon / 2, t = expiry][cite: 1]

STEP 5: LIQUIDITY & IMPLEMENTATION FIT VALIDATION
    VERIFY:
        - Open Interest >= min_open_interest (e.g., 500 contracts)[cite: 1]
        - Bid-Ask Spread / Mid Price <= max_slippage_pct[cite: 1]
    IF validation fails:
        FLAG instrument as LIQUIDITY_CONSTRAINED and degrade implementation score[cite: 1].

OUTPUT:
    - Structured options payload with [structure_type, expiry, long_strike, short_strike, 
      delta, net_debit, max_risk, scenario_matrix, liquidity_status][cite: 1].
Edge-TF / Reverse Engineering Alpha Engine
Module: src/trade_design/options_modeler.py
Purpose: Perform duration-matched derivative structuring, Greek surface evaluation,
         and multi-scenario payoff simulation for strategic trade candidates.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from scipy.stats import norm


@dataclass
class OptionContract:
    symbol: str
    strike: float
    expiry_days: int
    option_type: str
    bid: float
    ask: float
    implied_vol: float
    open_interest: int


@dataclass
class OptionGreeks:
    price: float
    delta: float
    gamma: float
    theta: float
    vega: float


class BlackScholesEngine:
    """Calculates Black-Scholes pricing and analytical Greek surfaces."""

    @staticmethod
    def calculate_call_greeks(
        S: float,
        K: float,
        T_years: float,
        r: float,
        sigma: float,
        q: float = 0.0,
    ) -> OptionGreeks:
        if T_years <= 0 or sigma <= 0:
            intrinsic = max(0.0, S - K)
            return OptionGreeks(
                price=intrinsic,
                delta=1.0 if S > K else 0.0,
                gamma=0.0,
                theta=0.0,
                vega=0.0,
            )

        d1 = (
            np.log(S / K) + (r - q + 0.5 * sigma**2) * T_years
        ) / (sigma * np.sqrt(T_years))
        d2 = d1 - sigma * np.sqrt(T_years)

        price = S * np.exp(-q * T_years) * norm.cdf(d1) - K * np.exp(
            -r * T_years
        ) * norm.cdf(d2)
        delta = np.exp(-q * T_years) * norm.cdf(d1)
        gamma = (np.exp(-q * T_years) * norm.pdf(d1)) / (
            S * sigma * np.sqrt(T_years)
        )
        theta = -(
            S * sigma * np.exp(-q * T_years) * norm.pdf(d1)
        ) / (2 * np.sqrt(T_years)) - r * K * np.exp(-r * T_years) * norm.cdf(
            d2
        ) + q * S * np.exp(-q * T_years) * norm.cdf(d1)
        # Convert theta to 1-day decay
        theta = theta / 365.0
        # Convert vega to 1% IV change
        vega = S * np.exp(-q * T_years) * norm.pdf(d1) * np.sqrt(T_years) / 100.0

        return OptionGreeks(
            price=float(price),
            delta=float(delta),
            gamma=float(gamma),
            theta=float(theta),
            vega=float(vega),
        )


def select_duration_matched_expiry(
    available_expiries_days: List[int],
    target_horizon_months: int,
) -> int:
    """Selects the closest available expiry that is greater than or equal to the thesis horizon."""
    target_days = target_horizon_months * 30
    viable = [d for d in available_expiries_days if d >= target_days]
    if not viable:
        # Fall back to maximum available duration if target exceeds chain
        return max(available_expiries_days)
    return min(viable)


def structure_leap_expression(
    underlying_price: float,
    thesis_horizon_months: int,
    available_contracts: List[OptionContract],
    target_delta: float = 0.70,
    r: float = 0.045,
    q: float = 0.0,
    upside_target_pct: float = 0.35,
    min_open_interest: int = 500,
) -> Dict[str, Any]:
    """Designs an optimal duration-matched derivative expression (ITM LEAP vs Call Spread)."""
    expiries = list({c.expiry_days for c in available_contracts})
    selected_expiry = select_duration_matched_expiry(
        expiries, thesis_horizon_months
    )

    contracts_at_expiry = [
        c
        for c in available_contracts
        if c.expiry_days == selected_expiry and c.option_type.upper() == "CALL"
    ]

    if not contracts_at_expiry:
        raise ValueError(
            f"No call contracts available for expiry {selected_expiry} days."
        )

    # 1. Compute Greeks across available strikes to find target delta
    T_years = selected_expiry / 365.0
    scored_contracts = []

    for c in contracts_at_expiry:
        mid_price = (c.bid + c.ask) / 2.0
        greeks = BlackScholesEngine.calculate_call_greeks(
            S=underlying_price,
            K=c.strike,
            T_years=T_years,
            r=r,
            sigma=c.implied_vol,
            q=q,
        )
        scored_contracts.append(
            {
                "contract": c,
                "mid_price": mid_price,
                "greeks": greeks,
                "delta_diff": abs(greeks.delta - target_delta),
            }
        )

    # Sort to locate contract closest to delta target
    scored_contracts.sort(key=lambda x: x["delta_diff"])
    best_long = scored_contracts[0]
    long_contract: OptionContract = best_long["contract"]
    long_greeks: OptionGreeks = best_long["greeks"]

    # 2. Check for elevated volatility to determine if spread dominant
    avg_iv = np.mean([c.implied_vol for c in contracts_at_expiry])
    structure_type = "OUTRIGHT_LEAP_CALL"
    short_contract: Optional[OptionContract] = None
    short_greeks: Optional[OptionGreeks] = None

    target_short_strike = underlying_price * (1.0 + upside_target_pct)

    # If IV is high (> 0.40), structure as vertical spread to finance theta/vega
    if avg_iv > 0.40:
        structure_type = "LEAP_CALL_SPREAD"
        spread_candidates = [
            x
            for x in scored_contracts
            if x["contract"].strike >= target_short_strike
        ]
        if spread_candidates:
            spread_candidates.sort(
                key=lambda x: abs(x["contract"].strike - target_short_strike)
            )
            best_short = spread_candidates[0]
            short_contract = best_short["contract"]
            short_greeks = best_short["greeks"]

    # 3. Calculate Payoff and Net Cost
    long_mid = best_long["mid_price"]
    short_mid = (
        (short_contract.bid + short_contract.ask) / 2.0
        if short_contract
        else 0.0
    )
    net_debit = long_mid - short_mid

    # 4. Liquidity & Spread Quality Gates
    is_liquid = (
        long_contract.open_interest >= min_open_interest
        and (
            short_contract.open_interest >= min_open_interest
            if short_contract
            else True
        )
    )

    return {
        "structure": structure_type,
        "underlying_price": underlying_price,
        "thesis_horizon_months": thesis_horizon_months,
        "expiry_days": selected_expiry,
        "long_leg": {
            "symbol": long_contract.symbol,
            "strike": long_contract.strike,
            "delta": long_greeks.delta,
            "theta_1d": long_greeks.theta,
            "vega": long_greeks.vega,
            "implied_vol": long_contract.implied_vol,
            "open_interest": long_contract.open_interest,
            "cost": long_mid,
        },
        "short_leg": (
            {
                "symbol": short_contract.symbol,
                "strike": short_contract.strike,
                "delta": short_greeks.delta,
                "theta_1d": short_greeks.theta,
                "vega": short_greeks.vega,
                "implied_vol": short_contract.implied_vol,
                "open_interest": short_contract.open_interest,
                "credit": short_mid,
            }
            if short_contract and short_greeks
            else None
        ),
        "net_debit": round(net_debit, 2),
        "max_risk": round(net_debit * 100.0, 2),  # 1 contract = 100 shares
        "liquidity_passed": is_liquid,
    }


def generate_scenario_surface(
    underlying_price: float,
    long_strike: float,
    net_debit: float,
    short_strike: Optional[float] = None,
    price_shifts: Optional[List[float]] = None,
) -> pd.DataFrame:
    """Generates scenario payoff table across price shift percentages at contract expiry."""
    if price_shifts is None:
        price_shifts = [-0.30, -0.15, 0.0, 0.15, 0.30, 0.50]

    scenarios = []
    for shift in price_shifts:
        term_price = underlying_price * (1.0 + shift)
        long_val = max(0.0, term_price - long_strike)
        short_val = (
            max(0.0, term_price - short_strike) if short_strike else 0.0
        )

        payoff = long_val - short_val
        pnl_per_share = payoff - net_debit
        roi_pct = (pnl_per_share / net_debit) * 100.0 if net_debit > 0 else 0.0

        scenarios.append(
            {
                "shift_pct": f"{int(shift * 100)}%",
                "terminal_price": round(term_price, 2),
                "gross_payoff": round(payoff, 2),
                "net_pnl": round(pnl_per_share, 2),
                "roi_pct": f"{round(roi_pct, 1)}%",
            }
        )

    return pd.DataFrame(scenarios)
