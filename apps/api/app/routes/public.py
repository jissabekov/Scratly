from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError

from app.contracts import TurnRequest, TurnResponse
from app.deps import get_context_builder, get_extractor, get_repo, get_writer
from app.repository import AssessmentRepository, TurnOutcome
from app.services.context_builder import ContextBuilder
from app.services.evidence_extractor import EvidenceExtractor
from app.services.azure_openai import QuestionWriter
from app.services.turn_processor import process_student_turn

router = APIRouter(tags=["student"])


@router.post("/sessions")
async def start_session(repo: AssessmentRepository = Depends(get_repo)):
    created = await repo.create_session()
    return {
        "session_id": created["session_id"],
        "student_id": created["student_id"],
        "stage": created["stage"],
    }


@router.get("/sessions/{session_id}")
async def resume_session(
    session_id: UUID, repo: AssessmentRepository = Depends(get_repo)
):
    session = await repo.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session_id": session["id"],
        "student_id": session["student_id"],
        "stage": session["stage"],
        "created_at": session["created_at"],
        "updated_at": session["updated_at"],
        "completed_at": session["completed_at"],
    }


@router.post("/sessions/{session_id}/turns", response_model=TurnResponse)
async def submit_turn(
    session_id: UUID,
    body: TurnRequest,
    repo: AssessmentRepository = Depends(get_repo),
    extractor: EvidenceExtractor = Depends(get_extractor),
    writer: QuestionWriter = Depends(get_writer),
    context_builder: ContextBuilder = Depends(get_context_builder),
):
    session = await repo.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    try:
        outcome = await process_student_turn(
            repo, extractor, writer, context_builder, session_id, body
        )
    except IntegrityError:
        # Concurrent idempotent retry lost the insert race; return the winner.
        outcome = await repo.completed_turn(session_id, body.idempotency_key)
        if outcome is None:
            raise HTTPException(
                status_code=409,
                detail="Turn conflict; retry with the same idempotency key",
            ) from None
    if isinstance(outcome, TurnOutcome):
        return outcome.as_response()
    raise HTTPException(status_code=500, detail="Turn processing returned no outcome")
