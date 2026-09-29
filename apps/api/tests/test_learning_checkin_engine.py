"""Unit tests for the deterministic check-in / coaching engines (Plan 05 W5.2)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from app.contracts.learning_checkin import (
    CHECKIN_COOLDOWN_SECONDS,
    MAX_CHECKINS_PER_SESSION,
    MIN_SECONDS_BETWEEN_CHECKINS,
    CheckinGate,
    CheckinKind,
    CheckinTrigger,
    InterventionLevel,
)
from app.services.learning_checkin_engine import (
    CheckinContext,
    InterventionContext,
    RetentionState,
    checkin_gate,
    choose_item,
    choose_kind,
    decay_state,
    dismiss_cooldown_seconds,
    due_cards,
    escalation_next,
    intervention_for,
    score_likert,
    score_mcq,
    score_rubric,
    select_trigger,
    sm2_lite_update,
    streak_steps,
)

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)


def ctx(**overrides: Any) -> CheckinContext:
    base: dict[str, Any] = {"now": NOW, "checkins_used": 0}
    base.update(overrides)
    return CheckinContext(**base)


# --- budget / caps -----------------------------------------------------------


def test_gate_available_with_no_history() -> None:
    assert checkin_gate(ctx()) == (CheckinGate.AVAILABLE, None)


def test_gate_blocked_during_quiz() -> None:
    assert checkin_gate(ctx(quiz_active=True)) == (CheckinGate.QUIZ_ACTIVE, None)


def test_gate_budget_exhausted_after_cap() -> None:
    assert checkin_gate(ctx(checkins_used=MAX_CHECKINS_PER_SESSION)) == (
        CheckinGate.BUDGET_EXHAUSTED,
        None,
    )


def test_gate_min_gap_between_checkins() -> None:
    gate, retry = checkin_gate(
        ctx(last_delivered_at=NOW - timedelta(seconds=MIN_SECONDS_BETWEEN_CHECKINS - 30))
    )
    assert gate == CheckinGate.COOLDOWN
    assert retry == 30


def test_gate_full_cooldown_after_delivery() -> None:
    gate, retry = checkin_gate(
        ctx(last_delivered_at=NOW - timedelta(seconds=MIN_SECONDS_BETWEEN_CHECKINS + 1))
    )
    assert gate == CheckinGate.COOLDOWN
    assert retry == CHECKIN_COOLDOWN_SECONDS - MIN_SECONDS_BETWEEN_CHECKINS - 1


def test_dismiss_doubles_the_cooldown() -> None:
    assert dismiss_cooldown_seconds() == CHECKIN_COOLDOWN_SECONDS * 2
    gate, retry = checkin_gate(ctx(last_dismissed_at=NOW - timedelta(seconds=60)))
    assert gate == CheckinGate.COOLDOWN
    assert retry == CHECKIN_COOLDOWN_SECONDS * 2 - 60


def test_gate_available_after_cooldown() -> None:
    assert checkin_gate(
        ctx(last_dismissed_at=NOW - timedelta(seconds=CHECKIN_COOLDOWN_SECONDS * 2 + 1))
    ) == (CheckinGate.AVAILABLE, None)


# --- trigger table -----------------------------------------------------------


def test_trigger_priority_retention_beats_error_burst() -> None:
    assert (
        select_trigger(ctx(retention_due=True, recent_wrong=5, milestone_passed=True))
        == CheckinTrigger.RETENTION_DUE
    )


def test_trigger_inactivity_after_72h() -> None:
    assert (
        select_trigger(ctx(last_activity_at=NOW - timedelta(hours=73))) == CheckinTrigger.INACTIVITY
    )
    assert select_trigger(ctx(last_activity_at=NOW - timedelta(hours=71))) is None


def test_trigger_fast_wrong_streak() -> None:
    assert select_trigger(ctx(recent_fast_wrong=3)) == CheckinTrigger.ERROR_BURST


def test_trigger_none_when_no_condition() -> None:
    assert select_trigger(ctx()) is None


# --- kind + item selection ---------------------------------------------------


def test_choose_kind_is_deterministic_and_mix_bounded() -> None:
    picks = {choose_kind(CheckinTrigger.SECTION_COMPLETE, ordinal=i) for i in range(100)}
    assert picks == {CheckinKind.MINI_EXERCISE, CheckinKind.SELF_EXPLAIN, CheckinKind.LIKERT}
    assert choose_kind(CheckinTrigger.RETENTION_DUE, 7) == CheckinKind.MINI_EXERCISE


def test_choose_item_matches_kind_and_is_stable() -> None:
    items = [
        {"kind": "likert", "seq": 1},
        {"kind": "mcq", "seq": 2},
        {"kind": "mini_exercise", "seq": 3},
    ]
    assert choose_item(items, CheckinKind.MCQ, 0)["seq"] == 2
    assert choose_item(items, CheckinKind.MCQ, 5)["seq"] == 2
    assert choose_item(items, CheckinKind.SELF_EXPLAIN, 0) is None


# --- scoring -----------------------------------------------------------------


def test_score_likert_normalizes() -> None:
    assert score_likert(1, 1, 5) == 0.0
    assert score_likert(5, 1, 5) == 1.0
    assert score_likert(3, 1, 5) == 0.5


def test_score_mcq_exact_match() -> None:
    assert score_mcq(["a"], ["a"]) == 1.0
    assert score_mcq(["a", "b"], ["a"]) == 0.0


def test_score_rubric_is_bounded() -> None:
    assert score_rubric(1, 2) == 0.5
    assert score_rubric(9, 2) == 1.0
    assert score_rubric(1, 0) == 0.0


# --- SM-2-lite ---------------------------------------------------------------


def test_sm2_lite_interval_progression() -> None:
    state = RetentionState()
    state = sm2_lite_update(state, 5)
    assert state.interval_days == 1 and state.reps == 1
    state = sm2_lite_update(state, 5)
    assert state.interval_days == 3 and state.reps == 2
    state = sm2_lite_update(state, 5)
    assert state.interval_days >= 7 and state.reps == 3


def test_sm2_lite_lapse_resets_interval_and_counts() -> None:
    state = RetentionState(ease=2.5, interval_days=16, reps=4, lapses=0)
    lapsed = sm2_lite_update(state, 2)
    assert lapsed.interval_days == 1
    assert lapsed.reps == 0
    assert lapsed.lapses == 1
    assert lapsed.ease < 2.5


def test_decay_state_marks_decaying_but_never_relocks() -> None:
    assert decay_state("mastered", lapsed=True) == "decaying"
    assert decay_state("mastered", lapsed=False) == "mastered"


def test_due_cards_ordered_oldest_first() -> None:
    cards = [
        {"objective_id": "b", "due_at": NOW - timedelta(hours=1)},
        {"objective_id": "a", "due_at": NOW - timedelta(hours=5)},
        {"objective_id": "c", "due_at": NOW + timedelta(hours=1)},
    ]
    assert [card["objective_id"] for card in due_cards(cards, NOW)] == ["a", "b"]


# --- intervention ladder -----------------------------------------------------


@pytest.mark.parametrize(
    ("context", "expected"),
    [
        (InterventionContext(quiz_fails_same_module=3), InterventionLevel.HANDOFF),
        (InterventionContext(bkt_stagnant_events=8), InterventionLevel.HANDOFF),
        (InterventionContext(fast_wrong_streak=3), InterventionLevel.HINT),
        (InterventionContext(quiz_fails_same_module=2), InterventionLevel.WALKTHROUGH),
        (InterventionContext(retention_lapsed=True), InterventionLevel.RETEACH),
        (InterventionContext(inactive=True), InterventionLevel.HINT),
        (InterventionContext(low_confidence_twice=True), InterventionLevel.RETEACH),
        (InterventionContext(quiz_fails_same_module=1), InterventionLevel.RETEACH),
    ],
)
def test_intervention_ladder_priority(
    context: InterventionContext, expected: InterventionLevel
) -> None:
    result = intervention_for(context)
    assert result is not None and result[0] == expected


def test_intervention_none_when_no_rule_fires() -> None:
    assert intervention_for(InterventionContext()) is None


def test_escalation_ladder_is_monotonic_and_terminal() -> None:
    assert escalation_next(InterventionLevel.HINT) == InterventionLevel.RETEACH
    assert escalation_next(InterventionLevel.RETEACH) == InterventionLevel.REQUIZ
    assert escalation_next(InterventionLevel.REQUIZ) == InterventionLevel.WALKTHROUGH
    assert escalation_next(InterventionLevel.WALKTHROUGH) == InterventionLevel.HANDOFF
    assert escalation_next(InterventionLevel.HANDOFF) == InterventionLevel.HANDOFF


# --- streak ------------------------------------------------------------------


def test_streak_steps_counts_checkins_and_module_steps() -> None:
    events = [
        {"verb": {"id": "completed"}},
        {"verb": {"id": "answered"}},
        {"verb": {"id": "checked_in"}},
        {"verb": {"id": "launched"}},
    ]
    assert streak_steps(events) == 3
