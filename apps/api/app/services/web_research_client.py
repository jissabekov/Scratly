"""Bounded web research: Azure Responses web_search tool or a direct search API.

Provider abstraction (Plan 01 W1.3): the Responses-API path is kept for
resources that support it; the default path is a config-driven direct search
API (tavily | brave | bing) with the same ``ResearchFindingPacket`` output so
the citation gate is unchanged. Queries run concurrently with a 12s bound and
partial success is retained.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.config import get_settings
from app.contracts import ResearchFindingPacket


def build_research_queries(profile: dict[str, Any], geo: dict[str, list[str]]) -> list[str]:
    topics = profile.get("topics") or []
    topic = topics[0] if topics else "student project"
    place = (geo.get("geo_places") or geo.get("geo_regions") or ["local"])[0]
    place = str(place).replace("_", " ")
    base = f"{topic} {place} youth OR student project OR internship OR open data OR community challenge"
    queries = [base]
    if len(topics) > 1:
        queries.append(f"{topics[1]} {place} student OR youth community project")
    if "remote_ok" in (geo.get("geo_regions") or []):
        queries.append(f"{topic} remote student open source OR open data project")
    return queries[:3]


def findings_from_web_response(response: Any) -> list[ResearchFindingPacket]:
    """Normalize citations/sources from a Responses API web_search result."""
    findings: list[ResearchFindingPacket] = []
    seen: set[str] = set()

    def add(
        url: str, title: str = "", snippet: str = "", publisher: str | None = None, rank: int = 0
    ):
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
        item_type = getattr(item, "type", None) or (
            item.get("type") if isinstance(item, dict) else None
        )
        if item_type == "web_search_call":
            action = getattr(item, "action", None) or (
                item.get("action") if isinstance(item, dict) else None
            )
            sources: list[Any] = []
            if action is not None:
                sources = (
                    getattr(action, "sources", None)
                    or (action.get("sources") if isinstance(action, dict) else [])
                    or []
                )
            for src in sources or []:
                url = getattr(src, "url", None) or (
                    src.get("url") if isinstance(src, dict) else None
                )
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
        settings = get_settings()
        self._provider = (settings.web_research_provider or "").strip().lower()
        self._api_key = (settings.web_research_api_key or "").strip()

    @property
    def configured(self) -> bool:
        if self._direct_configured:
            return True
        return self._responses_available

    @property
    def _responses_available(self) -> bool:
        return hasattr(self.llm, "web_search") and callable(getattr(self.llm, "web_search", None))

    @property
    def _direct_configured(self) -> bool:
        return bool(self._provider) and bool(self._api_key)

    async def research(
        self,
        *,
        profile: dict[str, Any],
        geo: dict[str, list[str]],
        user_location: dict[str, Any] | None = None,
    ) -> tuple[list[str], list[ResearchFindingPacket], str | None]:
        """Return (queries, findings, error_type)."""
        queries = build_research_queries(profile, geo)
        if not self._direct_configured and not self._responses_available:
            return queries, [], "web_search_unconfigured"

        async def run(query: str):
            try:
                if self._responses_available and not self._direct_configured:
                    response = await asyncio.wait_for(
                        self.llm.web_search(query, user_location=user_location or {}),
                        timeout=12,
                    )
                    return findings_from_web_response(response), None
                response = await asyncio.wait_for(
                    _search_api_query(self._provider, self._api_key, query),
                    timeout=12,
                )
                return _findings_from_search_api(response), None
            except Exception as exc:
                return [], type(exc).__name__

        # Queries are independent. Parallel execution both lowers matching latency and
        # lets one provider/query failure coexist with useful results from another.
        results = await asyncio.gather(*(run(query) for query in queries))
        all_findings: list[ResearchFindingPacket] = []
        errors: list[str] = []
        for findings, error in results:
            all_findings.extend(findings)
            if error:
                errors.append(error)
        # Dedupe by URL preserving order
        seen: set[str] = set()
        unique: list[ResearchFindingPacket] = []
        for f in all_findings:
            if f.url in seen:
                continue
            seen.add(f.url)
            unique.append(f)
        error = ",".join(sorted(set(errors))) if errors and not unique else None
        return queries, unique[:12], error


_SEARCH_ENDPOINTS = {
    "tavily": "https://api.tavily.com/search",
    "brave": "https://api.search.brave.com/res/v1/web/search",
    "bing": "https://api.bing.microsoft.com/v7.0/search",
}


async def _search_api_query(provider: str, api_key: str, query: str) -> list[ResearchFindingPacket]:
    """Query a direct search API and normalize results to ResearchFindingPacket."""
    headers: dict[str, str] = {}
    params: dict[str, Any] = {}
    if provider == "tavily":
        headers["Authorization"] = f"Bearer {api_key}"
        payload = {"query": query, "max_results": 6}
    elif provider == "brave":
        headers["X-Subscription-Token"] = api_key
        params = {"q": query, "count": 8}
    elif provider == "bing":
        headers["Ocp-Apim-Subscription-Key"] = api_key
        params = {"q": query, "responseFilter": "webpages", "count": 8}
    else:
        raise ValueError(f"unsupported_web_research_provider:{provider}")
    async with httpx.AsyncClient(timeout=10) as client:
        if provider == "tavily":
            resp = await client.post(_SEARCH_ENDPOINTS[provider], json=payload, headers=headers)
        else:
            resp = await client.get(_SEARCH_ENDPOINTS[provider], params=params, headers=headers)
        resp.raise_for_status()
        return _findings_from_search_api(resp.json())


def _findings_from_search_api(payload: dict[str, Any]) -> list[ResearchFindingPacket]:
    """Normalize tavily/brave/bing JSON into ResearchFindingPacket rows."""
    findings: list[ResearchFindingPacket] = []
    seen: set[str] = set()

    def add(url: str, title: str = "", snippet: str = "", rank: int = 0) -> None:
        url = (url or "").strip()
        if not url or url in seen:
            return
        seen.add(url)
        findings.append(ResearchFindingPacket(url=url, title=title, snippet=snippet, rank=rank))

    for i, item in enumerate((payload or {}).get("results") or [], start=1):
        add(
            str(item.get("url") or ""),
            title=str(item.get("title") or ""),
            snippet=str(item.get("content") or item.get("description") or ""),
            rank=i,
        )
    web = (payload.get("web") or {}).get("value") if isinstance(payload.get("web"), dict) else None
    for i, item in enumerate(web or [], start=1):
        add(str(item.get("url") or ""), title=str(item.get("name") or ""), rank=i)
    for i, item in enumerate(payload.get("webPages", {}).get("value", []) or [], start=1):
        add(str(item.get("url") or ""), title=str(item.get("name") or ""), rank=i)
    return findings
