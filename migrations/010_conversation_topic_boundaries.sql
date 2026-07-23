BEGIN;

-- Explicit student topic changes are policy state, not a transient prompt hint.
ALTER TABLE core.sessions
    ADD COLUMN IF NOT EXISTS rejected_topic_keys text[] NOT NULL DEFAULT '{}';

COMMIT;
