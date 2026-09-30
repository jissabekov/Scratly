-- Plan 06 W6.1 — learning integration seam.
--
-- Two seams land here and only here:
--   1. `progress_checkin` joins the assistant message kinds so the chat
--      terminal fast path can label a learning check-in reply (W6.2).
--   2. The learning repositories gain the same auditability as the assessment
--      write path: ten `learning_*` decision-event kinds emitted from the
--      learning endpoints (W6.3).
--
-- Enum values are added here but never *used* here: Postgres forbids using a
-- newly added enum value in the same transaction that adds it. The enum
-- statements therefore run without a wrapping transaction (mirroring 011) so
-- each ALTER TYPE commits before any code path emits the value.
--
-- `audit.decision_events.turn_id` was NOT NULL (002); learning endpoints are
-- not assessment turns and have no `conversation.turns` row. Relaxing the
-- column lets a turn-less learning event carry the same append-only
-- guarantees. A partial unique index preserves one-sequence-per-correlation
-- ordering for those rows: the table-level UNIQUE (turn_id, sequence) cannot
-- constrain NULL turn ids, because Postgres treats NULLs as distinct.

ALTER TYPE conversation.assistant_message_kind
    ADD VALUE IF NOT EXISTS 'progress_checkin';

ALTER TYPE audit.decision_event_type ADD VALUE IF NOT EXISTS 'learning_hub_viewed';
ALTER TYPE audit.decision_event_type ADD VALUE IF NOT EXISTS 'learning_slide_completed';
ALTER TYPE audit.decision_event_type ADD VALUE IF NOT EXISTS 'learning_quiz_drawn';
ALTER TYPE audit.decision_event_type ADD VALUE IF NOT EXISTS 'learning_quiz_scored';
ALTER TYPE audit.decision_event_type ADD VALUE IF NOT EXISTS 'learning_module_unlocked';
ALTER TYPE audit.decision_event_type ADD VALUE IF NOT EXISTS 'learning_checkin_delivered';
ALTER TYPE audit.decision_event_type ADD VALUE IF NOT EXISTS 'learning_checkin_answered';
ALTER TYPE audit.decision_event_type ADD VALUE IF NOT EXISTS 'learning_checkin_dismissed';
ALTER TYPE audit.decision_event_type ADD VALUE IF NOT EXISTS 'learning_intervention_opened';
ALTER TYPE audit.decision_event_type ADD VALUE IF NOT EXISTS 'learning_retention_card_due';

BEGIN;

-- Staged rollout seam (Plan 06 W6.5): every session starts with the learning
-- journey disabled. The documented e2e/settings toggle flips the default at
-- session-creation time; it never weakens an assertion.
ALTER TABLE core.sessions
    ADD COLUMN IF NOT EXISTS learning_enabled boolean NOT NULL DEFAULT false;

ALTER TABLE audit.decision_events
    ALTER COLUMN turn_id DROP NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS decision_events_learning_uidx
    ON audit.decision_events(correlation_id, sequence)
    WHERE turn_id IS NULL;

COMMIT;
