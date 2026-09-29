BEGIN;

-- Plan 01 W1.1: per-dimension question-exposure ledger for CAT item-exposure
-- control. Owned by the sole write path (process_student_turn) at
-- question-commit time; shape: {dim: {total, consecutive, last_asked_turn}}.
ALTER TABLE core.sessions
    ADD COLUMN IF NOT EXISTS dim_ask_counts jsonb NOT NULL DEFAULT '{}';

COMMIT;
