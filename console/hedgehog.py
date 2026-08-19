"""
HedgeHog console - chat-first operator surface.

Path: console/hedgehog.py

Run with:
    python -m streamlit run console/hedgehog.py

The conversation drives the funnel:

    strategy generation -> ETF disclosure synthesis -> thesis
        -> trade design -> approval -> execution

Views are generated per turn from the deterministic engines. Buttons inside a
view route back through the same agent handlers as typed messages, so a click
is just a pre-parsed sentence. The broker is dry-run.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional

import streamlit as st

from approvals.schemas import ApprovalState
from approvals.service import ApprovalError
from console.components.generative_view import render_component, render_view
from console.demo.wiring import build_stack, seed
from orchestration.agent import ChatAgent
from orchestration.llm import build_language_model, model_status, resolve_config
from orchestration.ui_composer import funnel_rail
from research.funnel import ResearchFunnel
from transactions.schemas import TransactionState
from ui.registry import action_approval_panel, approval_panel, project_switcher, validate_view
from ui.schemas import ActionType

st.set_page_config(page_title="HedgeHog - EDGE-TF", layout="wide")

OPENING = (
    "I work the funnel in order: **generate strategies**, **synthesize ETF disclosures**, "
    "**open a thesis**, then **design a trade**. Try *find strategies about nuclear power*, "
    "or name a dated macro event like *trade FOMC to Jackson Hole* and I will route it as a catalyst."
)


def boot() -> None:
    if "stack" in st.session_state:
        return
    st.session_state.stack = seed(build_stack())
    st.session_state.project_id = "proj-nuclear"
    st.session_state.operator = "op-2"
    st.session_state.funnels = {}
    st.session_state.agents = {}
    st.session_state.transcripts = {}
    open_project(st.session_state.project_id)


def open_project(project_id: str) -> None:
    stack = st.session_state.stack
    brief = stack.workbench.open_session(project_id=project_id, actor=st.session_state.operator)
    st.session_state.project_id = project_id
    st.session_state.brief = brief

    funnel = st.session_state.funnels.get(project_id)
    if funnel is None:
        funnel = ResearchFunnel(as_of=date(2026, 8, 18), storage_dir="data/simulated")
        st.session_state.funnels[project_id] = funnel

    st.session_state.agents[project_id] = ChatAgent(
        funnel=funnel,
        workbench=stack.workbench,
        transactions=stack.transactions,
        approvals=stack.approvals,
        project_id=project_id,
        session_id=brief.session_id,
        user_id=st.session_state.operator,
        model=build_language_model(),
    )
    st.session_state.transcripts.setdefault(project_id, [])


def authorized_hashes() -> set:
    stack = st.session_state.stack
    hashes = {r.preview.intent_hash for r in stack.transactions.records() if r.preview}
    hashes |= {r.action_hash for r in stack.approvals._records.values() if r.action_hash}
    return hashes


def handle(action: Optional[Dict[str, Any]]) -> None:
    """Route a clicked action: research actions to the agent, decisions to the services."""
    if not action:
        return
    stack = st.session_state.stack
    agent: ChatAgent = st.session_state.agents[st.session_state.project_id]
    kind = action["type"]
    payload = action.get("payload", {})

    if kind == "ui_event":
        # The UI is not the source of truth: persist first, then regenerate.
        turn = agent.record_ui_event(action["event"])
        if turn is not None:
            transcript().append(("assistant", turn.reply, turn.view))
        st.rerun()

    if kind == ActionType.SWITCH_PROJECT.value:
        open_project(payload["project_id"])
        st.rerun()

    if kind == ActionType.REQUEST_APPROVAL.value:
        _decide(action, payload)
        st.rerun()

    if kind == ActionType.CANCEL_ACTION.value:
        stack.approvals.cancel(payload["request_id"], reason="Rejected in console")
        st.rerun()

    if kind == ActionType.REJECT_INTENT.value:
        stack.transactions.cancel(payload["intent_id"], reason="Rejected in console")
        st.rerun()

    turn = agent.act(action)
    if turn is not None:
        transcript().append(("assistant", turn.reply, turn.view))
        st.rerun()


def _decide(action: Dict[str, Any], payload: Dict[str, Any]) -> None:
    stack = st.session_state.stack
    operator = st.session_state.operator

    if action.get("binds_intent_hash"):
        record = stack.transactions.approve(
            payload["intent_id"], intent_hash=action["binds_intent_hash"], approver_id=operator
        )
        if record.state is TransactionState.APPROVED:
            result = stack.transactions.execute(payload["intent_id"], user_id=operator)
            _flash(result.state.value, f"Order {result.state.value}: {result.broker_response}")
        else:
            _flash(record.state.value, f"Approval refused: {record.state.value}")
        return

    try:
        record = stack.approvals.approve(
            payload["request_id"], action_hash=action["binds_action_hash"], approver_id=operator
        )
    except ApprovalError as exc:
        st.session_state.flash = ("error", str(exc))
        return
    if record.state is ApprovalState.APPROVED:
        record = stack.approvals.execute(payload["request_id"], actor=operator)
    _flash(record.state.value, f"{payload['request_id']} -> {record.state.value}")


def _flash(state: str, message: str) -> None:
    good = state in {"SUBMITTED", "EXECUTED", "APPROVED"}
    st.session_state.flash = ("success" if good else "warning", message)


def transcript() -> list:
    return st.session_state.transcripts[st.session_state.project_id]


boot()
stack = st.session_state.stack
brief = st.session_state.brief
agent: ChatAgent = st.session_state.agents[st.session_state.project_id]
funnel: ResearchFunnel = st.session_state.funnels[st.session_state.project_id]

# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.title("HedgeHog")
    st.caption("EDGE-TF interaction layer - dry-run broker")
    if resolve_config():
        st.success(f"Router: {model_status()}")
    else:
        st.info(f"Router: {model_status()}")
        st.caption("Set OPENAI_API_KEY or ANTHROPIC_API_KEY to route with a model.")
    operator = st.selectbox("Acting as", ["op-1", "op-2", "op-3", "EDGE_TF"], index=1)
    if operator != st.session_state.operator:
        st.session_state.operator = operator
        agent.user_id = operator

    handle(render_component(project_switcher(stack.workbench.workspace_brief()), key="switcher"))

    st.divider()
    st.caption("Simulated adoption regime")
    regime = st.radio(
        "regime", ["BROAD_ADOPTION", "NARROW_ADOPTION", "DISTRIBUTION"], label_visibility="collapsed"
    )
    if regime != funnel.regime:
        funnel.regime = regime
        funnel._synthesis.clear()
        st.caption("Cleared synthesis cache - re-synthesize to see the change.")

    st.divider()
    st.caption(f"Session `{brief.session_id[:8]}` / {len(stack.workbench.events())} events")
    if st.button("Verify audit chain", use_container_width=True):
        st.success("Chain intact") if stack.workbench.verify_chain() else st.error("Tampered")
    if st.button("Simulate IAV collapse", use_container_width=True):
        stack.workbench.evaluate_watch_conditions(
            {"iav": 0.05}, project_id=st.session_state.project_id, session_id=brief.session_id
        )
        open_project(st.session_state.project_id)
        st.rerun()
    if st.button("Reset demo", use_container_width=True):
        st.session_state.clear()
        st.rerun()

if flash := st.session_state.pop("flash", None):
    getattr(st, flash[0])(flash[1])

# ------------------------------------------------------------ pipeline rail
render_component(funnel_rail(funnel.board()), key="rail")

chat_column, decision_column = st.columns([3, 2])

# ------------------------------------------------------------------- chat
with chat_column:
    st.subheader(brief.project.name if brief.project else st.session_state.project_id)
    if not transcript():
        with st.chat_message("assistant"):
            st.markdown(OPENING)

    for index, (role, content, view) in enumerate(transcript()):
        with st.chat_message(role):
            st.markdown(content)
            if view is not None:
                validate_view(view, authorized_hashes=authorized_hashes())
                handle(render_view(view, key_prefix=f"t{index}-"))

    if prompt := st.chat_input("Ask about a theme, or tell me what to do next"):
        transcript().append(("user", prompt, None))
        turn = agent.send(prompt)
        transcript().append(("assistant", turn.reply, turn.view))
        st.rerun()

# --------------------------------------------------------------- decisions
with decision_column:
    st.subheader("Waiting on you")
    pending_actions = stack.approvals.pending(project_id=st.session_state.project_id)
    pending_trades = [
        r.preview
        for r in stack.transactions.records()
        if r.preview is not None and r.state is TransactionState.AWAITING_APPROVAL
    ]
    if not pending_actions and not pending_trades:
        st.caption("Queue is empty.")
    for preview in pending_trades:
        handle(render_component(approval_panel(preview), key=f"tp-{preview.intent_id}"))
    for record in pending_actions:
        handle(
            render_component(
                action_approval_panel(record, policy=stack.approvals.policy), key=f"ap-{record.request_id}"
            )
        )

    with st.expander("Continuity from earlier sessions"):
        for thesis in brief.active_theses:
            st.write(f"`{thesis.state.value}` {thesis.title}")
        if brief.breached_conditions:
            st.warning(f"{len(brief.breached_conditions)} watch condition(s) breached")
        if brief.unresolved_questions:
            st.info("; ".join(brief.unresolved_questions))
