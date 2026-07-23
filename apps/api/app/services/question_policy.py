"""Deterministic stage and question-target policy."""

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
# Same-priority tie-break: interests before constraints (geo last among required).
DISCOVERY_KEY_ORDER = (
    "topics",
    "motivation",
    "work_mode",
    "capability",
    "collaboration",
    "challenge",
    "impact",
    "constraints",
    "constraints:geo",
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

_DISCOVERY_RANK = {k: i for i, k in enumerate(DISCOVERY_KEY_ORDER)}
_DISCOVERY_RANK_FALLBACK = len(DISCOVERY_KEY_ORDER)


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
                order[x.kind],
                _DISCOVERY_RANK.get(x.key, _DISCOVERY_RANK_FALLBACK),
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
    """Derive stage from established coverage and open true contradictions.

    Legacy callers may pass ``coverage`` (treated as established). Contested
    dims contribute only to ``coverage_touched``, so early false conflicts no
    longer force ``gap_resolution``.

    ``project_matching`` requires reviewed + location_ready (when provided).
    """
    established = (
        coverage
        if coverage_established is None and coverage is not None
        else (coverage_established or 0.0)
    )
    touched = (
        established
        if coverage_touched is None
        else coverage_touched
    )

    if projects_ready and reviewed:
        return "complete"
    if reviewed:
        if location_ready is False:
            # Stay in profile_review until geo is established.
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
    "topics": "What kinds of projects or topics are you drawn to?",
    "motivation": "What would make this project feel worth doing for you?",
    "work_mode": "How do you like to work — mostly alone, with others, or a mix?",
    "constraints": (
        "Any must-haves for the project — deadline, tools, budget, or other limits?"
    ),
    "constraints:geo": (
        "Where are you based (city or region), or is remote work fine?"
    ),
    "capability": "What skills or tools are you already comfortable using?",
    "collaboration": "How much collaboration do you want on this project?",
    "challenge": "How challenging do you want this project to feel?",
    "impact": "What kind of impact do you hope the project has?",
}


def required_fallback(key: str) -> str:
    """Teen-friendly seeded ask for a required / discovery target key."""
    if key in _REQUIRED_FALLBACKS:
        return _REQUIRED_FALLBACKS[key]
    label = key.replace("_", " ").replace(":", " ")
    return f"What should I know about your {label} for this project?"
