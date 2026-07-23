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


class EvidenceType(StrEnum):
    REPEATED_BEHAVIOR = "repeated_behavior"
    BEHAVIORAL_EXAMPLE = "behavioral_example"
    FORCED_TRADEOFF = "forced_tradeoff"
    STATED_PREFERENCE = "stated_preference"
    SELF_DESCRIPTION = "self_description"
    HYPOTHETICAL = "hypothetical"


class ProposedEvidence(StrictModel):
    dimension_key: str
    value_key: str | None = None
    strength: Annotated[float, Field(ge=0, le=1)]
    score_band: int | None = Field(default=None, ge=0, le=4)
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
    answer_quality: Literal["insufficient", "low", "medium", "high"] = "medium"
    ambiguities: list[str] = Field(default_factory=list)
    engagement: Literal["unknown", "low", "medium", "high"] = "unknown"


class ValidatedEvidence(ProposedEvidence):
    accepted: bool
    rejection_reason: str | None = None
    evidence_id: UUID | None = None


class ProfileStatus(StrEnum):
    UNKNOWN = "unknown"
    PROVISIONAL = "provisional"
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"


MotivationKey = Literal[
    "discovery_mastery",
    "competition_achievement",
    "impact_usefulness",
    "recognition_influence",
    "belonging_responsibility",
]


class InterestRecord(StrictModel):
    topic: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    score: int = Field(ge=0, le=4)
    evidence_count: int = Field(default=0, ge=0)
    examples: list[str] = Field(default_factory=list)
    status: ProfileStatus = ProfileStatus.UNKNOWN


class CapabilityRecord(StrictModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    level: int = Field(ge=0, le=3)
    evidence_count: int = Field(default=0, ge=0)
    examples: list[str] = Field(default_factory=list)
    status: ProfileStatus = ProfileStatus.UNKNOWN


class WorkModeScores(StrictModel):
    investigate: int | None = Field(default=None, ge=0, le=4)
    build: int | None = Field(default=None, ge=0, le=4)
    organize: int | None = Field(default=None, ge=0, le=4)
    communicate: int | None = Field(default=None, ge=0, le=4)


class WorkModeStatuses(StrictModel):
    investigate: ProfileStatus = ProfileStatus.UNKNOWN
    build: ProfileStatus = ProfileStatus.UNKNOWN
    organize: ProfileStatus = ProfileStatus.UNKNOWN
    communicate: ProfileStatus = ProfileStatus.UNKNOWN


class ExecutionScores(StrictModel):
    persistence: int | None = Field(default=None, ge=0, le=4)
    ambiguity_tolerance: int | None = Field(default=None, ge=0, le=4)
    outreach_willingness: int | None = Field(default=None, ge=0, le=4)
    public_visibility: int | None = Field(default=None, ge=0, le=4)


class ExecutionStatuses(StrictModel):
    persistence: ProfileStatus = ProfileStatus.UNKNOWN
    ambiguity_tolerance: ProfileStatus = ProfileStatus.UNKNOWN
    outreach_willingness: ProfileStatus = ProfileStatus.UNKNOWN
    public_visibility: ProfileStatus = ProfileStatus.UNKNOWN


class MotivationPair(StrictModel):
    primary: MotivationKey | None = None
    secondary: MotivationKey | None = None
    status: ProfileStatus = ProfileStatus.UNKNOWN
    evidence_count: int = Field(default=0, ge=0)


class ConstraintProfile(StrictModel):
    geo: list[str] = Field(default_factory=list)
    details: list[str] = Field(default_factory=list)
    status: ProfileStatus = ProfileStatus.UNKNOWN


class StudentProfileV1(StrictModel):
    interests: list[InterestRecord] = Field(default_factory=list)
    work_modes: WorkModeScores = Field(default_factory=WorkModeScores)
    work_mode_status: WorkModeStatuses = Field(default_factory=WorkModeStatuses)
    motivation: MotivationPair = Field(default_factory=MotivationPair)
    execution: ExecutionScores = Field(default_factory=ExecutionScores)
    execution_status: ExecutionStatuses = Field(default_factory=ExecutionStatuses)
    capabilities: list[CapabilityRecord] = Field(default_factory=list)
    assets: list[str] = Field(default_factory=list)
    constraints: ConstraintProfile = Field(default_factory=ConstraintProfile)


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
    message_kind: str | None = None
    elicitation: ElicitationSpec | None = None
    student_message_id: UUID | None = None
    assistant_message_id: UUID | None = None


class MessageItem(StrictModel):
    id: UUID
    turn_id: UUID | None = None
    sequence: int
    role: str
    content: str
    message_kind: str | None = None
    created_at: datetime


class SessionMessagesResponse(StrictModel):
    session_id: UUID
    stage: str
    completed_at: datetime | None = None
    items: list[MessageItem]


class StudentProjectItem(StrictModel):
    id: UUID
    title: str
    summary: str
    topic_keys: list[str] = Field(default_factory=list)
    work_mode_keys: list[str] = Field(default_factory=list)
    motivation_keys: list[str] = Field(default_factory=list)
    citation_count: int = 0


class SessionProjectsResponse(StrictModel):
    session_id: UUID
    items: list[StudentProjectItem]
