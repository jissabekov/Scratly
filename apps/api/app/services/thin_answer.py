"""Deterministic thin-answer detection for elicitation."""

from __future__ import annotations

import re

from app.contracts import ThinAnswerSignal

_THIN_PATTERNS = re.compile(
    r"^\s*(idk|i don'?t know|dont know|don'?t know|maybe|sure|ok|okay|"
    r"idk lol|not sure|no idea|whatever|same|y(?:eah|ep)?|nah|hmm+)\s*[.!?]*\s*$",
    re.IGNORECASE,
)


def evaluate_thin_answer(
    text: str,
    *,
    accepted_evidence_count: int,
    primary_intent: str,
    pending_contradiction: bool = False,
) -> ThinAnswerSignal:
    """Return whether the assessment answer is too thin to advance coverage."""
    reasons: list[str] = []
    if primary_intent in {"student_question", "meta_refusal"}:
        return ThinAnswerSignal(is_thin=False, reason_codes=["not_assessment_path"])
    if pending_contradiction:
        # Explicit A/B picks on contradiction turns are handled elsewhere.
        pass

    tokens = [t for t in re.split(r"\s+", (text or "").strip()) if t]
    if len(tokens) <= 4:
        reasons.append("short_token_count")
    if _THIN_PATTERNS.match(text or ""):
        reasons.append("idk_or_minimal_pattern")
    if accepted_evidence_count == 0 and primary_intent == "assessment_contribution":
        reasons.append("zero_accepted_evidence")

    # Thin if pattern/short OR (zero evidence on assessment contribution with short text)
    is_thin = False
    if "idk_or_minimal_pattern" in reasons:
        is_thin = True
    elif "short_token_count" in reasons and "zero_accepted_evidence" in reasons:
        is_thin = True
    elif "short_token_count" in reasons and len(tokens) <= 2:
        is_thin = True

    return ThinAnswerSignal(is_thin=is_thin, reason_codes=reasons)
