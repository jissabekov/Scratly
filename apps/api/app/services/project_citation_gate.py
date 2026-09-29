"""Citation gate for composed projects."""

from __future__ import annotations

from uuid import UUID

from app.contracts import ComposedProjectPacket, ProjectComposeOutput
from app.services.opportunity_matcher import topic_buckets


def filter_grounded_projects(
    output: ProjectComposeOutput,
    *,
    opportunity_ids: set[UUID],
    research_finding_ids: set[UUID],
    profile_topics: set[str] | None = None,
) -> tuple[list[ComposedProjectPacket], list[dict]]:
    """Return (accepted projects, rejection records)."""
    accepted: list[ComposedProjectPacket] = []
    rejected: list[dict] = []
    # Topic alignment uses the same coarse buckets as ``rank_opportunities``
    # (Plan 01 W1.4): the extractor emits free-form topics ("air_quality") while
    # the curated catalog carries bucket tags ("environment"). Comparing raw
    # strings rejected every catalog option the matcher had just accepted.
    profile_buckets = topic_buckets(profile_topics) if profile_topics else set()
    for project in output.projects:
        if profile_buckets and not (profile_buckets & topic_buckets(project.topic_keys)):
            rejected.append({"title": project.title, "reason": "profile_topic_mismatch"})
            continue
        if not project.citations:
            rejected.append(
                {
                    "title": project.title,
                    "reason": "missing_citations",
                }
            )
            continue
        ok = True
        for cite in project.citations:
            if cite.kind == "opportunity" and cite.id not in opportunity_ids:
                ok = False
                rejected.append(
                    {
                        "title": project.title,
                        "reason": "unknown_opportunity_citation",
                        "ref_id": str(cite.id),
                    }
                )
                break
            if cite.kind == "research_finding" and cite.id not in research_finding_ids:
                ok = False
                rejected.append(
                    {
                        "title": project.title,
                        "reason": "unknown_research_finding_citation",
                        "ref_id": str(cite.id),
                    }
                )
                break
        if ok:
            accepted.append(project)
    return accepted, rejected
