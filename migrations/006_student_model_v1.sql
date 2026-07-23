BEGIN;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
          FROM pg_type t
          JOIN pg_namespace n ON n.oid = t.typnamespace
          JOIN pg_enum e ON e.enumtypid = t.oid
         WHERE n.nspname = 'assessment'
           AND t.typname = 'dimension_status'
           AND e.enumlabel = 'established'
    ) THEN
        EXECUTE 'ALTER TYPE assessment.dimension_status RENAME VALUE ''established'' TO ''supported''';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_type t
          JOIN pg_namespace n ON n.oid = t.typnamespace
          JOIN pg_enum e ON e.enumtypid = t.oid
         WHERE n.nspname = 'assessment'
           AND t.typname = 'dimension_status'
           AND e.enumlabel = 'contested'
    ) THEN
        EXECUTE 'ALTER TYPE assessment.dimension_status RENAME VALUE ''contested'' TO ''contradicted''';
    END IF;
END $$;

ALTER TABLE assessment.evidence
    ADD COLUMN IF NOT EXISTS score_band smallint
        CHECK (score_band IS NULL OR score_band BETWEEN 0 AND 4);

DELETE FROM assessment.questions
 WHERE target_key IN ('collaboration', 'challenge', 'impact');

DELETE FROM assessment.coverage
 WHERE dimension_id IN (
    SELECT id FROM assessment.dimensions
     WHERE key IN ('collaboration', 'challenge', 'impact')
 );

DELETE FROM assessment.profile_changes
 WHERE dimension_id IN (
    SELECT id FROM assessment.dimensions
     WHERE key IN ('collaboration', 'challenge', 'impact')
 );

DELETE FROM assessment.contradiction_evidence ce
 USING assessment.contradictions c
 JOIN assessment.dimensions d ON d.id = c.dimension_id
 WHERE ce.contradiction_id = c.id
   AND d.key IN ('collaboration', 'challenge', 'impact');

DELETE FROM assessment.contradictions
 WHERE dimension_id IN (
    SELECT id FROM assessment.dimensions
     WHERE key IN ('collaboration', 'challenge', 'impact')
 );

DELETE FROM assessment.evidence
 WHERE dimension_id IN (
    SELECT id FROM assessment.dimensions
     WHERE key IN ('collaboration', 'challenge', 'impact')
 );

DELETE FROM assessment.dimensions
 WHERE key IN ('collaboration', 'challenge', 'impact');

UPDATE assessment.dimensions
   SET ordinal = ordinal + 100;

INSERT INTO assessment.dimensions(key, label, required, ordinal)
VALUES
    ('topics', 'Topic interests', true, 1),
    ('work_mode', 'Work mode', true, 2),
    ('motivation', 'Motivation', true, 3),
    ('capability', 'Capabilities', false, 4),
    ('constraints', 'Constraints', true, 5),
    ('execution', 'Execution', true, 6),
    ('assets', 'Assets', false, 7)
ON CONFLICT (key) DO UPDATE
SET label = EXCLUDED.label,
    required = EXCLUDED.required,
    ordinal = EXCLUDED.ordinal;

DELETE FROM assessment.motivation_values;

INSERT INTO assessment.motivation_values(key, label)
VALUES
    ('discovery_mastery', 'Discovery / Mastery'),
    ('competition_achievement', 'Competition / Achievement'),
    ('impact_usefulness', 'Impact / Usefulness'),
    ('recognition_influence', 'Recognition / Influence'),
    ('belonging_responsibility', 'Belonging / Responsibility');

UPDATE assessment.question_intents
   SET fallback_template = 'I heard two different signals. Which one feels more true for you right now?'
 WHERE key = 'contradiction';

UPDATE assessment.question_intents
   SET fallback_template = 'What practical constraints should I keep in mind, like location, schedule, or tools?'
 WHERE key = 'required_hard_variable';

UPDATE assessment.question_intents
   SET fallback_template = 'What topics or kinds of projects pull you in most right now?'
 WHERE key = 'project_critical_unknown';

UPDATE assessment.question_intents
   SET fallback_template = 'Could you share a concrete example so I can tell what that looks like for you?'
 WHERE key = 'provisional_dimension';

UPDATE assessment.question_intents
   SET fallback_template = 'Which way of working sounds more energizing right now: investigating, building, organizing, or communicating?'
 WHERE key = 'project_discrimination';

UPDATE assessment.question_intents
   SET fallback_template = 'Here is my read so far. What feels right, and what should I revise?'
 WHERE key = 'profile_validation';

UPDATE assessment.question_intents
   SET fallback_template = 'What city or region are you in, and is remote okay too?'
 WHERE key = 'location_constraint';

UPDATE assessment.question_intents
   SET fallback_template = 'Which of these feels closer right now, or what would you say instead?'
 WHERE key = 'elicitation';

DELETE FROM matching.project_fits;
DELETE FROM matching.opportunities;
DELETE FROM matching.project_archetypes;

INSERT INTO matching.project_archetypes
    (key, title, topics, work_modes, motivations, hard_constraints)
VALUES
    (
        'local_investigation',
        'Local Investigation Sprint',
        ARRAY['data', 'science', 'community'],
        ARRAY['investigate', 'organize'],
        ARRAY['discovery_mastery', 'impact_usefulness'],
        '{}'::jsonb
    ),
    (
        'prototype_builder',
        'Prototype Builder',
        ARRAY['technology', 'design', 'community'],
        ARRAY['build', 'investigate'],
        ARRAY['competition_achievement', 'discovery_mastery'],
        '{}'::jsonb
    ),
    (
        'community_storytelling',
        'Community Storytelling',
        ARRAY['community', 'writing', 'data'],
        ARRAY['communicate', 'organize', 'investigate'],
        ARRAY['impact_usefulness', 'recognition_influence'],
        '{"min_public_visibility": 2, "min_outreach_willingness": 1}'::jsonb
    ),
    (
        'supportive_coordination',
        'Supportive Coordination',
        ARRAY['community', 'education', 'operations'],
        ARRAY['organize', 'communicate'],
        ARRAY['belonging_responsibility', 'impact_usefulness'],
        '{"min_outreach_willingness": 2}'::jsonb
    );

INSERT INTO matching.opportunities
    (key, title, summary, topics, work_modes, motivations, geo_regions, geo_places, hard_constraints, source_url)
VALUES
    (
        'seattle_air_quality_map_v1',
        'Seattle Neighborhood Air Quality Map',
        'Investigate local air-quality readings, build a small pipeline, and organize the results for neighbors.',
        ARRAY['data', 'community', 'environment', 'science'],
        ARRAY['investigate', 'build', 'organize'],
        ARRAY['discovery_mastery', 'impact_usefulness'],
        ARRAY['seattle_metro'],
        ARRAY['seattle'],
        '{}'::jsonb,
        'https://example.org/opportunities/seattle-air-quality'
    ),
    (
        'seattle_open_data_story_v1',
        'Seattle Open Data Story',
        'Investigate a city dataset and communicate the findings through a short public-facing story.',
        ARRAY['data', 'community', 'writing'],
        ARRAY['investigate', 'communicate', 'organize'],
        ARRAY['impact_usefulness', 'recognition_influence'],
        ARRAY['seattle_metro'],
        ARRAY['seattle', 'bellevue'],
        '{"min_public_visibility": 2}'::jsonb,
        'https://example.org/opportunities/seattle-open-data'
    ),
    (
        'bay_area_transit_prototype_v1',
        'Bay Area Transit Prototype',
        'Build and test a simple commuter helper for students in the Bay Area.',
        ARRAY['technology', 'design', 'community'],
        ARRAY['build', 'investigate'],
        ARRAY['competition_achievement', 'impact_usefulness'],
        ARRAY['bay_area'],
        ARRAY['san_francisco', 'oakland', 'san_jose'],
        '{}'::jsonb,
        'https://example.org/opportunities/bay-transit'
    ),
    (
        'bay_area_climate_field_guide_v1',
        'Bay Area Climate Field Guide',
        'Investigate a local ecology question and communicate the results in a short guide.',
        ARRAY['science', 'environment', 'writing'],
        ARRAY['investigate', 'communicate'],
        ARRAY['discovery_mastery', 'impact_usefulness'],
        ARRAY['bay_area'],
        ARRAY['berkeley', 'oakland'],
        '{"min_public_visibility": 1}'::jsonb,
        'https://example.org/opportunities/bay-climate'
    ),
    (
        'austin_community_sensor_v1',
        'Austin Community Sensor Kit',
        'Build a low-cost sensor kit, investigate what the readings mean, and organize the setup for others.',
        ARRAY['science', 'technology', 'community'],
        ARRAY['build', 'investigate', 'organize'],
        ARRAY['discovery_mastery', 'impact_usefulness'],
        ARRAY['austin_metro'],
        ARRAY['austin'],
        '{}'::jsonb,
        'https://example.org/opportunities/austin-sensor'
    ),
    (
        'austin_youth_civic_brief_v1',
        'Austin Youth Civic Brief',
        'Talk with local stakeholders and communicate a short civic brief on an issue that matters to students.',
        ARRAY['community', 'writing'],
        ARRAY['investigate', 'communicate', 'organize'],
        ARRAY['belonging_responsibility', 'impact_usefulness'],
        ARRAY['austin_metro'],
        ARRAY['austin'],
        '{"min_outreach_willingness": 2, "min_public_visibility": 1}'::jsonb,
        'https://example.org/opportunities/austin-civic'
    ),
    (
        'remote_open_source_docs_v1',
        'Remote Open-Source Docs Sprint',
        'Improve documentation for a student-facing open-source tool with clear structure and visible artifacts.',
        ARRAY['technology', 'writing'],
        ARRAY['communicate', 'organize', 'build'],
        ARRAY['recognition_influence', 'discovery_mastery'],
        ARRAY['remote_ok'],
        ARRAY[]::text[],
        '{"min_public_visibility": 1}'::jsonb,
        'https://example.org/opportunities/remote-docs'
    ),
    (
        'remote_data_journalism_v1',
        'Remote Data Journalism Starter',
        'Investigate a public dataset and publish a short explainable article from anywhere.',
        ARRAY['data', 'writing', 'community'],
        ARRAY['investigate', 'communicate'],
        ARRAY['recognition_influence', 'impact_usefulness'],
        ARRAY['remote_ok'],
        ARRAY[]::text[],
        '{"min_public_visibility": 2}'::jsonb,
        'https://example.org/opportunities/remote-data-journalism'
    ),
    (
        'nyc_park_usage_study_v1',
        'NYC Park Usage Study',
        'Investigate park usage patterns, organize the evidence, and communicate one improvement idea.',
        ARRAY['data', 'community', 'environment'],
        ARRAY['investigate', 'organize', 'communicate'],
        ARRAY['impact_usefulness', 'discovery_mastery'],
        ARRAY['nyc_metro'],
        ARRAY['new_york', 'brooklyn'],
        '{"min_public_visibility": 1}'::jsonb,
        'https://example.org/opportunities/nyc-parks'
    );

COMMIT;
