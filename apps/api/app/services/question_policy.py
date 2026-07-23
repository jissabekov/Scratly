"""Deterministic stage and question-target policy (V1 anchors).

Merges the local V1 anchor policy (priority order, discovery gating, seeded
fallbacks) with the adaptive-conversation PR's reply classification, decision
value scoring, and interview-phase derivation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.services.location_policy import location_established_from_profile

PRIORITY = (
    "contradiction",
    "required_hard_variable",
    "project_critical_unknown",
    "provisional_dimension",
    "project_discrimination",
    "profile_validation",
)

# 7-anchor discovery order: interests → depth → work-mode → motivation →
# execution → hard outreach/visibility/geo. Decision-impact unknowns win ties.
ANCHOR_KEY_ORDER = (
    "topics",
    "work_mode",
    "motivation",
    "execution",
    "execution:persistence",
    "execution:ambiguity_tolerance",
    "execution:outreach_willingness",
    "execution:public_visibility",
    "constraints",
    "constraints:geo",
    "capability",
    "assets",
)

# Required dims other than topics stay gated until interest depth is real.
_POST_INTEREST_REQUIRED = {
    "work_mode",
    "motivation",
    "execution",
    "constraints",
    "constraints:geo",
    "capability",
    "assets",
}

STAGES = (
    "discovery",
    "measurement",
    "gap_resolution",
    "profile_review",
    "project_matching",
    "complete",
)

GAP_RESOLUTION_ESTABLISHED = 0.5
PROFILE_REVIEW_ESTABLISHED = 0.9
MEASUREMENT_TOUCHED = 0.4

_ANCHOR_RANK = {k: i for i, k in enumerate(ANCHOR_KEY_ORDER)}
_ANCHOR_RANK_FALLBACK = len(ANCHOR_KEY_ORDER)

# Back-compat alias used by older tests/docs.
DISCOVERY_KEY_ORDER = ANCHOR_KEY_ORDER

# Base decision value per target kind (adaptive-conversation PR).
BASE_VALUE = {
    "behavioral_anchor": .20,
    "required_hard_variable": .18,
    "project_critical_unknown": .16,
    "project_discrimination": .14,
    "provisional_dimension": .10,
    "profile_validation": .05,
}


class ReplySignal(StrEnum):
    GREETING = "greeting"
    CORRECTION = "correction"
    INSUFFICIENT = "insufficient"
    THIN = "thin_answer"
    SUBSTANTIVE = "substantive_answer"


class InterviewPhase(StrEnum):
    BROAD_DISCOVERY = "broad_discovery"
    BEHAVIORAL_EVIDENCE = "behavioral_evidence"
    PREFERENCE_DISCRIMINATION = "preference_discrimination"
    UNCERTAINTY_RESOLUTION = "uncertainty_resolution"
    PROJECT_FIT_PROBING = "project_fit_probing"
    REFLECTIVE_VALIDATION = "reflective_validation"


@dataclass(frozen=True)
class QuestionValue:
    project_discrimination: float = 0.0
    uncertainty_reduction: float = 0.0
    evidence_weakness: float = 0.0
    contradiction_resolution: float = 0.0
    conversational_relevance: float = 0.0
    novelty: float = 0.0
    repetition_penalty: float = 0.0
    leading_penalty: float = 0.0
    sensitivity_penalty: float = 0.0
    fatigue_penalty: float = 0.0


@dataclass(frozen=True)
class Target:
    kind: str
    key: str
    fallback_template: str
    # Adaptive-conversation decision-value fields (optional; default preserves
    # the V1 anchor-priority behavior when not supplied).
    information_gain: float = 0.5  # compatibility alias for early repositories
    continuity: float = 0.0
    asked_count: int = 0
    value: QuestionValue = field(default_factory=QuestionValue)
    target_dimensions: tuple[str, ...] = ()
    project_modes: tuple[str, ...] = ()


def classify_reply(text: str) -> ReplySignal:
    """Dialogue routing only: these cues never become assessment evidence."""
    normalized = " ".join((text or "").lower().split())
    if normalized in {"hi", "hello", "hey", "hiya", "yo"}:
        return ReplySignal.GREETING
    if any(
        cue in normalized
        for cue in (
            "i said",
            "that's not",
            "that is not",
            "you assumed",
            "why are you asking",
            "not what i",
        )
    ):
        return ReplySignal.CORRECTION
    if normalized in {
        "idk",
        "i don't know",
        "dont know",
        "dunno",
        "no idea",
        "nothing",
        "nothin",
    }:
        return ReplySignal.INSUFFICIENT
    if len(normalized.split()) <= 4:
        return ReplySignal.THIN
    return ReplySignal.SUBSTANTIVE


def question_value(target: Target) -> float:
    """Auditable V1 proxy for expected reduction in project-decision uncertainty."""
    value = target.value
    positive = (
        .30 * value.project_discrimination
        + .25 * max(value.uncertainty_reduction, target.information_gain)
        + .15 * value.evidence_weakness
        + .15 * value.contradiction_resolution
        + .10 * max(value.conversational_relevance, target.continuity)
        + .05 * value.novelty
    )
    penalties = (
        value.repetition_penalty
        + value.leading_penalty
        + value.sensitivity_penalty
        + value.fatigue_penalty
        + min(target.asked_count * .15, .6)
    )
    return round(BASE_VALUE.get(target.kind, 0.0) + positive - penalties, 6)


def select_next(candidates: list[Target]) -> Target | None:
    """Repair first, then contradictions; otherwise maximize decision value.

    Ties break by the V1 anchor order then key so the documented discovery
    sequence (topics → work-mode → …) is preserved when values are equal.
    """
    if not candidates:
        return None
    repair = [c for c in candidates if c.kind == "conversation_repair"]
    contradictions = [c for c in candidates if c.kind == "contradiction"]
    pool = repair or contradictions or candidates
    return min(
        pool,
        key=lambda x: (
            -question_value(x),
            _ANCHOR_RANK.get(x.key, _ANCHOR_RANK_FALLBACK),
            x.key,
        ),
    )


def derive_phase(
    *,
    anchors_observed: int,
    strong_evidence: int,
    contradictions: int,
    project_modes: int,
    reviewed: bool,
) -> InterviewPhase:
    if reviewed:
        return InterviewPhase.REFLECTIVE_VALIDATION
    if contradictions:
        return InterviewPhase.UNCERTAINTY_RESOLUTION
    if anchors_observed < 2:
        return InterviewPhase.BROAD_DISCOVERY
    if strong_evidence < 3:
        return InterviewPhase.BEHAVIORAL_EVIDENCE
    if project_modes < 2:
        return InterviewPhase.PREFERENCE_DISCRIMINATION
    return InterviewPhase.PROJECT_FIT_PROBING


def derive_stage(
    *,
    contradictions: int,
    reviewed: bool,
    projects_ready: bool,
    coverage_established: float | None = None,
    coverage_touched: float | None = None,
    coverage: float | None = None,
    location_ready: bool | None = None,
) -> str:
    """Derive stage from supported coverage and open true contradictions.

    Legacy callers may pass ``coverage`` (treated as supported/established).
    Contested dims contribute only to ``coverage_touched``.

    ``project_matching`` requires reviewed + location_ready (when provided).
    """
    established = (
        coverage
        if coverage_established is None and coverage is not None
        else (coverage_established or 0.0)
    )
    touched = established if coverage_touched is None else coverage_touched

    if projects_ready and reviewed:
        return "complete"
    if reviewed:
        if location_ready is False:
            return "profile_review"
        return "project_matching"
    if established >= PROFILE_REVIEW_ESTABLISHED and contradictions == 0:
        return "profile_review"
    if contradictions > 0 and established >= GAP_RESOLUTION_ESTABLISHED:
        return "gap_resolution"
    if touched >= MEASUREMENT_TOUCHED:
        return "measurement"
    return "discovery"


def location_ready(profile: dict) -> bool:
    return location_established_from_profile(profile)


def interest_depth_ready(profile: dict[str, Any] | None) -> bool:
    """True once we have enough interest depth to leave discovery-of-topics.

    Matches the documented 7-anchor order: warm open → interest depth → work-mode.
    A single casual mention ("playing videogames") stays provisional/shallow and
    must be deepened before other required dims (especially work_mode).
    """
    if not profile:
        return False
    dims = {
        d.get("key"): d
        for d in (profile.get("dimensions") or [])
        if isinstance(d, dict) and d.get("key")
    }
    topics = dims.get("topics") or {}
    status = topics.get("status")
    if status in {"supported", "contradicted"}:
        return True

    interests = profile.get("interests") or []
    best_score = -1
    best_evidence = 0
    for item in interests:
        if not isinstance(item, dict):
            continue
        score = item.get("score")
        if score is None:
            continue
        score_i = int(score)
        evidence = int(item.get("evidence_count") or 0)
        if score_i > best_score or (
            score_i == best_score and evidence > best_evidence
        ):
            best_score = score_i
            best_evidence = evidence

    # Need repeated behavioral signal — a single casual mention stays shallow.
    if best_score >= 2 and best_evidence >= 2:
        return True
    if best_score >= 3 and best_evidence >= 2:
        return True
    return False


def should_emit_required(key: str, *, interests_ready: bool) -> bool:
    """Gate post-interest required asks until interest depth is ready."""
    if key == "topics":
        return True
    if key in _POST_INTEREST_REQUIRED:
        return interests_ready
    return True


def contradiction_fallback(
    dimension_key: str, value_a: str | None, value_b: str | None
) -> str:
    """Seeded contradiction wording that names the concrete options."""
    label = dimension_key.replace("_", " ")
    if value_a and value_b:
        return (
            f"For {label}, do you lean more toward {value_a.replace('_', ' ')} "
            f"or {value_b.replace('_', ' ')} — or both in different situations?"
        )
    if value_a:
        return (
            f"For {label}, is {value_a.replace('_', ' ')} still the preference "
            f"you want to prioritize?"
        )
    return f"For {label}, which preference is closer to what you want now?"


_REQUIRED_FALLBACKS = {
    "topics": (
        "Hey — good to meet you. When you've had free time lately, what have you "
        "actually been spending it on?"
    ),
    "work_mode": (
        "When you're into something you care about, what usually pulls you in most — "
        "figuring out how it works, making or fixing things, getting people organized, "
        "or explaining it so others get it?"
    ),
    "motivation": (
        "If something you care about went really well, which outcome would matter most — "
        "mastering something hard, beating a target, helping someone, being noticed, "
        "or people counting on you?"
    ),
    "execution": (
        "What's something difficult you kept working at after it became frustrating "
        "or boring?"
    ),
    "execution:persistence": (
        "What's something difficult you kept working at after it became frustrating "
        "or boring?"
    ),
    "execution:ambiguity_tolerance": (
        "If I said 'find a way to make something useful in your area' with no steps, "
        "does that sound interesting or annoying — and what would you do first?"
    ),
    "execution:outreach_willingness": (
        "How comfortable would you be emailing an organization you've never talked to?"
    ),
    "execution:public_visibility": (
        "How do you feel about eventually presenting your work publicly — class only, "
        "outside orgs, or a bigger pitch/demo?"
    ),
    "constraints": (
        "Any must-haves I should keep in mind — deadline, tools, budget, or other limits?"
    ),
    "constraints:geo": (
        "Where are you based (city or region), or is remote fine too?"
    ),
    "capability": "What skills or tools are you already comfortable using?",
    "assets": (
        "Do you have any unusual access that could help — people, teams, datasets, "
        "equipment, communities, or a job/hobby connection?"
    ),
}


def interest_depth_fallback(topic: str | None = None) -> str:
    """Behavioral depth ask — not a work-mode / project-framed question."""
    if topic:
        label = str(topic).replace("_", " ").strip()
        return (
            f"Got it — {label}. Is that more occasional, something you do a lot, "
            f"or something you get pretty deep into?"
        )
    return (
        "Got it. Is that more occasional, something you do a lot, "
        "or something you get pretty deep into?"
    )


def required_fallback(key: str) -> str:
    """Teen-friendly seeded ask for a required / discovery target key."""
    if key in _REQUIRED_FALLBACKS:
        return _REQUIRED_FALLBACKS[key]
    label = key.replace("_", " ").replace(":", " ")
    return f"What should I know about your {label}?"
