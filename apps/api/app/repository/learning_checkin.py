"""Check-in delivery, responses, dismissal, and the coach summary (Plan 05 W5.3).

All scheduling and scoring is delegated to ``learning_checkin_engine`` (pure,
injected ``now``). This module only reads the deterministic context, writes one
transaction per mutation, and keeps the two hard boundaries:

* answers append xAPI-shaped ``learning.learning_events`` and update the
  ``learning.mastery_states`` projection — never ``assessment.evidence``;
* writes are idempotent by ``request_id``.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.learning_checkin import (
    APPLIED_EVIDENCE_WEIGHT,
    MAX_CHECKINS_PER_SESSION,
    CheckinDeliverResponse,
    CheckinDismissRequest,
    CheckinDismissResponse,
    CheckinFeedback,
    CheckinGate,
    CheckinItemView,
    CheckinKind,
    CheckinObjectiveState,
    CheckinOption,
    CheckinRespondRequest,
    CheckinRespondResponse,
    CheckinTrigger,
    CoachSummaryResponse,
    InterventionLevel,
    InterventionView,
    LikertScale,
    RetentionCardView,
)
from app.services.learning_checkin_engine import (
    CheckinContext,
    InterventionContext,
    RetentionState,
    checkin_gate,
    choose_item,
    choose_kind,
    dismiss_cooldown_seconds,
    due_cards,
    intervention_for,
    score_likert,
    score_mcq,
    score_rubric,
    select_trigger,
    streak_steps,
    update_card_state,
    with_decay,
)
from app.services.learning_progress import XAPI_VERB_COMPLETED, xapi_statement
from app.services.learning_quiz_engine import bkt_update, objective_state

CHECKIN_VERB = "checked_in"
CHECKIN_OBJECT_TYPE = "http://adlnet.gov/expapi/activities/assessment"
SECTION_WINDOW_MINUTES = 5
ERROR_WINDOW_MINUTES = 10
BKT_PRIOR = 0.2


class CheckinConflictError(Exception):
    """A check-in write collided with a different request_id."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


class CheckinRepository:
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

    async def _open_event(self, session_id: UUID) -> dict[str, Any] | None:
        result = await self.session.execute(
            text(
                """
                SELECT e.id, e.checkin_item_id, e.objective_id, e.trigger_reason,
                       e.delivered_at, e.scheduled_at
                  FROM learning.checkin_events e
                 WHERE e.session_id = :session_id
                   AND e.delivered_at IS NOT NULL
                   AND e.responded_at IS NULL
                   AND e.dismissed = false
                 ORDER BY e.delivered_at DESC LIMIT 1
                """
            ),
            {"session_id": session_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def _item(self, item_id: UUID) -> dict[str, Any] | None:
        result = await self.session.execute(
            text(
                """
                SELECT i.id, i.seq, i.kind, i.prompt, i.payload,
                       o.code AS objective_code, o.label AS objective_label
                  FROM learning.checkin_items i
                  JOIN learning.objectives o ON o.id = i.objective_id
                 WHERE i.id = :item_id
                """
            ),
            {"item_id": item_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def _items_for_objective(self, objective_id: UUID) -> list[dict[str, Any]]:
        result = await self.session.execute(
            text(
                """
                SELECT i.id, i.seq, i.kind, i.prompt, i.payload,
                       o.code AS objective_code, o.label AS objective_label
                  FROM learning.checkin_items i
                  JOIN learning.objectives o ON o.id = i.objective_id
                 WHERE i.objective_id = :objective_id
                 ORDER BY i.seq
                """
            ),
            {"objective_id": objective_id},
        )
        return [dict(row) for row in result.mappings()]

    async def _context(self, session_id: UUID) -> CheckinContext:
        now = _now()
        counts = await self.session.execute(
            text(
                """
                SELECT count(*) FILTER (WHERE delivered_at IS NOT NULL) AS used,
                       max(delivered_at) AS last_delivered,
                       max(responded_at) FILTER (WHERE dismissed) AS last_dismissed
                  FROM learning.checkin_events WHERE session_id = :session_id
                """
            ),
            {"session_id": session_id},
        )
        row = counts.mappings().one()
        last_dismissed = await self.session.execute(
            text(
                """
                SELECT max(created_at) AS dismissed_at
                  FROM learning.checkin_events
                 WHERE session_id = :session_id AND dismissed
                """
            ),
            {"session_id": session_id},
        )
        quiz_active = await self.session.execute(
            text(
                """
                SELECT EXISTS(
                    SELECT 1 FROM learning.quiz_attempts
                     WHERE session_id = :session_id AND submitted_at IS NULL
                ) AS active
                """
            ),
            {"session_id": session_id},
        )
        recent = await self.session.execute(
            text(
                """
                SELECT count(*) FILTER (WHERE result->>'success' = 'false') AS wrong
                  FROM learning.learning_events
                 WHERE session_id = :session_id
                   AND occurred_at >= now() - (:window || ' minutes')::interval
                   AND result ? 'success'
                """
            ),
            {"session_id": session_id, "window": str(ERROR_WINDOW_MINUTES)},
        )
        activity = await self.session.execute(
            text(
                """
                SELECT max(occurred_at) AS last_activity,
                       count(*) FILTER (
                           WHERE occurred_at >= now() - (:window || ' minutes')::interval
                             AND verb->>'id' = :completed
                             AND object->>'id' LIKE 'module:%'
                       ) AS milestone_recent,
                       count(*) FILTER (
                           WHERE occurred_at >= now() - (:window || ' minutes')::interval
                             AND verb->>'id' = :completed
                             AND object->>'id' LIKE 'slide:%'
                       ) AS section_recent
                  FROM learning.learning_events WHERE session_id = :session_id
                """
            ),
            {
                "session_id": session_id,
                "window": str(SECTION_WINDOW_MINUTES),
                "completed": XAPI_VERB_COMPLETED,
            },
        )
        act = activity.mappings().one()
        due = await self.session.execute(
            text(
                """
                SELECT count(*) AS due FROM learning.retention_cards
                 WHERE session_id = :session_id AND due_at <= now()
                """
            ),
            {"session_id": session_id},
        )
        return CheckinContext(
            now=now,
            checkins_used=int(row["used"] or 0),
            last_delivered_at=row["last_delivered"],
            last_dismissed_at=last_dismissed.scalar_one_or_none(),
            quiz_active=bool(quiz_active.scalar_one()),
            retention_due=int(due.scalar_one() or 0) > 0,
            recent_wrong=int(recent.scalar_one() or 0),
            last_activity_at=act["last_activity"],
            milestone_passed=int(act["milestone_recent"] or 0) > 0,
            section_completed=int(act["section_recent"] or 0) > 0,
        )

    # --- deliver -------------------------------------------------------------

    async def deliver(self, session_id: UUID) -> CheckinDeliverResponse | None:
        session_row = await self._session_student(session_id)
        if session_row is None:
            return None
        context = await self._context(session_id)
        open_event = await self._open_event(session_id)
        if open_event is not None:
            item = await self._item(open_event["checkin_item_id"])
            if item is not None:
                return CheckinDeliverResponse(
                    session_id=session_id,
                    gate=CheckinGate.AVAILABLE,
                    item=_item_view(item, open_event["trigger_reason"]),
                    checkins_used=context.checkins_used,
                )
        gate, retry = checkin_gate(context)
        if gate != CheckinGate.AVAILABLE:
            return CheckinDeliverResponse(
                session_id=session_id,
                gate=gate,
                retry_after_seconds=retry,
                checkins_used=context.checkins_used,
            )
        trigger = select_trigger(context)
        if trigger is None:
            return CheckinDeliverResponse(
                session_id=session_id,
                gate=CheckinGate.NONE,
                checkins_used=context.checkins_used,
            )
        objective_id = await self._trigger_objective(session_id, trigger)
        if objective_id is None:
            return CheckinDeliverResponse(
                session_id=session_id,
                gate=CheckinGate.NONE,
                checkins_used=context.checkins_used,
            )
        kind = choose_kind(trigger, context.checkins_used)
        item = choose_item(
            await self._items_for_objective(objective_id), kind, context.checkins_used
        )
        if item is None:
            return CheckinDeliverResponse(
                session_id=session_id,
                gate=CheckinGate.NONE,
                checkins_used=context.checkins_used,
            )
        async with self.transaction():
            await self.session.execute(
                text(
                    """
                    INSERT INTO learning.checkin_events
                        (id, student_id, session_id, checkin_item_id, objective_id,
                         trigger_reason, scheduled_at, delivered_at)
                    VALUES (:id, :student_id, :session_id, :item_id, :objective_id,
                            :trigger, :now, :now)
                    """
                ),
                {
                    "id": uuid4(),
                    "student_id": session_row["student_id"],
                    "session_id": session_id,
                    "item_id": item["id"],
                    "objective_id": objective_id,
                    "trigger": trigger.value,
                    "now": context.now,
                },
            )
        return CheckinDeliverResponse(
            session_id=session_id,
            gate=CheckinGate.AVAILABLE,
            item=_item_view(item, trigger.value),
            checkins_used=context.checkins_used + 1,
        )

    async def _trigger_objective(self, session_id: UUID, trigger: CheckinTrigger) -> UUID | None:
        if trigger == CheckinTrigger.RETENTION_DUE:
            cards = await self._retention_cards(session_id)
            due = due_cards(cards, _now())
            if due:
                return due[0]["objective_id"]
        result = await self.session.execute(
            text(
                """
                SELECT s.objective_id
                  FROM learning.slide_completions c
                  JOIN learning.slides s ON s.id = c.slide_id
                 WHERE c.session_id = :session_id AND s.objective_id IS NOT NULL
                 ORDER BY c.completed_at DESC LIMIT 1
                """
            ),
            {"session_id": session_id},
        )
        row = result.mappings().first()
        if row is not None:
            return row["objective_id"]
        fallback = await self.session.execute(
            text(
                """
                SELECT o.id FROM learning.objectives o
                 ORDER BY o.ordinal, o.code LIMIT 1
                """
            )
        )
        return fallback.scalar_one_or_none()

    async def _retention_cards(self, session_id: UUID) -> list[dict[str, Any]]:
        result = await self.session.execute(
            text(
                """
                SELECT objective_id, due_at, interval_days, reps, lapses
                  FROM learning.retention_cards WHERE session_id = :session_id
                """
            ),
            {"session_id": session_id},
        )
        return [dict(row) for row in result.mappings()]

    # --- respond -------------------------------------------------------------

    async def respond(
        self, session_id: UUID, event_id: UUID, body: CheckinRespondRequest
    ) -> CheckinRespondResponse | None:
        existing = await self.session.execute(
            text("SELECT id FROM learning.checkin_events WHERE request_id = :rid"),
            {"rid": body.request_id},
        )
        if existing.scalar_one_or_none() is not None:
            raise CheckinConflictError("request_id already used for a different check-in")
        row = await self.session.execute(
            text(
                """
                SELECT e.id, e.student_id, e.objective_id, e.checkin_item_id, e.trigger_reason,
                       i.kind, i.payload, o.code AS objective_code, o.is_critical
                  FROM learning.checkin_events e
                  JOIN learning.checkin_items i ON i.id = e.checkin_item_id
                  JOIN learning.objectives o ON o.id = e.objective_id
                 WHERE e.id = :event_id AND e.session_id = :session_id
                """
            ),
            {"event_id": event_id, "session_id": session_id},
        )
        event = row.mappings().first()
        if event is None:
            return None
        payload = event["payload"] or {}
        kind = CheckinKind(event["kind"])
        score, correct, feedback, correct_answer = _score(
            kind, payload, body.response, body.free_text
        )
        now = _now()
        scored = kind in {CheckinKind.MINI_EXERCISE, CheckinKind.MCQ}
        async with self.transaction():
            await self.session.execute(
                text(
                    """
                    UPDATE learning.checkin_events
                       SET responded_at = :now, response = :response::jsonb,
                           score = :score, latency_ms = :latency, request_id = :rid
                     WHERE id = :event_id
                    """
                ),
                {
                    "now": now,
                    "response": _json({"selected": body.response, "free_text": body.free_text}),
                    "score": score,
                    "latency": body.latency_ms,
                    "rid": body.request_id,
                    "event_id": event_id,
                },
            )
            if scored:
                await self._record_event(
                    student_id=event["student_id"],
                    session_id=session_id,
                    objective_id=event["objective_id"],
                    objective_code=event["objective_code"],
                    kind=kind,
                    score=score,
                    request_id=body.request_id,
                )
                await self._apply_mastery(
                    session_id,
                    event["objective_id"],
                    event["objective_code"],
                    kind,
                    score,
                    now,
                )
                await self._maybe_open_intervention(
                    session_id, event["objective_id"], event["objective_code"], score, now
                )
        mastery = await self._mastery(session_id)
        due_at = await self._refresh_retention(
            event["student_id"], session_id, event["objective_id"], score, now
        )
        return CheckinRespondResponse(
            event_id=event_id,
            item_id=event["checkin_item_id"],
            objective_code=event["objective_code"],
            kind=kind,
            scored=scored,
            result=CheckinFeedback(
                score=score,
                correct=correct,
                feedback=feedback,
                correct_answer=correct_answer,
            ),
            mastery=mastery,
            retention_due_at=due_at,
            next_action="refresher" if scored and score < 0.5 else "continue",
        )

    async def _record_event(
        self,
        *,
        student_id: UUID,
        session_id: UUID,
        objective_id: UUID,
        objective_code: str,
        kind: CheckinKind,
        score: float,
        request_id: str,
    ) -> None:
        statement = xapi_statement(
            actor_name=str(student_id),
            verb_id=f"http://adlnet.gov/expapi/verbs/{CHECKIN_VERB}",
            object_id=f"urn:scratly:objective:{objective_code}",
            object_type=CHECKIN_OBJECT_TYPE,
            object_name=objective_code,
            result={"success": score >= 0.5, "score": {"scaled": round(score, 3)}},
            context={
                "weight": APPLIED_EVIDENCE_WEIGHT if kind == CheckinKind.MINI_EXERCISE else 0.0,
                "kind": kind.value,
            },
        )
        await self.session.execute(
            text(
                """
                INSERT INTO learning.learning_events
                    (id, student_id, session_id, actor, verb, object, result, context, request_id)
                VALUES (gen_random_uuid(), :student_id, :session_id, :actor::jsonb, :verb::jsonb,
                        :object::jsonb, :result::jsonb, :context::jsonb, :request_id)
                ON CONFLICT (session_id, request_id) DO NOTHING
                """
            ),
            {
                "student_id": student_id,
                "session_id": session_id,
                "actor": _json(statement["actor"]),
                "verb": _json(statement["verb"]),
                "object": _json(statement["object"]),
                "result": _json(statement["result"]),
                "context": _json(statement["context"]),
                "request_id": request_id,
            },
        )

    async def _apply_mastery(
        self,
        session_id: UUID,
        objective_id: UUID,
        objective_code: str,
        kind: CheckinKind,
        score: float,
        now: datetime,
    ) -> None:
        current = await self.session.execute(
            text(
                """
                SELECT p_mastery, correct_count, wrong_count, evidence_count
                  FROM learning.mastery_states
                 WHERE session_id = :session_id AND objective_id = :objective_id
                """
            ),
            {"session_id": session_id, "objective_id": objective_id},
        )
        row = current.mappings().first()
        p = float(row["p_mastery"]) if row else BKT_PRIOR
        correct = score >= 0.5
        updated = bkt_update(p, correct, "mcq")
        state = objective_state(updated)
        await self.session.execute(
            text(
                """
                INSERT INTO learning.mastery_states
                    (session_id, objective_id, p_mastery, state, correct_count, wrong_count,
                     evidence_count, last_evidence_at, updated_at)
                VALUES (:session_id, :objective_id, :p, :state, :correct, :wrong, 1, :now, :now)
                ON CONFLICT (session_id, objective_id) DO UPDATE SET
                    p_mastery = EXCLUDED.p_mastery,
                    state = EXCLUDED.state,
                    correct_count = learning.mastery_states.correct_count + EXCLUDED.correct_count,
                    wrong_count = learning.mastery_states.wrong_count + EXCLUDED.wrong_count,
                    evidence_count = learning.mastery_states.evidence_count + 1,
                    last_evidence_at = EXCLUDED.last_evidence_at,
                    updated_at = EXCLUDED.updated_at
                """
            ),
            {
                "session_id": session_id,
                "objective_id": objective_id,
                "p": updated,
                "state": state,
                "correct": 1 if correct else 0,
                "wrong": 0 if correct else 1,
                "now": now,
            },
        )

    async def _refresh_retention(
        self,
        student_id: UUID,
        session_id: UUID,
        objective_id: UUID,
        score: float,
        now: datetime,
    ) -> datetime | None:
        result = await self.session.execute(
            text(
                """
                SELECT ease, interval_days, reps, lapses
                  FROM learning.retention_cards
                 WHERE student_id = :student_id AND objective_id = :objective_id
                """
            ),
            {"student_id": student_id, "objective_id": objective_id},
        )
        row = result.mappings().first()
        if row is None:
            return None
        quality = 5 if score >= 0.8 else (4 if score >= 0.5 else 2)
        updated = update_card_state(
            RetentionState(
                ease=float(row["ease"]),
                interval_days=int(row["interval_days"]),
                reps=int(row["reps"]),
                lapses=int(row["lapses"]),
            ),
            quality,
            now,
        )
        async with self.transaction():
            await self.session.execute(
                text(
                    """
                    UPDATE learning.retention_cards
                       SET ease = :ease, interval_days = :interval, due_at = :due_at,
                           reps = :reps, lapses = :lapses, updated_at = :now
                     WHERE student_id = :student_id AND objective_id = :objective_id
                    """
                ),
                {
                    "ease": updated["ease"],
                    "interval": updated["interval_days"],
                    "due_at": updated["due_at"],
                    "reps": updated["reps"],
                    "lapses": updated["lapses"],
                    "now": now,
                    "student_id": student_id,
                    "objective_id": objective_id,
                },
            )
            if updated["lapsed"]:
                await self.session.execute(
                    text(
                        """
                        UPDATE learning.mastery_states
                           SET state = :state, updated_at = :now
                         WHERE session_id = :session_id AND objective_id = :objective_id
                        """
                    ),
                    {
                        "state": with_decay("mastery", quality),
                        "now": now,
                        "session_id": session_id,
                        "objective_id": objective_id,
                    },
                )
        return updated["due_at"]

    # --- dismiss -------------------------------------------------------------

    async def dismiss(
        self, session_id: UUID, event_id: UUID, body: CheckinDismissRequest
    ) -> CheckinDismissResponse | None:
        row = await self.session.execute(
            text(
                """
                SELECT id FROM learning.checkin_events
                 WHERE id = :event_id AND session_id = :session_id
                   AND responded_at IS NULL
                """
            ),
            {"event_id": event_id, "session_id": session_id},
        )
        if row.scalar_one_or_none() is None:
            return None
        now = _now()
        async with self.transaction():
            await self.session.execute(
                text(
                    """
                    UPDATE learning.checkin_events
                       SET dismissed = true, responded_at = :now, request_id = :rid
                     WHERE id = :event_id
                    """
                ),
                {"now": now, "rid": body.request_id, "event_id": event_id},
            )
        cooldown = dismiss_cooldown_seconds()
        return CheckinDismissResponse(
            event_id=event_id,
            dismissed=True,
            cooldown_seconds=cooldown,
            next_available_in_seconds=cooldown,
        )

    # --- summary -------------------------------------------------------------

    async def summary(self, session_id: UUID) -> CoachSummaryResponse | None:
        session_row = await self._session_student(session_id)
        if session_row is None:
            return None
        mastery = await self._mastery(session_id)
        cards = await self._retention_cards(session_id)
        labels = await self._objective_labels(session_id)
        now = _now()
        due = [
            RetentionCardView(
                objective_code=labels.get(card["objective_id"], {}).get("code", ""),
                objective_label=labels.get(card["objective_id"], {}).get("label", ""),
                due_at=card["due_at"],
                interval_days=int(card["interval_days"]),
                reps=int(card["reps"]),
                lapses=int(card["lapses"]),
                overdue=card["due_at"] <= now,
            )
            for card in sorted(cards, key=lambda c: (c["due_at"], str(c["objective_id"])))
        ]
        events = await self.session.execute(
            text(
                """
                SELECT verb FROM learning.learning_events
                 WHERE session_id = :session_id ORDER BY occurred_at
                """
            ),
            {"session_id": session_id},
        )
        open_interventions = await self.session.execute(
            text(
                """
                SELECT i.id, i.level, i.trigger_rule, i.created_at, i.content,
                       o.code AS objective_code
                  FROM learning.interventions i
                  LEFT JOIN learning.objectives o ON o.id = i.objective_id
                 WHERE i.session_id = :session_id AND i.resolved_at IS NULL
                 ORDER BY i.created_at DESC
                """
            ),
            {"session_id": session_id},
        )
        used = await self.session.execute(
            text(
                """
                SELECT count(*) FROM learning.checkin_events
                 WHERE session_id = :session_id AND delivered_at IS NOT NULL
                """
            ),
            {"session_id": session_id},
        )
        return CoachSummaryResponse(
            session_id=session_id,
            streak_steps=streak_steps([dict(r) for r in events.mappings()]),
            mastery=mastery,
            due_retention=due,
            open_interventions=[
                InterventionView(
                    id=r["id"],
                    level=r["level"],
                    trigger_rule=r["trigger_rule"],
                    objective_code=r["objective_code"],
                    summary=str((r["content"] or {}).get("summary", "")),
                    created_at=r["created_at"],
                )
                for r in open_interventions.mappings()
            ],
            checkins_used=int(used.scalar_one() or 0),
            max_checkins=MAX_CHECKINS_PER_SESSION,
        )

    async def _maybe_open_intervention(
        self,
        session_id: UUID,
        objective_id: UUID,
        objective_code: str,
        score: float,
        now: datetime,
    ) -> None:
        """Priority-ordered advice ladder (Plan 05 §5.2); one open row per rule."""
        context = await self._intervention_context(session_id, score)
        decision = intervention_for(context)
        if decision is None:
            return
        level, rule = decision
        summary = _intervention_summary(level, objective_code)
        async with self.transaction():
            await self.session.execute(
                text(
                    """
                    INSERT INTO learning.interventions
                        (id, student_id, session_id, objective_id, level, trigger_rule, content)
                    SELECT gen_random_uuid(), s.student_id, s.id, :objective_id, :level,
                           :rule, :content::jsonb
                      FROM core.sessions s WHERE s.id = :session_id
                    """
                ),
                {
                    "objective_id": objective_id,
                    "level": level.value,
                    "rule": rule,
                    "content": _json({"summary": summary, "objective": objective_code}),
                    "session_id": session_id,
                },
            )

    async def _intervention_context(self, session_id: UUID, score: float) -> InterventionContext:
        quiz_fails = await self.session.execute(
            text(
                """
                SELECT count(*) FROM learning.quiz_attempts
                 WHERE session_id = :session_id AND submitted_at IS NOT NULL AND passed = false
                """
            ),
            {"session_id": session_id},
        )
        fast_wrong = await self.session.execute(
            text(
                """
                SELECT count(*) FROM learning.learning_events
                 WHERE session_id = :session_id
                   AND result->>'success' = 'false'
                   AND occurred_at >= now() - interval '10 minutes'
                """
            ),
            {"session_id": session_id},
        )
        return InterventionContext(
            quiz_fails_same_module=int(quiz_fails.scalar_one() or 0),
            fast_wrong_streak=int(fast_wrong.scalar_one() or 0),
            low_confidence_twice=score < 0.3,
        )

    async def _objective_labels(self, session_id: UUID) -> dict[UUID, dict[str, str]]:
        result = await self.session.execute(text("SELECT id, code, label FROM learning.objectives"))
        return {
            row["id"]: {"code": row["code"], "label": row["label"]} for row in result.mappings()
        }

    async def _mastery(self, session_id: UUID) -> list[CheckinObjectiveState]:
        result = await self.session.execute(
            text(
                """
                SELECT o.code AS objective_code, m.p_mastery, m.state, m.evidence_count
                  FROM learning.mastery_states m
                  JOIN learning.objectives o ON o.id = m.objective_id
                 WHERE m.session_id = :session_id
                 ORDER BY o.ordinal
                """
            ),
            {"session_id": session_id},
        )
        return [
            CheckinObjectiveState(
                objective_code=row["objective_code"],
                p_mastery=float(row["p_mastery"]),
                state=row["state"],
                evidence_count=int(row["evidence_count"]),
            )
            for row in result.mappings()
        ]

    async def create_milestone_card(self, session_id: UUID, objective_id: UUID) -> None:
        """Create an SM-2-lite card on module pass (never re-locks a module)."""
        session_row = await self._session_student(session_id)
        if session_row is None:
            return
        now = _now()
        async with self.transaction():
            await self.session.execute(
                text(
                    """
                    INSERT INTO learning.retention_cards
                        (student_id, session_id, objective_id, ease, interval_days, due_at, reps, lapses)
                    VALUES (:student_id, :session_id, :objective_id, 2.50, 1, :due_at, 0, 0)
                    ON CONFLICT (student_id, objective_id) DO NOTHING
                    """
                ),
                {
                    "student_id": session_row["student_id"],
                    "session_id": session_id,
                    "objective_id": objective_id,
                    "due_at": now + timedelta(days=1),
                },
            )


def _intervention_summary(level: InterventionLevel, objective_code: str) -> str:
    label = objective_code.replace("_", " ")
    return {
        InterventionLevel.HINT: f"Try a small hint on {label} before moving on.",
        InterventionLevel.RETEACH: f"Re-teach {label} with a worked example.",
        InterventionLevel.REQUIZ: f"Offer an alternate-form check on {label}.",
        InterventionLevel.WALKTHROUGH: f"Walk through {label} step by step together.",
        InterventionLevel.HANDOFF: f"Hand off {label} to a teacher or mentor.",
    }[level]


def _score(
    kind: CheckinKind, payload: dict[str, Any], response: list[str], free_text: str
) -> tuple[float, bool | None, str, list[str]]:
    """Deterministic scoring from the authored payload."""
    if kind == CheckinKind.LIKERT:
        scale = payload.get("scale") or {}
        try:
            value = int(response[0]) if response else int(scale.get("min", 1))
        except (TypeError, ValueError):
            value = int(scale.get("min", 1))
        return (
            score_likert(value, int(scale.get("min", 1)), int(scale.get("max", 5))),
            None,
            "Thanks — that helps me pace the next step.",
            [],
        )
    if kind == CheckinKind.MCQ:
        answer = [str(key) for key in (payload.get("answer") or [])]
        score = score_mcq(response, answer)
        return (
            score,
            score == 1.0,
            str(payload.get("explanation") or ""),
            answer,
        )
    rubric = payload.get("rubric") or {}
    criteria = list(rubric.get("criteria") or [])
    hits = sum(1 for criterion in criteria if criterion.lower() in (free_text or "").lower())
    score = score_rubric(hits, len(criteria))
    return (
        score,
        None,
        "Thanks — I used your answer to check the next step.",
        [],
    )


def _item_view(item: dict[str, Any], trigger_reason: str) -> CheckinItemView:
    payload = item.get("payload") or {}
    scale = payload.get("scale")
    return CheckinItemView(
        id=item["id"],
        objective_code=item["objective_code"],
        objective_label=item["objective_label"],
        kind=CheckinKind(item["kind"]),
        prompt=item["prompt"],
        trigger_reason=trigger_reason,
        scale=LikertScale.model_validate(scale) if scale else None,
        options=[
            CheckinOption(key=option["key"], label=option["label"])
            for option in (payload.get("options") or [])
        ],
    )


def _json(value: Any) -> str:
    import json

    return json.dumps(value, default=str)
