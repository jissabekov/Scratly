"""Deterministic stage and question-target policy (V1 anchors)."""

from __future__ import annotations

from dataclasses import dataclass
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


@dataclass(frozen=True)
class Target:
    kind: str
    key: str
    fallback_template: str


def select_next(candidates: list[Target]) -> Target | None:
    order = {v: i for i, v in enumerate(PRIORITY)}
    return (
        min(
            candidates,
            key=lambda x: (
                order.get(x.kind, len(PRIORITY)),
                _ANCHOR_RANK.get(x.key, _ANCHOR_RANK_FALLBACK),
                x.key,
            ),
        )
        if candidates
        else None
    )


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
