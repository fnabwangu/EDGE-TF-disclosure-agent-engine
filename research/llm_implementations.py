"""
Implementation generation via a hosted model - Path B.

Path: research/llm_implementations.py

Path A (research/implementations.py) derives every candidate deterministically
from Black-Scholes greeks and fund metadata. This module instead asks a
model to *propose* candidates, then puts every proposal through two gates
before it can reach a human:

    structural gate    the proposal must parse into ProposedImplementation -
                        wrong types, missing fields or an unknown enum value
                        never reach EDGE at all (enforced by the OpenAI SDK's
                        structured-output parsing itself)

    policy/risk gate    EDGE's own deterministic rules: every instrument must
                        exist in the permitted universe or the measured
                        disclosure set, numeric fields must be in bounds, and
                        the candidate must not duplicate a type already
                        accepted

The schema is not the validation gate. It only proves the shape is right;
whether the *content* is acceptable is decided here, by code the model does
not influence.

The model may propose ETF_LONG, ETF_HEDGED, OPTIONS, SINGLE_NAME,
EQUITY_BASKET or NO_TRADE. It has no path to select or execute one - those
functions are not importable from anywhere this module's output reaches.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from core.env import ensure_env_loaded
from research.implementations import (
    ImplementationAssumptions,
    ImplementationCandidate,
    ImplementationType,
    InstrumentCandidate,
)
from research.strategy_generation import StrategyCandidate
from research.synthesis import ThemeSynthesis

try:
    import openai as openai_sdk
except ImportError:  # pragma: no cover
    openai_sdk = None

DEFAULT_MODEL = "gpt-4o"
TIMEOUT_SECONDS = 30
MIN_LIQUIDITY = 0.05
_VALID_ROLES = {"CORE", "HEDGE", "OPTION", "COMPONENT"}

INSTRUCTIONS = """You propose implementation candidates for a confirmed institutional \
adoption thesis on EDGE-TF. You never decide which one is used - a human selects \
afterward through a separate, deterministic step you do not control.

Propose every eligible vehicle from: ETF_LONG, ETF_HEDGED, OPTIONS, SINGLE_NAME, \
EQUITY_BASKET, NO_TRADE. Use only tickers from the permitted instrument universe \
given to you - never invent a ticker. Ground thesis_fit, expected_return and \
downside_risk in the measured evidence provided; do not fabricate precision beyond \
what that evidence supports. Every candidate needs a rationale and at least one risk."""


class ProposedInstrument(BaseModel):
    ticker: str = Field(min_length=1)
    name: str = ""
    role: str = "CORE"
    weight: float = 1.0


class ProposedImplementation(BaseModel):
    """The structural gate. Only a value matching this shape is accepted from the model."""

    type: ImplementationType
    thesis_fit: float = Field(ge=0.0, le=1.0)
    expected_return: Optional[float] = None
    downside_risk: Optional[float] = Field(default=None, ge=0.0)
    convexity: Optional[float] = None
    carry_cost: Optional[float] = Field(default=None, ge=0.0)
    liquidity_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    concentration_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    instruments: List[ProposedInstrument] = Field(default_factory=list)
    rationale: str = Field(min_length=1)
    risks: List[str] = Field(default_factory=list)


class ProposalSet(BaseModel):
    candidates: List[ProposedImplementation] = Field(default_factory=list)


@dataclass
class QuarantinedCandidate:
    proposed_type: str
    reasons: List[str]
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelGenerationResult:
    """Everything the Decision Record needs, in one place."""

    model: str
    response_id: Optional[str]
    instructions: str
    input_summary: str
    raw_candidates: List[Dict[str, Any]]
    accepted: List[ImplementationCandidate]
    quarantined: List[QuarantinedCandidate]
    error: Optional[str] = None


def permitted_tickers(strategy: StrategyCandidate, synthesis: ThemeSynthesis) -> set:
    """The only instruments a proposal may reference - the model invents nothing."""
    tickers = {f.ticker for f in strategy.signal_funds}
    tickers |= {f.ticker for f in strategy.implementation_funds}
    tickers |= {f.ticker for f in strategy.control_funds}
    tickers |= {s.raw_identifier for s in synthesis.securities}
    return tickers


def _no_trade(strategy: StrategyCandidate, synthesis: ThemeSynthesis, assumptions: ImplementationAssumptions) -> ImplementationCandidate:
    """The null option is never sourced from the model - it must always be trustworthy."""
    leader = synthesis.leader()
    edge = max(-1.0, min(1.0, leader.iav.composite_score)) if leader else 0.0
    return ImplementationCandidate(
        id=f"{strategy.strategy_id}#no_trade",
        type=ImplementationType.NO_TRADE,
        thesis_fit=max(0.0, min(1.0, 1.0 - abs(edge))),
        expected_return=0.0,
        downside_risk=0.0,
        convexity=0.0,
        carry_cost=0.0,
        liquidity_score=1.0,
        concentration_score=0.0,
        instruments=[],
        rationale=f"Measured edge is {edge:+.3f}. Declining to express it costs nothing.",
        risks=["Opportunity cost if the adoption signal continues to build."],
        assumptions=assumptions.as_dict(),
        generated_by="EDGE_DETERMINISTIC",
    )


class LLMImplementationGenerator:
    """Calls the Responses API to propose candidates, then gates every one of them."""

    def __init__(self, *, model: Optional[str] = None, client: Optional[Any] = None):
        ensure_env_loaded()
        self.model = model or os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
        self._client = client

    def _get_client(self):
        if self._client is not None:
            return self._client
        if openai_sdk is None:
            raise RuntimeError("the openai package is not installed")
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or api_key.startswith("your_"):
            raise RuntimeError("OPENAI_API_KEY is not configured")
        self._client = openai_sdk.OpenAI(api_key=api_key)
        return self._client

    def generate(
        self,
        strategy: StrategyCandidate,
        synthesis: ThemeSynthesis,
        *,
        assumptions: Optional[ImplementationAssumptions] = None,
    ) -> ModelGenerationResult:
        assumptions = assumptions or ImplementationAssumptions()
        universe = sorted(permitted_tickers(strategy, synthesis))
        leader = synthesis.leader()

        prompt = self._build_prompt(strategy, synthesis, universe, assumptions)
        raw_candidates: List[Dict[str, Any]] = []

        try:
            client = self._get_client()
            response = client.responses.parse(
                model=self.model,
                instructions=INSTRUCTIONS,
                input=prompt,
                text_format=ProposalSet,
                timeout=TIMEOUT_SECONDS,
            )
        except Exception as exc:  # noqa: BLE001 - any failure degrades to "nothing proposed"
            error = f"{type(exc).__name__}: model call failed"
            accepted = [_no_trade(strategy, synthesis, assumptions)]
            return ModelGenerationResult(
                model=self.model,
                response_id=None,
                instructions=INSTRUCTIONS,
                input_summary=prompt,
                raw_candidates=raw_candidates,
                accepted=accepted,
                quarantined=[],
                error=error,
            )

        parsed = response.output_parsed or ProposalSet()
        raw_candidates = [c.model_dump(mode="json") for c in parsed.candidates]
        universe_set = set(universe)
        response_model = getattr(response, "model", None) or self.model
        model_accepted, quarantined = self._gate(parsed.candidates, universe_set, response_model)

        # The null option is never sourced from the model - it must always be trustworthy.
        accepted = [c for c in model_accepted if c.type != ImplementationType.NO_TRADE]
        accepted.append(_no_trade(strategy, synthesis, assumptions))
        accepted.sort(key=lambda c: -c.risk_adjusted_score)

        return ModelGenerationResult(
            model=response_model,
            response_id=getattr(response, "id", None),
            instructions=INSTRUCTIONS,
            input_summary=prompt,
            raw_candidates=raw_candidates,
            accepted=accepted,
            quarantined=quarantined,
        )

    # -- gates ---------------------------------------------------------

    def _gate(
        self, proposals: List[ProposedImplementation], universe: set, model_label: str
    ) -> "tuple[List[ImplementationCandidate], List[QuarantinedCandidate]]":
        """The policy/risk gate. The schema only proved the shape was right."""
        accepted: List[ImplementationCandidate] = []
        quarantined: List[QuarantinedCandidate] = []
        seen_types: set = set()

        for proposal in proposals:
            reasons = self._policy_violations(proposal, universe, seen_types)
            if reasons:
                quarantined.append(
                    QuarantinedCandidate(
                        proposed_type=proposal.type.value, reasons=reasons, raw=proposal.model_dump(mode="json")
                    )
                )
                continue
            seen_types.add(proposal.type)
            accepted.append(self._to_candidate(proposal, model_label))
        return accepted, quarantined

    @staticmethod
    def _policy_violations(proposal: ProposedImplementation, universe: set, seen_types: set) -> List[str]:
        """The actual policy/risk gate. The schema only proved the shape was right."""
        reasons: List[str] = []

        if proposal.type in seen_types:
            reasons.append(f"DUPLICATE_TYPE:{proposal.type.value}")

        if proposal.type != ImplementationType.NO_TRADE:
            if not proposal.instruments:
                reasons.append("NO_INSTRUMENT_SPECIFIED")
            for instrument in proposal.instruments:
                if instrument.ticker not in universe:
                    reasons.append(f"UNKNOWN_INSTRUMENT:{instrument.ticker}")

        if proposal.liquidity_score is not None and proposal.liquidity_score < MIN_LIQUIDITY:
            reasons.append(f"LIQUIDITY_BELOW_FLOOR:{proposal.liquidity_score:.3f}")

        if proposal.type == ImplementationType.OPTIONS and not proposal.risks:
            reasons.append("OPTIONS_REQUIRE_STATED_RISKS")

        for instrument in proposal.instruments:
            if instrument.role not in _VALID_ROLES:
                reasons.append(f"UNKNOWN_INSTRUMENT_ROLE:{instrument.role}")

        return reasons

    def _to_candidate(self, proposal: ProposedImplementation, model_label: str) -> ImplementationCandidate:
        return ImplementationCandidate(
            id=f"llm#{proposal.type.value.lower()}#{abs(hash(proposal.rationale)) % 10_000_000}",
            type=proposal.type,
            thesis_fit=proposal.thesis_fit,
            expected_return=proposal.expected_return,
            downside_risk=proposal.downside_risk,
            convexity=proposal.convexity,
            carry_cost=proposal.carry_cost,
            liquidity_score=proposal.liquidity_score,
            concentration_score=proposal.concentration_score,
            instruments=[
                InstrumentCandidate(
                    ticker=i.ticker,
                    name=i.name or i.ticker,
                    role=i.role if i.role in _VALID_ROLES else "COMPONENT",  # type: ignore[arg-type]
                    weight=i.weight,
                )
                for i in proposal.instruments
            ],
            rationale=proposal.rationale,
            risks=list(proposal.risks),
            generated_by=f"OPENAI:{model_label}",
        )

    @staticmethod
    def _build_prompt(
        strategy: StrategyCandidate,
        synthesis: ThemeSynthesis,
        universe: List[str],
        assumptions: ImplementationAssumptions,
    ) -> str:
        leader = synthesis.leader()
        evidence = (
            f"Leader security {leader.raw_identifier}: IAV {leader.iav.composite_score:+.3f}, "
            f"{leader.manager_breadth} independent clusters, active deviation {leader.aqd_pct:+.2%}, "
            f"persistence {leader.persistence:+.2f}, manager HHI {leader.manager_hhi:.2f}."
            if leader
            else "No security cleared synthesis."
        )
        return (
            f"Thesis: {strategy.thesis_seed}\n"
            f"Theme/function: {strategy.theme}/{strategy.function}\n"
            f"Evidence: {evidence}\n"
            f"Permitted instrument universe (use ONLY these tickers): {', '.join(universe) or 'none'}\n"
            f"Assumed volatility {assumptions.annualized_volatility:.2f}, horizon "
            f"{assumptions.horizon_days} days, risk-free rate {assumptions.risk_free_rate:.3f}."
        )


__all__ = [
    "INSTRUCTIONS",
    "LLMImplementationGenerator",
    "MIN_LIQUIDITY",
    "ModelGenerationResult",
    "ProposalSet",
    "ProposedImplementation",
    "ProposedInstrument",
    "QuarantinedCandidate",
    "permitted_tickers",
]
