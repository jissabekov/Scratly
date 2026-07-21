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


@dataclass(frozen=True)
class Target:
    kind: str
    key: str
    fallback_template: str


def select_next(candidates: list[Target]) -> Target | None:
    order = {v: i for i, v in enumerate(PRIORITY)}
    return (
        min(candidates, key=lambda x: (order[x.kind], x.key)) if candidates else None
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
