from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Quote = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
class StrictModel(BaseModel): model_config = ConfigDict(extra='forbid')
class Polarity(StrEnum): SUPPORT='support'; OPPOSE='oppose'
class EvidenceType(StrEnum):
    REPEATED_BEHAVIOR='repeated_behavior'
    BEHAVIORAL_EXAMPLE='behavioral_example'
    FORCED_TRADEOFF='forced_tradeoff'
    STATED_PREFERENCE='stated_preference'
    SELF_DESCRIPTION='self_description'
    HYPOTHETICAL='hypothetical'
class ProposedEvidence(StrictModel):
    dimension_key: str
    value_key: str | None = None
    strength: Annotated[float, Field(ge=0, le=1)]
    polarity: Polarity = Polarity.SUPPORT
    source_message_ids: Annotated[list[UUID], Field(min_length=1)]
    exact_source_quote: Quote
    rationale: str
    evidence_type: EvidenceType = EvidenceType.STATED_PREFERENCE
    confidence: Annotated[float, Field(ge=0, le=1)] = 0.5
    context_tags: list[str] = Field(default_factory=list)
class EvidencePacket(StrictModel):
    items: list[ProposedEvidence]
    no_evidence_reason: str | None = None
    answer_quality: Literal['insufficient','low','medium','high'] = 'medium'
    ambiguities: list[str] = Field(default_factory=list)
    engagement: Literal['unknown','low','medium','high'] = 'unknown'
class ValidatedEvidence(ProposedEvidence):
    accepted: bool
    rejection_reason: str | None = None
class QuestionResponse(StrictModel):
    question: Annotated[str, StringConstraints(min_length=1, max_length=500)]
class MemorySnapshotOutput(StrictModel):
    stable_preferences: list[str]
    commitments: list[str]
    unresolved_threads: list[str]
    boundary_sequence: int
class ProfileReviewOutput(StrictModel):
    narrative: str
    confirmations: list[str]
    corrections_requested: list[str]
class GeneratedProject(StrictModel):
    title: str; summary: str; topic_keys: list[str]; work_mode_keys: list[str]
    motivation_keys: list[str]; hard_constraints: dict[str, str]; scope_adjustments: list[str]
class ProjectGenerationOutput(StrictModel): projects: Annotated[list[GeneratedProject], Field(min_length=1, max_length=5)]
class TurnRequest(StrictModel):
    idempotency_key: Annotated[str, StringConstraints(min_length=8,max_length=128)]
    text: Annotated[str, StringConstraints(min_length=1,max_length=10000)]
class TurnResponse(StrictModel): turn_id: UUID; assistant_message: str; stage: str
