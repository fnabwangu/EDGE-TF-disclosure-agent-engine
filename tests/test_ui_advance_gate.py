"""UI-authoritative workflow transition gates."""

from ui.advance_gate import WorkflowState, ui_advance_gate
from ui.schemas import ComponentType, GenerativeView, UIComponent


def renderable_view(project_id="project-1", revision=4):
    return GenerativeView(
        view_id="view-1",
        title="Research",
        project_id=project_id,
        project_revision=revision,
        components=[
            UIComponent(
                type=ComponentType.METRIC,
                title="Progress",
                data={"value": "ready"},
            )
        ],
    )


def test_strategy_to_research_without_a_view_is_rejected():
    result = ui_advance_gate(
        previous_state=WorkflowState.STRATEGY,
        proposed_state=WorkflowState.RESEARCH,
        view=None,
    )
    assert result.passed is False
    assert result.reason == "PROSE_ONLY_STATE_ADVANCE_FORBIDDEN"


def test_strategy_to_research_requires_a_matching_hydrated_view():
    result = ui_advance_gate(
        previous_state=WorkflowState.STRATEGY,
        proposed_state=WorkflowState.RESEARCH,
        view=renderable_view(),
        project_id="project-1",
        project_revision=4,
    )
    assert result.passed is True


def test_implementation_to_options_design_without_ui_is_rejected():
    result = ui_advance_gate(
        previous_state=WorkflowState.IMPLEMENTATION,
        proposed_state=WorkflowState.OPTIONS_DESIGN,
        view=None,
    )
    assert result.passed is False
    assert result.reason == "PROSE_ONLY_STATE_ADVANCE_FORBIDDEN"


def test_mismatched_project_or_revision_is_rejected():
    view = renderable_view(project_id="other", revision=8)
    project_result = ui_advance_gate(
        previous_state=WorkflowState.STRATEGY,
        proposed_state=WorkflowState.RESEARCH,
        view=view,
        project_id="project-1",
        project_revision=4,
    )
    assert project_result.reason == "GENERATIVE_VIEW_PROJECT_MISMATCH"

    revision_result = ui_advance_gate(
        previous_state=WorkflowState.STRATEGY,
        proposed_state=WorkflowState.RESEARCH,
        view=renderable_view(revision=8),
        project_id="project-1",
        project_revision=4,
    )
    assert revision_result.reason == "GENERATIVE_VIEW_REVISION_MISMATCH"


def test_explanatory_prose_can_accompany_a_valid_view():
    result = ui_advance_gate(
        previous_state=WorkflowState.STRATEGY,
        proposed_state=WorkflowState.RESEARCH,
        view=renderable_view(),
    )
    assert result.passed is True
