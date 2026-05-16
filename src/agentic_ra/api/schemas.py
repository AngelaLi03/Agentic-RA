"""Inbound/outbound API models. Kept separate from `contracts/` because
these are transport-shaped (HTTP request bodies), not agent-boundary
types."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class ResearchRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    max_iterations: int | None = Field(default=None, ge=1, le=20)

    @field_validator("question")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("question must not be blank")
        return v
