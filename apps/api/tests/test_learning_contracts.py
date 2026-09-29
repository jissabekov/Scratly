"""Contract tests for the learning API surface and its Plan 04/05 boundaries."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.contracts.learning import (
    LearningHubResponse,
    LearningModuleSummary,
    ModuleDetailResponse,
    ModuleProgress,
    ModuleState,
    QuizGate,
    SlideCompleteRequest,
    SlideCompleteResponse,
    SlideItem,
)
from app.main import app


def _summary(state: ModuleState = ModuleState.AVAILABLE) -> LearningModuleSummary:
    return LearningModuleSummary(
        id=uuid4(),
        slug="how-apps-work",
        seq=1,
        title="Behind the Swipe",
        description="How an application actually works",
        est_minutes=12,
        state=state,
        slides_total=14,
        slides_completed=0,
        progress_pct=0,
        quiz_gate_locked=True,
    )


def test_hub_response_serializes_module_states():
    payload = LearningHubResponse(
        session_id=uuid4(),
        archetype_key="generic",
        modules=[_summary(ModuleState.AVAILABLE), _summary(ModuleState.LOCKED)],
        mastery_pct=0,
        streak_days=0,
    ).model_dump(mode="json")
    assert payload["modules"][0]["state"] == "available"
    assert payload["modules"][1]["state"] == "locked"
    assert payload["modules"][0]["quiz_gate_locked"] is True


def test_module_detail_keeps_typed_blocks_and_locked_gate():
    detail = ModuleDetailResponse(
        session_id=uuid4(),
        module=_summary(),
        slides=[
            SlideItem(
                id=uuid4(),
                index=1,
                lesson_seq=1,
                lesson_title="What the system receives",
                seq=1,
                kind="check",
                title="Where is boredom?",
                content=[
                    {
                        "type": "check",
                        "question": "Where does the record say the student was bored?",
                        "options": [
                            {"key": "a", "label": "It does not say"},
                            {"key": "b", "label": "In watch_time"},
                        ],
                        "answer_key": "a",
                        "explanation": "The record stores behavior, not feelings.",
                        "objective": "events",
                    }
                ],
                objective_code="events",
                completed=False,
            )
        ],
        progress=ModuleProgress(slides_total=14, slides_completed=0, current_slide_index=1),
        quiz=QuizGate(),
    )
    payload = detail.model_dump(mode="json")
    assert payload["slides"][0]["content"][0]["type"] == "check"
    assert payload["quiz"] == {"state": "locked", "available": False, "planned_phase": 4}


def test_slide_complete_request_and_response_shapes():
    request = SlideCompleteRequest(request_id="req-12345678", time_on_slide_ms=1500)
    assert request.time_on_slide_ms == 1500
    with pytest.raises(ValidationError):
        SlideCompleteRequest(request_id="short")

    response = SlideCompleteResponse(
        slide_id=uuid4(),
        completed=True,
        already_completed=False,
        module_progress=ModuleProgress(slides_total=14, slides_completed=1, current_slide_index=2),
        next_slide_index=2,
    )
    assert response.next_slide_index == 2


def test_learning_routes_are_registered_including_plan_boundaries():
    paths = {route.path for route in app.routes}
    expected = {
        "/v1/sessions/{session_id}/learning",
        "/v1/sessions/{session_id}/learning/modules/{module_id}",
        "/v1/sessions/{session_id}/learning/slides/{slide_id}/complete",
        "/v1/sessions/{session_id}/learning/modules/{module_id}/quiz",
        "/v1/sessions/{session_id}/learning/quiz-attempts",
        "/v1/sessions/{session_id}/learning/checkins",
        "/v1/sessions/{session_id}/learning/checkins/{checkin_id}",
    }
    assert expected <= paths


def test_assessment_write_path_is_untouched_by_learning_routes():
    """Learning must not expose any endpoint under the assessment surface."""
    learning_paths = {route.path for route in app.routes if "/learning" in route.path}
    assert learning_paths
    assert all("assessment" not in path for path in learning_paths)
