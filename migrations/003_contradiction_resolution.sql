BEGIN;

-- Append-only decision events for contradiction resolution and question gates.
ALTER TYPE audit.decision_event_type ADD VALUE IF NOT EXISTS 'contradiction_resolved';
ALTER TYPE audit.decision_event_type ADD VALUE IF NOT EXISTS 'question_quality_gate';

-- Clarification attempt counter for open contradictions (dismiss after N fails).
ALTER TABLE assessment.contradictions
    ADD COLUMN IF NOT EXISTS clarification_attempts smallint NOT NULL DEFAULT 0
        CHECK (clarification_attempts >= 0);

COMMIT;
