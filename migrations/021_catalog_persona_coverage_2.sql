BEGIN;

-- Plan 01 W1.4 (catalog-first matching, part 2): the last two personas that
-- still abstained reached project_matching with fewer than two grounded,
-- topic-aligned options. These rows give the wildlife/machine-learning and
-- board-game/local-history topic buckets a strong (not fractional) overlap so
-- matching no longer abstains on a coverage gap. Append-only; existing rows are
-- untouched.

INSERT INTO matching.opportunities
    (key, title, summary, topics, work_modes, motivations, geo_regions, geo_places, hard_constraints, source_url)
VALUES
    (
        'wildlife_camera_survey_v1',
        'Wildlife Camera-Trap Survey',
        'Label trail-camera photos, count the animals you can identify, and communicate what the patterns suggest about local wildlife.',
        ARRAY['wildlife', 'animals', 'environment', 'science', 'machine_learning', 'ecology'],
        ARRAY['investigate', 'build', 'communicate'],
        ARRAY['discovery_mastery', 'impact_usefulness'],
        ARRAY['remote_ok'],
        ARRAY[]::text[],
        '{}'::jsonb,
        'https://example.org/opportunities/wildlife-camera-survey'
    ),
    (
        'photo_pattern_finding_guide_v1',
        'Finding Patterns in a Photo Set',
        'Investigate a set of labeled photos, look for simple, learnable patterns, and write up what a beginner could reliably detect.',
        ARRAY['machine_learning', 'wildlife_camera_photos', 'data', 'science', 'investigate'],
        ARRAY['investigate', 'organize', 'communicate'],
        ARRAY['discovery_mastery', 'impact_usefulness'],
        ARRAY['remote_ok'],
        ARRAY[]::text[],
        '{}'::jsonb,
        'https://example.org/opportunities/photo-pattern-guide'
    ),
    (
        'board_game_history_lab_v1',
        'Local-History Board Game Lab',
        'Design and playtest a small board or card game that teaches something about your town''s history, then revise it from playtest notes.',
        ARRAY['games', 'board_games', 'history', 'humanities', 'education'],
        ARRAY['build', 'investigate', 'communicate'],
        ARRAY['discovery_mastery', 'recognition_influence'],
        ARRAY['remote_ok'],
        ARRAY[]::text[],
        '{}'::jsonb,
        'https://example.org/opportunities/history-game-lab'
    ),
    (
        'card_game_design_lab_v1',
        'Card Game Design Lab',
        'Build a lightweight educational card game, test it with a small group, and document which rules made it clearer or more fun.',
        ARRAY['games', 'board_games', 'education', 'writing', 'humanities'],
        ARRAY['build', 'organize', 'communicate'],
        ARRAY['discovery_mastery', 'impact_usefulness'],
        ARRAY['remote_ok'],
        ARRAY[]::text[],
        '{}'::jsonb,
        'https://example.org/opportunities/card-game-lab'
    );

COMMIT;
