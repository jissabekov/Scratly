"""Pure quiz-policy tests: gating matrix, form rotation, caps, BKT math."""

from uuid import uuid4

import pytest

from app.contracts.learning_quiz import MAX_ATTEMPTS, PASS_THRESHOLD
from app.services.learning_quiz_engine import (
    BKT_PRIOR,
    QuizItemFact,
    bkt_forecast,
    bkt_update,
    decide_next_action,
    is_correct,
    next_form_id,
    objective_state,
    remediation_slide_refs,
    replay_mastery,
    score_attempt,
)


def _item(objective: str, critical: bool, answer=("a",), kind: str = "mcq") -> QuizItemFact:
    return QuizItemFact(
        id=uuid4(), objective_code=objective, is_critical=critical, answer=answer, kind=kind
    )


# --- gating matrix -----------------------------------------------------------


def test_five_of_five_passes():
    items = [
        _item("events", True),
        _item("loop", True),
        _item("state", True),
        _item("state", True),
        _item("ai", False),
    ]
    responses = {item.id: item.answer for item in items}
    result = score_attempt(items, responses)
    assert result.score == 5
    assert result.passed
    assert result.critical_missed == ()


def test_four_of_five_passes_when_all_critical_covered():
    items = [
        _item("events", True),
        _item("loop", True),
        _item("state", True),
        _item("state", True),
        _item("ai", False),
    ]
    responses = {item.id: item.answer for item in items}
    responses[items[4].id] = ("z",)  # miss only the non-critical item
    result = score_attempt(items, responses)
    assert result.score == 4
    assert result.passed


def test_four_of_five_fails_when_a_critical_objective_is_missed():
    items = [
        _item("events", True),
        _item("loop", True),
        _item("state", True),
        _item("state", True),
        _item("ai", False),
    ]
    responses = {item.id: item.answer for item in items}
    responses[items[0].id] = ("z",)  # miss the only `events` item
    result = score_attempt(items, responses)
    assert result.score == 4
    assert not result.passed
    assert result.critical_missed == ("events",)


def test_three_of_five_fails():
    items = [
        _item("events", True),
        _item("loop", True),
        _item("state", True),
        _item("state", True),
        _item("ai", False),
    ]
    responses = {item.id: item.answer for item in items}
    responses[items[2].id] = ("z",)
    responses[items[3].id] = ("z",)
    result = score_attempt(items, responses)
    assert result.score == 3
    assert not result.passed


def test_select_all_requires_the_exact_set():
    assert is_correct(["a", "b"], ["b", "a"])
    assert not is_correct(["a"], ["a", "b"])
    assert not is_correct(["a", "b", "c"], ["a", "b"])


def test_pass_threshold_constant_matches_plan():
    assert PASS_THRESHOLD == 4
    assert MAX_ATTEMPTS == 3


# --- form rotation + caps ----------------------------------------------------


def test_form_rotation_is_deterministic_and_never_repeats_back_to_back():
    forms = [1, 2, 3]
    assert [next_form_id(forms, n) for n in (1, 2, 3, 4)] == [1, 2, 3, 1]
    assert next_form_id([1, 2], 1) == 1
    assert next_form_id([1, 2], 2) == 2
    assert next_form_id([1, 2], 3) == 1


def test_next_form_id_requires_forms():
    with pytest.raises(ValueError):
        next_form_id([], 1)


def test_attempt_ladder_retry_walkthrough_then_handoff_or_provisional_pass():
    assert decide_next_action(1, passed=False, min_critical_mastery=0.1) == "retry"
    assert decide_next_action(2, passed=False, min_critical_mastery=0.1) == "walkthrough"
    assert decide_next_action(3, passed=False, min_critical_mastery=0.5) == "handoff"
    assert decide_next_action(3, passed=False, min_critical_mastery=0.8) == "unlock_next"
    assert decide_next_action(1, passed=True, min_critical_mastery=0.0) == "unlock_next"
    # A pass at the cap still unlocks.
    assert decide_next_action(3, passed=True, min_critical_mastery=0.0) == "unlock_next"


def test_remediation_slide_refs_are_sorted_unique_and_drop_none():
    assert remediation_slide_refs([3, 1, 3, None, 2]) == [1, 2, 3]
    assert remediation_slide_refs([]) == []


# --- BKT math (hand-computed; also verified with the mathcheck MCP) ----------


def test_bkt_update_matches_hand_computation_for_mcq():
    # correct: 0.25*0.9 / (0.25*0.9 + 0.75*0.25) = 0.545454...; +0.454545*0.15
    assert bkt_update(BKT_PRIOR, True) == pytest.approx(0.6136363636, abs=1e-9)
    # wrong: 0.25*0.1 / (0.25*0.1 + 0.75*0.75) = 0.042553...; +0.957447*0.15
    assert bkt_update(BKT_PRIOR, False) == pytest.approx(0.1861702128, abs=1e-9)


def test_bkt_update_uses_a_lower_guess_rate_for_select_all():
    # 0.225 / (0.225 + 0.75*0.15) = 0.666666...; +0.333333*0.15
    assert bkt_update(BKT_PRIOR, True, "select_all") == pytest.approx(0.7166666667, abs=1e-9)


def test_bkt_forecast_is_the_predicted_item_success():
    assert bkt_forecast(BKT_PRIOR) == pytest.approx(0.4125, abs=1e-9)
    assert bkt_forecast(1.0) == pytest.approx(0.90, abs=1e-9)


def test_bkt_converges_after_five_correct_and_five_wrong():
    p = BKT_PRIOR
    for _ in range(5):
        p = bkt_update(p, True)
    assert p >= 0.95
    assert objective_state(p) == "mastered"

    p = BKT_PRIOR
    for _ in range(5):
        p = bkt_update(p, False)
    assert p < 0.20
    assert objective_state(p) == "unseen"


def test_objective_state_ladder():
    assert objective_state(0.25) == "unseen"
    assert objective_state(0.60) == "learning"
    assert objective_state(0.96) == "mastered"
    assert objective_state(0.10, passed=True) == "mastered"


# --- mastery replay (the projection must be reproducible from events) --------


def _answered(objective: str, success: bool, kind: str = "mcq") -> dict:
    return {
        "verb": {"id": "http://adlnet.gov/expapi/verbs/answered"},
        "result": {"success": success},
        "context": {"objective_code": objective, "kind": kind},
    }


def test_replay_mastery_matches_sequential_updates():
    events = [
        _answered("events", True),
        _answered("events", False),
        _answered("loop", True, "select_all"),
        _answered("events", True),
        _answered("loop", False, "select_all"),
    ]
    replayed = replay_mastery(events)

    events_p = BKT_PRIOR
    for success in (True, False, True):
        events_p = bkt_update(events_p, success)
    loop_p = BKT_PRIOR
    for success in (True, False):
        loop_p = bkt_update(loop_p, success, "select_all")

    assert replayed["events"] == pytest.approx(events_p, abs=1e-12)
    assert replayed["loop"] == pytest.approx(loop_p, abs=1e-12)
    assert "state" not in replayed  # untouched objectives are simply absent


def test_replay_mastery_ignores_unrelated_events():
    events = [
        {
            "verb": {"id": "http://adlnet.gov/expapi/verbs/completed"},
            "result": {"completion": True},
        },
        {"verb": {"id": "http://adlnet.gov/expapi/verbs/answered"}, "context": {}, "result": {}},
    ]
    assert replay_mastery(events) == {}
