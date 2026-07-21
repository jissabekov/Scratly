"""Deterministic opportunity matching with geo hard filters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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
    # Student marked remote_ok can take remote opportunities only (already handled)
    # or any if they have no local geo — still require some geo signal upstream.
    if "remote_ok" in student_regions and "remote_ok" in opp_regions:
        return True
    return False


def rank_opportunities(
    profile: dict[str, Any], opportunities: list[dict[str, Any]]
) -> list[OpportunityMatch]:
    topics = set(profile.get("topics") or [])
    work_modes = set(profile.get("work_modes") or [])
    motivations = set(profile.get("motivations") or [])
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
        constraints = profile.get("constraints") or {}
        if isinstance(hard, dict) and isinstance(constraints, dict):
            for key, value in hard.items():
                if constraints.get(key) != value:
                    failed.append(key)

        topic = _overlap(topics, set(opp.get("topics") or []))
        work = _overlap(work_modes, set(opp.get("work_modes") or []))
        motivation = _overlap(motivations, set(opp.get("motivations") or []))
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

