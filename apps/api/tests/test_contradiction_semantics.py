"""Contradiction semantics matrix for engine v2."""

from uuid import uuid4

from app.contracts import Polarity, ValidatedEvidence
from app.services.contradiction_engine import find_contradictions
from app.services.question_policy import Target, contradiction_fallback, derive_stage
from app.services.question_quality import apply_question_quality_gate


def _ev(dimension, value, *, polarity="support", strength=0.8, eid=None):
    return ValidatedEvidence(
        dimension_key=dimension,
        value_key=value,
        strength=strength,
        polarity=Polarity(polarity),
        source_message_ids=[uuid4()],
        exact_source_quote="quote",
        rationale="test",
        accepted=True,
        rejection_reason=None,
        evidence_id=eid or uuid4(),
    )


def test_maya_turn1_compatible_supports_are_not_conflicts():
    items = [
        _ev("topics", "neighborhood_data"),
        _ev("topics", "science_projects"),
        _ev("motivation", "curiosity"),
        _ev("motivation", "impact"),
        _ev("work_mode", "hands_on_building"),
        _ev("constraints", "small_projects"),
    ]
    assert find_contradictions(items) == []


def test_capability_multi_skill_plus_oppose_other_is_not_conflict():
    items = [
        _ev("capability", "python_basics"),
        _ev("capability", "spreadsheets"),
        _ev("capability", "full_web_app", polarity="oppose"),
    ]
    assert find_contradictions(items) == []


def test_support_and_oppose_same_value_is_conflict():
    items = [
        _ev("topics", "robotics"),
        _ev("topics", "robotics", polarity="oppose"),
    ]
    conflicts = find_contradictions(items)
    assert len(conflicts) == 1
    assert conflicts[0].reason == "support_oppose_same_value"


def test_declared_incompatible_pair_conflicts():
    items = [
        _ev("work_mode", "large_group"),
        _ev("work_mode", "solo_only"),
    ]
    conflicts = find_contradictions(items)
    assert len(conflicts) == 1
    assert conflicts[0].reason == "declared_incompatible_pair"


def test_preference_negation_on_single_choice_conflicts():
    items = [
        _ev("challenge", "seek_hard"),
        _ev("challenge", "avoid_hard", polarity="oppose"),
    ]
    conflicts = find_contradictions(items)
    assert len(conflicts) == 1
    assert conflicts[0].reason == "preference_negation"


def test_single_choice_competing_supports_conflict():
    items = [
        _ev("challenge", "medium"),
        _ev("challenge", "high"),
    ]
    conflicts = find_contradictions(items)
    assert len(conflicts) == 1
    assert conflicts[0].reason == "single_choice_competing_supports"


def test_collaboration_nuance_is_not_conflict():
    items = [
        _ev("collaboration", "small_group"),
        _ev("collaboration", "small_group_but_not_for_coding"),
    ]
    assert find_contradictions(items) == []


def test_stage_uses_established_not_touched_for_gap():
    # Touched everything via contested, but nothing established → discovery/measurement
    assert (
        derive_stage(
            coverage_established=0.0,
            coverage_touched=1.0,
            contradictions=2,
            reviewed=False,
            projects_ready=False,
        )
        == "measurement"
    )
    assert (
        derive_stage(
            coverage_established=0.25,
            coverage_touched=1.0,
            contradictions=1,
            reviewed=False,
            projects_ready=False,
        )
        == "measurement"
    )
    assert (
        derive_stage(
            coverage_established=0.5,
            coverage_touched=1.0,
            contradictions=1,
            reviewed=False,
            projects_ready=False,
        )
        == "gap_resolution"
    )
    assert (
        derive_stage(
            coverage_established=0.95,
            coverage_touched=1.0,
            contradictions=0,
            reviewed=False,
            projects_ready=False,
        )
        == "profile_review"
    )


def test_legacy_coverage_kwarg_still_works():
    assert (
        derive_stage(
            coverage=0.95, contradictions=0, reviewed=False, projects_ready=False
        )
        == "profile_review"
    )


def test_question_gate_rejects_generic_contradiction():
    target = Target(
        "contradiction",
        "motivation",
        "I heard two different preferences. Which is closer to what you want now?",
    )
    gate = apply_question_quality_gate(
        question=target.fallback_template,
        target=target,
        previous_assistant=None,
        value_a="curiosity",
        value_b="impact",
        azure_succeeded=True,
    )
    assert gate["outcome"] == "seeded_override"
    assert "curiosity" in gate["question"].lower() or "curiosity" in gate["question"]
    assert "two different preferences" not in gate["question"].lower()


def test_contradiction_fallback_names_options():
    text = contradiction_fallback("work_mode", "small_group", "independent")
    assert "small group" in text
    assert "independent" in text
    assert "two different preferences" not in text.lower()
