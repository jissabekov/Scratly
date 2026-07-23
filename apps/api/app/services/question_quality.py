"""Application-side question quality gate before persist."""

from __future__ import annotations

import re

from app.services.elicitation_policy import (
    build_elicitation_spec,
    elicitation_options_present,
)
from app.services.question_policy import (
    Target,
    contradiction_fallback,
    required_fallback,
)

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

    if target.kind == "elicitation":
        spec = build_elicitation_spec(target.key)
        if not elicitation_options_present(text, spec):
            text = spec.fallback_template
            outcome = "seeded_override"
            reason = "elicitation_missing_options"

    if _MULTI_QUESTION.search(text):
        if target.kind != "elicitation":
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
    if target.kind == "elicitation":
        return build_elicitation_spec(target.key).fallback_template
    if target.kind in {"required_hard_variable", "project_critical_unknown"}:
        return required_fallback(target.key)
    label = target.key.replace("_", " ")
    alternates = {
        "provisional_dimension": (
            f"Can you share a recent example that shows your {label} preference in action?"
        ),
        "project_discrimination": (
            f"Which option for {label} would make you more excited to start tomorrow?"
        ),
        "profile_validation": (
            "Looking at what we've covered so far, what feels most accurate — and what would you change?"
        ),
        "location_constraint": required_fallback("constraints:geo"),
    }
    return alternates.get(target.kind, target.fallback_template)


def _near_duplicate(a: str, b: str) -> bool:
    na = _norm(a)
    nb = _norm(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    ta, tb = set(na.split()), set(nb.split())
    if not ta or not tb:
        return False
    overlap = len(ta & tb) / max(len(ta | tb), 1)
    return overlap >= 0.92


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())
