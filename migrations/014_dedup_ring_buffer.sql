BEGIN;

-- Plan 01 W1.2: outgoing duplicate-reply control. Ring buffer of the last 8
-- assistant texts per session, maintained by the sole write path; near-duplicates
-- are rewritten once and traced.
ALTER TABLE core.sessions
    ADD COLUMN IF NOT EXISTS assistant_recent jsonb NOT NULL DEFAULT '[]';

ALTER TYPE audit.decision_event_type ADD VALUE IF NOT EXISTS
    'assistant_duplicate_rewritten';

COMMIT;
