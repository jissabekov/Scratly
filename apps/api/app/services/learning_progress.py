"""Deterministic learning progress logic (no DB, no LLM).

Module states, mastery, streaks, and the xAPI statement shape are pure
functions so they can be unit-tested and replayed. The LLM never owns tracking
state; every value here derives from ``learning.learning_events`` /
``learning.slide_completions``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from uuid import UUID

from app.contracts.learning import ModuleState

XAPI_VERB_COMPLETED = "http://adlnet.gov/expapi/verbs/completed"
XAPI_VERB_EXPERIENCED = "http://adlnet.gov/expapi/verbs/experienced"
XAPI_VERB_ATTEMPTED = "http://adlnet.gov/expapi/verbs/attempted"
XAPI_VERB_ANSWERED = "http://adlnet.gov/expapi/verbs/answered"
XAPI_VERB_PASSED = "http://adlnet.gov/expapi/verbs/passed"
XAPI_VERB_FAILED = "http://adlnet.gov/expapi/verbs/failed"
XAPI_OBJECT_SLIDE = "https://scratly.dev/xapi/activity/slide"
XAPI_OBJECT_LESSON = "https://scratly.dev/xapi/activity/lesson"
XAPI_OBJECT_MODULE = "https://scratly.dev/xapi/activity/module"
XAPI_OBJECT_QUIZ_ITEM = "https://scratly.dev/xapi/activity/quiz-item"
XAPI_ACTOR_HOME = "https://scratly.dev"


@dataclass(frozen=True)
class ModuleProgressView:
    """One module's completion facts, ordered by ``seq`` in the caller."""

    module_id: UUID
    seq: int
    slides_total: int
    slides_completed: int


def progress_pct(completed: int, total: int) -> int:
    """Whole-percent slide completion, clamped to 0..100."""
    if total <= 0:
        return 0
    return max(0, min(100, round(100 * completed / total)))


def derive_module_states(
    modules: Sequence[ModuleProgressView],
    quiz_passed_by_module: Mapping[UUID, bool] | None = None,
) -> list[ModuleState]:
    """Derive locked/available/in_progress/passed for an ordered module path.

    Phase 3 has no quizzes, so ``quiz_passed_by_module`` is empty and only the
    first module is ``available``; later modules stay ``locked`` behind the
    Plan-04 quiz gate.
    """
    passed = quiz_passed_by_module or {}
    states: list[ModuleState] = []
    for index, module in enumerate(modules):
        if passed.get(module.module_id):
            states.append(ModuleState.PASSED)
            continue
        if module.slides_completed > 0:
            states.append(ModuleState.IN_PROGRESS)
            continue
        unlocked = index == 0 or states[index - 1] is ModuleState.PASSED
        states.append(ModuleState.AVAILABLE if unlocked else ModuleState.LOCKED)
    return states


def overall_mastery_pct(modules: Sequence[ModuleProgressView]) -> int:
    """Share of all authored slides the student has completed."""
    total = sum(module.slides_total for module in modules)
    completed = sum(module.slides_completed for module in modules)
    return progress_pct(completed, total)


def compute_streak_days(event_days: Iterable[date], today: date) -> int:
    """Consecutive active days ending today (or yesterday if idle today)."""
    days = sorted(set(event_days), reverse=True)
    if not days:
        return 0
    if days[0] not in (today, today - timedelta(days=1)):
        return 0
    streak = 0
    cursor = days[0]
    for day in days:
        if day == cursor:
            streak += 1
            cursor -= timedelta(days=1)
        elif day < cursor:
            break
    return streak


def xapi_statement(
    *,
    actor_name: str,
    verb_id: str,
    object_id: str,
    object_type: str,
    object_name: str,
    verb_display: str | None = None,
    result: dict | None = None,
    context: dict | None = None,
) -> dict:
    """Build one xAPI-shaped statement (actor/verb/object/result/context)."""
    statement: dict = {
        "actor": {
            "objectType": "Agent",
            "account": {"homePage": XAPI_ACTOR_HOME, "name": actor_name},
        },
        "verb": {"id": verb_id, "display": {"en-US": verb_display or verb_id.rsplit("/", 1)[-1]}},
        "object": {
            "objectType": "Activity",
            "id": object_id,
            "definition": {"type": object_type, "name": {"en-US": object_name}},
        },
        "context": context or {},
    }
    if result is not None:
        statement["result"] = result
    return statement
