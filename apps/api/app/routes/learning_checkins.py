"""Plan 05 boundary: check-in delivery and responses are not implemented yet.

Phase 3 owns the tracking stream those check-ins will read from
(``learning.learning_events``). The scheduler, budgets, and advice ladder are
Plan 05.
"""

from uuid import UUID

from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["learning"])


def _not_implemented(endpoint: str) -> HTTPException:
    return HTTPException(
        status_code=501,
        detail={
            "error": "not_implemented",
            "endpoint": endpoint,
            "planned_phase": 5,
            "note": "Check-in scheduling and the advice ladder land in Plan 05.",
        },
    )


@router.get("/sessions/{session_id}/learning/checkins")
async def list_checkins(session_id: UUID):
    raise _not_implemented("GET checkins")


@router.post("/sessions/{session_id}/learning/checkins")
async def create_checkin(session_id: UUID):
    raise _not_implemented("POST checkins")


@router.post("/sessions/{session_id}/learning/checkins/{checkin_id}")
async def respond_to_checkin(session_id: UUID, checkin_id: UUID):
    raise _not_implemented("POST checkins/{id}")
