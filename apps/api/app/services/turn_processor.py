from app.services.decision_trace import DecisionTraceRecorder
from app.services.question_policy import derive_stage, select_next


async def process_student_turn(repo, extractor, writer, context_builder, session_id, request):
    """Sole normal turn path; state and its trace commit or roll back together."""
    existing = await repo.completed_turn(session_id, request.idempotency_key)
    if existing:
        return existing

    async with repo.transaction() as tx:
        # Unique(session_id,idempotency_key) is the final concurrency guard.
        turn, message = await tx.create_turn_and_student_message(
            session_id, request.idempotency_key, request.text
        )
        trace = DecisionTraceRecorder(tx, session_id, turn.id)
        await trace.record(
            "turn_started",
            "turn_processor",
            "v1",
            "Accepted a new idempotent student turn.",
            "new_idempotency_key",
            entity_refs={"student_message_ids": [str(message.id)]},
        )

        packet = await extractor.propose(
            context_builder.extractor(
                message, await tx.allowed_messages(session_id), await tx.taxonomy()
            )
        )
        await trace.record(
            "evidence_proposed",
            "evidence_extractor",
            "v1",
            f"Extractor proposed {len(packet.items)} evidence item(s).",
            "structured_extraction_completed",
            outputs={"proposed_count": len(packet.items)},
        )

        validated = await tx.validate_and_record_evidence(packet.items, message)
        accepted_count = sum(item.accepted for item in validated)
        rejected_reasons: dict[str, int] = {}
        for item in validated:
            if not item.accepted:
                reason = item.rejection_reason or "unspecified"
                rejected_reasons[reason] = rejected_reasons.get(reason, 0) + 1
        await trace.record(
            "evidence_validated",
            "grounding_validator",
            "v1",
            f"Accepted {accepted_count} of {len(validated)} proposed evidence item(s).",
            "grounding_checks_applied",
            inputs={"proposed_count": len(validated)},
            outputs={
                "accepted_count": accepted_count,
                "rejected_count": len(validated) - accepted_count,
                "rejection_reason_counts": rejected_reasons,
            },
        )

        # Only this deterministic DB path can alter assessment state.
        transition = await tx.apply_evidence_reduce_contradictions_snapshot(validated)
        await trace.record(
            "profile_reduced",
            "profile_reducer",
            "v1",
            "Recomputed profile solely from accepted grounded evidence.",
            "accepted_evidence_reduced",
            inputs={"accepted_evidence_count": accepted_count},
            entity_refs=transition.get("entity_refs", {}) if isinstance(transition, dict) else {},
        )
        contradiction_count = (
            transition.get("contradiction_count", 0)
            if isinstance(transition, dict)
            else 0
        )
        await trace.record(
            "contradiction_evaluated",
            "contradiction_engine",
            "v1",
            f"Detected or retained {contradiction_count} open contradiction(s).",
            "conflicts_kept_explicit_without_averaging",
            outputs={"open_contradiction_count": contradiction_count},
        )

        candidates = await tx.question_candidates()
        target = select_next(candidates)
        await trace.record(
            "question_target_selected",
            "question_policy",
            "v1",
            f"Selected {target.kind}:{target.key} from {len(candidates)} candidate(s).",
            f"priority_{target.kind}",
            inputs={"candidate_kinds": [candidate.kind for candidate in candidates]},
            outputs={"target_kind": target.kind, "target_key": target.key},
        )

        stage_inputs = await tx.stage_inputs()
        stage = derive_stage(**stage_inputs)
        await trace.record(
            "stage_derived",
            "stage_policy",
            "v1",
            f"Application policy derived stage '{stage}'.",
            f"stage_{stage}",
            inputs=stage_inputs,
            outputs={"stage": stage},
        )

        used_fallback = False
        try:
            question = await writer.write(
                context_builder.question_writer(
                    target,
                    await tx.recent_messages(),
                    await tx.memory(),
                    await tx.public_profile(),
                )
            )
            await trace.record(
                "question_written",
                "question_writer",
                "v1",
                "Azure personalized the application-selected question target.",
                "structured_writer_succeeded",
                outputs={"target_kind": target.kind},
            )
        except Exception as error:
            used_fallback = True
            question = target.fallback_template
            await trace.record(
                "question_fallback_used",
                "question_writer",
                "v1",
                "Used the seeded fallback after question personalization failed.",
                "writer_failure",
                outputs={"error_type": type(error).__name__, "target_kind": target.kind},
            )

        assistant = await tx.persist_question_and_complete(
            turn, target, question, stage, transition
        )
        await trace.record(
            "turn_completed",
            "turn_processor",
            "v1",
            "Persisted the question, assistant message, stage, and completed turn.",
            "turn_committed",
            outputs={"stage": stage, "used_fallback": used_fallback},
            entity_refs={"assistant_message_ids": [str(assistant.id)]}
            if hasattr(assistant, "id")
            else {},
        )
        return assistant
