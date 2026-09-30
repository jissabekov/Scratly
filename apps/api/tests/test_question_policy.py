"""Plan 07 acceptance: planner directive v2, pairing, and the named unit proofs."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.contracts import QuestionResponse
from app.repository.assessment import TurnTransaction
from app.services.azure_openai import LocalFallbackLLM, QuestionWriter
from app.services.context_builder import ContextBuilder
from app.services.elicitation_policy import elicitation_attempt_state
from app.services.question_policy import (
    PlannerAction,
    QuestionValue,
    Target,
    plan_next,
)
from app.services.question_quality import validate_turn_pairing
from app.services.turn_processor import (
    _transition_line,
    probe_counts_toward_exposure,
    uncompacted_token_estimate,
)

_PROMPTS = Path(__file__).resolve().parents[1] / "prompts" / "question_writer"
_RICH = "I kept rebuilding the level every night after school with my cousin"


def _target(
    kind: str,
    key: str,
    *,
    asked_count: int = 0,
    value: QuestionValue | None = None,
) -> Target:
    return Target(
        kind,
        key,
        f"Ask about {key}?",
        asked_count=asked_count,
        continuity=1.0,
        value=value or QuestionValue(),
    )


def _yielding_current() -> Target:
    return _target(
        "project_critical_unknown",
        "topics",
        asked_count=2,
        value=QuestionValue(
            project_discrimination=1,
            uncertainty_reduction=1,
            evidence_weakness=1,
            conversational_relevance=1,
            novelty=1,
        ),
    )


def _fresh_capability() -> Target:
    return _target(
        "required_hard_variable",
        "capability",
        value=QuestionValue(uncertainty_reduction=1, project_discrimination=1),
    )


def test_directive_fields_per_action():
    rich_follow = _target(
        "project_critical_unknown",
        "topics",
        asked_count=1,
        value=QuestionValue(
            project_discrimination=1,
            uncertainty_reduction=1,
            evidence_weakness=1,
            conversational_relevance=1,
            novelty=1,
        ),
    )
    weak = _target(
        "required_hard_variable",
        "capability",
        value=QuestionValue(uncertainty_reduction=0.05),
    )
    follow = plan_next([rich_follow, weak], last_target_key="topics", student_text=_RICH)
    assert follow is not None
    assert follow.action == PlannerAction.FOLLOW_UP
    assert follow.acknowledgment == "auto"
    assert follow.bridge_hint is None
    assert follow.closure is False
    assert follow.collect
    assert follow.reason == "one_high_value_behavioral_follow_up"

    bridge = plan_next(
        [
            _target("project_critical_unknown", "topics", asked_count=1),
            _fresh_capability(),
        ],
        last_target_key="topics",
        student_text=_RICH,
    )
    assert bridge is not None
    assert bridge.action == PlannerAction.BRIDGE
    assert bridge.acknowledgment == "brief"
    assert bridge.bridge_hint
    assert bridge.closure is False

    clarify = plan_next(
        [
            _target(
                "contradiction",
                "motivation",
                value=QuestionValue(contradiction_resolution=1, uncertainty_reduction=1),
            ),
            _target(
                "required_hard_variable",
                "assets",
                value=QuestionValue(uncertainty_reduction=0.1),
            ),
        ],
        last_target_key="topics",
        student_text=_RICH,
    )
    assert clarify is not None
    assert clarify.action == PlannerAction.CLARIFY
    assert clarify.acknowledgment == "validate"
    assert clarify.bridge_hint
    assert clarify.reason == "resolve_contradiction"

    gate = plan_next(
        [
            _target(
                "required_hard_variable",
                "constraints",
                value=QuestionValue(uncertainty_reduction=1, project_discrimination=1),
            ),
            _target(
                "project_critical_unknown",
                "topics",
                asked_count=1,
                value=QuestionValue(uncertainty_reduction=0.05),
            ),
        ],
        last_target_key="topics",
        student_text=_RICH,
    )
    assert gate is not None
    assert gate.action == PlannerAction.GATE
    assert gate.acknowledgment == "brief"
    assert gate.bridge_hint
    assert gate.reason == "hard_feasibility"

    rejected = plan_next(
        [_yielding_current(), _fresh_capability()],
        last_target_key="topics",
        student_text="Can we talk about something else?",
    )
    assert rejected is not None
    assert rejected.action == PlannerAction.SWITCH
    assert rejected.acknowledgment == "repair"
    assert rejected.bridge_hint
    assert rejected.closure is False
    assert rejected.reason == "topic_rejected"

    collapsed = plan_next(
        [
            _target("project_critical_unknown", "topics", asked_count=1),
            _fresh_capability(),
        ],
        last_target_key="topics",
        student_text="no",
    )
    assert collapsed is not None
    assert collapsed.reason == "branch_yield_collapsed"
    assert collapsed.closure is True
    assert collapsed.acknowledgment == "brief"
    assert collapsed.bridge_hint

    forced = plan_next(
        [_yielding_current(), _fresh_capability()],
        last_target_key="topics",
        student_text=_RICH,
    )
    assert forced is not None
    assert forced.action == PlannerAction.SWITCH
    assert forced.reason == "topic_budget_reached"
    assert forced.closure is True
    assert forced.acknowledgment == "brief"
    assert forced.target.key == "capability"

    exhausted = plan_next(
        [
            _target("project_critical_unknown", "topics", asked_count=3),
            _fresh_capability(),
        ],
        last_target_key="topics",
        student_text=_RICH,
        last_turn_accepted=True,
    )
    assert exhausted is not None
    assert exhausted.reason == "follow_up_exhausted"
    assert exhausted.closure is True
    assert "same thing" not in _transition_line(0, "What next?", "switch").lower()


def test_semantic_stay_extends_one_probe_when_the_answer_yielded():
    decision = plan_next(
        [_yielding_current(), _fresh_capability()],
        last_target_key="topics",
        student_text=_RICH,
        last_turn_accepted=True,
    )
    assert decision is not None
    assert decision.action == PlannerAction.FOLLOW_UP
    assert decision.reason == "topic_yielding_extended"
    assert decision.target.key == "topics"
    assert decision.closure is False
    assert decision.acknowledgment == "auto"
    assert decision.bridge_hint is None
    assert decision.probes_left_on_key == 1


def test_contradiction_on_the_dimension_just_asked_waits_one_turn():
    conflict = _target(
        "contradiction",
        "work_mode",
        value=QuestionValue(contradiction_resolution=1, uncertainty_reduction=1),
    )
    other = _target(
        "required_hard_variable",
        "assets",
        value=QuestionValue(uncertainty_reduction=0.2),
    )
    deferred = plan_next([conflict, other], last_target_key="work_mode", student_text=_RICH)
    assert deferred is not None
    assert deferred.target.kind != "contradiction"
    assert deferred.target.key == "assets"

    raised = plan_next(
        [conflict, other],
        last_target_key="work_mode",
        student_text=_RICH,
        student_raised_contradiction_keys=("work_mode",),
    )
    assert raised is not None
    assert raised.action == PlannerAction.CLARIFY
    assert raised.target.key == "work_mode"

    motivation = _target(
        "contradiction",
        "motivation",
        value=QuestionValue(contradiction_resolution=1, uncertainty_reduction=1),
    )
    other_dim = plan_next(
        [conflict, motivation, other],
        last_target_key="work_mode",
        student_text=_RICH,
    )
    assert other_dim is not None
    assert other_dim.target.key == "motivation"

    only = plan_next([conflict], last_target_key="work_mode", student_text=_RICH)
    assert only is not None
    assert only.action == PlannerAction.CLARIFY

    facet = plan_next(
        [
            _target(
                "contradiction",
                "execution",
                value=QuestionValue(contradiction_resolution=1, uncertainty_reduction=1),
            ),
            other,
        ],
        last_target_key="execution:persistence",
        student_text=_RICH,
    )
    assert facet is not None
    assert facet.target.key == "assets"


def test_elicitation_family_resets_when_the_planner_switches():
    same_key, same_attempts = elicitation_attempt_state(
        pending_key="work_mode",
        target_key="work_mode",
        target_kind="required_hard_variable",
        prior_attempts=1,
    )
    assert (same_key, same_attempts) == ("work_mode", 2)

    switched_key, switched_attempts = elicitation_attempt_state(
        pending_key="work_mode",
        target_key="execution:persistence",
        target_kind="required_hard_variable",
        prior_attempts=2,
    )
    assert (switched_key, switched_attempts) == ("execution", 1)

    geo_key, geo_attempts = elicitation_attempt_state(
        pending_key="constraints",
        target_key="constraints:geo",
        target_kind="required_hard_variable",
        prior_attempts=1,
    )
    assert (geo_key, geo_attempts) == ("constraints", 2)


def test_canned_non_probes_do_not_count_toward_exposure():
    assert not probe_counts_toward_exposure(
        stage="discovery",
        message_kind="matching_unavailable",
        matching_feedback_closed=False,
    )
    assert not probe_counts_toward_exposure(
        stage="discovery",
        message_kind="project_offer",
        matching_feedback_closed=False,
    )
    assert not probe_counts_toward_exposure(
        stage="complete",
        message_kind="question",
        matching_feedback_closed=False,
    )
    assert not probe_counts_toward_exposure(
        stage="project_matching",
        message_kind="student_answer",
        matching_feedback_closed=True,
    )
    assert probe_counts_toward_exposure(
        stage="discovery",
        message_kind="question",
        matching_feedback_closed=False,
    )


def test_asked_questions_query_joins_target_to_message_text():
    source = inspect.getsource(TurnTransaction.asked_questions)
    assert "q.target_key" in source
    assert "m.content" in source
    assert "assistant_message_id" in source
    assert "LIMIT :limit" in source
    assert "rows.reverse()" in source

    ledger = [{"target_key": "topics", "text": "What have you been playing?"}]
    context = ContextBuilder().question_writer(
        Target("project_critical_unknown", "topics", "x"),
        [],
        {"content": {"stable_preferences": ["maps"]}, "created_at": "storage"},
        {},
        asked_questions=ledger,
        post_answer_pivot=True,
    )
    assert context["asked_questions"] == ledger
    assert context["memory"] == {"stable_preferences": ["maps"]}
    assert context["post_answer_pivot"] is True


def test_compaction_counts_only_tokens_after_the_boundary():
    messages = [
        {"sequence": 2, "content": "a" * 40},
        {"sequence": 4, "content": "b" * 40},
        {"sequence": 5, "content": "cdefghij"},
    ]
    assert uncompacted_token_estimate(messages, 4) == 2
    assert uncompacted_token_estimate(messages, 0) == 22
    source = inspect.getsource(TurnTransaction.student_response_stats)
    assert '"last_boundary_sequence"' in source


def test_question_response_assembles_and_rejects_overlong_asks():
    assembled = QuestionResponse(
        student_point="builds maps with a cousin",
        acknowledgment="Maps with your cousin.",
        bridge="Different direction —",
        question="What kept you going after it got frustrating?",
    )
    assert assembled.compose() == (
        "Maps with your cousin. Different direction — "
        "What kept you going after it got frustrating?"
    )
    ask_only = QuestionResponse(question="What kept you going?")
    assert ask_only.compose() == "What kept you going?"
    with pytest.raises(ValidationError):
        QuestionResponse(question="x" * 321)


def test_turn_pairing_matches_the_directive():
    ok = validate_turn_pairing(
        student_point="builds maps",
        acknowledgment="Maps with your cousin.",
        bridge="Different direction —",
        acknowledgment_mode="brief",
        action="switch",
        bridge_hint="what they are already good at",
    )
    assert ok["passed"] is True
    assert ok["warnings"] == []

    missing_point = validate_turn_pairing(
        student_point=None,
        acknowledgment="Heard.",
        bridge=None,
        acknowledgment_mode="auto",
        action="follow_up",
        bridge_hint=None,
    )
    assert missing_point["passed"] is True
    assert missing_point["warnings"] == ["student_point_missing"]

    forbidden_ack = validate_turn_pairing(
        student_point="hi",
        acknowledgment="Hey.",
        bridge=None,
        acknowledgment_mode="none",
        action="follow_up",
        bridge_hint=None,
    )
    assert forbidden_ack["acknowledgment"] is None
    assert "acknowledgment_forbidden" in forbidden_ack["reasons"]

    missing_ack = validate_turn_pairing(
        student_point="hi",
        acknowledgment=None,
        bridge=None,
        acknowledgment_mode="auto",
        action="follow_up",
        bridge_hint=None,
    )
    assert missing_ack["passed"] is False
    assert "acknowledgment_required" in missing_ack["reasons"]

    follow_bridge = validate_turn_pairing(
        student_point="maps",
        acknowledgment="Maps.",
        bridge="Switching gears.",
        acknowledgment_mode="auto",
        action="follow_up",
        bridge_hint=None,
    )
    assert follow_bridge["bridge"] is None
    assert "bridge_forbidden" in follow_bridge["reasons"]

    missing_bridge = validate_turn_pairing(
        student_point="maps",
        acknowledgment="Maps.",
        bridge=None,
        acknowledgment_mode="brief",
        action="switch",
        bridge_hint="what they keep spending free time on",
    )
    assert missing_bridge["passed"] is False
    assert "bridge_required" in missing_bridge["reasons"]


def test_question_writer_prompt_v4_is_loaded_and_v3_remains():
    assert (_PROMPTS / "v4" / "system.txt").is_file()
    assert (_PROMPTS / "v3" / "system.txt").is_file()
    prompt = (_PROMPTS / "v4" / "system.txt").read_text(encoding="utf-8")
    assert "student_point" in prompt
    assert "planner_decision.acknowledgment" in prompt
    assert '"v4"' in inspect.getsource(QuestionWriter.write)


@pytest.mark.asyncio
async def test_local_fallback_writer_still_raises_for_the_question_shape():
    with pytest.raises(RuntimeError, match="azure_openai_not_configured"):
        await LocalFallbackLLM().structured(
            "writer", "question_writer", "v4", QuestionResponse, {}
        )
