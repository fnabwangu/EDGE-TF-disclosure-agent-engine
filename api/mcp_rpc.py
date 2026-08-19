"""
JSON-RPC surface for MCP clients.

Path: api/mcp_rpc.py

Wraps `MCPToolServer` in the JSON-RPC 2.0 envelope MCP clients speak, and
serves the widget as an MCP resource so a chat host can render it and call
back into EDGE.

Methods: initialize, tools/list, tools/call, resources/list, resources/read.

Note on host specifics: the JSON-RPC method names and the resource shape follow
the MCP spec. The `_meta["openai/outputTemplate"]` binding that associates a
tool with an inline widget is Apps-SDK-specific and is the one part worth
re-checking against current host documentation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from api.mcp import TOOL_DESCRIPTORS, MCPToolServer

PROTOCOL_VERSION = "2025-06-18"
WIDGET_URI = "ui://edge/index.html"
WIDGET_MIME = "text/html+skybridge"
WIDGET_PATH = Path(__file__).resolve().parent.parent / "web" / "index.html"

# Tools whose result should render as the interactive panel rather than text.
WIDGET_TOOLS = {"edge_send_message", "edge_get_view", "edge_record_ui_event", "edge_component_action", "edge_create_project"}

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


def load_widget() -> str:
    return WIDGET_PATH.read_text(encoding="utf-8")


def _descriptor(tool: Dict[str, Any]) -> Dict[str, Any]:
    descriptor = {
        "name": tool["name"],
        "description": tool["description"],
        "inputSchema": tool["input_schema"],
    }
    if tool["name"] in WIDGET_TOOLS:
        descriptor["_meta"] = {"openai/outputTemplate": WIDGET_URI}
    return descriptor


class MCPJsonRpcServer:
    def __init__(self, tools: MCPToolServer):
        self.tools = tools

    def handle(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if message.get("jsonrpc") != "2.0" or "method" not in message:
            return self._error(message.get("id"), INVALID_REQUEST, "not a JSON-RPC 2.0 request")

        method = message["method"]
        params = message.get("params") or {}
        request_id = message.get("id")

        # Notifications carry no id and expect no response.
        if request_id is None and method.startswith("notifications/"):
            return None

        try:
            handler = {
                "initialize": self._initialize,
                "tools/list": self._tools_list,
                "tools/call": self._tools_call,
                "resources/list": self._resources_list,
                "resources/read": self._resources_read,
                "ping": lambda **_: {},
            }.get(method)
            if handler is None:
                return self._error(request_id, METHOD_NOT_FOUND, f"unknown method {method}")
            return {"jsonrpc": "2.0", "id": request_id, "result": handler(**params)}
        except TypeError as exc:
            return self._error(request_id, INVALID_PARAMS, str(exc))
        except KeyError as exc:
            return self._error(request_id, INVALID_PARAMS, f"not found: {exc}")
        except Exception as exc:  # a tool failure must not kill the session
            return self._error(request_id, INTERNAL_ERROR, str(exc))

    # -- methods -----------------------------------------------------------

    def _initialize(self, **_: Any) -> Dict[str, Any]:
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}, "resources": {"listChanged": False}},
            "serverInfo": {"name": "edge-tf", "version": "0.1.0"},
        }

    def _tools_list(self, **_: Any) -> Dict[str, Any]:
        return {"tools": [_descriptor(tool) for tool in TOOL_DESCRIPTORS]}

    def _tools_call(self, name: str, arguments: Optional[Dict[str, Any]] = None, **_: Any) -> Dict[str, Any]:
        result = self.tools.call(name, arguments or {})
        return {
            "content": [{"type": "text", "text": _summarize(name, result)}],
            "structuredContent": result,
            "_meta": {"openai/outputTemplate": WIDGET_URI} if name in WIDGET_TOOLS else {},
            "isError": False,
        }

    def _resources_list(self, **_: Any) -> Dict[str, Any]:
        return {
            "resources": [
                {
                    "uri": WIDGET_URI,
                    "name": "EDGE strategy workspace",
                    "description": "Renders an EDGE generative view and writes interactions back.",
                    "mimeType": WIDGET_MIME,
                    "_meta": {
                        "openai/widgetCSP": {
                            "connect_domains": [],
                            "resource_domains": [],
                        }
                    },
                }
            ]
        }

    def _resources_read(self, uri: str, **_: Any) -> Dict[str, Any]:
        if uri != WIDGET_URI:
            raise KeyError(uri)
        return {"contents": [{"uri": uri, "mimeType": WIDGET_MIME, "text": load_widget()}]}

    @staticmethod
    def _error(request_id: Any, code: int, message: str) -> Dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _summarize(name: str, result: Dict[str, Any]) -> str:
    """Text a model reads when it cannot see the rendered panel."""
    if "reply" in result:
        return result["reply"]
    if "context" in result:
        return result["context"]
    if name == "edge_list_projects":
        projects = result.get("workspace", {}).get("projects", [])
        return "\n".join(
            f"{p['name']}: {p['pending_approval_count']} awaiting approval" for p in projects
        ) or "No projects."
    return json.dumps(result)[:2000]


__all__ = [
    "MCPJsonRpcServer",
    "PROTOCOL_VERSION",
    "WIDGET_MIME",
    "WIDGET_URI",
    "load_widget",
]
