"""Generative UI state continuity: UI event -> project state -> model context -> hydrated view."""

import tempfile
from datetime import date

import pytest

from console.demo.wiring import build_stack
from orchestration.agent import ChatAgent
from research.funnel import ResearchFunnel
from ui.hydration import as_values, field_value, hydrate, missing_required
from ui.state import Persistence, ProjectStateSnapshot, UIEvent, UIEventType, UIFieldState
from workbench.store import WorkbenchStore


@pytest.fixture()
def stack(tmp_path):
    stack = build_stack(log_path=tmp_path / "events.jsonl")
    stack.workbench.create_project(project_id="fomc-jackson-hole", name="FOMC to Jackson Hole")
    return stack


@pytest.fixture()
def agent(stack, tmp_path) -> ChatAgent:
    brief = stack.workbench.open_session(project_id="fomc-jackson-hole")
    return ChatAgent(
        funnel=ResearchFunnel(as_of=date(2026, 8, 18), storage_dir=tmp_path / "sim"),
        workbench=stack.workbench,
        transactions=stack.transactions,
        approvals=stack.approvals,
        project_id="fomc-jackson-hole",
        session_id=brief.session_id,
        user_id="op-1",
    )


def change(agent: ChatAgent, field_id: str, value, *, persistence=Persistence.PROJECT) -> None:
    agent.record_ui_event(
        UIEvent.field_changed(
            view_id="v-test",
            project_id=agent.project_id,
            session_id=agent.session_id,
            field_id=field_id,
            value=value,
            persistence=persistence,
        )
    )


# -- persistence -----------------------------------------------------------


def test_an_entered_value_becomes_authoritative_project_state(agent):
    change(agent, "jackson_hole_date", "2026-08-27")
    assert agent.project_state().value("jackson_hole_date") == "2026-08-27"


def test_entered_values_survive_a_rebuilt_store(stack, agent):
    change(agent, "jackson_hole_date", "2026-08-27")
    reopened = WorkbenchStore(log_path=stack.workbench.log_path)
    assert reopened.project_state("fomc-jackson-hole").value("jackson_hole_date") == "2026-08-27"


def test_edits_are_revisioned_rather_than_overwritten(agent, stack):
    change(agent, "catalyst_date", "2026-08-19")
    change(agent, "catalyst_date", "2026-08-27")

    field = agent.project_state().fields["catalyst_date"]
    assert field.value == "2026-08-27"
    assert field.revision == 2

    history = [
        e.payload["value"]
        for e in stack.workbench.events(project_id="fomc-jackson-hole")
        if e.payload.get("field_id") == "catalyst_date"
    ]
    assert history == ["2026-08-19", "2026-08-27"]


def test_state_survives_twenty_intervening_messages(agent):
    change(agent, "jackson_hole_date", "2026-08-27")
    for _ in range(20):
        agent.send("what can you do")
    assert agent.project_state().value("jackson_hole_date") == "2026-08-27"


def test_state_survives_a_new_session(stack, agent):
    change(agent, "jackson_hole_date", "2026-08-27")
    later = stack.workbench.open_session(project_id="fomc-jackson-hole")
    snapshot = stack.workbench.project_state("fomc-jackson-hole", session_id=later.session_id)
    assert snapshot.value("jackson_hole_date") == "2026-08-27"


def test_session_scoped_values_do_not_leak_between_sessions(stack, agent):
    change(agent, "expanded_panel", "evidence", persistence=Persistence.SESSION)
    change(agent, "catalyst_date", "2026-08-27")

    later = stack.workbench.open_session(project_id="fomc-jackson-hole")
    snapshot = stack.workbench.project_state("fomc-jackson-hole", session_id=later.session_id)
    assert snapshot.value("expanded_panel") is None
    assert snapshot.value("catalyst_date") == "2026-08-27"


def test_project_state_is_isolated_per_project(stack, agent):
    stack.workbench.create_project(project_id="other", name="Other")
    change(agent, "catalyst_date", "2026-08-27")
    assert stack.workbench.project_state("other").value("catalyst_date") is None


def test_non_field_interactions_are_recorded_without_becoming_state(stack, agent):
    agent.record_ui_event(
        UIEvent(
            view_id="v-test",
            project_id="fomc-jackson-hole",
            event_type=UIEventType.DISMISSED,
            action="reject_intent",
        )
    )
    assert agent.project_state().fields == {}
    kinds = [e.kind.value for e in stack.workbench.events(project_id="fomc-jackson-hole")]
    assert "UI_INTERACTION" in kinds


# -- model visibility ------------------------------------------------------


def test_entered_values_reach_the_model_context(agent):
    change(agent, "catalyst_date", "2026-08-19")
    change(agent, "secondary_catalyst_date", "2026-08-27")

    context = agent.state_context()
    assert "ACTIVE PROJECT STATE" in context
    assert "catalyst_date = 2026-08-19" in context
    assert "secondary_catalyst_date = 2026-08-27" in context


def test_context_carries_project_identity_and_open_work(agent):
    context = agent.state_context()
    assert "FOMC to Jackson Hole" in context


# -- hydration -------------------------------------------------------------


def test_regenerated_views_are_hydrated_not_blank(agent):
    change(agent, "catalyst_date", "2026-08-19")
    change(agent, "secondary_catalyst_date", "2026-08-27")

    turn = agent.send("trade FOMC into Jackson Hole")
    assert turn.view is not None
    assert field_value(turn.view, "secondary_catalyst_date") == "2026-08-27"
    assert "2026-08-27" in turn.reply


def test_the_position_must_survive_the_last_dated_event(agent):
    change(agent, "catalyst_date", "2026-08-19")
    change(agent, "secondary_catalyst_date", "2026-08-27")
    change(agent, "execution_buffer_days", 14)

    agent.send("trade FOMC into Jackson Hole")
    strategy = next(iter(agent.catalysts.values()))
    assert strategy.catalyst_date == date(2026, 8, 27)
    assert strategy.minimum_expiration() > date(2026, 9, 10)


def test_missing_required_fields_are_reportable(agent):
    turn = agent.send("trade the FOMC")
    missing = {spec.field_id for spec in missing_required(turn.view)}
    assert "catalyst_date" in missing

    change(agent, "catalyst_date", "2026-09-17")
    turn = agent.send("trade the FOMC")
    assert "catalyst_date" not in {spec.field_id for spec in missing_required(turn.view)}


def test_hydration_fills_declared_controls_from_a_snapshot():
    from ui.schemas import ComponentType, GenerativeView, UIComponent
    from ui.state import FieldSpec

    view = GenerativeView(
        view_id="v1",
        title="t",
        components=[
            UIComponent(
                type=ComponentType.RISK_BUDGET_PANEL,
                title="Requirements",
                data={"budgets": []},
                fields=[FieldSpec(field_id="catalyst_date", label="Catalyst date")],
            )
        ],
    )
    snapshot = ProjectStateSnapshot(
        project_id="p",
        fields={"catalyst_date": UIFieldState(field_id="catalyst_date", value="2026-08-27")},
    )

    hydrate(view, snapshot)
    assert as_values(view) == {"catalyst_date": "2026-08-27"}
