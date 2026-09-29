BEGIN;

-- Plan 01 W1.3 (catalog-first matching): extend the curated catalog with
-- archetype × geo spread so persona-relevant, feasibility-passing offers exist
-- from the catalog alone, without web research. Append-only; existing rows
-- stay untouched.

INSERT INTO matching.opportunities
    (key, title, summary, topics, work_modes, motivations, geo_regions, geo_places, hard_constraints, source_url)
VALUES
    (
        'family_food_stall_order_kit_v1',
        'Bilingual Order-Flow Kit for a Family Food Stall',
        'Design a bilingual order-flow kit — color cards, checklists, and a before/after rush comparison — for a family food stall.',
        ARRAY['food_service', 'cooking', 'organization', 'bilingual', 'community', 'process_improvement'],
        ARRAY['organize', 'build', 'communicate'],
        ARRAY['belonging_responsibility', 'impact_usefulness'],
        ARRAY['el_paso_metro', 'remote_ok'],
        ARRAY['el_paso'],
        '{}'::jsonb,
        'https://example.org/opportunities/bilingual-order-flow-kit'
    ),
    (
        'family_recipe_archive_v1',
        'Bilingual Family Recipe Archive and Tasting Night',
        'Collect family recipes with bilingual steps, design printable cards, and host a small tasting event.',
        ARRAY['cooking', 'food_service', 'culture', 'community', 'bilingual'],
        ARRAY['organize', 'build', 'communicate'],
        ARRAY['belonging_responsibility', 'impact_usefulness'],
        ARRAY['el_paso_metro', 'remote_ok'],
        ARRAY[]::text[],
        '{}'::jsonb,
        'https://example.org/opportunities/family-recipe-archive'
    ),
    (
        'stall_flow_observation_study_v1',
        'Stall Rush Flow Study',
        'Observe a busy food stall, time the order flow, and communicate one process improvement with evidence.',
        ARRAY['food_service', 'process_improvement', 'organization', 'community'],
        ARRAY['investigate', 'organize', 'communicate'],
        ARRAY['impact_usefulness', 'discovery_mastery'],
        ARRAY['remote_ok'],
        ARRAY[]::text[],
        '{}'::jsonb,
        'https://example.org/opportunities/stall-flow-study'
    ),
    (
        'neighborhood_photo_story_v1',
        'Neighborhood Photo Story Series',
        'Photograph and publish a short photo story series about people or places your neighborhood overlooks.',
        ARRAY['photography', 'storytelling', 'media', 'community', 'basketball'],
        ARRAY['communicate', 'organize', 'build'],
        ARRAY['impact_usefulness', 'recognition_influence'],
        ARRAY['baltimore_metro', 'remote_ok'],
        ARRAY['baltimore'],
        '{}'::jsonb,
        'https://example.org/opportunities/photo-story-series'
    ),
    (
        'team_season_mini_profiles_v1',
        'Team Story Mini Profiles',
        'Produce three short photo-and-audio profiles of local team members and share them with the community.',
        ARRAY['photography', 'storytelling', 'basketball', 'community', 'media'],
        ARRAY['communicate', 'build', 'organize'],
        ARRAY['impact_usefulness', 'recognition_influence'],
        ARRAY['baltimore_metro', 'remote_ok'],
        ARRAY[]::text[],
        '{}'::jsonb,
        'https://example.org/opportunities/team-story-profiles'
    ),
    (
        'community_audio_story_walk_v1',
        'Community Audio Story Walk',
        'Record short neighborhood audio stories and organize them into a walkable or scannable listening tour.',
        ARRAY['media', 'storytelling', 'community', 'writing'],
        ARRAY['communicate', 'organize', 'build'],
        ARRAY['impact_usefulness', 'belonging_responsibility'],
        ARRAY['remote_ok'],
        ARRAY[]::text[],
        '{}'::jsonb,
        'https://example.org/opportunities/audio-listening-tour'
    ),
    (
        'practical_repair_workshop_v1',
        'Practical Repair Workshop Series',
        'Troubleshoot and repair everyday items, document each fix, and communicate a repair decision guide.',
        ARRAY['repair', 'bikes', 'troubleshooting', 'controllers', 'electronics'],
        ARRAY['build', 'investigate', 'organize'],
        ARRAY['discovery_mastery', 'impact_usefulness'],
        ARRAY['milwaukee_metro', 'remote_ok'],
        ARRAY['milwaukee'],
        '{}'::jsonb,
        'https://example.org/opportunities/repair-workshop'
    ),
    (
        'device_diagnostics_guide_v1',
        'Device Diagnostics Decision Guide',
        'Build a step-by-step diagnostic guide for common electronics faults and test it on real repairs.',
        ARRAY['repair', 'controllers', 'electronics', 'technology', 'troubleshooting'],
        ARRAY['build', 'investigate', 'communicate'],
        ARRAY['discovery_mastery', 'impact_usefulness'],
        ARRAY['remote_ok'],
        ARRAY[]::text[],
        '{}'::jsonb,
        'https://example.org/opportunities/device-diagnostics'
    ),
    (
        'repair_case_zine_v1',
        'Supervised Repair Case Log',
        'Run supervised repair cases in a school workshop and communicate before/after evidence safely.',
        ARRAY['repair', 'bikes', 'electronics', 'education', 'community'],
        ARRAY['build', 'investigate', 'organize'],
        ARRAY['belonging_responsibility', 'discovery_mastery'],
        ARRAY['milwaukee_metro', 'remote_ok'],
        ARRAY['milwaukee'],
        '{}'::jsonb,
        'https://example.org/opportunities/repair-cases'
    ),
    (
        'chemistry_demo_kit_v1',
        'Chemistry Demonstration Kit for Younger Students',
        'Investigate safe classroom chemistry demos, build a kit, and communicate the science behind each one.',
        ARRAY['chemistry', 'science', 'education', 'demos'],
        ARRAY['build', 'investigate', 'communicate'],
        ARRAY['discovery_mastery', 'impact_usefulness'],
        ARRAY['remote_ok'],
        ARRAY[]::text[],
        '{}'::jsonb,
        'https://example.org/opportunities/chemistry-demo-kit'
    ),
    (
        'local_water_quality_monitor_v1',
        'Local Water Quality Monitoring Project',
        'Investigate a nearby creek or tap water, organize the readings, and communicate what they mean.',
        ARRAY['water_quality', 'environmental_science', 'science', 'community', 'environment'],
        ARRAY['investigate', 'build', 'communicate'],
        ARRAY['discovery_mastery', 'impact_usefulness'],
        ARRAY['remote_ok'],
        ARRAY[]::text[],
        '{}'::jsonb,
        'https://example.org/opportunities/water-quality'
    ),
    (
        'community_event_organizer_kit_v1',
        'Community Event Flow Kit',
        'Organize a small community event end to end: signage, schedules, and a simple feedback loop.',
        ARRAY['organization', 'community', 'event_planning', 'communication'],
        ARRAY['organize', 'communicate', 'build'],
        ARRAY['belonging_responsibility', 'impact_usefulness'],
        ARRAY['remote_ok'],
        ARRAY[]::text[],
        '{}'::jsonb,
        'https://example.org/opportunities/event-flow-kit'
    );

COMMIT;
