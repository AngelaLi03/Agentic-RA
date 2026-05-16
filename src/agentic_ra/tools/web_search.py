"""Tavily web search. Returns fenced, untrusted results."""

from __future__ import annotations

from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from agentic_ra.tools.base import Tool

TAVILY_ENDPOINT = "https://api.tavily.com/search"


def fence(source: str, content: str) -> str:
    """Wrap untrusted external content (CLAUDE.md defense #1). The model is
    instructed to treat anything inside these tags as data, never
    instructions."""
    return f"<untrusted_source origin={source!r}>\n{content}\n</untrusted_source>"


class WebSearchTool(Tool):
    name = "web_search"
    description = (
        "Search the public web for current information. Use for recent "
        "events, docs, blog posts, or anything not specific to arXiv. "
        "Returns titles, URLs, and content snippets."
    )

    def __init__(self, api_key: str, client: httpx.AsyncClient, max_results: int = 5) -> None:
        self._api_key = api_key
        self._client = client
        self._max_results = max_results

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query."},
            },
            "required": ["query"],
        }

    @retry(
        retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, max=8),
        reraise=True,
    )
    async def _call(self, query: str) -> dict[str, Any]:
        resp = await self._client.post(
            TAVILY_ENDPOINT,
            json={
                "api_key": self._api_key,
                "query": query,
                "max_results": self._max_results,
                "search_depth": "basic",
            },
        )
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        return data

    async def run(self, **kwargs: Any) -> str:
        query = str(kwargs.get("query", "")).strip()
        if not query:
            return "ERROR: empty query"

        data = await self._call(query)
        results = data.get("results", [])
        if not results:
            return fence("web_search", f"No results for: {query}")

        lines: list[str] = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "(untitled)")
            url = r.get("url", "")
            snippet = (r.get("content") or "").strip().replace("\n", " ")[:500]
            lines.append(f"[{i}] {title}\n    url: {url}\n    {snippet}")

        return fence("web_search", "\n".join(lines))
