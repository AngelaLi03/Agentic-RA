"""T-1.8 smoke harness: 5 hand-picked questions end-to-end against the
real model. Opt-in — costs money and needs live keys. Run with:

    RUN_SMOKE=1 pytest tests/integration -m smoke -s

Asserts the Week 1 acceptance gates: a valid `ResearchReport`, every
citation carries URL + snippet, loop hard-caps at max_steps, and p50 cost
per query < $0.15.
"""

from __future__ import annotations

import os
import statistics

import httpx
import pytest
from anthropic import AsyncAnthropic

from agentic_ra.agents.base import ReActAgent
from agentic_ra.config import get_settings
from agentic_ra.contracts import RunMeta, StepType
from agentic_ra.llm.client import LLMClient
from agentic_ra.tools.arxiv import ArxivSearchTool
from agentic_ra.tools.base import ToolRegistry
from agentic_ra.tools.web_search import WebSearchTool

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.skipif(
        not os.getenv("RUN_SMOKE"), reason="set RUN_SMOKE=1 to run live smoke tests"
    ),
]

QUESTIONS = [
    "What is retrieval-augmented generation and why is it used?",
    "What recent arXiv papers compare ReAct and Reflexion for agents?",
    "What is the difference between Cohen's kappa and Fleiss' kappa?",
    "What are the main prompt-injection defenses for LLM agents?",
    "What did the 2017 'Attention Is All You Need' paper introduce?",
]

MAX_STEPS = 6
COST_BUDGET_P50 = 0.15


@pytest.mark.asyncio
async def test_smoke_five_questions() -> None:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as http:
        anthropic = AsyncAnthropic(
            api_key=settings.anthropic_api_key.get_secret_value()
        )
        registry = ToolRegistry(
            [
                WebSearchTool(settings.tavily_api_key.get_secret_value(), http),
                ArxivSearchTool(http),
            ]
        )
        agent = ReActAgent(
            llm=LLMClient(anthropic),
            tools=registry,
            model=settings.agent_model,
            max_iterations=MAX_STEPS,
        )

        costs: list[float] = []
        for q in QUESTIONS:
            meta = RunMeta(question=q, model=settings.agent_model)
            final = None
            steps = 0
            async for step in agent.run(meta):
                steps += 1
                if step.type is StepType.FINAL:
                    final = step
            assert step.iteration <= MAX_STEPS, f"loop exceeded cap on: {q}"
            assert final is not None, f"no report produced for: {q}"
            report = final.report
            assert report is not None and report.summary
            for c in report.citations:
                assert str(c.url).startswith("http")
                assert c.snippet.strip(), "citation missing snippet"
            assert final.cost_usd is not None
            costs.append(final.cost_usd)

        await anthropic.close()

    p50 = statistics.median(costs)
    print(f"\nsmoke costs={[round(c, 4) for c in costs]} p50=${p50:.4f}")
    assert p50 < COST_BUDGET_P50, f"p50 cost ${p50:.4f} exceeds ${COST_BUDGET_P50}"
