from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Quote = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Polarity(StrEnum):
    SUPPORT = "support"
    OPPOSE = "oppose"


class ProposedEvidence(StrictModel):
    dimension_key: str
    value_key: str | None = None
    strength: Annotated[float, Field(ge=0, le=1)]
    polarity: Polarity = Polarity.SUPPORT
    source_message_ids: Annotated[list[UUID], Field(min_length=1)]
    exact_source_quote: Quote
    rationale: str


class EvidencePacket(StrictModel):
    items: list[ProposedEvidence]
    no_evidence_reason: str | None = None


class ValidatedEvidence(ProposedEvidence):
    accepted: bool
    rejection_reason: str | None = None
    evidence_id: UUID | None = None


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
    title: str
    summary: str
    topic_keys: list[str]
    work_mode_keys: list[str]
    motivation_keys: list[str]
    hard_constraints: dict[str, str]
    scope_adjustments: list[str]


class ProjectGenerationOutput(StrictModel):
    projects: Annotated[list[GeneratedProject], Field(min_length=1, max_length=5)]


class PrimaryIntent(StrEnum):
    ASSESSMENT_CONTRIBUTION = "assessment_contribution"
    STUDENT_QUESTION = "student_question"
    MIXED = "mixed"
    META_REFUSAL = "meta_refusal"


class QuestionTopic(StrEnum):
    PROCESS = "process"
    PROFILE = "profile"
    PROJECT = "project"
    OUT_OF_SCOPE = "out_of_scope"
    NONE = "none"


class TurnIntentPacket(StrictModel):
    primary_intent: PrimaryIntent
    question_topic: QuestionTopic = QuestionTopic.NONE
    confidence: Annotated[float, Field(ge=0, le=1)] = 0.5
    assessment_span: str | None = None
    question_span: str | None = None


class StudentAnswerMode(StrEnum):
    ANSWER = "answer"
    REFUSE = "refuse"


class StudentAnswerOutput(StrictModel):
    mode: StudentAnswerMode
    text: Annotated[str, StringConstraints(min_length=1, max_length=2000)]
    cited_evidence_ids: list[UUID] = Field(default_factory=list)
    cited_profile_fields: list[str] = Field(default_factory=list)
    refusal_reason_code: str | None = None


class ThinAnswerSignal(StrictModel):
    is_thin: bool
    reason_codes: list[str] = Field(default_factory=list)


class ElicitationOption(StrictModel):
    key: str
    label: str


class ElicitationSpec(StrictModel):
    options: Annotated[list[ElicitationOption], Field(min_length=2, max_length=3)]
    allow_both: bool = True
    allow_skip: bool = True
    dimension_key: str
    fallback_template: str


class ResearchFindingPacket(StrictModel):
    url: Annotated[str, StringConstraints(min_length=1, max_length=2000)]
    title: str = ""
    snippet: str = ""
    publisher: str | None = None
    rank: int = 0


class ProjectCitation(StrictModel):
    kind: Literal["opportunity", "research_finding"]
    id: UUID


class ComposedProjectPacket(StrictModel):
    title: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    summary: Annotated[str, StringConstraints(min_length=1, max_length=2000)]
    topic_keys: list[str] = Field(default_factory=list)
    work_mode_keys: list[str] = Field(default_factory=list)
    motivation_keys: list[str] = Field(default_factory=list)
    hard_constraints: dict[str, str] = Field(default_factory=dict)
    scope_adjustments: list[str] = Field(default_factory=list)
    citations: Annotated[list[ProjectCitation], Field(min_length=1, max_length=10)]


class ProjectComposeOutput(StrictModel):
    projects: Annotated[list[ComposedProjectPacket], Field(min_length=1, max_length=3)]


class TurnRequest(StrictModel):
    idempotency_key: Annotated[str, StringConstraints(min_length=8, max_length=128)]
    text: Annotated[str, StringConstraints(min_length=1, max_length=10000)]


class TurnResponse(StrictModel):
    turn_id: UUID
    assistant_message: str
    stage: str
