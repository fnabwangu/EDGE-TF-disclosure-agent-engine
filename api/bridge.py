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
from ui.registry import REGISTRY
from ui.schemas import ActionType, ComponentType, GenerativeView, UIAction, UIComponent
from ui.state import FieldKind, FieldSpec, Persistence, UIEvent
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
        """Apply a remote interaction and return the authoritative current view."""
        agent = self.agent(project_id)
        if event.project_id != project_id:
            event = event.model_copy(update={"project_id": project_id})
        if event.session_id is None:
            event = event.model_copy(update={"session_id": agent.session_id})

        refreshes = agent.record_ui_event(event)
        for refresh in refreshes:
            self._remember(refresh.turn.view)

        current = self._current_view(project_id, event.view_id, refreshes)

        return {
            "event_id": event.event_id,
            "state": agent.project_state().model_dump(mode="json"),
            "context": agent.state_context(),
            "refreshed": [self._refresh_payload(r) for r in refreshes],
            "view": current.model_dump(mode="json") if current else None,
        }

    def component_action(self, project_id: str, view_id: str, action_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Run a server-issued, non-authorizing workflow action."""
        view = self._views.get(view_id)
        if view is None or view.project_id != project_id:
            raise KeyError(view_id)
        try:
            action_enum = ActionType(action_type)
        except ValueError:
            raise ValueError(f"unsupported component action: {action_type}") from None
        allowed = {
            ActionType.GENERATE_STRATEGIES,
            ActionType.SYNTHESIZE_DISCLOSURES,
            ActionType.OPEN_THESIS,
            ActionType.SELECT_IMPLEMENTATION,
        }
        if action_enum not in allowed:
            raise ValueError(f"component action is not permitted: {action_type}")
        declared = []
        for component in view.components:
            spec = REGISTRY.get(component.type)
            if spec is None:
                continue
            declared.extend(
                action for action in component.actions if action.type in spec.allowed_actions
            )
        server_action = next(
            (action for action in declared if action.type is action_enum and action.payload == payload), None
        )
        if server_action is None:
            raise ValueError("component action was not issued by EDGE for this view")

        action_payload = dict(payload)
        if action_enum is ActionType.GENERATE_STRATEGIES and "query_field" in action_payload:
            field_id = action_payload.pop("query_field")
            action_payload["query"] = self.agent(project_id).project_state().value(field_id, "")
        turn = self.agent(project_id).act({"type": action_type, "payload": action_payload})
        if turn is None:
            raise ValueError(f"component action is not executable: {action_type}")
        self._remember(turn.view)
        agent = self.agent(project_id)
        return {
            "reply": turn.reply,
            "tool_calls": turn.tool_calls,
            "view": turn.view.model_dump(mode="json") if turn.view else None,
            "state": agent.project_state().model_dump(mode="json"),
            "context": agent.state_context(),
        }

    def create_project(self, name: str, *, description: Optional[str] = None, mandate: Optional[str] = None) -> Dict[str, Any]:
        project = self.workbench.create_project(name=name, description=description, mandate=mandate, actor="HOST")
        agent = self.agent(project.project_id)
        view = GenerativeView(
            view_id=f"intake-{project.project_id}",
            title="Start a strategy project",
            summary="Enter a theme, then generate strategy candidates from EDGE.",
            project_id=project.project_id,
            session_id=agent.session_id,
            components=[
                UIComponent(
                    type=ComponentType.METRIC,
                    title="Strategy theme",
                    data={"value": ""},
                    fields=[FieldSpec(
                        field_id="strategy_query",
                        label="What should EDGE research?",
                        kind=FieldKind.TEXT,
                        persistence=Persistence.PROJECT,
                        placeholder="Power infrastructure",
                        required=True,
                    )],
                    actions=[UIAction(
                        type=ActionType.GENERATE_STRATEGIES,
                        label="Generate strategy candidates",
                        payload={"query_field": "strategy_query"},
                    )],
                )
            ],
        )
        self._remember(view)
        return {
            "project_id": project.project_id,
            "state": agent.project_state().model_dump(mode="json"),
            "context": agent.state_context(),
            "view": view.model_dump(mode="json"),
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

    def _current_view(self, project_id: str, view_id: str, refreshes: List[ViewRefresh]) -> Optional[GenerativeView]:
        if refreshes:
            return refreshes[-1].turn.view
        stored = self._views.get(view_id)
        if stored is None:
            return None
        from ui.hydration import hydrate

        hydrate(stored, self.agent(project_id).project_state())
        return stored

    @staticmethod
    def _refresh_payload(refresh: ViewRefresh) -> Dict[str, Any]:
        return {
            "replaced_view_id": refresh.replaced_view_id,
            "reply": refresh.turn.reply,
            "view": refresh.turn.view.model_dump(mode="json") if refresh.turn.view else None,
        }


__all__ = ["HostBridge", "UnknownProject"]
