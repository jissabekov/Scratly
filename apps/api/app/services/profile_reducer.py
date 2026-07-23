from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from app.contracts import (
    CapabilityRecord,
    ConstraintProfile,
    EvidenceType,
    ExecutionScores,
    ExecutionStatuses,
    InterestRecord,
    MotivationPair,
    ProfileStatus,
    StudentProfileV1,
    ValidatedEvidence,
    WorkModeScores,
    WorkModeStatuses,
)
from app.services.location_policy import is_geo_value_key

WORK_MODE_KEYS = ("investigate", "build", "organize", "communicate")
EXECUTION_KEYS = (
    "persistence",
    "ambiguity_tolerance",
    "outreach_willingness",
    "public_visibility",
)
MOTIVATION_KEYS = (
    "discovery_mastery",
    "competition_achievement",
    "impact_usefulness",
    "recognition_influence",
    "belonging_responsibility",
)
STATUS_CONFIDENCE = {
    ProfileStatus.UNKNOWN: 0.0,
    ProfileStatus.PROVISIONAL: 0.5,
    ProfileStatus.SUPPORTED: 1.0,
    ProfileStatus.CONTRADICTED: 0.25,
}

# Reliability weighting from the adaptive-evidence model (origin/main). Higher
# reliability evidence (observed repeated behavior) outweighs self-description or
# hypotheticals when a facet bucket holds multiple competing observations.
RELIABILITY = {
    EvidenceType.REPEATED_BEHAVIOR: 1.00,
    EvidenceType.BEHAVIORAL_EXAMPLE: 0.90,
    EvidenceType.FORCED_TRADEOFF: 0.75,
    EvidenceType.STATED_PREFERENCE: 0.60,
    EvidenceType.SELF_DESCRIPTION: 0.50,
    EvidenceType.HYPOTHETICAL: 0.40,
}


def _evidence_weight(item: ValidatedEvidence) -> float:
    reliability = RELIABILITY.get(getattr(item, "evidence_type", None), 0.60)
    confidence = getattr(item, "confidence", 1.0)
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = 1.0
    return max(reliability * confidence, 1e-6)


@dataclass(frozen=True)
class DimensionState:
    key: str
    status: str
    value: str | None
    confidence: float
    values: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReducedProfile:
    profile: StudentProfileV1
    dimensions: tuple[DimensionState, ...]
    reducer_version: str

    @property
    def state(self) -> dict[str, object]:
        payload = self.profile.model_dump(mode="python")
        payload["dimensions"] = [
            {
                "key": dim.key,
                "status": dim.status,
                "value": dim.value,
                "confidence": dim.confidence,
                "values": list(dim.values),
            }
            for dim in self.dimensions
        ]
        return payload


@dataclass(frozen=True)
class FacetSummary:
    value_key: str
    score: int | None
    evidence_count: int
    examples: tuple[str, ...]
    status: ProfileStatus
    support_count: int
    oppose_count: int


def reduce_profile(
    evidence: list[ValidatedEvidence], version: str = "v2"
) -> ReducedProfile:
    accepted = [item for item in evidence if item.accepted]

    interest_summaries = _summaries_for_dimension(accepted, "topics")
    interests = [
        InterestRecord(
            topic=summary.value_key,
            score=summary.score if summary.score is not None else 0,
            evidence_count=summary.evidence_count,
            examples=list(summary.examples),
            status=summary.status,
        )
        for summary in _ordered_summaries(interest_summaries)
    ]

    work_mode_summaries = _summaries_for_dimension(
        accepted, "work_mode", allowed_keys=WORK_MODE_KEYS
    )
    work_mode_scores = {
        key: work_mode_summaries[key].score if key in work_mode_summaries else None
        for key in WORK_MODE_KEYS
    }
    work_mode_status = {
        key: (
            work_mode_summaries[key].status
            if key in work_mode_summaries
            else ProfileStatus.UNKNOWN
        )
        for key in WORK_MODE_KEYS
    }

    motivation_summaries = _summaries_for_dimension(
        accepted, "motivation", allowed_keys=MOTIVATION_KEYS
    )
    motivation_ranked = [
        summary
        for summary in _ordered_summaries(motivation_summaries)
        if summary.support_count > 0
    ]
    motivation = MotivationPair(
        primary=motivation_ranked[0].value_key if motivation_ranked else None,
        secondary=motivation_ranked[1].value_key if len(motivation_ranked) > 1 else None,
        status=_dimension_status(motivation_summaries.values()),
        evidence_count=sum(
            summary.evidence_count for summary in motivation_summaries.values()
        ),
    )

    execution_summaries = _summaries_for_dimension(
        accepted, "execution", allowed_keys=EXECUTION_KEYS
    )
    execution_scores = {
        key: execution_summaries[key].score if key in execution_summaries else None
        for key in EXECUTION_KEYS
    }
    execution_status = {
        key: (
            execution_summaries[key].status
            if key in execution_summaries
            else ProfileStatus.UNKNOWN
        )
        for key in EXECUTION_KEYS
    }

    capability_summaries = _summaries_for_dimension(
        accepted, "capability", max_band=3
    )
    capabilities = [
        CapabilityRecord(
            name=summary.value_key,
            level=summary.score if summary.score is not None else 0,
            evidence_count=summary.evidence_count,
            examples=list(summary.examples),
            status=summary.status,
        )
        for summary in _ordered_summaries(capability_summaries)
    ]

    assets = _reduce_assets(accepted)
    constraint_geo, constraint_details, constraint_status = _reduce_constraints(accepted)

    profile = StudentProfileV1(
        interests=interests,
        work_modes=WorkModeScores(**work_mode_scores),
        work_mode_status=WorkModeStatuses(**work_mode_status),
        motivation=motivation,
        execution=ExecutionScores(**execution_scores),
        execution_status=ExecutionStatuses(**execution_status),
        capabilities=capabilities,
        assets=assets,
        constraints=ConstraintProfile(
            geo=constraint_geo,
            details=constraint_details,
            status=constraint_status,
        ),
    )
    dimensions = _build_dimensions(
        profile=profile,
        topic_summaries=interest_summaries,
        work_mode_summaries=work_mode_summaries,
        motivation_summaries=motivation_summaries,
        capability_summaries=capability_summaries,
        execution_summaries=execution_summaries,
    )
    return ReducedProfile(profile=profile, dimensions=dimensions, reducer_version=version)


def _summaries_for_dimension(
    evidence: Iterable[ValidatedEvidence],
    dimension_key: str,
    *,
    max_band: int = 4,
    allowed_keys: Iterable[str] | None = None,
) -> dict[str, FacetSummary]:
    allowed = set(allowed_keys or [])
    grouped: dict[str, list[ValidatedEvidence]] = defaultdict(list)
    for item in evidence:
        if item.dimension_key != dimension_key or not item.value_key:
            continue
        if allowed and item.value_key not in allowed:
            continue
        grouped[item.value_key].append(item)
    return {
        value_key: _summarize_bucket(value_key, rows, max_band=max_band)
        for value_key, rows in grouped.items()
    }


def _summarize_bucket(
    value_key: str, rows: list[ValidatedEvidence], *, max_band: int
) -> FacetSummary:
    support = [
        (_band_for(item, max_band=max_band), _evidence_weight(item))
        for item in rows
        if item.polarity.value == "support"
    ]
    oppose = [
        (_band_for(item, max_band=max_band), _evidence_weight(item))
        for item in rows
        if item.polarity.value == "oppose"
    ]
    support_bands = [band for band, _ in support]
    oppose_bands = [band for band, _ in oppose]
    if support_bands and oppose_bands:
        net = round((sum(support_bands) - sum(oppose_bands)) / max(1, len(rows)))
        score = _clamp(net, 0, max_band)
        status = ProfileStatus.CONTRADICTED
    elif support_bands:
        score = _clamp(round(_weighted_mean(support)), 0, max_band)
        status = (
            ProfileStatus.SUPPORTED
            if len(support_bands) >= 2
            else ProfileStatus.PROVISIONAL
        )
    elif oppose_bands:
        score = 0
        status = (
            ProfileStatus.SUPPORTED
            if len(oppose_bands) >= 2
            else ProfileStatus.PROVISIONAL
        )
    else:
        score = None
        status = ProfileStatus.UNKNOWN
    return FacetSummary(
        value_key=value_key,
        score=score,
        evidence_count=len(rows),
        examples=_examples_from(rows),
        status=status,
        support_count=len(support_bands),
        oppose_count=len(oppose_bands),
    )


def _ordered_summaries(summaries: dict[str, FacetSummary]) -> list[FacetSummary]:
    return sorted(
        summaries.values(),
        key=lambda summary: (
            -(summary.score if summary.score is not None else -1),
            -summary.evidence_count,
            summary.value_key,
        ),
    )


def _reduce_assets(evidence: Iterable[ValidatedEvidence]) -> list[str]:
    assets: list[str] = []
    for item in evidence:
        if item.dimension_key != "assets" or item.polarity.value != "support":
            continue
        value = (item.value_key or item.exact_source_quote or "").strip()
        if value and value not in assets:
            assets.append(value)
    return assets


def _reduce_constraints(
    evidence: Iterable[ValidatedEvidence],
) -> tuple[list[str], list[str], ProfileStatus]:
    geo: list[str] = []
    details: list[str] = []
    count = 0
    for item in evidence:
        if item.dimension_key != "constraints" or item.polarity.value != "support":
            continue
        value = (item.value_key or "").strip()
        if not value:
            continue
        count += 1
        if is_geo_value_key(value):
            if value not in geo:
                geo.append(value)
        elif value not in details:
            details.append(value)
    if count == 0:
        status = ProfileStatus.UNKNOWN
    elif count >= 2:
        status = ProfileStatus.SUPPORTED
    else:
        status = ProfileStatus.PROVISIONAL
    return geo, details, status


def _build_dimensions(
    *,
    profile: StudentProfileV1,
    topic_summaries: dict[str, FacetSummary],
    work_mode_summaries: dict[str, FacetSummary],
    motivation_summaries: dict[str, FacetSummary],
    capability_summaries: dict[str, FacetSummary],
    execution_summaries: dict[str, FacetSummary],
) -> tuple[DimensionState, ...]:
    topic_status = _dimension_status(topic_summaries.values())
    work_mode_status = _dimension_status(work_mode_summaries.values())
    capability_status = _dimension_status(capability_summaries.values())
    execution_status = _dimension_status(execution_summaries.values())
    asset_status = (
        ProfileStatus.SUPPORTED
        if len(profile.assets) >= 2
        else (ProfileStatus.PROVISIONAL if profile.assets else ProfileStatus.UNKNOWN)
    )
    return (
        DimensionState(
            key="topics",
            status=topic_status.value,
            value=profile.interests[0].topic if profile.interests else None,
            confidence=STATUS_CONFIDENCE[topic_status],
            values=tuple(item.topic for item in profile.interests),
        ),
        DimensionState(
            key="work_mode",
            status=work_mode_status.value,
            value=_top_scored_key(profile.work_modes.model_dump()),
            confidence=STATUS_CONFIDENCE[work_mode_status],
            values=tuple(
                key for key, value in profile.work_modes.model_dump().items() if value is not None
            ),
        ),
        DimensionState(
            key="motivation",
            status=profile.motivation.status.value,
            value=profile.motivation.primary,
            confidence=STATUS_CONFIDENCE[profile.motivation.status],
            values=tuple(
                value
                for value in [profile.motivation.primary, profile.motivation.secondary]
                if value
            ),
        ),
        DimensionState(
            key="capability",
            status=capability_status.value,
            value=profile.capabilities[0].name if profile.capabilities else None,
            confidence=STATUS_CONFIDENCE[capability_status],
            values=tuple(item.name for item in profile.capabilities),
        ),
        DimensionState(
            key="constraints",
            status=profile.constraints.status.value,
            value=(profile.constraints.geo or profile.constraints.details or [None])[0],
            confidence=STATUS_CONFIDENCE[profile.constraints.status],
            values=tuple(profile.constraints.geo + profile.constraints.details),
        ),
        DimensionState(
            key="execution",
            status=execution_status.value,
            value=_top_scored_key(profile.execution.model_dump()),
            confidence=STATUS_CONFIDENCE[execution_status],
            values=tuple(
                key for key, value in profile.execution.model_dump().items() if value is not None
            ),
        ),
        DimensionState(
            key="assets",
            status=asset_status.value,
            value=profile.assets[0] if profile.assets else None,
            confidence=STATUS_CONFIDENCE[asset_status],
            values=tuple(profile.assets),
        ),
    )


def _dimension_status(items: Iterable[FacetSummary]) -> ProfileStatus:
    statuses = [item.status for item in items]
    if not statuses:
        return ProfileStatus.UNKNOWN
    if ProfileStatus.CONTRADICTED in statuses:
        return ProfileStatus.CONTRADICTED
    if ProfileStatus.SUPPORTED in statuses:
        return ProfileStatus.SUPPORTED
    if ProfileStatus.PROVISIONAL in statuses:
        return ProfileStatus.PROVISIONAL
    return ProfileStatus.UNKNOWN


def _examples_from(rows: Iterable[ValidatedEvidence]) -> tuple[str, ...]:
    seen: list[str] = []
    for item in rows:
        quote = (item.exact_source_quote or "").strip()
        if quote and quote not in seen:
            seen.append(quote)
        if len(seen) >= 3:
            break
    return tuple(seen)


def _band_for(item: ValidatedEvidence, *, max_band: int) -> int:
    if item.score_band is not None:
        return _clamp(int(item.score_band), 0, max_band)
    derived = round(float(item.strength) * max_band)
    return _clamp(derived, 0, max_band)


def _top_scored_key(scores: dict[str, int | None]) -> str | None:
    ranked = [(key, value) for key, value in scores.items() if value is not None]
    if not ranked:
        return None
    ranked.sort(key=lambda item: (-item[1], item[0]))
    return ranked[0][0]


def _weighted_mean(pairs: list[tuple[int, float]]) -> float:
    """Reliability/confidence-weighted mean of evidence bands.

    Invariant to the weight for single-item buckets, so deterministic V1
    scores are preserved while multi-observation buckets favor more reliable
    evidence.
    """
    total_weight = sum(weight for _, weight in pairs)
    if total_weight <= 0:
        return sum(band for band, _ in pairs) / len(pairs)
    return sum(band * weight for band, weight in pairs) / total_weight


def _clamp(value: int, lower: int, upper: int) -> int:
    return max(lower, min(upper, value))
