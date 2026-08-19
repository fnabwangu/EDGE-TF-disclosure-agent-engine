"""
Concept lexicon.

Path: research/lexicon.py

Maps trading vocabulary onto the universe's function tokens. "FOMC" and
"Jackson Hole" appear nowhere in `fund_universe.json`, but the instruments that
express them do, so a literal substring search finds nothing while the trade is
perfectly expressible.

The lexicon also classifies *what kind of trade* a query implies. That matters:
EDGE-TF measures institutional adoption from active manager disclosures, which
is a slow signal. A dated macro event is not an adoption trade and must not be
routed as one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Sequence, Set


class TradeKind(str, Enum):
    ADOPTION = "ADOPTION"
    MACRO_EVENT = "MACRO_EVENT"


class Stance(str, Enum):
    HAWKISH = "HAWKISH"
    DOVISH = "DOVISH"
    VOLATILITY = "VOLATILITY"
    UNSPECIFIED = "UNSPECIFIED"


@dataclass(frozen=True)
class Concept:
    key: str
    aliases: Sequence[str]
    kind: TradeKind
    functions: Sequence[str] = ()
    themes: Sequence[str] = ()
    event_name: Optional[str] = None
    note: Optional[str] = None


RATES_FUNCTIONS = (
    "duration_benchmark",
    "duration_short",
    "long_duration_benchmark",
    "short_duration_baseline",
    "ten_year_yield_baseline",
    "fed_funds_proxy",
    "rate_hike_hedge",
    "yield_expansion",
    "inflation_breakeven",
    "real_yield_hedge",
    "cash_equivalent",
)

VOL_FUNCTIONS = ("volatility_spike", "volatility_compression", "tail_risk_hedge")

DOLLAR_FUNCTIONS = (
    "dollar_liquidity_squeeze",
    "dollar_weakness_hedge",
    "monetary_debasement",
    "safe_haven_flight",
    "fx_volatility_hedge",
    "yen_carry_unwind",
)

CONCEPTS: List[Concept] = [
    Concept(
        key="fomc",
        aliases=[
            "fomc",
            "fed",
            "the fed",
            "fed meeting",
            "federal reserve",
            "fed decision",
            "rate decision",
            "dot plot",
            "powell",
            "monetary policy",
        ],
        kind=TradeKind.MACRO_EVENT,
        functions=RATES_FUNCTIONS + VOL_FUNCTIONS + DOLLAR_FUNCTIONS,
        themes=["rate_transmission_hedge", "currency_liquidity_hedge", "macro_market_control"],
        event_name="FOMC decision",
        note="Scheduled policy decision; expresses through the front and belly of the curve.",
    ),
    Concept(
        key="jackson_hole",
        aliases=["jackson hole", "kansas city symposium", "powell speech", "fed symposium"],
        kind=TradeKind.MACRO_EVENT,
        functions=RATES_FUNCTIONS + VOL_FUNCTIONS + DOLLAR_FUNCTIONS,
        themes=["rate_transmission_hedge", "currency_liquidity_hedge"],
        event_name="Jackson Hole symposium",
        note="Unscheduled-content event; historically a forward-guidance repricing catalyst.",
    ),
    Concept(
        key="cpi",
        aliases=["cpi", "inflation print", "pce", "inflation data"],
        kind=TradeKind.MACRO_EVENT,
        functions=RATES_FUNCTIONS + ("commodity_inflation_hedge", "energy_inflation_hedge"),
        themes=["rate_transmission_hedge", "macro_commodity_hedge"],
        event_name="Inflation print",
    ),
    Concept(
        key="payrolls",
        aliases=["nfp", "payrolls", "jobs report", "unemployment"],
        kind=TradeKind.MACRO_EVENT,
        functions=RATES_FUNCTIONS,
        themes=["rate_transmission_hedge"],
        event_name="Employment report",
    ),
    Concept(
        key="duration",
        aliases=["duration", "long end", "front end", "curve", "yields", "treasuries", "bonds", "notes"],
        kind=TradeKind.MACRO_EVENT,
        functions=RATES_FUNCTIONS,
        themes=["rate_transmission_hedge"],
    ),
    Concept(
        key="dollar",
        aliases=["dollar", "usd", "dxy", "currency", "yen", "euro", "fx"],
        kind=TradeKind.MACRO_EVENT,
        functions=DOLLAR_FUNCTIONS,
        themes=["currency_liquidity_hedge"],
    ),
    Concept(
        key="volatility",
        aliases=["volatility", "vol", "vix", "tail risk", "hedge the tape"],
        kind=TradeKind.MACRO_EVENT,
        functions=VOL_FUNCTIONS,
        themes=["geopolitical_risk_hedge"],
    ),
    Concept(
        key="nuclear",
        aliases=["nuclear", "uranium", "smr", "reactor", "enrichment"],
        kind=TradeKind.ADOPTION,
        functions=("uranium_mining", "fuel_enrichment", "smr_technology", "nuclear_reactors"),
        themes=["power_infrastructure"],
    ),
    Concept(
        key="ai_infrastructure",
        aliases=["ai", "artificial intelligence", "data center", "compute", "gpu", "accelerator"],
        kind=TradeKind.ADOPTION,
        functions=(
            "data_center_power",
            "leading_edge_compute",
            "custom_asic_design",
            "cloud_infrastructure",
            "ai_monetization",
            "cooling_infrastructure",
        ),
        themes=["compute_hardware", "enterprise_ai", "power_infrastructure"],
    ),
    Concept(
        key="defense",
        aliases=["defense", "defence", "military", "munitions", "drones", "unmanned"],
        kind=TradeKind.ADOPTION,
        functions=("defense_hardware", "defense_software", "munitions", "unmanned_systems", "battlefield_sensing"),
        themes=["defense_tech"],
    ),
    Concept(
        key="robotics",
        aliases=["robot", "robotics", "automation", "physical ai", "humanoid"],
        kind=TradeKind.ADOPTION,
        functions=("robotics_components", "factory_automation", "actuators", "machine_vision", "embodied_ai"),
        themes=["physical_ai"],
    ),
]

HAWKISH_TERMS = ("hawkish", "hike", "higher for longer", "tightening", "no cut", "sticky inflation")
DOVISH_TERMS = ("dovish", "cut", "easing", "pivot", "pause", "soft landing")
VOL_TERMS = ("volatility", "vol", "straddle", "tail", "hedge", "uncertain", "either way")


@dataclass
class ConceptMatch:
    query: str
    concepts: List[Concept] = field(default_factory=list)
    functions: Set[str] = field(default_factory=set)
    themes: Set[str] = field(default_factory=set)
    stance: Stance = Stance.UNSPECIFIED

    @property
    def matched(self) -> bool:
        return bool(self.concepts)

    @property
    def kind(self) -> Optional[TradeKind]:
        if not self.concepts:
            return None
        # A dated event dominates: it cannot be answered with a slow adoption signal.
        if any(c.kind is TradeKind.MACRO_EVENT for c in self.concepts):
            return TradeKind.MACRO_EVENT
        return TradeKind.ADOPTION

    @property
    def events(self) -> List[str]:
        return [c.event_name for c in self.concepts if c.event_name]

    @property
    def notes(self) -> List[str]:
        return [c.note for c in self.concepts if c.note]

    def label(self) -> str:
        return " + ".join(self.events) or ", ".join(c.key.replace("_", " ") for c in self.concepts)


def detect_stance(query: str) -> Stance:
    text = query.lower()
    if any(term in text for term in HAWKISH_TERMS):
        return Stance.HAWKISH
    if any(term in text for term in DOVISH_TERMS):
        return Stance.DOVISH
    if any(term in text for term in VOL_TERMS):
        return Stance.VOLATILITY
    return Stance.UNSPECIFIED


def expand(query: str) -> ConceptMatch:
    """Map free text onto universe functions, themes and a trade kind."""
    text = f" {query.lower()} "
    match = ConceptMatch(query=query, stance=detect_stance(query))

    for concept in CONCEPTS:
        if any(re.search(rf"\b{re.escape(alias)}\b", text) for alias in concept.aliases):
            match.concepts.append(concept)
            match.functions.update(concept.functions)
            match.themes.update(concept.themes)

    if match.kind is TradeKind.MACRO_EVENT and match.stance is Stance.UNSPECIFIED:
        match.stance = Stance.VOLATILITY
    return match


CONCEPTS_BY_KEY: Dict[str, Concept] = {concept.key: concept for concept in CONCEPTS}


def from_keys(keys: Iterable[str], *, stance: Stance = Stance.UNSPECIFIED, query: str = "") -> ConceptMatch:
    """Rebuild a match from persisted concept keys, so focus survives a new session."""
    match = ConceptMatch(query=query, stance=stance)
    for key in keys:
        concept = CONCEPTS_BY_KEY.get(key)
        if concept is None:
            continue
        match.concepts.append(concept)
        match.functions.update(concept.functions)
        match.themes.update(concept.themes)
    if match.kind is TradeKind.MACRO_EVENT and match.stance is Stance.UNSPECIFIED:
        match.stance = Stance.VOLATILITY
    return match


__all__ = [
    "CONCEPTS",
    "CONCEPTS_BY_KEY",
    "Concept",
    "ConceptMatch",
    "Stance",
    "TradeKind",
    "detect_stance",
    "expand",
    "from_keys",
]
