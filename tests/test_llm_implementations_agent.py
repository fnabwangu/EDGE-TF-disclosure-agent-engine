"""Chat-level access to the model-proposed implementation path (Path B)."""

from datetime import date

import pytest

from console.demo.wiring import build_stack
from orchestration.agent import ChatAgent
from research.funnel import ResearchFunnel
from research.implementations import ImplementationType
from research.llm_implementations import LLMImplementationGenerator, ProposalSet, ProposedImplementation, ProposedInstrument

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


def test_asking_the_model_without_a_key_configured_explains_why(agent, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    past_thesis(agent)

    turn = agent.send("ask the model to propose implementations")
    assert "no openai key" in turn.reply.lower()
    assert agent.funnel.implementations(STRATEGY_ID) == []


def test_asking_the_model_requires_a_thesis_first(agent, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
    agent.send("find strategies about nuclear power")
    agent.send("synthesize uranium mining")

    turn = agent.send("ask gpt to propose implementations")
    assert "no thesis" in turn.reply.lower() or "open a thesis" in turn.reply.lower()


def test_model_proposals_still_pass_through_edges_gates(agent, monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
    past_thesis(agent)

    universe = sorted(
        {f.ticker for f in agent.funnel.candidate(STRATEGY_ID).signal_funds}
        | {f.ticker for f in agent.funnel.candidate(STRATEGY_ID).implementation_funds}
    )

    class FakeResponse:
        model = "gpt-4o-mock"
        id = "resp_1"

        @property
        def output_parsed(self):
            return ProposalSet(
                candidates=[
                    ProposedImplementation(
                        type=ImplementationType.ETF_LONG,
                        thesis_fit=0.8,
                        expected_return=0.05,
                        downside_risk=0.1,
                        liquidity_score=0.6,
                        instruments=[ProposedInstrument(ticker=universe[0])],
                        rationale="grounded in measured breadth",
                        risks=["market risk"],
                    ),
                    ProposedImplementation(
                        type=ImplementationType.SINGLE_NAME,
                        thesis_fit=0.9,
                        instruments=[ProposedInstrument(ticker="TOTALLY_INVENTED")],
                        rationale="an invented instrument",
                        risks=["x"],
                    ),
                ]
            )

    class FakeClient:
        class responses:
            @staticmethod
            def parse(**kwargs):
                return FakeResponse()

    agent.funnel.llm_implementation_generator = LLMImplementationGenerator(client=FakeClient())
    from audit.decision_records import DecisionRecorder

    agent.funnel.decision_recorder = DecisionRecorder(log_dir=tmp_path / "decisions")

    turn = agent.send("ask the model to propose implementations")
    assert "ETF_LONG" in turn.reply
    assert "rejected by EDGE" in turn.reply
    assert "TOTALLY_INVENTED" not in [
        i.ticker for c in agent.funnel.implementations(STRATEGY_ID) for i in c.instruments
    ]
    assert ImplementationType.NO_TRADE in {c.type for c in agent.funnel.implementations(STRATEGY_ID)}
