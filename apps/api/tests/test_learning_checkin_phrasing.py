"""Unit tests for the check-in LLM phrasing boundary (Plan 05 W5.5)."""

from __future__ import annotations

import pytest

from app.contracts.learning_checkin import CheckinKind
from app.services.learning_checkin_phrasing import (
    CheckinPhrasing,
    phrase_and_classify_async,
)

RUBRIC = ("names the objective", "gives an example")


class _StubLLM:
    def __init__(self, result: CheckinPhrasing | Exception):
        self.result = result
        self.calls = 0
        self.context: dict | None = None

    async def structured(self, deployment, prompt_name, prompt_version, model, context):
        self.calls += 1
        self.context = context
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.mark.asyncio
async def test_no_llm_returns_deterministic_template() -> None:
    result = await phrase_and_classify_async(
        None,
        kind=CheckinKind.SELF_EXPLAIN,
        objective_code="events",
        objective_label="Explain events",
        prompt="Explain events in your own words.",
        rubric=RUBRIC,
    )
    assert result.phrasing == "Explain events in your own words."
    assert result.rubric_hits == []


@pytest.mark.asyncio
async def test_likert_and_mcq_never_call_the_model() -> None:
    llm = _StubLLM(CheckinPhrasing(phrasing="x", rubric_hits=list(RUBRIC)))
    for kind in (CheckinKind.LIKERT, CheckinKind.MCQ):
        result = await phrase_and_classify_async(
            llm,
            kind=kind,
            objective_code="events",
            objective_label="Explain events",
            prompt="How confident are you?",
            rubric=RUBRIC,
        )
        assert result.rubric_hits == []
    assert llm.calls == 0


@pytest.mark.asyncio
async def test_classification_is_validated_against_the_rubric() -> None:
    llm = _StubLLM(
        CheckinPhrasing(
            phrasing="Nice explanation.",
            rubric_hits=["names the objective", "invented criterion"],
        )
    )
    result = await phrase_and_classify_async(
        llm,
        kind=CheckinKind.MINI_EXERCISE,
        objective_code="events",
        objective_label="Explain events",
        prompt="Try this.",
        rubric=RUBRIC,
        student_response="I named the objective.",
    )
    assert result.rubric_hits == ["names the objective"]


@pytest.mark.asyncio
async def test_model_failure_falls_back_to_the_template() -> None:
    llm = _StubLLM(RuntimeError("azure_down"))
    result = await phrase_and_classify_async(
        llm,
        kind=CheckinKind.SELF_EXPLAIN,
        objective_code="state",
        objective_label="Explain state",
        prompt="Explain state.",
        rubric=RUBRIC,
        student_response="something",
    )
    assert result.phrasing == "Explain state."
    assert result.rubric_hits == []


@pytest.mark.asyncio
async def test_payload_carries_no_student_identity() -> None:
    llm = _StubLLM(CheckinPhrasing(phrasing="ok", rubric_hits=[]))
    await phrase_and_classify_async(
        llm,
        kind=CheckinKind.SELF_EXPLAIN,
        objective_code="loop",
        objective_label="Trace the loop",
        prompt="Trace it.",
        rubric=RUBRIC,
        student_response="the loop goes round",
    )
    assert llm.context is not None
    assert set(llm.context) == {
        "item_form",
        "objective_code",
        "objective_label",
        "rubric",
        "phrasing_style",
        "student_response",
    }
