BEGIN;

-- Plan 04 (Phase 4) W4.1: 5-item quizzes with pass-to-advance gating.
--
-- Pass = >=4/5 correct AND >=1 correct on every critical objective. Quiz answers
-- are learning evidence, never assessment evidence (hard rules 2/4): nothing
-- here writes assessment.*. Attempts/responses are append-only facts; BKT
-- mastery and item difficulty are replayable projections of them.

CREATE TYPE learning.quiz_item_kind AS ENUM ('mcq', 'select_all', 'short');
CREATE TYPE learning.objective_state AS ENUM ('unseen', 'learning', 'mastered', 'decaying');

CREATE TABLE learning.quiz_items (
    id uuid PRIMARY KEY,
    module_id uuid NOT NULL REFERENCES learning.modules(id) ON DELETE CASCADE,
    objective_id uuid NOT NULL REFERENCES learning.objectives(id) ON DELETE CASCADE,
    form_id smallint NOT NULL CHECK (form_id > 0),
    seq smallint NOT NULL CHECK (seq > 0),
    kind learning.quiz_item_kind NOT NULL,
    stem text NOT NULL CHECK (length(stem) > 0),
    options jsonb NOT NULL DEFAULT '[]'::jsonb,
    answer jsonb NOT NULL,
    difficulty numeric(3,2) NOT NULL DEFAULT 0.50 CHECK (difficulty BETWEEN 0 AND 1),
    hint_text text NOT NULL DEFAULT '',
    feedback_correct text NOT NULL DEFAULT '',
    feedback_wrong text NOT NULL DEFAULT '',
    slide_ref uuid REFERENCES learning.slides(id) ON DELETE SET NULL,
    is_critical boolean NOT NULL DEFAULT false,
    UNIQUE (module_id, form_id, seq),
    CHECK (jsonb_typeof(options) = 'array'),
    CHECK (jsonb_typeof(answer) = 'array')
);

CREATE INDEX quiz_items_module_form_idx ON learning.quiz_items(module_id, form_id, seq);

-- One row per attempt. GET creates the open attempt (submitted_at IS NULL);
-- POST submits it (request_id set) and scores deterministically.
CREATE TABLE learning.quiz_attempts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id uuid NOT NULL REFERENCES core.students(id) ON DELETE CASCADE,
    session_id uuid NOT NULL REFERENCES core.sessions(id) ON DELETE CASCADE,
    module_id uuid NOT NULL REFERENCES learning.modules(id) ON DELETE CASCADE,
    attempt_no smallint NOT NULL CHECK (attempt_no > 0),
    form_id smallint NOT NULL CHECK (form_id > 0),
    item_ids jsonb NOT NULL,
    score smallint NOT NULL DEFAULT 0 CHECK (score >= 0),
    passed boolean NOT NULL DEFAULT false,
    critical_missed text[] NOT NULL DEFAULT '{}',
    request_id text,
    started_at timestamptz NOT NULL DEFAULT now(),
    submitted_at timestamptz,
    UNIQUE (student_id, module_id, attempt_no),
    CHECK (jsonb_typeof(item_ids) = 'array')
);

CREATE UNIQUE INDEX quiz_attempts_open_uidx
    ON learning.quiz_attempts(session_id, module_id) WHERE submitted_at IS NULL;
CREATE UNIQUE INDEX quiz_attempts_request_uidx
    ON learning.quiz_attempts(request_id) WHERE request_id IS NOT NULL;
CREATE INDEX quiz_attempts_session_module_idx
    ON learning.quiz_attempts(session_id, module_id, attempt_no);

CREATE TABLE learning.quiz_responses (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    attempt_id uuid NOT NULL REFERENCES learning.quiz_attempts(id) ON DELETE CASCADE,
    item_id uuid NOT NULL REFERENCES learning.quiz_items(id) ON DELETE CASCADE,
    response jsonb NOT NULL,
    correct boolean NOT NULL,
    latency_ms integer CHECK (latency_ms IS NULL OR latency_ms >= 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (attempt_id, item_id),
    CHECK (jsonb_typeof(response) = 'array')
);

-- Replayable BKT projection (one row per objective per session).
CREATE TABLE learning.mastery_states (
    session_id uuid NOT NULL REFERENCES core.sessions(id) ON DELETE CASCADE,
    objective_id uuid NOT NULL REFERENCES learning.objectives(id) ON DELETE CASCADE,
    p_mastery numeric(5,4) NOT NULL CHECK (p_mastery BETWEEN 0 AND 1),
    state learning.objective_state NOT NULL DEFAULT 'unseen',
    correct_count integer NOT NULL DEFAULT 0 CHECK (correct_count >= 0),
    wrong_count integer NOT NULL DEFAULT 0 CHECK (wrong_count >= 0),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (session_id, objective_id)
);

-- Poor-man's IRT: observed p-hat per item, for author-estimated difficulty drift.
CREATE TABLE learning.item_stats (
    item_id uuid PRIMARY KEY REFERENCES learning.quiz_items(id) ON DELETE CASCADE,
    attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    correct integer NOT NULL DEFAULT 0 CHECK (correct >= 0),
    p_hat numeric(4,3) CHECK (p_hat IS NULL OR p_hat BETWEEN 0 AND 1),
    updated_at timestamptz NOT NULL DEFAULT now()
);

COMMIT;
