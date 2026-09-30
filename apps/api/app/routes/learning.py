"""Learning hub / module / slide-completion endpoints (Plan 03 W3.2).

Reads are cheap projections; the single write (slide completion) is idempotent
by ``request_id`` and lands in one DB transaction. Quiz and check-in endpoints
live behind their own routers (``learning_quiz``, ``learning_checkins``) so the
Plan 04/05 boundaries stay explicit.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.contracts.learning import (
    LearningHubResponse,
    ModuleDetailResponse,
    SlideCompleteRequest,
    SlideCompleteResponse,
)
from app.deps import get_learning_repo
from app.repository.learning import LearningRepository, SlideConflictError

router = APIRouter(tags=["learning"])


@router.get("/sessions/{session_id}/learning", response_model=LearningHubResponse)
async def learning_hub(session_id: UUID, repo: LearningRepository = Depends(get_learning_repo)):
    hub = await repo.hub(session_id)
    if hub is None:
        raise HTTPException(status_code=404, detail="Session not found")
    await repo.record_hub_viewed(session_id, hub)
    return hub


@router.get(
    "/sessions/{session_id}/learning/modules/{module_id}",
    response_model=ModuleDetailResponse,
)
async def learning_module(
    session_id: UUID,
    module_id: UUID,
    repo: LearningRepository = Depends(get_learning_repo),
):
    detail = await repo.module_detail(session_id, module_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Module not found for this session")
    return detail


@router.post(
    "/sessions/{session_id}/learning/slides/{slide_id}/complete",
    response_model=SlideCompleteResponse,
)
async def complete_slide(
    session_id: UUID,
    slide_id: UUID,
    body: SlideCompleteRequest,
    repo: LearningRepository = Depends(get_learning_repo),
):
    try:
        result = await repo.complete_slide(
            session_id, slide_id, body.request_id, body.time_on_slide_ms
        )
    except SlideConflictError as err:
        raise HTTPException(status_code=409, detail=str(err)) from None
    if result is None:
        raise HTTPException(status_code=404, detail="Slide not found for this session")
    return result
