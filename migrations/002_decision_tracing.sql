BEGIN;

CREATE TYPE audit.decision_event_type AS ENUM (
    'turn_started',
    'evidence_proposed',
    'evidence_validated',
    'profile_reduced',
    'contradiction_evaluated',
    'stage_derived',
    'question_target_selected',
    'question_written',
    'question_fallback_used',
    'turn_completed'
);

CREATE TABLE audit.decision_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id uuid NOT NULL REFERENCES core.sessions(id) ON DELETE CASCADE,
    turn_id uuid NOT NULL REFERENCES conversation.turns(id) ON DELETE CASCADE,
    correlation_id uuid NOT NULL,
    sequence integer NOT NULL CHECK (sequence > 0),
    event_type audit.decision_event_type NOT NULL,
    component text NOT NULL,
    component_version text NOT NULL,
    decision_summary text NOT NULL CHECK (length(decision_summary) > 0),
    reason_code text NOT NULL CHECK (length(reason_code) > 0),
    inputs jsonb NOT NULL DEFAULT '{}',
    outputs jsonb NOT NULL DEFAULT '{}',
    entity_refs jsonb NOT NULL DEFAULT '{}',
    llm_run_id uuid REFERENCES audit.llm_runs(id),
    duration_ms integer CHECK (duration_ms IS NULL OR duration_ms >= 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (turn_id, sequence),
    CHECK (jsonb_typeof(inputs) = 'object'),
    CHECK (jsonb_typeof(outputs) = 'object'),
    CHECK (jsonb_typeof(entity_refs) = 'object')
);

CREATE INDEX decision_events_session_time_idx
    ON audit.decision_events(session_id, created_at, sequence);
CREATE INDEX decision_events_correlation_idx
    ON audit.decision_events(correlation_id, sequence);
CREATE INDEX decision_events_reason_idx
    ON audit.decision_events(reason_code, created_at);

-- Decision history is append-only: corrections are represented by a later event.
CREATE FUNCTION audit.reject_decision_event_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'audit.decision_events is append-only';
END;
$$;
CREATE TRIGGER decision_events_immutable
    BEFORE UPDATE OR DELETE ON audit.decision_events
    FOR EACH ROW EXECUTE FUNCTION audit.reject_decision_event_mutation();

COMMIT;
