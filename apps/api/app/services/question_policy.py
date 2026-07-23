"""Deterministic stage and question-target policy (V1 anchors).

Merges the local V1 anchor policy (priority order, discovery gating, seeded
fallbacks) with the adaptive-conversation PR's reply classification, decision
value scoring, and interview-phase derivation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.services.location_policy import location_established_from_profile

PRIORITY = (
    "contradiction",
    "required_hard_variable",
    "project_critical_unknown",
    "provisional_dimension",
    "project_discrimination",
    "profile_validation",
)

# 7-anchor discovery order: interests → depth → work-mode → motivation →
# execution → hard outreach/visibility/geo. Decision-impact unknowns win ties.
ANCHOR_KEY_ORDER = (
    "topics",
    "work_mode",
    "motivation",
    "execution",
    "execution:persistence",
    "execution:ambiguity_tolerance",
    "execution:outreach_willingness",
    "execution:public_visibility",
    "constraints",
    "constraints:geo",
    "capability",
    "assets",
)

# Required dims other than topics stay gated until interest depth is real.
_POST_INTEREST_REQUIRED = {
    "work_mode",
    "motivation",
    "execution",
    "constraints",
    "constraints:geo",
    "capability",
    "assets",
}

STAGES = (
    "discovery",
    "measurement",
    "gap_resolution",
    "profile_review",
    "project_matching",
    "complete",
)

GAP_RESOLUTION_ESTABLISHED = 0.5
PROFILE_REVIEW_ESTABLISHED = 0.9
MEASUREMENT_TOUCHED = 0.4
CORE_REVIEW_ANCHORS = ("topics", "work_mode", "motivation", "execution")
CORE_REVIEW_REQUIRED_SUPPORTED = ("topics", "work_mode", "motivation")
HIGH_REPEAT_KEYS = frozenset(
    {"constraints", "constraints:geo", "capability", "execution", "profile", "work_mode"}
)

_ANCHOR_RANK = {k: i for i, k in enumerate(ANCHOR_KEY_ORDER)}
_ANCHOR_RANK_FALLBACK = len(ANCHOR_KEY_ORDER)

# Back-compat alias used by older tests/docs.
DISCOVERY_KEY_ORDER = ANCHOR_KEY_ORDER

# Base decision value per target kind (adaptive-conversation PR).
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


class PlannerAction(StrEnum):
    """The planner's intention; the question writer may not change it."""

    FOLLOW_UP = "follow_up"
    SWITCH = "switch"
    BRIDGE = "bridge"
    CLARIFY = "clarify"
    VERIFY = "verify"
    GATE = "gate"


class DiscoveryPhase(StrEnum):
    CONTRACT = "conversation_contract"
    BREADTH = "breadth_scan"
    VERIFY = "selective_verification"
    FEASIBILITY = "hard_feasibility"
    REFLECTION = "reflection"


DEFAULT_MAX_TOPIC_DEPTH = 2
ABSOLUTE_MAX_TOPIC_DEPTH = 3


@dataclass(frozen=True)
class PlannerDecision:
    target: Target
    action: PlannerAction
    phase: DiscoveryPhase
    reason: str
    avoid_topics: tuple[str, ...] = ()


def is_topic_rejection(text: str) -> bool:
    normalized = " ".join((text or "").lower().split())
    return any(cue in normalized for cue in (
        "talk about something else", "change the subject", "different topic",
        "move on", "stop asking about", "don't want to talk about",
        "dont want to talk about",
    ))


def is_frustration(text: str) -> bool:
    normalized = " ".join((text or "").lower().split())
    return is_topic_rejection(normalized) or any(cue in normalized for cue in (
        "why are you asking", "why do you keep asking", "this is annoying",
        "are you analyzing me", "personality test",
    ))


def plan_next(
    candidates: list[Target],
    *,
    last_target_key: str | None,
    student_text: str,
    breadth_complete: bool = False,
    blocked_topics: tuple[str, ...] = (),
) -> PlannerDecision | None:
    """Choose *what* happens next with hard breadth and saturation controls.

    Candidate ``key`` is the persisted topic identifier. A rejected topic is
    excluded immediately; the caller can persist that boundary in its trace.
    During breadth, an exhausted branch can never beat a major unasked area.
    """
    if not candidates:
        return None
    rejected = is_topic_rejection(student_text)
    frustrated = is_frustration(student_text)
    blocked = set(blocked_topics)
    if rejected and last_target_key:
        blocked.add(last_target_key)
    pool = [c for c in candidates if c.key not in blocked]
    if not pool:
        pool = candidates

    major_uncovered = [c for c in pool if c.asked_count == 0]
    current = [c for c in pool if c.key == last_target_key]
    current_depth = max((c.asked_count for c in current), default=0)

    if rejected or frustrated:
        target = select_next(major_uncovered or [c for c in pool if c.key != last_target_key] or pool)
        return PlannerDecision(
            target=target,
            action=PlannerAction.SWITCH,
            phase=DiscoveryPhase.BREADTH,
            reason="topic_rejected" if rejected else "friction_detected",
            avoid_topics=tuple(sorted(blocked)),
        )

    if classify_reply(student_text) == ReplySignal.INSUFFICIENT and major_uncovered:
        target = select_next([c for c in major_uncovered if c.key != last_target_key] or major_uncovered)
        return PlannerDecision(target, PlannerAction.SWITCH, DiscoveryPhase.BREADTH, "branch_yield_collapsed")

    if last_target_key and current_depth >= 3:
        switch_pool = [c for c in pool if c.key != last_target_key and not is_repetition_blocked(c)]
        if switch_pool:
            target = select_next(switch_pool)
            return PlannerDecision(
                target,
                PlannerAction.SWITCH,
                DiscoveryPhase.BREADTH if not breadth_complete else DiscoveryPhase.VERIFY,
                "follow_up_exhausted",
            )

    if not breadth_complete and major_uncovered and current_depth >= DEFAULT_MAX_TOPIC_DEPTH:
        target = select_next([c for c in major_uncovered if c.key != last_target_key] or major_uncovered)
        return PlannerDecision(target, PlannerAction.SWITCH, DiscoveryPhase.BREADTH, "topic_budget_reached")

    # A fourth ask is invalid before breadth completes, regardless of score.
    eligible = [
        c for c in pool
        if breadth_complete or c.asked_count < ABSOLUTE_MAX_TOPIC_DEPTH
    ] or pool
    target = select_next(eligible)
    if target is None:
        return None
    if target.key == last_target_key:
        action = PlannerAction.FOLLOW_UP
        reason = "one_high_value_behavioral_follow_up"
    else:
        action = PlannerAction.BRIDGE if last_target_key else PlannerAction.SWITCH
        reason = "largest_coverage_gap"
    if target.kind == "contradiction":
        action, reason = PlannerAction.CLARIFY, "resolve_contradiction"
    elif target.kind == "required_hard_variable" and target.key in {
        "constraints", "constraints:geo", "execution:outreach_willingness",
        "execution:public_visibility",
    }:
        action, reason = PlannerAction.GATE, "hard_feasibility"
    return PlannerDecision(
        target,
        action,
        DiscoveryPhase.VERIFY if breadth_complete else DiscoveryPhase.BREADTH,
        reason,
        tuple(sorted(blocked)),
    )


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
    # Adaptive-conversation decision-value fields (optional; default preserves
    # the V1 anchor-priority behavior when not supplied).
    information_gain: float = 0.5  # compatibility alias for early repositories
    continuity: float = 0.0
    asked_count: int = 0
    coverage_status: str = "unknown"
    value: QuestionValue = field(default_factory=QuestionValue)
    target_dimensions: tuple[str, ...] = ()
    project_modes: tuple[str, ...] = ()


def classify_reply(text: str) -> ReplySignal:
    """Dialogue routing only: these cues never become assessment evidence."""
    normalized = " ".join((text or "").lower().split())
    if normalized in {"hi", "hello", "hey", "hiya", "yo"}:
        return ReplySignal.GREETING
    if any(
        cue in normalized
        for cue in (
            "i said",
            "that's not",
            "that is not",
            "you assumed",
            "why are you asking",
            "not what i",
        )
    ):
        return ReplySignal.CORRECTION
    if normalized in {
        "idk",
        "i don't know",
        "dont know",
        "dunno",
        "no idea",
        "nothing",
        "nothin",
        "no",
        "not really",
    }:
        return ReplySignal.INSUFFICIENT
    if len(normalized.split()) <= 4:
        return ReplySignal.THIN
    return ReplySignal.SUBSTANTIVE


def is_repetition_blocked(target: Target) -> bool:
    """Hard-stop re-asking anchors that stop yielding new evidence."""
    if target.kind in {"contradiction", "conversation_repair"}:
        return False
    if target.asked_count >= 2 and target.coverage_status in {"supported", "established"}:
        return True
    if (
        target.asked_count >= 2
        and target.coverage_status == "provisional"
        and target.key in HIGH_REPEAT_KEYS
    ):
        return True
    if target.asked_count >= 3 and target.key in HIGH_REPEAT_KEYS:
        return True
    return False


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
        value.repetition_penalty
        + value.leading_penalty
        + value.sensitivity_penalty
        + value.fatigue_penalty
        + target.asked_count * .35
    )
    return round(BASE_VALUE.get(target.kind, 0.0) + positive - penalties, 6)


def select_next(candidates: list[Target]) -> Target | None:
    """Repair first, then contradictions; otherwise maximize decision value.

    Ties break by the V1 anchor order then key so the documented discovery
    sequence (topics → work-mode → …) is preserved when values are equal.
    """
    if not candidates:
        return None
    repair = [c for c in candidates if c.kind == "conversation_repair"]
    contradictions = [c for c in candidates if c.kind == "contradiction"]
    pool = repair or contradictions or candidates
    eligible = [c for c in pool if not is_repetition_blocked(c)] or pool
    return min(
        eligible,
        key=lambda x: (
            -question_value(x),
            _ANCHOR_RANK.get(x.key, _ANCHOR_RANK_FALLBACK),
            x.key,
        ),
    )


def derive_phase(
    *,
    anchors_observed: int,
    strong_evidence: int,
    contradictions: int,
    project_modes: int,
    reviewed: bool,
) -> InterviewPhase:
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


def evaluate_review_eligibility(
    *,
    contradictions: int,
    location_ready: bool | None,
    coverage_established: float,
    dimension_statuses: dict[str, str],
) -> tuple[bool, str | None]:
    """Decision-sufficient review latch — core anchors supported without full inventory."""
    if contradictions > 0:
        return False, None
    if location_ready is False:
        return False, None
    if not all(
        dimension_statuses.get(k) == "supported" for k in CORE_REVIEW_REQUIRED_SUPPORTED
    ):
        return False, None
    if dimension_statuses.get("execution") not in {"supported", "provisional"}:
        return False, None
    secondary_ok = (
        dimension_statuses.get("capability") in {"supported", "provisional"}
        or dimension_statuses.get("assets") in {"supported", "provisional"}
    )
    if not secondary_ok:
        return False, None
    if coverage_established >= 0.6:
        return True, "decision_sufficient_review"
    return False, None


def derive_stage(
    *,
    contradictions: int,
    reviewed: bool,
    projects_ready: bool,
    coverage_established: float | None = None,
    coverage_touched: float | None = None,
    coverage: float | None = None,
    location_ready: bool | None = None,
    dimension_statuses: dict[str, str] | None = None,
    **_ignored: Any,
) -> str:
    """Derive stage from supported coverage and open true contradictions.

    Legacy callers may pass ``coverage`` (treated as supported/established).
    Contested dims contribute only to ``coverage_touched``.

    ``project_matching`` requires reviewed + location_ready (when provided).
    """
    established = (
        coverage
        if coverage_established is None and coverage is not None
        else (coverage_established or 0.0)
    )
    touched = established if coverage_touched is None else coverage_touched
    statuses = dimension_statuses or {}

    if projects_ready and reviewed:
        return "complete"
    if reviewed:
        if location_ready is False:
            return "profile_review"
        return "project_matching"
    review_eligible, _reason = evaluate_review_eligibility(
        contradictions=contradictions,
        location_ready=location_ready,
        coverage_established=established,
        dimension_statuses=statuses,
    )
    if review_eligible and contradictions == 0:
        return "profile_review"
    if established >= PROFILE_REVIEW_ESTABLISHED and contradictions == 0:
        return "profile_review"
    if contradictions > 0 and established >= GAP_RESOLUTION_ESTABLISHED:
        return "gap_resolution"
    if touched >= MEASUREMENT_TOUCHED:
        return "measurement"
    return "discovery"


def location_ready(profile: dict) -> bool:
    return location_established_from_profile(profile)


def interest_depth_ready(profile: dict[str, Any] | None) -> bool:
    """True once we have enough interest depth to leave discovery-of-topics.

    Matches the documented 7-anchor order: warm open → interest depth → work-mode.
    A single casual mention ("playing videogames") stays provisional/shallow and
    must be deepened before other required dims (especially work_mode).
    """
    if not profile:
        return False
    dims = {
        d.get("key"): d
        for d in (profile.get("dimensions") or [])
        if isinstance(d, dict) and d.get("key")
    }
    topics = dims.get("topics") or {}
    status = topics.get("status")
    if status in {"supported", "contradicted"}:
        return True

    interests = profile.get("interests") or []
    best_score = -1
    best_evidence = 0
    for item in interests:
        if not isinstance(item, dict):
            continue
        score = item.get("score")
        if score is None:
            continue
        score_i = int(score)
        evidence = int(item.get("evidence_count") or 0)
        if score_i > best_score or (
            score_i == best_score and evidence > best_evidence
        ):
            best_score = score_i
            best_evidence = evidence

    # Need repeated behavioral signal — a single casual mention stays shallow.
    if best_score >= 2 and best_evidence >= 2:
        return True
    if best_score >= 3 and best_evidence >= 2:
        return True
    return False


def should_emit_required(key: str, *, interests_ready: bool) -> bool:
    """Gate post-interest required asks until interest depth is ready."""
    # Legacy `location` dimension from adaptive-conversation merge — geography
    # lives on constraints; never emit a duplicate required ask for it.
    if key == "location":
        return False
    if key == "topics":
        return True
    if key in _POST_INTEREST_REQUIRED:
        return interests_ready
    return True


def contradiction_fallback(
    dimension_key: str, value_a: str | None, value_b: str | None
) -> str:
    """Seeded contradiction wording that names the concrete options."""
    label = dimension_key.replace("_", " ")
    if value_a and value_b:
        return (
            f"For {label}, do you lean more toward {value_a.replace('_', ' ')} "
            f"or {value_b.replace('_', ' ')} — or both in different situations?"
        )
    if value_a:
        return (
            f"For {label}, is {value_a.replace('_', ' ')} still the preference "
            f"you want to prioritize?"
        )
    return f"For {label}, which preference is closer to what you want now?"


_REQUIRED_FALLBACKS = {
    "topics": (
        "Hey — good to meet you. When you've had free time lately, what have you "
        "actually been spending it on?"
    ),
    "work_mode": (
        "Thinking about what you just described, which part do you enjoy doing most?"
    ),
    "motivation": (
        "What usually makes something feel worth the time you put into it?"
    ),
    "execution": (
        "What's something difficult you kept working at after it became frustrating "
        "or boring?"
    ),
    "execution:persistence": (
        "What's something difficult you kept working at after it became frustrating "
        "or boring?"
    ),
    "execution:ambiguity_tolerance": (
        "If I said 'find a way to make something useful in your area' with no steps, "
        "does that sound interesting or annoying — and what would you do first?"
    ),
    "execution:outreach_willingness": (
        "How comfortable would you be emailing an organization you've never talked to?"
    ),
    "execution:public_visibility": (
        "How do you feel about eventually presenting your work publicly — class only, "
        "outside orgs, or a bigger pitch/demo?"
    ),
    "constraints": (
        "Any must-haves I should keep in mind — deadline, tools, budget, or other limits?"
    ),
    "constraints:geo": (
        "Where are you based (city or region), or is remote fine too?"
    ),
    "capability": "What skills or tools are you already comfortable using?",
    "assets": (
        "Do you have any unusual access that could help — people, teams, datasets, "
        "equipment, communities, or a job/hobby connection?"
    ),
}


def interest_depth_fallback(topic: str | None = None) -> str:
    """Natural follow-up to an interest — not a survey about engagement levels."""
    if topic:
        label = str(topic).replace("_", " ").strip()
        if any(word in label.lower() for word in ("game", "gaming")):
            return f"Nice — what games have you been playing lately?"
        return f"Nice — what do you enjoy most about {label}?"
    return "Nice — what do you enjoy most about it?"


def social_intro_target(
    last_target_key: str | None, student_text: str | None
) -> Target | None:
    """Return the next low-pressure introduction turn, if one is due.

    Introductions are deliberately outside the assessment dimensions. This makes
    the first exchange feel like meeting a person rather than starting a form.
    """
    if last_target_key is None:
        return Target(
            "social_intro",
            "conversation_contract",
            "I’m here to help find a course project you’d actually enjoy. I’ll bounce "
            "around between what you like, what you’re good at, and what feels doable—"
            "there are no right answers. What have you been into lately, even outside school?",
            continuity=1.0,
        )
    return None


def required_fallback(key: str) -> str:
    """Teen-friendly seeded ask for a required / discovery target key."""
    if key in _REQUIRED_FALLBACKS:
        return _REQUIRED_FALLBACKS[key]
    label = key.replace("_", " ").replace(":", " ")
    return f"What should I know about your {label}?"
