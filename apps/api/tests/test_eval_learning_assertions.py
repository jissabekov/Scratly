"""Fixture-driven unit tests for the eval harness learning assertions A19-A23.

These tests drive ``analyze_learning_dump`` / ``learning_assertions`` (and, for
the wiring check, ``assert_suite``) from ``scripts/eval_conversation_suite.py``
with synthetic learning dumps, so the Plan 06 assertion logic is validated in
seconds with zero LLM calls. The dynamic import mirrors
``test_eval_assertions.py``.

Each assertion gets one passing fixture and one violating fixture whose exact
violation string is asserted, plus the A19/A21/A22 sub-cases that the contract
calls out explicitly (module unlocked without a pass, check-ins during an open
quiz, missing mastery-replay events).
"""

import importlib.util
from pathlib import Path
from typing import Any

SUITE_PATH = Path(__file__).resolve().parents[3] / "scripts" / "eval_conversation_suite.py"
SPEC = importlib.util.spec_from_file_location("eval_conversation_suite", SUITE_PATH)
assert SPEC and SPEC.loader
SUITE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SUITE)
analyze_learning_dump = SUITE.analyze_learning_dump
learning_assertions = SUITE.learning_assertions
analyze_dump = SUITE.analyze_dump
assert_suite = SUITE.assert_suite

# BKT posterior for one correct ``mcq`` observation from the prior 0.25
# (learning_quiz_engine.bkt_update) — the value A22 replays for ``scope_small``.
REPLAYED_CORRECT = 0.6136


# ---------------------------------------------------------------------------
# Learning-dump builders (mirror test_eval_assertions.make_dump)
# ---------------------------------------------------------------------------


def _module(module_id: str, slug: str, *, state: str = "available", seq: int = 1) -> dict[str, Any]:
    """Build a LearningModuleSummary entry for the hub."""
    return {
        "id": module_id,
        "slug": slug,
        "seq": seq,
        "title": slug,
        "description": "",
        "est_minutes": 10,
        "state": state,
        "slides_total": 4,
        "slides_completed": 4 if state in {"in_progress", "passed"} else 0,
        "progress_pct": 100 if state == "passed" else 0,
        "quiz_gate_locked": state != "passed",
    }


def _hub(*modules: dict[str, Any]) -> dict[str, Any]:
    """Build a LearningHubResponse with the given module summaries."""
    return {
        "session_id": "test",
        "archetype_key": "generic",
        "modules": list(modules),
        "mastery_pct": 0,
        "streak_days": 0,
    }


def _draw(module_id: str, attempt_id: str) -> dict[str, Any]:
    """Build a QuizDrawResponse carrying an open attempt."""
    return {
        "session_id": "test",
        "module_id": module_id,
        "gate": "available",
        "attempts_used": 0,
        "max_attempts": 3,
        "retry_after_seconds": None,
        "attempt": {
            "attempt_id": attempt_id,
            "attempt_no": 1,
            "form_id": 1,
            "item_count": 5,
            "threshold": 4,
            "pass_rule": "4/5 + critical coverage",
            "items": [],
        },
    }


def _quiz_result(
    attempt_id: str,
    *,
    passed: bool,
    attempt_no: int = 1,
    unlocked_module_id: str | None = None,
) -> dict[str, Any]:
    """Build a QuizAttemptResponse."""
    return {
        "attempt_id": attempt_id,
        "attempt_no": attempt_no,
        "form_id": 1,
        "score": 5 if passed else 2,
        "item_count": 5,
        "threshold": 4,
        "passed": passed,
        "critical_missed": [] if passed else ["scope_small"],
        "missed": [],
        "next_action": "unlock_next" if passed else "retry",
        "next_form_id": None,
        "remediation": None,
        "mastery": [],
        "unlocked_module_id": unlocked_module_id,
    }


def _checkin(
    *,
    gate: str = "available",
    item: bool = True,
    checkins_used: int = 1,
    open_quiz_attempt_id: str | None = None,
) -> dict[str, Any]:
    """Build a CheckinDeliverResponse (optionally marked as quiz-open)."""
    response: dict[str, Any] = {
        "session_id": "test",
        "gate": gate,
        "item": {"id": "ci-1", "objective_code": "scope_small"} if item else None,
        "retry_after_seconds": None,
        "checkins_used": checkins_used,
        "max_checkins": 3,
    }
    if open_quiz_attempt_id is not None:
        response["open_quiz_attempt_id"] = open_quiz_attempt_id
    return response


def _summary(
    *,
    mastery: list[dict[str, Any]] | None = None,
    checkins_used: int = 0,
    max_checkins: int = 3,
    interventions: int = 0,
    due_retention: int = 0,
) -> dict[str, Any]:
    """Build a CoachSummaryResponse."""
    return {
        "session_id": "test",
        "streak_steps": 0,
        "mastery": mastery or [],
        "due_retention": [
            {
                "objective_code": f"obj{i}",
                "objective_label": "",
                "due_at": "2026-01-01",
                "interval_days": 1,
                "reps": 1,
                "lapses": 0,
                "overdue": True,
            }
            for i in range(due_retention)
        ],
        "open_interventions": [
            {
                "id": f"iv{i}",
                "level": "reteach",
                "trigger_rule": "quiz_fail_x1",
                "objective_code": "scope_small",
                "summary": "",
                "created_at": "2026-01-01",
            }
            for i in range(interventions)
        ],
        "checkins_used": checkins_used,
        "max_checkins": max_checkins,
    }


def _answered(objective_code: str, success: bool, kind: str = "mcq") -> dict[str, Any]:
    """Build an xAPI ``answered`` learning event."""
    return {
        "verb": {"id": "http://adlnet.gov/expapi/verbs/answered"},
        "result": {"success": success},
        "context": {"objective_code": objective_code, "kind": kind},
    }


def _module_passed_event() -> dict[str, Any]:
    """Build an xAPI module ``passed`` learning event."""
    return {
        "verb": {"id": "http://adlnet.gov/expapi/verbs/passed"},
        "result": {"success": True},
        "context": {"critical_missed": []},
    }


def _learning_event(event_type: str, **payload: Any) -> dict[str, Any]:
    """Build one ``learning_*`` decision-trace event."""
    return {"event_type": event_type, "component": "learning_repository", **payload}


def make_learning_dump(
    *,
    scenario_id: str = "synthetic_learning",
    hub: dict[str, Any] | None = None,
    quiz_draws: list[dict[str, Any]] | None = None,
    quiz_results: list[dict[str, Any]] | None = None,
    checkins: list[dict[str, Any]] | None = None,
    checkin_results: list[dict[str, Any]] | None = None,
    summary: dict[str, Any] | None = None,
    replayed: list[dict[str, Any]] | None = None,
    chat_checkins: list[dict[str, Any]] | None = None,
    xapi_events: list[dict[str, Any]] | None = None,
    learning_events: list[dict[str, Any]] | None = None,
    turns: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a minimal learning dump with every key ``analyze_learning_dump`` reads."""
    return {
        "scenario_id": scenario_id,
        "title": scenario_id,
        "aspects": [],
        "session": {"session_id": "test"},
        "completed": True,
        "errors": [],
        "turns": turns or [],
        "decision_trace": {"events": learning_events or []},
        "admin_views": {},
        "projects": {"items": []},
        "db_counts": {"llm_runs": 1, "memory_snapshots": 1},
        "scenario_mode": "learning",
        "learning": {
            "hub": hub,
            "module": None,
            "quiz_draws": quiz_draws or [],
            "quiz_checks": [],
            "quiz_results": quiz_results or [],
            "checkins": checkins or [],
            "checkin_results": checkin_results or [],
            "summary": summary,
            "replayed": replayed or [],
            "chat_checkins": chat_checkins or [],
            "xapi_events": xapi_events or [],
        },
    }


def _violations(dump: dict[str, Any]) -> list[str]:
    """Run ``learning_assertions`` over one synthetic learning dump."""
    return learning_assertions({}, [dump])


# ---------------------------------------------------------------------------
# A19 — no module passed/unlocked without a passed quiz attempt
# ---------------------------------------------------------------------------


def test_a19_passed_module_backed_by_passed_attempt_is_clean() -> None:
    dump = make_learning_dump(
        hub=_hub(_module("m1", "how-apps-work", state="passed")),
        quiz_draws=[_draw("m1", "a1")],
        quiz_results=[_quiz_result("a1", passed=True, unlocked_module_id="m1")],
    )
    assert not any(v.startswith("A19:") for v in _violations(dump))


def test_a19_passed_module_without_attempt_violates() -> None:
    dump = make_learning_dump(hub=_hub(_module("m1", "how-apps-work", state="passed")))
    assert (
        "A19: synthetic_learning module how-apps-work passed without a passed quiz attempt"
        in _violations(dump)
    )


def test_a19_unlocked_module_without_pass_violates() -> None:
    dump = make_learning_dump(
        quiz_results=[_quiz_result("a1", passed=False, unlocked_module_id="m2")],
    )
    assert (
        "A19: synthetic_learning module m2 unlocked without a passed quiz attempt"
        in _violations(dump)
    )


# ---------------------------------------------------------------------------
# A20 — quiz attempts idempotent under a replayed request_id
# ---------------------------------------------------------------------------


def test_a20_replayed_request_id_same_attempt_is_clean() -> None:
    dump = make_learning_dump(
        replayed=[{"request_id": "req-1", "first_attempt_id": "a1", "second_attempt_id": "a1"}],
    )
    assert not any(v.startswith("A20:") for v in _violations(dump))


def test_a20_replayed_request_id_new_attempt_violates() -> None:
    dump = make_learning_dump(
        replayed=[{"request_id": "req-1", "first_attempt_id": "a1", "second_attempt_id": "a2"}],
    )
    assert (
        "A20: synthetic_learning quiz replay request_id req-1 produced "
        "attempt ids a1 != a2" in _violations(dump)
    )


def _chat_checkin(event_id: str, key: str = "key-1") -> dict[str, Any]:
    """Build one captured terminal chat check-in entry."""
    return {
        "turn_index": None,
        "message_kind": "progress_checkin",
        "event_id": event_id,
        "gate": "available",
        "item_id": "ci-1",
        "idempotency_key": key,
    }


def test_a20_terminal_replay_same_event_is_clean() -> None:
    dump = make_learning_dump(chat_checkins=[_chat_checkin("ev-1"), _chat_checkin("ev-1")])
    assert not any(v.startswith("A20:") for v in _violations(dump))


def test_a20_terminal_replay_double_delivery_violates() -> None:
    dump = make_learning_dump(chat_checkins=[_chat_checkin("ev-1"), _chat_checkin("ev-2")])
    assert (
        "A20: synthetic_learning terminal replay idempotency_key key-1 "
        "delivered different check-ins ['ev-1', 'ev-2']" in _violations(dump)
    )


# ---------------------------------------------------------------------------
# A21 — check-in budget respected; none delivered during an open quiz
# ---------------------------------------------------------------------------


def test_a21_budget_and_no_open_quiz_checkin_is_clean() -> None:
    dump = make_learning_dump(
        checkins=[_checkin(checkins_used=3), _checkin(gate="budget_exhausted", item=False)],
        summary=_summary(checkins_used=3),
    )
    assert not any(v.startswith("A21:") for v in _violations(dump))


def test_a21_over_budget_violates() -> None:
    dump = make_learning_dump(summary=_summary(checkins_used=4, max_checkins=3))
    assert "A21: synthetic_learning checkins_used 4 exceeds max_checkins 3" in _violations(dump)


def test_a21_delivery_during_open_quiz_violates() -> None:
    dump = make_learning_dump(
        checkins=[_checkin(open_quiz_attempt_id="a1")],
        summary=_summary(checkins_used=1),
    )
    assert (
        "A21: synthetic_learning delivered 1 check-in(s) while a quiz attempt was open"
        in _violations(dump)
    )


# ---------------------------------------------------------------------------
# A22 — mastery projections replay exactly from learning_events
# ---------------------------------------------------------------------------


def test_a22_mastery_matching_replay_is_clean() -> None:
    dump = make_learning_dump(
        summary=_summary(
            mastery=[
                {
                    "objective_code": "scope_small",
                    "p_mastery": REPLAYED_CORRECT,
                    "state": "learning",
                }
            ]
        ),
        xapi_events=[_answered("scope_small", True)],
    )
    assert not any(v.startswith("A22:") for v in _violations(dump))


def test_a22_mastery_mismatch_violates() -> None:
    dump = make_learning_dump(
        summary=_summary(
            mastery=[{"objective_code": "scope_small", "p_mastery": 0.99, "state": "mastered"}]
        ),
        xapi_events=[_answered("scope_small", True)],
    )
    assert (
        "A22: synthetic_learning mastery replay mismatch for scope_small: "
        "summary=0.99 replayed=0.6136" in _violations(dump)
    )


def test_a22_missing_events_violates_rather_than_passing_silently() -> None:
    dump = make_learning_dump(
        summary=_summary(
            mastery=[{"objective_code": "scope_small", "p_mastery": 0.5, "state": "learning"}]
        ),
        xapi_events=[],
    )
    assert "A22: synthetic_learning missing learning_events for mastery replay" in _violations(dump)


# ---------------------------------------------------------------------------
# A23 — no PII in LLM payloads for learning turns
# ---------------------------------------------------------------------------


def test_a23_clean_learning_payload_is_clean() -> None:
    dump = make_learning_dump(
        learning_events=[_learning_event("learning_quiz_scored", outputs={"score": 5})],
    )
    assert not any(v.startswith("A23:") for v in _violations(dump))


def test_a23_forbidden_key_violates() -> None:
    dump = make_learning_dump(
        learning_events=[
            _learning_event("learning_checkin_answered", outputs={"content": "leaked"})
        ],
    )
    assert (
        "A23: synthetic_learning learning event learning_checkin_answered leaks "
        "forbidden key outputs.content" in _violations(dump)
    )


def test_a23_raw_student_utterance_violates() -> None:
    utterance = "I keep failing this module quiz and I am getting frustrated"
    dump = make_learning_dump(
        turns=[{"request": {"text": utterance}}],
        learning_events=[_learning_event("learning_quiz_scored", outputs={"echo": utterance})],
    )
    assert (
        "A23: synthetic_learning learning event learning_quiz_scored contains "
        "raw student utterance" in _violations(dump)
    )


# ---------------------------------------------------------------------------
# Wiring + assessment-dump isolation
# ---------------------------------------------------------------------------


def test_learning_violations_flow_through_assert_suite() -> None:
    dump = make_learning_dump(hub=_hub(_module("m1", "how-apps-work", state="passed")))
    metrics = analyze_dump(dump)
    report = {"by_id": {metrics["scenario_id"]: metrics}, "per_scenario": [metrics]}
    violations = assert_suite(report, [dump])
    assert "A19: synthetic_learning module how-apps-work passed without a passed quiz attempt" in (
        violations
    )


def test_assessment_dump_keeps_learning_metrics_empty() -> None:
    assessment = {
        "scenario_id": "synthetic",
        "session": {"session_id": "test"},
        "completed": True,
        "errors": [],
        "turns": [],
        "decision_trace": {"events": []},
        "admin_views": {},
        "projects": {"items": []},
        "db_counts": {"llm_runs": 1, "memory_snapshots": 1},
    }
    metrics = analyze_dump(assessment)
    assert metrics["learning_metrics"] == {}
    assert metrics["module_completion_rate"] is None
    assert metrics["intervention_count"] is None


def test_learning_metrics_roll_up_from_analysis() -> None:
    dump = make_learning_dump(
        hub=_hub(
            _module("m1", "how-apps-work", state="passed"),
            _module("m2", "next-steps", state="available", seq=2),
        ),
        quiz_draws=[_draw("m1", "a1")],
        quiz_results=[_quiz_result("a1", passed=True, unlocked_module_id="m1")],
        checkins=[_checkin()],
        checkin_results=[{"event_id": "e1", "result": {"score": 1.0}}],
        summary=_summary(checkins_used=1),
    )
    analysis = analyze_learning_dump(dump)
    assert analysis["modules_passed"] == ["m1"]
    assert analysis["module_completion_rate"] == 0.5
    assert analysis["first_attempt_pass"] is True
    assert analysis["first_attempt_pass_rate"] == 1.0
    assert analysis["checkin_response_rate"] == 1.0
    assert analysis["checkin_dismissal_rate"] == 0.0
