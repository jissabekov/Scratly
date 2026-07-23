"""Application-side question quality gate before persist."""

from __future__ import annotations

import re
from typing import Any

from app.services.elicitation_policy import (
    build_elicitation_spec,
    elicitation_options_present,
)
from app.services.question_policy import (
    Target,
    contradiction_fallback,
    interest_depth_fallback,
    interest_depth_ready,
    required_fallback,
)

_GENERIC_CONTRADICTION = re.compile(
    r"i heard two different preferences", re.IGNORECASE
)
_MULTI_QUESTION = re.compile(r"\?\s+.+\?")
_INTERNAL_JARGON = re.compile(
    r"\b(provisional|supported|score_band|curated opportunities|"
    r"bounded web research|citation|dimension_key)\b",
    re.IGNORECASE,
)
_PREMATURE_PROJECT = re.compile(
    r"\b(gaming project|game project|mods? or tools|build (an |a )?app)\b",
    re.IGNORECASE,
)
_WORK_MODE_OPTION_LIST = re.compile(
    r"(figure|investigat|dig into|mak(e|ing)|build|fix|organiz|explain|communicat)"
    r".{0,80}"
    r"(figure|investigat|dig into|mak(e|ing)|build|fix|organiz|explain|communicat)",
    re.IGNORECASE,
)


def apply_question_quality_gate(
    *,
    question: str,
    target: Target,
    previous_assistant: str | None,
    value_a: str | None = None,
    value_b: str | None = None,
    azure_succeeded: bool = True,
    public_profile: dict[str, Any] | None = None,
    opening_mode: str | None = None,
) -> dict:
    """Return possibly rewritten question plus gate outcome.

    Outcomes: passed | regenerated | seeded_override
    """
    text = (question or "").strip()
    outcome = "passed"
    reason = "ok"

    if previous_assistant and _near_duplicate(text, previous_assistant):
        text = _seeded_for(target, value_a, value_b, public_profile)
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

    if _INTERNAL_JARGON.search(text):
        text = _seeded_for(target, value_a, value_b, public_profile)
        outcome = "seeded_override"
        reason = "internal_jargon"

    # Don't projectize shallow interests into "gaming project" style asks.
    if (
        target.key in {"topics", "work_mode"}
        and _PREMATURE_PROJECT.search(text)
        and not interest_depth_ready(public_profile)
    ):
        text = _seeded_for(target, value_a, value_b, public_profile)
        outcome = "seeded_override"
        reason = "premature_project_framing"

    # Interest-depth asks must not morph into work-mode A/B/C/D.
    # Also rewrite premature work_mode asks while interest is still shallow.
    # Never rewrite elicitation banks — those are supposed to list the modes.
    if (
        target.kind != "elicitation"
        and _WORK_MODE_OPTION_LIST.search(text)
        and (target.key == "topics" or not interest_depth_ready(public_profile))
    ):
        text = interest_depth_fallback(_topic_label(public_profile))
        outcome = "seeded_override"
        reason = "topics_depth_became_work_mode"

    if opening_mode == "social_opener" and target.key == "topics":
        # Prefer warm open over cold survey phrasing on the first greeting turn.
        if not re.search(r"\b(hey|hi|hello|good to meet)\b", text, re.IGNORECASE):
            text = required_fallback("topics")
            outcome = "seeded_override"
            reason = "social_opener_needs_warmth"

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


def _topic_label(profile: dict[str, Any] | None) -> str | None:
    if not profile:
        return None
    for interest in profile.get("interests") or []:
        if isinstance(interest, dict) and interest.get("topic"):
            return str(interest["topic"])
    for dim in profile.get("dimensions") or []:
        if isinstance(dim, dict) and dim.get("key") == "topics" and dim.get("value"):
            return str(dim["value"])
    return None


def _seeded_for(
    target: Target,
    value_a: str | None,
    value_b: str | None,
    public_profile: dict[str, Any] | None = None,
) -> str:
    if target.kind == "contradiction":
        return contradiction_fallback(target.key, value_a, value_b)
    if target.kind == "elicitation":
        return build_elicitation_spec(target.key).fallback_template
    if target.key == "topics" and target.kind in {
        "project_critical_unknown",
        "provisional_dimension",
    }:
        return interest_depth_fallback(_topic_label(public_profile))
    if target.kind in {"required_hard_variable", "project_critical_unknown"}:
        return required_fallback(target.key)
    label = target.key.replace("_", " ")
    alternates = {
        "provisional_dimension": (
            interest_depth_fallback(_topic_label(public_profile))
            if target.key == "topics"
            else (
                f"Can you share a recent example that shows what {label} looks like "
                f"for you day to day?"
            )
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
