"""Path B: model-proposed implementations must pass structural and policy/risk gates."""

import tempfile
from datetime import date

import pytest

from audit.decision_records import DecisionRecorder
from research.funnel import ResearchFunnel, SelectionBeforeGeneration
from research.implementations import ImplementationType
from research.llm_implementations import (
    LLMImplementationGenerator,
    ProposalSet,
    ProposedImplementation,
    ProposedInstrument,
    permitted_tickers,
)

STRATEGY_ID = "power_infrastructure:grid_transmission"


@pytest.fixture()
def funnel(tmp_path) -> ResearchFunnel:
    f = ResearchFunnel(as_of=date(2026, 8, 18), storage_dir=tmp_path / "sim")
    f.generate()
    f.synthesize(STRATEGY_ID)
    return f


@pytest.fixture()
def strategy(funnel):
    return funnel.candidate(STRATEGY_ID)


@pytest.fixture()
def synthesis(funnel):
    return funnel.synthesis(STRATEGY_ID)


@pytest.fixture()
def universe(strategy, synthesis):
    return sorted(permitted_tickers(strategy, synthesis))


class FakeResponse:
    def __init__(self, parsed, *, model="gpt-4o-mock", response_id="resp_1"):
        self._parsed = parsed
        self.model = model
        self.id = response_id

    @property
    def output_parsed(self):
        return self._parsed


class FakeClient:
    """Stands in for OpenAI().responses; captures every call for inspection."""

    def __init__(self, response=None, *, raise_on_call: Exception | None = None):
        self._response = response
        self._raise = raise_on_call
        self.calls = []

        class _Responses:
            def parse(inner_self, **kwargs):
                self.calls.append(kwargs)
                if self._raise is not None:
                    raise self._raise
                return self._response

        self.responses = _Responses()


def proposal(
    type_: ImplementationType,
    *,
    ticker: str = "X",
    thesis_fit: float = 0.7,
    rationale: str = "grounded in measured evidence",
    risks=None,
    liquidity_score: float | None = 0.6,
    instruments=None,
) -> ProposedImplementation:
    if instruments is None:
        instruments = [] if type_ == ImplementationType.NO_TRADE else [ProposedInstrument(ticker=ticker)]
    return ProposedImplementation(
        type=type_,
        thesis_fit=thesis_fit,
        expected_return=0.05,
        downside_risk=0.1,
        liquidity_score=liquidity_score,
        instruments=instruments,
        rationale=rationale,
        risks=["market risk"] if risks is None else risks,
    )


def generate(strategy, synthesis, candidates, **kwargs):
    client = FakeClient(FakeResponse(ProposalSet(candidates=candidates)))
    result = LLMImplementationGenerator(client=client).generate(strategy, synthesis, **kwargs)
    return result, client


# -- structural gate ---------------------------------------------------------


def test_an_unknown_type_never_parses():
    with pytest.raises(Exception):
        ProposedImplementation(type="NOT_A_REAL_TYPE", thesis_fit=0.5, rationale="x")


def test_thesis_fit_out_of_bounds_never_parses():
    with pytest.raises(Exception):
        ProposedImplementation(type=ImplementationType.ETF_LONG, thesis_fit=1.5, rationale="x")


def test_missing_rationale_never_parses():
    with pytest.raises(Exception):
        ProposedImplementation(type=ImplementationType.ETF_LONG, thesis_fit=0.5, rationale="")


# -- policy/risk gate (the schema is not the validation gate) ---------------


def test_an_invented_ticker_is_quarantined_not_trusted(strategy, synthesis, universe):
    result, _ = generate(
        strategy, synthesis, [proposal(ImplementationType.SINGLE_NAME, ticker="TOTALLY_INVENTED_TICKER")]
    )
    accepted_types = {c.type for c in result.accepted}
    assert ImplementationType.SINGLE_NAME not in accepted_types
    assert any("UNKNOWN_INSTRUMENT" in r for q in result.quarantined for r in q.reasons)


def test_a_permitted_ticker_is_accepted(strategy, synthesis, universe):
    result, _ = generate(strategy, synthesis, [proposal(ImplementationType.ETF_LONG, ticker=universe[0])])
    accepted_types = {c.type for c in result.accepted}
    assert ImplementationType.ETF_LONG in accepted_types


def test_a_duplicate_type_is_quarantined(strategy, synthesis, universe):
    result, _ = generate(
        strategy,
        synthesis,
        [
            proposal(ImplementationType.ETF_LONG, ticker=universe[0], rationale="first"),
            proposal(ImplementationType.ETF_LONG, ticker=universe[0], rationale="second"),
        ],
    )
    etf_long = [c for c in result.accepted if c.type == ImplementationType.ETF_LONG]
    assert len(etf_long) == 1
    assert any("DUPLICATE_TYPE" in r for q in result.quarantined for r in q.reasons)


def test_liquidity_below_the_floor_is_quarantined(strategy, synthesis, universe):
    result, _ = generate(
        strategy, synthesis, [proposal(ImplementationType.ETF_LONG, ticker=universe[0], liquidity_score=0.001)]
    )
    assert ImplementationType.ETF_LONG not in {c.type for c in result.accepted}
    assert any("LIQUIDITY_BELOW_FLOOR" in r for q in result.quarantined for r in q.reasons)


def test_options_without_stated_risk_is_quarantined(strategy, synthesis, universe):
    result, _ = generate(
        strategy, synthesis, [proposal(ImplementationType.OPTIONS, ticker=universe[0], risks=[])]
    )
    assert ImplementationType.OPTIONS not in {c.type for c in result.accepted}
    assert any("OPTIONS_REQUIRE_STATED_RISKS" in r for q in result.quarantined for r in q.reasons)


def test_an_instrument_with_no_ticker_at_all_is_quarantined(strategy, synthesis):
    result, _ = generate(strategy, synthesis, [proposal(ImplementationType.ETF_LONG, instruments=[])])
    assert ImplementationType.ETF_LONG not in {c.type for c in result.accepted}
    assert any("NO_INSTRUMENT_SPECIFIED" in r for q in result.quarantined for r in q.reasons)


def test_an_unknown_instrument_role_is_quarantined(strategy, synthesis, universe):
    result, _ = generate(
        strategy,
        synthesis,
        [proposal(ImplementationType.ETF_LONG, instruments=[ProposedInstrument(ticker=universe[0], role="SHADOW")])],
    )
    assert ImplementationType.ETF_LONG not in {c.type for c in result.accepted}
    assert any("UNKNOWN_INSTRUMENT_ROLE" in r for q in result.quarantined for r in q.reasons)


# -- NO_TRADE is never sourced from the model --------------------------------


def test_no_trade_is_always_present_even_if_the_model_omits_it(strategy, synthesis, universe):
    result, _ = generate(strategy, synthesis, [proposal(ImplementationType.ETF_LONG, ticker=universe[0])])
    no_trade = next(c for c in result.accepted if c.type == ImplementationType.NO_TRADE)
    assert no_trade.generated_by == "EDGE_DETERMINISTIC"


def test_a_model_proposed_no_trade_is_ignored_in_favor_of_the_deterministic_one(strategy, synthesis, universe):
    result, _ = generate(
        strategy,
        synthesis,
        [proposal(ImplementationType.NO_TRADE, rationale="model says do nothing", thesis_fit=0.99)],
    )
    no_trade_candidates = [c for c in result.accepted if c.type == ImplementationType.NO_TRADE]
    assert len(no_trade_candidates) == 1
    assert no_trade_candidates[0].generated_by == "EDGE_DETERMINISTIC"


# -- provenance and grounding -------------------------------------------------


def test_accepted_candidates_are_tagged_with_the_model_that_proposed_them(strategy, synthesis, universe):
    result, _ = generate(strategy, synthesis, [proposal(ImplementationType.ETF_LONG, ticker=universe[0])])
    etf_long = next(c for c in result.accepted if c.type == ImplementationType.ETF_LONG)
    assert etf_long.generated_by == "OPENAI:gpt-4o-mock"


def test_the_prompt_only_offers_the_permitted_universe(strategy, synthesis, universe):
    result, client = generate(strategy, synthesis, [proposal(ImplementationType.ETF_LONG, ticker=universe[0])])
    assert all(ticker in result.input_summary for ticker in universe)
    assert client.calls[0]["model"]


# -- failure modes degrade to the null option, never crash -------------------


def test_a_failed_model_call_still_returns_no_trade(strategy, synthesis):
    client = FakeClient(raise_on_call=RuntimeError("network unreachable"))
    result = LLMImplementationGenerator(client=client).generate(strategy, synthesis)
    assert [c.type for c in result.accepted] == [ImplementationType.NO_TRADE]
    assert result.error is not None
    assert "network unreachable" not in result.error  # exception message is not echoed verbatim


def test_a_missing_api_key_is_refused_without_a_client_override(strategy, synthesis, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = LLMImplementationGenerator().generate(strategy, synthesis)
    assert [c.type for c in result.accepted] == [ImplementationType.NO_TRADE]
    assert result.error is not None


# -- the model has no path to select or execute ------------------------------


def test_the_module_exposes_no_selection_or_execution_capability():
    import research.llm_implementations as module

    forbidden = {"select_implementation", "execute", "approve", "submit_order"}
    assert not forbidden & set(dir(module))


# -- decision record ----------------------------------------------------------


def test_decision_record_captures_the_full_chain(tmp_path, strategy, synthesis, universe):
    result, _ = generate(
        strategy,
        synthesis,
        [
            proposal(ImplementationType.ETF_LONG, ticker=universe[0]),
            proposal(ImplementationType.SINGLE_NAME, ticker="INVENTED"),
        ],
    )
    recorder = DecisionRecorder(log_dir=tmp_path / "decisions")
    record = recorder.record_implementation_generation(
        project_id="p1",
        strategy_id=STRATEGY_ID,
        model=result.model,
        response_id=result.response_id,
        instructions=result.instructions,
        input_summary=result.input_summary,
        raw_candidates=result.raw_candidates,
        validation_results=[{"proposed_type": q.proposed_type, "reasons": q.reasons} for q in result.quarantined],
        accepted_candidate_ids=[c.id for c in result.accepted],
        error=result.error,
    )

    assert record.model == "gpt-4o-mock"
    assert record.response_id == "resp_1"
    assert len(record.raw_candidates) == 2
    assert any("UNKNOWN_INSTRUMENT" in r["reasons"][0] for r in record.validation_results)
    assert len(record.accepted_candidate_ids) == 2  # ETF_LONG + deterministic NO_TRADE

    reloaded = recorder.read_all()
    assert len(reloaded) == 1
    assert reloaded[0].record_hash == record.record_hash


def test_decision_record_hash_changes_if_the_file_is_tampered_with(tmp_path, strategy, synthesis, universe):
    recorder = DecisionRecorder(log_dir=tmp_path / "decisions")
    record = recorder.record_implementation_generation(
        project_id="p1",
        strategy_id=STRATEGY_ID,
        model="gpt-4o-mock",
        response_id="r1",
        instructions="x",
        input_summary="y",
        raw_candidates=[],
        validation_results=[],
        accepted_candidate_ids=[],
    )
    original_hash = record.record_hash

    import json

    path = next((tmp_path / "decisions").glob("*.json"))
    payload = json.loads(path.read_text())
    payload["accepted_candidate_ids"] = ["tampered"]
    path.write_text(json.dumps(payload))

    reloaded = recorder.read_all()[0]
    assert reloaded.record_hash == original_hash  # the stored hash is untouched
    assert reloaded.compute_hash() != original_hash  # but recomputing it reveals the tamper


def test_a_fake_key_never_appears_in_the_decision_record(tmp_path, strategy, synthesis, universe, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-must-not-leak-into-decision-record")
    result, _ = generate(strategy, synthesis, [proposal(ImplementationType.ETF_LONG, ticker=universe[0])])
    recorder = DecisionRecorder(log_dir=tmp_path / "decisions")
    recorder.record_implementation_generation(
        project_id="p1",
        strategy_id=STRATEGY_ID,
        model=result.model,
        response_id=result.response_id,
        instructions=result.instructions,
        input_summary=result.input_summary,
        raw_candidates=result.raw_candidates,
        validation_results=[],
        accepted_candidate_ids=[c.id for c in result.accepted],
    )
    path = next((tmp_path / "decisions").glob("*.json"))
    assert "sk-must-not-leak-into-decision-record" not in path.read_text()


# -- funnel wiring -------------------------------------------------------------


def test_funnel_requires_synthesis_before_the_llm_path_too(tmp_path):
    f = ResearchFunnel(as_of=date(2026, 8, 18), storage_dir=tmp_path / "sim")
    f.generate()
    with pytest.raises(SelectionBeforeGeneration):
        f.generate_implementations_llm(STRATEGY_ID)


def test_funnel_generate_implementations_llm_logs_and_stores(funnel, universe, tmp_path):
    client = FakeClient(FakeResponse(ProposalSet(candidates=[proposal(ImplementationType.ETF_LONG, ticker=universe[0])])))
    generator = LLMImplementationGenerator(client=client)
    recorder = DecisionRecorder(log_dir=tmp_path / "decisions")

    candidates = funnel.generate_implementations_llm(
        STRATEGY_ID, project_id="p1", generator=generator, recorder=recorder
    )
    assert {c.type for c in candidates} >= {ImplementationType.ETF_LONG, ImplementationType.NO_TRADE}
    assert len(recorder.read_all()) == 1
    assert funnel.selected_implementation(STRATEGY_ID) is None


def test_funnel_selection_works_identically_regardless_of_source(funnel, universe, tmp_path):
    client = FakeClient(FakeResponse(ProposalSet(candidates=[proposal(ImplementationType.ETF_LONG, ticker=universe[0])])))
    funnel.generate_implementations_llm(
        STRATEGY_ID, generator=LLMImplementationGenerator(client=client), recorder=DecisionRecorder(log_dir=tmp_path / "d")
    )
    etf_long = next(c for c in funnel.implementations(STRATEGY_ID) if c.type == ImplementationType.ETF_LONG)
    chosen = funnel.select_implementation(STRATEGY_ID, etf_long.id)
    assert chosen.generated_by.startswith("OPENAI:")
    assert funnel.selected_implementation(STRATEGY_ID) is chosen


def test_quarantined_candidates_are_retrievable_from_the_funnel(funnel, tmp_path):
    client = FakeClient(FakeResponse(ProposalSet(candidates=[proposal(ImplementationType.SINGLE_NAME, ticker="FAKE")])))
    funnel.generate_implementations_llm(
        STRATEGY_ID, generator=LLMImplementationGenerator(client=client), recorder=DecisionRecorder(log_dir=tmp_path / "d")
    )
    quarantined = funnel.quarantined_candidates(STRATEGY_ID)
    assert quarantined and "UNKNOWN_INSTRUMENT" in quarantined[0].reasons[0]
