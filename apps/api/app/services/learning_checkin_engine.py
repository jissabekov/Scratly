"""Deterministic engines for progress check-ins and coaching (Plan 05 / Phase 5).

Every function here is a pure function of its inputs with an injected ``now`` —
no wall-clock reads, no randomness, no LLM. The LLM may only phrase an
already-decided item and classify free text against its rubric; scheduling,
scoring, the intervention ladder, and retention intervals are owned here.

Reused from Phase 4 rather than duplicated: ``bkt_update`` /
``objective_state`` (``learning_quiz_engine``) and ``xapi_statement`` /
``compute_streak_days`` (``learning_progress``).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Any, Iterable, Mapping, Sequence

from app.contracts.learning_checkin import (
    CHECKIN_COOLDOWN_SECONDS,
    CHECKIN_DISMISS_COOLDOWN_MULTIPLIER,
    INACTIVITY_HOURS,
    MAX_CHECKINS_PER_SESSION,
    MIN_SECONDS_BETWEEN_CHECKINS,
    RETENTION_INTERVALS_DAYS,
    CheckinGate,
    CheckinKind,
    CheckinTrigger,
    InterventionLevel,
)

# Deterministic kind mix per trigger (Plan 05 §5.1). Values are integer weights
# so the choice is a pure function of an ordinal.
TRIGGER_KIND_MIX: dict[CheckinTrigger, dict[CheckinKind, int]] = {
    CheckinTrigger.SECTION_COMPLETE: {
        CheckinKind.MINI_EXERCISE: 60,
        CheckinKind.SELF_EXPLAIN: 25,
        CheckinKind.LIKERT: 15,
    },
    CheckinTrigger.MILESTONE: {
        CheckinKind.LIKERT: 60,
        CheckinKind.MINI_EXERCISE: 40,
    },
    CheckinTrigger.ERROR_BURST: {
        CheckinKind.LIKERT: 50,
        CheckinKind.MINI_EXERCISE: 50,
    },
    CheckinTrigger.INACTIVITY: {
        CheckinKind.MINI_EXERCISE: 70,
        CheckinKind.LIKERT: 30,
    },
    CheckinTrigger.STREAK_DAY: {
        CheckinKind.LIKERT: 50,
        CheckinKind.MINI_EXERCISE: 50,
    },
    CheckinTrigger.RETENTION_DUE: {
        CheckinKind.MINI_EXERCISE: 100,
    },
}

# Priority order for the trigger table (Plan 05 §5.1). Lower index wins.
TRIGGER_PRIORITY: tuple[CheckinTrigger, ...] = (
    CheckinTrigger.RETENTION_DUE,
    CheckinTrigger.ERROR_BURST,
    CheckinTrigger.INACTIVITY,
    CheckinTrigger.MILESTONE,
    CheckinTrigger.STREAK_DAY,
    CheckinTrigger.SECTION_COMPLETE,
)

ERROR_BURST_THRESHOLD = 3
FAST_WRONG_MS = 2500
FAST_WRONG_STREAK = 3
CONFIDENCE_LOW = 2
RETENTION_LAPSE_QUALITY = 3


@dataclass(frozen=True)
class CheckinContext:
    """Everything the scheduler needs, all already measured by the caller."""

    now: datetime
    checkins_used: int
    last_delivered_at: datetime | None = None
    last_dismissed_at: datetime | None = None
    quiz_active: bool = False
    retention_due: bool = False
    recent_wrong: int = 0
    recent_fast_wrong: int = 0
    last_activity_at: datetime | None = None
    milestone_passed: bool = False
    streak_day: bool = False
    section_completed: bool = False


def dismiss_cooldown_seconds(base_seconds: int = CHECKIN_COOLDOWN_SECONDS) -> int:
    """A "not now" doubles the cooldown (autonomy support)."""
    return base_seconds * CHECKIN_DISMISS_COOLDOWN_MULTIPLIER


def checkin_gate(context: CheckinContext) -> tuple[CheckinGate, int | None]:
    """Return (gate, retry_after_seconds). Deterministic budget/caps (§5.1)."""
    if context.quiz_active:
        return CheckinGate.QUIZ_ACTIVE, None
    if context.checkins_used >= MAX_CHECKINS_PER_SESSION:
        return CheckinGate.BUDGET_EXHAUSTED, None
    if context.last_dismissed_at is not None:
        cooldown = dismiss_cooldown_seconds()
        elapsed = (context.now - context.last_dismissed_at).total_seconds()
        if elapsed < cooldown:
            return CheckinGate.COOLDOWN, int(cooldown - elapsed)
    if context.last_delivered_at is not None:
        elapsed = (context.now - context.last_delivered_at).total_seconds()
        if elapsed < MIN_SECONDS_BETWEEN_CHECKINS:
            return CheckinGate.COOLDOWN, int(MIN_SECONDS_BETWEEN_CHECKINS - elapsed)
        if elapsed < CHECKIN_COOLDOWN_SECONDS:
            return CheckinGate.COOLDOWN, int(CHECKIN_COOLDOWN_SECONDS - elapsed)
    return CheckinGate.AVAILABLE, None


def select_trigger(context: CheckinContext) -> CheckinTrigger | None:
    """First matching trigger in priority order, or None."""
    conditions: dict[CheckinTrigger, bool] = {
        CheckinTrigger.RETENTION_DUE: context.retention_due,
        CheckinTrigger.ERROR_BURST: context.recent_wrong >= ERROR_BURST_THRESHOLD
        or context.recent_fast_wrong >= FAST_WRONG_STREAK,
        CheckinTrigger.INACTIVITY: _inactive(context),
        CheckinTrigger.MILESTONE: context.milestone_passed,
        CheckinTrigger.STREAK_DAY: context.streak_day,
        CheckinTrigger.SECTION_COMPLETE: context.section_completed,
    }
    for trigger in TRIGGER_PRIORITY:
        if conditions[trigger]:
            return trigger
    return None


def _inactive(context: CheckinContext) -> bool:
    if context.last_activity_at is None:
        return False
    return (context.now - context.last_activity_at) >= timedelta(hours=INACTIVITY_HOURS)


def choose_kind(trigger: CheckinTrigger, ordinal: int) -> CheckinKind:
    """Deterministic kind choice from the trigger's mix (no RNG)."""
    mix = TRIGGER_KIND_MIX.get(trigger) or {CheckinKind.LIKERT: 1}
    total = sum(mix.values())
    point = ordinal % total
    running = 0
    for kind in sorted(mix, key=lambda k: k.value):
        running += mix[kind]
        if point < running:
            return kind
    return next(iter(mix))


def choose_item(items: Sequence[Any], kind: CheckinKind, ordinal: int) -> Any | None:
    """Pick an item of ``kind`` deterministically; None when the bank lacks one."""
    matching = [item for item in items if _kind_of(item) == kind]
    if not matching:
        return None
    return matching[ordinal % len(matching)]


def _kind_of(item: Any) -> str:
    kind = getattr(item, "kind", None) or (item.get("kind") if isinstance(item, dict) else None)
    return getattr(kind, "value", kind) or ""


# --- scoring -----------------------------------------------------------------


def score_likert(value: int, minimum: int, maximum: int) -> float:
    """Normalize a Likert response to 0..1."""
    span = max(1, maximum - minimum)
    return min(1.0, max(0.0, (value - minimum) / span))


def score_mcq(selected: Iterable[str], answer: Iterable[str]) -> float:
    """Exact set match, no partial credit (mirrors the quiz scorer)."""
    return 1.0 if set(selected) == set(answer) else 0.0


def score_rubric(hits: int, criteria: int) -> float:
    """Deterministic score from an LLM rubric classification (0..1)."""
    if criteria <= 0:
        return 0.0
    return min(1.0, max(0.0, hits / criteria))


def applied_evidence_weight(kind: CheckinKind) -> float:
    """Applied mini-exercises are real BKT evidence (weight 0.5); self-report is not."""
    if kind == CheckinKind.MINI_EXERCISE:
        return 0.5
    return 0.0


# --- SM-2-lite retention -----------------------------------------------------


@dataclass(frozen=True)
class RetentionState:
    ease: float = 2.5
    interval_days: int = 1
    reps: int = 0
    lapses: int = 0


def sm2_lite_update(state: RetentionState, quality: int) -> RetentionState:
    """SM-2-lite: quality 0..5. A lapse resets the interval but never re-locks."""
    quality = min(5, max(0, quality))
    ease = state.ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    ease = min(2.8, max(1.3, ease))
    if quality < 3:
        return RetentionState(
            ease=ease,
            interval_days=RETENTION_INTERVALS_DAYS[0],
            reps=0,
            lapses=state.lapses + 1,
        )
    reps = state.reps + 1
    if reps == 1:
        interval = RETENTION_INTERVALS_DAYS[0]
    elif reps == 2:
        interval = RETENTION_INTERVALS_DAYS[1]
    else:
        interval = max(
            RETENTION_INTERVALS_DAYS[1],
            int(round(state.interval_days * ease)),
        )
    return RetentionState(ease=ease, interval_days=interval, reps=reps, lapses=state.lapses)


def next_due_at(now: datetime, interval_days: int) -> datetime:
    return now + timedelta(days=interval_days)


def due_cards(cards: Sequence[Mapping[str, Any]], now: datetime) -> list[Mapping[str, Any]]:
    """Cards whose due_at has passed, oldest first (deterministic order)."""
    due = [card for card in cards if card.get("due_at") is not None and card["due_at"] <= now]
    return sorted(due, key=lambda card: (card["due_at"], str(card.get("objective_id"))))


def decay_state(state: str, lapsed: bool) -> str:
    """A retention lapse marks the objective ``decaying`` — never re-locks a module."""
    if not lapsed:
        return state
    return "decaying"


# --- intervention ladder -----------------------------------------------------


@dataclass(frozen=True)
class InterventionContext:
    quiz_fails_same_module: int = 0
    bkt_stagnant_events: int = 0
    fast_wrong_streak: int = 0
    inactive: bool = False
    low_confidence_twice: bool = False
    retention_lapsed: bool = False


def intervention_for(context: InterventionContext) -> tuple[InterventionLevel, str] | None:
    """Priority-ordered escalation (Plan 05 §5.2). Returns (level, trigger_rule)."""
    if context.quiz_fails_same_module >= 3 or context.bkt_stagnant_events >= 8:
        return InterventionLevel.HANDOFF, "quiz_fail_x3_or_bkt_stagnant"
    if context.fast_wrong_streak >= FAST_WRONG_STREAK:
        return InterventionLevel.HINT, "fast_wrong_streak"
    if context.quiz_fails_same_module == 2:
        return InterventionLevel.WALKTHROUGH, "quiz_fail_x2_same_module"
    if context.retention_lapsed:
        return InterventionLevel.RETEACH, "retention_lapse"
    if context.inactive:
        return InterventionLevel.HINT, "inactivity_72h"
    if context.low_confidence_twice:
        return InterventionLevel.RETEACH, "low_confidence_twice"
    if context.quiz_fails_same_module == 1:
        return InterventionLevel.RETEACH, "quiz_fail_x1"
    return None


def escalation_next(level: InterventionLevel) -> InterventionLevel:
    """Ladder: hint -> re-teach -> re-quiz -> walkthrough -> handoff."""
    order = (
        InterventionLevel.HINT,
        InterventionLevel.RETEACH,
        InterventionLevel.REQUIZ,
        InterventionLevel.WALKTHROUGH,
        InterventionLevel.HANDOFF,
    )
    index = order.index(level)
    return order[min(index + 1, len(order) - 1)]


# --- streak ------------------------------------------------------------------


def streak_steps(events: Sequence[Mapping[str, Any]]) -> int:
    """Streak unit = "one step counts": a check-in or a module step (not time)."""
    steps = 0
    for event in events:
        verb = event.get("verb") or {}
        if isinstance(verb, dict) and verb.get("id") in {"completed", "answered", "checked_in"}:
            steps += 1
    return steps


def update_card_state(state: RetentionState, quality: int, now: datetime) -> dict[str, Any]:
    """Convenience: SM-2-lite update plus the next due date."""
    updated = sm2_lite_update(state, quality)
    return {
        "ease": updated.ease,
        "interval_days": updated.interval_days,
        "reps": updated.reps,
        "lapses": updated.lapses,
        "due_at": next_due_at(now, updated.interval_days),
        "lapsed": quality < 3,
    }


def with_decay(state: str, quality: int) -> str:
    return decay_state(state, quality < RETENTION_LAPSE_QUALITY)


def replace_state(state: RetentionState, **changes: Any) -> RetentionState:
    return replace(state, **changes)
