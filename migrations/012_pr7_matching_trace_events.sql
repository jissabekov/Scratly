-- PR #7: project-matching abstention traces and new assistant message kinds.

ALTER TYPE audit.decision_event_type ADD VALUE IF NOT EXISTS 'project_matching_abstained';
ALTER TYPE audit.decision_event_type ADD VALUE IF NOT EXISTS 'post_match_feedback_handled';

ALTER TYPE conversation.assistant_message_kind ADD VALUE IF NOT EXISTS 'matching_unavailable';
ALTER TYPE conversation.assistant_message_kind ADD VALUE IF NOT EXISTS 'post_match_feedback';
