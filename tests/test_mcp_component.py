"""The MCP surface a chat host binds to, and the component it renders."""

import json
import re
from datetime import date

import pytest
from starlette.testclient import TestClient

from api.app import TOKEN_ENV, app, set_bridge
from api.bridge import HostBridge
from api.mcp import MCPToolServer
from api.mcp_rpc import (
    METHOD_NOT_FOUND,
    PROTOCOL_VERSION,
    WIDGET_MIME,
    WIDGET_URI,
    MCPJsonRpcServer,
    load_widget,
)
from console.demo.wiring import build_stack

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
def rpc(bridge) -> MCPJsonRpcServer:
    return MCPJsonRpcServer(MCPToolServer(bridge))


@pytest.fixture()
def client(bridge) -> TestClient:
    return TestClient(app)


def call(rpc: MCPJsonRpcServer, method: str, params=None, request_id: int = 1):
    return rpc.handle({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}})


# -- protocol --------------------------------------------------------------


def test_initialize_announces_tools_and_resources(rpc):
    result = call(rpc, "initialize")["result"]
    assert result["protocolVersion"] == PROTOCOL_VERSION
    assert "tools" in result["capabilities"] and "resources" in result["capabilities"]


def test_tools_list_uses_mcp_field_names(rpc):
    tools = call(rpc, "tools/list")["result"]["tools"]
    assert tools
    for tool in tools:
        assert set(tool) >= {"name", "description", "inputSchema"}


def test_widget_bearing_tools_declare_an_output_template(rpc):
    tools = {t["name"]: t for t in call(rpc, "tools/list")["result"]["tools"]}
    assert tools["edge_send_message"]["_meta"]["openai/outputTemplate"] == WIDGET_URI
    assert "_meta" not in tools["edge_list_projects"]


def test_unknown_method_is_a_json_rpc_error(rpc):
    error = call(rpc, "does/not/exist")["error"]
    assert error["code"] == METHOD_NOT_FOUND


def test_notifications_get_no_response(rpc):
    assert rpc.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_a_malformed_envelope_is_rejected(rpc):
    assert rpc.handle({"method": "tools/list"})["error"]["code"] == -32600


def test_a_failing_tool_does_not_kill_the_session(rpc):
    response = call(rpc, "tools/call", {"name": "edge_get_project_state", "arguments": {"project_id": "nope"}})
    assert "error" in response
    assert call(rpc, "tools/list")["result"]["tools"]


# -- the component ---------------------------------------------------------


def test_the_widget_is_served_as_an_mcp_resource(rpc):
    listed = call(rpc, "resources/list")["result"]["resources"]
    assert listed[0]["uri"] == WIDGET_URI
    assert listed[0]["mimeType"] == WIDGET_MIME

    contents = call(rpc, "resources/read", {"uri": WIDGET_URI})["result"]["contents"][0]
    assert contents["mimeType"] == WIDGET_MIME
    assert "<script>" in contents["text"]


def test_reading_an_unknown_resource_fails_cleanly(rpc):
    assert "error" in call(rpc, "resources/read", {"uri": "ui://widget/nope"})


def test_the_component_writes_changes_back_rather_than_holding_them():
    source = load_widget()
    assert "edge_record_ui_event" in source
    assert 'event_type: "FIELD_CHANGED"' in source
    # Controls are populated from persisted state, not from local memory.
    assert "function fieldValue" in source
    assert "view.state" in source
    assert "function adoptResult" in source
    assert "edge_component_action" in source
    assert "component.actions" in source


def test_the_component_handles_every_field_kind():
    source = load_widget()
    for kind in ("DATE", "NUMBER", "CHOICE"):
        assert kind in source


def test_the_component_is_served_over_http(client):
    response = client.get("/widget/edge-panel.html")
    assert response.status_code == 200
    assert "edge_record_ui_event" in response.text


# -- round trip through the RPC surface ------------------------------------


def test_a_component_field_change_persists_and_rehydrates(rpc):
    # The panel has to exist before it can be typed into.
    call(
        rpc,
        "tools/call",
        {
            "name": "edge_send_message",
            "arguments": {"project_id": "fomc-jackson-hole", "message": "trade FOMC into Jackson Hole"},
        },
    )
    call(
        rpc,
        "tools/call",
        {
            "name": "edge_record_ui_event",
            "arguments": {
                "project_id": "fomc-jackson-hole",
                "view_id": "chat-block-1",
                "event_type": "FIELD_CHANGED",
                "field_id": "catalyst_date",
                "value": "2026-08-27",
            },
        },
    )
    reply = call(
        rpc,
        "tools/call",
        {"name": "edge_send_message", "arguments": {"project_id": "fomc-jackson-hole", "message": "go"}},
    )["result"]

    assert "2026-08-27" in reply["content"][0]["text"]
    assert reply["structuredContent"]["view"]["state"]["catalyst_date"]["value"] == "2026-08-27"
    assert reply["_meta"]["openai/outputTemplate"] == WIDGET_URI


def test_a_field_change_without_refresh_keeps_the_current_view(rpc):
    created = call(
        rpc,
        "tools/call",
        {"name": "edge_create_project", "arguments": {"name": "Power infrastructure"}},
    )["result"]["structuredContent"]
    view = created["view"]
    result = call(
        rpc,
        "tools/call",
        {
            "name": "edge_record_ui_event",
            "arguments": {
                "project_id": created["project_id"],
                "view_id": view["view_id"],
                "event_type": "FIELD_CHANGED",
                "field_id": "strategy_query",
                "value": "Power infrastructure",
            },
        },
    )["result"]["structuredContent"]

    assert result["refreshed"] == []
    assert result["view"]["view_id"] == view["view_id"]
    assert result["view"]["state"]["strategy_query"]["value"] == "Power infrastructure"


def test_component_actions_drive_the_research_funnel_without_capital_tools(rpc):
    created = call(
        rpc,
        "tools/call",
        {"name": "edge_create_project", "arguments": {"name": "Power infrastructure"}},
    )["result"]["structuredContent"]
    project_id = created["project_id"]
    intake = created["view"]
    call(
        rpc,
        "tools/call",
        {
            "name": "edge_record_ui_event",
            "arguments": {
                "project_id": project_id,
                "view_id": intake["view_id"],
                "event_type": "FIELD_CHANGED",
                "field_id": "strategy_query",
                "value": "Power infrastructure",
            },
        },
    )
    generate = call(
        rpc,
        "tools/call",
        {
            "name": "edge_component_action",
            "arguments": {
                "project_id": project_id,
                "view_id": intake["view_id"],
                "type": "generate_strategies",
                "payload": {"query_field": "strategy_query"},
            },
        },
    )["result"]["structuredContent"]
    strategy_view = generate["view"]
    synth_action = next(
        action
        for component in strategy_view["components"]
        for action in component.get("actions", [])
        if action["type"] == "synthesize_disclosures"
    )
    synthesis = call(
        rpc,
        "tools/call",
        {"name": "edge_component_action", "arguments": {
            "project_id": project_id,
            "view_id": strategy_view["view_id"],
            "type": synth_action["type"],
            "payload": synth_action["payload"],
        }},
    )["result"]["structuredContent"]
    thesis_action = next(
        action
        for component in synthesis["view"]["components"]
        for action in component.get("actions", [])
        if action["type"] == "open_thesis"
    )
    thesis = call(
        rpc,
        "tools/call",
        {"name": "edge_component_action", "arguments": {
            "project_id": project_id,
            "view_id": synthesis["view"]["view_id"],
            "type": thesis_action["type"],
            "payload": thesis_action["payload"],
        }},
    )["result"]["structuredContent"]

    assert thesis["view"] is not None
    implementations = call(
        rpc,
        "tools/call",
        {"name": "edge_send_message", "arguments": {
            "project_id": project_id,
            "message": "compare implementations",
        }},
    )["result"]["structuredContent"]
    select_action = next(
        action
        for component in implementations["view"]["components"]
        for action in component.get("actions", [])
        if action["type"] == "select_implementation"
    )
    selected = call(
        rpc,
        "tools/call",
        {"name": "edge_component_action", "arguments": {
            "project_id": project_id,
            "view_id": implementations["view"]["view_id"],
            "type": select_action["type"],
            "payload": select_action["payload"],
        }},
    )["result"]["structuredContent"]

    assert selected["view"] is not None
    assert selected["state"]["project_id"] == project_id
    assert "edge_component_action" in {tool["name"] for tool in call(rpc, "tools/list")["result"]["tools"]}
    names = {tool["name"] for tool in call(rpc, "tools/list")["result"]["tools"]}
    assert not {name for name in names if re.search(r"approve|execute|submit_order|kill_switch", name)}


def test_a_date_with_no_named_event_says_so(rpc):
    call(
        rpc,
        "tools/call",
        {
            "name": "edge_record_ui_event",
            "arguments": {
                "project_id": "fomc-jackson-hole",
                "view_id": "chat-block-1",
                "event_type": "FIELD_CHANGED",
                "field_id": "catalyst_date",
                "value": "2026-08-27",
            },
        },
    )
    reply = call(
        rpc,
        "tools/call",
        {"name": "edge_send_message", "arguments": {"project_id": "fomc-jackson-hole", "message": "go"}},
    )["result"]
    assert "2026-08-27" in reply["content"][0]["text"]
    assert "no event named" in reply["content"][0]["text"]


def test_tool_results_carry_text_for_a_model_that_cannot_see_the_panel(rpc):
    result = call(rpc, "tools/call", {"name": "edge_list_projects", "arguments": {}})["result"]
    assert result["content"][0]["type"] == "text"
    assert isinstance(result["content"][0]["text"], str)


# -- transport -------------------------------------------------------------


def test_the_rpc_endpoint_requires_authorization(client):
    unauthorized = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert unauthorized.status_code == 401

    ok = client.post(
        "/mcp",
        headers={"Authorization": f"Bearer {TOKEN}"},
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )
    assert ok.status_code == 200
    assert ok.json()["result"]["tools"]


def test_batched_requests_are_supported(client):
    response = client.post(
        "/mcp",
        headers={"Authorization": f"Bearer {TOKEN}"},
        json=[
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 2, "method": "resources/list"},
        ],
    )
    assert [item["id"] for item in response.json()] == [1, 2]


def test_the_rpc_surface_exposes_no_execution_tool(rpc):
    names = {tool["name"] for tool in call(rpc, "tools/list")["result"]["tools"]}
    assert not {n for n in names if re.search(r"approve|execute|submit|kill", n)}


def test_the_rpc_surface_never_exposes_the_openai_key(rpc, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-must-not-leak-over-mcp")
    tools = json.dumps(call(rpc, "tools/list")["result"])
    resources = json.dumps(call(rpc, "resources/list")["result"])
    assert "sk-must-not-leak-over-mcp" not in tools
    assert "sk-must-not-leak-over-mcp" not in resources
