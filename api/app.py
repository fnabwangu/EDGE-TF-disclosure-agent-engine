"""
HTTP transport for the host bridge.

Path: api/app.py

Run with:
    EDGE_API_TOKEN=... python -m uvicorn api.app:app --port 8600

Built on Starlette, which is already present. Endpoints:

    GET  /health
    GET  /projects                              workspace overview
    GET  /projects/{project_id}/state           authoritative state + model context
    POST /projects/{project_id}/events          record a UI interaction
    POST /projects/{project_id}/messages        send a chat turn
    GET  /projects/{project_id}/views/{view_id} re-hydrate a previously issued view

Authorization is a bearer token from EDGE_API_TOKEN and fails closed: with no
token configured the surface refuses every request rather than running open.

There is deliberately no approval or execution route. A hosted chat surface is
not an authenticated operator.
"""

from __future__ import annotations

import os
from typing import Any, Callable, Dict

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from api.bridge import HostBridge, UnknownProject
from ui.state import UIEvent

TOKEN_ENV = "EDGE_API_TOKEN"

_bridge: HostBridge | None = None


def bridge() -> HostBridge:
    global _bridge
    if _bridge is None:
        _bridge = HostBridge()
    return _bridge


def set_bridge(instance: HostBridge) -> None:
    global _bridge
    _bridge = instance


def _authorized(request: Request) -> bool:
    expected = os.getenv(TOKEN_ENV, "")
    if not expected:
        return False
    header = request.headers.get("authorization", "")
    scheme, _, presented = header.partition(" ")
    return scheme.lower() == "bearer" and _constant_time_equal(presented, expected)


def _constant_time_equal(left: str, right: str) -> bool:
    import hmac

    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


def guarded(handler: Callable[[Request], Any]) -> Callable[[Request], Any]:
    async def wrapper(request: Request) -> JSONResponse:
        if not _authorized(request):
            reason = (
                "server has no EDGE_API_TOKEN configured"
                if not os.getenv(TOKEN_ENV, "")
                else "invalid bearer token"
            )
            return JSONResponse({"error": "UNAUTHORIZED", "detail": reason}, status_code=401)
        try:
            return await handler(request)
        except UnknownProject as exc:
            return JSONResponse({"error": "UNKNOWN_PROJECT", "detail": str(exc)}, status_code=404)
        except KeyError as exc:
            return JSONResponse({"error": "NOT_FOUND", "detail": str(exc)}, status_code=404)
        except ValueError as exc:
            return JSONResponse({"error": "INVALID_REQUEST", "detail": str(exc)}, status_code=422)

    return wrapper


async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "auth_configured": bool(os.getenv(TOKEN_ENV, ""))})


@guarded
async def projects(request: Request) -> JSONResponse:
    return JSONResponse(bridge().workspace())


@guarded
async def project_state(request: Request) -> JSONResponse:
    return JSONResponse(bridge().project_state(request.path_params["project_id"]))


@guarded
async def record_event(request: Request) -> JSONResponse:
    payload = await request.json()
    project_id = request.path_params["project_id"]
    payload.setdefault("project_id", project_id)
    event = UIEvent.model_validate(payload)
    return JSONResponse(bridge().record_event(project_id, event))


@guarded
async def send_message(request: Request) -> JSONResponse:
    payload = await request.json()
    message = payload.get("message")
    if not isinstance(message, str) or not message.strip():
        raise ValueError("message is required")
    return JSONResponse(bridge().send_message(request.path_params["project_id"], message))


@guarded
async def get_view(request: Request) -> JSONResponse:
    return JSONResponse(
        bridge().view(request.path_params["project_id"], request.path_params["view_id"])
    )


routes = [
    Route("/health", health, methods=["GET"]),
    Route("/projects", projects, methods=["GET"]),
    Route("/projects/{project_id}/state", project_state, methods=["GET"]),
    Route("/projects/{project_id}/events", record_event, methods=["POST"]),
    Route("/projects/{project_id}/messages", send_message, methods=["POST"]),
    Route("/projects/{project_id}/views/{view_id}", get_view, methods=["GET"]),
]

app = Starlette(routes=routes)


__all__ = ["TOKEN_ENV", "app", "bridge", "routes", "set_bridge"]
