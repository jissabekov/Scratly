"""Sole normal turn path; state and its trace commit or roll back together."""

from __future__ import annotations

from typing import Any

from app.contracts import (
    PrimaryIntent,
    ProfileReviewOutput,
    QuestionTopic,
    StudentAnswerMode,
    ValidatedEvidence,
)
from app.services.decision_trace import DecisionTraceRecorder
from app.services.elicitation_policy import (
    build_elicitation_spec,
    elicitation_dimension_family,
    elicitation_target,
    should_offer_options,
)
from app.services.location_policy import extract_geo_from_profile, infer_geo_from_text
from app.services.memory_compactor import MemoryCompactor
from app.services.opportunity_matcher import rank_opportunities
from app.services.project_composer import ProjectComposer
from app.services.question_policy import (
    ReplySignal,
    Target,
    classify_reply,
    derive_stage,
    interest_depth_fallback,
    is_repetition_blocked,
    plan_next,
    question_value,
    select_next,
    social_intro_target,
    is_topic_rejection,
)
from app.services.question_quality import apply_question_quality_gate
from app.services.student_answerer import (
    StudentAnswerer,
    answer_scope_gate,
    is_framing_pushback,
    validate_answer_citations,
)
from app.services.thin_answer import evaluate_thin_answer
from app.services.turn_intent_classifier import TurnIntentClassifier
from app.services.web_research_client import WebResearchClient
from uuid import UUID

_FALLBACK_TARGET = Target(
    "profile_validation",
    "profile",
    "Does this description of your preferences feel accurate?",
)


async def process_student_turn(repo, extractor, writer, context_builder, session_id, request):
    """Sole normal turn path; state and its trace commit or roll back together."""
    existing = await repo.completed_turn(session_id, request.idempotency_key)
    if existing:
        return existing

    async with repo.transaction() as tx:
        turn, message = await tx.create_turn_and_student_message(
            session_id, request.idempotency_key, request.text
        )
        llm = getattr(extractor, "llm", None) or getattr(writer, "llm", None)
        if llm is not None and hasattr(llm, "set_turn_context"):
            llm.set_turn_context(session_id, turn.id)

            async def _audit_writer(**kwargs):
                return await tx.record_llm_run(**kwargs)

            llm.audit = _audit_writer

        trace = DecisionTraceRecorder(tx, session_id, turn.id)
        await trace.record(
            "turn_started",
            "turn_processor",
            "v2",
            "Accepted a new idempotent student turn.",
            "new_idempotency_key",
            entity_refs={"student_message_ids": [str(message.id)]},
        )

        counters = await tx.session_counters()
        last_q = await tx.last_question_target()
        public_profile = await tx.public_profile()

        # --- Intent classification ---
        classifier = TurnIntentClassifier(llm)
        intent = await classifier.classify(
            {
                "student_message": {
                    "id": str(message.id),
                    "content": request.text,
                },
                "last_target_key": (last_q or {}).get("target_key"),
                "stage": (await tx.stage_inputs()).get("reviewed"),
            }
        )
        # Hard safety: heuristic out-of-scope / clear questions override a soft LLM miss.
        from app.services.turn_intent_classifier import heuristic_classify

        heuristic = heuristic_classify(request.text)
        if heuristic.question_topic == QuestionTopic.OUT_OF_SCOPE:
            intent = heuristic
        elif (
            heuristic.primary_intent == PrimaryIntent.STUDENT_QUESTION
            and heuristic.question_topic == QuestionTopic.PROCESS
            and intent.question_topic == QuestionTopic.PROJECT
            and heuristic.confidence >= 0.65
        ):
            # "why are you asking about X project?" is process, not project-matching.
            intent = heuristic
        elif (
            heuristic.primary_intent == PrimaryIntent.STUDENT_QUESTION
            and heuristic.question_topic
            in {QuestionTopic.PROCESS, QuestionTopic.PROFILE, QuestionTopic.PROJECT}
            and intent.primary_intent == PrimaryIntent.ASSESSMENT_CONTRIBUTION
            and heuristic.confidence >= 0.65
        ):
            intent = heuristic
        await trace.record(
            "turn_intent_classified",
            "turn_intent_classifier",
            "v1",
            f"Classified intent {intent.primary_intent.value}.",
            f"intent_{intent.primary_intent.value}",
            outputs={
                "primary_intent": intent.primary_intent.value,
                "question_topic": intent.question_topic.value,
                "confidence": intent.confidence,
            },
        )

        assistant_prefix: str | None = None
        message_kind = "assessment_question"
        elicitation_spec = None
        skip_evidence = intent.primary_intent == PrimaryIntent.STUDENT_QUESTION

        # --- Student question branch ---
        if intent.primary_intent in {
            PrimaryIntent.STUDENT_QUESTION,
            PrimaryIntent.MIXED,
        }:
            forced = answer_scope_gate(
                intent,
                consecutive_student_questions=int(
                    counters.get("consecutive_student_questions") or 0
                ),
            )
            evidence_summaries = await tx.accepted_evidence_summaries()
            allowed_ids = {UUID(e["id"]) for e in evidence_summaries}
            allowed_fields = {
                d.get("key")
                for d in (public_profile.get("dimensions") or [])
                if d.get("key")
            }
            if forced is not None:
                answer = forced
            else:
                answerer = StudentAnswerer(llm)
                answer = await answerer.answer(
                    {
                        "intent": intent.model_dump(mode="json"),
                        "student_message": {"content": request.text},
                        "student_text": request.text,
                        "public_profile_summary": public_profile,
                        "accepted_evidence": evidence_summaries,
                        "last_target_key": (last_q or {}).get("target_key"),
                        "last_intent_key": (last_q or {}).get("intent_key"),
                    }
                )
                answer = validate_answer_citations(
                    answer,
                    allowed_evidence_ids=allowed_ids,
                    allowed_profile_fields=allowed_fields,
                )

            if answer.mode == StudentAnswerMode.REFUSE:
                await trace.record(
                    "student_answer_refused",
                    "answer_scope_gate",
                    "v1",
                    "Refused out-of-scope or capped student question.",
                    answer.refusal_reason_code or "refused",
                    outputs={
                        "refusal_reason_code": answer.refusal_reason_code,
                        "topic": intent.question_topic.value,
                    },
                )
                assistant_prefix = answer.text
                message_kind = "refusal"
            else:
                await trace.record(
                    "student_answer_written",
                    "student_answerer",
                    "v1",
                    "Answered in-scope process/profile/project question.",
                    f"topic_{intent.question_topic.value}",
                    outputs={
                        "topic": intent.question_topic.value,
                        "cited_profile_field_count": len(answer.cited_profile_fields),
                        "cited_evidence_count": len(answer.cited_evidence_ids),
                    },
                    entity_refs={
                        "cited_evidence_ids": [str(i) for i in answer.cited_evidence_ids],
                        "cited_profile_fields": list(answer.cited_profile_fields),
                    },
                )
                assistant_prefix = answer.text
                message_kind = "student_answer"

            await tx.update_session_counters(
                consecutive_student_questions=int(
                    counters.get("consecutive_student_questions") or 0
                )
                + 1
            )
        else:
            await tx.update_session_counters(consecutive_student_questions=0)

        pending_dim = await tx.pending_contradiction_target()
        validated: list[ValidatedEvidence] = []
        accepted_count = 0
        transition: dict = {
            "version": None,
            "contradiction_count": 0,
            "resolved_this_turn": [],
            "active_conflict_dimensions": [],
        }

        if skip_evidence:
            await trace.record(
                "evidence_extraction_skipped",
                "turn_processor",
                "v2",
                "Skipped evidence extraction for pure student question.",
                "skipped_no_assessment_content",
            )
        else:
            packet = await extractor.propose(
                context_builder.extractor(
                    message, await tx.allowed_messages(session_id), await tx.taxonomy()
                )
            )
            allowed_messages = await tx.allowed_messages(session_id)
            owned_message_ids = {m.id for m in allowed_messages}
            pre_filter_dropped = 0
            if packet.items:
                filtered_items = []
                for item in packet.items:
                    if any(mid not in owned_message_ids for mid in item.source_message_ids):
                        pre_filter_dropped += 1
                        continue
                    filtered_items.append(item)
                packet = packet.model_copy(update={"items": filtered_items})
            extract_run_id = getattr(llm, "last_llm_run_id", None) if llm else None
            await trace.record(
                "evidence_proposed",
                "evidence_extractor",
                "v2",
                f"Extractor proposed {len(packet.items)} evidence item(s).",
                "structured_extraction_completed",
                outputs={
                    "proposed_count": len(packet.items),
                    "pre_filter_dropped": pre_filter_dropped,
                },
                llm_run_id=extract_run_id,
            )

            validated = await tx.validate_and_record_evidence(packet.items, message)
            accepted_count = sum(item.accepted for item in validated)
            if not skip_evidence and not await tx.location_established():
                geo_key = infer_geo_from_text(request.text)
                if geo_key and await tx.record_geo_from_text(message, geo_key):
                    await tx.apply_evidence_reduce_contradictions_snapshot([])
                    accepted_count += 1
                    await trace.record(
                        "geo_inferred_from_text",
                        "location_policy",
                        "v1",
                        f"Inferred geo constraint {geo_key} from student text.",
                        "geo_text_fallback",
                        outputs={"geo_key": geo_key},
                    )
            rejected_reasons: dict[str, int] = {}
            for item in validated:
                if not item.accepted:
                    reason = item.rejection_reason or "unspecified"
                    rejected_reasons[reason] = rejected_reasons.get(reason, 0) + 1
            await trace.record(
                "evidence_validated",
                "grounding_validator",
                "v2",
                f"Accepted {accepted_count} of {len(validated)} proposed evidence item(s).",
                "grounding_checks_applied",
                inputs={"proposed_count": len(validated)},
                outputs={
                    "accepted_count": accepted_count,
                    "rejected_count": len(validated) - accepted_count,
                    "rejection_reason_counts": rejected_reasons,
                    "evidence_yield": round(
                        accepted_count / max(len(validated), 1), 4
                    ),
                },
            )

            prior_open = set(await tx.open_contradiction_dimensions())
            transition = await tx.apply_evidence_reduce_contradictions_snapshot(
                validated
            )
            await trace.record(
                "profile_reduced",
                "profile_reducer",
                "v1",
                "Recomputed profile solely from accepted grounded evidence.",
                "accepted_evidence_reduced",
                inputs={"accepted_evidence_count": accepted_count},
                entity_refs=transition.get("entity_refs", {})
                if isinstance(transition, dict)
                else {},
            )

            for closed in transition.get("resolved_this_turn") or []:
                await trace.record(
                    "contradiction_resolved",
                    "contradiction_engine",
                    "v2",
                    f"Closed non-conflict on {closed.get('dimension_key')}.",
                    closed.get("resolution") or "dismissed_not_conflict",
                    outputs=closed,
                    entity_refs={
                        "contradiction_ids": [closed["contradiction_id"]],
                        "dimension_keys": [closed["dimension_key"]],
                    },
                )

            resolve_dims: list[str] = []
            if pending_dim:
                resolve_dims.append(pending_dim)
            for dim in transition.get("active_conflict_dimensions") or []:
                if dim in resolve_dims:
                    continue
                has_new = any(
                    item.accepted and item.dimension_key == dim and item.evidence_id
                    for item in validated
                )
                if not has_new:
                    continue
                if dim in prior_open or _explicit_preference(validated, dim):
                    resolve_dims.append(dim)

            for dim in resolve_dims:
                resolution = await tx.attempt_resolve_contradiction(dim, validated)
                if resolution and resolution.get("resolution"):
                    await trace.record(
                        "contradiction_resolved",
                        "contradiction_engine",
                        "v2",
                        f"Resolved contradiction on {dim}.",
                        resolution["resolution"],
                        outputs=resolution,
                        entity_refs={
                            "contradiction_ids": [resolution["contradiction_id"]],
                            "dimension_keys": [dim],
                            "evidence_ids": (
                                [resolution["resolved_by_evidence_id"]]
                                if resolution.get("resolved_by_evidence_id")
                                else []
                            ),
                        },
                    )

        contradiction_count = await tx.open_contradiction_count()
        if isinstance(transition, dict):
            transition["contradiction_count"] = contradiction_count
            if contradiction_count == 0:
                transition["active_conflict_dimensions"] = []

        await trace.record(
            "contradiction_evaluated",
            "contradiction_engine",
            "v2",
            f"Detected or retained {contradiction_count} open contradiction(s).",
            "conflicts_kept_explicit_without_averaging",
            outputs={
                "open_contradiction_count": contradiction_count,
                "engine_version": (
                    transition.get("engine_version")
                    if isinstance(transition, dict)
                    else "v2"
                ),
                "active_conflict_dimensions": (
                    transition.get("active_conflict_dimensions", [])
                    if isinstance(transition, dict)
                    else []
                ),
            },
        )

        # Refresh profile after possible reduce
        public_profile = await tx.public_profile()
        stage_inputs = await tx.stage_inputs()
        await trace.record(
            "location_readiness_checked",
            "location_policy",
            "v1",
            "Checked whether geo constraints are established.",
            "location_ready"
            if stage_inputs.get("location_ready")
            else "location_missing",
            outputs={"location_ready": bool(stage_inputs.get("location_ready"))},
        )

        candidates = await tx.question_candidates()
        blocked_candidates: list[dict[str, Any]] = []
        filtered_candidates: list[Target] = []
        for candidate in candidates:
            if is_repetition_blocked(candidate):
                blocked_candidates.append(
                    {
                        "blocked_key": candidate.key,
                        "asked_count": candidate.asked_count,
                        "status": candidate.coverage_status,
                        "kind": candidate.kind,
                    }
                )
                continue
            filtered_candidates.append(candidate)
        if blocked_candidates:
            replacement = select_next(filtered_candidates or candidates)
            await trace.record(
                "question_target_blocked",
                "question_policy",
                "v1",
                f"Blocked {len(blocked_candidates)} over-asked supported target(s).",
                "repetition_hard_stop",
                outputs={
                    "blocked": blocked_candidates,
                    "chosen_instead": (
                        {"kind": replacement.kind, "key": replacement.key}
                        if replacement
                        else None
                    ),
                },
            )
        candidates = filtered_candidates or candidates

        # Adaptive dialogue repair: corrections and greetings inject high-continuity
        # candidates so we acknowledge before probing (these never become evidence).
        reply_signal = classify_reply(request.text)
        if reply_signal == ReplySignal.CORRECTION:
            candidates.append(
                Target(
                    "conversation_repair",
                    "repair_rejected_assumption",
                    "You’re right — I made an assumption there. What part of what you "
                    "mentioned would you be up for telling me a little more about?",
                    information_gain=1.0,
                    continuity=1.0,
                )
            )
        elif reply_signal == ReplySignal.GREETING and not candidates:
            candidates.append(
                Target(
                    "behavioral_anchor",
                    "low_pressure_welcome",
                    "Hey — I’ll help you notice what kinds of activities and projects "
                    "genuinely fit. What have you enjoyed spending time on lately, even "
                    "if it seems ordinary?",
                    information_gain=1.0,
                    continuity=1.0,
                )
            )
        await trace.record(
            "reply_signal_classified",
            "question_policy",
            "v1",
            f"Classified reply signal {reply_signal.value}.",
            f"reply_{reply_signal.value}",
            outputs={"reply_signal": reply_signal.value},
        )

        social_target = social_intro_target(
            (last_q or {}).get("target_key"), request.text
        )
        planner_decision = None
        if social_target is None:
            # The policy owns subject selection. The writer receives this decision
            # later and is never allowed to continue a topic on conversational instinct.
            blocked_topics: tuple[str, ...] = ()
            load_blocked = getattr(tx, "rejected_topics", None)
            if load_blocked:
                blocked_topics = tuple(await load_blocked())
            if is_topic_rejection(request.text) and (last_q or {}).get("target_key"):
                block_topic = getattr(tx, "reject_topic", None)
                if block_topic:
                    await block_topic((last_q or {})["target_key"])
                blocked_topics = tuple(
                    sorted(set(blocked_topics) | {(last_q or {})["target_key"]})
                )
            planner_decision = plan_next(
                candidates,
                last_target_key=(last_q or {}).get("target_key"),
                student_text=request.text,
                breadth_complete=bool(stage_inputs.get("coverage_touched", 0) >= 0.8),
                blocked_topics=blocked_topics,
            )
        target = (
            social_target
            or (planner_decision.target if planner_decision else None)
            or _FALLBACK_TARGET
        )
        if planner_decision:
            if planner_decision.reason == "follow_up_exhausted":
                await trace.record(
                    "question_target_blocked",
                    "question_policy",
                    "v1",
                    f"Follow-up exhausted on {planner_decision.target.key}; switching.",
                    "follow_up_exhausted",
                    outputs={
                        "blocked_key": (last_q or {}).get("target_key"),
                        "chosen_instead": {
                            "kind": target.kind,
                            "key": target.key,
                        },
                    },
                )
            await trace.record(
                "question_target_selected",
                "conversation_planner",
                "v1",
                f"Planner chose {planner_decision.action.value} toward {target.key}.",
                planner_decision.reason,
                outputs={
                    "target_kind": target.kind,
                    "target_key": target.key,
                    "planner_action": planner_decision.action.value,
                    "action": planner_decision.action.value,
                    "phase": planner_decision.phase.value,
                    "asked_count": target.asked_count,
                    "candidate_count": len(candidates),
                    "decision_value": question_value(target),
                    "avoid_topics": list(planner_decision.avoid_topics),
                },
            )

        # Framing pushback ("I just play — why a project?") → stay on interest depth.
        if is_framing_pushback(request.text) and not (
            planner_decision
            and planner_decision.reason in {"friction_detected", "topic_rejected"}
        ):
            topics_status = next(
                (
                    d.get("status")
                    for d in (public_profile.get("dimensions") or [])
                    if isinstance(d, dict) and d.get("key") == "topics"
                ),
                "unknown",
            )
            if topics_status != "supported":
                topic_label = None
                for interest in public_profile.get("interests") or []:
                    if isinstance(interest, dict) and interest.get("topic"):
                        topic_label = str(interest["topic"])
                        break
                if not topic_label:
                    for dim in public_profile.get("dimensions") or []:
                        if (
                            isinstance(dim, dict)
                            and dim.get("key") == "topics"
                            and dim.get("value")
                        ):
                            topic_label = str(dim["value"])
                            break
                target = Target(
                    "project_critical_unknown",
                    "topics",
                    interest_depth_fallback(topic_label),
                )
                await trace.record(
                    "question_target_selected",
                    "question_policy",
                    "v1",
                    "Retargeted to interest depth after framing pushback.",
                    "interest_depth_after_pushback",
                    outputs={"topic": topic_label, "topics_status": topics_status},
                )

        # --- Thin answer → elicitation ---
        # Prefer last_question presence as a cheap prior-ask signal.
        prior_assistant_questions = 1 if last_q else 0
        thin = evaluate_thin_answer(
            request.text,
            accepted_evidence_count=accepted_count,
            primary_intent=intent.primary_intent.value,
            pending_contradiction=bool(pending_dim),
            prior_assistant_questions=prior_assistant_questions,
        )
        await trace.record(
            "answer_thinness_evaluated",
            "thin_answer",
            "v1",
            f"Thin answer={thin.is_thin}.",
            "thin" if thin.is_thin else "substantive",
            outputs={
                "is_thin": thin.is_thin,
                "reason_codes": thin.reason_codes,
            },
        )

        counters = await tx.session_counters()
        if thin.is_thin and not skip_evidence:
            pending_key = counters.get("elicitation_target_key")
            if pending_key:
                elicit_key = pending_key
                if elicit_key == "constraints:geo":
                    elicit_key = "constraints"
                attempts = int(counters.get("elicitation_attempts_for_target") or 0) + 1
            else:
                elicit_key = elicitation_dimension_family(target.key)
                if target.key == "constraints:geo":
                    elicit_key = "constraints"
                if target.kind == "profile_validation":
                    elicit_key = "profile"
                attempts = 1
            can_recover = target.kind in {
                "required_hard_variable",
                "project_critical_unknown",
                "provisional_dimension",
                "project_discrimination",
                "contradiction",
                "elicitation",
            } or (
                target.kind == "behavioral_anchor" and prior_assistant_questions >= 1
            )
            if not can_recover:
                await trace.record(
                    "elicitation_skipped_not_recoverable",
                    "elicitation_policy",
                    "v1",
                    f"Thin answer on non-recoverable target {target.kind}:{target.key}.",
                    "not_recoverable",
                    outputs={"dimension_key": elicit_key, "attempt": attempts},
                )
            elif can_recover and attempts == 1:
                await tx.update_session_counters(
                    elicitation_attempts_for_target=attempts,
                    elicitation_target_key=elicit_key,
                )
                await trace.record(
                    "elicitation_rephrase",
                    "elicitation_policy",
                    "v1",
                    f"First thin answer on {elicit_key}; rephrase before options.",
                    "thin_answer_rephrase",
                    outputs={"dimension_key": elicit_key, "attempt": attempts},
                )
            elif can_recover and should_offer_options(
                reply_signal=reply_signal.value,
                attempts=attempts,
                is_thin=thin.is_thin,
            ):
                target = elicitation_target(elicit_key)
                message_kind = "elicitation"
                elicitation_spec = build_elicitation_spec(elicit_key)
                await tx.update_session_counters(
                    elicitation_attempts_for_target=attempts,
                    elicitation_target_key=elicit_key,
                )
                await trace.record(
                    "elicitation_selected",
                    "elicitation_policy",
                    "v1",
                    f"Selected elicitation options for {elicit_key}.",
                    "thin_answer_elicitation",
                    outputs={
                        "dimension_key": elicit_key,
                        "attempt": attempts,
                    },
                )
            elif can_recover:
                await trace.record(
                    "elicitation_exhausted",
                    "elicitation_policy",
                    "v1",
                    f"Elicitation exhausted for {elicit_key}; advancing priority.",
                    "elicitation_cap_reached",
                    outputs={"dimension_key": elicit_key, "attempt": attempts},
                )
                # Soft-skip: drop exhausted target kind/key and reselect
                remaining = [
                    c
                    for c in candidates
                    if not (c.kind == target.kind and c.key == target.key)
                    and c.key != elicit_key
                    and c.key != f"constraints:geo"
                ]
                target = select_next(remaining) or _FALLBACK_TARGET
                await tx.update_session_counters(
                    elicitation_attempts_for_target=0,
                    clear_elicitation_target=True,
                )
        elif accepted_count > 0:
            await tx.update_session_counters(
                elicitation_attempts_for_target=0,
                clear_elicitation_target=True,
            )

        await trace.record(
            "question_target_selected",
            "question_policy",
            "v2",
            f"Selected {target.kind}:{target.key} from {len(candidates)} candidate(s).",
            f"priority_{target.kind}",
            inputs={
                "candidates": [
                    {
                        "kind": candidate.kind,
                        "key": candidate.key,
                        "decision_value": question_value(candidate),
                        "asked_count": candidate.asked_count,
                        "continuity": candidate.continuity,
                    }
                    for candidate in candidates
                ]
            },
            outputs={
                "target_kind": target.kind,
                "target_key": target.key,
                "decision_value": question_value(target),
                "asked_count": target.asked_count,
                "continuity": target.continuity,
                "candidate_count": len(candidates),
                "planner_action": (
                    planner_decision.action.value if planner_decision else None
                ),
            },
        )

        missing_established = [
            key
            for key, status in (stage_inputs.get("dimension_statuses") or {}).items()
            if status != "supported"
        ]
        await trace.record(
            "stage_gate_evaluated",
            "stage_policy",
            "v2",
            "Evaluated profile-review stage gate inputs.",
            stage_inputs.get("review_reason") or "stage_gate",
            outputs={
                "coverage_established": stage_inputs.get("coverage_established"),
                "coverage_touched": stage_inputs.get("coverage_touched"),
                "missing_established_keys": missing_established,
                "location_ready": stage_inputs.get("location_ready"),
                "review_eligible": stage_inputs.get("review_eligible"),
                "reason_code": stage_inputs.get("review_reason"),
            },
        )

        stage = derive_stage(**stage_inputs)
        await trace.record(
            "stage_derived",
            "stage_policy",
            "v2",
            f"Application policy derived stage '{stage}'.",
            f"stage_{stage}",
            inputs={k: stage_inputs[k] for k in stage_inputs},
            outputs={"stage": stage},
        )

        # --- Profile review narrative when entering/staying in profile_review ---
        if stage == "profile_review" and target.kind == "profile_validation":
            try:
                review = await llm.structured(
                    "writer",
                    "profile_review",
                    "v2",
                    ProfileReviewOutput,
                    context_builder.profile_review(
                        public_profile, await tx.accepted_evidence_summaries()
                    ),
                )
                if review and review.narrative:
                    assistant_prefix = (
                        f"{assistant_prefix}\n\n{review.narrative}"
                        if assistant_prefix
                        else review.narrative
                    )
                    message_kind = "profile_review"
            except Exception:
                pass

        # Mark reviewed when student affirms during profile_review
        if stage_inputs.get("reviewed") is False and stage == "profile_review":
            # Latch after a profile_validation ask has already happened + this turn
            # contributed confirmation-like evidence or non-thin affirmation.
            last = last_q or {}
            if last.get("intent_key") == "profile_validation" and (
                accepted_count > 0 or not thin.is_thin
            ):
                await tx.update_session_counters(profile_reviewed=True)
                await trace.record(
                    "profile_review_completed",
                    "turn_processor",
                    "v2",
                    "Latched profile_reviewed after validation turn.",
                    "profile_validation_accepted",
                )
                stage_inputs = await tx.stage_inputs()
                stage = derive_stage(**stage_inputs)

        recent = await tx.recent_messages()
        memory = await tx.memory()
        value_a = value_b = None
        if target.kind == "contradiction":
            value_a, value_b = await tx.contradiction_sides(target.key)

        previous_assistant = None
        for msg in reversed(recent):
            role = msg.get("role") if isinstance(msg, dict) else getattr(msg, "role", None)
            if role == "assistant":
                previous_assistant = (
                    msg.get("content")
                    if isinstance(msg, dict)
                    else getattr(msg, "content", None)
                )
                break

        used_fallback = False
        azure_succeeded = False
        opening_mode = None
        if "social_opener" in (thin.reason_codes or []):
            opening_mode = "social_opener"
        force_seeded_depth = (
            is_framing_pushback(request.text)
            and target.key == "topics"
            and target.kind in {"project_critical_unknown", "provisional_dimension"}
        )
        try:
            if force_seeded_depth:
                question = target.fallback_template
                used_fallback = True
                await trace.record(
                    "question_fallback_used",
                    "question_writer",
                    "v2",
                    "Used seeded interest-depth ask after framing pushback.",
                    "framing_pushback_seeded_depth",
                    outputs={"target_kind": target.kind},
                )
            elif target.kind == "social_intro":
                # Social introductions are deterministic: an assessment writer
                # must not turn "what's your name?" into a scored survey item.
                question = target.fallback_template
                used_fallback = True
                await trace.record(
                    "question_fallback_used",
                    "question_writer",
                    "v2",
                    "Used the seeded social introduction question.",
                    "social_intro_seeded",
                    outputs={"target_key": target.key},
                )
            else:
                writer_context = context_builder.question_writer(
                    target,
                    recent,
                    memory,
                    public_profile,
                    contradiction_sides={"value_a": value_a, "value_b": value_b}
                    if target.kind == "contradiction"
                    else None,
                    previous_assistant_question=previous_assistant,
                )
                if planner_decision:
                    writer_context["planner_decision"] = {
                        "action": planner_decision.action.value,
                        "target": target.key,
                        "reason": planner_decision.reason,
                        "avoid_topics": list(planner_decision.avoid_topics),
                        "phase": planner_decision.phase.value,
                    }
                if opening_mode:
                    writer_context["opening_mode"] = opening_mode
                if target.kind == "elicitation":
                    writer_context["elicitation"] = build_elicitation_spec(
                        target.key
                    ).model_dump()
                question = await writer.write(writer_context)
                write_run_id = getattr(llm, "last_llm_run_id", None) if llm else None
                await trace.record(
                    "question_written",
                    "question_writer",
                    "v2",
                    "Azure personalized the application-selected question target.",
                    "structured_writer_succeeded",
                    outputs={"target_kind": target.kind},
                    llm_run_id=write_run_id,
                )
                azure_succeeded = True
        except Exception as error:
            used_fallback = True
            question = target.fallback_template
            await trace.record(
                "question_fallback_used",
                "question_writer",
                "v2",
                "Used the seeded fallback after question personalization failed.",
                "writer_failure",
                outputs={
                    "error_type": type(error).__name__,
                    "target_kind": target.kind,
                },
            )

        gate = apply_question_quality_gate(
            question=question,
            target=target,
            previous_assistant=previous_assistant,
            value_a=value_a,
            value_b=value_b,
            azure_succeeded=azure_succeeded and not used_fallback,
            public_profile=public_profile,
            opening_mode=opening_mode,
        )
        question = gate["question"]
        if gate["outcome"] != "passed":
            await trace.record(
                "question_quality_gate",
                "question_quality",
                "v1",
                f"Question quality gate outcome: {gate['outcome']}.",
                gate["reason"],
                outputs={
                    "outcome": gate["outcome"],
                    "reason": gate["reason"],
                    "target_kind": target.kind,
                    "target_key": target.key,
                },
            )
            if gate["outcome"] == "seeded_override":
                used_fallback = True

        # --- Project matching when stage allows ---
        if stage == "project_matching" and stage_inputs.get("location_ready"):
            project_blurb = await _run_project_matching(tx, llm, trace, context_builder)
            if project_blurb:
                assistant_prefix = (
                    f"{assistant_prefix}\n\n{project_blurb}"
                    if assistant_prefix
                    else project_blurb
                )
                message_kind = "project_offer"

        if message_kind == "elicitation" and elicitation_spec is None:
            elicit_key = target.key
            if elicit_key == "constraints:geo":
                elicit_key = "constraints"
            elicitation_spec = build_elicitation_spec(elicit_key)

        assistant = await tx.persist_question_and_complete(
            turn,
            target,
            question,
            stage,
            transition,
            used_fallback=used_fallback,
            message_kind=message_kind,
            assistant_prefix=assistant_prefix,
            elicitation=elicitation_spec,
            student_message_id=message.id,
        )

        try:
            await _maybe_compact_memory(tx, context_builder, llm, trace)
        except Exception:
            pass

        await trace.record(
            "turn_completed",
            "turn_processor",
            "v2",
            "Persisted the question, assistant message, stage, and completed turn.",
            "turn_committed",
            outputs={
                "stage": stage,
                "used_fallback": used_fallback,
                "message_kind": message_kind,
            },
            entity_refs={"assistant_message_ids": [str(assistant.id)]}
            if hasattr(assistant, "id")
            else {},
        )
        return assistant


async def _run_project_matching(tx, llm, trace, context_builder) -> str | None:
    profile = await tx.matching_profile()
    geo = extract_geo_from_profile(profile)
    opportunities = await tx.list_active_opportunities()
    matches = rank_opportunities(profile, opportunities)
    await tx.persist_opportunity_fits(matches)
    eligible = [m for m in matches if m.eligible]
    await trace.record(
        "opportunities_matched",
        "opportunity_matcher",
        "v1",
        f"Ranked {len(matches)} opportunities; {len(eligible)} eligible.",
        "deterministic_opportunity_rank",
        outputs={
            "match_count": len(matches),
            "eligible_count": len(eligible),
            "failed_geo_count": sum(
                1 for m in matches if "geo" in m.failed_constraints
            ),
            "top_keys": [m.opportunity_key for m in matches[:5]],
        },
    )

    research = WebResearchClient(llm)
    await trace.record(
        "research_started",
        "web_research_client",
        "v1",
        "Starting bounded web research queries.",
        "research_begin",
        outputs={"configured": research.configured},
    )
    user_location = {}
    if geo.get("geo_places"):
        user_location = {"type": "approximate", "city": geo["geo_places"][0]}
    elif geo.get("geo_regions"):
        user_location = {"type": "approximate", "region": geo["geo_regions"][0]}

    queries, findings, error = await research.research(
        profile=profile, geo=geo, user_location=user_location
    )
    stored_findings: list[dict] = []
    if error and not findings:
        run_id = await tx.create_research_run(
            query=queries[0] if queries else "n/a",
            user_location=user_location,
            status="skipped" if error == "web_search_unconfigured" else "failed",
            error_type=error,
        )
        await trace.record(
            "research_failed",
            "web_research_client",
            "v1",
            "Web research unavailable; continuing with curated catalog.",
            error,
            outputs={"research_run_id": str(run_id), "query_count": len(queries)},
        )
    else:
        for i, query in enumerate(queries or ["research"]):
            run_id = await tx.create_research_run(
                query=query,
                user_location=user_location,
                status="succeeded" if findings else "failed",
                llm_run_id=getattr(llm, "last_llm_run_id", None),
                error_type=error,
            )
            if i == 0 and findings:
                stored_findings = await tx.persist_research_findings(run_id, findings)
        await trace.record(
            "research_findings_stored",
            "web_research_client",
            "v1",
            f"Stored {len(stored_findings)} URL-grounded research finding(s).",
            "findings_persisted",
            outputs={"finding_count": len(stored_findings)},
            entity_refs={
                "research_finding_ids": [f["id"] for f in stored_findings],
            },
        )

    top_opps = []
    opp_by_id = {o["id"]: o for o in opportunities}
    for match in eligible[:5]:
        opp = opp_by_id.get(match.opportunity_id)
        if opp:
            top_opps.append(opp)
    if not top_opps:
        # Still offer remote_ok if any
        top_opps = [o for o in opportunities if "remote_ok" in (o.get("geo_regions") or [])][
            :3
        ]

    findings_rows = stored_findings or await tx.list_research_findings()
    composer = ProjectComposer(llm)
    accepted, rejected = await composer.compose(
        {
            "profile": profile,
            "opportunities": top_opps,
            "research_findings": findings_rows,
            "opportunity_ids": [o["id"] for o in top_opps],
            "research_finding_ids": [f["id"] for f in findings_rows],
        }
    )
    for rej in rejected:
        await trace.record(
            "project_citation_rejected",
            "project_citation_gate",
            "v1",
            "Rejected composed project lacking valid citations.",
            rej.get("reason") or "citation_rejected",
            outputs={"reason": rej.get("reason")},
        )
    if accepted:
        stored = await tx.persist_generated_projects(accepted)
        await trace.record(
            "project_composed",
            "project_composer",
            "v1",
            f"Persisted {len(stored)} citation-grounded project offer(s).",
            "projects_persisted",
            outputs={"project_count": len(stored)},
            entity_refs={"generated_project_ids": [p["id"] for p in stored]},
        )
        await trace.record(
            "project_fits_persisted",
            "opportunity_matcher",
            "v1",
            "Opportunity fits and generated projects are available for teacher review.",
            "fits_ready",
            outputs={
                "eligible_count": len(eligible),
                "generated_count": len(stored),
            },
        )
        lines = ["Here are grounded project directions that fit your profile:"]
        for p in accepted[:3]:
            lines.append(f"- {p.title}: {p.summary}")
        lines.append("Which of these directions interests you most, or what would you change?")
        return "\n".join(lines)
    return None


def _explicit_preference(validated, dimension_key: str) -> bool:
    """True when this turn both supports one value and opposes another on dim."""
    supports = {
        item.value_key
        for item in validated
        if item.accepted
        and item.dimension_key == dimension_key
        and item.polarity.value == "support"
        and item.value_key
    }
    opposes = {
        item.value_key
        for item in validated
        if item.accepted
        and item.dimension_key == dimension_key
        and item.polarity.value == "oppose"
        and item.value_key
    }
    return bool(supports and opposes and supports != opposes)


async def _maybe_compact_memory(tx, context_builder, llm, trace) -> None:
    if llm is None:
        return
    stats = await tx.student_response_stats()
    settings = getattr(tx, "_settings", None)
    interval = getattr(settings, "memory_response_interval", 8) if settings else 8
    token_threshold = (
        getattr(settings, "memory_token_threshold", 6000) if settings else 6000
    )
    compactor = MemoryCompactor(
        llm, interval=interval, token_threshold=token_threshold
    )
    raw = await tx.allowed_messages(tx._session_id)
    raw_dicts = [
        {
            "id": str(m.id),
            "sequence": m.sequence,
            "role": m.role,
            "content": m.content,
        }
        for m in raw
    ]
    uncompacted_tokens = sum(len(m.get("content") or "") // 4 for m in raw_dicts)
    if not compactor.due(stats["responses_since_snapshot"], uncompacted_tokens):
        return
    boundary = stats["max_sequence"]
    snapshot = await compactor.compact(context_builder, raw_dicts, boundary)
    if snapshot is None:
        return
    if hasattr(snapshot, "model_dump"):
        content = snapshot.model_dump()
    elif isinstance(snapshot, dict):
        content = dict(snapshot)
    else:
        content = {
            "stable_preferences": getattr(snapshot, "stable_preferences", []),
            "commitments": getattr(snapshot, "commitments", []),
            "unresolved_threads": getattr(snapshot, "unresolved_threads", []),
            "boundary_sequence": boundary,
        }
    content["boundary_sequence"] = boundary
    await tx.insert_memory_snapshot(
        content=content,
        boundary_sequence=boundary,
        prompt_version="v1",
    )
