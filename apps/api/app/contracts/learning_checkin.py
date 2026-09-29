"""Contracts for progress check-ins and the advice ladder (Plan 05 / Phase 5).

Content models validate the versioned ``checkins.json`` files next to each
``module.json``. Response models mirror ``app/routes/learning_checkins.py``.

Two hard boundaries this module encodes:

* Scheduling, scoring, the intervention ladder, and retention intervals are
  deterministic. The LLM may only phrase an already-decided item and classify
  free text against the item's rubric; ``CheckinItemView`` therefore never
  carries correctness for an ``mcq`` item.
* Check-in answers are learning evidence only. They append xAPI-shaped
  ``learning_events`` and update the ``mastery_states`` projection — they never
  write ``assessment.evidence``.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StringConstraints, model_validator

from .learning import Key, LearningModel, ShortText, Text

# --- policy constants (deterministic; unit-tested) ---------------------------

CHECKIN_COOLDOWN_SECONDS = 600
CHECKIN_DISMISS_COOLDOWN_MULTIPLIER = 2
MAX_CHECKINS_PER_SESSION = 3
MIN_SECONDS_BETWEEN_CHECKINS = 300
INACTIVITY_HOURS = 72
APPLIED_EVIDENCE_WEIGHT = 0.5
RETENTION_INTERVALS_DAYS = (1, 3, 7, 16)
RETENTION_LAPSE_STATE = "decaying"
RESPONSE_RATE_TARGET = 0.60


class CheckinKind(StrEnum):
    LIKERT = "likert"
    MCQ = "mcq"
    MINI_EXERCISE = "mini_exercise"
    SELF_EXPLAIN = "self_explain"


class CheckinTrigger(StrEnum):
    """Deterministic trigger reasons (Plan 05 §5.1)."""

    SECTION_COMPLETE = "section_complete"
    MILESTONE = "milestone"
    ERROR_BURST = "error_burst"
    INACTIVITY = "inactivity"
    STREAK_DAY = "streak_day"
    RETENTION_DUE = "retention_due"


class InterventionLevel(StrEnum):
    HINT = "hint"
    RETEACH = "reteach"
    REQUIZ = "requiz"
    WALKTHROUGH = "walkthrough"
    HANDOFF = "handoff"


class CheckinGate(StrEnum):
    AVAILABLE = "available"
    COOLDOWN = "cooldown"
    DISMISSED = "dismissed"
    BUDGET_EXHAUSTED = "budget_exhausted"
    QUIZ_ACTIVE = "quiz_active"
    NONE = "none"


# --- content files (content/modules/**/checkins.json) ------------------------


class LikertScale(LearningModel):
    min: int = Field(ge=1, le=5)
    max: int = Field(ge=1, le=5)
    low_label: ShortText
    high_label: ShortText

    @model_validator(mode="after")
    def _ordered(self) -> "LikertScale":
        if self.max <= self.min:
            raise ValueError("likert scale max must exceed min")
        return self


class CheckinOption(LearningModel):
    key: Key
    label: ShortText


class CheckinRubric(LearningModel):
    criteria: Annotated[list[ShortText], Field(min_length=1, max_length=6)]


class CheckinItemContent(LearningModel):
    seq: int = Field(ge=1, le=99)
    # Authored at the bank level; normalized onto each item by
    # ``CheckinObjectiveContent`` so downstream code has one shape.
    objective: str = ""
    kind: CheckinKind
    prompt: Text
    scale: LikertScale | None = None
    options: Annotated[list[CheckinOption], Field(max_length=5)] = Field(default_factory=list)
    answer: Annotated[list[Key], Field(max_length=5)] = Field(default_factory=list)
    explanation: str = ""
    rubric: CheckinRubric | None = None

    @model_validator(mode="after")
    def _kind_shape(self) -> "CheckinItemContent":
        if self.kind == CheckinKind.LIKERT:
            if self.scale is None:
                raise ValueError("likert items require a scale")
        elif self.kind == CheckinKind.MCQ:
            keys = [option.key for option in self.options]
            if len(set(keys)) != len(keys):
                raise ValueError("option keys must be unique")
            if len(keys) < 2:
                raise ValueError("mcq items require at least two options")
            if not self.answer:
                raise ValueError("mcq items require at least one answer key")
            unknown = [key for key in self.answer if key not in keys]
            if unknown:
                raise ValueError(f"answer keys not among options: {unknown}")
        elif self.rubric is None:
            raise ValueError(f"{self.kind} items require a rubric")
        return self


class CheckinObjectiveContent(LearningModel):
    objective: Key
    items: Annotated[list[CheckinItemContent], Field(min_length=1, max_length=8)]

    @model_validator(mode="after")
    def _shape(self) -> "CheckinObjectiveContent":
        seqs = [item.seq for item in self.items]
        if len(set(seqs)) != len(seqs):
            raise ValueError("item sequences must be unique within an objective")
        for item in self.items:
            item.objective = self.objective
        return self


class LearningCheckinContent(LearningModel):
    version: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
    slug: Key
    objectives: Annotated[list[CheckinObjectiveContent], Field(min_length=1, max_length=32)]

    @model_validator(mode="after")
    def _shape(self) -> "LearningCheckinContent":
        codes = [bank.objective for bank in self.objectives]
        if len(set(codes)) != len(codes):
            raise ValueError("objective codes must be unique")
        return self


# --- API: deliver ------------------------------------------------------------


class CheckinItemView(LearningModel):
    """A delivered item as the student sees it — never includes the answer key."""

    id: UUID
    objective_code: str
    objective_label: str
    kind: CheckinKind
    prompt: str
    trigger_reason: str
    scale: LikertScale | None = None
    options: list[CheckinOption] = Field(default_factory=list)


class CheckinDeliverResponse(LearningModel):
    session_id: UUID
    gate: CheckinGate
    item: CheckinItemView | None = None
    retry_after_seconds: int | None = None
    checkins_used: int = 0
    max_checkins: int = MAX_CHECKINS_PER_SESSION


# --- API: respond ------------------------------------------------------------


class CheckinRespondRequest(LearningModel):
    request_id: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=8, max_length=128)
    ]
    response: Annotated[list[Key], Field(max_length=5)] = Field(default_factory=list)
    free_text: str = ""
    latency_ms: int | None = Field(default=None, ge=0, le=24 * 60 * 60 * 1000)


class CheckinFeedback(LearningModel):
    score: float
    correct: bool | None = None
    feedback: str
    correct_answer: list[str] = Field(default_factory=list)


class CheckinObjectiveState(LearningModel):
    objective_code: str
    p_mastery: float
    state: str
    evidence_count: int = 0


class CheckinRespondResponse(LearningModel):
    event_id: UUID
    item_id: UUID
    objective_code: str
    kind: CheckinKind
    scored: bool
    result: CheckinFeedback
    mastery: list[CheckinObjectiveState] = Field(default_factory=list)
    retention_due_at: datetime | None = None
    next_action: Literal["continue", "refresher", "dismissed"] = "continue"


class CheckinDismissRequest(LearningModel):
    request_id: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=8, max_length=128)
    ]
    reason: str = ""


class CheckinDismissResponse(LearningModel):
    event_id: UUID
    dismissed: bool = True
    cooldown_seconds: int
    next_available_in_seconds: int


# --- API: coach summary ------------------------------------------------------


class RetentionCardView(LearningModel):
    objective_code: str
    objective_label: str
    due_at: datetime
    interval_days: int
    reps: int
    lapses: int
    overdue: bool = False


class InterventionView(LearningModel):
    id: UUID
    level: InterventionLevel
    trigger_rule: str
    objective_code: str | None = None
    summary: str = ""
    created_at: datetime


class CoachSummaryResponse(LearningModel):
    session_id: UUID
    streak_steps: int
    mastery: list[CheckinObjectiveState] = Field(default_factory=list)
    due_retention: list[RetentionCardView] = Field(default_factory=list)
    open_interventions: list[InterventionView] = Field(default_factory=list)
    checkins_used: int = 0
    max_checkins: int = MAX_CHECKINS_PER_SESSION
