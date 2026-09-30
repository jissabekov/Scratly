"""Turn-less, append-only audit records for the learning domain (Plan 06 W6.3).

Learning writes are not assessment turns: they have no ``conversation.turns``
row, so they record into ``audit.decision_events`` with ``turn_id = NULL``.
Migration ``022`` relaxes that column and adds a partial unique index on
``(correlation_id, sequence)`` for those rows, since the table-level
``UNIQUE (turn_id, sequence)`` cannot constrain NULL turn ids.

The privacy guard is shared with the assessment recorder, so neither domain can
leak raw student text into the audit schema (hard rule 2).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.decision_trace import assert_no_raw_text

LEARNING_EVENT_TYPES = frozenset(
    {
        "learning_hub_viewed",
        "learning_slide_completed",
        "learning_quiz_drawn",
        "learning_quiz_scored",
        "learning_module_unlocked",
        "learning_checkin_delivered",
        "learning_checkin_answered",
        "learning_checkin_dismissed",
        "learning_intervention_opened",
        "learning_retention_card_due",
    }
)


@dataclass
class LearningTraceRecorder:
    """Append-only recorder for one learning write (one correlation id)."""

    session: AsyncSession
    session_id: UUID
    correlation_id: UUID = field(default_factory=uuid4)
    sequence: int = 0

    async def record(
        self,
        event_type: str,
        component: str,
        component_version: str,
        decision_summary: str,
        reason_code: str,
        *,
        inputs: dict[str, Any] | None = None,
        outputs: dict[str, Any] | None = None,
        entity_refs: dict[str, Any] | None = None,
    ) -> None:
        """Append one learning decision event, rejecting raw student text."""
        if event_type not in LEARNING_EVENT_TYPES:
            raise ValueError(f"{event_type!r} is not a learning decision event")
        safe_inputs, safe_outputs = inputs or {}, outputs or {}
        assert_no_raw_text(safe_inputs, "inputs")
        assert_no_raw_text(safe_outputs, "outputs")
        self.sequence += 1
        await self.session.execute(
            text(
                """
                INSERT INTO audit.decision_events
                    (session_id, turn_id, correlation_id, sequence, event_type,
                     component, component_version, decision_summary, reason_code,
                     inputs, outputs, entity_refs)
                VALUES
                    (:session_id, NULL, :correlation_id, :sequence,
                     CAST(:event_type AS audit.decision_event_type),
                     :component, :component_version, :decision_summary, :reason_code,
                     CAST(:inputs AS jsonb), CAST(:outputs AS jsonb),
                     CAST(:entity_refs AS jsonb))
                """
            ),
            {
                "session_id": self.session_id,
                "correlation_id": self.correlation_id,
                "sequence": self.sequence,
                "event_type": event_type,
                "component": component,
                "component_version": component_version,
                "decision_summary": decision_summary,
                "reason_code": reason_code,
                "inputs": json.dumps(safe_inputs),
                "outputs": json.dumps(safe_outputs),
                "entity_refs": json.dumps(entity_refs or {}),
            },
        )


def learning_trace(session: AsyncSession, session_id: UUID) -> LearningTraceRecorder:
    """Build a recorder for one learning write on ``session_id``."""
    return LearningTraceRecorder(session=session, session_id=session_id)
