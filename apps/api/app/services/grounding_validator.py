from typing import Iterable, Protocol
from uuid import UUID

from app.contracts import ProposedEvidence, ValidatedEvidence

_MAX_PROPOSALS = 5


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
    result: list[ValidatedEvidence] = []
    for index, item in enumerate(items):
        reason = None
        strength = max(0.0, min(1.0, float(item.strength)))
        if index >= max_proposals:
            reason = "excess_proposals_trimmed"
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
            and allowed_motivation_keys is not None
            and item.value_key
            and item.value_key not in allowed_motivation_keys
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
