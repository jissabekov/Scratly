"""Scoped student answers for process/profile/project questions only."""

from __future__ import annotations

from uuid import UUID

from app.contracts import (
    QuestionTopic,
    StudentAnswerMode,
    StudentAnswerOutput,
    TurnIntentPacket,
)

_PURPOSE = (
    "I'm here to help you find a real project opportunity for your course — "
    "something you could build as an app, product, or website. "
    "I ask a few focused questions about what you're into, how you like to work, "
    "and any must-haves, then match you with grounded options."
)

_PROCESS_TEMPLATES = {
    "topics": (
        "I start with interests so we can match projects you'll actually want to "
        "build — then I dig into how deep that interest really is."
    ),
    "motivation": (
        "Motivation is your top reward drivers — like mastering something, beating "
        "a target, helping someone, being noticed, or people counting on you. "
        "That changes how we frame the project."
    ),
    "work_mode": (
        "Work modes are Investigate, Build, Organize, and Communicate — the kinds "
        "of project work that energize you. That shapes what the project asks you to do."
    ),
    "execution": (
        "Execution covers persistence, comfort with unclear goals, outreach, and "
        "public visibility — practical gates for what kinds of projects are feasible."
    ),
    "execution:outreach_willingness": (
        "Outreach willingness tells us whether contacting outside organizations "
        "can be a core part of the project — or should stay optional."
    ),
    "execution:public_visibility": (
        "Public visibility tells us how far to push demos, presentations, or publicity."
    ),
    "constraints": (
        "Must-haves like deadline, tools, budget, or location keep suggestions "
        "realistic. We usually cover interests and work style first."
    ),
    "constraints:geo": (
        "Where you're based (or if remote is fine) matters because many "
        "opportunities are local or place-specific."
    ),
    "assets": (
        "Assets are unusual access — people, orgs, datasets, equipment, communities — "
        "that can unlock projects a personality quiz would miss."
    ),
    "capability": (
        "Capabilities shape how much scaffolding we give — not whether you get a "
        "software project. You're here to learn."
    ),
    "default": _PURPOSE,
}

_REFUSAL_HOMEWORK = (
    "I can't help with homework or general tutoring here. "
    "I can explain how this assessment works, what we've learned about your "
    "preferences so far, or how project matching works — then we'll continue."
)


def answer_scope_gate(
    intent: TurnIntentPacket,
    *,
    consecutive_student_questions: int = 0,
    max_consecutive: int = 2,
) -> StudentAnswerOutput | None:
    """Return a forced refusal/redirect when scope or caps require it.

    Returns None when the answerer LLM (or seeded answer) should run.
    """
    topic = intent.question_topic
    if topic == QuestionTopic.OUT_OF_SCOPE:
        return StudentAnswerOutput(
            mode=StudentAnswerMode.REFUSE,
            text=_REFUSAL_HOMEWORK,
            refusal_reason_code="out_of_scope_homework_or_general",
        )
    if consecutive_student_questions >= max_consecutive:
        return StudentAnswerOutput(
            mode=StudentAnswerMode.REFUSE,
            text=(
                "Let's do one more discovery question so we keep building your "
                "profile — you can ask again after that."
            ),
            refusal_reason_code="consecutive_question_cap",
        )
    if topic not in {
        QuestionTopic.PROCESS,
        QuestionTopic.PROFILE,
        QuestionTopic.PROJECT,
    }:
        if intent.primary_intent.value in {"student_question", "mixed"}:
            return StudentAnswerOutput(
                mode=StudentAnswerMode.REFUSE,
                text=_REFUSAL_HOMEWORK,
                refusal_reason_code="out_of_scope_other",
            )
    return None


def validate_answer_citations(
    answer: StudentAnswerOutput,
    *,
    allowed_evidence_ids: set[UUID],
    allowed_profile_fields: set[str],
) -> StudentAnswerOutput:
    """Drop invented citations; refuse profile answers that claim fields without cites."""
    good_evidence = [i for i in answer.cited_evidence_ids if i in allowed_evidence_ids]
    good_fields = [f for f in answer.cited_profile_fields if f in allowed_profile_fields]
    if answer.mode == StudentAnswerMode.REFUSE:
        return answer.model_copy(
            update={
                "cited_evidence_ids": good_evidence,
                "cited_profile_fields": good_fields,
            }
        )
    # Profile-topic answers that assert fields should cite them.
    return answer.model_copy(
        update={
            "cited_evidence_ids": good_evidence,
            "cited_profile_fields": good_fields,
        }
    )


def seeded_student_answer(
    intent: TurnIntentPacket,
    *,
    public_profile: dict | None = None,
    last_target_key: str | None = None,
    student_text: str | None = None,
) -> StudentAnswerOutput:
    topic = intent.question_topic
    if topic == QuestionTopic.OUT_OF_SCOPE:
        return StudentAnswerOutput(
            mode=StudentAnswerMode.REFUSE,
            text=_REFUSAL_HOMEWORK,
            refusal_reason_code="out_of_scope_homework_or_general",
        )
    if topic == QuestionTopic.PROFILE:
        dims = (public_profile or {}).get("dimensions") or []
        known = [
            f"{d.get('key')}={d.get('value')}"
            for d in dims
            if d.get("status") in {"supported", "provisional"} and d.get("value")
        ]
        fields = [d.get("key") for d in dims if d.get("key")]
        if not known:
            text = (
                "We do not have supported preferences yet — that is expected early on. "
                "As you answer, I will reflect what we learn."
            )
        else:
            text = "So far I have noted: " + "; ".join(known[:6]) + "."
        return StudentAnswerOutput(
            mode=StudentAnswerMode.ANSWER,
            text=text,
            cited_profile_fields=[f for f in fields if f][:8],
        )
    if topic == QuestionTopic.PROJECT:
        return StudentAnswerOutput(
            mode=StudentAnswerMode.ANSWER,
            text=(
                "After your profile is stable and reviewed — including where you are based — "
                "we match curated opportunities and may run bounded web research. "
                "Suggested projects must cite those sources; we do not invent them."
            ),
        )
    # process — mission / purpose / why we ask
    lowered = (student_text or "").lower()
    asks_mission = any(
        token in lowered
        for token in ("mission", "purpose", "why are you", "why ask", "why are u")
    )
    dim_text = _PROCESS_TEMPLATES.get(
        last_target_key or "default", _PROCESS_TEMPLATES["default"]
    )
    if asks_mission or last_target_key in {None, "default", "profile"}:
        text = _PURPOSE if asks_mission else dim_text
        if asks_mission and last_target_key and last_target_key not in {
            "default",
            "profile",
        }:
            text = f"{_PURPOSE} {dim_text}"
    else:
        text = dim_text
    return StudentAnswerOutput(mode=StudentAnswerMode.ANSWER, text=text)


class StudentAnswerer:
    def __init__(self, llm):
        self.llm = llm

    async def answer(self, context: dict) -> StudentAnswerOutput:
        try:
            return await self.llm.structured(
                "writer", "student_answerer", "v2", StudentAnswerOutput, context
            )
        except Exception:
            intent = context.get("intent")
            if isinstance(intent, TurnIntentPacket):
                packet = intent
            elif isinstance(intent, dict):
                packet = TurnIntentPacket.model_validate(intent)
            else:
                packet = TurnIntentPacket(
                    primary_intent="student_question",
                    question_topic="process",
                )
            return seeded_student_answer(
                packet,
                public_profile=context.get("public_profile_summary"),
                last_target_key=context.get("last_target_key"),
                student_text=context.get("student_text")
                or context.get("latest_student_message"),
            )
