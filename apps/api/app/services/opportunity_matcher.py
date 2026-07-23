"""Deterministic opportunity matching with geo + execution hard filters (V1)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


WORK_MODE_KEYS = ("investigate", "build", "organize", "communicate")
EXECUTION_GATE_KEYS = (
    "persistence",
    "ambiguity_tolerance",
    "outreach_willingness",
    "public_visibility",
)


@dataclass(frozen=True)
class OpportunityMatch:
    opportunity_id: str
    opportunity_key: str
    eligible: bool
    score: float
    topic: float
    work_mode: float
    motivation: float
    failed_constraints: tuple[str, ...]
    scope_adjustments: tuple[str, ...]


def _overlap(wanted: set[str], offered: set[str]) -> float:
    if not wanted:
        return 0.0
    return len(wanted & offered) / max(1, len(wanted))


def _work_mode_alignment(
    student_modes: dict[str, int | None], offered: set[str]
) -> float:
    """Weight student facet scores against opportunity work_mode tags."""
    if not offered:
        return 0.0
    scored = []
    for key in offered:
        if key not in WORK_MODE_KEYS:
            continue
        val = student_modes.get(key)
        if val is None:
            continue
        scored.append(max(0, min(4, int(val))) / 4.0)
    if scored:
        return sum(scored) / len(scored)
    # Fallback: treat listed modes as a set of interest tags.
    known = {k for k, v in student_modes.items() if v is not None}
    return _overlap(known, offered)


def _motivation_alignment(profile: dict[str, Any], offered: set[str]) -> float:
    primary = profile.get("primary_reward") or profile.get("motivation_primary")
    secondary = profile.get("secondary_reward") or profile.get("motivation_secondary")
    motivations = set(profile.get("motivations") or [])
    if primary:
        motivations.add(str(primary))
    if secondary:
        motivations.add(str(secondary))
    if not motivations or not offered:
        return 0.0
    score = 0.0
    if primary and primary in offered:
        score += 0.7
    if secondary and secondary in offered:
        score += 0.3
    if score == 0.0:
        score = _overlap(motivations, offered)
    return min(1.0, score)


def _geo_eligible(
    student_regions: set[str],
    student_places: set[str],
    opp_regions: set[str],
    opp_places: set[str],
) -> bool:
    if "remote_ok" in opp_regions:
        return True
    if student_regions & opp_regions:
        return True
    if student_places & opp_places:
        return True
    if "remote_ok" in student_regions and "remote_ok" in opp_regions:
        return True
    return False


def _execution_gates(
    profile: dict[str, Any], hard: dict[str, Any]
) -> list[str]:
    """PASS/FAIL execution minima. Unknown (null) does not fail."""
    failed: list[str] = []
    execution = profile.get("execution") or {}
    if not isinstance(execution, dict):
        execution = {}
    for key in EXECUTION_GATE_KEYS:
        if key not in hard:
            continue
        try:
            required = int(hard[key])
        except (TypeError, ValueError):
            continue
        raw = execution.get(key)
        if raw is None:
            continue  # UNKNOWN ≠ fail
        try:
            actual = int(raw)
        except (TypeError, ValueError):
            continue
        if actual < required:
            failed.append(key)
    return failed


def rank_opportunities(
    profile: dict[str, Any], opportunities: list[dict[str, Any]]
) -> list[OpportunityMatch]:
    topics = set(profile.get("topics") or [])
    # Prefer structured work_modes map; fall back to tag set.
    raw_modes = profile.get("work_modes")
    if isinstance(raw_modes, dict):
        student_modes = {
            k: (int(v) if v is not None else None) for k, v in raw_modes.items()
        }
    else:
        student_modes = {k: 3 for k in (raw_modes or []) if k in WORK_MODE_KEYS}

    student_regions = set(profile.get("geo_regions") or [])
    student_places = set(profile.get("geo_places") or [])
    gaps = tuple(profile.get("capability_gaps") or [])
    adjustments = tuple(f"scaffold:{x}" for x in gaps)

    matches: list[OpportunityMatch] = []
    for opp in opportunities:
        failed: list[str] = []
        opp_regions = set(opp.get("geo_regions") or [])
        opp_places = set(opp.get("geo_places") or [])
        if not _geo_eligible(student_regions, student_places, opp_regions, opp_places):
            failed.append("geo")

        hard = opp.get("hard_constraints") or {}
        if not isinstance(hard, dict):
            hard = {}

        # Non-execution hard constraints (string equality) still apply when student has value.
        constraints = profile.get("constraints") or {}
        if isinstance(constraints, dict):
            for key, value in hard.items():
                if key in EXECUTION_GATE_KEYS:
                    continue
                if key in constraints and constraints.get(key) != value:
                    failed.append(key)

        failed.extend(_execution_gates(profile, hard))

        topic = _overlap(topics, set(opp.get("topics") or []))
        work = _work_mode_alignment(student_modes, set(opp.get("work_modes") or []))
        motivation = _motivation_alignment(profile, set(opp.get("motivations") or []))
        score = 0.4 * topic + 0.4 * work + 0.2 * motivation
        matches.append(
            OpportunityMatch(
                opportunity_id=str(opp["id"]),
                opportunity_key=str(opp.get("key") or opp["id"]),
                eligible=not failed,
                score=score,
                topic=topic,
                work_mode=work,
                motivation=motivation,
                failed_constraints=tuple(failed),
                scope_adjustments=adjustments,
            )
        )
    return sorted(
        matches, key=lambda m: (not m.eligible, -m.score, m.opportunity_key)
    )
