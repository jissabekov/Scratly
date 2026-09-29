BEGIN;

-- Plan 01 W1.4: the matcher expands free-form student topics onto coarse
-- buckets; the catalog must carry those buckets so every persona archetype has
-- >=2 feasible, topic-aligned options without web research.

UPDATE matching.opportunities SET topics = topics || ARRAY['science','technology','environment']
WHERE key = 'seattle_air_quality_map_v1' AND NOT topics @> ARRAY['science'];

UPDATE matching.opportunities
    SET topics = array_append(topics, 'environment')
 WHERE key = 'seattle_open_data_story_v1' AND NOT topics @> ARRAY['environment'];

UPDATE matching.opportunities SET topics = topics || ARRAY['technology']
WHERE key IN ('bay_area_transit_prototype_v1', 'remote_open_source_docs_v1')
  AND NOT topics @> ARRAY['technology'];

UPDATE matching.opportunities SET topics = topics || ARRAY['science']
WHERE key = 'bay_area_climate_field_guide_v1' AND NOT topics @> ARRAY['science'];

UPDATE matching.opportunities SET topics = topics || ARRAY['technology']
WHERE key = 'austin_community_sensor_v1' AND NOT topics @> ARRAY['technology'];

INSERT INTO matching.opportunities
    (key, title, summary, topics, work_modes, motivations, geo_regions, geo_places, hard_constraints, source_url)
VALUES
    (
        'neighborhood_sensor_project_v1',
        'Neighborhood Sensor Data Project',
        'Investigate a local environmental question with low-cost sensors and communicate what the data shows.',
        ARRAY['science', 'technology', 'environment', 'community_civic'],
        ARRAY['investigate', 'build', 'communicate', 'organize'],
        ARRAY['discovery_mastery', 'impact_usefulness'],
        ARRAY['remote_ok'],
        ARRAY[]::text[],
        '{}'::jsonb,
        'https://example.org/opportunities/neighborhood-sensors'
    ),
    (
        'hands_on_repair_series_v1',
        'Hands-On Repair Series',
        'Diagnose and repair everyday devices or bikes with supervision, then document what fixed each fault.',
        ARRAY['repair_build', 'technology', 'science'],
        ARRAY['build', 'investigate', 'organize'],
        ARRAY['discovery_mastery', 'impact_usefulness'],
        ARRAY['remote_ok'],
        ARRAY[]::text[],
        '{}'::jsonb,
        'https://example.org/opportunities/hands-on-repair'
    ),
    (
        'community_media_studio_v1',
        'Community Media Story Studio',
        'Photograph, record, and publish short stories about people and places your school cares about.',
        ARRAY['arts_media', 'community_civic', 'writing'],
        ARRAY['communicate', 'organize', 'build'],
        ARRAY['impact_usefulness', 'recognition_influence'],
        ARRAY['remote_ok'],
        ARRAY[]::text[],
        '{}'::jsonb,
        'https://example.org/opportunities/media-studio'
    ),
    (
        'food_systems_project_v1',
        'Family Food Systems Project',
        'Improve how a small food business runs day to day and communicate the before/after with real examples.',
        ARRAY['food', 'community_civic', 'business'],
        ARRAY['organize', 'build', 'communicate'],
        ARRAY['belonging_responsibility', 'impact_usefulness'],
        ARRAY['remote_ok'],
        ARRAY[]::text[],
        '{}'::jsonb,
        'https://example.org/opportunities/food-systems'
    ),
    (
        'games_and_learning_lab_v1',
        'Games and Learning Lab',
        'Design and playtest a small game that teaches something, then revise it from real playtest notes.',
        ARRAY['games', 'science', 'technology', 'humanities'],
        ARRAY['build', 'investigate', 'communicate'],
        ARRAY['discovery_mastery', 'impact_usefulness'],
        ARRAY['remote_ok'],
        ARRAY[]::text[],
        '{}'::jsonb,
        'https://example.org/opportunities/games-lab'
    ),
    (
        'music_production_project_v1',
        'Music Production Project',
        'Produce and polish a short original track or beat, then gather listener feedback and revise.',
        ARRAY['arts_media', 'technology'],
        ARRAY['build', 'communicate'],
        ARRAY['discovery_mastery', 'recognition_influence'],
        ARRAY['remote_ok'],
        ARRAY[]::text[],
        '{}'::jsonb,
        'https://example.org/opportunities/music-production'
    ),
    (
        'digital_art_portfolio_v1',
        'Digital Art Portfolio Project',
        'Grow a focused digital art portfolio with a clear theme and share it in a low-pressure showcase.',
        ARRAY['arts_media', 'technology', 'community_civic'],
        ARRAY['build', 'communicate', 'organize'],
        ARRAY['discovery_mastery', 'recognition_influence'],
        ARRAY['remote_ok'],
        ARRAY[]::text[],
        '{}'::jsonb,
        'https://example.org/opportunities/digital-art'
    ),
    (
        'civic_engagement_project_v1',
        'Youth Civic Engagement Project',
        'Coordinate people and communicate a visible benefit for a local group you care about.',
        ARRAY['community_civic', 'writing', 'food'],
        ARRAY['organize', 'communicate', 'investigate'],
        ARRAY['belonging_responsibility', 'impact_usefulness'],
        ARRAY['remote_ok'],
        ARRAY[]::text[],
        '{}'::jsonb,
        'https://example.org/opportunities/civic-engagement'
    ),
    (
        'green_action_project_v1',
        'Local Environmental Action Project',
        'Investigate a nearby environmental question, run a small cleanup or monitoring effort, and report results.',
        ARRAY['environment', 'science', 'community_civic'],
        ARRAY['investigate', 'organize', 'communicate'],
        ARRAY['impact_usefulness', 'discovery_mastery'],
        ARRAY['remote_ok'],
        ARRAY[]::text[],
        '{}'::jsonb,
        'https://example.org/opportunities/green-action'
    ),
    (
        'code_for_good_project_v1',
        'Coding for Good Starter',
        'Build a small, testable tech helper for a club, family, or community need, with teacher support.',
        ARRAY['technology', 'community_civic', 'science'],
        ARRAY['build', 'investigate', 'communicate'],
        ARRAY['discovery_mastery', 'impact_usefulness'],
        ARRAY['remote_ok'],
        ARRAY[]::text[],
        '{}'::jsonb,
        'https://example.org/opportunities/code-for-good'
    );

COMMIT;
