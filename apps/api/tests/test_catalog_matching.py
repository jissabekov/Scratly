"""Catalog-first matching proofs (Plan 01 W1.3): personas match without research."""

from uuid import uuid4

from app.contracts import ComposedProjectPacket, ProjectCitation, ProjectComposeOutput
from app.services.opportunity_matcher import rank_opportunities
from app.services.project_citation_gate import filter_grounded_projects


def _opp(key: str, topics: list[str], modes: list[str]) -> dict:
    return {
        "id": str(uuid4()),
        "key": key,
        "title": key.replace("_", " ").title(),
        "summary": "A curated local opportunity.",
        "topics": topics,
        "work_modes": modes,
        "motivations": ["impact_usefulness", "belonging_responsibility"],
        "geo_regions": ["remote_ok"],
        "geo_places": [],
        "hard_constraints": {},
        "source_url": "https://example.org/opportunity",
    }


_CATALOG = [
    _opp(
        "stall_order_flow_kit_v1",
        ["food_service", "cooking", "organization", "community"],
        ["organize", "build", "communicate"],
    ),
    _opp(
        "family_recipe_cards_v1",
        ["cooking", "family", "bilingual", "community"],
        ["organize", "communicate"],
    ),
    _opp(
        "neighborhood_photo_story_v1",
        ["photography", "storytelling", "basketball", "community"],
        ["communicate", "organize"],
    ),
    _opp(
        "community_media_desk_v1",
        ["photography", "media", "storytelling", "community"],
        ["communicate", "build"],
    ),
    _opp(
        "repair_workshop_log_v1",
        ["bikes", "bike_repair", "repair", "controllers"],
        ["build", "investigate"],
    ),
    _opp(
        "device_diagnostics_lab_v1",
        ["bikes", "controllers", "electronics", "troubleshooting", "repair"],
        ["build", "investigate"],
    ),
]


def test_catalog_alone_yields_two_options_per_sim_persona():
    luz = {"topics": ["cooking", "food_service"], "work_modes": {"organize": 3, "build": 2}}
    nia = {"topics": ["photography", "basketball"], "work_modes": {"communicate": 3}}
    eli = {"topics": ["bikes", "bike_repair"], "work_modes": {"build": 4}}
    for persona in (luz, nia, eli):
        eligible = [m for m in rank_opportunities(persona, _CATALOG) if m.eligible]
        assert len(eligible) >= 2, (
            persona,
            [(m.opportunity_key, m.failed_constraints) for m in eligible],
        )


def test_citation_gate_still_rejects_topic_mismatch():
    packet = ComposedProjectPacket(
        title="Unrelated",
        summary="s",
        topic_keys=["space"],
        work_mode_keys=[],
        motivation_keys=[],
        citations=[ProjectCitation(kind="opportunity", id=uuid4())],
    )
    accepted, rejected = filter_grounded_projects(
        ProjectComposeOutput(projects=[packet]),
        opportunity_ids={uuid4()},
        research_finding_ids=set(),
        profile_topics={"cooking"},
    )
    assert not accepted
    assert rejected[0]["reason"] == "profile_topic_mismatch"
