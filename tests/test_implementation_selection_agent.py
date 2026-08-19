"""Chat-level wiring: implementations must be generated and selected before sizing."""

import tempfile
from datetime import date

import pytest

from console.demo.wiring import build_stack
from orchestration.agent import ChatAgent
from research.funnel import ResearchFunnel, FunnelStage
from research.implementations import ImplementationType

STRATEGY_ID = "power_infrastructure:uranium_mining"


@pytest.fixture()
def agent(tmp_path) -> ChatAgent:
    stack = build_stack(log_path=tmp_path / "events.jsonl")
    stack.workbench.create_project(project_id="p1", name="Test project")
    brief = stack.workbench.open_session(project_id="p1")
    chat = ChatAgent(
        funnel=ResearchFunnel(as_of=date(2026, 8, 18), storage_dir=tmp_path / "sim"),
        workbench=stack.workbench,
        transactions=stack.transactions,
        approvals=stack.approvals,
        project_id="p1",
        session_id=brief.session_id,
        user_id="op-1",
    )
    chat.stack = stack
    return chat


def past_thesis(agent: ChatAgent) -> None:
    agent.send("find strategies about nuclear power")
    agent.send("synthesize uranium mining")
    agent.send("open a thesis on this")


def select_top(agent: ChatAgent):
    candidates = agent.funnel.generate_implementations(STRATEGY_ID)
    chosen = next(c for c in candidates if c.type != ImplementationType.NO_TRADE)
    agent.act(
        {"type": "select_implementation", "payload": {"strategy_id": STRATEGY_ID, "implementation_id": chosen.id}}
    )
    return chosen


# -- the guard, from the chat surface ---------------------------------------


def test_design_trade_publishes_siblings_instead_of_choosing(agent):
    """This is the bug: advancing straight into a single implementation."""
    past_thesis(agent)
    turn = agent.send("design a trade for it")

    view_types = {row["type"] for row in turn.view.components[0].data["rows"]}
    assert {"ETF_LONG", "ETF_HEDGED", "OPTIONS", "NO_TRADE"} <= view_types
    assert agent.funnel.selected_implementation(STRATEGY_ID) is None


def test_generate_implementations_requires_a_thesis(agent):
    agent.send("find strategies about nuclear power")
    agent.send("synthesize uranium mining")
    turn = agent.send("compare implementations")
    assert "no thesis" in turn.reply.lower() or "open a thesis" in turn.reply.lower()


def test_select_implementation_before_generation_generates_instead_of_erroring(agent):
    """Never crash the chat: fall back to publishing the set."""
    past_thesis(agent)
    turn = agent.act(
        {"type": "select_implementation", "payload": {"strategy_id": STRATEGY_ID, "implementation_id": "bogus"}}
    )
    assert turn is not None
    assert agent.funnel.selected_implementation(STRATEGY_ID) is None


def test_selecting_an_unknown_id_after_generation_reports_it_cleanly(agent):
    past_thesis(agent)
    agent.funnel.generate_implementations(STRATEGY_ID)
    turn = agent.act(
        {"type": "select_implementation", "payload": {"strategy_id": STRATEGY_ID, "implementation_id": "bogus"}}
    )
    assert "not one of the generated candidates" in turn.reply


# -- selection then sizing ---------------------------------------------------


def test_selecting_then_designing_produces_a_preview(agent):
    past_thesis(agent)
    chosen = select_top(agent)

    turn = agent.send("design a trade for it")
    assert "needs your approval" in turn.reply
    intent = agent.transactions.records()[-1].intent
    assert chosen.type.value in intent.rationale


def test_the_sized_ticker_matches_the_selected_implementation(agent):
    past_thesis(agent)
    chosen = select_top(agent)

    agent.send("design a trade for it")
    intent = agent.transactions.records()[-1].intent
    assert intent.underlying == chosen.instruments[0].ticker


def test_selecting_a_button_click_can_go_straight_to_a_preview(agent):
    """A click is a pre-parsed sentence: select_implementation routes through design_trade."""
    past_thesis(agent)
    candidates = agent.funnel.generate_implementations(STRATEGY_ID)
    chosen = next(c for c in candidates if c.type != ImplementationType.NO_TRADE)

    turn = agent.act(
        {"type": "select_implementation", "payload": {"strategy_id": STRATEGY_ID, "implementation_id": chosen.id}}
    )
    assert "needs your approval" in turn.reply


def test_selecting_no_trade_commits_nothing(agent):
    past_thesis(agent)
    candidates = agent.funnel.generate_implementations(STRATEGY_ID)
    no_trade = next(c for c in candidates if c.type == ImplementationType.NO_TRADE)

    turn = agent.act(
        {"type": "select_implementation", "payload": {"strategy_id": STRATEGY_ID, "implementation_id": no_trade.id}}
    )
    assert "NO_TRADE" in turn.reply
    assert agent.transactions.records() == []


def test_options_selection_is_refused_rather_than_faked(agent):
    """Sizing an option leg needs a catalyst date this handler does not collect."""
    past_thesis(agent)
    candidates = agent.funnel.generate_implementations(STRATEGY_ID)
    options = next(c for c in candidates if c.type == ImplementationType.OPTIONS)
    agent.act(
        {"type": "select_implementation", "payload": {"strategy_id": STRATEGY_ID, "implementation_id": options.id}}
    )

    turn = agent.send("design a trade for it")
    assert "catalyst" in turn.reply.lower()
    assert agent.transactions.records() == []


def test_funnel_stage_reflects_generation_then_selection(agent):
    past_thesis(agent)
    assert agent.funnel.positions[STRATEGY_ID].stage is FunnelStage.EVIDENCE_REVIEW

    agent.send("compare implementations")
    assert agent.funnel.positions[STRATEGY_ID].stage is FunnelStage.IMPLEMENTATION_GENERATION

    # Selecting a real candidate proceeds straight to sizing, so the stage
    # advances through IMPLEMENTATION_SELECTED to APPROVAL in the same click.
    select_top(agent)
    position = agent.funnel.positions[STRATEGY_ID]
    assert position.stage is FunnelStage.APPROVAL
    assert position.implementation_id is not None


def test_intent_rationale_cites_how_many_alternatives_were_compared(agent):
    past_thesis(agent)
    chosen = select_top(agent)
    agent.send("design a trade for it")

    intent = agent.transactions.records()[-1].intent
    generated_count = len(agent.funnel.implementations(STRATEGY_ID))
    assert str(generated_count) in intent.rationale
