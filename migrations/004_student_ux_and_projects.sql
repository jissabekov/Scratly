BEGIN;

-- Decision events for student Q&A, elicitation, location, research, projects.
ALTER TYPE audit.decision_event_type ADD VALUE IF NOT EXISTS 'turn_intent_classified';
ALTER TYPE audit.decision_event_type ADD VALUE IF NOT EXISTS 'student_answer_written';
ALTER TYPE audit.decision_event_type ADD VALUE IF NOT EXISTS 'student_answer_refused';
ALTER TYPE audit.decision_event_type ADD VALUE IF NOT EXISTS 'answer_thinness_evaluated';
ALTER TYPE audit.decision_event_type ADD VALUE IF NOT EXISTS 'elicitation_selected';
ALTER TYPE audit.decision_event_type ADD VALUE IF NOT EXISTS 'elicitation_exhausted';
ALTER TYPE audit.decision_event_type ADD VALUE IF NOT EXISTS 'location_readiness_checked';
ALTER TYPE audit.decision_event_type ADD VALUE IF NOT EXISTS 'profile_review_completed';
ALTER TYPE audit.decision_event_type ADD VALUE IF NOT EXISTS 'research_started';
ALTER TYPE audit.decision_event_type ADD VALUE IF NOT EXISTS 'research_findings_stored';
ALTER TYPE audit.decision_event_type ADD VALUE IF NOT EXISTS 'research_failed';
ALTER TYPE audit.decision_event_type ADD VALUE IF NOT EXISTS 'opportunities_matched';
ALTER TYPE audit.decision_event_type ADD VALUE IF NOT EXISTS 'project_composed';
ALTER TYPE audit.decision_event_type ADD VALUE IF NOT EXISTS 'project_citation_rejected';
ALTER TYPE audit.decision_event_type ADD VALUE IF NOT EXISTS 'project_fits_persisted';
ALTER TYPE audit.decision_event_type ADD VALUE IF NOT EXISTS 'evidence_extraction_skipped';

CREATE TYPE conversation.assistant_message_kind AS ENUM (
    'assessment_question',
    'student_answer',
    'refusal',
    'elicitation',
    'profile_review',
    'project_offer'
);

ALTER TABLE conversation.messages
    ADD COLUMN IF NOT EXISTS message_kind conversation.assistant_message_kind;

ALTER TABLE core.sessions
    ADD COLUMN IF NOT EXISTS consecutive_student_questions smallint NOT NULL DEFAULT 0
        CHECK (consecutive_student_questions >= 0),
    ADD COLUMN IF NOT EXISTS elicitation_attempts_for_target smallint NOT NULL DEFAULT 0
        CHECK (elicitation_attempts_for_target >= 0),
    ADD COLUMN IF NOT EXISTS elicitation_target_key text,
    ADD COLUMN IF NOT EXISTS profile_reviewed boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS matching_completed boolean NOT NULL DEFAULT false;

INSERT INTO assessment.question_intents(key, priority, fallback_template)
VALUES
    (
        'elicitation',
        4,
        'Which of these is closer: option A, option B, or something else?'
    ),
    (
        'location_constraint',
        2,
        'Where are you based (city or region), or is remote work fine?'
    )
ON CONFLICT (key) DO NOTHING;

-- Update required_hard_variable fallback to mention location when useful.
UPDATE assessment.question_intents
   SET fallback_template = 'Are there any non-negotiable constraints — including where you are based — that your project must meet?'
 WHERE key = 'required_hard_variable';

CREATE TABLE matching.opportunities (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    key text UNIQUE NOT NULL,
    title text NOT NULL,
    summary text NOT NULL,
    topics text[] NOT NULL DEFAULT '{}',
    work_modes text[] NOT NULL DEFAULT '{}',
    motivations text[] NOT NULL DEFAULT '{}',
    geo_regions text[] NOT NULL DEFAULT '{}',
    geo_places text[] NOT NULL DEFAULT '{}',
    hard_constraints jsonb NOT NULL DEFAULT '{}',
    source_url text,
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TYPE matching.research_status AS ENUM (
    'pending',
    'succeeded',
    'failed',
    'skipped'
);

CREATE TABLE matching.research_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id uuid NOT NULL REFERENCES core.sessions(id) ON DELETE CASCADE,
    query text NOT NULL,
    user_location jsonb NOT NULL DEFAULT '{}',
    status matching.research_status NOT NULL DEFAULT 'pending',
    llm_run_id uuid REFERENCES audit.llm_runs(id),
    error_type text,
    created_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz
);

CREATE TABLE matching.research_findings (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    research_run_id uuid NOT NULL REFERENCES matching.research_runs(id) ON DELETE CASCADE,
    url text NOT NULL,
    title text NOT NULL DEFAULT '',
    snippet text NOT NULL DEFAULT '',
    publisher text,
    rank smallint NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (research_run_id, url)
);

CREATE TABLE matching.generated_projects (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id uuid NOT NULL REFERENCES core.sessions(id) ON DELETE CASCADE,
    title text NOT NULL,
    summary text NOT NULL,
    payload jsonb NOT NULL DEFAULT '{}',
    composer_version text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TYPE matching.citation_kind AS ENUM ('opportunity', 'research_finding');

CREATE TABLE matching.generated_project_citations (
    project_id uuid NOT NULL REFERENCES matching.generated_projects(id) ON DELETE CASCADE,
    kind matching.citation_kind NOT NULL,
    ref_id uuid NOT NULL,
    PRIMARY KEY (project_id, kind, ref_id)
);

ALTER TABLE matching.project_fits
    ADD COLUMN IF NOT EXISTS opportunity_id uuid REFERENCES matching.opportunities(id),
    ADD COLUMN IF NOT EXISTS generated_project_id uuid REFERENCES matching.generated_projects(id),
    ADD COLUMN IF NOT EXISTS algorithm_version text NOT NULL DEFAULT 'v1';

-- Drop old uniqueness if it blocks opportunity fits; allow multiple fit types.
ALTER TABLE matching.project_fits DROP CONSTRAINT IF EXISTS project_fits_session_id_archetype_id_profile_snapshot_id_key;
CREATE UNIQUE INDEX IF NOT EXISTS project_fits_session_archetype_snapshot_uidx
    ON matching.project_fits(session_id, archetype_id, profile_snapshot_id)
    WHERE archetype_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS project_fits_session_opportunity_snapshot_uidx
    ON matching.project_fits(session_id, opportunity_id, profile_snapshot_id)
    WHERE opportunity_id IS NOT NULL;

INSERT INTO matching.opportunities
    (key, title, summary, topics, work_modes, motivations, geo_regions, geo_places, hard_constraints, source_url)
VALUES
    (
        'seattle_air_quality_map',
        'Seattle Neighborhood Air Quality Map',
        'Build a small Python pipeline that maps local air-quality readings for neighbors.',
        ARRAY['data', 'community', 'environment', 'science'],
        ARRAY['analysis', 'building', 'research'],
        ARRAY['impact', 'curiosity'],
        ARRAY['seattle_metro'],
        ARRAY['seattle'],
        '{}'::jsonb,
        'https://example.org/opportunities/seattle-air-quality'
    ),
    (
        'seattle_open_data_story',
        'Seattle Open Data Story',
        'Turn a city open-data set into a short community story with charts.',
        ARRAY['data', 'community', 'storytelling'],
        ARRAY['analysis', 'storytelling', 'writing'],
        ARRAY['impact', 'curiosity'],
        ARRAY['seattle_metro'],
        ARRAY['seattle', 'bellevue'],
        '{}'::jsonb,
        'https://example.org/opportunities/seattle-open-data'
    ),
    (
        'bay_area_transit_prototype',
        'Bay Area Transit Prototype',
        'Prototype a simple transit-helper flow for students commuting in the Bay Area.',
        ARRAY['technology', 'design', 'community'],
        ARRAY['building', 'iteration'],
        ARRAY['mastery', 'impact'],
        ARRAY['bay_area'],
        ARRAY['san_francisco', 'oakland', 'san_jose'],
        '{}'::jsonb,
        'https://example.org/opportunities/bay-transit'
    ),
    (
        'bay_area_climate_field_guide',
        'Bay Area Climate Field Guide',
        'Research and write a short field guide on a local climate or ecology topic.',
        ARRAY['science', 'environment', 'writing'],
        ARRAY['research', 'writing'],
        ARRAY['curiosity', 'impact'],
        ARRAY['bay_area'],
        ARRAY['berkeley', 'oakland'],
        '{}'::jsonb,
        'https://example.org/opportunities/bay-climate'
    ),
    (
        'austin_community_sensor',
        'Austin Community Sensor Kit',
        'Design a low-cost sensor kit and explain readings for a local neighborhood.',
        ARRAY['science', 'technology', 'community'],
        ARRAY['building', 'research'],
        ARRAY['curiosity', 'impact'],
        ARRAY['austin_metro'],
        ARRAY['austin'],
        '{}'::jsonb,
        'https://example.org/opportunities/austin-sensor'
    ),
    (
        'austin_youth_civic_brief',
        'Austin Youth Civic Brief',
        'Interview stakeholders and produce a one-page civic brief on a local issue.',
        ARRAY['community', 'writing'],
        ARRAY['research', 'writing', 'storytelling'],
        ARRAY['impact', 'belonging'],
        ARRAY['austin_metro'],
        ARRAY['austin'],
        '{}'::jsonb,
        'https://example.org/opportunities/austin-civic'
    ),
    (
        'remote_open_source_docs',
        'Remote Open-Source Docs Sprint',
        'Improve documentation for an open-source tool used by students; fully remote.',
        ARRAY['technology', 'writing'],
        ARRAY['writing', 'independent', 'building'],
        ARRAY['mastery', 'autonomy'],
        ARRAY['remote_ok'],
        ARRAY[]::text[],
        '{}'::jsonb,
        'https://example.org/opportunities/remote-docs'
    ),
    (
        'remote_data_journalism',
        'Remote Data Journalism Starter',
        'Analyze a public dataset and publish a short explainable article; remote-friendly.',
        ARRAY['data', 'writing', 'community'],
        ARRAY['analysis', 'writing', 'independent'],
        ARRAY['curiosity', 'impact'],
        ARRAY['remote_ok'],
        ARRAY[]::text[],
        '{}'::jsonb,
        'https://example.org/opportunities/remote-data-journalism'
    ),
    (
        'nyc_park_usage_study',
        'NYC Park Usage Study',
        'Study park usage patterns with public data and propose one improvement.',
        ARRAY['data', 'community', 'environment'],
        ARRAY['analysis', 'research'],
        ARRAY['impact', 'curiosity'],
        ARRAY['nyc_metro'],
        ARRAY['new_york', 'brooklyn'],
        '{}'::jsonb,
        'https://example.org/opportunities/nyc-parks'
    )
ON CONFLICT (key) DO NOTHING;

COMMIT;
