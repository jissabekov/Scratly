"""Regression tests for F7 reliability defects (FK, NUL, grounding)."""

from uuid import uuid4

from app.contracts import ProposedEvidence
from app.services.grounding_validator import validate_grounding


class _Msg:
    def __init__(self, mid, session_id, content):
        self.id = mid
        self.session_id = session_id
        self.content = content


def _item(mid, quote="exact", value="a", strength=0.8):
    return ProposedEvidence(
        dimension_key="topics",
        value_key=value,
        strength=strength,
        source_message_ids=[mid],
        exact_source_quote=quote,
        rationale="test",
    )


def test_rejected_proposal_with_foreign_message_id_is_rejected_not_linked():
    session_id = uuid4()
    other_session = uuid4()
    owned = _Msg(uuid4(), session_id, "an exact answer")
    foreign = _Msg(uuid4(), other_session, "foreign")
    result = validate_grounding(
        [_item(foreign.id, "foreign")],
        [owned, foreign],
        session_id,
    )
    assert not result[0].accepted
    assert result[0].rejection_reason == "source_message_unavailable_or_not_owned"


def test_nul_bytes_in_quote_are_cleaned_before_persist():
    quote = "hello\x00world"
    cleaned = quote.replace("\x00", "")
    assert "\x00" not in cleaned
    assert cleaned == "helloworld"


def test_azure_openai_contextvars_are_isolated():
    from contextvars import copy_context

    from app.services import azure_openai

    ctx_a = copy_context()
    ctx_b = copy_context()

    def set_a():
        azure_openai._llm_last_run_id.set(uuid4())

    def read_b():
        return azure_openai._llm_last_run_id.get()

    ctx_a.run(set_a)
    assert ctx_b.run(read_b) is None
