from dataclasses import replace
from typing import Iterable, Protocol
from uuid import UUID
from app.contracts import ProposedEvidence, ValidatedEvidence
class Message(Protocol):
    id: UUID; session_id: UUID; content: str

def validate_grounding(items: Iterable[ProposedEvidence], messages: Iterable[Message], session_id: UUID) -> list[ValidatedEvidence]:
    owned = {m.id:m for m in messages if m.session_id == session_id}
    result=[]
    for item in items:
        reason=None
        if any(mid not in owned for mid in item.source_message_ids): reason='source_message_unavailable_or_not_owned'
        elif not any(item.exact_source_quote in owned[mid].content for mid in item.source_message_ids): reason='exact_quote_not_found'
        result.append(ValidatedEvidence(**item.model_dump(), accepted=reason is None, rejection_reason=reason))
    return result
