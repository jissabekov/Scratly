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
