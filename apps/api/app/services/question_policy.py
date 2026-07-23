"""Deterministic stage and question-target policy (V1 anchors)."""

from dataclasses import dataclass

from app.services.location_policy import location_established_from_profile

PRIORITY = (
    "contradiction",
    "required_hard_variable",
    "project_critical_unknown",
    "provisional_dimension",
    "project_discrimination",
    "profile_validation",
)

# 7-anchor discovery order: interests → depth/work-mode → motivation →
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
        "Think about the last few months — when nobody was making you do anything, "
        "what have you spent the most time doing or learning about?"
    ),
    "work_mode": (
        "When something you care about needs fixing, which part pulls you in most — "
        "figuring out what's going on, building something that helps, getting people "
        "organized, or explaining it so others pay attention?"
    ),
    "motivation": (
        "Imagine your project turns out really well. Which outcome would make you "
        "care the most — mastering something hard, beating a target, helping someone, "
        "being noticed, or people counting on you?"
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
        "Any must-haves for the project — deadline, tools, budget, or other limits?"
    ),
    "constraints:geo": (
        "Where are you based (city or region), or is remote work fine?"
    ),
    "capability": "What skills or tools are you already comfortable using?",
    "assets": (
        "Do you have any unusual access that could help — people, teams, datasets, "
        "equipment, communities, or a job/hobby connection?"
    ),
}


def required_fallback(key: str) -> str:
    """Teen-friendly seeded ask for a required / discovery target key."""
    if key in _REQUIRED_FALLBACKS:
        return _REQUIRED_FALLBACKS[key]
    label = key.replace("_", " ").replace(":", " ")
    return f"What should I know about your {label} for this project?"
