"""Contracts for the learning track (Plan 03) and its Plan 04/05 boundaries.

Content is a typed block list — never free-form HTML — so one renderer
(``components/learn/SlideBlock.tsx``) can display every slide. Response models
mirror the FastAPI surface in ``app/routes/learning.py``.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
Key = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]

SlideKind = Literal["text", "callout", "diagram", "check", "worked_example"]


class LearningModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- content blocks (typed; rendered by one component) -----------------------


class TextBlock(LearningModel):
    type: Literal["text"]
    text: Text


class CalloutBlock(LearningModel):
    type: Literal["callout"]
    tone: Literal["info", "success", "warning"] = "info"
    title: str = ""
    text: Text


class DiagramBlock(LearningModel):
    type: Literal["diagram"]
    asset: Key
    alt: ShortText
    caption: str = ""
    steps: list[ShortText] = Field(default_factory=list)


class CheckOption(LearningModel):
    key: Key
    label: ShortText


class CheckBlock(LearningModel):
    """A retryable, low-stakes in-slide check. Never silently advances."""

    type: Literal["check"]
    question: Text
    options: Annotated[list[CheckOption], Field(min_length=2, max_length=4)]
    answer_key: Key
    explanation: Text
    objective: str | None = None

    @model_validator(mode="after")
    def _answer_key_must_exist(self) -> "CheckBlock":
        keys = {option.key for option in self.options}
        if self.answer_key not in keys:
            raise ValueError("answer_key must match one of the option keys")
        if len(keys) != len(self.options):
            raise ValueError("check option keys must be unique")
        return self


class WorkedExampleBlock(LearningModel):
    type: Literal["worked_example"]
    title: ShortText
    steps: Annotated[list[Text], Field(min_length=1, max_length=8)]


SlideBlock = Annotated[
    Union[TextBlock, CalloutBlock, DiagramBlock, CheckBlock, WorkedExampleBlock],
    Field(discriminator="type"),
]


# --- content files (content/modules/**/module.json) -------------------------


class ContentObjective(LearningModel):
    code: Key
    label: ShortText
    is_critical: bool = False
    ordinal: int = Field(ge=1, le=99)


class ContentSlide(LearningModel):
    seq: int = Field(ge=1, le=999)
    kind: SlideKind
    title: str = ""
    objective: str | None = None
    blocks: Annotated[list[SlideBlock], Field(min_length=1, max_length=3)]

    @model_validator(mode="after")
    def _one_idea_per_slide(self) -> "ContentSlide":
        if self.kind != self.blocks[0].type:
            raise ValueError("slide kind must match the first block type")
        if sum(block.type == "check" for block in self.blocks) > 1:
            raise ValueError("a slide may hold at most one check block")
        if self.objective is None and any(block.type == "check" for block in self.blocks):
            raise ValueError("check blocks must name the objective they assess")
        return self


class ContentLesson(LearningModel):
    seq: int = Field(ge=1, le=999)
    title: ShortText
    slides: Annotated[list[ContentSlide], Field(min_length=1)]


class LearningModuleContent(LearningModel):
    version: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
    slug: Key
    seq: int = Field(ge=1, le=99)
    title: ShortText
    description: str = ""
    est_minutes: int = Field(default=10, ge=1, le=240)
    objectives: Annotated[list[ContentObjective], Field(min_length=1)]
    lessons: Annotated[list[ContentLesson], Field(min_length=1)]

    @model_validator(mode="after")
    def _references_resolve(self) -> "LearningModuleContent":
        codes = [objective.code for objective in self.objectives]
        if len(set(codes)) != len(codes):
            raise ValueError("objective codes must be unique")
        lesson_seqs = [lesson.seq for lesson in self.lessons]
        if len(set(lesson_seqs)) != len(lesson_seqs):
            raise ValueError("lesson sequences must be unique")
        known = set(codes)
        for lesson in self.lessons:
            slide_seqs = [slide.seq for slide in lesson.slides]
            if len(set(slide_seqs)) != len(slide_seqs):
                raise ValueError("slide sequences must be unique within a lesson")
            for slide in lesson.slides:
                if slide.objective is not None and slide.objective not in known:
                    raise ValueError(f"slide references unknown objective {slide.objective!r}")
        return self


# --- API responses ----------------------------------------------------------


class ModuleState(StrEnum):
    LOCKED = "locked"
    AVAILABLE = "available"
    IN_PROGRESS = "in_progress"
    PASSED = "passed"


class LearningModuleSummary(LearningModel):
    id: UUID
    slug: str
    seq: int
    title: str
    description: str
    est_minutes: int
    state: ModuleState
    slides_total: int
    slides_completed: int
    progress_pct: int
    quiz_gate_locked: bool


class LearningHubResponse(LearningModel):
    session_id: UUID
    archetype_key: str
    modules: list[LearningModuleSummary]
    mastery_pct: int
    streak_days: int


class SlideItem(LearningModel):
    id: UUID
    index: int
    lesson_seq: int
    lesson_title: str
    seq: int
    kind: str
    title: str
    content: list[SlideBlock]
    objective_code: str | None = None
    completed: bool


class ModuleProgress(LearningModel):
    slides_total: int
    slides_completed: int
    current_slide_index: int


class QuizGate(LearningModel):
    """Plan 04 owns the pass rule; Phase 3 only reports the gate state."""

    state: Literal["locked", "available", "passed"] = "locked"
    available: bool = False
    planned_phase: int = 4


class ModuleDetailResponse(LearningModel):
    session_id: UUID
    module: LearningModuleSummary
    slides: list[SlideItem]
    progress: ModuleProgress
    quiz: QuizGate


class SlideCompleteRequest(LearningModel):
    request_id: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=8, max_length=128)
    ]
    time_on_slide_ms: int | None = Field(default=None, ge=0, le=24 * 60 * 60 * 1000)


class SlideCompleteResponse(LearningModel):
    slide_id: UUID
    completed: bool
    already_completed: bool
    module_progress: ModuleProgress
    next_slide_index: int | None = None


class LearningEventItem(LearningModel):
    id: UUID
    verb: str
    object_id: str
    result: dict | None = None
    context: dict
    occurred_at: datetime
