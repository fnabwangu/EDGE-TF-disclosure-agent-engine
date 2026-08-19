"""
Research funnel stages.

Path: research/funnel.py

Ties the stages together and records where every idea sits:

    STRATEGY_GENERATION -> DISCLOSURE_SYNTHESIS -> EVIDENCE_REVIEW
        -> IMPLEMENTATION_GENERATION -> IMPLEMENTATION_SELECTED
        -> TRADE_DESIGN -> APPROVAL -> EXECUTED

The funnel does research and caches results. It does not persist theses or
touch capital; the agent maps funnel output onto workbench and transaction
tools, which is where durability and authorization live.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

from research.implementations import (
    ImplementationAssumptions,
    ImplementationCandidate,
    ImplementationGenerator,
)
from research.simulation import Regime, ingest_candidate
from research.strategy_generation import StrategyCandidate, StrategyGenerator
from research.synthesis import DisclosureSynthesizer, ThemeSynthesis, build_panel

if TYPE_CHECKING:
    from audit.decision_records import DecisionRecorder
    from research.llm_implementations import LLMImplementationGenerator, QuarantinedCandidate


class SelectionBeforeGeneration(RuntimeError):
    """Raised when an implementation is chosen before the alternatives exist."""


class FunnelStage(str, Enum):
    STRATEGY_GENERATION = "STRATEGY_GENERATION"
    DISCLOSURE_SYNTHESIS = "DISCLOSURE_SYNTHESIS"
    EVIDENCE_REVIEW = "EVIDENCE_REVIEW"
    IMPLEMENTATION_GENERATION = "IMPLEMENTATION_GENERATION"
    IMPLEMENTATION_SELECTED = "IMPLEMENTATION_SELECTED"
    TRADE_DESIGN = "TRADE_DESIGN"
    APPROVAL = "APPROVAL"
    EXECUTED = "EXECUTED"


STAGE_ORDER: List[FunnelStage] = list(FunnelStage)


def stage_index(stage: FunnelStage) -> int:
    return STAGE_ORDER.index(stage)


@dataclass
class FunnelPosition:
    """Where one idea currently sits, and what it is waiting on."""

    strategy_id: str
    stage: FunnelStage
    thesis_id: Optional[str] = None
    intent_id: Optional[str] = None
    implementation_id: Optional[str] = None
    blocked_reason: Optional[str] = None

    def advance_to(self, stage: FunnelStage) -> "FunnelPosition":
        if stage_index(stage) > stage_index(self.stage):
            self.stage = stage
        return self


class ResearchFunnel:
    """Stage 1 and 2 orchestration with per-strategy caching."""

    def __init__(
        self,
        *,
        generator: Optional[StrategyGenerator] = None,
        synthesizer: Optional[DisclosureSynthesizer] = None,
        as_of: Optional[date] = None,
        storage_dir: Path | str = "data/simulated",
        regime: Regime = "BROAD_ADOPTION",
    ):
        self.generator = generator or StrategyGenerator()
        self.synthesizer = synthesizer or DisclosureSynthesizer(
            cluster_map=self.generator.cluster_map(),
            theme_map=self.generator.theme_map(),
            relevance_map={f.fund_id: f.mandate_relevance for f in self.generator.funds},
            independence_map={f.fund_id: f.manager_independence for f in self.generator.funds},
            anomaly_lookback=3,
        )
        self.as_of = as_of or date.today()
        self.storage_dir = Path(storage_dir)
        self.regime: Regime = regime
        self.positions: Dict[str, FunnelPosition] = {}
        self._candidates: Dict[str, StrategyCandidate] = {}
        self._synthesis: Dict[str, ThemeSynthesis] = {}
        self._implementations: Dict[str, List[ImplementationCandidate]] = {}
        self._quarantined: Dict[str, List["QuarantinedCandidate"]] = {}
        self._selected: Dict[str, ImplementationCandidate] = {}
        self.implementation_generator = ImplementationGenerator()
        self.llm_implementation_generator: Optional["LLMImplementationGenerator"] = None
        self.decision_recorder: Optional["DecisionRecorder"] = None

    # -- stage 1 -----------------------------------------------------------

    def generate(self, query: Optional[str] = None, *, limit: int = 6) -> List[StrategyCandidate]:
        candidates = (
            self.generator.search(query, limit=limit) if query else self.generator.generate(limit=limit)
        )
        for candidate in candidates:
            self._candidates[candidate.strategy_id] = candidate
            self.positions.setdefault(
                candidate.strategy_id,
                FunnelPosition(
                    strategy_id=candidate.strategy_id,
                    stage=FunnelStage.STRATEGY_GENERATION,
                    blocked_reason="; ".join(candidate.rejection_reasons) or None,
                ),
            )
        return candidates

    def candidate(self, strategy_id: str) -> StrategyCandidate:
        if strategy_id not in self._candidates:
            theme, _, function = strategy_id.partition(":")
            self._candidates[strategy_id] = self.generator.build(theme, function)
        return self._candidates[strategy_id]

    # -- stage 2 -----------------------------------------------------------

    def synthesize(self, strategy_id: str, *, refresh: bool = False) -> ThemeSynthesis:
        if refresh or strategy_id not in self._synthesis:
            candidate = self.candidate(strategy_id)
            rows = ingest_candidate(
                candidate,
                as_of=self.as_of,
                regime=self.regime,
                storage_dir=self.storage_dir,
            )
            self._synthesis[strategy_id] = self.synthesizer.synthesize(
                build_panel(rows),
                strategy_id=strategy_id,
                theme=candidate.theme,
                function=candidate.function,
            )
        synthesis = self._synthesis[strategy_id]
        position = self.positions.setdefault(
            strategy_id, FunnelPosition(strategy_id=strategy_id, stage=FunnelStage.STRATEGY_GENERATION)
        )
        if synthesis.usable:
            position.advance_to(FunnelStage.EVIDENCE_REVIEW)
            position.blocked_reason = None
        else:
            position.advance_to(FunnelStage.DISCLOSURE_SYNTHESIS)
            position.blocked_reason = "; ".join(synthesis.blocking_reasons)
        return synthesis

    def synthesis(self, strategy_id: str) -> Optional[ThemeSynthesis]:
        return self._synthesis.get(strategy_id)

    # -- stage 3 -----------------------------------------------------------

    def generate_implementations(
        self,
        strategy_id: str,
        *,
        assumptions: Optional[ImplementationAssumptions] = None,
        refresh: bool = False,
    ) -> List[ImplementationCandidate]:
        """Every eligible expression. Must run before an implementation can be chosen."""
        synthesis = self._synthesis.get(strategy_id)
        if synthesis is None:
            raise SelectionBeforeGeneration(f"{strategy_id} has not been synthesized")

        if refresh or strategy_id not in self._implementations:
            self._implementations[strategy_id] = self.implementation_generator.generate(
                self.candidate(strategy_id), synthesis, assumptions=assumptions
            )
            self._selected.pop(strategy_id, None)

        self.mark(strategy_id, FunnelStage.IMPLEMENTATION_GENERATION)
        return self._implementations[strategy_id]

    def generate_implementations_llm(
        self,
        strategy_id: str,
        *,
        project_id: Optional[str] = None,
        assumptions: Optional[ImplementationAssumptions] = None,
        generator: Optional["LLMImplementationGenerator"] = None,
        recorder: Optional["DecisionRecorder"] = None,
        refresh: bool = False,
    ) -> List[ImplementationCandidate]:
        """Path B: propose candidates via a model, gate every one, log the Decision Record."""
        from audit.decision_records import DecisionRecorder
        from research.llm_implementations import LLMImplementationGenerator

        synthesis = self._synthesis.get(strategy_id)
        if synthesis is None:
            raise SelectionBeforeGeneration(f"{strategy_id} has not been synthesized")

        if refresh or strategy_id not in self._implementations:
            generator = generator or self.llm_implementation_generator or LLMImplementationGenerator()
            recorder = recorder or self.decision_recorder or DecisionRecorder()
            result = generator.generate(self.candidate(strategy_id), synthesis, assumptions=assumptions)

            recorder.record_implementation_generation(
                project_id=project_id,
                strategy_id=strategy_id,
                model=result.model,
                response_id=result.response_id,
                instructions=result.instructions,
                input_summary=result.input_summary,
                raw_candidates=result.raw_candidates,
                validation_results=[
                    {"proposed_type": q.proposed_type, "reasons": q.reasons} for q in result.quarantined
                ],
                accepted_candidate_ids=[c.id for c in result.accepted],
                error=result.error,
            )

            self._implementations[strategy_id] = result.accepted
            self._quarantined[strategy_id] = result.quarantined
            self._selected.pop(strategy_id, None)

        self.mark(strategy_id, FunnelStage.IMPLEMENTATION_GENERATION)
        return self._implementations[strategy_id]

    def quarantined_candidates(self, strategy_id: str) -> List["QuarantinedCandidate"]:
        return self._quarantined.get(strategy_id, [])

    def implementations(self, strategy_id: str) -> List[ImplementationCandidate]:
        return self._implementations.get(strategy_id, [])

    def select_implementation(self, strategy_id: str, implementation_id: str) -> ImplementationCandidate:
        """Refuses to choose from a set that was never generated."""
        available = self._implementations.get(strategy_id)
        if not available:
            raise SelectionBeforeGeneration(
                f"no implementations generated for {strategy_id}; "
                "call generate_implementations() before selecting"
            )
        chosen = next((c for c in available if c.id == implementation_id), None)
        if chosen is None:
            raise KeyError(f"unknown implementation {implementation_id}")

        self._selected[strategy_id] = chosen
        position = self.mark(strategy_id, FunnelStage.IMPLEMENTATION_SELECTED)
        position.implementation_id = chosen.id
        return chosen

    def selected_implementation(self, strategy_id: str) -> Optional[ImplementationCandidate]:
        return self._selected.get(strategy_id)

    # -- stage tracking ----------------------------------------------------

    def mark(
        self,
        strategy_id: str,
        stage: FunnelStage,
        *,
        thesis_id: Optional[str] = None,
        intent_id: Optional[str] = None,
    ) -> FunnelPosition:
        position = self.positions.setdefault(
            strategy_id, FunnelPosition(strategy_id=strategy_id, stage=stage)
        )
        position.advance_to(stage)
        if thesis_id:
            position.thesis_id = thesis_id
        if intent_id:
            position.intent_id = intent_id
        return position

    def board(self) -> Dict[str, List[FunnelPosition]]:
        """Positions bucketed by stage, for a pipeline rail in the UI."""
        buckets: Dict[str, List[FunnelPosition]] = {stage.value: [] for stage in STAGE_ORDER}
        for position in self.positions.values():
            buckets[position.stage.value].append(position)
        return buckets


__all__ = ["FunnelPosition", "FunnelStage", "ResearchFunnel", "STAGE_ORDER", "stage_index"]
