"""Scoped student answers for process/profile/project questions only."""

from __future__ import annotations

from uuid import UUID

from app.contracts import (
    QuestionTopic,
    StudentAnswerMode,
    StudentAnswerOutput,
    TurnIntentPacket,
)

_PROCESS_TEMPLATES = {
    "work_mode": (
        "Work mode means how you prefer to get things done — for example alone, "
        "with a small group, or mixed depending on the task. I'll ask about that "
        "so we can match a project that fits how you work."
    ),
    "default": (
        "This conversation maps your interests, constraints, and working style. "
        "I ask one focused question at a time so we can build an explainable profile "
        "before suggesting projects."
    ),
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
            if d.get("status") in {"established", "provisional"} and d.get("value")
        ]
        fields = [d.get("key") for d in dims if d.get("key")]
        if not known:
            text = (
                "We do not have established preferences yet — that is expected early on. "
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
    # process
    key = last_target_key or "default"
    text = _PROCESS_TEMPLATES.get(key, _PROCESS_TEMPLATES["default"])
    if last_target_key and last_target_key != "profile":
        text = (
            f"I asked about {last_target_key.replace('_', ' ')} because it helps "
            f"match a realistic project. {text}"
        )
    return StudentAnswerOutput(mode=StudentAnswerMode.ANSWER, text=text)


class StudentAnswerer:
    def __init__(self, llm):
        self.llm = llm

    async def answer(self, context: dict) -> StudentAnswerOutput:
        try:
            return await self.llm.structured(
                "writer", "student_answerer", "v1", StudentAnswerOutput, context
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
            )
