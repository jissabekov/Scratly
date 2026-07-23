from typing import Iterable, Protocol
from uuid import UUID

from app.contracts import ProposedEvidence, ValidatedEvidence

_MAX_PROPOSALS = 5
DEFAULT_MOTIVATION_KEYS = {
    "discovery_mastery",
    "competition_achievement",
    "impact_usefulness",
    "recognition_influence",
    "belonging_responsibility",
}
WORK_MODE_FACETS = {"investigate", "build", "organize", "communicate"}


class Message(Protocol):
    id: UUID
    session_id: UUID
    content: str


def validate_grounding(
    items: Iterable[ProposedEvidence],
    messages: Iterable[Message],
    session_id: UUID,
    *,
    allowed_motivation_keys: set[str] | None = None,
    max_proposals: int = _MAX_PROPOSALS,
) -> list[ValidatedEvidence]:
    owned = {m.id: m for m in messages if m.session_id == session_id}
    motivation_keys = allowed_motivation_keys or DEFAULT_MOTIVATION_KEYS
    result: list[ValidatedEvidence] = []
    for index, item in enumerate(items):
        reason = None
        strength = max(0.0, min(1.0, float(item.strength)))
        if index >= max_proposals:
            reason = "excess_proposals_trimmed"
        elif item.score_band is not None and not 0 <= int(item.score_band) <= 4:
            reason = "score_band_out_of_range"
        elif not (item.exact_source_quote or "").strip():
            reason = "empty_quote"
        elif any(mid not in owned for mid in item.source_message_ids):
            reason = "source_message_unavailable_or_not_owned"
        elif not any(
            item.exact_source_quote in owned[mid].content
            for mid in item.source_message_ids
        ):
            reason = "exact_quote_not_found"
        elif (
            item.dimension_key == "motivation"
            and item.value_key
            and item.value_key not in motivation_keys
        ):
            reason = "taxonomy_value_not_allowed"
        elif (
            item.dimension_key == "work_mode"
            and item.value_key
            and item.value_key not in WORK_MODE_FACETS
        ):
            reason = "taxonomy_value_not_allowed"
        payload = item.model_dump()
        payload["strength"] = strength
        result.append(
            ValidatedEvidence(
                **payload, accepted=reason is None, rejection_reason=reason
            )
        )
    return result
