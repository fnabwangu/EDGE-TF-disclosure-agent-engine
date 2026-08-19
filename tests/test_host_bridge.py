"""The host transport: a remote interaction must reach EDGE's event handler."""

from datetime import date

import pytest
from starlette.testclient import TestClient

from api.app import TOKEN_ENV, app, set_bridge
from api.bridge import HostBridge, UnknownProject
from api.mcp import FORBIDDEN_OVER_HOST, MCPToolServer, TOOL_DESCRIPTORS
from console.demo.wiring import build_stack
from ui.state import UIEvent

TOKEN = "test-token"


@pytest.fixture()
def bridge(tmp_path, monkeypatch) -> HostBridge:
    monkeypatch.setenv(TOKEN_ENV, TOKEN)
    stack = build_stack(log_path=tmp_path / "events.jsonl")
    stack.workbench.create_project(project_id="fomc-jackson-hole", name="FOMC to Jackson Hole")
    instance = HostBridge(stack=stack, as_of=date(2026, 8, 18), simulation_dir=tmp_path / "sim")
    set_bridge(instance)
    return instance


@pytest.fixture()
def client(bridge) -> TestClient:
    return TestClient(app)


def auth(token: str = TOKEN) -> dict:
    return {"Authorization": f"Bearer {token}"}


# -- authorization ---------------------------------------------------------


def test_requests_without_a_token_are_refused(client):
    assert client.get("/projects").status_code == 401


def test_a_wrong_token_is_refused(client):
    assert client.get("/projects", headers=auth("nope")).status_code == 401


def test_the_surface_fails_closed_when_no_token_is_configured(bridge, monkeypatch):
    monkeypatch.delenv(TOKEN_ENV, raising=False)
    response = TestClient(app).get("/projects", headers=auth())
    assert response.status_code == 401
    assert "no EDGE_API_TOKEN" in response.json()["detail"]


def test_health_is_open_but_reveals_nothing(client, monkeypatch):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert set(body) == {"status", "auth_configured", "openai_configured"}


def test_health_never_contains_a_raw_key(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-must-not-appear-in-health")
    response = client.get("/health")
    assert "sk-must-not-appear-in-health" not in response.text


# -- the round trip that was missing ---------------------------------------


def test_a_remote_field_change_becomes_project_state(client):
    response = client.post(
        "/projects/fomc-jackson-hole/events",
        headers=auth(),
        json={
            "view_id": "app-block-1",
            "event_type": "FIELD_CHANGED",
            "field_id": "secondary_catalyst_date",
            "value": "2026-08-27",
        },
    )
    assert response.status_code == 200

    state = client.get("/projects/fomc-jackson-hole/state", headers=auth()).json()
    assert state["state"]["fields"]["secondary_catalyst_date"]["value"] == "2026-08-27"


def test_the_model_context_carries_the_entered_value(client):
    client.post(
        "/projects/fomc-jackson-hole/events",
        headers=auth(),
        json={
            "view_id": "app-block-1",
            "event_type": "FIELD_CHANGED",
            "field_id": "secondary_catalyst_date",
            "value": "2026-08-27",
        },
    )
    context = client.get("/projects/fomc-jackson-hole/state", headers=auth()).json()["context"]
    assert "ACTIVE PROJECT STATE" in context
    assert "secondary_catalyst_date = 2026-08-27" in context


def test_go_after_entering_a_date_needs_no_re_asking(client):
    """Enter Aug 27 in the component, then say 'go' - the date must already be known."""
    client.post(
        "/projects/fomc-jackson-hole/events",
        headers=auth(),
        json={
            "view_id": "app-block-1",
            "event_type": "FIELD_CHANGED",
            "field_id": "catalyst_date",
            "value": "2026-08-27",
        },
    )
    body = client.post(
        "/projects/fomc-jackson-hole/messages",
        headers=auth(),
        json={"message": "go - trade FOMC into Jackson Hole"},
    ).json()

    assert "2026-08-27" in body["reply"]
    assert body["view"]["state"]["catalyst_date"]["value"] == "2026-08-27"


def test_a_returned_view_is_hydrated_for_the_host_to_render(client):
    client.post(
        "/projects/fomc-jackson-hole/events",
        headers=auth(),
        json={
            "view_id": "app-block-1",
            "event_type": "FIELD_CHANGED",
            "field_id": "execution_buffer_days",
            "value": 21,
        },
    )
    body = client.post(
        "/projects/fomc-jackson-hole/messages", headers=auth(), json={"message": "trade the FOMC"}
    ).json()

    assert body["view"]["state"]["execution_buffer_days"]["value"] == 21
    declared = {f["field_id"] for c in body["view"]["components"] for f in c["fields"]}
    assert "catalyst_date" in declared


def test_a_remote_change_reports_which_views_it_invalidated(client):
    message = client.post(
        "/projects/fomc-jackson-hole/messages", headers=auth(), json={"message": "trade the FOMC"}
    ).json()
    view_id = message["view"]["view_id"]

    body = client.post(
        "/projects/fomc-jackson-hole/events",
        headers=auth(),
        json={
            "view_id": view_id,
            "event_type": "FIELD_CHANGED",
            "field_id": "catalyst_date",
            "value": "2026-09-17",
        },
    ).json()

    assert [r["replaced_view_id"] for r in body["refreshed"]] == [view_id]
    assert body["refreshed"][0]["view"]["state"]["catalyst_date"]["value"] == "2026-09-17"


def test_a_view_can_be_rehydrated_by_id(client):
    message = client.post(
        "/projects/fomc-jackson-hole/messages", headers=auth(), json={"message": "trade the FOMC"}
    ).json()
    view_id = message["view"]["view_id"]

    client.post(
        "/projects/fomc-jackson-hole/events",
        headers=auth(),
        json={
            "view_id": "elsewhere",
            "event_type": "FIELD_CHANGED",
            "field_id": "catalyst_date",
            "value": "2026-10-29",
        },
    )
    rehydrated = client.get(f"/projects/fomc-jackson-hole/views/{view_id}", headers=auth()).json()
    assert rehydrated["state"]["catalyst_date"]["value"] == "2026-10-29"


# -- transport robustness --------------------------------------------------


def test_redelivery_of_the_same_event_is_ignored(client):
    payload = {
        "event_id": "evt-1",
        "view_id": "app-block-1",
        "event_type": "FIELD_CHANGED",
        "field_id": "catalyst_date",
        "value": "2026-08-27",
    }
    client.post("/projects/fomc-jackson-hole/events", headers=auth(), json=payload)
    client.post("/projects/fomc-jackson-hole/events", headers=auth(), json=payload)

    field = client.get("/projects/fomc-jackson-hole/state", headers=auth()).json()["state"]["fields"]
    assert field["catalyst_date"]["revision"] == 1


def test_unknown_project_is_a_404(client):
    assert client.get("/projects/nope/state", headers=auth()).status_code == 404


def test_an_empty_message_is_rejected(client):
    response = client.post(
        "/projects/fomc-jackson-hole/messages", headers=auth(), json={"message": "   "}
    )
    assert response.status_code == 422


def test_the_bridge_refuses_an_unknown_project(bridge):
    with pytest.raises(UnknownProject):
        bridge.agent("does-not-exist")


# -- MCP surface -----------------------------------------------------------


def test_mcp_exposes_no_approval_or_execution_tool():
    names = {tool["name"] for tool in TOOL_DESCRIPTORS}
    assert not {n for n in names if any(bad in n for bad in FORBIDDEN_OVER_HOST)}
    assert "edge_record_ui_event" in names


def test_mcp_tool_call_writes_state(bridge):
    server = MCPToolServer(bridge)
    server.call(
        "edge_record_ui_event",
        {
            "project_id": "fomc-jackson-hole",
            "view_id": "app-block-1",
            "event_type": "FIELD_CHANGED",
            "field_id": "catalyst_date",
            "value": "2026-08-27",
        },
    )
    state = server.call("edge_get_project_state", {"project_id": "fomc-jackson-hole"})
    assert state["state"]["fields"]["catalyst_date"]["value"] == "2026-08-27"
    assert "catalyst_date = 2026-08-27" in state["context"]


def test_mcp_rejects_an_unknown_tool(bridge):
    with pytest.raises(KeyError):
        MCPToolServer(bridge).call("edge_execute_order", {})


def test_every_mcp_tool_declares_a_schema():
    for tool in TOOL_DESCRIPTORS:
        assert tool["input_schema"]["additionalProperties"] is False
        assert tool["description"]
