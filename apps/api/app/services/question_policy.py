from dataclasses import dataclass, field
from enum import StrEnum


STAGES = ("discovery", "measurement", "gap_resolution", "profile_review", "project_matching", "complete")
BASE_VALUE = {
    "behavioral_anchor": .20,
    "required_hard_variable": .18,
    "project_critical_unknown": .16,
    "project_discrimination": .14,
    "provisional_dimension": .10,
    "profile_validation": .05,
}


class ReplySignal(StrEnum):
    GREETING = "greeting"
    CORRECTION = "correction"
    INSUFFICIENT = "insufficient"
    THIN = "thin_answer"
    SUBSTANTIVE = "substantive_answer"


class InterviewPhase(StrEnum):
    BROAD_DISCOVERY = "broad_discovery"
    BEHAVIORAL_EVIDENCE = "behavioral_evidence"
    PREFERENCE_DISCRIMINATION = "preference_discrimination"
    UNCERTAINTY_RESOLUTION = "uncertainty_resolution"
    PROJECT_FIT_PROBING = "project_fit_probing"
    REFLECTIVE_VALIDATION = "reflective_validation"


@dataclass(frozen=True)
class QuestionValue:
    project_discrimination: float = 0.0
    uncertainty_reduction: float = 0.0
    evidence_weakness: float = 0.0
    contradiction_resolution: float = 0.0
    conversational_relevance: float = 0.0
    novelty: float = 0.0
    repetition_penalty: float = 0.0
    leading_penalty: float = 0.0
    sensitivity_penalty: float = 0.0
    fatigue_penalty: float = 0.0


@dataclass(frozen=True)
class Target:
    kind: str
    key: str
    fallback_template: str
    information_gain: float = 0.5  # compatibility alias for early repositories
    continuity: float = 0.0
    asked_count: int = 0
    value: QuestionValue = field(default_factory=QuestionValue)
    target_dimensions: tuple[str, ...] = ()
    project_modes: tuple[str, ...] = ()


def classify_reply(text: str) -> ReplySignal:
    """Dialogue routing only: these cues never become assessment evidence."""
    normalized = " ".join(text.lower().split())
    if normalized in {"hi", "hello", "hey", "hiya", "yo"}:
        return ReplySignal.GREETING
    if any(cue in normalized for cue in ("i said", "that's not", "that is not", "you assumed", "why are you asking", "not what i")):
        return ReplySignal.CORRECTION
    if normalized in {"idk", "i don't know", "dont know", "dunno", "no idea", "nothing", "nothin"}:
        return ReplySignal.INSUFFICIENT
    if len(normalized.split()) <= 4:
        return ReplySignal.THIN
    return ReplySignal.SUBSTANTIVE


def question_value(target: Target) -> float:
    """Auditable V1 proxy for expected reduction in project-decision uncertainty."""
    value = target.value
    positive = (
        .30 * value.project_discrimination
        + .25 * max(value.uncertainty_reduction, target.information_gain)
        + .15 * value.evidence_weakness
        + .15 * value.contradiction_resolution
        + .10 * max(value.conversational_relevance, target.continuity)
        + .05 * value.novelty
    )
    penalties = (
        value.repetition_penalty + value.leading_penalty
        + value.sensitivity_penalty + value.fatigue_penalty
        + min(target.asked_count * .15, .6)
    )
    return round(BASE_VALUE.get(target.kind, 0.0) + positive - penalties, 6)


def select_next(candidates: list[Target]) -> Target | None:
    """Repair first; otherwise select the question with maximum decision value."""
    if not candidates:
        return None
    repair = [candidate for candidate in candidates if candidate.kind == "conversation_repair"]
    contradictions = [candidate for candidate in candidates if candidate.kind == "contradiction"]
    pool = repair or contradictions or candidates
    return min(pool, key=lambda item: (-question_value(item), item.key))


def derive_phase(*, anchors_observed: int, strong_evidence: int, contradictions: int,
                 project_modes: int, reviewed: bool) -> InterviewPhase:
    if reviewed:
        return InterviewPhase.REFLECTIVE_VALIDATION
    if contradictions:
        return InterviewPhase.UNCERTAINTY_RESOLUTION
    if anchors_observed < 2:
        return InterviewPhase.BROAD_DISCOVERY
    if strong_evidence < 3:
        return InterviewPhase.BEHAVIORAL_EVIDENCE
    if project_modes < 2:
        return InterviewPhase.PREFERENCE_DISCRIMINATION
    return InterviewPhase.PROJECT_FIT_PROBING


def derive_stage(*, coverage: float, contradictions: int, reviewed: bool, projects_ready: bool) -> str:
    if projects_ready and reviewed:
        return "complete"
    if reviewed:
        return "project_matching"
    if coverage >= 0.75 and contradictions == 0:
        return "profile_review"
    if contradictions:
        return "gap_resolution"
    if coverage >= 0.3:
        return "measurement"
    return "discovery"
