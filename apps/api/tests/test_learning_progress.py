"""Pure progress tests: module states, mastery, streaks, xAPI statements."""

from datetime import date, timedelta
from uuid import uuid4

from app.contracts.learning import ModuleState
from app.services.learning_progress import (
    ModuleProgressView,
    compute_streak_days,
    derive_module_states,
    overall_mastery_pct,
    progress_pct,
    xapi_statement,
)


def _module(seq: int, total: int = 3, completed: int = 0) -> ModuleProgressView:
    return ModuleProgressView(
        module_id=uuid4(), seq=seq, slides_total=total, slides_completed=completed
    )


def test_only_first_module_is_available_without_quizzes():
    modules = [_module(1), _module(2), _module(3)]
    assert derive_module_states(modules) == [
        ModuleState.AVAILABLE,
        ModuleState.LOCKED,
        ModuleState.LOCKED,
    ]


def test_started_module_is_in_progress_and_does_not_unlock_the_next():
    modules = [_module(1, completed=1), _module(2)]
    assert derive_module_states(modules) == [ModuleState.IN_PROGRESS, ModuleState.LOCKED]


def test_fully_completed_module_awaits_the_quiz_gate():
    modules = [_module(1, total=3, completed=3), _module(2)]
    assert derive_module_states(modules)[0] is ModuleState.IN_PROGRESS


def test_passing_a_quiz_unlocks_the_next_module():
    first, second = _module(1, total=3, completed=3), _module(2)
    states = derive_module_states([first, second], {first.module_id: True})
    assert states == [ModuleState.PASSED, ModuleState.AVAILABLE]


def test_progress_and_mastery_percentages():
    assert progress_pct(0, 0) == 0
    assert progress_pct(1, 3) == 33
    assert progress_pct(5, 3) == 100
    modules = [_module(1, total=4, completed=1), _module(2, total=4, completed=3)]
    assert overall_mastery_pct(modules) == 50
    assert overall_mastery_pct([]) == 0


def test_streak_counts_consecutive_days_ending_today_or_yesterday():
    today = date(2026, 9, 29)
    assert compute_streak_days([], today) == 0
    assert compute_streak_days([today], today) == 1
    assert compute_streak_days([today, today - timedelta(days=1)], today) == 2
    # Idle today but active yesterday keeps the streak alive.
    assert compute_streak_days([today - timedelta(days=1)], today) == 1
    # A gap breaks the streak.
    assert compute_streak_days([today, today - timedelta(days=2)], today) == 1
    # Old activity alone is not a current streak.
    assert compute_streak_days([today - timedelta(days=5)], today) == 0
    # Duplicates within a day count once.
    assert compute_streak_days([today, today, today - timedelta(days=1)], today) == 2


def test_xapi_statement_shape_is_privacy_safe():
    statement = xapi_statement(
        actor_name="student-uuid",
        verb_id="http://adlnet.gov/expapi/verbs/completed",
        object_id="slide:abc",
        object_type="https://scratly.dev/xapi/activity/slide",
        object_name="Slide 1",
        result={"completion": True, "duration_ms": 1200},
        context={"module_id": "m1"},
    )
    assert statement["actor"]["account"]["name"] == "student-uuid"
    assert statement["verb"]["id"].endswith("/completed")
    assert statement["verb"]["display"]["en-US"] == "completed"
    assert statement["object"]["id"] == "slide:abc"
    assert statement["result"]["completion"] is True
    assert statement["context"]["module_id"] == "m1"


def test_xapi_statement_omits_result_when_absent():
    statement = xapi_statement(
        actor_name="student-uuid",
        verb_id="http://adlnet.gov/expapi/verbs/experienced",
        object_id="slide:abc",
        object_type="https://scratly.dev/xapi/activity/slide",
        object_name="Slide 1",
    )
    assert "result" not in statement
    assert statement["context"] == {}
