"""
Host bridge.

Path: api/bridge.py

The transport-agnostic half of the ChatGPT-host integration. A published chat
component has no way to reach EDGE, so an interaction inside it dies in browser
memory. This turns a remote interaction into the same call the console makes:

    host component -> UIEvent -> bridge.record_event -> workbench log
        -> ProjectState -> model context -> hydrated GenerativeView

The bridge holds no business logic. It resolves a project to its agent, applies
the same handlers, and serializes the result.

Scope is deliberately narrow: read state, record interactions, send messages.
Approval and execution are not reachable from here - a hosted chat surface is
not an authenticated operator, and capital authorization stays in the console.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

from approvals.service import ApprovalService
from console.demo.wiring import DemoStack, build_stack, seed
from orchestration.agent import ChatAgent, ViewRefresh
from orchestration.llm import build_language_model, model_status
from research.funnel import ResearchFunnel
from ui.schemas import GenerativeView
from ui.state import UIEvent
from workbench.store import WorkbenchStore


class UnknownProject(KeyError):
    pass


class HostBridge:
    """Resolves a project to a live agent and exposes it over a transport."""

    def __init__(
        self,
        *,
        stack: Optional[DemoStack] = None,
        as_of: Optional[date] = None,
        simulation_dir: Path | str = "data/simulated",
    ):
        self.stack = stack or seed(build_stack(fresh=False))
        self.as_of = as_of or date(2026, 8, 18)
        self.simulation_dir = Path(simulation_dir)
        self._agents: Dict[str, ChatAgent] = {}
        self._views: Dict[str, GenerativeView] = {}

    # -- resolution --------------------------------------------------------

    @property
    def workbench(self) -> WorkbenchStore:
        return self.stack.workbench

    @property
    def approvals(self) -> ApprovalService:
        return self.stack.approvals

    def known_projects(self) -> List[str]:
        return [p.project_id for p in self.workbench.list_projects()]

    def agent(self, project_id: str) -> ChatAgent:
        if project_id not in {p.project_id for p in self.workbench.list_projects(include_archived=True)}:
            raise UnknownProject(project_id)
        if project_id not in self._agents:
            brief = self.workbench.open_session(project_id=project_id, actor="HOST")
            self._agents[project_id] = ChatAgent(
                funnel=ResearchFunnel(as_of=self.as_of, storage_dir=self.simulation_dir),
                workbench=self.workbench,
                transactions=self.stack.transactions,
                approvals=self.approvals,
                project_id=project_id,
                session_id=brief.session_id,
                user_id="HOST",
                model=build_language_model(),
            )
        return self._agents[project_id]

    # -- operations --------------------------------------------------------

    def workspace(self) -> Dict[str, Any]:
        brief = self.workbench.workspace_brief()
        return {"router": model_status(), "workspace": brief.model_dump(mode="json")}

    def project_state(self, project_id: str) -> Dict[str, Any]:
        agent = self.agent(project_id)
        snapshot = agent.project_state()
        return {
            "project_id": project_id,
            "session_id": agent.session_id,
            "state": snapshot.model_dump(mode="json"),
            "context": snapshot.as_context(),
        }

    def record_event(self, project_id: str, event: UIEvent) -> Dict[str, Any]:
        """Apply a remote interaction and return whatever it invalidated."""
        agent = self.agent(project_id)
        if event.project_id != project_id:
            event = event.model_copy(update={"project_id": project_id})
        if event.session_id is None:
            event = event.model_copy(update={"session_id": agent.session_id})

        refreshes = agent.record_ui_event(event)
        for refresh in refreshes:
            self._remember(refresh.turn.view)

        return {
            "event_id": event.event_id,
            "state": agent.project_state().model_dump(mode="json"),
            "context": agent.state_context(),
            "refreshed": [self._refresh_payload(r) for r in refreshes],
        }

    def send_message(self, project_id: str, message: str) -> Dict[str, Any]:
        agent = self.agent(project_id)
        turn = agent.send(message)
        self._remember(turn.view)
        return {
            "reply": turn.reply,
            "tool_calls": turn.tool_calls,
            "view": turn.view.model_dump(mode="json") if turn.view else None,
            "state": agent.project_state().model_dump(mode="json"),
            "context": agent.state_context(),
        }

    def view(self, project_id: str, view_id: str) -> Dict[str, Any]:
        """Re-hydrate a previously issued view against current state."""
        from ui.hydration import hydrate

        stored = self._views.get(view_id)
        if stored is None:
            raise KeyError(view_id)
        hydrate(stored, self.agent(project_id).project_state())
        return stored.model_dump(mode="json")

    # -- internals ---------------------------------------------------------

    def _remember(self, view: Optional[GenerativeView]) -> None:
        if view is not None:
            self._views[view.view_id] = view

    @staticmethod
    def _refresh_payload(refresh: ViewRefresh) -> Dict[str, Any]:
        return {
            "replaced_view_id": refresh.replaced_view_id,
            "reply": refresh.turn.reply,
            "view": refresh.turn.view.model_dump(mode="json") if refresh.turn.view else None,
        }


__all__ = ["HostBridge", "UnknownProject"]
