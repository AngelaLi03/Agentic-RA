"""ReAct trace contracts — the streamed step types and per-run metadata.

`WorkerResult` (a worker's typed output) is a Week 2 addition (T-2.4) and
is intentionally absent here.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from agentic_ra.contracts.report import ResearchReport


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _run_id() -> str:
    return uuid4().hex[:12]


class StepType(StrEnum):
    THOUGHT = "thought"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    FINAL = "final"
    ERROR = "error"


class ToolCall(BaseModel):
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    tool: str
    ok: bool
    content: str
    error: str | None = None


class ReActStep(BaseModel):
    """One streamed step of the loop, emitted over SSE."""

    run_id: str
    iteration: int = Field(ge=0)
    type: StepType
    text: str | None = None
    tool_call: ToolCall | None = None
    tool_result: ToolResult | None = None
    report: ResearchReport | None = None
    cost_usd: float | None = None
    at: datetime = Field(default_factory=_utcnow)


class RunMeta(BaseModel):
    run_id: str = Field(default_factory=_run_id)
    question: str
    model: str
    started_at: datetime = Field(default_factory=_utcnow)
