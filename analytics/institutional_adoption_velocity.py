"""Deterministic Institutional Adoption Velocity (IAV) model.

IAV measures ownership formation, not ETF indicative net asset value. The model
accepts already-normalized evidence produced by ingestion and analytics layers;
it performs no language-model inference and no price/NAV valuation.
"""

from dataclasses import dataclass, field
from typing import Dict, Mapping, Optional

import numpy as np


@dataclass(frozen=True)
class IAVInputs:
    """Normalized evidence for one security and one evaluation window.

    All factor values are expected in the closed interval [-1, 1]. Positive
    values indicate adoption or quality; negative values indicate contraction
    or poor quality. ``ambiguity`` and penalties are non-negative [0, 1].
    """

    normalized_active_allocation: float
    independent_manager_breadth: float
    persistence: float
    diffusion: float
    strategic_relevance: float
    anomaly_quality: float
    ambiguity: float = 0.0
    passive_inclusion_penalty: float = 0.0
    corporate_action_penalty: float = 0.0
    crowding_penalty: float = 0.0
    saturation_penalty: float = 0.0
    price_drift_penalty: float = 0.0
    manager_dependence_penalty: float = 0.0


@dataclass(frozen=True)
class IAVResult:
    """Auditable IAV output with component and penalty breakdowns."""

    composite_score: float
    core_score: float
    quality_multiplier: float
    penalty_total: float
    components: Dict[str, float] = field(default_factory=dict)
    penalties: Dict[str, float] = field(default_factory=dict)
    accepted: bool = False


class InstitutionalAdoptionVelocity:
    """Compute a deterministic, bounded institutional adoption score.

    The core score is a weighted sum of normalized active allocation, manager
    breadth, persistence, diffusion, strategic relevance, and anomaly quality.
    Quality and ambiguity adjust the core; structural penalties are subtracted
    after weighting. The final result is clipped to [-1, 1].
    """

    DEFAULT_WEIGHTS: Mapping[str, float] = {
        "normalized_active_allocation": 0.20,
        "independent_manager_breadth": 0.20,
        "persistence": 0.15,
        "diffusion": 0.15,
        "strategic_relevance": 0.15,
        "anomaly_quality": 0.15,
    }
    PENALTY_NAMES = (
        "passive_inclusion_penalty",
        "corporate_action_penalty",
        "crowding_penalty",
        "saturation_penalty",
        "price_drift_penalty",
        "manager_dependence_penalty",
    )

    def __init__(
        self,
        weights: Optional[Mapping[str, float]] = None,
        ambiguity_penalty_weight: float = 0.25,
        acceptance_threshold: float = 0.0,
    ):
        self.weights = dict(weights or self.DEFAULT_WEIGHTS)
        if set(self.weights) != set(self.DEFAULT_WEIGHTS):
            raise ValueError("IAV weights must define all six required components.")
        if any(value < 0 for value in self.weights.values()) or not np.isclose(sum(self.weights.values()), 1.0):
            raise ValueError("IAV component weights must be non-negative and sum to 1.")
        if not 0 <= ambiguity_penalty_weight <= 1:
            raise ValueError("ambiguity_penalty_weight must be in [0, 1].")
        self.ambiguity_penalty_weight = ambiguity_penalty_weight
        self.acceptance_threshold = acceptance_threshold

    @staticmethod
    def _bounded(value: float, name: str) -> float:
        value = float(value)
        if not np.isfinite(value) or value < -1.0 or value > 1.0:
            raise ValueError(f"{name} must be finite and in [-1, 1].")
        return value

    @staticmethod
    def _penalty(value: float, name: str) -> float:
        value = float(value)
        if not np.isfinite(value) or value < 0.0 or value > 1.0:
            raise ValueError(f"{name} must be finite and in [0, 1].")
        return value

    def compute(self, inputs: IAVInputs) -> IAVResult:
        component_values = {
            name: self._bounded(getattr(inputs, name), name)
            for name in self.DEFAULT_WEIGHTS
        }
        core_score = float(sum(self.weights[name] * component_values[name] for name in self.weights))

        ambiguity = self._penalty(inputs.ambiguity, "ambiguity")
        quality_multiplier = max(0.0, 1.0 - self.ambiguity_penalty_weight * ambiguity)
        adjusted_core = core_score * quality_multiplier

        penalties = {
            name: self._penalty(getattr(inputs, name), name)
            for name in self.PENALTY_NAMES
        }
        penalty_total = float(sum(penalties.values()) / len(penalties))
        composite_score = float(np.clip(adjusted_core - penalty_total, -1.0, 1.0))

        return IAVResult(
            composite_score=composite_score,
            core_score=core_score,
            quality_multiplier=quality_multiplier,
            penalty_total=penalty_total,
            components=component_values,
            penalties=penalties,
            accepted=composite_score >= self.acceptance_threshold,
        )

    def compute_iav(self, inputs: IAVInputs) -> IAVResult:
        """Explicit IAV-named alias for callers using the paper terminology."""
        return self.compute(inputs)


__all__ = ["IAVInputs", "IAVResult", "InstitutionalAdoptionVelocity"]
