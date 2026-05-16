"""Claim-level evidence contracts.

`Claim` and `Citation` live here because Week 2's Critic
(`agents/critic.py`) is their primary consumer — it verifies each claim
against its cited sources. Keeping them atomic now makes that tractable.
`CriticVerdict` is intentionally NOT defined yet (Week 2 / T-2.5).
"""

from __future__ import annotations

from pydantic import BaseModel, Field, HttpUrl, field_validator


class Citation(BaseModel):
    """A source the agent actually consulted. `index` is the [n] marker
    referenced inline by claims. `snippet` is mandatory — Week 1 acceptance
    requires every citation to carry URL + snippet."""

    index: int = Field(ge=1)
    title: str = Field(min_length=1)
    url: HttpUrl
    snippet: str = Field(min_length=1, max_length=2000)


class Claim(BaseModel):
    """An atomic factual statement plus the citation indices that back it."""

    text: str = Field(min_length=1)
    citation_indices: list[int] = Field(default_factory=list)

    @field_validator("citation_indices")
    @classmethod
    def _positive(cls, v: list[int]) -> list[int]:
        if any(i < 1 for i in v):
            raise ValueError("citation indices are 1-based")
        return v
