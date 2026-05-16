"""Tool protocol + registry.

Each tool exposes an Anthropic-tool-use JSON schema and an async `run`.
The registry doubles as the per-role allow-list (CLAUDE.md defense #3):
an agent only ever sees the tools registered for it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Tool(ABC):
    name: str
    description: str

    @property
    @abstractmethod
    def input_schema(self) -> dict[str, Any]:
        """JSON schema for the tool's arguments (Anthropic tool-use format)."""

    @abstractmethod
    async def run(self, **kwargs: Any) -> str:
        """Execute and return a string result.

        Returned content is UNTRUSTED. Callers must fence it before it ever
        re-enters the model context (CLAUDE.md defense #1)."""

    def to_anthropic(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


class ToolRegistry:
    def __init__(self, tools: list[Tool]) -> None:
        self._tools: dict[str, Tool] = {}
        for t in tools:
            if t.name in self._tools:
                raise ValueError(f"duplicate tool name: {t.name}")
            self._tools[t.name] = t

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def specs(self) -> list[dict[str, Any]]:
        return [t.to_anthropic() for t in self._tools.values()]

    def __len__(self) -> int:
        return len(self._tools)
