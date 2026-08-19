"""
View dependency map.

Path: ui/dependencies.py

A rendered view is a function of project state. When a field changes, every
live view computed from that field is stale and must be regenerated - not just
the one that happened to contain the control.

A view depends on the fields it declares, plus any it consumed without
rendering (a trade preview reads max_loss without drawing a box for it).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, Iterable, List, Tuple


@dataclass(frozen=True)
class ViewProducer:
    """How to rebuild a view, and what it is computed from."""

    name: str
    intent_name: str
    intent_args: Dict[str, Any] = field(default_factory=dict)
    depends_on: FrozenSet[str] = frozenset()

    def with_dependencies(self, fields: Iterable[str]) -> "ViewProducer":
        return ViewProducer(
            name=self.name,
            intent_name=self.intent_name,
            intent_args=dict(self.intent_args),
            depends_on=self.depends_on | frozenset(fields),
        )


class DependencyMap:
    """Tracks which live views are computed from which fields."""

    def __init__(self) -> None:
        self._producers: Dict[str, ViewProducer] = {}

    def register(self, view_id: str, producer: ViewProducer) -> None:
        self._producers[view_id] = producer

    def forget(self, view_id: str) -> None:
        self._producers.pop(view_id, None)

    def replace(self, old_view_id: str, new_view_id: str, producer: ViewProducer) -> None:
        self.forget(old_view_id)
        self.register(new_view_id, producer)

    def producer(self, view_id: str) -> ViewProducer | None:
        return self._producers.get(view_id)

    def fields_for(self, view_id: str) -> FrozenSet[str]:
        producer = self._producers.get(view_id)
        return producer.depends_on if producer else frozenset()

    def affected_by(self, field_id: str) -> List[Tuple[str, ViewProducer]]:
        """Live views that must be regenerated because `field_id` changed."""
        return [
            (view_id, producer)
            for view_id, producer in self._producers.items()
            if field_id in producer.depends_on
        ]

    def live_view_ids(self) -> List[str]:
        return list(self._producers)

    def __len__(self) -> int:
        return len(self._producers)


__all__ = ["DependencyMap", "ViewProducer"]
