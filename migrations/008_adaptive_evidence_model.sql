BEGIN;

-- Adaptive evidence model (idempotent): evidence typing, curated-intent metadata,
-- and a teacher-only project-fit distribution table.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM pg_type t
          JOIN pg_namespace n ON n.oid = t.typnamespace
         WHERE n.nspname = 'assessment'
           AND t.typname = 'evidence_type'
    ) THEN
        CREATE TYPE assessment.evidence_type AS ENUM (
            'repeated_behavior', 'behavioral_example', 'forced_tradeoff',
            'stated_preference', 'self_description', 'hypothetical'
        );
    END IF;
END $$;

ALTER TABLE assessment.evidence
  ADD COLUMN IF NOT EXISTS evidence_type assessment.evidence_type NOT NULL DEFAULT 'stated_preference',
  ADD COLUMN IF NOT EXISTS extraction_confidence numeric(4,3) NOT NULL DEFAULT .500 CHECK(extraction_confidence BETWEEN 0 AND 1),
  ADD COLUMN IF NOT EXISTS context_tags text[] NOT NULL DEFAULT '{}';

ALTER TABLE assessment.question_intents
  ADD COLUMN IF NOT EXISTS question_class text NOT NULL DEFAULT 'discover',
  ADD COLUMN IF NOT EXISTS purpose text NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS target_dimensions text[] NOT NULL DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS allowed_formats text[] NOT NULL DEFAULT ARRAY['open'],
  ADD COLUMN IF NOT EXISTS prerequisites jsonb NOT NULL DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS avoid_patterns text[] NOT NULL DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS requires_behavioral_followup boolean NOT NULL DEFAULT false;

CREATE TABLE IF NOT EXISTS assessment.project_fit_distributions(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id uuid NOT NULL REFERENCES core.sessions(id) ON DELETE CASCADE,
  profile_snapshot_id uuid NOT NULL REFERENCES assessment.profile_snapshots(id),
  probabilities jsonb NOT NULL,
  entropy numeric(8,6) NOT NULL CHECK(entropy >= 0),
  top_probability numeric(7,6) NOT NULL CHECK(top_probability BETWEEN 0 AND 1),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(session_id, profile_snapshot_id)
);

COMMIT;
