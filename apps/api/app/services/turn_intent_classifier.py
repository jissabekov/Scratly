"""Turn intent classification (structured LLM + heuristic fallback)."""

from __future__ import annotations

import re

from app.contracts import PrimaryIntent, QuestionTopic, TurnIntentPacket

_QUESTION_MARKERS = re.compile(
    r"(\?|what do you mean|why are you asking|what do you know about me|"
    r"what does .+ mean|how does this work|what'?s my profile|"
    r"can you explain|why ask)",
    re.IGNORECASE,
)
_OUT_OF_SCOPE = re.compile(
    r"(write (my|an|the|me)?\s*(history |english |math )?(essay|paper|homework)|"
    r"solve (this|my) |what is the capital of|help me with math|translate this)",
    re.IGNORECASE,
)
_PROFILE_ASK = re.compile(
    r"(what do you know about me|my profile|what have you learned|"
    r"summarize (what you know|my preferences))",
    re.IGNORECASE,
)
_PROJECT_ASK = re.compile(
    r"(how (do|does) (project|matching)|when (do|will) (i|we) get a project|"
    r"what projects)",
    re.IGNORECASE,
)


def heuristic_classify(text: str) -> TurnIntentPacket:
    raw = (text or "").strip()
    out_of_scope = bool(_OUT_OF_SCOPE.search(raw))
    is_question = bool(_QUESTION_MARKERS.search(raw)) or raw.endswith("?")

    if out_of_scope and is_question:
        return TurnIntentPacket(
            primary_intent=PrimaryIntent.STUDENT_QUESTION,
            question_topic=QuestionTopic.OUT_OF_SCOPE,
            confidence=0.7,
            question_span=raw[:200],
        )
    if out_of_scope:
        return TurnIntentPacket(
            primary_intent=PrimaryIntent.STUDENT_QUESTION,
            question_topic=QuestionTopic.OUT_OF_SCOPE,
            confidence=0.65,
            question_span=raw[:200],
        )

    topic = QuestionTopic.NONE
    if _PROFILE_ASK.search(raw):
        topic = QuestionTopic.PROFILE
    elif _PROJECT_ASK.search(raw):
        topic = QuestionTopic.PROJECT
    elif is_question:
        topic = QuestionTopic.PROCESS

    if is_question and len(raw.split()) > 12 and not raw.strip().endswith("?"):
        # Likely mixed: long answer that also asks something.
        return TurnIntentPacket(
            primary_intent=PrimaryIntent.MIXED,
            question_topic=topic if topic != QuestionTopic.NONE else QuestionTopic.PROCESS,
            confidence=0.55,
            assessment_span=raw[:200],
            question_span=raw[:200],
        )
    if is_question and topic != QuestionTopic.NONE:
        # Short question-only if mostly interrogative and short.
        words = raw.split()
        if len(words) <= 20 or raw.count("?") >= 1 and len(words) <= 40:
            # If it also contains preference language, treat as mixed.
            preference_hints = re.search(
                r"\b(i (like|prefer|want|need|am)|my (constraint|topic))\b",
                raw,
                re.IGNORECASE,
            )
            if preference_hints and len(words) > 15:
                return TurnIntentPacket(
                    primary_intent=PrimaryIntent.MIXED,
                    question_topic=topic,
                    confidence=0.6,
                )
            return TurnIntentPacket(
                primary_intent=PrimaryIntent.STUDENT_QUESTION,
                question_topic=topic,
                confidence=0.7,
                question_span=raw[:200],
            )

    return TurnIntentPacket(
        primary_intent=PrimaryIntent.ASSESSMENT_CONTRIBUTION,
        question_topic=QuestionTopic.NONE,
        confidence=0.6,
        assessment_span=raw[:200],
    )


class TurnIntentClassifier:
    def __init__(self, llm):
        self.llm = llm

    async def classify(self, context: dict) -> TurnIntentPacket:
        text = ""
        msg = context.get("student_message") or {}
        if isinstance(msg, dict):
            text = msg.get("content") or ""
        try:
            return await self.llm.structured(
                "analyzer", "turn_intent", "v1", TurnIntentPacket, context
            )
        except Exception:
            return heuristic_classify(text)
