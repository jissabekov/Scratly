BEGIN;

-- Plan 03 (Phase 3) W3.1: content-agnostic learning schema.
--
-- Learning is a separate evidence stream from assessment. Nothing here writes
-- assessment.evidence (hard rules 2/4); the sole assessment write path stays
-- process_student_turn. Content is authored in the repo as versioned JSON
-- (content/modules/...), validated, and seeded deterministically; row ids are
-- uuid5 of the natural key so reseeding never orphans a completion.

CREATE SCHEMA learning;

CREATE TYPE learning.module_status AS ENUM ('draft', 'published', 'archived');
CREATE TYPE learning.slide_kind AS ENUM (
    'text', 'callout', 'diagram', 'check', 'worked_example'
);

CREATE TABLE learning.modules (
    id uuid PRIMARY KEY,
    archetype_key text NOT NULL CHECK (length(archetype_key) > 0),
    slug text NOT NULL CHECK (length(slug) > 0),
    seq smallint NOT NULL CHECK (seq > 0),
    title text NOT NULL CHECK (length(title) > 0),
    description text NOT NULL DEFAULT '',
    est_minutes smallint NOT NULL DEFAULT 10 CHECK (est_minutes > 0),
    status learning.module_status NOT NULL DEFAULT 'published',
    content_version text NOT NULL CHECK (length(content_version) > 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (archetype_key, slug),
    UNIQUE (archetype_key, seq)
);

CREATE TABLE learning.objectives (
    id uuid PRIMARY KEY,
    module_id uuid NOT NULL REFERENCES learning.modules(id) ON DELETE CASCADE,
    code text NOT NULL CHECK (length(code) > 0),
    label text NOT NULL CHECK (length(label) > 0),
    is_critical boolean NOT NULL DEFAULT false,
    ordinal smallint NOT NULL CHECK (ordinal > 0),
    UNIQUE (module_id, code),
    UNIQUE (module_id, ordinal)
);

CREATE TABLE learning.lessons (
    id uuid PRIMARY KEY,
    module_id uuid NOT NULL REFERENCES learning.modules(id) ON DELETE CASCADE,
    seq smallint NOT NULL CHECK (seq > 0),
    title text NOT NULL CHECK (length(title) > 0),
    UNIQUE (module_id, seq)
);

-- content jsonb is a typed block list (no free-form HTML), rendered by one
-- SlideBlock component: text | callout | diagram | check | worked_example.
CREATE TABLE learning.slides (
    id uuid PRIMARY KEY,
    lesson_id uuid NOT NULL REFERENCES learning.lessons(id) ON DELETE CASCADE,
    seq smallint NOT NULL CHECK (seq > 0),
    kind learning.slide_kind NOT NULL,
    title text NOT NULL DEFAULT '',
    content jsonb NOT NULL DEFAULT '[]'::jsonb,
    objective_id uuid REFERENCES learning.objectives(id) ON DELETE SET NULL,
    UNIQUE (lesson_id, seq),
    CHECK (jsonb_typeof(content) = 'array')
);

CREATE INDEX slides_lesson_seq_idx ON learning.slides(lesson_id, seq);

-- Idempotent automatic tracking: request_id is the idempotency key, and a
-- student can only complete a given slide once.
CREATE TABLE learning.slide_completions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id uuid NOT NULL REFERENCES core.students(id) ON DELETE CASCADE,
    session_id uuid NOT NULL REFERENCES core.sessions(id) ON DELETE CASCADE,
    slide_id uuid NOT NULL REFERENCES learning.slides(id) ON DELETE CASCADE,
    request_id text NOT NULL CHECK (length(request_id) > 0),
    time_on_slide_ms integer CHECK (time_on_slide_ms IS NULL OR time_on_slide_ms >= 0),
    completed_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (student_id, slide_id),
    UNIQUE (request_id)
);

CREATE INDEX slide_completions_session_idx
    ON learning.slide_completions(session_id, completed_at);

-- Append-only xAPI-shaped statement log. Deterministic triggers only; the LLM
-- never owns tracking state. Rollups are replayable projections of this table.
CREATE TABLE learning.learning_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id uuid NOT NULL REFERENCES core.students(id) ON DELETE CASCADE,
    session_id uuid NOT NULL REFERENCES core.sessions(id) ON DELETE CASCADE,
    actor jsonb NOT NULL,
    verb jsonb NOT NULL,
    object jsonb NOT NULL,
    result jsonb,
    context jsonb NOT NULL DEFAULT '{}'::jsonb,
    request_id text NOT NULL CHECK (length(request_id) > 0),
    occurred_at timestamptz NOT NULL DEFAULT now(),
    recorded_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (session_id, request_id),
    CHECK (jsonb_typeof(actor) = 'object'),
    CHECK (jsonb_typeof(verb) = 'object'),
    CHECK (jsonb_typeof(object) = 'object'),
    CHECK (result IS NULL OR jsonb_typeof(result) = 'object'),
    CHECK (jsonb_typeof(context) = 'object')
);

CREATE INDEX learning_events_session_time_idx
    ON learning.learning_events(session_id, occurred_at);
CREATE INDEX learning_events_verb_idx
    ON learning.learning_events((verb ->> 'id'), occurred_at);

-- Append-only: corrections are represented by a later event.
CREATE FUNCTION learning.reject_learning_event_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'learning.learning_events is append-only';
END;
$$;
CREATE TRIGGER learning_events_immutable
    BEFORE UPDATE OR DELETE ON learning.learning_events
    FOR EACH ROW EXECUTE FUNCTION learning.reject_learning_event_mutation();

CREATE TABLE learning.progress_rollups (
    session_id uuid NOT NULL REFERENCES core.sessions(id) ON DELETE CASCADE,
    module_id uuid NOT NULL REFERENCES learning.modules(id) ON DELETE CASCADE,
    slides_completed integer NOT NULL DEFAULT 0 CHECK (slides_completed >= 0),
    slides_total integer NOT NULL DEFAULT 0 CHECK (slides_total >= 0),
    time_on_module_ms bigint NOT NULL DEFAULT 0 CHECK (time_on_module_ms >= 0),
    last_slide_id uuid REFERENCES learning.slides(id) ON DELETE SET NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (session_id, module_id)
);

COMMIT;
