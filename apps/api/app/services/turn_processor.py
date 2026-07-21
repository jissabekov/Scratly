from app.services.decision_trace import DecisionTraceRecorder
from app.services.memory_compactor import MemoryCompactor
from app.services.question_policy import Target, derive_stage, select_next
from app.services.question_quality import apply_question_quality_gate

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
            "v1",
            "Accepted a new idempotent student turn.",
            "new_idempotency_key",
            entity_refs={"student_message_ids": [str(message.id)]},
        )

        pending_dim = await tx.pending_contradiction_target()

        packet = await extractor.propose(
            context_builder.extractor(
                message, await tx.allowed_messages(session_id), await tx.taxonomy()
            )
        )
        extract_run_id = getattr(llm, "last_llm_run_id", None) if llm else None
        await trace.record(
            "evidence_proposed",
            "evidence_extractor",
            "v2",
            f"Extractor proposed {len(packet.items)} evidence item(s).",
            "structured_extraction_completed",
            outputs={"proposed_count": len(packet.items)},
            llm_run_id=extract_run_id,
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
            "v2",
            f"Accepted {accepted_count} of {len(validated)} proposed evidence item(s).",
            "grounding_checks_applied",
            inputs={"proposed_count": len(validated)},
            outputs={
                "accepted_count": accepted_count,
                "rejected_count": len(validated) - accepted_count,
                "rejection_reason_counts": rejected_reasons,
            },
        )

        prior_open = set(await tx.open_contradiction_dimensions())
        transition = await tx.apply_evidence_reduce_contradictions_snapshot(validated)
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

        # Resolve when: prior question targeted the dim, dim was already open and
        # this turn added evidence, or this turn's evidence is an explicit preference.
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

        candidates = await tx.question_candidates()
        target = select_next(candidates) or _FALLBACK_TARGET
        await trace.record(
            "question_target_selected",
            "question_policy",
            "v2",
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
            "v2",
            f"Application policy derived stage '{stage}'.",
            f"stage_{stage}",
            inputs=stage_inputs,
            outputs={"stage": stage},
        )

        recent = await tx.recent_messages()
        memory = await tx.memory()
        profile = await tx.public_profile()
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
        try:
            writer_context = context_builder.question_writer(
                target,
                recent,
                memory,
                profile,
                contradiction_sides={"value_a": value_a, "value_b": value_b}
                if target.kind == "contradiction"
                else None,
                previous_assistant_question=previous_assistant,
            )
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

        assistant = await tx.persist_question_and_complete(
            turn, target, question, stage, transition, used_fallback=used_fallback
        )

        try:
            await _maybe_compact_memory(tx, context_builder, llm, trace)
        except Exception:
            pass

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
