"""Dependency wiring. Week 1 needs the LLM client + tool registry; Redis
and the asyncpg pool slot in here in Week 4 without touching routes."""

from __future__ import annotations

from dataclasses import dataclass

import httpx
from anthropic import AsyncAnthropic
from fastapi import Request

from agentic_ra.config import Settings
from agentic_ra.llm.client import LLMClient
from agentic_ra.tools.arxiv import ArxivSearchTool
from agentic_ra.tools.base import ToolRegistry
from agentic_ra.tools.web_search import WebSearchTool


@dataclass
class AppContext:
    settings: Settings
    http: httpx.AsyncClient
    anthropic: AsyncAnthropic
    llm: LLMClient
    registry: ToolRegistry


def build_context(settings: Settings) -> AppContext:
    http = httpx.AsyncClient(timeout=settings.http_timeout_seconds)
    anthropic = AsyncAnthropic(api_key=settings.anthropic_api_key.get_secret_value())
    registry = ToolRegistry(
        [
            WebSearchTool(settings.tavily_api_key.get_secret_value(), http),
            ArxivSearchTool(http),
        ]
    )
    return AppContext(
        settings=settings,
        http=http,
        anthropic=anthropic,
        llm=LLMClient(anthropic),
        registry=registry,
    )


def get_context(request: Request) -> AppContext:
    ctx: AppContext = request.app.state.ctx
    return ctx
