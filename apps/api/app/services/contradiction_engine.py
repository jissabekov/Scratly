"""Contradiction detection and resolution (engine v2).

Cardinality modes:
- single_choice: competing supports may conflict (plus incompatibility table)
- multi_value: multiple supports coexist; conflict only for support+oppose on
  the same value_key, or declared incompatible pairs
- structured: same as multi_value by default; compound facet keys coexist

Never averages strengths. Resolution prefers explicit newest evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
from uuid import UUID

from app.contracts import ValidatedEvidence

ENGINE_VERSION = "v2"

# Default: multi_value (compatible coexistence). Only force single_choice
# where the product truly needs one primary answer.
DIMENSION_CARDINALITY: dict[str, str] = {
    "topics": "multi_value",
    "work_mode": "structured",
    "motivation": "multi_value",
    "capability": "multi_value",
    "constraints": "multi_value",
    "execution": "structured",
    "assets": "multi_value",
}

# Sparse true rivals only. Unlisted facet pairs are compatible.
VALUE_INCOMPATIBILITIES: frozenset[tuple[str, str, str]] = frozenset()


@dataclass(frozen=True)
class Contradiction:
    dimension_key: str
    evidence_ids: tuple[str, ...]
    status: str = "open"
    reason: str = "incompatible_supports"
    value_keys: tuple[str, ...] = ()


def cardinality_for(dimension_key: str) -> str:
    return DIMENSION_CARDINALITY.get(dimension_key, "multi_value")


def values_incompatible(dimension_key: str, a: str, b: str) -> bool:
    if a == b:
        return False
    return (dimension_key, a, b) in VALUE_INCOMPATIBILITIES


def _evidence_id(item: ValidatedEvidence) -> str:
    eid = getattr(item, "evidence_id", None)
    if eid is None:
        return ""
    return str(eid)


def find_contradictions(items: list[ValidatedEvidence]) -> list[Contradiction]:
    """Detect true conflicts only; compatible multi-valued supports coexist."""
    accepted = [x for x in items if x.accepted]
    out: list[Contradiction] = []
    for dimension in sorted({x.dimension_key for x in accepted}):
        group = [x for x in accepted if x.dimension_key == dimension]
        conflict = _conflict_for_dimension(dimension, group)
        if conflict is not None:
            out.append(conflict)
    return out


def _conflict_for_dimension(
    dimension: str, group: list[ValidatedEvidence]
) -> Contradiction | None:
    by_value: dict[str, list[ValidatedEvidence]] = {}
    for item in group:
        if not item.value_key:
            continue
        by_value.setdefault(item.value_key, []).append(item)

    # Same value_key with both support and oppose.
    for value_key, rows in by_value.items():
        polarities = {x.polarity.value for x in rows}
        if "support" in polarities and "oppose" in polarities:
            ids = tuple(_evidence_id(x) for x in rows if _evidence_id(x))
            return Contradiction(
                dimension_key=dimension,
                evidence_ids=ids,
                reason="support_oppose_same_value",
                value_keys=(value_key,),
            )

    supports = [x for x in group if x.polarity.value == "support" and x.value_key]
    opposes = [x for x in group if x.polarity.value == "oppose" and x.value_key]
    support_values = sorted({x.value_key for x in supports if x.value_key})
    oppose_values = sorted({x.value_key for x in opposes if x.value_key})
    mode = cardinality_for(dimension)

    # Explicit "prefer X not Y" against a declared rival or single-choice set.
    for supported in support_values:
        for opposed in oppose_values:
            if supported == opposed:
                continue
            if values_incompatible(dimension, supported, opposed) or mode == "single_choice":
                ids = tuple(
                    _evidence_id(x)
                    for x in group
                    if x.value_key in {supported, opposed} and _evidence_id(x)
                )
                return Contradiction(
                    dimension_key=dimension,
                    evidence_ids=ids,
                    reason="preference_negation",
                    value_keys=tuple(sorted({supported, opposed})),
                )

    if len(support_values) < 2:
        return None

    incompatible_pairs = [
        (a, b)
        for i, a in enumerate(support_values)
        for b in support_values[i + 1 :]
        if values_incompatible(dimension, a, b)
    ]
    if incompatible_pairs:
        involved = {v for pair in incompatible_pairs for v in pair}
        ids = tuple(
            _evidence_id(x)
            for x in supports
            if x.value_key in involved and _evidence_id(x)
        )
        return Contradiction(
            dimension_key=dimension,
            evidence_ids=ids,
            reason="declared_incompatible_pair",
            value_keys=tuple(sorted(involved)),
        )

    if mode == "single_choice":
        ids = tuple(_evidence_id(x) for x in supports if _evidence_id(x))
        return Contradiction(
            dimension_key=dimension,
            evidence_ids=ids,
            reason="single_choice_competing_supports",
            value_keys=tuple(support_values),
        )

    # multi_value / structured: coexisting supports are not contested.
    return None


def resolve_with_newest(
    *,
    contradiction_dimension: str,
    explicit_evidence_id: UUID | str,
    resolution: str = "explicit_newest",
) -> dict:
    """Deterministic resolution payload. Never averages strengths."""
    return {
        "status": "resolved",
        "resolution": resolution,
        "winning_evidence_id": str(explicit_evidence_id),
        "dimension_key": contradiction_dimension,
        "engine_version": ENGINE_VERSION,
    }


def pick_resolution_evidence(
    items: Iterable[ValidatedEvidence],
    dimension_key: str,
) -> ValidatedEvidence | None:
    """Newest accepted evidence on the target dimension wins clarification."""
    candidates = [
        x
        for x in items
        if x.accepted and x.dimension_key == dimension_key and x.value_key
    ]
    if not candidates:
        return None
    # Prefer items that carry evidence_id from this turn / DB order last.
    return candidates[-1]


def sides_from_evidence(
    items: Iterable[ValidatedEvidence], dimension_key: str
) -> tuple[str | None, str | None]:
    """Return up to two distinct support value keys for writer context."""
    values: list[str] = []
    for item in items:
        if (
            item.accepted
            and item.dimension_key == dimension_key
            and item.polarity.value == "support"
            and item.value_key
            and item.value_key not in values
        ):
            values.append(item.value_key)
        if len(values) >= 2:
            break
    a = values[0] if values else None
    b = values[1] if len(values) > 1 else None
    return a, b
