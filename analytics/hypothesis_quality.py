"""Deterministic scoring of structured hypotheses after semantic extraction."""

from dataclasses import dataclass
from typing import Sequence

import numpy as np


@dataclass(frozen=True)
class HypothesisQualityResult:
    score: float
    evidence_quality: float
    falsifiability: float
    catalyst_specificity: float
    ambiguity_penalty: float


class HypothesisQualityScorer:
    """Score evidence quality without accepting an LLM confidence value."""

    def score(
        self,
        evidence_count: int,
        falsification_criteria_count: int,
        catalyst_specificity: float,
        ambiguity: float = 0.0,
    ) -> HypothesisQualityResult:
        if evidence_count < 0 or falsification_criteria_count < 0:
            raise ValueError("evidence counts cannot be negative")
        if not 0.0 <= catalyst_specificity <= 1.0:
            raise ValueError("catalyst_specificity must be in [0, 1]")
        if not 0.0 <= ambiguity <= 1.0:
            raise ValueError("ambiguity must be in [0, 1]")
        evidence_quality = float(np.clip(evidence_count / 3.0, 0.0, 1.0))
        falsifiability = float(np.clip(falsification_criteria_count / 2.0, 0.0, 1.0))
        score = float(np.clip((evidence_quality + falsifiability + catalyst_specificity) / 3.0 - ambiguity * 0.25, 0.0, 1.0))
        return HypothesisQualityResult(score, evidence_quality, falsifiability, catalyst_specificity, ambiguity * 0.25)


__all__ = ["HypothesisQualityResult", "HypothesisQualityScorer"]
