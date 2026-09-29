"""Progress check-ins, dismissal, and the coach summary (Plan 05 W5.3).

``GET`` delivers (or resumes) the next deterministic check-in; ``POST`` scores
one response idempotently by ``request_id``; ``PATCH`` dismisses it (doubling the
cooldown); ``GET .../summary`` backs the progress dashboard. All writes touch
``learning.*`` only — check-in answers are learning evidence, never assessment
evidence (hard rules 2/4).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.contracts.learning_checkin import (
    CheckinDeliverResponse,
    CheckinDismissRequest,
    CheckinDismissResponse,
    CheckinRespondRequest,
    CheckinRespondResponse,
    CoachSummaryResponse,
)
from app.deps import get_checkin_repo
from app.repository.learning_checkin import CheckinConflictError, CheckinRepository

router = APIRouter(tags=["learning"])


@router.get(
    "/sessions/{session_id}/learning/checkins",
    response_model=CheckinDeliverResponse,
)
async def deliver_checkin(
    session_id: UUID,
    repo: CheckinRepository = Depends(get_checkin_repo),
):
    result = await repo.deliver(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return result


@router.post(
    "/sessions/{session_id}/learning/checkins/{checkin_id}",
    response_model=CheckinRespondResponse,
)
async def respond_to_checkin(
    session_id: UUID,
    checkin_id: UUID,
    body: CheckinRespondRequest,
    repo: CheckinRepository = Depends(get_checkin_repo),
):
    try:
        result = await repo.respond(session_id, checkin_id, body)
    except CheckinConflictError as err:
        raise HTTPException(status_code=409, detail=str(err)) from None
    if result is None:
        raise HTTPException(status_code=404, detail="Check-in not found for this session")
    return result


@router.patch(
    "/sessions/{session_id}/learning/checkins/{checkin_id}",
    response_model=CheckinDismissResponse,
)
async def dismiss_checkin(
    session_id: UUID,
    checkin_id: UUID,
    body: CheckinDismissRequest,
    repo: CheckinRepository = Depends(get_checkin_repo),
):
    result = await repo.dismiss(session_id, checkin_id, body)
    if result is None:
        raise HTTPException(status_code=404, detail="Check-in not found for this session")
    return result


@router.get(
    "/sessions/{session_id}/learning/summary",
    response_model=CoachSummaryResponse,
)
async def coach_summary(
    session_id: UUID,
    repo: CheckinRepository = Depends(get_checkin_repo),
):
    result = await repo.summary(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return result
