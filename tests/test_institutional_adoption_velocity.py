import pytest

from analytics.institutional_adoption_velocity import IAVInputs, InstitutionalAdoptionVelocity


def test_iav_composes_adoption_factors_and_penalties():
    model = InstitutionalAdoptionVelocity(acceptance_threshold=0.20)
    result = model.compute(IAVInputs(
        normalized_active_allocation=0.8,
        independent_manager_breadth=0.7,
        persistence=0.6,
        diffusion=0.5,
        strategic_relevance=0.9,
        anomaly_quality=0.8,
        ambiguity=0.1,
        crowding_penalty=0.2,
    ))
    assert 0.0 < result.composite_score < 1.0
    assert result.accepted is True
    assert result.penalties["crowding_penalty"] == 0.2


def test_iav_rejects_invalid_component_ranges():
    model = InstitutionalAdoptionVelocity()
    with pytest.raises(ValueError, match="diffusion"):
        model.compute(IAVInputs(
            normalized_active_allocation=0.0,
            independent_manager_breadth=0.0,
            persistence=0.0,
            diffusion=1.5,
            strategic_relevance=0.0,
            anomaly_quality=0.0,
        ))


def test_iav_is_not_an_nav_calculator():
    assert not hasattr(InstitutionalAdoptionVelocity, "calculate_inav")
    assert not hasattr(InstitutionalAdoptionVelocity, "_black_scholes_price")
