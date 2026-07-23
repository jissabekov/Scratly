"""V1 student model: reducer, matching gates, anchors, thin greetings."""

from uuid import uuid4

from app.contracts import (
    Polarity,
    PrimaryIntent,
    ProposedEvidence,
    QuestionTopic,
    TurnIntentPacket,
    ValidatedEvidence,
)
from app.services.opportunity_matcher import rank_opportunities
from app.services.profile_reducer import reduce_profile
from app.services.project_matcher import rank_projects
from app.services.question_policy import Target, required_fallback, select_next
from app.services.thin_answer import evaluate_thin_answer
from app.services.student_answerer import seeded_student_answer


def _ev(
    dimension: str,
    value: str,
    *,
    score_band: int | None = None,
    strength: float = 0.8,
    polarity: str = "support",
    quote: str = "exact quote",
) -> ValidatedEvidence:
    mid = uuid4()
    return ValidatedEvidence(
        dimension_key=dimension,
        value_key=value,
        strength=strength,
        score_band=score_band,
        polarity=Polarity(polarity),
        source_message_ids=[mid],
        exact_source_quote=quote,
        rationale="test",
        accepted=True,
    )


def test_reducer_unknown_not_zero_for_missing_work_mode():
    profile = reduce_profile(
        [
            _ev("topics", "basketball", score_band=4, quote="I play basketball weekly"),
            _ev("work_mode", "investigate", score_band=3, quote="I dig into stats"),
            _ev("work_mode", "communicate", score_band=4, quote="I make highlight videos"),
        ]
    )
    modes = profile.profile.work_modes
    assert modes.investigate == 3
    assert modes.communicate == 4
    assert modes.organize is None
    assert modes.build is None
    assert profile.reducer_version == "v2"


def test_reducer_motivation_primary_secondary():
    profile = reduce_profile(
        [
            _ev(
                "motivation",
                "competition_achievement",
                score_band=4,
                quote="I want to beat the baseline",
            ),
            _ev(
                "motivation",
                "recognition_influence",
                score_band=3,
                quote="I want people to notice",
            ),
        ]
    )
    assert profile.profile.motivation.primary == "competition_achievement"
    assert profile.profile.motivation.secondary == "recognition_influence"


def test_reducer_assets_have_no_numeric_score():
    profile = reduce_profile(
        [_ev("assets", "brother coaches youth basketball", quote="my brother coaches")]
    )
    assert "brother coaches youth basketball" in profile.profile.assets


def test_execution_gate_fail_known_zero_pass_unknown():
    opp = {
        "id": "1",
        "key": "youth_network",
        "topics": ["basketball"],
        "work_modes": ["organize", "communicate"],
        "motivations": ["impact_usefulness"],
        "geo_regions": ["remote_ok"],
        "geo_places": [],
        "hard_constraints": {"outreach_willingness": 3},
    }
    fail_profile = {
        "topics": ["basketball"],
        "work_modes": {"organize": 3, "communicate": 3, "investigate": None, "build": None},
        "motivations": ["impact_usefulness"],
        "primary_reward": "impact_usefulness",
        "execution": {"outreach_willingness": 0},
        "geo_regions": ["remote_ok"],
        "geo_places": [],
        "constraints": {},
        "capability_gaps": [],
    }
    unknown_profile = {
        **fail_profile,
        "execution": {"outreach_willingness": None},
    }
    failed = rank_opportunities(fail_profile, [opp])[0]
    unknown = rank_opportunities(unknown_profile, [opp])[0]
    assert not failed.eligible and "outreach_willingness" in failed.failed_constraints
    assert unknown.eligible


def test_capabilities_scaffold_not_eligibility():
    project = {
        "id": "p1",
        "topics": ["technology"],
        "work_modes": ["build"],
        "motivations": ["discovery_mastery"],
        "hard_constraints": {},
    }
    profile = {
        "topics": ["technology"],
        "work_modes": {"build": 3, "investigate": None, "organize": None, "communicate": None},
        "motivations": ["discovery_mastery"],
        "primary_reward": "discovery_mastery",
        "execution": {},
        "constraints": {},
        "capability_gaps": ["coding"],
    }
    match = rank_projects(profile, [project])[0]
    assert match.eligible
    assert "scaffold:coding" in match.scope_adjustments


def test_anchor_order_prefers_topics_first():
    targets = [
        Target("required_hard_variable", "constraints", required_fallback("constraints")),
        Target("required_hard_variable", "execution", required_fallback("execution")),
        Target("required_hard_variable", "topics", required_fallback("topics")),
        Target("required_hard_variable", "work_mode", required_fallback("work_mode")),
        Target("required_hard_variable", "motivation", required_fallback("motivation")),
    ]
    assert select_next(targets).key == "topics"


def test_greeting_not_thin_before_first_question():
    thin = evaluate_thin_answer(
        "hello",
        accepted_evidence_count=0,
        primary_intent="assessment_contribution",
        prior_assistant_questions=0,
    )
    assert not thin.is_thin
    assert "social_opener" in thin.reason_codes

    mid = evaluate_thin_answer(
        "idk",
        accepted_evidence_count=0,
        primary_intent="assessment_contribution",
        prior_assistant_questions=1,
    )
    assert mid.is_thin


def test_process_answer_mentions_course_project():
    packet = TurnIntentPacket(
        primary_intent=PrimaryIntent.STUDENT_QUESTION,
        question_topic=QuestionTopic.PROCESS,
    )
    answer = seeded_student_answer(
        packet,
        student_text="do u have a mission, why are u asking?",
        last_target_key="topics",
    )
    lowered = answer.text.lower()
    assert "course" in lowered or "project" in lowered
