"""Async PostgreSQL repository for the sole turn write path."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.contracts import ProposedEvidence, TurnResponse, ValidatedEvidence
from app.services.contradiction_engine import find_contradictions
from app.services.grounding_validator import validate_grounding
from app.services.profile_reducer import reduce_profile
from app.services.question_policy import Target


@dataclass
class MessageRow:
    id: UUID
    session_id: UUID
    content: str
    sequence: int
    role: str = "student"


@dataclass
class TurnRow:
    id: UUID
    session_id: UUID
    idempotency_key: str
    status: str


@dataclass
class TurnOutcome:
    id: UUID
    turn_id: UUID
    content: str
    stage: str

    def as_response(self) -> TurnResponse:
        return TurnResponse(
            turn_id=self.turn_id, assistant_message=self.content, stage=self.stage
        )


class AssessmentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
        self._tx: TurnTransaction | None = None

    async def create_session(self, external_ref: str | None = None) -> dict[str, Any]:
        student_id = uuid4()
        session_id = uuid4()
        await self.session.execute(
            text(
                """
                INSERT INTO core.students (id, external_ref)
                VALUES (:id, :external_ref)
                """
            ),
            {"id": student_id, "external_ref": external_ref},
        )
        await self.session.execute(
            text(
                """
                INSERT INTO core.sessions (id, student_id, stage)
                VALUES (:id, :student_id, 'discovery')
                """
            ),
            {"id": session_id, "student_id": student_id},
        )
        # Seed coverage rows for all dimensions.
        await self.session.execute(
            text(
                """
                INSERT INTO assessment.coverage (session_id, dimension_id, status)
                SELECT :session_id, d.id, 'unknown'
                  FROM assessment.dimensions d
                """
            ),
            {"session_id": session_id},
        )
        await self.session.commit()
        return {"session_id": session_id, "student_id": student_id, "stage": "discovery"}

    async def get_session(self, session_id: UUID) -> dict[str, Any] | None:
        result = await self.session.execute(
            text(
                """
                SELECT id, student_id, stage::text AS stage, created_at, updated_at, completed_at
                  FROM core.sessions
                 WHERE id = :session_id
                """
            ),
            {"session_id": session_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def list_sessions(self, limit: int = 50) -> list[dict[str, Any]]:
        result = await self.session.execute(
            text(
                """
                SELECT s.id AS session_id,
                       s.student_id,
                       s.stage::text AS stage,
                       s.created_at,
                       s.updated_at,
                       (
                         SELECT count(*) FROM conversation.turns t
                          WHERE t.session_id = s.id AND t.status = 'completed'
                       ) AS turn_count
                  FROM core.sessions s
                 ORDER BY s.updated_at DESC
                 LIMIT :limit
                """
            ),
            {"limit": limit},
        )
        return [dict(row) for row in result.mappings()]

    async def completed_turn(
        self, session_id: UUID, idempotency_key: str
    ) -> TurnOutcome | None:
        result = await self.session.execute(
            text(
                """
                SELECT t.id AS turn_id,
                       t.status,
                       m.id AS message_id,
                       m.content,
                       s.stage::text AS stage
                  FROM conversation.turns t
                  JOIN core.sessions s ON s.id = t.session_id
             LEFT JOIN conversation.messages m ON m.id = t.assistant_message_id
                 WHERE t.session_id = :session_id
                   AND t.idempotency_key = :idempotency_key
                """
            ),
            {"session_id": session_id, "idempotency_key": idempotency_key},
        )
        row = result.mappings().first()
        if not row or row["status"] != "completed" or row["message_id"] is None:
            return None
        return TurnOutcome(
            id=row["message_id"],
            turn_id=row["turn_id"],
            content=row["content"],
            stage=row["stage"],
        )

    @asynccontextmanager
    async def transaction(self):
        tx = TurnTransaction(self.session)
        self._tx = tx
        try:
            yield tx
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        finally:
            self._tx = None


class TurnTransaction:
    def __init__(self, session: AsyncSession):
        self.session = session
        self._session_id: UUID | None = None
        self._settings = get_settings()

    async def create_turn_and_student_message(
        self, session_id: UUID, idempotency_key: str, text_content: str
    ) -> tuple[TurnRow, MessageRow]:
        self._session_id = session_id
        turn_id = uuid4()
        message_id = uuid4()
        await self.session.execute(
            text(
                """
                INSERT INTO conversation.turns (id, session_id, idempotency_key, status)
                VALUES (:id, :session_id, :idempotency_key, 'processing')
                """
            ),
            {
                "id": turn_id,
                "session_id": session_id,
                "idempotency_key": idempotency_key,
            },
        )
        seq_result = await self.session.execute(
            text(
                """
                SELECT COALESCE(MAX(sequence), 0) + 1 AS next_seq
                  FROM conversation.messages
                 WHERE session_id = :session_id
                """
            ),
            {"session_id": session_id},
        )
        sequence = int(seq_result.scalar_one())
        await self.session.execute(
            text(
                """
                INSERT INTO conversation.messages
                    (id, session_id, turn_id, sequence, role, content)
                VALUES
                    (:id, :session_id, :turn_id, :sequence, 'student', :content)
                """
            ),
            {
                "id": message_id,
                "session_id": session_id,
                "turn_id": turn_id,
                "sequence": sequence,
                "content": text_content,
            },
        )
        await self.session.execute(
            text(
                """
                UPDATE conversation.turns
                   SET student_message_id = :message_id
                 WHERE id = :turn_id
                """
            ),
            {"message_id": message_id, "turn_id": turn_id},
        )
        turn = TurnRow(
            id=turn_id,
            session_id=session_id,
            idempotency_key=idempotency_key,
            status="processing",
        )
        message = MessageRow(
            id=message_id,
            session_id=session_id,
            content=text_content,
            sequence=sequence,
            role="student",
        )
        return turn, message

    async def allowed_messages(self, session_id: UUID) -> list[MessageRow]:
        result = await self.session.execute(
            text(
                """
                SELECT id, session_id, content, sequence, role::text AS role
                  FROM conversation.messages
                 WHERE session_id = :session_id
                 ORDER BY sequence
                """
            ),
            {"session_id": session_id},
        )
        return [
            MessageRow(
                id=row["id"],
                session_id=row["session_id"],
                content=row["content"],
                sequence=row["sequence"],
                role=row["role"],
            )
            for row in result.mappings()
        ]

    async def taxonomy(self) -> dict[str, Any]:
        dims = await self.session.execute(
            text(
                "SELECT key, label, required FROM assessment.dimensions ORDER BY ordinal"
            )
        )
        motivations = await self.session.execute(
            text("SELECT key, label FROM assessment.motivation_values ORDER BY key")
        )
        return {
            "dimensions": [dict(r) for r in dims.mappings()],
            "motivation_values": [dict(r) for r in motivations.mappings()],
        }

    async def validate_and_record_evidence(
        self, items: list[ProposedEvidence], message: MessageRow
    ) -> list[ValidatedEvidence]:
        assert self._session_id is not None
        messages = await self.allowed_messages(self._session_id)
        grounded = validate_grounding(items, messages, self._session_id)
        dim_map = await self._dimension_map()
        validated: list[ValidatedEvidence] = []
        for item in grounded:
            dimension_id = dim_map.get(item.dimension_key)
            if dimension_id is None:
                item = item.model_copy(
                    update={
                        "accepted": False,
                        "rejection_reason": item.rejection_reason
                        or "unknown_dimension_key",
                    }
                )
            status = "accepted" if item.accepted else "rejected"
            evidence_id = uuid4()
            # Persist rejected unknown-dimension items against a placeholder only
            # when we have at least one dimension; otherwise skip the row.
            persist_dimension_id = dimension_id
            if persist_dimension_id is None and dim_map:
                persist_dimension_id = next(iter(dim_map.values()))
            if persist_dimension_id is not None:
                await self.session.execute(
                    text(
                        """
                        INSERT INTO assessment.evidence
                            (id, session_id, dimension_id, value_key, strength, polarity,
                             exact_source_quote, status, rejection_reason, reducer_version)
                        VALUES
                            (:id, :session_id, :dimension_id, :value_key, :strength, :polarity,
                             :exact_source_quote, CAST(:status AS assessment.evidence_status),
                             :rejection_reason, :reducer_version)
                        """
                    ),
                    {
                        "id": evidence_id,
                        "session_id": self._session_id,
                        "dimension_id": persist_dimension_id,
                        "value_key": item.value_key,
                        "strength": item.strength,
                        "polarity": item.polarity.value,
                        "exact_source_quote": item.exact_source_quote,
                        "status": status,
                        "rejection_reason": item.rejection_reason
                        if status == "rejected"
                        else None,
                        "reducer_version": self._settings.reducer_version
                        if status == "accepted"
                        else None,
                    },
                )
                for mid in item.source_message_ids:
                    await self.session.execute(
                        text(
                            """
                            INSERT INTO assessment.evidence_sources (evidence_id, message_id)
                            VALUES (:evidence_id, :message_id)
                            ON CONFLICT DO NOTHING
                            """
                        ),
                        {"evidence_id": evidence_id, "message_id": mid},
                    )
            validated.append(item)
        return validated

    async def apply_evidence_reduce_contradictions_snapshot(
        self, validated: list[ValidatedEvidence]
    ) -> dict[str, Any]:
        assert self._session_id is not None
        # Load all accepted evidence for this session as ProposedEvidence-shaped rows.
        accepted_rows = await self.session.execute(
            text(
                """
                SELECT e.id, d.key AS dimension_key, e.value_key, e.strength,
                       e.polarity, e.exact_source_quote,
                       ARRAY(
                         SELECT es.message_id::text
                           FROM assessment.evidence_sources es
                          WHERE es.evidence_id = e.id
                       ) AS source_ids
                  FROM assessment.evidence e
                  JOIN assessment.dimensions d ON d.id = e.dimension_id
                 WHERE e.session_id = :session_id
                   AND e.status = 'accepted'
                 ORDER BY e.created_at
                """
            ),
            {"session_id": self._session_id},
        )
        evidence_for_reduce: list[ValidatedEvidence] = []
        for row in accepted_rows.mappings():
            source_ids = [UUID(x) for x in (row["source_ids"] or [])] or [uuid4()]
            evidence_for_reduce.append(
                ValidatedEvidence(
                    dimension_key=row["dimension_key"],
                    value_key=row["value_key"],
                    strength=float(row["strength"]),
                    polarity=row["polarity"],
                    source_message_ids=source_ids,
                    exact_source_quote=row["exact_source_quote"],
                    rationale="persisted",
                    accepted=True,
                    rejection_reason=None,
                )
            )
        # Include newly accepted items from this turn that may not yet round-trip
        # if insert used an unknown dimension fallback path.
        for item in validated:
            if item.accepted:
                evidence_for_reduce.append(item)

        profile = reduce_profile(
            evidence_for_reduce, version=self._settings.reducer_version
        )
        version_result = await self.session.execute(
            text(
                """
                SELECT COALESCE(MAX(version), 0) + 1 AS next_version
                  FROM assessment.profile_snapshots
                 WHERE session_id = :session_id
                """
            ),
            {"session_id": self._session_id},
        )
        version = int(version_result.scalar_one())
        snapshot_id = uuid4()
        state = {
            "dimensions": [
                {
                    "key": d.key,
                    "status": d.status,
                    "value": d.value,
                    "confidence": d.confidence,
                }
                for d in profile.dimensions
            ]
        }
        now = datetime.now(timezone.utc)
        await self.session.execute(
            text(
                """
                INSERT INTO assessment.profile_snapshots
                    (id, session_id, version, reducer_version, state, evidence_boundary)
                VALUES
                    (:id, :session_id, :version, :reducer_version, CAST(:state AS jsonb), :boundary)
                """
            ),
            {
                "id": snapshot_id,
                "session_id": self._session_id,
                "version": version,
                "reducer_version": profile.reducer_version,
                "state": json.dumps(state),
                "boundary": now,
            },
        )
        await self.session.execute(
            text(
                """
                INSERT INTO assessment.profile_changes
                    (session_id, snapshot_id, before_state, after_state, reason, accepted_evidence_ids)
                VALUES
                    (:session_id, :snapshot_id, CAST('{}' AS jsonb), CAST(:after_state AS jsonb),
                     'accepted_evidence_reduced', CAST('{}' AS uuid[]))
                """
            ),
            {
                "session_id": self._session_id,
                "snapshot_id": snapshot_id,
                "after_state": json.dumps(state),
            },
        )

        dim_map = await self._dimension_map()
        for dim in profile.dimensions:
            dim_id = dim_map.get(dim.key)
            if dim_id is None:
                continue
            await self.session.execute(
                text(
                    """
                    INSERT INTO assessment.coverage (session_id, dimension_id, status, updated_at)
                    VALUES (:session_id, :dimension_id, CAST(:status AS assessment.dimension_status), now())
                    ON CONFLICT (session_id, dimension_id) DO UPDATE
                      SET status = EXCLUDED.status, updated_at = now()
                    """
                ),
                {
                    "session_id": self._session_id,
                    "dimension_id": dim_id,
                    "status": dim.status,
                },
            )

        contradictions = find_contradictions(evidence_for_reduce)
        # Mark contested coverage for contradicted dimensions.
        for contradiction in contradictions:
            dim_id = dim_map.get(contradiction.dimension_key)
            if dim_id is None:
                continue
            await self.session.execute(
                text(
                    """
                    UPDATE assessment.coverage
                       SET status = 'contested', updated_at = now()
                     WHERE session_id = :session_id AND dimension_id = :dimension_id
                    """
                ),
                {"session_id": self._session_id, "dimension_id": dim_id},
            )
            await self.session.execute(
                text(
                    """
                    INSERT INTO assessment.contradictions
                        (session_id, dimension_id, status)
                    SELECT :session_id, :dimension_id, 'open'
                     WHERE NOT EXISTS (
                       SELECT 1 FROM assessment.contradictions c
                        WHERE c.session_id = :session_id
                          AND c.dimension_id = :dimension_id
                          AND c.status = 'open'
                     )
                    """
                ),
                {"session_id": self._session_id, "dimension_id": dim_id},
            )

        open_count = await self.session.execute(
            text(
                """
                SELECT count(*) FROM assessment.contradictions
                 WHERE session_id = :session_id AND status = 'open'
                """
            ),
            {"session_id": self._session_id},
        )
        return {
            "snapshot_id": str(snapshot_id),
            "version": version,
            "contradiction_count": int(open_count.scalar_one()),
            "entity_refs": {
                "profile_snapshot_ids": [str(snapshot_id)],
                "dimension_keys": [d.key for d in profile.dimensions],
            },
        }

    async def question_candidates(self) -> list[Target]:
        assert self._session_id is not None
        intents = await self.session.execute(
            text(
                """
                SELECT key, priority, fallback_template
                  FROM assessment.question_intents
                 ORDER BY priority
                """
            )
        )
        intent_map = {row["key"]: row for row in intents.mappings()}

        open_contradictions = await self.session.execute(
            text(
                """
                SELECT d.key AS dimension_key
                  FROM assessment.contradictions c
                  JOIN assessment.dimensions d ON d.id = c.dimension_id
                 WHERE c.session_id = :session_id AND c.status = 'open'
                """
            ),
            {"session_id": self._session_id},
        )
        coverage = await self.session.execute(
            text(
                """
                SELECT d.key, d.required, c.status::text AS status
                  FROM assessment.dimensions d
                  JOIN assessment.coverage c
                    ON c.dimension_id = d.id AND c.session_id = :session_id
                 ORDER BY d.ordinal
                """
            ),
            {"session_id": self._session_id},
        )
        coverage_rows = list(coverage.mappings())

        candidates: list[Target] = []

        def add(kind: str, key: str) -> None:
            intent = intent_map.get(kind)
            if intent is None:
                return
            candidates.append(
                Target(kind=kind, key=key, fallback_template=intent["fallback_template"])
            )

        for row in open_contradictions.mappings():
            add("contradiction", row["dimension_key"])

        for row in coverage_rows:
            if row["required"] and row["status"] == "unknown":
                add("required_hard_variable", row["key"])

        for row in coverage_rows:
            if row["key"] in {"topics", "work_mode"} and row["status"] == "unknown":
                add("project_critical_unknown", row["key"])

        for row in coverage_rows:
            if row["status"] == "provisional":
                add("provisional_dimension", row["key"])

        established = sum(1 for r in coverage_rows if r["status"] == "established")
        if established >= 2:
            add("project_discrimination", "work_mode")

        add("profile_validation", "profile")

        # De-duplicate while preserving priority order from intent priority + key.
        seen: set[tuple[str, str]] = set()
        unique: list[Target] = []
        for candidate in candidates:
            marker = (candidate.kind, candidate.key)
            if marker in seen:
                continue
            seen.add(marker)
            unique.append(candidate)
        return unique

    async def stage_inputs(self) -> dict[str, Any]:
        assert self._session_id is not None
        required = await self.session.execute(
            text(
                """
                SELECT count(*) FILTER (WHERE d.required) AS required_total,
                       count(*) FILTER (
                         WHERE d.required AND c.status::text <> 'unknown'
                       ) AS required_known
                  FROM assessment.dimensions d
                  JOIN assessment.coverage c
                    ON c.dimension_id = d.id AND c.session_id = :session_id
                """
            ),
            {"session_id": self._session_id},
        )
        row = required.mappings().one()
        total = int(row["required_total"] or 0) or 1
        known = int(row["required_known"] or 0)
        open_c = await self.session.execute(
            text(
                """
                SELECT count(*) FROM assessment.contradictions
                 WHERE session_id = :session_id AND status = 'open'
                """
            ),
            {"session_id": self._session_id},
        )
        session = await self.session.execute(
            text(
                "SELECT stage::text AS stage FROM core.sessions WHERE id = :session_id"
            ),
            {"session_id": self._session_id},
        )
        current_stage = session.scalar_one()
        reviewed = current_stage in ("profile_review", "project_matching", "complete")
        projects_ready = current_stage in ("project_matching", "complete")
        return {
            "coverage": known / total,
            "contradictions": int(open_c.scalar_one()),
            "reviewed": reviewed,
            "projects_ready": projects_ready,
        }

    async def recent_messages(self) -> list[dict[str, Any]]:
        assert self._session_id is not None
        messages = await self.allowed_messages(self._session_id)
        return [
            {
                "id": str(m.id),
                "sequence": m.sequence,
                "role": m.role,
                "content": m.content,
            }
            for m in messages
        ]

    async def memory(self) -> dict[str, Any] | None:
        assert self._session_id is not None
        result = await self.session.execute(
            text(
                """
                SELECT content, boundary_sequence, prompt_version, created_at
                  FROM conversation.memory_snapshots
                 WHERE session_id = :session_id
                 ORDER BY boundary_sequence DESC
                 LIMIT 1
                """
            ),
            {"session_id": self._session_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def public_profile(self) -> dict[str, Any]:
        """Teacher-facing numerics stay out; writer gets labels and statuses only."""
        assert self._session_id is not None
        result = await self.session.execute(
            text(
                """
                SELECT state
                  FROM assessment.profile_snapshots
                 WHERE session_id = :session_id
                 ORDER BY version DESC
                 LIMIT 1
                """
            ),
            {"session_id": self._session_id},
        )
        row = result.mappings().first()
        if not row:
            return {"dimensions": []}
        state = row["state"]
        if isinstance(state, str):
            state = json.loads(state)
        public_dims = [
            {
                "key": d.get("key"),
                "status": d.get("status"),
                "value": d.get("value"),
            }
            for d in state.get("dimensions", [])
        ]
        return {"dimensions": public_dims}

    async def persist_question_and_complete(
        self,
        turn: TurnRow,
        target: Target,
        question: str,
        stage: str,
        transition: dict[str, Any],
        *,
        used_fallback: bool = False,
    ) -> TurnOutcome:
        assert self._session_id is not None
        intent = await self.session.execute(
            text("SELECT id FROM assessment.question_intents WHERE key = :key"),
            {"key": target.kind},
        )
        intent_id = intent.scalar_one()
        question_id = uuid4()
        rationale = {
            "target_kind": target.kind,
            "target_key": target.key,
            "used_fallback": used_fallback,
            "transition": {
                k: transition.get(k)
                for k in ("version", "contradiction_count", "snapshot_id")
                if k in transition
            },
        }
        await self.session.execute(
            text(
                """
                INSERT INTO assessment.questions
                    (id, session_id, turn_id, intent_id, target_key, rationale, used_fallback)
                VALUES
                    (:id, :session_id, :turn_id, :intent_id, :target_key,
                     CAST(:rationale AS jsonb), :used_fallback)
                """
            ),
            {
                "id": question_id,
                "session_id": self._session_id,
                "turn_id": turn.id,
                "intent_id": intent_id,
                "target_key": target.key,
                "rationale": json.dumps(rationale),
                "used_fallback": used_fallback,
            },
        )
        seq_result = await self.session.execute(
            text(
                """
                SELECT COALESCE(MAX(sequence), 0) + 1 AS next_seq
                  FROM conversation.messages
                 WHERE session_id = :session_id
                """
            ),
            {"session_id": self._session_id},
        )
        sequence = int(seq_result.scalar_one())
        assistant_id = uuid4()
        await self.session.execute(
            text(
                """
                INSERT INTO conversation.messages
                    (id, session_id, turn_id, sequence, role, content)
                VALUES
                    (:id, :session_id, :turn_id, :sequence, 'assistant', :content)
                """
            ),
            {
                "id": assistant_id,
                "session_id": self._session_id,
                "turn_id": turn.id,
                "sequence": sequence,
                "content": question,
            },
        )
        await self.session.execute(
            text(
                """
                UPDATE conversation.turns
                   SET assistant_message_id = :assistant_id,
                       status = 'completed',
                       completed_at = now()
                 WHERE id = :turn_id
                """
            ),
            {"assistant_id": assistant_id, "turn_id": turn.id},
        )
        await self.session.execute(
            text(
                """
                UPDATE core.sessions
                   SET stage = CAST(:stage AS conversation.stage),
                       updated_at = now(),
                       completed_at = CASE
                         WHEN :stage = 'complete' THEN now()
                         ELSE completed_at
                       END
                 WHERE id = :session_id
                """
            ),
            {"stage": stage, "session_id": self._session_id},
        )
        return TurnOutcome(
            id=assistant_id, turn_id=turn.id, content=question, stage=stage
        )

    async def record_decision_event(
        self,
        *,
        session_id: UUID,
        turn_id: UUID,
        correlation_id: UUID,
        sequence: int,
        event_type: str,
        component: str,
        component_version: str,
        decision_summary: str,
        reason_code: str,
        inputs: dict[str, Any],
        outputs: dict[str, Any],
        entity_refs: dict[str, Any],
        llm_run_id: UUID | None = None,
        duration_ms: int | None = None,
    ) -> None:
        await self.session.execute(
            text(
                """
                INSERT INTO audit.decision_events
                    (session_id, turn_id, correlation_id, sequence, event_type,
                     component, component_version, decision_summary, reason_code,
                     inputs, outputs, entity_refs, llm_run_id, duration_ms)
                VALUES
                    (:session_id, :turn_id, :correlation_id, :sequence,
                     CAST(:event_type AS audit.decision_event_type),
                     :component, :component_version, :decision_summary, :reason_code,
                     CAST(:inputs AS jsonb), CAST(:outputs AS jsonb),
                     CAST(:entity_refs AS jsonb), :llm_run_id, :duration_ms)
                """
            ),
            {
                "session_id": session_id,
                "turn_id": turn_id,
                "correlation_id": correlation_id,
                "sequence": sequence,
                "event_type": event_type,
                "component": component,
                "component_version": component_version,
                "decision_summary": decision_summary,
                "reason_code": reason_code,
                "inputs": json.dumps(inputs),
                "outputs": json.dumps(outputs),
                "entity_refs": json.dumps(entity_refs),
                "llm_run_id": llm_run_id,
                "duration_ms": duration_ms,
            },
        )

    async def record_llm_run(
        self,
        *,
        prompt_name: str,
        prompt_version: str,
        deployment: str,
        response_id: str | None,
        usage: Any,
        session_id: UUID | None = None,
        turn_id: UUID | None = None,
        status: str = "succeeded",
        error_code: str | None = None,
    ) -> UUID:
        run_id = uuid4()
        usage_payload = None
        if usage is not None:
            if hasattr(usage, "model_dump"):
                usage_payload = usage.model_dump()
            elif isinstance(usage, dict):
                usage_payload = usage
            else:
                usage_payload = {"raw": str(usage)}
        fingerprint = f"{prompt_name}:{prompt_version}:{deployment}"
        await self.session.execute(
            text(
                """
                INSERT INTO audit.llm_runs
                    (id, session_id, turn_id, purpose, prompt_version, deployment_name,
                     status, response_id, input_fingerprint, usage, error_code, completed_at)
                VALUES
                    (:id, :session_id, :turn_id, :purpose, :prompt_version, :deployment,
                     CAST(:status AS audit.llm_status), :response_id, :fingerprint,
                     CAST(:usage AS jsonb), :error_code, now())
                """
            ),
            {
                "id": run_id,
                "session_id": session_id,
                "turn_id": turn_id,
                "purpose": prompt_name,
                "prompt_version": prompt_version,
                "deployment": deployment,
                "status": status,
                "response_id": response_id,
                "fingerprint": fingerprint,
                "usage": json.dumps(usage_payload) if usage_payload is not None else None,
                "error_code": error_code,
            },
        )
        return run_id

    async def _dimension_map(self) -> dict[str, int]:
        result = await self.session.execute(
            text("SELECT id, key FROM assessment.dimensions")
        )
        return {row["key"]: row["id"] for row in result.mappings()}
