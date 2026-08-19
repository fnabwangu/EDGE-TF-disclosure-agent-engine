"""Tests for the generative UI contract and orchestration guardrails."""

import pytest

from approvals.schemas import ActionKind
from approvals.service import ApprovalService
from orchestration.guardrails import Capability, GuardrailViolation, ToolSpec, assert_model_safe
from tests.test_transaction_boundary import make_intent, make_service
from tests.test_workflow_approvals import make_request
from ui.registry import (
    UISchemaViolation,
    action_approval_panel,
    approval_inbox,
    approval_panel,
    component_catalog,
    continuity_panel,
    project_switcher,
    validate_view,
)
from ui.schemas import ActionType, ComponentType, GenerativeView, UIAction, UIComponent
from workbench.store import WorkbenchStore


@pytest.fixture()
def store(tmp_path) -> WorkbenchStore:
    store = WorkbenchStore(log_path=tmp_path / "events.jsonl")
    store.create_project(name="Nuclear power", project_id="proj-nuclear")
    return store


def _preview():
    service = make_service()
    service.register_draft(make_intent())
    return service.create_preview("intent-1", user_id="op-1", strategy_state="CONFIRMED_ADOPTION").preview


def _action_record(store):
    service = ApprovalService(workbench=store)
    service.register_executor(ActionKind.DATA_SOURCE_ONBOARDING, lambda req: {})
    service.propose(make_request())
    return service.submit_for_approval("req-1")


def test_deterministic_trade_approval_panel_validates():
    preview = _preview()
    view = GenerativeView(view_id="v1", title="Candidate implementation", components=[approval_panel(preview)])
    validate_view(view, authorized_hashes=[preview.intent_hash])


def test_deterministic_action_approval_panel_validates(store):
    record = _action_record(store)
    view = GenerativeView(view_id="v2", title="Onboarding", components=[action_approval_panel(record)])
    validate_view(view, authorized_hashes=[record.action_hash])


def test_model_cannot_forge_a_trade_approval_hash():
    preview = _preview()
    forged = approval_panel(preview)
    forged.data["intent_hash"] = "0" * 64

    with pytest.raises(UISchemaViolation):
        validate_view(
            GenerativeView(view_id="v3", title="Forged", components=[forged]),
            authorized_hashes=[preview.intent_hash],
        )


def test_model_cannot_forge_an_action_approval_hash(store):
    record = _action_record(store)
    forged = action_approval_panel(record)
    forged.data["action_hash"] = "0" * 64

    with pytest.raises(UISchemaViolation):
        validate_view(
            GenerativeView(view_id="v4", title="Forged", components=[forged]),
            authorized_hashes=[record.action_hash],
        )


def test_approval_action_must_bind_the_displayed_hash():
    preview = _preview()
    panel = approval_panel(preview)
    panel.actions = [UIAction(type=ActionType.REQUEST_APPROVAL, label="Approve", binds_intent_hash="deadbeef")]

    with pytest.raises(UISchemaViolation):
        validate_view(
            GenerativeView(view_id="v5", title="Mismatched", components=[panel]),
            authorized_hashes=[preview.intent_hash],
        )


def test_inbox_merges_trades_and_actions_and_checks_every_hash(store):
    preview = _preview()
    record = _action_record(store)
    inbox = approval_inbox(previews=[preview], actions=[record])

    assert inbox.data["count"] == 2
    validate_view(
        GenerativeView(view_id="v6", title="Inbox", components=[inbox]),
        authorized_hashes=[preview.intent_hash, record.action_hash],
    )

    with pytest.raises(UISchemaViolation):
        validate_view(
            GenerativeView(view_id="v7", title="Inbox", components=[inbox]),
            authorized_hashes=[preview.intent_hash],
        )


def test_project_switcher_and_continuity_panel_render(store):
    brief = store.open_session(project_id="proj-nuclear")
    view = GenerativeView(
        view_id="v8",
        title="Workspace",
        project_id="proj-nuclear",
        components=[project_switcher(store.workspace_brief()), continuity_panel(brief)],
    )
    validate_view(view)


def test_unpermitted_action_on_a_component_is_rejected():
    component = UIComponent(
        type=ComponentType.METRIC,
        title="IAV",
        data={"value": 0.71, "state": "EMERGING"},
        actions=[UIAction(type=ActionType.REQUEST_APPROVAL, label="Approve")],
    )
    with pytest.raises(UISchemaViolation):
        validate_view(GenerativeView(view_id="v9", title="Bad action", components=[component]))


def test_evidence_bearing_components_require_provenance():
    component = UIComponent(type=ComponentType.IAV_GAUGE, title="IAV", data={"value": 0.71, "state": "EMERGING"})
    with pytest.raises(UISchemaViolation):
        validate_view(GenerativeView(view_id="v10", title="No provenance", components=[component]))

    component.provenance = ["tool:calculate_iav"]
    validate_view(GenerativeView(view_id="v10", title="With provenance", components=[component]))


def test_missing_required_data_fields_are_rejected():
    component = UIComponent(type=ComponentType.TABLE, title="Holdings", data={"columns": ["ticker"]})
    with pytest.raises(UISchemaViolation):
        validate_view(GenerativeView(view_id="v11", title="Incomplete table", components=[component]))


def test_catalog_marks_approval_surfaces_as_not_model_authorable():
    catalog = component_catalog()
    assert catalog["approval_panel"]["model_authorable"] is False
    assert catalog["action_approval_panel"]["model_authorable"] is False
    assert catalog["approval_inbox"]["model_authorable"] is False
    assert catalog["signal_card"]["model_authorable"] is True
    assert catalog["project_switcher"]["model_authorable"] is True


def test_guardrails_reject_execute_capability():
    with pytest.raises(GuardrailViolation):
        assert_model_safe([ToolSpec("send_it", "", Capability.EXECUTE, lambda: None)])


def test_guardrails_reject_forbidden_tool_names():
    with pytest.raises(GuardrailViolation):
        assert_model_safe([ToolSpec("place_trade", "", Capability.DRAFT, lambda: None)])


def test_registry_exposes_no_approval_or_execution_tool(store):
    from orchestration.tool_registry import build_tools

    approvals = ApprovalService(workbench=store)
    tools = build_tools(
        transactions=make_service(),
        approvals=approvals,
        workbench=store,
        project_id="proj-nuclear",
        session_id="s1",
        user_id="op-1",
    )
    names = {t.name for t in tools}
    assert not names & {"approve", "execute", "approve_action", "submit_order"}
    assert {"draft_trade_intent", "request_preview", "propose_action", "get_approval_inbox"} <= names


def test_tools_are_bound_to_one_project(store):
    from orchestration.tool_registry import build_tools

    store.create_project(name="Semiconductors", project_id="proj-semis")
    tools = {
        t.name: t
        for t in build_tools(
            transactions=make_service(),
            approvals=ApprovalService(workbench=store),
            workbench=store,
            project_id="proj-nuclear",
            session_id="s1",
            user_id="op-1",
        )
    }
    tools["create_thesis"].handler(title="Nuclear adoption", claim="Managers are accumulating.")

    assert tools["get_current_project"].handler()["project_id"] == "proj-nuclear"
    assert len(tools["list_theses"].handler()) == 1
    assert set(store.projection(project_id="proj-semis").theses) == set()
    assert len(tools["get_workspace_overview"].handler()["brief"]["projects"]) == 2
