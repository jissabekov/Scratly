"""Deterministic thin-answer detection for elicitation (V1)."""

from __future__ import annotations

import re

from app.contracts import ThinAnswerSignal

_THIN_PATTERNS = re.compile(
    r"^\s*(idk|i don'?t know|dont know|don'?t know|maybe|sure|ok|okay|"
    r"idk lol|not sure|no idea|whatever|same|y(?:eah|ep)?|nah|hmm+)\s*[.!?]*\s*$",
    re.IGNORECASE,
)

_GREETING_PATTERNS = re.compile(
    r"^\s*(hi|hello|hey|yo|sup|good\s+(morning|afternoon|evening))"
    r"(\s|,|!|\.|$)",
    re.IGNORECASE,
)


def evaluate_thin_answer(
    text: str,
    *,
    accepted_evidence_count: int,
    primary_intent: str,
    pending_contradiction: bool = False,
    prior_assistant_questions: int = 0,
) -> ThinAnswerSignal:
    """Return whether the assessment answer is too thin to advance coverage.

    Greetings and social openers before any assessment question are never thin —
    they should get a warm open ask, not elicitation chips.
    """
    reasons: list[str] = []
    if primary_intent in {"student_question", "meta_refusal"}:
        return ThinAnswerSignal(is_thin=False, reason_codes=["not_assessment_path"])

    raw = (text or "").strip()
    tokens = [t for t in re.split(r"\s+", raw) if t]

    # First open: greetings / name intros are warm entry, not thin answers.
    if prior_assistant_questions == 0 and (
        _GREETING_PATTERNS.match(raw)
        or (
            len(tokens) <= 8
            and any(t.lower() in {"i'm", "im", "my", "name"} for t in tokens)
        )
    ):
        return ThinAnswerSignal(is_thin=False, reason_codes=["social_opener"])

    if pending_contradiction:
        pass

    if len(tokens) <= 4:
        reasons.append("short_token_count")
    if _THIN_PATTERNS.match(raw):
        reasons.append("idk_or_minimal_pattern")
    if accepted_evidence_count == 0 and primary_intent == "assessment_contribution":
        reasons.append("zero_accepted_evidence")

    is_thin = False
    if "idk_or_minimal_pattern" in reasons:
        is_thin = True
    elif "short_token_count" in reasons and "zero_accepted_evidence" in reasons:
        # Only treat as thin after we already asked something (mid-assessment).
        is_thin = prior_assistant_questions >= 1
        if is_thin:
            reasons.append("mid_assessment_short_empty")
    elif "short_token_count" in reasons and len(tokens) <= 2:
        is_thin = prior_assistant_questions >= 1
        if is_thin:
            reasons.append("mid_assessment_ultra_short")

    return ThinAnswerSignal(is_thin=is_thin, reason_codes=reasons)
