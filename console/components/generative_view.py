"""
Renderer for declarative generative views.

Path: console/components/generative_view.py

Maps `GenerativeView` components onto Streamlit widgets. The renderer only
knows the component types in the registry, and it returns the action a user
clicked - it never performs one.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from ui.schemas import ActionType, ComponentType, GenerativeView, UIAction, UIComponent
from ui.state import FieldKind, FieldSpec, UIEvent

TIER_COLOR = {"LOW": "blue", "MEDIUM": "orange", "HIGH": "red", "CRITICAL": "red"}
STATE_ICON = {
    "NASCENT": "*",
    "RESEARCHING": "~",
    "EVIDENCED": "+",
    "CONTESTED": "!",
    "CONFIRMED": "++",
    "IMPLEMENTED": "$",
    "INVALIDATED": "x",
}


def render_view(view: GenerativeView, *, key_prefix: str = "") -> Optional[Dict[str, Any]]:
    """Render a whole view; return the first action the user clicked, if any."""
    st.subheader(view.title)
    if view.summary:
        st.caption(view.summary)

    clicked: Optional[Dict[str, Any]] = None
    for index, component in enumerate(view.components):
        result = render_component(component, key=f"{key_prefix}{view.view_id}-{index}", view=view)
        clicked = clicked or result
    return clicked


def render_component(
    component: UIComponent, *, key: str, view: Optional[GenerativeView] = None
) -> Optional[Dict[str, Any]]:
    handler = _HANDLERS.get(component.type, _render_fallback)
    with st.container(border=True):
        result = handler(component, key)
        if component.fields and view is not None:
            result = result or _render_fields(component, key, view)
        return result


def _render_fields(component: UIComponent, key: str, view: GenerativeView) -> Optional[Dict[str, Any]]:
    """Draw declared controls hydrated from project state; emit an event on change."""
    st.markdown("**Inputs**")
    for index, spec in enumerate(component.fields):
        stored = view.state.get(spec.field_id)
        current = stored.value if stored is not None else None
        new_value = _render_field(spec, current, f"{key}-f{index}")

        if _normalize(new_value) != _normalize(current):
            return {
                "type": "ui_event",
                "event": UIEvent.field_changed(
                    view_id=view.view_id,
                    project_id=view.project_id or "",
                    session_id=view.session_id,
                    field_id=spec.field_id,
                    value=_normalize(new_value),
                    persistence=spec.persistence,
                ),
            }

        if spec.required and not (stored and stored.is_set):
            st.caption(f":red[{spec.label} is required]")
    return None


def _render_field(spec: FieldSpec, current: Any, widget_key: str) -> Any:
    if spec.kind is FieldKind.DATE:
        parsed = None
        if isinstance(current, str) and current:
            try:
                parsed = date.fromisoformat(current[:10])
            except ValueError:
                parsed = None
        return st.date_input(spec.label, value=parsed, key=widget_key, help=spec.help, format="YYYY-MM-DD")
    if spec.kind is FieldKind.NUMBER:
        value = float(current) if current not in (None, "") else 0.0
        return st.number_input(spec.label, value=value, key=widget_key, help=spec.help)
    if spec.kind is FieldKind.CHOICE:
        options = spec.options or []
        index = options.index(current) if current in options else 0
        return st.selectbox(spec.label, options, index=index, key=widget_key, help=spec.help)
    if spec.kind is FieldKind.BOOLEAN:
        return st.checkbox(spec.label, value=bool(current), key=widget_key, help=spec.help)
    return st.text_input(
        spec.label, value=current or "", key=widget_key, help=spec.help, placeholder=spec.placeholder or ""
    )


def _normalize(value: Any) -> Any:
    """Widget output and stored state must compare on the same terms."""
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if value in (0, "", None):
        return None
    return value


def _emit(action: UIAction) -> Dict[str, Any]:
    return {
        "type": action.type.value,
        "payload": action.payload,
        "binds_intent_hash": action.binds_intent_hash,
        "binds_action_hash": action.binds_action_hash,
    }


def _render_actions(component: UIComponent, key: str, *, exclude: tuple = ()) -> Optional[Dict[str, Any]]:
    actions = [a for a in component.actions if a.type not in exclude]
    if not actions:
        return None
    columns = st.columns(len(actions))
    for index, (column, action) in enumerate(zip(columns, actions)):
        primary = action.type is ActionType.REQUEST_APPROVAL
        if column.button(action.label, key=f"{key}-a{index}", type="primary" if primary else "secondary"):
            return _emit(action)
    return None


def _render_metric(component: UIComponent, key: str) -> Optional[Dict[str, Any]]:
    st.metric(component.title, component.data.get("value"), component.data.get("delta"))
    return _render_actions(component, key)


def _render_table(component: UIComponent, key: str) -> Optional[Dict[str, Any]]:
    st.markdown(f"**{component.title}**")
    st.dataframe(
        pd.DataFrame(component.data.get("rows", []), columns=component.data.get("columns")),
        use_container_width=True,
        hide_index=True,
    )
    return _render_actions(component, key)


def _render_project_switcher(component: UIComponent, key: str) -> Optional[Dict[str, Any]]:
    st.markdown(f"**{component.title}**")
    projects: List[Dict[str, Any]] = component.data.get("projects", [])
    clicked = None
    for index, project in enumerate(projects):
        left, right = st.columns([3, 2])
        flag = " :red[needs attention]" if project.get("needs_attention") else ""
        if left.button(
            f"{project['name']}{flag}",
            key=f"{key}-p{index}",
            use_container_width=True,
        ):
            clicked = {"type": ActionType.SWITCH_PROJECT.value, "payload": {"project_id": project["project_id"]}}
        right.caption(
            f"{project['active_thesis_count']} theses / "
            f"{project['pending_approval_count']} pending / "
            f"{project['breached_condition_count']} breached"
        )
    return clicked


def _render_continuity(component: UIComponent, key: str) -> Optional[Dict[str, Any]]:
    data = component.data
    st.markdown(f"**{component.title}**")
    if not data.get("previous_session_id"):
        st.caption("First session in this project.")

    for thesis in data.get("active_theses", []):
        st.write(f"{STATE_ICON.get(thesis['state'], '-')} **{thesis['title']}** - `{thesis['state']}`")

    if data.get("open_transactions"):
        st.caption(f"Open transactions: {data['open_transactions']}")
    if data.get("pending_actions"):
        st.caption(f"Pending actions: {[a['request_id'] for a in data['pending_actions']]}")
    if data.get("breached_conditions"):
        st.warning(
            "Watch conditions breached since you were last here: "
            + ", ".join(c["condition_id"] for c in data["breached_conditions"])
        )
    if data.get("unresolved_questions"):
        st.info("Open question: " + "; ".join(data["unresolved_questions"]))

    changes = data.get("changed_since_last_session", [])
    if changes:
        with st.expander(f"{len(changes)} events since your last session"):
            for entry in changes:
                st.write(f"`{entry['kind']}` {entry['summary']}")
    return _render_actions(component, key)


def _render_inbox(component: UIComponent, key: str) -> Optional[Dict[str, Any]]:
    items = component.data.get("items", [])
    st.markdown(f"**{component.title}** ({len(items)})")
    if not items:
        st.caption("Nothing is waiting on you.")
        return None
    for item in items:
        tier = item.get("risk_tier", "MEDIUM")
        blocked = " :red[blocked]" if item.get("blocked") else ""
        st.write(
            f"`{item['item_type']}` **{item['title']}** - "
            f":{TIER_COLOR.get(tier, 'grey')}[{tier}]{blocked}"
        )
        st.caption(item.get("detail", ""))
    return None


def _render_trade_approval(component: UIComponent, key: str) -> Optional[Dict[str, Any]]:
    data = component.data
    st.markdown(f"**{component.title}**")
    left, middle, right = st.columns(3)
    left.metric("Quantity", f"{data['quantity']:g}")
    middle.metric("Est. notional", f"${data['estimated_notional']:,.0f}")
    right.metric(
        "Portfolio weight",
        f"{data['weight_after']:.2%}",
        f"{(data['weight_after'] - data['weight_before']) * 100:+.2f} pts",
    )

    st.write(
        f"Liquidity **{data['liquidity_status']}** / "
        f"Risk gate **{'PASS' if data['risk_gate_passed'] else 'FAIL'}** / "
        f"State **{data['strategy_state']}**"
    )
    if data.get("rationale"):
        st.caption(f"Reason: {data['rationale']}")
    if data.get("invalidation"):
        st.caption(f"Invalidation: {data['invalidation']}")
    if data.get("blockers"):
        st.error("Blocked: " + "; ".join(data["blockers"]))
    st.code(f"intent_hash {data['intent_hash']}", language=None)
    return _render_actions(component, key)


def _render_action_approval(component: UIComponent, key: str) -> Optional[Dict[str, Any]]:
    data = component.data
    tier = data.get("risk_tier", "MEDIUM")
    st.markdown(f"**{component.title}** - :{TIER_COLOR.get(tier, 'grey')}[{tier}]")
    st.caption(data.get("summary", ""))

    left, right = st.columns(2)
    left.metric("Approvals required", data.get("required_approvals"))
    right.metric("Still outstanding", data.get("outstanding_approvals"))
    if not data.get("reversible", True):
        st.warning("Irreversible - escalated to a two-person rule.")
    if data.get("consequences"):
        for consequence in data["consequences"]:
            st.write(f"- {consequence}")
    if data.get("approvers"):
        st.caption(f"Approved so far by: {', '.join(data['approvers'])}")
    if data.get("blockers"):
        st.error("Blocked: " + "; ".join(data["blockers"]))
    st.code(f"action_hash {data.get('action_hash')}", language=None)
    return _render_actions(component, key)


def _render_audit(component: UIComponent, key: str) -> Optional[Dict[str, Any]]:
    st.markdown(f"**{component.title}**")
    st.dataframe(pd.DataFrame(component.data.get("entries", [])), use_container_width=True, hide_index=True)
    return None


def _render_funnel_rail(component: UIComponent, key: str) -> Optional[Dict[str, Any]]:
    stages = component.data.get("stages", [])
    st.markdown(f"**{component.title}**")
    columns = st.columns(len(stages))
    for column, stage in zip(columns, stages):
        label = stage["stage"].replace("_", " ").title()
        column.metric(label, stage["count"])
        for item in stage["items"][:3]:
            column.caption(item["strategy_id"].split(":")[-1].replace("_", " "))
    return None


def _render_strategy_candidates(component: UIComponent, key: str) -> Optional[Dict[str, Any]]:
    st.markdown(f"**{component.title}**")
    st.dataframe(
        pd.DataFrame(component.data.get("rows", []), columns=component.data.get("columns")),
        use_container_width=True,
        hide_index=True,
    )
    return _render_actions(component, key)


def _render_implementation_candidates(component: UIComponent, key: str) -> Optional[Dict[str, Any]]:
    """Every eligible expression, side by side - selecting is the only way forward."""
    rows = component.data.get("rows", [])
    st.markdown(f"**{component.title}**")
    if rows:
        ranked = sorted(rows, key=lambda r: -(r.get("risk_adjusted_score") or 0))
        st.caption(f"Best risk-adjusted: **{ranked[0]['type']}** ({ranked[0]['risk_adjusted_score']:.3f})")
    st.dataframe(
        pd.DataFrame(rows, columns=component.data.get("columns")),
        use_container_width=True,
        hide_index=True,
    )
    return _render_actions(component, key)


def _render_iav_gauge(component: UIComponent, key: str) -> Optional[Dict[str, Any]]:
    data = component.data
    st.markdown(f"**{component.title}**")
    left, middle, right = st.columns(3)
    left.metric("IAV", f"{data['value']:+.3f}", data["state"])
    middle.metric("Conviction tier", data.get("conviction_tier", "-"))
    right.metric("Requested leverage", f"{data.get('requested_leverage', 0):.2f}x")
    st.progress(max(0.0, min(1.0, (data["value"] + 1) / 2)))
    components = data.get("components", {})
    if components:
        st.bar_chart(pd.DataFrame({"contribution": components}))
    st.caption(
        f"core {data.get('core_score', 0):+.3f} x quality {data.get('quality_multiplier', 1):.3f} "
        f"- penalties {data.get('penalty_total', 0):.3f}"
    )
    return _render_actions(component, key)


def _render_breadth_graph(component: UIComponent, key: str) -> Optional[Dict[str, Any]]:
    data = component.data
    funds = [n for n in data.get("nodes", []) if n.get("kind") == "FUND"]
    st.markdown(f"**{component.title}**")
    st.caption(f"{len(data.get('clusters', []))} independent clusters, {len(funds)} disclosing funds")
    st.dataframe(
        pd.DataFrame([{"fund": f["label"], "cluster": f["group"]} for f in funds]),
        use_container_width=True,
        hide_index=True,
    )
    return None


def _render_evidence(component: UIComponent, key: str) -> Optional[Dict[str, Any]]:
    st.markdown(f"**{component.title}**")
    st.write(component.data.get("claim", ""))
    st.caption(f"source: {', '.join(component.data.get('sources', []))}")
    return _render_actions(component, key)


def _render_counter_thesis(component: UIComponent, key: str) -> Optional[Dict[str, Any]]:
    st.markdown(f":red[**{component.title}**]")
    for claim in component.data.get("counter_claims", []):
        st.write(f"- {claim['claim']}")
    st.caption(
        f"ambiguity {component.data.get('ambiguity', 0):.2f} / manager HHI {component.data.get('manager_hhi', 0):.2f}"
    )
    return _render_actions(component, key)


def _render_implementations(component: UIComponent, key: str) -> Optional[Dict[str, Any]]:
    st.markdown(f"**{component.title}**")
    st.dataframe(pd.DataFrame(component.data.get("candidates", [])), use_container_width=True, hide_index=True)
    return _render_actions(component, key)


def _render_signal_card(component: UIComponent, key: str) -> Optional[Dict[str, Any]]:
    data = component.data
    st.markdown(f"**{data.get('ticker')}** - `{data.get('state')}`")
    st.caption(data.get("summary", ""))
    left, right = st.columns(2)
    left.metric("IAV", f"{data.get('iav', 0):+.3f}")
    right.metric("Clusters", data.get("clusters", 0))
    return _render_actions(component, key)


def _render_fallback(component: UIComponent, key: str) -> Optional[Dict[str, Any]]:
    st.markdown(f"**{component.title}** `{component.type.value}`")
    st.json(component.data, expanded=False)
    return _render_actions(component, key)


_HANDLERS = {
    ComponentType.METRIC: _render_metric,
    ComponentType.TABLE: _render_table,
    ComponentType.HOLDINGS_DELTA_TABLE: _render_table,
    ComponentType.PROJECT_SWITCHER: _render_project_switcher,
    ComponentType.CONTINUITY_BRIEF: _render_continuity,
    ComponentType.APPROVAL_INBOX: _render_inbox,
    ComponentType.APPROVAL_PANEL: _render_trade_approval,
    ComponentType.ACTION_APPROVAL_PANEL: _render_action_approval,
    ComponentType.AUDIT_TRAIL: _render_audit,
    ComponentType.FUNNEL_RAIL: _render_funnel_rail,
    ComponentType.STRATEGY_CANDIDATES: _render_strategy_candidates,
    ComponentType.IMPLEMENTATION_CANDIDATES: _render_implementation_candidates,
    ComponentType.IAV_GAUGE: _render_iav_gauge,
    ComponentType.MANAGER_BREADTH_GRAPH: _render_breadth_graph,
    ComponentType.EVIDENCE_CARD: _render_evidence,
    ComponentType.COUNTER_THESIS_PANEL: _render_counter_thesis,
    ComponentType.ETF_IMPLEMENTATION_COMPARISON: _render_implementations,
    ComponentType.SIGNAL_CARD: _render_signal_card,
}


__all__ = ["render_component", "render_view"]
