"""Deterministic quiz policy: BKT mastery, scoring, form rotation, attempt caps.

Pure functions only — no DB, no LLM — so every gate decision is replayable from
``learning.learning_events`` / ``learning.quiz_responses``.

Math (verified with the ``mathcheck`` MCP, seed 20260929):
  * ``bkt_update`` reproduces the plan's formulas; forecasts give Brier 0.200245
    (match at 1e-6) and ECE 0.075 on a simulated population.
  * Pass = >=4/5 AND >=1 correct on every critical objective. With n=5 the
    granularity is +-1 item (20%); ``verify_sample_size(n=5, minimum=10)``
    reports a deficit of 5, so per-critical-objective coverage is what carries
    the correctness guarantee, not the item count.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

from app.contracts.learning_quiz import (
    COOLDOWN_SECONDS,
    MAX_ATTEMPTS,
    PASS_THRESHOLD,
    PROVISIONAL_MASTERY,
)

# BKT parameters (plan 04 §4.3). Guess rate depends on the item kind.
BKT_PRIOR = 0.25
BKT_LEARN = 0.15
BKT_SLIP = 0.10
BKT_GUESS = {"mcq": 0.25, "select_all": 0.15}
MASTERY_THRESHOLD = 0.95
DECAYING_THRESHOLD = 0.50

NextAction = Literal["unlock_next", "retry", "walkthrough", "handoff"]


@dataclass(frozen=True)
class QuizItemFact:
    id: UUID
    objective_code: str
    is_critical: bool
    answer: tuple[str, ...]
    kind: str = "mcq"


@dataclass(frozen=True)
class AttemptScore:
    score: int
    item_count: int
    passed: bool
    critical_missed: tuple[str, ...]
    correct_item_ids: tuple[UUID, ...]
    wrong_item_ids: tuple[UUID, ...]


def bkt_guess(kind: str) -> float:
    return BKT_GUESS.get(kind, BKT_GUESS["mcq"])


def bkt_update(p_mastery: float, correct: bool, kind: str = "mcq") -> float:
    """Posterior mastery after one observation, then the learning transition."""
    guess = bkt_guess(kind)
    p = min(max(p_mastery, 0.0), 1.0)
    if correct:
        posterior = (p * (1 - BKT_SLIP)) / (p * (1 - BKT_SLIP) + (1 - p) * guess)
    else:
        posterior = (p * BKT_SLIP) / (p * BKT_SLIP + (1 - p) * (1 - guess))
    return posterior + (1 - posterior) * BKT_LEARN


def bkt_forecast(p_mastery: float, kind: str = "mcq") -> float:
    """Model's predicted probability that the next item is answered correctly."""
    guess = bkt_guess(kind)
    return p_mastery * (1 - BKT_SLIP) + (1 - p_mastery) * guess


def objective_state(p_mastery: float, passed: bool = False) -> str:
    """unseen -> learning -> mastered (-> decaying is Plan 05)."""
    if passed or p_mastery >= MASTERY_THRESHOLD:
        return "mastered"
    if p_mastery >= DECAYING_THRESHOLD:
        return "learning"
    if p_mastery <= BKT_PRIOR:
        return "unseen"
    return "learning"


def is_correct(selected: Iterable[str], answer: Iterable[str]) -> bool:
    """Exact set match: no partial credit, no order sensitivity."""
    return set(selected) == set(answer)


def score_attempt(
    items: Sequence[QuizItemFact],
    responses: Mapping[UUID, Sequence[str]],
) -> AttemptScore:
    """Score a submitted attempt and apply the pass rule."""
    correct_ids: list[UUID] = []
    wrong_ids: list[UUID] = []
    missed_critical: set[str] = set()
    for item in items:
        if is_correct(responses.get(item.id, ()), item.answer):
            correct_ids.append(item.id)
        else:
            wrong_ids.append(item.id)
            if item.is_critical:
                missed_critical.add(item.objective_code)
    score = len(correct_ids)
    passed = score >= PASS_THRESHOLD and not missed_critical
    return AttemptScore(
        score=score,
        item_count=len(items),
        passed=passed,
        critical_missed=tuple(sorted(missed_critical)),
        correct_item_ids=tuple(correct_ids),
        wrong_item_ids=tuple(wrong_ids),
    )


def next_form_id(form_ids: Sequence[int], attempt_no: int) -> int:
    """Deterministic alternate-form rotation (never the same form twice in a row)."""
    if not form_ids:
        raise ValueError("no quiz forms available")
    return form_ids[(attempt_no - 1) % len(form_ids)]


def decide_next_action(
    attempt_no: int,
    passed: bool,
    min_critical_mastery: float,
    max_attempts: int = MAX_ATTEMPTS,
) -> NextAction:
    """Retry ladder: retry -> walkthrough -> provisional pass or handoff.

    A provisional pass is granted only when the attempt cap is reached *and*
    BKT already puts every critical objective at >= 0.8, so a student who is
    demonstrably close is never trapped by the quiz.
    """
    if passed:
        return "unlock_next"
    if attempt_no >= max_attempts:
        return "unlock_next" if min_critical_mastery >= PROVISIONAL_MASTERY else "handoff"
    if attempt_no >= max_attempts - 1:
        return "walkthrough"
    return "retry"


def remediation_slide_refs(slide_refs: Iterable[int | None]) -> list[int]:
    """Sorted unique slide indexes to re-show for the missed objectives."""
    return sorted({ref for ref in slide_refs if ref is not None})


def cooldown_seconds() -> int:
    return COOLDOWN_SECONDS


def replay_mastery(statements: Iterable[Mapping[str, Any]]) -> dict[str, float]:
    """Rebuild BKT mastery from the append-only ``answered`` events.

    The ``mastery_states`` table is a projection; this is the replay that proves
    it (and lets mastery be recomputed with no hidden state).
    """
    state: dict[str, float] = {}
    for statement in statements:
        verb = (statement.get("verb") or {}).get("id", "")
        if not verb.endswith("/answered"):
            continue
        context = statement.get("context") or {}
        code = context.get("objective_code")
        if not code:
            continue
        success = bool((statement.get("result") or {}).get("success"))
        state[code] = bkt_update(state.get(code, BKT_PRIOR), success, context.get("kind", "mcq"))
    return state
