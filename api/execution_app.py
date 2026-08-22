"""
HTTP transport for the external execution boundary.

Path: api/execution_app.py

Run with:
    EDGE_EXECUTION_TOKEN=... python -m uvicorn api.execution_app:app --port 8601

This is the machine-facing half of the decision engine, served as a separate
Starlette app from api/app.py on purpose: the hosted chat surface is not an
authenticated operator, and the execution service is not a chat user. Each
gets its own process, its own port, and its own bearer token.

Endpoints (all fail closed without EDGE_EXECUTION_TOKEN):

    GET  /health
    GET  /execution/orders                        approved trades as structured instructions
    POST /execution/orders/{trade_id}/claim       atomic handoff; body: {"executor_id": ...}
    POST /execution/orders/{trade_id}/reports     broker outcome; body: ExecutionReport
    POST /execution/portfolio/snapshots           balances/positions; body: BrokerAccountSnapshot
    GET  /execution/portfolio/state               latest known broker state + open trades

Broker credentials never touch this process. The executor authenticates to
Schwab (or any other broker) on its own side of the wire.
"""

from __future__ import annotations

import os
from typing import Any, Callable, Optional

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from core.env import ensure_env_loaded
from execution.contracts import BrokerAccountSnapshot, ExecutionReport
from execution.gateway import ExecutionGateway, ExecutionGatewayError

TOKEN_ENV = "EDGE_EXECUTION_TOKEN"

ensure_env_loaded()

_gateway: Optional[ExecutionGateway] = None


def gateway() -> ExecutionGateway:
    """Lazy default wiring for development; production injects via set_gateway."""
    global _gateway
    if _gateway is None:
        from console.demo.wiring import build_stack

        stack = build_stack(fresh=False)
        _gateway = ExecutionGateway(
            transactions=stack.transactions,
            kill_switch=stack.kill_switch,
        )
    return _gateway


def set_gateway(instance: ExecutionGateway) -> None:
    global _gateway
    _gateway = instance


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
                f"server has no {TOKEN_ENV} configured"
                if not os.getenv(TOKEN_ENV, "")
                else "invalid bearer token"
            )
            return JSONResponse({"error": "UNAUTHORIZED", "detail": reason}, status_code=401)
        try:
            return await handler(request)
        except ExecutionGatewayError as exc:
            status = 404 if exc.code == "UNKNOWN_TRADE" else 409
            return JSONResponse({"error": exc.code, "detail": str(exc)}, status_code=status)
        except ValueError as exc:
            return JSONResponse({"error": "INVALID_REQUEST", "detail": str(exc)}, status_code=422)

    return wrapper


async def health(request: Request) -> JSONResponse:
    return JSONResponse(
        {
            "status": "ok",
            "auth_configured": bool(os.getenv(TOKEN_ENV, "")),
            "service": "edge-execution-gateway",
        }
    )


@guarded
async def list_orders(request: Request) -> JSONResponse:
    instructions = gateway().list_instructions()
    return JSONResponse({"orders": [i.model_dump(mode="json") for i in instructions]})


@guarded
async def claim_order(request: Request) -> JSONResponse:
    payload = await request.json()
    executor_id = payload.get("executor_id")
    if not isinstance(executor_id, str) or not executor_id.strip():
        raise ValueError("executor_id is required")
    instruction = gateway().claim(request.path_params["trade_id"], executor_id=executor_id)
    return JSONResponse(instruction.model_dump(mode="json"))


@guarded
async def report_execution(request: Request) -> JSONResponse:
    payload = await request.json()
    payload.setdefault("trade_id", request.path_params["trade_id"])
    if payload["trade_id"] != request.path_params["trade_id"]:
        raise ValueError("trade_id in body must match the path")
    report = ExecutionReport.model_validate(payload)
    return JSONResponse(gateway().report(report))


@guarded
async def post_snapshot(request: Request) -> JSONResponse:
    snapshot = BrokerAccountSnapshot.model_validate(await request.json())
    return JSONResponse(gateway().record_snapshot(snapshot), status_code=201)


@guarded
async def portfolio_state(request: Request) -> JSONResponse:
    return JSONResponse(gateway().portfolio_state())


routes = [
    Route("/health", health, methods=["GET"]),
    Route("/execution/orders", list_orders, methods=["GET"]),
    Route("/execution/orders/{trade_id}/claim", claim_order, methods=["POST"]),
    Route("/execution/orders/{trade_id}/reports", report_execution, methods=["POST"]),
    Route("/execution/portfolio/snapshots", post_snapshot, methods=["POST"]),
    Route("/execution/portfolio/state", portfolio_state, methods=["GET"]),
]

app = Starlette(routes=routes)


__all__ = ["TOKEN_ENV", "app", "gateway", "routes", "set_gateway"]
