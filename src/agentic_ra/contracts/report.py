"""The final-answer contract. This is the ONLY shape the agent may emit
as an answer (CLAUDE.md prompt-injection defense #2)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from agentic_ra.contracts.critic import Citation, Claim


class ResearchReport(BaseModel):
    question: str
    summary: str = Field(min_length=1)
    claims: list[Claim] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)

    def validate_citation_refs(self) -> list[int]:
        """Return claim citation indices with no matching Citation. Not
        raised here — the agent loop decides whether to retry."""
        known = {c.index for c in self.citations}
        return sorted(
            {i for claim in self.claims for i in claim.citation_indices if i not in known}
        )
