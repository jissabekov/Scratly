"""Async repository for the learning track (Plan 03).

All writes go through :meth:`LearningRepository.complete_slide`, which is one
DB transaction and idempotent by ``request_id``. This module never touches
``assessment.*`` — learning is a separate evidence stream (hard rules 2/4).
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.learning import (
    LearningHubResponse,
    LearningModuleSummary,
    ModuleDetailResponse,
    ModuleProgress,
    ModuleState,
    QuizGate,
    SlideCompleteResponse,
    SlideItem,
)
from app.services.learning_content import GENERIC_ARCHETYPE_KEY
from app.services.learning_progress import (
    XAPI_OBJECT_LESSON,
    XAPI_OBJECT_MODULE,
    XAPI_OBJECT_SLIDE,
    XAPI_VERB_COMPLETED,
    ModuleProgressView,
    compute_streak_days,
    derive_module_states,
    overall_mastery_pct,
    progress_pct,
    xapi_statement,
)

XAPI_VERB = "completed"


class SlideConflictError(Exception):
    """A ``request_id`` was reused for a different slide."""


class LearningRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    @asynccontextmanager
    async def transaction(self):
        try:
            yield
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

    async def session_student(self, session_id: UUID) -> dict[str, Any] | None:
        result = await self.session.execute(
            text(
                """
                SELECT id, student_id, stage::text AS stage
                  FROM core.sessions
                 WHERE id = :session_id
                """
            ),
            {"session_id": session_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def resolve_archetype_key(self, session_id: UUID) -> str:
        """Top eligible matched archetype for the session, else ``generic``."""
        result = await self.session.execute(
            text(
                """
                SELECT a.key
                  FROM matching.project_fits f
                  JOIN matching.project_archetypes a ON a.id = f.archetype_id
                 WHERE f.session_id = :session_id AND f.eligible AND a.active
                 ORDER BY f.total_score DESC, a.key
                 LIMIT 1
                """
            ),
            {"session_id": session_id},
        )
        row = result.first()
        return row[0] if row else GENERIC_ARCHETYPE_KEY

    async def _module_rows(self, archetype_key: str) -> list[dict[str, Any]]:
        result = await self.session.execute(
            text(
                """
                SELECT m.id, m.slug, m.seq, m.title, m.description, m.est_minutes,
                       (
                         SELECT count(*) FROM learning.slides s
                           JOIN learning.lessons l ON l.id = s.lesson_id
                          WHERE l.module_id = m.id
                       )::int AS slides_total
                  FROM learning.modules m
                 WHERE m.archetype_key = :archetype_key
                   AND m.status = 'published'
                 ORDER BY m.seq
                """
            ),
            {"archetype_key": archetype_key},
        )
        return [dict(row) for row in result.mappings()]

    async def _completion_counts(self, session_id: UUID) -> dict[UUID, int]:
        result = await self.session.execute(
            text(
                """
                SELECT l.module_id, count(*)::int AS completed
                  FROM learning.slide_completions c
                  JOIN learning.slides s ON s.id = c.slide_id
                  JOIN learning.lessons l ON l.id = s.lesson_id
                 WHERE c.session_id = :session_id
                 GROUP BY l.module_id
                """
            ),
            {"session_id": session_id},
        )
        return {row["module_id"]: row["completed"] for row in result.mappings()}

    async def _event_days(self, session_id: UUID) -> list[date]:
        result = await self.session.execute(
            text(
                """
                SELECT DISTINCT (occurred_at AT TIME ZONE 'UTC')::date AS day
                  FROM learning.learning_events
                 WHERE session_id = :session_id
                 ORDER BY day DESC
                """
            ),
            {"session_id": session_id},
        )
        return [row["day"] for row in result.mappings()]

    async def _resolved_modules(
        self, session_id: UUID
    ) -> tuple[str, list[dict[str, Any]], dict[UUID, int]]:
        archetype_key = await self.resolve_archetype_key(session_id)
        rows = await self._module_rows(archetype_key)
        if not rows and archetype_key != GENERIC_ARCHETYPE_KEY:
            archetype_key = GENERIC_ARCHETYPE_KEY
            rows = await self._module_rows(archetype_key)
        return archetype_key, rows, await self._completion_counts(session_id)

    async def hub(self, session_id: UUID) -> LearningHubResponse | None:
        session = await self.session_student(session_id)
        if session is None:
            return None
        archetype_key, rows, completed_by_module = await self._resolved_modules(session_id)

        views = [
            ModuleProgressView(
                module_id=row["id"],
                seq=row["seq"],
                slides_total=row["slides_total"],
                slides_completed=completed_by_module.get(row["id"], 0),
            )
            for row in rows
        ]
        states = derive_module_states(views)
        modules = [
            LearningModuleSummary(
                id=row["id"],
                slug=row["slug"],
                seq=row["seq"],
                title=row["title"],
                description=row["description"],
                est_minutes=row["est_minutes"],
                state=state,
                slides_total=row["slides_total"],
                slides_completed=view.slides_completed,
                progress_pct=progress_pct(view.slides_completed, row["slides_total"]),
                quiz_gate_locked=state is not ModuleState.PASSED,
            )
            for row, view, state in zip(rows, views, states, strict=True)
        ]
        days = await self._event_days(session_id)
        return LearningHubResponse(
            session_id=session_id,
            archetype_key=archetype_key,
            modules=modules,
            mastery_pct=overall_mastery_pct(views),
            streak_days=compute_streak_days(days, datetime.now(timezone.utc).date()),
        )

    async def module_detail(self, session_id: UUID, module_id: UUID) -> ModuleDetailResponse | None:
        hub = await self.hub(session_id)
        if hub is None:
            return None
        summary = next((module for module in hub.modules if module.id == module_id), None)
        if summary is None:
            return None

        result = await self.session.execute(
            text(
                """
                SELECT s.id, s.seq, s.kind::text AS kind, s.title, s.content,
                       o.code AS objective_code,
                       l.seq AS lesson_seq, l.title AS lesson_title,
                       EXISTS (
                         SELECT 1 FROM learning.slide_completions c
                          WHERE c.slide_id = s.id AND c.session_id = :session_id
                       ) AS completed
                  FROM learning.slides s
                  JOIN learning.lessons l ON l.id = s.lesson_id
             LEFT JOIN learning.objectives o ON o.id = s.objective_id
                 WHERE l.module_id = :module_id
                 ORDER BY l.seq, s.seq
                """
            ),
            {"session_id": session_id, "module_id": module_id},
        )
        slides = [
            SlideItem(
                id=row["id"],
                index=index,
                lesson_seq=row["lesson_seq"],
                lesson_title=row["lesson_title"],
                seq=row["seq"],
                kind=row["kind"],
                title=row["title"],
                content=row["content"],
                objective_code=row["objective_code"],
                completed=bool(row["completed"]),
            )
            for index, row in enumerate(result.mappings(), start=1)
        ]
        current = next((slide.index for slide in slides if not slide.completed), len(slides) or 1)
        return ModuleDetailResponse(
            session_id=session_id,
            module=summary,
            slides=slides,
            progress=ModuleProgress(
                slides_total=summary.slides_total,
                slides_completed=summary.slides_completed,
                current_slide_index=current,
            ),
            quiz=QuizGate(state="locked", available=False, planned_phase=4),
        )

    async def _slide_context(self, slide_id: UUID) -> dict[str, Any] | None:
        result = await self.session.execute(
            text(
                """
                SELECT s.id AS slide_id, s.seq AS slide_seq, s.title AS slide_title,
                       l.id AS lesson_id, l.seq AS lesson_seq, l.title AS lesson_title,
                       m.id AS module_id, m.title AS module_title, m.slug AS module_slug
                  FROM learning.slides s
                  JOIN learning.lessons l ON l.id = s.lesson_id
                  JOIN learning.modules m ON m.id = l.module_id
                 WHERE s.id = :slide_id
                """
            ),
            {"slide_id": slide_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def _counts_for(
        self, session_id: UUID, module_id: UUID, lesson_id: UUID
    ) -> dict[str, int]:
        result = await self.session.execute(
            text(
                """
                SELECT
                  (
                    SELECT count(*) FROM learning.slides s
                      JOIN learning.lessons l ON l.id = s.lesson_id
                     WHERE l.module_id = :module_id
                  )::int AS module_total,
                  (
                    SELECT count(*) FROM learning.slide_completions c
                      JOIN learning.slides s ON s.id = c.slide_id
                      JOIN learning.lessons l ON l.id = s.lesson_id
                     WHERE l.module_id = :module_id AND c.session_id = :session_id
                  )::int AS module_completed,
                  (
                    SELECT count(*) FROM learning.slides s WHERE s.lesson_id = :lesson_id
                  )::int AS lesson_total,
                  (
                    SELECT count(*) FROM learning.slide_completions c
                      JOIN learning.slides s ON s.id = c.slide_id
                     WHERE s.lesson_id = :lesson_id AND c.session_id = :session_id
                  )::int AS lesson_completed
                """
            ),
            {"session_id": session_id, "module_id": module_id, "lesson_id": lesson_id},
        )
        row = result.mappings().first()
        if row is None:
            return {
                "module_total": 0,
                "module_completed": 0,
                "lesson_total": 0,
                "lesson_completed": 0,
            }
        return dict(row)

    async def _record_event(
        self,
        *,
        student_id: UUID,
        session_id: UUID,
        request_id: str,
        verb_id: str,
        object_id: str,
        object_type: str,
        object_name: str,
        result: dict | None,
        context: dict | None,
    ) -> None:
        statement = xapi_statement(
            actor_name=str(student_id),
            verb_id=verb_id,
            object_id=object_id,
            object_type=object_type,
            object_name=object_name,
            result=result,
            context=context,
        )
        await self.session.execute(
            text(
                """
                INSERT INTO learning.learning_events
                    (student_id, session_id, actor, verb, object, result, context, request_id)
                VALUES (:student_id, :session_id, CAST(:actor AS jsonb), CAST(:verb AS jsonb),
                        CAST(:object AS jsonb), CAST(:result AS jsonb), CAST(:context AS jsonb),
                        :request_id)
                ON CONFLICT (session_id, request_id) DO NOTHING
                """
            ),
            {
                "student_id": student_id,
                "session_id": session_id,
                "actor": json.dumps(statement["actor"]),
                "verb": json.dumps(statement["verb"]),
                "object": json.dumps(statement["object"]),
                "result": json.dumps(statement["result"]) if statement.get("result") else None,
                "context": json.dumps(statement["context"]),
                "request_id": request_id,
            },
        )

    async def complete_slide(
        self,
        session_id: UUID,
        slide_id: UUID,
        request_id: str,
        time_on_slide_ms: int | None,
    ) -> SlideCompleteResponse | None:
        """Idempotently mark a slide complete and append tracking events."""
        session = await self.session_student(session_id)
        if session is None:
            return None
        context = await self._slide_context(slide_id)
        if context is None:
            return None

        async with self.transaction():
            inserted = (
                await self.session.execute(
                    text(
                        """
                        INSERT INTO learning.slide_completions
                            (student_id, session_id, slide_id, request_id, time_on_slide_ms)
                        VALUES (:student_id, :session_id, :slide_id, :request_id, :time_on_slide_ms)
                        ON CONFLICT DO NOTHING
                        RETURNING id
                        """
                    ),
                    {
                        "student_id": session["student_id"],
                        "session_id": session_id,
                        "slide_id": slide_id,
                        "request_id": request_id,
                        "time_on_slide_ms": time_on_slide_ms,
                    },
                )
            ).first() is not None

            if not inserted:
                existing = (
                    await self.session.execute(
                        text(
                            """
                            SELECT slide_id FROM learning.slide_completions
                             WHERE request_id = :request_id
                            """
                        ),
                        {"request_id": request_id},
                    )
                ).first()
                if existing is None or existing[0] != slide_id:
                    raise SlideConflictError("request_id already used for a different slide")

            module_id = context["module_id"]
            lesson_id = context["lesson_id"]
            counts = await self._counts_for(session_id, module_id, lesson_id)

            if inserted:
                await self._record_event(
                    student_id=session["student_id"],
                    session_id=session_id,
                    request_id=f"{request_id}:slide",
                    verb_id=XAPI_VERB_COMPLETED,
                    object_id=f"slide:{slide_id}",
                    object_type=XAPI_OBJECT_SLIDE,
                    object_name=context["slide_title"] or f"Slide {context['slide_seq']}",
                    result={
                        "completion": True,
                        "duration_ms": time_on_slide_ms,
                    },
                    context={"module_id": str(module_id), "lesson_id": str(lesson_id)},
                )
                if counts["lesson_completed"] >= counts["lesson_total"]:
                    await self._record_event(
                        student_id=session["student_id"],
                        session_id=session_id,
                        request_id=f"{request_id}:lesson",
                        verb_id=XAPI_VERB_COMPLETED,
                        object_id=f"lesson:{lesson_id}",
                        object_type=XAPI_OBJECT_LESSON,
                        object_name=context["lesson_title"],
                        result={"completion": True},
                        context={"module_id": str(module_id)},
                    )
                if counts["module_completed"] >= counts["module_total"]:
                    await self._record_event(
                        student_id=session["student_id"],
                        session_id=session_id,
                        request_id=f"{request_id}:module",
                        verb_id=XAPI_VERB_COMPLETED,
                        object_id=f"module:{module_id}",
                        object_type=XAPI_OBJECT_MODULE,
                        object_name=context["module_title"],
                        result={"completion": True},
                        context={"slug": context["module_slug"]},
                    )

            await self.session.execute(
                text(
                    """
                    INSERT INTO learning.progress_rollups
                        (session_id, module_id, slides_completed, slides_total,
                         time_on_module_ms, last_slide_id, updated_at)
                    VALUES (:session_id, :module_id, :completed, :total,
                            :duration, :slide_id, now())
                    ON CONFLICT (session_id, module_id) DO UPDATE SET
                        slides_completed = EXCLUDED.slides_completed,
                        slides_total = EXCLUDED.slides_total,
                        time_on_module_ms = learning.progress_rollups.time_on_module_ms
                                            + EXCLUDED.time_on_module_ms,
                        last_slide_id = EXCLUDED.last_slide_id,
                        updated_at = now()
                    """
                ),
                {
                    "session_id": session_id,
                    "module_id": module_id,
                    "completed": counts["module_completed"],
                    "total": counts["module_total"],
                    # Only a fresh completion adds time; an idempotent replay must not.
                    "duration": (time_on_slide_ms or 0) if inserted else 0,
                    "slide_id": slide_id,
                },
            )

            next_row = (
                await self.session.execute(
                    text(
                        """
                        SELECT s.id FROM learning.slides s
                          JOIN learning.lessons l ON l.id = s.lesson_id
                         WHERE l.module_id = :module_id
                           AND (l.seq, s.seq) > (
                             SELECT l2.seq, s2.seq FROM learning.slides s2
                               JOIN learning.lessons l2 ON l2.id = s2.lesson_id
                              WHERE s2.id = :slide_id
                           )
                         ORDER BY l.seq, s.seq
                         LIMIT 1
                        """
                    ),
                    {"module_id": module_id, "slide_id": slide_id},
                )
            ).first()

        detail = await self.module_detail(session_id, module_id)
        next_index = None
        if detail is not None and next_row is not None:
            next_index = next(
                (slide.index for slide in detail.slides if slide.id == next_row[0]), None
            )
        return SlideCompleteResponse(
            slide_id=slide_id,
            completed=True,
            already_completed=not inserted,
            module_progress=ModuleProgress(
                slides_total=counts["module_total"],
                slides_completed=counts["module_completed"],
                current_slide_index=next_index or counts["module_total"],
            ),
            next_slide_index=next_index,
        )
