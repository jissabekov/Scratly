from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db

router = APIRouter(tags=["teacher"])


@router.get("/sessions/{session_id}/decision-trace")
async def decision_trace(
    session_id: UUID,
    correlation_id: UUID | None = None,
    limit: int = Query(default=250, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    """Return ordered, privacy-safe explanations for decisions in a session."""
    result = await db.execute(
        text(
            """
            SELECT id, turn_id, correlation_id, sequence, event_type::text,
                   component, component_version, decision_summary, reason_code,
                   inputs, outputs, entity_refs, llm_run_id, duration_ms, created_at
              FROM audit.decision_events
             WHERE session_id = :session_id
               AND (:correlation_id IS NULL OR correlation_id = :correlation_id)
             ORDER BY created_at, turn_id, sequence
             LIMIT :limit
            """
        ),
        {
            "session_id": session_id,
            "correlation_id": correlation_id,
            "limit": limit,
        },
    )
    events = [dict(row) for row in result.mappings()]
    return {"session_id": session_id, "events": events}


@router.get("/sessions/{session_id}/{view}")
async def inspect(session_id: UUID, view: str):
    allowed = {
        "profile",
        "evidence",
        "transcript",
        "profile-history",
        "contradictions",
        "question-history",
        "why-next-question",
        "project-fit",
    }
    if view not in allowed:
        raise HTTPException(status_code=404, detail="Unknown inspection view")
    return {"session_id": session_id, "view": view, "items": []}
