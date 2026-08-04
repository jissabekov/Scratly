"""Citation gate for composed projects."""

from __future__ import annotations

from uuid import UUID

from app.contracts import ComposedProjectPacket, ProjectComposeOutput


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
    for project in output.projects:
        if profile_topics and not (profile_topics & set(project.topic_keys)):
            rejected.append(
                {"title": project.title, "reason": "profile_topic_mismatch"}
            )
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
