"""A field change must invalidate every live view computed from it."""

from datetime import date

import pytest

from console.demo.wiring import build_stack
from orchestration.agent import ChatAgent
from research.funnel import ResearchFunnel
from ui.dependencies import DependencyMap, ViewProducer
from ui.hydration import field_value
from ui.state import UIEvent


@pytest.fixture()
def agent(tmp_path) -> ChatAgent:
    stack = build_stack(log_path=tmp_path / "events.jsonl")
    stack.workbench.create_project(project_id="p1", name="Macro")
    brief = stack.workbench.open_session(project_id="p1")
    return ChatAgent(
        funnel=ResearchFunnel(as_of=date(2026, 8, 18), storage_dir=tmp_path / "sim"),
        workbench=stack.workbench,
        transactions=stack.transactions,
        approvals=stack.approvals,
        project_id="p1",
        session_id=brief.session_id,
        user_id="op-1",
    )


def change(agent: ChatAgent, field_id: str, value):
    return agent.record_ui_event(
        UIEvent.field_changed(
            view_id="v-external",
            project_id=agent.project_id,
            session_id=agent.session_id,
            field_id=field_id,
            value=value,
        )
    )


# -- map ------------------------------------------------------------------


def test_map_returns_only_views_fed_by_the_changed_field():
    dependencies = DependencyMap()
    dependencies.register("v1", ViewProducer("catalyst", "catalyst", depends_on=frozenset({"catalyst_date"})))
    dependencies.register("v2", ViewProducer("trade", "design_trade", depends_on=frozenset({"max_loss"})))

    assert [v for v, _ in dependencies.affected_by("catalyst_date")] == ["v1"]
    assert [v for v, _ in dependencies.affected_by("max_loss")] == ["v2"]
    assert dependencies.affected_by("unrelated") == []


def test_map_replaces_and_forgets():
    dependencies = DependencyMap()
    producer = ViewProducer("catalyst", "catalyst", depends_on=frozenset({"catalyst_date"}))
    dependencies.register("v1", producer)
    dependencies.replace("v1", "v2", producer)

    assert dependencies.producer("v1") is None
    assert dependencies.fields_for("v2") == frozenset({"catalyst_date"})

    dependencies.forget("v2")
    assert len(dependencies) == 0


def test_producer_dependencies_accumulate():
    producer = ViewProducer("catalyst", "catalyst", depends_on=frozenset({"a"})).with_dependencies({"b"})
    assert producer.depends_on == frozenset({"a", "b"})


# -- agent integration ----------------------------------------------------


def test_a_view_depends_on_the_controls_it_declares(agent):
    turn = agent.send("trade the FOMC")
    fields = agent.dependencies.fields_for(turn.view.view_id)
    assert {"catalyst_date", "max_loss", "invalidation_condition"} <= fields


def test_changing_a_declared_field_regenerates_that_view(agent):
    turn = agent.send("trade the FOMC")
    original_id = turn.view.view_id

    refreshes = change(agent, "catalyst_date", "2026-09-17")
    assert len(refreshes) == 1
    assert refreshes[0].replaced_view_id == original_id
    assert refreshes[0].turn.view.view_id != original_id
    assert field_value(refreshes[0].turn.view, "catalyst_date") == "2026-09-17"
    assert "2026-09-17" in refreshes[0].turn.reply


def test_an_unrelated_field_regenerates_nothing(agent):
    agent.send("trade the FOMC")
    assert change(agent, "some_unrelated_field", "x") == []


def test_a_superseded_view_is_no_longer_tracked(agent):
    turn = agent.send("trade the FOMC")
    original_id = turn.view.view_id

    change(agent, "catalyst_date", "2026-09-17")
    assert agent.dependencies.producer(original_id) is None
    assert original_id not in agent.dependencies.live_view_ids()

    # The regenerated view is tracked in its place, so the next edit still lands.
    assert len(change(agent, "catalyst_date", "2026-09-18")) == 1


def test_every_live_view_fed_by_a_field_is_refreshed(agent):
    first = agent.send("trade the FOMC")
    second = agent.send("what if the Fed is hawkish?")
    assert first.view.view_id != second.view.view_id

    refreshed = {r.replaced_view_id for r in change(agent, "execution_buffer_days", 21)}
    assert refreshed == {first.view.view_id, second.view.view_id}


def test_implicit_dependencies_refresh_views_with_no_such_control(agent):
    """A trade preview reads max_loss without drawing a box for it."""
    strategy_id = "power_infrastructure:uranium_mining"
    agent.send("find strategies about nuclear power")
    agent.send("synthesize uranium mining")
    agent.send("open a thesis on this")
    chosen = next(c for c in agent.funnel.generate_implementations(strategy_id) if c.type.value != "NO_TRADE")
    agent.act(
        {"type": "select_implementation", "payload": {"strategy_id": strategy_id, "implementation_id": chosen.id}}
    )
    trade = agent.send("design a trade for it")
    assert trade.view is not None

    declared = {spec.field_id for spec in trade.view.declared_fields()}
    assert "max_loss" not in declared
    assert "max_loss" in agent.dependencies.fields_for(trade.view.view_id)

    refreshes = change(agent, "max_loss", 25_000)
    assert [r.replaced_view_id for r in refreshes] == [trade.view.view_id]


def test_an_entered_max_loss_reaches_the_drafted_intent(agent):
    strategy_id = "power_infrastructure:uranium_mining"
    agent.send("find strategies about nuclear power")
    agent.send("synthesize uranium mining")
    agent.send("open a thesis on this")
    chosen = next(c for c in agent.funnel.generate_implementations(strategy_id) if c.type.value != "NO_TRADE")
    agent.act(
        {"type": "select_implementation", "payload": {"strategy_id": strategy_id, "implementation_id": chosen.id}}
    )
    change(agent, "max_loss", 25_000)

    agent.send("design a trade for it")
    intent = agent.transactions.records()[-1].intent
    assert intent.max_loss == 25_000
