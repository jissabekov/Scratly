import importlib.util
from pathlib import Path


SUITE_PATH = Path(__file__).resolve().parents[3] / "scripts" / "eval_conversation_suite.py"
SPEC = importlib.util.spec_from_file_location("eval_conversation_suite", SUITE_PATH)
assert SPEC and SPEC.loader
SUITE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SUITE)
analyze_dump = SUITE.analyze_dump
assert_suite = SUITE.assert_suite
compare_reports = SUITE.compare_reports
simulated_reply = SUITE._simulated_reply


def _dump(
    messages: list[str],
    *,
    keys: list[str],
    stages: list[str] | None = None,
    kinds: list[str] | None = None,
) -> dict:
    stages = stages or ["measurement"] * len(messages)
    kinds = kinds or ["assessment_question"] * len(messages)
    events = []
    for key in keys:
        events.append(
            {
                "event_type": "question_target_selected",
                "component": "question_policy",
                "outputs": {"target_kind": "required_hard_variable", "target_key": key},
            }
        )
    return {
        "scenario_id": "synthetic",
        "session": {"session_id": "test"},
        "completed": True,
        "errors": [],
        "turns": [
            {
                "duration_ms": (index + 1) * 100,
                "response": {
                    "assistant_message": message,
                    "stage": stages[index],
                    "message_kind": kinds[index],
                },
            }
            for index, message in enumerate(messages)
        ],
        "decision_trace": {"events": events},
        "admin_views": {},
        "db_counts": {"llm_runs": 1, "memory_snapshots": 1},
    }


def test_analysis_captures_trajectory_quality_not_only_global_counts():
    dump = _dump(
        ["What do you enjoy?", "Tell me more.", "What tools do you use?"],
        keys=["topics", "topics", "capability"],
    )
    metrics = analyze_dump(dump)
    assert metrics["max_consecutive_target_repeats"] == 2
    assert metrics["unique_target_ratio"] == 0.667
    assert metrics["p50_turn_ms"] == 200
    assert metrics["p95_turn_ms"] == 300
    assert metrics["duplicate_assistant_ratio"] == 0


def test_analysis_detects_repeated_offers_compound_questions_and_regression():
    dump = _dump(
        [
            "Here are projects. Which one? What would you change?",
            "Here are projects. Which one? What would you change?",
        ],
        keys=["profile", "profile"],
        stages=["project_matching", "measurement"],
        kinds=["project_offer", "project_offer"],
    )
    metrics = analyze_dump(dump)
    assert metrics["duplicate_assistant_messages"] == 1
    assert metrics["multi_question_response_count"] == 2
    assert metrics["project_offer_count"] == 2
    assert metrics["stage_regressions"] == 1

    report = {"by_id": {"synthetic": metrics}, "per_scenario": [metrics]}
    violations = assert_suite(report, [dump])
    assert any(item.startswith("A13:") for item in violations)
    assert any(item.startswith("A14:") for item in violations)
    assert any(item.startswith("A15:") for item in violations)
    assert any(item.startswith("A16:") for item in violations)


def test_reassessment_compares_only_shared_scenarios_and_reports_set_changes():
    baseline = {
        "generated_at": "before",
        "by_id": {
            "shared": {"duplicate_assistant_ratio": 0.5, "p95_turn_ms": 900},
            "removed": {"duplicate_assistant_ratio": 0},
        },
    }
    current = {
        "generated_at": "after",
        "by_id": {
            "shared": {"duplicate_assistant_ratio": 0.1, "p95_turn_ms": 1000},
            "added": {"duplicate_assistant_ratio": 0},
        },
    }
    comparison = compare_reports(current, baseline)
    assert comparison["shared_scenarios"] == ["shared"]
    assert comparison["missing_from_current"] == ["removed"]
    assert comparison["new_in_current"] == ["added"]
    assert comparison["per_scenario_deltas"]["shared"] == {
        "duplicate_assistant_ratio": -0.4,
        "p95_turn_ms": 100,
    }


def test_three_adaptive_personas_are_long_and_cover_final_options():
    simulated = [s for s in SUITE.SCENARIOS if s.get("simulator")]
    assert len(simulated) >= 3
    for scenario in simulated:
        spec = scenario["simulator"]
        assert spec["min_turns"] >= 14
        assert spec["max_turns"] >= spec["min_turns"]
        assert spec["project_feedback"]
        assert {
            "topics", "work_mode", "motivation", "execution",
            "capability", "assets", "constraints", "profile",
        } <= set(spec["facts"])


def test_simulated_persona_answers_actual_target_then_sets_repeat_boundary():
    from collections import Counter

    spec = {
        "facts": {"topics": ["first real detail", "second real detail"]},
        "project_feedback": "I choose option two.",
    }
    used = Counter()
    assert simulated_reply(spec, target_key="topics", response={}, used=used) == (
        "first real detail", "topics"
    )
    assert simulated_reply(spec, target_key="topics", response={}, used=used) == (
        "second real detail", "topics"
    )
    text, target = simulated_reply(spec, target_key="topics", response={}, used=used)
    assert target == "topics"
    assert "without repeating myself" in text
    assert simulated_reply(
        spec, target_key="profile", response={"message_kind": "project_offer"}, used=used
    ) == ("I choose option two.", "project_options")


def test_adaptive_metrics_require_multiple_grounded_relevant_options():
    dump = _dump(
        ["What do you enjoy?", "Here are options. Which fits best?"],
        keys=["topics", "profile"],
        stages=["profile_review", "project_matching"],
        kinds=["assessment_question", "project_offer"],
    )
    dump.update({
        "scenario_mode": "adaptive_simulation",
        "scenario_expectations": {
            "min_turns": 2,
            "project_keywords": ["repair"],
        },
        "projects": {
            "items": [
                {"title": "Repair guide", "summary": "Fix bikes", "citation_count": 1},
                {"title": "Repair log", "summary": "Track fixes", "citation_count": 1},
            ]
        },
    })
    dump["turns"][1]["simulation"] = {"answered_target": "project_options"}
    metrics = analyze_dump(dump)
    assert metrics["project_option_count"] == 2
    assert metrics["end_to_end_checks"]["options_presented"]
    assert metrics["end_to_end_checks"]["options_are_grounded"]
    assert metrics["end_to_end_checks"]["options_fit_persona"]


def test_analysis_separates_profile_gain_ranking_changes_and_component_latency():
    dump = _dump(["Question?", "Another question?"], keys=["topics", "work_mode"])
    dump["decision_trace"]["events"].extend([
        {
            "event_type": "profile_reduced",
            "outputs": {
                "accepted_evidence_count": 3,
                "change_count": 2,
                "resolved_unknown_keys": ["topics"],
            },
        },
        {
            "event_type": "opportunities_matched",
            "outputs": {"relevant_top_keys": ["a", "b"]},
        },
        {
            "event_type": "opportunities_matched",
            "outputs": {"relevant_top_keys": ["b", "c"]},
        },
        {
            "event_type": "turn_intent_classified",
            "outputs": {"duration_ms": 10, "model_call_used": False},
        },
        {
            "event_type": "turn_completed",
            "outputs": {"total_duration_ms": 100, "writer_duration_ms": 30},
        },
    ])
    metrics = analyze_dump(dump)
    assert metrics["info_gain_turns"] == 1
    assert metrics["profile_change_count"] == 2
    assert metrics["resolved_unknown_keys"] == ["topics"]
    assert metrics["project_decision_change_count"] == 1
    assert metrics["component_latency_ms"]["intent"]["p95"] == 10
    assert metrics["component_latency_ms"]["writer"]["p50"] == 30
