"""Unit tests for stage monotonicity (A15): derive_stage never regresses."""

from typing import Any

from app.services.question_policy import (
    STAGE_RANK,
    STAGES,
    derive_stage,
    should_force_review_checkpoint,
)

_STAGE_INPUTS: dict[str, dict[str, Any]] = {
    "discovery": {
        "contradictions": 0,
        "reviewed": False,
        "projects_ready": False,
        "coverage_established": 0.0,
        "coverage_touched": 0.0,
    },
    "measurement": {
        "contradictions": 2,
        "reviewed": False,
        "projects_ready": False,
        "coverage_established": 0.0,
        "coverage_touched": 0.5,
    },
    "gap_resolution": {
        "contradictions": 1,
        "reviewed": False,
        "projects_ready": False,
        "coverage_established": 0.6,
        "coverage_touched": 0.6,
    },
    "profile_review": {
        "contradictions": 0,
        "reviewed": False,
        "projects_ready": False,
        "coverage_established": 0.95,
    },
    "project_matching": {
        "contradictions": 0,
        "reviewed": True,
        "projects_ready": False,
        "location_ready": True,
    },
    "complete": {
        "contradictions": 0,
        "reviewed": True,
        "projects_ready": True,
    },
}


def test_derive_stage_regression_matrix_never_regresses():
    """Every regressive (current, derived) pair clamps back to current."""
    for current in STAGES:
        for derived in STAGES:
            if STAGE_RANK[derived] >= STAGE_RANK[current]:
                continue
            inputs = dict(_STAGE_INPUTS[derived])
            assert derive_stage(**inputs, current_stage=current) == current


def test_complete_stage_is_terminal():
    """Once complete, no freshly derived stage can move the session back."""
    for derived in STAGES:
        stage = derive_stage(**_STAGE_INPUTS[derived], current_stage="complete")
        assert stage == "complete"


def test_raising_current_stage_never_lowers_output():
    """Monotonicity property: output rank is non-decreasing in current rank."""
    inputs = _STAGE_INPUTS["discovery"]
    fresh_stage = derive_stage(**inputs)
    previous_rank = -1
    for current in STAGES:
        stage = derive_stage(**inputs, current_stage=current)
        assert stage in {fresh_stage, current}
        assert STAGE_RANK[stage] >= STAGE_RANK[fresh_stage]
        assert STAGE_RANK[stage] >= STAGE_RANK[current]
        assert STAGE_RANK[stage] >= previous_rank
        previous_rank = STAGE_RANK[stage]


def test_unknown_or_missing_current_stage_is_ignored():
    """Backward compat: absent, None, or unknown current_stage changes nothing."""
    inputs = _STAGE_INPUTS["profile_review"]
    assert derive_stage(**inputs) == "profile_review"
    assert derive_stage(**inputs, current_stage=None) == "profile_review"
    assert derive_stage(**inputs, current_stage="not_a_stage") == "profile_review"


def test_stage_inputs_shape_flows_current_stage_through_unpacking():
    """The production call derive_stage(**stage_inputs) picks up the session
    stage from the dict; repository.stage_inputs now returns current_stage."""
    stage_inputs = {
        **_STAGE_INPUTS["profile_review"],
        "dimension_statuses": {},
        "exhausted_keys": (),
        "review_eligible": False,
        "review_reason": None,
        "current_stage": "project_matching",
    }
    assert derive_stage(**stage_inputs) == "project_matching"


def test_review_checkpoint_override_is_the_only_sanctioned_regression():
    """derive_stage itself never regresses. The caller-side override in
    turn_processor.process_student_turn (force_review_checkpoint) is the only
    sanctioned regression path: it runs after derive_stage and is traced via
    the stage_derived event. test_determinism's
    test_exhausted_candidate_pool_forces_review_instead_of_fresh_profile_probe_loop
    pins the override trigger and stays green."""
    stage = derive_stage(**_STAGE_INPUTS["profile_review"], current_stage="project_matching")
    assert stage == "project_matching"
    # Caller-side pattern from turn_processor: derive first, then override.
    if should_force_review_checkpoint(
        candidate_count=0,
        has_social_target=False,
        reviewed=False,
        contradictions=0,
    ):
        stage = "profile_review"
    assert stage == "profile_review"
