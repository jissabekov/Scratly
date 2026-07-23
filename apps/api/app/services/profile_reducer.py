from collections import defaultdict
from dataclasses import dataclass
from app.contracts import EvidenceType, ValidatedEvidence


RELIABILITY = {
    EvidenceType.REPEATED_BEHAVIOR: 1.00,
    EvidenceType.BEHAVIORAL_EXAMPLE: .90,
    EvidenceType.FORCED_TRADEOFF: .75,
    EvidenceType.STATED_PREFERENCE: .60,
    EvidenceType.SELF_DESCRIPTION: .50,
    EvidenceType.HYPOTHETICAL: .40,
}


@dataclass(frozen=True)
class DimensionState:
    key: str
    status: str
    value: str | None
    confidence: float
    estimate: float = 0.0
    supporting_evidence: int = 0
    contradicting_evidence: int = 0
    evidence_diversity: float = 0.0


@dataclass(frozen=True)
class ReducedProfile:
    dimensions: tuple[DimensionState, ...]
    reducer_version: str


def reduce_profile(evidence: list[ValidatedEvidence], version='v2') -> ReducedProfile:
    """Deterministically weight evidence quality; the LLM never mutates state."""
    grouped = defaultdict(list)
    for item in evidence:
        if item.accepted:
            grouped[item.dimension_key].append(item)
    states = []
    for key, items in sorted(grouped.items()):
        scores = defaultdict(float)
        for item in items:
            weight = item.strength * item.confidence * RELIABILITY[item.evidence_type]
            scores[item.value_key] += weight * (1 if item.polarity.value == 'support' else -1)
        value, score = max(scores.items(), key=lambda pair: (pair[1], str(pair[0])))
        supporting = sum(item.polarity.value == 'support' and item.value_key == value for item in items)
        contradicting = sum(item.polarity.value == 'oppose' or item.value_key != value for item in items)
        contexts = {tag for item in items for tag in item.context_tags}
        evidence_types = {item.evidence_type for item in items}
        diversity = min(1.0, .2 * len(contexts) + .2 * len(evidence_types))
        confidence = min(1.0, max(0.0, abs(score)) * (.7 + .3 * diversity))
        states.append(DimensionState(
            key=key,
            status='established' if confidence >= .7 and supporting >= 2 else 'provisional',
            value=value,
            confidence=round(confidence, 4),
            estimate=round(max(-1.0, min(1.0, score)), 4),
            supporting_evidence=supporting,
            contradicting_evidence=contradicting,
            evidence_diversity=round(diversity, 4),
        ))
    return ReducedProfile(tuple(states), version)
