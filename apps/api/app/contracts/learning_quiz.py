"""Contracts for the 5-item module quiz (Plan 04) and its gating policy.

Content models validate the versioned ``quiz.json`` files; response models
mirror ``app/routes/learning_quiz.py``. Item answers never leave the server on
a draw — ``QuizItemView`` deliberately carries no correctness.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StringConstraints, model_validator

from .learning import Key, LearningModel, ShortText, Text

FORM_SIZE = 5
PASS_THRESHOLD = 4
MAX_ATTEMPTS = 3
COOLDOWN_SECONDS = 600
PROVISIONAL_MASTERY = 0.8
PASS_RULE_TEXT = (
    "Answer at least 4 of 5 correctly, including at least one on every critical objective."
)


# --- content files (content/modules/**/quiz.json) ---------------------------


class QuizOption(LearningModel):
    key: Key
    label: ShortText


class QuizItemContent(LearningModel):
    seq: int = Field(ge=1, le=99)
    objective: Key
    kind: Literal["mcq", "select_all"]
    stem: Text
    options: Annotated[list[QuizOption], Field(min_length=2, max_length=5)]
    answer: Annotated[list[Key], Field(min_length=1, max_length=5)]
    difficulty: Annotated[float, Field(ge=0, le=1)] = 0.5
    hint_text: str = ""
    feedback_correct: str = ""
    feedback_wrong: str = ""
    slide_ref: int = Field(ge=1, le=999)
    is_critical: bool = False

    @model_validator(mode="after")
    def _answers_resolve(self) -> "QuizItemContent":
        keys = [option.key for option in self.options]
        if len(set(keys)) != len(keys):
            raise ValueError("option keys must be unique")
        unknown = [key for key in self.answer if key not in keys]
        if unknown:
            raise ValueError(f"answer keys not among options: {unknown}")
        if self.kind == "mcq" and len(self.answer) != 1:
            raise ValueError("mcq items must have exactly one answer key")
        return self


class QuizFormContent(LearningModel):
    form_id: int = Field(ge=1, le=9)
    items: Annotated[list[QuizItemContent], Field(min_length=FORM_SIZE, max_length=FORM_SIZE)]

    @model_validator(mode="after")
    def _shape(self) -> "QuizFormContent":
        seqs = [item.seq for item in self.items]
        if len(set(seqs)) != len(seqs):
            raise ValueError("item sequences must be unique within a form")
        return self


class LearningQuizContent(LearningModel):
    version: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
    slug: Key
    forms: Annotated[list[QuizFormContent], Field(min_length=1, max_length=9)]

    @model_validator(mode="after")
    def _shape(self) -> "LearningQuizContent":
        form_ids = [form.form_id for form in self.forms]
        if len(set(form_ids)) != len(form_ids):
            raise ValueError("form ids must be unique")
        return self


# --- API: draw ---------------------------------------------------------------


class QuizGateState(StrEnum):
    AVAILABLE = "available"
    COOLDOWN = "cooldown"
    HANDOFF = "handoff"
    PASSED = "passed"
    UNAVAILABLE = "unavailable"


class QuizItemView(LearningModel):
    """A drawn item as the student sees it — never includes the answer."""

    id: UUID
    seq: int
    objective_code: str
    kind: str
    stem: str
    options: list[QuizOption]
    hint_text: str = ""
    is_critical: bool = False


class QuizAttemptView(LearningModel):
    attempt_id: UUID
    attempt_no: int
    form_id: int
    item_count: int
    threshold: int = PASS_THRESHOLD
    pass_rule: str = PASS_RULE_TEXT
    items: list[QuizItemView]


class QuizDrawResponse(LearningModel):
    session_id: UUID
    module_id: UUID
    gate: QuizGateState
    attempts_used: int
    max_attempts: int = MAX_ATTEMPTS
    retry_after_seconds: int | None = None
    attempt: QuizAttemptView | None = None


# --- API: submit -------------------------------------------------------------


class QuizResponseInput(LearningModel):
    item_id: UUID
    response: list[Key] = Field(default_factory=list, max_length=5)
    latency_ms: int | None = Field(default=None, ge=0, le=24 * 60 * 60 * 1000)


class QuizItemCheckRequest(LearningModel):
    """One answer, checked immediately without leaking the rest of the bank."""

    item_id: UUID
    response: list[Key] = Field(default_factory=list, max_length=5)
    latency_ms: int | None = Field(default=None, ge=0, le=24 * 60 * 60 * 1000)


class QuizItemCheckResponse(LearningModel):
    item_id: UUID
    correct: bool
    feedback: str
    correct_answer: list[str]


class QuizAttemptRequest(LearningModel):
    request_id: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=8, max_length=128)
    ]
    attempt_id: UUID
    responses: Annotated[list[QuizResponseInput], Field(min_length=1, max_length=FORM_SIZE)]


class QuizMissedItem(LearningModel):
    item_id: UUID
    objective_code: str
    stem: str
    feedback_wrong: str
    slide_ref: int | None = None
    selected: list[str]
    correct: list[str]


class QuizRemediation(LearningModel):
    objectives: list[str]
    slide_refs: list[int]
    cooldown_seconds: int = COOLDOWN_SECONDS


class ObjectiveMastery(LearningModel):
    objective_code: str
    p_mastery: float
    state: str


class QuizAttemptResponse(LearningModel):
    attempt_id: UUID
    attempt_no: int
    form_id: int
    score: int
    item_count: int
    threshold: int = PASS_THRESHOLD
    passed: bool
    critical_missed: list[str]
    missed: list[QuizMissedItem]
    next_action: Literal["unlock_next", "retry", "walkthrough", "handoff"]
    next_form_id: int | None = None
    remediation: QuizRemediation | None = None
    mastery: list[ObjectiveMastery] = Field(default_factory=list)
    unlocked_module_id: UUID | None = None
