"""Unit proofs for CAT item-exposure control (Plan 01 W1.1, fixes A2)."""

from app.services.question_policy import (
    QuestionValue,
    Target,
    is_repetition_blocked,
    repetition_block_reason,
    select_next,
)
from app.services.turn_processor import (
    _bump_exposure,
    _exposure_fallback,
)


def test_exposure_cap_prefers_fresh_dimension():
    execution = Target(
        "project_discrimination",
        "execution",
        "x",
        asked_count=2,
        coverage_status="supported",
        continuity=1.0,
        consecutive_count=2,
    )
    assets = Target(
        "required_hard_variable",
        "assets",
        "y",
        asked_count=0,
        coverage_status="unknown",
        value=QuestionValue(uncertainty_reduction=1.0),
    )
    assert repetition_block_reason(execution) == "exposure_cap"
    assert not is_repetition_blocked(assets)
    assert select_next([execution, assets]).key == "assets"


def test_contradiction_selectable_at_consecutive_cap():
    contradiction = Target(
        "contradiction",
        "work_mode",
        "Which is it — build or investigate?",
        consecutive_count=2,
        value=QuestionValue(contradiction_resolution=1.0),
    )
    assert repetition_block_reason(contradiction) is None
    assert select_next([contradiction]) is contradiction


def test_repair_and_social_intro_never_capped():
    repair = Target(
        "conversation_repair",
        "repair_rejected_assumption",
        "Tell me more?",
        consecutive_count=4,
    )
    social = Target("social_intro", "conversation_contract", "Hi!", consecutive_count=3)
    assert not is_repetition_blocked(repair)
    assert not is_repetition_blocked(social)


def test_cumulative_hard_stop_still_binds():
    over_asked = Target(
        "project_discrimination",
        "constraints",
        "x",
        asked_count=2,
        coverage_status="provisional",
        consecutive_count=0,
    )
    assert is_repetition_blocked(over_asked)
    assert repetition_block_reason(over_asked) == "repetition_hard_stop"


def test_bump_exposure_resets_other_streaks():
    exposure = _bump_exposure("topics", {})
    assert exposure["topics"] == {"total": 1, "consecutive": 1, "last_asked_turn": 1}
    exposure = _bump_exposure("topics", exposure)
    assert exposure["topics"]["consecutive"] == 2
    exposure = _bump_exposure("assets", exposure)
    assert exposure["assets"]["consecutive"] == 1
    assert exposure["topics"]["consecutive"] == 0
    assert exposure["topics"]["total"] == 2
    assert exposure["assets"]["last_asked_turn"] == 3


def test_fallback_bank_never_repeats_three_turns():
    exposure: dict = {}
    picks: list[str] = []
    for _ in range(9):
        probe = _exposure_fallback(exposure)
        picks.append(probe.key)
        exposure = _bump_exposure(probe.key, exposure)
    for start in range(len(picks) - 2):
        assert not (picks[start] == picks[start + 1] == picks[start + 2]), picks
