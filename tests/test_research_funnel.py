"""Tests for the research funnel: strategy generation, synthesis and the chat agent."""

import tempfile
from datetime import date

import pytest

from console.demo.wiring import build_stack
from orchestration.agent import ChatAgent, Intent, KeywordRouter
from research.funnel import FunnelStage, ResearchFunnel
from research.simulation import ingest_candidate
from research.strategy_generation import MIN_INDEPENDENT_CLUSTERS, StrategyGenerator
from research.synthesis import DisclosureSynthesizer, build_panel
from ui.registry import validate_view

AS_OF = date(2026, 8, 18)


@pytest.fixture(scope="module")
def generator() -> StrategyGenerator:
    return StrategyGenerator()


@pytest.fixture()
def funnel(tmp_path) -> ResearchFunnel:
    return ResearchFunnel(as_of=AS_OF, storage_dir=tmp_path / "sim")


@pytest.fixture()
def agent(funnel, tmp_path) -> ChatAgent:
    stack = build_stack(log_path=tmp_path / "events.jsonl")
    stack.workbench.create_project(project_id="p1", name="Test project")
    brief = stack.workbench.open_session(project_id="p1")
    chat = ChatAgent(
        funnel=funnel,
        workbench=stack.workbench,
        transactions=stack.transactions,
        approvals=stack.approvals,
        project_id="p1",
        session_id=brief.session_id,
        user_id="op-1",
    )
    chat.stack = stack
    return chat


# -- stage 1 ---------------------------------------------------------------


def test_universe_loads_with_real_themes_and_clusters(generator):
    assert len(generator.funds) > 50
    assert "power_infrastructure" in generator.themes()
    assert "uranium_mining" in generator.functions("power_infrastructure")


def test_search_maps_natural_language_onto_functions(generator):
    ids = {c.strategy_id for c in generator.search("nuclear power")}
    assert any("uranium_mining" in i or "smr_technology" in i for i in ids)


def test_single_cluster_strategies_are_rejected(generator):
    candidate = generator.build("power_infrastructure", "nuclear_reactors")
    assert candidate.cluster_count < MIN_INDEPENDENT_CLUSTERS
    assert not candidate.viable
    assert any("INSUFFICIENT_MANAGER_BREADTH" in r for r in candidate.rejection_reasons)


def test_search_hides_unviable_candidates_by_default(generator):
    assert all(c.viable for c in generator.search("nuclear power", limit=30))
    assert any(not c.viable for c in generator.search("nuclear power", limit=30, include_unviable=True))


def test_disclosing_funds_are_valid_implementation_vehicles(generator):
    candidate = generator.build("power_infrastructure", "uranium_mining")
    assert candidate.viable
    assert candidate.implementation_tickers
    assert set(candidate.implementation_tickers) & set(candidate.signal_tickers)


def test_observability_rewards_breadth(generator):
    broad = generator.build("power_infrastructure", "grid_transmission")
    narrow = generator.build("power_infrastructure", "uranium_mining")
    assert broad.cluster_count > narrow.cluster_count
    assert broad.observability_score > narrow.observability_score


# -- stage 2 ---------------------------------------------------------------


def _synthesize(generator, regime: str, tmp_path):
    candidate = generator.build("power_infrastructure", "uranium_mining")
    rows = ingest_candidate(candidate, as_of=AS_OF, regime=regime, storage_dir=tmp_path)
    synthesizer = DisclosureSynthesizer(
        cluster_map=generator.cluster_map(),
        theme_map=generator.theme_map(),
        relevance_map={f.fund_id: f.mandate_relevance for f in generator.funds},
        independence_map={f.fund_id: f.manager_independence for f in generator.funds},
        anomaly_lookback=3,
    )
    return synthesizer.synthesize(
        build_panel(rows), strategy_id=candidate.strategy_id, theme=candidate.theme, function=candidate.function
    )


def test_simulated_disclosures_pass_the_real_ingestor(generator, tmp_path):
    candidate = generator.build("power_infrastructure", "uranium_mining")
    rows = ingest_candidate(candidate, as_of=AS_OF, storage_dir=tmp_path)
    panel = build_panel(rows)

    assert not panel.empty
    assert (panel["u_normalized"] > 0).all()
    assert {"security_id", "fund_id", "etf_shares_outstanding", "canonical_id"} <= set(panel.columns)


def test_anomaly_detection_preserves_identifier_columns(generator, tmp_path):
    """Regression: groupby.apply dropped grouping columns on pandas 3."""
    from analytics.anomaly_detector import AnomalyDetector

    candidate = generator.build("power_infrastructure", "uranium_mining")
    panel = build_panel(ingest_candidate(candidate, as_of=AS_OF, storage_dir=tmp_path))
    enriched, _ = AnomalyDetector(min_history_periods=3).detect_anomalies(panel, lookback=3)

    assert {"fund_id", "security_id", "z_score", "aqd", "aqd_pct"} <= set(enriched.columns)


def test_accumulation_and_distribution_produce_opposite_signals(generator, tmp_path):
    broad = _synthesize(generator, "BROAD_ADOPTION", tmp_path / "a")
    distributing = _synthesize(generator, "DISTRIBUTION", tmp_path / "b")

    assert broad.usable and distributing.usable
    assert broad.leader().iav.composite_score > 0
    assert distributing.leader().iav.composite_score < 0
    assert broad.leader().persistence > distributing.leader().persistence


def test_synthesis_emits_traceable_evidence(generator, tmp_path):
    synthesis = _synthesize(generator, "BROAD_ADOPTION", tmp_path)
    evidence = synthesis.leader().evidence()

    assert evidence
    assert {"AnomalyDetector", "ManagerGraphEngine"} <= {row.source for row in evidence}
    assert any(row.stance == "SUPPORTS" for row in evidence)


def test_insufficient_history_blocks_synthesis(generator, tmp_path):
    candidate = generator.build("power_infrastructure", "uranium_mining")
    rows = ingest_candidate(candidate, as_of=AS_OF, storage_dir=tmp_path, periods=1)
    synthesizer = DisclosureSynthesizer(cluster_map=generator.cluster_map(), theme_map=generator.theme_map())
    synthesis = synthesizer.synthesize(
        build_panel(rows), strategy_id=candidate.strategy_id, theme=candidate.theme, function=candidate.function
    )

    assert not synthesis.usable
    assert any("INSUFFICIENT_HISTORY" in r for r in synthesis.blocking_reasons)


# -- chat ------------------------------------------------------------------


def test_router_maps_phrases_to_intents():
    router = KeywordRouter()
    assert router.route("where did we leave off", history=[], intents=[]).name == "continuity"
    assert router.route("what is waiting on me", history=[], intents=[]).name == "inbox"
    assert router.route("synthesize the disclosures", history=[], intents=[]).name == "synthesize"
    assert router.route("find strategies about nuclear", history=[], intents=[]).name == "generate"


def test_conversation_walks_the_whole_funnel(agent):
    agent.send("find strategies about nuclear power")
    agent.send("synthesize uranium mining")
    thesis_turn = agent.send("open a thesis on this")
    trade_turn = agent.send("design a trade for it")

    assert "Opened" in thesis_turn.reply
    assert "needs your approval" in trade_turn.reply

    position = agent.funnel.positions["power_infrastructure:uranium_mining"]
    assert position.stage is FunnelStage.APPROVAL
    assert position.thesis_id and position.intent_id


def test_every_generated_view_passes_the_ui_contract(agent):
    for message in [
        "find strategies about nuclear power",
        "synthesize uranium mining",
        "open a thesis on this",
        "design a trade for it",
        "what is waiting on me",
    ]:
        turn = agent.send(message)
        if turn.view is None:
            continue
        hashes = {r.preview.intent_hash for r in agent.transactions.records() if r.preview}
        validate_view(turn.view, authorized_hashes=hashes)


def test_explicit_strategy_id_beats_the_focused_one(agent):
    agent.send("find strategies about nuclear power")
    agent.send("synthesize power_infrastructure:grid_transmission")
    assert agent.focus_strategy_id == "power_infrastructure:grid_transmission"

    agent.send("synthesize power_infrastructure:uranium_mining")
    assert agent.focus_strategy_id == "power_infrastructure:uranium_mining"


def test_a_thesis_cannot_be_opened_without_synthesis(agent):
    turn = agent.send("open a thesis on this")
    assert "Synthesize the disclosures first" in turn.reply


def test_a_trade_cannot_be_designed_without_a_thesis(agent):
    agent.send("find strategies about nuclear power")
    agent.send("synthesize uranium mining")
    turn = agent.send("design a trade for it")
    assert "no thesis" in turn.reply


def test_opening_a_thesis_records_evidence_and_a_watch_condition(agent):
    agent.send("find strategies about nuclear power")
    agent.send("synthesize uranium mining")
    agent.send("open a thesis on this")

    state = agent.workbench.projection(project_id="p1")
    thesis = next(iter(state.theses.values()))
    assert thesis.evidence_ids
    assert thesis.counter_evidence_ids
    assert thesis.watch_conditions[0].metric == "iav"
    assert thesis.watch_conditions[0].on_breach == "DEMOTE"


def test_a_button_click_runs_the_same_handler_as_a_sentence(agent):
    agent.send("find strategies about nuclear power")
    turn = agent.act(
        {"type": "synthesize_disclosures", "payload": {"strategy_id": "power_infrastructure:uranium_mining"}}
    )
    assert turn is not None
    assert agent.funnel.synthesis("power_infrastructure:uranium_mining") is not None


def test_the_agent_never_approves_its_own_trade(agent):
    agent.send("find strategies about nuclear power")
    agent.send("synthesize uranium mining")
    agent.send("open a thesis on this")
    agent.send("design a trade for it")

    record = agent.transactions.records()[-1]
    assert record.state.value == "AWAITING_APPROVAL"
    assert record.approval is None
    assert agent.stack.broker.submitted == []
