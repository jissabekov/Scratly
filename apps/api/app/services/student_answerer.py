"""Scoped student answers for process/profile/project questions only."""

from __future__ import annotations

import re
from uuid import UUID

from app.contracts import (
    QuestionTopic,
    StudentAnswerMode,
    StudentAnswerOutput,
    TurnIntentPacket,
)

_PURPOSE = (
    "I'm here to help you find a real course project — something you could build "
    "as an app, product, or website. I ask a few questions about what you're into "
    "and how you like to spend time, then look for options that fit."
)

_PROCESS_TEMPLATES = {
    "topics": (
        "I just mean how you choose to spend your time when nobody is assigning you anything. "
        "Games absolutely count."
    ),
    "motivation": (
        "I'm trying to learn what kind of win matters most to you — mastering something, "
        "beating a target, helping people, being noticed, or people counting on you."
    ),
    "work_mode": (
        "I mean the part of an activity you naturally enjoy doing. I worded that badly."
    ),
    "execution": (
        "I'm checking practical fit — like sticking with hard stuff, unclear goals, "
        "reaching out to people, or presenting in public — so we don't suggest something "
        "that fights how you work."
    ),
    "execution:outreach_willingness": (
        "Just checking whether contacting people outside school should be a core part "
        "of the project, or stay optional."
    ),
    "execution:public_visibility": (
        "Just checking how public you're comfortable being with demos or presentations."
    ),
    "constraints": (
        "Must-haves like deadline, tools, budget, or location keep suggestions realistic. "
        "We usually cover interests first."
    ),
    "constraints:geo": (
        "Where you're based (or if remote is fine) helps because some options are local."
    ),
    "assets": (
        "Unusual access — people, teams, datasets, equipment, communities — can unlock "
        "ideas a personality quiz would miss."
    ),
    "capability": (
        "Skills shape how much scaffolding we give — not whether you get a software "
        "project. You're here to learn."
    ),
    "default": _PURPOSE,
}

_REFUSAL_HOMEWORK = (
    "I can't help with homework or general tutoring here. "
    "I can explain how this works, what I've learned about your preferences so far, "
    "or how project matching works — then we'll continue."
)

_FRAMING_PUSHBACK = re.compile(
    r"("
    r"i (said|just).{0,24}play|"
    r"why .{0,80}(gaming |game )?(project|mod|build)|"
    r"not .{0,24}(a |the )?(gaming |game )?project|"
    r"don'?t assume"
    r")",
    re.IGNORECASE,
)


def is_framing_pushback(student_text: str | None) -> bool:
    return bool(_FRAMING_PUSHBACK.search(student_text or ""))


def answer_scope_gate(
    intent: TurnIntentPacket,
    *,
    consecutive_student_questions: int = 0,
    max_consecutive: int | None = None,
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
    if max_consecutive is not None and consecutive_student_questions >= max_consecutive:
        return StudentAnswerOutput(
            mode=StudentAnswerMode.REFUSE,
            text=(
                "Let's do one more discovery question so we keep learning what fits — "
                "you can ask again after that."
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
    lowered = (student_text or "").lower()

    if topic == QuestionTopic.OUT_OF_SCOPE:
        return StudentAnswerOutput(
            mode=StudentAnswerMode.REFUSE,
            text=_REFUSAL_HOMEWORK,
            refusal_reason_code="out_of_scope_homework_or_general",
        )

    # Framing pushback ("why gaming project?") — own the miss, stay conversational.
    if _FRAMING_PUSHBACK.search(lowered) and topic in {
        QuestionTopic.PROCESS,
        QuestionTopic.PROJECT,
        QuestionTopic.NONE,
    }:
        return StudentAnswerOutput(
            mode=StudentAnswerMode.ANSWER,
            text=(
                "Fair — I jumped ahead. Playing is enough to start; I'm just trying to "
                "understand what about it clicks for you, not assume you're building a project."
            ),
        )

    if topic == QuestionTopic.PROFILE:
        dims = (public_profile or {}).get("dimensions") or []
        known_labels: list[str] = []
        for d in dims:
            if d.get("status") not in {"supported", "provisional"} or not d.get("value"):
                continue
            key = str(d.get("key") or "").replace("_", " ")
            value = str(d.get("value")).replace("_", " ")
            known_labels.append(f"{key}: {value}")
        fields = [d.get("key") for d in dims if d.get("key")]
        if not known_labels:
            text = (
                "Still early — I don't have a clear read on your preferences yet. "
                "As you answer, I'll reflect what I'm learning."
            )
        else:
            text = "So far I've noted: " + "; ".join(known_labels[:6]) + "."
        return StudentAnswerOutput(
            mode=StudentAnswerMode.ANSWER,
            text=text,
            cited_profile_fields=[f for f in fields if f][:8],
        )
    if topic == QuestionTopic.PROJECT:
        return StudentAnswerOutput(
            mode=StudentAnswerMode.ANSWER,
            text=(
                "Project ideas come later, after I understand what you're into and where "
                "you're based. I won't invent options — they have to come from real sources."
            ),
        )
    # process — mission / purpose / why we ask
    asks_mission = any(
        token in lowered for token in ("mission", "purpose", "what are you for")
    )
    asks_why = bool(re.search(r"why (are|do) (you|u) ask|why ask", lowered))
    dim_text = _PROCESS_TEMPLATES.get(
        last_target_key or "default", _PROCESS_TEMPLATES["default"]
    )
    if asks_mission:
        text = _PURPOSE
        if last_target_key and last_target_key not in {"default", "profile"}:
            text = f"{_PURPOSE} {dim_text}"
    elif asks_why:
        text = dim_text
    elif last_target_key in {None, "default", "profile"}:
        text = _PROCESS_TEMPLATES["default"]
    else:
        text = dim_text
    return StudentAnswerOutput(mode=StudentAnswerMode.ANSWER, text=text)


class StudentAnswerer:
    def __init__(self, llm):
        self.llm = llm

    async def answer(self, context: dict) -> StudentAnswerOutput:
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
        student_text = (
            context.get("student_text")
            or context.get("latest_student_message")
            or ""
        )
        # Deterministic repair for framing pushback — don't let the model dump process jargon.
        if is_framing_pushback(student_text):
            return seeded_student_answer(
                packet,
                public_profile=context.get("public_profile_summary"),
                last_target_key=context.get("last_target_key"),
                student_text=student_text,
            )
        try:
            return await self.llm.structured(
                "writer", "student_answerer", "v2", StudentAnswerOutput, context
            )
        except Exception:
            return seeded_student_answer(
                packet,
                public_profile=context.get("public_profile_summary"),
                last_target_key=context.get("last_target_key"),
                student_text=student_text,
            )
