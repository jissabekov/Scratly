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
        _ev("motivation", "discovery_mastery"),
        _ev("motivation", "impact_usefulness"),
        _ev("work_mode", "build"),
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


def test_work_mode_facets_can_coexist():
    items = [
        _ev("work_mode", "investigate"),
        _ev("work_mode", "build"),
    ]
    assert find_contradictions(items) == []


def test_execution_support_and_oppose_same_facet_conflicts():
    items = [
        _ev("execution", "public_visibility"),
        _ev("execution", "public_visibility", polarity="oppose"),
    ]
    conflicts = find_contradictions(items)
    assert len(conflicts) == 1
    assert conflicts[0].reason == "support_oppose_same_value"


def test_execution_facets_can_coexist():
    items = [
        _ev("execution", "persistence"),
        _ev("execution", "ambiguity_tolerance"),
    ]
    assert find_contradictions(items) == []


def test_assets_can_coexist_without_conflict():
    items = [
        _ev("assets", "python basics"),
        _ev("assets", "community mentor"),
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
        value_a="discovery_mastery",
        value_b="impact_usefulness",
        azure_succeeded=True,
    )
    assert gate["outcome"] == "seeded_override"
    assert "discovery" in gate["question"].lower() or "mastery" in gate["question"].lower()
    assert "two different preferences" not in gate["question"].lower()


def test_contradiction_fallback_names_options():
    text = contradiction_fallback("work_mode", "investigate", "build")
    assert "investigate" in text
    assert "build" in text
    assert "two different preferences" not in text.lower()
