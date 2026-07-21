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

    def question_writer(self, target, recent_messages, memory_snapshot, public_profile_summary):
        recent = recent_messages[-6:] if recent_messages else []
        return {
            "selected_target": _target(target),
            "recent_messages": [
                m if isinstance(m, dict) or not hasattr(m, "id") else _msg(m)
                for m in recent
            ],
            "memory": memory_snapshot,
            "public_profile_summary": public_profile_summary,
        }

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
