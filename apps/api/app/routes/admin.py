from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_repo
from app.repository import AssessmentRepository

router = APIRouter(tags=["teacher"])


@router.get("/sessions")
async def list_sessions(
    limit: int = Query(default=50, ge=1, le=200),
    repo: AssessmentRepository = Depends(get_repo),
):
    return {"items": await repo.list_sessions(limit=limit)}


@router.get("/sessions/{session_id}/decision-trace")
async def decision_trace(
    session_id: UUID,
    correlation_id: UUID | None = None,
    limit: int = Query(default=250, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    """Return ordered, privacy-safe explanations for decisions in a session."""
    if correlation_id is None:
        result = await db.execute(
            text(
                """
                SELECT id, turn_id, correlation_id, sequence, event_type::text,
                       component, component_version, decision_summary, reason_code,
                       inputs, outputs, entity_refs, llm_run_id, duration_ms, created_at
                  FROM audit.decision_events
                 WHERE session_id = :session_id
                 ORDER BY created_at, turn_id, sequence
                 LIMIT :limit
                """
            ),
            {"session_id": session_id, "limit": limit},
        )
    else:
        result = await db.execute(
            text(
                """
                SELECT id, turn_id, correlation_id, sequence, event_type::text,
                       component, component_version, decision_summary, reason_code,
                       inputs, outputs, entity_refs, llm_run_id, duration_ms, created_at
                  FROM audit.decision_events
                 WHERE session_id = :session_id
                   AND correlation_id = :correlation_id
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
async def inspect(
    session_id: UUID,
    view: str,
    db: AsyncSession = Depends(get_db),
    repo: AssessmentRepository = Depends(get_repo),
):
    session = await repo.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    handlers = {
        "profile": _profile,
        "evidence": _evidence,
        "transcript": _transcript,
        "profile-history": _profile_history,
        "contradictions": _contradictions,
        "question-history": _question_history,
        "why-next-question": _why_next_question,
        "project-fit": _project_fit,
    }
    handler = handlers.get(view)
    if handler is None:
        raise HTTPException(status_code=404, detail="Unknown inspection view")
    items = await handler(db, session_id)
    return {"session_id": session_id, "view": view, "items": items}


async def _profile(db: AsyncSession, session_id: UUID) -> list[dict]:
    result = await db.execute(
        text(
            """
            SELECT d.key, d.label, d.required, c.status::text AS status,
                   ps.state
              FROM assessment.dimensions d
              JOIN assessment.coverage c
                ON c.dimension_id = d.id AND c.session_id = :session_id
         LEFT JOIN LATERAL (
                SELECT state
                  FROM assessment.profile_snapshots
                 WHERE session_id = :session_id
                 ORDER BY version DESC
                 LIMIT 1
              ) ps ON true
             ORDER BY d.ordinal
            """
        ),
        {"session_id": session_id},
    )
    items = []
    for row in result.mappings():
        state = row["state"] or {}
        if isinstance(state, str):
            import json

            state = json.loads(state)
        dim_state = next(
            (d for d in state.get("dimensions", []) if d.get("key") == row["key"]),
            {},
        )
        items.append(
            {
                "key": row["key"],
                "label": row["label"],
                "required": row["required"],
                "status": row["status"],
                "value": dim_state.get("value"),
                "confidence": dim_state.get("confidence"),
            }
        )
    return items


async def _evidence(db: AsyncSession, session_id: UUID) -> list[dict]:
    result = await db.execute(
        text(
            """
            SELECT e.id, d.key AS dimension_key, e.value_key, e.strength,
                   e.polarity, e.status::text AS status, e.rejection_reason,
                   e.exact_source_quote, e.created_at,
                   ARRAY(
                     SELECT es.message_id::text
                       FROM assessment.evidence_sources es
                      WHERE es.evidence_id = e.id
                   ) AS source_message_ids
              FROM assessment.evidence e
              JOIN assessment.dimensions d ON d.id = e.dimension_id
             WHERE e.session_id = :session_id
             ORDER BY e.created_at
            """
        ),
        {"session_id": session_id},
    )
    return [dict(row) for row in result.mappings()]


async def _transcript(db: AsyncSession, session_id: UUID) -> list[dict]:
    result = await db.execute(
        text(
            """
            SELECT id, turn_id, sequence, role::text AS role, content, created_at
              FROM conversation.messages
             WHERE session_id = :session_id
             ORDER BY sequence
            """
        ),
        {"session_id": session_id},
    )
    return [dict(row) for row in result.mappings()]


async def _profile_history(db: AsyncSession, session_id: UUID) -> list[dict]:
    result = await db.execute(
        text(
            """
            SELECT id, version, reducer_version, state, evidence_boundary, created_at
              FROM assessment.profile_snapshots
             WHERE session_id = :session_id
             ORDER BY version
            """
        ),
        {"session_id": session_id},
    )
    return [dict(row) for row in result.mappings()]


async def _contradictions(db: AsyncSession, session_id: UUID) -> list[dict]:
    result = await db.execute(
        text(
            """
            SELECT c.id, d.key AS dimension_key, c.status::text AS status,
                   c.resolution, c.created_at, c.resolved_at
              FROM assessment.contradictions c
              JOIN assessment.dimensions d ON d.id = c.dimension_id
             WHERE c.session_id = :session_id
             ORDER BY c.created_at
            """
        ),
        {"session_id": session_id},
    )
    return [dict(row) for row in result.mappings()]


async def _question_history(db: AsyncSession, session_id: UUID) -> list[dict]:
    result = await db.execute(
        text(
            """
            SELECT q.id, q.turn_id, qi.key AS intent_key, q.target_key,
                   q.rationale, q.used_fallback, q.created_at,
                   m.content AS assistant_question
              FROM assessment.questions q
              JOIN assessment.question_intents qi ON qi.id = q.intent_id
         LEFT JOIN conversation.turns t ON t.id = q.turn_id
         LEFT JOIN conversation.messages m ON m.id = t.assistant_message_id
             WHERE q.session_id = :session_id
             ORDER BY q.created_at
            """
        ),
        {"session_id": session_id},
    )
    return [dict(row) for row in result.mappings()]


async def _why_next_question(db: AsyncSession, session_id: UUID) -> list[dict]:
    result = await db.execute(
        text(
            """
            SELECT id, turn_id, sequence, event_type::text AS event_type,
                   component, reason_code, decision_summary, inputs, outputs,
                   entity_refs, created_at
              FROM audit.decision_events
             WHERE session_id = :session_id
               AND event_type IN (
                 'question_target_selected',
                 'question_written',
                 'question_fallback_used',
                 'stage_derived'
               )
             ORDER BY created_at DESC, sequence DESC
             LIMIT 20
            """
        ),
        {"session_id": session_id},
    )
    return [dict(row) for row in result.mappings()]


async def _project_fit(db: AsyncSession, session_id: UUID) -> list[dict]:
    result = await db.execute(
        text(
            """
            SELECT pf.id, pa.key AS archetype_key, pa.title, pf.eligible,
                   pf.topic_score, pf.work_mode_score, pf.motivation_score,
                   pf.total_score, pf.failed_constraints, pf.scope_adjustments,
                   pf.created_at
              FROM matching.project_fits pf
              JOIN matching.project_archetypes pa ON pa.id = pf.archetype_id
             WHERE pf.session_id = :session_id
             ORDER BY pf.eligible DESC, pf.total_score DESC, pa.key
            """
        ),
        {"session_id": session_id},
    )
    items = [dict(row) for row in result.mappings()]
    if items:
        return items
    # No fits computed yet — show seeded archetypes as reference.
    archetypes = await db.execute(
        text(
            """
            SELECT key, title, topics, work_modes, motivations, hard_constraints
              FROM matching.project_archetypes
             WHERE active
             ORDER BY key
            """
        )
    )
    return [
        {
            **dict(row),
            "eligible": None,
            "total_score": None,
            "note": "No project-fit computation yet for this session",
        }
        for row in archetypes.mappings()
    ]
