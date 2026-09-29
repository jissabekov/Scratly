"""LLM phrasing boundary for check-ins (Plan 05 W5.5).

The LLM may only **phrase** an already-decided check-in and **classify** a
free-text answer against the item's rubric. It never chooses what to ask, when to
ask, or what a score means — ``learning_checkin_engine`` owns all of that.

Privacy (§5.5): the payload carries objective ids, the rubric, and the item form
only. It never receives chat PII. Any failure falls back to the deterministic
authored prompt, so the pipeline works with no model at all.
"""

from __future__ import annotations

from typing import Any, Sequence

from pydantic import Field

from app.contracts.learning import LearningModel
from app.contracts.learning_checkin import CheckinKind

PROMPT_NAME = "checkin_phrasing"
PROMPT_VERSION = "v1"
PHRASING_DEPLOYMENT = "writer"


class CheckinPhrasing(LearningModel):
    """Structured output: one phrasing plus the rubric hits it observed."""

    phrasing: str
    rubric_hits: list[str] = Field(default_factory=list)


async def phrase_and_classify_async(
    llm: Any,
    *,
    kind: CheckinKind,
    objective_code: str,
    objective_label: str,
    prompt: str,
    rubric: Sequence[str] = (),
    student_response: str = "",
) -> CheckinPhrasing:
    """Async variant that calls the model when available and validates its output.

    The classification is validated server-side: only criteria that appear
    verbatim in the item's rubric are kept, and a failure returns the
    deterministic template.
    """
    fallback = CheckinPhrasing(phrasing=prompt, rubric_hits=[])
    if llm is None or kind in {CheckinKind.LIKERT, CheckinKind.MCQ}:
        return fallback
    context = {
        "item_form": kind.value,
        "objective_code": objective_code,
        "objective_label": objective_label,
        "rubric": {"criteria": list(rubric)},
        "phrasing_style": "teen",
        "student_response": student_response,
    }
    try:
        result = await llm.structured(
            PHRASING_DEPLOYMENT,
            PROMPT_NAME,
            PROMPT_VERSION,
            CheckinPhrasing,
            context,
        )
    except Exception:
        return fallback
    allowed = {criterion for criterion in rubric}
    hits = [hit for hit in result.rubric_hits if hit in allowed]
    phrasing = (result.phrasing or "").strip() or prompt
    return CheckinPhrasing(phrasing=phrasing, rubric_hits=hits)
