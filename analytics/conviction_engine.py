"""
Edge-TF Disclosure Agent Engine - Conviction Engine
Path: analytics/conviction_engine.py

Converts already-normalized event probabilities and EDGE-TF implementation
evidence into a bounded, deterministic implementation-quality score and a
*requested* (not final) leverage figure.

This module performs no LLM inference. All weights and thresholds are
sourced from ``config/conviction_policy.json`` or explicit constructor
arguments so that conviction never collapses into a single hand-authored
if/else rule such as ``if confidence > 0.90: leverage = 2.0``.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

import numpy as np

from core.schemas import ConvictionInputs, ConvictionResult, EventProbability, LeverageLimits

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path("config/conviction_policy.json")

DEFAULT_WEIGHTS: Mapping[str, float] = {
    "iav": 0.25,
    "aqd_quality": 0.15,
    "anomaly_score": 0.10,
    "manager_breadth_score": 0.15,
    "persistence_score": 0.15,
    "diffusion_score": 0.10,
    "evidence_quality": 0.10,
}

DEFAULT_QUALITY_THRESHOLDS: Mapping[str, float] = {
    "weak_max": 0.30,
    "emerging_max": 0.60,
    "confirmed_max": 0.80,
}

DEFAULT_LEVERAGE_BOUNDS: Mapping[str, float] = {
    "min_leverage": 0.5,
    "max_leverage": 2.0,
}


class ConvictionEngine:
    """Computes deterministic implementation quality and requested leverage.

    Q = w1*IAV + w2*AQDq + w3*Anomaly + w4*Breadth + w5*Persistence
        + w6*Diffusion + w7*EvidenceQuality - ambiguity_penalty_weight * ambiguity_penalty

    L_requested = min_leverage + Q * (max_leverage - min_leverage)
    """

    def __init__(
        self,
        weights: Optional[Mapping[str, float]] = None,
        quality_thresholds: Optional[Mapping[str, float]] = None,
        leverage_bounds: Optional[Mapping[str, float]] = None,
        ambiguity_penalty_weight: Optional[float] = None,
        config_path: Optional[Path] = None,
    ):
        config = self._load_config(config_path)
        self.weights = dict(weights or config.get("implementation_quality_weights", DEFAULT_WEIGHTS))
        if set(self.weights) != set(DEFAULT_WEIGHTS):
            raise ValueError("Conviction engine weights must define all seven required components.")
        if any(value < 0 for value in self.weights.values()) or not np.isclose(sum(self.weights.values()), 1.0):
            raise ValueError("Conviction engine weights must be non-negative and sum to 1.")

        self.quality_thresholds = dict(quality_thresholds or config.get("quality_thresholds", DEFAULT_QUALITY_THRESHOLDS))
        self.leverage_bounds = dict(leverage_bounds or config.get("leverage_bounds", DEFAULT_LEVERAGE_BOUNDS))
        if self.leverage_bounds["max_leverage"] <= self.leverage_bounds["min_leverage"]:
            raise ValueError("max_leverage must exceed min_leverage in leverage_bounds.")

        self.ambiguity_penalty_weight = (
            ambiguity_penalty_weight
            if ambiguity_penalty_weight is not None
            else float(config.get("ambiguity_penalty_weight", 0.25))
        )
        if not 0.0 <= self.ambiguity_penalty_weight <= 1.0:
            raise ValueError("ambiguity_penalty_weight must be in [0, 1].")

        default_limits = config.get("default_leverage_limits")
        self.default_leverage_limits: Optional[LeverageLimits] = (
            LeverageLimits(**default_limits) if default_limits else None
        )

    @staticmethod
    def _load_config(config_path: Optional[Path]) -> Dict[str, Any]:
        path = config_path or DEFAULT_CONFIG_PATH
        try:
            with open(path, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except Exception as exc:
            logger.warning("Falling back to built-in conviction defaults: failed to load %s: %s", path, exc)
            return {}

    def compute_implementation_quality(self, inputs: ConvictionInputs) -> float:
        """Deterministic weighted composite of independently sourced evidence."""
        core = (
            self.weights["iav"] * inputs.iav
            + self.weights["aqd_quality"] * inputs.aqd_quality
            + self.weights["anomaly_score"] * inputs.anomaly_score
            + self.weights["manager_breadth_score"] * inputs.manager_breadth_score
            + self.weights["persistence_score"] * inputs.persistence_score
            + self.weights["diffusion_score"] * inputs.diffusion_score
            + self.weights["evidence_quality"] * inputs.evidence_quality
        )
        penalty = self.ambiguity_penalty_weight * inputs.ambiguity_penalty
        return float(np.clip(core - penalty, 0.0, 1.0))

    def classify_quality(self, quality: float) -> str:
        if quality < self.quality_thresholds["weak_max"]:
            return "weak"
        if quality < self.quality_thresholds["emerging_max"]:
            return "emerging"
        if quality < self.quality_thresholds["confirmed_max"]:
            return "confirmed"
        return "strong"

    def compute_requested_leverage(self, quality: float) -> float:
        """Convert implementation quality into a *requested* exposure, pre-risk-caps."""
        min_leverage = self.leverage_bounds["min_leverage"]
        max_leverage = self.leverage_bounds["max_leverage"]
        return float(min_leverage + quality * (max_leverage - min_leverage))

    def evaluate(
        self,
        inputs: ConvictionInputs,
        event_probability: Optional[EventProbability] = None,
    ) -> ConvictionResult:
        """Full deterministic pipeline: evidence -> quality -> requested leverage.

        The event's expected value is diagnostic only; it does not directly
        set leverage. Non-favorable expected value (EV <= 0) is flagged via a
        reason code rather than silently overridden.
        """
        reason_codes = []

        quality = self.compute_implementation_quality(inputs)
        tier = self.classify_quality(quality)
        requested_leverage = self.compute_requested_leverage(quality)

        reason_codes.append(f"IMPLEMENTATION_QUALITY_{tier.upper()}")

        event_ev = inputs.event_expected_value
        if event_probability is not None:
            event_ev = event_probability.expected_value
        if event_ev <= 0:
            reason_codes.append("EVENT_EXPECTED_VALUE_NON_POSITIVE")
        if inputs.event_probability_quality < 0.5:
            reason_codes.append("EVENT_PROBABILITY_LOW_QUALITY")
        if inputs.ambiguity_penalty > 0:
            reason_codes.append("AMBIGUITY_PENALTY_APPLIED")

        return ConvictionResult(
            implementation_quality=quality,
            quality_tier=tier,
            requested_leverage=requested_leverage,
            reason_codes=reason_codes,
        )


__all__ = ["ConvictionEngine", "DEFAULT_WEIGHTS", "DEFAULT_QUALITY_THRESHOLDS", "DEFAULT_LEVERAGE_BOUNDS"]
