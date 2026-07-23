"""Archetype project matching (V1) — mirrors opportunity gates."""

from __future__ import annotations

from dataclasses import dataclass
from math import exp, log2
from typing import Any

from app.services.opportunity_matcher import (
    EXECUTION_GATE_KEYS,
    WORK_MODE_KEYS,
    _execution_gates,
    _motivation_alignment,
    _work_mode_alignment,
)


@dataclass(frozen=True)
class Match:
    project_id: str
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


def rank_projects(profile: dict[str, Any], projects: list[dict[str, Any]]) -> list[Match]:
    topics = set(profile.get("topics") or [])
    raw_modes = profile.get("work_modes")
    if isinstance(raw_modes, dict):
        student_modes = {
            k: (int(v) if v is not None else None) for k, v in raw_modes.items()
        }
    else:
        student_modes = {k: 3 for k in (raw_modes or []) if k in WORK_MODE_KEYS}

    gaps = tuple(profile.get("capability_gaps") or [])
    adjustments = tuple(f"scaffold:{x}" for x in gaps)
    constraints = profile.get("constraints") or {}
    if not isinstance(constraints, dict):
        constraints = {}

    matches: list[Match] = []
    for project in projects:
        failed: list[str] = []
        hard = project.get("hard_constraints") or {}
        if not isinstance(hard, dict):
            hard = {}
        for key, value in hard.items():
            if key in EXECUTION_GATE_KEYS:
                continue
            if key in constraints and constraints.get(key) != value:
                failed.append(key)
        failed.extend(_execution_gates(profile, hard))

        topic = _overlap(topics, set(project.get("topics") or []))
        work = _work_mode_alignment(
            student_modes, set(project.get("work_modes") or [])
        )
        motivation = _motivation_alignment(
            profile, set(project.get("motivations") or [])
        )
        score = 0.4 * topic + 0.4 * work + 0.2 * motivation
        matches.append(
            Match(
                project["id"],
                not failed,
                score,
                topic,
                work,
                motivation,
                tuple(failed),
                adjustments,
            )
        )
    return sorted(matches, key=lambda m: (not m.eligible, -m.score, m.project_id))


def fit_distribution(matches: list[Match], temperature: float = .2) -> dict[str, float]:
    """Expose uncertainty over eligible project modes instead of only a ranking."""
    eligible = [match for match in matches if match.eligible]
    if not eligible:
        return {}
    scale = max(temperature, .01)
    weights = {match.project_id: exp(match.score / scale) for match in eligible}
    total = sum(weights.values())
    return {key: round(value / total, 6) for key, value in weights.items()}


def decision_entropy(distribution: dict[str, float]) -> float:
    return -sum(probability * log2(probability) for probability in distribution.values() if probability > 0)


def recommendation_ready(distribution: dict[str, float], *, threshold: float = .70) -> bool:
    """Stop when a project mode is decisive; never stop merely because turns elapsed."""
    return bool(distribution) and max(distribution.values()) >= threshold
