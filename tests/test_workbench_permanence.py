"""Tests for project-scoped, cross-session permanence of ideas and trades."""

import json

import pytest

from workbench.schemas import EventKind, Evidence, IdeaState, PinnedView, ProjectState, Thesis, WatchCondition
from workbench.store import (
    ChainIntegrityError,
    IllegalIdeaTransition,
    IllegalProjectTransition,
    WorkbenchStore,
)


@pytest.fixture()
def store(tmp_path) -> WorkbenchStore:
    return WorkbenchStore(log_path=tmp_path / "events.jsonl")


def seed_thesis(store: WorkbenchStore, project_id: str, session_id: str, *, thesis_id: str, title: str) -> Thesis:
    thesis = Thesis(
        thesis_id=thesis_id,
        project_id=project_id,
        title=title,
        claim=f"{title} is being accumulated ahead of consensus.",
        invalidation_condition="IAV falls below 0.40",
    )
    store.append(
        EventKind.THESIS_CREATED,
        project_id=project_id,
        session_id=session_id,
        actor="op-1",
        subject_id=thesis.thesis_id,
        payload=thesis.model_dump(mode="json"),
    )
    store.append(
        EventKind.STATE_CHANGED,
        project_id=project_id,
        session_id=session_id,
        subject_id=thesis.thesis_id,
        payload={"state": IdeaState.RESEARCHING.value, "reason": "initial investigation"},
    )
    return thesis


def test_projects_isolate_their_own_state(store):
    nuclear = store.create_project(name="Nuclear power", project_id="proj-nuclear")
    semis = store.create_project(name="Semiconductors", project_id="proj-semis")

    n_session = store.open_session(project_id=nuclear.project_id)
    s_session = store.open_session(project_id=semis.project_id)
    seed_thesis(store, nuclear.project_id, n_session.session_id, thesis_id="th-n", title="Nuclear adoption")
    seed_thesis(store, semis.project_id, s_session.session_id, thesis_id="th-s", title="Semis adoption")

    assert set(store.projection(project_id="proj-nuclear").theses) == {"th-n"}
    assert set(store.projection(project_id="proj-semis").theses) == {"th-s"}
    assert set(store.projection().theses) == {"th-n", "th-s"}


def test_continuity_is_scoped_to_the_project(store):
    store.create_project(name="Nuclear power", project_id="proj-nuclear")
    store.create_project(name="Semiconductors", project_id="proj-semis")

    first = store.open_session(project_id="proj-nuclear")
    seed_thesis(store, "proj-nuclear", first.session_id, thesis_id="th-n", title="Nuclear adoption")
    other = store.open_session(project_id="proj-semis")
    seed_thesis(store, "proj-semis", other.session_id, thesis_id="th-s", title="Semis adoption")

    second = store.open_session(project_id="proj-nuclear")
    assert second.previous_session_id == first.session_id
    assert [t.thesis_id for t in second.active_theses] == ["th-n"]
    assert all(entry["subject_id"] != "th-s" for entry in second.changed_since_last_session)


def test_workspace_brief_surfaces_projects_needing_attention(store):
    store.create_project(name="Nuclear power", project_id="proj-nuclear")
    store.create_project(name="Quiet project", project_id="proj-quiet")

    session = store.open_session(project_id="proj-nuclear")
    seed_thesis(store, "proj-nuclear", session.session_id, thesis_id="th-n", title="Nuclear adoption")
    store.append(
        EventKind.INTENT_LINKED,
        project_id="proj-nuclear",
        session_id=session.session_id,
        subject_id="th-n",
        payload={"intent_id": "intent-1", "state": "AWAITING_APPROVAL"},
    )

    brief = store.workspace_brief()
    by_id = {d.project_id: d for d in brief.projects}
    assert by_id["proj-nuclear"].needs_attention is True
    assert by_id["proj-nuclear"].pending_approval_count == 1
    assert by_id["proj-quiet"].needs_attention is False
    assert brief.projects[0].project_id == "proj-nuclear"
    assert brief.total_pending_approvals == 1


def test_archived_projects_drop_out_of_the_overview(store):
    store.create_project(name="Old idea", project_id="proj-old")
    store.set_project_state("proj-old", ProjectState.ARCHIVED, reason="thesis played out")

    assert [p.project_id for p in store.list_projects()] == []
    assert [p.project_id for p in store.list_projects(include_archived=True)] == ["proj-old"]


def test_illegal_project_transition_is_rejected_on_replay(store):
    store.create_project(name="Old idea", project_id="proj-old")
    store.set_project_state("proj-old", ProjectState.ARCHIVED)
    store.append(
        EventKind.PROJECT_STATE_CHANGED,
        project_id="proj-old",
        subject_id="proj-old",
        payload={"state": ProjectState.ACTIVE.value},
    )
    with pytest.raises(IllegalProjectTransition):
        store.projection(project_id="proj-old")


def test_ideas_survive_across_sessions_with_a_change_digest(store):
    store.create_project(name="Nuclear power", project_id="proj-nuclear")
    first = store.open_session(project_id="proj-nuclear")
    seed_thesis(store, "proj-nuclear", first.session_id, thesis_id="th-n", title="Nuclear adoption")
    store.append(
        EventKind.EVIDENCE_ADDED,
        project_id="proj-nuclear",
        session_id=first.session_id,
        subject_id="th-n",
        payload=Evidence(
            evidence_id="ev-1",
            thesis_id="th-n",
            claim="4 independent manager clusters increased normalized weight",
            stance="SUPPORTS",
            metric="iav",
            value=0.71,
        ).model_dump(mode="json"),
    )

    second = store.open_session(project_id="proj-nuclear")
    assert "EVIDENCE_ADDED" in {e["kind"] for e in second.changed_since_last_session}
    assert second.project.name == "Nuclear power"


def test_pinned_views_rehydrate_into_a_new_session(store):
    store.create_project(name="Nuclear power", project_id="proj-nuclear")
    first = store.open_session(project_id="proj-nuclear")
    seed_thesis(store, "proj-nuclear", first.session_id, thesis_id="th-n", title="Nuclear adoption")
    pin = PinnedView(pin_id="pin-1", thesis_id="th-n", title="Adoption snapshot", view={"components": []})
    store.append(
        EventKind.VIEW_PINNED,
        project_id="proj-nuclear",
        session_id=first.session_id,
        payload=pin.model_dump(mode="json"),
    )

    second = store.open_session(project_id="proj-nuclear")
    assert [p.pin_id for p in second.pinned_views] == ["pin-1"]


def test_breached_watch_condition_demotes_the_idea(store):
    store.create_project(name="Nuclear power", project_id="proj-nuclear")
    first = store.open_session(project_id="proj-nuclear")
    seed_thesis(store, "proj-nuclear", first.session_id, thesis_id="th-n", title="Nuclear adoption")
    store.append(
        EventKind.STATE_CHANGED,
        project_id="proj-nuclear",
        session_id=first.session_id,
        subject_id="th-n",
        payload={"state": IdeaState.EVIDENCED.value},
    )
    store.append(
        EventKind.WATCH_CONDITION_SET,
        project_id="proj-nuclear",
        session_id=first.session_id,
        subject_id="th-n",
        payload=WatchCondition(
            condition_id="wc-1", metric="iav", operator="<", threshold=0.40, on_breach="DEMOTE"
        ).model_dump(mode="json"),
    )

    breaches = store.evaluate_watch_conditions({"iav": 0.31}, project_id="proj-nuclear")
    assert breaches[0]["condition_id"] == "wc-1"
    assert store.projection(project_id="proj-nuclear").theses["th-n"].state is IdeaState.CONTESTED

    second = store.open_session(project_id="proj-nuclear")
    assert second.breached_conditions[0]["condition_id"] == "wc-1"


def test_illegal_idea_transition_is_rejected_on_replay(store):
    store.create_project(name="Nuclear power", project_id="proj-nuclear")
    first = store.open_session(project_id="proj-nuclear")
    seed_thesis(store, "proj-nuclear", first.session_id, thesis_id="th-n", title="Nuclear adoption")
    store.append(
        EventKind.STATE_CHANGED,
        project_id="proj-nuclear",
        session_id=first.session_id,
        subject_id="th-n",
        payload={"state": IdeaState.IMPLEMENTED.value},
    )
    with pytest.raises(IllegalIdeaTransition):
        store.projection(project_id="proj-nuclear")


def test_the_chain_spans_projects_and_detects_tampering(store):
    store.create_project(name="Nuclear power", project_id="proj-nuclear")
    store.create_project(name="Semiconductors", project_id="proj-semis")
    first = store.open_session(project_id="proj-nuclear")
    seed_thesis(store, "proj-nuclear", first.session_id, thesis_id="th-n", title="Nuclear adoption")
    assert store.verify_chain() is True

    lines = store.log_path.read_text(encoding="utf-8").splitlines()
    record = json.loads(lines[3])
    record["payload"]["claim"] = "rewritten history"
    lines[3] = json.dumps(record)
    store.log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(ChainIntegrityError):
        store.verify_chain()


def test_history_is_replayable_to_an_earlier_point_in_time(store):
    store.create_project(name="Nuclear power", project_id="proj-nuclear")
    first = store.open_session(project_id="proj-nuclear")
    seed_thesis(store, "proj-nuclear", first.session_id, thesis_id="th-n", title="Nuclear adoption")
    checkpoint = store.events()[-1].at

    store.append(
        EventKind.STATE_CHANGED,
        project_id="proj-nuclear",
        session_id=first.session_id,
        subject_id="th-n",
        payload={"state": IdeaState.EVIDENCED.value},
    )

    assert store.projection(project_id="proj-nuclear").theses["th-n"].state is IdeaState.EVIDENCED
    assert store.projection(project_id="proj-nuclear", until=checkpoint).theses["th-n"].state is IdeaState.RESEARCHING
