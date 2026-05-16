"""HTTP surface. `POST /research` streams each `ReActStep` as an SSE
event; the terminal `final` event carries the structured report."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from agentic_ra.agents.base import ReActAgent
from agentic_ra.api.deps import AppContext, get_context
from agentic_ra.api.schemas import ResearchRequest
from agentic_ra.contracts import ReActStep, RunMeta
from agentic_ra.logging import bind_request, clear_request, get_logger

log = get_logger(__name__)
router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


def _sse(step: ReActStep) -> dict[str, Any]:
    return {"event": step.type.value, "data": step.model_dump_json()}


@router.post("/research")
async def research(
    req: ResearchRequest,
    ctx: Annotated[AppContext, Depends(get_context)],
) -> EventSourceResponse:
    settings = ctx.settings
    agent = ReActAgent(
        llm=ctx.llm,
        tools=ctx.registry,
        model=settings.agent_model,
        max_iterations=req.max_iterations or settings.agent_max_iterations,
    )
    meta = RunMeta(question=req.question, model=settings.agent_model)
    bind_request(meta.run_id)
    log.info("research_request", question=req.question)

    async def event_stream() -> AsyncIterator[dict[str, Any]]:
        try:
            yield {"event": "run_started", "data": meta.model_dump_json()}
            async for step in agent.run(meta):
                yield _sse(step)
        except Exception as e:  # noqa: BLE001
            log.error("stream_failed", error=str(e))
            yield {
                "event": "error",
                "data": json.dumps({"run_id": meta.run_id, "error": str(e)}),
            }
        finally:
            yield {"event": "done", "data": json.dumps({"run_id": meta.run_id})}
            clear_request()

    return EventSourceResponse(event_stream())
