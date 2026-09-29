"""Plan 04 boundary: quiz delivery and attempts are not implemented yet.

Phase 3 builds the module path and the *shape* of the quiz gate only (the hub
reports ``quiz_gate_locked`` and the module detail reports a locked gate). The
4/5 + critical-objective pass rule, remediation, and BKT mastery are Plan 04.
These endpoints exist so the boundary is explicit and routable.
"""

from uuid import UUID

from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["learning"])


def _not_implemented(endpoint: str, phase: int) -> HTTPException:
    return HTTPException(
        status_code=501,
        detail={
            "error": "not_implemented",
            "endpoint": endpoint,
            "planned_phase": phase,
            "note": "Quiz gating (4/5 + critical objective) lands in Plan 04.",
        },
    )


@router.get("/sessions/{session_id}/learning/modules/{module_id}/quiz")
async def next_quiz_attempt(session_id: UUID, module_id: UUID):
    raise _not_implemented("GET module quiz", 4)


@router.post("/sessions/{session_id}/learning/quiz-attempts")
async def submit_quiz_attempt(session_id: UUID):
    raise _not_implemented("POST quiz-attempts", 4)
