"""
MCP tool surface for the host bridge.

Path: api/mcp.py

The ChatGPT Apps SDK binds an app to MCP tools. These descriptors map those
tool calls onto the same bridge the HTTP transport uses, so a component
rendered inside a chat host can write an interaction back into EDGE.

The tool list mirrors the guardrails already enforced in
`orchestration/guardrails.py`: read state, record interactions, send messages.
Nothing here can approve or execute.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List

from api.bridge import HostBridge
from orchestration.guardrails import Capability
from ui.state import Persistence, UIEvent, UIEventType

TOOL_DESCRIPTORS: List[Dict[str, Any]] = [
    {
        "name": "edge_list_projects",
        "capability": Capability.READ.value,
        "description": "List EDGE projects and what each is waiting on.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "edge_get_project_state",
        "capability": Capability.READ.value,
        "description": (
            "Authoritative project state, including every value the user has entered. "
            "Call this before reasoning about dates or assumptions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"project_id": {"type": "string"}},
            "required": ["project_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "edge_record_ui_event",
        "capability": Capability.DRAFT.value,
        "description": (
            "Persist an interaction from a rendered component. A field change becomes "
            "authoritative project state and survives the component being replaced."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "view_id": {"type": "string"},
                "event_type": {
                    "type": "string",
                    "enum": [e.value for e in UIEventType],
                },
                "field_id": {"type": "string"},
                "value": {},
                "action": {"type": "string"},
                "persistence": {"type": "string", "enum": [p.value for p in Persistence]},
                "event_id": {
                    "type": "string",
                    "description": "Stable id; redelivery with the same id is ignored.",
                },
            },
            "required": ["project_id", "view_id", "event_type"],
            "additionalProperties": False,
        },
    },
    {
        "name": "edge_send_message",
        "capability": Capability.COMPUTE.value,
        "description": (
            "Send a turn to the EDGE agent and receive a reply plus a renderable view, "
            "hydrated from current project state."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"project_id": {"type": "string"}, "message": {"type": "string"}},
            "required": ["project_id", "message"],
            "additionalProperties": False,
        },
    },
    {
        "name": "edge_get_view",
        "capability": Capability.READ.value,
        "description": "Re-hydrate a previously issued view against current project state.",
        "input_schema": {
            "type": "object",
            "properties": {"project_id": {"type": "string"}, "view_id": {"type": "string"}},
            "required": ["project_id", "view_id"],
            "additionalProperties": False,
        },
    },
]

FORBIDDEN_OVER_HOST = {"approve", "execute", "submit_order", "reset_kill_switch", "cancel_order"}


class MCPToolServer:
    """Dispatches MCP tool calls onto the bridge."""

    def __init__(self, bridge: HostBridge):
        self.bridge = bridge
        self._handlers: Dict[str, Callable[..., Any]] = {
            "edge_list_projects": self._list_projects,
            "edge_get_project_state": self._get_project_state,
            "edge_record_ui_event": self._record_ui_event,
            "edge_send_message": self._send_message,
            "edge_get_view": self._get_view,
        }

    def list_tools(self) -> List[Dict[str, Any]]:
        return TOOL_DESCRIPTORS

    def call(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        handler = self._handlers.get(name)
        if handler is None:
            raise KeyError(f"unknown tool {name}")
        return handler(**arguments)

    # -- handlers ----------------------------------------------------------

    def _list_projects(self) -> Dict[str, Any]:
        return self.bridge.workspace()

    def _get_project_state(self, project_id: str) -> Dict[str, Any]:
        return self.bridge.project_state(project_id)

    def _record_ui_event(self, project_id: str, **payload: Any) -> Dict[str, Any]:
        event = UIEvent.model_validate({"project_id": project_id, **payload})
        return self.bridge.record_event(project_id, event)

    def _send_message(self, project_id: str, message: str) -> Dict[str, Any]:
        return self.bridge.send_message(project_id, message)

    def _get_view(self, project_id: str, view_id: str) -> Dict[str, Any]:
        return {"view": self.bridge.view(project_id, view_id)}


__all__ = ["FORBIDDEN_OVER_HOST", "MCPToolServer", "TOOL_DESCRIPTORS"]
