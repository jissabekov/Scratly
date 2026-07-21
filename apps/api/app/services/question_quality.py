"""Application-side question quality gate before persist."""

from __future__ import annotations

import re

from app.services.question_policy import Target, contradiction_fallback

_GENERIC_CONTRADICTION = re.compile(
    r"i heard two different preferences", re.IGNORECASE
)
_MULTI_QUESTION = re.compile(r"\?\s+.+\?")


def apply_question_quality_gate(
    *,
    question: str,
    target: Target,
    previous_assistant: str | None,
    value_a: str | None = None,
    value_b: str | None = None,
    azure_succeeded: bool = True,
) -> dict:
    """Return possibly rewritten question plus gate outcome.

    Outcomes: passed | regenerated | seeded_override
    """
    text = (question or "").strip()
    outcome = "passed"
    reason = "ok"

    if previous_assistant and _near_duplicate(text, previous_assistant):
        text = _seeded_for(target, value_a, value_b)
        outcome = "seeded_override"
        reason = "near_duplicate_previous_assistant"

    if target.kind == "contradiction" and _GENERIC_CONTRADICTION.search(text):
        text = contradiction_fallback(target.key, value_a, value_b)
        outcome = "seeded_override"
        reason = "generic_contradiction_fallback"

    if _MULTI_QUESTION.search(text):
        # Keep the first question only.
        first = text.split("?")[0].strip() + "?"
        text = first
        if outcome == "passed":
            outcome = "regenerated"
        reason = "stacked_questions_trimmed"

    if (
        azure_succeeded
        and target.kind == "contradiction"
        and text == target.fallback_template
        and value_a
        and value_b
        and "two different preferences" in text.lower()
    ):
        text = contradiction_fallback(target.key, value_a, value_b)
        outcome = "seeded_override"
        reason = "template_leaked_with_known_sides"

    return {
        "question": text,
        "outcome": outcome,
        "reason": reason,
        "passed": outcome == "passed",
    }


def _seeded_for(target: Target, value_a: str | None, value_b: str | None) -> str:
    if target.kind == "contradiction":
        return contradiction_fallback(target.key, value_a, value_b)
    label = target.key.replace("_", " ")
    alternates = {
        "provisional_dimension": (
            f"Can you share a recent example that shows your {label} preference in action?"
        ),
        "required_hard_variable": (
            f"What is one non-negotiable detail about {label} for your project?"
        ),
        "project_critical_unknown": (
            f"If you had to choose one focus for {label} this month, what would it be?"
        ),
        "project_discrimination": (
            f"Which option for {label} would make you more excited to start tomorrow?"
        ),
        "profile_validation": (
            "Looking at what we've covered so far, what feels most accurate — and what would you change?"
        ),
    }
    return alternates.get(target.kind, target.fallback_template)


def _near_duplicate(a: str, b: str) -> bool:
    na = _norm(a)
    nb = _norm(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    # High overlap on token sets catches minor rephrases of the same ask.
    ta, tb = set(na.split()), set(nb.split())
    if not ta or not tb:
        return False
    overlap = len(ta & tb) / max(len(ta | tb), 1)
    return overlap >= 0.92


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())
