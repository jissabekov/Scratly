"""Compose grounded project offers from opportunities + research findings."""

from __future__ import annotations

from uuid import UUID

from app.contracts import (
    ComposedProjectPacket,
    ProjectCitation,
    ProjectComposeOutput,
)
from app.services.project_citation_gate import filter_grounded_projects


def _seeded_compose(context: dict) -> ProjectComposeOutput:
    opportunities = context.get("opportunities") or []
    findings = context.get("research_findings") or []
    projects: list[ComposedProjectPacket] = []
    for opp in opportunities[:3]:
        opp_id = opp.get("id")
        if not opp_id:
            continue
        citations = [
            ProjectCitation(kind="opportunity", id=UUID(str(opp_id))),
        ]
        if findings:
            fid = findings[0].get("id")
            if fid:
                citations.append(
                    ProjectCitation(kind="research_finding", id=UUID(str(fid)))
                )
        projects.append(
            ComposedProjectPacket(
                title=str(opp.get("title") or "Matched opportunity"),
                summary=str(
                    opp.get("summary")
                    or "A project shaped from a curated local opportunity."
                ),
                topic_keys=list(opp.get("topics") or []),
                work_mode_keys=list(opp.get("work_modes") or []),
                motivation_keys=list(opp.get("motivations") or []),
                citations=citations,
            )
        )
    if not projects:
        raise RuntimeError("no_opportunities_to_compose")
    return ProjectComposeOutput(projects=projects)


class ProjectComposer:
    def __init__(self, llm):
        self.llm = llm

    async def compose(self, context: dict) -> tuple[list[ComposedProjectPacket], list[dict]]:
        opportunity_ids = {
            UUID(str(o["id"])) for o in (context.get("opportunities") or []) if o.get("id")
        }
        research_ids = {
            UUID(str(f["id"]))
            for f in (context.get("research_findings") or [])
            if f.get("id")
        }
        try:
            raw = await self.llm.structured(
                "writer", "project_composer", "v1", ProjectComposeOutput, context
            )
        except Exception:
            raw = _seeded_compose(context)
        return filter_grounded_projects(
            raw,
            opportunity_ids=opportunity_ids,
            research_finding_ids=research_ids,
        )
