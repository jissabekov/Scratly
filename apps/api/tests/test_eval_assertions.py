"""Fixture-driven unit tests for the eval harness assertions A1-A18.

These tests drive ``analyze_dump`` and ``assert_suite`` from
``scripts/eval_conversation_suite.py`` with synthetic dumps, so assertion and
analysis logic is validated in seconds with zero LLM calls. The dynamic import
mirrors ``test_eval_conversation_suite.py``.

The live traces under ``eval/traces/`` are gitignored (see .gitignore), so the
A16/A18 regression cases are synthesized from the *shape* of the committed runs
rather than loaded wholesale. Where a case needs the full 21-scenario set (A5,
A17) the minimal cohort is built from ``SUITE.SCENARIOS`` and documented inline.

A11 (zero Postgres FK violations) is a manual database-level check with no branch
in ``assert_suite`` (see docs/eval-suite.md), so its test documents that absence.
"""

import importlib.util
from pathlib import Path
from typing import Any

SUITE_PATH = Path(__file__).resolve().parents[3] / "scripts" / "eval_conversation_suite.py"
SPEC = importlib.util.spec_from_file_location("eval_conversation_suite", SUITE_PATH)
assert SPEC and SPEC.loader
SUITE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SUITE)
analyze_dump = SUITE.analyze_dump
assert_suite = SUITE.assert_suite


def _turn(
    message: str,
    *,
    index: int,
    stage: str = "measurement",
    kind: str = "assessment_question",
    simulation: dict[str, Any] | None = None,
    elicitation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one turn entry with the fields ``analyze_dump`` reads."""
    response: dict[str, Any] = {
        "assistant_message": message,
        "stage": stage,
        "message_kind": kind,
    }
    if elicitation is not None:
        response["elicitation"] = elicitation
    turn: dict[str, Any] = {
        "index": index,
        "response_status": 200,
        "response": response,
        "duration_ms": (index + 1) * 100,
    }
    if simulation is not None:
        turn["simulation"] = simulation
    return turn


def _turns_from_messages(
    messages: list[str],
    *,
    stages: list[str] | None = None,
    kinds: list[str] | None = None,
    simulations: list[dict[str, Any] | None] | None = None,
    elicitations: list[dict[str, Any] | None] | None = None,
) -> list[dict[str, Any]]:
    """Expand parallel per-turn lists into turn dicts with sequential indices."""
    stages = stages or ["measurement"] * len(messages)
    kinds = kinds or ["assessment_question"] * len(messages)
    simulations = simulations or [None] * len(messages)
    elicitations = elicitations or [None] * len(messages)
    return [
        _turn(
            message,
            index=index,
            stage=stages[index],
            kind=kinds[index],
            simulation=simulations[index],
            elicitation=elicitations[index],
        )
        for index, message in enumerate(messages)
    ]


def _target_event(
    target_key: str,
    *,
    target_kind: str | None = "required_hard_variable",
    component: str = "question_policy",
) -> dict[str, Any]:
    """Build a committed ``question_target_selected`` decision-trace event."""
    outputs: dict[str, Any] = {"target_key": target_key}
    if target_kind is not None:
        outputs["target_kind"] = target_kind
    return {
        "event_type": "question_target_selected",
        "component": component,
        "outputs": outputs,
    }


def make_dump(
    *,
    scenario_id: str = "synthetic",
    turns: list[dict[str, Any]] | None = None,
    target_keys: list[str] | None = None,
    extra_events: list[dict[str, Any]] | None = None,
    accepted_dimensions: list[str] | None = None,
    contradictions: list[dict[str, Any]] | None = None,
    project_items: list[dict[str, Any]] | None = None,
    project_keywords: list[str] | None = None,
    min_turns: int | None = None,
    scenario_mode: str | None = None,
    completed: bool = True,
    errors: list[str] | None = None,
    llm_runs: int = 1,
    memory_snapshots: int = 1,
) -> dict[str, Any]:
    """Build a minimal but valid dump dict with every key ``analyze_dump`` needs."""
    events = [_target_event(key) for key in target_keys or []]
    events.extend(extra_events or [])
    evidence_items = [
        {"dimension_key": dim, "status": "accepted"} for dim in accepted_dimensions or []
    ]
    expectations: dict[str, Any] = {}
    if min_turns is not None:
        expectations["min_turns"] = min_turns
    if project_keywords is not None:
        expectations["project_keywords"] = project_keywords
    dump: dict[str, Any] = {
        "scenario_id": scenario_id,
        "title": scenario_id,
        "aspects": [],
        "session": {"session_id": "test"},
        "completed": completed,
        "errors": errors or [],
        "turns": turns or [],
        "decision_trace": {"events": events},
        "admin_views": {
            "profile": {"profile": {"state": {}}},
            "evidence": {"items": evidence_items},
            "contradictions": {"items": contradictions or []},
            "question-history": {"items": []},
        },
        "projects": {"items": project_items or []},
        "db_counts": {"llm_runs": llm_runs, "memory_snapshots": memory_snapshots},
    }
    if expectations:
        dump["scenario_expectations"] = expectations
    if scenario_mode is not None:
        dump["scenario_mode"] = scenario_mode
    return dump


def _suite(dumps: list[dict[str, Any]]) -> dict[str, Any]:
    """Assemble the minimal report shape ``assert_suite`` consumes."""
    metrics = [analyze_dump(dump) for dump in dumps]
    by_id = {m["scenario_id"]: m for m in metrics if m.get("scenario_id")}
    return {"by_id": by_id, "per_scenario": metrics}


def _violations(dumps: list[dict[str, Any]]) -> list[str]:
    """Run ``assert_suite`` over synthetic dumps and return the violations."""
    return assert_suite(_suite(dumps), dumps)


def _adaptive_turns(
    *,
    extra_measurement: int = 0,
    include_profile_review: bool = True,
    include_offer: bool = True,
) -> list[dict[str, Any]]:
    """Assemble monotonic adaptive-simulation turns; knobs reproduce live regressions."""
    turns = [
        _turn("What do you enjoy making?", index=0, stage="discovery"),
        _turn("Tell me about a tool you have used.", index=1, stage="measurement"),
    ]
    for extra in range(extra_measurement):
        turns.append(
            _turn(f"Any more detail on that? ({extra})", index=len(turns), stage="measurement")
        )
    if include_profile_review:
        turns.append(
            _turn("Does this profile sound right?", index=len(turns), stage="profile_review")
        )
    if include_offer:
        turns.append(
            _turn(
                "Here are two grounded projects. Which fits you best?",
                index=len(turns),
                stage="project_matching",
                kind="project_offer",
            )
        )
        turns.append(
            _turn(
                "",
                index=len(turns),
                stage="project_matching",
                kind="student_answer",
                simulation={"answered_target": "project_options"},
            )
        )
    turns.append(
        _turn(
            "Great choice, let's begin.",
            index=len(turns),
            stage="complete",
            kind="post_match_feedback",
        )
    )
    return turns


def _adaptive_dump(
    scenario_id: str,
    *,
    min_turns: int,
    extra_measurement: int = 0,
    include_profile_review: bool = True,
    include_offer: bool = True,
    project_keywords: list[str] | None = None,
    project_items: list[dict[str, Any]] | None = None,
    accepted_dimensions: list[str] | None = None,
) -> dict[str, Any]:
    """Build an adaptive dump whose ``end_to_end_checks`` come from analyze_dump."""
    return make_dump(
        scenario_id=scenario_id,
        turns=_adaptive_turns(
            extra_measurement=extra_measurement,
            include_profile_review=include_profile_review,
            include_offer=include_offer,
        ),
        target_keys=["topics", "capability", "profile"],
        accepted_dimensions=accepted_dimensions or [],
        project_items=project_items or [],
        project_keywords=project_keywords or [],
        min_turns=min_turns,
        scenario_mode="adaptive_simulation",
    )


# ---------------------------------------------------------------------------
# A1-A18 — one pass fixture (and, where practical, a paired violation fixture)
# ---------------------------------------------------------------------------


def test_a01_completed_and_error_free_dump_passes() -> None:
    assert _violations([make_dump()]) == []


def test_a01_incomplete_or_erroring_dump_violates() -> None:
    violations = _violations([make_dump(scenario_id="bad", completed=False, errors=["boom"])])
    assert "A1: bad not completed" in violations
    assert "A1: bad errors=['boom']" in violations


def test_a02_long_session_repeating_one_target_three_times_violates() -> None:
    messages = [f"Question {index}?" for index in range(8)]
    passing = make_dump(
        turns=_turns_from_messages(messages),
        target_keys=[
            "topics",
            "topics",
            "capability",
            "capability",
            "execution",
            "profile",
            "assets",
            "work_mode",
        ],
    )
    assert not any(v.startswith("A2:") for v in _violations([passing]))

    looping = make_dump(
        turns=_turns_from_messages(messages),
        target_keys=[
            "topics",
            "topics",
            "topics",
            "capability",
            "execution",
            "profile",
            "assets",
            "work_mode",
        ],
    )
    assert "A2: synthetic repeated one target 3 consecutive times" in _violations([looping])


def test_a03_thin_scenario_requires_elicitation_selected_event() -> None:
    passing = make_dump(
        scenario_id="thin_elicitation_loop",
        extra_events=[{"event_type": "elicitation_selected", "component": "elicitation"}],
    )
    assert not any(v.startswith("A3:") for v in _violations([passing]))

    missing = make_dump(scenario_id="thin_elicitation_loop")
    assert "A3: thin_elicitation_loop missing elicitation_selected event" in _violations([missing])


def test_a04_thin_scenario_requires_response_elicitation() -> None:
    passing = make_dump(
        scenario_id="thin_elicitation_loop",
        turns=_turns_from_messages(["Say more?"], elicitations=[{"reason": "thin"}]),
    )
    assert not any(v.startswith("A4:") for v in _violations([passing]))

    missing = make_dump(
        scenario_id="thin_elicitation_loop",
        turns=_turns_from_messages(["Say more?"]),
    )
    assert "A4: thin_elicitation_loop missing response.elicitation" in _violations([missing])


def test_a05_stuck_cohort_must_mostly_reach_review_or_matching() -> None:
    # A5 only applies once the full four-scenario stuck cohort is present, so the
    # fixture is built from SUITE.STUCK_STAGE_COHORT rather than a partial set.
    def cohort_dump(sid: str, *, reached: bool) -> dict[str, Any]:
        stage = "profile_review" if reached else "measurement"
        return make_dump(
            scenario_id=sid,
            turns=_turns_from_messages(["Does this sound right?"], stages=[stage]),
        )

    passing = [cohort_dump(sid, reached=True) for sid in sorted(SUITE.STUCK_STAGE_COHORT)]
    assert not any(v.startswith("A5:") for v in _violations(passing))

    failing = [cohort_dump(sid, reached=False) for sid in sorted(SUITE.STUCK_STAGE_COHORT)]
    assert "A5: stuck cohort reached review/matching 0/4 (0%) < 75%" in _violations(failing)


def test_a06_multi_value_nuance_must_have_no_open_contradictions() -> None:
    passing = make_dump(
        scenario_id="multi_value_nuance",
        contradictions=[{"status": "resolved"}],
    )
    assert not any(v.startswith("A6:") for v in _violations([passing]))

    failing = make_dump(
        scenario_id="multi_value_nuance",
        contradictions=[{"status": "open"}],
    )
    assert "A6: multi_value_nuance open_contradictions=1" in _violations([failing])


def test_a07_refusal_scenario_requires_refuse_and_extract_skip() -> None:
    passing = make_dump(
        scenario_id="student_questions_and_refuse",
        extra_events=[
            {"event_type": "student_answer_refused", "component": "turn_processor"},
            {"event_type": "evidence_extraction_skipped", "component": "extraction"},
        ],
    )
    assert not any(v.startswith("A7:") for v in _violations([passing]))

    violations = _violations([make_dump(scenario_id="student_questions_and_refuse")])
    assert "A7: student_questions_and_refuse missing refusal event" in violations
    assert "A7: student_questions_and_refuse missing extract skip" in violations


def test_a08_internal_policy_phrasing_is_leakage() -> None:
    passing = make_dump(turns=_turns_from_messages(["What do you enjoy?"]))
    assert not any(v.startswith("A8:") for v in _violations([passing]))

    failing = make_dump(turns=_turns_from_messages(["Your profile is stable now."]))
    assert "A8: assistant_leak_hits=1" in _violations([failing])


def test_a09_long_sessions_need_llm_runs_and_memory_snapshots() -> None:
    turns = _turns_from_messages([f"Question {index}?" for index in range(8)])
    assert not any(v.startswith("A9:") for v in _violations([make_dump(turns=turns)]))

    failing = make_dump(turns=turns, llm_runs=0, memory_snapshots=0)
    violations = _violations([failing])
    assert "A9: synthetic missing llm_runs for long session" in violations
    assert "A9: synthetic missing memory_snapshots for long session" in violations


def test_a10_early_complete_attempt_cannot_match_before_turn_eight() -> None:
    passing = make_dump(
        scenario_id="early_complete_attempt",
        turns=_turns_from_messages([f"Question {index}?" for index in range(7)]),
    )
    assert not any(v.startswith("A10:") for v in _violations([passing]))

    failing = make_dump(
        scenario_id="early_complete_attempt",
        turns=_turns_from_messages(
            [f"Question {index}?" for index in range(7)],
            stages=[
                "discovery",
                "measurement",
                "measurement",
                "project_matching",
                "project_matching",
                "measurement",
                "measurement",
            ],
        ),
    )
    assert "A10: early_complete_attempt entered project_matching before turn 8" in _violations(
        [failing]
    )


def test_a11_postgres_fk_check_is_manual_not_in_assert_suite() -> None:
    """A11 (zero Postgres FK violations) is a manual DB-level check.

    docs/eval-suite.md lists A11 as "(Manual) zero Postgres FK violations during
    suite", so ``assert_suite`` has no A11 branch; this guards against a silent
    renumbering that would drop the documented assertion.
    """
    dumps = [make_dump(), make_dump(scenario_id="thin_elicitation_loop")]
    assert not any(v.startswith("A11:") for v in _violations(dumps))


def test_a12_null_target_kind_on_committed_question_violates() -> None:
    passing = make_dump(target_keys=["topics", "capability"])
    assert not any(v.startswith("A12:") for v in _violations([passing]))

    failing = make_dump(extra_events=[_target_event("topics", target_kind=None)])
    assert "A12: synthetic has 1/1 question_target_selected with null target_kind" in _violations(
        [failing]
    )


def test_a13_at_most_one_project_offer_per_session() -> None:
    passing = make_dump(
        turns=_turns_from_messages(
            ["Which project fits?", "Tell me more."],
            kinds=["project_offer", "assessment_question"],
        ),
    )
    assert not any(v.startswith("A13:") for v in _violations([passing]))

    failing = make_dump(
        turns=_turns_from_messages(
            ["Which project fits?", "Here is another offer."],
            kinds=["project_offer", "project_offer"],
        ),
    )
    assert "A13: synthetic emitted 2 project offers" in _violations([failing])


def test_a14_duplicate_assistant_ratio_over_ten_percent_violates() -> None:
    passing = make_dump(
        turns=_turns_from_messages(["Question one?", "Question two?", "Question three?"]),
    )
    assert not any(v.startswith("A14:") for v in _violations([passing]))

    failing = make_dump(
        turns=_turns_from_messages(
            ["Same question?", "Same question?", "Different question?"],
        ),
    )
    assert "A14: synthetic duplicate assistant ratio 33% > 10%" in _violations([failing])


def test_a15_stage_path_must_not_regress() -> None:
    passing = make_dump(
        turns=_turns_from_messages(
            ["A?", "B?", "C?"],
            stages=["discovery", "measurement", "profile_review"],
        ),
    )
    assert not any(v.startswith("A15:") for v in _violations([passing]))

    failing = make_dump(
        turns=_turns_from_messages(
            ["A?", "B?", "C?"],
            stages=["measurement", "project_matching", "measurement"],
        ),
    )
    assert "A15: synthetic has 1 stage regression(s)" in _violations([failing])


def test_a16_each_assistant_response_asks_at_most_one_question() -> None:
    passing = make_dump(turns=_turns_from_messages(["What do you enjoy?"]))
    assert not any(v.startswith("A16:") for v in _violations([passing]))

    failing = make_dump(turns=_turns_from_messages(["Which one? And what would you change?"]))
    assert "A16: synthetic has 1 response(s) with multiple questions" in _violations([failing])


def test_a17_full_suite_needs_at_least_three_adaptive_scenarios() -> None:
    # A17 only fires when every declared scenario is present, so build one dump
    # per SUITE.SCENARIOS entry and toggle which are adaptive_simulation.
    sim_ids = {scenario["id"] for scenario in SUITE.SCENARIOS if scenario.get("simulator")}
    assert len(sim_ids) >= 3

    passing = [
        make_dump(
            scenario_id=scenario["id"],
            scenario_mode="adaptive_simulation" if scenario["id"] in sim_ids else "scripted_probe",
        )
        for scenario in SUITE.SCENARIOS
    ]
    assert not any(v.startswith("A17:") for v in _violations(passing))

    failing = [
        make_dump(scenario_id=scenario["id"], scenario_mode="scripted_probe")
        for scenario in SUITE.SCENARIOS
    ]
    assert "A17: adaptive end-to-end scenarios=0 < 3" in _violations(failing)


def test_a18_adaptive_run_passing_every_end_to_end_check_is_clean() -> None:
    passing = _adaptive_dump(
        "sim_synthetic",
        min_turns=6,
        project_keywords=["repair"],
        project_items=[
            {"title": "Repair guide", "summary": "Fix bikes", "citation_count": 2},
            {"title": "Repair log", "summary": "Track fixes", "citation_count": 1},
        ],
        accepted_dimensions=[
            "topics",
            "work_mode",
            "motivation",
            "execution",
            "capability",
            "assets",
        ],
    )
    assert all(analyze_dump(passing)["end_to_end_checks"].values())
    assert not any(v.startswith("A18:") for v in _violations([passing]))


def test_a18_regression_nia_creative_community_fails_long_enough() -> None:
    # Reproduces eval/traces/2026-09-29-phase1-full/sim_nia_creative_community.json:
    # min_turns=14 but the run stopped at 10 turns, so only long_enough fails.
    dump = _adaptive_dump(
        "sim_nia_creative_community",
        min_turns=14,
        extra_measurement=4,
        project_keywords=["photo", "story"],
        project_items=[
            {
                "title": "Photo story series",
                "summary": "A photo story about neighbors",
                "citation_count": 1,
            },
            {"title": "Story map", "summary": "Map the photo stories", "citation_count": 1},
        ],
        accepted_dimensions=[
            "topics",
            "work_mode",
            "motivation",
            "execution",
            "capability",
            "assets",
        ],
    )
    metrics = analyze_dump(dump)
    assert metrics["n_turns"] == 10
    assert metrics["end_to_end_checks"]["long_enough"] is False
    assert "A18: sim_nia_creative_community failed end-to-end checks: long_enough" in _violations(
        [dump]
    )


def test_a18_regression_eli_practical_fixing_fails_option_checks() -> None:
    # Reproduces eval/traces/2026-09-29-phase1-full/sim_eli_practical_fixing.json:
    # no project items were persisted, so every option/feedback check fails while
    # the length and profile-review checks still pass.
    dump = _adaptive_dump(
        "sim_eli_practical_fixing",
        min_turns=14,
        extra_measurement=12,
        include_offer=False,
        project_keywords=["repair", "fix"],
        project_items=[],
        accepted_dimensions=[],
    )
    metrics = analyze_dump(dump)
    assert metrics["n_turns"] >= 14
    failed = [key for key, ok in metrics["end_to_end_checks"].items() if not ok]
    assert failed == [
        "broad_evidence",
        "options_presented",
        "options_are_grounded",
        "options_fit_persona",
        "feedback_after_options",
    ]
    assert (
        "A18: sim_eli_practical_fixing failed end-to-end checks: "
        "broad_evidence,options_presented,options_are_grounded,"
        "options_fit_persona,feedback_after_options" in _violations([dump])
    )


def test_a18_regression_luz_bilingual_food_also_misses_profile_review() -> None:
    # Reproduces eval/traces/2026-09-29-phase1-full/sim_luz_bilingual_food.json:
    # the run never left measurement, so profile_review_reached fails alongside
    # the option/feedback checks.
    dump = _adaptive_dump(
        "sim_luz_bilingual_food",
        min_turns=14,
        extra_measurement=12,
        include_profile_review=False,
        include_offer=False,
        project_keywords=["order", "food"],
        project_items=[],
        accepted_dimensions=[
            "topics",
            "work_mode",
            "motivation",
            "execution",
            "capability",
            "assets",
        ],
    )
    metrics = analyze_dump(dump)
    assert metrics["n_turns"] >= 14
    failed = [key for key, ok in metrics["end_to_end_checks"].items() if not ok]
    assert failed == [
        "profile_review_reached",
        "options_presented",
        "options_are_grounded",
        "options_fit_persona",
        "feedback_after_options",
    ]
    assert (
        "A18: sim_luz_bilingual_food failed end-to-end checks: "
        "profile_review_reached,options_presented,options_are_grounded,"
        "options_fit_persona,feedback_after_options" in _violations([dump])
    )
