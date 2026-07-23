"""Unit tests for student UX, elicitation, location, and project citation gates."""

from uuid import uuid4

from app.contracts import (
    ComposedProjectPacket,
    PrimaryIntent,
    ProjectCitation,
    ProjectComposeOutput,
    QuestionTopic,
    TurnIntentPacket,
)
from app.services.elicitation_policy import (
    build_elicitation_spec,
    elicitation_options_present,
    elicitation_target,
)
from app.services.location_policy import (
    location_established_from_profile,
    location_established_from_values,
)
from app.services.opportunity_matcher import rank_opportunities
from app.services.project_citation_gate import filter_grounded_projects
from app.services.question_policy import Target, derive_stage, select_next, required_fallback
from app.services.question_quality import apply_question_quality_gate
from app.services.thin_answer import evaluate_thin_answer
from app.services.turn_intent_classifier import heuristic_classify
from app.services.student_answerer import answer_scope_gate, seeded_student_answer


def _req(key: str) -> Target:
    return Target("required_hard_variable", key, required_fallback(key))


def test_discovery_select_next_prefers_topics_over_constraints():
    targets = [
        _req("constraints"),
        _req("constraints:geo"),
        _req("motivation"),
        _req("topics"),
        _req("work_mode"),
        _req("execution"),
    ]
    assert select_next(targets).key == "topics"

    without_topics = [t for t in targets if t.key != "topics"]
    assert select_next(without_topics).key == "work_mode"

    without_work = [t for t in without_topics if t.key != "work_mode"]
    assert select_next(without_work).key == "motivation"

    without_motivation = [t for t in without_work if t.key != "motivation"]
    assert select_next(without_motivation).key == "execution"

    without_exec = [t for t in without_motivation if t.key != "execution"]
    assert select_next(without_exec).key == "constraints"

    geo_only = [t for t in without_exec if t.key != "constraints"]
    assert select_next(geo_only).key == "constraints:geo"


def test_required_fallback_avoids_non_negotiable_opener():
    for key in ("topics", "motivation", "work_mode", "constraints", "constraints:geo"):
        text = required_fallback(key).lower()
        assert "non-negotiable" not in text
    topics = required_fallback("topics").lower()
    assert "free time" in topics or "spending" in topics or "into" in topics
    assert "must-have" in required_fallback("constraints").lower() or "deadline" in required_fallback(
        "constraints"
    ).lower()
    assert "project" not in required_fallback("work_mode").lower()


def test_seeded_process_answer_states_course_project_purpose():
    process = TurnIntentPacket(
        primary_intent=PrimaryIntent.STUDENT_QUESTION,
        question_topic=QuestionTopic.PROCESS,
    )
    mission = seeded_student_answer(
        process,
        last_target_key="constraints",
        student_text="do u have a mission, why are u asking this question?",
    )
    assert mission.mode.value == "answer"
    lowered = mission.text.lower()
    assert "course" in lowered or "project opportunity" in lowered
    assert "app" in lowered or "website" in lowered or "product" in lowered

    why_topics = seeded_student_answer(
        process,
        last_target_key="topics",
        student_text="why are you asking this?",
    )
    assert "spend time" in why_topics.text.lower() or "interest" in why_topics.text.lower() or "into" in why_topics.text.lower()


def test_heuristic_student_question_and_homework_refusal():
    process_q = heuristic_classify("What does work mode mean?")
    assert process_q.primary_intent == PrimaryIntent.STUDENT_QUESTION
    assert process_q.question_topic == QuestionTopic.PROCESS

    homework = heuristic_classify("Write my history essay on Rome")
    assert homework.question_topic == QuestionTopic.OUT_OF_SCOPE

    assessment = heuristic_classify(
        "I like building air quality maps with Python and a couple of friends."
    )
    assert assessment.primary_intent == PrimaryIntent.ASSESSMENT_CONTRIBUTION


def test_answer_scope_gate_out_of_scope_and_cap():
    intent = TurnIntentPacket(
        primary_intent=PrimaryIntent.STUDENT_QUESTION,
        question_topic=QuestionTopic.OUT_OF_SCOPE,
    )
    refused = answer_scope_gate(intent)
    assert refused is not None and refused.mode.value == "refuse"

    process = TurnIntentPacket(
        primary_intent=PrimaryIntent.STUDENT_QUESTION,
        question_topic=QuestionTopic.PROCESS,
    )
    capped = answer_scope_gate(process, consecutive_student_questions=2)
    assert capped is not None and capped.refusal_reason_code == "consecutive_question_cap"

    seeded = seeded_student_answer(process, last_target_key="work_mode")
    assert seeded.mode.value == "answer"
    lowered = seeded.text.lower()
    assert "energiz" in lowered or "figuring" in lowered or "work" in lowered
    assert "investigate" not in lowered
    assert "curated opportunities" not in lowered


def test_thin_answer_idk_and_substantive():
    thin = evaluate_thin_answer(
        "idk",
        accepted_evidence_count=0,
        primary_intent="assessment_contribution",
    )
    assert thin.is_thin
    assert "idk_or_minimal_pattern" in thin.reason_codes

    ok = evaluate_thin_answer(
        "ok",
        accepted_evidence_count=0,
        primary_intent="assessment_contribution",
    )
    assert ok.is_thin

    question = evaluate_thin_answer(
        "idk",
        accepted_evidence_count=0,
        primary_intent="student_question",
    )
    assert not question.is_thin

    long = evaluate_thin_answer(
        "I prefer working with one or two friends on analysis and alone for coding.",
        accepted_evidence_count=2,
        primary_intent="assessment_contribution",
    )
    assert not long.is_thin


def test_elicitation_options_and_quality_gate():
    spec = build_elicitation_spec("work_mode")
    assert len(spec.options) >= 2
    target = elicitation_target("work_mode")
    assert target.kind == "elicitation"
    assert elicitation_options_present(spec.fallback_template, spec)

    gate = apply_question_quality_gate(
        question="What do you think?",
        target=target,
        previous_assistant=None,
    )
    assert gate["outcome"] == "seeded_override"
    assert elicitation_options_present(gate["question"], spec)


def test_location_established_and_stage_gate():
    assert location_established_from_values(["seattle_metro"])
    assert not location_established_from_values(["evening_only"])
    profile = {
        "dimensions": [
            {"key": "constraints", "status": "supported", "value": "seattle_metro"}
        ]
    }
    assert location_established_from_profile(profile)
    assert (
        derive_stage(
            coverage_established=0.95,
            contradictions=0,
            reviewed=True,
            projects_ready=False,
            location_ready=False,
        )
        == "profile_review"
    )
    assert (
        derive_stage(
            coverage_established=0.95,
            contradictions=0,
            reviewed=True,
            projects_ready=False,
            location_ready=True,
        )
        == "project_matching"
    )


def test_opportunity_geo_filter():
    profile = {
        "topics": ["data", "community"],
        "work_modes": ["analysis"],
        "motivations": ["impact"],
        "geo_regions": ["seattle_metro"],
        "geo_places": ["seattle"],
        "constraints": {},
        "capability_gaps": [],
    }
    opportunities = [
        {
            "id": str(uuid4()),
            "key": "local",
            "topics": ["data"],
            "work_modes": ["analysis"],
            "motivations": ["impact"],
            "geo_regions": ["seattle_metro"],
            "geo_places": ["seattle"],
            "hard_constraints": {},
        },
        {
            "id": str(uuid4()),
            "key": "elsewhere",
            "topics": ["data"],
            "work_modes": ["analysis"],
            "motivations": ["impact"],
            "geo_regions": ["nyc_metro"],
            "geo_places": ["brooklyn"],
            "hard_constraints": {},
        },
        {
            "id": str(uuid4()),
            "key": "remote",
            "topics": ["data"],
            "work_modes": ["analysis"],
            "motivations": ["impact"],
            "geo_regions": ["remote_ok"],
            "geo_places": [],
            "hard_constraints": {},
        },
    ]
    ranked = rank_opportunities(profile, opportunities)
    by_key = {m.opportunity_key: m for m in ranked}
    assert by_key["local"].eligible
    assert not by_key["elsewhere"].eligible
    assert "geo" in by_key["elsewhere"].failed_constraints
    assert by_key["remote"].eligible


def test_project_citation_gate_rejects_unknown():
    opp_id = uuid4()
    bad_id = uuid4()
    output = ProjectComposeOutput(
        projects=[
            ComposedProjectPacket(
                title="Good",
                summary="Uses a real opportunity.",
                citations=[ProjectCitation(kind="opportunity", id=opp_id)],
            ),
            ComposedProjectPacket(
                title="Bad",
                summary="Invented citation.",
                citations=[ProjectCitation(kind="opportunity", id=bad_id)],
            ),
        ]
    )
    accepted, rejected = filter_grounded_projects(
        output, opportunity_ids={opp_id}, research_finding_ids=set()
    )
    assert len(accepted) == 1 and accepted[0].title == "Good"
    assert len(rejected) == 1


def test_location_hard_variable_priority():
    targets = [
        Target("profile_validation", "z", "z"),
        Target("required_hard_variable", "constraints:geo", "Where based?"),
    ]
    assert select_next(targets).key == "constraints:geo"
