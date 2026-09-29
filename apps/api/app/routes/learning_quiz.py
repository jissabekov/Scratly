"""Module quiz delivery and submission (Plan 04 W4.4).

``GET`` draws (or resumes) the current form's 5 items; ``POST`` scores one
attempt idempotently by ``request_id`` and returns the gate decision. Both
write only to ``learning.*`` — quiz answers are learning evidence, never
assessment evidence (hard rules 2/4).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.contracts.learning_quiz import (
    QuizAttemptRequest,
    QuizAttemptResponse,
    QuizDrawResponse,
    QuizItemCheckRequest,
    QuizItemCheckResponse,
)
from app.deps import get_quiz_repo
from app.repository.learning_quiz import QuizConflictError, QuizRepository

router = APIRouter(tags=["learning"])


@router.get(
    "/sessions/{session_id}/learning/modules/{module_id}/quiz",
    response_model=QuizDrawResponse,
)
async def next_quiz_attempt(
    session_id: UUID,
    module_id: UUID,
    repo: QuizRepository = Depends(get_quiz_repo),
):
    result = await repo.draw(session_id, module_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Module not found for this session")
    return result


@router.post(
    "/sessions/{session_id}/learning/quiz-attempts/{attempt_id}/responses",
    response_model=QuizItemCheckResponse,
)
async def check_quiz_item(
    session_id: UUID,
    attempt_id: UUID,
    body: QuizItemCheckRequest,
    repo: QuizRepository = Depends(get_quiz_repo),
):
    try:
        result = await repo.check_item(session_id, attempt_id, body)
    except QuizConflictError as err:
        raise HTTPException(status_code=409, detail=str(err)) from None
    if result is None:
        raise HTTPException(status_code=404, detail="Quiz item not found for this attempt")
    return result


@router.post(
    "/sessions/{session_id}/learning/quiz-attempts",
    response_model=QuizAttemptResponse,
)
async def submit_quiz_attempt(
    session_id: UUID,
    body: QuizAttemptRequest,
    repo: QuizRepository = Depends(get_quiz_repo),
):
    try:
        result = await repo.submit(session_id, body)
    except QuizConflictError as err:
        raise HTTPException(status_code=409, detail=str(err)) from None
    if result is None:
        raise HTTPException(status_code=404, detail="Quiz attempt not found for this session")
    return result
