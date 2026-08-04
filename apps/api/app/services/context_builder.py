from dataclasses import asdict, is_dataclass


def _msg(message):
    if isinstance(message, dict) or not hasattr(message, "id"):
        return message
    return {
        "id": str(message.id),
        "session_id": str(message.session_id),
        "content": message.content,
        "sequence": getattr(message, "sequence", None),
        "role": getattr(message, "role", None),
    }


def _target(target):
    if isinstance(target, (dict, str)):
        return target
    if is_dataclass(target) and not isinstance(target, type):
        return asdict(target)
    return {
        "kind": target.kind,
        "key": target.key,
        "fallback_template": target.fallback_template,
    }


class ContextBuilder:
    def extractor(self, student_message, allowed_messages, taxonomy):
        return {
            "student_message": _msg(student_message),
            "allowed_source_messages": [_msg(m) for m in allowed_messages],
            "taxonomy": taxonomy,
        }

    def question_writer(
        self,
        target,
        recent_messages,
        memory_snapshot,
        public_profile_summary,
        contradiction_sides=None,
        previous_assistant_question=None,
    ):
        recent = recent_messages[-8:] if recent_messages else []
        last_student = next(
            (m for m in reversed(recent) if _role(m) == "student"), None
        )
        from app.services.question_policy import classify_reply
        from app.services.question_library import BY_KEY

        target_key = (
            target.get("key")
            if isinstance(target, dict)
            else getattr(target, "key", None)
        )
        target_kind = (
            target.get("kind")
            if isinstance(target, dict)
            else getattr(target, "kind", None)
        )
        payload = {
            "selected_target": _target(target),
            "target_kind": target_kind,
            "target_key": target_key,
            "curated_intent": BY_KEY.get(target_key or ""),
            "recent_messages": [
                m if isinstance(m, dict) or not hasattr(m, "id") else _msg(m)
                for m in recent
            ],
            "last_reply_signal": (
                classify_reply(_content(last_student)).value if last_student else None
            ),
            "memory": memory_snapshot,
            "public_profile_summary": public_profile_summary,
            "previous_assistant_question": previous_assistant_question,
            "conversation_rules": {
                "one_question_only": True,
                "acknowledgment_optional": True,
                "never_mechanically_repeat_student_answer": True,
                "writer_must_not_change_planner_target": True,
                "never_expand_playing_into_building_or_projects": True,
                "prefer_concrete_past_behavior_over_hypotheticals": True,
                "repair_corrections_before_continuing": True,
                "location_granularity": "city_or_region_and_country; never request an address",
                "adolescent_stance": {
                    "voice": "calm interested adult; mirror brevity, never imitate slang",
                    "autonomy": "uncertainty, skipping, correction, and topic changes are valid",
                    "inference": "behavior is context, never a personality diagnosis",
                    "burden": "ask only what can alter fit, scope, support, or feasibility",
                },
            },
        }
        if contradiction_sides:
            payload["contradiction_sides"] = contradiction_sides
        return payload

    def memory(self, complete_raw_transcript, boundary_sequence):
        return {
            "raw_transcript": complete_raw_transcript,
            "boundary_sequence": boundary_sequence,
        }

    def profile_review(self, profile, accepted_evidence):
        return {"profile": profile, "accepted_evidence": accepted_evidence}

    def project(self, profile, constraints, archetypes):
        return {
            "profile": profile,
            "constraints": constraints,
            "archetypes": archetypes,
        }


def _role(message):
    if isinstance(message, dict):
        return message.get("role")
    return getattr(message, "role", None)


def _content(message):
    if isinstance(message, dict):
        return message.get("content", "")
    return getattr(message, "content", "")
