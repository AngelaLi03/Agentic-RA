"""ReAct loop primitives + the Week 1 single-agent implementation.

`AgentBase` factors out what Week 2's Planner/Worker/Critic will share.
`ReActAgent` drives the Anthropic Messages API with native tool use and
ends a run by calling the `submit_report` pseudo-tool, whose arguments are
parsed into a `ResearchReport`. Final answers are therefore structured-only
— no free text from a fetched page can become the answer (CLAUDE.md
defense #2).

`run()` is an async generator of `ReActStep`s so the API layer can stream
the agent's reasoning over SSE.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from pydantic import ValidationError

from agentic_ra.agents.prompts import load_prompt
from agentic_ra.contracts import (
    Citation,
    Claim,
    ReActStep,
    ResearchReport,
    RunMeta,
    StepType,
    ToolCall,
    ToolResult,
)
from agentic_ra.llm.client import CostMeter, LLMClient
from agentic_ra.logging import get_logger
from agentic_ra.tools.base import ToolRegistry

log = get_logger(__name__)

MAX_TOKENS = 4096

SUBMIT_REPORT_TOOL: dict[str, Any] = {
    "name": "submit_report",
    "description": (
        "Submit the final structured research report. Call this exactly "
        "once when you have enough evidence. This ends the task."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "claims": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "citation_indices": {
                            "type": "array",
                            "items": {"type": "integer", "minimum": 1},
                        },
                    },
                    "required": ["text", "citation_indices"],
                },
            },
            "citations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "index": {"type": "integer", "minimum": 1},
                        "title": {"type": "string"},
                        "url": {"type": "string"},
                        "snippet": {"type": "string"},
                    },
                    "required": ["index", "title", "url", "snippet"],
                },
            },
        },
        "required": ["summary", "claims", "citations"],
    },
}


class AgentBase:
    """Shared construction surface for all agent roles."""

    def __init__(
        self,
        llm: LLMClient,
        tools: ToolRegistry,
        model: str,
        max_iterations: int = 8,
    ) -> None:
        self._llm = llm
        self._tools = tools
        self._model = model
        self._max_iterations = max_iterations


class ReActAgent(AgentBase):
    async def run(self, meta: RunMeta) -> AsyncIterator[ReActStep]:
        rid = meta.run_id
        meter = CostMeter()
        system = load_prompt("react_system")
        messages: list[dict[str, Any]] = [{"role": "user", "content": meta.question}]
        tool_specs = [*self._tools.specs(), SUBMIT_REPORT_TOOL]

        for it in range(self._max_iterations):
            try:
                resp, _ = await self._llm.create(
                    model=self._model,
                    max_tokens=MAX_TOKENS,
                    system=system,
                    tools=tool_specs,
                    messages=messages,
                    meter=meter,
                )
            except Exception as e:  # noqa: BLE001 — surface as a stream step
                log.error("anthropic_call_failed", iteration=it, error=str(e))
                yield ReActStep(
                    run_id=rid, iteration=it, type=StepType.ERROR,
                    text=f"model call failed: {e}", cost_usd=meter.total_usd,
                )
                return

            assistant_content: list[dict[str, Any]] = []
            tool_uses: list[Any] = []

            for block in resp.content:
                if block.type == "text" and block.text.strip():
                    assistant_content.append({"type": "text", "text": block.text})
                    yield ReActStep(
                        run_id=rid, iteration=it, type=StepType.THOUGHT,
                        text=block.text.strip(),
                    )
                elif block.type == "tool_use":
                    assistant_content.append(
                        {
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        }
                    )
                    tool_uses.append(block)

            messages.append({"role": "assistant", "content": assistant_content})

            if not tool_uses:
                yield ReActStep(
                    run_id=rid, iteration=it, type=StepType.ERROR,
                    text="model did not call a tool; requesting structured report",
                )
                messages.append(
                    {
                        "role": "user",
                        "content": "Call `submit_report` now with what you have.",
                    }
                )
                continue

            tool_results_content: list[dict[str, Any]] = []

            for tu in tool_uses:
                args: dict[str, Any] = tu.input or {}

                if tu.name == "submit_report":
                    report, err = _parse_report(meta.question, args)
                    if report is not None:
                        log.info(
                            "run_complete", iterations=it + 1,
                            claims=len(report.claims),
                            citations=len(report.citations),
                            cost_usd=round(meter.total_usd, 6),
                            llm_calls=meter.calls,
                        )
                        yield ReActStep(
                            run_id=rid, iteration=it, type=StepType.FINAL,
                            report=report, cost_usd=meter.total_usd,
                        )
                        return
                    yield ReActStep(
                        run_id=rid, iteration=it, type=StepType.ERROR,
                        text=f"invalid report: {err}",
                    )
                    tool_results_content.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tu.id,
                            "content": f"Report rejected: {err}. Fix and resubmit.",
                            "is_error": True,
                        }
                    )
                    continue

                yield ReActStep(
                    run_id=rid, iteration=it, type=StepType.TOOL_CALL,
                    tool_call=ToolCall(tool=tu.name, arguments=args),
                )

                tool = self._tools.get(tu.name)
                if tool is None:
                    out, ok, errmsg = f"unknown tool: {tu.name}", False, "unknown tool"
                else:
                    try:
                        out = await tool.run(**args)
                        ok, errmsg = True, None
                    except Exception as e:  # noqa: BLE001
                        out, ok, errmsg = f"tool error: {e}", False, str(e)
                        log.warning("tool_failed", tool=tu.name, error=str(e))

                yield ReActStep(
                    run_id=rid, iteration=it, type=StepType.TOOL_RESULT,
                    tool_result=ToolResult(
                        tool=tu.name, ok=ok, content=out, error=errmsg
                    ),
                )
                tool_results_content.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tu.id,
                        "content": out,
                        "is_error": not ok,
                    }
                )

            messages.append({"role": "user", "content": tool_results_content})

        log.warning("max_iterations_reached", limit=self._max_iterations)
        yield ReActStep(
            run_id=rid, iteration=self._max_iterations, type=StepType.ERROR,
            text=f"max iterations ({self._max_iterations}) reached without a report",
            cost_usd=meter.total_usd,
        )


def _parse_report(
    question: str, args: dict[str, Any]
) -> tuple[ResearchReport | None, str | None]:
    try:
        citations = [Citation(**c) for c in args.get("citations", [])]
        claims = [Claim(**c) for c in args.get("claims", [])]
        report = ResearchReport(
            question=question,
            summary=args.get("summary", ""),
            claims=claims,
            citations=citations,
        )
    except ValidationError as e:
        return None, str(e)

    dangling = report.validate_citation_refs()
    if dangling:
        return None, f"claims reference unknown citation indices: {dangling}"
    return report, None
