from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import Field

from .assessment import StrictModel


class DecisionEventType(StrEnum):
    TURN_STARTED = "turn_started"
    EVIDENCE_PROPOSED = "evidence_proposed"
    EVIDENCE_VALIDATED = "evidence_validated"
    PROFILE_REDUCED = "profile_reduced"
    CONTRADICTION_EVALUATED = "contradiction_evaluated"
    CONTRADICTION_RESOLVED = "contradiction_resolved"
    STAGE_DERIVED = "stage_derived"
    QUESTION_TARGET_SELECTED = "question_target_selected"
    QUESTION_WRITTEN = "question_written"
    QUESTION_FALLBACK_USED = "question_fallback_used"
    QUESTION_QUALITY_GATE = "question_quality_gate"
    TURN_COMPLETED = "turn_completed"


class DecisionEvent(StrictModel):
    id: UUID
    session_id: UUID
    turn_id: UUID
    correlation_id: UUID
    sequence: int = Field(gt=0)
    event_type: DecisionEventType
    component: str
    component_version: str
    decision_summary: str
    reason_code: str
    inputs: dict[str, Any]
    outputs: dict[str, Any]
    entity_refs: dict[str, Any]
    llm_run_id: UUID | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    created_at: datetime


class DecisionTrace(StrictModel):
    session_id: UUID
    correlation_id: UUID
    events: list[DecisionEvent]
