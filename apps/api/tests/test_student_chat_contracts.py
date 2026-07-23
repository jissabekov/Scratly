"""Contract tests for student-facing turn and transcript shapes."""

from uuid import uuid4

from app.contracts import (
    ElicitationOption,
    ElicitationSpec,
    MessageItem,
    SessionMessagesResponse,
    SessionProjectsResponse,
    StudentProjectItem,
    TurnResponse,
)
from app.repository.assessment import TurnOutcome
from app.services.elicitation_policy import build_elicitation_spec


def test_turn_response_includes_enriched_fields():
    elicitation = build_elicitation_spec("topics")
    turn_id = uuid4()
    student_id = uuid4()
    assistant_id = uuid4()
    response = TurnResponse(
        turn_id=turn_id,
        assistant_message="Which topic fits best?",
        stage="discovery",
        message_kind="elicitation",
        elicitation=elicitation,
        student_message_id=student_id,
        assistant_message_id=assistant_id,
    )
    payload = response.model_dump(mode="json")
    assert payload["message_kind"] == "elicitation"
    assert payload["elicitation"]["dimension_key"] == "topics"
    assert len(payload["elicitation"]["options"]) >= 2
    assert payload["student_message_id"] == str(student_id)
    assert payload["assistant_message_id"] == str(assistant_id)


def test_turn_outcome_as_response_maps_fields():
    elicitation = ElicitationSpec(
        options=[
            ElicitationOption(key="a", label="alpha"),
            ElicitationOption(key="b", label="beta"),
        ],
        dimension_key="work_mode",
        fallback_template="pick one",
    )
    assistant_id = uuid4()
    student_id = uuid4()
    turn_id = uuid4()
    outcome = TurnOutcome(
        id=assistant_id,
        turn_id=turn_id,
        content="For work mode, which is closer?",
        stage="measurement",
        message_kind="elicitation",
        elicitation=elicitation,
        student_message_id=student_id,
        assistant_message_id=assistant_id,
    )
    response = outcome.as_response()
    assert response.turn_id == turn_id
    assert response.message_kind == "elicitation"
    assert response.elicitation is not None
    assert response.elicitation.dimension_key == "work_mode"
    assert response.student_message_id == student_id
    assert response.assistant_message_id == assistant_id


def test_session_messages_and_projects_contracts():
    session_id = uuid4()
    messages = SessionMessagesResponse(
        session_id=session_id,
        stage="discovery",
        completed_at=None,
        items=[
            MessageItem(
                id=uuid4(),
                turn_id=uuid4(),
                sequence=1,
                role="student",
                content="Hello",
                message_kind=None,
                created_at="2026-07-23T12:00:00Z",
            ),
            MessageItem(
                id=uuid4(),
                turn_id=uuid4(),
                sequence=2,
                role="assistant",
                content="What constraints matter?",
                message_kind="assessment_question",
                created_at="2026-07-23T12:00:01Z",
            ),
        ],
    )
    assert len(messages.items) == 2
    assert messages.items[1].message_kind == "assessment_question"

    projects = SessionProjectsResponse(
        session_id=session_id,
        items=[
            StudentProjectItem(
                id=uuid4(),
                title="Air quality map",
                summary="Map local sensors with Python.",
                topic_keys=["data"],
                work_mode_keys=["build", "investigate"],
                motivation_keys=["impact_usefulness"],
                citation_count=2,
            )
        ],
    )
    assert projects.items[0].citation_count == 2
    assert "confidence" not in projects.model_dump()
