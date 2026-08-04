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
    should_offer_options,
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
from app.services.project_composer import ProjectComposer
from app.services.turn_processor import _post_match_reply
from app.services.turn_intent_classifier import TurnIntentClassifier
from app.services.web_research_client import WebResearchClient
from app.repository.assessment import _profile_change_summary


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
    assert "personality label" in why_topics.text.lower()
    assert "let's switch" in why_topics.text.lower()


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


async def test_obvious_assessment_answer_skips_intent_model_round_trip():
    class LLM:
        calls = 0

        async def structured(self, *args, **kwargs):
            self.calls += 1
            raise AssertionError("obvious assessment answer should use heuristic")

    llm = LLM()
    result = await TurnIntentClassifier(llm).classify(
        {"student_message": {"content": "I repair bikes with my teacher on Saturdays."}}
    )
    assert result.primary_intent == PrimaryIntent.ASSESSMENT_CONTRIBUTION
    assert llm.calls == 0


def test_answer_scope_gate_out_of_scope_without_default_question_cap():
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
    assert answer_scope_gate(process, consecutive_student_questions=20) is None
    capped = answer_scope_gate(
        process, consecutive_student_questions=2, max_consecutive=2
    )
    assert capped is not None and capped.refusal_reason_code == "consecutive_question_cap"

    seeded = seeded_student_answer(process, last_target_key="work_mode")
    assert seeded.mode.value == "answer"
    lowered = seeded.text.lower()
    assert "activity" in lowered and "enjoy" in lowered
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


def test_options_are_only_a_second_insufficient_answer_recovery():
    assert not should_offer_options(reply_signal="insufficient", attempts=1)
    assert should_offer_options(reply_signal="insufficient", attempts=2)
    assert should_offer_options(reply_signal="insufficient", attempts=3)
    assert should_offer_options(reply_signal="thin_answer", attempts=2)
    assert should_offer_options(reply_signal="substantive_answer", attempts=2, is_thin=True)
    assert not should_offer_options(reply_signal="substantive_answer", attempts=2, is_thin=False)


def test_infer_geo_from_text_nashville_and_chicago():
    from app.services.location_policy import infer_geo_from_text

    assert infer_geo_from_text("I'm in Nashville.") == "nashville"
    assert infer_geo_from_text("i live near Chicago") == "chicago"


def test_location_established_and_stage_gate():
    assert location_established_from_values(["seattle_metro"])
    assert not location_established_from_values(["evening_only"])
    assert not location_established_from_values(["time_limited"])
    # Freeform city/state labels must count — otherwise we re-ask after answers
    # like "Bristow, Oklahoma" stored as constraints/oklahoma.
    assert location_established_from_values(["oklahoma"])
    assert location_established_from_values(["bristow"])
    profile = {
        "dimensions": [
            {"key": "constraints", "status": "supported", "value": "seattle_metro"}
        ]
    }
    assert location_established_from_profile(profile)
    freeform = {
        "dimensions": [
            {
                "key": "constraints",
                "status": "supported",
                "value": "oklahoma",
                "values": ["oklahoma"],
            }
        ],
        "constraints": {"geo": [], "details": ["oklahoma"], "status": "supported"},
    }
    assert location_established_from_profile(freeform)
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


def test_irrelevant_catalog_opportunity_is_not_eligible():
    matches = rank_opportunities(
        {
            "topics": ["bike_repair"],
            "work_modes": {"build": 4},
            "motivations": ["impact_usefulness"],
            "geo_regions": ["remote_ok"],
        },
        [{
            "id": "generic-docs",
            "key": "generic-docs",
            "topics": ["documentation"],
            "work_modes": ["build"],
            "motivations": ["impact_usefulness"],
            "geo_regions": ["remote_ok"],
        }],
    )
    assert not matches[0].eligible
    assert "topic_mismatch" in matches[0].failed_constraints


def test_profile_change_summary_separates_real_changes_from_evidence_yield():
    before = {"dimensions": [{"key": "topics", "status": "unknown"}]}
    after = {
        "dimensions": [{"key": "topics", "status": "provisional"}],
        "interests": [{"topic": "bike_repair"}],
    }
    summary = _profile_change_summary(before, after)
    assert summary["change_count"] > 0
    assert summary["resolved_unknown_keys"] == ["topics"]
    assert summary["status_transitions"] == [
        {"key": "topics", "before": "unknown", "after": "provisional"}
    ]


def test_post_match_reply_is_contextual_to_feedback_and_project():
    projects = [
        {"title": "Neighborhood Bike Repair Guide"},
        {"title": "Supervised Repair Log"},
    ]
    scoped = _post_match_reply("Can we make the first option smaller?", projects)
    selected = _post_match_reply("I choose the first one", projects)
    selected_second = _post_match_reply("Actually I pick the second option", projects)
    assert "scope change" in scoped
    assert "Neighborhood Bike Repair Guide" in scoped
    assert "selection feedback" in selected
    assert "Supervised Repair Log" in selected_second


async def test_research_keeps_partial_success_when_another_query_fails():
    class Response:
        output = [{
            "type": "web_search_call",
            "action": {"sources": [{"url": "https://example.org/source"}]},
        }]

    class LLM:
        async def web_search(self, query, user_location=None):
            if "second" in query:
                raise RuntimeError("provider failure")
            return Response()

    client = WebResearchClient(LLM())
    queries, findings, error = await client.research(
        profile={"topics": ["first", "second"]},
        geo={"geo_places": ["seattle"], "geo_regions": []},
    )
    assert len(queries) == 2
    assert [item.url for item in findings] == ["https://example.org/source"]
    assert error is None


async def test_research_findings_can_seed_two_grounded_topic_relevant_options():
    class LLM:
        async def structured(self, *args, **kwargs):
            raise RuntimeError("use deterministic fallback")

    findings = [
        {"id": str(uuid4()), "title": "Bike source A", "snippet": "Repair access"},
        {"id": str(uuid4()), "title": "Bike source B", "snippet": "Safety checks"},
    ]
    accepted, rejected = await ProjectComposer(LLM()).compose(
        {
            "profile": {"topics": ["bike_repair"]},
            "opportunities": [],
            "research_findings": findings,
        }
    )
    assert len(accepted) == 2
    assert not rejected
    assert all(project.topic_keys == ["bike_repair"] for project in accepted)


def test_should_not_emit_legacy_location_dimension():
    from app.services.question_policy import should_emit_required

    assert should_emit_required("location", interests_ready=True) is False
    assert should_emit_required("location", interests_ready=False) is False
    assert should_emit_required("topics", interests_ready=False) is True


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
