"""Unit tests for the turn-less learning decision recorder (Plan 06 W6.3).

The recorder writes ``audit.decision_events`` rows with ``turn_id = NULL``; the
schema work that makes that legal lives in migration ``022``. These tests drive
the recorder with a fake session so the SQL shape, the event-type allowlist, and
the shared privacy guard are all pinned without a database.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest

from app.services.decision_trace import TracePrivacyError
from app.services.learning_trace import LEARNING_EVENT_TYPES, learning_trace


class _FakeResult:
    def mappings(self) -> _FakeResult:
        return self

    def first(self) -> None:
        return None


class _FakeSession:
    """Captures ``execute`` calls so the emitted SQL + params are assertable."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def execute(self, statement: Any, params: dict[str, Any] | None = None) -> _FakeResult:
        self.calls.append((str(statement), dict(params or {})))
        return _FakeResult()


def test_event_type_allowlist_is_exactly_the_ten_learning_events() -> None:
    assert LEARNING_EVENT_TYPES == {
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


@pytest.mark.asyncio
async def test_record_writes_a_turn_less_append_only_row() -> None:
    session = _FakeSession()
    session_id = uuid4()
    recorder = learning_trace(session, session_id)  # type: ignore[arg-type]

    await recorder.record(
        "learning_slide_completed",
        "learning_repository",
        "v1",
        "Student completed a slide.",
        "slide_completed",
        outputs={"slides_completed": 1},
        entity_refs={"slide_id": "abc"},
    )

    assert len(session.calls) == 1
    sql, params = session.calls[0]
    assert "INSERT INTO audit.decision_events" in sql
    assert "NULL" in sql  # turn_id is always NULL for learning writes
    assert "CAST(:event_type AS audit.decision_event_type)" in sql
    assert params["session_id"] == session_id
    assert params["sequence"] == 1
    assert params["event_type"] == "learning_slide_completed"
    assert params["outputs"] == '{"slides_completed": 1}'
    assert params["entity_refs"] == '{"slide_id": "abc"}'


@pytest.mark.asyncio
async def test_sequence_increments_and_correlation_is_stable_per_recorder() -> None:
    session = _FakeSession()
    recorder = learning_trace(session, uuid4())  # type: ignore[arg-type]

    await recorder.record("learning_quiz_drawn", "quiz_repository", "v1", "d", "r")
    await recorder.record("learning_quiz_scored", "quiz_repository", "v1", "d", "r")

    first, second = session.calls
    assert first[1]["sequence"] == 1
    assert second[1]["sequence"] == 2
    assert first[1]["correlation_id"] == second[1]["correlation_id"]
    assert isinstance(first[1]["correlation_id"], UUID)


@pytest.mark.asyncio
async def test_unknown_event_type_is_rejected() -> None:
    recorder = learning_trace(_FakeSession(), uuid4())  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="not a learning decision event"):
        await recorder.record("turn_started", "turn_processor", "v2", "d", "r")


@pytest.mark.asyncio
async def test_raw_student_text_is_rejected_in_inputs_and_outputs() -> None:
    recorder = learning_trace(_FakeSession(), uuid4())  # type: ignore[arg-type]
    with pytest.raises(TracePrivacyError):
        await recorder.record(
            "learning_checkin_answered",
            "checkin_repository",
            "v1",
            "d",
            "r",
            inputs={"student_text": "I love maps"},
        )
    with pytest.raises(TracePrivacyError):
        await recorder.record(
            "learning_checkin_answered",
            "checkin_repository",
            "v1",
            "d",
            "r",
            outputs={"nested": [{"content": "raw"}]},
        )
