BEGIN;

-- Plan 05 (Phase 5) W5.1: progress check-ins, advice/intervention ladder, and
-- SM-2-lite retention cards.
--
-- Learning evidence stays a separate stream: nothing here writes assessment.*.
-- `learning.learning_events` (017) remains the append-only source of truth and
-- `learning.mastery_states` / rollups remain replayable projections of it.
--
-- Check-in scheduling, scoring, the intervention ladder, and retention
-- intervals are 100% deterministic; the LLM may only phrase an already-decided
-- item and classify free text against its rubric.

CREATE TYPE learning.checkin_kind AS ENUM ('likert', 'mcq', 'mini_exercise', 'self_explain');

CREATE TYPE learning.intervention_level AS ENUM (
    'hint', 'reteach', 'requiz', 'walkthrough', 'handoff'
);

-- One row per authored check-in item. `payload` is a typed per-kind contract
-- validated in code (StrictModel, extra="forbid"), mirroring quiz_items.
CREATE TABLE learning.checkin_items (
    id uuid PRIMARY KEY,
    objective_id uuid NOT NULL REFERENCES learning.objectives(id) ON DELETE CASCADE,
    seq smallint NOT NULL CHECK (seq > 0),
    kind learning.checkin_kind NOT NULL,
    prompt text NOT NULL CHECK (length(prompt) > 0),
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    content_version text NOT NULL CHECK (length(content_version) > 0),
    UNIQUE (objective_id, seq),
    CHECK (jsonb_typeof(payload) = 'object')
);

CREATE INDEX checkin_items_objective_idx ON learning.checkin_items(objective_id, seq);

-- Delivery + response lifecycle. `request_id` is the idempotency key for the
-- write path; `scheduled_at`/`delivered_at` are set by the deterministic
-- scheduler, `responded_at`/`dismissed` by the student.
CREATE TABLE learning.checkin_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id uuid NOT NULL REFERENCES core.students(id) ON DELETE CASCADE,
    session_id uuid NOT NULL REFERENCES core.sessions(id) ON DELETE CASCADE,
    checkin_item_id uuid NOT NULL REFERENCES learning.checkin_items(id) ON DELETE CASCADE,
    objective_id uuid NOT NULL REFERENCES learning.objectives(id) ON DELETE CASCADE,
    trigger_reason text NOT NULL CHECK (length(trigger_reason) > 0),
    scheduled_at timestamptz NOT NULL DEFAULT now(),
    delivered_at timestamptz,
    responded_at timestamptz,
    response jsonb,
    score numeric(4,3) CHECK (score IS NULL OR score BETWEEN 0 AND 1),
    latency_ms integer CHECK (latency_ms IS NULL OR latency_ms >= 0),
    dismissed boolean NOT NULL DEFAULT false,
    request_id text,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (response IS NULL OR jsonb_typeof(response) = 'object'),
    CHECK (dismissed = false OR responded_at IS NULL)
);

CREATE UNIQUE INDEX checkin_events_request_uidx
    ON learning.checkin_events(request_id) WHERE request_id IS NOT NULL;
CREATE INDEX checkin_events_session_idx
    ON learning.checkin_events(session_id, scheduled_at DESC);
-- At most one open (delivered, unanswered) check-in per session at a time.
CREATE UNIQUE INDEX checkin_events_open_uidx
    ON learning.checkin_events(session_id)
    WHERE delivered_at IS NOT NULL AND responded_at IS NULL AND dismissed = false;

-- Advice / intervention ladder. Priority-ordered; every row records the rule
-- that fired, the rendered content, and when it was resolved.
CREATE TABLE learning.interventions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id uuid NOT NULL REFERENCES core.students(id) ON DELETE CASCADE,
    session_id uuid NOT NULL REFERENCES core.sessions(id) ON DELETE CASCADE,
    objective_id uuid REFERENCES learning.objectives(id) ON DELETE SET NULL,
    level learning.intervention_level NOT NULL,
    trigger_rule text NOT NULL CHECK (length(trigger_rule) > 0),
    content jsonb NOT NULL DEFAULT '{}'::jsonb,
    request_id text,
    created_at timestamptz NOT NULL DEFAULT now(),
    resolved_at timestamptz,
    CHECK (jsonb_typeof(content) = 'object')
);

CREATE UNIQUE INDEX interventions_request_uidx
    ON learning.interventions(request_id) WHERE request_id IS NOT NULL;
CREATE INDEX interventions_session_idx
    ON learning.interventions(session_id, created_at DESC);

-- SM-2-lite spaced-repetition cards. One card per (student, objective); a lapse
-- resets the interval but NEVER re-locks a module.
CREATE TABLE learning.retention_cards (
    student_id uuid NOT NULL REFERENCES core.students(id) ON DELETE CASCADE,
    session_id uuid NOT NULL REFERENCES core.sessions(id) ON DELETE CASCADE,
    objective_id uuid NOT NULL REFERENCES learning.objectives(id) ON DELETE CASCADE,
    ease numeric(4,2) NOT NULL DEFAULT 2.50 CHECK (ease BETWEEN 1.30 AND 2.80),
    interval_days smallint NOT NULL DEFAULT 1 CHECK (interval_days >= 1),
    due_at timestamptz NOT NULL,
    reps integer NOT NULL DEFAULT 0 CHECK (reps >= 0),
    lapses integer NOT NULL DEFAULT 0 CHECK (lapses >= 0),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (student_id, objective_id)
);

CREATE INDEX retention_cards_due_idx ON learning.retention_cards(student_id, due_at);

-- Plan 05 §6 correction: `learning.mastery_states` already exists (018) keyed
-- `(session_id, objective_id)`. Session<->student is 1:1 in this product, so we
-- extend the existing projection instead of adding a second key. Migrations are
-- append-only: no column is dropped or retyped.
ALTER TABLE learning.mastery_states
    ADD COLUMN elo numeric(7,2) NOT NULL DEFAULT 1500.00,
    ADD COLUMN evidence_count integer NOT NULL DEFAULT 0 CHECK (evidence_count >= 0),
    ADD COLUMN last_evidence_at timestamptz;

COMMIT;
