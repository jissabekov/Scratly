class ContextBuilder:
    def extractor(self, student_message, allowed_messages, taxonomy):
        return {'student_message':student_message,'allowed_source_messages':allowed_messages,'taxonomy':taxonomy}
    def question_writer(self, target, recent_messages, memory_snapshot, public_profile_summary):
        recent = recent_messages[-8:]
        last_student = next((m for m in reversed(recent) if _role(m) == 'student'), None)
        from app.services.question_policy import classify_reply
        from app.services.question_library import BY_KEY
        intent = BY_KEY.get(getattr(target, 'key', ''))
        return {
            'selected_target': target,
            'curated_intent': intent,
            'recent_messages': recent,
            'last_reply_signal': classify_reply(_content(last_student)).value if last_student else None,
            'memory': memory_snapshot,
            'public_profile_summary': public_profile_summary,
            'conversation_rules': {
                'one_question_only': True,
                'acknowledge_before_probe': True,
                'never_expand_playing_into_building_or_projects': True,
                'prefer_concrete_past_behavior_over_hypotheticals': True,
                'repair_corrections_before_continuing': True,
                'location_granularity': 'city_or_region_and_country; never request an address',
            },
        }
    def memory(self, complete_raw_transcript, boundary_sequence):
        return {'raw_transcript':complete_raw_transcript,'boundary_sequence':boundary_sequence}
    def profile_review(self, profile, accepted_evidence):
        return {'profile':profile,'accepted_evidence':accepted_evidence}
    def project(self, profile, constraints, archetypes):
        return {'profile':profile,'constraints':constraints,'archetypes':archetypes}


def _role(message):
    return getattr(message, 'role', message.get('role') if isinstance(message, dict) else None)


def _content(message):
    return getattr(message, 'content', message.get('content', '') if isinstance(message, dict) else '')
