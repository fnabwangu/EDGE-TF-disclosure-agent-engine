"""
Stage 3 - implementation generation.

Path: research/implementations.py

A confirmed thesis says *what* is happening, not *how to express it*. Several
vehicles can carry the same view with very different risk shapes, so every
eligible one is generated before any is chosen. Selection is a separate,
later step - `generate_implementations()` must run first.

`NO_TRADE` is always generated. The null option has to be on the table for a
comparison to be honest.

Where numbers come from:
  convexity, carry_cost   BlackScholesEngine greeks (analytics/options_modeler)
  liquidity, concentration  fund metadata in config/fund_universe.json
  thesis_fit, expected_return, downside_risk
                          derived from the measured IAV and conviction under
                          the stated assumptions, which travel with the
                          candidate so they are never mistaken for measurements
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Sequence

from analytics.options_modeler import BlackScholesEngine
from research.strategy_generation import FundRef, StrategyCandidate
from research.synthesis import SecuritySynthesis, ThemeSynthesis

# Maps a unit of measured adoption velocity onto an annualized excess return.
# A calibration constant, not a measurement.
EDGE_TO_ANNUAL_RETURN = 0.25
ONE_TAIL_95 = 1.645


class ImplementationType(str, Enum):
    ETF_LONG = "ETF_LONG"
    ETF_HEDGED = "ETF_HEDGED"
    OPTIONS = "OPTIONS"
    SINGLE_NAME = "SINGLE_NAME"
    EQUITY_BASKET = "EQUITY_BASKET"
    NO_TRADE = "NO_TRADE"


InstrumentRole = Literal["CORE", "HEDGE", "OPTION", "COMPONENT"]


@dataclass
class InstrumentCandidate:
    ticker: str
    name: str
    role: InstrumentRole
    weight: float
    classification: str = "unknown"
    liquidity: float = 0.0


@dataclass
class ImplementationAssumptions:
    annualized_volatility: float = 0.28
    risk_free_rate: float = 0.045
    horizon_days: int = 180
    hedge_ratio: float = 0.5
    hedge_cost_annual: float = 0.035
    option_delta_target: float = 0.70
    reference_price: float = 100.0

    @property
    def horizon_years(self) -> float:
        return max(self.horizon_days, 1) / 365.0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "annualized_volatility": self.annualized_volatility,
            "risk_free_rate": self.risk_free_rate,
            "horizon_days": self.horizon_days,
            "hedge_ratio": self.hedge_ratio,
            "hedge_cost_annual": self.hedge_cost_annual,
            "option_delta_target": self.option_delta_target,
            "reference_price": self.reference_price,
        }


@dataclass
class ImplementationCandidate:
    id: str
    type: ImplementationType
    thesis_fit: float
    expected_return: Optional[float]
    downside_risk: Optional[float]
    convexity: Optional[float]
    carry_cost: Optional[float]
    liquidity_score: Optional[float]
    concentration_score: Optional[float]
    instruments: List[InstrumentCandidate]
    rationale: str
    risks: List[str] = field(default_factory=list)
    assumptions: Dict[str, Any] = field(default_factory=dict)
    # "EDGE_DETERMINISTIC" or "OPENAI:<model>" - who proposed this candidate.
    # Provenance only: acceptance always runs through the same structural and
    # policy/risk gates regardless of source.
    generated_by: str = "EDGE_DETERMINISTIC"

    @property
    def risk_adjusted_score(self) -> float:
        """Return per unit of downside, tilted by fit and liquidity, less carry."""
        if self.expected_return is None or self.downside_risk is None:
            return 0.0
        downside = max(self.downside_risk, 1e-6)
        base = (self.expected_return - (self.carry_cost or 0.0)) / downside
        return round(base * self.thesis_fit * (0.5 + 0.5 * (self.liquidity_score or 0.5)), 4)

    def summary(self) -> str:
        tickers = ", ".join(i.ticker for i in self.instruments) or "-"
        return f"{self.type.value}: {tickers}"


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _concentration(weights: Sequence[float]) -> float:
    total = sum(abs(w) for w in weights)
    if total <= 0:
        return 1.0
    return round(sum((abs(w) / total) ** 2 for w in weights), 4)


class ImplementationGenerator:
    """Produces every eligible expression of a confirmed thesis."""

    def __init__(self, assumptions: Optional[ImplementationAssumptions] = None):
        self.assumptions = assumptions or ImplementationAssumptions()

    def generate(
        self,
        strategy: StrategyCandidate,
        synthesis: ThemeSynthesis,
        *,
        assumptions: Optional[ImplementationAssumptions] = None,
    ) -> List[ImplementationCandidate]:
        assumptions = assumptions or self.assumptions
        leader = synthesis.leader()
        if leader is None:
            return [self._no_trade(strategy, None, "No security cleared synthesis.", assumptions)]

        candidates: List[ImplementationCandidate] = []
        for builder in (
            self._etf_long,
            self._etf_hedged,
            self._options,
            self._single_name,
            self._equity_basket,
        ):
            candidate = builder(strategy, synthesis, leader, assumptions)
            if candidate is not None:
                candidates.append(candidate)

        candidates.append(self._no_trade(strategy, leader, None, assumptions))
        return self.rank(candidates)

    @staticmethod
    def rank(candidates: List[ImplementationCandidate]) -> List[ImplementationCandidate]:
        return sorted(candidates, key=lambda c: -c.risk_adjusted_score)

    # -- builders ----------------------------------------------------------

    def _edge(self, leader: SecuritySynthesis) -> float:
        return max(-1.0, min(1.0, leader.iav.composite_score))

    def _annual_return(self, leader: SecuritySynthesis) -> float:
        return self._edge(leader) * EDGE_TO_ANNUAL_RETURN

    def _horizon_return(self, leader: SecuritySynthesis, a: ImplementationAssumptions) -> float:
        return self._annual_return(leader) * a.horizon_years

    def _horizon_downside(self, a: ImplementationAssumptions, multiplier: float = 1.0) -> float:
        return a.annualized_volatility * math.sqrt(a.horizon_years) * ONE_TAIL_95 * multiplier

    def _etf_long(self, strategy, synthesis, leader, a) -> Optional[ImplementationCandidate]:
        funds = strategy.implementation_funds[:1]
        if not funds:
            return None
        instruments = [self._instrument(funds[0], "CORE", 1.0)]
        return ImplementationCandidate(
            id=f"{strategy.strategy_id}#etf_long",
            type=ImplementationType.ETF_LONG,
            thesis_fit=_clamp(0.55 + 0.15 * min(leader.manager_breadth, 3) - 0.3 * leader.manager_hhi),
            expected_return=round(self._horizon_return(leader, a), 4),
            downside_risk=round(self._horizon_downside(a), 4),
            convexity=0.0,
            carry_cost=0.0,
            liquidity_score=round(funds[0].liquidity, 4),
            concentration_score=_concentration([1.0]),
            instruments=instruments,
            rationale=(
                "Cleanest expression of a breadth signal: the thesis is about adoption across "
                "managers, and a diversified vehicle carries that without single-name risk."
            ),
            risks=[
                "Full directional exposure with no downside protection.",
                "Fund may hold names outside the measured signal.",
            ],
            assumptions=a.as_dict(),
        )

    def _etf_hedged(self, strategy, synthesis, leader, a) -> Optional[ImplementationCandidate]:
        funds = strategy.implementation_funds[:1]
        hedges = strategy.control_funds[:1]
        if not funds or not hedges:
            return None
        instruments = [
            self._instrument(funds[0], "CORE", 1.0),
            self._instrument(hedges[0], "HEDGE", -a.hedge_ratio),
        ]
        carry = a.hedge_cost_annual * a.hedge_ratio * a.horizon_years
        return ImplementationCandidate(
            id=f"{strategy.strategy_id}#etf_hedged",
            type=ImplementationType.ETF_HEDGED,
            thesis_fit=_clamp(0.70 + 0.10 * min(leader.manager_breadth, 3) - 0.2 * leader.manager_hhi),
            expected_return=round(self._horizon_return(leader, a) * (1 - 0.4 * a.hedge_ratio), 4),
            downside_risk=round(self._horizon_downside(a, 1 - a.hedge_ratio), 4),
            convexity=0.0,
            carry_cost=round(carry, 4),
            liquidity_score=round((funds[0].liquidity + hedges[0].liquidity) / 2, 4),
            concentration_score=_concentration([1.0, a.hedge_ratio]),
            instruments=instruments,
            rationale=(
                "Isolates the adoption signal from broad market direction by shorting the "
                "passive benchmark, so the position pays for relative rather than absolute moves."
            ),
            risks=[
                "Hedge carry is paid whether or not the thesis works.",
                "Basis risk between the thematic vehicle and the benchmark.",
            ],
            assumptions=a.as_dict(),
        )

    def _options(self, strategy, synthesis, leader, a) -> Optional[ImplementationCandidate]:
        funds = strategy.implementation_funds[:1]
        if not funds:
            return None

        spot = a.reference_price
        strike = spot * (1.0 - (a.option_delta_target - 0.5))
        greeks = BlackScholesEngine.calculate_call_greeks(
            S=spot, K=strike, T_years=a.horizon_years, r=a.risk_free_rate, sigma=a.annualized_volatility
        )
        premium = max(greeks.price, 1e-6)

        underlying_move = spot * self._horizon_return(leader, a)
        expected_return = (greeks.delta * underlying_move) / premium
        convexity = (greeks.gamma * spot**2) / premium
        carry = abs(greeks.theta) * a.horizon_days / premium

        return ImplementationCandidate(
            id=f"{strategy.strategy_id}#options",
            type=ImplementationType.OPTIONS,
            # Premium decay only pays off on a strong signal.
            thesis_fit=_clamp(0.25 + 0.75 * max(0.0, self._edge(leader))),
            expected_return=round(expected_return, 4),
            downside_risk=1.0,
            convexity=round(convexity, 4),
            carry_cost=round(carry, 4),
            liquidity_score=round(funds[0].liquidity * 0.7, 4),
            concentration_score=_concentration([1.0]),
            instruments=[
                InstrumentCandidate(
                    ticker=f"{funds[0].ticker} CALL",
                    name=f"{funds[0].name} duration-matched call",
                    role="OPTION",
                    weight=1.0,
                    classification="option",
                    liquidity=funds[0].liquidity * 0.7,
                )
            ],
            rationale=(
                f"Convex expression with loss capped at premium. Delta {greeks.delta:.2f}, "
                f"gamma {greeks.gamma:.4f}, {a.horizon_days}-day theta {greeks.theta:.4f} per contract."
            ),
            risks=[
                "Entire premium is at risk if the move does not arrive in time.",
                "Requires a dated catalyst; adoption signals are slow and may outlast the expiry.",
                "Option liquidity is thinner than the underlying.",
            ],
            assumptions=a.as_dict() | {"strike": round(strike, 2), "premium": round(premium, 4)},
        )

    def _single_name(self, strategy, synthesis, leader, a) -> Optional[ImplementationCandidate]:
        return ImplementationCandidate(
            id=f"{strategy.strategy_id}#single_name",
            type=ImplementationType.SINGLE_NAME,
            # Only fits when the signal is genuinely concentrated in one security.
            thesis_fit=_clamp(0.20 + 0.5 * leader.manager_hhi + 0.3 * max(0.0, self._edge(leader))),
            expected_return=round(self._horizon_return(leader, a) * 1.4, 4),
            downside_risk=round(self._horizon_downside(a, 1.6), 4),
            convexity=0.0,
            carry_cost=0.0,
            liquidity_score=0.6,
            concentration_score=1.0,
            instruments=[
                InstrumentCandidate(
                    ticker=leader.raw_identifier,
                    name=f"Disclosure security {leader.security_id}",
                    role="CORE",
                    weight=1.0,
                    classification="single_name",
                    liquidity=0.6,
                )
            ],
            rationale=(
                f"Highest beta to the measured signal: {leader.raw_identifier} carries the largest "
                f"active deviation ({leader.aqd_pct:+.2%}) across {leader.manager_breadth} clusters."
            ),
            risks=[
                "Concentrates idiosyncratic risk the adoption signal does not measure.",
                "Disclosure securities require a security master to map onto tradeable lines.",
            ],
            assumptions=a.as_dict(),
        )

    def _equity_basket(self, strategy, synthesis, leader, a) -> Optional[ImplementationCandidate]:
        members = synthesis.ranked()[:4]
        if len(members) < 2:
            return None
        weight = round(1.0 / len(members), 4)
        return ImplementationCandidate(
            id=f"{strategy.strategy_id}#equity_basket",
            type=ImplementationType.EQUITY_BASKET,
            thesis_fit=_clamp(0.45 + 0.15 * len(members) - 0.3 * leader.manager_hhi),
            expected_return=round(self._horizon_return(leader, a) * 1.15, 4),
            downside_risk=round(self._horizon_downside(a, 1.25), 4),
            convexity=0.0,
            carry_cost=0.0,
            liquidity_score=0.55,
            concentration_score=_concentration([weight] * len(members)),
            instruments=[
                InstrumentCandidate(
                    ticker=member.raw_identifier,
                    name=f"Disclosure security {member.security_id}",
                    role="COMPONENT",
                    weight=weight,
                    classification="single_name",
                    liquidity=0.55,
                )
                for member in members
            ],
            rationale=(
                f"Equal-weight basket of the {len(members)} securities carrying the signal, keeping "
                "breadth exposure while dropping the fund's off-thesis holdings."
            ),
            risks=[
                "Requires execution across several lines and ongoing rebalancing.",
                "Disclosure securities require a security master to map onto tradeable lines.",
            ],
            assumptions=a.as_dict(),
        )

    def _no_trade(self, strategy, leader, reason, a) -> ImplementationCandidate:
        edge = self._edge(leader) if leader is not None else 0.0
        return ImplementationCandidate(
            id=f"{strategy.strategy_id}#no_trade",
            type=ImplementationType.NO_TRADE,
            # Doing nothing fits best exactly when the measured edge is weakest.
            thesis_fit=_clamp(1.0 - abs(edge)),
            expected_return=0.0,
            downside_risk=0.0,
            convexity=0.0,
            carry_cost=0.0,
            liquidity_score=1.0,
            concentration_score=0.0,
            instruments=[],
            rationale=reason
            or (
                f"Measured edge is {edge:+.3f}. Declining to express it costs nothing and "
                "remains available once the signal strengthens."
            ),
            risks=["Opportunity cost if the adoption signal continues to build."],
            assumptions=a.as_dict(),
        )

    @staticmethod
    def _instrument(fund: FundRef, role: InstrumentRole, weight: float) -> InstrumentCandidate:
        return InstrumentCandidate(
            ticker=fund.ticker,
            name=fund.name,
            role=role,
            weight=weight,
            classification=fund.classification,
            liquidity=fund.liquidity,
        )


__all__ = [
    "EDGE_TO_ANNUAL_RETURN",
    "ImplementationAssumptions",
    "ImplementationCandidate",
    "ImplementationGenerator",
    "ImplementationType",
    "InstrumentCandidate",
]
