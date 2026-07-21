import asyncio
from uuid import uuid4

import pytest

from app.services.decision_trace import DecisionTraceRecorder, TracePrivacyError


class TransactionSpy:
    def __init__(self):
        self.events = []

    async def record_decision_event(self, **event):
        self.events.append(event)


def test_trace_is_ordered_and_correlated_without_raw_text():
    tx = TransactionSpy()
    recorder = DecisionTraceRecorder(tx, uuid4(), uuid4())

    async def record():
        await recorder.record(
            "stage_derived",
            "stage_policy",
            "v1",
            "Derived measurement stage.",
            "stage_measurement",
            inputs={"coverage": 0.5},
            outputs={"stage": "measurement"},
        )
        await recorder.record(
            "question_target_selected",
            "question_policy",
            "v1",
            "Selected required constraint.",
            "priority_required_hard_variable",
            entity_refs={"dimension_ids": ["constraints"]},
        )

    asyncio.run(record())
    assert [event["sequence"] for event in tx.events] == [1, 2]
    assert len({event["correlation_id"] for event in tx.events}) == 1
    assert tx.events[0]["inputs"] == {"coverage": 0.5}


def test_trace_rejects_duplicate_student_text():
    tx = TransactionSpy()
    recorder = DecisionTraceRecorder(tx, uuid4(), uuid4())

    with pytest.raises(TracePrivacyError, match="raw student text"):
        asyncio.run(
            recorder.record(
                "evidence_validated",
                "grounding_validator",
                "v1",
                "Validated evidence.",
                "grounded",
                inputs={"transcript": "student words"},
            )
        )
    assert tx.events == []
