"""Contract tests for the Phase 6 chat routing seam (Plan 06 W6.2/W6.5).

These pin the deterministic routing decision — when the terminal fast path
surfaces a learning check-in versus falling back to post-match feedback — and
the rollout seam (``learning_enabled`` defaults to false per session) without a
live server.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from app.contracts import (
    CheckinDeliverResponse,
    CheckinGate,
    CheckinItemView,
    CheckinKind,
    SessionCreateRequest,
    TurnResponse,
)
from app.repository.assessment import TurnOutcome
from app.services.turn_processor import _maybe_deliver_checkin, _progress_checkin_reply


class _FakeTx:
    def __init__(self, *, learning: bool) -> None:
        self._learning = learning

    async def learning_enabled(self) -> bool:
        return self._learning


class _FakeCheckinRepo:
    def __init__(self, response: CheckinDeliverResponse | None) -> None:
        self._response = response
        self.calls: list[tuple[Any, bool]] = []

    async def deliver(
        self, session_id: Any, *, commit: bool = True
    ) -> CheckinDeliverResponse | None:
        self.calls.append((session_id, commit))
        return self._response


def _delivered(*, gate: CheckinGate = CheckinGate.AVAILABLE) -> CheckinDeliverResponse:
    session_id = uuid4()
    item = (
        CheckinItemView(
            id=uuid4(),
            objective_code="OBJ-1",
            objective_label="Reading a dataset",
            kind=CheckinKind.MINI_EXERCISE,
            prompt="Which summary best describes what the column means?",
            trigger_reason="section_complete",
        )
        if gate == CheckinGate.AVAILABLE
        else None
    )
    return CheckinDeliverResponse(
        session_id=session_id,
        gate=gate,
        item=item,
        event_id=uuid4() if item else None,
        checkins_used=1,
    )


@pytest.mark.asyncio
async def test_disabled_learning_never_delivers() -> None:
    repo = _FakeCheckinRepo(_delivered())
    result = await _maybe_deliver_checkin(_FakeTx(learning=False), repo, uuid4())
    assert result is None
    assert repo.calls == []  # gate is not even consulted when learning is off


@pytest.mark.asyncio
async def test_missing_repo_is_a_noop() -> None:
    assert await _maybe_deliver_checkin(_FakeTx(learning=True), None, uuid4()) is None


@pytest.mark.asyncio
async def test_enabled_and_available_delivers_inside_the_turn_transaction() -> None:
    repo = _FakeCheckinRepo(_delivered())
    result = await _maybe_deliver_checkin(_FakeTx(learning=True), repo, uuid4())
    assert result is not None and result.item is not None
    # The delivery must NOT commit on its own: it shares the turn transaction.
    assert repo.calls and repo.calls[0][1] is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "gate", [CheckinGate.COOLDOWN, CheckinGate.BUDGET_EXHAUSTED, CheckinGate.QUIZ_ACTIVE]
)
async def test_non_available_gate_falls_back_to_post_match(gate: CheckinGate) -> None:
    repo = _FakeCheckinRepo(_delivered(gate=gate))
    assert await _maybe_deliver_checkin(_FakeTx(learning=True), repo, uuid4()) is None


def test_progress_checkin_reply_names_the_objective_and_asks_one_question() -> None:
    reply = _progress_checkin_reply(_delivered())
    assert "Reading a dataset" in reply
    assert reply.count("?") == 1


def test_progress_checkin_reply_handles_an_item_less_delivery() -> None:
    assert "progress check-in" in _progress_checkin_reply(_delivered(gate=CheckinGate.NONE))


def test_turn_response_carries_the_learning_payload() -> None:
    delivered = _delivered()
    outcome = TurnOutcome(
        id=uuid4(),
        turn_id=uuid4(),
        content="Quick progress check-in",
        stage="complete",
        message_kind="progress_checkin",
        learning=delivered,
    )
    response = outcome.as_response()
    assert isinstance(response, TurnResponse)
    assert response.learning is not None
    assert response.learning.event_id == delivered.event_id


def test_session_create_request_defaults_to_none() -> None:
    assert SessionCreateRequest().learning_enabled is None
    assert SessionCreateRequest(learning_enabled=True).learning_enabled is True
