class ContextBuilder:
    def extractor(self, student_message, allowed_messages, taxonomy):
        return {'student_message':student_message,'allowed_source_messages':allowed_messages,'taxonomy':taxonomy}
    def question_writer(self, target, recent_messages, memory_snapshot, public_profile_summary):
        return {'selected_target':target,'recent_messages':recent_messages[-6:],'memory':memory_snapshot,'public_profile_summary':public_profile_summary}
    def memory(self, complete_raw_transcript, boundary_sequence):
        return {'raw_transcript':complete_raw_transcript,'boundary_sequence':boundary_sequence}
    def profile_review(self, profile, accepted_evidence):
        return {'profile':profile,'accepted_evidence':accepted_evidence}
    def project(self, profile, constraints, archetypes):
        return {'profile':profile,'constraints':constraints,'archetypes':archetypes}
