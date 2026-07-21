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
            SELECT id, turn_id, sequence, role::text AS role, content,
                   message_kind::text AS message_kind, created_at
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
    opp_fits = await db.execute(
        text(
            """
            SELECT pf.id::text AS id, o.key AS opportunity_key, o.title, pf.eligible,
                   pf.topic_score, pf.work_mode_score, pf.motivation_score,
                   pf.total_score, pf.failed_constraints, pf.scope_adjustments,
                   pf.algorithm_version, pf.created_at, o.geo_regions, o.geo_places,
                   o.source_url, 'opportunity' AS fit_kind
              FROM matching.project_fits pf
              JOIN matching.opportunities o ON o.id = pf.opportunity_id
             WHERE pf.session_id = :session_id
             ORDER BY pf.eligible DESC, pf.total_score DESC, o.key
            """
        ),
        {"session_id": session_id},
    )
    items = [dict(row) for row in opp_fits.mappings()]

    generated = await db.execute(
        text(
            """
            SELECT p.id::text AS id, p.title, p.summary, p.composer_version,
                   p.created_at,
                   COALESCE(
                     json_agg(
                       json_build_object('kind', c.kind::text, 'ref_id', c.ref_id::text)
                     ) FILTER (WHERE c.ref_id IS NOT NULL),
                     '[]'
                   ) AS citations
              FROM matching.generated_projects p
         LEFT JOIN matching.generated_project_citations c ON c.project_id = p.id
             WHERE p.session_id = :session_id
             GROUP BY p.id
             ORDER BY p.created_at DESC
            """
        ),
        {"session_id": session_id},
    )
    for row in generated.mappings():
        item = dict(row)
        if isinstance(item.get("citations"), str):
            import json as _json

            item["citations"] = _json.loads(item["citations"])
        item["fit_kind"] = "generated_project"
        item["eligible"] = True
        item["total_score"] = None
        items.append(item)

    findings = await db.execute(
        text(
            """
            SELECT f.id::text AS id, f.url AS source_url, f.title, f.snippet,
                   f.publisher, f.rank, r.query, r.status::text AS run_status,
                   r.created_at, 'research_finding' AS fit_kind
              FROM matching.research_findings f
              JOIN matching.research_runs r ON r.id = f.research_run_id
             WHERE r.session_id = :session_id
             ORDER BY f.created_at DESC
             LIMIT 30
            """
        ),
        {"session_id": session_id},
    )
    for row in findings.mappings():
        item = dict(row)
        item["eligible"] = None
        item["total_score"] = None
        item["failed_constraints"] = []
        items.append(item)

    if items:
        return items

    opportunities = await db.execute(
        text(
            """
            SELECT key AS opportunity_key, title, topics, work_modes, motivations,
                   geo_regions, geo_places, hard_constraints, source_url,
                   'catalog' AS fit_kind
              FROM matching.opportunities
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
            "note": "No project-fit computation yet for this session; showing catalog",
        }
        for row in opportunities.mappings()
    ]
