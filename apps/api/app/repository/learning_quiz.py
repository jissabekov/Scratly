"""Async repository for module quizzes (Plan 04 W4.4).

One write path: :meth:`QuizRepository.submit`, which is a single transaction and
idempotent by ``request_id``. Quiz answers land in ``learning.*`` only — never in
``assessment.*`` (hard rules 2/4). The draw is persisted as an open attempt so
form rotation and the attempt cap are auditable and replayable.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.contracts.learning_quiz import (
    MAX_ATTEMPTS,
    PASS_RULE_TEXT,
    PASS_THRESHOLD,
    PROVISIONAL_MASTERY,
    ObjectiveMastery,
    QuizAttemptRequest,
    QuizAttemptResponse,
    QuizAttemptView,
    QuizDrawResponse,
    QuizGateState,
    QuizItemCheckRequest,
    QuizItemCheckResponse,
    QuizItemView,
    QuizMissedItem,
    QuizRemediation,
)
from app.services.learning_progress import (
    XAPI_OBJECT_MODULE,
    XAPI_OBJECT_QUIZ_ITEM,
    XAPI_VERB_ANSWERED,
    XAPI_VERB_ATTEMPTED,
    XAPI_VERB_FAILED,
    XAPI_VERB_PASSED,
    xapi_statement,
)
from app.services.learning_quiz_engine import (
    BKT_PRIOR,
    QuizItemFact,
    bkt_update,
    decide_next_action,
    is_correct,
    next_form_id,
    objective_state,
    remediation_slide_refs,
    score_attempt,
)
from app.services.learning_trace import learning_trace


class QuizConflictError(Exception):
    """An attempt was already submitted under a different request_id."""


class QuizRepository:
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

    # --- reads ---------------------------------------------------------------

    async def _session_student(self, session_id: UUID) -> dict[str, Any] | None:
        result = await self.session.execute(
            text("SELECT id, student_id FROM core.sessions WHERE id = :session_id"),
            {"session_id": session_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def _module(self, module_id: UUID) -> dict[str, Any] | None:
        result = await self.session.execute(
            text(
                """
                SELECT id, slug, seq, title, archetype_key
                  FROM learning.modules WHERE id = :module_id
                """
            ),
            {"module_id": module_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def _objectives(self, module_id: UUID) -> list[dict[str, Any]]:
        result = await self.session.execute(
            text(
                """
                SELECT id, code, label, is_critical, ordinal
                  FROM learning.objectives WHERE module_id = :module_id
                 ORDER BY ordinal
                """
            ),
            {"module_id": module_id},
        )
        return [dict(row) for row in result.mappings()]

    async def _forms(self, module_id: UUID) -> list[int]:
        result = await self.session.execute(
            text(
                """
                SELECT DISTINCT form_id FROM learning.quiz_items
                 WHERE module_id = :module_id ORDER BY form_id
                """
            ),
            {"module_id": module_id},
        )
        return [row[0] for row in result.all()]

    async def _form_items(self, module_id: UUID, form_id: int) -> list[dict[str, Any]]:
        result = await self.session.execute(
            text(
                """
                SELECT i.id, i.seq, i.kind, i.stem, i.options, i.answer, i.hint_text,
                       i.feedback_correct, i.feedback_wrong, i.slide_ref, i.is_critical,
                       o.code AS objective_code
                  FROM learning.quiz_items i
                  JOIN learning.objectives o ON o.id = i.objective_id
                 WHERE i.module_id = :module_id AND i.form_id = :form_id
                 ORDER BY i.seq
                """
            ),
            {"module_id": module_id, "form_id": form_id},
        )
        return [dict(row) for row in result.mappings()]

    async def _items(self, item_ids: list[UUID]) -> list[dict[str, Any]]:
        result = await self.session.execute(
            text(
                """
                SELECT i.id, i.seq, i.kind, i.stem, i.options, i.answer, i.hint_text,
                       i.feedback_correct, i.feedback_wrong, i.slide_ref, i.is_critical,
                       o.code AS objective_code
                  FROM learning.quiz_items i
                  JOIN learning.objectives o ON o.id = i.objective_id
                 WHERE i.id = ANY(:item_ids)
                 ORDER BY i.form_id, i.seq
                """
            ),
            {"item_ids": item_ids},
        )
        return [dict(row) for row in result.mappings()]

    async def _attempts(self, session_id: UUID, module_id: UUID) -> list[dict[str, Any]]:
        result = await self.session.execute(
            text(
                """
                SELECT id, attempt_no, form_id, item_ids, score, passed, provisional,
                       critical_missed, request_id, started_at, submitted_at
                  FROM learning.quiz_attempts
                 WHERE session_id = :session_id AND module_id = :module_id
                 ORDER BY attempt_no
                """
            ),
            {"session_id": session_id, "module_id": module_id},
        )
        return [dict(row) for row in result.mappings()]

    async def _attempt(self, session_id: UUID, attempt_id: UUID) -> dict[str, Any] | None:
        result = await self.session.execute(
            text(
                """
                SELECT id, module_id, attempt_no, form_id, item_ids, score, passed,
                       provisional, critical_missed, request_id, started_at, submitted_at
                  FROM learning.quiz_attempts
                 WHERE session_id = :session_id AND id = :attempt_id
                """
            ),
            {"session_id": session_id, "attempt_id": attempt_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def _slide_index(self, module_id: UUID) -> dict[UUID, int]:
        result = await self.session.execute(
            text(
                """
                SELECT s.id FROM learning.slides s
                  JOIN learning.lessons l ON l.id = s.lesson_id
                 WHERE l.module_id = :module_id
                 ORDER BY l.seq, s.seq
                """
            ),
            {"module_id": module_id},
        )
        return {row[0]: index for index, row in enumerate(result.all(), start=1)}

    async def _mastery(self, session_id: UUID, module_id: UUID) -> dict[str, dict[str, Any]]:
        result = await self.session.execute(
            text(
                """
                SELECT o.code, m.p_mastery, m.state, m.correct_count, m.wrong_count
                  FROM learning.mastery_states m
                  JOIN learning.objectives o ON o.id = m.objective_id
                 WHERE m.session_id = :session_id AND o.module_id = :module_id
                """
            ),
            {"session_id": session_id, "module_id": module_id},
        )
        return {row["code"]: dict(row) for row in result.mappings()}

    async def quiz_passed_by_module(self, session_id: UUID) -> dict[UUID, bool]:
        """Modules whose gate is cleared (strict or provisional pass)."""
        result = await self.session.execute(
            text(
                """
                SELECT module_id
                  FROM learning.quiz_attempts
                 WHERE session_id = :session_id AND (passed OR provisional)
                 GROUP BY module_id
                """
            ),
            {"session_id": session_id},
        )
        return {row[0]: True for row in result.all()}

    # --- draw (GET) ----------------------------------------------------------

    async def draw(self, session_id: UUID, module_id: UUID) -> QuizDrawResponse | None:
        session = await self._session_student(session_id)
        if session is None:
            return None
        module = await self._module(module_id)
        if module is None:
            return None

        attempts = await self._attempts(session_id, module_id)
        submitted = [a for a in attempts if a["submitted_at"] is not None]
        attempts_used = len(submitted)

        def response(
            gate: QuizGateState,
            attempt: QuizAttemptView | None = None,
            retry_after: int | None = None,
        ) -> QuizDrawResponse:
            return QuizDrawResponse(
                session_id=session_id,
                module_id=module_id,
                gate=gate,
                attempts_used=attempts_used,
                retry_after_seconds=retry_after,
                attempt=attempt,
            )

        if any(a["passed"] or a["provisional"] for a in submitted):
            return response(QuizGateState.PASSED)

        forms = await self._forms(module_id)
        if not forms:
            return response(QuizGateState.UNAVAILABLE)

        open_attempt = next((a for a in attempts if a["submitted_at"] is None), None)
        if open_attempt is not None:
            rows = await self._items(list(open_attempt["item_ids"]))
            return response(QuizGateState.AVAILABLE, self._attempt_view(open_attempt, rows))

        if attempts_used >= MAX_ATTEMPTS:
            # Provisional pass is normally granted at submit time; re-evaluate on
            # read so mastery gained elsewhere (Plan 05) still unlocks the path.
            min_critical = await self._min_critical_mastery(session_id, module_id)
            if min_critical >= PROVISIONAL_MASTERY:
                return response(QuizGateState.PASSED)
            return response(QuizGateState.HANDOFF)

        cooldown = get_settings().learning_quiz_cooldown_seconds
        last = submitted[-1] if submitted else None
        if last is not None and cooldown > 0:
            elapsed = (datetime.now(timezone.utc) - last["submitted_at"]).total_seconds()
            if elapsed < cooldown:
                return response(
                    QuizGateState.COOLDOWN,
                    retry_after=int(cooldown - elapsed),
                )

        attempt_no = attempts_used + 1
        form_id = next_form_id(forms, attempt_no)
        rows = await self._form_items(module_id, form_id)
        item_ids = [row["id"] for row in rows]
        async with self.transaction():
            inserted = (
                await self.session.execute(
                    text(
                        """
                        INSERT INTO learning.quiz_attempts
                            (student_id, session_id, module_id, attempt_no, form_id, item_ids)
                        VALUES (:student_id, :session_id, :module_id, :attempt_no, :form_id,
                                CAST(:item_ids AS jsonb))
                        ON CONFLICT DO NOTHING
                        RETURNING id
                        """
                    ),
                    {
                        "student_id": session["student_id"],
                        "session_id": session_id,
                        "module_id": module_id,
                        "attempt_no": attempt_no,
                        "form_id": form_id,
                        "item_ids": json.dumps([str(item) for item in item_ids]),
                    },
                )
            ).first()
            if inserted is None:
                # Another request created the open attempt first; reuse it.
                existing = (
                    (
                        await self.session.execute(
                            text(
                                """
                            SELECT id, attempt_no, form_id, item_ids FROM learning.quiz_attempts
                             WHERE session_id = :session_id AND module_id = :module_id
                               AND submitted_at IS NULL
                            """
                            ),
                            {"session_id": session_id, "module_id": module_id},
                        )
                    )
                    .mappings()
                    .first()
                )
                if existing is None:
                    raise QuizConflictError("could not open a quiz attempt")
                rows = await self._items(list(existing["item_ids"]))
                return response(
                    QuizGateState.AVAILABLE,
                    self._attempt_view(dict(existing), rows),
                )
            attempt = {
                "id": inserted[0],
                "attempt_no": attempt_no,
                "form_id": form_id,
                "item_ids": item_ids,
            }
            await learning_trace(self.session, session_id).record(
                "learning_quiz_drawn",
                "quiz_repository",
                "v1",
                "Opened a fresh quiz attempt for the module gate.",
                "attempt_opened",
                outputs={"attempt_no": attempt_no, "form_id": form_id, "item_count": len(rows)},
                entity_refs={
                    "module_id": str(module_id),
                    "attempt_id": str(attempt["id"]),
                },
            )
        return response(QuizGateState.AVAILABLE, self._attempt_view(attempt, rows))

    async def _min_critical_mastery(self, session_id: UUID, module_id: UUID) -> float:
        objectives = await self._objectives(module_id)
        mastery = await self._mastery(session_id, module_id)
        values = [
            float(mastery.get(objective["code"], {}).get("p_mastery", BKT_PRIOR))
            for objective in objectives
            if objective["is_critical"]
        ]
        return min(values) if values else BKT_PRIOR

    def _attempt_view(self, attempt: dict[str, Any], rows: list[dict[str, Any]]) -> QuizAttemptView:
        return QuizAttemptView(
            attempt_id=attempt["id"],
            attempt_no=attempt["attempt_no"],
            form_id=attempt["form_id"],
            item_count=len(rows),
            threshold=PASS_THRESHOLD,
            pass_rule=PASS_RULE_TEXT,
            items=[
                QuizItemView(
                    id=row["id"],
                    seq=row["seq"],
                    objective_code=row["objective_code"],
                    kind=row["kind"],
                    stem=row["stem"],
                    options=row["options"],
                    hint_text=row["hint_text"],
                    is_critical=row["is_critical"],
                )
                for row in rows
            ],
        )

    async def check_item(
        self, session_id: UUID, attempt_id: UUID, body: QuizItemCheckRequest
    ) -> QuizItemCheckResponse | None:
        """Record one answer and return immediate feedback (answers stay server-side)."""
        attempt = await self._attempt(session_id, attempt_id)
        if attempt is None:
            return None
        if attempt["submitted_at"] is not None:
            raise QuizConflictError("attempt already submitted")
        rows = await self._items(list(attempt["item_ids"]))
        row = next((candidate for candidate in rows if candidate["id"] == body.item_id), None)
        if row is None:
            return None
        correct = is_correct(body.response, row["answer"])
        async with self.transaction():
            await self.session.execute(
                text(
                    """
                    INSERT INTO learning.quiz_responses
                        (attempt_id, item_id, response, correct, latency_ms)
                    VALUES (:attempt_id, :item_id, CAST(:response AS jsonb), :correct, :latency)
                    ON CONFLICT (attempt_id, item_id) DO UPDATE SET
                        response = EXCLUDED.response,
                        correct = EXCLUDED.correct,
                        latency_ms = EXCLUDED.latency_ms
                    """
                ),
                {
                    "attempt_id": attempt["id"],
                    "item_id": body.item_id,
                    "response": json.dumps(list(body.response)),
                    "correct": correct,
                    "latency": body.latency_ms,
                },
            )
        return QuizItemCheckResponse(
            item_id=body.item_id,
            correct=correct,
            feedback=(row["feedback_correct"] if correct else row["feedback_wrong"]) or "",
            correct_answer=list(row["answer"]),
        )

    # --- submit (POST) -------------------------------------------------------

    async def submit(
        self, session_id: UUID, body: QuizAttemptRequest
    ) -> QuizAttemptResponse | None:
        session = await self._session_student(session_id)
        if session is None:
            return None
        attempt = await self._attempt(session_id, body.attempt_id)
        if attempt is None:
            return None
        module_id = attempt["module_id"]
        module = await self._module(module_id)
        if module is None:
            return None

        objectives = await self._objectives(module_id)
        slide_index = await self._slide_index(module_id)
        rows = await self._items(list(attempt["item_ids"]))

        if attempt["submitted_at"] is not None:
            if attempt["request_id"] != body.request_id:
                raise QuizConflictError("attempt already submitted under another request_id")
            return await self._compose(session_id, module_id, module, attempt, rows, slide_index)

        facts = [
            QuizItemFact(
                id=row["id"],
                objective_code=row["objective_code"],
                is_critical=row["is_critical"],
                answer=tuple(row["answer"]),
                kind=row["kind"],
            )
            for row in rows
        ]
        responses = {item.item_id: list(item.response) for item in body.responses}
        result = score_attempt(facts, responses)

        mastery_before = await self._mastery(session_id, module_id)
        p_by_code = {
            objective["code"]: float(
                mastery_before.get(objective["code"], {}).get("p_mastery", BKT_PRIOR)
            )
            for objective in objectives
        }
        correct_by_objective: dict[str, int] = {}
        wrong_by_objective: dict[str, int] = {}
        for row in rows:
            code = row["objective_code"]
            success = row["id"] not in result.wrong_item_ids
            p_by_code[code] = bkt_update(p_by_code[code], success, row["kind"])
            if success:
                correct_by_objective[code] = correct_by_objective.get(code, 0) + 1
            else:
                wrong_by_objective[code] = wrong_by_objective.get(code, 0) + 1
        if result.passed:
            # A clean pass settles its critical objectives at mastery.
            for objective in objectives:
                if objective["is_critical"]:
                    p_by_code[objective["code"]] = 1.0

        critical_values = [p_by_code[o["code"]] for o in objectives if o["is_critical"]]
        min_critical = min(critical_values) if critical_values else BKT_PRIOR
        next_action = decide_next_action(
            attempt["attempt_no"], result.passed, min_critical, MAX_ATTEMPTS
        )
        provisional = next_action == "unlock_next" and not result.passed

        async with self.transaction():
            for item in body.responses:
                correct = item.item_id not in result.wrong_item_ids
                await self.session.execute(
                    text(
                        """
                        INSERT INTO learning.quiz_responses
                            (attempt_id, item_id, response, correct, latency_ms)
                        VALUES (:attempt_id, :item_id, CAST(:response AS jsonb), :correct, :latency)
                        ON CONFLICT (attempt_id, item_id) DO UPDATE SET
                            response = EXCLUDED.response,
                            correct = EXCLUDED.correct,
                            latency_ms = EXCLUDED.latency_ms
                        """
                    ),
                    {
                        "attempt_id": attempt["id"],
                        "item_id": item.item_id,
                        "response": json.dumps(list(item.response)),
                        "correct": correct,
                        "latency": item.latency_ms,
                    },
                )
            await self.session.execute(
                text(
                    """
                    UPDATE learning.quiz_attempts
                       SET score = :score, passed = :passed, provisional = :provisional,
                           critical_missed = :critical_missed, request_id = :request_id,
                           submitted_at = now()
                     WHERE id = :attempt_id
                    """
                ),
                {
                    "score": result.score,
                    "passed": result.passed,
                    "provisional": provisional,
                    "critical_missed": list(result.critical_missed),
                    "request_id": body.request_id,
                    "attempt_id": attempt["id"],
                },
            )
            for row in rows:
                await self.session.execute(
                    text(
                        """
                        INSERT INTO learning.item_stats (item_id, attempts, correct, p_hat)
                        VALUES (:item_id, 1, :correct, :p_hat)
                        ON CONFLICT (item_id) DO UPDATE SET
                            attempts = learning.item_stats.attempts + 1,
                            correct = learning.item_stats.correct + EXCLUDED.correct,
                            p_hat = ROUND(
                                (learning.item_stats.correct + EXCLUDED.correct)::numeric
                                / (learning.item_stats.attempts + 1), 3),
                            updated_at = now()
                        """
                    ),
                    {
                        "item_id": row["id"],
                        "correct": 0 if row["id"] in result.wrong_item_ids else 1,
                        "p_hat": Decimal("0.0" if row["id"] in result.wrong_item_ids else "1.0"),
                    },
                )
            for objective in objectives:
                code = objective["code"]
                await self.session.execute(
                    text(
                        """
                        INSERT INTO learning.mastery_states
                            (session_id, objective_id, p_mastery, state,
                             correct_count, wrong_count, updated_at)
                        VALUES (:session_id, :objective_id, :p, :state, :correct, :wrong, now())
                        ON CONFLICT (session_id, objective_id) DO UPDATE SET
                            p_mastery = EXCLUDED.p_mastery,
                            state = EXCLUDED.state,
                            correct_count = learning.mastery_states.correct_count + EXCLUDED.correct_count,
                            wrong_count = learning.mastery_states.wrong_count + EXCLUDED.wrong_count,
                            updated_at = now()
                        """
                    ),
                    {
                        "session_id": session_id,
                        "objective_id": objective["id"],
                        "p": Decimal(str(round(p_by_code[code], 4))),
                        "state": objective_state(
                            p_by_code[code], result.passed and objective["is_critical"]
                        ),
                        "correct": correct_by_objective.get(code, 0),
                        "wrong": wrong_by_objective.get(code, 0),
                    },
                )
            await self._record_result_events(
                session_id=session_id,
                student_id=session["student_id"],
                module=module,
                attempt=attempt,
                result=result,
                responses=responses,
                rows=rows,
                next_action=next_action,
                request_id=body.request_id,
            )
            trace = learning_trace(self.session, session_id)
            await trace.record(
                "learning_quiz_scored",
                "quiz_repository",
                "v1",
                "Scored a submitted quiz attempt against the pass rule.",
                "attempt_scored",
                outputs={
                    "attempt_no": attempt["attempt_no"],
                    "form_id": attempt["form_id"],
                    "score": result.score,
                    "item_count": result.item_count,
                    "passed": result.passed,
                    "provisional": provisional,
                    "next_action": next_action,
                    "critical_missed": list(result.critical_missed),
                },
                entity_refs={
                    "module_id": str(module_id),
                    "attempt_id": str(attempt["id"]),
                },
            )
            if next_action == "unlock_next":
                await trace.record(
                    "learning_module_unlocked",
                    "quiz_repository",
                    "v1",
                    "Module gate satisfied; the next module is unlocked.",
                    "quiz_passed" if result.passed else "provisional_pass",
                    outputs={"score": result.score, "passed": result.passed},
                    entity_refs={
                        "module_id": str(module_id),
                        "attempt_id": str(attempt["id"]),
                    },
                )

        refreshed = await self._attempt(session_id, body.attempt_id)
        assert refreshed is not None
        return await self._compose(session_id, module_id, module, refreshed, rows, slide_index)

    async def _record_result_events(
        self,
        *,
        session_id: UUID,
        student_id: UUID,
        module: dict[str, Any],
        attempt: dict[str, Any],
        result: Any,
        responses: dict[UUID, list[str]],
        rows: list[dict[str, Any]],
        next_action: str,
        request_id: str,
    ) -> None:
        base_context = {
            "attempt_id": str(attempt["id"]),
            "attempt_no": attempt["attempt_no"],
            "form_id": attempt["form_id"],
        }
        statements: list[tuple[str, str, str, str, str, dict | None, dict]] = [
            (
                f"{request_id}:attempted",
                XAPI_VERB_ATTEMPTED,
                f"module:{module['id']}",
                XAPI_OBJECT_MODULE,
                module["title"],
                None,
                base_context,
            )
        ]
        for row in rows:
            statements.append(
                (
                    f"{request_id}:item:{row['id']}",
                    XAPI_VERB_ANSWERED,
                    f"quiz-item:{row['id']}",
                    XAPI_OBJECT_QUIZ_ITEM,
                    row["stem"][:120],
                    {"success": row["id"] not in result.wrong_item_ids},
                    {
                        **base_context,
                        "objective_code": row["objective_code"],
                        "kind": row["kind"],
                        "response": responses.get(row["id"], []),
                    },
                )
            )
        statements.append(
            (
                f"{request_id}:result",
                XAPI_VERB_PASSED if result.passed else XAPI_VERB_FAILED,
                f"module:{module['id']}",
                XAPI_OBJECT_MODULE,
                module["title"],
                {
                    "success": result.passed,
                    "score": result.score,
                    "item_count": result.item_count,
                    "provisional": next_action == "unlock_next" and not result.passed,
                },
                {**base_context, "critical_missed": list(result.critical_missed)},
            )
        )
        for suffix, verb, object_id, object_type, name, res, context in statements:
            statement = xapi_statement(
                actor_name=str(student_id),
                verb_id=verb,
                object_id=object_id,
                object_type=object_type,
                object_name=name,
                result=res,
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
                    "request_id": suffix,
                },
            )

    async def _compose(
        self,
        session_id: UUID,
        module_id: UUID,
        module: dict[str, Any],
        attempt: dict[str, Any],
        rows: list[dict[str, Any]],
        slide_index: dict[UUID, int],
    ) -> QuizAttemptResponse:
        response_rows = (
            await self.session.execute(
                text(
                    """
                    SELECT item_id, response, correct FROM learning.quiz_responses
                     WHERE attempt_id = :attempt_id
                    """
                ),
                {"attempt_id": attempt["id"]},
            )
        ).mappings()
        by_item = {row["item_id"]: dict(row) for row in response_rows}
        mastery = await self._mastery(session_id, module_id)
        forms = await self._forms(module_id)
        provisional = bool(attempt["provisional"])
        passed = bool(attempt["passed"]) or provisional

        missed: list[QuizMissedItem] = []
        for row in rows:
            stored = by_item.get(row["id"])
            if stored is not None and stored["correct"]:
                continue
            missed.append(
                QuizMissedItem(
                    item_id=row["id"],
                    objective_code=row["objective_code"],
                    stem=row["stem"],
                    feedback_wrong=row.get("feedback_wrong") or "",
                    slide_ref=slide_index.get(row["slide_ref"]) if row["slide_ref"] else None,
                    selected=list(stored["response"]) if stored else [],
                    correct=list(row["answer"]),
                )
            )

        next_action = (
            "unlock_next"
            if passed
            else decide_next_action(
                attempt["attempt_no"],
                False,
                await self._min_critical_mastery(session_id, module_id),
                MAX_ATTEMPTS,
            )
        )
        remediation = None
        if not passed:
            remediation = QuizRemediation(
                objectives=sorted({item.objective_code for item in missed}),
                slide_refs=remediation_slide_refs(item.slide_ref for item in missed),
                cooldown_seconds=get_settings().learning_quiz_cooldown_seconds,
            )
        unlocked = module_id if next_action == "unlock_next" else None
        return QuizAttemptResponse(
            attempt_id=attempt["id"],
            attempt_no=attempt["attempt_no"],
            form_id=attempt["form_id"],
            score=int(attempt["score"]),
            item_count=len(rows),
            threshold=PASS_THRESHOLD,
            passed=passed,
            critical_missed=list(attempt["critical_missed"]),
            missed=missed,
            next_action=next_action,
            next_form_id=(
                next_form_id(forms, attempt["attempt_no"] + 1)
                if next_action in ("retry", "walkthrough") and forms
                else None
            ),
            remediation=remediation,
            mastery=[
                ObjectiveMastery(
                    objective_code=code,
                    p_mastery=float(row.get("p_mastery", BKT_PRIOR)),
                    state=row.get("state", "unseen"),
                )
                for code, row in sorted(mastery.items())
            ],
            unlocked_module_id=unlocked,
        )
