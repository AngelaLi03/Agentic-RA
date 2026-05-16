"""Anthropic SDK wrapper (T-1.2).

Single chokepoint for model calls so retry policy and cost accounting are
applied uniformly. `CostMeter` accumulates per-run spend; the ReAct loop
reads it to enforce / report the cost budget.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from anthropic import AsyncAnthropic
from anthropic.types import Message

from agentic_ra.llm.models import cost_usd
from agentic_ra.llm.retry import llm_retrying
from agentic_ra.logging import get_logger

log = get_logger(__name__)


@dataclass
class CostMeter:
    """Mutable per-run cost accumulator."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_usd: float = 0.0
    calls: int = 0
    _by_model: dict[str, float] = field(default_factory=dict)

    def record(self, model: str, in_tok: int, out_tok: int) -> float:
        c = cost_usd(model, in_tok, out_tok)
        self.input_tokens += in_tok
        self.output_tokens += out_tok
        self.total_usd += c
        self.calls += 1
        self._by_model[model] = self._by_model.get(model, 0.0) + c
        return c


class LLMClient:
    def __init__(self, client: AsyncAnthropic) -> None:
        self._client = client

    async def create(
        self,
        *,
        model: str,
        max_tokens: int,
        system: str,
        tools: list[dict[str, Any]],
        messages: list[dict[str, Any]],
        meter: CostMeter | None = None,
    ) -> tuple[Message, float]:
        """Make one retried Messages call. Returns (message, call_cost_usd)
        and records the cost on `meter` if provided."""

        async for attempt in llm_retrying():
            with attempt:
                resp: Message = await self._client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    system=system,
                    tools=tools,  # type: ignore[arg-type]
                    messages=messages,  # type: ignore[arg-type]
                )

        call_cost = (
            meter.record(model, resp.usage.input_tokens, resp.usage.output_tokens)
            if meter is not None
            else cost_usd(model, resp.usage.input_tokens, resp.usage.output_tokens)
        )
        log.debug(
            "llm_call",
            model=model,
            in_tok=resp.usage.input_tokens,
            out_tok=resp.usage.output_tokens,
            cost_usd=round(call_cost, 6),
        )
        return resp, call_cost
