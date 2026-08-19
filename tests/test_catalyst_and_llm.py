"""Tests for concept mapping, the catalyst pathway and the language model seam."""

import json
from datetime import date, timedelta

import pytest

from orchestration.llm import HostedLanguageModel, ModelConfig, resolve_config
from research.catalyst import CatalystPlanner
from research.lexicon import Stance, TradeKind, expand
from research.strategy_generation import StrategyGenerator


@pytest.fixture(scope="module")
def generator() -> StrategyGenerator:
    return StrategyGenerator()


@pytest.fixture(scope="module")
def planner(generator) -> CatalystPlanner:
    return CatalystPlanner(generator)


# -- lexicon ---------------------------------------------------------------


def test_macro_vocabulary_maps_onto_universe_functions():
    match = expand("Lets trade FOMC Notes to Jackson Hole")
    assert match.matched
    assert match.kind is TradeKind.MACRO_EVENT
    assert "FOMC decision" in match.events and "Jackson Hole symposium" in match.events
    assert {"duration_short", "fed_funds_proxy", "tail_risk_hedge"} <= match.functions


def test_a_dated_event_outranks_an_adoption_theme():
    match = expand("how does the FOMC affect nuclear power")
    assert match.kind is TradeKind.MACRO_EVENT


def test_stance_is_read_from_the_question():
    assert expand("what if the Fed is hawkish").stance is Stance.HAWKISH
    assert expand("what if they cut").stance is Stance.DOVISH
    assert expand("FOMC decision").stance is Stance.VOLATILITY


def test_adoption_vocabulary_stays_on_the_adoption_path():
    match = expand("uranium and smr adoption")
    assert match.kind is TradeKind.ADOPTION
    assert "uranium_mining" in match.functions


def test_concept_expansion_reaches_strategies_literal_search_cannot(generator):
    """'gpu' appears in no theme or function name, yet must still find compute strategies."""
    assert not [fn for fn in generator.functions() if "gpu" in fn]
    results = generator.search("gpu", limit=10)
    assert results
    assert {c.function for c in results} & set(expand("gpu").functions)


# -- catalyst pathway ------------------------------------------------------


def test_fomc_routes_to_expression_vehicles(planner):
    strategy = planner.plan(expand("FOMC and Jackson Hole"))
    assert strategy.legs
    assert {"TBT", "UUP"} & {leg.ticker for leg in strategy.legs}


def test_stance_changes_the_instruments(planner):
    hawkish = planner.plan(expand("FOMC hawkish higher for longer"))
    dovish = planner.plan(expand("FOMC cut easing pivot"))
    assert hawkish.stance is Stance.HAWKISH and dovish.stance is Stance.DOVISH
    assert {leg.ticker for leg in hawkish.legs} != {leg.ticker for leg in dovish.legs}
    assert "TBT" in {leg.ticker for leg in hawkish.legs}


def test_catalyst_never_claims_an_adoption_signal(planner):
    strategy = planner.plan(expand("Jackson Hole"))
    assert strategy.adoption_available is False
    codes = " ".join(strategy.limitations)
    assert "ADOPTION_SIGNAL_UNAVAILABLE" in codes
    assert "DISCLOSURE_LATENCY" in codes


def test_rates_complex_genuinely_has_no_disclosing_managers(generator):
    """The limitation is structural, not a data gap: assert it against the universe."""
    signal = {"active_thematic", "rules_based_thematic", "specialist_adjacency"}
    rates = [f for f in generator.funds if f.primary_theme == "rate_transmission_hedge"]
    assert rates
    assert not [f for f in rates if f.classification in signal]


def test_a_catalyst_without_a_date_cannot_be_sized(planner):
    strategy = planner.plan(expand("FOMC"))
    assert strategy.catalyst_date is None
    assert any("CATALYST_DATE_REQUIRED" in reason for reason in strategy.limitations)
    assert strategy.minimum_expiration() is None


def test_expiration_floor_clears_catalyst_plus_buffer(planner):
    catalyst = date(2026, 9, 17)
    strategy = planner.plan(expand("FOMC"), catalyst_date=catalyst, execution_buffer_days=14)
    assert strategy.minimum_expiration() > catalyst + timedelta(days=14)
    assert not any("CATALYST_DATE_REQUIRED" in reason for reason in strategy.limitations)


# -- language model seam ---------------------------------------------------


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, content):
        self.content = content
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse({"choices": [{"message": {"content": self.content}}]})


def _model(content: str) -> HostedLanguageModel:
    session = FakeSession(content)
    model = HostedLanguageModel(ModelConfig("openai", "gpt-4o", "sk-test"), session=session)
    return model


def test_model_routes_to_a_known_intent():
    intent = _model(json.dumps({"intent": "catalyst", "args": {"query": "FOMC", "stance": "HAWKISH"}})).route(
        "trade the FOMC", history=[], intents=["catalyst", "generate"]
    )
    assert intent.name == "catalyst"
    assert intent.args["stance"] == "HAWKISH"


def test_model_cannot_invent_an_intent():
    assert _model(json.dumps({"intent": "execute_order", "args": {}})).route(
        "just do it", history=[], intents=["catalyst", "generate"]
    ) is None


def test_malformed_model_output_falls_back_rather_than_crashing():
    assert _model("not json at all").route("hello", history=[], intents=["generate"]) is None


def test_fenced_json_is_tolerated():
    fenced = '```json\n{"intent": "generate", "args": {"query": "nuclear"}}\n```'
    assert _model(fenced).route("nuclear", history=[], intents=["generate"]).name == "generate"


def test_placeholder_api_keys_are_not_treated_as_configured(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "your_openai_api_key_here")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert resolve_config() is None

    monkeypatch.setenv("OPENAI_API_KEY", "sk-real")
    assert resolve_config().provider == "openai"
