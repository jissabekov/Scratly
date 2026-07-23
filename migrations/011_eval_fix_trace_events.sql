-- Trace events for eval fix plan (W1–W3, W2 stage gate, geo fallback).

ALTER TYPE audit.decision_event_type ADD VALUE IF NOT EXISTS 'question_target_blocked';
ALTER TYPE audit.decision_event_type ADD VALUE IF NOT EXISTS 'stage_gate_evaluated';
ALTER TYPE audit.decision_event_type ADD VALUE IF NOT EXISTS 'elicitation_rephrase';
ALTER TYPE audit.decision_event_type ADD VALUE IF NOT EXISTS 'elicitation_skipped_not_recoverable';
ALTER TYPE audit.decision_event_type ADD VALUE IF NOT EXISTS 'geo_inferred_from_text';
