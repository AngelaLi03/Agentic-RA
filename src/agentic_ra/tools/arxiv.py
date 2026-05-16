"""arXiv search via the public Atom API. No key required."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from agentic_ra.tools.base import Tool
from agentic_ra.tools.web_search import fence

ARXIV_ENDPOINT = "http://export.arxiv.org/api/query"
_ATOM = "{http://www.w3.org/2005/Atom}"


class ArxivSearchTool(Tool):
    name = "arxiv_search"
    description = (
        "Search arXiv for academic papers. Use for ML/CS research, "
        "methods, and citable scientific results. Returns title, authors, "
        "abstract, and the arXiv abstract URL."
    )

    def __init__(self, client: httpx.AsyncClient, max_results: int = 5) -> None:
        self._client = client
        self._max_results = max_results

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query / keywords."},
            },
            "required": ["query"],
        }

    @retry(
        retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, max=8),
        reraise=True,
    )
    async def _call(self, query: str) -> str:
        resp = await self._client.get(
            ARXIV_ENDPOINT,
            params={
                "search_query": f"all:{query}",
                "start": 0,
                "max_results": self._max_results,
                "sortBy": "relevance",
            },
        )
        resp.raise_for_status()
        return resp.text

    async def run(self, **kwargs: Any) -> str:
        query = str(kwargs.get("query", "")).strip()
        if not query:
            return "ERROR: empty query"

        xml = await self._call(query)
        try:
            root = ET.fromstring(xml)
        except ET.ParseError as e:
            return f"ERROR: failed to parse arXiv response: {e}"

        entries = root.findall(f"{_ATOM}entry")
        if not entries:
            return fence("arxiv", f"No papers for: {query}")

        lines: list[str] = []
        for i, entry in enumerate(entries, 1):
            title = (entry.findtext(f"{_ATOM}title") or "(untitled)").strip()
            summary = (
                (entry.findtext(f"{_ATOM}summary") or "").strip().replace("\n", " ")[:600]
            )
            url = (entry.findtext(f"{_ATOM}id") or "").strip()
            authors = [
                (a.findtext(f"{_ATOM}name") or "").strip()
                for a in entry.findall(f"{_ATOM}author")
            ]
            author_str = ", ".join(a for a in authors[:5] if a) or "unknown"
            lines.append(
                f"[{i}] {title}\n    authors: {author_str}\n"
                f"    url: {url}\n    abstract: {summary}"
            )

        return fence("arxiv", "\n\n".join(lines))
