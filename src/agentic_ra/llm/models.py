"""Model identifiers and a cost table for per-call accounting (T-1.2).

Prices are USD per 1M tokens (input / output), current published Claude
pricing tiers. Centralised here so cost math has one source of truth and
the Week 1 "p50 cost < $0.15" acceptance gate is measurable.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class ModelName(StrEnum):
    SONNET_4_6 = "claude-sonnet-4-6"
    HAIKU_4_5 = "claude-haiku-4-5-20251001"
    OPUS_4_7 = "claude-opus-4-7"


class Price(BaseModel):
    input_per_mtok: float
    output_per_mtok: float


# Conservative published tier pricing; override via config if it drifts.
COST_TABLE: dict[str, Price] = {
    ModelName.SONNET_4_6: Price(input_per_mtok=3.0, output_per_mtok=15.0),
    ModelName.HAIKU_4_5: Price(input_per_mtok=1.0, output_per_mtok=5.0),
    ModelName.OPUS_4_7: Price(input_per_mtok=15.0, output_per_mtok=75.0),
}


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    price = COST_TABLE.get(model)
    if price is None:
        return 0.0
    return (
        input_tokens / 1_000_000 * price.input_per_mtok
        + output_tokens / 1_000_000 * price.output_per_mtok
    )
