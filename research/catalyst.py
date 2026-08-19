"""
Catalyst (event) pathway.

Path: research/catalyst.py

EDGE-TF's adoption signal reads active manager ETF disclosures. Those arrive
with reporting lag and the rates/FX/vol complex in this universe contains no
active disclosing managers at all - only passive benchmarks and leveraged
implementation vehicles. A dated macro event therefore cannot be validated by
institutional adoption, and this module never fabricates an IAV for one.

What it can do honestly: identify which instruments express the event, in which
direction, and force the event-trade discipline (catalyst date, execution
buffer, defined max loss, invalidation) that `transactions/validator.py`
already enforces.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional, Sequence

from research.lexicon import ConceptMatch, Stance
from research.strategy_generation import FundRef, StrategyGenerator

DEFAULT_EXECUTION_BUFFER_DAYS = 14

# Which universe functions express which directional view on a policy repricing.
STANCE_FUNCTIONS: Dict[Stance, Sequence[str]] = {
    Stance.HAWKISH: (
        "duration_short",
        "rate_hike_hedge",
        "yield_expansion",
        "dollar_liquidity_squeeze",
        "fed_funds_proxy",
        "cash_equivalent",
    ),
    Stance.DOVISH: (
        "long_duration_benchmark",
        "duration_benchmark",
        "ten_year_yield_baseline",
        "dollar_weakness_hedge",
        "monetary_debasement",
    ),
    Stance.VOLATILITY: (
        "tail_risk_hedge",
        "volatility_spike",
        "fx_volatility_hedge",
        "yield_expansion",
        "safe_haven_flight",
    ),
}

STANCE_RATIONALE: Dict[Stance, str] = {
    Stance.HAWKISH: "Higher-for-longer guidance reprices the front end and supports the dollar.",
    Stance.DOVISH: "Easing guidance rallies the long end and pressures the dollar.",
    Stance.VOLATILITY: "Direction unknown; express the repricing itself rather than its sign.",
}


@dataclass
class ExpressionLeg:
    ticker: str
    name: str
    classification: str
    function: str
    direction: str
    liquidity: float
    rationale: str


@dataclass
class CatalystStrategy:
    """An event trade: expression vehicles plus the discipline the event demands."""

    event_label: str
    stance: Stance
    concepts: List[str]
    legs: List[ExpressionLeg] = field(default_factory=list)
    benchmarks: List[ExpressionLeg] = field(default_factory=list)
    catalyst_date: Optional[date] = None
    execution_buffer_days: int = DEFAULT_EXECUTION_BUFFER_DAYS
    adoption_available: bool = False
    limitations: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    @property
    def strategy_id(self) -> str:
        return f"catalyst:{self.event_label.lower().replace(' ', '_')}:{self.stance.value.lower()}"

    @property
    def primary(self) -> Optional[ExpressionLeg]:
        return self.legs[0] if self.legs else None

    def minimum_expiration(self) -> Optional[date]:
        if self.catalyst_date is None:
            return None
        return self.catalyst_date + timedelta(days=self.execution_buffer_days + 1)


class CatalystPlanner:
    def __init__(self, generator: Optional[StrategyGenerator] = None):
        self.generator = generator or StrategyGenerator()

    def plan(
        self,
        match: ConceptMatch,
        *,
        catalyst_date: Optional[date] = None,
        execution_buffer_days: int = DEFAULT_EXECUTION_BUFFER_DAYS,
    ) -> CatalystStrategy:
        stance = match.stance if match.stance is not Stance.UNSPECIFIED else Stance.VOLATILITY
        wanted = set(STANCE_FUNCTIONS.get(stance, ())) & (match.functions or set(STANCE_FUNCTIONS[stance]))
        if not wanted:
            wanted = set(STANCE_FUNCTIONS[stance])

        strategy = CatalystStrategy(
            event_label=match.label() or "Macro catalyst",
            stance=stance,
            concepts=[c.key for c in match.concepts],
            catalyst_date=catalyst_date,
            execution_buffer_days=execution_buffer_days,
            notes=list(match.notes),
        )

        for fund in self.generator.funds:
            overlap = wanted & set(fund.eligible_functions)
            if not overlap:
                continue
            leg = ExpressionLeg(
                ticker=fund.ticker,
                name=fund.name,
                classification=fund.classification,
                function=sorted(overlap)[0],
                direction="BUY",
                liquidity=fund.liquidity,
                rationale=STANCE_RATIONALE.get(stance, ""),
            )
            if fund.classification == "broad_passive_control":
                strategy.benchmarks.append(leg)
            else:
                strategy.legs.append(leg)

        strategy.legs.sort(key=lambda leg: -leg.liquidity)
        strategy.benchmarks.sort(key=lambda leg: -leg.liquidity)
        # Passive benchmarks are still tradeable ETFs; rank them behind dedicated vehicles.
        strategy.legs.extend(strategy.benchmarks)

        strategy.limitations = self._limitations(match, strategy)
        return strategy

    def _limitations(self, match: ConceptMatch, strategy: CatalystStrategy) -> List[str]:
        limitations = [
            "ADOPTION_SIGNAL_UNAVAILABLE: no active disclosing managers cover this complex, "
            "so IAV, manager breadth and active quantity deviation cannot be computed.",
            "DISCLOSURE_LATENCY: ETF holdings arrive with reporting lag and cannot resolve a "
            "single-day policy catalyst.",
        ]
        if not strategy.legs:
            limitations.append("NO_EXPRESSION_VEHICLE: the universe holds no instrument for this stance.")
        if strategy.catalyst_date is None:
            limitations.append("CATALYST_DATE_REQUIRED: an event trade cannot be sized without a dated catalyst.")
        return limitations


__all__ = [
    "CatalystPlanner",
    "CatalystStrategy",
    "DEFAULT_EXECUTION_BUFFER_DAYS",
    "ExpressionLeg",
    "STANCE_FUNCTIONS",
]
