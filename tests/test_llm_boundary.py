import pytest

from agents.hypothesis_agent import CatalystType, HypothesisAgent
from analytics.hypothesis_quality import HypothesisQualityScorer


def test_llm_hypothesis_contract_has_no_conviction_score():
    hypothesis = HypothesisAgent().register_hypothesis(
        ticker="ABC",
        thematic_cluster="enterprise_ai",
        thesis_statement="Adoption is expanding across relevant institutions.",
        primary_catalyst=CatalystType.PRODUCT_CYCLE,
    )
    assert not hasattr(hypothesis, "conviction_score")
    assert "conviction_score" not in hypothesis.to_dict()


def test_quantitative_quality_is_scored_downstream():
    result = HypothesisQualityScorer().score(3, 2, 1.0, ambiguity=0.0)
    assert result.score == 1.0
    assert result.ambiguity_penalty == 0.0


def test_quality_scorer_rejects_invalid_numeric_inputs():
    with pytest.raises(ValueError):
        HypothesisQualityScorer().score(1, 1, 1.5)
