from typing import Any
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
        "learning-progress": _learning_progress,
        "quiz-history": _quiz_history,
        "interventions": _interventions,
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
        dim_state: dict[str, Any] = next(
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


# --- learning track views (Plan 06 W6.3) ------------------------------------
#
# Read-only projections over the `learning` schema. They mirror the assessment
# views' shape (`{items: [...]}`) so the teacher console renders them with the
# same generic table component. Nothing here writes state.


async def _learning_progress(db: AsyncSession, session_id: UUID) -> list[dict]:
    """Per-module slide progress, quiz gate, mastery, and check-in budget."""
    items: list[dict] = []

    modules = await db.execute(
        text(
            """
            SELECT m.slug, m.seq, m.title,
                   pr.slides_completed, pr.slides_total, pr.time_on_module_ms,
                   pr.last_slide_id::text AS last_slide_id, pr.updated_at,
                   COALESCE((
                     SELECT count(*) FROM learning.quiz_attempts qa
                      WHERE qa.session_id = :session_id AND qa.module_id = m.id
                        AND qa.submitted_at IS NOT NULL
                   ), 0) AS quiz_attempts,
                   COALESCE((
                     SELECT bool_or(qa.passed) FROM learning.quiz_attempts qa
                      WHERE qa.session_id = :session_id AND qa.module_id = m.id
                   ), false) AS quiz_passed,
                   'module' AS row_kind
              FROM learning.progress_rollups pr
              JOIN learning.modules m ON m.id = pr.module_id
             WHERE pr.session_id = :session_id
             ORDER BY m.seq
            """
        ),
        {"session_id": session_id},
    )
    items.extend(dict(row) for row in modules.mappings())

    mastery = await db.execute(
        text(
            """
            SELECT o.code AS objective_code, o.label, o.is_critical,
                   m.slug AS module_slug, ms.p_mastery, ms.state::text AS state,
                   ms.correct_count, ms.wrong_count, ms.elo, ms.evidence_count,
                   ms.last_evidence_at, 'mastery' AS row_kind
              FROM learning.mastery_states ms
              JOIN learning.objectives o ON o.id = ms.objective_id
              JOIN learning.modules m ON m.id = o.module_id
             WHERE ms.session_id = :session_id
             ORDER BY m.seq, o.ordinal
            """
        ),
        {"session_id": session_id},
    )
    items.extend(dict(row) for row in mastery.mappings())

    checkins = await db.execute(
        text(
            """
            SELECT count(*) FILTER (WHERE delivered_at IS NOT NULL) AS checkins_delivered,
                   count(*) FILTER (WHERE responded_at IS NOT NULL) AS checkins_answered,
                   count(*) FILTER (WHERE dismissed) AS checkins_dismissed,
                   'checkin_budget' AS row_kind
              FROM learning.checkin_events
             WHERE session_id = :session_id
            """
        ),
        {"session_id": session_id},
    )
    items.extend(dict(row) for row in checkins.mappings())
    return items


async def _quiz_history(db: AsyncSession, session_id: UUID) -> list[dict]:
    """Every quiz attempt with its form, score, gate outcome, and replay key."""
    result = await db.execute(
        text(
            """
            SELECT qa.id::text AS id, m.slug AS module_slug, m.title AS module_title,
                   qa.attempt_no, qa.form_id, qa.score, qa.passed, qa.provisional,
                   qa.critical_missed, qa.request_id, qa.started_at, qa.submitted_at,
                   (SELECT count(*) FROM learning.quiz_responses r
                     WHERE r.attempt_id = qa.id) AS responses,
                   (SELECT count(*) FROM learning.quiz_responses r
                     WHERE r.attempt_id = qa.id AND r.correct) AS correct
              FROM learning.quiz_attempts qa
              JOIN learning.modules m ON m.id = qa.module_id
             WHERE qa.session_id = :session_id
             ORDER BY qa.started_at
            """
        ),
        {"session_id": session_id},
    )
    return [dict(row) for row in result.mappings()]


async def _interventions(db: AsyncSession, session_id: UUID) -> list[dict]:
    """The advice escalation ladder plus the spaced-repetition card state."""
    items: list[dict] = []

    interventions = await db.execute(
        text(
            """
            SELECT i.id::text AS id, i.level::text AS level, i.trigger_rule,
                   o.code AS objective_code, i.content, i.request_id,
                   i.created_at, i.resolved_at, 'intervention' AS row_kind
              FROM learning.interventions i
         LEFT JOIN learning.objectives o ON o.id = i.objective_id
             WHERE i.session_id = :session_id
             ORDER BY i.created_at
            """
        ),
        {"session_id": session_id},
    )
    items.extend(dict(row) for row in interventions.mappings())

    cards = await db.execute(
        text(
            """
            SELECT rc.objective_id::text AS id, o.code AS objective_code, o.label,
                   rc.ease, rc.interval_days, rc.due_at, rc.reps, rc.lapses,
                   (rc.due_at <= now()) AS overdue, 'retention_card' AS row_kind
              FROM learning.retention_cards rc
              JOIN learning.objectives o ON o.id = rc.objective_id
             WHERE rc.session_id = :session_id
             ORDER BY rc.due_at
            """
        ),
        {"session_id": session_id},
    )
    items.extend(dict(row) for row in cards.mappings())
    return items
