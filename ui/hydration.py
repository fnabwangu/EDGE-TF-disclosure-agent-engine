"""
View hydration.

Path: ui/hydration.py

Closes the round trip. A regenerated view declares its controls; hydration
fills them from authoritative project state, so a value entered twenty messages
ago is still there when the panel is rebuilt.
"""

from __future__ import annotations

from typing import Any, Dict, List

from ui.schemas import GenerativeView
from ui.state import FieldSpec, ProjectStateSnapshot, UIFieldState


def hydrate(view: GenerativeView, snapshot: ProjectStateSnapshot) -> GenerativeView:
    """Populate `view.state` for every control the view declares."""
    for spec in view.declared_fields():
        stored = snapshot.fields.get(spec.field_id)
        view.state[spec.field_id] = stored or UIFieldState(
            field_id=spec.field_id, value=None, persistence=spec.persistence
        )
    return view


def field_value(view: GenerativeView, field_id: str, default: Any = None) -> Any:
    state = view.state.get(field_id)
    return state.value if state is not None and state.is_set else default


def missing_required(view: GenerativeView) -> List[FieldSpec]:
    """Required controls the user has not filled - what the UI should highlight."""
    return [
        spec
        for spec in view.declared_fields()
        if spec.required and not (view.state.get(spec.field_id) or UIFieldState(field_id=spec.field_id)).is_set
    ]


def as_values(view: GenerativeView) -> Dict[str, Any]:
    return {field_id: state.value for field_id, state in view.state.items() if state.is_set}


__all__ = ["as_values", "field_value", "hydrate", "missing_required"]
