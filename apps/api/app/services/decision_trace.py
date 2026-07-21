"""Structured, privacy-aware records explaining deterministic turn decisions."""
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4


class TracePrivacyError(ValueError):
    pass


_FORBIDDEN_KEYS = frozenset({"content", "message", "raw_text", "student_text", "transcript", "exact_source_quote"})


def _assert_no_raw_text(value: Any, path: str = "payload") -> None:
    """Reject fields that could duplicate student text in the audit schema."""
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in _FORBIDDEN_KEYS:
                raise TracePrivacyError(f"raw student text is forbidden at {path}.{key}")
            _assert_no_raw_text(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_raw_text(child, f"{path}[{index}]")


@dataclass
class DecisionTraceRecorder:
    tx: Any
    session_id: UUID
    turn_id: UUID
    correlation_id: UUID = field(default_factory=uuid4)
    sequence: int = 0

    async def record(
        self,
        event_type: str,
        component: str,
        component_version: str,
        decision_summary: str,
        reason_code: str,
        *,
        inputs: dict[str, Any] | None = None,
        outputs: dict[str, Any] | None = None,
        entity_refs: dict[str, Any] | None = None,
        llm_run_id: UUID | None = None,
        duration_ms: int | None = None,
    ) -> None:
        safe_inputs, safe_outputs = inputs or {}, outputs or {}
        _assert_no_raw_text(safe_inputs, "inputs")
        _assert_no_raw_text(safe_outputs, "outputs")
        self.sequence += 1
        await self.tx.record_decision_event(
            session_id=self.session_id,
            turn_id=self.turn_id,
            correlation_id=self.correlation_id,
            sequence=self.sequence,
            event_type=event_type,
            component=component,
            component_version=component_version,
            decision_summary=decision_summary,
            reason_code=reason_code,
            inputs=safe_inputs,
            outputs=safe_outputs,
            entity_refs=entity_refs or {},
            llm_run_id=llm_run_id,
            duration_ms=duration_ms,
        )
