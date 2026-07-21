"""Bounded web research via Azure Responses API web_search tool."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from app.contracts import ResearchFindingPacket


def build_research_queries(profile: dict[str, Any], geo: dict[str, list[str]]) -> list[str]:
    topics = profile.get("topics") or []
    topic = topics[0] if topics else "student project"
    place = (geo.get("geo_places") or geo.get("geo_regions") or ["local"])[0]
    place = str(place).replace("_", " ")
    base = f"{topic} {place} youth OR student project OR internship OR open data OR community challenge"
    queries = [base]
    if len(topics) > 1:
        queries.append(
            f"{topics[1]} {place} student OR youth community project"
        )
    if "remote_ok" in (geo.get("geo_regions") or []):
        queries.append(f"{topic} remote student open source OR open data project")
    return queries[:3]


def findings_from_web_response(response: Any) -> list[ResearchFindingPacket]:
    """Normalize citations/sources from a Responses API web_search result."""
    findings: list[ResearchFindingPacket] = []
    seen: set[str] = set()

    def add(url: str, title: str = "", snippet: str = "", publisher: str | None = None, rank: int = 0):
        url = (url or "").strip()
        if not url or url in seen:
            return
        seen.add(url)
        findings.append(
            ResearchFindingPacket(
                url=url,
                title=title or "",
                snippet=snippet or "",
                publisher=publisher,
                rank=rank,
            )
        )

    # Prefer explicit include sources if present.
    output = getattr(response, "output", None) or []
    rank = 0
    for item in output:
        item_type = getattr(item, "type", None) or (item.get("type") if isinstance(item, dict) else None)
        if item_type == "web_search_call":
            action = getattr(item, "action", None) or (
                item.get("action") if isinstance(item, dict) else None
            )
            sources = []
            if action is not None:
                sources = getattr(action, "sources", None) or (
                    action.get("sources") if isinstance(action, dict) else []
                ) or []
            for src in sources or []:
                url = getattr(src, "url", None) or (src.get("url") if isinstance(src, dict) else None)
                rank += 1
                add(str(url or ""), rank=rank)
        if item_type == "message":
            content = getattr(item, "content", None) or (
                item.get("content") if isinstance(item, dict) else []
            )
            for block in content or []:
                annotations = getattr(block, "annotations", None) or (
                    block.get("annotations") if isinstance(block, dict) else []
                )
                for ann in annotations or []:
                    ann_type = getattr(ann, "type", None) or (
                        ann.get("type") if isinstance(ann, dict) else None
                    )
                    if ann_type == "url_citation":
                        url = getattr(ann, "url", None) or (
                            ann.get("url") if isinstance(ann, dict) else None
                        )
                        title = getattr(ann, "title", None) or (
                            ann.get("title") if isinstance(ann, dict) else ""
                        )
                        rank += 1
                        add(str(url or ""), title=str(title or ""), rank=rank)
    return findings


class WebResearchClient:
    """Runs ≤3 bounded web_search queries; never mutates profile."""

    def __init__(self, llm):
        self.llm = llm

    @property
    def configured(self) -> bool:
        return hasattr(self.llm, "web_search") and callable(
            getattr(self.llm, "web_search", None)
        )

    async def research(
        self,
        *,
        profile: dict[str, Any],
        geo: dict[str, list[str]],
        user_location: dict[str, Any] | None = None,
    ) -> tuple[list[str], list[ResearchFindingPacket], str | None]:
        """Return (queries, findings, error_type)."""
        queries = build_research_queries(profile, geo)
        if not self.configured:
            return queries, [], "web_search_unconfigured"
        all_findings: list[ResearchFindingPacket] = []
        error: str | None = None
        for query in queries:
            try:
                response = await self.llm.web_search(
                    query, user_location=user_location or {}
                )
                all_findings.extend(findings_from_web_response(response))
            except Exception as exc:
                error = type(exc).__name__
                break
        # Dedupe by URL preserving order
        seen: set[str] = set()
        unique: list[ResearchFindingPacket] = []
        for f in all_findings:
            if f.url in seen:
                continue
            seen.add(f.url)
            unique.append(f)
        return queries, unique[:12], error
