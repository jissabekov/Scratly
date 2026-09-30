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

STAGE_RANK = {stage: rank for rank, stage in enumerate(STAGES)}

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
    "behavioral_anchor": 0.20,
    "required_hard_variable": 0.18,
    "project_critical_unknown": 0.16,
    "project_discrimination": 0.14,
    "contradiction": 0.12,
    "provisional_dimension": 0.10,
    "profile_validation": 0.05,
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

# Student-facing goal per target key (Plan 07): the single thing this turn may
# learn, in vocabulary a 15-year-old parses — carried on the planner directive
# so the writer aims at it instead of an abstract dimension name.
COLLECT_HINTS: dict[str, str] = {
    "topics": "what they keep spending free time on",
    "work_mode": "how they like to do the work",
    "motivation": "what makes the effort worth it to them",
    "execution": "how they handle the hard or boring parts",
    "execution:persistence": "what keeps them going after it stops being fun",
    "execution:ambiguity_tolerance": "how they handle tasks with no clear instructions",
    "execution:outreach_willingness": "whether they would show the work to people",
    "execution:public_visibility": "whether they would let others see or use it",
    "constraints": "what has to be true for the project to fit their life",
    "constraints:geo": "where they are (city or region)",
    "capability": "what they are already good at or get asked to help with",
    "assets": "what tools, time, or support they already have",
    "contradiction": "which of two things fits them better",
    "profile_validation": "whether the summary sounds right",
    "conversation_repair": "what they actually meant",
    "social_intro": "a simple hello",
}


def collect_hint_for(key: str) -> str:
    """Student-vocabulary goal for a target key, falling back to its family."""
    if key in COLLECT_HINTS:
        return COLLECT_HINTS[key]
    family = key.split(":", 1)[0]
    return COLLECT_HINTS.get(family, "what would help them next")


@dataclass(frozen=True)
class PlannerDecision:
    target: Target
    action: PlannerAction
    phase: DiscoveryPhase
    reason: str
    avoid_topics: tuple[str, ...] = ()
    # Plan 07 directive fields: the writer consumes these verbatim; the planner
    # owns every presentation-level decision (ack mode, closure beat, bridge
    # seed, remaining probe budget) so the model never improvises structure.
    closure: bool = False
    acknowledgment: str = "auto"  # none | brief | repair | validate | auto
    collect: str | None = None
    bridge_hint: str | None = None
    probes_left_on_key: int = 0


def is_topic_rejection(text: str) -> bool:
    normalized = " ".join((text or "").lower().split())
    return any(
        cue in normalized
        for cue in (
            "talk about something else",
            "change the subject",
            "different topic",
            "move on",
            "stop asking about",
            "don't want to talk about",
            "dont want to talk about",
        )
    )


def is_frustration(text: str) -> bool:
    normalized = " ".join((text or "").lower().split())
    return is_topic_rejection(normalized) or any(
        cue in normalized
        for cue in (
            "why are you asking",
            "why do you keep asking",
            "this is annoying",
            "are you analyzing me",
            "personality test",
        )
    )


def _finalize(
    decision: PlannerDecision,
    *,
    breadth_complete: bool,
    last_turn_accepted: bool,
    last_target_key: str | None,
) -> PlannerDecision:
    """Attach the writer-facing directive fields to a planner decision."""
    ack = "auto"
    if decision.action == PlannerAction.CLARIFY:
        ack = "validate"
    elif decision.reason in {"topic_rejected", "friction_detected"}:
        ack = "repair"
    elif decision.closure or decision.action in {
        PlannerAction.BRIDGE,
        PlannerAction.GATE,
    }:
        ack = "brief"
    needs_bridge = decision.action != PlannerAction.FOLLOW_UP and bool(last_target_key)
    depth_budget = ABSOLUTE_MAX_TOPIC_DEPTH + 1
    if not breadth_complete:
        depth_budget = ABSOLUTE_MAX_TOPIC_DEPTH if last_turn_accepted else DEFAULT_MAX_TOPIC_DEPTH
    return PlannerDecision(
        target=decision.target,
        action=decision.action,
        phase=decision.phase,
        reason=decision.reason,
        avoid_topics=decision.avoid_topics,
        closure=decision.closure,
        acknowledgment=ack,
        collect=collect_hint_for(decision.target.key),
        bridge_hint=collect_hint_for(decision.target.key) if needs_bridge else None,
        probes_left_on_key=max(0, depth_budget - decision.target.asked_count),
    )


def _same_contradiction_dimension(candidate_key: str, last_target_key: str) -> bool:
    """True when a contradiction's dimension is the topic just asked."""
    if candidate_key == last_target_key:
        return True
    return candidate_key == last_target_key.split(":", 1)[0]


def _defer_same_dimension_contradiction(
    pool: list[Target],
    *,
    last_target_key: str | None,
    raised_keys: tuple[str, ...],
) -> list[Target]:
    """Drop a contradiction on the dimension just asked, when alternatives exist.

    The student explicitly raising that conflict (support and oppose on the
    same dimension this turn) keeps the clarify candidate in the pool.
    """
    if not last_target_key:
        return pool
    raised = set(raised_keys)

    def deferred(candidate: Target) -> bool:
        if candidate.kind != "contradiction":
            return False
        if not _same_contradiction_dimension(candidate.key, last_target_key):
            return False
        family = candidate.key.split(":", 1)[0]
        return candidate.key not in raised and family not in raised

    kept = [candidate for candidate in pool if not deferred(candidate)]
    if kept and len(kept) < len(pool):
        return kept
    return pool


def plan_next(
    candidates: list[Target],
    *,
    last_target_key: str | None,
    student_text: str,
    breadth_complete: bool = False,
    blocked_topics: tuple[str, ...] = (),
    last_target_kind: str | None = None,
    last_turn_accepted: bool = False,
    student_raised_contradiction_keys: tuple[str, ...] = (),
) -> PlannerDecision | None:
    """Choose *what* happens next with hard breadth and saturation controls.

    Candidate ``key`` is the persisted topic identifier. A rejected topic is
    excluded immediately; the caller can persist that boundary in its trace.
    During breadth, an exhausted branch can never beat a major unasked area —
    unless the last ask on the current branch still yielded evidence, in which
    case the budget extends to ABSOLUTE_MAX_TOPIC_DEPTH (one more probe) and
    the stay is traced as ``topic_yielding_extended``.

    ``last_target_kind`` is the previous question's intent (callers still pass
    it). Deferral keys off the dimension, not that intent: a contradiction on
    the dimension just asked waits one turn unless this message raised it.
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

    # A contradiction on the dimension just asked waits one turn (Plan 07),
    # unless the student put that conflict on the table themselves. Other
    # contradictions stay in the pool and compete on value. The clarify-attempt
    # lifecycle (max 2 → dismissed) is unchanged.
    pool = _defer_same_dimension_contradiction(
        pool,
        last_target_key=last_target_key,
        raised_keys=student_raised_contradiction_keys,
    )

    major_uncovered = [c for c in pool if c.asked_count == 0]
    current = [c for c in pool if c.key == last_target_key]
    current_depth = max((c.asked_count for c in current), default=0)

    def decided(decision: PlannerDecision) -> PlannerDecision:
        return _finalize(
            decision,
            breadth_complete=breadth_complete,
            last_turn_accepted=last_turn_accepted,
            last_target_key=last_target_key,
        )

    if rejected or frustrated:
        target = select_next(
            major_uncovered or [c for c in pool if c.key != last_target_key] or pool
        )
        return decided(
            PlannerDecision(
                target=target,
                action=PlannerAction.SWITCH,
                phase=DiscoveryPhase.BREADTH,
                reason="topic_rejected" if rejected else "friction_detected",
                avoid_topics=tuple(sorted(blocked)),
            )
        )

    if classify_reply(student_text) == ReplySignal.INSUFFICIENT and major_uncovered:
        target = select_next(
            [c for c in major_uncovered if c.key != last_target_key] or major_uncovered
        )
        return decided(
            PlannerDecision(
                target,
                PlannerAction.SWITCH,
                DiscoveryPhase.BREADTH,
                "branch_yield_collapsed",
                closure=True,
            )
        )

    if last_target_key and current_depth >= ABSOLUTE_MAX_TOPIC_DEPTH:
        switch_pool = [c for c in pool if c.key != last_target_key and not is_repetition_blocked(c)]
        if switch_pool:
            target = select_next(switch_pool)
            return decided(
                PlannerDecision(
                    target,
                    PlannerAction.SWITCH,
                    DiscoveryPhase.BREADTH if not breadth_complete else DiscoveryPhase.VERIFY,
                    "follow_up_exhausted",
                    closure=True,
                )
            )

    # Breadth ceiling. A yielding answer raises it to the absolute max; the
    # branch below is what actually stays, so a fresh dimension cannot outscore
    # the extra probe.
    effective_budget = ABSOLUTE_MAX_TOPIC_DEPTH if last_turn_accepted else DEFAULT_MAX_TOPIC_DEPTH
    if not breadth_complete and major_uncovered and current_depth >= effective_budget:
        target = select_next(
            [c for c in major_uncovered if c.key != last_target_key] or major_uncovered
        )
        return decided(
            PlannerDecision(
                target,
                PlannerAction.SWITCH,
                DiscoveryPhase.BREADTH,
                "topic_budget_reached",
                closure=True,
            )
        )

    # Semantic stay: the budget would have switched, but this answer still
    # yielded evidence, so take one more probe on the same topic. Scoring would
    # otherwise prefer the unasked dimension and undo the extension.
    if (
        not breadth_complete
        and last_turn_accepted
        and major_uncovered
        and current
        and DEFAULT_MAX_TOPIC_DEPTH <= current_depth < ABSOLUTE_MAX_TOPIC_DEPTH
    ):
        staying = [c for c in current if not is_repetition_blocked(c)]
        if staying:
            target = select_next(staying) or staying[0]
            # A conflict the student just raised still clarifies; the extra
            # probe name is only for staying on the same non-conflict ask.
            if target.kind == "contradiction":
                action, reason = PlannerAction.CLARIFY, "resolve_contradiction"
            else:
                action, reason = PlannerAction.FOLLOW_UP, "topic_yielding_extended"
            return decided(
                PlannerDecision(
                    target,
                    action,
                    DiscoveryPhase.BREADTH,
                    reason,
                )
            )

    # A fourth ask is invalid before breadth completes, regardless of score.
    eligible = [
        c for c in pool if breadth_complete or c.asked_count < ABSOLUTE_MAX_TOPIC_DEPTH
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
        "constraints",
        "constraints:geo",
        "execution:outreach_willingness",
        "execution:public_visibility",
    }:
        action, reason = PlannerAction.GATE, "hard_feasibility"
    return decided(
        PlannerDecision(
            target,
            action,
            DiscoveryPhase.VERIFY if breadth_complete else DiscoveryPhase.BREADTH,
            reason,
            tuple(sorted(blocked)),
        )
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
    # CAT item-exposure control (Plan 01 W1.1): how many consecutive turns this
    # target's dimension was just asked. Persisted per session in
    # core.sessions.dim_ask_counts; 0 when the dimension was not the previous
    # commit or the session has no ledger yet.
    consecutive_count: int = 0


# Dimensions at this many consecutive asks become ineligible regardless of
# decision value. Repair/correction kinds are exempt (see
# _EXPOSURE_EXEMPT_KINDS); a fresh dimension always wins over a capped one.
EXPOSURE_CONSECUTIVE_CAP = 2

# Kinds that never accrue or bind to exposure: repairs answer an explicit
# student correction, introductions are one-shot conversation contracts.
EXEMPT_FROM_EXPOSURE_CAP = frozenset({"contradiction", "conversation_repair", "social_intro"})


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


def repetition_block_reason(target: Target) -> str | None:
    """Classify why a target must not be selected again this turn.

    ``exposure_cap`` — the dimension was asked on the last two committed turns
    (consecutive_count >= 2), regardless of decision value; or the cumulative
    hard-stop rules below fired. Contradictions, repairs, and social
    introductions never bind.
    """
    if target.kind in {"contradiction", "conversation_repair", "social_intro"}:
        return None
    if target.consecutive_count >= 2:
        return "exposure_cap"
    # Absolute per-dimension ask cap: an alternated pair of dims can otherwise
    # cycle forever (consecutive_count never reaches 2), starving every other
    # probe and blocking the review checkpoint (Plan 01 W1.4, sim_luz).
    if target.asked_count >= ABSOLUTE_MAX_TOPIC_DEPTH + 1:
        return "repetition_hard_stop"
    if target.asked_count >= 2 and target.coverage_status in {"supported", "established"}:
        return "repetition_hard_stop"
    if (
        target.asked_count >= 2
        and target.coverage_status == "provisional"
        and target.key in HIGH_REPEAT_KEYS
    ):
        return "repetition_hard_stop"
    if target.asked_count >= 3 and target.key in HIGH_REPEAT_KEYS:
        return "repetition_hard_stop"
    return None


def is_repetition_blocked(target: Target) -> bool:
    """Hard-stop re-asking anchors that stop yielding new evidence."""
    return repetition_block_reason(target) is not None


def should_force_review_checkpoint(
    *,
    candidate_count: int,
    has_social_target: bool,
    reviewed: bool,
    contradictions: int,
) -> bool:
    """Review once all useful probes are exhausted; never synthesize another probe."""
    return candidate_count == 0 and not has_social_target and not reviewed and contradictions == 0


def question_value(target: Target) -> float:
    """Auditable V1 proxy for expected reduction in project-decision uncertainty."""
    value = target.value
    positive = (
        0.30 * value.project_discrimination
        + 0.25 * max(value.uncertainty_reduction, target.information_gain)
        + 0.15 * value.evidence_weakness
        + 0.15 * value.contradiction_resolution
        + 0.10 * max(value.conversational_relevance, target.continuity)
        + 0.05 * value.novelty
    )
    penalties = (
        value.repetition_penalty
        + value.leading_penalty
        + value.sensitivity_penalty
        + value.fatigue_penalty
        + target.asked_count * 0.35
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
    # Contradictions compete on decision value (their contradiction_resolution
    # component + unknown-state uncertainty normally wins) instead of replacing
    # the pool wholesale — an open conflict earns the next ask, not a hijack of
    # the whole agenda (Plan 07). Repairs still preempt everything.
    pool = repair or candidates
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
    exhausted_keys: tuple[str, ...] = (),
) -> tuple[bool, str | None]:
    """Full-inventory review latch with a fatigue escape.

    Review normally requires the full required-dimension inventory
    (``coverage_established >= PROFILE_REVIEW_ESTABLISHED``). A student must not
    be trapped in an interview because a repeatedly explored preference remains
    provisional, so the fatigue path still admits review at 0.4+ coverage once a
    core anchor has been probed twice without resolving; it presents that field
    as tentative and invites correction rather than promoting it to supported.
    """
    if contradictions > 0:
        return False, None
    if location_ready is False:
        return False, None
    exhausted = set(exhausted_keys)
    if dimension_statuses.get("topics") != "supported":
        return False, None
    for key in ("work_mode", "motivation"):
        status = dimension_statuses.get(key)
        if status != "supported" and not (status == "provisional" and key in exhausted):
            return False, None
    if dimension_statuses.get("execution") not in {"supported", "provisional"}:
        return False, None
    secondary_ok = dimension_statuses.get("capability") in {
        "supported",
        "provisional",
    } or dimension_statuses.get("assets") in {"supported", "provisional"}
    if not secondary_ok:
        return False, None
    if coverage_established >= PROFILE_REVIEW_ESTABLISHED:
        return True, "full_inventory_review"
    if {"work_mode", "motivation"} & exhausted and coverage_established >= 0.4:
        return True, "fatigue_bounded_review"
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
    current_stage: str | None = None,
    **_ignored: Any,
) -> str:
    """Derive stage from supported coverage and open true contradictions.

    Legacy callers may pass ``coverage`` (treated as supported/established).
    Contested dims contribute only to ``coverage_touched``.

    ``project_matching`` requires reviewed + location_ready (when provided).

    Stages never regress: when ``current_stage`` is provided, a freshly derived
    stage ranking below it is clamped up to ``current_stage`` (``complete``
    stays terminal). The only sanctioned regression is the caller-side
    review-checkpoint override in turn_processor, applied and traced after
    this function returns.
    """
    stage = _derive_stage_fresh(
        contradictions=contradictions,
        reviewed=reviewed,
        projects_ready=projects_ready,
        coverage_established=coverage_established,
        coverage_touched=coverage_touched,
        coverage=coverage,
        location_ready=location_ready,
        dimension_statuses=dimension_statuses,
        **_ignored,
    )
    if current_stage is None:
        return stage
    current_rank = STAGE_RANK.get(current_stage)
    if current_rank is not None and STAGE_RANK[stage] < current_rank:
        return current_stage
    return stage


def _derive_stage_fresh(
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
    """Derive the stage from inputs alone, before the monotonicity clamp."""
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
        exhausted_keys=tuple(_ignored.get("exhausted_keys") or ()),
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
        if score_i > best_score or (score_i == best_score and evidence > best_evidence):
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


def contradiction_fallback(dimension_key: str, value_a: str | None, value_b: str | None) -> str:
    """Seeded contradiction wording that names the concrete options.

    Value keys resolve through the elicitation option banks so raw snake_case
    never reaches the student (Plan 07 W7.3).
    """
    from app.services.elicitation_policy import value_label_for

    label = dimension_key.replace("_", " ")
    a = value_label_for(dimension_key, value_a)
    b = value_label_for(dimension_key, value_b)
    if a and b:
        return (
            f"Sounds like {label} could go either way — {a}, or {b}. "
            "Which fits you better, or is it both depending on the situation?"
        )
    if a:
        return f"For {label}, is {a} still the thing that fits best?"
    return f"For {label}, which of these fits you better right now?"


_REQUIRED_FALLBACKS = {
    "topics": (
        "Hey — good to meet you. When you've had free time lately, what have you "
        "actually been spending it on?"
    ),
    "work_mode": ("Thinking about what you just described, which part do you enjoy doing most?"),
    "motivation": ("What usually makes something feel worth the time you put into it?"),
    "execution": (
        "What's something difficult you kept working at after it became frustrating or boring?"
    ),
    "execution:persistence": (
        "What's something difficult you kept working at after it became frustrating or boring?"
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
    "constraints:geo": ("Where are you based (city or region), or is remote fine too?"),
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
            return "Nice — what games have you been playing lately?"
        return f"Nice — what do you enjoy most about {label}?"
    return "Nice — what do you enjoy most about it?"


def social_intro_target(last_target_key: str | None, student_text: str | None) -> Target | None:
    """Return the next low-pressure introduction turn, if one is due.

    Introductions are deliberately outside the assessment dimensions. This makes
    the first exchange feel like meeting a person rather than starting a form.
    """
    if last_target_key is None:
        normalized = " ".join((student_text or "").strip().split())
        greeting_only = classify_reply(normalized) == ReplySignal.GREETING
        opening = (
            "Hey — good to meet you. I’ll help you find a course project that fits "
            "you. What have you been into lately, in or out of school?"
            if greeting_only
            else "Good to meet you. I’ll help you find a course project that fits "
            "what you enjoy and what is realistic for you. What part of what you "
            "just mentioned do you enjoy most?"
        )
        return Target(
            "social_intro",
            "conversation_contract",
            opening,
            continuity=1.0,
        )
    return None


def required_fallback(key: str) -> str:
    """Teen-friendly seeded ask for a required / discovery target key."""
    if key in _REQUIRED_FALLBACKS:
        return _REQUIRED_FALLBACKS[key]
    label = key.replace("_", " ").replace(":", " ")
    return f"What should I know about your {label}?"
